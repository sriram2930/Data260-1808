# Part 2 — Agentic AI: Deliverables

## Command used

```
.venv\Scripts\python.exe agents_demo.py --input-file sample_input.json --temperature 0.7
```

Model: `qwen2.5:1.5b-instruct` (substituted for the spec default `qwen3:8b` — this
machine has no dedicated GPU, integrated Iris Xe graphics, 16GB RAM; documented in
[README.md](../../README.md)).

## Console screenshot

See the submitted screenshot showing, in order: `INPUT`, `PLANNER OUTPUT`,
`REVIEWER OUTPUT`, `FINALIZED / PUBLISH OUTPUT`, and pipeline latency.

## Q1. The 3 final tags obtained

```json
["machine learning", "data pipelines", "pipelines design"]
```

## Q2. The final summary (<=25 words)

> This course focuses on designing and operating data pipelines for machine
> learning systems, including schema design, ingestion, feature stores, versioning,
> and monitoring. Students build a

(Exactly 25 words. It ends mid-sentence because the Finalizer enforces the word
limit with a hard truncation rather than an LLM rewrite — see Q3 and the design
note below for why that trade-off was made.)

## Q3. Did the Reviewer agent change anything? (yes/no + explanation)

**Not meaningfully.** The Reviewer returned the same 3 tags as the Planner and only
lightly reworded the summary, marking `"approved": true, "changes": "No changes
needed."` — but its own summary was still 42 words long, well over the 25-word
limit it was explicitly told to check for. So the Reviewer's self-assessment was
wrong: it approved a draft that still violated the actual constraint. The
deterministic Finalizer step is what caught this and truncated the summary to 25
words (see `"finalizer_notes": ["truncated summary from 42 to 25 words"]` in the
Publish output) — not the Reviewer. This is a concrete example of why a
code-enforced Finalizer, rather than trusting a second model call to self-certify,
matters for guaranteeing the output contract.

## Explanation of each step (in my own words)

1. **Planner** receives only the raw `title` and `content` and is asked, via a
   domain-agnostic system prompt, to propose exactly 3 topical tags and a
   one-sentence summary (<=25 words). Its output is constrained to a Pydantic
   schema (`PlannerOutput`) via Ollama's JSON-schema-constrained generation, so
   the response is guaranteed to be valid JSON in the right shape before anything
   downstream sees it.
2. **Reviewer** receives the *same* title/content plus the Planner's draft tags
   and summary, and is asked to critique and, if needed, correct them — checking
   specifically for exactly 3 relevant tags and a faithful, <=25-word summary. This
   is the "two agents talk to each other" part: the Reviewer's input is literally
   built from the Planner's output.
3. **Finalizer** is plain Python, not a third model call. It de-duplicates and
   hard-caps the tag list to exactly 3 entries, and hard-truncates the summary to
   25 words if it's longer — guaranteeing the output contract holds regardless of
   what either model call actually produced. This run demonstrates exactly why
   that matters: the Reviewer *said* everything was fine when it wasn't.
4. The **Publish JSON** bundles the final tags/summary with bookkeeping (model
   name, temperature, whether the Reviewer claimed approval, what the Finalizer
   had to fix, and a timestamp) and is what gets printed as the pipeline's final
   output.
