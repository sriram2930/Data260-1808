"""
Part-1/auth.py -- DATA-260 HW3, Part 1 (FastAPI authentication)

A small login/session/logout system for the Campus Course Catalogue app,
handled as its own APIRouter so it stays separate from the CRUD routes in
main.py. Session state is Starlette's SessionMiddleware (signed cookie, no
server-side session store needed for this scale), with a manual idle timeout
on top -- max_age on the cookie alone is a fixed expiry from login time, not
an idle timeout, so this checks "time since last request" itself and clears
the session once that gap is too long.

Demo credentials only (this is not a real user database):
    username: advisor
    password: course123
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

router = APIRouter()

IDLE_TIMEOUT_SECONDS = 30

DEMO_USERS = {
    "advisor": {"password": "course123", "name": "Course Advisor"},
}


def get_current_user(request: Request) -> str | None:
    """Returns the logged-in user's display name, or None -- and enforces the
    idle timeout as a side effect (clears the session if it's been idle too
    long). Used by main.py's home route too, so the navbar can show the
    right links without duplicating this logic."""
    user = request.session.get("user")
    last_seen = request.session.get("last_seen")
    if not user or not last_seen:
        return None
    if time.time() - last_seen > IDLE_TIMEOUT_SECONDS:
        request.session.clear()
        return None
    request.session["last_seen"] = time.time()
    return user


@router.get("/login")
def login_form(request: Request, error: str = ""):
    if get_current_user(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
def login(request: Request, username: str = Form(""), password: str = Form("")):
    record = DEMO_USERS.get(username)
    if not record or record["password"] != password:
        return RedirectResponse(
            url="/login?error=Invalid+username+or+password.", status_code=303
        )
    request.session["user"] = record["name"]
    request.session["last_seen"] = time.time()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard")
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(
            url="/login?error=Session+expired+or+not+logged+in.+Please+log+in+again.",
            status_code=303,
        )
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
