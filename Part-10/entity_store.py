"""
Part-10/entity_store.py -- DATA-260 HW8, Part 1.III (entity validation + store)

The Course entity (this project's primary domain entity, same fields as
Part-1/models.py's Course) backed by a plain Python dict inside the worker
process, per the assignment ("Store entities in a plain Python dictionary
inside the worker for this Kafka exercise" -- deliberately not MySQL this
time, so the Kafka exercise's correctness doesn't depend on HW4-7's DB).
"""

from __future__ import annotations

import uuid
from typing import Optional

REQUIRED_FIELDS = ("course_code", "course_title")
OPTIONAL_FIELDS = {"description": None, "department": None, "seats_available": 30}


def validate_course_data(data: dict) -> Optional[str]:
    """Returns an error message if `data` is invalid, else None."""
    if not isinstance(data, dict):
        return "data must be a JSON object"
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"missing or empty required field: {field!r}"
    if "seats_available" in data and data["seats_available"] is not None:
        if not isinstance(data["seats_available"], int) or data["seats_available"] < 0:
            return "seats_available must be a non-negative integer"
    return None


class EntityStore:
    """In-memory course store, scoped to one worker process."""

    def __init__(self) -> None:
        self._courses: dict[str, dict] = {}

    def create(self, data: dict) -> dict:
        course_id = str(uuid.uuid4())
        record = {"course_id": course_id}
        for field in REQUIRED_FIELDS:
            record[field] = data[field]
        for field, default in OPTIONAL_FIELDS.items():
            record[field] = data.get(field, default)
        self._courses[course_id] = record
        return record

    def get(self, course_id: str) -> Optional[dict]:
        return self._courses.get(course_id)

    def __len__(self) -> int:
        return len(self._courses)
