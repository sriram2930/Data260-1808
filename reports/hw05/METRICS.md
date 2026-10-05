# METRICS - DATA-260 HW5

## Part 2: MCP Tool Servers

### A. TheMealDB tutorial server (`Part-7/meals_server.py`)

Four tools (`search_meals_by_name`, `meals_by_ingredient`, `random_meal`,
`meal_details`), run with `mcp dev meals_server.py` and tested in the MCP
Inspector, plus verified directly against the live TheMealDB API before
that (search for "Arrabiata" -> 1 match, filter by "chicken" -> cards
returned, a random meal -> full recipe shape, lookup by a known id -> the
right meal name, a nonsense query -> `{"count": 0, "message": "no matches"}`
instead of an error).

### B. Domain server (`Part-7/domain_server.py`)

Three tools over the real `s1808_rel` MySQL database (the same one Part 1's
FastAPI backend uses, via `Part-1/db.py` / `models.py`), all returning the
shared `{ok, data, error}` envelope (`envelope.py`):

| Tool | Role | Valid example | Invalid example |
|---|---|---|---|
| `search_courses(query, limit)` | search | `{"query": "Cloud Computing", "limit": 3}` -> 3 matching courses | `{"query": "", "limit": 3}` -> rejected |
| `course_detail(course_id)` | detail lookup | `{"course_id": 7}` -> full course + department | `{"course_id": 999999}` -> not found |
| `department_stats(department_id)` | aggregate | `{"department_id": 1}` -> course_count/total/avg seats | `{"department_id": 999999}` -> not found |

## Part 3: Tool Contracts Under Stress

### 3.18: Expected schema, rejected input, and error per tool

**`search_courses`**
- Expected input: `{"query": "<non-empty string>", "limit": "<int, 1-100>"}`
- Rejected input: `{"query": "", "limit": 5}`
- Returned error: `{"ok": false, "data": null, "error": "query must be a non-empty string"}`
- Why rejected: an empty/whitespace-only query would otherwise match every
  row in a 5,000+ row table via the `LIKE '%%'` pattern, so it's rejected
  before it ever reaches the database.

**`course_detail`**
- Expected input: `{"course_id": "<positive int>"}`
- Rejected input: `{"course_id": 999999}`
- Returned error: `{"ok": false, "data": null, "error": "course_id 999999 not found"}`
- Why rejected: no row with that id exists in `courses`. (A second,
  type-level rejection also exists: `{"course_id": -1}` ->
  `"course_id must be a positive integer"`, checked before any query runs.)

**`department_stats`**
- Expected input: `{"department_id": "<positive int>"}`
- Rejected input: `{"department_id": 999999}`
- Returned error: `{"ok": false, "data": null, "error": "department_id 999999 not found"}`
- Why rejected: no row with that id exists in `departments`.

All three rejections return the normal `{ok, data, error}` envelope with a
`False`/`null`/message shape, never an exception or an HTTP-style error
code - the same contract an agent calling `execute_tool` (Part 4) can rely
on regardless of which tool it called or why it failed.

### 3.19: Retry policy demonstration (`Part-7/run_fault_injection.py`, Scenario A/B/C)

Full transcript: [`RUN_LOG.txt`](RUN_LOG.txt).

| Scenario | Attempts | Outcome |
|---|---|---|
| A: success on the first attempt | 1 | succeeds immediately, no retry needed |
| B: failure on attempt 1, success on retry | 2 | first attempt raises, backoff sleep, second attempt succeeds |
| C: failure on every attempt | 3 (= max_retries + 1) | all three fail; `RetryExhausted` raised cleanly (no crash) instead of the original exception |

### 3.20: 150-call fault injection (`VERIFY_SEED = 261808`)

Command run:
```
python run_fault_injection.py
```
Raw per-call records (all 150): [`raw/fault_injection_calls.csv`](raw/fault_injection_calls.csv),
[`raw/fault_injection_calls.json`](raw/fault_injection_calls.json). Summary:
[`raw/fault_injection_summary.json`](raw/fault_injection_summary.json).

| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |
|---|---|---|---|
| 0%  | 1.00 | 42.03 | 71.81  |
| 20% | 0.98 | 54.11 | 185.06 |
| 50% | 0.82 | 99.90 | 188.59 |

Reproducibility check: re-running `FlakyOperation(seed=261808, failure_rate=0.5)`
through `call_with_retry` from a fresh process twice in a row produced the
identical 5-call outcome sequence both times
(`[('ok', 1), ('ok', 2), ('ok', 2), ('ok', 2), ('ok', 2)]`), confirming the
seed genuinely pins the success/failure pattern rather than just looking
stable by chance.

With `max_retries=2` (3 attempts total) and attempts drawn independently at
the injected rate, the chance of a given call exhausting all 3 attempts is
`rate^3`: 0% at a 0% injected rate, 0.8% at 20%, 12.5% at 50%. Over 50 calls
that predicts roughly 0, 0.4, and 6.25 failed calls - the observed 0, 1, and
9 failures are all consistent with that (50 calls is a small enough sample
that 9 vs. an expected ~6 is normal binomial variance, not a sign of a
broken policy). Latency rises with the injected rate for the same reason:
more calls need a second or third attempt, and each extra attempt adds both
its own ~40ms simulated work and a backoff sleep before it runs.

