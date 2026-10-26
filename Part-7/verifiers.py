"""
Part-7/verifiers.py -- DATA-260 HW7, Part 3.I (deterministic per-task verifiers)

One deterministic check per fixed verification task (A/B/C). Each verifier
looks at the REAL tool results already produced by this exact run (not a
hardcoded expected answer) and checks whether the final answer is actually
supported by them -- this is what lets Reflexion catch "technically
finished, but the answer doesn't match what the tools returned" failures,
like Task B's model once answering "No courses found" right after a
department_stats call that returned course_count=1257.

Each verifier returns {"passed": bool, "reason": str} -- reason is always
filled in (even on pass), since reflexion.py logs it as the evidence for
any reflection.
"""

from __future__ import annotations

import re


def _tool_results(result: dict, tool_name: str) -> list[dict]:
    return [s["result"]["data"] for s in result["steps"] if s["type"] == "tool_call" and s["tool"] == tool_name and s["result"]["ok"]]


def verify_task_a(result: dict) -> dict:
    searches = _tool_results(result, "search_courses")
    if not searches or not searches[0]:
        return {"passed": False, "reason": "no successful search_courses call with results found in this run"}
    first_hit_code = searches[0][0]["course_code"]
    final = (result.get("final_answer") or "")
    if first_hit_code not in final:
        return {
            "passed": False,
            "reason": f"final answer does not mention {first_hit_code!r}, the actual first search result",
        }
    return {"passed": True, "reason": f"final answer mentions {first_hit_code!r} as expected"}


def verify_task_b(result: dict) -> dict:
    stats = _tool_results(result, "department_stats")
    if not stats:
        return {"passed": False, "reason": "no successful department_stats call found in this run"}
    course_count = stats[0]["course_count"]
    final = (result.get("final_answer") or "")
    if str(course_count) not in final:
        return {
            "passed": False,
            "reason": f"final answer does not mention the real course_count ({course_count}) from department_stats",
        }
    return {"passed": True, "reason": f"final answer mentions the real course_count ({course_count})"}


def verify_task_c(result: dict) -> dict:
    details = _tool_results(result, "course_detail")
    final = (result.get("final_answer") or "")
    codes_mentioned = {d["course_code"] for d in details if d and d.get("course_code") in final}
    needed = {"CS-00005", "DATA-00006"}
    missing = needed - codes_mentioned
    if missing:
        return {"passed": False, "reason": f"final answer is missing a comparison of: {sorted(missing)}"}
    return {"passed": True, "reason": "final answer mentions both compared course codes"}


VERIFIERS = {"A": verify_task_a, "B": verify_task_b, "C": verify_task_c}


_COURSE_CODE_PATTERN = re.compile(r"\b[A-Z]{2,5}-\d{4,6}\b")


def count_unsupported_claims(result: dict) -> int:
    """Scans the final answer for course-code-shaped substrings and counts
    how many never appeared in any tool result from this same run -- a
    simple, generic proxy for "the model invented a reference that was
    never actually returned by a tool", used by the Part 3.III comparison
    table's "Unsupported claims" row."""
    final = result.get("final_answer") or ""
    claimed_codes = set(_COURSE_CODE_PATTERN.findall(final))
    if not claimed_codes:
        return 0
    seen_codes = set()
    for step in result["steps"]:
        if step["type"] == "tool_call" and step["result"].get("ok"):
            data = step["result"]["data"]
            rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
            for row in rows:
                if isinstance(row, dict) and "course_code" in row:
                    seen_codes.add(row["course_code"])
    return len(claimed_codes - seen_codes)
