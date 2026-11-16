"""
Part-15/trace_demo.py -- DATA-260 HW10, Part 4.2 (the three required trace examples)

  1. cache-MISS trace that completes the agent path (stored in the semantic cache on the way out)
  2. cache-HIT trace (the same question again: served from Redis, no Kafka stage runs)
  3. FAILED trace (malformed message: Planner raises on every retry, message is dead-lettered)

Writes reports/hw10/raw/trace_examples.json (the three trace_ids) and prints each trace's spans in stage order.
Needs Kafka, Redis, MySQL, Ollama and the three HW8 agents running.   Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_service import TracedQA  # noqa: E402
from tracing import RAW_DIR, STAGE_ORDER, read_spans  # noqa: E402

QUESTION = "Which department offers DATA-00007, and how many seats are available in it?"


def show(trace_id: str, label: str) -> None:
    spans = [s for s in read_spans() if s["trace_id"] == trace_id]
    spans.sort(key=lambda s: (s["start_ms"], STAGE_ORDER.index(s["stage"]) if s["stage"] in STAGE_ORDER else 99))
    print(f"\n=== {label} | trace_id={trace_id}")
    print(f"{'stage':<14}{'status':<8}{'start_time':<32}{'end_time':<32}{'ms':>10}  detail")
    for s in spans:
        detail = s["error"] or ", ".join(f"{k}={v}" for k, v in s["attrs"].items() if v not in (None, "") and k in ("cache_hit", "similarity", "path", "failed_stage", "attempts"))
        print(f"{s['stage']:<14}{s['status']:<8}{s['start_time']:<32}{s['end_time']:<32}{s['duration_ms']:>10.1f}  {detail}")


def main() -> None:
    qa = TracedQA(timeout_s=180)
    qa.cache.flush()
    print("=== Part 4.2 trace examples | student Sreeramachandrasai Achutuni | threshold", qa.cache.threshold)
    miss = qa.ask(QUESTION)
    print("miss:", {k: miss[k] for k in ("trace_id", "is_cached", "status", "latency_ms")})
    hit = qa.ask(QUESTION)
    print("hit :", {k: hit[k] for k in ("trace_id", "is_cached", "similarity", "status", "latency_ms")})
    fail = qa.ask_malformed()
    print("fail:", fail)
    ids = {"cache_miss_success": miss["trace_id"], "cache_hit": hit["trace_id"], "failed": fail["trace_id"],
           "question": QUESTION, "failed_stage": fail["failed_stage"], "error": fail["error"],
           "miss_latency_ms": miss["latency_ms"], "hit_latency_ms": hit["latency_ms"]}
    (RAW_DIR / "trace_examples.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
    show(miss["trace_id"], "1. CACHE MISS (agent path completed)")
    show(hit["trace_id"], "2. CACHE HIT")
    show(fail["trace_id"], "3. FAILED (malformed message)")
    qa.close()


if __name__ == "__main__":
    main()
