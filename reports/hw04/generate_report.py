"""One-off script that assembles the HW4 Word report from the extracted
screenshots plus METRICS.md / AI_USE.md content. Not part of the graded
deliverable, kept here only so the report can be regenerated if a screenshot
or the commit hash placeholder needs to change."""

import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

SS = "screenshots/"

doc = docx.Document()

doc.add_heading("DATA 260 Homework 4 Report", level=0)
doc.add_paragraph("Sreeram Achutuni")
doc.add_paragraph("SJSU ID: 019151808")

# ---------------------------------------------------------------- Section 0
doc.add_heading("Section 0: Config values", level=1)
config_rows = [
    ("SID4", "1808"),
    ("PORT_BASE", "8008"),
    ("PREFIX", "s1808"),
    ("SEED", "1808"),
    ("VERIFY_SEED", "261808"),
    ("DOMAIN_ID", "0, Campus course catalogue and enrolment"),
    ("Hardware", "Intel Core i7-11390H, 16GB RAM, integrated Iris Xe graphics (no dedicated GPU)"),
    ("Database", "MySQL 8 in Docker, host port 3307 (this machine already had a native MySQL "
                 "instance bound to the default 3306, so the container was remapped instead)"),
    ("Local model", "sentence-transformers/all-MiniLM-L6-v2 for embeddings (Part 4 retrieval), "
                     "qwen2.5:1.5b-instruct via Ollama for generation (Part 4 answers), both "
                     "running CPU-only on the machine above, no dedicated GPU"),
    ("Repo", "https://github.com/sriram2930/Data260-1808"),
    ("Commit tagged as hw4", "63d2bd2a13e423ed71d7a8414704d84da008cec5"),
]
t = doc.add_table(rows=0, cols=2)
t.style = "Table Grid"
for k, v in config_rows:
    row = t.add_row()
    row.cells[0].text = k
    row.cells[1].text = v

def h1(text):
    doc.add_heading(text, level=1)

def h2(text):
    doc.add_heading(text, level=2)

def p(text):
    doc.add_paragraph(text)

def img(path, width=6.3):
    doc.add_picture(SS + path, width=Inches(width))

def code_block(text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)

def note(text):
    para = doc.add_paragraph()
    run = para.add_run("Note: " + text)
    run.italic = True

# --------------------------------------------------------------------- P1
h1("Part 1: React Client (Login and CRUD against the FastAPI backend)")
p(
    "This part is a new Vite + React app in Part-6/, separate from the server-rendered "
    "templates built in HW2 and HW3. It talks to the same FastAPI backend from Part-1/ "
    "over fetch with credentials included, so the browser's session cookie goes along "
    "with every request. App.jsx owns the course list and the currently selected course "
    "as state, and passes callback props (onCreate, onUpdate, onDelete) down into the "
    "Create/Update/Delete pages instead of having each page fetch on its own, which is "
    "what the assignment specifically asked for. Routing is react-router-dom: / for the "
    "list, /login, /create, /update, and /delete."
)

h2("Home page, not logged in")
p("Visiting / with no session shows a \"Login required\" message instead of the course list.")
img("p01_img1.png")

h2("Login page")
p("Demo credentials (advisor@sjsu.edu / course123) filled in.")
img("p01_img2.png")

h2("Home page, logged in")
p("After login the same route now shows the actual course catalogue and an Add Record button.")
img("p02_img1.jpeg")

h2("Add a Course")
p("The create form. Submitting calls onCreate, which POSTs to /api/courses and refreshes the list.")
img("p02_img2.png")

h2("Update Course")
p("Clicking Update on a row navigates to /update pre-filled with that course's current values.")
img("p03_img2.png")

h2("Delete Course")
p("Clicking Delete goes to a confirmation screen before the DELETE request actually fires.")
img("p04_img1.png")

h2("App.jsx — shared state and routes")
p("The parent component owning the course list, the selected record, and the <Routes> wiring.")
img("p05_img1.png")
img("p05_img2.png")

