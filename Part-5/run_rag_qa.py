"""
Part-5/run_rag_qa.py -- DATA-260 HW4, Part 4 experiment runner

Runs all 6 questions (reports/hw04/rag_questions.yaml) through all 3
configurations (No-RAG, Basic-RAG, Context-RAG), then sweeps k in {1, 3, 5}
on one multi-chunk question (q2) under Context-RAG, then scores every
(question, config) pair against objective, wording-independent checks:

  correct_retrieval  -- did at least one of the retrieved chunks come from
                         one of the question's expected_source_files
                         (only meaningful for basic_rag/context_rag; no_rag
                         retrieves nothing, so this is always None for it)
  correct_answer     -- does the answer contain at least one of the
                         question's expected_keywords (only meaningful for
                         questions that have keywords, i.e. not q4/q5/q6)
  grounded           -- for context_rag only: does the answer contain a
                         [n] citation
  refused            -- does the answer contain the exact required refusal
                         sentence

Writes every raw answer, the k-sweep, and the evaluation table to
reports/hw04/raw/.

Usage:
    python run_rag_qa.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import yaml

import rag_qa as rq

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
QUESTIONS_PATH = REPO_ROOT / "reports" / "hw04" / "rag_questions.yaml"
RAW_DIR = REPO_ROOT / "reports" / "hw04" / "raw"

CONFIGS = ["no_rag", "basic_rag", "context_rag"]
K_SWEEP_QUESTION_ID = "q2"
K_SWEEP_VALUES = [1, 3, 5]


def run_config(config: str, question: str, k: int = 3) -> dict:
    if config == "no_rag":
        return rq.answer_no_rag(question)
    if config == "basic_rag":
        return rq.answer_basic_rag(question, k=k)
    if config == "context_rag":
        return rq.answer_context_rag(question, k=k)
    raise ValueError(config)


def check_correct_retrieval(result: dict, expected_sources: list[str]) -> bool | None:
    if result["config"] == "no_rag" or not expected_sources:
        return None
    got_sources = {c["source"] for c in result["chunks_used"]}
    return bool(got_sources & set(expected_sources))


def check_correct_answer(answer: str, expected_keywords: list[str]) -> bool | None:
    if not expected_keywords:
        return None
    low = answer.lower()
    return any(kw.lower() in low for kw in expected_keywords)


def check_grounded(result: dict) -> bool | None:
    if result["config"] != "context_rag":
        return None
    return bool(re.search(r"\[\d+\]", result["content"]))


def check_refused(answer: str) -> bool:
    return rq.REFUSAL_TEXT.lower() in answer.lower()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = yaml.safe_load(f)["questions"]

    print(f"=== DATA-260 HW4 Part 4 RAG QA experiment started {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("Building index (one-time cost for this run)...")
    rq.build_index()
    print("Index ready.\n")

    all_results = []
    eval_rows = []

    print("=== Three-configuration comparison (6 questions x 3 configs) ===")
    for q in questions:
        for config in CONFIGS:
            print(f"\n--- {q['id']} [{config}] ---")
            print(f"Q: {q['question']}")
            result = run_config(config, q["question"])
            print(f"A: {result['content']}")

            correct_retrieval = check_correct_retrieval(result, q["expected_source_files"])
            correct_answer = check_correct_answer(result["content"], q["expected_keywords"])
            grounded = check_grounded(result)
            refused = check_refused(result["content"])

            row = {
                "question_id": q["id"],
                "category": q["category"],
                "config": config,
                "question": q["question"],
                "answer": result["content"],
                "chunks_used": [
                    {"chunk_id": c["chunk_id"], "source": c["source"], "score": c["score"]}
                    for c in result["chunks_used"]
                ],
                "latency_ms": round(result["latency_ms"], 1),
                "correct_retrieval": correct_retrieval,
                "correct_answer": correct_answer,
                "grounded": grounded,
                "refused": refused,
                "must_refuse": q["must_refuse"],
                "refused_correctly": (refused == q["must_refuse"]),
            }
            all_results.append(row)
            eval_rows.append(row)
            print(f"  [checks] correct_retrieval={correct_retrieval} correct_answer={correct_answer} "
                  f"grounded={grounded} refused={refused} (must_refuse={q['must_refuse']})")

    print(f"\n=== k-sweep on {K_SWEEP_QUESTION_ID} (context_rag) ===")
    sweep_q = next(q for q in questions if q["id"] == K_SWEEP_QUESTION_ID)
    sweep_results = []
    for k in K_SWEEP_VALUES:
        print(f"\n--- k={k} ---")
        result = rq.answer_context_rag(sweep_q["question"], k=k)
        print(f"A: {result['content']}")
        irrelevant = sum(1 for c in rq.retrieve_chunks(sweep_q["question"], k=k, print_output=False)
                          if c["score"] < rq.RELEVANCE_THRESHOLD)
        sweep_results.append({
            "k": k,
            "answer": result["content"],
            "chunks_retrieved": k,
            "chunks_used_after_curation": len(result["chunks_used"]),
            "irrelevant_chunks_in_top_k": irrelevant,
            "correct_answer": check_correct_answer(result["content"], sweep_q["expected_keywords"]),
            "latency_ms": round(result["latency_ms"], 1),
        })

    with open(RAW_DIR / "rag_three_config_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    with open(RAW_DIR / "rag_k_sweep_results.json", "w", encoding="utf-8") as f:
        json.dump(sweep_results, f, indent=2)

    summary = {
        "accuracy": round(
            sum(1 for r in eval_rows if r["correct_answer"] is True)
            / max(1, sum(1 for r in eval_rows if r["correct_answer"] is not None)),
            3,
        ),
        "faithfulness_grounded_rate": round(
            sum(1 for r in eval_rows if r["grounded"] is True)
            / max(1, sum(1 for r in eval_rows if r["grounded"] is not None)),
            3,
        ),
        "refusal_correctness_rate": round(
            sum(1 for r in eval_rows if r["refused_correctly"]) / len(eval_rows), 3
        ),
    }
    with open(RAW_DIR / "rag_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== EVALUATION SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\n=== finished {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
