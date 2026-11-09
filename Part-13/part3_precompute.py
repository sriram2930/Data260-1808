"""
Part-13/part3_precompute.py -- DATA-260 HW9, Part 3.2 (record real pipeline answers once)

The threshold sweep runs 40 cases x 5 thresholds. Re-running the Kafka pipeline (~20 s per
call on this CPU-only machine) for every miss at every threshold would take hours and add
noise, so each DISTINCT query text in cache_cases.yaml goes through the real HW8 pipeline
exactly once here; the sweep (part3_sweep.py) replays {answer, agent latency} for misses and
measures the cache path (embedding + Redis KNN) live.
"""
import json
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from domain_facts import facts_for  # noqa: E402
from semantic_cache import KafkaPipeline  # noqa: E402

spec = yaml.safe_load((HERE / "cache_cases.yaml").read_text(encoding="utf-8"))
texts = list(dict.fromkeys([s["query"] for s in spec["seeds"]] + [c["query"] for c in spec["cases"]]))
out_path = HERE.parent / "reports" / "hw09" / "raw" / "part3_pipeline_answers.json"
done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

pipe = KafkaPipeline()
for i, q in enumerate(texts, 1):
    if q in done:
        continue
    f = facts_for(q)
    t0 = time.perf_counter()
    ans = pipe.ask(q, f["facts"])
    ms = (time.perf_counter() - t0) * 1000
    done[q] = {"answer": ans, "agent_ms": round(ms, 1), "data_version": f["version"]}
    out_path.write_text(json.dumps(done, indent=2), encoding="utf-8")
    print(f"[{i}/{len(texts)}] {ms:7.0f} ms  {q}  ->  {ans[:90]!r}", flush=True)
pipe.close()
print("done:", len(done), "distinct queries")
