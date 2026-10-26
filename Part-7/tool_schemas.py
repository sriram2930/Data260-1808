"""
Part-7/tool_schemas.py -- DATA-260 HW7, Part 2 (tool JSON schemas + validation)

Minimal JSON Schema for each of the three domain tools (same three as
execute_tool.py), plus a validate() that checks a proposed tool call's
inputs against its schema before the call ever reaches execute_tool. This
lets the agent loop (agent.py) tell "malformed arguments" apart from
"unknown tool" apart from a downstream execution failure, which the
Part 2.III reliability measurement classifies separately.
"""

from __future__ import annotations

from typing import Any

TOOL_SCHEMAS: dict[str, dict] = {
    "search_courses": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
    },
    "course_detail": {
        "type": "object",
        "required": ["course_id"],
        "properties": {"course_id": {"type": "integer", "minimum": 1}},
    },
    "department_stats": {
        "type": "object",
        "required": ["department_id"],
        "properties": {"department_id": {"type": "integer", "minimum": 1}},
    },
}


def validate(tool_name: str, inputs: Any) -> list[str]:
    """Returns a list of human-readable problems (empty = valid). Does not
    raise -- an agent loop calls this before execute_tool and reprompts
    with the problem list if it's non-empty."""
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return [f"unknown tool: {tool_name!r} (known tools: {sorted(TOOL_SCHEMAS)})"]

    if not isinstance(inputs, dict):
        return [f"inputs must be a JSON object, got {type(inputs).__name__}"]

    problems: list[str] = []
    for field in schema["required"]:
        if field not in inputs:
            problems.append(f"missing required field: {field!r}")

    for field, value in inputs.items():
        spec = schema["properties"].get(field)
        if spec is None:
            problems.append(f"unexpected field: {field!r}")
            continue
        if spec["type"] == "string" and not isinstance(value, str):
            problems.append(f"{field!r} must be a string, got {type(value).__name__}")
        elif spec["type"] == "integer" and not (isinstance(value, int) and not isinstance(value, bool)):
            problems.append(f"{field!r} must be an integer, got {type(value).__name__}")
        elif spec["type"] == "string" and isinstance(value, str) and len(value) < spec.get("minLength", 0):
            problems.append(f"{field!r} must be at least {spec['minLength']} characters")
        elif spec["type"] == "integer" and isinstance(value, int):
            if "minimum" in spec and value < spec["minimum"]:
                problems.append(f"{field!r} must be >= {spec['minimum']}")
            if "maximum" in spec and value > spec["maximum"]:
                problems.append(f"{field!r} must be <= {spec['maximum']}")

    return problems
