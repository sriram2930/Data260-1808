"""One-off script assembling the HW8 Word report. Not part of the graded
deliverable, kept here only so the report can be regenerated.

Evidence is real screenshots (terminal-look pages built from real
captured Kafka/docker/model output, screenshotted with Playwright) plus
short, relevant code snippets. The one honestly-incomplete piece (Part
3.II's live redelivery demonstration) is presented as such, not hidden."""

import docx
from docx.shared import Inches, Pt

doc = docx.Document()
SCREENSHOTS = "screenshots/"

doc.add_heading("DATA 260 Homework 8 Report", level=0)
doc.add_paragraph("Sreeram Achutuni")
doc.add_paragraph("SJSU ID: 019151808")
doc.add_paragraph("GitHub repository: https://github.com/sriram2930/Data260-1808")

h1 = lambda t: doc.add_heading(t, level=1)  # noqa: E731
h2 = lambda t: doc.add_heading(t, level=2)  # noqa: E731
p = lambda t: doc.add_paragraph(t)  # noqa: E731


def code_block(text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)


def shot(filename, width_in=6.3):
    doc.add_picture(SCREENSHOTS + filename, width=Inches(width_in))


def note(text):
    para = doc.add_paragraph()
    run = para.add_run("Note: " + text)
    run.italic = True


def table(rows):
    t = doc.add_table(rows=0, cols=len(rows[0]))
    t.style = "Table Grid"
    for row_vals in rows:
        row = t.add_row()
        for i, v in enumerate(row_vals):
            row.cells[i].text = str(v)


h1("Section 0: Config values")
table([
    ("SID4", "1808"),
    ("PORT_BASE", "8008"),
    ("PREFIX", "s1808"),
    ("SEED", "1808"),
    ("VERIFY_SEED", "261808"),
    ("DOMAIN_ID", "0, Campus course catalogue and enrolment"),
    ("Hardware", "Intel Core i7-11390H, 16GB RAM, integrated Iris Xe graphics (no dedicated GPU)"),
    ("Local model", "qwen2.5:1.5b-instruct via Ollama (Part 2's Planner/Writer/Reviewer)"),
    ("Repo", "https://github.com/sriram2930/Data260-1808"),
    ("Collaborators", "Sbnikitha and supriyaselvanganesan have repo access"),
    ("Commit tagged as hw8", "b9bc4af690a5fb105794a01bf541404132aa41d2"),
])

# ============================================================= PART 1
h1("Part 1: Backend Service Request/Response over Kafka")
p(
    "Primary domain entity: Course. CREATE_ENTITY/GET_ENTITY map to CREATE_COURSE/GET_COURSE, "
    "entity_id is course_id. Topics: s1808_entity_requests, s1808_entity_responses. Store: "
    "a plain Python dict inside the worker (Part-10/entity_store.py), per the assignment."
)

h2("Message schema")
code_block(
    'request:  {"correlation_id": "...", "reply_to": "s1808_entity_responses",\n'
    '           "operation": "CREATE_ENTITY" | "GET_ENTITY", "data": {...}}\n'
    'response: {"correlation_id": "...", "success": true|false, ...}'
)

h2("Docker containers running: Kafka, worker, and FastAPI services")
shot("p1_docker_ps.png")
shot("p1_topics_created.png")

h2("CREATE_ENTITY and GET_ENTITY execution (via the FastAPI wrapper)")
shot("p1_crud_evidence.png")

h2("Kafka message-flow logs: worker (receive -> process -> reply)")
shot("p1_worker_log.png")

h2("Kafka message-flow logs: FastAPI (send -> receive)")
shot("p1_api_log.png")

h2("Full sequence: homework_demo.py -- CREATE_ENTITY -> GET_ENTITY, correlation_id preserved")
shot("p1_homework_demo.png")

h2("Error cases: missing field, unknown operation, not-found")
shot("p1_error_cases.png")

h2("Code: worker's CREATE_ENTITY/GET_ENTITY handling")
code_block(
    'def handle_request(store, operation, data):\n'
    '    if operation == "CREATE_ENTITY":\n'
    '        problem = validate_course_data(data)\n'
    '        if problem:\n'
    '            return {"success": False, "error": problem}\n'
    '        record = store.create(data)\n'
    '        return {"success": True, "entity_id": record["course_id"], "message": "Entity created"}\n'
    '    if operation == "GET_ENTITY":\n'
    '        entity_id = data.get("entity_id")\n'
    '        record = store.get(entity_id)\n'
    '        if record is None:\n'
    '            return {"success": False, "error": "Entity not found"}\n'
    '        return {"success": True, "entity": record}\n'
    '    return {"success": False, "error": "Unknown operation"}'
)

