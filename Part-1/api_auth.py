"""
Part-1/api_auth.py -- DATA-260 HW4, Part 1 & 2 (React client auth API)

JSON auth endpoints for the React client, separate from HW3's template-based
admin login (auth.py) which stays as-is for that older UI. This one uses
real server-side sessions: on login, a random opaque token is generated,
stored in the MySQL sessions table (with the user id and an expiry), and
that token -- nothing else -- is set as an HTTP-only cookie. The cookie
itself never carries user data; every request that needs to know who's
logged in looks the token up in the sessions table.

    POST /api/login   {email, password} -> sets cookie, returns user info
    GET  /api/me       -> current user info, or 401 if not logged in
    POST /api/logout   -> deletes the session row, clears the cookie
"""

from __future__ import annotations

import datetime
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from db import get_db
from models import User, UserSession

router = APIRouter(prefix="/api")

SESSION_COOKIE_NAME = "s1808_api_session"
SESSION_TTL_HOURS = 24


def create_session(db: Session, user: User) -> str:
    token = secrets.token_hex(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=SESSION_TTL_HOURS)
    db.add(UserSession(id=token, user_id=user.id, expires_at=expires_at))
    db.commit()
    return token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    session_row = db.query(UserSession).filter_by(id=token).first()
    if not session_row:
        return None
    if session_row.expires_at < datetime.datetime.utcnow():
        db.delete(session_row)
        db.commit()
        return None
    return db.query(User).filter_by(id=session_row.user_id).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user


@router.post("/login")
def login(payload: dict, response: Response, db: Session = Depends(get_db)):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = db.query(User).filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session(db, user)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
    )
    return {"id": user.id, "name": user.name, "email": user.email}


@router.get("/me")
def me(user: User = Depends(require_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        db.query(UserSession).filter_by(id=token).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"ok": True}
