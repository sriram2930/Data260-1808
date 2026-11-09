"""One-off script assembling the HW9 Word report (then exported to PDF). Not part of the graded
deliverable; kept so the report can be regenerated. Every number in the tables comes from the
captured JSON in raw/ -- nothing is typed in by hand except prose.

Usage:  python generate_report.py [final_commit_hash]
"""

import json
import sys
from pathlib import Path

import docx
import yaml
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).parent
RAW = HERE / "raw"
SHOTS = HERE / "screenshots"
REPO = HERE.parent.parent
FINAL_HASH = sys.argv[1] if len(sys.argv) > 1 else "(filled in after the final commit)"
CASES_COMMIT = "1686f9f"  # commit that added Part-13/cache_cases.yaml BEFORE any threshold sweep

j = lambda name: json.loads((RAW / name).read_text(encoding="utf-8"))  # noqa: E731
p2 = j("part2_results.json")
sweep = j("part3_sweep_summary.json")
rows = j("part3_sweep_rows.json")
stale = j("part3_stale_results.json")
test = j("part4_test_results.json")
guard = j("part3_posthoc_code_guard.json")
spec = yaml.safe_load((REPO / "Part-13" / "cache_cases.yaml").read_text(encoding="utf-8"))
lessons = json.loads((REPO / "Part-14" / "lessons.json").read_text(encoding="utf-8"))

doc = docx.Document()
for s in doc.sections:
    s.left_margin = s.right_margin = Inches(0.9)
    s.top_margin = s.bottom_margin = Inches(0.8)


def style(name, size, bold=False):
    st = doc.styles[name]
    st.font.name = "Calibri"
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = RGBColor(0, 0, 0)


style("Normal", 11)
style("Heading 1", 14, True)
style("Heading 2", 12, True)
doc.styles["Normal"].paragraph_format.space_after = Pt(5)

h1 = lambda t: doc.add_heading(t, level=1)  # noqa: E731
h2 = lambda t: doc.add_heading(t, level=2)  # noqa: E731


def p(text, bold=False, italic=False):
    para = doc.add_paragraph()
    r = para.add_run(text)
    r.bold, r.italic = bold, italic
    return para


def code(text, size=8.5):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(4)
    r = para.add_run(text)
    r.font.name = "Consolas"
    r.font.size = Pt(size)


def shot(name, width=6.5, caption=None):
    doc.add_picture(str(SHOTS / name), width=Inches(width))
    if caption:
        c = doc.add_paragraph()
        r = c.add_run(caption)
        r.italic = True
        r.font.size = Pt(10)


def table(data, widths=None, size=10):
    t = doc.add_table(rows=0, cols=len(data[0]))
    t.style = "Table Grid"
    for i, vals in enumerate(data):
        cells = t.add_row().cells
        for k, v in enumerate(vals):
            cells[k].text = ""
            run = cells[k].paragraphs[0].add_run(str(v))
            run.font.size = Pt(size)
            run.bold = i == 0
    if widths:
        for row in t.rows:
            for k, w in enumerate(widths):
                row.cells[k].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def src(path, start, end):
    """Verbatim excerpt of a source file from the line containing `start` up to (not incl.) the line containing `end`."""
    lines = (REPO / path).read_text(encoding="utf-8").splitlines()
    i = next(k for k, ln in enumerate(lines) if start in ln)
    j = next(k for k in range(i + 1, len(lines)) if end in lines[k])
    return "\n".join(lines[i:j]).rstrip()


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


# ------------------------------------------------------------------ title
t = doc.add_paragraph()
r = t.add_run("DATA 260 Homework 9 Report")
r.bold, r.font.size = True, Pt(14)
p("Sreeram Achutuni  |  SJSU ID: 019151808  |  GitHub: https://github.com/sriram2930/Data260-1808")
p("Builds on HW8. Adds a Redis view counter, a Redis-vector semantic response cache in front of the HW8 "
  "Planner -> Writer -> Reviewer pipeline, a threshold/cost/staleness study, and a two-agent self-improving system.")

