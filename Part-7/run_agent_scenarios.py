"""
Part-7/run_agent_scenarios.py -- DATA-260 HW5, Part 5.IV

Runs at least four scenarios through run_agent() against the real local
Ollama model, logging each to agent_runs.jsonl (via run_agent itself) and
printing a summary table (step count, stop reason, tool-call count) for
METRICS.md / the report.

Run:
    python run_agent_scenarios.py
"""

from __future__ import annotations

import time

from agent import run_agent

SCENARIOS = [
    "What are the details for course id 7?",
    "Give me the stats for department 1.",
    "Search for courses about Cloud Computing.",
    "Search for courses about data, with a limit of 50.",
]


def main() -> None:
    print(f"=== run_agent_scenarios.py started {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
    rows = []
    for i, scenario in enumerate(SCENARIOS, start=1):
        print(f"--- Scenario {i}: {scenario!r} ---")
        result = run_agent(scenario, max_steps=4)
        print(f"  stop_reason={result['stop_reason']} step_count={result['step_count']} tool_call_count={result['tool_call_count']}")
        print(f"  final_answer: {result['final_answer']!r}\n")
        rows.append({
            "scenario": scenario,
            "step_count": result["step_count"],
            "stop_reason": result["stop_reason"],
            "tool_call_count": result["tool_call_count"],
        })

    print("Summary:")
    print(f"{'#':<3}{'Steps':<8}{'Stop reason':<20}{'Tool calls':<12}Scenario")
    for i, r in enumerate(rows, start=1):
        print(f"{i:<3}{r['step_count']:<8}{r['stop_reason']:<20}{r['tool_call_count']:<12}{r['scenario']}")

    print(f"\n=== finished {time.strftime('%Y-%m-%dT%H:%M:%S')} ===")


if __name__ == "__main__":
    main()
