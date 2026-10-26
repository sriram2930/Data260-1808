# data260-1808 — DATA-260 Homework Repository

This repository is extended for every DATA-260 homework this semester. Each
homework's code is split into one folder per part (`Part-1` ... `Part-4`);
`reports/hw01/` holds the graded deliverables per the assignment spec.

All commands below assume your current directory is the **repo root**
(`data260-1808/`) — scripts are invoked by their path (e.g. `Part-2\agents_demo.py`)
rather than by `cd`-ing into each folder, so relative paths inside the scripts
resolve correctly regardless of where you run them from.

## Section 0 — Personal Configuration

| Value | Formula | Value |
|---|---|---|
| SID4 | last 4 digits of SJSU ID | `1808` |
| PORT_BASE | 8000 + (SID4 mod 900) | `8008` |
| PREFIX | "s" + SID4 | `s1808` |
| SEED | SID4 | `1808` |
| VERIFY_SEED | 260000 + SID4 | `261808` |
| DOMAIN_ID | SID4 mod 8 | `0` — Campus course catalogue and enrolment |
| Hardware | | Intel Core i7-11390H, 16GB RAM, integrated Intel Iris Xe Graphics (no dedicated GPU) |
| Local model | | `qwen2.5:1.5b-instruct` (Ollama) — see note below |

**Model substitution note:** the spec default is `qwen3:8b`. This machine has no
dedicated GPU (integrated Iris Xe only), so an 8B model would make CPU-only
inference impractical for the 80+ sequential model calls Part 3 requires (20
runs × 2 temperatures × 2 agent calls per run). `qwen2.5:1.5b-instruct` keeps the
same model family/instruction-tuning lineage as the spec default while
completing the full Part 3 batch in ~13-15 minutes.

---

## Part 1 — HTML/JS App (Course Catalogue Submission Form)

Files: [Part-1/index.html](Part-1/index.html), [Part-1/app.js](Part-1/app.js),
[Part-1/DOMAIN_SCHEMA.md](Part-1/DOMAIN_SCHEMA.md)

### Run without Docker (quick check)
```
cd Part-1
python -m http.server 8008
```
then visit `http://localhost:8008`.

### Run with Docker (local)
```
cd Part-1
docker build -t data260-1808-hw1 .
docker run -d -p 8008:8008 --name data260-1808-hw1-container data260-1808-hw1
```
Open `http://localhost:8008` in a browser. Stop/clean up when done:
```
docker stop data260-1808-hw1-container
docker rm data260-1808-hw1-container
```

### Deploy to AWS ECS (Fargate, single task)

Deployed via AWS CLI (after pushing the image to ECR from AWS CloudShell — see
note below) rather than console clicks; the resulting resources match the
standard ECR → Security Group → ECS Cluster → Task Definition → Service flow,
all using **PORT_BASE = 8008**.

1. **Build & push image to ECR** — built locally with `docker build`, then
   pushed to ECR **from AWS CloudShell** rather than this machine's Docker
   Desktop, which has a known bug where `docker login` fails against ECR with
   an unexplained `400 Bad Request` even with valid credentials (confirmed via
   a direct authenticated HTTPS request to the registry, which succeeded).
   CloudShell's own Docker has no such issue.
   ```
   aws ecr create-repository --repository-name data260-1808-hw1 --region us-east-1
   aws ecr get-login-password --region us-east-1 | docker login --username AWS \
     --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   docker tag data260-1808-hw1:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/data260-1808-hw1:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/data260-1808-hw1:latest
   ```
2. **Security group** — `s1808-hw1-sg`, inbound: TCP **8008** from `0.0.0.0/0`.
3. **ECS Cluster** — `s1808-hw1-cluster`, AWS Fargate (serverless). (First
   attempt failed with "Unable to assume the service linked role" — a
   known first-time-account race condition; creating the
   `AWSServiceRoleForECS` role and retrying succeeded.)
4. **Task Definition** — see [`Part-1/ecs-task-def.json`](Part-1/ecs-task-def.json):
   family `s1808-hw1-task`, Fargate, Linux/X86_64, 0.25 vCPU / 0.5 GB, execution
   role `ecsTaskExecutionRole` (created manually — didn't exist on this fresh
   account), container `hw1-container`, port 8008, `awslogs` → `/ecs/s1808-hw1`
   (also created manually — the standard `AmazonECSTaskExecutionRolePolicy`
   grants `logs:CreateLogStream`/`PutLogEvents` but not `CreateLogGroup`).
5. **ECS Service** — `s1808-hw1-service` in `s1808-hw1-cluster`, desired
   tasks **1**, default VPC, public subnets, `s1808-hw1-sg`, **Public IP:
   Enabled**.
6. **Verified** reachable at the task's public IP on port 8008 (`HTTP 200`,
   correct page title) before screenshotting for the report.
7. **Cleanup** performed immediately after the screenshot: service scaled to
   0 → service deleted → cluster deleted → task definition deregistered →
   ECR repository deleted → security group deleted → log group deleted, to
   avoid ongoing Fargate charges.

---

## Part 2 — Agentic AI (Planner → Reviewer → Finalizer)

