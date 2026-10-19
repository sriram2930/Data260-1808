"""
Part-1/api_chat.py -- DATA-260 HW6, Part 2 (chat + memory introspection API)

    POST /api/chat                 one conversational turn (see memory.py
                                    for the short/long/episodic logic)
    GET  /api/memory/{user_id}     last ~16 messages, latest session +
                                    lifetime summaries, last ~20 episodes
    GET  /api/aggregate/{user_id}  daily message counts + recent summaries

These are intentionally NOT behind api_auth.require_user: the chat memory
system is its own user_id-scoped concept (matching the assignment's
{user_id, session_id, message} request shape), separate from the MySQL
session-cookie login HW4/HW5's Course/Department CRUD uses.
"""

from __future__ import annotations

from fastapi import APIRouter

from db_mongo import get_db
from memory import SHORT_TERM_N, chat_turn
from models_mongo import ChatIn, ChatOut

router = APIRouter(prefix="/api")


@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn):
    result = chat_turn(payload.user_id, payload.session_id, payload.message, SHORT_TERM_N)
    return {"reply": result["reply"], "session_id": result["session_id"], "used": result["used"]}


@router.get("/memory/{user_id}")
def get_memory(user_id: str):
    db = get_db()
    messages = list(
        db.messages.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(16)
    )
    messages.reverse()
    session_summary = db.summaries.find_one(
        {"user_id": user_id, "scope": "session"}, {"_id": 0}, sort=[("created_at", -1)]
    )
    lifetime_summary = db.summaries.find_one(
        {"user_id": user_id, "scope": "user"}, {"_id": 0}, sort=[("created_at", -1)]
    )
    episodes = list(
        db.episodes.find({"user_id": user_id}, {"_id": 0, "embedding": 0})
        .sort("created_at", -1)
        .limit(20)
    )
    return {
        "messages": messages,
        "latest_session_summary": session_summary,
        "latest_lifetime_summary": lifetime_summary,
        "episodes": episodes,
    }


@router.get("/aggregate/{user_id}")
def get_aggregate(user_id: str):
    db = get_db()
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    daily_counts = [{"date": r["_id"], "count": r["count"]} for r in db.messages.aggregate(pipeline)]
    recent_summaries = list(
        db.summaries.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(5)
    )
    return {"daily_message_counts": daily_counts, "recent_summaries": recent_summaries}
