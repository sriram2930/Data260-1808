"""
Part-5/run_retrieval_comparison.py -- DATA-260 HW3, Part 2 experiment runner

Builds all three chunking pipelines (rag_compare.build_all_pipelines), runs
every question in reports/hw03/questions.yaml against every technique with
rag_compare.retrieve(), prints the full per-query transcript required by the
assignment, and writes raw per-row data plus per-technique chunk stats to
reports/hw03/raw/. Run compute_metrics.py afterward to turn this raw data
into the summary table in METRICS.md -- that recompute step is intentionally
a separate script/file, per the assignment.

Usage:
    python run_retrieval_comparison.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from rag_compare import build_all_pipelines, chunk_stats, retrieve

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
QUESTIONS_PATH = REPO_ROOT / "reports" / "hw03" / "questions.yaml"
RAW_DIR = REPO_ROOT / "reports" / "hw03" / "raw"

K = 5


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = yaml.safe_load(f)["questions"]

    print(f"=== DATA-260 HW3 Part 2 retrieval comparison started {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Loaded {len(questions)} questions from {QUESTIONS_PATH}")

    print("\nBuilding pipelines (token / semantic / sentence_window)...")
    pipelines = build_all_pipelines()
    for tech, p in pipelines.items():
        stats = chunk_stats(p["nodes"])
        print(f"  {tech}: {stats['num_chunks']} chunks, "
              f"avg chunk length {stats['avg_chunk_length_chars']:.1f} chars")

    stats_out = {tech: chunk_stats(p["nodes"]) for tech, p in pipelines.items()}
    with open(RAW_DIR / "chunk_stats.json", "w", encoding="utf-8") as f:
        json.dump(stats_out, f, indent=2)

    all_rows = []
    jsonl_path = RAW_DIR / "retrieval_results.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as jf:
        for q in questions:
            for tech in pipelines:
                result = retrieve(tech, pipelines[tech]["index"], q["question"].strip(), k=K)
                for row in result["rows"]:
                    full_row = {
                        "question_id": q["id"],
                        "question": q["question"].strip(),
                        "expected_source_file": q["expected_source_file"],
                        "single_source": q.get("single_source", False),
                        "technique": tech,
                        "k": K,
                        "retrieval_latency_ms": result["retrieval_latency_ms"],
                        "query_embedding_dim": result["query_embedding_dim"],
                        **row,
                    }
                    all_rows.append(full_row)
                    jf.write(json.dumps(full_row) + "\n")

    csv_path = RAW_DIR / "retrieval_results.csv"
    import csv
    fieldnames = list(all_rows[0].keys()) if all_rows else []
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {jsonl_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {RAW_DIR / 'chunk_stats.json'}")
    print(f"\n=== finished {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
