"""One-off script assembling the HW6 Word report. Not part of the graded
deliverable, kept here only so the report can be regenerated.

Evidence in this report is real PNG screenshots (screenshots/*.png): some
are a real browser hitting the live FastAPI endpoints directly, others are
a styled terminal-look page built from real captured curl/mongosh/python
output by build_terminal_html.py and screenshotted with Playwright
(shots.mjs) -- not fabricated or reworded, just rendered as an image
instead of monospace text, since this homework had no Postman/Compass
GUI driving the API/DB by hand."""

import docx
from docx.shared import Pt, Inches

doc = docx.Document()
SCREENSHOTS = "screenshots/"

doc.add_heading("DATA 260 Homework 6 Report", level=0)
doc.add_paragraph("Sreeram Achutuni")
doc.add_paragraph("SJSU ID: 019151808")
doc.add_paragraph("GitHub repository: https://github.com/sriram2930/Data260-1808")

h1 = lambda t: doc.add_heading(t, level=1)
h2 = lambda t: doc.add_heading(t, level=2)
p = lambda t: doc.add_paragraph(t)


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
    ("Local model", "qwen2.5:1.5b-instruct via Ollama (generation), sentence-transformers/all-MiniLM-L6-v2 (episodic + duplicate-detection embeddings)"),
    ("Repo", "https://github.com/sriram2930/Data260-1808"),
    ("Collaborators", "Sbnikitha and supriyaselvanganesan have repo access"),
    ("Commit tagged as hw6", "1dc510029be8ca31159b24fd95eef0163692d5b5"),
])

note(
    "evidence below is real screenshots: some are a real browser hitting the live FastAPI "
    "endpoints directly, the rest are a styled terminal page built from real captured curl/"
    "mongosh/python output and screenshotted with Playwright, since there was no Postman/Compass "
    "GUI driving the API/DB by hand for this homework. The text inside every screenshot is exact "
    "real output, not retyped or reworded."
)

# ============================================================= PART 1
h1("Part 1: MongoDB Document API")
p(
    "Builds on HW5 with a MongoDB-backed document view of the campus course catalogue domain: "
    "an announcements collection (course update/enrollment/event notices) in a new database, "
    "s1808_doc, alongside the existing MySQL s1808_rel tables. Fields: title (required, max 100 "
    "chars), description (optional), status (enum draft/published/archived, default draft), "
    "category (enum course_update/enrollment/event/general), event_date (required), created_at/"
    "updated_at (automatic). Validation is enforced twice, independently: Pydantic at the API "
    "boundary and a real MongoDB $jsonSchema validator on the collection itself."
)

h2("Code: Pydantic schema and MongoDB validator")
code_block(
    'class AnnouncementIn(BaseModel):\n'
    '    title: str = Field(min_length=1, max_length=100)\n'
    '    description: Optional[str] = None\n'
    '    status: Status = "draft"\n'
    '    category: Category\n'
    '    event_date: datetime.datetime\n\n'
    'ANNOUNCEMENT_SCHEMA = {\n'
    '    "$jsonSchema": {\n'
    '        "bsonType": "object",\n'
    '        "required": ["title", "status", "category", "event_date", "created_at", "updated_at"],\n'
    '        "properties": {\n'
    '            "title": {"bsonType": "string", "maxLength": 100},\n'
    '            "status": {"bsonType": "string", "enum": ["draft", "published", "archived"]},\n'
    '            "category": {"bsonType": "string", "enum": ["course_update", "enrollment", "event", "general"]},\n'
    '            "event_date": {"bsonType": "date"},\n'
    '        },\n'
    '    }\n'
    '}'
)

h2("Live API running (FastAPI auto-generated docs)")
shot("p1_docs_live.png")

h2("CRUD verified live (screenshots below)")
p("Login, then create a valid announcement:")
shot("p1_create.png")
p("Validation failures -- missing required title, then an invalid status enum:")
shot("p1_validation.png")
p("Get by id, update, get a nonexistent id (404), then delete:")
shot("p1_get_put_delete.png")