note(
    "three real operational issues were found and fixed while building this: a consumer-group "
    "join race (a single poll() does not reliably complete the rebalance -- measured at ~7 "
    "polls/~3.5s), a Docker single-listener trap (works for a container's first bootstrap "
    "request, then ECONNREFUSED on every request after, since the broker advertises \"localhost\" "
    "which means the container itself), and unflushed/buffered container stdout masking real, "
    "fast processing as apparent stalls. Full story in AI_USE.md."
)

# ============================================================= PART 2
h1("Part 2: Three-Agent Kafka Pipeline")
p(
    "Planner, Writer, and Reviewer run as three independent processes, each in its own "
    "terminal, coordinating only through Kafka (s1808_inbox -> s1808_tasks -> s1808_drafts -> "
    "s1808_final). No process calls another directly."
)

h2("Code: the shared agent-loop shape (planner/writer/reviewer all use this)")
code_block(
    'def run_consumer_agent(log, in_topic, out_topic, group_id, process):\n'
    '    consumer = make_consumer(in_topic, group_id, enable_auto_commit=False)\n'
    '    producer = make_producer()\n'
    '    while True:\n'
    '        batches = consumer.poll(timeout_ms=500)\n'
    '        for msg in [...records from batches...]:\n'
    '            message = msg.value\n'
    '            result = process(message)  # real model call (planner/writer/reviewer)\n'
    '            result.setdefault("correlation_id", message["correlation_id"])\n'
    '            producer.send(out_topic, value=result)\n'
    '            producer.flush()\n'
    '            consumer.commit()  # only after success -- see Part 3.II'
)

h2("One complete message journey: s1808_inbox -> s1808_final")
shot("p2_journey.png")

h2("How Kafka helped the agents coordinate")
p(
    "Each agent only needs to know one topic to read from and one to write to -- Planner never "
    "needs to know Writer or Reviewer exist. The correlation_id is what lets three "
    "independently-scaled, independently-restartable processes agree on which answer belongs to "
    "which question, entirely through message content rather than shared call-stack state -- the "
    "same coordination problem HW2's in-process graph solved with direct function calls, solved "
    "here with topics and a correlation key instead."
)

# ============================================================= PART 3
h1("Part 3: Failure Behavior")

h2("I. Duplicate Delivery")
p("Replayed a message with the same correlation_id. The shared agent loop's in-memory "
  "seen_correlation_ids set drops the replay before process() runs -- no second model call, "
  "no second output message.")
shot("p3_idempotency.png")

h2("Code: idempotency + manual offset commit")
code_block(
    'seen_correlation_ids = set()\n'
    '...\n'
    'if correlation_id in seen_correlation_ids:\n'
    '    log.info("DUPLICATE detected, dropping (no side effect)")\n'
    '    consumer.commit()\n'
    '    continue\n'
    '...\n'
    '# only after process() succeeds AND the result is published:\n'
    'seen_correlation_ids.add(correlation_id)\n'
    'producer.send(out_topic, value=result)\n'
    'producer.flush()\n'
    'consumer.commit()'
)

h2("II. Consumer Death")
p(
    "Spawned the real writer.py as a subprocess, sent one real task message, killed it the "
    "instant its log showed it had received the message (before the model call returns)."
)
shot("p3_consumer_death.png")
note(
    "the kill-time behavior is proven with real, repeated broker evidence: "
    "kafka-consumer-groups --describe shows the message's offset was never committed (LAG "
    "unchanged from before the message was fetched), confirming consumer.commit() -- called "
    "only after success -- does exactly what it should. Completing the live second half "
    "(restart Writer, watch the SAME message get redelivered and finish inside this one "
    "orchestrated test run) did not succeed across seven real attempts, despite fixing six "
    "distinct, independently-confirmed real problems along the way (documented in full in "
    "AI_USE.md). Redelivery itself is not a hope -- it follows directly from the offset never "
    "having been committed, which IS the mechanism by which Kafka's at-least-once guarantee "
    "works -- but the live end-to-end demonstration completing inside this one test is the "
    "piece not cleanly captured. Reported as an open finding, not hidden."
)

h2("III. Poison Message")
p(
    "Sent one message missing a required field (deterministically fails every retry), "
    "immediately followed by a well-formed message."
)
shot("p3_poison.png")

h2("Code: bounded retries + dead-letter")
code_block(
    'for attempt in range(1, MAX_RETRIES + 1):\n'
    '    try:\n'
    '        result = process(message)\n'
    '        break\n'
    '    except Exception as exc:\n'
    '        last_error = exc\n'
    '        if attempt < MAX_RETRIES:\n'
    '            time.sleep(RETRY_BACKOFF_S)\n'
    'if last_error is not None:\n'
    '    producer.send(DEAD_LETTER_TOPIC, value={"correlation_id": correlation_id,\n'
    '        "original_message": message, "error": str(last_error), "retries": MAX_RETRIES})\n'
    '    consumer.commit()  # move past it -- do not block the partition forever'
)

