"""
Part-10/api.py -- DATA-260 HW8, Part 1 (FastAPI client/API wrapper over Kafka)

A thin HTTP front end: every call publishes a request message to
s1808_entity_requests with a fresh correlation_id, then waits for the
matching response on s1808_entity_responses (filtering by correlation_id,
since other requests' responses may interleave on the same topic). This
process never touches the in-memory Course store directly -- worker.py is
the only thing that does, and it finds out about requests purely through
Kafka, exactly like the protocol requires.

One persistent background consumer (not a fresh one per request): a
consumer group's join/sync rebalance against this broker measured at
~3.5s (confirmed empirically, see AI_USE.md), so creating a new consumer
group per HTTP call would add that delay to every single request and
leave a pile of orphaned groups behind. Instead, one consumer thread
started at import time dispatches each incoming response, by
correlation_id, to whichever request thread is waiting on it via a
threading.Event.

Run (PORT_BASE=8008; the HW4-7 Part-1/main.py server must not already be
bound to this port -- stop it first, this is a different demo service):
    python -m uvicorn api:app --host 0.0.0.0 --port 8008
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import uuid

from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer, KafkaProducer
from kafka_config import BOOTSTRAP_SERVERS, ENTITY_REQUESTS_TOPIC, ENTITY_RESPONSES_TOPIC, PORT_BASE
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s API %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("api")

app = FastAPI(title="HW8 Part 1 -- Kafka-backed Course service")

_producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

_pending: dict[str, dict] = {}
_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


def _response_listener() -> None:
    consumer = KafkaConsumer(
        ENTITY_RESPONSES_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id="s1808_api_responses",
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    # See AI_USE.md: one poll() does not reliably complete the group's
    # join/sync rebalance against this broker -- it took ~7 polls in
    # testing before consumer.assignment() was non-empty.
    while not consumer.assignment():
        consumer.poll(timeout_ms=300)
    log.info("response listener ready, assigned: %s", consumer.assignment())

    for msg in consumer:
        response = msg.value
        correlation_id = response.get("correlation_id")
        with _lock:
            event = _events.get(correlation_id)
            if event is not None:
                _pending[correlation_id] = response
                event.set()


_listener_thread = threading.Thread(target=_response_listener, daemon=True)
_listener_thread.start()


class CourseIn(BaseModel):
    course_code: str
    course_title: str
    description: str | None = None
    department: str | None = None
    seats_available: int | None = None


def _send_and_wait(operation: str, data: dict, timeout_s: float = 15.0) -> dict:
    correlation_id = str(uuid.uuid4())
    request = {
        "correlation_id": correlation_id,
        "reply_to": ENTITY_RESPONSES_TOPIC,
        "operation": operation,
        "data": data,
    }
    event = threading.Event()
    with _lock:
        _events[correlation_id] = event

    log.info("sending request: correlation_id=%s operation=%s data=%s", correlation_id, operation, data)
    _producer.send(ENTITY_REQUESTS_TOPIC, value=request)
    _producer.flush()

    got_it = event.wait(timeout=timeout_s)
    with _lock:
        response = _pending.pop(correlation_id, None)
        _events.pop(correlation_id, None)

    if not got_it or response is None:
        raise HTTPException(status_code=504, detail=f"no response for correlation_id={correlation_id} within {timeout_s}s")

    log.info("received response: correlation_id=%s success=%s", correlation_id, response.get("success"))
    return response


@app.post("/api/courses")
def create_course(payload: CourseIn):
    data = payload.model_dump(exclude_none=True)
    response = _send_and_wait("CREATE_ENTITY", data)
    if not response.get("success"):
        raise HTTPException(status_code=422, detail=response.get("error"))
    return response


@app.get("/api/courses/{course_id}")
def get_course(course_id: str):
    response = _send_and_wait("GET_ENTITY", {"entity_id": course_id})
    if not response.get("success"):
        raise HTTPException(status_code=404, detail=response.get("error"))
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=PORT_BASE, reload=False)
