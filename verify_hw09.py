"""
verify_hw09.py -- DATA-260 HW9 self-check / smoke test (no LLM calls, runs in ~1 minute).

  Part 1: increment_course_views counts in Redis under an s1808-prefixed key and syncs the
          count to MySQL on every 10th increment (and only then).
  Part 2: the Redis vector index exists on the s1808:semcache: prefix; an exact duplicate is a
          hit (is_cached=True, similarity ~1.0) WITHOUT calling the agent; an unrelated query is a miss.
  Part 3: cache_cases.yaml has 40 labeled cases (4 categories x 10); the sweep covered all 5
          thresholds; data-version validation turns a stale hit into a miss after the source row changes.
  Part 4: input datasets contain only questions (no answers); lessons.json has the required
          fields; the Evaluator PASSes a correct answer and REVISEs a wrong one; solve() never
          exceeds 2 attempts.

Writes reports/hw09/verification.json.   Usage:  python verify_hw09.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
for sub in ("Part-1", "Part-12", "Part-13", "Part-14"):
    sys.path.insert(0, str(HERE / sub))

SID4, SEED, VERIFY_SEED, PREFIX = 1808, 1808, 261808, "s1808"
checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "pass": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name, detail)


def commit_hash() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- Part 1
def part1() -> None:
    from course_store import CourseStore
    from sqlalchemy import text

    cid = 4  # BUS-00002: scratch course for the check
    s = CourseStore()
    s.redis_client.delete(s.views_key(cid))
    with s._session_factory() as sess:
        sess.execute(text("UPDATE courses SET view_count=0 WHERE id=:i"), {"i": cid})
        sess.commit()
    counts = [s.increment_course_views(cid) for _ in range(9)]
    check("p1_key_has_prefix", s.views_key(cid).startswith(f"{PREFIX}:"), s.views_key(cid))
    check("p1_counts_1_to_9", counts == list(range(1, 10)))
    check("p1_no_db_write_before_10", s.db_view_count(cid) == 0)
    check("p1_returns_10_and_syncs", s.increment_course_views(cid) == 10 and s.db_view_count(cid) == 10)
    s.increment_course_views(cid)
    check("p1_no_sync_on_11", s.db_view_count(cid) == 10)
    s.redis_client.delete(s.views_key(cid))
    with s._session_factory() as sess:
        sess.execute(text("UPDATE courses SET view_count=0 WHERE id=:i"), {"i": cid})
        sess.commit()


# ---------------------------------------------------------------- Part 2/3
def part23() -> None:
    from db import engine
    from domain_facts import facts_for
    from semantic_cache import INDEX_NAME, KEY_PREFIX, SemanticCache
    from sqlalchemy import text

    calls = []

    def stub(q, facts):
        calls.append(q)
        return f"stub-answer-for:{q}"

    c = SemanticCache(stub, threshold=0.85)
    c.flush()
    c.r.ft(INDEX_NAME).info()  # raises if the index is missing
    check("p2_vector_index_exists", INDEX_NAME.startswith(PREFIX) and KEY_PREFIX.startswith(PREFIX), INDEX_NAME)
    q = "How many seats are available in course CS-00005?"
    m1 = c.handle(q)
    n_calls = len(calls)
    m2 = c.handle(q)
    check("p2_first_is_miss", m1["is_cached"] is False and n_calls == 1)
    check("p2_duplicate_is_hit_without_agent", m2["is_cached"] is True and len(calls) == n_calls and m2["similarity"] >= 0.99, f"sim={m2['similarity']}")
    m3 = c.handle("Who painted the Mona Lisa?")
    check("p2_unrelated_is_miss", m3["is_cached"] is False)
    check("p2_latency_fields_present", all(k in m2 for k in ("latency_ms", "similarity", "is_cached")))

    spec = yaml.safe_load((HERE / "Part-13" / "cache_cases.yaml").read_text(encoding="utf-8"))
    cats = {}
    for case in spec["cases"]:
        cats[case["category"]] = cats.get(case["category"], 0) + 1
    check("p3_cases_40_in_4_categories_of_10", len(spec["cases"]) == 40 and sorted(cats.values()) == [10, 10, 10, 10], str(cats))
    summ = HERE / "reports" / "hw09" / "raw" / "part3_sweep_summary.json"
    ths = sorted(s["threshold"] for s in json.loads(summ.read_text())["summary"]) if summ.exists() else []
    check("p3_sweep_has_5_thresholds", ths == [0.75, 0.8, 0.85, 0.9, 0.95], str(ths))

    # stale detection: change the source row, validation must turn the hit into a miss
    c.flush()
    c.validate_versions = True
    c.handle(q)
    with engine.begin() as conn:
        orig = conn.execute(text("SELECT seats_available FROM courses WHERE course_code='CS-00005'")).scalar()
        conn.execute(text("UPDATE courses SET seats_available=:n WHERE course_code='CS-00005'"), {"n": orig + 1})
    try:
        before = len(calls)
        r = c.handle(q)
        check("p3_stale_hit_invalidated_to_miss", r["is_cached"] is False and r["stale_evicted"] is not None and len(calls) == before + 1)
        r2 = c.handle(q)
        check("p3_rebuilt_entry_is_valid_hit", r2["is_cached"] is True)
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE courses SET seats_available=:n WHERE course_code='CS-00005'"), {"n": orig})
    check("p3_version_marker_changes_with_data", facts_for(q)["version"] != "none")
    c.flush()


# ---------------------------------------------------------------- Part 4
def part4() -> None:
    from agents import AnsweringAgent, EvaluatorAgent, solve

    p4 = HERE / "Part-14"
    ok = True
    for name in ("training_data.json", "validation_data.json", "test_data.json"):
        data = json.loads((p4 / name).read_text(encoding="utf-8"))
        ok &= all(set(d) == {"id", "question"} for d in data)
    check("p4_datasets_contain_only_questions", ok)
    ids = [d["question"] for n in ("training_data.json", "validation_data.json", "test_data.json")
           for d in json.loads((p4 / n).read_text(encoding="utf-8"))]
    check("p4_no_question_shared_across_splits", len(ids) == len(set(ids)))
    lessons = json.loads((p4 / "lessons.json").read_text(encoding="utf-8"))
    need = {"lesson_id", "failure_pattern", "correction", "created_at", "use_count"}
    check("p4_lessons_have_required_fields", bool(lessons) and all(need <= set(lesson) for lesson in lessons), f"{len(lessons)} lessons")

    ev = EvaluatorAgent()
    q = "How many seats are available in CS-00018?"
    check("p4_evaluator_passes_correct", ev.evaluate(q, "CS-00018 has 8 seats available.").result == "PASS")
    check("p4_evaluator_revises_wrong", ev.evaluate(q, "CS-00018 has 30 seats available.").result == "REVISE")
    check("p4_evaluator_revises_unsupported",
          ev.evaluate("What is the capital of France?", "Paris.").result == "REVISE")
    check("p4_evaluator_passes_decline",
          ev.evaluate("What is the capital of France?", "I can only answer course catalogue questions.").result == "PASS")

    class Stub:
        def __init__(self):
            self.n = 0

        def answer(self, question, feedback=None, previous_answer=None, forced_answer=None):
            self.n += 1
            return {"answer": "no idea", "lessons_used": [], "attempt_ms": 0.0}

    stub = Stub()
    r = solve(q, stub, ev, max_attempts=2)
    check("p4_stops_after_two_attempts", stub.n == 2 and r["attempts"] == 2 and r["final_result"] == "REVISE")
    _ = AnsweringAgent  # imported to prove the class loads


def main() -> None:
    for fn in (part1, part23, part4):
        try:
            fn()
        except Exception as e:  # keep going so one broken part does not hide the others
            check(f"{fn.__name__}_ran_without_exception", False, repr(e))
    out = {"homework": "hw09", "sid4": SID4, "commit_hash": commit_hash(), "seed": SEED, "verify_seed": VERIFY_SEED,
           "model": "qwen2.5:1.5b-instruct (Ollama) via the shared ModelClient; embeddings all-MiniLM-L6-v2",
           "checks": checks, "all_pass": all(c["pass"] for c in checks)}
    (HERE / "reports" / "hw09" / "verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n{sum(c['pass'] for c in checks)}/{len(checks)} checks passed")
    sys.exit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
