"""
Part-1/main.py -- DATA-260 HW2, Parts 1 & 2 (FastAPI backend + responsive/stateful UI)

Serves the Campus Course Catalogue entity (Course: primary field courseCode,
secondary field courseTitle) as a small server-rendered CRUD app on PORT_BASE
(8008):

  GET  /                        home view: list + search, with loading/empty/
                                 error states
  POST /courses                 add a new record, redirect to "/"
  GET  /courses/{id}/edit       edit form for one record
  POST /courses/{id}/update     update a record (used to update id=1 per the
                                 assignment)
  POST /courses/delete-highest  delete the record with the highest id,
                                 redirect to "/"
  GET  /api/courses             JSON list (optionally filtered by ?q=), used
                                 by the search box's fetch-based live update

Storage is a simple in-memory list (module-level), seeded with a few sample
records on startup so id=1 exists and "delete highest id" has something to do.
This is intentionally not a database -- the assignment only requires the CRUD
behavior and redirect flow, not persistence across restarts.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import auth

HERE = Path(__file__).parent
PORT_BASE = 8008

app = FastAPI(title="Campus Course Catalogue & Enrolment")

# Session cookie: signed (SessionMiddleware always sends HttpOnly), Secure so
# it's only sent back over HTTPS (Chrome/Edge treat localhost as a secure
# context so this still works for local testing), SameSite=lax. secret_key is
# regenerated on every process start -- fine for a homework demo, since it
# just means old sessions don't survive a restart, but not something to reuse
# for anything real.
app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_hex(32),
    session_cookie="s1808_session",
    same_site="lax",
    https_only=True,
)

app.include_router(auth.router)
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
templates = Jinja2Templates(directory=str(HERE / "templates"))

DEPARTMENTS = ["Computer Science", "Data Science & AI", "Business Analytics", "Engineering"]

COURSES: list[dict] = []
_next_id = 1


def _new_id() -> int:
    global _next_id
    i = _next_id
    _next_id += 1
    return i


def _seed() -> None:
    global COURSES, _next_id
    COURSES = []
    _next_id = 1
    for rec in [
        dict(
            courseCode="DATA-260",
            courseTitle="Big Data Technologies and Systems",
            submitterEmail="jane.doe@sjsu.edu",
            description="Design and operation of data pipelines feeding ML systems.",
            department="Data Science & AI",
            agreeTerms=True,
        ),
        dict(
            courseCode="CS-146",
            courseTitle="Data Structures and Algorithms",
            submitterEmail="prof.lee@sjsu.edu",
            description="Core data structures, algorithm design, and complexity analysis.",
            department="Computer Science",
            agreeTerms=True,
        ),
        dict(
            courseCode="BUS-181",
            courseTitle="Business Analytics Fundamentals",
            submitterEmail="prof.rao@sjsu.edu",
            description="Statistical and analytical techniques for business decision making.",
            department="Business Analytics",
            agreeTerms=True,
        ),
    ]:
        rec["id"] = _new_id()
        COURSES.append(rec)


_seed()


def _highest_id() -> Optional[int]:
    return max((c["id"] for c in COURSES), default=None)


def _find(course_id: int) -> Optional[dict]:
    return next((c for c in COURSES if c["id"] == course_id), None)


def _matches(course: dict, q: str) -> bool:
    ql = q.strip().lower()
    return ql in course["courseCode"].lower() or ql in course["courseTitle"].lower()


@app.get("/")
def home(request: Request, q: str = "", error: str = "", success: str = ""):
    rows = [c for c in COURSES if _matches(c, q)] if q else COURSES
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "courses": rows,
            "q": q,
            "error": error,
            "success": success,
            "departments": DEPARTMENTS,
            "user": auth.get_current_user(request),
        },
    )


@app.get("/api/courses")
def api_courses(q: str = ""):
    rows = [c for c in COURSES if _matches(c, q)] if q else COURSES
    return rows


@app.post("/courses")
def create_course(
    courseCode: str = Form(""),
    courseTitle: str = Form(""),
    submitterEmail: str = Form(""),
    description: str = Form(""),
    department: str = Form(DEPARTMENTS[0]),
    agreeTerms: Optional[str] = Form(None),
):
    if not courseCode.strip() or not courseTitle.strip():
        return RedirectResponse(
            url="/?error=Course+Code+and+Course+Title+are+required.", status_code=303
        )
    rec = dict(
        id=_new_id(),
        courseCode=courseCode.strip(),
        courseTitle=courseTitle.strip(),
        submitterEmail=submitterEmail.strip(),
        description=description.strip(),
        department=department,
        agreeTerms=bool(agreeTerms),
    )
    COURSES.append(rec)
    return RedirectResponse(url="/?success=Course+added.", status_code=303)


@app.get("/courses/{course_id}/edit")
def edit_course_form(request: Request, course_id: int):
    rec = _find(course_id)
    if rec is None:
        return RedirectResponse(url="/?error=Record+not+found.", status_code=303)
    return templates.TemplateResponse(
        request, "edit.html", {"course": rec, "departments": DEPARTMENTS}
    )


@app.post("/courses/{course_id}/update")
def update_course(
    course_id: int,
    courseCode: str = Form(""),
    courseTitle: str = Form(""),
    submitterEmail: str = Form(""),
    description: str = Form(""),
    department: str = Form(DEPARTMENTS[0]),
    agreeTerms: Optional[str] = Form(None),
):
    rec = _find(course_id)
    if rec is None:
        return RedirectResponse(url="/?error=Record+not+found.", status_code=303)
    if not courseCode.strip() or not courseTitle.strip():
        return RedirectResponse(
            url="/?error=Course+Code+and+Course+Title+are+required.", status_code=303
        )
    rec.update(
        courseCode=courseCode.strip(),
        courseTitle=courseTitle.strip(),
        submitterEmail=submitterEmail.strip(),
        description=description.strip(),
        department=department,
        agreeTerms=bool(agreeTerms),
    )
    return RedirectResponse(url="/?success=Course+updated.", status_code=303)


@app.post("/courses/delete-highest")
def delete_highest():
    global COURSES
    hid = _highest_id()
    if hid is None:
        return RedirectResponse(url="/?error=No+records+to+delete.", status_code=303)
    COURSES = [c for c in COURSES if c["id"] != hid]
    return RedirectResponse(url=f"/?success=Deleted+course+%23{hid}.", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT_BASE, reload=False)
