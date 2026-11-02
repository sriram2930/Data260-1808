"""
Part-11/reviewer.py -- DATA-260 HW8, Part 2 (Reviewer agent)

Consumes a draft from s1808_drafts, asks the local model to check it
against the question and plan (fixing it if needed), and publishes the
final {correlation_id, status, answer} JSON to s1808_final.

Run (Kafka must already be up, topics already created):
    python reviewer.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

from kafka_config import DRAFTS_TOPIC, FINAL_TOPIC  # noqa: E402
from kafka_utils import run_consumer_agent  # noqa: E402
from src.model_client import ModelClient  # noqa: E402
from timed_model_client import TimedModelClient as _TimedModelClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s REVIEWER %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("reviewer")

SYSTEM_PROMPT = (
    "You are the Reviewer in a three-agent question-answering pipeline. You are "
    "given a QUESTION, a PLAN, and a DRAFT answer. If the draft correctly and "
    "completely answers the question per the plan, reply with the draft "
    "unchanged. If it has a problem, reply with a corrected version instead. "
    "Reply with ONLY the final answer text -- no preamble, no explanation of "
    "what you changed."
)


def make_process(model: ModelClient):
    def process(message: dict) -> dict:
        question = message["question"]
        plan = message["plan"]
        draft = message["draft"]
        response = model.complete([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"QUESTION: {question}\n\nPLAN:\n{plan}\n\nDRAFT:\n{draft}"},
        ])
        final_answer = response["content"].strip()
        log.info("reviewed and approved answer for question=%r", question)
        return {"status": "approved", "answer": final_answer}

    return process


def main() -> None:
    model = _TimedModelClient()
    run_consumer_agent(log, DRAFTS_TOPIC, FINAL_TOPIC, "s1808_reviewer", make_process(model))


if __name__ == "__main__":
    main()
