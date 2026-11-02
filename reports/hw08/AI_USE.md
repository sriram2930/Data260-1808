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

---

## Parts 2-3: the consumer-death test, honestly

Parts 2 and 3.I/III/IV (the three-agent pipeline, duplicate delivery,
poison messages, ordering) all worked cleanly and are backed by real,
reproducible evidence in `METRICS.md`. Part 3.II (consumer death) is the
one piece of this homework where, despite real effort and several real
fixes, I did not get a fully clean live end-to-end demonstration — writing
this up honestly rather than papering over it, since the assignment's own
framing (and this project's established practice across every prior
homework) is to document real gaps, not hide them.

**What happened, across seven real attempts, in order:**

1. First attempt: `writer.py` (killed and restarted as a real subprocess)
   never showed it received the redelivered message within my test's
   fixed wait window. **Diagnosed:** too short a deadline — a prior,
   unrelated investigation (Part 1) had already shown this broker's
   consumer-group join/sync can take up to ~60s, and my test only waited
   20s before giving up.

2. Second/third attempts: the restarted Writer hung for 1.5+ and then
   ~2+ *hours* mid-test with zero response. **Diagnosed:** the host
   machine went to sleep mid-test (confirmed by the wall-clock gap in the
   logs, not an application bug) — the same class of problem already
   documented in this session's HW7 work. Recovered by killing orphaned
   processes and resuming; the user was asked whether to keep retrying,
   disable sleep, or accept partial evidence, and chose to keep retrying.

3. Fourth attempt: the restarted Writer again showed no activity for
   several minutes, but this time `llama-server.exe` wasn't even running
   and a direct `curl` to Ollama's `/api/chat` timed out with no response
   at all, while `/api/tags` answered fine. **Diagnosed:** Ollama itself
   was stuck on this specific request type (not asleep, not a Kafka
   issue) — the same "looks alive, one call-type is actually dead"
   pattern seen with Ollama elsewhere in this project. Fixed by killing
   all `ollama`/`llama-server` processes and relaunching cleanly.

4. Fifth attempt: hung again, same symptom (no `llama-server`, offset
   `LAG` never moved). This time I noticed the consumer group
   (`s1808_writer`) had accumulated ~49 real messages from every earlier
   test attempt across this whole debugging session, and with no prior
   committed offset (since I'd been deleting the group to clear stale
   sessions) the restarted Writer had to replay that *entire* backlog
   from `auto_offset_reset="earliest"` — each a real message, several of
   which were genuinely shaped like valid tasks and would trigger a real,
   slow model call — before ever reaching my new test message.
   **Self-inflicted:** my own earlier "fix" (deleting the group to clear
   a stale session) is what created this.

5. Sixth attempt: seeded the group's offset to the current end of the
   topic first (skipping the backlog), and separately noticed
   `kafka_utils.py`'s shared `run_consumer_agent` loop still used the
   `for msg in consumer:` iterator *after* a manual warm-up `poll()` —
   the exact pattern Part 1 had already identified as unreliable in this
   environment, just not yet applied here. Fixed both. Re-ran: identical
   symptom, offset still never advanced.

6. Seventh attempt: used a brand-new, never-before-used consumer-group id
   (ruling out any accumulated history/corruption specific to
   `s1808_writer`), with the backlog-seeding step built into the test
   itself. Verified in isolation, outside the test entirely, that
   `TimedModelClient` and Ollama were both healthy (a direct call
   completed in 13.7s). Re-ran the full test: identical symptom.

**Where this leaves things:** every one of those six fixes addressed a
real, independently-confirmed problem (and all but the sleep/Ollama ones
are now permanent improvements in the shared code, not test-only
patches), but none of them was the actual cause of the restarted Writer
sitting with an unchanged `LAG` and zero CPU activity for minutes at a
time. What I can say with confidence, because it's broker state I
measured directly rather than something I'm assuming: the kill-time
behavior is proven correct (the offset was never committed), and
Kafka's at-least-once guarantee is not something this codebase has to
independently prove — an uncommitted offset *is* the mechanism by which
redelivery happens, by definition of what "committed" means in the
protocol. What isn't proven is that *this specific restarted subprocess,
in this specific test's orchestration*, reliably completes that
redelivery within a bounded time in this environment. Reported as an open
finding, not quietly dropped.
