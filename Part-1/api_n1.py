"""
Part-1/api_n1.py -- DATA-260 HW4, Part 3 (N+1 measurement and query tuning)

Two list endpoints over the same 5,000-course / 200-section seed data
(seed_n1.py), returning identical data shaped identically, differing only in
how many SQL statements they issue to fetch it:

  GET /api/n1/naive?page_size=N  -- 1 query for the page of courses, then one
                                     more query PER course to fetch its
                                     sections separately (the classic N+1).
  GET /api/n1/fixed?page_size=N  -- a single query using a LEFT OUTER JOIN
                                     (joinedload) to fetch courses and their
                                     sections together, so the query count
                                     stays flat regardless of page size.

Both responses include query_count (from db.get_query_count(), reset at the
top of each request) so the measurement script (run_n1_experiment.py) can
read it straight off the JSON without needing separate DB-side logging.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from db import get_db, get_query_count, reset_query_count
from models import Course

router = APIRouter(prefix="/api/n1")


def _section_dict(s):
    return {
        "id": s.id,
        "semester": s.semester,
        "instructor": s.instructor,
        "enrolled_count": s.enrolled_count,
    }


@router.get("/naive")
def list_naive(page_size: int = 10, db: Session = Depends(get_db)):
    reset_query_count()
    courses = db.query(Course).order_by(Course.id).limit(page_size).all()  # query 1

    result = []
    for c in courses:
        # One extra query per course -- accessing the lazy-loaded
        # relationship here is what triggers a fresh SELECT ... WHERE
        # course_id = :id for every single row. This loop is the N+1 itself.
        sections = c.sections
        result.append(
            {
                "id": c.id,
                "course_code": c.course_code,
                "course_title": c.course_title,
                "sections": [_section_dict(s) for s in sections],
            }
        )

    return {"page_size": page_size, "query_count": get_query_count(), "courses": result}


@router.get("/fixed")
def list_fixed(page_size: int = 10, db: Session = Depends(get_db)):
    reset_query_count()
    courses = (
        db.query(Course)
        .options(joinedload(Course.sections))
        .order_by(Course.id)
        .limit(page_size)
        .all()
    )  # one query total, LEFT OUTER JOIN

    result = [
        {
            "id": c.id,
            "course_code": c.course_code,
            "course_title": c.course_title,
            "sections": [_section_dict(s) for s in c.sections],
        }
        for c in courses
    ]

    return {"page_size": page_size, "query_count": get_query_count(), "courses": result}