h2("App.jsx — create / update / delete handlers")
p("Each handler calls the matching api.js function, then calls refreshCourses() so the list "
  "in state reflects the server afterward.")
img("p04_img2.png")

# --------------------------------------------------------------------- P2
h1("Part 2: MySQL Persistence and Server-Side Sessions")
p(
    "The course data that used to live in a plain Python list is now backed by MySQL through "
    "SQLAlchemy. The session factory in db.py is named db_session_basede26, matching the exact "
    "name the assignment required. Logging in creates a row in a sessions table with a random "
    "token as its primary key; the browser only ever holds that opaque token, in an HttpOnly, "
    "Secure, SameSite=lax cookie, never anything about the user. This is different from HW3's "
    "session setup, which used Starlette's SessionMiddleware and a signed cookie that carried "
    "the session data itself rather than just a pointer to a server-side row."
)

h2("Session helpers and the require_user dependency")
p("create_session writes the token row; get_current_user reads the cookie and looks the token "
  "up (deleting it if expired); require_user is the FastAPI dependency every protected route uses.")
img("p11_img1.png")

h2("Login / me / logout routes")
p("POST /api/login checks the bcrypt hash and sets the cookie; GET /api/me returns the current "
  "user for require_user-gated routes; POST /api/logout deletes the session row and the cookie.")
img("p12_img1.png")

h2("Course Pydantic models")
p("CourseIn/CourseOut for the request and response bodies of the CRUD routes below.")
img("p13_img1.png")

h2("CRUD route implementations")
p("create_course, list_courses, get_course, and update_course, all behind Depends(require_user).")
img("p14_img1.png")

note(
    "the screenshot set does not include a dedicated Postman screenshot of the raw POST "
    "/api/login response with its Set-Cookie header. The Part 1 screenshots above already "
    "exercise the underlying POST /api/courses, PUT /api/courses/{id}, and DELETE "
    "/api/courses/{id} endpoints end to end through the browser (Add/Update/Delete Course), "
    "and the GET responses below prove a session was active (a request with no valid session "
    "gets a 401, not a course list), so the round trip is demonstrated, just not with a "
    "standalone login screenshot."
)

h2("GET /api/courses (all)")
p("With a valid session cookie attached, this returns the full course list from MySQL.")
img("p06_img2.jpeg")

h2("GET /api/courses/{id}")
p("A single course by id.")
img("p07_img2.png")

h2("Database contents")
p("Querying the MySQL container directly to confirm the courses, sections, users, and sessions "
  "tables actually hold this data, not just the API's view of it.")
img("p07_img3.png")

h2("Project structure")
p("Part-1/ (backend), Part-5/ (RAG pipeline) and Part-6/ (React client) as they sit in the repo.")
img("p08_img1.png")
img("p09_img1.png")
img("p10_img1.png")

# --------------------------------------------------------------------- P3
h1("Part 3: N+1 Query Measurement and Index Tuning")
p(
    "Section is a related entity to Course, one-to-many with a foreign key back to courses.id. "
    "seed_n1.py deterministically generates 5,000 courses and 200 sections (SEED=1808). Two read "
    "endpoints return the same data two different ways: /api/n1/naive loops over the page and "
    "touches c.sections per row, which lazy-loads a fresh query for every single course; "
    "/api/n1/fixed uses SQLAlchemy's joinedload so the whole page comes back in one query with a "
    "LEFT OUTER JOIN. Both endpoints report their own SQL statement count in the response body, "
    "using a per-request counter in db.py built on a before_cursor_execute event listener."
)

h2("api_n1.py — naive endpoint")
img("p18_img1.png")

h2("api_n1.py — fixed endpoint")
img("p19_img1.png")

h2("Naive, page_size=10 (query_count=11)")
img("p03_img1.png")

h2("Fixed, page_size=10 (query_count=1)")
img("p14_img2.png")