h1("Section 0: Config values")
table([
    ("Value", "Setting"),
    ("SID4 / PREFIX", "1808 / s1808  (every Redis key starts with s1808:)"),
    ("PORT_BASE / SEED / VERIFY_SEED", "8008 / 1808 / 261808"),
    ("DOMAIN_ID", "0, Campus course catalogue and enrolment (primary entity: Course; related tables in s1808_rel)"),
    ("Hardware", "Intel Core i7-11390H, 16GB RAM, integrated Iris Xe graphics (no dedicated GPU)"),
    ("Local model", "qwen2.5:1.5b-instruct via Ollama and the shared ModelClient adapter (all agents, temperature 0 in Part 4)"),
    ("Embeddings / vector store", "sentence-transformers/all-MiniLM-L6-v2 (384-d, normalised); Redis Stack 7.2 (redis/redis-stack-server), FLAT index, COSINE"),
    ("Databases / broker", "MySQL 8 (s1808_rel), Kafka 7.5 + Zookeeper (HW8 stack, unchanged)"),
    ("cache_cases.yaml committed in", f"{CASES_COMMIT}, before any threshold sweep was run"),
    ("HW9 code commit (tag hw9 is on the report-only commit after it)", FINAL_HASH),
], widths=[2.2, 4.6])

# ------------------------------------------------------------------ PART 1
h1("Part 1: Redis-backed view counter")
p("Primary entity: Course. A new column courses.view_count (migration Part-1/migrate_hw09.py) holds the durable count; "
  "CourseStore.increment_course_views(course_id) in Part-12/course_store.py is the one new method. Key format: "
  "s1808:views:course:<id>.")
code(
    "def increment_course_views(self, course_id: int) -> int:\n"
    "    count = self.redis_client.incr(self.views_key(course_id))      # atomic, in-memory\n"
    "    if count % SYNC_EVERY == 0:                                    # every 10th increment\n"
    "        with self._session_factory() as session:\n"
    "            session.execute(text(\"UPDATE courses SET view_count = :c WHERE id = :id\"),\n"
    "                            {\"c\": count, \"id\": course_id})\n"
    "            session.commit()\n"
    "        log.info(\"Synced views to database\")\n"
    "    return count"
)
shot("p1_counter.png", caption="Part 1: 25 accesses of CS-00005. The DB column changes only at access 10 and 20.")
shot("p1_infra.png", caption="Redis holds 25, MySQL view_count holds 20; the Redis container runs next to the HW8 stack.")
p("Result: 25 accesses cost 25 Redis INCRs and 2 database UPDATEs instead of 25. Trade-off: the database lags Redis by up "
  "to 9 views (here 20 vs 25), and a Redis crash before the next sync would lose those unsynced counts.")

# ------------------------------------------------------------------ PART 2
h1("Part 2: Semantic response cache")
p("The cache sits at the ingress of the course Q&A endpoint (Part-13/semantic_cache.py, SemanticCache.handle). "
  "Each request is embedded and matched against cached queries with a Redis KNN search over a COSINE vector index "
  "(similarity = 1 - distance). Similarity >= threshold (0.85 here) is a hit: the stored final answer is returned, "
  "is_cached=True, similarity logged, no agent run. Otherwise it is a miss: the question is grounded with the matching "
  "s1808_rel records and sent through the real HW8 pipeline over Kafka (s1808_inbox -> planner -> writer -> reviewer -> "
  "s1808_final); the query, embedding, final answer and a data-version marker are stored, and is_cached=False is returned. "
  "Timestamps are taken around the embedding, the Redis search, and the agent call.")
