# AI_USE.md — DATA-260 HW1

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code as a pair-programming assistant throughout this homework:
scaffolding the HTML form and `app.js` validation/JSON/closure logic for Part 1;
installing and configuring the local toolchain (Ollama, Python 3.12 venv,
AWS CLI) .


## 2. One AI-produced output that was wrong/unsuitable

Within the homework's own agent pipeline (not the coding assistant, but the
local LLM the Part 2 pipeline calls): the **Reviewer agent** marked a draft
`"approved": true, "changes": "No changes needed."` while its own summary was
still 42 words long — well over the 25-word limit it had just been explicitly
instructed to check for. It correctly used the right JSON shape and even
lightly reworded the summary, but it did not actually verify the constraint
it claimed to have checked.

## 3. How I detected the problem

By word-counting the Reviewer's own output and comparing it against the limit
stated in its own system prompt — a simple `len(summary.split())` check. The
Reviewer's JSON was structurally valid and its `approved: true` claim looked
authoritative, so this only surfaces if you actually check the number rather
than trust the model's self-report.

## 4. What I changed, and why it works now

I did not try to make the Reviewer more reliable through prompt tuning, since
that only reduces the failure rate, not eliminates it. Instead I added a
**deterministic Finalizer step** in plain Python (`_enforce_contract` in
`agents_demo.py`) that runs after the Reviewer regardless of what it reported:
it hard-truncates the summary to 25 words and hard-caps the tag list to
exactly 3 entries. This guarantees the published output always meets the
contract, independent of whether the Reviewer's self-assessment was correct —
verified by rerunning the same input and confirming `finalizer_notes` reports
the truncation whenever the Reviewer's summary is too long.
