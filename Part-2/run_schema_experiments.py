"""
Part-2/run_schema_experiments.py -- DATA-260 HW2, Part 4 (Output Schema and
Loop Safety) experiments

Runs the three experiments Part 4 asks for, all against agent_graph.run_graph():

  1. 30 runs on the fixed reports/hw02/cases/schema_input.json (turn_ceiling=10),
     classified into the four buckets (valid first attempt / valid after 1
     retry / valid after 2+ retries / hit turn ceiling), with count + mean
     latency per bucket.
  2. Turn-ceiling comparison: 20 runs at ceiling=2 vs 20 runs at ceiling=10 on
     the same frozen input and model settings, reporting completion rate and
     mean latency for each.
  3. The adversarial input (reports/hw02/cases/adversarial_input.json), 5 runs
     at ceiling=10, reporting the observed ceiling-hit rate.

Writes raw per-run rows (CSV + JSON) and an aggregate summary JSON to
reports/hw02/raw/.

Usage:
    python run_schema_experiments.py
"""

from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

from agent_graph import run_graph

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
CASES = REPO_ROOT / "reports" / "hw02" / "cases"
RAW = REPO_ROOT / "reports" / "hw02" / "raw"

SCHEMA_CEILING = 10
N_CLASSIFY_RUNS = 30
CEILINGS_TO_COMPARE = [2, 10]
N_CEILING_RUNS = 20
N_ADVERSARIAL_RUNS = 5
ADV_CEILING = 10

BUCKETS = [
    "valid_first_attempt",
    "valid_after_1_retry",
    "valid_after_2plus_retries",
    "hit_turn_ceiling",
]


def load(name: str) -> dict:
    with open(CASES / name, "r", encoding="utf-8") as f:
        return json.load(f)


def run_n(title: str, content: str, turn_ceiling: int, n: int, label: str) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        result = run_graph(title=title, content=content, turn_ceiling=turn_ceiling, stream=False)
        row = {
            "label": label,
            "run_index": i,
            "turn_ceiling": turn_ceiling,
            "outcome": result["outcome"],
            "turn_count": result["final_state"]["turn_count"],
            "latency_ms": round(result["latency_ms"], 1),
            "started_at": started_at,
        }
        rows.append(row)
        print(
            f"[{started_at}] [{label}] run {i}/{n} ceiling={turn_ceiling} -> "
            f"outcome={row['outcome']} turns={row['turn_count']} latency={row['latency_ms']}ms",
            flush=True,
        )
    return rows


def summarize_classification(rows: list[dict]) -> dict:
    summary = {}
    for b in BUCKETS:
        lat = [r["latency_ms"] for r in rows if r["outcome"] == b]
        summary[b] = {
            "count": len(lat),
            "mean_latency_ms": round(statistics.mean(lat), 1) if lat else None,
        }
    return summary


def summarize_ceiling(rows: list[dict], ceiling: int) -> dict:
    subset = [r for r in rows if r["turn_ceiling"] == ceiling]
    completed = [r for r in subset if r["outcome"] != "hit_turn_ceiling"]
    completion_rate = len(completed) / len(subset) if subset else 0.0
    mean_latency = statistics.mean([r["latency_ms"] for r in subset]) if subset else None
    return {
        "n": len(subset),
        "completion_rate": round(completion_rate, 3),
        "mean_latency_ms": round(mean_latency, 1) if mean_latency is not None else None,
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    schema_input = load("schema_input.json")
    adv_input = load("adversarial_input.json")

    print(f"=== DATA-260 HW2 Part 4 experiments started {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")

    all_rows: list[dict] = []

    print(f"=== Experiment 1: {N_CLASSIFY_RUNS}-run classification "
          f"(schema_input.json, ceiling={SCHEMA_CEILING}) ===")
    classify_rows = run_n(
        schema_input["title"], schema_input["content"], SCHEMA_CEILING, N_CLASSIFY_RUNS, "classification"
    )
    all_rows += classify_rows
    classify_summary = summarize_classification(classify_rows)

    print(f"\n=== Experiment 2: turn-ceiling comparison "
          f"({CEILINGS_TO_COMPARE}, {N_CEILING_RUNS} runs each) ===")
    ceiling_rows: list[dict] = []
    for c in CEILINGS_TO_COMPARE:
        ceiling_rows += run_n(
            schema_input["title"], schema_input["content"], c, N_CEILING_RUNS, f"ceiling_{c}"
        )
    all_rows += ceiling_rows
    ceiling_summary = {str(c): summarize_ceiling(ceiling_rows, c) for c in CEILINGS_TO_COMPARE}

    print(f"\n=== Experiment 3: adversarial input "
          f"({N_ADVERSARIAL_RUNS} runs, ceiling={ADV_CEILING}) ===")
    adv_rows = run_n(
        adv_input["title"], adv_input["content"], ADV_CEILING, N_ADVERSARIAL_RUNS, "adversarial"
    )
    all_rows += adv_rows
    adv_hit_rate = sum(1 for r in adv_rows if r["outcome"] == "hit_turn_ceiling") / len(adv_rows)

    csv_path = RAW / "schema_experiment_runs.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["label", "run_index", "turn_ceiling", "outcome", "turn_count", "latency_ms", "started_at"]
        )
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    json_path = RAW / "schema_experiment_runs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2)

    summary = {
        "classification_30_runs": classify_summary,
        "ceiling_comparison": ceiling_summary,
        "adversarial": {"n": len(adv_rows), "hit_ceiling_rate": round(adv_hit_rate, 3)},
    }
    summary_path = RAW / "schema_experiment_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nRaw rows (CSV): {csv_path}")
    print(f"Raw rows (JSON): {json_path}")
    print(f"Summary: {summary_path}")
    print(f"\n=== finished {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