p("Core of the request handler (Part-13/semantic_cache.py, excerpt):")
code(src("Part-13/semantic_cache.py", "def handle(self, question", "# ---- miss path"), size=7.5)
code(src("Part-13/semantic_cache.py", "# ---- miss path", "def make_cache_with_kafka")[:1900], size=7.5)
shot("p2_index.png", caption="The vector index on the s1808:semcache: key prefix (HASH, FLAT, FLOAT32, COSINE).")
shot("p2_run_a.png", caption="14 queries at threshold 0.85, part 1 of 2 (misses call the real Kafka pipeline).")
shot("p2_run_b.png", caption="Part 2 of 2, with the summary.")
hits = [r for r in p2 if r["is_cached"]]
miss = [r for r in p2 if not r["is_cached"]]
mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
table([
    ("Measure (threshold 0.85, 14 queries)", "Measured"),
    ("Cache hit rate", f"{len(hits)}/{len(p2)} = {100 * len(hits) / len(p2):.1f}%  (3 exact duplicates at 1.000, 3 paraphrases at 0.90-0.94)"),
    ("Average latency, cached", f"{mean([r['latency_ms'] for r in hits]):.1f} ms  (n={len(hits)})"),
    ("Average latency, not cached", f"{mean([r['latency_ms'] for r in miss]):,.1f} ms  (n={len(miss)}; full Planner -> Writer -> Reviewer run)"),
], widths=[2.6, 4.2])
p("These are the measured values from this run; no speed-up was targeted. Of the 8 misses, all 8 were first-time questions. "
  "One of them (\"What is the capital of France?\") was answered \"Paris\" by the HW8 pipeline: the pipeline has no scope guard, "
  "which is what Part 4's decline lesson addresses.")

# ------------------------------------------------------------------ PART 3
h1("Part 3: Threshold economics and stale answers")
h2("3.1 Labeled test set")
cats = {}
for c in spec["cases"]:
    cats[c["category"]] = cats.get(c["category"], 0) + 1
p(f"Part-13/cache_cases.yaml holds 40 labeled queries (10 exact duplicates, 10 paraphrases, 10 superficially similar with a "
  f"different correct answer, 10 unrelated) plus the 10 seed queries the cache is warmed with. It was committed in "
  f"{CASES_COMMIT} before any sweep and not edited afterwards. The full list is in Appendix A. Labeling mistakes found after "
  f"seeing results: none. (C13, a paraphrase labeled should-hit, scored 0.835 and missed at 0.85 and above; that is the model "
  f"being less similar than I expected, not a wrong label, so the label stays.)")

h2("3.2 Threshold sweep")
p("For each threshold the cache was flushed, warmed with the 10 seeds, and the 40 cases were sent read-only (misses are not "
  "inserted, so every case sees the same cache). Cache-path time is measured live. Because re-running the ~20 s Kafka pipeline "
  "for every miss at five thresholds would take hours, each distinct query went through the real pipeline once beforehand "
  "(part3_precompute.py) and a miss in the sweep adds that recorded agent latency; so mean latency = live cache time + recorded real "
  "pipeline time for misses. Hit rate = hits/40. False hit = a hit on a should-miss case, or a hit that returned the wrong seed; "
  "false-hit rate = false hits / 20 should-miss cases.")
tab = [("Threshold", "Hit rate", "False-hit rate", "Mean latency (ms)", "Total cost")]
for s in sweep["summary"]:
    tab.append((f"{s['threshold']:.2f}", f"{100 * s['hit_rate']:.1f}% ({s['hits']}/40)",
                f"{100 * s['false_hit_rate']:.1f}% ({s['false_hits']}/20)", f"{s['mean_latency_ms']:,.1f}", f"${s['total_cost']:.3f}"))
table(tab, widths=[0.9, 1.4, 1.6, 1.6, 1.1])
shot("p3_sweep.png", caption="Sweep output. Missed hits (should-hit cases that missed): 0, 0, 1, 1, 9 of 20 at 0.75 to 0.95.")

