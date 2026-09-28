"""
verify_hw04.py -- DATA-260 HW4 self-check / smoke test.

Covers all four parts behaviorally (not exact wording):
  Part 1/2: FastAPI responds on PORT_BASE, login sets a session cookie,
            the MySQL-backed CRUD API round-trips a record.
  Part 3:   naive and fixed /api/n1 endpoints both return data, and naive's
            SQL query count is strictly greater than fixed's at the same
            page size (proving the N+1 difference is real, not just that
            both endpoints "work").
  Part 4:   the RAG QA pipeline finishes without hanging and produces a
            non-empty answer for a normal question.

Writes reports/hw04/verification.json. Does not modify any application code.

Usage:
    python verify_hw04.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SID4 = 1808
SEED = 1808
VERIFY_SEED = 261808
PORT_BASE = 8008
MODEL = "qwen2.5:1.5b-instruct"

sys.path.insert(0, str(HERE / "Part-5"))


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


def check_backend_and_db(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        status, _ = _http_get(f"{base}/")
        checks.append({"check": "fastapi_responds_on_port_base", "pass": status == 200})
    except Exception as e:
        checks.append({"check": "fastapi_responds_on_port_base", "pass": False, "detail": str(e)})
        return

    try:
        status, body, cookie = _http_post_json(
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
        req = urllib.request.Request(f"{base}/api/courses", headers={"Cookie": session_cookie})
        with urllib.request.urlopen(req, timeout=10) as resp:
            before = json.loads(resp.read())

        req = urllib.request.Request(
            f"{base}/api/courses", method="POST",
            data=json.dumps({"course_code": "VERIFY-1", "course_title": "Verify Course"}).encode(),
            headers={"Content-Type": "application/json", "Cookie": session_cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            created = json.loads(resp.read())

        req = urllib.request.Request(f"{base}/api/courses", headers={"Cookie": session_cookie})
        with urllib.request.urlopen(req, timeout=10) as resp:
            after = json.loads(resp.read())

        checks.append({
            "check": "mysql_crud_create_and_list_roundtrip",
            "pass": len(after) == len(before) + 1 and created["course_code"] == "VERIFY-1",
        })

        req = urllib.request.Request(
            f"{base}/api/courses/{created['id']}", method="DELETE",
            headers={"Cookie": session_cookie},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        checks.append({"check": "mysql_crud_create_and_list_roundtrip", "pass": False, "detail": str(e)})


def check_n1_endpoints(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        _, naive_body = _http_get(f"{base}/api/n1/naive?page_size=10")
        _, fixed_body = _http_get(f"{base}/api/n1/fixed?page_size=10")
        naive = json.loads(naive_body)
        fixed = json.loads(fixed_body)
        checks.append({
            "check": "n1_naive_and_fixed_both_return_data",
            "pass": len(naive["courses"]) == 10 and len(fixed["courses"]) == 10,
        })
        checks.append({
            "check": "n1_naive_query_count_greater_than_fixed",
            "pass": naive["query_count"] > fixed["query_count"],
            "detail": f"naive={naive['query_count']}, fixed={fixed['query_count']}",
        })
    except Exception as e:
        checks.append({"check": "n1_naive_and_fixed_both_return_data", "pass": False, "detail": str(e)})


def check_rag(checks: list[dict]) -> None:
    import rag_qa as rq

    t0 = time.time()
    try:
        result = rq.answer_context_rag("What course should a CS major with no prior computing experience take?", k=3)
        elapsed = time.time() - t0
        checks.append({
            "check": "rag_pipeline_finishes_without_hanging",
            "pass": elapsed < 180,
            "detail": f"finished in {elapsed:.1f}s",
        })
        checks.append({
            "check": "rag_pipeline_returns_nonempty_answer",
            "pass": bool(result["content"].strip()),
        })
    except Exception as e:
        checks.append({"check": "rag_pipeline_finishes_without_hanging", "pass": False, "detail": str(e)})


def main() -> None:
    checks: list[dict] = []
    check_backend_and_db(checks)
    check_n1_endpoints(checks)
    check_rag(checks)

    result = {
        "homework": "hw04",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": MODEL,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw04" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
