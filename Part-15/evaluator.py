"""
Part-15/evaluator.py -- DATA-260 HW10, Part 2 (automated evaluation of the Kafka pipeline)

For a trace_id (= the HW8 correlation_id) the evaluator
  1. LOADS the Planner plan (s1808_tasks), Writer draft (s1808_drafts) and Reviewer final (s1808_final) messages from
     reports/hw10/raw/messages.jsonl -- the raw Kafka messages with topic/partition/offset/timestamps saved by the
     MessageCollector -- joining on correlation_id;
  2. scores, on one 1-5 scale with the Part-15/judge.py GEval judge (qwen3:8b via Ollama):
       Plan Quality               plan   -> score + reason
       Writer Helpfulness         draft  -> score + trace_id
       Final Answer Helpfulness   final  -> score + the final answer
       Final-vs-Draft Improvement final score - draft score, with an interpretation;
  3. writes one record to reports/hw10/raw/evaluations.jsonl and an "evaluation" span for the trace.

Bounded: a missing/malformed message or an unavailable judge produces status="error" with the reason; nothing
retries forever and a per-trace time budget stops the run. Cache-hit traces have no plan/draft (the agents never ran)
and are not evaluated.

Usage:  python Part-15/evaluator.py --trace <trace_id>
        python Part-15/evaluator.py --pending            (every ok cache-miss trace without an evaluation yet)
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "Part-11"))

from judge import JUDGE_SETTINGS, judge  # noqa: E402
from tracing import RAW_DIR, now_ms, read_spans, write_span  # noqa: E402

MESSAGES_PATH = RAW_DIR / "messages.jsonl"
REQUESTS_PATH = RAW_DIR / "requests.jsonl"
EVALS_PATH = RAW_DIR / "evaluations.jsonl"
TRACE_BUDGET_S = 900  # hard stop for one trace (3 judge calls, each already bounded by the client timeout)


def _jsonl(path: Path) -> list[dict]:
    rows = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return rows


def collect(trace_id: str) -> dict:
    """Join plan + draft + final (+ original question/facts) for one correlation_id, keeping message metadata."""
    by_topic: dict[str, dict] = {}
    for row in _jsonl(MESSAGES_PATH):
        if row.get("correlation_id") == trace_id:
            by_topic[row["topic"]] = row
    req = next((r for r in _jsonl(REQUESTS_PATH) if r.get("trace_id") == trace_id), {})
    meta = lambda row: None if not row else {k: row[k] for k in ("topic", "partition", "offset", "kafka_timestamp_ms")}  # noqa: E731
    tasks, drafts, final = (by_topic.get(t) for t in ("s1808_tasks", "s1808_drafts", "s1808_final"))
    return {
        "trace_id": trace_id,
        "question": req.get("question") or (tasks or {}).get("value", {}).get("question"),
        "facts": req.get("facts") or [],
        "plan": (tasks or {}).get("value", {}).get("plan"),
        "draft": (drafts or {}).get("value", {}).get("draft"),
        "final": (final or {}).get("value", {}).get("answer"),
        "message_meta": {"plan": meta(tasks), "draft": meta(drafts), "final": meta(final)},
    }


def interpret(draft: str, final: str, d: Optional[int], f: Optional[int]) -> str:
    if d is None or f is None:
        return "Not interpretable: a judge score is missing."
    diff = f - d
    same_text = (draft or "").strip() == (final or "").strip()
    if diff > 0:
        return f"The Reviewer improved the answer: helpfulness {d} -> {f} (+{diff})."
    if diff < 0:
        return f"The Reviewer made the answer worse: helpfulness {d} -> {f} ({diff}). Review should be tightened."
    if same_text:
        return f"No change: the Reviewer returned the Writer's draft verbatim (both {d}); it added nothing but also cost a model call."
    return f"No score change ({d} -> {f}): the Reviewer rewrote the text but the judge sees equal helpfulness."


def evaluate_trace(trace_id: str) -> dict:
    t0 = now_ms()
    t_wall = time.monotonic()
    c = collect(trace_id)
    rec = {"trace_id": trace_id, "status": "ok", "error": None, "judge_settings": JUDGE_SETTINGS, **c}
    missing = [k for k in ("question", "plan", "draft", "final") if not c.get(k)]
    if missing:
        rec.update(status="error", error=f"incomplete or malformed messages, missing: {', '.join(missing)}")
    else:
        q, facts = c["question"], c["facts"]
        results = {}
        for kind, name, text in (("plan_quality", "plan", c["plan"]), ("helpfulness", "draft", c["draft"]),
                                 ("helpfulness", "final", c["final"])):
            if time.monotonic() - t_wall > TRACE_BUDGET_S:
                results[name] = {"score": None, "reason": "", "error": "TimeoutError: per-trace evaluation budget exhausted",
                                 "latency_ms": 0}
                continue
            results[name] = judge(kind, q, text, facts if kind == "helpfulness" else None)
        p, d, f = results["plan"], results["draft"], results["final"]
        errs = [f"{n}: {r['error']}" for n, r in results.items() if r["error"]]
        rec.update(
            plan_quality={"score": p["score"], "reason": p["reason"]},
            writer_helpfulness={"score": d["score"], "trace_id": trace_id, "reason": d["reason"]},
            final_helpfulness={"score": f["score"], "final_answer": c["final"], "reason": f["reason"]},
            improvement={"draft_score": d["score"], "final_score": f["score"],
                         "difference": None if d["score"] is None or f["score"] is None else f["score"] - d["score"],
                         "interpretation": interpret(c["draft"], c["final"], d["score"], f["score"])},
            judge_latency_ms={n: r["latency_ms"] for n, r in results.items()},
        )
        if errs:
            rec.update(status="error", error="; ".join(errs))
    t1 = now_ms()
    rec["evaluation_ms"] = round(t1 - t0, 1)
    write_span(trace_id, "evaluation", t0, t1, rec["status"], rec["error"], judge_model=JUDGE_SETTINGS["model"])
    with EVALS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")
    return rec


def pending_traces() -> list[str]:
    done = {r["trace_id"] for r in _jsonl(EVALS_PATH) if r.get("status") == "ok"}
    out = []
    for s in read_spans():
        if s["stage"] == "request" and s["status"] == "ok" and s["attrs"].get("path") == "cache_miss" and s["trace_id"] not in done:
            out.append(s["trace_id"])
    return list(dict.fromkeys(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace")
    ap.add_argument("--pending", action="store_true")
    ap.add_argument("--only", help="comma-separated trace_ids to restrict --pending to")
    ap.add_argument("--show", help="print the saved evaluation record for this trace_id (no judge call)")
    a = ap.parse_args()
    if a.show:
        rec = [r for r in _jsonl(EVALS_PATH) if r.get("trace_id") == a.show and r.get("status") == "ok"][-1]
        print(f"=== Part 2 evaluation record | student Sreeramachandrasai Achutuni | trace_id={rec['trace_id']}")
        print(f"question : {rec['question']}")
        print(f"messages : plan {rec['message_meta']['plan']['topic']}@{rec['message_meta']['plan']['offset']}, "
              f"draft {rec['message_meta']['draft']['topic']}@{rec['message_meta']['draft']['offset']}, "
              f"final {rec['message_meta']['final']['topic']}@{rec['message_meta']['final']['offset']} (all joined on correlation_id)")
        print(f"judge    : {rec['judge_settings']['model']} temp={rec['judge_settings']['temperature']} seed={rec['judge_settings']['seed']} scale={rec['judge_settings']['scale']}")
        print(f"1 Plan Quality               score={rec['plan_quality']['score']}  reason: {rec['plan_quality']['reason'][:230]}")
        print(f"2 Writer Helpfulness         score={rec['writer_helpfulness']['score']}  trace_id={rec['writer_helpfulness']['trace_id']}")
        print(f"3 Final Answer Helpfulness   score={rec['final_helpfulness']['score']}  final answer: {rec['final_helpfulness']['final_answer'][:230]}")
        im = rec["improvement"]
        print(f"4 Final-vs-Draft Improvement draft={im['draft_score']} final={im['final_score']} difference={im['difference']}")
        print(f"  interpretation: {im['interpretation']}")
        return
    ids = [a.trace] if a.trace else pending_traces()
    if a.only:
        keep = set(a.only.split(","))
        ids = [i for i in ids if i in keep]
    print(f"=== Part 2 evaluator | student Sreeramachandrasai Achutuni | judge {JUDGE_SETTINGS['model']} | {len(ids)} trace(s)", flush=True)
    for tid in ids:
        r = evaluate_trace(tid)
        if r["status"] == "ok":
            print(f"{tid} plan={r['plan_quality']['score']} draft={r['writer_helpfulness']['score']} "
                  f"final={r['final_helpfulness']['score']} diff={r['improvement']['difference']} | {r['improvement']['interpretation']} "
                  f"[{r['evaluation_ms'] / 1000:.0f}s]", flush=True)
        else:
            print(f"{tid} ERROR {r['error']}", flush=True)


if __name__ == "__main__":
    main()