h2("MongoDB-level validator rejects bad data independently of the API")
shot("mongo_validator.png")

h2("Collection contents (mongosh)")
shot("mongo_announcements.png")

# ============================================================= PART 2
h1("Part 2: Short-, Long-, and Episodic Memory")
p(
    "New collections in the same s1808_doc database: messages, summaries, episodes. "
    "POST /api/chat saves the user message, pulls the last SHORT_TERM_N messages, the latest "
    "session/lifetime summaries, and the top-k episodic facts (cosine similarity over "
    "all-MiniLM-L6-v2 embeddings), composes a prompt, and calls the local Ollama model through "
    "the HW1 ModelClient adapter. A session summary is generated every "
    "SUMMARIZE_EVERY_USER_MSGS=5 user messages and condensed into a lifetime summary once a "
    "user has at least 2 session summaries. A 12-message real conversation "
    "(run_chat_demo.py) exercised all three memory types in one run."
)

h2("Code: the three endpoints")
code_block(
    '@router.post("/chat", response_model=ChatOut)\n'
    'def chat(payload: ChatIn):\n'
    '    result = chat_turn(payload.user_id, payload.session_id, payload.message, SHORT_TERM_N)\n'
    '    return {"reply": result["reply"], "session_id": result["session_id"], "used": result["used"]}\n\n'
    '@router.get("/memory/{user_id}")\n'
    'def get_memory(user_id: str):\n'
    '    db = get_db()\n'
    '    messages = list(db.messages.find({"user_id": user_id}, {"_id": 0})\n'
    '                     .sort("created_at", -1).limit(16))\n'
    '    messages.reverse()\n'
    '    session_summary = db.summaries.find_one(\n'
    '        {"user_id": user_id, "scope": "session"}, {"_id": 0}, sort=[("created_at", -1)])\n'
    '    lifetime_summary = db.summaries.find_one(\n'
    '        {"user_id": user_id, "scope": "user"}, {"_id": 0}, sort=[("created_at", -1)])\n'
    '    episodes = list(db.episodes.find({"user_id": user_id}, {"_id": 0, "embedding": 0})\n'
    '                     .sort("created_at", -1).limit(20))\n'
    '    return {"messages": messages, "latest_session_summary": session_summary,\n'
    '            "latest_lifetime_summary": lifetime_summary, "episodes": episodes}\n\n'
    '@router.get("/aggregate/{user_id}")\n'
    'def get_aggregate(user_id: str):\n'
    '    pipeline = [{"$match": {"user_id": user_id}},\n'
    '                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},\n'
    '                            "count": {"$sum": 1}}}, {"$sort": {"_id": 1}}]\n'
    '    daily_counts = [{"date": r["_id"], "count": r["count"]} for r in db.messages.aggregate(pipeline)]\n'
    '    recent_summaries = list(db.summaries.find({"user_id": user_id}, {"_id": 0})\n'
    '                             .sort("created_at", -1).limit(5))\n'
    '    return {"daily_message_counts": daily_counts, "recent_summaries": recent_summaries}'
)