h2("3.3 One false hit in full")
fh = next(r for r in rows if r["threshold"] == 0.85 and r["id"] == "C23")
table([
    ("Item", "Value"),
    ("Cached query (seed S03)", fh["matched_query"]),
    ("Incoming query (C23)", fh["query"]),
    ("Similarity score", f"{fh['similarity_to_best']:.4f}  (hit at every threshold from 0.75 to 0.95)"),
    ("Cached answer returned", fh["returned_answer"]),
    ("Correct answer", "12 seats (s1808_rel: DATA-00007, seats_available = 12)"),
], widths=[1.9, 4.9])
p("Why the model confused them: the two questions share 12 of 13 word-piece tokens. The embedding model's tokenizer splits "
  "the codes into ['data', '-', '000', '##0', '##6'] and ['data', '-', '000', '##0', '##7'], so the only difference is one "
  "trailing digit piece. A sentence embedding is dominated by the shared template (\"how many seats are available in course "
  "DATA-...\") and encodes an identifier digit very weakly. Similarity 0.994 is higher than every genuine paraphrase in the "
  "set (0.83-0.95), so no threshold can separate them: C22, C23, C28 and C29 (0.957-0.994) are false hits at every threshold.")

h2("3.4 Cost model and threshold choice")
p(f"Total cost = (queries not served from cache) x C_miss + (false hits) x C_false.  C_miss = ${sweep['c_miss']:.3f}: one miss runs "
  "the 3-call pipeline (roughly 1.5k tokens at about $1-3 per million tokens on a small hosted model, plus compute; it took "
  "about 23 s here). C_false = $2.00: a wrong seat count, room or instructor presented as authoritative sends a student to the wrong "
  "place or triggers a support contact; I assume about 3 minutes of staff time at roughly $40/hour. Both figures are assumptions, "
  "not measurements. C_false is 400x C_miss because a wrong answer costs a human, while a miss costs a few cents of compute.")
sens = sweep["sensitivity"]
table([("C_false", "0.75", "0.80", "0.85", "0.90", "0.95", "Cheapest")] + [
    (f"${float(cf):.2f}", *[f"${v:,.3f}" for v in d.values()], f"{min(d, key=d.get)}") for cf, d in sens.items()
], size=9)
p("Decision: ship 0.90. It is the cheapest threshold at C_false = $0.10, $2 and $20 alike. Going lower buys no extra correct hits "
  "(missed hits are already 1 of 20) but adds false hits: C30 at 0.861 for 0.85 and 0.80, then C25, C21, C24 at 0.75; going to 0.95 removes none of the four remaining "
  "false hits yet loses 8 more correct paraphrase hits (45% missed hits), costing $0.04 more than 0.90. "
  "Honest caveat: 0.90 still has a 20% false-hit rate on these should-miss cases (4/20), all of them same-template questions that "
  "differ only in a course code. I would not rely on the threshold alone for this domain. Post-hoc observation, not part of "
  "the sweep and checked only on this same 40-case set: also requiring the course codes in the two queries to match would have "
  f"blocked those four ({guard['0.9'][0]} hits at 0.90 become {guard['0.9'][1]}, with {guard['0.9'][2]} false hits). It needs "
  "fresh data before anyone trusts it.")

h2("3.5 Stale answers and invalidation")
p("Cached query: \"How many seats are available in course CS-00005?\", whose answer depends on one s1808_rel record "
  "(courses.seats_available for CS-00005). Each cache entry stores data_version, a hash of the full content of the database rows "
  "the answer was built from (domain_facts.py).")
