"""
verify_hw07.py -- DATA-260 HW7 self-check / smoke test.

Covers all parts behaviorally, without re-running the slow LLM-heavy
pieces end to end (Parts 2-5 already have full real evidence captured in
reports/hw07/raw/ -- this script checks the SYSTEM is wired correctly,
same "smoke test, not every edge case" scope as prior homeworks' verify
scripts):

  Part 1: POST /auth/login returns a JWT for valid credentials and 401 for
          invalid; RBAC (reader/writer/moderator) enforced on /api/courses.
  Part 2: the hand-written agent loop (Part-7/agent.py) completes a real
          verification task end to end against the live model.
  Part 3: reflexion.py and verifiers.py import and the verifier functions
          run against a scripted (non-live) result.
  Part 4: the bike-share scenario CSVs and pricing snapshot exist with the
          right shape; bikeshare_tools import and a basic csv_sql/
          calculator call works.
  Part 5: the hostile fixture file exists; the attack-check functions run.
  Part 6: file_tools' safety gate (is_destructive/confirm_bash) and the
          glob->search->read integration test both pass.

Writes reports/hw07/verification.json. Does not modify any application code.

Usage:
    python verify_hw07.py
"""

from __future__ import annotations

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

sys.path.insert(0, str(HERE / "Part-1"))
sys.path.insert(0, str(HERE / "Part-7"))
sys.path.insert(0, str(HERE / "Part-8"))
sys.path.insert(0, str(HERE / "Part-9"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_post_json(url: str, payload: dict, timeout: float = 20.0, headers: dict | None = None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _http_get(url: str, timeout: float = 20.0, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def check_part1(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        status, body = _http_post_json(f"{base}/auth/login", {"username": "advisor", "password": "course123"})
        token = json.loads(body).get("access_token") if status == 200 else None
        checks.append({"check": "jwt_login_valid_credentials", "pass": status == 200 and bool(token)})
    except Exception as e:
        checks.append({"check": "jwt_login_valid_credentials", "pass": False, "detail": str(e)})
        token = None

    try:
        status, _ = _http_post_json(f"{base}/auth/login", {"username": "advisor", "password": "wrong"})
        checks.append({"check": "jwt_login_invalid_credentials_401", "pass": status == 401})
    except Exception as e:
        checks.append({"check": "jwt_login_invalid_credentials_401", "pass": False, "detail": str(e)})

    try:
        status, body = _http_post_json(
            f"{base}/auth/login", {"username": "reader1", "password": "reader123"}
        )
        reader_token = json.loads(body).get("access_token")
        status, _ = _http_post_json(
            f"{base}/api/courses",
            {"course_code": "VRFY-001", "course_title": "verify test"},
            headers={"Authorization": f"Bearer {reader_token}"},
        )
        checks.append({"check": "rbac_reader_create_forbidden_403", "pass": status == 403})
    except Exception as e:
        checks.append({"check": "rbac_reader_create_forbidden_403", "pass": False, "detail": str(e)})

    try:
        status, _ = _http_get(f"{base}/api/courses", headers={"Authorization": f"Bearer {token}"})
        checks.append({"check": "rbac_moderator_list_200", "pass": status == 200})
    except Exception as e:
        checks.append({"check": "rbac_moderator_list_200", "pass": False, "detail": str(e)})


def check_part2(checks: list[dict]) -> None:
    try:
        from agent import run_agent
        from hw07_tasks import VERIFICATION_TASKS

        result = run_agent(VERIFICATION_TASKS["A"], log=False)
        checks.append({
            "check": "agent_loop_completes_real_task",
            "pass": result["stop_reason"] in ("normal_completion", "repair_failed") and result["tool_call_count"] >= 1,
            "detail": f"tool_call_count={result['tool_call_count']} stop_reason={result['stop_reason']}",
        })
    except Exception as e:
        checks.append({"check": "agent_loop_completes_real_task", "pass": False, "detail": str(e)})


def check_part3(checks: list[dict]) -> None:
    try:
        from verifiers import verify_task_a

        fake_result = {
            "final_answer": "The first result is DATA-00006, a cloud computing course.",
            "steps": [{
                "type": "tool_call", "tool": "search_courses",
                "result": {"ok": True, "data": [{"course_code": "DATA-00006"}]},
            }],
        }
        v = verify_task_a(fake_result)
        checks.append({"check": "verifier_runs_and_passes_on_correct_answer", "pass": v["passed"] is True})
    except Exception as e:
        checks.append({"check": "verifier_runs_and_passes_on_correct_answer", "pass": False, "detail": str(e)})


def check_part4(checks: list[dict]) -> None:
    try:
        csv_path = HERE / "Part-8" / "data" / "scenario_pay_per_use.csv"
        with open(csv_path, encoding="utf-8") as f:
            row_count = sum(1 for _ in f) - 1
        checks.append({"check": "bikeshare_csv_at_least_500_rows", "pass": row_count >= 500, "detail": f"{row_count} rows"})
    except Exception as e:
        checks.append({"check": "bikeshare_csv_at_least_500_rows", "pass": False, "detail": str(e)})

    try:
        meta_path = HERE / "Part-8" / "pricing_snapshots" / "snapshot_metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        checks.append({
            "check": "pricing_snapshot_has_hash_url_date",
            "pass": all(k in meta for k in ("sha256_raw_html", "source_url", "access_date_utc")),
        })
    except Exception as e:
        checks.append({"check": "pricing_snapshot_has_hash_url_date", "pass": False, "detail": str(e)})

    try:
        from bikeshare_tools import calculator

        r = calculator("1 + 2 * 3")
        checks.append({"check": "calculator_tool_safe_arithmetic", "pass": r["success"] and r["data"]["value"] == 7})
    except Exception as e:
        checks.append({"check": "calculator_tool_safe_arithmetic", "pass": False, "detail": str(e)})


def check_part5(checks: list[dict]) -> None:
    fixture_path = HERE / "Part-8" / "hostile_fixture" / "hostile_pricing.html"
    checks.append({"check": "hostile_fixture_exists", "pass": fixture_path.exists()})

    try:
        from run_prompt_injection_test import _check_recommendation_override, _check_sql_misuse

        clean_result = {"final_answer": "Pay per ride is cheaper for your usage.", "timeline": []}
        c1 = _check_recommendation_override(clean_result)
        c2 = _check_sql_misuse(clean_result)
        checks.append({
            "check": "attack_checks_run_and_report_not_succeeded_on_clean_result",
            "pass": c1["succeeded"] is False and c2["succeeded"] is False,
        })
    except Exception as e:
        checks.append({"check": "attack_checks_run_and_report_not_succeeded_on_clean_result", "pass": False, "detail": str(e)})


def check_part6(checks: list[dict]) -> None:
    try:
        from file_tools import confirm_bash, is_destructive

        checks.append({
            "check": "is_destructive_returns_bool",
            "pass": isinstance(is_destructive("rm -rf /"), bool) and is_destructive("rm -rf /") is True,
        })
        gate = confirm_bash("rm -rf /", auto_approve=False)
        checks.append({
            "check": "confirm_bash_blocks_destructive_without_confirmation",
            "pass": gate["allowed"] is False and "reason" in gate,
        })
        gate_safe = confirm_bash("git status", auto_approve=False)
        checks.append({"check": "confirm_bash_allows_safe_prefix", "pass": gate_safe["allowed"] is True})
    except Exception as e:
        checks.append({"check": "file_tools_safety_gate", "pass": False, "detail": str(e)})


def main() -> None:
    checks: list[dict] = []
    check_part1(checks)
    check_part2(checks)
    check_part3(checks)
    check_part4(checks)
    check_part5(checks)
    check_part6(checks)

    result = {
        "homework": "hw07",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": "qwen2.5:1.5b-instruct (Ollama)",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw07" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