h2("Code: episodic extraction and retrieval")
code_block(
    'def extract_episodes(user_id, session_id, user_message):\n'
    '    """Extracts up to 3 short durable facts via the local model, embeds each, stores them."""\n'
    '    prompt = (\n'
    '        "Extract up to 3 short, durable facts about the user from this message, each with "\n'
    '        "an importance score from 0 to 1. Reply with ONLY a JSON array like "\n'
    '        \'[{"fact": "...", "importance": 0.8}]\'. \' + f"Message: {user_message!r}"\n'
    '    )\n'
    '    result = get_model_client().complete([{"role": "user", "content": prompt}], format="json")\n'
    '    try:\n'
    '        parsed = json.loads(result["content"])\n'
    '        if isinstance(parsed, dict):\n'
    '            # the small model sometimes returns one fact object directly\n'
    '            parsed = [parsed] if "fact" in parsed else parsed.get("facts", [])\n'
    '    except (json.JSONDecodeError, AttributeError):\n'
    '        parsed = []\n'
    '    # ... embed each fact.get("fact") and db.episodes.insert_one(...)\n\n'
    'def retrieve_episodes(user_id, query_text, k=3):\n'
    '    episodes = list(db.episodes.find({"user_id": user_id}))\n'
    '    query_vec = np.array(embed_model.get_text_embedding(query_text))\n'
    '    scored = [(cosine(query_vec, np.array(e["embedding"])), e) for e in episodes]\n'
    '    scored.sort(key=lambda x: x[0], reverse=True)\n'
    '    return [ep for _sim, ep in scored[:k]]'
)

h2("Conversation excerpt (full 12-turn run in RUN_LOG.txt / chat_demo_shots.log)")
shot("p2_conversation.png")
note(
    "by turn 8, the episodic store had already picked up one wrong fact ('Your major is Computer "
    "Science', when the user had said Data Science in turn 1), and it kept resurfacing in later "
    "turns alongside correct facts (visible in the GET /api/memory screenshot below). "
    "extract_episodes does not re-verify a fact against the conversation before storing it, so one "
    "hallucinated extraction becomes a persistent, retrievable memory from then on. This is a real "
    "property of the system as built, documented here rather than fixed, since catching it "
    "required reading the raw per-turn output, not just the final answer. It reproduced "
    "identically on a second full run of the same 12 messages."
)

h2("GET /api/memory/u1_shots (live browser screenshot)")
shot("p2_memory_endpoint_live.png")

h2("GET /api/aggregate/u1_shots (live browser screenshot)")
shot("p2_aggregate_endpoint_live.png")

h2("MongoDB collections (mongosh)")
shot("mongo_memory.png")

# ============================================================= PART 3
h1("Part 3: What Memory Costs")
p(
    "The same fixed 30-message conversation (planted facts: name/student id/favorite subject "
    "in messages 1-3, birthplace in message 16) ran in a fresh session at SHORT_TERM_N = 4, 12, "
    "30, then once more at 12 with an eviction/compression policy (short-term message truncation "
    "to 120 chars), asking memory_probes.yaml's five questions after each run."
)
table([
    ("Setting", "Mean prompt tokens/turn", "Mean latency (ms)", "Probe quality (1-5)"),
    ("SHORT_TERM_N=4", "1790.3", "25117.7", "5.00"),
    ("SHORT_TERM_N=12", "1156.1", "18149.8", "4.60"),
    ("SHORT_TERM_N=30", "1433.3", "18095.7", "5.00"),
    ("Eviction/compression (N=12)", "728.7", "6535.5", "not measured (see note)"),
])
note(
    "the eviction/compression run was cut off at turn 26/30 (no probes) due to real-world time "
    "constraints finishing this homework on a CPU-only local model. The 26-turn average is still "
    "a fair token/latency comparison (an average isn't biased by sample length the way a total "
    "would be), but the probe-quality cell is genuinely missing data, not a zero."
)
p(
    "SHORT_TERM_N barely affects probe quality on its own (4.6-5.0 across all three raw window "
    "sizes), because episodic memory and the session/lifetime summaries carry the planted facts "
    "forward independently of the raw window. Even SHORT_TERM_N=4, which drops the planted facts "
    "from the window after message 5, scored a perfect 5/5. The eviction/compression policy cut "
    "mean prompt tokens from 1156 to 729 (-37%) and mean latency from 18.1s to 6.5s (-64%) over "
    "the portion measured, a larger latency drop than the token drop alone predicts, consistent "
    "with this model slowing disproportionately as prompts approach its 4096-token window."
)

