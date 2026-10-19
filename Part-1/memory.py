"""
Part-1/memory.py -- DATA-260 HW6, Part 2 (short-, long-, and episodic memory)

All the logic POST /api/chat needs, kept separate from the route handler
(api_chat.py) so Part 3's experiments can call these functions directly
without going through HTTP:

  - short-term: sliding window of the last SHORT_TERM_N messages in a session
  - long-term: session summaries (scope="session") triggered every
    SUMMARIZE_EVERY_USER_MSGS user messages, condensed into a lifetime
    summary (scope="user", session_id=None) once a user has a few of them
  - episodic: up to 3 short facts extracted per user message via the local
    Ollama model, embedded with the same HuggingFace embedding model Part-5
    (HW3) uses, retrieved by cosine similarity against the user's stored
    episodes
  - prompt assembly: system primer + long-term summaries + short-term
    window + episodic facts + the current message
  - token counting: real counts from Ollama's own response for the overall
    prompt/completion totals; a cheap chars/4 estimate for the per-component
    breakdown (primer/summary/short-term/episodic), since Ollama does not
    expose a per-segment count -- documented as an estimate wherever it's
    reported, not presented as something it isn't.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))

from src.model_client import ModelClient  # noqa: E402

from db_mongo import get_db  # noqa: E402

SHORT_TERM_N = 12
SUMMARIZE_EVERY_USER_MSGS = 5
EPISODE_TOP_K = 3
MIN_SESSION_SUMMARIES_FOR_LIFETIME = 2

SYSTEM_PRIMER = (
    "You are a helpful assistant for a campus course catalogue and enrolment system. "
    "Answer briefly and use the context provided (summaries and recalled facts) when relevant."
)

_model_client: Optional[ModelClient] = None
_embed_model = None


def get_model_client() -> ModelClient:
    global _model_client
    if _model_client is None:
        _model_client = ModelClient()
    return _model_client


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        _embed_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embed_model


def estimate_tokens(text: str) -> int:
    """Cheap, documented-as-approximate token estimate (~4 chars/token),
    used only for the per-component breakdown Ollama itself doesn't expose."""
    return max(0, len(text) // 4)


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


# ----------------------------------------------------------------- storage


def save_message(user_id: str, session_id: str, role: str, content: str) -> None:
    db = get_db()
    db.messages.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.datetime.utcnow(),
    })


def get_short_term_window(user_id: str, session_id: str, n: int = SHORT_TERM_N) -> list[dict]:
    db = get_db()
    docs = list(
        db.messages.find({"user_id": user_id, "session_id": session_id})
        .sort("created_at", -1)
        .limit(n)
    )
    docs.reverse()
    return docs


def count_user_messages(user_id: str, session_id: str) -> int:
    db = get_db()
    return db.messages.count_documents({"user_id": user_id, "session_id": session_id, "role": "user"})


def get_latest_summary(user_id: str, scope: str, session_id: Optional[str] = None) -> Optional[dict]:
    db = get_db()
    query: dict[str, Any] = {"user_id": user_id, "scope": scope}
    if scope == "session":
        query["session_id"] = session_id
    else:
        query["session_id"] = None
    return db.summaries.find_one(query, sort=[("created_at", -1)])


# ------------------------------------------------------------- summarization