h2("Naive, page_size=50 (query_count=51)")
img("p15_img1.jpeg")

h2("Fixed, page_size=50 (query_count=1)")
img("p15_img2.jpeg")

h2("Fixed, page_size=200 (query_count=1)")
img("p16_img1.jpeg")

note(
    "a naive?page_size=200 screenshot is missing from this set (page_size=10 and 50 are covered "
    "for both versions, 200 only got captured for the fixed endpoint). The measurement script's "
    "raw output still has that row: 201 SQL statements and a 2552.57ms p50, reproduced in the "
    "results table below from reports/hw04/raw/n1_experiment_summary.json."
)

h2("Results (180 requests: 3 page sizes x 2 versions x 30 each)")
results = [
    ("Page size", "Version", "SQL stmts/req", "p50 (ms)", "p95 (ms)", "p99 (ms)"),
    ("10", "naive", "11", "2072.75", "2105.45", "2119.57"),
    ("10", "fixed", "1", "2043.77", "2058.61", "2066.52"),
    ("50", "naive", "51", "2173.87", "2197.92", "2213.18"),
    ("50", "fixed", "1", "2050.82", "2064.70", "2065.87"),
    ("200", "naive", "201", "2552.57", "2636.69", "2644.59"),
    ("200", "fixed", "1", "2059.02", "2079.75", "2097.28"),
]
t = doc.add_table(rows=0, cols=6)
t.style = "Table Grid"
for r in results:
    row = t.add_row()
    for i, val in enumerate(r):
        row.cells[i].text = val

p(
    "Every request on this machine, even the flat single-query fixed endpoint, sits on top of a "
    "roughly constant ~2050ms floor. That is not part of the N+1 story, it shows up identically "
    "whether the request runs one query or two hundred and one, and it looks like Docker "
    "Desktop's WSL2 networking overhead on Windows rather than anything about MySQL or the join "
    "versus loop difference. Netting that floor out isolates the real signal:"
)
netted = [
    ("Page size", "naive p50 - fixed p50 (ms)", "extra queries", "cost per extra query (ms)"),
    ("10", "28.98", "10", "2.90"),
    ("50", "123.05", "50", "2.46"),
    ("200", "493.55", "200", "2.47"),
]
t = doc.add_table(rows=0, cols=4)
t.style = "Table Grid"
for r in netted:
    row = t.add_row()
    for i, val in enumerate(r):
        row.cells[i].text = val
p(
    "Once the shared floor is subtracted, the extra cost per additional N+1 query lands "
    "consistently around 2.5-2.9ms and scales linearly with page size, which is exactly the N+1 "
    "signature the experiment is meant to surface. The SQL statement counts alone (11/51/201 "
    "versus a flat 1) already make the point unambiguously, independent of any latency floor."
)

h2("EXPLAIN before adding an index")
p(
    "sections.course_id already has an index, but MySQL refuses to drop it for a clean before/"
    "after demo since it backs a live foreign key (error 1553). So this demonstrates a genuinely "
    "new index instead, on courses.department, for the query "
    "SELECT * FROM courses WHERE department = 'Data Science & AI' (1,257 matching rows out of 5,000)."
)
img("p16_img2.png")

h2("EXPLAIN after adding the index")
img("p17_img1.png")
p(
    "Before the index, MySQL has no way to jump to the matching rows, so it does a full table "
    "scan (type=ALL) across all ~5,000 rows and filters each one in memory, its own filtered "
    "estimate of 10% meaning it expects to throw away 90% of what it reads. After adding "
    "ix_courses_department, the plan switches to type=ref, scanning almost exactly the 1,257 "
    "rows that actually match (filtered=100%). It goes from reading everything and keeping a "
    "tenth of it to reading only what is needed."
)

