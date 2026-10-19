"""
Part-1/init_mongo.py -- DATA-260 HW6, Part 1.I / Part 2 (MongoDB schema setup)

Creates the s1808_doc database's collections with real MongoDB-level
$jsonSchema validators (required fields, string length limits, enum
constraints) -- not just Pydantic validation at the API layer, per the
assignment's "the schema must include proper validation rules" requirement.

  announcements -- Part 1's document-oriented domain entity (the campus
                   course catalogue's "announcements" board: course
                   updates, enrollment notices, events).
  messages, summaries, episodes -- Part 2's short/long/episodic memory
                   collections.

Safe to re-run: drops and recreates each collection, so this is meant for
dev setup, not a production migration.

Run once:
    python init_mongo.py
"""

from __future__ import annotations

from db_mongo import get_db

ANNOUNCEMENT_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "status", "category", "event_date", "created_at", "updated_at"],
        "properties": {
            "title": {"bsonType": "string", "maxLength": 100, "description": "required, max 100 chars"},
            "description": {"bsonType": ["string", "null"]},
            "status": {"bsonType": "string", "enum": ["draft", "published", "archived"]},
            "category": {
                "bsonType": "string",
                "enum": ["course_update", "enrollment", "event", "general"],
            },
            "event_date": {"bsonType": "date"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

MESSAGE_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "role", "content", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": "string"},
            "role": {"bsonType": "string", "enum": ["user", "assistant"]},
            "content": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

SUMMARY_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "scope", "text", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": ["string", "null"]},
            "scope": {"bsonType": "string", "enum": ["session", "user"]},
            "text": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

EPISODE_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "fact", "importance", "embedding", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": "string"},
            "fact": {"bsonType": "string"},
            "importance": {"bsonType": "double", "minimum": 0.0, "maximum": 1.0},
            "embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
            "created_at": {"bsonType": "date"},
        },
    }
}


def recreate(db, name: str, validator: dict) -> None:
    if name in db.list_collection_names():
        db.drop_collection(name)
    db.create_collection(name, validator=validator)
    print(f"  created {name} with validator")


def main() -> None:
    db = get_db()
    print(f"Setting up database: {db.name}")
    recreate(db, "announcements", ANNOUNCEMENT_SCHEMA)
    recreate(db, "messages", MESSAGE_SCHEMA)
    recreate(db, "summaries", SUMMARY_SCHEMA)
    recreate(db, "episodes", EPISODE_SCHEMA)
    db.messages.create_index([("user_id", 1), ("session_id", 1), ("created_at", 1)])
    db.summaries.create_index([("user_id", 1), ("scope", 1), ("created_at", -1)])
    db.episodes.create_index([("user_id", 1)])
    print("Done.")


if __name__ == "__main__":
    main()
