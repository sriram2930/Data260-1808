"""
Part-11/test_consumer_death.py -- DATA-260 HW8, Part 3.II (consumer death)

Spawns the REAL writer.py as a subprocess (not a stand-in -- this test is
specifically about Writer's own lifecycle), sends one real task message
directly to s1808_tasks, waits until the log shows Writer has started
processing it (i.e. the model call is in flight), then kills the
subprocess mid-call with no graceful shutdown.

Shows, using kafka-consumer-groups --describe against the real broker (not
just application-level logging), that the message's offset was NOT
committed -- kafka_utils.py only calls consumer.commit() after a message
is fully processed and its result published, so a kill mid-call leaves
the offset exactly where it was before this message was fetched. Then
restarts Writer and shows the same message gets redelivered (because the
offset never advanced) and this time completes, with the offset finally
advancing only after that success.

Run (Kafka must already be up; the real planner.py/reviewer.py should
already be running so the eventual output flows to completion, but
neither is required for this test's actual assertions):
    python test_consumer_death.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import uuid

from kafka_config import DRAFTS_TOPIC, TASKS_TOPIC
from kafka_utils import make_consumer, make_producer

logging.basicConfig(level=logging.INFO, format="%(asctime)s TEST %(message)s", stream=sys.stdout)
logging.getLogger("kafka").setLevel(logging.WARNING)
log = logging.getLogger("test_consumer_death")

# A fresh, never-before-used group id for this run, not the real
# "s1808_writer" group the live Part 2 pipeline uses -- repeatedly
# creating/deleting/reseeding that exact group id across many earlier
# test attempts in this same session left it in a state where a restarted
# consumer could be assigned its partitions but never actually receive a
# fetched message, for minutes at a time, with no error and no CPU
# activity. A brand-new group id with no history does not reproduce this.
# See AI_USE.md for the full story.
GROUP_ID = f"s1808_writer_deathtest_{uuid.uuid4().hex[:8]}"
_WRITER_ENV = {**os.environ, "WRITER_GROUP_ID": GROUP_ID}


def _group_offset(group_id: str, topic: str) -> dict:
    out = subprocess.run(
        ["docker", "exec", "s1808-kafka", "kafka-consumer-groups",
         "--bootstrap-server", "localhost:9092", "--describe", "--group", group_id],
        capture_output=True, text=True, check=False,
    )
    return {"stdout": out.stdout.strip(), "stderr": out.stderr.strip()}


def main() -> None:
    # Seed GROUP_ID's offset to the current end of s1808_tasks before
    # anything is sent: a real deployment's consumer group has a
    # committed position from its own prior runs, but a fresh group id
    # (deliberately used here, see the comment above) has none and
    # defaults to "earliest" -- without this, attempt 1 would have to
    # chew through this topic's entire real history (accumulated from
    # every earlier Part 2/3 run, each a real model call) before it ever
    # reached the one message this test actually cares about.
    seed_consumer = make_consumer(TASKS_TOPIC, GROUP_ID, auto_offset_reset="latest")
    seed_consumer.commit()
    seed_consumer.close()
    log.info("seeded %s's offset to latest on %s (skipping prior backlog)", GROUP_ID, TASKS_TOPIC)

    producer = make_producer()
    drafts_consumer = make_consumer(DRAFTS_TOPIC, f"s1808_drafts_watch_{uuid.uuid4().hex}", auto_offset_reset="latest")

    correlation_id = str(uuid.uuid4())
    message = {
        "correlation_id": correlation_id,
        "question": "Explain what a deadlock is, in two sentences.",
        "plan": "- define deadlock\n- give one real-world analogy",
    }

    log.info("=== spawning writer.py (attempt 1), group_id=%s ===", GROUP_ID)
    proc1 = subprocess.Popen(
        [sys.executable, "-u", "writer.py"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=_WRITER_ENV,
    )

    # Wait for Writer to print "ready", then send the message, then wait
    # for it to print "received" (i.e. it has the message and is about to
    # call the model) before killing it.
    started_processing = False
    lines_seen: list[str] = []
    deadline = time.monotonic() + 90  # "ready" alone has taken up to ~60s in testing
    sent = False
    while time.monotonic() < deadline:
        line = proc1.stdout.readline()
        if line:
            lines_seen.append(line.rstrip())
            log.info("[writer attempt 1] %s", line.rstrip())
        if not sent and ("ready and listening" in line):
            time.sleep(1)
            log.info("SEND -> %s: correlation_id=%s", TASKS_TOPIC, correlation_id)
            producer.send(TASKS_TOPIC, value=message)
            producer.flush()
            sent = True
        if sent and "received from" in line:
            started_processing = True
            break

    assert started_processing, "writer.py never showed it received the message before the deadline"

    log.info("=== killing writer.py NOW, mid-processing (before the model call returns) ===")
    proc1.kill()
    proc1.wait(timeout=5)
    log.info("writer.py (attempt 1) killed. Checking consumer group offset...")

    time.sleep(1)
    offset_after_kill = _group_offset(GROUP_ID, TASKS_TOPIC)
    log.info("consumer group state after kill:\n%s", offset_after_kill["stdout"])

    no_draft_yet = None
    batches = drafts_consumer.poll(timeout_ms=2000)
    for records in batches.values():
        for r in records:
            if r.value.get("correlation_id") == correlation_id:
                no_draft_yet = r.value
    log.info("draft present after kill (expected: None, message was never fully processed): %s", no_draft_yet)
    assert no_draft_yet is None, "a draft was produced despite killing the writer mid-processing"

    log.info("=== restarting writer.py (attempt 2) ===")
    proc2 = subprocess.Popen(
        [sys.executable, "-u", "writer.py"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=_WRITER_ENV,
    )

    redelivered = False
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        line = proc2.stdout.readline()
        if line:
            log.info("[writer attempt 2] %s", line.rstrip())
            if correlation_id in line and "received from" in line:
                redelivered = True
            if correlation_id in line and "sent to" in line:
                break

    assert redelivered, "the message was not redelivered to the restarted writer -- offset must have advanced on the kill"

    final_draft = None
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and final_draft is None:
        for records in drafts_consumer.poll(timeout_ms=500).values():
            for r in records:
                if r.value.get("correlation_id") == correlation_id:
                    final_draft = r.value

    log.info("final draft after restart: %s", json.dumps(final_draft, indent=2) if final_draft else None)
    assert final_draft is not None, "the restarted writer never completed the redelivered message"

    offset_after_success = _group_offset(GROUP_ID, TASKS_TOPIC)
    log.info("consumer group state after success:\n%s", offset_after_success["stdout"])

    proc2.kill()
    log.info("PASS: killed mid-processing -> offset NOT committed -> redelivered on restart -> completed -> offset committed only now.")


if __name__ == "__main__":
    main()
