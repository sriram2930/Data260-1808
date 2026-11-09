"""
Part-13/seed_hw09.py -- DATA-260 HW9 (idempotent test-data setup)

All 5,000 seeded courses have seats_available = 30, which would make any two
"how many seats?" questions have the SAME correct answer -- useless for Part
3's "superficially similar questions with different correct answers". This
gives three course records distinct seat counts and resets CS-00005 to 30
(the record Part 3.5 mutates). Safe to re-run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Part-1"))
from db import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

SEATS = {"DATA-00006": 25, "DATA-00007": 12, "CS-00018": 8, "CS-00005": 30}

with engine.begin() as conn:
    for code, seats in SEATS.items():
        conn.execute(text("UPDATE courses SET seats_available=:s WHERE course_code=:c"), {"s": seats, "c": code})
        print(f"{code}: seats_available = {seats}")