# --------------------------------------------------------------------- P4
h1("Part 4: Grounded RAG Question-Answering")
p(
    "This reuses the 32-document SJSU corpus built for HW3 (already well past the 5-document "
    "minimum) rather than building a new one, re-chunked with a TokenTextSplitter at chunk_size="
    "500 and chunk_overlap=50, 226 chunks total, embedded with the same all-MiniLM-L6-v2 model as "
    "HW3. What is new in HW4 is generation: answers actually come from qwen2.5:1.5b-instruct "
    "running locally through Ollama, routed through the same ModelClient adapter used everywhere "
    "else in this repo. Six questions (rag_questions.yaml) are run through three configurations, "
    "No-RAG (no retrieval, just the raw question to the model), Basic-RAG (retrieved chunks "
    "pasted into the prompt with no curation), and Context-RAG (relevance filtering, near-"
    "duplicate removal, source labeling, and an explicit grounding-and-refusal system prompt "
    "requiring bracketed citations)."
)

h2("rag_qa.py — the three answer configurations")
code_block(
    'def answer_no_rag(question: str) -> dict:\n'
    '    messages = [\n'
    '        {"role": "system", "content": "Answer the user\'s question directly and concisely."},\n'
    '        {"role": "user", "content": question},\n'
    '    ]\n'
    '    result = call_llm(messages)\n'
    '    return {"config": "no_rag", "question": question, "chunks_used": [], **result}\n\n'
    'def answer_basic_rag(question: str, k: int = 3) -> dict:\n'
    '    chunks = retrieve_chunks(question, k=k)\n'
    '    context = "\\n\\n".join(c["text"] for c in chunks)\n'
    '    messages = [\n'
    '        {"role": "system", "content": "Use the following context to answer the question."},\n'
    '        {"role": "user", "content": f"CONTEXT:\\n{context}\\n\\nQUESTION: {question}"},\n'
    '    ]\n'
    '    result = call_llm(messages)\n'
    '    return {"config": "basic_rag", "question": question, "chunks_used": chunks, **result}\n\n'
    'CONTEXT_RAG_SYSTEM_PROMPT = f"""You are a grounded question-answering assistant.\n'
    'You must answer ONLY using the numbered SOURCE excerpts provided below -- do not\n'
    'use any outside knowledge. For every factual claim, cite the source number in\n'
    'square brackets, e.g. [1]. If the sources do not contain enough information to\n'
    'answer confidently, respond with EXACTLY this sentence and nothing else:\n'
    '"{REFUSAL_TEXT}\\""""\n\n'
    'def answer_context_rag(question: str, k: int = 3) -> dict:\n'
    '    raw_chunks = retrieve_chunks(question, k=k)\n'
    '    curated = curate_chunks(raw_chunks)\n'
    '    if not curated:\n'
    '        labeled_context = "(no sufficiently relevant sources were retrieved)"\n'
    '    else:\n'
    '        labeled_context = "\\n\\n".join(\n'
    '            f"SOURCE [{i+1}] (file: {c[\'source\']}):\\n{c[\'text\']}" for i, c in enumerate(curated)\n'
    '        )\n'
    '    messages = [\n'
    '        {"role": "system", "content": CONTEXT_RAG_SYSTEM_PROMPT},\n'
    '        {"role": "user", "content": f"{labeled_context}\\n\\nQUESTION: {question}"},\n'
    '    ]\n'
    '    result = call_llm(messages)\n'
    '    return {"config": "context_rag", "question": question, "chunks_used": curated, **result}\n'
)
note("no screenshot of this file was captured, so the actual source text is reproduced above instead.")

h2("q1, all three configurations")
p("\"What course should a CS major with no prior computing experience take instead of jumping "
  "straight into CS 46A?\" — No-RAG guesses (and gets it wrong), both RAG configurations retrieve "
  "the right chunk and answer correctly.")
img("p19_img2.png")

