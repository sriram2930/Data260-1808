# HW9 Metrics

## Config

| Value | Setting |
|---|---|
| SID4 / PREFIX | 1808 / s1808 (all Redis keys start with `s1808:`) |
| Local model | qwen2.5:1.5b-instruct (Ollama), shared `ModelClient` |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2, 384-d, normalised |
| Vector store | redis/redis-stack-server 7.2.0-v10, FLAT index, COSINE, key prefix `s1808:semcache:` |
| Hardware | i7-11390H, 16GB RAM, integrated Iris Xe (no dedicated GPU) |
| cache_cases.yaml commit | 1686f9f (committed before any sweep) |

## Part 1 - counter

25 accesses of CS-00005: Redis = 25, `courses.view_count` = 20 (synced at 10 and 20). 2 DB writes instead of 25.

## Part 2 - semantic cache (threshold 0.85, 14 queries, real Kafka pipeline on misses)

Hit rate 6/14 = 42.9%. Avg latency cached 60.4 ms (n=6); not cached 23,245.7 ms (n=8).

## Part 3 - sweep over 40 labeled cases (misses add the recorded real pipeline latency)

| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |
|---|---|---|---|---|
| 0.75 | 70.0% | 40.0% (8/20) | 8,815.1 | $16.060 |
| 0.80 | 62.5% | 25.0% (5/20) | 10,337.3 | $10.075 |
| 0.85 | 60.0% | 25.0% (5/20) | 10,824.0 | $10.080 |
| 0.90 | 57.5% | 20.0% (4/20) | 11,752.8 | $8.085 |
| 0.95 | 37.5% | 20.0% (4/20) | 16,764.5 | $8.125 |

Cost = misses x $0.005 + false hits x $2.00 (assumptions; sensitivity at $0.10 / $20 also picks 0.90).
Shipped threshold: 0.90. Four false hits (C22, C23, C28, C29, similarity 0.957-0.994) survive every threshold:
questions differing only in a course-code digit. Post-hoc, same-set only: requiring matching course codes would remove them.

Stale answer (CS-00005 seats 30 -> 12): stale hit served the old "30"; validate-on-read detected the changed
data_version, evicted, re-ran the pipeline ("12"). Validation overhead per valid hit: 40.7 ms -> 57.5 ms.

## Part 4 - test_data.json (20 questions, run once at the end)

| Variant | Correct | Incorrect | Avg attempts | Avg latency |
|---|---|---|---|---|
| Baseline | 15 | 5 | 1.00 | 3.17 s |
| Evaluator Repair | 16 | 4 | 1.25 | 2.94 s |
| Lesson Memory | 18 | 2 | 1.25 | 3.45 s |
| Validated Improvement | 18 | 2 | 1.25 | 3.47 s |

First-attempt correctness is 15/20 for every variant. Lesson Memory and Validated Improvement are identical because the
single lesson (lesson_001, unsupported-answer) passed validation (16 -> 17/20 on validation, no regression).
Training: 16/20 first attempt, 17/20 after repair. Self-check: `python verify_hw09.py` -> 23/23.

## Reproduce

Docker: `s1808-mysql`, `s1808-zookeeper`, `s1808-kafka`, `s1808-redis`
(`docker run -d --name s1808-redis -p 6379:6379 redis/redis-stack-server:7.2.0-v10`).
Start `Part-11/planner.py`, `writer.py`, `reviewer.py`. Then, from the repo root:
`python Part-1/migrate_hw09.py` (from `Part-1`), `python Part-13/seed_hw09.py`, `python Part-12/counter_demo.py`,
`python Part-13/part2_demo.py`, `python Part-13/part3_precompute.py`, `python Part-13/part3_sweep.py`,
`python Part-13/part3_stale_demo.py`, `python Part-14/make_datasets.py`, `python Part-14/run_training.py`,
`python Part-14/run_validation.py`, `python Part-14/run_variants.py`, `python Part-14/demo_revision.py`,
`python Part-14/demo_lesson_reuse.py`, `python verify_hw09.py`.
