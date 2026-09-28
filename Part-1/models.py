"""
Part-1/models.py -- DATA-260 HW4, Part 2 SQLAlchemy models

Course: the primary domain entity (Campus course catalogue and enrolment),
        primary field course_code, secondary field course_title.
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


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(32), nullable=False, index=True)
    course_title = Column(String(255), nullable=False)
    submitter_email = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    department = Column(String(64), nullable=True)
    agree_terms = Column(Boolean, default=False)

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
