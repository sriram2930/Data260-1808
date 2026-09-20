# AI_USE.md - HW3

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code to write essentially all the code for both parts: the
FastAPI auth router and Bootstrap templates, the corpus fetch/clean script,
and the three-technique LlamaIndex chunking/retrieval pipeline plus the
metrics recompute script. It also ran everything on this machine - starting
the auth server and testing login/session/idle-timeout behavior with curl,
fetching the real SJSU pages, and running the actual embedding model locally
to produce the retrieval comparison numbers.

What I did myself: picked which SJSU pages to use as the domain corpus (and
rejected using `catalog.sjsu.edu` once it turned out to be gated), wrote and
verified the five `questions.yaml` questions and their expected answers by
hand against the actual corpus text before any retrieval was run, and made
the final call on chunking parameters (token chunk size, semantic buffer
size, sentence-window size) and on which technique to recommend in the
conclusion.

## 2. One AI-produced output that was wrong/unsuitable

The first version of the corpus cleaning script only stripped literal
`<nav>`/`<header>`/`<footer>` tags. On `ischool.sjsu.edu` pages that left a
wall of one- and two-word menu lines (a persistent sidebar rendered as a
plain `<div>`/`<ul>`, not a semantic `<nav>` element) ahead of any real
content, and the saved "clean" text files ended up almost entirely nav noise
with the actual article content buried in the middle - one file
(`sjsu_adding_dropping_classes.txt`) had roughly 200 lines of menu items
before its two real paragraphs. Total corpus size after this first pass was
only 27.9KB, well under the 200KB minimum, even though the raw HTML fetched
totaled almost 1MB.

## 3. How I detected the problem / verified the result

By actually reading one of the saved output files line by line instead of
just trusting the byte count. The first 60 lines were obviously a site
navigation menu (single words and short phrases like "Financial Aid",
"Scholarships", "Internships"), which made it clear the issue wasn't that the
pages lacked content, it was that the cleaning wasn't distinguishing real
content from menu chrome that happened to sit outside a `<nav>` tag.

## 4. What I changed and why it works now

Added a second cleaning pass: strip elements whose `id`/`class` matches
common sidebar/menu/breadcrumb naming patterns, then collapse any run of 4 or
more consecutive short (<=6 words) lines that don't end in sentence
punctuation, on the reasoning that real prose sentences almost always end in
`.`/`?`/`!`/`:` while menu items almost never do. Re-running the fetch after
this change dropped the near-empty `ischool.sjsu.edu` pages down further
(confirming those specific pages really were almost all chrome) while
`www.sjsu.edu` FAQ-style pages kept most of their real paragraph content, and
after adding more of those `www.sjsu.edu` pages the corpus reached 208.4KB,
clearing the 200KB requirement with real, readable text - verified by
re-reading a sample of the output files again and confirming they now read
as actual paragraphs rather than menu dumps.

A second, smaller finding worth recording: in the retrieval output, the
in-memory vector store's own `store_score` and the cosine similarity I
recomputed by hand from the raw embeddings don't always match exactly (e.g.
one row showed `store_score=0.5835` vs recomputed `cosine_sim=0.6305` for the
same chunk). I didn't chase down the exact reason (could be a normalization
difference or a distance-to-similarity conversion inside the store), but I
kept both numbers in the output and the report rather than assuming they were
interchangeable, since the assignment explicitly asks for both to be printed
separately.
