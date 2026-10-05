"""
Part-7/agent.py -- DATA-260 HW5, Part 5.II (agent loop)

run_agent(user_input) drives a simple tool-use loop against the local
Ollama model (via Part-4's ModelClient, same adapter used everywhere else
in this repo) and the three domain tools, through execute_tool (so the
Part 5.I safety rule is always enforced). The model is asked, each turn, to
reply with exactly one JSON object: either {"tool": name, "inputs": {...}}
to call a tool, or {"final": "..."} to stop. Every step (the model's raw
reply, any tool call + result, and the final stop reason) is logged to
agent_runs.jsonl.

MockModel lets the loop be tested offline (Part 5.III) without a live
Ollama server: it returns a pre-scripted sequence of "model replies" instead
of calling anything real.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

from execute_tool import execute_tool

HERE = Path(__file__).parent
AGENT_LOG_PATH = HERE.parent / "reports" / "hw05" / "raw" / "agent_runs.jsonl"

SYSTEM_PROMPT = """You are an assistant for a campus course catalogue. You have three tools:

- search_courses(query: str, limit: int) -- search courses by code or title
- course_detail(course_id: int) -- full detail for one course
- department_stats(department_id: int) -- course count / seat aggregates for a department

On every turn, reply with EXACTLY ONE JSON object and nothing else:
  To call a tool:  {"tool": "<name>", "inputs": {...}}
  To finish:       {"final": "<your answer to the user, in plain text>"}

Call a tool whenever you need information you do not already have from a
previous tool result in this conversation. Once you have enough information,
reply with {"final": ...} and stop."""


class MockModel:
    """A scripted stand-in for ModelClient, for offline tests (Part 5.III).
    `replies` is a list of JSON strings returned in order, one per call."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls = 0

    def complete(self, messages: list[dict], format: Optional[str] = None) -> dict:
        if self.calls >= len(self._replies):
            # Ran out of scripted replies -- keep looping so max_steps can
            # actually be exercised by a short script list like ["..."]*1.
            content = self._replies[-1]
        else:
            content = self._replies[self.calls]
        self.calls += 1
        return {"content": content, "usage": {"total_tokens": 0}}


def _get_real_model():
    from src.model_client import ModelClient

    return ModelClient()


def _parse_step(raw_content: str) -> dict:
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        return {"final": f"(could not parse model output as JSON: {raw_content[:200]!r})"}


def run_agent(user_input: str, *, model=None, max_steps: int = 6) -> dict:
    """Runs the tool-use loop. Returns a dict: final_answer, stop_reason
    ("normal_completion" | "max_steps"), steps (list), tool_call_count."""
    if model is None:
        model = _get_real_model()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    steps: list[dict] = []
    tool_call_count = 0
    final_answer = None
    stop_reason = "max_steps"

    for step_num in range(1, max_steps + 1):
        response = model.complete(messages, format="json")
        raw = response["content"]
        parsed = _parse_step(raw)

        if "final" in parsed:
            final_answer = parsed["final"]
            stop_reason = "normal_completion"
            steps.append({"step": step_num, "type": "final", "content": final_answer})
            break

        if "tool" in parsed:
            tool_name = parsed.get("tool")
            tool_inputs = parsed.get("inputs", {})
            result_json = execute_tool(tool_name, tool_inputs)
            tool_call_count += 1
            steps.append({
                "step": step_num,
                "type": "tool_call",
                "tool": tool_name,
                "inputs": tool_inputs,
                "result": json.loads(result_json),
            })
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"TOOL RESULT for {tool_name}: {result_json}"})
            continue

        # Model replied with neither "tool" nor "final" -- treat it as a
        # (malformed) final answer rather than looping forever on garbage.
        final_answer = parsed.get("final", raw)
        stop_reason = "normal_completion"
        steps.append({"step": step_num, "type": "final", "content": final_answer})
        break

    result = {
        "user_input": user_input,
        "final_answer": final_answer,
        "stop_reason": stop_reason,
        "steps": steps,
        "step_count": len(steps),
        "tool_call_count": tool_call_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    AGENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")

    return result
