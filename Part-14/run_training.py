"""
Part-14/run_training.py -- DATA-260 HW9, Part 4.1/4.2 (develop on training_data.json only)

Runs the Evaluator-Repair workflow (no lessons) over training_data.json, tallies the
failure pattern the Evaluator reports on each FIRST attempt, and turns every pattern that
repeats on >= MIN_REPEATS distinct questions into a reusable lesson in lessons.json
(status "candidate": not yet validated). test_data.json is never read here.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agents import AnsweringAgent, EvaluatorAgent, LessonStore, solve  # noqa: E402

MIN_REPEATS = 2
RAW = HERE.parent / "reports" / "hw09" / "raw"

train = json.loads((HERE / "training_data.json").read_text(encoding="utf-8"))
ev = EvaluatorAgent()
agent = AnsweringAgent(lessons=[])
store = LessonStore()
store.save([])  # fresh lessons.json for this development run

print("=== Part 4 training run | student Sreeramachandrasai Achutuni | evaluator-repair, no lessons ===")
results, counter = [], collections.Counter()
for item in train:
    r = solve(item["question"], agent, ev)
    r["id"] = item["id"]
    results.append(r)
    for p in set(r["first_attempt_patterns"]):
        counter[p] += 1
    print(f"{item['id']} first={r['first_attempt_result']:<6} final={r['final_result']:<6} attempts={r['attempts']} {r['first_attempt_patterns']}  | {item['question']}")

print("\nFailure patterns on first attempts (distinct questions):")
for p, n in counter.most_common():
    print(f"  {p}: {n}")
created = []
for p, n in counter.most_common():
    if n >= MIN_REPEATS:
        lesson = store.add_from_pattern(p, status="candidate")
        if lesson:
            created.append(lesson)
            print(f"  -> created {lesson['lesson_id']} (trigger={lesson['trigger']}): {lesson['failure_pattern']}")
RAW.mkdir(parents=True, exist_ok=True)
(RAW / "part4_training.json").write_text(json.dumps({"results": results, "patterns": counter, "lessons_created": created}, indent=2), encoding="utf-8")
first_ok = sum(r["first_attempt_result"] == "PASS" for r in results)
final_ok = sum(r["final_result"] == "PASS" for r in results)
print(f"\ntraining: first-attempt PASS {first_ok}/{len(train)} | after repair PASS {final_ok}/{len(train)}")
