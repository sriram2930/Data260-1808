"""
Part-1/migrate_hw05.py -- DATA-260 HW5, Part 1.I (schema migration)

Applies the HW5 schema changes to the already-populated HW4 database instead
of dropping and recreating it (seed_n1.py's 5,000 courses stay intact):

  1. Creates the new `departments` table (Base.metadata.create_all only
     creates tables that don't exist yet, it never alters existing ones).
  2. Seeds the four departments already implied by HW4's seed data
     (Computer Science/CS, Data Science & AI/DATA, Business Analytics/BUS,
     Engineering/ENGR), each with a dept_code, a building, and timestamps.
  3. ALTERs `courses` to add department_id (FK), seats_available (numeric,
     default 30), created_at, updated_at -- SQLAlchemy can't add columns to
     an existing table on its own, so this part is raw SQL.
  4. Backfills department_id on all 5,000 existing rows from the old
     free-text `department` column, which is left in place untouched (HW4's
     Part 3 N+1 seed data and EXPLAIN index demo both depend on it).
  5. Adds a UNIQUE constraint on courses.course_code, after first checking
     there are no duplicates (the seed data already uses a globally unique
     per-row counter, so this should be a no-op check, not a real dedupe).

Safe to re-run: every step checks "does this already exist" before acting.
"""

from __future__ import annotations

from sqlalchemy import text

from db import Base, db_session_basede26, engine
import models  # noqa: F401
from models import Course, Department

DEPARTMENTS = [
    ("Computer Science", "CS", "Engineering Building, Room 210"),
    ("Data Science & AI", "DATA", "MacQuarrie Hall, Room 420"),
    ("Business Analytics", "BUS", "Lucas Hall, Room 310"),
    ("Engineering", "ENGR", "Engineering Building, Room 100"),
]


def column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(row)


def constraint_exists(conn, table: str, constraint: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.table_constraints "
            "WHERE table_schema = DATABASE() AND table_name = :t AND constraint_name = :c"
        ),
        {"t": table, "c": constraint},
    ).scalar()
    return bool(row)


def main() -> None:
    print("Step 1: creating departments table if missing...")
    Base.metadata.create_all(bind=engine, tables=[Department.__table__])

    db = db_session_basede26()
    try:
        print("Step 2: seeding departments...")
        for name, code, building in DEPARTMENTS:
            existing = db.query(Department).filter_by(dept_code=code).first()
            if existing:
                print(f"  {code} already exists, skipping")
                continue
            db.add(Department(name=name, dept_code=code, building=building))
        db.commit()
        dept_by_code = {d.dept_code: d.id for d in db.query(Department).all()}
        print(f"  departments: {dept_by_code}")
        db.commit()  # close out the read transaction -- an open one here holds a
        # metadata lock on departments that deadlocks against Step 3's
        # ALTER TABLE ... ADD FOREIGN KEY ... REFERENCES departments below

        print("Step 3: altering courses table (add columns if missing)...")
        with engine.begin() as conn:
            if not column_exists(conn, "courses", "department_id"):
                conn.execute(text(
                    "ALTER TABLE courses ADD COLUMN department_id INT NULL, "
                    "ADD CONSTRAINT fk_courses_department FOREIGN KEY (department_id) "
                    "REFERENCES departments(id)"
                ))
                print("  added department_id (FK)")
            else:
                print("  department_id already present")

            if not column_exists(conn, "courses", "seats_available"):
                conn.execute(text(
                    "ALTER TABLE courses ADD COLUMN seats_available INT NOT NULL DEFAULT 30"
                ))
                print("  added seats_available")
            else:
                print("  seats_available already present")

            if not column_exists(conn, "courses", "created_at"):
                conn.execute(text(
                    "ALTER TABLE courses ADD COLUMN created_at DATETIME NULL"
                ))
                conn.execute(text(
                    "UPDATE courses SET created_at = NOW() WHERE created_at IS NULL"
                ))
                conn.execute(text(
                    "ALTER TABLE courses MODIFY COLUMN created_at DATETIME NOT NULL"
                ))
                print("  added created_at")
            else:
                print("  created_at already present")

            if not column_exists(conn, "courses", "updated_at"):
                conn.execute(text(
                    "ALTER TABLE courses ADD COLUMN updated_at DATETIME NULL"
                ))
                conn.execute(text(
                    "UPDATE courses SET updated_at = NOW() WHERE updated_at IS NULL"
                ))
                conn.execute(text(
                    "ALTER TABLE courses MODIFY COLUMN updated_at DATETIME NOT NULL"
                ))
                print("  added updated_at")
            else:
                print("  updated_at already present")

        print("Step 4: backfilling department_id from the old department string...")
        updated = 0
        for name, code, _building in DEPARTMENTS:
            dept_id = dept_by_code[code]
            res = db.execute(
                text("UPDATE courses SET department_id = :did WHERE department = :name AND department_id IS NULL"),
                {"did": dept_id, "name": name},
            )
            updated += res.rowcount
        db.commit()
        print(f"  backfilled department_id on {updated} rows")

        remaining = db.execute(text("SELECT COUNT(*) FROM courses WHERE department_id IS NULL")).scalar()
        print(f"  courses still without department_id: {remaining}")

        print("Step 5: checking for duplicate course_code values before adding UNIQUE...")
        dupes = db.execute(
            text("SELECT course_code, COUNT(*) c FROM courses GROUP BY course_code HAVING c > 1")
        ).fetchall()
        db.commit()  # close the read transaction before the DDL below
        if dupes:
            print(f"  FOUND {len(dupes)} duplicate course_code values, NOT adding UNIQUE constraint:")
            for code, count in dupes:
                print(f"    {code}: {count} rows")
        else:
            with engine.begin() as conn:
                if not constraint_exists(conn, "courses", "course_code"):
                    conn.execute(text("ALTER TABLE courses ADD UNIQUE KEY course_code (course_code)"))
                    print("  added UNIQUE constraint on course_code")
                else:
                    print("  UNIQUE constraint on course_code already present")

        print("\nDone.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
