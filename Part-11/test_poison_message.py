"""
Part-11/test_poison_message.py -- DATA-260 HW8, Part 3.III (poison message)

Sends one malformed ("poison") message that deterministically makes
process() raise, followed by a normal, well-formed message. Shows that
the poison message is retried up to MAX_RETRIES (kafka_utils.py), then
forwarded to s1808_dead_letter with its error attached -- and critically,
that the well-formed message sent right after it is NOT blocked and
still gets processed normally, proving one bad message can't jam the
rest of the topic forever.

Uses its own throwaway topic pair, same reasoning as test_idempotency.py.

Run (Kafka must already be up, s1808_dead_letter topic already created):
    python test_poison_message.py
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid

from kafka import KafkaConsumer
from kafka_config import BOOTSTRAP_SERVERS
from kafka_utils import make_consumer, make_producer, run_consumer_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s TEST %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("test_poison_message")

IN_TOPIC = "s1808_poison_in"
OUT_TOPIC = "s1808_poison_out"
DEAD_LETTER_TOPIC = "s1808_dead_letter"


def process(message: dict) -> dict:
    # Deterministically poison: this message has no "payload" key at all,
    # so this raises KeyError every single retry -- a real, reproducible
    # failure, not a flaky one.
    return {"echo": message["payload"]}


def _run_agent_in_background():
    agent_log = logging.getLogger("test_poison_message.agent")
    run_consumer_agent(agent_log, IN_TOPIC, OUT_TOPIC, "s1808_poison_test", process)


def main() -> None:
    from kafka.admin import KafkaAdminClient, NewTopic

    admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
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
    time.sleep(4)

    producer = make_producer()
    dlq_consumer: KafkaConsumer = make_consumer(
        DEAD_LETTER_TOPIC, f"s1808_dlq_reader_{uuid.uuid4().hex}", auto_offset_reset="latest"
    )
    out_consumer: KafkaConsumer = make_consumer(
        OUT_TOPIC, f"s1808_out_reader_{uuid.uuid4().hex}", auto_offset_reset="latest"
    )

    poison_id = str(uuid.uuid4())
    good_id = str(uuid.uuid4())

    log.info("--- sending POISON message (missing 'payload' field, correlation_id=%s) ---", poison_id)
    producer.send(IN_TOPIC, value={"correlation_id": poison_id, "not_payload": "oops"})
    producer.flush()

    log.info("--- sending a GOOD message right after it (correlation_id=%s) ---", good_id)
    producer.send(IN_TOPIC, value={"correlation_id": good_id, "payload": "this one is fine"})
    producer.flush()

    dlq_result = None
    good_result = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and (dlq_result is None or good_result is None):
        for records in dlq_consumer.poll(timeout_ms=300).values():
            for r in records:
                if r.value.get("correlation_id") == poison_id:
                    dlq_result = r.value
        for records in out_consumer.poll(timeout_ms=300).values():
            for r in records:
                if r.value.get("correlation_id") == good_id:
                    good_result = r.value

    log.info("dead-letter record for the poison message: %s", json.dumps(dlq_result, indent=2))
    log.info("output for the good message that followed it: %s", good_result)

    assert dlq_result is not None, "poison message was never forwarded to the dead-letter topic"
    assert dlq_result["retries"] == 3, "expected exactly MAX_RETRIES retries recorded"
    assert good_result is not None, "the good message behind the poison one was blocked"
    log.info("PASS: poison message retried, dead-lettered, and did not block the message behind it.")


if __name__ == "__main__":
    main()
