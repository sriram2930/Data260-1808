# AGENT.md - Project and Agent Instructions

## Project description

This repository (`data260-<SID4>`) is a single, continuously-extended
semester project for DATA-260: a campus course catalogue and enrolment
system (DOMAIN_ID 0). Each homework adds to the same codebase rather than
starting a new one. HW2 added the FastAPI backend, HW4 added MySQL and a
React client, HW5 added MCP tool servers and an agent loop, HW6 adds a
MongoDB document view, a short/long/episodic chat-memory system, and this
file-based memory system.

## Technology stack

- Backend: FastAPI (Python), served on `PORT_BASE` from `Part-1/main.py`.
- Relational data: MySQL via SQLAlchemy (`Part-1/db.py`, `models.py`).
- Document data: MongoDB via PyMongo (`Part-1/db_mongo.py`, `models_mongo.py`).
- Local LLM: Ollama (`qwen2.5:1.5b-instruct`), always called through
  `Part-4/src/model_client.py`'s `ModelClient`, never call `ollama` or an
  HTTP endpoint directly from new code.
- Frontend: React + Redux Toolkit (`Part-6/`).

## Coding conventions

- Respond with **bullet points only** when asked to review code, with no
  introductory sentence and no concluding paragraph, no prose outside the
  bullets. Each bullet is a single, specific, actionable comment
  (correctness, edge cases, naming, style, efficiency, whichever
  applies). If the code has no issues, respond with exactly one bullet:
  `- No issues found.` Never use numbered lists, headings, or code blocks
  in a review response, bullets (`-`) only. This applies to every code
  review request in the conversation, not just the first; a request that
  is *not* a code review gets a normal prose answer instead.
- New Python modules get a short module-level docstring explaining what the
  file is for and why it exists, matching the style already used across
  `Part-1/` through `Part-8/`.
- Reuse existing adapters (`ModelClient`, `db.py`/`db_mongo.py`) instead of
  opening new, parallel connections or clients for the same resource.

## Testing approach

- New backend logic gets verified against the real, running dependency it
  touches (the real MySQL/Mongo container, the real local Ollama model,
  the real MCP STDIO protocol) before being called done, not just unit
  tests against mocks. Offline/mocked tests (e.g. `Part-7/test_tools.py`)
  are for fast, repeatable regression checks on top of that, not a
  replacement for it.
- Every homework's `reports/hwNN/` folder gets a `verify_hwNN.py` smoke
  test that checks the previous behavior still works, and writes
  `verification.json`.

## Prohibited actions

- Never commit real secrets (passwords, API keys, tokens) to the
  repository, even in a `.env`-style file. Use environment variables with
  documented defaults instead, as `db.py`/`db_mongo.py` already do.
- Never silently drop or overwrite a previous homework's working code to
  make room for a new one; extend it in place (see `models.py`'s
  HW4-era `department` string column, kept untouched through HW5 and HW6
  because earlier experiments depend on it).
- Never fabricate experiment results, screenshots, or metrics. If evidence
  could not be captured (a GUI tool wasn't available, a screenshot didn't
  make it in time), say so directly in the report rather than presenting
  something that didn't happen as if it did.
