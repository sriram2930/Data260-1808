"""One-off script assembling the HW10 Word report (then exported to PDF). Not part of the graded deliverable; kept so the
report can be regenerated. Every number in the tables comes from the captured files in raw/ -- only prose is typed.

Usage:  python generate_report.py [final_commit_hash]
"""

import collections
import csv
import json
import re
import statistics as st
import sys
from pathlib import Path

import docx
import numpy as np
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

HERE = Path(__file__).parent
RAW = HERE / "raw"
SHOTS = HERE / "screenshots"
REPO = HERE.parent.parent
FINAL_HASH = sys.argv[1] if len(sys.argv) > 1 else "(filled in after the final commit)"
LABELS_COMMIT = "0318870"  # eval_cases.json + human_labels.csv, committed before any judge score for them existed

j = lambda name: json.loads((RAW / name).read_text(encoding="utf-8"))  # noqa: E731
jl = lambda name: [json.loads(x) for x in (RAW / name).read_text(encoding="utf-8").splitlines() if x.strip()]  # noqa: E731
spans = jl("spans.jsonl")
exp = j("latency_experiment.json")
lat = j("latency_table.json")
val = j("judge_validation.json")
ex = j("trace_examples.json")
cases = json.loads((REPO / "Part-15" / "eval_cases.json").read_text(encoding="utf-8"))
labels = {r["case_id"]: int(r["human_label"]) for r in csv.DictReader((REPO / "Part-15" / "human_labels.csv").open(encoding="utf-8"))}
evals = {}
for e in jl("evaluations.jsonl"):
    evals[e["trace_id"]] = e  # last record per trace wins (8 traces were re-run after the empty-context fix)
ids50 = [r["trace_id"] for r in exp["requests"]]
ev50 = [evals[i] for i in ids50 if evals[i]["status"] == "ok"]
verif = j("../verification.json")

by = collections.defaultdict(dict)
queue = collections.defaultdict(float)
for s in spans:
    if s["stage"].startswith("queue_"):
        queue[s["trace_id"]] += s["duration_ms"]
    else:
        by[s["trace_id"]][s["stage"]] = s["duration_ms"]

doc = docx.Document()
for s_ in doc.sections:
    s_.left_margin = s_.right_margin = Inches(0.9)
    s_.top_margin = s_.bottom_margin = Inches(0.8)


def style(name, size, bold=False):
    stl = doc.styles[name]
    stl.font.name = "Calibri"
    stl.font.size = Pt(size)
    stl.font.bold = bold
    stl.font.color.rgb = RGBColor(0, 0, 0)


style("Normal", 11)
style("Heading 1", 14, True)
style("Heading 2", 12, True)
doc.styles["Normal"].paragraph_format.space_after = Pt(5)

h1 = lambda t: doc.add_heading(t, level=1)  # noqa: E731
h2 = lambda t: doc.add_heading(t, level=2)  # noqa: E731
FIG = [0]
FIGNUM = {}
CROP = HERE / "screenshots_crop"
CROP.mkdir(exist_ok=True)


def p(text, bold=False, italic=False):
    para = doc.add_paragraph()
    r = para.add_run(text)
    r.bold, r.italic = bold, italic
    return para


def code(text, size=7.5):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(4)
    r = para.add_run(text)
    r.font.name = "Consolas"
    r.font.size = Pt(size)


def prep(name: str) -> Path:
    """Dashboard PNGs: trim the blank area below the content so the page is not wasted on whitespace."""
    src_p = SHOTS / name
    if not name.startswith("d"):
        return src_p
    im = Image.open(src_p).convert("RGB")
    a = np.asarray(im)[:, 330:, :]
    rows = np.where((a < 245).any(axis=(1, 2)))[0]
    bottom = min(im.height, int(rows.max()) + 40) if len(rows) else im.height
    out = CROP / name
    im.crop((0, 0, im.width, bottom)).save(out)
    return out


def shot(name, caption, width=6.5, maxh=8.3):
    path = prep(name)
    w, h = Image.open(path).size
    width = min(width, maxh * w / h)
    doc.add_picture(str(path), width=Inches(width))
    FIG[0] += 1
    FIGNUM[name] = FIG[0]
    c = doc.add_paragraph()
    r = c.add_run(f"Screenshot {FIG[0]}: {caption}")
    r.italic = True
    r.font.size = Pt(10)


def cshot(name, caption, width=6.2):
    path = HERE / "code_shots" / name
    w, h = Image.open(path).size
    doc.add_picture(str(path), width=Inches(min(width, 7.4 * w / h)))
    FIG[0] += 1
    FIGNUM[name] = FIG[0]
    c = doc.add_paragraph()
    r = c.add_run(f"Screenshot {FIG[0]}: {caption}")
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
    k2 = next(k for k in range(i + 1, len(lines)) if end in lines[k])
    return "\n".join(lines[i:k2]).rstrip()


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


pc = lambda x, q: float(np.percentile(x, q))  # noqa: E731
fmt = lambda v: f"{v:,.0f}" if v >= 100 else f"{v:,.1f}"  # noqa: E731

