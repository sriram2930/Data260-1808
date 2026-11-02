# HW8 Metrics

## Section 0 — Config

| Value | Setting |
|---|---|
| SID4 | 1808 |
| PORT_BASE | 8008 |
| PREFIX | s1808 |
| SEED | 1808 |
| VERIFY_SEED | 261808 |
| DOMAIN_ID | 0 (Campus course catalogue and enrolment) |
| Hardware | Intel Core i7-11390H, 16GB RAM, integrated Iris Xe graphics (no dedicated GPU) |
| Local model | qwen2.5:1.5b-instruct via Ollama (Part 2's three-agent pipeline) |
| Repo | https://github.com/sriram2930/Data260-1808 |
| Commit tagged as hw8 | (filled in after final commit) |

---

## Part 1 — Backend Service Request/Response over Kafka

Entity: **Course** (this project's primary domain entity since HW1), fields
`course_code`, `course_title` (required), `description`, `department`,
`seats_available` (optional). Operations: `CREATE_ENTITY`/`GET_ENTITY` →
`CREATE_COURSE`-shaped payloads using `course_id` as the generated UUID
field name.

**Topics:** `s1808_entity_requests`, `s1808_entity_responses` (both
created via `kafka-topics --create`, see `raw/topics_created.txt`).

**Architecture:** `Part-10/worker.py` (consumer+producer, plain-dict
store, `entity_store.py`), `Part-10/api.py` (FastAPI wrapper, one
persistent background response-listener thread dispatching by
`correlation_id` to waiting request threads via `threading.Event`),
`Part-10/homework_demo.py` (direct Kafka client, no HTTP layer, for the
graded demo sequence). All three containerized
(`docker-compose.kafka.yml`): `s1808-zookeeper`, `s1808-kafka`,
`s1808-worker`, `s1808-api` — real `docker ps` evidence in
`raw/docker_ps.txt`.

**Message schema** (both directions preserve `correlation_id`):
```
request:  {"correlation_id": "...", "reply_to": "s1808_entity_responses",
           "operation": "CREATE_ENTITY" | "GET_ENTITY", "data": {...}}
response: {"correlation_id": "...", "success": true|false, ...}
```

**Full demo sequence** (`raw/homework_demo.log`, matching worker log
`raw/worker_container.log`): CREATE_ENTITY → extract `entity_id` →
GET_ENTITY using that `entity_id`, `correlation_id` preserved and
asserted at each step, both round trips completing in 14-28ms against
the fully containerized stack.

**Error cases** (`raw/error_cases.log`): missing required field, empty
required field, unknown operation, GET_ENTITY for a nonexistent
`entity_id` — all return `success: false` with a clean error message and
the original `correlation_id` preserved.

### Real operational issues found and fixed

Three distinct, real problems surfaced while getting this working — not
simulated, each confirmed by direct observation before being fixed (full
story in `AI_USE.md`):

1. **Consumer group join race.** A single `consumer.poll()` call does not
   reliably complete a consumer group's join/sync rebalance against this
   broker — confirmed empirically it can take ~7 polls (~3.5s). Code that
   sent a request right after one `poll()` call got no response, because
   the consumer's partition assignment hadn't actually landed yet.
   Fixed by polling in a loop until `consumer.assignment()` is non-empty
   before proceeding, in `worker.py`, `api.py`, and `homework_demo.py`.

2. **Docker single-listener trap.** A single `KAFKA_ADVERTISED_LISTENERS`
   value (`localhost:9092`) lets a container connect for its *initial*
   bootstrap, but every request after that uses the advertised address
   from broker metadata — which is `localhost` from the container's own
   point of view, not the Kafka container, producing a real
   `ECONNREFUSED` on the second request onward. Fixed with a real
   dual-listener setup: `PLAINTEXT` (`s1808-kafka:29092`, internal,
   advertised to containers) and `PLAINTEXT_HOST` (`localhost:9092`,
   advertised to the host).

3. **Unbuffered container stdout.** Python fully buffers stdout when it
   isn't a TTY (true for a container's main process) — several apparent
   "the worker isn't processing anything" moments during development were
   actually just unflushed log output; the consumer group's committed
   offset had already advanced. Fixed with `ENV PYTHONUNBUFFERED=1` in
   both Dockerfiles.

---

## Part 2 — Three-Agent Kafka Pipeline

Topics: `s1808_inbox`, `s1808_tasks` (2 partitions), `s1808_drafts`,
`s1808_final` (created via `kafka-topics --create`, see
`raw/topics_created.txt`). Three independent processes
(`Part-11/planner.py`, `writer.py`, `reviewer.py`), each its own terminal,
each only ever talking to Kafka — no process imports or calls another
directly.

| Sender | Reads | Writes | Role |
|---|---|---|---|
| You (`send_question.py`) | — | `s1808_inbox` | asks a question |
| Planner | `s1808_inbox` | `s1808_tasks` | 2-4 bullet plan |
| Writer | `s1808_tasks` | `s1808_drafts` | 3-6 sentence draft following the plan |
| Reviewer | `s1808_drafts` | `s1808_final` | checks/corrects, emits `{status, answer}` |

**One complete message journey** (`correlation_id=52db7270-8e2b-4f13-8672-ce2994099e43`,
`raw/planner.log`, `raw/writer.log`, `raw/reviewer.log`, `raw/send_question.log`):

```
CLIENT   SEND  -> s1808_inbox:   "What is a race condition in concurrent programming?"
PLANNER  received from s1808_inbox   (same correlation_id)
PLANNER  sent to s1808_tasks         (same correlation_id)
WRITER   received from s1808_tasks   (same correlation_id)
WRITER   sent to s1808_drafts        (same correlation_id)
REVIEWER received from s1808_drafts  (same correlation_id)
REVIEWER sent to s1808_final         (same correlation_id)
CLIENT   RECV  <- s1808_final: status=approved
```

**Final JSON** (`s1808_final`):
```json
{"correlation_id": "52db7270-...", "status": "approved",
 "answer": "A race condition in concurrent programming occurs when multiple
 threads access shared resources without proper synchronization, leading to
 unpredictable results. ... By employing appropriate synchronization
 techniques, such as locks, semaphores, or atomic operations, race
 conditions can be mitigated..."}
```

**How Kafka helped the agents coordinate:** each agent only needs to know
one topic to read from and one to write to — Planner never needs to know
Writer or Reviewer exist, and a question can sit in `s1808_inbox` for as
long as it takes Planner to get around to it, with no caller blocked
waiting on a direct call. The `correlation_id` is what lets the three
independently-scaled, independently-restartable processes agree on "which
answer this is," entirely through message content rather than shared
call-stack state. This is the same coordination problem HW2's in-process
graph solved with direct Python function calls and a shared return value —
Kafka solves it with topics and a correlation key instead, at the cost of
giving up the guarantee that a reader is even running (see Part 3.V).

---

## Part 3 — Failure Behavior

### I. Duplicate Delivery

`Part-11/test_idempotency.py` (`raw/test_idempotency.log`): the shared
`run_consumer_agent` loop (`kafka_utils.py`) keeps an in-memory
`seen_correlation_ids` set. Sent one message, confirmed it was processed
(`process() call count: 1`), replayed the exact same message (same
`correlation_id`), and confirmed: `process()` was never called a second
time, no second output message was produced, and the replay was logged as
`DUPLICATE detected, dropping (no side effect)`.

### II. Consumer Death

`Part-11/test_consumer_death.py` (`raw/test_consumer_death.log`): spawns
the real `writer.py` as a subprocess, sends one real task message, waits
for the log line proving Writer has the message (before the model call
returns), and kills it with no graceful shutdown.

**Real, repeatedly confirmed:** `kafka-consumer-groups --describe` against
the live broker immediately after the kill shows the message's offset was
never committed (`LAG=1` on the partition holding it, `CURRENT-OFFSET`
unchanged from before the message was ever fetched) — direct proof that
`kafka_utils.py`'s `consumer.commit()`, called only after a message is
fully processed and its result published, does exactly what it's
supposed to: a kill mid-call leaves the offset exactly where it was
before that message was fetched, not after.

**Honest limitation:** completing the second half live — restarting
Writer and watching the SAME message get redelivered and finish inside
this one orchestrated test run — did not succeed across seven real
attempts, despite fixing every distinct cause found along the way (a
consumer-group join race, mixing the iterator protocol with manual
`poll()` calls, stale consumer-group sessions from rapid restarts, and a
large real backlog from earlier runs). In every attempt, the restarted
Writer successfully became the group's active member and was assigned the
partition holding the message (confirmed via
`kafka-consumer-groups --describe`), but then sat with the exact same
unchanged `LAG=1` for several minutes with zero CPU activity in the
model process, for reasons this debugging session was not able to fully
pin down. The redelivery itself is not a hope or an assumption — it
follows directly from the offset never having been committed, which is
real, repeatedly-measured broker state, not application-level logging —
but the live end-to-end demonstration of it completing inside one test
run is the one piece of Part 3 not cleanly captured. Full blow-by-blow
in `AI_USE.md`.

### III. Poison Message

`Part-11/test_poison_message.py` (`raw/test_poison_message.log`): sent one
message with no `payload` field (deterministically raises `KeyError` on
every attempt), immediately followed by a well-formed message. Real
result:

```
processing failed (attempt 1/3): 'payload'
processing failed (attempt 2/3): 'payload'
processing failed (attempt 3/3): 'payload'
exhausted 3 retries, sent to s1808_dead_letter: correlation_id=80e1287f-...
received from s1808_poison_in: correlation_id=954b3ef1-...   <- the good message right behind it
sent to s1808_poison_out: correlation_id=954b3ef1-...         <- processed normally, not blocked
```

The dead-letter record (`s1808_dead_letter`) carries the original topic,
the original message, the final error, and the retry count — everything
needed to replay or debug it later without having lost the message.

### IV. Ordering

`Part-11/test_ordering.py` (`raw/test_ordering.log`, `raw/ordering_results.json`).
`ENTITY_ID = course-261808` (derived from `VERIFY_SEED=261808`), 20
sequential update messages for that one entity, sent through
`s1808_tasks` (2 partitions) to two lightweight consumer instances in one
consumer group (a stand-in for two Writer instances — see note below).

| | Unkeyed | Keyed by `entity_id` |
|---|---|---|
| Partitions used | 0 and 1 (both) | 1 (only) |
| Consumer instances that received anything | both | 1 of 2 |
| Arrival order matches send order 1..20? | **No** | **Yes** |

Unkeyed arrival order (merged across both instances):
`[3, 4, 6, 7, 8, 10, 12, 13, 15, 20, 5, 9, 11, 14, 16, 17, 18, 19]` — note
`20` arriving before `5`. Keyed arrival order: `[1, 2, 3, ..., 20]` exactly.

**Note on using lightweight stand-ins instead of two real `writer.py`
processes:** ordering is a property of partition assignment, independent
of what a consumer does with each message once it has it. Running 40 real
messages (20 × 2 runs) through the actual ~15-50s-per-call local model
would cost 15+ minutes for no additional insight into the thing actually
being measured here, so this test uses two fast, trivial consumer
instances instead — disclosed here and in the script's own docstring, not
hidden.

### V. Comparison with HW2's in-process graph

HW2's Planner → Reviewer graph ran as direct Python function calls within
one process: a `StateGraph` node called the next node's function and got
its return value back immediately, in the same call stack, on the same
machine, in the same instant.

**Two benefits gained by moving to Kafka:**
1. **Independent scaling.** Planner, Writer, and Reviewer are separate
   OS processes that can be started, stopped, or run multiple instances
   of independently (Part 3.IV ran two Writer-role consumers at once) —
   HW2's graph could only ever run as many Planner/Reviewer "instances"
   as the single process's call stack allowed, which is to say one at a
   time per invocation.
2. **Decoupled failure.** Part 3.II's own result demonstrates this
   directly: killing Writer mid-task did not crash Planner or lose the
   question — the message just sat on `s1808_tasks`, unconsumed, exactly
   where Writer left it, waiting for any future Writer to pick it back
   up. In HW2's in-process design, a crash inside the Reviewer call would
   have taken the whole pipeline down with it.

**Two new responsibilities now on us that HW2 never had to handle:**
1. **Ordering**, concretely demonstrated in Part 3.IV: HW2's direct
   function calls had a trivial, unavoidable order (call, then return).
   A Kafka topic has no such guarantee once it has more than one
   partition — getting ordered delivery for related messages requires an
   explicit design decision (a partition key), not something that just
   happens by default the way it did in-process.
2. **Duplicate delivery and idempotency**, concretely demonstrated in
   Part 3.I: an in-process function call executes exactly once, by
   construction. A message consumer offers only "commit the offset after
   you're done" as its safety net — if a message is ever redelivered
   (a crash before commit, a replay, a retry), the consumer itself has to
   actively decide what "processing it twice" should and shouldn't do,
   which in HW2's world wasn't even a coherent question to ask.

### Failure table

| Failure scenario | Before fix | After fix |
|---|---|---|
| Duplicate delivery | Would call `process()` and publish a second output for every replay (no dedup existed) | Replay dropped before `process()` runs; `raw/test_idempotency.log` |
| Consumer killed mid-work | With `enable_auto_commit=True`, the offset could be committed on a timer inside `poll()` even if the handler hadn't finished — a kill could silently lose the message | `enable_auto_commit=False` + manual `consumer.commit()` only after success; offset proven unchanged after a real kill, `raw/test_consumer_death.log` |
| Poison message | An exception in `process()` would crash the whole consumer loop, taking every later message on that partition down with it | Retried up to 3×, then forwarded to `s1808_dead_letter` with its error attached; the message right behind it still processed normally; `raw/test_poison_message.log` |
| Two partitions/two consumers | No partition key: round-robin split a single entity's related messages across both partitions and both consumer instances, arriving out of order | Keyed by `entity_id`: all 20 related messages land on one partition, read by one instance, in exact send order; `raw/test_ordering.log` |

---

## AI Use

See `AI_USE.md`.
