# METRICS - DATA-260 HW2

Model: `qwen2.5:1.5b-instruct` (Ollama), no explicit temperature override.
These numbers are from the actual final run used for the report screenshots
(finished 2026-09-13 18:44:15), produced by:
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

## Experiment 1: 30-run classification (`schema_input.json`, turn_ceiling=10)

| Outcome over 30 runs | Count | Mean latency (ms) |
|---|---|---|
| Valid first attempt | 14 | 4682.4 |
| Valid after 1 retry | 8 | 8366.1 |
| Valid after 2+ retries | 7 | 14656.6 |
| Hit turn ceiling | 1 | 28392.1 |

29 out of 30 runs eventually got an approved result, one run used up all 10
Planner attempts without the Reviewer ever approving. Latency goes up with
retry count, which makes sense since each retry is another full round trip to
the model (and sometimes a Reviewer call on top of that).

## Experiment 2: Turn-ceiling comparison (20 runs each, same input/model settings)

| Turn ceiling | n | Completion rate | Mean latency (ms) |
|---|---|---|---|
| 2 | 20 | 70% | 6109.4 |
| 10 | 20 | 100% | 9714.8 |

For deployment I'd pick turn_ceiling = 10. It costs about 3.6 more seconds on
average than ceiling 2, but ceiling 2 fails to reach an approved result 30% of
the time, which is a rough failure rate if someone is actually waiting on this.
Ceiling 10 got every single run to a valid, approved answer.

## Experiment 3: Adversarial input (5 runs, turn_ceiling=10)

| Metric | Value |
|---|---|
| Runs | 5 |
| Hit turn ceiling | 4 / 5 (80%) |

The adversarial input is the longer, denser HW1 course description
(`adversarial_input.json`), not a broken or nonsense input, it's completely
valid, on-topic text. It still breaks the pipeline most of the time: the
Planner keeps writing a summary well past the 25-word limit, and telling it
the exact word count it's over doesn't reliably fix that. My guess is there's
just too much content in that description (schema design, batch/streaming
ingestion, feature stores, versioning, drift monitoring, failure modes) for
the model to compress into 25 words, so it keeps choosing to keep the content
over following the word limit. A fix worth trying: instead of just repeating
the word-count error, give it something more mechanical to follow, like "write
this as 3 short clauses separated by semicolons," or fall back to the HW1
Finalizer's hard truncation after enough failed retries so an adversarial
input at least degrades into something usable instead of returning nothing.