# ============================================================== derived numbers used in the prose
tbl = {t["stage"]: t for t in lat["table"]}
req_total = sum(by[i]["request"] for i in ids50)
verb = [e for e in ev50 if e["draft"].strip() == e["final"].strip()]
rev_on_verb = sum(by[e["trace_id"]]["reviewer"] for e in verb)
sc = lambda key: [e[key]["score"] for e in ev50]  # noqa: E731
plan_s, draft_s, final_s = sc("plan_quality"), sc("writer_helpfulness"), sc("final_helpfulness")
diffs = [e["improvement"]["difference"] for e in ev50]
up, same, down = sum(d > 0 for d in diffs), sum(d == 0 for d in diffs), sum(d < 0 for d in diffs)
is_catalog = lambda q: bool(re.search(r"[A-Z]{2,4}-\d{5}", q) or "department" in q.lower())  # noqa: E731
on = [e for e in ev50 if is_catalog(e["question"])]
off = [e for e in ev50 if not is_catalog(e["question"])]
mean = lambda xs, k: st.mean(e[k]["score"] for e in xs)  # noqa: E731
best = max(ev50, key=lambda e: e["improvement"]["difference"])
worst = min(ev50, key=lambda e: e["improvement"]["difference"])
draft_len = st.mean(len(e["draft"]) for e in ev50)
final_len = st.mean(len(e["final"]) for e in ev50)
reqs = [s for s in spans if s["stage"] == "request"]
n_req = len(reqs)
n_hit = sum(s["attrs"].get("path") == "cache_hit" for s in reqs)
n_miss = sum(s["attrs"].get("path") == "cache_miss" for s in reqs)
n_err = sum(s["status"] == "error" for s in reqs)
hit_lat = [s["duration_ms"] for s in reqs if s["attrs"].get("path") == "cache_hit"]
hl = np.array(hit_lat)
human = np.array([labels[c["case_id"]] for c in cases])
jud = {c["case_id"]: val["per_case"][k] for k, c in enumerate(cases)}

# ============================================================== title + config
t = doc.add_paragraph()
r = t.add_run("DATA 260 Homework 10 Report")
r.bold, r.font.size = True, Pt(14)
p("Sreeram Achutuni  |  SJSU ID: 019151808  |  GitHub: https://github.com/sriram2930/Data260-1808")
p("Builds on HW8 (Kafka Planner -> Writer -> Reviewer pipeline) and HW9 (Redis semantic cache). Adds end-to-end trace spans, "
  "a DeepEval G-Eval evaluator, a validation of that judge against my own human labels, a 50-request stage-latency "
  "experiment, and a three-page Streamlit operations dashboard.")

h1("Section 0: Config values")
table([
    ("Value", "Setting"),
    ("SID4 / PREFIX", "1808 / s1808  (Kafka topics s1808_*, Redis keys s1808:*, MySQL s1808_rel)"),
    ("PORT_BASE / SEED / VERIFY_SEED", "8008 / 1808 / 261808"),
    ("DOMAIN_ID", "0, Campus course catalogue and enrolment (unchanged from HW8/HW9)"),
    ("Hardware", "Intel Core i7-11390H, 16GB RAM, integrated Iris Xe graphics (no dedicated GPU); everything below ran on this machine"),
    ("Pipeline models (HW8 agents)", "qwen2.5:1.5b-instruct via Ollama (Planner, Writer, Reviewer), unchanged apart from span logging"),
    ("Judge model", "qwen3:8b via local Ollama, DeepEval 4.3.4 GEval; temperature 0, seed 1808, thinking off, max 400 new tokens, 180 s request timeout; 1-5 scale"),
    ("Cache (HW9, reused)", "all-MiniLM-L6-v2 embeddings, Redis Stack FLAT/COSINE index, threshold 0.90, data-version validation on every hit"),
    ("Infrastructure", "Kafka 7.5 + Zookeeper, MySQL 8, Redis Stack 7.2 (Docker); Streamlit 1.67; Python 3.12 virtualenv"),
    ("eval_cases.json + human_labels.csv committed in", f"{LABELS_COMMIT}, before any judge score existed for them"),
    ("HW10 final code commit", FINAL_HASH),
], widths=[2.2, 4.6])
p("Where things are: Part-15/ holds all new code (tracing.py, qa_service.py, judge.py, evaluator.py, validate_judge.py, "
  "latency_experiment.py, latency_report.py, dashboard.py, label_tool.py). Part-11/kafka_utils.py and the three agents received a small "
  "span hook. verify_hw10.py is the self-check. Raw evidence is in reports/hw10/raw/.", italic=True)

# ============================================================== PART 1
h1("Part 1: Streamlit operations dashboard")
p("The dashboard (Part-15/dashboard.py, run with: streamlit run Part-15/dashboard.py) reads only files the system itself writes: "
  "spans.jsonl (one JSON span per stage), evaluations.jsonl, judge_validation.json and trace_examples.json. Nothing on it is simulated.")
