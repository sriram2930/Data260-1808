"""
Part-1/db_mongo.py -- DATA-260 HW6, Part 1.I (MongoDB connection)

PyMongo connection to the s1808_doc database (a local MongoDB container,
see README's HW6 section for the docker run command), kept as a separate
module from db.py (the MySQL/SQLAlchemy connection HW4/HW5 use) since the
two are genuinely different databases serving different parts of the app,
not a replacement for one another.
"""

from __future__ import annotations

import os

from pymongo import MongoClient

MONGO_HOST = os.environ.get("MONGO_HOST", "127.0.0.1")
MONGO_PORT = os.environ.get("MONGO_PORT", "27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "s1808_doc")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(f"mongodb://{MONGO_HOST}:{MONGO_PORT}/")
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]
