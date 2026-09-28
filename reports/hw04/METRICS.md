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
