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

Two, both caught by reading real run output rather than trusting a
summary. First: the original `csv_sql` schema had no duration column
(Divvy's raw export only has `started_at`/`ended_at`), and the first
live run of Part 4's acceptance scenarios showed the model reliably
guessing a `duration` column into existence (`SELECT AVG(duration)`),
getting a real SQL error, and giving up after one tool call instead of
recovering. Second: Part 3's Task-A verifier (string-matches the course
code `"DATA-00006"` in the final answer) rejected an answer that
correctly described the right course by title and department but never
restated its code — a real false rejection, not a model failure.

### 3. How I detected the problem

For the duration-column bug: I read the actual tool-call timeline saved
in `bikeshare_pay_per_use.json`, not just the printed final answer — it
showed exactly one `csv_sql` call with a real `sqlite3` error
(`no such column: duration`) immediately followed by the agent giving
up. For the verifier false rejection: I read the Reflexion comparison
log's reflection text and the actual final answer side by side and
noticed the verifier's failure reason ("does not mention 'DATA-00006'")
didn't match what the answer actually said, which was correct in
substance.

### 4. What I changed and why it works now

For the duration bug: `CsvSqlEngine._load_csv` now precomputes a real
`duration_min` column from `started_at`/`ended_at` at load time (not a
prompt hack — legitimate ETL, the same thing a real data pipeline would
do), and the agent's system prompt now lists the exact real column
names including `duration_min` instead of leaving the schema for the
model to guess. Re-running Part 4's scenarios with this fix is what
produced the real cost breakdowns in METRICS.md rather than the earlier
apology-and-give-up failure.

For the verifier: documented honestly in METRICS.md's Part 3 section
rather than loosened after the fact, since the assignment specifically
asks for a written note on any verifier false rejection — changing the
verifier's matching rule once I saw the failure it caused would have
hidden the exact case the assignment wants surfaced.
