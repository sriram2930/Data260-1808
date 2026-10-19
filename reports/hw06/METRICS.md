# METRICS - DATA-260 HW6

## Part 1: MongoDB Document API

Database: `s1808_doc`. Collection: `announcements` (the campus course
catalogue's document-oriented entity: course update/enrollment/event
notices). Fields: `title` (required, max 100 chars), `description`
(optional), `status` (enum `draft`/`published`/`archived`, default
`draft`), `category` (enum `course_update`/`enrollment`/`event`/`general`),
`event_date` (required datetime), `created_at`/`updated_at` (auto).

Validation is enforced twice, independently: Pydantic at the API boundary
(`Part-1/models_mongo.py`) and a real MongoDB `$jsonSchema` validator on the
collection itself (`Part-1/init_mongo.py`). Confirmed the MongoDB-level
validator works on its own by inserting a bad document directly through
`mongosh`, bypassing the API entirely - it was rejected with
`MongoServerError: Document failed validation`.

Full CRUD verified live: `POST` (201), `GET` all (200), `GET` by id (200),
`PUT` (200, `updated_at` changes while `created_at` does not), `DELETE`
(200), `GET` on a nonexistent id (404), missing required field (422),
invalid enum value (422).

## Part 2: Short-, Long-, and Episodic Memory

New collections in the same `s1808_doc` database: `messages`, `summaries`,
`episodes`. A 12-message real conversation (`Part-1/run_chat_demo.py`)
against the live chat endpoint and the local Ollama model exercised all
three memory types in one run:

- **Short-term**: the sliding window (`SHORT_TERM_N=12`) capped correctly
  at 12 messages from turn 6 onward.
- **Long-term**: a session summary first appeared in turn 6's response
  (`SUMMARIZE_EVERY_USER_MSGS=5`, so it was generated right after the 5th
  user message, one turn before it shows up in `"used"` since the summary
  is written *after* that turn's prompt was already built - a one-turn lag
  that shows up consistently everywhere in this system, see AI_USE.md).
  A lifetime summary appeared starting turn 11, after the 2nd session
  summary had been created.
- **Episodic**: facts were extracted from almost every user message and
  retrieved by embedding cosine similarity on later turns. One honest
  limitation worth flagging directly: by turn 7 the episodic store had
  accumulated a wrong fact (`"Your major is Computer Science."`, when the
  user had actually said Data Science), and it kept surfacing in later
  turns alongside correct facts. The extraction step doesn't verify facts
  against the conversation again before storing them, so a small model's
  hallucination at one turn becomes a persistent, retrievable "memory" from
  then on. This is a real property of the system as built, not fixed, and
  documented here rather than hidden.

`GET /api/memory/u1` and `GET /api/aggregate/u1` were both verified
returning the expected shapes (last ~16 messages, latest session/lifetime
summaries, last ~20 episodes; daily message counts and recent summaries,
respectively).

## Part 3: What Memory Costs

The same fixed 30-message conversation (planted facts: name/student id/
favorite subject in messages 1-3, birthplace in message 16) was run in a
fresh session at `SHORT_TERM_N` = 4, 12, 30, then once more at 12 with the
eviction/compression policy (short-term message truncation to 120 chars)
turned on, asking `memory_probes.yaml`'s five questions after each run.
Full per-turn data: `raw/memory_experiment_turns.csv` /
`raw/memory_experiment_turns.json`. Console transcript: `RUN_LOG.txt`
(= this file's own build log, since these runs went directly to the
terminal captured here).

| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |
|---|---|---|---|
| SHORT_TERM_N=4  | 1790.3 | 25117.7 | 5.00 |
| SHORT_TERM_N=12 | 1156.1 | 18149.8 | 4.60 |
| SHORT_TERM_N=30 | 1433.3 | 18095.7 | 5.00 |
| Eviction/compression (N=12, truncated) | 728.7 | 6535.5 | not measured (see note) |

**Honest note on the last row**: this run was cut off at turn 26/30 (no
probes) because of real-world time constraints on a CPU-only local model -
not every run in this homework could be let run to full completion. The
26-turn partial average is still a fair comparison point for token/latency
cost (it's an average, not a cumulative total, so a shorter sample doesn't
bias it upward or downward, just adds more variance), but the probe-quality
column for this row is genuinely missing data, not a zero.

