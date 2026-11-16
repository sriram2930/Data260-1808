"""
Part-15/latency_report.py -- DATA-260 HW10, Part 4.3 (turn the 50 confirmed-miss traces into the stage table)

Reads reports/hw10/raw/latency_experiment.json + spans.jsonl (+ the evaluation spans) and writes
reports/hw10/raw/latency_table.json and prints the table.

  p50 / p95        percentile over the 50 traces of that stage's duration (queue wait = sum of the 4 queue spans per trace)
  % of e2e         (sum of the stage over the 50 traces) / (sum of the end-to-end time over the 50 traces)
                   e2e_serving = request span (cache lookup start -> answer returned: what the user waits for)
                   e2e_traced  = request span + evaluation span (cache lookup through evaluation, the whole traced path)
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tracing import RAW_DIR, read_spans  # noqa: E402


def main() -> None:
    exp = json.loads((RAW_DIR / "latency_experiment.json").read_text(encoding="utf-8"))
    ids = [r["trace_id"] for r in exp["requests"]]
    by = {i: {} for i in ids}
    queue = {i: 0.0 for i in ids}
    for s in read_spans():
        t = s["trace_id"]
        if t not in by:
            continue
        if s["stage"].startswith("queue_"):
            queue[t] += s["duration_ms"]
        else:
            by[t][s["stage"]] = s["duration_ms"]  # last span of a stage wins (evaluation may be re-run)
    rows = []
    for t in ids:
        d = by[t]
        rows.append({"cache_lookup": d.get("cache_lookup"), "facts_lookup": d.get("facts_lookup"), "planner": d.get("planner"),
                     "writer": d.get("writer"), "reviewer": d.get("reviewer"), "queue_total": queue[t], "evaluation": d.get("evaluation"),
                     "request": d.get("request")})
    n_eval = sum(r["evaluation"] is not None for r in rows)
    e2e_serving = sum(r["request"] for r in rows)
    e2e_traced = e2e_serving + sum(r["evaluation"] or 0 for r in rows)
    table = []
    for label, key in [("Cache lookup", "cache_lookup"), ("Planner", "planner"), ("Writer", "writer"), ("Reviewer", "reviewer"),
                       ("Queue wait (total)", "queue_total"), ("Evaluation", "evaluation"), ("Facts lookup (MySQL, extra)", "facts_lookup")]:
        x = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
        if not len(x):  # e.g. evaluation not run yet
            table.append({"stage": label, "n": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None, "pct_of_serving_e2e": None, "pct_of_traced_e2e": None})
            continue
        tot = float(x.sum())
        table.append({"stage": label, "n": len(x), "p50_ms": round(float(np.percentile(x, 50)), 1), "p95_ms": round(float(np.percentile(x, 95)), 1),
                      "mean_ms": round(float(x.mean()), 1), "pct_of_serving_e2e": None if key == "evaluation" else round(100 * tot / e2e_serving, 1),
                      "pct_of_traced_e2e": round(100 * tot / e2e_traced, 1)})
    req = np.array([r["request"] for r in rows])
    acc = sum(float(np.sum([r[k] for r in rows])) for k in ("cache_lookup", "facts_lookup", "planner", "writer", "reviewer", "queue_total"))
    out = {"n": len(rows), "n_with_evaluation": n_eval, "e2e_serving_p50_ms": round(float(np.percentile(req, 50)), 1),
           "e2e_serving_p95_ms": round(float(np.percentile(req, 95)), 1), "e2e_serving_mean_ms": round(float(req.mean()), 1),
           "unattributed_pct_of_serving": round(100 * (e2e_serving - acc) / e2e_serving, 2), "table": table,
           "dominant_stage_serving": max((t for t in table if t["pct_of_serving_e2e"] is not None and "extra" not in t["stage"]), key=lambda t: t["pct_of_serving_e2e"])["stage"],
           "dominant_stage_traced": max((t for t in table if t["pct_of_traced_e2e"] is not None and "extra" not in t["stage"]), key=lambda t: t["pct_of_traced_e2e"])["stage"]}
    (RAW_DIR / "latency_table.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"n={out['n']} (evaluated {n_eval}) | e2e serving p50 {out['e2e_serving_p50_ms']} ms p95 {out['e2e_serving_p95_ms']} ms | unattributed {out['unattributed_pct_of_serving']}%")
    print(f"{'Stage':<30}{'n':>4}{'p50 (ms)':>12}{'p95 (ms)':>12}{'% serving e2e':>16}{'% traced e2e':>14}")
    for t in table:
        if not t["n"]:
            print(f"{t['stage']:<30}{0:>4}  (no data yet)")
            continue
        print(f"{t['stage']:<30}{t['n']:>4}{t['p50_ms']:>12,.1f}{t['p95_ms']:>12,.1f}{str(t['pct_of_serving_e2e']):>16}{t['pct_of_traced_e2e']:>14}")
    print("dominant (serving):", out["dominant_stage_serving"], "| dominant (traced incl. evaluation):", out["dominant_stage_traced"])


if __name__ == "__main__":
    main()