h2("1.1 Summary page")
table([
    ("Metric", "Time window", "Data source"),
    ("Recent request count", "selectable: last 1 h / 6 h / 24 h / 7 d / all (default all); the exact first/last request time is printed", "spans.jsonl, spans with stage=request"),
    ("Semantic-cache hit rate (hits and misses shown separately)", "same window", "request spans, attrs.path = cache_hit vs cache_miss (the cache_lookup outcome)"),
    ("Error rate", "same window", "request spans with status=error / all request spans"),
    ("End-to-end latency", "same window; hit and miss reported separately (p50, p95, mean)", "request span duration (cache lookup start to answer returned)"),
    ("Stage latency on successful misses", "same window", "all spans joined on trace_id"),
], widths=[2.0, 2.5, 2.3], size=9)
p("Caching: parsing the JSON-lines files and the Redis connection are the reusable, relatively expensive parts, so the loaders use "
  "@st.cache_data keyed on the file's modification time (a changed file refreshes automatically) and the Redis client uses "
  "@st.cache_resource (one shared connection). Light dataframe filtering is recomputed on every rerun, which is cheap.")
cshot("c7_dashboard_cache.png", "Part-15/dashboard.py: the cached loaders (@st.cache_data keyed on file mtime) and the shared Redis connection (@st.cache_resource).", width=5.4)
shot("d1_summary_all.png", "Summary page, window = all recorded data. The hit rate here is low on purpose: it contains the 50-request experiment, which is all misses by design, and the page says so.", width=6.0)
shot("d1_summary_1h.png", "Summary page, window = last hour at capture time: the mixed traffic run (8 first-time questions then 8 repeats/rewordings) plus the three Part 4.2 example requests. 9 hits, 9 misses, 1 error (the deliberate malformed message).", width=6.0)
p(f"Reading the 1-hour window: cache hits answered in a median {pc(hl, 50):.0f} ms (p95 {pc(hl, 95):.0f} ms) while misses took a median 17.1 s (p95 31.7 s), "
  f"several hundred times longer, which is why the two are never averaged together. Over the whole recorded data there were {n_req} requests: "
  f"{n_hit} hits, {n_miss} misses and {n_err} error.")
h2("1.2 Evaluation page")
p("Shows the Part 2 results (scores by case and by pipeline stage, plus the score distribution) and the Part 3 judge validation "
  "(Spearman correlation, mean absolute difference, repeatability, the per-case table and the verdict). The interpretation text under "
  "the Part 2 table is generated from the numbers on the page, not typed.")
shot("d2a_evaluation_part2.png", "Evaluation page, Part 2: per-case scores for the Planner, Writer and Reviewer stages (scrollable table), the score distribution and the interpretation. The page averages all 51 evaluated traces (the 50 experiment traces plus the Part 4.2 example), so its means differ slightly from the 50-trace tables in Part 2.", width=6.2)
shot("d2b_evaluation_part3.png", "Evaluation page, Part 3: Spearman, mean absolute difference and repeatability from the 20 frozen cases, the per-case table and the verdict.", width=6.0)
h2("1.3 Trace lookup page")
p("A text box takes a trace_id (three buttons load the required example traces). The page shows every span of that trace in stage order with "
  "start time, end time, duration, status, detail and error, a timeline chart, and a banner that states the path: green CACHE HIT "
  "(no Kafka stage ran), blue CACHE MISS (inbox to final), or red FAILED with the failing stage and error. If the trace was "
  "evaluated, its judge scores are shown underneath.")
shot("d3_trace_hit.png", f"Trace lookup, cache-hit path (trace {ex['cache_hit']}): only cache_lookup and request spans exist.", width=5.6)
shot("d3_trace_miss.png", f"Trace lookup, cache-miss path (trace {ex['cache_miss_success']}): every stage in order, then the offline evaluation span and its scores.", width=5.6)
shot("d3_trace_failed.png", f"Trace lookup, failed path (trace {ex['failed']}): the planner span has status=error, KeyError: 'question', 3 attempts.", width=5.6)

# ============================================================== PART 2
h1("Part 2: Automated evaluation of the Kafka pipeline")
h2("2.1 Inputs and linkage")
p("Part-15/qa_service.py wraps the HW9 cache in front of the HW8 pipeline. Its MessageCollector consumes s1808_tasks (Planner plan), "
  "s1808_drafts (Writer draft), s1808_final (Reviewer answer) and s1808_dead_letter, and appends every raw message with its topic, partition, "
  "offset and Kafka timestamp to raw/messages.jsonl. Part-15/evaluator.py loads those rows and joins them on correlation_id, which is the "
  "trace_id (no second identifier exists). The saved evaluation record keeps the original question, grounding facts, plan, draft, final, "
  "message metadata and the judge settings, so any score can be reproduced.")
p("The evaluator is bounded: every judge request has a 180 s timeout and a per-trace budget of 900 s; a missing or malformed message or an "
  "unavailable judge returns status=error with the reason instead of raising or hanging; the evaluation always writes its span. Cache-hit "
  "traces have no plan or draft (the agents never ran), so they are not evaluated.")
