"""
Part-11/test_idempotency.py -- DATA-260 HW8, Part 3.I (duplicate delivery)

Sends one task message, lets a consumer agent process it (real Kafka,
real run_consumer_agent -- the same shared loop planner/writer/reviewer
use, with real idempotency built in: an in-memory seen_correlation_ids
set), then REPLAYS the exact same message (same correlation_id) and shows
it gets dropped with no second side effect (no second "processed" count
increment, no second message on the output topic).

Uses its own throwaway topic pair (not s1808_tasks/s1808_drafts) so this
test doesn't interfere with the live Planner/Writer/Reviewer pipeline,
and a trivial process() function (not a real model call) since
idempotency is a property of the Kafka consumption pattern, independent
of what the handler does with each message.

Run (Kafka must already be up):
    python test_idempotency.py
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import uuid

from kafka_utils import make_consumer, make_producer, run_consumer_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s TEST %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("test_idempotency")

IN_TOPIC = "s1808_idempotency_in"
OUT_TOPIC = "s1808_idempotency_out"

process_call_count = 0


def process(message: dict) -> dict:
    global process_call_count
    process_call_count += 1
    return {"echo": message["payload"], "processed_count_at_handling_time": process_call_count}


def _run_agent_in_background():
    agent_log = logging.getLogger("test_idempotency.agent")
    run_consumer_agent(agent_log, IN_TOPIC, OUT_TOPIC, "s1808_idempotency_test", process)


def main() -> None:
    from kafka.admin import KafkaAdminClient, NewTopic

    admin = KafkaAdminClient(bootstrap_servers="localhost:9092")
    try:
        admin.create_topics([
            NewTopic(name=IN_TOPIC, num_partitions=1, replication_factor=1),
            NewTopic(name=OUT_TOPIC, num_partitions=1, replication_factor=1),
        ])
    except Exception as exc:  # noqa: BLE001 -- topic may already exist from a prior run
        log.info("topic creation note: %s", exc)
    admin.close()

    agent_thread = threading.Thread(target=_run_agent_in_background, daemon=True)
    agent_thread.start()
    time.sleep(4)  # let the agent's consumer group finish its join/sync

    producer = make_producer()
    out_consumer = make_consumer(OUT_TOPIC, f"s1808_test_reader_{uuid.uuid4().hex}", auto_offset_reset="latest")

    correlation_id = str(uuid.uuid4())
    message = {"correlation_id": correlation_id, "payload": "original payload"}

    log.info("--- first send (correlation_id=%s) ---", correlation_id)
    producer.send(IN_TOPIC, value=message)
    producer.flush()

    first_result = None
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and first_result is None:
        batches = out_consumer.poll(timeout_ms=500)
        for records in batches.values():
            for r in records:
                if r.value.get("correlation_id") == correlation_id:
                    first_result = r.value
    log.info("first processing result: %s", first_result)
    log.info("process() call count after first send: %d", process_call_count)

    log.info("--- REPLAY: same message, same correlation_id ---")
    producer.send(IN_TOPIC, value=message)
    producer.flush()
    time.sleep(3)

    replay_result = None
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        batches = out_consumer.poll(timeout_ms=500)
        for records in batches.values():
            for r in records:
                if r.value.get("correlation_id") == correlation_id and r.value != first_result:
                    replay_result = r.value

    log.info("process() call count after replay: %d (expected: still %d -- no second call)", process_call_count, process_call_count)
    log.info("second output message produced by the replay: %s (expected: None)", replay_result)

    assert process_call_count == 1, "idempotency failed: process() was called more than once"
    assert replay_result is None, "idempotency failed: the replay produced a second output message"
    log.info("PASS: replay was dropped before reaching process() -- no second side effect.")


if __name__ == "__main__":
    main()
