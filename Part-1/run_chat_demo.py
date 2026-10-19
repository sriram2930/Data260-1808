"""
Part-1/run_chat_demo.py -- DATA-260 HW6, Part 2 (demo conversation)

Sends a real 10+ message conversation to POST /api/chat in one session, so
the short-term window, session/lifetime summarization, and episodic
retrieval can all be observed (per the assignment's "how to run and test").

Run (backend must already be up on PORT_BASE):
    python run_chat_demo.py
"""

from __future__ import annotations

import json
import time

import requests

BASE_URL = "http://127.0.0.1:8008"
USER_ID = "u1"

MESSAGES = [
    "Hi, my name is Sreeram and I am a grad student in Data Science.",
    "What courses does the Computer Science department offer?",
    "I'm especially interested in cloud computing topics.",
    "My advisor is Course Advisor and my student id is 019151808.",
    "Can you remind me what my major is?",
    "What is the difference between a session summary and a lifetime summary?",
    "I prefer online office hours over in-person ones.",
    "How many courses are in the Data Science and AI department?",
    "What was the first thing I told you about myself?",
    "Do you remember my preferred office hours format?",
    "One more thing, I am also minoring in Business Analytics.",
    "Can you summarize everything you know about me so far?",
]


def main() -> None:
    session_id = None
    print(f"=== run_chat_demo.py started {time.strftime('%Y-%m-%dT%H:%M:%S')} ===\n")
    for i, msg in enumerate(MESSAGES, start=1):
        payload = {"user_id": USER_ID, "message": msg}
        if session_id:
            payload["session_id"] = session_id
        t0 = time.perf_counter()
        resp = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=120)
        elapsed = time.perf_counter() - t0
        resp.raise_for_status()
        data = resp.json()
        session_id = data["session_id"]
        print(f"--- turn {i} ({elapsed:.1f}s) ---")
        print(f"user: {msg}")
        print(f"assistant: {data['reply']}")
        print(f"used: short_term_count={data['used']['short_term_count']}, "
              f"has_session_summary={data['used']['long_term_summary'] is not None}, "
              f"has_lifetime_summary={data['used']['lifetime_summary'] is not None}, "
              f"episodic_facts={data['used']['episodic_facts']}")
        print()

    print(f"=== finished {time.strftime('%Y-%m-%dT%H:%M:%S')} ===")
    print(f"session_id = {session_id}")


if __name__ == "__main__":
    main()