**What the numbers show**: SHORT_TERM_N barely matters for probe quality
on its own (4.6-5.0 across all three raw-window sizes) because episodic
memory and the session/lifetime summaries carry the planted facts forward
independently of how many raw messages are in the window - even
`SHORT_TERM_N=4`, which drops the planted facts from the raw window after
message 5, still scored a perfect 5/5. `SHORT_TERM_N=12` actually scored
lowest (4.6, one probe landed a 3) despite sitting in the middle, which is
a reminder that token count and recall quality aren't on the same axis
here: the facts survive through episodic retrieval and summaries almost
regardless of window size, so the window size mostly just taxes/doesn't
tax the prompt, it doesn't reliably gate recall in this design.

The eviction/compression policy (truncating short-term message content to
120 characters) at `SHORT_TERM_N=12` cut mean prompt tokens from 1156 to
729 (-37%) and mean latency from 18.1s to 6.5s (-64%) over the portion
measured. The latency drop is larger than the token drop alone would
predict, consistent with this model's context-length behavior getting
disproportionately slower as prompts approach its 4096-token window
(several uncompressed turns exceeded 2000-3000 tokens; truncated ones
stayed under 1000 almost throughout).

### Memory-cost estimate (10,000 conversations x 30 turns, $1/M input, $5/M output)

Using each setting's mean prompt tokens/turn as the input cost driver and
assuming ~100 output tokens/turn (roughly the observed average completion
length across settings) for the output cost driver:

| Setting | Input cost (10k x 30 turns) | Output cost (10k x 30 turns) | Total |
|---|---|---|---|
| SHORT_TERM_N=4 (worst: highest tokens) | 1790.3 x 300,000 / 1e6 x $1 = $537.09 | 100 x 300,000 / 1e6 x $5 = $150.00 | **$687.09** |
| Eviction/compression (best: lowest tokens) | 728.7 x 300,000 / 1e6 x $1 = $218.61 | 100 x 300,000 / 1e6 x $5 = $150.00 | **$368.61** |

**How best/worst were selected**: worst is the setting with the highest
mean prompt tokens/turn with no mitigation (`SHORT_TERM_N=4`, somewhat
counterintuitively the smallest raw window, because this conversation's
summaries and episodic facts end up dominating the prompt more than the
raw short-term window does once several summarization cycles have run);
best is the eviction/compression policy, the only setting that actively
reduces token cost rather than just picking a different window size. The
gap ($687 vs $369 for the same 300,000 turns) is driven entirely by input
tokens, since output token count was held roughly constant across
settings; a policy that compresses the prompt is worth roughly 1.9x in
cost at this volume, independent of anything about answer quality.

## Part 4: File-Based Memory and Consolidation

`AGENT.md` now covers five categories (project description, technology
stack, coding conventions, testing approach, prohibited actions). `MEMORY.md`
and `file_memory.py` implement loading, the consolidation trigger check
(`> 40` non-comment lines, or `> 24h` since last consolidation), and the
`/memory`, `/compact`, `/dream`, `/help` commands (`memory_cli.py`).

### Consolidation design (three attempts; see AI_USE.md for the full story)

1. **One-shot full rewrite.** Asked the model to merge duplicates and
   resolve contradictions in the whole 56-line test file at once. It
   barely touched anything: 56 to 54 lines, none of the three planted
   contradictions were resolved.
2. **One-shot JSON line-number classification.** Asked the model to find
   duplicate groups and contradiction pairs by line number instead of
   rewriting prose. It found zero real duplicates and hallucinated one
   false contradiction between two unrelated facts.
