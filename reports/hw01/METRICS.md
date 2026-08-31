# METRICS — DATA-260 HW1

**PREFIX:** s1808 · **SEED:** 1808 · **Model:** `qwen2.5:1.5b-instruct` (substituted for the
spec default `qwen3:8b` — this machine has no dedicated GPU, integrated Iris Xe graphics,
16GB RAM; a 1.5B model keeps the 80-call Part 3 batch practical on CPU-only inference).

Fixed input used for all 40 runs: [`reports/hw01/cases/nondeterminism_input.json`](cases/nondeterminism_input.json)
(a `Course` entity — title + description — from the assigned domain, Campus course
catalogue and enrolment).

Command run:
```
.venv\Scripts\python.exe run_nondeterminism.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part3.txt
```

Raw per-run data (all 40 runs, tags + latency): [`raw/nondeterminism_runs.csv`](raw/nondeterminism_runs.csv),
[`raw/nondeterminism_runs.json`](raw/nondeterminism_runs.json). Aggregate summary:
[`raw/nondeterminism_summary.json`](raw/nondeterminism_summary.json). Full console
transcript with real timestamps: [`RUN_LOG_part3.txt`](RUN_LOG_part3.txt).

A "tag set" is compared order-independently and case-insensitively (e.g. `["Data
Pipelines", "pipeline design"]` and `["pipeline design", "data pipelines"]` count as
the same set) — the experiment is measuring semantic/topical consistency, not the
order or capitalization the model happened to print tags in.

## Part 3 — Non-Determinism Results (20 runs per temperature)

| Metric | Temp 0.7 | Temp 0.0 |
|---|---|---|
| Distinct tag sets (out of 20) | **10** | **1** |
| Tags in all 20 runs | *(none)* | `data pipelines`, `data systems`, `machine learning` |
| Tags in exactly 1 run | `data management`, `ingestion`, `machine learning pipelines`, `pipelining` | *(none)* |

| Latency (ms) | Temp 0.7 | Temp 0.0 |
|---|---|---|
| p50 | 8076.6 | 7116.5 |
| p95 | 12253.8 | 7511.0 |
| p99 | 16409.7 | 7671.5 |

### What two users sending identical input might see

At **temperature 0.0**, two users submitting the exact same course title and
description would see **the same 3 tags every single time** — all 20 runs produced
an identical tag set (`data pipelines`, `data systems`, `machine learning`), and
latency was also the tightest and most predictable of the two settings (p50→p99
spans only ~550ms). The pipeline behaves like a deterministic function of its input.

At **temperature 0.7**, two users submitting the identical input could very
plausibly see **completely different tag sets** — 10 distinct tag sets appeared
across only 20 runs (half the runs produced a tag combination no other run
produced), and there was **no tag that appeared in all 20 runs at all**. So there
is no "core" tag either user is guaranteed to see; the closest thing to a stable
signal is that near-synonyms of "machine learning," "data pipelines," and "data
systems" recur under slightly different wording (e.g. "data-pipelines" vs
"pipeline design" vs "pipelining"), but the exact strings are not reproducible.
Latency is also both higher and more variable at temp 0.7 (p50 8.1s vs 7.1s; p99
16.4s vs 7.7s), since sampling occasionally leads the model down a longer
generation path.

### Where run-to-run variation is acceptable vs. not

- **Acceptable**: a "suggested tags" feature shown to a course-catalogue submitter
  while they draft a listing, purely to speed up manual tagging. If temp 0.7
  suggests `pipeline design` on one attempt and `pipelining` on a retry, the
  submitter just picks (or edits) whichever reads better — the variation is
  invisible to anyone but the one person interacting with it, and no other part
  of the system depends on the exact string.

- **Not acceptable**: using these tags as a stable key elsewhere in the system —
  e.g. a prerequisite-matching or search-index feature that groups courses by
  tag string. If the same course could be filed under `machine learning
  pipelines` today and `data-pipelines` tomorrow purely from re-running the
  pipeline, two students querying "show me courses tagged X" at different times
  would get different results for input that never changed, and any code that
  assumes tags are a stable identifier (not just a display hint) would silently
  break. For that use case, temperature 0.0 — or an equivalent deterministic/
  canonicalized tagging step — is the only defensible choice.

