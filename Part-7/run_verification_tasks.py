"""
Part-7/run_verification_tasks.py -- DATA-260 HW7, Part 2.I/2.II

Runs the three fixed verification tasks (A, B, C) and the error-recovery
case once each against the real local model, printing a compact
transcript of each tool call + the final answer, and asserting each
verification task used at least two tool calls without any follow-up
prompting (a single run_agent() call per task, by construction -- the
"without follow-up prompting" requirement is structural, not something a
transcript has to separately prove).

Run (backend/model must be available -- domain_server.py talks to MySQL
directly, no HTTP server needed):
    python run_verification_tasks.py
"""

from __future__ import annotations

from agent import run_agent
from hw07_tasks import ERROR_RECOVERY_TASK, VERIFICATION_TASKS


def _print_transcript(label: str, result: dict) -> None:
    print(f"=== {label} ===")
    print(f"prompt: {result['user_input']}\n")
    for step in result["steps"]:
        if step["type"] == "tool_call":
            print(f"  [tool call] {step['tool']}({step['inputs']}) -> {step['result']}")
        elif step["type"] == "invalid_tool_call":
            print(f"  [invalid call, reprompted] {step['tool']}({step['inputs']}) -- {step['problems']}")
        elif step["type"] == "final":
            print(f"  [final] {step['content']}")
    print(f"\nstop_reason={result['stop_reason']}  tool_call_count={result['tool_call_count']}  "
          f"repair_count={result['repair_count']}\n")


def main() -> None:
    for label, prompt in VERIFICATION_TASKS.items():
        result = run_agent(prompt)
        _print_transcript(f"Task {label}", result)
        if result["tool_call_count"] >= 2:
            print(f"PASS: Task {label} completed with {result['tool_call_count']} tool calls, no follow-up prompting.\n")
        else:
            print(f"FAIL: Task {label} used only {result['tool_call_count']} tool calls (needed >= 2).\n")

    error_result = run_agent(ERROR_RECOVERY_TASK)
    _print_transcript("Error recovery (nonexistent course_id)", error_result)
    if error_result["final_answer"] is not None:
        print("PASS: error-recovery case handled without crashing (execute_tool returned a usable error message).")
    else:
        print("FAIL: agent produced no final answer for the error-recovery case.")


if __name__ == "__main__":
    main()
