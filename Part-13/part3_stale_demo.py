"""
Part-13/part3_stale_demo.py -- DATA-260 HW9, Part 3.5 (stale answer + invalidation)

Cached query : "How many seats are available in course CS-00005?"  (depends on s1808_rel.courses row CS-00005)
Steps        : cache it (real HW8 pipeline) -> UPDATE the row -> show the STALE hit -> turn on
               data-version validation -> same query is detected stale, evicted, re-answered by the
               pipeline with the new value -> next hit is fresh. The record is restored afterwards.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import json
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import engine  # noqa: E402
from domain_facts import facts_for  # noqa: E402
from semantic_cache import make_cache_with_kafka  # noqa: E402
from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="    log: %(message)s", stream=sys.stdout)
for n in ("kafka", "sentence_transformers", "httpx"):
    logging.getLogger(n).setLevel(logging.WARNING)

Q = "How many seats are available in course CS-00005?"
Q_PARA = "What is the number of seats still available for CS-00005?"


def set_seats(n):
    with engine.begin() as c:
        c.execute(text("UPDATE courses SET seats_available=:n WHERE course_code='CS-00005'"), {"n": n})


def db_seats():
    with engine.connect() as c:
        return c.execute(text("SELECT seats_available FROM courses WHERE course_code='CS-00005'")).scalar()


def show(label, r):
    print(f"  {label}: is_cached={r['is_cached']} sim={r['similarity']} latency={r['latency_ms']:.0f} ms")
    print(f"    answer: {r['answer']!r}")
    if r.get("stale_evicted"):
        print(f"    stale_evicted: {json.dumps(r['stale_evicted'])}")


set_seats(30)
cache, pipe = make_cache_with_kafka(threshold=0.85, validate_versions=False)
cache.embed("warm-up")
cache.flush()

print("=== Part 3.5: stale answers and invalidation | student Sreeramachandrasai Achutuni ===\n")
print(f"[1] DB: CS-00005 seats_available = {db_seats()}   data_version = {facts_for(Q)['version']}")
r1 = cache.handle(Q)
show("[1] first ask (miss -> pipeline -> cached with its data_version)", r1)

set_seats(12)
print("\n[2] UPDATE courses SET seats_available = 12 WHERE course_code='CS-00005'")
print(f"    DB now says {db_seats()}   data_version now = {facts_for(Q)['version']}   (cached entry still stores {r1['data_version']})")

r2 = cache.handle(Q_PARA)
show("[3] paraphrase, NO validation (STALE HIT: cache serves the old answer)", r2)

cache.validate_versions = True
print("\n[4] Invalidation strategy ON: on every hit, re-hash the source rows and compare to the stored data_version")
r3 = cache.handle(Q_PARA)
show("[4] same paraphrase, validation ON (stale detected -> evicted -> pipeline re-run)", r3)
r4 = cache.handle(Q_PARA)
show("[5] again (entry rebuilt with the new data_version -> valid fresh hit)", r4)

lat_on, lat_off = [], []
logging.disable(logging.CRITICAL)  # 30 identical hit lines would drown the transcript
for _ in range(15):
    cache.validate_versions = True
    lat_on.append(cache.handle(Q_PARA)["latency_ms"])
    cache.validate_versions = False
    lat_off.append(cache.handle(Q_PARA)["latency_ms"])
print(f"\n[6] validation overhead on a valid hit (15 each): without={statistics.mean(lat_off):.1f} ms  with={statistics.mean(lat_on):.1f} ms")

set_seats(30)
print(f"\n[7] restored CS-00005 seats_available = {db_seats()}")
pipe.close()
out = {"first": r1, "stale_hit": r2, "invalidated": r3, "fresh_hit": r4,
       "overhead_ms": {"without": statistics.mean(lat_off), "with": statistics.mean(lat_on)}}
Path("reports/hw09/raw/part3_stale_results.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
