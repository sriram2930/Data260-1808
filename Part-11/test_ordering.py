"""
Part-11/test_ordering.py -- DATA-260 HW8, Part 3.IV (ordering)

Generates 20 related messages (sequential updates #1-20 for ONE entity,
course_id derived from VERIFY_SEED=261808) and sends them through
s1808_tasks (2 partitions) to two lightweight consumer instances in the
same consumer group, recording the order each instance actually receives
them in. Run twice:

  1. No message key -- the default partitioner round-robins across both
     partitions, so the two instances process disjoint, INTERLEAVED
     subsets concurrently; the globally observed order does not have to
     match the original send order.
  2. Keyed by entity_id -- Kafka's partitioner hashes the key
     consistently, so every message for this one entity lands on the
     SAME partition; only one of the two instances ever receives them,
     strictly in send order.

Two lightweight stand-in consumer instances, not two real writer.py
processes: ordering is a partition-assignment property, independent of
what a handler does with each message, and running 20 messages x2 through
the real ~20-50s-per-call local model would take 15+ minutes for no
additional insight into the thing actually being tested here. This is
noted explicitly in METRICS.md/AI_USE.md, not hidden.

Run (Kafka must already be up; the real writer.py should NOT be running
at the same time, since this reuses s1808_tasks and a from-scratch
consumer group name distinct from "s1808_writer"):
    python test_ordering.py
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import uuid

from kafka import KafkaConsumer
from kafka_config import BOOTSTRAP_SERVERS, TASKS_TOPIC
from kafka_utils import make_producer, wait_for_assignment

logging.basicConfig(level=logging.INFO, format="%(asctime)s ORDERTEST %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("test_ordering")

VERIFY_SEED = 261808
ENTITY_ID = f"course-{VERIFY_SEED}"
N_MESSAGES = 20
GROUP_ID = "s1808_ordering_test"


def _make_messages(run_label: str) -> list[dict]:
    return [
        {
            "correlation_id": f"{run_label}-{uuid.uuid4()}",
            "entity_id": ENTITY_ID,
            "seq": i,
            "question": f"update #{i} for {ENTITY_ID}",
            "plan": "- n/a (ordering test message)",
        }
        for i in range(1, N_MESSAGES + 1)
    ]


def _consumer_instance(instance_name: str, received: list, lock: threading.Lock, stop_event: threading.Event) -> None:
    consumer: KafkaConsumer = KafkaConsumer(
        TASKS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    wait_for_assignment(consumer)
    log.info("%s ready, assigned partitions: %s", instance_name, [tp.partition for tp in consumer.assignment()])
    while not stop_event.is_set():
        for tp, records in consumer.poll(timeout_ms=300).items():
            for r in records:
                with lock:
                    received.append({
                        "instance": instance_name,
                        "partition": tp.partition,
                        "seq": r.value.get("seq"),
                        "correlation_id": r.value.get("correlation_id"),
                    })
    consumer.close()


def _run_once(run_label: str, use_key: bool) -> list[dict]:
    received: list[dict] = []
    lock = threading.Lock()
    stop_event = threading.Event()

    t1 = threading.Thread(target=_consumer_instance, args=("instance-A", received, lock, stop_event), daemon=True)
    t2 = threading.Thread(target=_consumer_instance, args=("instance-B", received, lock, stop_event), daemon=True)
    t1.start()
    t2.start()
    time.sleep(6)  # let both instances finish joining the group before anything is sent

    producer = make_producer()
    messages = _make_messages(run_label)
    log.info("--- sending %d messages, keyed=%s ---", len(messages), use_key)
    for m in messages:
        key = ENTITY_ID.encode("utf-8") if use_key else None
        producer.send(TASKS_TOPIC, key=key, value=m)
    producer.flush()

    time.sleep(5)  # let both instances finish consuming everything sent
    stop_event.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    return received


def main() -> None:
    log.info("ENTITY_ID = %s (derived from VERIFY_SEED=%d)", ENTITY_ID, VERIFY_SEED)

    log.info("\n========== RUN 1: no message key ==========")
    unkeyed = _run_once("unkeyed", use_key=False)
    unkeyed_sorted_by_arrival = sorted(unkeyed, key=lambda r: (r["instance"], r["partition"]))
    partitions_used = sorted({r["partition"] for r in unkeyed})
    arrival_seqs = [r["seq"] for r in unkeyed]
    in_order = arrival_seqs == sorted(arrival_seqs)
    log.info("partitions used (unkeyed): %s", partitions_used)
    log.info("arrival order of seq numbers (merged across instances): %s", arrival_seqs)
    log.info("global arrival order matches original send order 1..20? %s", in_order)
    for r in unkeyed_sorted_by_arrival[:6]:
        log.info("  sample: %s", r)

    time.sleep(2)

    log.info("\n========== RUN 2: keyed by entity_id ==========")
    keyed = _run_once("keyed", use_key=True)
    partitions_used_keyed = sorted({r["partition"] for r in keyed})
    instances_used_keyed = sorted({r["instance"] for r in keyed})
    keyed_seqs_in_arrival_order = [r["seq"] for r in keyed]
    keyed_in_order = keyed_seqs_in_arrival_order == sorted(keyed_seqs_in_arrival_order)
    log.info("partitions used (keyed): %s (expected: exactly 1)", partitions_used_keyed)
    log.info("consumer instances that received anything (keyed): %s (expected: exactly 1)", instances_used_keyed)
    log.info("arrival order of seq numbers (keyed): %s", keyed_seqs_in_arrival_order)
    log.info("order preserved (keyed)? %s (expected: True)", keyed_in_order)

    assert len(partitions_used_keyed) == 1, "keyed messages for one entity landed on more than one partition"
    assert len(instances_used_keyed) == 1, "keyed messages for one entity were split across consumer instances"
    assert keyed_in_order, "keyed messages for one entity were not processed in send order"
    log.info("PASS: keying by entity_id confined all 20 related messages to one partition, in order.")

    with open("../reports/hw08/raw/ordering_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "entity_id": ENTITY_ID,
            "unkeyed": {"partitions_used": partitions_used, "arrival_seqs": arrival_seqs, "in_order": in_order},
            "keyed": {
                "partitions_used": partitions_used_keyed,
                "instances_used": instances_used_keyed,
                "arrival_seqs": keyed_seqs_in_arrival_order,
                "in_order": keyed_in_order,
            },
        }, f, indent=2)
    log.info("wrote ../reports/hw08/raw/ordering_results.json")


if __name__ == "__main__":
    main()