h2("Three-configuration comparison, all six questions")
comparison = [
    ("Q", "Category", "Config", "Correct retrieval", "Correct answer", "Grounded (cite)", "Refused (exact phrase)"),
    ("q1", "single chunk", "No-RAG", "-", "No", "-", "No"),
    ("q1", "single chunk", "Basic-RAG", "Yes", "Yes", "-", "No"),
    ("q1", "single chunk", "Context-RAG", "Yes", "Yes", "No", "No"),
    ("q2", "two chunks", "No-RAG", "-", "Yes*", "-", "No"),
    ("q2", "two chunks", "Basic-RAG", "Yes", "Yes*", "-", "No"),
    ("q2", "two chunks", "Context-RAG", "Yes", "Yes*", "No", "No"),
    ("q3", "similar across docs", "No-RAG", "-", "No", "-", "No"),
    ("q3", "similar across docs", "Basic-RAG", "Yes", "Yes", "-", "No"),
    ("q3", "similar across docs", "Context-RAG", "Yes", "Yes", "No", "No"),
    ("q4", "ambiguous", "No-RAG", "-", "n/a", "-", "No"),
    ("q4", "ambiguous", "Basic-RAG", "-", "n/a", "-", "No"),
    ("q4", "ambiguous", "Context-RAG", "-", "n/a", "No", "No"),
    ("q5", "not in documents", "No-RAG", "-", "n/a", "-", "No (soft “I don't know”)"),
    ("q5", "not in documents", "Basic-RAG", "-", "n/a", "-", "No (soft “not mentioned”)"),
    ("q5", "not in documents", "Context-RAG", "-", "n/a", "No", "Yes"),
    ("q6", "unrelated", "No-RAG", "-", "n/a", "-", "No (fabricated a full recipe)"),
    ("q6", "unrelated", "Basic-RAG", "-", "n/a", "-", "No (garbled non-answer)"),
    ("q6", "unrelated", "Context-RAG", "-", "n/a", "No", "Yes"),
]
t = doc.add_table(rows=0, cols=7)
t.style = "Table Grid"
for r in comparison:
    row = t.add_row()
    for i, val in enumerate(r):
        row.cells[i].text = val
p(
    "* \"Correct answer\" for q2 is misleading as scored. The automated checker only requires one "
    "expected keyword to be present, and every q2 answer got the GPA half right (2.0) while "
    "getting the years half wrong, so it counts as a pass despite being genuinely half-"
    "hallucinated. See the k-sweep and written analysis below for the actual text."
)

h2("k-sweep on q2 (Context-RAG, k = 1, 3, 5)")
img("p20_img1.png")
ksweep = [
    ("k", "Answer (years part)", "Correct (GPA)", "Correct (years)", "Latency (ms)"),
    ("1", "\"...generally has five years...\"", "Yes", "No", "8985.8"),
    ("3", "\"...complete their degree within 4 years.\"", "Yes", "No", "14200.3"),
    ("5", "\"...minimum of four years...\"", "Yes", "No", "22162.3"),
]
t = doc.add_table(rows=0, cols=5)
t.style = "Table Grid"
for r in ksweep:
    row = t.add_row()
    for i, val in enumerate(r):
        row.cells[i].text = val
p(
    "More context did not help here. At k=5 the retriever finally pulled in a chunk from the "
    "correct file (sjsu_mscs_faq.txt) that was not present at k=1 or k=3, but that particular "
    "chunk landed on a different part of the FAQ (about admission offers) than the sentence that "
    "actually states \"up to 7 years\", which sits in a different chunk of the same file that "
    "never made the top five. Retrieval got closer, right file, wrong chunk, without ever "
    "surfacing the fact, and the model filled the gap with a different wrong number each time "
    "(five, then four, then four), which suggests it was guessing rather than recalling anything "
    "reliably. No irrelevant chunks entered the context at any k, every retrieved chunk scored "
    "above the 0.30 relevance threshold, so this was not a case of junk crowding out the signal, "
    "the signal genuinely was not in any of the retrieved chunks. Latency scaled up substantially "
    "with k (9.0s to 14.2s to 22.2s) purely from longer prompts, for zero accuracy benefit on "
    "this question. The best choice of k here is honestly k=1: same wrong answer, a third of the "
    "latency."
)