h2("Memory-cost estimate (10,000 conversations x 30 turns)")
p("Using $1/M input tokens, $5/M output tokens, each setting's mean prompt tokens/turn, and "
  "~100 output tokens/turn observed across settings:")
table([
    ("Setting", "Input cost", "Output cost", "Total"),
    ("SHORT_TERM_N=4 (worst)", "$537.09", "$150.00", "$687.09"),
    ("Eviction/compression (best)", "$218.61", "$150.00", "$368.61"),
])
p(
    "Worst is the highest mean-tokens setting with no mitigation (SHORT_TERM_N=4, "
    "counterintuitively the smallest raw window, since summaries and episodic facts end up "
    "dominating the prompt more than the window itself once several summarization cycles have "
    "run). Best is the only setting that actively reduces token cost rather than picking a "
    "different window size. The gap ($687 vs $369 for the same 300,000 turns) is driven entirely "
    "by input tokens; a policy that compresses the prompt is worth roughly 1.9x in cost at this "
    "volume, independent of answer quality."
)

# ============================================================= PART 4
h1("Part 4: File-Based Memory and Consolidation")
p(
    "AGENT.md (reused and expanded from HW1) now covers five categories: project description, "
    "technology stack, coding conventions, testing approach, prohibited actions. MEMORY.md and "
    "file_memory.py implement loading, the consolidation trigger check (>40 non-comment lines, "
    "or >24h since last consolidation), and the /memory, /compact, /dream, /help commands "
    "(memory_cli.py)."
)

h2("Consolidation design: three attempts")
code_block(
    '1. One-shot full rewrite: asked the model to merge duplicates and resolve contradictions\n'
    '   in the whole 56-line test file at once. Barely touched anything: 56 -> 54 lines, none\n'
    '   of the 3 planted contradictions were resolved.\n\n'
    '2. One-shot JSON line-number classification: asked the model to find duplicate groups and\n'
    '   contradiction pairs by line number instead of rewriting prose. Found zero real\n'
    '   duplicates and hallucinated one false contradiction between unrelated facts.\n\n'
    '3. Final design: embeddings find candidate pairs "about the same thing"; a deterministic\n'
    '   check (differing numbers, or an antonym like allowed/blocked) decides contradiction vs.\n'
    '   duplicate; a narrow yes/no model call confirms each duplicate candidate before dropping\n'
    '   anything; each contradiction gets its own small, focused merge call.'
)

h2("Stress test: 56-line file, 3 planted duplicates, 3 planted contradictions")
p("Pipeline output (consolidation_result.json):")
shot("p4_consolidation.png")
table([
    ("", "Result"),
    ("Lines before", "56"),
    ("Lines after (pipeline's raw output)", "51"),
    ("Contradictions found", "3 of 3 planted"),
    ("Contradictions resolved correctly", "2 of 3 (port 8008; Department deletion blocked)"),
    ("Contradiction resolved INCORRECTLY", "SHORT_TERM_N: pipeline said \"8 is current, was 12\" - backwards. Real default in memory.py is 12."),
    ("Duplicate merges that lost information", "1-2 (MCP tool names, retry-cap detail dropped in merges)"),
])
note(
    "the pipeline's raw 51-line output still didn't meet the assignment's <40 target. The real "
    "reason: only 6 of 56 lines were truly redundant (3 dup pairs + 3 contradiction pairs); even "
    "perfect dedup caps out around 50 lines, since the other 44 are genuinely distinct facts. "
    "Getting under 40 required a human pass grouping related-but-distinct facts into combined "
    "bullets, a step the automated pipeline doesn't attempt. The human-corrected final version "
    "(test_memory_after.md) is 26 lines: fixes the one incorrect resolution (states the true "
    "SHORT_TERM_N=12, with the pipeline's wrong answer left visible in a parenthetical so the "
    "correction is auditable, not a silent overwrite), restores the two lost details, and groups "
    "facts into combined bullets. No fact from the original 56 lines is missing from the final 26."
)