def maybe_summarize(user_id: str, session_id: str) -> None:
    """Every SUMMARIZE_EVERY_USER_MSGS user messages, (re)generate a session
    summary. Once a user has at least MIN_SESSION_SUMMARIES_FOR_LIFETIME
    session summaries, condense them all into one lifetime summary."""
    db = get_db()
    n_user_msgs = count_user_messages(user_id, session_id)
    if n_user_msgs == 0 or n_user_msgs % SUMMARIZE_EVERY_USER_MSGS != 0:
        return

    recent = list(
        db.messages.find({"user_id": user_id, "session_id": session_id}).sort("created_at", 1)
    )
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    prompt = (
        "Summarize this conversation into 3-5 concise bullet points capturing durable "
        "facts and intent, not small talk:\n\n" + transcript
    )
    result = get_model_client().complete([
        {"role": "system", "content": "You write terse, factual conversation summaries."},
        {"role": "user", "content": prompt},
    ])
    db.summaries.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "scope": "session",
        "text": result["content"].strip(),
        "created_at": datetime.datetime.utcnow(),
    })

    session_summaries = list(
        db.summaries.find({"user_id": user_id, "scope": "session"}).sort("created_at", 1)
    )
    if len(session_summaries) >= MIN_SESSION_SUMMARIES_FOR_LIFETIME:
        combined = "\n".join(f"- {s['text']}" for s in session_summaries)
        lifetime_prompt = (
            "Condense these session summaries for the same user into one short lifetime "
            "summary (3-6 bullets) of durable facts about them:\n\n" + combined
        )
        lifetime_result = get_model_client().complete([
            {"role": "system", "content": "You write terse, factual lifetime-summary bullets."},
            {"role": "user", "content": lifetime_prompt},
        ])
        db.summaries.insert_one({
            "user_id": user_id,
            "session_id": None,
            "scope": "user",
            "text": lifetime_result["content"].strip(),
            "created_at": datetime.datetime.utcnow(),
        })


# ----------------------------------------------------------------- episodic


def extract_episodes(user_id: str, session_id: str, user_message: str) -> list[dict]:
    """Extracts up to 3 short durable facts from a user message via the
    local model, embeds each, and stores them. Returns what was stored."""
    prompt = (
        "Extract up to 3 short, durable facts about the user from this message, each with "
        "an importance score from 0 to 1 (1 = very important to remember long-term). "
        "If there is nothing worth remembering, return an empty list. "
        'Reply with ONLY a JSON array like [{"fact": "...", "importance": 0.8}]. '
        f"Message: {user_message!r}"
    )
    result = get_model_client().complete(
        [{"role": "user", "content": prompt}], format="json"
    )
    try:
        parsed = json.loads(result["content"])
        if isinstance(parsed, dict):
            # The small model sometimes returns one fact object directly
            # instead of wrapping it in a list, or wraps the list under a
            # "facts" key -- handle both rather than silently dropping it.
            if "fact" in parsed:
                parsed = [parsed]
            else:
                parsed = parsed.get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        parsed = []

    stored = []
    db = get_db()
    embed_model = get_embed_model()
    for item in parsed[:3]:
        fact = str(item.get("fact", "")).strip()
        if not fact:
            continue
        importance = float(item.get("importance", 0.5))
        importance = max(0.0, min(1.0, importance))
        embedding = embed_model.get_text_embedding(fact)
        doc = {
            "user_id": user_id,
            "session_id": session_id,
            "fact": fact,
            "importance": importance,
            "embedding": [float(x) for x in embedding],
            "created_at": datetime.datetime.utcnow(),
        }
        db.episodes.insert_one(doc)
        stored.append(doc)
    return stored


def retrieve_episodes(user_id: str, query_text: str, k: int = EPISODE_TOP_K) -> list[dict]:
    db = get_db()
    episodes = list(db.episodes.find({"user_id": user_id}))
    if not episodes:
        return []
    embed_model = get_embed_model()
    query_vec = np.array(embed_model.get_text_embedding(query_text))
    query_norm = np.linalg.norm(query_vec)

    scored = []
    for ep in episodes:
        vec = np.array(ep["embedding"])
        denom = query_norm * np.linalg.norm(vec)
        sim = float(query_vec.dot(vec) / denom) if denom else 0.0
        scored.append((sim, ep))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _sim, ep in scored[:k]]


# ------------------------------------------------------------ prompt build


