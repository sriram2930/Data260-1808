# AI_USE.md - HW6

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code to design and write the MongoDB schema and CRUD API
(Part 1), the short/long/episodic memory system and chat endpoint (Part 2),
the token-cost experiment harness (Part 3), and the file-based memory
system with consolidation (Part 4). It ran all of this against real
infrastructure throughout: a real MongoDB container, the real local Ollama
model, and real embeddings for episodic/duplicate-detection similarity, not
simulated data.

What I did myself: designed the `announcements` entity and its fields for
this domain, decided how the one-turn lag in summaries/episodic retrieval
should work (and confirmed it was intentional, not a bug, by re-reading the
actual turn-by-turn output), picked the 30-message test conversation and
where to plant the probe facts in `memory_probes.yaml`, and iterated
through three failed consolidation designs myself before the one that
actually works, reading the real output of each attempt rather than trusting
that "it ran without an error" meant it worked.

## 2. One AI-produced output that was wrong/unsuitable

Two, because they were both instructive in different ways.

**Episode extraction silently stored nothing.** The first version of
`extract_episodes` asked the model for a JSON array of facts and did
`parsed.get("facts", [])` if it got a dict back instead of a list. In
practice, for the very first message of the first real conversation, the
model replied with a single JSON object that WAS the fact itself
(`{"fact": "...", "importance": 1.0}`), not a list and not `{"facts": [...]}`.
My code treated that as "no facts" and silently stored nothing, even though
the model's answer was perfectly usable, it just wasn't wrapped the way I
assumed it would always be.

**Consolidation barely touched a 56-line file.** Part 4.5's stress test
deliberately plants 3+ duplicate facts and 3+ contradictions in a crafted
MEMORY.md and expects consolidation to merge/resolve them and land under 40
lines. The first design asked the model to rewrite the whole file in one
shot (merge duplicates, resolve contradictions, reply with the new file).
It went from 56 lines to 54, two duplicates were dropped and nothing else
happened, none of the three planted contradictions were touched.

## 3. How I detected the problem

For the episode bug: I queried MongoDB directly after the first real
conversation turn (`db.episodes.find({user_id:"u1"})`) and got zero
results, even though the user's first message ("my name is Sreeram, grad
student in Data Science") obviously contained something worth remembering.
I ran the extraction prompt by hand outside the app to see the model's raw
reply, and saw it was a bare object, not an array, immediately showing
where my parsing assumption broke.

For consolidation: I checked the before/after line counts and the actual
diff of the file. 56 to 54 lines was an immediate signal something had
gone wrong given the assignment's target (under 40), and reading the
"after" content directly showed all three planted contradictions were
still present as separate, unresolved bullets.

I then tried two more designs before landing on one that held up: a
deterministic string-similarity dedup pass (failed, because the
contradictions in this domain happen to share almost all their wording and
differ only in one number, so they score *higher* on character-overlap
similarity than true duplicates do, which are differently worded on
purpose); and asking the model to classify line numbers into duplicate
groups/contradiction pairs via JSON (failed, it found zero real duplicates
and hallucinated one false contradiction between two unrelated facts). The
working design uses embeddings to find which pairs are "about the same
thing" (duplicates and contradictions both score high here, since both
share nearly all their words) and then a deterministic check, differing
numbers or an explicit antonym pair like allowed/blocked, to decide which
of the two a given pair actually is. The LLM is only trusted to compose the
final one-line merge once a real contradiction pair has already been found
deterministically, and at that narrower task it was reliable every time I
tested it in isolation.

## 4. What I changed and why it works now

For episode extraction: the parser now checks whether the returned dict
itself looks like a single fact (`"fact"` key present) and wraps it in a
one-item list, in addition to the `{"facts": [...]}` case. After that fix,
the same first message correctly produced a stored episode, and every
later conversation turn had episodes to retrieve from.

For consolidation: duplicates are now merged with a similarity-based
embedding pass (never relies on an LLM to notice an obvious duplicate, and
is at least transparent about its own threshold), contradictions are found
by checking which similar-pair differs in a number or a polarity word, and
only the final one-line resolution text for each confirmed contradiction
goes through the model. This is slower (several small calls instead of
one big one) but each individual call is small enough for a 1.5B local
model to actually get right, which the earlier one-shot and JSON-classify
designs were not. See `METRICS.md` for whether this pipeline's own
duplicate/contradiction calls were themselves still imperfect on the real
test file, and what, if anything, needed a human correction on top, since
the assignment specifically asks for that to be identified rather than
hidden.
