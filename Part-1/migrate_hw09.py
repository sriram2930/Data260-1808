"""
Part-1/migrate_hw09.py -- DATA-260 HW9, Part 1 (schema migration)

Adds courses.view_count (INT NOT NULL DEFAULT 0): the durable copy of the
Redis access counter. Redis holds the live count; every 10th increment is
written back to this column. Same idempotent add-column-if-missing pattern
as migrate_hw05.py / migrate_hw07.py -- safe to re-run.
"""

from __future__ import annotations

from db import engine
from sqlalchemy import text


def main() -> None:
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = DATABASE() "
                "AND table_name = 'courses' AND column_name = 'view_count'"
            )
        ).scalar()
        if exists:
            print("courses.view_count already present")
        else:
            conn.execute(text("ALTER TABLE courses ADD COLUMN view_count INT NOT NULL DEFAULT 0"))
            print("added courses.view_count")


if __name__ == "__main__":
    main()
