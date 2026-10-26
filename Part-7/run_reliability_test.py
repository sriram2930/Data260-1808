"""
Part-7/run_reliability_test.py -- DATA-260 HW7, Part 2.III (20-attempt reliability measurement)

Cycles through the three fixed verification tasks (hw07_tasks.py), running
run_agent() repeatedly with the same model settings, until at least 20
individual tool-call ATTEMPTS have been observed (a single run_agent() call
can contain more than one attempt: every raw {"tool": ...} the model
proposes, whether it passes schema validation immediately, gets fixed by
the one-shot repair, or is never fixed).

Rate definitions:
  well_formed_before_repair = attempts valid on the model's FIRST try /
                               total attempts
  well_formed_after_repair  = attempts that ended up executing (first try
                               OR after the one allowed reprompt) /
                               total distinct tool-call slots

Failures are classified into exactly the four buckets the assignment
names:
  malformed_arguments      -- schema validation failed on a KNOWN tool
  unknown_tool              -- schema validation failed because the tool
                               name itself wasn't recognized
  text_when_tool_required   -- the task needs tool use, but the model's
                               very first step was a {"final": ...} with
                               zero tool calls
  lost_multi_step_chain     -- the run finished with tool_call_count < 2
                               (the structural minimum every fixed task
                               requires) despite making at least one
                               tool call -- i.e. it started the chain and
                               dropped it before finishing

Writes reports/hw07/raw/reliability_results.json (per-attempt data) and
prints the summary table.

Run:
    python run_reliability_test.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from agent import run_agent
from hw07_tasks import VERIFICATION_TASKS

MIN_ATTEMPTS = 20
HERE = Path(__file__).parent
OUT_PATH = HERE.parent / "reports" / "hw07" / "raw" / "reliability_results.json"


def _attempts_from_run(task_label: str, run_idx: int, result: dict) -> list[dict]:
    """Reconstructs one record per raw tool-call attempt (valid + invalid)
    from a single run_agent() result, in the order they happened.

    is_first_attempt is False only for a step that is itself a repair
    RETRY (the step immediately after an invalid_tool_call for the same
    slot) -- that covers both a successful repair (a tool_call right after
    an invalid one) and a failed repair's second, still-invalid attempt.
    "Slots" = attempts where is_first_attempt is True; a slot "resolves"
    if any tool_call step belongs to it (its own call, or its repair)."""
    attempts = []
    prev_was_invalid = False
    for step in result["steps"]:
        if step["type"] == "tool_call":
            attempts.append({
                "task": task_label, "run": run_idx, "step": step["step"],
                "tool": step["tool"], "is_first_attempt": not prev_was_invalid,
                "resolved": True, "classification": "well_formed",
            })
            prev_was_invalid = False
        elif step["type"] == "invalid_tool_call":
            is_unknown = any("unknown tool" in p for p in step["problems"])
            attempts.append({
                "task": task_label, "run": run_idx, "step": step["step"],
                "tool": step["tool"], "is_first_attempt": not prev_was_invalid,
                "resolved": False,
                "classification": "unknown_tool" if is_unknown else "malformed_arguments",
                "problems": step["problems"],
            })
            prev_was_invalid = True
        else:
            prev_was_invalid = False

    # A slot that started invalid but was followed by a successful repair
    # resolves -- mark its first-attempt record resolved=True too.
    for i, a in enumerate(attempts):
        if a["is_first_attempt"] and not a["resolved"] and i + 1 < len(attempts):
            nxt = attempts[i + 1]
            if not nxt["is_first_attempt"] and nxt["resolved"]:
                a["resolved"] = True

    return attempts


def main() -> None:
    all_attempts: list[dict] = []
    run_summaries: list[dict] = []
    task_cycle = itertools.cycle(VERIFICATION_TASKS.items())
    run_idx = 0

    while len(all_attempts) < MIN_ATTEMPTS:
        run_idx += 1
        label, prompt = next(task_cycle)
        result = run_agent(prompt, log=False)
        run_attempts = _attempts_from_run(label, run_idx, result)
        all_attempts.extend(run_attempts)

        first_step_is_final = result["steps"] and result["steps"][0]["type"] == "final"
        text_when_tool_required = bool(first_step_is_final)
        lost_multi_step_chain = (
            not text_when_tool_required and result["tool_call_count"] >= 1 and result["tool_call_count"] < 2
        )

        run_summaries.append({
            "run": run_idx, "task": label, "stop_reason": result["stop_reason"],
            "tool_call_count": result["tool_call_count"], "repair_count": result["repair_count"],
            "text_when_tool_required": text_when_tool_required,
            "lost_multi_step_chain": lost_multi_step_chain,
        })
        print(f"run {run_idx} (task {label}): tool_calls={result['tool_call_count']} "
              f"repairs={result['repair_count']} stop_reason={result['stop_reason']} "
              f"attempts_so_far={len(all_attempts)}/{MIN_ATTEMPTS}")

    # "Before repair" is measured over first attempts only (one per slot):
    # did the model's raw, un-repaired call pass schema validation?
    # "After repair" is measured over the same slots: did the slot end up
    # resolved at all, counting a successful one-shot repair as resolved.
    first_attempts = [a for a in all_attempts if a["is_first_attempt"]]
    total_slots = len(first_attempts)
    well_formed_first = sum(1 for a in first_attempts if a["classification"] == "well_formed")
    well_formed_after = sum(1 for a in first_attempts if a["resolved"])

    malformed_count = sum(1 for a in all_attempts if a["classification"] == "malformed_arguments")
    unknown_count = sum(1 for a in all_attempts if a["classification"] == "unknown_tool")
    text_required_count = sum(1 for r in run_summaries if r["text_when_tool_required"])
    lost_chain_count = sum(1 for r in run_summaries if r["lost_multi_step_chain"])

    summary = {
        "total_attempts": len(all_attempts),
        "total_slots": total_slots,
        "total_runs": run_idx,
        "well_formed_before_repair_rate": round(well_formed_first / total_slots, 3),
        "well_formed_after_repair_rate": round(well_formed_after / total_slots, 3),
        "failures": {
            "malformed_arguments": malformed_count,
            "unknown_tool": unknown_count,
            "text_when_tool_required": text_required_count,
            "lost_multi_step_chain": lost_chain_count,
        },
    }

    print("\n=== summary ===")
    print(json.dumps(summary, indent=2))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "attempts": all_attempts, "run_summaries": run_summaries}, f, indent=2)
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
