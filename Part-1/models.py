"""
Part-1/models.py -- DATA-260 HW4/HW5 SQLAlchemy models

Course: the primary domain entity (Campus course catalogue and enrolment),
        primary field course_code, secondary field course_title.
Department: HW5's required "related entity" (the book/author-style second
         table) -- Course.department_id FKs into it. Kept alongside the old
         free-text Course.department column from HW4 (used by Part 3's N+1
         seed data and the EXPLAIN index demo) rather than replacing it, per
         "keep extending, don't start a new one" / don't break prior parts.
Section: the "related" table Part 3's N+1 experiment needs -- course
         offerings (semester, instructor, enrolled_count), FK'd to Course.
         200 rows get seeded here, spread across a subset of the 5,000
         seeded courses, per the assignment.
User / UserSession: auth tables for the React client's server-side sessions
         (Part 2) -- the session token itself is the sessions.id primary key,
         and the browser's HTTP-only cookie holds only that opaque token,
         never user data directly.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    building = Column(String(128), nullable=True)
    dept_code = Column(String(16), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    courses = relationship("Course", back_populates="department_ref")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(32), nullable=False, unique=True, index=True)
    course_title = Column(String(255), nullable=False)
    submitter_email = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    department = Column(String(64), nullable=True)  # HW4 free-text field, kept as-is
    agree_terms = Column(Boolean, default=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    seats_available = Column(Integer, default=30, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False
    )

    department_ref = relationship("Department", back_populates="courses")
    sections = relationship("Section", back_populates="course")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    semester = Column(String(32), nullable=False)
    instructor = Column(String(128), nullable=False)
    enrolled_count = Column(Integer, default=0)

    course = relationship("Course", back_populates="sections")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)


class UserSession(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)  # the opaque session token itself
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
