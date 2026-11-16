"""
verify_hw10.py -- DATA-260 HW10 self-check (no LLM calls, runs in seconds; it only re-reads the saved evidence).

  Part 4.1  every span has trace_id/stage/start/end/status/error; the same trace_id appears on the plan, draft and final
            Kafka messages (no second request identifier); cache-hit trace has no Kafka stage spans; miss trace has all stages
  Part 4.2  hit / miss / failed example traces exist, failed trace names the failing stage and error
  Part 4.3  50 confirmed cache misses (cache_hit=False on every cache_lookup span); p50/p95 table recomputes from the spans
  Part 3    20 cases, 20 hand labels in 1-5, both files committed BEFORE the first judge score file existed;
            Spearman / MAD / repeatability recompute from judge_scores.csv
  Part 2    evaluation records carry the four required criteria on a 1-5 scale
  Part 1    dashboard.py parses, has the three pages and uses st.cache_data and st.cache_resource

Writes reports/hw10/verification.json.   Usage:  python verify_hw10.py
"""

from __future__ import annotations

import ast
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).parent
RAW = HERE / "reports" / "hw10" / "raw"
P15 = HERE / "Part-15"
SID4, PREFIX = 1808, "s1808"
checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "pass": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name, detail)


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True).stdout.strip()


