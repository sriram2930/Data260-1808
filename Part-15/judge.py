"""
Part-15/judge.py -- DATA-260 HW10, Parts 2-3 (the G-Eval judge)

Judge model : qwen3:8b served by local Ollama (a different, larger model than the 1.5B generators it grades).
Framework   : DeepEval GEval, custom DeepEvalBaseLLM wrapper.
Settings    : temperature 0, seed 1808, thinking OFF, max 400 new tokens, 180 s per request -- fixed and written
              into every output file (JUDGE_SETTINGS) so the repeatability runs are comparable.
Scale       : 1-5 (1 = very poor, 5 = excellent), the same scale as the human labels. DeepEval returns
              (g - 1) / 4 for a rubric spanning 1..5; judge_1to5 = 1 + 4 * score, which recovers the integer g.
Bounded     : every call has a request timeout; a failure returns score=None with the error text instead of raising,
              so one bad message or an unavailable judge cannot hang or crash an evaluation run.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import json
import time
from typing import Optional

import ollama
from deepeval.metrics import GEval
from deepeval.metrics.g_eval.utils import Rubric
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams

JUDGE_MODEL = "qwen3:8b"
JUDGE_SETTINGS = {
    "model": JUDGE_MODEL, "host": "http://localhost:11434", "temperature": 0.0, "seed": 1808, "think": False,
    "num_predict": 400, "request_timeout_s": 180, "scale": "1-5 (1 very poor, 5 excellent)", "framework": "deepeval GEval",
}

RUBRIC = [
    Rubric(score_range=(1, 1), expected_outcome="Very poor: wrong, irrelevant, or missing what the question needs."),
    Rubric(score_range=(2, 2), expected_outcome="Poor: mostly unhelpful, with significant errors or omissions."),
    Rubric(score_range=(3, 3), expected_outcome="Fair: partly helpful, but incomplete, padded, or with a minor error."),
    Rubric(score_range=(4, 4), expected_outcome="Good: accurate and helpful, with only minor weaknesses."),
    Rubric(score_range=(5, 5), expected_outcome="Excellent: accurate, complete, relevant and clearly written."),
]

CRITERIA = {
    "plan_quality": (
        "Evaluate whether the Planner's PLAN (Actual Output) is a useful plan for answering the QUESTION (Input): it should "
        "name the specific points an answer must cover, be relevant to the question, and not answer the question itself.",
        [
            "Read the question and decide which specific facts or points a correct answer must contain.",
            "Check that the plan lists points that cover those needs and that every bullet is relevant to the question.",
            "Penalise a plan that is vague, off-topic, misses a part of the question, or simply answers the question.",
            "Give 5 for a specific, complete, relevant plan; 1 for an irrelevant or useless plan.",
        ],
    ),
    "helpfulness": (
        "Evaluate whether the ANSWER (Actual Output) is accurate, helpful and relevant to the QUESTION (Input). "
        "When Context lines are given they are the only trusted facts: the answer must agree with them.",
        [
            "Identify exactly what the question asks for (each requested fact).",
            "If Context facts are provided, check every claim in the answer against them; an answer that contradicts or invents facts "
            "must score 2 or lower. If the question is outside the university course catalogue, the best answer politely says so.",
            "Check that the answer actually provides each requested fact directly, without irrelevant padding.",
            "Give 5 only for a correct, complete, relevant and clear answer; 1 for a wrong or irrelevant one.",
        ],
    ),
}


class OllamaJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = JUDGE_MODEL, host: str = JUDGE_SETTINGS["host"]):
        self.model_name = model
        self.client = ollama.Client(host=host, timeout=JUDGE_SETTINGS["request_timeout_s"])
        self.calls = 0

    def load_model(self):
        return self.client

    def get_model_name(self) -> str:
        return self.model_name

    def generate(self, prompt: str, schema=None, **_):
        self.calls += 1
        resp = self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format=schema.model_json_schema() if schema is not None else None,
            think=JUDGE_SETTINGS["think"],
            options={"temperature": JUDGE_SETTINGS["temperature"], "seed": JUDGE_SETTINGS["seed"],
                     "num_predict": JUDGE_SETTINGS["num_predict"]},
        )
        text = resp["message"]["content"]
        return schema.model_validate_json(text) if schema is not None else text

    async def a_generate(self, prompt: str, schema=None, **kw):
        return self.generate(prompt, schema=schema, **kw)


_judge: Optional[OllamaJudge] = None


def get_judge() -> OllamaJudge:
    global _judge
    if _judge is None:
        _judge = OllamaJudge()
    return _judge


def make_metric(kind: str) -> GEval:
    criteria, steps = CRITERIA[kind]
    return GEval(
        name=kind, criteria=criteria, evaluation_steps=steps, rubric=RUBRIC,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT]
        + ([SingleTurnParams.CONTEXT] if kind == "helpfulness" else []),
        model=get_judge(), async_mode=False, verbose_mode=False, threshold=0.5,
    )


def judge(kind: str, question: str, output: str, facts: Optional[list[str]] = None) -> dict:
    """Score one (question, output) pair on the 1-5 scale. Never raises: errors come back in 'error'."""
    t0 = time.perf_counter()
    try:
        m = make_metric(kind)
        ctx = None
        if kind == "helpfulness":  # GEval requires a non-empty context; "no facts matched" is itself the context
            ctx = facts or ["No course-catalogue facts matched this question (it may be off-topic or name a course that does not exist)."]
        case = LLMTestCase(input=question, actual_output=output or "(empty)", context=ctx)
        raw = m.measure(case, _show_indicator=False)
        score = round(1 + 4 * float(raw))
        return {"kind": kind, "score": int(score), "reason": (m.reason or "").strip(), "error": None,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 -- bounded evaluator: report, do not hang or crash
        return {"kind": kind, "score": None, "reason": "", "error": f"{type(exc).__name__}: {exc}"[:300],
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


if __name__ == "__main__":
    q = "How many seats are available in course CS-00018?"
    facts = ["CS-00018 (Introduction to Cloud Computing): seats_available=8"]
    good = judge("helpfulness", q, "CS-00018 currently has 8 seats available.", facts)
    bad = judge("helpfulness", q, "CS-00018 has 30 seats available.", facts)
    print(json.dumps({"good": good, "bad": bad, "settings": JUDGE_SETTINGS}, indent=2))
