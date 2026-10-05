"""
Part-7/test_tools.py -- DATA-260 HW5, Part 4.23-24 (offline test runner)

Assert-based tests against execute_tool for all three domain tools, one
valid and one invalid input case each (6 minimum), plus two extra cases
exercising execute_tool itself (unknown tool name, malformed inputs). Runs
fully offline and repeatably: make_test_session() builds a temporary
in-memory SQLite database from the same SQLAlchemy models as the real
MySQL-backed one (Part-1/models.py), seeds two fixture rows, and every test
injects that session into execute_tool via its session= parameter --
dependency injection, so no network, no MySQL container, and no LLM.

Part 5.III adds two more tests here afterward (safety-rule block,
run_agent's MockModel max_steps stop).

Run:
    python test_tools.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-1"))

from db import Base  # noqa: E402
from models import Course, Department  # noqa: E402

from execute_tool import execute_tool  # noqa: E402

TEST_DEPT_ID = 1
TEST_COURSE_1_ID = 1
TEST_COURSE_2_ID = 2


def make_test_session():
    """A fresh in-memory SQLite DB per call, seeded with one department and
    two courses -- a temporary fixture, not the real MySQL database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    dept = Department(id=TEST_DEPT_ID, name="Test Dept", dept_code="TD", building="Bldg 1")
    session.add(dept)
    session.add(
        Course(
            id=TEST_COURSE_1_ID,
            course_code="TD-00001",
            course_title="Intro to Testing",
            department_id=TEST_DEPT_ID,
            seats_available=25,
        )
    )
    session.add(
        Course(
            id=TEST_COURSE_2_ID,
            course_code="TD-00002",
            course_title="Advanced Testing",
            department_id=TEST_DEPT_ID,
            seats_available=15,
        )
    )
    session.commit()
    return session


def run_tests() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        results.append((name, condition, detail))

    session = make_test_session()

    # --- search_courses -----------------------------------------------
    out = json.loads(execute_tool("search_courses", {"query": "Testing", "limit": 10}, session=session))
    check(
        "search_courses: valid query finds both seeded courses",
        out["ok"] is True and len(out["data"]) == 2,
        f"got {out}",
    )

    out = json.loads(execute_tool("search_courses", {"query": "", "limit": 10}, session=session))
    check(
        "search_courses: empty query is rejected cleanly",
        out["ok"] is False and "non-empty" in (out["error"] or ""),
        f"got {out}",
    )

    # --- course_detail ---------------------------------------------------
    out = json.loads(execute_tool("course_detail", {"course_id": TEST_COURSE_1_ID}, session=session))
    check(
        "course_detail: valid id returns the right course + department",
        out["ok"] is True
        and out["data"]["course_code"] == "TD-00001"
        and out["data"]["department"]["dept_code"] == "TD",
        f"got {out}",
    )

    out = json.loads(execute_tool("course_detail", {"course_id": 999999}, session=session))
    check(
        "course_detail: nonexistent id is rejected cleanly (not a crash)",
        out["ok"] is False and "not found" in (out["error"] or ""),
        f"got {out}",
    )

    # --- department_stats -------------------------------------------------
    out = json.loads(execute_tool("department_stats", {"department_id": TEST_DEPT_ID}, session=session))
    check(
        "department_stats: valid id aggregates correctly (2 courses, 40 total seats, 20.0 avg)",
        out["ok"] is True
        and out["data"]["course_count"] == 2
        and out["data"]["total_seats_available"] == 40
        and out["data"]["avg_seats_available"] == 20.0,
        f"got {out}",
    )

    out = json.loads(execute_tool("department_stats", {"department_id": 999999}, session=session))
    check(
        "department_stats: nonexistent id is rejected cleanly (not a crash)",
        out["ok"] is False and "not found" in (out["error"] or ""),
        f"got {out}",
    )

    # --- execute_tool itself ----------------------------------------------
    out = json.loads(execute_tool("not_a_real_tool", {}, session=session))
    check(
        "execute_tool: unknown tool name is rejected cleanly (not a crash)",
        out["ok"] is False and "unknown tool" in (out["error"] or ""),
        f"got {out}",
    )

    out = json.loads(execute_tool("course_detail", {"wrong_arg": 1}, session=session))
    check(
        "execute_tool: malformed inputs (wrong arg name) are rejected cleanly (not a crash)",
        out["ok"] is False and "bad inputs" in (out["error"] or ""),
        f"got {out}",
    )

    session.close()
    return results


def main() -> int:
    results = run_tests()
    passed = 0
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{status}] {name}")
        if not ok:
            print(f"       {detail}")
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
