"""
verify_hw02.py -- DATA-260 HW2 self-check / smoke test.

Starts the FastAPI backend, exercises add/update/delete/search behaviorally
(not exact wording), runs the LangGraph agent once to confirm it terminates
instead of hanging, and confirms the correction loop actually routes back to
the Planner. Writes reports/hw02/verification.json.

Does not modify any application code -- it only imports/invokes it and talks
to the running server over HTTP.

Usage:
    python verify_hw02.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
SID4 = 1808
SEED = 1808
VERIFY_SEED = 261808
PORT_BASE = 8008
MODEL = "qwen2.5:1.5b-instruct"

sys.path.insert(0, str(HERE / "Part-2"))
sys.path.insert(0, str(HERE / "Part-4"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def _http_post(url: str, data: dict, timeout: float = 10.0):
    body = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in data.items()).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.geturl()


def check_fastapi(checks: list[dict]) -> None:
    proc = subprocess.Popen(
        [
            str(HERE / ".venv" / "Scripts" / "python.exe"),
            "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", str(PORT_BASE),
        ],
        cwd=str(HERE / "Part-1"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        up = False
        for _ in range(30):
            try:
                status, _ = _http_get(f"{base}/api/courses")
                if status == 200:
                    up = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        checks.append({"check": "fastapi_responds_on_port_base", "pass": up})
        if not up:
            return

        status, body = _http_get(f"{base}/api/courses")
        before = json.loads(body)
        checks.append({"check": "home_page_200", "pass": _http_get(base)[0] == 200})

        status, _ = _http_post(f"{base}/courses", {
            "courseCode": f"VERIFY-{VERIFY_SEED}", "courseTitle": "Verification Course",
            "department": "Engineering",
        })
        status, body = _http_get(f"{base}/api/courses")
        after_add = json.loads(body)
        checks.append({
            "check": "add_record_succeeds",
            "pass": status == 200 and len(after_add) == len(before) + 1,
        })

        status, _ = _http_post(f"{base}/courses/1/update", {
            "courseCode": "VERIFIED-1", "courseTitle": "Updated By Verify Script",
            "department": "Engineering",
        })
        status, body = _http_get(f"{base}/api/courses")
        rec1 = next((c for c in json.loads(body) if c["id"] == 1), None)
        checks.append({
            "check": "update_record_id1_succeeds",
            "pass": rec1 is not None and rec1["courseCode"] == "VERIFIED-1",
        })

        status, body = _http_get(f"{base}/api/courses")
        before_delete = json.loads(body)
        highest_id = max(c["id"] for c in before_delete)
        _http_post(f"{base}/courses/delete-highest", {})
        status, body = _http_get(f"{base}/api/courses")
        after_delete = json.loads(body)
        checks.append({
            "check": "delete_highest_id_succeeds",
            "pass": all(c["id"] != highest_id for c in after_delete)
            and len(after_delete) == len(before_delete) - 1,
        })

        status, body = _http_get(f"{base}/api/courses?q=VERIFIED")
        results = json.loads(body)
        checks.append({
            "check": "search_filters_by_primary_or_secondary_field",
            "pass": status == 200 and any(c["courseCode"] == "VERIFIED-1" for c in results),
        })
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def check_langgraph(checks: list[dict]) -> None:
    from agent_graph import run_graph

    t0 = time.time()
    result = run_graph(
        title="Verify Course", content="A short course used only for the HW2 smoke test.",
        turn_ceiling=6, stream=False,
    )
    elapsed = time.time() - t0
    checks.append({
        "check": "langgraph_finishes_without_hanging",
        "pass": elapsed < 120,
        "detail": f"finished in {elapsed:.1f}s",
    })

    outcome = result["outcome"]
    approved_ok = outcome in (
        "valid_first_attempt", "valid_after_1_retry", "valid_after_2plus_retries",
    )
    if approved_ok:
        tags = result["final_state"]["planner_proposal"]["tags"]
        checks.append({
            "check": "approved_run_returns_exactly_3_tags",
            "pass": len(tags) == 3,
        })
    else:
        checks.append({
            "check": "approved_run_returns_exactly_3_tags",
            "pass": None,
            "detail": "run hit the turn ceiling instead of being approved; not applicable this run",
        })

    forced = run_graph(
        title="Verify Course", content="A short course used only for the HW2 smoke test.",
        turn_ceiling=2, force_reviewer_issues=True, stream=False,
    )
    checks.append({
        "check": "correction_loop_routes_back_to_planner",
        "pass": forced["outcome"] == "hit_turn_ceiling" and forced["final_state"]["turn_count"] == 2,
        "detail": f"turn_count={forced['final_state']['turn_count']}, outcome={forced['outcome']}",
    })


def main() -> None:
    checks: list[dict] = []
    check_fastapi(checks)
    check_langgraph(checks)

    result = {
        "homework": "hw02",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": MODEL,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw02" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