cshot("c4_judge.png", "Part-15/judge.py: the G-Eval metric (rubric 1-5, evaluation steps) and the bounded judge() call that never raises.", width=6.0)
cshot("c5_evaluate_trace.png", "Part-15/evaluator.py: evaluate_trace joins plan/draft/final, scores the four criteria within a time budget, and writes the evaluation span.", width=6.2)
h2("2.2 Criteria and results")
table([
    ("Criterion", "Judged text", "Saved with the score"),
    ("Plan Quality", "Planner plan vs the question", "score + reason"),
    ("Writer Helpfulness", "Writer draft vs question and catalogue facts", "score + trace_id"),
    ("Final Answer Helpfulness", "Reviewer final vs question and catalogue facts", "score + final answer"),
    ("Final-vs-Draft Improvement", "final score minus draft score", "both scores, the difference, an interpretation"),
], widths=[1.8, 2.7, 2.3], size=9)
p("All criteria use one 1-5 scale (1 very poor, 5 excellent), the same scale as the human labels. G-Eval is given explicit evaluation steps and a "
  "five-level rubric, and returns (score-1)/4, which I convert back to the integer 1-5.")
shot("t3_evaluator_example.png", "End-to-end test question: one saved evaluation record (the cache-miss example trace). All four required criteria, the message offsets used for the join and the judge settings.", width=6.4)
shot("t3_evaluator.png", "First evaluator pass over the 50 latency-experiment traces (excerpt; full log in raw/evaluator_run.txt). The ERROR lines are the 8 traces that hit the empty-context bug described in 2.3; they were re-run after the fix (raw/evaluator_rerun.txt) and all 50 ended ok.", width=6.4)
table([
    ("Stage (n = 50 traces)", "Mean score", "Score 1", "2", "3", "4", "5"),
    *[(name, f"{st.mean(s_):.2f}", *[sum(x == k for x in s_) for k in range(1, 6)]) for name, s_ in
      (("Planner: plan quality", plan_s), ("Writer: draft helpfulness", draft_s), ("Reviewer: final helpfulness", final_s))],
], widths=[2.4, 0.9, 0.6, 0.5, 0.5, 0.5, 0.5], size=9)
table([
    ("Final vs draft (n = 50)", "Traces", "Detail"),
    ("Final scored higher", up, f"largest gain +{best['improvement']['difference']}"),
    ("Same score", same, f"{len(verb)} of the 50 finals are word-for-word identical to the draft"),
    ("Final scored lower", down, f"largest loss {worst['improvement']['difference']}"),
    ("Mean final - draft", f"{st.mean(diffs):+.2f}", f"mean answer length {draft_len:.0f} -> {final_len:.0f} characters"),
], widths=[2.4, 0.9, 3.5], size=9)
h2("2.3 What the scores indicate about coordination")
bullets([
    f"The Planner scores highest ({st.mean(plan_s):.2f}) and the Writer lower ({st.mean(draft_s):.2f}), so the weak stage is the Writer turning a good plan into a draft, not the plan. "
    f"Plan quality is the same for catalogue questions ({mean(on, 'plan_quality'):.2f}) and off-topic ones ({mean(off, 'plan_quality'):.2f}): the Planner never reacts to scope.",
    "A caveat on the plan score: the Planner receives the grounded prompt, so its plan can already contain the answer. In the example trace the plan is "
    "'- Department offering DATA-00007: Data Science & AI department / - Seats available in DATA-00007: 12'. The rubric says a plan should not answer the "
    "question, yet that plan scored 5, so this judge does not enforce that part of the criterion.",
    f"The Reviewer did not improve the answer in any meaningful way: mean final - draft = {st.mean(diffs):+.2f}. It improved {up} traces, left {same} unchanged "
    f"and worsened {down}; in {len(verb)} of 50 traces it returned the draft verbatim. I am reporting this as found rather than forcing a positive conclusion.",
    f"Where the Reviewer helped it mostly rewrote a weak draft into a short one (e.g. '{best['question']}': {best['improvement']['draft_score']} -> "
    f"{best['improvement']['final_score']}). Where it hurt it removed or invented content (e.g. '{worst['question']}': {worst['improvement']['draft_score']} -> "
    f"{worst['improvement']['final_score']}). For 'Recommend a good book about the Roman Empire' (2 -> 1) the final names a book title and author that I could not verify and that look fabricated.",
    f"Off-topic questions (n={len(off)}) score {mean(off, 'writer_helpfulness'):.2f} for the draft and {mean(off, 'final_helpfulness'):.2f} for the final; catalogue questions "
    f"(n={len(on)}) {mean(on, 'writer_helpfulness'):.2f} and {mean(on, 'final_helpfulness'):.2f}. The pipeline has no scope guard, so off-topic questions get fluent general-knowledge answers that this judge scores low.",
    "A bug found while running this: the first evaluator pass failed on 8 of 50 traces with MissingTestCaseParamsError, because DeepEval's G-Eval rejects an empty "
    "context and questions with no matching catalogue facts have none. I now pass 'no catalogue facts matched this question' as the context, re-ran those 8, and all 50 evaluated with 0 errors.",
])

