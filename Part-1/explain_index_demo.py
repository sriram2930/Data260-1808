"""
Part-1/explain_index_demo.py -- DATA-260 HW4, Part 3.8

Shows the EXPLAIN plan, before and after adding an index, for a realistic
query on this domain: filtering the course catalogue by department
(SELECT ... FROM courses WHERE department = :dept). courses.department has
no index today, so this is a genuinely new index, not the sections.course_id
one -- that one turned out to already be required by its foreign key
constraint (MySQL refuses "DROP INDEX" on an index backing an FK: error 1553,
"needed in a foreign key constraint"), so it couldn't be used for a clean
before/after demo without also dropping and recreating the FK itself. Adding
a fresh index on an unindexed column sidesteps that entirely and is a more
realistic story anyway: "the list-by-department endpoint is slow, add an
index for it" is exactly the kind of tuning this part is about.

Usage:
    python explain_index_demo.py
"""

from __future__ import annotations

import pymysql

from db import MYSQL_DB, MYSQL_HOST, MYSQL_PASSWORD, MYSQL_PORT, MYSQL_USER

INDEX_NAME = "ix_courses_department"
DEPARTMENT = "Data Science & AI"


def connect():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
    )


def explain(cur) -> list[dict]:
    cur.execute("EXPLAIN SELECT * FROM courses WHERE department = %s", (DEPARTMENT,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def print_explain(rows: list[dict]) -> None:
    for row in rows:
        for k, v in row.items():
            print(f"  {k}: {v}")
        print()


def main() -> None:
    conn = connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM courses WHERE department = %s", (DEPARTMENT,))
    matching = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM courses")
    total = cur.fetchone()[0]
    print(f"Query: SELECT * FROM courses WHERE department = '{DEPARTMENT}'")
    print(f"({matching} matching rows out of {total} total courses)\n")

    cur.execute(f"SHOW INDEX FROM courses WHERE Key_name = '{INDEX_NAME}'")
    if cur.fetchone() is not None:
        print(f"Index {INDEX_NAME} already exists from a prior run -- dropping it first "
              f"to get a clean 'before' state...")
        cur.execute(f"ALTER TABLE courses DROP INDEX {INDEX_NAME}")
        conn.commit()

    print("=== EXPLAIN before index ===")
    before = explain(cur)
    print_explain(before)

    print(f"Creating index {INDEX_NAME} on courses(department)...")
    cur.execute(f"CREATE INDEX {INDEX_NAME} ON courses(department)")
    conn.commit()

    print("=== EXPLAIN after index ===")
    after = explain(cur)
    print_explain(after)

    print("=== What changed ===")
    b, a = before[0], after[0]
    print(f"type: {b.get('type')} -> {a.get('type')}")
    print(f"key: {b.get('key')} -> {a.get('key')}")
    print(f"rows (estimated scanned): {b.get('rows')} -> {a.get('rows')}")
    print(
        "\nBefore: no usable index on department, so MySQL does a full table\n"
        f"scan (type=ALL) across all {total} rows and filters each one in memory.\n"
        "After: the new index lets it jump straight to matching rows (type=ref),\n"
        f"scanning roughly just the {matching} rows that actually match instead of\n"
        f"all {total}."
    )

    conn.close()


if __name__ == "__main__":
    main()