Files: [Part-2/agents_demo.py](Part-2/agents_demo.py), [Part-2/sample_input.json](Part-2/sample_input.json)

### Setup
Requires Python 3.11/3.12 (not 3.13+) and Ollama running locally with a model
pulled. One shared venv at the repo root covers Parts 2-4:
```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen2.5:1.5b-instruct
```

### Run
```
.venv\Scripts\python Part-2\agents_demo.py --input-file Part-2\sample_input.json --temperature 0.7
```
or with inline text:
```
.venv\Scripts\python Part-2\agents_demo.py --title "..." --content "..." --temperature 0.7
```
Prints, in order: the input, the Planner's draft JSON, the Reviewer's JSON
(approved/corrected), and the Finalized/Publish JSON — plus pipeline latency.
Full write-up (Q1-Q3, step explanation): [`reports/hw01/PART2_AGENTIC_AI.md`](reports/hw01/PART2_AGENTIC_AI.md).

### Design notes
- **Planner** and **Reviewer** are each one call to the local Ollama model via
  `langchain_ollama.ChatOllama`, using `with_structured_output` (Pydantic
  schemas) so Ollama's JSON-schema-constrained generation forces valid JSON
  matching the expected shape.
- **Finalizer** is deterministic Python (`_enforce_contract`), not a third
  model call — it guarantees exactly 3 tags and a ≤25-word summary no matter
  what the model returned, which matters for running this unattended 40 times
  in Part 3.
- Nothing in `agents_demo.py` references any specific domain — tags/summary
  are derived only from whatever `title`/`content` the caller passes in.

---

## Part 3 — Measuring Non-Determinism

Files: [Part-3/run_nondeterminism.py](Part-3/run_nondeterminism.py),
[reports/hw01/cases/nondeterminism_input.json](reports/hw01/cases/nondeterminism_input.json)

```
.venv\Scripts\python.exe Part-3\run_nondeterminism.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part3.txt
```
`run_nondeterminism.py` imports `run_pipeline` directly from `Part-2\agents_demo.py`
(no duplicated agent logic — it adds `Part-2/` to `sys.path` at import time) and
runs the pipeline 20× at temperature 0.7 and 20× at temperature 0.0 on the fixed
input, writing raw rows + summary metrics to `reports/hw01/raw/`. Full results
tables and write-up: [`reports/hw01/METRICS.md`](reports/hw01/METRICS.md).

> Note: Windows PowerShell 5.1's `Tee-Object`/`Out-File` default to UTF-16.
> Re-save any regenerated log as UTF-8 with:
> `Get-Content -Raw -Encoding Unicode <file> | Set-Content -Encoding utf8 <file>`

---

## Part 4 — Model Client and Token Accounting

Files: [Part-4/src/model_client.py](Part-4/src/model_client.py),
[Part-4/hw1_client.py](Part-4/hw1_client.py), [Part-4/AGENT.md](Part-4/AGENT.md)

```
.venv\Scripts\python.exe Part-4\hw1_client.py
```
A small interactive CLI chat built on `src/model_client.py`'s
`ModelClient.complete(messages, tools=None)` adapter — the one interface all
model calls in this file go through. Loads `AGENT.md` (a strict bullet-only
code-review contract, sitting alongside it in `Part-4/`) as the system prompt.
After every model response it prints that turn's input/output/total tokens;
`/stats` shows cumulative turn count, cumulative token counts, and serialized
conversation-history length without altering the history; on exit it prints
cumulative totals.

To reproduce the exact 5-turn conversation used for the report:
```
Get-Content Part-4\smoke_test_conversation.txt | .venv\Scripts\python.exe Part-4\hw1_client.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part4.txt
```
Full results (per-turn token table, `/stats` snapshots, AGENT.md compliance
finding, and the four conceptual answers) are in
[`reports/hw01/METRICS.md`](reports/hw01/METRICS.md).

**Why is prior conversation context resent with every turn?** The model is
stateless between calls — it has no memory of earlier turns unless that
content is physically included in the current request, so the client must
resend the full history (system prompt + every prior message) each turn.

