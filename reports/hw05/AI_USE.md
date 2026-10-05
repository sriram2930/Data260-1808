# AI_USE.md - HW5

(Covers Parts 1-4 so far; Part 5 -- the agent loop, safety rule, and
reflection -- is still in progress and this file will be extended once
that's done, same as the rest of HW5's incremental build-and-commit
pattern.)

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code to design and write the Department entity and its
migration against the already-populated HW4 database, extend the Course API
with validation and proper error codes, migrate the React client's data
layer to Redux Toolkit, build both MCP servers (the TheMealDB tutorial
server and the required domain server), write the retry/backoff policy and
the fault-injection experiment, and build the Part 4 offline test runner.
It ran all of this against real infrastructure throughout: the actual
MySQL container with the real 5,000-row HW4 dataset, the real TheMealDB
API, and the real MCP STDIO protocol (not just calling the Python functions
directly -- `inspect_tools.py` drives both servers through an actual MCP
client session, the same protocol the Inspector UI uses).

What I did myself: decided Department was the right "related entity" (and
that it should be a genuinely new table rather than repurposing HW4's
free-text `department` column, which stays untouched since Part 3's N+1
seed data and EXPLAIN demo depend on it), chose the domain server's three
tools and what "aggregate operation" should mean for this domain
(course_count/total/average seats per department), and designed the one
safety rule search_courses needed (rejecting an empty query, so the agent
can't dump the whole 5,000-row catalogue through a single call) before any
agent code existed to enforce it against.

## 2. One AI-produced output that was wrong/unsuitable

The first version of `migrate_hw05.py` deadlocked. It opened one SQLAlchemy
session, used it to read back the newly-seeded Department rows
(`db.query(Department).all()`), and then, without closing that read
transaction, opened a second connection to run
`ALTER TABLE courses ADD COLUMN department_id ... ADD CONSTRAINT ... FOREIGN
KEY (department_id) REFERENCES departments(id)`. Adding a foreign key needs
a metadata lock on both tables involved, including the referenced table
(`departments`), and the first session's still-open read transaction was
already holding a lock on `departments` that the DDL statement then had to
wait for forever.

## 3. How I detected the problem

The script just sat there with zero output for about three minutes. Rather
than assume it was simply slow (the honest lesson from HW4's N+1 experiment
was the opposite mistake, killing a slow-but-working process too early), I
checked `Get-Process` CPU time for the two Python processes first: both
were at a fraction of a second of CPU time after three minutes of wall
time, which rules out "slow but computing" and points at "blocked waiting
on something." `SHOW PROCESSLIST` on the MySQL container confirmed it
directly: one connection sitting in `Sleep`, and a second stuck in `Waiting
for table metadata lock` on the exact `ALTER TABLE` statement.

## 4. What I changed and why it works now

I added an explicit `db.commit()` right after each read that happens
before a DDL step, closing out that transaction (and its locks) before the
`ALTER TABLE` runs. After that fix, the script completed in a couple of
seconds end to end, and rerunning it is idempotent (every step checks
"does this already exist" first) so I could verify it safely a second
time. The broader habit this reinforced: with SQLAlchemy's default
`autocommit=False`, even a plain `SELECT` opens a transaction that stays
open, and holding one across a later schema change is enough to deadlock
against yourself in a single script, not just against a genuinely separate
concurrent process.