# ============================================================== PART 3
h1("Part 3: Validate the judge")
h2("3.1 Frozen evaluation cases")
p("eval_cases.json holds 20 Writer drafts produced by the running pipeline for 20 fixed questions (catalogue lookups, department questions, comparisons, "
  "ambiguous ones, two off-topic, two nonexistent courses, one about data the catalogue does not hold). The questions were written before any draft "
  "existed and no draft was re-selected. I assigned the 1-5 human label for each draft myself through a one-click page (Part-15/label_tool.py) that "
  "shows the question, the facts and the draft and no judge score. The two files were committed before the judge ever scored them and have not changed since.")
shot("t4_freeze.png", "Freeze evidence: the commit of the two files (23:46:38) precedes the first judge-score file for these drafts (created 00:08); git status shows no change since.", width=6.4)
h2("3.2 Judge vs human labels")
rho = val["spearman_rho"]
table([
    ("Measure (n = 20, judge run 1)", "Value"),
    ("Spearman rank correlation (human vs judge)", f"{rho:.3f}  (p = {val['spearman_p']:.2f}, not significant)"),
    ("Mean absolute difference", f"{val['mean_abs_diff']:.2f} points on the 1-5 scale"),
    ("Mean signed difference (judge - human)", f"{val['mean_signed_diff_judge_minus_human']:+.2f}  (the judge is stricter)"),
    ("Exact agreement / within 1 point", f"{val['exact_agreement']} / 20  and  {val['within_one']} / 20"),
    ("Human label distribution", "5 x 12, 4 x 7, 3 x 1 (no 1s or 2s)"),
    ("Judge score distribution (run 1)", ", ".join(f"{k} x {v}" for k, v in sorted(collections.Counter(int(x['judge_run1']) for x in val['per_case']).items(), reverse=True))),
], widths=[3.0, 3.8], size=9.5)
cshot("c6_validation_stats.png", "Part-15/validate_judge.py: Spearman, mean absolute difference and the repeatability statistics, all recomputable from judge_scores.csv.", width=6.2)
shot("t4_judge_validation.png", "Judge validation run (excerpt of the 60 judge calls) and the computed statistics and verdict.", width=6.2, maxh=7.6)
table([("Case", "Question", "Human", "Judge r1", "Judge r2", "Judge r3", "|diff| r1")] +
      [(c["case_id"], c["question"][:62], labels[c["case_id"]], jud[c["case_id"]]["judge_run1"], jud[c["case_id"]]["judge_run2"],
        jud[c["case_id"]]["judge_run3"], jud[c["case_id"]]["abs_diff_run1"]) for c in cases],
      widths=[0.5, 3.4, 0.6, 0.6, 0.6, 0.6, 0.6], size=8)
p("Raw per-case data (human labels, three judge runs, judge reasons) are in raw/judge_scores.csv and raw/judge_runs.json, so every statistic can be recomputed (verify_hw10.py does).", italic=True)
p("Why the agreement is poor. The correlation is slightly negative and the judge sits a full point below the labels on average. Reading the judge's "
  "reasons for the largest gaps gives three different causes, and they should not be blended into one explanation:", bold=False)
bullets([
    "Rubric disagreement (c16 Mona Lisa 5 vs 1, c17 hash table 5 vs 3): my judge criterion says an off-catalogue question is best answered by saying it is out of scope, "
    "while the human label rewarded a correct general-knowledge answer. The judge applies a policy the labeller did not.",
    "Strictness on padding (c01, c18, c19, c20, 4-5 vs 3): the judge marks down correct answers for extra sentences that were not requested.",
    "Possible label leniency (c14 5 vs 1, c10 5 vs 2): c14's draft invents a 'University Name' graduate program for 'Advanced Database Systems' when no catalogue facts exist, and "
    "c10's draft says the course is 'not full' although 40 students are enrolled against 30 seats. The judge's reasons point to real defects there. The labels are the reference and "
    "were not changed after I saw the scores, so I report the disagreement as measured.",
])
p("Two properties of this experiment also limit what the correlation can show: the human labels use only three values (3, 4, 5), so Spearman has very "
  "little rank variation to work with, and n = 20 gives a wide confidence interval. I did not retune the rubric to raise agreement, because that would be fitting the judge to the labels it is being tested against.")
h2("3.3 Repeatability")
rp = val["repeatability"]
table([
    ("Measure (3 runs, same 20 drafts, same inputs and settings)", "Value"),
    ("Cases whose score changed in any run", f"{rp['cases_changed']} of 20 ({rp['pct_cases_changed']}%)"),
    ("Pairwise run comparisons with a change", f"{rp['pairs_with_change']} of {rp['pair_comparisons']} ({rp['pct_pairs_changed']}%)"),
    ("Mean / maximum absolute change", f"{rp['mean_abs_change']} / {rp['max_abs_change']}"),
    ("Per-run Spearman / MAD", "; ".join(f"run {x['run']}: {x['spearman']} / {x['mean_abs_diff']}" for x in val['per_run_agreement'])),
], widths=[3.6, 3.2], size=9.5)
p("The judge was perfectly repeatable: all 60 scores were identical across the three runs. That is expected, not a strength of the judge, because I fixed temperature at 0 "
  "and the seed at 1808; it shows the settings make the run deterministic, not that the scores are valid. Repeatability is necessary but says nothing about the large disagreement with the human labels above.")
