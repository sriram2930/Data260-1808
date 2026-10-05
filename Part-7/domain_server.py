"""
Part-7/domain_server.py -- DATA-260 HW5, Part 2.B (required domain MCP server)

A second local MCP server, over this project's own s1808_rel domain data
(the Campus Course Catalogue -- Course/Department, from Part-1/models.py),
with exactly three tools:

  search_courses(query, limit)     -- search
  course_detail(course_id)         -- detail lookup
  department_stats(department_id)  -- aggregate operation

All three return the {ok, data, error} envelope from envelope.py (the same
shape Part 4's execute_tool reuses). Each public tool function is a thin
MCP-schema wrapper around a private `_..._impl` function that takes an
optional `session` for dependency injection -- that's what lets Part 4's
offline test runner exercise this logic against a temporary in-memory
database instead of the real MySQL container (see test_tools.py).

STDIO logging rule: never print to stdout. All logging goes to stderr.

Run and debug with the MCP Inspector:
    mcp dev domain_server.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-1"))

from db import db_session_basede26  # noqa: E402
from models import Course, Department  # noqa: E402
from envelope import ok, fail  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s domain_server: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("domain_server")

mcp = FastMCP("s1808_rel-domain")


def _session_scope(session: Optional[Any]):
    """Returns (session, should_close) -- reuses an injected session for
    tests, or opens+closes a real one against MySQL otherwise."""
    if session is not None:
        return session, False
    return db_session_basede26(), True


def _search_courses_impl(query: str, limit: int = 10, session: Optional[Any] = None) -> dict:
    if not isinstance(query, str) or not query.strip():
        return fail("query must be a non-empty string")
    if not isinstance(limit, int) or not (1 <= limit <= 100):
        return fail("limit must be an integer between 1 and 100")

    db, should_close = _session_scope(session)
    try:
        like = f"%{query.strip()}%"
        rows = (
            db.query(Course)
            .filter((Course.course_code.like(like)) | (Course.course_title.like(like)))
            .order_by(Course.id)
            .limit(limit)
            .all()
        )
        data = [
            {
                "id": c.id,
                "course_code": c.course_code,
                "course_title": c.course_title,
                "department_id": c.department_id,
                "seats_available": c.seats_available,
            }
            for c in rows
        ]
        return ok(data)
    except Exception as exc:  # noqa: BLE001 -- clean error envelope, never crash the caller
        log.error("search_courses failed: %s", exc)
        return fail(f"search_courses failed: {exc}")
    finally:
        if should_close:
            db.close()


def _course_detail_impl(course_id: int, session: Optional[Any] = None) -> dict:
    if not isinstance(course_id, int) or course_id <= 0:
        return fail("course_id must be a positive integer")

    db, should_close = _session_scope(session)
    try:
        c = db.query(Course).filter_by(id=course_id).first()
        if not c:
            return fail(f"course_id {course_id} not found")
        dept = db.query(Department).filter_by(id=c.department_id).first() if c.department_id else None
        data = {
            "id": c.id,
            "course_code": c.course_code,
            "course_title": c.course_title,
            "description": c.description,
            "seats_available": c.seats_available,
            "department": (
                {"id": dept.id, "name": dept.name, "dept_code": dept.dept_code} if dept else None
            ),
        }
        return ok(data)
    except Exception as exc:  # noqa: BLE001
        log.error("course_detail failed: %s", exc)
        return fail(f"course_detail failed: {exc}")
    finally:
        if should_close:
            db.close()


def _department_stats_impl(department_id: int, session: Optional[Any] = None) -> dict:
    if not isinstance(department_id, int) or department_id <= 0:
        return fail("department_id must be a positive integer")

    db, should_close = _session_scope(session)
    try:
        dept = db.query(Department).filter_by(id=department_id).first()
        if not dept:
            return fail(f"department_id {department_id} not found")
        courses = db.query(Course).filter_by(department_id=department_id).all()
        count = len(courses)
        total_seats = sum(c.seats_available for c in courses)
        avg_seats = round(total_seats / count, 2) if count else 0.0
        data = {
            "department_id": dept.id,
            "department_name": dept.name,
            "course_count": count,
            "total_seats_available": total_seats,
            "avg_seats_available": avg_seats,
        }
        return ok(data)
    except Exception as exc:  # noqa: BLE001
        log.error("department_stats failed: %s", exc)
        return fail(f"department_stats failed: {exc}")
    finally:
        if should_close:
            db.close()


@mcp.tool()
def search_courses(query: str, limit: int = 10) -> dict[str, Any]:
    """Search courses by course_code or course_title substring match."""
    return _search_courses_impl(query, limit)


@mcp.tool()
def course_detail(course_id: int) -> dict[str, Any]:
    """Get full details for one course, including its department."""
    return _course_detail_impl(course_id)


@mcp.tool()
def department_stats(department_id: int) -> dict[str, Any]:
    """Aggregate: course count, total and average seats_available for a department."""
    return _department_stats_impl(department_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
