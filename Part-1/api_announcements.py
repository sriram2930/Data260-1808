"""
Part-1/api_announcements.py -- DATA-260 HW6, Part 1.II (Announcement CRUD JSON API)

Document-oriented view of the campus course catalogue domain: course
update/enrollment/event announcements, stored in MongoDB (s1808_doc) rather
than the MySQL s1808_rel database HW4/HW5's Course/Department live in.
Reuses the auth dependency from api_auth.py (same require_user check as
every other protected route in this app), not a separate login system.

    POST   /api/announcements         add a new announcement
    GET    /api/announcements         list all announcements
    GET    /api/announcements/{id}    get one by id
    PUT    /api/announcements/{id}    update an announcement
    DELETE /api/announcements/{id}    delete an announcement
"""

from __future__ import annotations

import datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import PyMongoError, WriteError

from api_auth import require_user
from db_mongo import get_db
from models import User
from models_mongo import AnnouncementIn, AnnouncementOut

router = APIRouter(prefix="/api/announcements")


def _doc_to_out(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def _object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=422, detail=f"'{id_str}' is not a valid id")


@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(payload: AnnouncementIn, _user: User = Depends(require_user)):
    db = get_db()
    now = datetime.datetime.utcnow()
    doc = payload.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    try:
        result = db.announcements.insert_one(doc)
    except WriteError as exc:
        raise HTTPException(status_code=422, detail=f"MongoDB schema validation failed: {exc}")
    doc["_id"] = result.inserted_id
    return _doc_to_out(doc)


@router.get("", response_model=list[AnnouncementOut])
def list_announcements(_user: User = Depends(require_user)):
    db = get_db()
    return [_doc_to_out(d) for d in db.announcements.find().sort("created_at", -1)]


@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(announcement_id: str, _user: User = Depends(require_user)):
    db = get_db()
    doc = db.announcements.find_one({"_id": _object_id(announcement_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _doc_to_out(doc)


@router.put("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: str, payload: AnnouncementIn, _user: User = Depends(require_user)
):
    db = get_db()
    oid = _object_id(announcement_id)
    update = payload.model_dump()
    update["updated_at"] = datetime.datetime.utcnow()
    try:
        result = db.announcements.update_one({"_id": oid}, {"$set": update})
    except WriteError as exc:
        raise HTTPException(status_code=422, detail=f"MongoDB schema validation failed: {exc}")
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _doc_to_out(db.announcements.find_one({"_id": oid}))


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, _user: User = Depends(require_user)):
    db = get_db()
    result = db.announcements.delete_one({"_id": _object_id(announcement_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"ok": True, "deleted_id": announcement_id}
