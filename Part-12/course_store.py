"""
Part-12/course_store.py -- DATA-260 HW9, Part 1 (Redis-backed view counter)

The primary domain entity is the Course (s1808_rel.courses). CourseStore is
the database/cache class; increment_course_views is the ONE new method the
assignment asks for.

Why Redis: counting a view with `UPDATE courses SET view_count = view_count + 1`
on every access is a disk write + row lock per request. INCR on an in-memory
key is atomic and cheap, so the hot path touches only Redis and the database
sees one write per 10 views.

Key format (must start with PREFIX): s1808:views:course:<id>
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import redis

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-1"))

from db import db_session_basede26  # noqa: E402
from sqlalchemy import text  # noqa: E402

PREFIX = "s1808"
SYNC_EVERY = 10

log = logging.getLogger("course_store")


class CourseStore:
    def __init__(self, redis_client: redis.Redis | None = None, session_factory=db_session_basede26):
        self.redis_client = redis_client or redis.Redis(host="localhost", port=6379, decode_responses=True)
        self._session_factory = session_factory

    @staticmethod
    def views_key(course_id: int) -> str:
        return f"{PREFIX}:views:course:{course_id}"

    def increment_course_views(self, course_id: int) -> int:
        """Count one access to `course_id` and return the running total.

        1. INCR the Redis counter (atomic; creates the key at 1 if missing).
        2. Every SYNC_EVERY-th increment (count % 10 == 0), write the count
           to courses.view_count and log "Synced views to database".
        3. Return the current count.
        """
        count = self.redis_client.incr(self.views_key(course_id))
        if count % SYNC_EVERY == 0:
            with self._session_factory() as session:
                session.execute(
                    text("UPDATE courses SET view_count = :c WHERE id = :id"),
                    {"c": count, "id": course_id},
                )
                session.commit()
            log.info("Synced views to database")
        return count

    def db_view_count(self, course_id: int) -> int:
        with self._session_factory() as session:
            return session.execute(
                text("SELECT view_count FROM courses WHERE id = :id"), {"id": course_id}
            ).scalar()
