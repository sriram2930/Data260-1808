"""
Part-1/migrate_hw07.py -- DATA-260 HW7, Part 1.III (schema migration)

Adds username (unique, JWT login identity) and role (reader/writer/
moderator) to the existing users table, same idempotent
add-column-if-missing pattern as migrate_hw05.py. Backfills the HW4 demo
user (advisor@sjsu.edu) with username "advisor" and role "moderator", then
seeds two more demo accounts -- one writer, one reader -- so RBAC has all
three roles to test against from the start.

Safe to re-run: every step checks "does this already exist" before acting.
"""

from __future__ import annotations

import bcrypt
import models  # noqa: F401
from db import db_session_basede26, engine
from models import User
from sqlalchemy import text

DEMO_USERS = [
    # username, password, role, name, email
    ("advisor", "course123", "moderator", "Course Advisor", "advisor@sjsu.edu"),
    ("writer1", "writer123", "writer", "Writer Demo", "writer1@sjsu.edu"),
    ("reader1", "reader123", "reader", "Reader Demo", "reader1@sjsu.edu"),
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


def main() -> None:
    print("Step 1: altering users table (add columns if missing)...")
    with engine.begin() as conn:
        if not column_exists(conn, "users", "username"):
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(64) NULL"))
            print("  added username")
        else:
            print("  username already present")

        if not column_exists(conn, "users", "role"):
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(16) NULL"))
            print("  added role")
        else:
            print("  role already present")

    db = db_session_basede26()
    try:
        print("Step 2: seeding/backfilling demo users...")
        for username, password, role, name, email in DEMO_USERS:
            existing = db.query(User).filter_by(email=email).first()
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            if existing:
                existing.username = username
                existing.role = role
                existing.password_hash = pw_hash
                print(f"  updated {email}: username={username}, role={role}")
            else:
                db.add(User(name=name, email=email, password_hash=pw_hash, username=username, role=role))
                print(f"  created {email}: username={username}, role={role}")
        db.commit()

        print("Step 3: checking for duplicate usernames before adding UNIQUE...")
        with engine.begin() as conn:
            dupes = conn.execute(
                text("SELECT username, COUNT(*) c FROM users WHERE username IS NOT NULL GROUP BY username HAVING c > 1")
            ).fetchall()
            if dupes:
                print(f"  FOUND {len(dupes)} duplicate usernames, NOT adding UNIQUE constraint:")
                for uname, count in dupes:
                    print(f"    {uname}: {count} rows")
            else:
                existing_unique = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.table_constraints "
                        "WHERE table_schema = DATABASE() AND table_name = 'users' AND constraint_name = 'username'"
                    )
                ).scalar()
                if not existing_unique:
                    conn.execute(text("ALTER TABLE users ADD UNIQUE KEY username (username)"))
                    print("  added UNIQUE constraint on username")
                else:
                    print("  UNIQUE constraint on username already present")

        print("\nDone.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
