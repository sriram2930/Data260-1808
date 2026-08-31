"""
run_nondeterminism.py — DATA-260 HW1, Part 3 (Measuring Non-Determinism)

Runs the Planner -> Reviewer -> Finalizer pipeline (agents_demo.run_pipeline) on one
fixed input: 20 times at temperature 0.7, then 20 times at temperature 0.0 (40 runs
total). For each temperature, reports the number of distinct tag sets, the tags that
appeared in all 20 runs, the tags that appeared in exactly one run, and latency
p50/p95/p99. Raw per-run rows are saved as CSV and JSON under reports/hw01/raw/.

A "tag set" is compared order-independently and case-insensitively (e.g. ["Data",
"pipelines"] and ["pipelines", "data"] count as the same set) since the assignment
is measuring semantic consistency of the tags produced, not their printed order.

Usage:
    python run_nondeterminism.py
"""

import csv
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from agents_demo import run_pipeline, DEFAULT_MODEL

HERE = Path(__file__).parent
CASES_DIR = HERE / "reports" / "hw01" / "cases"
RAW_DIR = HERE / "reports" / "hw01" / "raw"
INPUT_FILE = CASES_DIR / "nondeterminism_input.json"

N_RUNS = 20
TEMPERATURES = [0.7, 0.0]


def percentile(values, p):
    """Nearest-rank percentile (no numpy dependency needed for 20 samples)."""
    if not values:
        return float("nan")
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def tag_key(tags):
    """Order-independent, case-insensitive identity for a tag set."""
    return tuple(sorted(t.strip().lower() for t in tags))


def run_batch(title, content, temperature, n_runs, model=DEFAULT_MODEL):
    rows = []
    for i in range(1, n_runs + 1):
        started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        result = run_pipeline(title=title, content=content, temperature=temperature, model=model)
        row = {
            "run_index": i,
            "temperature": temperature,
            "tags": result["publish"]["tags"],
            "summary": result["publish"]["summary"],
            "latency_ms": round(result["latency_ms"], 1),
            "reviewer_approved": result["publish"]["reviewer_approved"],
            "finalizer_notes": result["publish"]["finalizer_notes"],
            "started_at": started_at,
        }
        rows.append(row)
        print(
            f"[{started_at}] [temp={temperature}] run {i}/{n_runs} -> "
            f"tags={row['tags']} latency={row['latency_ms']}ms",
            flush=True,
        )
    return rows


def summarize(rows):
    tag_sets = [tag_key(r["tags"]) for r in rows]
    distinct_sets = len(set(tag_sets))

    tag_counter = Counter()
    for r in rows:
        for t in set(x.strip().lower() for x in r["tags"]):
            tag_counter[t] += 1

    n = len(rows)
    in_all = sorted(t for t, c in tag_counter.items() if c == n)
    in_exactly_one = sorted(t for t, c in tag_counter.items() if c == 1)

    latencies = [r["latency_ms"] for r in rows]
    return {
        "distinct_tag_sets": distinct_sets,
        "tags_in_all_runs": in_all,
        "tags_in_exactly_one_run": in_exactly_one,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "latency_p99_ms": percentile(latencies, 99),
    }


def main():
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_FILE.exists():
        print(f"Missing fixed input file: {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    title, content = payload["title"], payload["content"]

    print(f"=== DATA-260 HW1 Part 3 - non-determinism run started {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Fixed input: {INPUT_FILE}")
    print(f"Model: {DEFAULT_MODEL} | Runs per temperature: {N_RUNS} | Temperatures: {TEMPERATURES}\n")

    all_rows = []
    summaries = {}
    for temp in TEMPERATURES:
        print(f"\n=== Running {N_RUNS} runs at temperature={temp} ===")
        rows = run_batch(title, content, temp, N_RUNS)
        all_rows.extend(rows)
        summaries[temp] = summarize(rows)

    csv_path = RAW_DIR / "nondeterminism_runs.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_index", "temperature", "tags", "summary", "latency_ms",
                "reviewer_approved", "finalizer_notes", "started_at",
            ],
        )
        writer.writeheader()
        for row in all_rows:
            out = dict(row)
            out["tags"] = json.dumps(out["tags"])
            out["finalizer_notes"] = json.dumps(out["finalizer_notes"])
            writer.writerow(out)

    json_path = RAW_DIR / "nondeterminism_runs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2)

    summary_path = RAW_DIR / "nondeterminism_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in summaries.items()}, f, indent=2)

    print("\n=== SUMMARY ===")
    for temp, s in summaries.items():
        print(f"\n--- temperature={temp} ---")
        print(json.dumps(s, indent=2))

    print(f"\nRaw rows (CSV): {csv_path}")
    print(f"Raw rows (JSON): {json_path}")
    print(f"Summary: {summary_path}")
    print(f"\n=== finished {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
