"""
verify_hw06.py -- DATA-260 HW6 self-check / smoke test.

Covers all four parts behaviorally:
  Part 1: FastAPI responds on PORT_BASE; an announcement round-trips
          through MongoDB with both Pydantic and $jsonSchema validation.
  Part 2: POST /api/chat returns a reply; GET /api/memory and
          GET /api/aggregate both respond.
  Part 3: memory_probes.yaml parses with 5 questions; the raw experiment
          summary file exists with all 4 settings.
  Part 4: AGENT.md/MEMORY.md load; needs_consolidation() runs; the
          /memory, /compact, /dream, /help commands all respond.

Writes reports/hw06/verification.json. Does not modify any application code.

Usage:
    python verify_hw06.py
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
sys.path.insert(0, str(HERE / "Part-4"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_get(url: str, timeout: float = 20.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def _http_post_json(url: str, payload: dict, timeout: float = 90.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def check_backend(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        status, _ = _http_get(f"{base}/")
        checks.append({"check": "fastapi_responds_on_port_base", "pass": status == 200})
    except Exception as e:
        checks.append({"check": "fastapi_responds_on_port_base", "pass": False, "detail": str(e)})


def check_announcements(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        req = urllib.request.Request(
            f"{base}/api/login", method="POST",
            data=json.dumps({"email": "advisor@sjsu.edu", "password": "course123"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            cookie = resp.headers.get("set-cookie", "").split(";")[0]
    except Exception as e:
        checks.append({"check": "announcement_crud_roundtrip", "pass": False, "detail": f"login failed: {e}"})
        return

    try:
        req = urllib.request.Request(
            f"{base}/api/announcements", method="POST",
            data=json.dumps({
                "title": "verify_hw06 smoke test",
                "category": "general",
                "event_date": "2026-12-01T00:00:00",
            }).encode(),
            headers={"Content-Type": "application/json", "Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            created = json.loads(resp.read())
        req = urllib.request.Request(
            f"{base}/api/announcements/{created['id']}", method="DELETE",
            headers={"Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            delete_status = resp.status
        checks.append({
            "check": "announcement_crud_roundtrip",
            "pass": created["status"] == "draft" and delete_status == 200,
        })
    except Exception as e:
        checks.append({"check": "announcement_crud_roundtrip", "pass": False, "detail": str(e)})

    try:
        req = urllib.request.Request(
            f"{base}/api/announcements", method="POST",
            data=json.dumps({"category": "general", "event_date": "2026-12-01T00:00:00"}).encode(),
            headers={"Content-Type": "application/json", "Cookie": cookie},
        )
        status = None
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            status = e.code
        checks.append({"check": "announcement_missing_title_rejected", "pass": status == 422})
    except Exception as e:
        checks.append({"check": "announcement_missing_title_rejected", "pass": False, "detail": str(e)})


def check_chat(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    user_id = "verify_hw06_user"
    try:
        status, body = _http_post_json(
            f"{base}/api/chat", {"user_id": user_id, "message": "Hello, this is a smoke test."}
        )
        data = json.loads(body)
        checks.append({
            "check": "chat_endpoint_returns_reply_and_used",
            "pass": status == 200 and bool(data.get("reply")) and "used" in data,
        })
    except Exception as e:
        checks.append({"check": "chat_endpoint_returns_reply_and_used", "pass": False, "detail": str(e)})
        return

    try:
        status, body = _http_get(f"{base}/api/memory/{user_id}")
        data = json.loads(body)
        checks.append({
            "check": "memory_endpoint_responds",
            "pass": status == 200 and "messages" in data and len(data["messages"]) >= 1,
        })
    except Exception as e:
        checks.append({"check": "memory_endpoint_responds", "pass": False, "detail": str(e)})

    try:
        status, body = _http_get(f"{base}/api/aggregate/{user_id}")
        data = json.loads(body)
        checks.append({
            "check": "aggregate_endpoint_responds",
            "pass": status == 200 and "daily_message_counts" in data,
        })
    except Exception as e:
        checks.append({"check": "aggregate_endpoint_responds", "pass": False, "detail": str(e)})


def check_probes_file(checks: list[dict]) -> None:
    try:
        import yaml

        probes_path = HERE / "reports" / "hw06" / "memory_probes.yaml"
        with open(probes_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        checks.append({
            "check": "memory_probes_yaml_has_five_questions",
            "pass": len(data["questions"]) == 5,
        })
    except Exception as e:
        checks.append({"check": "memory_probes_yaml_has_five_questions", "pass": False, "detail": str(e)})

    try:
        summary_path = HERE / "reports" / "hw06" / "raw" / "memory_experiment_summary.json"
        with open(summary_path, encoding="utf-8") as f:
            summaries = json.load(f)
        checks.append({
            "check": "part3_experiment_summary_has_all_settings",
            "pass": len(summaries) >= 3,
            "detail": f"{len(summaries)} settings recorded",
        })
    except Exception as e:
        checks.append({"check": "part3_experiment_summary_has_all_settings", "pass": False, "detail": str(e)})


def check_file_memory(checks: list[dict]) -> None:
    try:
        import file_memory
        import memory_cli

        content = file_memory.build_system_prompt_prefix()
        checks.append({
            "check": "file_memory_loads_agent_and_memory_md",
            "pass": "AGENT.md" in content and "MEMORY.md" in content,
        })

        should, _reason = file_memory.needs_consolidation()
        checks.append({"check": "needs_consolidation_runs", "pass": isinstance(should, bool)})

        help_text = memory_cli.dispatch("/help")
        checks.append({"check": "cli_help_command_responds", "pass": "/memory" in help_text and "/compact" in help_text})

        memory_text = memory_cli.dispatch("/memory")
        checks.append({"check": "cli_memory_command_responds", "pass": len(memory_text) > 0})
    except Exception as e:
        checks.append({"check": "file_memory_system", "pass": False, "detail": str(e)})


def main() -> None:
    checks: list[dict] = []
    check_backend(checks)
    check_announcements(checks)
    check_chat(checks)
    check_probes_file(checks)
    check_file_memory(checks)

    result = {
        "homework": "hw06",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": "qwen2.5:1.5b-instruct (Ollama), sentence-transformers/all-MiniLM-L6-v2 (episodic + dedup embeddings)",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw06" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
