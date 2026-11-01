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

*(filled in once Part 2 is built)*

---

## Part 3 — Failure Behavior

*(filled in once Part 3 is built)*

---

## AI Use

See `AI_USE.md`.
