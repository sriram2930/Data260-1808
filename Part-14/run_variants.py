"""
Part-14/run_variants.py -- DATA-260 HW9, Part 4.4 (final evaluation on test_data.json, four variants)

  1 Baseline              one attempt, no evaluator feedback, no lessons
  2 Evaluator Repair      up to 2 attempts, evaluator feedback, no lessons
  3 Lesson Memory         Evaluator Repair + EVERY lesson in lessons.json loaded (no validation gate)
  4 Validated Improvement Evaluator Repair + only lessons whose status is "kept" (passed run_validation.py)

test_data.json is read only here, after lessons were selected on training/validation, and is never
modified. Lessons are not created or edited during this run (the test set may not be used to create
lessons); use_count is written to a scratch copy so the real lessons.json is untouched.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agents import AnsweringAgent, EvaluatorAgent, LessonStore, solve  # noqa: E402

RAW = HERE.parent / "reports" / "hw09" / "raw"
test = json.loads((HERE / "test_data.json").read_text(encoding="utf-8"))
ev = EvaluatorAgent()
all_lessons = LessonStore().load()
kept = [lesson for lesson in all_lessons if lesson["status"] == "kept"]

scratch = Path(tempfile.mkdtemp()) / "lessons.json"
shutil.copy(HERE / "lessons.json", scratch)
store = LessonStore(scratch)

VARIANTS = [
    ("Baseline", [], 1),
    ("Evaluator Repair", [], 2),
    ("Lesson Memory", all_lessons, 2),
    ("Validated Improvement", kept, 2),
]
print("=== Part 4.4 final test | student Sreeramachandrasai Achutuni ===")
print(f"lessons in lessons.json: {[lesson['lesson_id'] for lesson in all_lessons]} | kept after validation: {[lesson['lesson_id'] for lesson in kept]}\n")
table, detail = [], {}
for name, lessons, max_attempts in VARIANTS:
    agent = AnsweringAgent(lessons=lessons, store=store)
    rows = []
    for item in test:
        r = solve(item["question"], agent, ev, max_attempts=max_attempts)
        r["id"] = item["id"]
        rows.append(r)
    ok = sum(r["final_result"] == "PASS" for r in rows)
    row = {"variant": name, "correct": ok, "incorrect": len(rows) - ok,
           "avg_attempts": round(sum(r["attempts"] for r in rows) / len(rows), 2),
           "avg_latency_s": round(sum(r["latency_ms"] for r in rows) / len(rows) / 1000, 2),
           "first_attempt_correct": sum(r["first_attempt_result"] == "PASS" for r in rows)}
    table.append(row)
    detail[name] = rows
    print(f"{name:<22} correct={ok:>2}/20 incorrect={row['incorrect']:>2} avg_attempts={row['avg_attempts']:.2f} "
          f"avg_latency={row['avg_latency_s']:.2f}s (first-attempt correct {row['first_attempt_correct']}/20)")
    print("   failed: " + (", ".join(f"{r['id']}" for r in rows if r["final_result"] != "PASS") or "none"))

(RAW / "part4_test_results.json").write_text(json.dumps({"table": table, "detail": detail}, indent=2), encoding="utf-8")
print("\n| Variant | Correct | Incorrect | Avg attempts | Avg latency (s) |")
for r in table:
    print(f"| {r['variant']} | {r['correct']} | {r['incorrect']} | {r['avg_attempts']} | {r['avg_latency_s']} |")
