"""
verify_hw05.py -- DATA-260 HW5 self-check / smoke test.

Covers Parts 1-4 behaviorally (not exact wording; Part 5 isn't built yet, so
no agent-loop checks here -- this file gets extended once that lands, same
incremental pattern as the rest of HW5):

  Part 1:   FastAPI responds on PORT_BASE, login sets a session cookie, a
            Department create/list/delete round-trips, and an obviously
            malformed course_code is rejected.
  Part 2:   both MCP servers (meals, domain) start over real STDIO and
            respond to a real tool call.
  Part 3:   the retry policy actually produces all three documented
            behaviors (first-try success, fail-then-retry success,
            exhausted-retries clean error).
  Part 4:   execute_tool's offline test suite passes in full.

Writes reports/hw05/verification.json. Does not modify any application code.

Usage:
    python verify_hw05.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SID4 = 1808
SEED = 1808
VERIFY_SEED = 261808
PORT_BASE = 8008

sys.path.insert(0, str(HERE / "Part-7"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_get(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def _http_post_json(url: str, payload: dict, cookie: str = "", timeout: float = 10.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        cookie_out = resp.headers.get("set-cookie", "")
        return resp.status, resp.read().decode("utf-8"), cookie_out


def check_backend_and_department(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        status, _ = _http_get(f"{base}/")
        checks.append({"check": "fastapi_responds_on_port_base", "pass": status == 200})
    except Exception as e:
        checks.append({"check": "fastapi_responds_on_port_base", "pass": False, "detail": str(e)})
        return

    try:
        status, _, cookie = _http_post_json(
            f"{base}/api/login", {"email": "advisor@sjsu.edu", "password": "course123"}
        )
        session_cookie = cookie.split(";")[0] if cookie else ""
        checks.append({
            "check": "login_sets_session_cookie",
            "pass": status == 200 and "s1808_api_session" in cookie,
        })
    except Exception as e:
        checks.append({"check": "login_sets_session_cookie", "pass": False, "detail": str(e)})
        session_cookie = ""

    try:
        req = urllib.request.Request(
            f"{base}/api/departments", method="POST",
            data=json.dumps({"name": "Verify Dept", "dept_code": "VFY", "building": "N/A"}).encode(),
            headers={"Content-Type": "application/json", "Cookie": session_cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            created = json.loads(resp.read())

        req = urllib.request.Request(
            f"{base}/api/departments?limit=5", headers={"Cookie": session_cookie}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            listed = json.loads(resp.read())

        req = urllib.request.Request(
            f"{base}/api/departments/{created['id']}", method="DELETE",
            headers={"Cookie": session_cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            delete_status = resp.status

        checks.append({
            "check": "department_create_list_delete_roundtrip",
            "pass": created["dept_code"] == "VFY" and listed["total"] >= 1 and delete_status == 200,
        })
    except Exception as e:
        checks.append({"check": "department_create_list_delete_roundtrip", "pass": False, "detail": str(e)})

    try:
        req = urllib.request.Request(
            f"{base}/api/courses", method="POST",
            data=json.dumps({"course_code": "bad code", "course_title": "x"}).encode(),
            headers={"Content-Type": "application/json", "Cookie": session_cookie},
        )
        status = None
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            status = e.code
        checks.append({"check": "course_code_format_rejected", "pass": status == 422})
    except Exception as e:
        checks.append({"check": "course_code_format_rejected", "pass": False, "detail": str(e)})


async def _mcp_tool_call(script: str, tool: str, args: dict) -> bool:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    python = str(HERE / ".venv" / "Scripts" / "python.exe")
    params = StdioServerParameters(command=python, args=[str(HERE / "Part-7" / script)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return not result.isError


def check_mcp_servers(checks: list[dict]) -> None:
    try:
        ok = asyncio.run(_mcp_tool_call("meals_server.py", "random_meal", {}))
        checks.append({"check": "meals_mcp_server_responds_to_tool_call", "pass": ok})
    except Exception as e:
        checks.append({"check": "meals_mcp_server_responds_to_tool_call", "pass": False, "detail": str(e)})

    try:
        ok = asyncio.run(_mcp_tool_call("domain_server.py", "department_stats", {"department_id": 1}))
        checks.append({"check": "domain_mcp_server_responds_to_tool_call", "pass": ok})
    except Exception as e:
        checks.append({"check": "domain_mcp_server_responds_to_tool_call", "pass": False, "detail": str(e)})


def check_retry_policy(checks: list[dict]) -> None:
    try:
        from retry_policy import CountingFlakyOperation, RetryExhausted, call_with_retry

        _, attempts = call_with_retry(CountingFlakyOperation(fail_first_n=0), max_retries=2, base_delay_s=0.0, timeout_s=1.0)
        first_try_ok = len(attempts) == 1 and attempts[0].success

        _, attempts = call_with_retry(CountingFlakyOperation(fail_first_n=1), max_retries=2, base_delay_s=0.0, timeout_s=1.0)
        retry_ok = len(attempts) == 2 and not attempts[0].success and attempts[1].success

        exhausted_ok = False
        try:
            call_with_retry(CountingFlakyOperation(fail_first_n=99), max_retries=2, base_delay_s=0.0, timeout_s=1.0)
        except RetryExhausted as exc:
            exhausted_ok = len(exc.attempts) == 3 and all(not a.success for a in exc.attempts)

        checks.append({
            "check": "retry_policy_demonstrates_all_three_scenarios",
            "pass": first_try_ok and retry_ok and exhausted_ok,
        })
    except Exception as e:
        checks.append({"check": "retry_policy_demonstrates_all_three_scenarios", "pass": False, "detail": str(e)})


def check_agent(checks: list[dict]) -> None:
    try:
        from agent import MockModel, run_agent
        from execute_tool import execute_tool

        out = json.loads(execute_tool("search_courses", {"query": "a", "limit": 50}))
        checks.append({
            "check": "part5_safety_rule_blocks_oversized_search",
            "pass": out["ok"] is False and "safety rule" in (out["error"] or ""),
        })

        mock = MockModel(['{"tool": "department_stats", "inputs": {"department_id": 1}}'])
        result = run_agent("verify max_steps", model=mock, max_steps=2)
        checks.append({
            "check": "part5_mock_agent_stops_at_max_steps",
            "pass": result["stop_reason"] == "max_steps" and result["step_count"] == 2,
        })
    except Exception as e:
        checks.append({"check": "part5_agent_checks", "pass": False, "detail": str(e)})


def check_offline_tests(checks: list[dict]) -> None:
    try:
        from test_tools import run_tests

        results = run_tests()
        all_passed = all(ok for _, ok, _ in results) and len(results) >= 6
        checks.append({
            "check": "part4_offline_test_suite_passes",
            "pass": all_passed,
            "detail": f"{sum(1 for _, ok, _ in results if ok)}/{len(results)} passed",
        })
    except Exception as e:
        checks.append({"check": "part4_offline_test_suite_passes", "pass": False, "detail": str(e)})


def main() -> None:
    checks: list[dict] = []
    check_backend_and_department(checks)
    check_mcp_servers(checks)
    check_retry_policy(checks)
    check_agent(checks)
    check_offline_tests(checks)

    result = {
        "homework": "hw05",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": "qwen2.5:1.5b-instruct (Ollama), via Part-4's ModelClient (Part 5 agent loop)",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw05" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