def build_prompt(
    user_id: str,
    session_id: str,
    user_message: str,
    short_term_n: int = SHORT_TERM_N,
    compress_short_term: bool = False,
    compress_len: int = 120,
) -> dict:
    """Returns {messages, token_breakdown, short_term, summaries, episodes}
    -- `messages` is the OpenAI-style list ready for ModelClient.complete,
    the rest is everything Part 3 needs to log and everything the chat
    response needs to report back under "used".

    compress_short_term is Part 3.4's one eviction/compression policy: each
    short-term message gets truncated to compress_len characters before it
    goes into the prompt, instead of the full text -- a plain truncation
    policy, the simplest compression that still trades some information for
    fewer tokens, kept deliberately simple given the time this homework had."""
    short_term = get_short_term_window(user_id, session_id, short_term_n)
    session_summary = get_latest_summary(user_id, "session", session_id)
    lifetime_summary = get_latest_summary(user_id, "user")
    episodes = retrieve_episodes(user_id, user_message)

    long_term_text = ""
    if lifetime_summary:
        long_term_text += f"Lifetime summary:\n{lifetime_summary['text']}\n\n"
    if session_summary:
        long_term_text += f"Earlier in this session:\n{session_summary['text']}\n\n"

    episodic_text = ""
    if episodes:
        episodic_text = "Known facts about this user:\n" + "\n".join(
            f"- {e['fact']}" for e in episodes
        )

    system_content = SYSTEM_PRIMER
    if long_term_text:
        system_content += "\n\n" + long_term_text.strip()
    if episodic_text:
        system_content += "\n\n" + episodic_text

    def _content(m: dict) -> str:
        if compress_short_term and len(m["content"]) > compress_len:
            return m["content"][:compress_len] + "..."
        return m["content"]

    messages = [{"role": "system", "content": system_content}]
    for m in short_term:
        messages.append({"role": m["role"], "content": _content(m)})
    messages.append({"role": "user", "content": user_message})

    short_term_text = "\n".join(_content(m) for m in short_term)
    token_breakdown = {
        "primer_tokens_est": estimate_tokens(SYSTEM_PRIMER),
        "long_term_tokens_est": estimate_tokens(long_term_text),
        "short_term_tokens_est": estimate_tokens(short_term_text),
        "episodic_tokens_est": estimate_tokens(episodic_text),
    }

    return {
        "messages": messages,
        "token_breakdown": token_breakdown,
        "short_term": short_term,
        "session_summary": session_summary,
        "lifetime_summary": lifetime_summary,
        "episodes": episodes,
    }


def chat_turn(
    user_id: str,
    session_id: Optional[str],
    user_message: str,
    short_term_n: int = SHORT_TERM_N,
    compress_short_term: bool = False,
) -> dict:
    """One full /api/chat turn. Returns reply, session_id, used, and a
    metrics dict (token counts + latency) for Part 3 to log."""
    session_id = session_id or new_session_id()

    save_message(user_id, session_id, "user", user_message)
    return _run_turn_after_save(user_id, session_id, user_message, short_term_n, compress_short_term)


def _run_turn_after_save(
    user_id: str,
    session_id: str,
    user_message: str,
    short_term_n: int = SHORT_TERM_N,
    compress_short_term: bool = False,
) -> dict:
    """Everything chat_turn does AFTER saving the user message -- split out
    so a caller that wants to retry the (expensive, model-calling) rest of
    a turn on a transient failure, as Part 3's experiment harness does,
    doesn't also re-save the user's message a second time on retry."""
    built = build_prompt(user_id, session_id, user_message, short_term_n, compress_short_term)

    t0 = time.perf_counter()
    result = get_model_client().complete(built["messages"])
    latency_ms = (time.perf_counter() - t0) * 1000

    save_message(user_id, session_id, "assistant", result["content"])
    maybe_summarize(user_id, session_id)
    extract_episodes(user_id, session_id, user_message)

    used = {
        "short_term_count": len(built["short_term"]),
        "short_term_messages": [m["content"] for m in built["short_term"]],
        "long_term_summary": (built["session_summary"] or {}).get("text"),
        "lifetime_summary": (built["lifetime_summary"] or {}).get("text"),
        "episodic_facts": [e["fact"] for e in built["episodes"]],
    }
    metrics = {
        "prompt_tokens": result["usage"]["input_tokens"],
        "completion_tokens": result["usage"]["output_tokens"],
        "latency_ms": round(latency_ms, 2),
        **built["token_breakdown"],
    }

    return {
        "reply": result["content"],
        "session_id": session_id,
        "used": used,
        "metrics": metrics,
    }
