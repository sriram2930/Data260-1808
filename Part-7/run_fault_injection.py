"""
Part-7/run_fault_injection.py -- DATA-260 HW5, Part 3.19-20

1. Demonstrates the retry policy on three scenarios: success on the first
   attempt, failure then success after a retry, and failure through every
   allowed retry (clean RetryExhausted, not a crash).
2. Runs the required 150-call fault-injection experiment: 50 calls each at
   injected failure rates of 0%, 20%, and 50%, using VERIFY_SEED so the same
   seed reproduces the same success/failure sequence every run. Reports
   success rate, mean latency, and p99 latency per rate, and saves every
   call's raw record to reports/hw05/raw/.

Run:
    python run_fault_injection.py
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from retry_policy import CountingFlakyOperation, FlakyOperation, RetryExhausted, call_with_retry

VERIFY_SEED = 261808
RATES = [0.0, 0.20, 0.50]
CALLS_PER_RATE = 50
MAX_RETRIES = 2
BASE_DELAY_S = 0.02
TIMEOUT_S = 1.0

HERE = Path(__file__).parent
REPORT_DIR = HERE.parent / "reports" / "hw05"
RAW_DIR = REPORT_DIR / "raw"


def percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))
    return s[k]


def demonstrate_scenarios() -> list[str]:
    lines = []

    lines.append("--- Scenario A: success on the first attempt ---")
    op = CountingFlakyOperation(fail_first_n=0)
    result, attempts = call_with_retry(op, max_retries=MAX_RETRIES, base_delay_s=BASE_DELAY_S, timeout_s=TIMEOUT_S)
    lines.append(f"result={result!r} attempts_used={len(attempts)}")
    for a in attempts:
        lines.append(f"  attempt {a.attempt}: success={a.success} elapsed_ms={a.elapsed_ms:.1f} error={a.error}")

    lines.append("\n--- Scenario B: failure on attempt 1, success on retry (attempt 2) ---")
    op = CountingFlakyOperation(fail_first_n=1)
    result, attempts = call_with_retry(op, max_retries=MAX_RETRIES, base_delay_s=BASE_DELAY_S, timeout_s=TIMEOUT_S)
    lines.append(f"result={result!r} attempts_used={len(attempts)}")
    for a in attempts:
        lines.append(f"  attempt {a.attempt}: success={a.success} elapsed_ms={a.elapsed_ms:.1f} error={a.error}")

    lines.append(f"\n--- Scenario C: failure on every attempt (max_retries={MAX_RETRIES}, so {MAX_RETRIES + 1} attempts) ---")
    op = CountingFlakyOperation(fail_first_n=99)
    try:
        call_with_retry(op, max_retries=MAX_RETRIES, base_delay_s=BASE_DELAY_S, timeout_s=TIMEOUT_S)
        lines.append("UNEXPECTED: call succeeded")
    except RetryExhausted as exc:
        lines.append(f"RetryExhausted raised cleanly (no crash): {exc}")
        for a in exc.attempts:  # type: ignore[attr-defined]
            lines.append(f"  attempt {a.attempt}: success={a.success} elapsed_ms={a.elapsed_ms:.1f} error={a.error}")

    return lines


def run_experiment() -> tuple[list[dict], dict]:
    all_rows: list[dict] = []
    summary: dict = {}

    for rate in RATES:
        op = FlakyOperation(seed=VERIFY_SEED, failure_rate=rate)
        for call_index in range(CALLS_PER_RATE):
            t0 = time.perf_counter()
            try:
                _, attempts = call_with_retry(
                    op, max_retries=MAX_RETRIES, base_delay_s=BASE_DELAY_S, timeout_s=TIMEOUT_S
                )
                success = True
                error = None
            except RetryExhausted as exc:
                attempts = exc.attempts  # type: ignore[attr-defined]
                success = False
                error = str(exc)
            total_latency_ms = (time.perf_counter() - t0) * 1000
            all_rows.append(
                {
                    "failure_rate": rate,
                    "call_index": call_index,
                    "success": success,
                    "attempts_used": len(attempts),
                    "total_latency_ms": round(total_latency_ms, 3),
                    "error": error,
                }
            )

        rate_rows = [r for r in all_rows if r["failure_rate"] == rate]
        latencies = [r["total_latency_ms"] for r in rate_rows]
        successes = sum(1 for r in rate_rows if r["success"])
        summary[f"{int(rate * 100)}%"] = {
            "success_rate": round(successes / CALLS_PER_RATE, 3),
            "mean_latency_ms": round(sum(latencies) / len(latencies), 2),
            "p99_latency_ms": round(percentile(latencies, 99), 2),
        }

    return all_rows, summary


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    log_lines = [f"=== run_fault_injection.py started {time.strftime('%Y-%m-%dT%H:%M:%S')} ==="]
    log_lines.append(f"VERIFY_SEED={VERIFY_SEED}, max_retries={MAX_RETRIES}, base_delay_s={BASE_DELAY_S}, timeout_s={TIMEOUT_S}\n")

    log_lines.append("=== Part 3.19: retry policy demonstration ===")
    log_lines.extend(demonstrate_scenarios())

    log_lines.append("\n=== Part 3.20: 150-call fault-injection experiment ===")
    rows, summary = run_experiment()

    with open(RAW_DIR / "fault_injection_calls.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["failure_rate", "call_index", "success", "attempts_used", "total_latency_ms", "error"])
        writer.writeheader()
        writer.writerows(rows)

    with open(RAW_DIR / "fault_injection_calls.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)

    with open(RAW_DIR / "fault_injection_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    log_lines.append(f"\nTotal calls: {len(rows)} (expected {len(RATES) * CALLS_PER_RATE})")
    log_lines.append("\nSummary:")
    log_lines.append(f"{'Rate':<8}{'Success rate':<15}{'Mean latency (ms)':<20}{'p99 latency (ms)':<20}")
    for rate_label, stats in summary.items():
        log_lines.append(
            f"{rate_label:<8}{stats['success_rate']:<15}{stats['mean_latency_ms']:<20}{stats['p99_latency_ms']:<20}"
        )
    log_lines.append(f"\nRaw data: {RAW_DIR / 'fault_injection_calls.csv'}, {RAW_DIR / 'fault_injection_calls.json'}")
    log_lines.append(f"=== finished {time.strftime('%Y-%m-%dT%H:%M:%S')} ===")

    full_log = "\n".join(log_lines)
    print(full_log)
    with open(REPORT_DIR / "RUN_LOG.txt", "a", encoding="utf-8") as f:
        f.write(full_log + "\n\n")


if __name__ == "__main__":
    main()
