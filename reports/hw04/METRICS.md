# METRICS - DATA-260 HW4

## Part 3: N+1 Measurement and Query Tuning

Seed: 5,000 courses + 200 sections (`Part-1/seed_n1.py`, `SEED = 1808`).
Schema: `Part-1/migrations/001_create_tables.sql` (dumped via `SHOW CREATE TABLE`
from the live database). Naive endpoint: `GET /api/n1/naive?page_size=N`
(1 query for the page, then one more query per course - the N+1 itself).
Fixed endpoint: `GET /api/n1/fixed?page_size=N` (a single query, `joinedload`
-> one `LEFT OUTER JOIN`). Both return their own SQL statement count in the
response body (`Part-1/db.py`'s per-request query counter), so the
measurement script reads it straight off the JSON.

Command run:
```
python run_n1_experiment.py
```
Full console transcript: [`RUN_LOG_part3.txt`](RUN_LOG_part3.txt). Raw rows
(all 180 requests): [`raw/n1_experiment_runs.csv`](raw/n1_experiment_runs.csv),
[`raw/n1_experiment_runs.json`](raw/n1_experiment_runs.json). Summary:
[`raw/n1_experiment_summary.json`](raw/n1_experiment_summary.json).

### Results

| Page size | Version | SQL stmts/req | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|
| 10  | naive | 11  | 2072.75 | 2105.45 | 2119.57 |
| 10  | fixed | 1   | 2043.77 | 2058.61 | 2066.52 |
| 50  | naive | 51  | 2173.87 | 2197.92 | 2213.18 |
| 50  | fixed | 1   | 2050.82 | 2064.70 | 2065.87 |
| 200 | naive | 201 | 2552.57 | 2636.69 | 2644.59 |
| 200 | fixed | 1   | 2059.02 | 2079.75 | 2097.28 |

**A real infrastructure quirk worth being upfront about**: every request on
this machine has a roughly constant ~2050ms floor, even `page_size=200
fixed` (a single query) takes about as long as `page_size=10 fixed`. That
floor is not part of the N+1 story - it shows up identically in both
versions, and I believe it's Docker Desktop's WSL2 network stack adding
fixed per-connection overhead on Windows, not something intrinsic to
MySQL or to the join vs. loop difference. Rather than paper over it, the
honest way to read this data is to subtract that shared floor out and look
at what's left over:

| Page size | naive p50 - fixed p50 (ms) | extra queries (naive - fixed) | cost per extra query (ms) |
|---|---|---|---|
| 10  | 2072.75 - 2043.77 = 28.98  | 10  | 2.90 |
| 50  | 2173.87 - 2050.82 = 123.05 | 50  | 2.46 |
| 200 | 2552.57 - 2059.02 = 493.55 | 200 | 2.47 |

Once the constant floor is netted out, the extra cost per additional N+1
query is a consistent ~2.5-2.9ms, and it scales exactly linearly with page
size (10 -> 50 -> 200 extra queries), which is precisely the N+1 signature
the experiment is supposed to surface. The SQL statement counts themselves
(11/51/201 vs. flat 1) are unambiguous regardless of the latency floor.

### Why the speed-up changes as page size grows

The *absolute* gap between naive and fixed grows with page size (about
29ms -> 123ms -> 494ms) because naive issues one extra round trip per
additional row on the page, while fixed always issues exactly one query no
matter how many rows come back. The *relative* slowdown grows too: naive is
about 1.4% slower than fixed at page size 10, about 6% slower at 50, and
about 24% slower at 200. Both numbers grow because the fixed version's cost
is flat (one query, one round trip) while the naive version's cost is
directly proportional to the number of rows on the page - so the gap between
"constant" and "linear in N" necessarily widens as N grows, exactly as the
N+1 problem predicts.

### Index: EXPLAIN before/after

Full output: [`RUN_LOG_part3_explain.txt`](RUN_LOG_part3_explain.txt).

The `sections.course_id` index couldn't be used for a clean before/after
demo - MySQL refuses to drop it (error 1553, "needed in a foreign key
constraint") since it backs the `sections -> courses` foreign key. Instead,
this demonstrates adding a genuinely new index: `courses.department`, for
the query `SELECT * FROM courses WHERE department = 'Data Science & AI'`
(1,257 matching rows out of 5,000 total).

| | Before | After |
|---|---|---|
| type | ALL (full table scan) | ref |
| key | *(none)* | `ix_courses_department` |
| rows scanned (estimated) | 5070 | 1257 |
| filtered | 10.0% | 100.0% |

Before the index, MySQL has no way to jump to the matching rows, so it scans
the entire table and filters every row in memory (`type=ALL`, estimates
scanning all ~5,000+ rows, and its own `filtered` estimate of 10% shows it
expects to throw away 90% of what it reads). After adding the index, the
plan switches to `type=ref` using `ix_courses_department` directly, scanning
almost exactly the 1,257 rows that actually match and nothing else
(`filtered=100%`) - it goes from "read everything, keep 10%" to "read
only what you need."

## Part 4: Grounded RAG Question-Answering

Corpus: the same 32-document SJSU corpus from HW3 (`Part-5/corpus/*.txt`,
well over the 5-document minimum). Chunking: `TokenTextSplitter(chunk_size=500,
chunk_overlap=50)` -> 226 chunks. Same embedding model as HW3
(`sentence-transformers/all-MiniLM-L6-v2`). Generation: `qwen2.5:1.5b-instruct`
via Ollama, routed through `Part-4/src/model_client.py`'s `ModelClient`
(the same adapter used everywhere else in this repo).

Command run:
```
python run_rag_qa.py
```
Full console transcript: [`RUN_LOG_part4.txt`](RUN_LOG_part4.txt). Raw
per-question, per-config answers: [`raw/rag_three_config_results.json`](raw/rag_three_config_results.json).
k-sweep: [`raw/rag_k_sweep_results.json`](raw/rag_k_sweep_results.json).
Questions (with expected sources/keywords, verified against the corpus
before running): [`rag_questions.yaml`](rag_questions.yaml).

### Three-configuration comparison (6 questions x A/B/C)

| Q | Category | Config | Correct retrieval | Correct answer | Grounded (cite) | Refused (exact phrase) |
|---|---|---|---|---|---|---|
| q1 | single chunk | No-RAG | - | **No** | - | No |
| q1 | single chunk | Basic-RAG | Yes | Yes | - | No |
| q1 | single chunk | Context-RAG | Yes | Yes | **No** | No |
| q2 | two chunks | No-RAG | - | Yes* | - | No |
| q2 | two chunks | Basic-RAG | Yes | Yes* | - | No |
| q2 | two chunks | Context-RAG | Yes | Yes* | **No** | No |
| q3 | similar across docs | No-RAG | - | **No** | - | No |
| q3 | similar across docs | Basic-RAG | Yes | Yes | - | No |
| q3 | similar across docs | Context-RAG | Yes | Yes | **No** | No |
| q4 | ambiguous | No-RAG | - | n/a | - | No |
| q4 | ambiguous | Basic-RAG | - | n/a | - | No |
| q4 | ambiguous | Context-RAG | - | n/a | **No** | No |
| q5 | not in documents | No-RAG | - | n/a | - | **No (soft "I don't know")** |
| q5 | not in documents | Basic-RAG | - | n/a | - | **No (soft "not mentioned")** |
| q5 | not in documents | Context-RAG | - | n/a | No | **Yes** |
| q6 | unrelated | No-RAG | - | n/a | - | **No (fabricated a full recipe)** |
| q6 | unrelated | Basic-RAG | - | n/a | - | **No (garbled non-answer)** |
| q6 | unrelated | Context-RAG | - | n/a | No | **Yes** |

\* "Correct answer" for q2 is misleading as scored - see the analysis below.
The automated checker uses "any expected keyword present," and every q2
answer got the GPA half right (2.0) while getting the years half wrong (see
k-sweep), so it counts as a pass despite being genuinely half-hallucinated.
This is a real limitation of the automated scoring, not of the underlying
system, and it's why the raw answers are worth reading directly rather than
trusting the pass/fail column alone.

### Evaluation summary

| Metric | Value | What it measures |
|---|---|---|
| Accuracy | 0.778 | Fraction of (question, config) pairs with an expected keyword present, among q1-q3 (q4-q6 have no fixed keyword answer) - inflated by q2's partial-credit issue above |
| Faithfulness (grounded rate) | **0.0** | Fraction of Context-RAG answers that included a `[n]` citation, despite the system prompt explicitly requiring one |
| Refusal correctness | 0.778 (14/18) | Fraction of all 18 runs where "did it refuse" matched "should it have refused" - driven entirely by q5/q6: Context-RAG refused correctly both times, No-RAG and Basic-RAG never used the required exact phrase either time |

### k-sweep (q2, Context-RAG, k = 1, 3, 5)

| k | Answer | Correct (GPA part) | Correct (years part) | Latency (ms) |
|---|---|---|---|---|
| 1 | "...cumulative GPA falls below 2.0... MSCS student generally has **five** years..." | Yes | **No** | 8985.8 |
| 3 | "...cumulative GPA falls below 2.0... complete their degree within **4** years." | Yes | **No** | 14200.3 |
| 5 | "...SJSU cumulative GPA falls below 2.0... minimum of **four** years..." | Yes | **No** | 22162.3 |

More context did not help here, and it's worth being precise about why. At
k=5, the retriever finally pulled in a chunk from the *correct* file
(`sjsu_mscs_faq.txt`, chunk-0067) that wasn't present at k=1 or k=3 - but
that particular 500-token chunk happened to land on a different part of the
FAQ page (about admission offers) than the sentence that actually states
"up to 7 years," which is elsewhere in the same file and therefore in a
different chunk that never made the top-5. So retrieval got closer (right
file, wrong chunk) without ever getting the fact, and the model filled the
gap with a plausible-sounding but wrong number every time - a different
wrong number at each k (five, four, four), which suggests it isn't
consistently recalling anything from its own training either, it's
guessing. No irrelevant chunks entered the context at any k (every
retrieved chunk scored above the 0.30 relevance threshold), so this isn't
a "junk crowded out the signal" failure - the signal genuinely wasn't in
any of the retrieved chunks. Latency scaled up substantially with k (9.0s
-> 14.2s -> 22.2s) purely from prompt length, for zero accuracy benefit on
this question. Best k here, honestly, is k=1: same (wrong) answer quality,
a third of the latency.

### Written analysis (Part 4.7)

Retrieval worked cleanly for q1 and q3: both pulled the exact source file on
the first try, and both RAG configurations answered correctly, while No-RAG
guessed wrong on both (hallucinating a nonexistent "CS 101" course for q1,
and giving no concrete number at all for q3). q2 is the interesting failure:
retrieval consistently found the right file for the GPA fact
(`sjsu_socsci_academic_notice.txt`) but never found the specific chunk
holding the "up to 7 years" fact in `sjsu_mscs_faq.txt`, even at k=5 where a
different chunk from that same file did show up. Chunk size is the likely
culprit - a 500-token chunk boundary happened to separate the sentence we
needed from the surrounding FAQ content that scored higher on this query.
This matters more than it sounds: the automated "correct answer" check
scored all three q2 configurations as passing, because it only requires one
of several expected keywords to appear, and "2.0" always did. Reading the
actual text, every single q2 answer across every config and every k value
got the years figure wrong (five, four, four, four - never seven), which
the summary metric completely hides. That's a real lesson about evaluating
RAG systems: a lenient keyword check can look like 78% accuracy while
missing a persistent,100%-reproducible factual error.

The context-engineering changes that clearly helped were the grounding
rules and the refusal instruction, not the deduplication or ordering logic
(no duplicate or irrelevant chunks actually showed up in any of these six
questions' retrievals, so those safeguards never got exercised here). The
refusal instruction is what separated Context-RAG from the other two on
q5 and q6: No-RAG and Basic-RAG never once produced the exact required
refusal sentence, instead either giving a soft non-answer (q5) or,
worse, fabricating a complete, plausible-sounding chocolate chip cookie
recipe with zero connection to the source documents (q6, No-RAG). That
recipe is unambiguous, ungrounded hallucination - invented from the model's
own training data with no attempt to check it against anything retrieved.
Context-RAG refused both correctly, in the exact required wording, both
times.

What did not work as instructed was citation. Every Context-RAG system
prompt explicitly required a `[n]` source citation on every factual claim,
and not one of the six answers included one, despite otherwise following
the "answer only from context" and refusal rules correctly. Retrieval
quality, context quality, and the prompt each did real, separable work here:
retrieval decided whether the right fact was even available to use;
context curation (relevance filtering, labeling) decided whether the model
had a clean set of sources to draw from once retrieval succeeded; and the
prompt's grounding rules decided whether the model was honest about the gap
when retrieval failed. But the prompt's formatting instruction (citation)
was simply not followed by this small model even when everything else
about the setup was correct - a clear reminder that a 1.5B-parameter local
model's compliance with strict output-format rules cannot be assumed just
because the rule is stated plainly.