**How is a system prompt different from a user message?** A system message
sets standing, session-wide behavior (here, `AGENT.md`'s bullet-only rule) and
is configuration rather than something "said" in the conversation; a user
message is the live, changing input the model is meant to respond to each turn.

**Why do input tokens grow over a conversation?** Every turn's input is the
full prior history plus the new message, so it grows monotonically — observed
directly: 217 → 337 → 448 → 489 → 596 input tokens across 5 turns.

**What eventually limits that growth?** The model's context window — a fixed
maximum token count per call. Once history + new message would exceed it,
something gives: truncation, summarization, or the call failing outright.

---

## HW1 Verification

```
python verify_hw01.py
```
Runs a self-check (required files present in each `Part-N/` folder, Python
version, `index.html`/`app.js` contain the required elements/patterns, Ollama
reachable with the target model pulled, non-determinism raw data well-formed)
and writes [`reports/hw01/verification.json`](reports/hw01/verification.json).

---

# HW2

HW2 extends the same folders rather than adding new ones: **Part-1/** gains a
FastAPI backend on top of the HW1 static page, and **Part-2/** gains a
LangGraph refactor of the HW1 Planner/Reviewer agents. Same shared root-level
`.venv` (now also includes `fastapi`, `uvicorn`, `jinja2`, `python-multipart`,
`langgraph` — see `requirements.txt`).

## Part 1-2 — Responsive/Stateful UI + FastAPI CRUD Backend

Files: [Part-1/main.py](Part-1/main.py), [Part-1/templates/](Part-1/templates/),
[Part-1/static/style.css](Part-1/static/style.css)

```
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8008
```
(run from inside `Part-1/`, or point uvicorn at `Part-1.main:app` from the repo
root). Then visit `http://localhost:8008`.

- **Add** a course via the form at the bottom of the page (redirects home,
  303, on success).
- **Update** any record via its **Edit** link (`/courses/{id}/edit`); the
  assignment's specific example is updating id=1.
- **Delete** the highest-id record via the button on that card
  (`POST /courses/delete-highest`).
- **Search** by course code or title updates the list live via
  `fetch('/api/courses?q=...')`, showing a real loading spinner while the
  request is in flight, an empty-state message when nothing matches, and an
  error-state message if the request fails. Mutating forms (add/update/delete)
  show their own "Loading..." button state during the real network
  round-trip.
- Layout is mobile-first (single-column cards, fluid widths, no fixed widths
  wider than a phone screen) so it holds up at 375px without a separate
  "mobile" stylesheet.
- Storage is a simple in-memory list seeded with 3 sample records on startup
  (not a database — the assignment only requires the CRUD/redirect behavior).

## Part 3-4 — Stateful Agent Graph + Output Schema and Loop Safety

Files: [Part-2/agent_graph.py](Part-2/agent_graph.py),
[Part-2/run_schema_experiments.py](Part-2/run_schema_experiments.py),
[reports/hw02/cases/](reports/hw02/cases/)

```
.venv\Scripts\python.exe Part-2\agent_graph.py --input-file reports\hw02\cases\schema_input.json --turn-ceiling 10
```

Refactors HW1's Planner→Reviewer waterfall into a LangGraph graph implementing
the supervisor pattern (`AgentState` TypedDict, `planner_node`/`reviewer_node`/
`supervisor_node`, conditional edges via `router_logic`). All LLM calls go
through `Part-4/src/model_client.py`'s `ModelClient` adapter (extended with
optional `format=`/`temperature=` passthrough), not langchain or raw `ollama`
directly, per the assignment.

- **Schema validation** (`PlannerTags` Pydantic model): exactly 3 tags, each
  3-30 characters, summary ≤25 words. On failure, the validation error is fed
  back into the Planner's next prompt and it retries, up to `--turn-ceiling`
  Planner attempts.
- **Correction loop test**: `--force-reviewer-issues` makes the Reviewer
  always reject (no LLM call needed for it), to demonstrate/confirm the graph
  routes back to the Planner instead of ending —
  ```
  .venv\Scripts\python.exe Part-2\agent_graph.py --input-file reports\hw02\cases\schema_input.json --turn-ceiling 3 --force-reviewer-issues
  ```
- **Outcome classification**: each run ends in one of `valid_first_attempt`,
  `valid_after_1_retry`, `valid_after_2plus_retries`, or `hit_turn_ceiling`
  (`turn_count` is incremented once per Planner attempt specifically, so it
  maps directly onto these buckets).

### Running the Part 4 experiments
```
.venv\Scripts\python.exe Part-2\run_schema_experiments.py | Tee-Object -FilePath reports\hw02\RUN_LOG.txt
```
Runs, against `reports/hw02/cases/schema_input.json` and
`.../adversarial_input.json`: 30 runs classified into the four buckets, a
turn-ceiling comparison (2 vs. 10, 20 runs each), and 5 adversarial-input runs.
Writes raw rows to `reports/hw02/raw/` and a summary to
`reports/hw02/raw/schema_experiment_summary.json`. Full write-up and filled-in
tables: [`reports/hw02/METRICS.md`](reports/hw02/METRICS.md).

## HW2 Verification

```
python verify_hw02.py
```
Starts the FastAPI backend and exercises add/update(id=1)/delete-highest/search
behaviorally over HTTP, runs the LangGraph agent once to confirm it terminates
instead of hanging (and returns exactly 3 tags on an approved run), and confirms
the forced-rejection correction loop actually routes back to the Planner. Writes
[`reports/hw02/verification.json`](reports/hw02/verification.json).

---

# HW3

HW3 again extends existing folders: **Part-1/** gains a login/session/logout
system on top of the HW2 CRUD app, and a new **Part-5/** folder holds the
LlamaIndex chunking/retrieval comparison (a genuinely new capability, not an
extension of any earlier part). Same shared root-level `.venv` (now also
includes `itsdangerous`, `beautifulsoup4`, `lxml`, `llama-index`,
`llama-index-embeddings-huggingface`, `sentence-transformers`, `faiss-cpu`,
`numpy`, `pandas`, `pyyaml` — see `requirements.txt`).

## Part 1 — FastAPI Authentication

Files: [Part-1/auth.py](Part-1/auth.py), [Part-1/templates/login.html](Part-1/templates/login.html),
[Part-1/templates/dashboard.html](Part-1/templates/dashboard.html)

```
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8008
```
(same server as HW2 — `auth.py`'s router is mounted into `Part-1/main.py`.)
Demo credentials: `advisor` / `course123`.

- `/` — home page, now session-aware (shows a login link or a
  dashboard+logout link in the navbar depending on session state).
- `/login` — Bootstrap card + form; invalid credentials show a Bootstrap
  alert.
- `/dashboard` — protected; redirects to `/login` if not logged in or if the
  session has idle-timed-out.
- `/logout` — clears the session, redirects home.
- Session cookie: Starlette `SessionMiddleware`, `HttpOnly` + `Secure` +
  `SameSite=lax` all set (verified via the raw `Set-Cookie` header, not just
  assumed).
- **Idle timeout**: 30 seconds (short on purpose, so it's actually
  demoable — see `IDLE_TIMEOUT_SECONDS` in `auth.py`), enforced manually
  (`get_current_user()` checks elapsed time since `last_seen` on every
  request), since the cookie's own `max_age` is a fixed expiry from login
  time, not a sliding idle timeout.
- Note on logout: this is a stateless, signed-cookie session (no
  server-side session store), so `/logout` works by sending the browser a
  new, cleared cookie that overwrites the old one — a real browser
  correctly picks that up and the old session is gone. If someone captured
  a copy of the *raw* pre-logout cookie value and replayed it directly
  (bypassing normal browser cookie-jar behavior), that specific bypass is
  not something a purely stateless session can prevent without a
  server-side revocation list; `verify_hw03.py` tests the former (normal
  logout-then-reuse-of-the-real-cookie-the-server-sent), which is the
  standard interpretation of "log out and confirm the session doesn't
  work anymore."

## Part 2 — Compare Three LlamaIndex Chunking Techniques

Files: [Part-5/fetch_corpus.py](Part-5/fetch_corpus.py),
[Part-5/rag_compare.py](Part-5/rag_compare.py),
[Part-5/run_retrieval_comparison.py](Part-5/run_retrieval_comparison.py),
[Part-5/compute_metrics.py](Part-5/compute_metrics.py)

```
.venv\Scripts\python.exe Part-5\fetch_corpus.py            # one-time corpus build (already done, real snapshots committed)
.venv\Scripts\python.exe Part-5\run_retrieval_comparison.py  # 5 questions x 3 techniques, writes raw/
.venv\Scripts\python.exe Part-5\compute_metrics.py            # recomputes the summary table from raw/ only
```

- **Corpus**: 32 real SJSU pages (registrar/admissions/department FAQ pages),
  fetched and cleaned to plain text, 208.4KB total. Documented with SHA-256
  hashes in [`reports/hw03/CORPUS_MANIFEST.json`](reports/hw03/CORPUS_MANIFEST.json)
  / [`SOURCES.md`](reports/hw03/SOURCES.md).
- **Questions**: [`reports/hw03/questions.yaml`](reports/hw03/questions.yaml)
  (5 domain questions with expected answer + expected source file, committed
  before any retrieval was run).
- **Techniques**: `TokenTextSplitter` (256/40 chunk size/overlap),
  `SemanticSplitterNodeParser` (buffer_size=1), `SentenceWindowNodeParser`
  (window_size=3) — each builds its own in-memory `VectorStoreIndex` over
  `sentence-transformers/all-MiniLM-L6-v2` embeddings (384-dim).
- `rag_compare.retrieve()` is the shared retrieval-only helper: prints the
  query embedding (dim + first 8 values), top-k with store score AND an
  explicitly recomputed cosine similarity (these don't always match exactly —
  see `METRICS.md`), chunk length, preview, and the query/doc vector shapes.
- Full write-up (results table, a confidently-scored miss with an
  explanation, observations, conclusion):
  [`reports/hw03/METRICS.md`](reports/hw03/METRICS.md).

## HW3 Verification

```
python verify_hw03.py
```
Starts the FastAPI app and checks login sets the 3-attribute cookie,
dashboard is reachable with a valid session and unreachable after logout;
builds the token-chunking pipeline over the real corpus and checks it
terminates, returns exactly k=5 results, and produces 384-dim embeddings.
Writes [`reports/hw03/verification.json`](reports/hw03/verification.json).

---

# HW4

HW4 is the biggest jump yet: the domain data moves from the in-memory list
to **MySQL**, a **React** frontend replaces (well, sits alongside) the
server-rendered UI, and Part-5 gains an actual **generation** step on top of
HW3's retrieval-only pipeline. Mapping: **Part-1/** gets the MySQL/session
layer plus the N+1 endpoints (still the same FastAPI service from HW2/HW3,
per the assignment's "keep extending, don't start a new one"); a new
**Part-6/** holds the React client (a genuinely new stack: Node/Vite, not an
extension of anything existing); **Part-5/** gains `rag_qa.py` alongside
HW3's retrieval-only `rag_compare.py`.

## Prerequisite: MySQL (Docker)

No native MySQL is required — a container is enough:
```
docker run -d --name s1808-mysql -e MYSQL_ROOT_PASSWORD=s1808_root_pw -e MYSQL_DATABASE=s1808_rel -p 3307:3306 mysql:8
```
(Port 3307 on the host, not 3306 — this machine already had a native MySQL
service bound to 3306.) Then, once, create the tables and seed a demo user:
```
.venv\Scripts\python.exe Part-1\init_db.py
```

## Part 1 — React Client

Files: [Part-6/src/](Part-6/src/)
```
cd Part-6
npm install
npm run dev
```
Visit `http://localhost:5173`. Talks to the FastAPI backend (below) via
`fetch(..., { credentials: "include" })`; `Login.jsx` / `Home.jsx` /
`CreateRecord.jsx` / `UpdateRecord.jsx` / `DeleteRecord.jsx` map to
`/login`, `/`, `/create`, `/update`, `/delete`. `App.jsx` owns the shared
course list and passes create/update/delete handlers down as props, per the
assignment. Verified end to end with a Playwright-driven headless browser
session (login gating, full CRUD, no console errors) before considering it
done.

## Part 2 — MySQL Persistence and Server-Side Sessions

Files: [Part-1/db.py](Part-1/db.py), [Part-1/models.py](Part-1/models.py),
[Part-1/api_auth.py](Part-1/api_auth.py), [Part-1/api_courses.py](Part-1/api_courses.py)
```
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8008
```
(run from `Part-1/`). Demo login: `advisor@sjsu.edu` / `course123` (POST
`/api/login`). Sessions are real server-side rows in MySQL's `sessions`
table (`db.py`'s session factory is literally named `db_session_basede26`,
per the assignment's exact naming requirement); the browser only ever holds
an opaque token in an `HttpOnly`+`Secure`+`SameSite=lax` cookie, never user
data. `GET/POST/GET-by-id/PUT/DELETE /api/courses` are the CRUD endpoints,
all auth-protected. Schema dump: [`Part-1/migrations/001_create_tables.sql`](Part-1/migrations/001_create_tables.sql).

## Part 3 — N+1 Measurement and Query Tuning

Files: [Part-1/seed_n1.py](Part-1/seed_n1.py), [Part-1/api_n1.py](Part-1/api_n1.py),
[Part-1/run_n1_experiment.py](Part-1/run_n1_experiment.py), [Part-1/explain_index_demo.py](Part-1/explain_index_demo.py)
```
.venv\Scripts\python.exe Part-1\seed_n1.py            # once: 5,000 courses + 200 sections, SEED=1808
.venv\Scripts\python.exe Part-1\run_n1_experiment.py   # 180 requests (3 page sizes x 2 versions x 30)
.venv\Scripts\python.exe Part-1\explain_index_demo.py  # EXPLAIN before/after adding an index
```
`GET /api/n1/naive?page_size=N` issues one query per course (the N+1);
`GET /api/n1/fixed?page_size=N` uses `joinedload` for one query flat,
confirmed empirically (11/51/201 vs. a constant 1). Full results, including
an honest note about a ~2050ms per-request floor on this machine (Docker
Desktop/WSL2 overhead, present in both versions equally) that had to be
netted out to see the real ~2.5ms-per-extra-query N+1 cost:
[`reports/hw04/METRICS.md`](reports/hw04/METRICS.md).

## Part 4 — Grounded RAG Question-Answering

Files: [Part-5/rag_qa.py](Part-5/rag_qa.py), [Part-5/run_rag_qa.py](Part-5/run_rag_qa.py)
```
.venv\Scripts\python.exe Part-5\run_rag_qa.py
```
Reuses HW3's 32-document SJSU corpus (already well over the 5-document
minimum), re-chunked with `TokenTextSplitter(chunk_size=500, chunk_overlap=50)`.
Runs [`reports/hw04/rag_questions.yaml`](reports/hw04/rag_questions.yaml)'s
six questions through three configurations (No-RAG / Basic-RAG /
Context-RAG with relevance filtering, deduplication, source labeling, and
grounding+refusal rules), sweeps `k` in {1, 3, 5} on the two-chunk question,
and scores everything with objective checks. Full results, raw answers, and
the required written analysis: [`reports/hw04/METRICS.md`](reports/hw04/METRICS.md).

## HW4 Verification

```
python verify_hw04.py
```
Checks the backend responds on PORT_BASE, login sets the session cookie, a
MySQL CRUD create/list round-trip works, both `/api/n1` endpoints return
data with naive's query count strictly greater than fixed's, and the RAG
pipeline finishes without hanging and returns a non-empty answer. Writes
[`reports/hw04/verification.json`](reports/hw04/verification.json).

# HW5

Builds on HW4's FastAPI + MySQL backend and React client rather than
starting fresh. Mapping: **Part-1/** gains a second entity (Department) and
tighter validation on Course; **Part-6/** moves its course data layer from
component state to Redux Toolkit; a new **Part-7/** holds everything that's
genuinely new in HW5 -- the two MCP servers, the retry/fault-injection
harness, and `execute_tool` (the Part 5 agent loop lands here too).

## Part 1 — Department Entity, Extended Course API, Redux Client

Files: [Part-1/models.py](Part-1/models.py), [Part-1/api_departments.py](Part-1/api_departments.py),
[Part-1/migrate_hw05.py](Part-1/migrate_hw05.py), [Part-6/src/store.js](Part-6/src/store.js),
[Part-6/src/coursesSlice.js](Part-6/src/coursesSlice.js)
```
.venv\Scripts\python.exe Part-1\migrate_hw05.py   # once: adds departments + Course columns in place
cd Part-6 && npm install && npm run dev
```
Department is the required related entity (name, building, `dept_code`
unique, timestamps); Course gains `department_id` (FK, RESTRICT by
default), `seats_available` (numeric, default 30), timestamps, and a unique
`course_code`. `/api/departments` has full CRUD, pagination, and a
relationship endpoint (`/api/departments/{id}/courses`). The React client's
course state moved from `App.jsx`'s `useState` to Redux Toolkit
(`store.js`/`coursesSlice.js`, axios-based thunks); Update/Delete now take
the record id from the URL (`/update/:id`, `/delete/:id`) instead of an
App-level "selected" prop. Verified with a scripted Playwright run through
the real dev server (login, create, update, delete all round-tripped, no
console errors; the test script and Playwright were removed afterward).

## Part 2 — MCP Tool Servers

Files: [Part-7/meals_server.py](Part-7/meals_server.py), [Part-7/domain_server.py](Part-7/domain_server.py),
[Part-7/envelope.py](Part-7/envelope.py)
```
mcp dev Part-7/meals_server.py     # TheMealDB tutorial server, 4 tools
mcp dev Part-7/domain_server.py    # required domain server, 3 tools
```
The domain server reuses Part-1's SQLAlchemy models directly (no separate
copy of the schema) and returns the shared `{ok, data, error}` envelope
from all three tools (`search_courses`, `course_detail`,
`department_stats` -- search / detail lookup / aggregate). Both servers are
verified two ways: direct Python calls against live data (meals_server
against the real TheMealDB API, domain_server against the real MySQL
database), and `Part-7/inspect_tools.py`, which drives both over the actual
MCP STDIO protocol via the MCP SDK's own client -- the same protocol the
Inspector UI uses -- and saves the raw request/response records to
[`reports/hw05/raw/mcp_inspector_outputs.json`](reports/hw05/raw/mcp_inspector_outputs.json).

## Part 3 — Tool Contracts Under Stress

Files: [Part-7/retry_policy.py](Part-7/retry_policy.py), [Part-7/run_fault_injection.py](Part-7/run_fault_injection.py)
```
.venv\Scripts\python.exe Part-7\run_fault_injection.py
```
`call_with_retry` wraps any callable with a per-attempt timeout (enforced
via a worker thread) and bounded exponential backoff. Demonstrates all
three required scenarios (first-try success, fail-then-retry success,
exhausted retries raising a clean `RetryExhausted` instead of crashing),
then runs the required 150-call fault-injection experiment (3 rates x 50
calls, seeded from `VERIFY_SEED` for reproducibility). Full results and the
interactive-vs-batch retry policy analysis:
[`reports/hw05/METRICS.md`](reports/hw05/METRICS.md).

## Part 4 — One Safe Tool Entry Point and Offline Tests

Files: [Part-7/execute_tool.py](Part-7/execute_tool.py), [Part-7/test_tools.py](Part-7/test_tools.py)
```
.venv\Scripts\python.exe Part-7\test_tools.py
```
`execute_tool(name, inputs)` is the single function Part 5's agent calls;
it reuses the `{ok, data, error}` envelope and a JSON string, and never
raises. The offline test runner builds a temporary in-memory SQLite
database from the same models the real MySQL database uses (dependency
injection via `execute_tool`'s `session=` parameter) so all 8 tests
(6 required + 2 covering `execute_tool`'s own dispatch logic) run without
touching the network, the real database, or an LLM.

## Part 5 — Agent Loop, Safety Rule, and Reflection

Files: [Part-7/execute_tool.py](Part-7/execute_tool.py), [Part-7/agent.py](Part-7/agent.py),
[Part-7/run_agent_scenarios.py](Part-7/run_agent_scenarios.py)
```
.venv\Scripts\python.exe Part-7\run_agent_scenarios.py
```
One safety rule lives inside `execute_tool`: agent calls to `search_courses`
are capped at `limit<=20` (stricter than the 100 a trusted direct caller
gets), so the loop can't pull a huge chunk of the catalogue into its own
context in one call. `run_agent(user_input)` drives a JSON-protocol tool-use
loop against the real local Ollama model (`qwen2.5:1.5b-instruct`, via
Part-4's `ModelClient`) and the three domain tools, with a turn counter and
`max_steps` ceiling, logging every step to
[`reports/hw05/raw/agent_runs.jsonl`](reports/hw05/raw/agent_runs.jsonl).
Four scenarios run against the real model (3 finished normally, 1 hit
`max_steps` after repeatedly tripping the safety rule); full results,
`MockModel`-based offline tests for the safety rule and the `max_steps`
stop, and the required reflection: [`reports/hw05/METRICS.md`](reports/hw05/METRICS.md),
[`reports/hw05/REFLECTION.md`](reports/hw05/REFLECTION.md).

## HW5 Verification

```
python verify_hw05.py
```
Covers all five parts: backend + session + Department CRUD + course
validation, both MCP servers responding over real STDIO, all three
retry-policy scenarios, the Part 5 safety rule + MockModel max_steps stop,
and the full Part 4 offline suite (10/10). Writes
[`reports/hw05/verification.json`](reports/hw05/verification.json).

# HW6

Builds on HW5 again: the FastAPI backend (`Part-1/`) gains a MongoDB
document view alongside its existing MySQL tables, a short/long/episodic
chat-memory system, and (in `Part-4/`, alongside the HW1 `AGENT.md`) a
second, file-based memory system for comparison.

## Prerequisite: MongoDB (Docker)

```
docker run -d --name s1808-mongo -p 27017:27017 mongo:7
.venv\Scripts\python.exe Part-1\init_mongo.py
```

## Part 1 — MongoDB Document API

Files: [Part-1/db_mongo.py](Part-1/db_mongo.py), [Part-1/models_mongo.py](Part-1/models_mongo.py),
[Part-1/api_announcements.py](Part-1/api_announcements.py), [Part-1/init_mongo.py](Part-1/init_mongo.py)

`announcements` is the document-oriented view of the campus course
catalogue domain (course update/enrollment/event notices): `title`
(required, max 100 chars), `description` (optional), `status` (enum,
default `draft`), `category` (enum), `event_date` (required), auto
`created_at`/`updated_at`. Validated twice: Pydantic at the API boundary
and a real MongoDB `$jsonSchema` validator on the collection, confirmed
independently by inserting a bad document straight through `mongosh`.

## Part 2 — Short-, Long-, and Episodic Memory

Files: [Part-1/memory.py](Part-1/memory.py), [Part-1/api_chat.py](Part-1/api_chat.py)
```
.venv\Scripts\python.exe Part-1\run_chat_demo.py
```
`POST /api/chat` saves the message, pulls the last `SHORT_TERM_N` messages,
the latest session/lifetime summaries, and the top-k episodic facts
(cosine similarity over `sentence-transformers/all-MiniLM-L6-v2`
embeddings), and calls the local Ollama model through the HW1
`ModelClient` adapter. A session summary is generated every
`SUMMARIZE_EVERY_USER_MSGS` user messages and condensed into a lifetime
summary once a user has a few of them. `GET /api/memory/{user_id}` and
`GET /api/aggregate/{user_id}` round out the introspection endpoints.

## Part 3 — What Memory Costs

Files: [Part-1/run_memory_experiments.py](Part-1/run_memory_experiments.py)
```
.venv\Scripts\python.exe Part-1\run_memory_experiments.py
```
Runs the same fixed 30-message conversation at `SHORT_TERM_N` = 4, 12, 30,
plus once more at 12 with a short-term message-truncation compression
policy, asking [`reports/hw06/memory_probes.yaml`](reports/hw06/memory_probes.yaml)'s
five fixed questions after each run. Full results and the cost estimate:
[`reports/hw06/METRICS.md`](reports/hw06/METRICS.md).

## Part 4 — File-Based Memory and Consolidation

Files: [Part-4/AGENT.md](Part-4/AGENT.md), [Part-4/MEMORY.md](Part-4/MEMORY.md),
[Part-4/file_memory.py](Part-4/file_memory.py), [Part-4/memory_cli.py](Part-4/memory_cli.py)

`AGENT.md` now covers five categories (project description, tech stack,
coding conventions, testing approach, prohibited actions). `/memory`,
`/compact`, `/dream`, and `/help` are implemented in `memory_cli.py`.
Consolidation went through three real design iterations before landing on
one that actually works reliably on this local 1.5B model; see
`AI_USE.md` and `METRICS.md` for what failed and why.

## HW6 Verification

```
python verify_hw06.py
```
Writes [`reports/hw06/verification.json`](reports/hw06/verification.json).

# HW7

JWT auth + RBAC, a schema-validated agent loop with bounded repair,
Reflexion self-correction, a framework-based bike-share ReAct/MRKL agent,
prompt-injection red-teaming, and file tools with a safety gate.

## Part 1 — JWT Authentication, Role-based authorization, and Linting

Files: [Part-1/jwt_auth.py](Part-1/jwt_auth.py), [Part-1/migrate_hw07.py](Part-1/migrate_hw07.py)

`/api/courses` migrated from HW4's session cookie to JWT bearer auth with
three roles (`reader`, `writer`, `moderator`); HW4's session code stays as
history at the `hw4` tag. Ruff + pre-commit set up at the repo root
(`pyproject.toml`, `.pre-commit-config.yaml`) — the first real commit
attempt was genuinely blocked by 5 real import-order errors.

## Part 2 — Agent Loop with Bounded Repair

Files: [Part-7/agent.py](Part-7/agent.py), [Part-7/tool_schemas.py](Part-7/tool_schemas.py),
[Part-7/run_reliability_test.py](Part-7/run_reliability_test.py)

Extends the HW5 agent loop: an unknown tool or a schema-invalid argument
is reprompted once with the specific problem, then stops cleanly. 20-attempt
reliability run: 90% well-formed before repair, 95% after.

## Part 3 — Reflexion and Bounded Self-Correction

Files: [Part-7/reflexion.py](Part-7/reflexion.py), [Part-7/verifiers.py](Part-7/verifiers.py)

Up to 2 retries, token-budgeted, deterministic per-task verifiers that
check the final answer against that run's own real tool results. Reflections
never touch `SYSTEM_PROMPT` or tool permissions.

## Part 4 — Framework ReAct/MRKL Public-Data Exercise

Files: [Part-8/bikeshare_agent.py](Part-8/bikeshare_agent.py), [Part-8/bikeshare_tools.py](Part-8/bikeshare_tools.py),
[Part-8/ui_server.py](Part-8/ui_server.py)
```
.venv\Scripts\python.exe Part-8\run_scenarios.py
```
`langgraph.prebuilt.create_react_agent` + `ChatOllama` + three real tools
(`csv_sql`, `policy_retriever`, `calculator`) over real public Divvy
(Chicago) trip data and the real Divvy pricing page. See `AI_USE.md` for
why the acceptance-case runs pre-seed the first two tool calls and the
final cost comparison rather than leaving full orchestration to a 1.5B
local model.

## Part 5 — Prompt Injection and Tool Security

Files: [Part-8/run_prompt_injection_test.py](Part-8/run_prompt_injection_test.py),
[Part-8/hostile_fixture/hostile_pricing.html](Part-8/hostile_fixture/hostile_pricing.html)

Threat model in [`reports/hw07/THREAT_MODEL.md`](reports/hw07/THREAT_MODEL.md).
Both defenses (untrusted-data labeling, `csv_sql`'s single-SELECT
enforcement) are already built into Part 4's tools.

## Part 6 — File Tools and a Safety Gate

Files: [Part-9/file_tools.py](Part-9/file_tools.py)

Six file tools plus `SAFE_PREFIXES`, `confirm_bash`, and an independent
`is_destructive` deny-list. 10-command safety-gate test: 5/5 pass, 5/5
blocked, 0 false allows.

## HW7 Verification

```
python verify_hw07.py
```
Writes [`reports/hw07/verification.json`](reports/hw07/verification.json).

## Repository layout
```
Part-1/   index.html, app.js, Dockerfile, nginx.conf, DOMAIN_SCHEMA.md, ecs-task-def.json  (HW1)
          main.py, templates/, static/style.css                                            (HW2)
          auth.py, templates/login.html, templates/dashboard.html, templates/_navbar.html  (HW3)
          db.py, models.py, init_db.py, api_auth.py, api_courses.py, api_n1.py,
          seed_n1.py, run_n1_experiment.py, explain_index_demo.py, migrations/              (HW4)
          api_departments.py, migrate_hw05.py                                               (HW5)
          db_mongo.py, models_mongo.py, api_announcements.py, memory.py, api_chat.py        (HW6)
          jwt_auth.py, migrate_hw07.py                                                      (HW7)
Part-2/   agents_demo.py, sample_input.json                                                 (HW1)
          agent_graph.py, run_schema_experiments.py                                         (HW2)
Part-3/   run_nondeterminism.py  (imports run_pipeline from ../Part-2/agents_demo.py)        (HW1)
Part-4/   hw1_client.py, AGENT.md, smoke_test_conversation.txt, src/model_client.py          (HW1)
          MEMORY.md, file_memory.py, memory_cli.py                                          (HW6)
Part-5/   fetch_corpus.py, corpus/, rag_compare.py, run_retrieval_comparison.py,
          compute_metrics.py                                                                (HW3)
          rag_qa.py, run_rag_qa.py                                                          (HW4)
Part-6/   src/App.jsx, src/Home.jsx, src/Login.jsx, src/CreateRecord.jsx,
          src/UpdateRecord.jsx, src/DeleteRecord.jsx, src/AuthContext.jsx, src/api.js        (HW4)
          src/store.js, src/coursesSlice.js, src/axiosClient.js                             (HW5)
Part-7/   meals_server.py, domain_server.py, envelope.py, retry_policy.py,
          run_fault_injection.py, execute_tool.py, test_tools.py, inspect_tools.py,
          agent.py, run_agent_scenarios.py                                                   (HW5)
          tool_schemas.py, hw07_tasks.py, run_verification_tasks.py,
          run_reliability_test.py, reflexion.py, verifiers.py,
          run_reflexion_compare.py                                                           (HW7)
Part-8/   bikeshare_tools.py, bikeshare_agent.py, build_scenarios.py, run_scenarios.py,
          run_prompt_injection_test.py, ui_server.py, ui_static/, hostile_fixture/,
          pricing_snapshots/, data/                                                          (HW7)
Part-9/   file_tools.py, run_integration_test.py, run_safety_gate_test.py                     (HW7)
requirements.txt, verify_hw01.py, verify_hw02.py, verify_hw03.py, verify_hw04.py,
verify_hw05.py, verify_hw06.py, verify_hw07.py, pyproject.toml,
.pre-commit-config.yaml                                                           — shared, repo root
reports/hw01/, reports/hw02/, reports/hw03/, reports/hw04/, reports/hw05/,
reports/hw06/, reports/hw07/                                                      — deliverables per assignment spec
```
