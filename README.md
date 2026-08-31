# data260-1808 — DATA-260 Homework Repository

This repository is extended for every DATA-260 homework this semester.

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

Files: [index.html](index.html), [app.js](app.js), [DOMAIN_SCHEMA.md](DOMAIN_SCHEMA.md)

### Run without Docker (quick check)
```
python -m http.server 8008
```
then visit `http://localhost:8008`.

### Run with Docker (local)
```
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
4. **Task Definition** — see [`ecs-task-def.json`](ecs-task-def.json): family
   `s1808-hw1-task`, Fargate, Linux/X86_64, 0.25 vCPU / 0.5 GB, execution role
   `ecsTaskExecutionRole` (created manually — didn't exist on this fresh
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

Files: [agents_demo.py](agents_demo.py), [sample_input.json](sample_input.json)

### Setup
Requires Python 3.11/3.12 (not 3.13+) and Ollama running locally with a model pulled.
```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen2.5:1.5b-instruct
```

### Run
```
.venv\Scripts\python agents_demo.py --input-file sample_input.json --temperature 0.7
```
or with inline text:
```
.venv\Scripts\python agents_demo.py --title "..." --content "..." --temperature 0.7
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

Files: [run_nondeterminism.py](run_nondeterminism.py), [reports/hw01/cases/nondeterminism_input.json](reports/hw01/cases/nondeterminism_input.json)

```
.venv\Scripts\python.exe run_nondeterminism.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part3.txt
```
Runs the pipeline 20× at temperature 0.7 and 20× at temperature 0.0 on the
fixed input, writing raw rows + summary metrics to `reports/hw01/raw/`. Full
results tables and write-up: [`reports/hw01/METRICS.md`](reports/hw01/METRICS.md).

> Note: Windows PowerShell 5.1's `Tee-Object`/`Out-File` default to UTF-16.
> Re-save any regenerated log as UTF-8 with:
> `Get-Content -Raw -Encoding Unicode <file> | Set-Content -Encoding utf8 <file>`

---

## Part 4 — Model Client and Token Accounting

Files: [src/model_client.py](src/model_client.py), [hw1_client.py](hw1_client.py), [AGENT.md](AGENT.md)

```
.venv\Scripts\python.exe hw1_client.py
```
A small interactive CLI chat built on `src/model_client.py`'s
`ModelClient.complete(messages, tools=None)` adapter — the one interface all
model calls in this file go through. Loads `AGENT.md` (a strict bullet-only
code-review contract) as the system prompt. After every model response it
prints that turn's input/output/total tokens; `/stats` shows cumulative turn
count, cumulative token counts, and serialized conversation-history length
without altering the history; on exit it prints cumulative totals.

To reproduce the exact 5-turn conversation used for the report:
```
Get-Content smoke_test_conversation.txt | .venv\Scripts\python.exe hw1_client.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part4.txt
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

## Verification

```
python verify_hw01.py
```
Runs a self-check (required files present, Python version, `index.html`/`app.js`
contain the required elements/patterns, Ollama reachable with the target model
pulled, non-determinism raw data well-formed) and writes
[`reports/hw01/verification.json`](reports/hw01/verification.json).

## Repository layout
```
index.html, app.js, Dockerfile, nginx.conf   — Part 1 app
DOMAIN_SCHEMA.md                             — Part 1, written before coding
agents_demo.py, sample_input.json            — Part 2
run_nondeterminism.py                        — Part 3 driver (reuses agents_demo.run_pipeline)
src/model_client.py                          — Part 4 model adapter
hw1_client.py, AGENT.md                      — Part 4 CLI demo
smoke_test_conversation.txt                  — reproducible 5-turn script for Part 4
ecs-task-def.json                            — ECS task definition used for AWS deployment
reports/hw01/                                — all HW1 deliverables (see assignment spec)
```