h2("IV. Ordering")
p(
    "20 sequential messages for ENTITY_ID = course-261808 (derived from VERIFY_SEED=261808), "
    "sent through s1808_tasks (2 partitions) to two consumer instances in one group."
)
shot("p3_ordering.png")

h2("Code: partition key")
code_block(
    'key = ENTITY_ID.encode("utf-8") if use_key else None\n'
    'producer.send(TASKS_TOPIC, key=key, value=message)'
)

h2("V. Comparison with HW2's in-process graph")
table([
    ("Two benefits gained by Kafka", "Two new responsibilities now on us"),
    ("Independent scaling: Planner/Writer/Reviewer run and restart independently (Part 3.IV ran two Writer-role consumers at once)",
     "Ordering: a Kafka topic with >1 partition has no default order across related messages -- requires an explicit partition key (Part 3.IV)"),
    ("Decoupled failure: killing Writer mid-task did not crash Planner or lose the question (Part 3.II)",
     "Duplicate delivery / idempotency: a redelivered message is a real possibility a consumer must actively handle, unlike an in-process call that executes exactly once by construction (Part 3.I)"),
])

h2("Failure table")
table([
    ("Failure scenario", "Before fix", "After fix"),
    ("Duplicate delivery", "Would call process() and publish a second output for every replay", "Replay dropped before process() runs"),
    ("Consumer killed mid-work", "Auto-commit on a timer could lose a message not yet finished", "Manual commit only after success; offset proven unchanged after a real kill"),
    ("Poison message", "An exception would crash the whole consumer loop", "Retried 3x, then dead-lettered; the message behind it still processed"),
    ("Two partitions/two consumers", "Unkeyed: one entity's messages split across partitions, arrived out of order", "Keyed by entity_id: confined to one partition, exact send order"),
])

# ============================================================= AI_USE
h1("AI Use Statement")

h2("1. What I used an AI assistant for, and what I did myself")
p(
    "I used Claude Code to design and write the Kafka request/response worker and FastAPI "
    "wrapper (Part 1), the three-agent pipeline (Part 2), and the failure-mode harnesses "
    "(Part 3), and to set up the Kafka/Zookeeper/worker/API Docker Compose stack. It ran "
    "everything against a real local Kafka broker -- no part of this homework is simulated."
)
p(
    "What I did myself: decided the Course entity's required/optional field split, picked the "
    "real topic/partition layout, and diagnosed every operational failure below by reading "
    "actual broker and consumer-group state (kafka-consumer-groups --describe, docker logs) "
    "rather than guessing."
)

h2("2. One AI-produced output that was wrong/unsuitable")
p(
    "Several, compounding. The most expensive: Part 3.II's consumer-death test hit six "
    "distinct real problems across seven attempts -- a too-short wait deadline, two separate "
    "host-sleep interruptions mid-test, a stuck Ollama request, a self-inflicted consumer-group "
    "backlog (deleting a group to clear a stale session reset it to replay the entire topic "
    "history), and an iterator/poll mixing bug already found in Part 1 but not yet applied to "
    "Part 2/3's shared code."
)

h2("3. How I detected the problem")
p(
    "kafka-consumer-groups --describe against the live broker, not application logs, is what "
    "actually proved each state: LAG remaining unchanged after a kill (offset not committed), "
    "a consumer successfully joining a group yet LAG never decreasing (the still-unexplained "
    "part), and a direct, isolated test of the model client (13.7s, succeeded) that ruled out "
    "the model itself as the cause of the final stuck state."
)

h2("4. What I changed and why it works now")
p(
    "Fixed, and now permanent in the shared code: manual offset commit (enable_auto_commit=False, "
    "committed only after success) replacing the earlier auto-commit design; an explicit "
    "consumer.poll() loop instead of the `for msg in consumer:` iterator; and a real request "
    "timeout on the model client (TimedModelClient) so a stuck Ollama call fails bounded instead "
    "of hanging forever. What's still honestly unresolved: a restarted Writer subprocess, in "
    "this test's specific orchestration, did not reliably complete the redelivery-and-finish "
    "cycle within a bounded time in this environment, despite the offset-not-committed half "
    "being proven correct every single time. Documented in full in AI_USE.md rather than "
    "silently reworked into a result that looks cleaner than what actually happened."
)

out_path = "Achutuni_HW8.docx"
doc.save(out_path)
print("wrote full draft:", out_path)
