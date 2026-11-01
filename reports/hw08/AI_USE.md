# HW8 AI Use Statement

### 1. What I used an AI assistant for, and what I did myself

I used Claude Code to design and write the Kafka request/response worker
and FastAPI wrapper (Part 1), the three-agent pipeline (Part 2), and the
failure-mode harnesses (Part 3), and to set up the Kafka/Zookeeper/worker/
API Docker Compose stack. It ran everything against a real local Kafka
broker — no part of this homework is simulated or mocked.

What I did myself: decided the Course entity's required/optional field
split for `CREATE_ENTITY`, picked the real topic/partition layout, and
diagnosed three real operational failures by reading actual broker and
consumer-group state (`kafka-consumer-groups --describe`,
`kafka-console-consumer`, `docker logs`) rather than guessing — each one
below was confirmed before being "fixed", not assumed.

### 2. One AI-produced output that was wrong/unsuitable

Three, in order of how long each took to actually nail down:

**First:** my first Kafka client implementation (`api.py`'s
`_send_and_wait`) created a fresh consumer per HTTP request and attempted
to position it with `consumer.assign([...]) + consumer.seek_to_end()`
immediately before sending the request. This silently never advanced —
`homework_demo.py` and the API both reliably timed out waiting for
responses that the worker had genuinely already sent.

**Second:** after switching to a group-based `auto_offset_reset="latest"`
consumer with a single warm-up `poll()` call, it *still* silently never
advanced in some runs.

**Third, and the most expensive:** after containerizing the worker and
API, they could reach Kafka for the initial bootstrap but every
subsequent request failed with a real `ECONNREFUSED` — and, overlapping
with that, long stretches that looked like "the worker just isn't
processing" turned out to be `docker logs` showing nothing because
stdout was buffered, not because nothing had happened.

### 3. How I detected each problem

**First:** `kafka-consumer-groups --bootstrap-server ... --describe`
directly against the broker showed `LAG=1` on a message the worker never
logged receiving — the message was genuinely sitting unconsumed, not a
logging gap.

**Second:** a minimal isolated repro script (bypassing both `api.py` and
`homework_demo.py` entirely) proved `consumer.assignment()` was still an
empty `set()` immediately after one `poll(timeout_ms=3000)` call, and
only became non-empty after about 7 polls (~3.5s) in a tight loop —
measured directly, not inferred.

**Third:** `docker logs s1808-worker` showed the real traceback
(`kafka.errors.KafkaConnectionError: KafkaConnectionError: 111
ECONNREFUSED`) naming `localhost:9092` as the address the container tried
and failed to reach for its second request — which only makes sense once
you realize "localhost" inside that container means the container
itself. Separately, `kafka-consumer-groups --describe` showed the
consumer group's committed offset had advanced to match the log-end
offset even though `docker logs` showed no corresponding "received
request" line — proof the processing had happened and the log line was
just stuck in a buffer, not proof of a stall.

### 4. What I changed and why it works now

**First/second (group-join race):** replaced the single warm-up `poll()`
with a loop that polls repeatedly until `consumer.assignment()` is
actually non-empty, in `worker.py`, `api.py`, and `homework_demo.py`
alike, and switched from the `for msg in consumer:` iterator to an
explicit `consumer.poll()` loop in the client-side waiting code (mixing a
manual warm-up `poll()` with the iterator protocol was part of what made
the second failure mode non-obvious).

**Third (container networking + buffering):** `docker-compose.kafka.yml`
now declares two real Kafka listeners — `PLAINTEXT` (`s1808-kafka:29092`,
advertised to containers) and `PLAINTEXT_HOST` (`localhost:9092`,
advertised to the host) — so a container's *every* request, not just its
first, resolves to an address it can actually reach. Both Dockerfiles now
set `ENV PYTHONUNBUFFERED=1`, so `docker logs` reflects what the process
has actually done, not what's made it through an internal buffer yet.
Verified end to end afterward: `homework_demo.py` run from the host
against the fully containerized worker/API completed both round trips in
14-28ms, with the worker's own log and `docker logs` showing matching,
immediate receive/process/reply lines for every request.
