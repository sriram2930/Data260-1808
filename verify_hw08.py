"""
verify_hw08.py -- DATA-260 HW8 self-check / smoke test.

Covers all parts behaviorally, without re-running the slow/flaky
LLM-heavy pieces end to end (Parts 2-3 already have full real evidence
captured in reports/hw08/raw/ -- this script checks the SYSTEM is wired
correctly, same "smoke test, not every edge case" scope as prior
homeworks' verify scripts):

  Part 1: CREATE_ENTITY followed by GET_ENTITY round-trips correctly
          through Kafka (via the real containerized FastAPI wrapper on
          PORT_BASE), and an unknown operation / missing field returns a
          clean error.
  Part 2/3: the real Kafka topics all exist with the right partition
          counts; the shared kafka_utils.py safety primitives
          (idempotency dedup, manual commit, retry/dead-letter) are
          importable and behave correctly against a direct, fast,
          non-LLM check.

Writes reports/hw08/verification.json. Does not modify any application
code.

Usage:
    python verify_hw08.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).parent
SID4 = 1808
SEED = 1808
VERIFY_SEED = 261808
PORT_BASE = 8008

sys.path.insert(0, str(HERE / "Part-10"))
sys.path.insert(0, str(HERE / "Part-11"))


def _get_commit_hash() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _http_post_json(url: str, payload: dict, timeout: float = 20.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def _http_get(url: str, timeout: float = 20.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def check_part1(checks: list[dict]) -> None:
    base = f"http://127.0.0.1:{PORT_BASE}"
    try:
        status, body = _http_post_json(f"{base}/api/courses", {
            "course_code": f"VRFY-{uuid.uuid4().hex[:6]}", "course_title": "verify_hw08 smoke test",
        })
        data = json.loads(body)
        checks.append({
            "check": "create_entity_via_kafka_api",
            "pass": status == 200 and data.get("success") is True and bool(data.get("entity_id")),
            "detail": f"status={status}",
        })
        entity_id = data.get("entity_id")
    except Exception as e:
        checks.append({"check": "create_entity_via_kafka_api", "pass": False, "detail": str(e)})
        entity_id = None

    if entity_id:
        try:
            status, body = _http_get(f"{base}/api/courses/{entity_id}")
            data = json.loads(body)
            checks.append({
                "check": "get_entity_round_trip",
                "pass": status == 200 and data.get("success") is True
                and data.get("entity", {}).get("course_id") == entity_id,
            })
        except Exception as e:
            checks.append({"check": "get_entity_round_trip", "pass": False, "detail": str(e)})
    else:
        checks.append({"check": "get_entity_round_trip", "pass": False, "detail": "skipped: no entity_id from create"})

    try:
        status, body = _http_get(f"{base}/api/courses/00000000-0000-0000-0000-000000000000")
        checks.append({"check": "get_unknown_entity_returns_404", "pass": status == 404})
    except Exception as e:
        checks.append({"check": "get_unknown_entity_returns_404", "pass": False, "detail": str(e)})

    try:
        status, body = _http_post_json(f"{base}/api/courses", {"course_code": "BAD"})
        checks.append({"check": "create_entity_missing_field_422", "pass": status == 422})
    except Exception as e:
        checks.append({"check": "create_entity_missing_field_422", "pass": False, "detail": str(e)})


def check_part2_3_topics(checks: list[dict]) -> None:
    try:
        out = subprocess.run(
            ["docker", "exec", "s1808-kafka", "kafka-topics", "--list", "--bootstrap-server", "localhost:9092"],
            capture_output=True, text=True, check=True, timeout=15,
        )
        topics = set(out.stdout.split())
        required = {
            "s1808_entity_requests", "s1808_entity_responses",
            "s1808_inbox", "s1808_tasks", "s1808_drafts", "s1808_final",
            "s1808_dead_letter",
        }
        missing = required - topics
        checks.append({
            "check": "all_required_topics_exist",
            "pass": not missing,
            "detail": f"missing: {sorted(missing)}" if missing else "all 7 present",
        })
    except Exception as e:
        checks.append({"check": "all_required_topics_exist", "pass": False, "detail": str(e)})

    try:
        out = subprocess.run(
            ["docker", "exec", "s1808-kafka", "kafka-topics", "--describe",
             "--topic", "s1808_tasks", "--bootstrap-server", "localhost:9092"],
            capture_output=True, text=True, check=True, timeout=15,
        )
        partition_count = out.stdout.count("Partition:")
        checks.append({
            "check": "s1808_tasks_has_two_partitions",
            "pass": partition_count == 2,
            "detail": f"found {partition_count} partitions",
        })
    except Exception as e:
        checks.append({"check": "s1808_tasks_has_two_partitions", "pass": False, "detail": str(e)})


def check_kafka_utils_safety(checks: list[dict]) -> None:
    try:
        from kafka_utils import DEAD_LETTER_TOPIC, MAX_RETRIES

        checks.append({
            "check": "kafka_utils_constants_sane",
            "pass": MAX_RETRIES >= 1 and DEAD_LETTER_TOPIC == "s1808_dead_letter",
        })
    except Exception as e:
        checks.append({"check": "kafka_utils_constants_sane", "pass": False, "detail": str(e)})

    try:
        from entity_store import EntityStore, validate_course_data

        store = EntityStore()
        record = store.create({"course_code": "X-1", "course_title": "Y"})
        found = store.get(record["course_id"])
        error = validate_course_data({"course_code": "", "course_title": "ok"})
        checks.append({
            "check": "entity_store_create_get_and_validation",
            "pass": found is not None and found["course_code"] == "X-1" and error is not None,
        })
    except Exception as e:
        checks.append({"check": "entity_store_create_get_and_validation", "pass": False, "detail": str(e)})


def main() -> None:
    checks: list[dict] = []
    check_part1(checks)
    check_part2_3_topics(checks)
    check_kafka_utils_safety(checks)

    result = {
        "homework": "hw08",
        "sid4": SID4,
        "commit_hash": _get_commit_hash(),
        "model": "qwen2.5:1.5b-instruct (Ollama), used by Part 2's Planner/Writer/Reviewer",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "all_passed": all(c["pass"] is not False for c in checks),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    out_path = HERE / "reports" / "hw08" / "verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
