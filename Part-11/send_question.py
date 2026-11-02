"""
Part-11/send_question.py -- DATA-260 HW8, Part 2 (send one question, read the final answer)

Publishes one question with a fresh correlation_id to s1808_inbox, then
waits on s1808_final for the matching result (filtering by
correlation_id, since other questions' results may interleave on the
same topic) -- the only way to see the whole Planner -> Writer ->
Reviewer journey complete.

Run (Kafka must already be up, and planner.py/writer.py/reviewer.py must
each already be running in their own terminal):
    python send_question.py "What is a race condition?"
"""

from __future__ import annotations

import logging
import sys
import time
import uuid

from kafka_config import FINAL_TOPIC, INBOX_TOPIC
from kafka_utils import make_consumer, make_producer

logging.basicConfig(level=logging.INFO, format="%(asctime)s CLIENT %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("send_question")

DEFAULT_QUESTION = "What is a race condition in concurrent programming?"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION
    correlation_id = str(uuid.uuid4())

    producer = make_producer()
    consumer = make_consumer(FINAL_TOPIC, f"s1808_client_{uuid.uuid4().hex}", auto_offset_reset="latest")

    log.info("--- question (correlation_id=%s) ---", correlation_id)
    log.info("SEND -> %s: %s", INBOX_TOPIC, question)
    producer.send(INBOX_TOPIC, value={"correlation_id": correlation_id, "question": question})
    producer.flush()

    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        batches = consumer.poll(timeout_ms=500)
        for records in batches.values():
            for record in records:
                result = record.value
                if result.get("correlation_id") == correlation_id:
                    log.info("RECV <- %s: status=%s", FINAL_TOPIC, result.get("status"))
                    log.info("ANSWER: %s", result.get("answer"))
                    consumer.close()
                    producer.close()
                    return

    raise TimeoutError(f"no final result for correlation_id={correlation_id}")


if __name__ == "__main__":
    main()
