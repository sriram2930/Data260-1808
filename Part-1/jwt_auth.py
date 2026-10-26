"""
Part-1/jwt_auth.py -- DATA-260 HW7, Part 1 (JWT auth + role-based authorization)

Replaces the HW4 server-side session mechanism (api_auth.py, still importable
for anything that still wants it, but no longer used on the Course routes --
the HW4 session code stays reachable at the `hw4` tag as history) with
stateless JWT bearer tokens carrying username + role.

    POST /auth/login   {username, password} -> {access_token, token_type, role}
    GET  /auth/me      -> {username, role} for the token's owner

require_role(*roles) is a FastAPI dependency factory: require_role() alone
just requires any valid token (used for list/read), require_role("writer",
"moderator") requires the token's role to be one of those (used for
create/delete).
"""

from __future__ import annotations

import datetime
import os

import bcrypt
import jwt
from db import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth")

JWT_SECRET = os.environ.get("JWT_SECRET", "s1808_hw7_dev_secret_do_not_use_in_prod")
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = 60

ROLES = ("reader", "writer", "moderator")

_bearer = HTTPBearer(auto_error=False)


def create_access_token(username: str, role: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=JWT_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (ExpiredSignatureError, InvalidTokenError, ...)
    on anything wrong with the token -- callers turn that into 401."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_claims(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return decode_access_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {exc}")


def require_role(*allowed_roles: str):
    """Dependency factory. No args = any authenticated role. With args,
    the token's role must be one of them, or this raises 403."""

    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        if allowed_roles and claims.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"role '{claims.get('role')}' is not permitted (needs one of {allowed_roles})",
            )
        return claims

    return _dep


@router.post("/login")
def login(payload: dict, db: Session = Depends(get_db)):
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""
    user = db.query(User).filter_by(username=username).first()
    if not user or not user.role or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.get("/me")
def me(claims: dict = Depends(get_current_claims)):
    return {"username": claims["sub"], "role": claims["role"]}
