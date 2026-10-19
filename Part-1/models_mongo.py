"""
Part-1/models_mongo.py -- DATA-260 HW6, Part 1.II-III (Pydantic schemas)

Pydantic models for the MongoDB-backed collections. These enforce the same
rules as init_mongo.py's $jsonSchema validators, but at the API boundary --
so a bad request gets a clean 422 with a field-level message before it ever
reaches Mongo, and Mongo's own validator is the second, DB-level line of
defense (belt and suspenders, not redundant: nothing bypasses the API in
this app, but the DB-level check is still real and was verified directly).
"""

from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["draft", "published", "archived"]
Category = Literal["course_update", "enrollment", "event", "general"]


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    status: Status = "draft"
    category: Category
    event_date: datetime.datetime

    model_config = {"json_schema_extra": {"example": {
        "title": "Midterm date moved",
        "description": "DATA-260 midterm moves to next Thursday.",
        "status": "published",
        "category": "course_update",
        "event_date": "2026-11-05T10:00:00",
    }}}


class AnnouncementOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    category: str
    event_date: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ChatIn(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    message: str = Field(min_length=1)


class ChatOut(BaseModel):
    reply: str
    session_id: str
    used: dict