shot("p3_stale.png", caption="Stale hit, then invalidation by data-version check, then a fresh answer.")
bullets([
    f"Update: seats_available 30 -> 12. The row's hash changes from {stale['first']['data_version']} to {stale['invalidated']['data_version']}; the cached entry still stores the old one.",
    f"Stale hit (no validation): the paraphrase hits at similarity {stale['stale_hit']['similarity']:.3f} in {stale['stale_hit']['latency_ms']:.0f} ms and returns the old answer: \"{stale['stale_hit']['answer']}\" while the database says 12.",
    f"Strategy implemented: validate on read. On every hit, re-hash the source rows of the cached query and compare with the stored data_version; a mismatch evicts the entry and falls through to the miss path. The same query then missed ({stale['invalidated']['latency_ms']:,.0f} ms), the pipeline answered \"{stale['invalidated']['answer']}\", and the next ask was a fresh valid hit.",
    f"Trade-off: it never serves a stale answer for rows it hashes, but every hit now costs a database read: {stale['overhead_ms']['without']:.1f} ms -> {stale['overhead_ms']['with']:.1f} ms per valid hit (+{stale['overhead_ms']['with'] - stale['overhead_ms']['without']:.1f} ms, 15 runs each). That is still about 400x cheaper than a miss, but it adds load on the database the cache was meant to protect, needs the dependency rows to be recomputable from the cached query, and cannot see changes to rows it did not hash. A TTL would avoid the read but leaves a stale window.",
])

# ------------------------------------------------------------------ PART 4
h1("Part 4: Self-improving two-agent system")
p("Files in Part-14: agents.py (AnsweringAgent, EvaluatorAgent, LessonStore, solve), reference_dataset.json (4 departments, 26 courses "
  "with sections, exported from s1808_rel), training_data.json / validation_data.json / test_data.json (20 questions each; only id and "
  "question, no answers), lessons.json. Question mix per split: multi-fact course questions, department questions, a seat comparison, "
  "out-of-scope questions and nonexistent course codes. The test set was read only by run_variants.py, after the lesson was chosen.")
h2("Agent communication, stopping condition")
p("The agents exchange plain dicts. The Answering Agent retrieves live catalogue facts (s1808_rel), loads relevant lessons into its "
  "system prompt, and returns {answer, lessons_used}. The Evaluator Agent never sees those facts: it checks the answer against "
  "reference_dataset.json (its own ground truth) and returns {PASS|REVISE, explanation, feedback, failure patterns}. On REVISE the "
  "feedback goes back to the Answering Agent as a new chat turn after its own previous answer. solve() allows at most 2 answer "
  "attempts: it stops on the first PASS or after the second attempt, whatever the result. The Evaluator is deterministic (rules "
  "and string matching over the reference data), not an LLM judge.")
code(
    "def solve(question, answerer, evaluator, max_attempts=2, ...):\n"
    "    for attempt in range(1, max_attempts + 1):\n"
    "        out = answerer.answer(question, feedback=feedback, previous_answer=prev, ...)\n"
    "        ev = evaluator.evaluate(question, out['answer'])      # PASS | REVISE + feedback\n"
    "        if ev.result == 'PASS': break\n"
    "        feedback, prev = ev.feedback, out['answer']          # loop ends after attempt 2",
)
p("Answering Agent (Part-14/agents.py, AnsweringAgent.answer):", bold=True)
code(src("Part-14/agents.py", "    def answer(self, question: str, feedback", "# ----"), size=7.5)
p("Evaluator Agent (Part-14/agents.py, EvaluatorAgent.evaluate):", bold=True)
code(src("Part-14/agents.py", "    def evaluate(self, question: str, answer: str)", "# ----"), size=7.5)
h2("4.1 Controlled revision sequence")
p("The first answer is injected (incomplete on purpose) so the repair path can be shown reliably; the revision is real model output.")
shot("p4_demo_revision.png", caption="Question, initial answer, evaluator feedback, revised answer, final evaluation, attempts, final response.")
h2("4.2 Saving and reusing lessons")
p("Development used training_data.json only (Evaluator Repair, no lessons): 16/20 passed on the first attempt, 17/20 after repair. "
  "A failure pattern that occurs on at least 2 distinct questions becomes a lesson: 'unsupported_answer' occurred on 3 (capital of France, "
  "FIFA World Cup, sourdough). 'missing_fact:seats' occurred on only 1 question, so no lesson was made for it.")
