# HW9 AI Use Statement

### 1. What AI was used for

The assignment, the Course-catalogue domain, the HW1-HW8 repository and the
local environment are the student's. Claude Code designed and wrote the Redis
view counter, the semantic cache and Redis vector index, the threshold
sweep / stale-answer demo / cost model, the two-agent self-improving system
with lessons and validation, `verify_hw09.py`, and the report, and started the
Redis / MySQL / Kafka containers. Everything was run for real (Redis Stack,
MySQL and Kafka in Docker; Ollama for every model call). The one replayed
element is disclosed in the report (3.2): each distinct sweep query went
through the real HW8 pipeline once and the sweep reuses that recorded answer
and latency for misses.

### 2. AI output that was wrong or unsuitable

- First Redis import path (`redis.commands.search.indexDefinition`) does not
  exist in the installed redis-py (it is `index_definition`); failed on first run.
- All 5,000 seeded courses had `seats_available = 30`, so two "how many seats"
  questions had the same correct answer and could not be "similar, different
  answer" cases. Three records were given distinct seat counts
  (`Part-13/seed_hw09.py`; CS-00005 reset to 30).
- The first Answering Agent revision prompt put the previous answer and the
  feedback in one user message; on the training set the 1.5B model repeated its
  first answer word for word (three traces inspected), so repair fixed 0
  questions (`raw/part4_training_run_v1_single_prompt.txt`). Sending feedback
  as a separate chat turn fixed the seat comparison (16 -> 17/20 after repair).

### 3. How the problems were detected

By running the code and reading real output: the import error, a query
showing every course had 30 seats, the training trace where attempt 2 equalled
attempt 1, and a before/after prompt test on training questions only.

### 4. What changed and why it works now

Import fixed; seat data seeded idempotently; revision feedback is a proper chat
turn; the evaluator was not changed after the test set was read. Still
unresolved (stated in the report): the similarity threshold alone cannot
separate course codes that differ by one digit, and the 1.5B model often
ignores a decline instruction.

> Note for the student: this statement describes what Claude Code did. Add
> anything you personally decided or checked before submitting.