### 3.21: Is this retry policy right for an interactive assistant?

Mostly yes, with one caveat. `max_retries=2` and the fast exponential
backoff (20ms, then 40ms) mean even the worst case in this data (p99 at the
50% rate) stays under 200ms, which is well inside what feels instant to a
person typing into a chat UI. The real risk for an interactive setting
isn't the retry policy's own latency, it's `timeout_s=1.0`: a genuinely
slow (not failed) dependency could make a single attempt take up to a full
second before even starting its backoff, and three of those back to back
would be a multi-second stall a user would notice and probably assume the
app had frozen. For an interactive assistant I'd tighten `timeout_s` to
something like 300-500ms (fail fast, let the retry handle the recovery
instead of a long single wait) and keep `max_retries` at 2 or even drop it
to 1, since the data above shows almost everything that's going to succeed
already succeeds by attempt 2.

For batch processing, where nobody is watching a spinner, I'd invert most
of those choices: raise `max_retries` to something like 5, lengthen the
backoff base delay so retries are spaced further apart (giving a
genuinely overloaded dependency more time to recover instead of hammering
it every 20-40ms), and raise `timeout_s` substantially (several seconds)
since a slow-but-eventually-successful response is still strictly better
than a wasted retry in a batch job with no user waiting on it. The
underlying trade-off is the same policy shape (timeout + bounded
exponential backoff) tuned for a different cost function: interactive
optimizes for bounded worst-case latency even if that means giving up a
little sooner, batch optimizes for eventual success even if that means
waiting longer.

## Part 4: One Safe Tool Entry Point and Offline Tests

`Part-7/execute_tool.py`'s `execute_tool(name, inputs)` reuses the exact
`{ok, data, error}` envelope from Part 2B, returns it as a JSON string, and
never raises - an unknown tool name, malformed inputs, or an unexpected
exception from inside a tool all come back as a normal `ok: false` envelope
instead of propagating.

Offline test runner: `Part-7/test_tools.py`. Fully offline and repeatable -
`make_test_session()` builds a fresh in-memory SQLite database from the
same SQLAlchemy models the real MySQL database uses, seeds one department
and two courses, and every test injects that session into `execute_tool`
via its `session=` parameter instead of touching the real `s1808_rel`
database. Ran three times in a row with identical results each time.

Command run:
```
python test_tools.py
```

```
[PASS] search_courses: valid query finds both seeded courses
[PASS] search_courses: empty query is rejected cleanly
[PASS] course_detail: valid id returns the right course + department
[PASS] course_detail: nonexistent id is rejected cleanly (not a crash)
[PASS] department_stats: valid id aggregates correctly (2 courses, 40 total seats, 20.0 avg)
[PASS] department_stats: nonexistent id is rejected cleanly (not a crash)
[PASS] execute_tool: unknown tool name is rejected cleanly (not a crash)
[PASS] execute_tool: malformed inputs (wrong arg name) are rejected cleanly (not a crash)

8/8 tests passed
```

8 tests total (6 required: one valid + one invalid per domain tool), plus
two extra covering `execute_tool`'s own dispatch logic (unknown tool name,
malformed inputs) rather than a specific domain tool's business rules.

## Part 5: Agent Loop, Safety Rule, and Reflection

### Safety rule

`execute_tool.py`'s `_check_safety_rule`: agent calls to `search_courses`
are capped at `limit<=20`, stricter than the 100 the API itself allows for
a trusted direct caller (Postman/Inspector) - this specifically stops the
autonomous loop from pulling a large chunk of the catalogue into its own
context in one call.

```
allowed: {"ok": true, "data": [... 10 courses ...], "error": null}
blocked: {"ok": false, "data": null, "error": "safety rule: agent calls to
          search_courses are capped at limit<=20 (got 50)"}
```

### Offline tests (now 10/10, two added for Part 5)

```
[PASS] execute_tool: safety rule blocks search_courses with limit>20
[PASS] run_agent: MockModel that never finishes stops at max_steps

10/10 tests passed
```

### Scenarios (`Part-7/run_agent_scenarios.py`, real local Ollama model)

| # | Scenario | Steps | Stop reason | Tool calls |
|---|---|---|---|---|
| 1 | "What are the details for course id 7?" | 2 | normal_completion | 1 |
| 2 | "Give me the stats for department 1." | 2 | normal_completion | 1 |
| 3 | "Search for courses about Cloud Computing." | 2 | normal_completion | 1 |
| 4 | "Search for courses about data, with a limit of 50." | 4 | max_steps | 4 |

Raw per-step log: [`raw/agent_runs.jsonl`](raw/agent_runs.jsonl). Scenario 4
is the one walked through step by step in [`REFLECTION.md`](REFLECTION.md) -
the safety rule blocked the oversized call every time it was tried, and the
model never recovered by retrying with a smaller limit, instead wandering
into two other tools with type-mismatched arguments before the loop hit
`max_steps` and stopped cleanly.