shot("p4_training.png", caption="Training run and the lesson it produced.")
code(json.dumps([{k: lesson[k] for k in ("lesson_id", "failure_pattern", "correction", "created_at", "use_count")} for lesson in lessons], indent=1), size=8)
p("lessons.json also carries trigger, pattern_key and status fields (candidate / kept / rejected). use_count is 0 here because "
  "validation and the final test write usage to scratch copies. The demonstration below uses a scratch lessons file and a "
  "controlled failure (one failed answer is enough in demo mode) to show a lesson being created, then loaded and used for a later question.")
shot("p4_demo_lesson.png", caption="A lesson from one failed answer is loaded before the later question and its use_count goes 0 -> 1.")
p("Caveat: the later question would very likely have passed without the lesson too, so this demonstrates loading and reuse, not "
  "that the lesson changed the outcome. The measured effect of the real lesson is in 4.3 and 4.4.")
h2("4.3 Validation before keeping a lesson")
p("Each candidate lesson is run on validation_data.json single-attempt, before (no lessons) and after (that lesson only). It is kept "
  "only if no previously correct answer becomes incorrect, correct answers do not decrease, and no out-of-scope question newly gets an "
  "unsupported answer. Single attempt is used so the repair loop cannot hide the lesson's effect.")
shot("p4_validation.png", caption="lesson_001: 16/20 -> 17/20 correct, fixed va14, no regressions: KEPT.")
p("The lesson fixed 1 of the 4 failing validation questions (the recipe question) and left the other two out-of-scope questions "
  "(tallest mountain, haiku) and the seat comparison unchanged. Nothing regressed, so it was kept. The gate never had to reject a lesson.")
h2("4.4 Four system variants on test_data.json")
tt = [("Variant", "Correct answers", "Incorrect answers", "Average attempts", "Average latency")]
for r in test["table"]:
    tt.append((r["variant"], f"{r['correct']}/20", f"{r['incorrect']}/20", f"{r['avg_attempts']:.2f}", f"{r['avg_latency_s']:.2f} s"))
table(tt, widths=[1.9, 1.3, 1.3, 1.2, 1.1])
shot("p4_variants.png", caption="Final run: each variant on the same unchanged 20-question test set.")
p("Reading the table honestly: first-attempt correctness is 15/20 in every variant. Evaluator Repair fixed one question (the seat "
  "comparison, te10) on the second attempt. The lesson helped only together with feedback: with lesson_001 loaded, two out-of-scope questions "
  "(te12 Mona Lisa, te14 photosynthesis) passed on attempt 2, which Evaluator Repair alone had not managed. The lesson did not change any "
  "first answer. Lesson Memory and Validated Improvement are identical because there was only one lesson and it passed validation, so "
  "these two rows are not independent evidence that the validation gate works. With 20 test questions, 15 -> 18 is a 3-question difference, "
  "and latency differences of a few tenths of a second are within run-to-run noise (Evaluator Repair, which does extra work, averaged "
  "lower than Baseline).")
h2("One limitation")
p("The Evaluator is strict string matching against the reference. On te09 (\"building and department code for Data Science & AI\") the "
  "answer \"The building code is MacQuarrie Hall and the department code is DATA\" failed in every variant because the reference building "
  "is \"MacQuarrie Hall, Room 420\" and the room is missing; a human might accept it as mostly right. The Evaluator also cannot judge a "
  "free-form answer, and the 1.5B model still ignores the decline instruction on some out-of-scope questions (te13 blockchain failed "
  "twice even with feedback and the lesson). I did not change the evaluator after seeing test results.")

# ------------------------------------------------------------------ verification
h1("Self-check")
shot("verify.png", caption="verify_hw09.py: 23/23 checks passed (counter, cache hit/miss, stale invalidation, dataset hygiene, evaluator, 2-attempt stop).")

# ------------------------------------------------------------------ appendices
h1("Appendix A: cache_cases.yaml (Part-13/cache_cases.yaml)")
p("Seeds cached before every sweep: " + "; ".join(f"{s['id']} {s['query']}" for s in spec["seeds"]), italic=False)
at = [("ID", "Category", "Query", "Expected")]
for c in spec["cases"]:
    exp = "hit" if c["should_hit"] else f"miss ({c['correct_answer']})" if c.get("correct_answer") else "miss"
    at.append((c["id"], c["category"], c["query"], exp))
