"""
Part-4/memory_cli.py -- DATA-260 HW6, Part 4.3 (file-based memory commands)

Implements the four required commands as plain functions (so they're easy
to call from a test or a script) plus a tiny REPL wrapper for manual use.

    /memory   -- display the current file-based memory (AGENT.md + MEMORY.md)
    /compact  -- consolidate MEMORY.md, report before/after line counts
    /dream    -- extract durable facts from recent conversation into MEMORY.md
    /help     -- list the commands

/dream pulls "recent conversation" from Part 2's MongoDB messages
collection for a given user_id when one is passed, so the two memory
systems can share the same conversation history as their source material
rather than needing a second, separate log of what was said.

Run interactively:
    python memory_cli.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "Part-1"))

import file_memory

HELP_TEXT = """Available commands:
  /memory          Show the current AGENT.md + MEMORY.md content.
  /compact         Consolidate MEMORY.md (merge duplicates, resolve
                   contradictions explicitly) and report the line count
                   before and after.
  /dream <user_id> Pull that user's recent messages from MongoDB (Part 2)
                   and extract durable facts into MEMORY.md.
  /help            Show this message.
Anything else is treated as plain text and just echoed (this CLI is for
exercising the memory commands, not a full chat client -- see
Part-1/api_chat.py for that)."""


def cmd_memory() -> str:
    return file_memory.build_system_prompt_prefix()


def cmd_compact() -> str:
    should, reason = file_memory.needs_consolidation()
    result = file_memory.consolidate_memory_md()
    return (
        f"consolidation trigger check: {reason} -> {'triggered' if should else 'ran anyway (manual /compact)'}\n"
        f"before: {result['before_count']} lines\n"
        f"after:  {result['after_count']} lines"
    )


def _recent_conversation_text(user_id: str, limit: int = 20) -> str:
    sys.path.insert(0, str(REPO_ROOT / "Part-1"))
    from db_mongo import get_db

    db = get_db()
    msgs = list(
        db.messages.find({"user_id": user_id}, {"_id": 0, "role": 1, "content": 1})
        .sort("created_at", -1)
        .limit(limit)
    )
    msgs.reverse()
    return "\n".join(f"{m['role']}: {m['content']}" for m in msgs)


def cmd_dream(user_id: str) -> str:
    convo = _recent_conversation_text(user_id)
    if not convo:
        return f"no messages found for user_id={user_id!r}"
    added = file_memory.dream(convo)
    if not added:
        return "no new durable facts found"
    return "added to MEMORY.md:\n" + "\n".join(f"- {f}" for f in added)


def cmd_help() -> str:
    return HELP_TEXT


def dispatch(line: str) -> str:
    line = line.strip()
    if line == "/memory":
        return cmd_memory()
    if line == "/compact":
        return cmd_compact()
    if line.startswith("/dream"):
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            return "usage: /dream <user_id>"
        return cmd_dream(parts[1].strip())
    if line == "/help":
        return cmd_help()
    return f"(not a command, echoing): {line}"


def main() -> None:
    print("File-based memory CLI. Type /help for commands, Ctrl+C to exit.")
    while True:
        try:
            line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        print(dispatch(line))


if __name__ == "__main__":
    main()
