# HW7 AI Use Statement

### 1. What I used an AI assistant for, and what I did myself

I used Claude Code to design and write the JWT auth/RBAC migration, the
schema-validated agent loop and its 20-attempt reliability harness, the
Reflexion self-correction loop and its deterministic verifiers, the
framework-based (langgraph) bike-share ReAct/MRKL agent and its three
tools, the prompt-injection attack harness, and the file tools/safety
gate. It ran everything against real infrastructure: the real MySQL
container, the real local Ollama model, real downloaded public Divvy
trip data, and the real Divvy pricing page.

What I did myself: decided which domain routes to migrate to JWT and
which roles map to which operations, picked the two real Divvy months
(January vs. July 2024) for the two bike-share scenarios specifically
for their seasonal contrast, decided how to resolve the tension between
"CSV needs ≥500 rows" and "one scenario needs few/short rides" (stated
usage frequency in the prompt, real trip data from csv_sql only for
duration-pattern context — not literally treating every CSV row as one
rider's personal trip), wrote the three attacker goals and their
success conditions by hand, and reviewed every real run's output rather
than accepting a "PASS" label at face value (see Q2 below for two cases
where that review caught a real problem).

### 2. One AI-produced output that was wrong/unsuitable

Three, all caught by reading real run output rather than trusting a
summary or a "stop_reason=normal_completion" label at face value.

First: the original `csv_sql` schema had no duration column (Divvy's raw
export only has `started_at`/`ended_at`), and the first live run of
Part 4's acceptance scenarios showed the model reliably guessing a
`duration` column into existence (`SELECT AVG(duration)`), getting a
real SQL error, and giving up after one tool call instead of recovering.

Second, and more serious: even after fixing the schema and giving the
model an explicit, directive step-by-step system prompt (call csv_sql,
then policy_retriever, then calculator, in that order), live runs showed
it skipping tools anyway — one run went completely off-topic (a generic
"how to clean a pandas dataframe" answer to a bike-share membership
question), another invented a `$120` membership price instead of ever
calling `policy_retriever`. After pre-seeding the first two tool calls
(running them for real in code and injecting the genuine results as
already-executed tool-call/observation pairs, so the model only had to
synthesize an answer from real grounded numbers), the model STILL got
the final arithmetic comparison backwards: given the correct real
numbers $7.80 (pay-per-use) and $11.99 (membership) directly in its
context, it wrote "$11.99 is lower than $7.80" and concluded "Buy
Monthly Membership" — the wrong decision for that scenario, stated with
complete confidence next to the correct numbers.

Third: Part 3's Task-A verifier (string-matches the course code
`"DATA-00006"` in the final answer) rejected an answer that correctly
described the right course by title and department but never restated
its code — a real false rejection, not a model failure.

### 3. How I detected the problem

For the duration-column bug: read the actual tool-call timeline saved in
`bikeshare_pay_per_use.json`, not just the printed final answer — it
showed exactly one `csv_sql` call with a real `sqlite3` error
(`no such column: duration`) immediately followed by the agent giving
up. For the tool-skipping and backwards-comparison bugs: same approach,
read the full timeline and the literal final-answer text for each real
run rather than skimming for a plausible-looking paragraph — the
backwards comparison in particular would have been easy to miss if I'd
only checked "did it give an answer with a decision in it" instead of
checking whether that decision was arithmetically consistent with the
numbers it just cited. For the verifier false rejection: read the
Reflexion comparison log's reflection text and the actual final answer
side by side and noticed the verifier's failure reason didn't match what
the answer actually said.

### 4. What I changed and why it works now

For the duration bug: `CsvSqlEngine._load_csv` now precomputes a real
`duration_min` column from `started_at`/`ended_at` at load time (legitimate
ETL, not a prompt hack), and the system prompt lists the exact real
column names and the exact real `rideable_type` values instead of
leaving the schema for the model to guess.

For tool-skipping and the backwards comparison: `run_bikeshare_agent`
gained a `preseed_grounding_calls` path (on by default for Part 4's
acceptance runs, off for Part 5's injection test, which needs the model
to receive a live, possibly-hostile tool result itself). `csv_sql` and
`policy_retriever` are called for real, in code, and their real results
are injected as genuine executed tool-call/observation pairs before the
model's first turn. Once the backwards-comparison failure showed up even
with real numbers already in context, I stopped asking the model to
compare two numbers at all: the comparison is done in code
(`pay_per_use_value < membership_value`), and the model is told the
already-determined decision string and instructed not to recompute or
contradict it — its job is reduced to templating a justification, cost
breakdown, and caveats around numbers and a conclusion it no longer has
to derive itself. This is a real, load-bearing design choice: a 1.5B
local model reliably produces fluent, well-structured prose, and
unreliably does multi-step tool orchestration and even basic numeric
comparison, so the tools are still real (every number cited is genuinely
computed by `csv_sql`/`policy_retriever`/`calculator`) but the
*sequencing and comparison* that this specific model couldn't be trusted
with were moved out of its hands. Both acceptance scenarios now give the
correct decision (pay-per-use wins at 3 rides/month, membership wins at
40) with real cited numbers.

For the verifier: documented honestly in METRICS.md's Part 3 section
rather than loosened after the fact, since the assignment specifically
asks for a written note on any verifier false rejection — changing the
verifier's matching rule once I saw the failure it caused would have
hidden the exact case the assignment wants surfaced.
