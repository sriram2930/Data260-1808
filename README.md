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

## Repository layout
```
Part-1/   index.html, app.js, Dockerfile, nginx.conf, DOMAIN_SCHEMA.md, ecs-task-def.json  (HW1)
          main.py, templates/, static/style.css                                            (HW2)
Part-2/   agents_demo.py, sample_input.json                                                 (HW1)
          agent_graph.py, run_schema_experiments.py                                         (HW2)
Part-3/   run_nondeterminism.py  (imports run_pipeline from ../Part-2/agents_demo.py)        (HW1)
Part-4/   hw1_client.py, AGENT.md, smoke_test_conversation.txt, src/model_client.py          (HW1)
requirements.txt, verify_hw01.py, verify_hw02.py   — shared, repo root
reports/hw01/, reports/hw02/                       — deliverables per assignment spec
```
