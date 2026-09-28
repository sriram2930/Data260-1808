"""
Part-1/seed_n1.py -- DATA-260 HW4, Part 3.1 (N+1 measurement seed data)

Seeds 5,000 Course rows and 200 Section rows (the "related" table -- a
course offering: semester, instructor, enrolled_count, FK'd to courses),
using SEED = 1808 for reproducibility. Clears any existing rows in both
tables first so re-running this always lands on exactly 5,000 / 200, not an
accumulating pile from repeated runs.

Run once before the N+1 experiment:
    python seed_n1.py
"""

from __future__ import annotations

import random

from db import Base, db_session_basede26, engine
import models  # noqa: F401
from models import Course, Section

SEED = 1808
N_COURSES = 5000
N_SECTIONS = 200

DEPARTMENTS = ["Computer Science", "Data Science & AI", "Business Analytics", "Engineering"]
DEPT_PREFIX = {"Computer Science": "CS", "Data Science & AI": "DATA", "Business Analytics": "BUS", "Engineering": "ENGR"}
TOPICS = [
    "Introduction to", "Advanced", "Foundations of", "Applied", "Topics in",
    "Seminar in", "Principles of", "Computational", "Statistical", "Modern",
]
SUBJECTS = [
    "Data Structures", "Machine Learning", "Database Systems", "Software Engineering",
    "Cloud Computing", "Business Analytics", "Enrollment Systems", "Distributed Systems",
    "Algorithms", "Human-Computer Interaction", "Data Pipelines", "Operating Systems",
    "Cybersecurity", "Networks", "Statistics", "Linear Algebra", "Operations Research",
]
SEMESTERS = ["Fall 2026", "Spring 2027", "Summer 2027"]
INSTRUCTOR_FIRST = ["Alex", "Priya", "Wei", "Maria", "Sam", "Fatima", "Chen", "Diego", "Lena", "Omar"]
INSTRUCTOR_LAST = ["Nguyen", "Patel", "Garcia", "Kim", "Rossi", "Khan", "Silva", "Lopez", "Chen", "Brown"]


def main() -> None:
    rng = random.Random(SEED)
    Base.metadata.create_all(bind=engine)

    db = db_session_basede26()
    try:
        print("Clearing existing courses and sections...")
        db.query(Section).delete()
        db.query(Course).delete()
        db.commit()

        print(f"Seeding {N_COURSES} courses...")
        courses = []
        for i in range(1, N_COURSES + 1):
            dept = rng.choice(DEPARTMENTS)
            code = f"{DEPT_PREFIX[dept]}-{i:05d}"
            title = f"{rng.choice(TOPICS)} {rng.choice(SUBJECTS)}"
            courses.append(
                Course(
                    course_code=code,
                    course_title=title,
                    submitter_email=f"faculty{i % 200}@sjsu.edu",
                    description=f"Auto-generated seed course #{i} for N+1 load testing.",
                    department=dept,
                    agree_terms=True,
                )
            )
        db.add_all(courses)
        db.commit()
        print(f"  inserted {len(courses)} courses")

        # Refresh to get assigned ids, then attach 200 sections to randomly
        # chosen courses (most of the 5,000 courses end up with zero
        # sections, a few end up with one -- that's fine, the assignment
        # only asks for 200 related rows total, not full coverage).
        all_ids = [c.id for c in db.query(Course.id).all()]
        print(f"Seeding {N_SECTIONS} sections across {len(all_ids)} course ids...")
        sections = []
        for _ in range(N_SECTIONS):
            course_id = rng.choice(all_ids)
            sections.append(
                Section(
                    course_id=course_id,
                    semester=rng.choice(SEMESTERS),
                    instructor=f"{rng.choice(INSTRUCTOR_FIRST)} {rng.choice(INSTRUCTOR_LAST)}",
                    enrolled_count=rng.randint(5, 45),
                )
            )
        db.add_all(sections)
        db.commit()
        print(f"  inserted {len(sections)} sections")

        course_count = db.query(Course).count()
        section_count = db.query(Section).count()
        print(f"\nFinal counts: courses={course_count}, sections={section_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
