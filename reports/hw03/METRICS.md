# METRICS - DATA-260 HW3, Part 2

Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim), via
`llama-index-embeddings-huggingface`. In-memory vector store (LlamaIndex's
default `SimpleVectorStore`), k=5. Corpus: 32 local SJSU pages, 208.4KB (see
[`SOURCES.md`](SOURCES.md) / [`CORPUS_MANIFEST.json`](CORPUS_MANIFEST.json)).
Questions: [`questions.yaml`](questions.yaml), committed before this
experiment was run.

Command run:
```
python run_retrieval_comparison.py
python compute_metrics.py
```
Full console transcript: [`RUN_LOG.txt`](RUN_LOG.txt). Raw per-row data (75
rows = 5 questions x 3 techniques x k=5): [`raw/retrieval_results.jsonl`](raw/retrieval_results.jsonl),
[`raw/retrieval_results.csv`](raw/retrieval_results.csv). Per-technique chunk
counts: [`raw/chunk_stats.json`](raw/chunk_stats.json). This table, recomputed
straight from those raw files (no re-embedding, no network) by
`compute_metrics.py`: [`raw/metrics_summary.json`](raw/metrics_summary.json).

## Retrieval quality comparison

| Technique | Chunks | Avg chunk length (chars) | Top-1 cosine | Mean@k cosine | Recall@k | Mean retrieval latency (ms) |
|---|---|---|---|---|---|---|
| Token | 235 | 1045.7 | 0.6991 | 0.6329 | 1.00 | 77.77 |
| Semantic | 150 | 1392.6 | 0.6560 | 0.6085 | 1.00 | 52.07 |
| Sentence window | 2114 | 98.8 | 0.7239 | 0.6793 | 1.00 | 149.87 |

Recall@k here means: for each of the 5 questions, did at least one of the
top-5 retrieved chunks come from that question's `expected_source_file`. All
three techniques hit 1.00 - with only 32 documents and fairly distinct topics,
the right document reliably shows up somewhere in the top 5 regardless of how
it got chunked. So recall doesn't separate these three; cosine quality and
latency do.

## A confidently-scored retrieval that doesn't actually contain the answer

Two clean examples came out of q3 ("At what cumulative GPA is an
undergraduate placed on academic notice?"), expected source
`sjsu_socsci_academic_notice.txt`:

- **Token**, cosine 0.6931, top result was actually from
  `sjsu_grade_changes.txt`: "...IC = Incomplete - Charged. The following
  grades are not calculated into your GPA. No Credit. Equivalent to D+ and
  below*. See the current SJSU Catalog for details regarding the grading
  symbols and policies..."
- **Semantic**, cosine 0.7053, same wrong source file, similar passage.

Neither of these chunks states the 2.0 GPA threshold that triggers academic
notice. My guess at why the embedding rated it so highly anyway: both texts
live in the same "GPA / academic standing" vocabulary neighborhood (GPA,
grade, calculated, academic standing/notice), so a small sentence-embedding
model picks up on that shared topic vocabulary even though one document is
about how individual grade symbols factor into GPA math and the other is
about the specific cumulative-GPA cutoff for academic notice. Same general
subject, different specific fact - exactly the kind of near-miss a keyword
search would probably also make.

A second, different kind of miss showed up in **sentence_window**, q5
("...enrollment appointment get posted on MySJSU?"), cosine 0.8065 (the
highest-confidence miss of the whole run), attributed to
`sjsu_chhs_faqs.txt` instead of the expected `sjsu_registration_basics.txt`.
The retrieved sentence - "Your enrollment appointment date and time is listed
in your MySJSU student center" - is actually true and relevant, it's just
that near-identical boilerplate about enrollment appointments is repeated
across multiple SJSU college FAQ pages (registration procedures are
university-wide, so every college's student success center FAQ restates the
same basic facts). So this "miss" isn't really a bad retrieval, it's the
`expected_source_file` label being an imperfect proxy - when the same fact
legitimately appears in more than one document, "did it come from the one
file I picked as canonical" understates how well the retrieval actually did.

## Observations

Sentence-window chunking got the best cosine scores by a real margin (0.72
top-1 vs 0.70 for token and 0.66 for semantic), and it's not surprising why:
each indexed unit is a single sentence, so when the query and the answer
share a specific sentence's worth of vocabulary, nothing else in that chunk
dilutes the similarity. The cost is chunk count - 2114 sentence-level nodes
versus 150-235 for the other two - and that shows up directly in latency:
sentence-window is very roughly 2-3x slower than token chunking and about 3x
slower than semantic, since the retriever is doing a nearest-neighbor search
over an order of magnitude more vectors. Semantic chunking produced the
fewest, longest chunks and was the fastest, but also had the lowest cosine
scores of the three - grouping several sentences into one semantically-
coherent-ish chunk means the embedding has to represent more mixed content
at once, which waters down how sharply it matches a narrow question.

The best technique differed a little by question. For q1 and q2 (both very
specific, narrow FAQ facts - the CS 22A recommendation, the CS 200W
prerequisite for CS 297) sentence-window's top-1 cosine was clearly highest,
since the exact answering sentence could be its own chunk. For q3 and q5,
where the useful chunk is more like "a short paragraph" than "one sentence,"
token and semantic still worked, but sentence-window occasionally split the
answer awkwardly across two adjacent sentence-chunks (e.g. q5 rank 1 and rank
2 in `RUN_LOG.txt` are two separate one-sentence chunks that together contain
the full answer, neither alone).

## Conclusion

For this corpus, **sentence-window chunking is the one I'd pick**, mainly
because its cosine scores were consistently the highest and its Recall@k
tied the other two at a perfect 1.0 - it finds the right document just as
reliably and scores its best match more confidently than token or semantic
chunking do. The latency cost (about 150ms mean vs 52-78ms) is real, but at
this corpus size it's still well under a fifth of a second per query, which
is not a meaningful cost for a retrieval-only step. If the corpus were much
larger (say, the full multi-megabyte SJSU catalog rather than 32 pages), that
latency gap would matter more and I'd lean back toward token chunking as the
more balanced default - good-enough cosine scores, far fewer chunks to search
over, and simpler to reason about than semantic breakpoint detection.