h2("Evaluation summary")
img("p20_img2.png")
evalsum = [
    ("Metric", "Value", "What it measures"),
    ("Accuracy", "0.778", "Fraction of (question, config) pairs with an expected keyword present, "
                            "among q1-q3 only (q4-q6 have no fixed keyword answer); inflated by q2's "
                            "partial-credit issue above"),
    ("Faithfulness (grounded rate)", "0.0", "Fraction of Context-RAG answers that included a [n] "
                                             "citation, despite the system prompt explicitly requiring one"),
    ("Refusal correctness", "0.778 (14/18)", "Fraction of all 18 runs where \"did it refuse\" matched "
                                              "\"should it have refused\"; driven entirely by q5/q6, where "
                                              "Context-RAG refused correctly both times and neither "
                                              "No-RAG nor Basic-RAG ever used the required exact phrase"),
]
t = doc.add_table(rows=0, cols=3)
t.style = "Table Grid"
for r in evalsum:
    row = t.add_row()
    for i, val in enumerate(r):
        row.cells[i].text = val

h2("Written analysis")
p(
    "Retrieval worked cleanly for q1 and q3: both pulled the exact source file on the first try, "
    "and both RAG configurations answered correctly, while No-RAG guessed wrong on both "
    "(hallucinating a nonexistent \"CS 101\" course for q1, and giving no concrete number at all "
    "for q3). q2 is the interesting failure: retrieval consistently found the right file for the "
    "GPA fact (sjsu_socsci_academic_notice.txt) but never found the specific chunk holding the "
    "\"up to 7 years\" fact in sjsu_mscs_faq.txt, even at k=5 where a different chunk from that "
    "same file did show up. Chunk size is the likely culprit, a 500-token chunk boundary happened "
    "to separate the sentence needed from the surrounding FAQ content that scored higher on this "
    "query. This matters more than it sounds: the automated \"correct answer\" check scored all "
    "three q2 configurations as passing, because it only requires one of several expected "
    "keywords to appear, and \"2.0\" always did. Reading the actual text, every single q2 answer "
    "across every config and every k value got the years figure wrong (five, four, four, four, "
    "never seven), which the summary metric completely hides. That is a real lesson about "
    "evaluating RAG systems: a lenient keyword check can look like 78% accuracy while missing a "
    "persistent, 100%-reproducible factual error."
)
p(
    "The context-engineering changes that clearly helped were the grounding rules and the "
    "refusal instruction, not the deduplication or ordering logic (no duplicate or irrelevant "
    "chunks actually showed up in any of these six questions' retrievals, so those safeguards "
    "never got exercised here). The refusal instruction is what separated Context-RAG from the "
    "other two on q5 and q6: No-RAG and Basic-RAG never once produced the exact required refusal "
    "sentence, instead either giving a soft non-answer (q5) or, worse, fabricating a complete, "
    "plausible-sounding chocolate chip cookie recipe with zero connection to the source documents "
    "(q6, No-RAG). That recipe is unambiguous, ungrounded hallucination, invented from the "
    "model's own training data with no attempt to check it against anything retrieved. "
    "Context-RAG refused both correctly, in the exact required wording, both times."
)
p(
    "What did not work as instructed was citation. Every Context-RAG system prompt explicitly "
    "required a [n] source citation on every factual claim, and not one of the six answers "
    "included one, despite otherwise following the \"answer only from context\" and refusal "
    "rules correctly. Retrieval quality, context quality, and the prompt each did real, separable "
    "work here: retrieval decided whether the right fact was even available to use; context "
    "curation (relevance filtering, labeling) decided whether the model had a clean set of "
    "sources to draw from once retrieval succeeded; and the prompt's grounding rules decided "
    "whether the model was honest about the gap when retrieval failed. But the prompt's "
    "formatting instruction (citation) was simply not followed by this small model even when "
    "everything else about the setup was correct, a clear reminder that a 1.5B-parameter local "
    "model's compliance with strict output-format rules cannot be assumed just because the rule "
    "is stated plainly."
)