table(at, widths=[0.5, 1.3, 3.8, 1.4], size=8)

h1("Appendix B: Part 4 input questions (full files are in Part-14)")
for fname in ("training_data.json", "validation_data.json", "test_data.json"):
    data = json.loads((REPO / "Part-14" / fname).read_text(encoding="utf-8"))
    p(fname + " (" + str(len(data)) + " questions, no answers):", bold=True)
    code("\n".join(f"{d['id']}  {d['question']}" for d in data), size=8)
p("reference_dataset.json (full ground truth used by the Evaluator; file in Part-14):", bold=True)
ref = json.loads((REPO / "Part-14" / "reference_dataset.json").read_text(encoding="utf-8"))
table([("Department", "Code", "Building")] + [(d["name"], d["dept_code"], d["building"]) for d in ref["departments"]], size=8)
rt = [("Course", "Title", "Department", "Seats", "Section (semester / instructor / enrolled)")]
for c in ref["courses"]:
    sec = "; ".join(f"{x['semester']} / {x['instructor']} / {x['enrolled_count']}" for x in c["sections"]) or "-"
    rt.append((c["course_code"], c["course_title"], c["department"], c["seats_available"], sec))
table(rt, widths=[0.9, 1.9, 1.3, 0.5, 2.2], size=7.5)
p("Course codes not listed (e.g. CS-09999, DATA-09001, ENGR-09999, CS-08888, DATA-09999, BUS-07777) do not exist; the Evaluator expects a decline for them.", italic=True)

# ------------------------------------------------------------------ AI use
h1("AI Use Statement")
h2("1. What AI was used for")
p("The assignment, the Course-catalogue domain, the HW1-HW8 repository and the local environment are mine. I used Claude Code to design "
  "and write the Redis counter, the semantic cache and vector index, the threshold sweep, stale-answer demo and cost model, the two-agent "
  "system with lessons and validation, the verification script and this report, and to start the Redis/MySQL/Kafka containers. "
  "Everything was run for real: Redis Stack, MySQL and Kafka in Docker, and Ollama for every model call. The only replayed element is "
  "disclosed in 3.2 (recorded real pipeline answers/latencies reused for the 5-threshold sweep).")
h2("2. AI output that was wrong or unsuitable")
bullets([
    "The first Redis import path (redis.commands.search.indexDefinition) does not exist in the installed redis-py (it is index_definition). It failed on the first run.",
    "The seeded data had seats_available = 30 for all 5,000 courses, so any two 'how many seats' questions had the same correct answer and could not serve as 'different correct answer' cases. I gave three records distinct seat counts (and reset CS-00005 to 30) (Part-13/seed_hw09.py).",
    "The first Answering Agent revision prompt put the previous answer and the feedback into one user message. On the training set the 1.5B model repeated its first answer word for word (on the three traces I inspected), so repair fixed 0 questions (raw/part4_training_run_v1_single_prompt.txt). Sending the feedback as a separate chat turn fixed the seat comparison (16 -> 17/20 after repair).",
])
h2("3. How the problems were detected")
p("By running the code and reading real output: the import error on the first run, the database query that showed every course had 30 seats, "
  "the training trace where attempt 2 was identical to attempt 1, and a direct before/after prompt test on training questions only.")
h2("4. What changed and why it works now")
p("The import path is fixed; seat data is seeded idempotently; revision feedback is a proper chat turn; the evaluator was not changed "
  "after the test set was read. Still unresolved and stated above: the threshold alone cannot separate course codes that differ by "
  "one digit, and the 1.5B model often ignores a decline instruction.")

doc.save(HERE / "Achutuni_HW9.docx")
print("wrote", HERE / "Achutuni_HW9.docx")
