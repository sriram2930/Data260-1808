"""
Part-11/writer.py -- DATA-260 HW8, Part 2 (Writer agent)

Consumes a plan from s1808_tasks, asks the local model to write a draft
answer following that plan, and publishes {correlation_id, question, plan,
draft} to s1808_drafts.

Run (Kafka must already be up, topics already created):
    python writer.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

from kafka_config import DRAFTS_TOPIC, TASKS_TOPIC  # noqa: E402
from kafka_utils import run_consumer_agent  # noqa: E402
from src.model_client import ModelClient  # noqa: E402
from timed_model_client import TimedModelClient as _TimedModelClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s WRITER %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("writer")

SYSTEM_PROMPT = (
    "You are the Writer in a three-agent question-answering pipeline. You are "
    "given a QUESTION and a PLAN (bullet points of what to cover). Write a clear, "
    "concise draft answer (3-6 sentences) that follows the plan and directly "
    "answers the question."
)


def make_process(model: ModelClient):
    def process(message: dict) -> dict:
        question = message["question"]
        plan = message["plan"]
        response = model.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"QUESTION: {question}\n\nPLAN:\n{plan}"},
        ])
        draft = response["content"].strip()
        log.info("wrote draft for question=%r", question)
        return {"question": question, "plan": plan, "draft": draft}

    return process


def main() -> None:
    group_id = os.environ.get("WRITER_GROUP_ID", "s1808_writer")
    model = _TimedModelClient()
    run_consumer_agent(log, TASKS_TOPIC, DRAFTS_TOPIC, group_id, make_process(model))


if __name__ == "__main__":
    main()
