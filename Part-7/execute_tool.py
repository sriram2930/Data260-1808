"""
Part-7/execute_tool.py -- DATA-260 HW5, Part 4.22 (single safe tool entry point)

execute_tool(name, inputs) is the one function the Part 5 agent calls to run
any of the three domain tools (domain_server.py's _..._impl functions,
reused directly here rather than going back over the MCP/STDIO protocol --
execute_tool is the in-process call path, domain_server.py is the
MCP-over-STDIO path, same underlying logic either way).

Always returns a JSON string of the {ok, data, error} envelope (envelope.py)
-- never raises, even for an unknown tool name or a completely unexpected
exception, so a caller (the agent, or the test runner) never needs its own
try/except around this call.

The session= parameter exists purely for Part 4's offline test runner
(test_tools.py) to inject a temporary database via dependency injection
instead of hitting the real MySQL container.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from domain_server import _course_detail_impl, _department_stats_impl, _search_courses_impl
from envelope import fail

_TOOLS = {
    "search_courses": _search_courses_impl,
    "course_detail": _course_detail_impl,
    "department_stats": _department_stats_impl,
}


def execute_tool(name: str, inputs: dict, *, session: Optional[Any] = None) -> str:
    """Runs one of the three domain tools by name. Always returns a JSON
    string of {ok, data, error} -- never raises."""
    impl = _TOOLS.get(name)
    if impl is None:
        return json.dumps(fail(f"unknown tool: {name!r} (known tools: {sorted(_TOOLS)})"))

    if not isinstance(inputs, dict):
        return json.dumps(fail("inputs must be a dict"))

    try:
        result = impl(**inputs, session=session)
    except TypeError as exc:
        # Wrong/missing argument names for this tool -- a bad call shape,
        # not a crash.
        return json.dumps(fail(f"bad inputs for {name}: {exc}"))
    except Exception as exc:  # noqa: BLE001 -- execute_tool must never raise
        return json.dumps(fail(f"{name} raised an unexpected error: {exc}"))

    return json.dumps(result)
