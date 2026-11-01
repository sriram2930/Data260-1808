"""
Part-10/test_error_cases.py -- DATA-260 HW8, Part 1.III (error-case evidence)

Exercises the worker's validation/error paths directly over real Kafka:
missing required CREATE_ENTITY fields, an unknown operation, and
GET_ENTITY for a nonexistent entity_id. Not the graded homework_demo.py
sequence -- a supplementary script purely to capture real error-response
evidence for the report.

Run (Kafka + worker.py must already be up):
    python test_error_cases.py
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
log = logging.getLogger("test_error_cases")


def _wait_for_assignment(consumer: KafkaConsumer, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        consumer.poll(timeout_ms=300)
        if consumer.assignment():
            return
    raise TimeoutError("consumer group never completed its partition assignment")


def send_and_wait(producer, consumer, operation: str, data: dict, timeout_s: float = 10.0) -> dict:
    correlation_id = str(uuid.uuid4())
    request = {"correlation_id": correlation_id, "reply_to": ENTITY_RESPONSES_TOPIC, "operation": operation, "data": data}
    log.info("SEND  -> %s", json.dumps(request))
    producer.send(ENTITY_REQUESTS_TOPIC, value=request)
    producer.flush()

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        batches = consumer.poll(timeout_ms=500)
        for records in batches.values():
            for record in records:
                response = record.value
                if response.get("correlation_id") == correlation_id:
                    log.info("RECV  <- %s", json.dumps(response))
                    return response
    raise TimeoutError(f"no response for correlation_id={correlation_id}")


def main() -> None:
    producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v).encode("utf-8"))
    consumer = KafkaConsumer(
        ENTITY_RESPONSES_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=f"s1808_errtest_{uuid.uuid4().hex}",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    _wait_for_assignment(consumer)

    log.info("--- CREATE_ENTITY missing required field (course_title) ---")
    r1 = send_and_wait(producer, consumer, "CREATE_ENTITY", {"course_code": "BAD-001"})
    assert r1["success"] is False

    log.info("--- CREATE_ENTITY empty required field ---")
    r2 = send_and_wait(producer, consumer, "CREATE_ENTITY", {"course_code": "", "course_title": "x"})
    assert r2["success"] is False

    log.info("--- unknown operation ---")
    r3 = send_and_wait(producer, consumer, "DELETE_ENTITY", {"entity_id": "whatever"})
    assert r3["success"] is False

    log.info("--- GET_ENTITY for a nonexistent entity_id ---")
    r4 = send_and_wait(producer, consumer, "GET_ENTITY", {"entity_id": "00000000-0000-0000-0000-000000000000"})
    assert r4["success"] is False

    log.info("ALL ERROR CASES BEHAVED AS EXPECTED (success=false, clean error, correlation_id preserved each time).")
    consumer.close()
    producer.close()


if __name__ == "__main__":
    main()
