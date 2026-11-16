"""
Part-15/latency_experiment.py -- DATA-260 HW10, Part 4.3 (stage-latency experiment on confirmed cache misses)

Sends 50 NEW questions one at a time (concurrency 1, so queue wait is real Kafka/agent hand-off time and not backlog
from our own load) through the traced path. A request counts only if its cache_lookup span says cache_hit=False; a
request that the cache would have served is discarded and replaced from a reserve list, and every similarity score is
recorded, so "none of the 50 was served from the semantic cache" is verified, not assumed. The cache is NOT flushed
(it still holds the Part 4.2 demo entry) and store_on_miss=False keeps the 50 questions from caching each other.

Output: reports/hw10/raw/latency_experiment.json.   Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_service import TracedQA  # noqa: E402
from tracing import RAW_DIR, read_spans  # noqa: E402

REF = json.loads((HERE.parent / "Part-14" / "reference_dataset.json").read_text(encoding="utf-8"))
COURSES = [c["course_code"] for c in REF["courses"]]
TAUGHT = [c["course_code"] for c in REF["courses"] if c["sections"]]
DEPTS = [d["name"] for d in REF["departments"]]
OFF_TOPIC = [
    "What is the boiling point of water at sea level?", "Recommend a good book about the Roman Empire.",
    "How do vaccines train the immune system?", "What is the capital of Australia?", "Write a short poem about the ocean.",
    "How many moons does Jupiter have?", "Explain the rules of chess in two sentences.", "What causes a rainbow to appear?",
]
TEMPLATES_ANY = [
    "How many seats are available in {c}?", "What is the title of {c} and which department offers it?",
    "Tell me about the course {c}.", "Does {c} still have open seats?",
]
TEMPLATES_TAUGHT = [
    "Who teaches {c}?", "Which semester is {c} offered, and what is the enrollment?", "Who is the instructor of {c} and how many students enrolled?",
]
TEMPLATES_DEPT = ["Where is the {d} department located?", "What is the department code and building for {d}?"]


def build_questions(seed: int = 1808, n: int = 62) -> list[str]:
    rng = random.Random(seed)
    qs: list[str] = []
    pool = [(t, c) for t in TEMPLATES_ANY for c in COURSES] + [(t, c) for t in TEMPLATES_TAUGHT for c in TAUGHT]
    rng.shuffle(pool)
    qs += [t.format(c=c) for t, c in pool[:42]]
    qs += [t.format(d=d) for t in TEMPLATES_DEPT for d in DEPTS][:6]
    qs += OFF_TOPIC
    qs = list(dict.fromkeys(qs))
    rng.shuffle(qs)
    return qs[:n]


def main() -> None:
    qa = TracedQA(timeout_s=240)
    qs = build_questions()
    kept, discarded = [], []
    print(f"=== Part 4.3 latency experiment | student Sreeramachandrasai Achutuni | target 50 confirmed misses, {len(qs)} candidates | threshold {qa.cache.threshold}", flush=True)
    for q in qs:
        if len(kept) == 50:
            break
        r = qa.ask(q, store_on_miss=False)
        row = {"trace_id": r["trace_id"], "question": q, "is_cached": r["is_cached"], "similarity": r["similarity"],
               "latency_ms": r.get("latency_ms"), "status": r["status"], "error": r["error"]}
        (discarded if r["is_cached"] or r["status"] != "ok" else kept).append(row)
        print(f"[{len(kept):>2}/50] {'HIT-DISCARD' if r['is_cached'] else r['status']:<11} sim={r['similarity']} {r.get('latency_ms')} ms | {q}", flush=True)
    qa.close()
    sims = [k["similarity"] for k in kept if k["similarity"] is not None]
    spans = [s for s in read_spans() if s["trace_id"] in {k["trace_id"] for k in kept} and s["stage"] == "cache_lookup"]
    out = {"n_confirmed_misses": len(kept), "all_cache_hit_false": all(s["attrs"].get("cache_hit") is False for s in spans) and len(spans) == len(kept),
           "max_similarity_to_cache": max(sims) if sims else None, "threshold": qa.cache.threshold, "discarded": discarded,
           "concurrency": 1, "store_on_miss": False, "requests": kept}
    (RAW_DIR / "latency_experiment.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"confirmed misses={len(kept)} | cache_lookup cache_hit=False for all: {out['all_cache_hit_false']} | max similarity {out['max_similarity_to_cache']} | discarded {len(discarded)}")


if __name__ == "__main__":
    main()