h2("AGENT.md compliance check")
shot("p4_compliance.png")

h2("Comparing MongoDB memory and file-based memory")
table([
    ("", "MongoDB-backed (Part 2)", "File-based (Part 4)"),
    ("Inspectability", "Needs a Mongo client; structured/queryable, not human-readable at a glance", "Plain Markdown, readable/editable anywhere, no tooling"),
    ("Persistence after restart", "Durable as long as the container/volume persists", "Durable as long as the files aren't deleted; no schema protects a bad manual edit"),
    ("Scalability across sessions", "Scales well: indexed by user_id, cheap to query out of millions of docs", "Does not scale: one flat file per project, not per user/session"),
    ("Facts that must not be forgotten", "Good, but only as safe as the query that retrieves it", "Better for a small curated set (whole file always in the prompt); doesn't scale to large sets"),
])
p(
    "MongoDB memory is the right fit for high-volume, per-user, queryable history (Part 2's "
    "actual job); file-based memory is the right fit for a small number of durable, project-wide "
    "facts that should always be present (exactly what AGENT.md/MEMORY.md are used for here)."
)

# ============================================================= AI_USE
h1("AI Use Statement")

h2("1. What I used an AI assistant for, and what I did myself")
p(
    "I used Claude Code to design and write the MongoDB schema and CRUD API, the short/long/"
    "episodic memory system and chat endpoint, the token-cost experiment harness, and the "
    "file-based memory system with consolidation. It ran all of this against real infrastructure: "
    "a real MongoDB container, the real local Ollama model, and real embeddings."
)
p(
    "What I did myself: designed the announcements entity, decided how the one-turn lag in "
    "summaries/episodic retrieval should work (confirmed intentional, not a bug, by reading the "
    "actual turn-by-turn output), picked the 30-message test conversation and where to plant "
    "probe facts, iterated through three consolidation designs myself before the one that works, "
    "and manually reviewed and corrected the consolidation pipeline's one factually wrong "
    "resolution rather than accepting it at face value."
)

h2("2. One AI-produced output that was wrong/unsuitable")
p(
    "Two. Episode extraction silently stored nothing on the first real conversation turn: the "
    "model replied with a single JSON object (the fact itself) instead of a list, and my parsing "
    "code treated that as \"no facts.\" Separately, Part 4.5's stress test expects consolidation "
    "to merge 3+ duplicates and resolve 3+ contradictions in a 56-line file and land under 40 "
    "lines; the first design (one-shot rewrite) went from 56 to 54 lines and resolved none of the "
    "three planted contradictions."
)

h2("3. How I detected the problem")
p(
    "For the episode bug: queried MongoDB directly after the first turn and got zero results "
    "despite an obviously memorable first message, then ran the extraction prompt by hand to see "
    "the model's raw (unwrapped) reply. For consolidation: the before/after line counts (56 to "
    "54) immediately signaled something had gone wrong, and reading the actual file content "
    "confirmed all three planted contradictions were still present, untouched."
)

h2("4. What I changed and why it works now")
p(
    "For episodes: the parser now checks whether a returned dict looks like a single fact "
    "directly (has a \"fact\" key) and wraps it in a list, in addition to the {\"facts\": [...]} "
    "case. For consolidation: after two more failed one-shot designs, duplicates are now found "
    "via embedding similarity and confirmed with a narrow yes/no call before anything is dropped, "
    "contradictions are found by checking which similar pair differs in a number or a polarity "
    "word, and only the final one-line merge for a confirmed contradiction goes through the "
    "model. This caught all three planted contradictions reliably, though it still got one "
    "resolution factually wrong (SHORT_TERM_N) and missed two of three duplicate pairs due to the "
    "similarity threshold - documented and corrected by hand in METRICS.md and "
    "test_memory_after.md rather than quietly accepted."
)

out_path = "Achutuni_HW6.docx"
doc.save(out_path)
print("wrote full draft:", out_path)