# --------------------------------------------------------------------- AI_USE
h1("AI Use Statement")

h2("1. What I used an AI assistant for, and what I did myself")
p(
    "I used Claude Code to write and run essentially everything: the React client, the "
    "SQLAlchemy models and MySQL-backed session/auth system, the N+1 naive/fixed endpoints and "
    "the 180-request measurement script, the EXPLAIN demo, and the full grounded RAG QA pipeline "
    "(chunking, retrieval, three answer configurations, the k-sweep, and the automated evaluation "
    "checks). It also ran the actual experiments on this machine against a real MySQL container "
    "and the real local Ollama model, not simulated data."
)
p(
    "What I did myself: decided the \"related entity\" design for Part 3 (course sections, "
    "foreign-keyed to courses, since the assignment left that open), picked which of my own "
    "prior corpus and infrastructure to reuse versus rebuild (reused the HW3 SJSU corpus for "
    "Part 4 instead of building a new one, since it already met the 5-document minimum and kept "
    "the domain consistent), wrote and verified the six RAG test questions' expected facts "
    "against the actual corpus text before running anything, and read through the raw model "
    "outputs myself rather than trusting the automated pass/fail scores at face value."
)

h2("2. One AI-produced output that was wrong or unsuitable")
p(
    "The automated \"correct_answer\" check in the RAG evaluation (Part 4) scores an answer as "
    "correct if it contains at least one of several expected keywords. For question 2 (\"what GPA "
    "keeps you off academic notice, and how many years does an MSCS student have to finish\"), "
    "every single answer across all three configurations and all three k-sweep values got the "
    "GPA half right (2.0) but the years half wrong (it said five, four, or four, never the actual "
    "seven). Because the keyword check only requires one match, all of these got marked "
    "correct_answer: true, and the summary metric reported 77.8% accuracy, a number that quietly "
    "hides a 100%-reproducible factual error on one of the six questions."
)

h2("3. How I detected the problem")
p(
    "By reading the actual raw answer text in reports/hw04/raw/rag_three_config_results.json and "
    "the k-sweep output instead of only looking at the summary JSON's pass/fail booleans. The "
    "automated check technically did what I told it to do (check for any expected keyword), it "
    "just was not a strict enough check to catch a partially wrong, two-part answer."
)

h2("4. What I changed and why it works now")
p(
    "I did not change the scoring code itself, since a stricter check (requiring every expected "
    "keyword) would have its own failure modes for other questions with alternative valid "
    "phrasings. Instead I added an explicit callout in METRICS.md's evaluation table and written "
    "analysis saying plainly that q2's \"correct\" marks are misleading and pointing at the real "
    "answer text, plus an explanation of why retrieval never surfaced the \"7 years\" fact even "
    "at k=5 (it retrieved a different chunk from the right file, not the chunk with that sentence "
    "in it). This is the honest fix: rather than pretend the automated metric is the ground "
    "truth, the report says outright where it isn't, and shows the actual wrong numbers next to it."
)
p(
    "A second thing worth recording here, not a bug I fixed so much as a real system limitation "
    "I verified by reading the raw output: the Context-RAG system prompt explicitly required a "
    "[n] citation on every claim, and I checked programmatically (a regex for \\[\\d+\\]) whether "
    "any of the six answers actually included one. None did, faithfulness_grounded_rate: 0.0. I "
    "did not \"fix\" this by re-prompting or adding few-shot examples, since the assignment's "
    "interest here is in observing and reporting real context/prompt-engineering behavior rather "
    "than engineering the model into compliance; the honest result is that this small local model "
    "followed the grounding and refusal rules but not the citation-format rule, and that asymmetry "
    "is reported as-is."
)

out_path = "DATA 260 HW 4 Report FINAL.docx"
doc.save(out_path)
print("wrote", out_path)
