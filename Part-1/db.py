"""
Part-1/db.py -- DATA-260 HW4, Part 2 (MySQL persistence and server-side sessions)

SQLAlchemy engine + session setup for the s1808_rel MySQL database (running
in a local Docker container, see Part-1/README section on HW4). The session
factory variable is named db_session_basede26, per the assignment's explicit
naming requirement.

Connection settings are read from environment variables with defaults that
match the docker run command documented in the README, so this works out of
the box for local dev without needing a .env file.
"""

from __future__ import annotations

import contextvars
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3307")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "s1808_root_pw")
MYSQL_DB = os.environ.get("MYSQL_DB", "s1808_rel")

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

# Required variable name per the HW4 spec: "Name your database connection
# variable 'db_session_basede26' strictly."
db_session_basede26 = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields one session per request, always closed."""
    db = db_session_basede26()
    try:
        yield db
    finally:
        db.close()


# --- Per-request SQL query counter (HW4, Part 3: N+1 measurement) ---------
# A ContextVar rather than a plain global so concurrent requests (FastAPI
# runs sync route functions in a threadpool, and Starlette copies the
# context into each thread) don't stomp on each other's counts.
_query_count_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "query_count", default=0
)


@event.listens_for(engine, "before_cursor_execute")
def _count_query(conn, cursor, statement, parameters, context, executemany):
    _query_count_var.set(_query_count_var.get() + 1)


def reset_query_count() -> None:
    _query_count_var.set(0)


def get_query_count() -> int:
    return _query_count_var.get()
