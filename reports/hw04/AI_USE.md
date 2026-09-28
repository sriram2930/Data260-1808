# AI_USE.md - HW4

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code to write and run essentially everything: the React client,
the SQLAlchemy models and MySQL-backed session/auth system, the N+1 naive/
fixed endpoints and the 180-request measurement script, the EXPLAIN demo, and
the full grounded RAG QA pipeline (chunking, retrieval, three answer
configurations, the k-sweep, and the automated evaluation checks). It also
ran the actual experiments on this machine against a real MySQL container and
the real local Ollama model, not simulated data.

What I did myself: decided the "related entity" design for Part 3 (course
sections, FK'd to courses, since the assignment left that open), picked
which of my own prior corpus and infrastructure to reuse versus rebuild
(reused the HW3 SJSU corpus for Part 4 instead of building a new one, since
it already met the 5-document minimum and kept the domain consistent), wrote
and verified the six RAG test questions' expected facts against the actual
corpus text before running anything, and read through the raw model outputs
myself rather than trusting the automated pass/fail scores at face value.

## 2. One AI-produced output that was wrong/unsuitable

The automated "correct_answer" check in the RAG evaluation (Part 4) scores an
answer as correct if it contains at least one of several expected keywords.
For question 2 ("what GPA keeps you off academic notice, and how many years
does an MSCS student have to finish"), every single answer across all three
configurations and all three k-sweep values got the GPA half right (2.0) but
the years half wrong (it said five, four, or four, never the actual seven).
Because the keyword check only requires one match, all of these got marked
`correct_answer: true`, and the summary metric reported 77.8% accuracy - a
number that quietly hides a 100%-reproducible factual error on one of the
six questions.

## 3. How I detected the problem

By reading the actual raw answer text in `reports/hw04/raw/rag_three_config_results.json`
and the k-sweep output instead of only looking at the summary JSON's
pass/fail booleans. The automated check technically did what I told it to do
(check for any expected keyword), it just wasn't a strict enough check to
catch a partially-wrong, two-part answer.

## 4. What I changed and why it works now

I didn't change the scoring code itself, since a stricter check (e.g.
requiring every expected keyword) would have its own failure modes for
other questions with alternative valid phrasings. Instead I added an
explicit callout in `METRICS.md`'s evaluation table and written analysis
saying plainly that q2's "correct" marks are misleading and pointing at
the real answer text, plus a from-scratch explanation of why retrieval
never surfaced the "7 years" fact even at k=5 (it retrieved a different
chunk from the right file, not the chunk with that sentence in it). This
is the honest fix: rather than pretend the automated metric is the ground
truth, the report says outright where it isn't, and shows the actual wrong
numbers next to it.

A second thing worth recording here, not a bug I fixed so much as a real
system limitation I verified by reading the raw output: the Context-RAG
system prompt explicitly required a `[n]` citation on every claim, and I
checked programmatically (a regex for `\[\d+\]`) whether any of the six
answers actually included one. None did - `faithfulness_grounded_rate: 0.0`.
I did not "fix" this by re-prompting or adding few-shot examples, since the
assignment's interest here is in observing and reporting real context/
prompt-engineering behavior rather than engineering the model into
compliance; the honest result is that this small local model followed the
grounding and refusal rules but not the citation-format rule, and that
asymmetry is reported as-is.
