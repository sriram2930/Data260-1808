"""
Part-7/reflexion.py -- DATA-260 HW7, Part 3 (bounded Reflexion self-correction)

run_agent_with_reflexion(task_label, prompt) runs the Part 2 agent loop,
checks the result with the matching deterministic verifier (verifiers.py),
and -- only if the check fails -- writes one short reflection (a concise
failure explanation + revised strategy, backed by the actual evidence from
the failed run) and retries with that reflection appended to the task
prompt. At most max_retries (2) retries, bounded by a hard token budget,
with a clean stop_reason: "success", "budget_exhausted", or "human_review"
(verifier never passed after retries were exhausted).

Safety/isolation (Part 3.II):
  - A reflection is a plain string appended to the USER-role prompt for
    the next attempt only. It is NEVER concatenated into SYSTEM_PROMPT,
    so it cannot alter the agent's instructions, and execute_tool's Part
    5.I safety rule runs unconditionally regardless of what a reflection
    says -- a reflection has no path to touch tool permissions or safety
    gates.
  - Reflections live only in this function's local `reflections` list,
    scoped to this one run_agent_with_reflexion() call. Nothing here
    reads or writes any shared/global store, so a reflection from one
    user's run can never leak into another run.
  - The reflection text logged is exactly "what failed + what to try
    differently" (the model is asked for 1-2 plain sentences) -- no raw
    model chain-of-thought is ever stored or shown.
"""

from __future__ import annotations

import time

from agent import run_agent
from verifiers import VERIFIERS, count_unsupported_claims

TOKEN_BUDGET = 6000


def _reflection_prompt(task_label: str, prompt: str, result: dict, verify: dict) -> list[dict]:
    last_tool_step = next((s for s in reversed(result["steps"]) if s["type"] == "tool_call"), None)
    evidence_lines = [f"Verifier result: FAILED -- {verify['reason']}"]
    if last_tool_step:
        evidence_lines.append(
            f"Last tool call: {last_tool_step['tool']}({last_tool_step['inputs']}) -> {last_tool_step['result']}"
        )
    evidence_lines.append(f"Final answer given: {result.get('final_answer')!r}")

    instruction = (
        "An assistant attempted the task below and a deterministic check found a problem. "
        "In exactly 1-2 plain sentences, explain what went wrong and what the assistant should "
        "do differently next time. Do not include step-by-step reasoning, only the concise "
        "explanation and the revised strategy.\n\n"
        f"Task: {prompt}\n\n" + "\n".join(evidence_lines)
    )
    return [{"role": "user", "content": instruction}]


def run_agent_with_reflexion(
    task_label: str, prompt: str, *, model=None, max_retries: int = 2, token_budget: int = TOKEN_BUDGET
) -> dict:
    verifier = VERIFIERS[task_label]
    reflections: list[dict] = []
    current_prompt = prompt
    t0 = time.perf_counter()
    result = run_agent(current_prompt, model=model, log=False)
    total_tokens = result["total_tokens"]
    verify = verifier(result)
    attempt = 0

    while not verify["passed"] and attempt < max_retries:
        if total_tokens >= token_budget:
            stop_reason = "budget_exhausted"
            break
        attempt += 1

        reflection_messages = _reflection_prompt(task_label, prompt, result, verify)
        reflect_model = model if model is not None else _reflection_model_default()
        reflection_response = reflect_model.complete(reflection_messages)
        total_tokens += reflection_response.get("usage", {}).get("total_tokens", 0)
        reflection_text = reflection_response["content"].strip()

        reflections.append({
            "attempt": attempt,
            "evidence": {
                "verifier_reason": verify["reason"],
                "last_tool_step": next(
                    (s for s in reversed(result["steps"]) if s["type"] == "tool_call"), None
                ),
                "final_answer": result.get("final_answer"),
            },
            "reflection": reflection_text,
        })

        current_prompt = (
            f"{prompt}\n\n"
            f"Reflection from a previous failed attempt (apply this correction): {reflection_text}"
        )
        result = run_agent(current_prompt, model=model, log=False)
        total_tokens += result["total_tokens"]
        verify = verifier(result)

        if total_tokens >= token_budget and not verify["passed"]:
            stop_reason = "budget_exhausted"
            break
    else:
        stop_reason = "success" if verify["passed"] else "human_review"

    return {
        "task_label": task_label,
        "final_answer": result.get("final_answer"),
        "verifier_passed": verify["passed"],
        "verifier_reason": verify["reason"],
        "unsupported_claims": count_unsupported_claims(result),
        "retry_count": attempt,
        "tool_call_count": result["tool_call_count"],
        "total_tokens": total_tokens,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "stop_reason": stop_reason,
        "reflections": reflections,
        "last_result": result,
    }


def _reflection_model_default():
    from agent import _get_real_model

    return _get_real_model()
