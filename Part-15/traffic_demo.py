"""
Part-15/traffic_demo.py -- DATA-260 HW10, Part 1.1 (a small realistic traffic mix for the dashboard)

The 50-request latency experiment is all misses by design, so it dominates the all-time hit rate. This sends a short mixed
workload through the same traced path: 8 first-time questions (cache misses, stored on the way out), then repeats and
light rewordings of them (hits when similarity >= the 0.90 threshold, otherwise honest misses). Nothing is forced: every
outcome is whatever the cache decided.  Writes reports/hw10/raw/traffic_demo_run.txt via the shell.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_service import TracedQA  # noqa: E402

FIRST = [
    "What is the title of CS-00024 and which department offers it?",
    "Who teaches ENGR-00327 and in which semester?",
    "How many seats are available in DATA-00015?",
    "Where is the Data Science & AI department located?",
    "Which semester is BUS-00220 offered, and what is the enrollment?",
    "How many seats are available in BUS-00002?",
    "What is the department code and building for Engineering?",
    "Who is the instructor of CS-00121 and how many students enrolled?",
]
REPEATS = [
    FIRST[0],                                                       # exact repeat
    FIRST[2],                                                       # exact repeat
    "Where is the Data Science and AI department located?",         # light rewording
    FIRST[4],                                                       # exact repeat
    "How many seats does BUS-00002 have available?",                # light rewording
    FIRST[6],                                                       # exact repeat
    "Who teaches ENGR-00327, and in which semester?",               # light rewording
    FIRST[7],                                                       # exact repeat
]


def main() -> None:
    qa = TracedQA(timeout_s=240)
    print("=== Part 1.1 traffic mix | student Sreeramachandrasai Achutuni | threshold", qa.cache.threshold, flush=True)
    for label, qs in (("first-time", FIRST), ("repeat/reword", REPEATS)):
        for q in qs:
            r = qa.ask(q, store_on_miss=True)
            print(f"{label:<14} {'HIT ' if r['is_cached'] else 'MISS'} sim={r['similarity']} {r.get('latency_ms'):>9} ms status={r['status']} | {q}", flush=True)
    qa.close()


if __name__ == "__main__":
    main()
