"""
Part-10/worker.py -- DATA-260 HW8, Part 1 (Kafka request/response worker)

Consumes CREATE_ENTITY / GET_ENTITY requests from s1808_entity_requests,
processes them against an in-memory Course store (entity_store.py), and
publishes the response to whatever topic the request's reply_to names
(always s1808_entity_responses for this homework, but read dynamically
per-message rather than hardcoded, since that's what the protocol
actually specifies). The worker never talks to the client directly --
every byte it emits goes back out through Kafka.

Run (Kafka must already be up, see docker-compose.kafka.yml, and the
topics must already exist, see reports/hw08/raw/topics_created.txt):
    python worker.py
"""

from __future__ import annotations

import json
import logging
import sys
import time

from entity_store import EntityStore, validate_course_data
from kafka import KafkaConsumer, KafkaProducer
from kafka_config import BOOTSTRAP_SERVERS, ENTITY_REQUESTS_TOPIC

logging.basicConfig(level=logging.INFO, format="%(asctime)s WORKER %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("worker")


def handle_request(store: EntityStore, operation: str, data: dict) -> dict:
    if operation == "CREATE_ENTITY":
        problem = validate_course_data(data)
        if problem:
            return {"success": False, "error": problem}
        record = store.create(data)
        return {"success": True, "entity_id": record["course_id"], "message": "Entity created"}

    if operation == "GET_ENTITY":
        entity_id = data.get("entity_id") if isinstance(data, dict) else None
        if not entity_id:
            return {"success": False, "error": "missing required field: 'entity_id'"}
        record = store.get(entity_id)
        if record is None:
            return {"success": False, "error": "Entity not found"}
        return {"success": True, "entity": record}

    return {"success": False, "error": "Unknown operation"}


def main() -> None:
    store = EntityStore()
    consumer = KafkaConsumer(
        ENTITY_REQUESTS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id="s1808_entity_worker",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    # A single poll() does not reliably complete this consumer group's
    # join/sync rebalance against this broker -- confirmed empirically it
    # can take ~7 polls (~3.5s). Without this, the first message after a
    # restart could sit unconsumed for much longer (observed up to ~28s
    # once) before the iterator below picks it up. See AI_USE.md.
    while not consumer.assignment():
        consumer.poll(timeout_ms=300)

    log.info("Consumer is ready and listening on %s...", ENTITY_REQUESTS_TOPIC)

    for msg in consumer:
        request = msg.value
        correlation_id = request.get("correlation_id")
        reply_to = request.get("reply_to")
        operation = request.get("operation")
        data = request.get("data", {})

        log.info(
            "received request: correlation_id=%s operation=%s data=%s",
            correlation_id, operation, data,
        )
        log.info("processing operation=%s ...", operation)

        t0 = time.perf_counter()
        result = handle_request(store, operation, data)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        response = {"correlation_id": correlation_id, **result}
        producer.send(reply_to, value=response)
        producer.flush()

        log.info(
            "sent response to %s: correlation_id=%s success=%s (%.2fms)",
            reply_to, correlation_id, result.get("success"), elapsed_ms,
        )


if __name__ == "__main__":
    main()
