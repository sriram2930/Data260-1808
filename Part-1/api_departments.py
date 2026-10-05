"""
Part-1/api_departments.py -- DATA-260 HW5, Part 1.II (Department CRUD JSON API)

Department is HW5's required "related entity" (the book/author-style second
table): a course's department_id FKs into this table. Mirrors api_courses.py's
shape (auth-gated, Pydantic in/out models) and adds the two things that file
doesn't need: pagination on the list endpoint, and a relationship-query
endpoint (all courses in a given department).

    POST   /api/departments                 add a new department
    GET    /api/departments?skip=&limit=     list departments, paginated
    GET    /api/departments/{id}             get one department by id
    PUT    /api/departments/{id}             update a department
    DELETE /api/departments/{id}             delete a department (blocked if
                                              any course still references it)
    GET    /api/departments/{id}/courses     all courses in this department
"""

from __future__ import annotations

import datetime
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api_auth import require_user
from db import get_db
from models import Course, Department, User

router = APIRouter(prefix="/api/departments")

DEPT_CODE_PATTERN = re.compile(r"^[A-Z]{2,8}$")


class DepartmentIn(BaseModel):
    name: str
    building: Optional[str] = None
    dept_code: str = Field(min_length=2, max_length=16)

    @field_validator("dept_code")
    @classmethod
    def validate_dept_code(cls, v: str) -> str:
        if not DEPT_CODE_PATTERN.match(v):
            raise ValueError("dept_code must be 2-8 uppercase letters, e.g. 'CS' or 'DATA'")
        return v


class DepartmentOut(BaseModel):
    id: int
    name: str
    building: Optional[str] = None
    dept_code: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    department_id: Optional[int] = None
    seats_available: int

    class Config:
        from_attributes = True


class PaginatedDepartments(BaseModel):
    items: list[DepartmentOut]
    total: int
    skip: int
    limit: int


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(
    payload: DepartmentIn, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = Department(**payload.model_dump())
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="dept_code already exists")
    db.refresh(rec)
    return rec


@router.get("", response_model=PaginatedDepartments)
def list_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_user),
):
    total = db.query(Department).count()
    items = db.query(Department).order_by(Department.id).offset(skip).limit(limit).all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = db.query(Department).filter_by(id=department_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Department not found")
    return rec


@router.put("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentIn,
    db: Session = Depends(get_db),
    _user: User = Depends(require_user),
):
    rec = db.query(Department).filter_by(id=department_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Department not found")
    for key, value in payload.model_dump().items():
        setattr(rec, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="dept_code already exists")
    db.refresh(rec)
    return rec


@router.delete("/{department_id}")
def delete_department(
    department_id: int, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = db.query(Department).filter_by(id=department_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Department not found")
    in_use = db.query(Course).filter_by(department_id=department_id).count()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {in_use} course(s) still reference this department",
        )
    db.delete(rec)
    db.commit()
    return {"ok": True, "deleted_id": department_id}


@router.get("/{department_id}/courses", response_model=list[CourseOut])
def list_courses_in_department(
    department_id: int, db: Session = Depends(get_db), _user: User = Depends(require_user)
):
    rec = db.query(Department).filter_by(id=department_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Department not found")
    return db.query(Course).filter_by(department_id=department_id).order_by(Course.id).all()
