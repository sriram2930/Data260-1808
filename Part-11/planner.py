"""
Part-11/planner.py -- DATA-260 HW8, Part 2 (Planner agent)

Consumes a question from s1808_inbox, asks the local model for a short
plan (2-4 bullet points of what the answer needs to cover), and publishes
{correlation_id, question, plan} to s1808_tasks. Never calls Writer or
Reviewer directly -- the only way this process's output reaches them is
through Kafka.

Run (Kafka must already be up, topics already created):
    python planner.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

from kafka_config import INBOX_TOPIC, TASKS_TOPIC  # noqa: E402
from kafka_utils import run_consumer_agent  # noqa: E402
from src.model_client import ModelClient  # noqa: E402
from timed_model_client import TimedModelClient as _TimedModelClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s PLANNER %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("planner")

SYSTEM_PROMPT = (
    "You are the Planner in a three-agent question-answering pipeline. Given a "
    "question, reply with a short plan: 2-4 bullet points (each starting with '- ') "
    "naming the key points a good answer must cover. Do not answer the question "
    "yourself -- only plan what the answer should cover."
)


def make_process(model: ModelClient):
    def process(message: dict) -> dict:
        question = message["question"]
        response = model.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ])
        plan = response["content"].strip()
        log.info("planned for question=%r", question)
        return {"question": question, "plan": plan}

    return process


def main() -> None:
    model = _TimedModelClient()
    run_consumer_agent(log, INBOX_TOPIC, TASKS_TOPIC, "s1808_planner", make_process(model))


if __name__ == "__main__":
    main()
