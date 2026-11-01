"""
Part-10/homework_demo.py -- DATA-260 HW8, Part 1.IV (full demo sequence)

Acts as the Kafka client directly (not through api.py's HTTP layer, to keep
the raw request/response protocol itself front and center): one
correlation_id, a CREATE_ENTITY request, then a GET_ENTITY request using
the entity_id the CREATE_ENTITY response returned, logging every stage of
both round trips. worker.py must already be running (python worker.py in
its own terminal) before this script is run, since this script only
produces requests and consumes responses -- it never processes anything
itself.

Run (Kafka + worker.py must already be up):
    python homework_demo.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from kafka import KafkaConsumer, KafkaProducer
from kafka_config import BOOTSTRAP_SERVERS, ENTITY_REQUESTS_TOPIC, ENTITY_RESPONSES_TOPIC

logging.basicConfig(level=logging.INFO, format="%(asctime)s CLIENT %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("homework_demo")


def _wait_for_assignment(consumer: KafkaConsumer, timeout_s: float = 10.0) -> None:
    """A single poll() does not reliably complete a consumer group's
    join/sync rebalance against this broker -- confirmed empirically it
    can take ~7 polls (~3.5s) before consumer.assignment() is non-empty.
    Poll repeatedly until the partition assignment actually lands, instead
    of assuming one poll() is enough (an earlier version did, and every
    request sent right after it silently got no response)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        consumer.poll(timeout_ms=300)
        if consumer.assignment():
            return
    raise TimeoutError("consumer group never completed its partition assignment")


def send_and_wait(
    producer: KafkaProducer, consumer: KafkaConsumer, operation: str, data: dict, timeout_s: float = 15.0
) -> dict:
    correlation_id = str(uuid.uuid4())
    request = {
        "correlation_id": correlation_id,
        "reply_to": ENTITY_RESPONSES_TOPIC,
        "operation": operation,
        "data": data,
    }

    log.info("--- %s (correlation_id=%s) ---", operation, correlation_id)
    log.info("SEND  -> %s: %s", ENTITY_REQUESTS_TOPIC, json.dumps(request))
    producer.send(ENTITY_REQUESTS_TOPIC, value=request)
    producer.flush()
    log.info("(worker.py's own log shows it receiving, processing, and replying to this request)")

    # Explicit poll() loop rather than the `for msg in consumer:` iterator --
    # more predictable when a manual warm-up poll() already ran before this
    # (an earlier version mixing the two silently never advanced; see
    # AI_USE.md).
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        batches = consumer.poll(timeout_ms=500)
        for records in batches.values():
            for record in records:
                response = record.value
                if response.get("correlation_id") == correlation_id:
                    log.info("RECV  <- %s: %s", ENTITY_RESPONSES_TOPIC, json.dumps(response))
                    assert response["correlation_id"] == correlation_id, "correlation_id was not preserved!"
                    log.info("correlation_id preserved: %s", correlation_id)
                    return response

    raise TimeoutError(f"no response for correlation_id={correlation_id}")


def main() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    # A fresh, unique consumer group per run: with auto_offset_reset="latest"
    # and no prior committed offset, a brand-new group starts reading from
    # whatever the end of the topic is at the moment it first joins -- the
    # standard, well-tested way to say "only show me new messages", instead
    # of a manual assign()+seek_to_end() which raced with this client's own
    # metadata fetch and silently never advanced in an earlier version of
    # this script.
    consumer = KafkaConsumer(
        ENTITY_RESPONSES_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=f"s1808_client_{uuid.uuid4().hex}",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        consumer_timeout_ms=15000,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    _wait_for_assignment(consumer)  # force group-join to complete before any request is sent

    log.info("=== STEP 1-7: CREATE_ENTITY ===")
    create_response = send_and_wait(producer, consumer, "CREATE_ENTITY", {
        "course_code": "DATA-00500",
        "course_title": "HW8 Kafka Demo Course",
        "description": "Created by homework_demo.py to demonstrate the request/response flow.",
        "department": "Data Science & AI",
        "seats_available": 25,
    })
    entity_id = create_response["entity_id"]
    log.info("extracted entity_id from CREATE_ENTITY response: %s", entity_id)

    time.sleep(0.5)

    log.info("=== STEP 8-10: GET_ENTITY using the extracted entity_id ===")
    get_response = send_and_wait(producer, consumer, "GET_ENTITY", {"entity_id": entity_id})

    log.info("retrieved entity: %s", json.dumps(get_response["entity"], indent=2))
    log.info("DEMO COMPLETE -- CREATE_ENTITY and GET_ENTITY both round-tripped with correlation_id preserved.")

    consumer.close()
    producer.close()


if __name__ == "__main__":
    main()