h2("Would I trust this judge to gate a deployment?")
p("No. Correlation with the human reference is negative and not significant (-0.26), the average error is 1.25 points and the judge is systematically a point stricter than the labels. "
  "Perfect repeatability does not help when the scores are unrelated to the reference. Before using it as a gate I would require: (1) a larger labelled set, at least 100 cases and "
  "more than one labeller so inter-annotator agreement is known, including clearly bad drafts so false passes can be measured; (2) a rubric agreed with the labellers about scope and "
  "padding, then re-validated on a fresh held-out set; (3) a second judge model or prompt to measure sensitivity; (4) evidence that low scores predict real failures (wrong "
  "seat counts, invented facts) rather than style; and (5) a target such as rho >= 0.8 and MAD <= 0.5 with a confidence interval, not just a point estimate.")

# ============================================================== PART 4
h1("Part 4: Distributed tracing and latency analysis")
h2("4.1 Trace propagation")
p("trace_id is the HW8 correlation_id end to end; no second request identifier is created. Every stage appends one structured JSON span "
  "(Part-15/tracing.py) to raw/spans.jsonl with: trace_id, stage, start_time, end_time (ISO-8601 UTC), start_ms/end_ms, duration_ms, status (ok or error), error (null or text) and stage-specific attrs.")
table([
    ("Span stage", "Written by", "What it measures / attrs"),
    ("cache_lookup", "qa_service (client)", "embedding + Redis KNN (+ data-version check); attrs.cache_hit, similarity, matched_query"),
    ("facts_lookup", "qa_service", "MySQL grounding facts (miss path only)"),
    ("queue_inbox / queue_tasks / queue_drafts", "Kafka consumers (Planner / Writer / Reviewer)", "Kafka record create time to the moment the next agent starts on it; topic, partition, offset"),
    ("planner / writer / reviewer", "the three HW8 agents", "model call incl. retries; status error with the exception text if all 3 attempts fail; attrs.attempts"),
    ("queue_final", "qa_service", "reviewer's final record create time to the client receiving it"),
    ("request", "qa_service", "ingress to answer returned (the user-visible latency); attrs.path = cache_hit / cache_miss / malformed_input, failed_stage"),
    ("evaluation", "evaluator", "plan + draft + final judging for the trace (offline, after the answer)"),
], widths=[1.9, 1.8, 3.1], size=8.5)
p("The hook in the shared Kafka consumer loop records queue wait and the stage span from the same correlation_id the message already carries; if Part-15/tracing.py "
  "cannot be imported the hook is a no-op, so HW8 and HW9 scripts still behave as before.")
cshot("c1_span_logger.png", "Part-15/tracing.py: span() writes one JSON span per stage, marking status=error and re-raising on failure; read_spans() skips torn lines.", width=6.0)
cshot("c2_kafka_hook.png", "Part-11/kafka_utils.py: queue wait (record create time to start of work) and the stage span, including the error span when all retries fail.", width=6.0)
cshot("c3_cache_lookup_span.png", "Part-15/qa_service.py: the cache_lookup span; attrs.cache_hit makes hit and miss paths distinguishable.", width=6.0)
shot("t0_infra.png", "The stack the traces ran on: Kafka, Zookeeper, Redis Stack and MySQL containers, the s1808 topics, the Redis vector index, and the three agents running with the span hook.", width=6.4)
h2("4.2 Required trace examples")
table([
    ("Trace", "trace_id", "Outcome"),
    ("Cache hit", ex["cache_hit"], f"served from Redis in {ex['hit_latency_ms']:.1f} ms (similarity 1.0); no Kafka span"),
    ("Cache miss, completed", ex["cache_miss_success"], f"full agent path in {ex['miss_latency_ms'] / 1000:.1f} s; every stage status ok"),
    ("Failed", ex["failed"], f"stage {ex['failed_stage']} failed: {ex['error']}; the message was dead-lettered"),
], widths=[1.4, 3.2, 2.2], size=8.5)
p("The failure is a deliberately malformed inbox message with no 'question' field. The Planner raises KeyError: 'question' on all three attempts, the HW8 consumer "
  "dead-letters it, and the client sees the dead-letter record and ends the request with status=error and failed_stage=planner. The question used for the hit and miss traces is: " + ex["question"])
shot("t1_trace_miss.png", "Part 4.2 (1/2): cache-miss trace, every stage in order with start, end and duration in the span log.", width=6.4)
shot("t1_trace_hit_fail.png", "Part 4.2 (2/2): the cache-hit trace (cache_lookup and request only) and the failed trace (planner span status=error).", width=6.4)
p("All three trace IDs are loadable from the dashboard's Trace lookup page (Screenshots " + f"{FIGNUM['d3_trace_hit.png']}-{FIGNUM['d3_trace_failed.png']}" + ") and are stored in raw/trace_examples.json.", italic=True)
h2("4.3 Stage-latency experiment")
p(f"Fifty new questions (course lookups in several phrasings, department questions and off-topic ones, generated with seed 1808; list in Appendix B) were sent one at a time, so the "
  f"queue wait is real hand-off time and not backlog from my own load. The cache was not flushed and store_on_miss was off so the questions could not cache each other. "
  f"Every request's cache_lookup span says cache_hit = False; the highest similarity to anything cached was {exp['max_similarity_to_cache']} against a threshold of {exp['threshold']}, "
  f"and {len(exp['discarded'])} requests had to be discarded and replaced. Queue wait is the sum of the four queue spans per trace.")