def main() -> None:
    spans = jl(RAW / "spans.jsonl")
    msgs = jl(RAW / "messages.jsonl")
    ex = json.loads((RAW / "trace_examples.json").read_text(encoding="utf-8"))
    by: dict[str, list[dict]] = {}
    for s in spans:
        by.setdefault(s["trace_id"], []).append(s)

    # ------------------------------------------------------------ Part 4.1 / 4.2
    need = {"trace_id", "stage", "start_time", "end_time", "status", "error"}
    check("p41_every_span_has_required_fields", all(need <= set(s) for s in spans), f"{len(spans)} spans")
    check("p41_status_values", {s["status"] for s in spans} <= {"ok", "error"})
    check("p41_error_spans_carry_error_text", all(s["error"] for s in spans if s["status"] == "error"))

    miss, hit, fail = (by[ex[k]] for k in ("cache_miss_success", "cache_hit", "failed"))
    stages = lambda t: {s["stage"] for s in t}  # noqa: E731
    check("p42_miss_trace_has_all_stages", {"cache_lookup", "queue_inbox", "planner", "queue_tasks", "writer", "queue_drafts", "reviewer", "queue_final", "request"} <= stages(miss), str(sorted(stages(miss))))
    check("p42_miss_trace_all_ok", all(s["status"] == "ok" for s in miss))
    check("p42_miss_lookup_says_miss", next(s for s in miss if s["stage"] == "cache_lookup")["attrs"]["cache_hit"] is False)
    check("p42_hit_trace_lookup_says_hit", next(s for s in hit if s["stage"] == "cache_lookup")["attrs"]["cache_hit"] is True)
    check("p42_hit_trace_has_no_kafka_stage", not (stages(hit) & {"planner", "writer", "reviewer", "queue_inbox", "queue_tasks", "queue_drafts", "queue_final"}), str(sorted(stages(hit))))
    bad = [s for s in fail if s["status"] == "error" and s["stage"] == "planner"]
    check("p42_failed_trace_names_stage_and_error", bool(bad) and bool(bad[0]["error"]) and ex["failed_stage"] == "planner", f"{ex['failed_stage']}: {bad[0]['error'] if bad else None}")
    check("p42_three_distinct_trace_ids", len({ex["cache_miss_success"], ex["cache_hit"], ex["failed"]}) == 3)

    rows = {m["topic"]: m for m in msgs if m["correlation_id"] == ex["cache_miss_success"]}
    check("p41_same_id_on_plan_draft_final", all(t in rows for t in ("s1808_tasks", "s1808_drafts", "s1808_final")), "tasks/drafts/final all carry the trace_id as correlation_id")
    allowed = {"correlation_id", "question", "plan", "draft", "status", "answer", "original_topic", "original_message", "error", "retries"}
    check("p41_no_second_request_identifier", all(set(m["value"]) <= allowed for m in msgs), "no extra id fields on any message")

    # ------------------------------------------------------------ Part 4.3
    exp = json.loads((RAW / "latency_experiment.json").read_text(encoding="utf-8"))
    ids = [r["trace_id"] for r in exp["requests"]]
    check("p43_50_requests", len(ids) == 50 and len(set(ids)) == 50)
    lookups = [next(s for s in by[i] if s["stage"] == "cache_lookup") for i in ids]
    check("p43_none_served_from_cache", all(lk["attrs"]["cache_hit"] is False for lk in lookups) and exp["all_cache_hit_false"])
    check("p43_max_similarity_below_threshold", exp["max_similarity_to_cache"] < exp["threshold"], f"max {exp['max_similarity_to_cache']} < {exp['threshold']}")
    lt = json.loads((RAW / "latency_table.json").read_text(encoding="utf-8"))
    pl = np.array([next(s for s in by[i] if s["stage"] == "planner")["duration_ms"] for i in ids])
    row = next(t for t in lt["table"] if t["stage"] == "Planner")
    check("p43_table_recomputes_from_spans", abs(float(np.percentile(pl, 50)) - row["p50_ms"]) < 0.11 and abs(float(np.percentile(pl, 95)) - row["p95_ms"]) < 0.11, f"planner p50 {row['p50_ms']} p95 {row['p95_ms']}")

    # ------------------------------------------------------------ Part 3
    cases = json.loads((P15 / "eval_cases.json").read_text(encoding="utf-8"))
    labels = {r["case_id"]: r["human_label"] for r in csv.DictReader((P15 / "human_labels.csv").open(encoding="utf-8"))}
    check("p31_20_cases_20_labels", len(cases) == 20 and set(labels) == {c["case_id"] for c in cases})
    check("p31_labels_in_1_to_5", all(v.isdigit() and 1 <= int(v) <= 5 for v in labels.values()))
    first_commit = {f: int(git("log", "--diff-filter=A", "--format=%ct", "--", f).splitlines()[-1]) for f in ("Part-15/eval_cases.json", "Part-15/human_labels.csv")}
    runs_file = RAW / "judge_runs.json"
    first_score_time = int(runs_file.stat().st_ctime)
    check("p31_frozen_before_judge_scores", max(first_commit.values()) < first_score_time, f"labels committed {max(first_commit.values())} < judge_runs.json created {first_score_time}")
    check("p31_files_unmodified_since_commit", git("status", "--porcelain", "--", "Part-15/eval_cases.json", "Part-15/human_labels.csv") == "")

    val = json.loads((RAW / "judge_validation.json").read_text(encoding="utf-8"))
    sc = list(csv.DictReader((RAW / "judge_scores.csv").open(encoding="utf-8")))
    h = np.array([float(r["human"]) for r in sc])
    j = np.array([[float(r[f"judge_run{k}"]) for r in sc] for k in (1, 2, 3)])
    rho = spearmanr(h, j[0])[0]
    check("p32_spearman_recomputes", (np.isnan(rho) and val["spearman_rho"] is None) or abs(rho - val["spearman_rho"]) < 1e-6, f"rho={val['spearman_rho']}")
    check("p32_mad_recomputes", abs(float(np.mean(np.abs(h - j[0]))) - val["mean_abs_diff"]) < 1e-3, f"MAD={val['mean_abs_diff']}")
    changed = int((j.max(axis=0) != j.min(axis=0)).sum())
    check("p33_repeatability_recomputes", changed == val["repeatability"]["cases_changed"], f"{changed}/20 cases changed across 3 runs")
    check("p33_three_runs_20_scores_each", j.shape == (3, 20) and not np.isnan(j).any())

    # ------------------------------------------------------------ Part 2
    ev = [e for e in jl(RAW / "evaluations.jsonl") if e["status"] == "ok"]
    last = {e["trace_id"]: e for e in ev}
    need2 = ("plan_quality", "writer_helpfulness", "final_helpfulness", "improvement")
    check("p2_records_have_four_criteria", bool(last) and all(all(k in e for k in need2) for e in last.values()), f"{len(last)} evaluated traces")
    scores = [e["plan_quality"]["score"] for e in last.values()] + [e["writer_helpfulness"]["score"] for e in last.values()] + [e["final_helpfulness"]["score"] for e in last.values()]
    check("p2_scores_on_1_to_5_scale", all(isinstance(s, int) and 1 <= s <= 5 for s in scores))
    one = next(iter(last.values()))
    check("p2_improvement_has_both_scores_diff_interpretation", {"draft_score", "final_score", "difference", "interpretation"} <= set(one["improvement"]))
    check("p2_message_metadata_kept", all(one["message_meta"][k] for k in ("plan", "draft", "final")) and bool(one["judge_settings"]))
    check("p2_plan_draft_final_joined_on_trace_id", all(e["trace_id"] in {m["correlation_id"] for m in msgs} for e in last.values()))

    # ------------------------------------------------------------ Part 1
    src = (P15 / "dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    check("p1_three_pages", {"page_summary", "page_evaluation", "page_trace"} <= funcs)
    check("p1_uses_streamlit_caching", "st.cache_data" in src and "st.cache_resource" in src)
    check("p1_trace_id_input_and_windows_stated", 'st.text_input("trace_id"' in src and "Window:" in src and "Source:" in src)
    check("prefix_s1808_on_cache_keys", "s1808:semcache" in src)

    commit = git("rev-parse", "HEAD")
    out = {"homework": "hw10", "sid4": SID4, "commit_hash": commit, "judge": "qwen3:8b via Ollama, deepeval GEval",
           "checks": checks, "all_pass": all(c["pass"] for c in checks)}
    (HERE / "reports" / "hw10" / "verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{sum(c['pass'] for c in checks)}/{len(checks)} checks passed")
    sys.exit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
