"""
Part-1/api_courses.py -- DATA-260 HW4/HW5 (Course CRUD JSON API)

REST endpoints for the Course entity, backed by MySQL (models.Course) instead
of the in-memory list main.py used through HW2/HW3. This is what the React
client and the Postman screenshots hit. All operations require a valid
session (see api_auth.require_user) -- only logged-in users may view or
modify records, per the assignment.

HW5 additions: course_code is now unique + format-validated, department_id
(FK to Department) replaces free-form department entry on new/updated rows,
and seats_available is a numeric field with a default.

    POST   /api/courses         add a new course
    GET    /api/courses         list all courses
    GET    /api/courses/{id}    get one course by id
    PUT    /api/courses/{id}    update a course
    DELETE /api/courses/{id}    delete a course
"""

from __future__ import annotations

import datetime
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api_auth import require_user
from db import get_db
from models import Course, Department, User

router = APIRouter(prefix="/api/courses")

COURSE_CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,8}-[A-Z0-9]{1,8}$")


class CourseIn(BaseModel):
    course_code: str = Field(min_length=3, max_length=32)
    course_title: str
    submitter_email: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    agree_terms: bool = False
    department_id: Optional[int] = None
    seats_available: int = 30

    @field_validator("course_code")
    @classmethod
    def validate_course_code(cls, v: str) -> str:
        if not COURSE_CODE_PATTERN.match(v):
            raise ValueError("course_code must look like 'CS-00001' (letters/digits, a dash, letters/digits)")
        return v

    @field_validator("seats_available")
    @classmethod
    def validate_seats(cls, v: int) -> int:
        if v < 0:
            raise ValueError("seats_available cannot be negative")
        return v


class CourseOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    submitter_email: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    agree_terms: bool
    department_id: Optional[int] = None
    seats_available: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


def _check_department_exists(db: Session, department_id: Optional[int]) -> None:
    if department_id is None:
        return
    if not db.query(Department).filter_by(id=department_id).first():
        raise HTTPException(status_code=422, detail=f"department_id {department_id} does not exist")


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    payload: CourseIn, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    _check_department_exists(db, payload.department_id)
    rec = Course(**payload.model_dump())
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="course_code already exists")
    db.refresh(rec)
    return rec


@router.get("", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db), _user: User = Depends(require_user)):
    return db.query(Course).order_by(Course.id).all()


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = db.query(Course).filter_by(id=course_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Course not found")
    return rec


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    payload: CourseIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_user),
):
    rec = db.query(Course).filter_by(id=course_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Course not found")
    _check_department_exists(db, payload.department_id)
    for key, value in payload.model_dump().items():
        setattr(rec, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="course_code already exists")
    db.refresh(rec)
    return rec


@router.delete("/{course_id}")
def delete_course(
    course_id: int, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = db.query(Course).filter_by(id=course_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(rec)
    db.commit()
    return {"ok": True, "deleted_id": course_id}