shot("t2_latency_run.png", "The 50-request experiment (excerpt; full log in raw/latency_experiment_run.txt). Every row is a confirmed miss; the last line confirms none was served from the cache.", width=6.4)
rows = [("Stage", "p50 (ms)", "p95 (ms)", "% of cache-miss end-to-end (serving)", "% incl. evaluation")]
for label in ("Cache lookup", "Planner", "Writer", "Reviewer", "Queue wait (total)", "Evaluation"):
    tt = tbl[label]
    rows.append((label, fmt(tt["p50_ms"]), fmt(tt["p95_ms"]),
                 "n/a (offline)" if tt["pct_of_serving_e2e"] is None else f"{tt['pct_of_serving_e2e']:.1f}%", f"{tt['pct_of_traced_e2e']:.1f}%"))
table(rows, widths=[1.5, 0.9, 0.9, 2.3, 1.2], size=9.5)
p(f"End-to-end (request span, cache lookup start to answer returned) is p50 {fmt(lat['e2e_serving_p50_ms'])} ms and p95 {fmt(lat['e2e_serving_p95_ms'])} ms. "
  f"'Serving' percentages are each stage's total over the 50 traces divided by the total end-to-end time (they add to about 100%, with {lat['unattributed_pct_of_serving']}% unattributed). "
  f"Evaluation runs after the answer is returned and is not part of what the user waits for, so its serving share is n/a; the last column divides by end-to-end plus evaluation. "
  f"MySQL facts lookup (not a required row) is p50 {fmt(tbl['Facts lookup (MySQL, extra)']['p50_ms'])} ms, {tbl['Facts lookup (MySQL, extra)']['pct_of_serving_e2e']}%.")
shot("t2_latency_table.png", "Output of latency_report.py, the source of the table above.", width=6.4)
h2("Dominant contributor and what I would optimize first")
rv = tbl["Reviewer"]["pct_of_serving_e2e"]
wr = tbl["Writer"]["pct_of_serving_e2e"]
pl = tbl["Planner"]["pct_of_serving_e2e"]
p(f"On the path the user waits for, the three model calls are {pl + wr + rv:.0f}% of the time: Writer {wr:.1f}%, Reviewer {rv:.1f}%, Planner {pl:.1f}%. Cache lookup (0.1%) and Kafka queue "
  f"wait (0.1%, a median {fmt(tbl['Queue wait (total)']['p50_ms'])} ms in total) are negligible, so Kafka is not the bottleneck. The Writer is the dominant stage. If evaluation is included, the 8B judge dominates "
  f"({tbl['Evaluation']['pct_of_traced_e2e']:.1f}% of the traced total, about {tbl['Evaluation']['p50_ms'] / 1000:.0f} s per trace for three judge calls), but it is offline and does not add user latency.")
p(f"What I would optimize first: the Writer's output length. All three stages are token-generation bound on this CPU-only machine, the Writer is prompted for 3-6 sentences and its drafts "
  f"average {draft_len:.0f} characters, while the Reviewer's finals average {final_len:.0f} and scored equal or higher ({st.mean(final_s):.2f} vs {st.mean(draft_s):.2f}). A tighter length limit on the Writer "
  f"(and on the Reviewer) should cut the two largest stages without hurting this judge's score. Second: the Reviewer returned the draft unchanged on {len(verb)} of 50 requests and those calls cost "
  f"{rev_on_verb / 1000:.0f} s of the {req_total / 1000:.0f} s total ({100 * rev_on_verb / req_total:.0f}%), so a cheap check that skips an unnecessary review is worth testing. "
  f"These are hypotheses from the measurements; I did not run an experiment that applies either change.")
p("Cache-hit latency is kept as its own dashboard metric: from the request spans, hits answered in a median "
  f"{pc(hl, 50):.1f} ms (p95 {pc(hl, 95):.1f} ms, n = {len(hl)}) against a cache-miss median of {fmt(lat['e2e_serving_p50_ms'])} ms.")
shot("t5_traffic.png", "The mixed traffic run behind the Summary page's 1-hour window: 8 first-time questions (misses) then 8 repeats and rewordings (all hits).", width=6.4)

# ============================================================== verification
h1("Self-check (verify_hw10.py)")
p(f"verify_hw10.py re-reads the saved evidence (no model calls) and runs {len(verif['checks'])} checks: span schema, the same trace_id on plan/draft/final and no extra identifier fields, hit trace without Kafka "
  "spans, failed trace naming its stage and error, 50 confirmed misses, p50/p95 recomputed from spans, 20 cases and labels committed before the first judge file, Spearman/MAD/repeatability recomputed "
  f"from judge_scores.csv, four criteria on a 1-5 scale, and the dashboard's pages and caching. Result: {sum(c['pass'] for c in verif['checks'])}/{len(verif['checks'])} passed.")