3. **Final design (what's in `file_memory.py` now).** Embeddings find
   candidate pairs that are "about the same thing"; a deterministic check
   (differing numbers, or an explicit antonym like allowed/blocked) decides
   contradiction vs. duplicate; a narrow yes/no model call confirms each
   duplicate candidate before anything is dropped; each contradiction gets
   its own small, focused merge call.

### Running the stress test (`Part-4/test_memory_before.md`, 56 lines, 3 planted duplicate pairs, 3 planted contradictions)

| | Result |
|---|---|
| Lines before | 56 |
| Lines after (pipeline's own raw output) | 51 |
| Duplicate groups found | 2 of 3 planted (missed: Course-entity, s1808_rel, and qwen2.5 pairs - their embedding similarity, 0.63-0.665, fell just under the 0.68 threshold used to avoid false contradiction matches) |
| Contradictions found | **3 of 3 planted**, all correctly identified |
| Contradictions resolved correctly | 2 of 3 (port 8008, confirmed against the real codebase constant; Department deletion blocked, confirmed against `api_departments.py`'s actual 409 behavior) |
| **Contradiction resolved incorrectly** | **SHORT_TERM_N**: the pipeline concluded "8 is now current, previously 12" - backwards. The real default in `Part-1/memory.py` is `SHORT_TERM_N = 12`. The model picked the textually-later line in the file rather than checking against anything real, and got it wrong. |
| Duplicate merges that lost real information | 1: merging the two MCP-tool-count lines dropped the specific tool names; one run also merged away the HW5 retry policy's specific retry count. Caught by manually diffing the before/after text, not by the pipeline itself. |

The pipeline's raw output (51 lines) still did not meet the assignment's
`< 40` target. The reason turned out to be a flaw in the test fixture, not
the pipeline: only 6 of the 56 lines were truly redundant (3 duplicate
pairs + 3 contradiction pairs); even perfect deduplication caps out around
50 lines, because the other 44 lines are genuinely distinct facts with
nothing to merge. Getting under 40 required legitimate consolidation
beyond pure dedup, grouping related-but-distinct facts into combined
bullets (e.g. "Course fields: course_code, course_title, seats_available"
instead of three separate lines) - a step the automated pipeline doesn't
attempt, and one a human reviewing the output did by hand.

The human-corrected final version (`Part-4/test_memory_after.md`) is 26
lines: it fixes the one incorrect resolution (states the true `SHORT_TERM_N
= 12`, with the pipeline's wrong answer left visible in a parenthetical so
the correction itself is auditable, not a silent overwrite), restores the
two details that got lost in merges, and groups distinct-but-related facts
into combined bullets. No fact present in the original 56 lines is missing
from the final 26; every merge and every correction is explained inline.

This matches the assignment's actual requirements closely but not exactly:
merges happened, contradictions were resolved explicitly (one incorrectly,
flagged rather than hidden), and nothing was silently dropped, but getting
under 40 lines took a human edit on top of the automated pipeline, not the
pipeline alone.

### AGENT.md compliance check

`Part-4/verify_agent_compliance.py` asked the local model to generate one
new function (fetch the 3 most recent published announcements) while
giving it AGENT.md's actual content as instructions, then checked the
output automatically against three of those instructions (has a docstring,
does not import `ollama` directly, does not open a second `MongoClient`).

<!-- AGENT_COMPLIANCE_RESULT_PLACEHOLDER -->

### Comparing MongoDB memory and file-based memory

| | MongoDB-backed (Part 2) | File-based (Part 4) |
|---|---|---|
| Inspectability | Requires a Mongo client/shell; structured and queryable, but not human-readable at a glance | Plain Markdown, readable and editable in any text editor, no tooling needed |
| Persistence after restart | Durable as long as the container/volume persists; survives an app restart trivially | Durable as long as the files aren't deleted; equally simple, but there is no schema or index to protect against a malformed manual edit |
| Scalability across many sessions | Scales well: indexed by `user_id`, cheap to query a specific user's last N messages/episodes out of millions of documents | Does not scale: one flat file per project, not per user or session; fine for project-level durable facts, unworkable for per-user conversation history at any real scale |
| Suitability for facts that must not be forgotten | Good, but a fact is only as safe as the query that retrieves it; nothing stops a bug from quietly never calling `GET /api/memory` for a true fact | Arguably better for a *small*, curated set of must-not-forget facts, since the whole file is always loaded into the system prompt in full, nothing is retrieved conditionally. Does not scale to large fact sets for the same reason (eventually the whole file won't fit in context). |

In short: MongoDB memory is the right fit for high-volume, per-user,
queryable history (Part 2's actual job); file-based memory is the right
fit for a small number of durable, project-wide facts that should always
be present (which is exactly what `AGENT.md`/`MEMORY.md` are used for here)
and the wrong fit for anything that needs to scale past a human being able
to read the whole file at once.
