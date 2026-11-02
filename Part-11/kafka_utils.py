"""
Part-11/kafka_utils.py -- DATA-260 HW8, Parts 2-3 (shared agent-loop helper)

run_consumer_agent(...) is the shared shape every agent in this pipeline
(planner.py, writer.py, reviewer.py) follows: consume one message from
`in_topic`, call `process(message) -> dict | None`, and if it returned
something, produce it to `out_topic` with the same correlation_id. None
means "drop this message" (used for duplicate detection below).

Part 3 behaviors built into this shared loop, not bolted on as separate
test-only code:

  - Idempotency (3.I): an in-memory `seen_correlation_ids` set. A
    correlation_id already seen is logged and dropped -- process() is
    never called again for it, so a replayed message has no side effect
    (no second model call, no second message published).

  - Manual offset commit (3.II): enable_auto_commit=False: the consumer
    only commits a message's offset AFTER it has been fully processed and
    (if applicable) the result published -- never on a timer inside
    poll(), which is what let an earlier design auto-commit an offset for
    a message whose handler hadn't actually finished (or hadn't even
    started) if the process was killed between the commit and the work.

  - Bounded retries + dead-letter (3.III): process() exceptions are
    retried up to MAX_RETRIES times with a short backoff; still failing
    after that, the original message is forwarded to
    PREFIX_dead_letter (with the final error attached) and its offset is
    committed anyway, so one poison message can't block everything behind
    it on the same partition forever.

wait_for_assignment exists because a single poll() does not reliably
complete a consumer group's join/sync rebalance against this broker --
confirmed empirically in Part 1 (~7 polls, ~3.5s).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

from kafka import KafkaConsumer, KafkaProducer
from kafka_config import BOOTSTRAP_SERVERS

MAX_RETRIES = 3
RETRY_BACKOFF_S = 0.5
DEAD_LETTER_TOPIC = "s1808_dead_letter"


def wait_for_assignment(consumer: KafkaConsumer, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        consumer.poll(timeout_ms=300)
        if consumer.assignment():
            return
    raise TimeoutError("consumer group never completed its partition assignment")


def make_consumer(
    topic: str, group_id: str, auto_offset_reset: str = "earliest", enable_auto_commit: bool = False
) -> KafkaConsumer:
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=enable_auto_commit,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    wait_for_assignment(consumer)
    return consumer


def make_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def run_consumer_agent(
    log: logging.Logger,
    in_topic: str,
    out_topic: str,
    group_id: str,
    process: Callable[[dict], Optional[dict]],
    *,
    enable_dead_letter: bool = True,
) -> None:
    consumer = make_consumer(in_topic, group_id, enable_auto_commit=False)
    producer = make_producer()
    seen_correlation_ids: set[str] = set()
    log.info("ready and listening on %s...", in_topic)

    # Explicit poll() loop, not `for msg in consumer:` -- mixing the
    # iterator protocol with wait_for_assignment()'s manual poll() calls
    # (inside make_consumer) was already confirmed in Part 1 to silently
    # stop yielding messages in this exact environment. Every consumer in
    # this codebase uses explicit poll() now for that reason.
    pending_messages = []
    while True:
        if not pending_messages:
            batches = consumer.poll(timeout_ms=500)
            for records in batches.values():
                pending_messages.extend(records)
            if not pending_messages:
                continue
        msg = pending_messages.pop(0)
        message = msg.value
        correlation_id = message.get("correlation_id")

        if correlation_id in seen_correlation_ids:
            log.info("DUPLICATE detected, dropping (no side effect): correlation_id=%s", correlation_id)
            consumer.commit()
            continue

        log.info("received from %s: correlation_id=%s", in_topic, correlation_id)

        result = None
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = process(message)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 -- must classify + retry/dead-letter, never crash the loop
                last_error = exc
                log.warning(
                    "processing failed (attempt %d/%d) for correlation_id=%s: %s",
                    attempt, MAX_RETRIES, correlation_id, exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_S)

        if last_error is not None:
            if enable_dead_letter:
                producer.send(DEAD_LETTER_TOPIC, value={
                    "correlation_id": correlation_id,
                    "original_topic": in_topic,
                    "original_message": message,
                    "error": str(last_error),
                    "retries": MAX_RETRIES,
                })
                producer.flush()
                log.error(
                    "exhausted %d retries, sent to %s: correlation_id=%s",
                    MAX_RETRIES, DEAD_LETTER_TOPIC, correlation_id,
                )
            seen_correlation_ids.add(correlation_id)
            consumer.commit()
            continue

        seen_correlation_ids.add(correlation_id)

        if result is None:
            log.info("dropped message (process() returned None): correlation_id=%s", correlation_id)
            consumer.commit()
            continue

        result.setdefault("correlation_id", correlation_id)
        producer.send(out_topic, value=result)
        producer.flush()
        consumer.commit()
        log.info("sent to %s: correlation_id=%s", out_topic, correlation_id)