## Part 4 — Model Client and Token Accounting

Command run:
```
Get-Content smoke_test_conversation.txt | .venv\Scripts\python.exe hw1_client.py | Tee-Object -FilePath reports\hw01\RUN_LOG_part4.txt
```
Full transcript: [`RUN_LOG_part4.txt`](RUN_LOG_part4.txt). AGENT.md (the bullet-only
code-review contract) is loaded as the system prompt every run: [`../../AGENT.md`](../../AGENT.md).

### Per-turn token counts (5-turn conversation)

| Turn | User message (summary) | Input tokens | Output tokens | Total tokens |
|---|---|---|---|---|
| 1 | review `divide(a, b)` | 217 | 105 | 322 |
| 2 | review `get_first(lst)` | 346 | 88 | 434 |
| 3 | tags for a relational-databases course (not a code review) | 455 | 17 | 472 |
| 4 | review `add(a, b)` | 496 | 105 | 601 |
| 5 | closing remark (not a code review) | 618 | 6 | 624 |

### `/stats` snapshots

| | After turn 3 | After turn 5 |
|---|---|---|
| Turn count | 3 | 5 |
| Cumulative input tokens | 1018 | 2132 |
| Cumulative output tokens | 210 | 321 |
| Cumulative total tokens | 1228 | 2453 |
| Serialized conversation-history length (chars) | 2335 | 3082 |

On exit: cumulative input tokens **2132**, cumulative output tokens **321**, turn
count **5** — matching the final `/stats` call exactly, confirming `/stats` reads
the same running totals without altering them.

### AGENT.md compliance check ("verify the model actually follows it")

**Partially followed.** Across two separate runs (an earlier smoke test and this
official run), the model reliably used bullet points for every code-review
response — but its handling of the "no issues -> single bullet" and "non-review
question -> plain prose" rules was inconsistent:
- In the smoke test, turn 1 and turn 4 each ended with a spurious `**No issues
  found.**` line appended *after* a list of real issues already found — directly
  contradicting both "no prose outside bullets" and "only say no issues found
  when there are none."
- In this official run, turn 5 (a plain closing remark, not a code review request)
  was answered with a single bullet `- No issues found.` instead of the plain
  prose the contract calls for on non-review questions — the bullet-only habit
  leaked into an unrelated turn.
- Turn 3 (a non-review "what tags would you use" question) was answered as a
  bare bullet list in both runs — arguably reasonable formatting on its own
  merits, but again not the "plain prose" the contract specifies for non-review
  turns.

So the model follows the letter of "use bullets for code review" fairly reliably,
but does not reliably distinguish *when* the bullet-only rule should and
shouldn't apply — a real limitation worth calling out rather than claiming full
compliance.

### Report / README questions

**Why is prior conversation context resent with every turn?**
The model itself is stateless between API calls — Ollama (like most LLM serving
layers) has no memory of earlier requests. Everything the model "knows" about the
conversation has to be included in the `messages` list of the current call, so the
client must resend the full history (system prompt + every prior user/assistant
message) each turn or the model would have no idea what was discussed before.

**How is a system prompt different from a user message?**
A system message (`role: "system"`) is a standing instruction that configures the
model's behavior for the whole conversation — here, `AGENT.md`'s bullet-only
review contract — and is set once, not something a person said. A user message
(`role: "user"`) is the actual live input for that turn, changes every turn, and
is what the model is meant to be responding to. Models are generally trained to
treat the system role as higher-priority/standing configuration rather than
conversational content to respond to directly.

**Why do input tokens grow over a conversation?**
Because the entire growing history is resent every turn. The table above shows
this directly: turn 1's input was 217 tokens (system prompt + turn 1's message
only), but by turn 5 the input was 618 tokens — every prior user message and every
prior assistant response is now part of what gets resent, so input size grows
roughly monotonically with turn count.

**What eventually limits that growth?**
The model's context window — a fixed maximum number of tokens it can accept in a
single call (set by the model architecture/config, independent of any one
conversation). Once system prompt + full history + the new message would exceed
that limit, something has to give: older turns get truncated or summarized out of
the history, or the call fails outright. Some deployments add their own smaller
caps (max turns, max cost per session) well before hitting the model's hard
context limit.
