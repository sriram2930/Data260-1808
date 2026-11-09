"""
Part-12/counter_demo.py -- DATA-260 HW9, Part 1 demo ("=== Testing Counter ===")

Resets the demo course's Redis key and view_count column to 0 so the
transcript starts at Access #1, makes 25 accesses, and prints the Redis
value next to the database value after each so the "DB only changes every
10th access" behaviour is visible. Student: Sreeramachandrasai Achutuni (SID4 1808).

Run from the repo root:  python Part-12/counter_demo.py [course_id]
"""

from __future__ import annotations

import logging
import sys

from course_store import CourseStore
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
# The log line the assignment shows: "✓ Synced views to database"
logging.getLogger("course_store").handlers = []


class _Tick(logging.Handler):
    def emit(self, record):
        print(f"✓ {record.getMessage()}")


logging.getLogger("course_store").addHandler(_Tick())
logging.getLogger("course_store").propagate = False

COURSE_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 7  # CS-00005


def main() -> None:
    store = CourseStore()
    store.redis_client.delete(store.views_key(COURSE_ID))
    with store._session_factory() as s:
        s.execute(text("UPDATE courses SET view_count = 0 WHERE id = :id"), {"id": COURSE_ID})
        s.commit()
        code = s.execute(text("SELECT course_code FROM courses WHERE id = :id"), {"id": COURSE_ID}).scalar()

    print("=== Testing Counter ===")
    print(f"(student: Sreeramachandrasai Achutuni | key {store.views_key(COURSE_ID)} | course {code})\n")
    for i in range(1, 26):
        total = store.increment_course_views(COURSE_ID)
        print(f"Access #{i}: Total = {total}   [redis={store.redis_client.get(store.views_key(COURSE_ID))} db={store.db_view_count(COURSE_ID)}]")
    print(f"\nFinal: redis={store.redis_client.get(store.views_key(COURSE_ID))}  db.view_count={store.db_view_count(COURSE_ID)} (last sync at 20; 21-25 live only in Redis)")


if __name__ == "__main__":
    main()
