"""
Part-13/part3_sweep.py -- DATA-260 HW9, Part 3.2-3.4 (threshold sweep + cost model)

For each threshold in 0.75..0.95: flush the cache, warm it with the 10 seed queries
(real pipeline answers recorded by part3_precompute.py), then send all 40 labeled cases
from cache_cases.yaml READ-ONLY (a miss does not insert, so every case sees the same 10-entry cache).

Latency per request = cache path measured live (embedding + Redis KNN [+ facts lookup on a miss])
                    + the recorded real pipeline latency of that exact query, for misses only.

Definitions
  hit rate        = hits / 40
  false hit       = a hit on a should-miss case (similar_different, unrelated) OR a hit that returned
                    a different seed than the case's expected seed
  false-hit rate  = false hits / 20 should-miss cases
  missed-hit rate = should-hit cases that missed / 20 (reported for context)

Cost model (assumptions are stated in the report):  total = misses x C_MISS + false_hits x C_FALSE
"""
import json
import statistics
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from semantic_cache import SemanticCache  # noqa: E402

RAW = HERE.parent / "reports" / "hw09" / "raw"
THRESHOLDS = [0.75, 0.80, 0.85, 0.90, 0.95]
C_MISS = 0.005  # $ per request that must run the 3-call agent pipeline
C_FALSE = 2.00  # $ per false hit (wrong catalogue answer -> ~3 min of staff time at ~$40/h)

spec = yaml.safe_load((HERE / "cache_cases.yaml").read_text(encoding="utf-8"))
answers = json.loads((RAW / "part3_pipeline_answers.json").read_text(encoding="utf-8"))
seed_by_query = {s["query"]: s["id"] for s in spec["seeds"]}


def replay_agent(q, facts):
    return answers[q]["answer"]


cache = SemanticCache(replay_agent, threshold=0.85)
cache.embed("warm-up")

all_rows, summary = [], []
for th in THRESHOLDS:
    cache.threshold = th
    cache.flush()
    for s in spec["seeds"]:
        cache.store(s["query"], cache.embed(s["query"]), answers[s["query"]]["answer"], answers[s["query"]]["data_version"])
    rows = []
    for c in spec["cases"]:
        r = cache.handle(c["query"], store_on_miss=False)
        total_ms = r["latency_ms"] + (0.0 if r["is_cached"] else answers[c["query"]]["agent_ms"])
        got_seed = seed_by_query.get(r["matched_query"]) if r["is_cached"] else None
        false_hit = r["is_cached"] and (not c["should_hit"] or got_seed != c.get("seed"))
        rows.append({
            "threshold": th, "id": c["id"], "category": c["category"], "query": c["query"],
            "should_hit": c["should_hit"], "is_cached": r["is_cached"], "similarity_to_best": r["similarity"],
            "matched_query": r["matched_query"], "false_hit": bool(false_hit),
            "cache_path_ms": r["latency_ms"], "total_ms": round(total_ms, 1),
            "returned_answer": r["answer"] if r["is_cached"] else None,
            "correct_answer": c.get("correct_answer"),
        })
    hits = sum(r["is_cached"] for r in rows)
    fh = sum(r["false_hit"] for r in rows)
    misses = len(rows) - hits
    missed_hits = sum(1 for r in rows if r["should_hit"] and not r["is_cached"])
    summary.append({
        "threshold": th, "hits": hits, "hit_rate": hits / 40, "false_hits": fh, "false_hit_rate": fh / 20,
        "missed_hit_rate": missed_hits / 20, "mean_latency_ms": round(statistics.mean(r["total_ms"] for r in rows), 1),
        "misses": misses, "total_cost": round(misses * C_MISS + fh * C_FALSE, 4),
    })
    all_rows += rows

print("threshold | hit rate | false-hit rate | missed-hit rate | mean latency (ms) | total cost")
for s in summary:
    print(f"  {s['threshold']:.2f}    |  {s['hit_rate']*100:5.1f}%  |    {s['false_hit_rate']*100:5.1f}%     |     {s['missed_hit_rate']*100:5.1f}%      |   {s['mean_latency_ms']:9.1f}     | ${s['total_cost']:.3f}")

print(f"\nSensitivity of total cost to the false-hit cost (C_MISS fixed at ${C_MISS:.3f}):")
sens = {}
for cf in (0.10, 2.00, 20.00):
    sens[cf] = {s["threshold"]: round(s["misses"] * C_MISS + s["false_hits"] * cf, 3) for s in summary}
    best = min(sens[cf], key=sens[cf].get)
    print(f"  C_FALSE=${cf:>5.2f}: " + "  ".join(f"{t:.2f}=${v:.3f}" for t, v in sens[cf].items()) + f"   -> cheapest: {best:.2f}")

(RAW / "part3_sweep_rows.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
(RAW / "part3_sweep_summary.json").write_text(
    json.dumps({"c_miss": C_MISS, "c_false": C_FALSE, "summary": summary,
                "sensitivity": {str(k): {str(t): v for t, v in d.items()} for k, d in sens.items()}}, indent=2),
    encoding="utf-8")

print("\nFalse hits by threshold (similarity to nearest seed):")
for th in THRESHOLDS:
    fhs = sorted([r for r in all_rows if r["threshold"] == th and r["false_hit"]], key=lambda r: -r["similarity_to_best"])
    print(f"  {th:.2f}: " + (", ".join(f"{r['id']}({r['similarity_to_best']:.3f})" for r in fhs) or "none"))
