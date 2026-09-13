# METRICS — DATA-260 HW2

**Model:** `qwen2.5:1.5b-instruct` (Ollama), no explicit temperature override
(Ollama default). All three experiments below were produced by one run of
[`Part-2/run_schema_experiments.py`](../../Part-2/run_schema_experiments.py):
```
.venv\Scripts\python.exe Part-2\run_schema_experiments.py | Tee-Object -FilePath reports\hw02\RUN_LOG.txt
```
Full console transcript (all 75 runs, real timestamps): [`RUN_LOG.txt`](RUN_LOG.txt).
Raw per-run rows: [`raw/schema_experiment_runs.csv`](raw/schema_experiment_runs.csv),
[`raw/schema_experiment_runs.json`](raw/schema_experiment_runs.json).
Aggregate summary: [`raw/schema_experiment_summary.json`](raw/schema_experiment_summary.json).

Fixed inputs (saved once, unchanged):
[`cases/schema_input.json`](cases/schema_input.json) (main experiment),
[`cases/adversarial_input.json`](cases/adversarial_input.json) (Part 4.5).

## Experiment 1 — 30-run classification (`schema_input.json`, turn_ceiling=10)

| Outcome over 30 runs | Count | Mean latency (ms) |
|---|---|---|
| Valid first attempt | 17 | 4923.0 |
| Valid after 1 retry | 6 | 8819.8 |
| Valid after 2+ retries | 7 | 15042.9 |
| Hit turn ceiling | 0 | — |

All 30 runs eventually produced an approved result; none were abandoned at the
ceiling. Latency scales almost linearly with retry count, which is expected —
each retry is one more full Planner (+ possibly Reviewer) round trip to the
model. Just over half the runs (17/30) succeeded on the very first Planner
attempt with no Reviewer rejection and no schema-validation failure.

## Experiment 2 — Turn-ceiling comparison (20 runs each, same input/model settings)

| Turn ceiling | n | Completion rate | Mean latency (ms) |
|---|---|---|---|
| 2 | 20 | 90.0% | 5608.6 |
| 10 | 20 | 100.0% | 6935.7 |

**Choice for deployment: turn_ceiling = 10.** Raising the ceiling from 2 to 10
closes the remaining 10% failure gap entirely (every run completed) for about
1327ms of extra mean latency (+23.7%) — a small, predictable cost for
guaranteed completion. A ceiling of 2 would leave 1 in 10 real users getting an
abandoned/failed request with no fallback, which is a worse trade for a
user-facing feature than an extra second of latency. (If this were instead a
tight-latency batch job where an occasional dropped item is acceptable and
gets retried by an outer process, ceiling=2 would be the more defensible
choice — the right ceiling depends on what's downstream, which is why both
numbers are reported rather than assuming one answer.)

## Experiment 3 — Adversarial input (5 runs, turn_ceiling=10)

| Metric | Value |
|---|---|
| Runs | 5 |
| Hit turn ceiling | 5 / 5 (100%) |

The adversarial input is the longer, denser HW1 course description
(`adversarial_input.json`) rather than a nonsense or malformed input — it is
completely valid, on-topic text. It reliably breaks the pipeline anyway: the
Planner consistently writes a summary well over the 25-word Pydantic limit
(observed 26-67 words across attempts in earlier testing), and reruns after
being told the exact word-count error keep failing the same way rather than
converging on a compliant length. **Why it causes trouble:** the input simply
contains too many distinct sub-topics (schema design, batch/streaming
ingestion, feature stores, versioning, drift monitoring, failure modes) for the
model to compress into 25 words without either dropping the instruction's word
limit or dropping most of the content — and this small model consistently
chooses to keep the content and blow the limit, rather than reliably trading
off toward brevity even when told exactly how many words it's over. **Proposed
fix:** rather than only telling the Planner "your summary was N words, fix it,"
give it a harder constraint it's more likely to follow mechanically — e.g.
"write the summary in at most 3 short clauses separated by semicolons" or
provide a word budget per clause — or, more robustly, keep the deterministic
truncation approach from HW1's Finalizer as a final safety net after N failed
retries, so an adversarial input degrades gracefully into "a truncated but
still 3-tagged result" instead of consuming the entire turn ceiling and
returning nothing.
