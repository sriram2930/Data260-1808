"""
Part-5/compute_metrics.py -- DATA-260 HW3, Part 2 metrics recompute

Reads ONLY the raw data already written by run_retrieval_comparison.py
(reports/hw03/raw/retrieval_results.jsonl + chunk_stats.json) -- no LlamaIndex
imports, no network, no recomputation of embeddings -- and recomputes the
summary table the assignment asks for:

    Technique | Chunks | Avg chunk length | Top-1 cosine | Mean@k cosine |
    Recall@k | Mean retrieval latency (ms)

top-1 cosine and mean@k cosine are averaged across the 5 questions (each
question's own top-1 / mean-of-top-k first, then averaged across questions).
Recall@k is defined as: for each question, 1 if any of the top-k retrieved
chunks came from that question's expected_source_file, else 0 -- averaged
across the 5 questions.

Also finds and prints at least one "confidently scored retrieval that does
not contain the answer": the highest-cosine row, per technique, whose source
file does NOT match the question's expected_source_file.

Usage:
    python compute_metrics.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
RAW_DIR = REPO_ROOT / "reports" / "hw03" / "raw"

CONFIDENT_THRESHOLD = 0.5


def load_rows() -> list[dict]:
    rows = []
    with open(RAW_DIR / "retrieval_results.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_chunk_stats() -> dict:
    with open(RAW_DIR / "chunk_stats.json", "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    rows = load_rows()
    stats = load_chunk_stats()

    by_tech_question = defaultdict(list)
    for r in rows:
        by_tech_question[(r["technique"], r["question_id"])].append(r)

    techniques = sorted({r["technique"] for r in rows})
    summary = {}
    for tech in techniques:
        question_ids = sorted({qid for (t, qid) in by_tech_question if t == tech})
        top1_list, mean_k_list, recall_list, latency_list = [], [], [], []
        for qid in question_ids:
            group = sorted(by_tech_question[(tech, qid)], key=lambda r: r["rank"])
            cosines = [g["cosine_sim"] for g in group]
            top1_list.append(cosines[0])
            mean_k_list.append(sum(cosines) / len(cosines))
            expected = group[0]["expected_source_file"]
            hit = any(g["source_file"] == expected for g in group)
            recall_list.append(1.0 if hit else 0.0)
            latency_list.append(group[0]["retrieval_latency_ms"])

        summary[tech] = {
            "chunks": stats[tech]["num_chunks"],
            "avg_chunk_length": round(stats[tech]["avg_chunk_length_chars"], 1),
            "top1_cosine": round(sum(top1_list) / len(top1_list), 4),
            "mean_at_k_cosine": round(sum(mean_k_list) / len(mean_k_list), 4),
            "recall_at_k": round(sum(recall_list) / len(recall_list), 4),
            "mean_retrieval_latency_ms": round(sum(latency_list) / len(latency_list), 2),
        }

    print("=== Summary table ===")
    header = f"{'Technique':<18}{'Chunks':<9}{'AvgLen':<9}{'Top1cos':<10}{'Mean@kcos':<11}{'Recall@k':<10}{'MeanLatMs':<10}"
    print(header)
    for tech in techniques:
        s = summary[tech]
        print(f"{tech:<18}{s['chunks']:<9}{s['avg_chunk_length']:<9}{s['top1_cosine']:<10}"
              f"{s['mean_at_k_cosine']:<11}{s['recall_at_k']:<10}{s['mean_retrieval_latency_ms']:<10}")

    # Find a confidently-scored miss per technique: highest-cosine row whose
    # source file does NOT match the expected source for that question.
    misses = {}
    for tech in techniques:
        candidates = [
            r for r in rows
            if r["technique"] == tech and r["source_file"] != r["expected_source_file"]
            and r["cosine_sim"] >= CONFIDENT_THRESHOLD
        ]
        if candidates:
            worst = max(candidates, key=lambda r: r["cosine_sim"])
            misses[tech] = worst

    print(f"\n=== Confidently-scored (cosine >= {CONFIDENT_THRESHOLD}) retrievals that miss the expected source ===")
    for tech, r in misses.items():
        print(f"[{tech}] q={r['question_id']!r} cosine={r['cosine_sim']:.4f} "
              f"expected={r['expected_source_file']} got={r['source_file']}")
        print(f"  preview: {r['preview']}")

    out = {"summary": summary, "confident_misses": misses}
    with open(RAW_DIR / "metrics_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {RAW_DIR / 'metrics_summary.json'}")


if __name__ == "__main__":
    main()
