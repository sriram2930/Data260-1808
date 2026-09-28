"""
Part-1/run_n1_experiment.py -- DATA-260 HW4, Part 3.4-3.7

Hits /api/n1/naive and /api/n1/fixed at page sizes 10, 50, 200, 30 requests
each (180 requests total), recording the SQL query count (from the response
body) and client-measured latency per request. Computes p50/p95/p99 latency
per (page_size, version) group and writes both the raw 180 rows and the
summary table to reports/hw04/raw/.

Requires the FastAPI app (main.py) already running on PORT_BASE (8008) with
seed_n1.py already run.

Usage:
    python run_n1_experiment.py
"""

from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8008"
PAGE_SIZES = [10, 50, 200]
VERSIONS = ["naive", "fixed"]
N_REQUESTS = 30

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
RAW_DIR = REPO_ROOT / "reports" / "hw04" / "raw"


def percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def run_one(version: str, page_size: int, run_index: int) -> dict:
    t0 = time.perf_counter()
    resp = requests.get(f"{BASE_URL}/api/n1/{version}", params={"page_size": page_size})
    latency_ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    body = resp.json()
    return {
        "version": version,
        "page_size": page_size,
        "run_index": run_index,
        "sql_query_count": body["query_count"],
        "latency_ms": round(latency_ms, 3),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== DATA-260 HW4 Part 3 N+1 experiment started {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"{len(PAGE_SIZES)} page sizes x {len(VERSIONS)} versions x {N_REQUESTS} requests "
          f"= {len(PAGE_SIZES) * len(VERSIONS) * N_REQUESTS} total requests\n")

    all_rows = []
    for page_size in PAGE_SIZES:
        for version in VERSIONS:
            print(f"--- page_size={page_size} version={version} ---")
            for i in range(1, N_REQUESTS + 1):
                row = run_one(version, page_size, i)
                all_rows.append(row)
                print(f"  run {i}/{N_REQUESTS}: sql_query_count={row['sql_query_count']} "
                      f"latency={row['latency_ms']}ms")

    csv_path = RAW_DIR / "n1_experiment_runs.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["version", "page_size", "run_index", "sql_query_count", "latency_ms", "started_at"]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    json_path = RAW_DIR / "n1_experiment_runs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2)

    summary = []
    for page_size in PAGE_SIZES:
        for version in VERSIONS:
            group = [r for r in all_rows if r["page_size"] == page_size and r["version"] == version]
            latencies = [r["latency_ms"] for r in group]
            summary.append({
                "page_size": page_size,
                "version": version,
                "sql_stmts_per_req": group[0]["sql_query_count"],
                "p50_ms": round(percentile(latencies, 50), 2),
                "p95_ms": round(percentile(latencies, 95), 2),
                "p99_ms": round(percentile(latencies, 99), 2),
            })

    summary_path = RAW_DIR / "n1_experiment_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY ===")
    print(f"{'Page size':<11}{'Version':<9}{'SQL/req':<9}{'p50 (ms)':<10}{'p95 (ms)':<10}{'p99 (ms)':<10}")
    for s in summary:
        print(f"{s['page_size']:<11}{s['version']:<9}{s['sql_stmts_per_req']:<9}"
              f"{s['p50_ms']:<10}{s['p95_ms']:<10}{s['p99_ms']:<10}")

    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {summary_path}")
    print(f"\n=== finished {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
