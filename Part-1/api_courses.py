"""
Part-1/api_courses.py -- DATA-260 HW4, Part 1 & 2 (Course CRUD JSON API)

REST endpoints for the Course entity, backed by MySQL (models.Course) instead
of the in-memory list main.py used through HW2/HW3. This is what the React
client and the Postman screenshots hit. All five operations require a valid
session (see api_auth.require_user) -- only logged-in users may view or
modify records, per the assignment.

    POST   /api/courses         add a new course
    GET    /api/courses         list all courses
    GET    /api/courses/{id}    get one course by id
    PUT    /api/courses/{id}    update a course
    DELETE /api/courses/{id}    delete a course
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_auth import require_user
from db import get_db
from models import Course, User

router = APIRouter(prefix="/api/courses")


class CourseIn(BaseModel):
    course_code: str
    course_title: str
    submitter_email: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    agree_terms: bool = False


class CourseOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    submitter_email: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    agree_terms: bool

    class Config:
        from_attributes = True


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    payload: CourseIn, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = Course(**payload.model_dump())
    db.add(rec)
    db.commit()
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
    for key, value in payload.model_dump().items():
        setattr(rec, key, value)
    db.commit()
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
