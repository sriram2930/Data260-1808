"""
Part-1/init_db.py -- DATA-260 HW4, Part 2

Creates all tables (courses, sections, users, sessions) in the s1808_rel
MySQL database and seeds one demo user for logging into the React client.
Run once against a fresh database:

    python init_db.py
"""

from __future__ import annotations

import bcrypt

from db import Base, db_session_basede26, engine
import models  # noqa: F401 -- import registers the models on Base.metadata
from models import User

DEMO_EMAIL = "advisor@sjsu.edu"
DEMO_PASSWORD = "course123"
DEMO_NAME = "Course Advisor"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already existed): courses, sections, users, sessions")

    db = db_session_basede26()
    try:
        existing = db.query(User).filter_by(email=DEMO_EMAIL).first()
        if existing:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            return
        pw_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
        db.add(User(name=DEMO_NAME, email=DEMO_EMAIL, password_hash=pw_hash))
        db.commit()
        print(f"Seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
