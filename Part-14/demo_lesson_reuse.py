"""
Part-14/demo_lesson_reuse.py -- DATA-260 HW9, Part 4.2 required demonstration #2 (lesson reuse)

Uses a scratch lessons file (the real lessons.json is not touched). Flow:
  1. A controlled bad first answer FAILS on question A -> the Evaluator reports a failure pattern
     -> a lesson is created immediately (min_repeats=1 here, so one failed answer is enough for the demo;
     run_training.py uses 2 for real lesson creation).
  2. The lesson is written to lessons.json-format storage (use_count 0).
  3. A LATER, related question B: the Answering Agent loads relevant lessons BEFORE answering,
     injects the correction into its prompt, and use_count goes 0 -> 1.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import AnsweringAgent, EvaluatorAgent, LessonStore, solve  # noqa: E402

store = LessonStore(Path(tempfile.mkdtemp()) / "lessons.json")
ev = EvaluatorAgent()

QA = "Who teaches BUS-00134, and what is the term?"
print("=== Part 4.2 lesson reuse | student Sreeramachandrasai Achutuni ===\n")
print("[1] Question A with a controlled failing first answer (injected):", QA)
ra = solve(QA, AnsweringAgent(lessons=[]), ev, max_attempts=1, forced_first_answer="BUS-00134 has a faculty member.")
print(f"    evaluator: {ra['first_attempt_result']}  patterns={ra['first_attempt_patterns']}")
for p in ra["first_attempt_patterns"]:
    lesson = store.add_from_pattern(p, status="kept")
    if lesson:
        print(f"    -> lesson created: {json.dumps(lesson)}")

print("\n[2] lessons file now contains:")
print(json.dumps([{k: lesson[k] for k in ("lesson_id", "failure_pattern", "correction", "created_at", "use_count")} for lesson in store.load()], indent=2))

QB = "Who teaches CS-00185 and in which semester?"
print(f"\n[3] LATER related question B: {QB}")
agent = AnsweringAgent(lessons=store.load(), store=store)
rb = solve(QB, agent, ev, max_attempts=2)
t = rb["trace"][0]
print(f"    lessons loaded before answering: {t['lessons_used']}")
print(f"    answer    : {t['answer']}")
print(f"    evaluation: {t['result']}  (attempts={rb['attempts']})")
print("\n[4] use_count after reuse:", [(lesson["lesson_id"], lesson["use_count"]) for lesson in store.load()])
