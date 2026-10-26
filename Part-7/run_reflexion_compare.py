"""
Part-7/run_reflexion_compare.py -- DATA-260 HW7, Part 3.III (original vs Reflexion)

Runs each of the three fixed verification tasks twice: once through the
plain Part 2 loop (run_agent, single pass, no retry) and once through the
Part 3 Reflexion loop (run_agent_with_reflexion, up to 2 retries gated by
the same deterministic verifiers), with the same model settings for both.
Every original-loop run is checked with the SAME verifier the Reflexion
loop uses, purely as a measurement -- the original loop itself never sees
or acts on the verifier's result.

Writes reports/hw07/raw/reflexion_compare.json and prints the comparison
table (averaged across the 3 tasks, except task_success and retry_rate
which are reported as "N of 3 tasks").

Run:
    python run_reflexion_compare.py
"""

from __future__ import annotations

import json
from pathlib import Path

from agent import run_agent
from hw07_tasks import VERIFICATION_TASKS
from reflexion import run_agent_with_reflexion
from verifiers import VERIFIERS, count_unsupported_claims

HERE = Path(__file__).parent
OUT_PATH = HERE.parent / "reports" / "hw07" / "raw" / "reflexion_compare.json"


def main() -> None:
    per_task = []

    for label, prompt in VERIFICATION_TASKS.items():
        print(f"=== Task {label}: original loop ===")
        orig = run_agent(prompt, log=False)
        orig_verify = VERIFIERS[label](orig)
        orig_claims = count_unsupported_claims(orig)
        print(f"  success={orig_verify['passed']} ({orig_verify['reason']}) "
              f"tool_calls={orig['tool_call_count']} tokens={orig['total_tokens']} "
              f"latency_ms={orig['latency_ms']} unsupported_claims={orig_claims}")

        print(f"=== Task {label}: Reflexion loop ===")
        refl = run_agent_with_reflexion(label, prompt)
        print(f"  success={refl['verifier_passed']} ({refl['verifier_reason']}) "
              f"retries={refl['retry_count']} tool_calls={refl['tool_call_count']} "
              f"tokens={refl['total_tokens']} latency_ms={refl['latency_ms']} "
              f"unsupported_claims={refl['unsupported_claims']} stop_reason={refl['stop_reason']}")
        for r in refl["reflections"]:
            print(f"    reflection (attempt {r['attempt']}): {r['reflection']}")

        per_task.append({
            "task": label,
            "original": {
                "success": orig_verify["passed"], "reason": orig_verify["reason"],
                "unsupported_claims": orig_claims, "tool_call_count": orig["tool_call_count"],
                "total_tokens": orig["total_tokens"], "latency_ms": orig["latency_ms"],
            },
            "reflexion": {
                "success": refl["verifier_passed"], "reason": refl["verifier_reason"],
                "retry_count": refl["retry_count"], "unsupported_claims": refl["unsupported_claims"],
                "tool_call_count": refl["tool_call_count"], "total_tokens": refl["total_tokens"],
                "latency_ms": refl["latency_ms"], "stop_reason": refl["stop_reason"],
                "reflections": refl["reflections"],
            },
        })
        print()

    n = len(per_task)
    orig_success = sum(1 for t in per_task if t["original"]["success"])
    refl_success = sum(1 for t in per_task if t["reflexion"]["success"])
    orig_claims_total = sum(t["original"]["unsupported_claims"] for t in per_task)
    refl_claims_total = sum(t["reflexion"]["unsupported_claims"] for t in per_task)
    refl_retries_total = sum(t["reflexion"]["retry_count"] for t in per_task)
    tasks_needing_retry = sum(1 for t in per_task if t["reflexion"]["retry_count"] > 0)

    summary = {
        "task_success": {"original": f"{orig_success}/{n}", "reflexion": f"{refl_success}/{n}"},
        "unsupported_claims": {"original": orig_claims_total, "reflexion": refl_claims_total},
        "retry_rate": {"original": f"0/{n}", "reflexion": f"{tasks_needing_retry}/{n} tasks ({refl_retries_total} total retries)"},
        "tool_calls_avg": {
            "original": round(sum(t["original"]["tool_call_count"] for t in per_task) / n, 1),
            "reflexion": round(sum(t["reflexion"]["tool_call_count"] for t in per_task) / n, 1),
        },
        "tokens_avg": {
            "original": round(sum(t["original"]["total_tokens"] for t in per_task) / n, 1),
            "reflexion": round(sum(t["reflexion"]["total_tokens"] for t in per_task) / n, 1),
        },
        "latency_ms_avg": {
            "original": round(sum(t["original"]["latency_ms"] for t in per_task) / n, 1),
            "reflexion": round(sum(t["reflexion"]["latency_ms"] for t in per_task) / n, 1),
        },
    }

    print("=== summary (averaged across 3 tasks) ===")
    print(json.dumps(summary, indent=2))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "per_task": per_task}, f, indent=2)
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
