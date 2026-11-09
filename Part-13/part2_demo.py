"""
Part-13/part2_demo.py -- DATA-260 HW9, Part 2 demo (Student: Sreeramachandrasai Achutuni, SID4 1808)

Sends 14 queries (new, exact duplicates, paraphrases) through the semantic cache at
threshold 0.85. Misses go through the REAL HW8 Planner->Writer->Reviewer pipeline over
Kafka. Reports per-request is_cached / similarity / latency, hit rate, and average
latency cached vs not cached -- exactly what was measured, no target speed-up.

Prereqs: Docker (s1808-redis, s1808-kafka, s1808-mysql) and Part-11/planner.py, writer.py,
reviewer.py running. Run from the repo root:  python Part-13/part2_demo.py
"""
import json
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_cache import make_cache_with_kafka  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)
for noisy in ("kafka", "sentence_transformers", "httpx"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

QUERIES = [
    ("new",       "Where is the Computer Science department located?"),
    ("duplicate", "Where is the Computer Science department located?"),
    ("paraphrase","In which building can I find the Computer Science department?"),
    ("new",       "What is the title of course CS-00005?"),
    ("paraphrase","What is the name of course CS-00005?"),
    ("new",       "How many seats are available in course DATA-00006?"),
    ("duplicate", "How many seats are available in course DATA-00006?"),
    ("new",       "What is the capital of France?"),
    ("new",       "Who teaches CS-00020 in Fall 2026?"),
    ("paraphrase","Who is the instructor for CS-00020 during Fall 2026?"),
    ("new",       "What is the title of course DATA-00016?"),
    ("duplicate", "What is the title of course DATA-00016?"),
    ("new",       "Which department offers ENGR-00003?"),
    ("new",       "What building is the Engineering department in?"),
]

cache, pipeline = make_cache_with_kafka(threshold=0.85)
cache.embed("warm-up")  # load the embedding model before any timed request
print(f"=== Part 2: semantic cache | student Sreeramachandrasai Achutuni | threshold={cache.threshold} ===")
print(f"flushed {cache.flush()} old cache entries\n")

results = []
for i, (kind, q) in enumerate(QUERIES, 1):
    r = cache.handle(q)
    r["kind"] = kind
    results.append(r)
    print(f"#{i:<2} [{kind:<10}] is_cached={str(r['is_cached']):<5} sim={r['similarity']} latency={r['latency_ms']:.0f} ms")
    print(f"     Q: {q}\n     A: {r['answer'][:160]!r}\n")
pipeline.close()

hits = [r for r in results if r["is_cached"]]
miss = [r for r in results if not r["is_cached"]]
print("=== Summary ===")
print(f"queries: {len(results)} | hits: {len(hits)} | misses: {len(miss)} | hit rate: {100*len(hits)/len(results):.1f}%")
print(f"avg latency cached     : {statistics.mean(r['latency_ms'] for r in hits):.1f} ms  (n={len(hits)})")
print(f"avg latency not cached : {statistics.mean(r['latency_ms'] for r in miss):.1f} ms  (n={len(miss)})")
Path("reports/hw09/raw/part2_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