shot("t6_verify.png", "verify_hw10.py output.", width=6.2)
h2("Limitations")
bullets([
    "Twenty human-labelled cases and one labeller: the judge conclusions carry wide uncertainty and the labels were not cross-checked.",
    "The judge (qwen3:8b) and the generators (qwen2.5:1.5b) are both local Qwen-family models; a judge from the same family may share blind spots.",
    "Latency is from one CPU-only machine with the requests run serially; a loaded system would show real queue wait. Queue wait compares Kafka's record create time with the consumer clock on the same host.",
    "Cache hits are not evaluated (no plan or draft exists for them).",
    "The 50 latency questions are template-based and include 8 off-topic ones; a real workload would differ.",
])

# ============================================================== appendices
h1("Appendix A: the 20 frozen evaluation cases (Part-15/eval_cases.json)")
at = [("Case", "Question", "Human", "Writer draft (first 170 characters)")]
for c in cases:
    at.append((c["case_id"], c["question"], labels[c["case_id"]], c["draft"].replace("\n", " ")[:170] + ("..." if len(c["draft"]) > 170 else "")))
table(at, widths=[0.45, 2.0, 0.5, 3.85], size=7.5)
h1("Appendix B: the 50 cache-miss latency questions")
code("\n".join(f"{k + 1:>2}  {r['question']}   [{r['latency_ms'] / 1000:.1f} s, sim {r['similarity']}]" for k, r in enumerate(exp["requests"])), size=7)
h1("Appendix C: how to reproduce")
code("docker start s1808-zookeeper s1808-kafka s1808-redis s1808-mysql\n"
     "python Part-11/planner.py ; python Part-11/writer.py ; python Part-11/reviewer.py     # agents, with span hook\n"
     "python Part-15/trace_demo.py                 # Part 4.2: hit, miss, failed traces\n"
     "python Part-15/make_eval_cases.py            # Part 3.1: 20 drafts  (then label them: streamlit run Part-15/label_tool.py; commit both files)\n"
     "python Part-15/latency_experiment.py         # Part 4.3: 50 confirmed misses\n"
     "python Part-15/evaluator.py --pending        # Part 2: evaluate traces\n"
     "python Part-15/validate_judge.py             # Part 3.2/3.3 (refuses to run unless labels are committed)\n"
     "python Part-15/latency_report.py             # Part 4.3 table\n"
     "streamlit run Part-15/dashboard.py           # Part 1\n"
     "python verify_hw10.py                        # self-check", size=8)

# ============================================================== AI use
h1("AI Use Statement")
h2("1. What AI was used for")
p("The assignment, the domain, the HW1-HW9 repository, the machine and every human label are mine. I used Claude Code to design and write the span logger and the "
  "hook in the Kafka consumer loop, the traced Q&A service, the DeepEval judge wrapper and evaluator, the judge-validation and latency scripts, the Streamlit dashboard and labelling page, the "
  "verification script and this report, and to start the Docker containers and agents and run every experiment. Everything reported was run for real: Kafka, Redis and MySQL in Docker, Ollama for every "
  "pipeline and judge call. I assigned all 20 human labels myself through the labelling page; Claude explained the 1-5 scale and suggested using the whole range, and did not propose a label for any case.")
h2("2. AI output that was wrong or unsuitable")
bullets([
    "The first evaluator pass failed on 8 of 50 traces: G-Eval rejects an empty context and questions with no catalogue facts have none (MissingTestCaseParamsError).",
    "After the first traced request the Planner span and queue_inbox span were missing. A week-old HW8 planner process from an earlier session was still running, held the consumer group and handled the messages with the old code; it had to be stopped.",
    "The first queue_final span was negative (-148 ms): the collector took its 'received' timestamp before the blocking poll instead of after it.",
    "An edit left a stray newline inside a string literal in qa_service.py, so the first launch of the 50-request experiment crashed immediately on a SyntaxError.",
    "Docker-side Kafka would not restart cleanly the first time (a stale Zookeeper node from the unclean shutdown) and had to be retried after the session expired.",
])
h2("3. How the problems were detected")
p("By running the code and reading real output: the MissingTestCaseParamsError text in the evaluator log, the missing planner row in the span listing, the negative duration in the first trace, the traceback of the crashed experiment, and the Kafka container log.")
h2("4. What changed and why it works now")
p("The judge passes an explicit 'no facts matched' context; the stale process was stopped and the agents restarted with the hook; the collector timestamps after the poll; the syntax error was fixed before any measured run; "
  "Kafka was restarted after Zookeeper's session expired. All 50 traces evaluated with no errors and verify_hw10.py passes. Still unresolved and stated above: the judge's poor agreement with my labels, "
  "and that the review step adds little.")

doc.save(HERE / "Achutuni_HW10.docx")
print("wrote", HERE / "Achutuni_HW10.docx")
