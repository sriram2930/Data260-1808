"""
Part-14/run_validation.py -- DATA-260 HW9, Part 4.3 (validate each lesson before keeping it)

For every candidate lesson in lessons.json: run validation_data.json single-attempt BEFORE
(no lessons) and AFTER (only that lesson), compare per question, and keep the lesson only if
  (a) no previously-correct answer became incorrect        (regression check)
  (b) the number of correct answers did not go down        (failures improve or stay unchanged)
  (c) no out-of-scope/nonexistent-course question newly gets an unsupported answer
Single-attempt is used on purpose: with the repair loop on, feedback can mask a lesson's effect.
A lesson that fails is marked "rejected" and documented in the output (not silently deleted).
test_data.json is never read here.  Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from agents import AnsweringAgent, EvaluatorAgent, LessonStore  # noqa: E402

RAW = HERE.parent / "reports" / "hw09" / "raw"
val = json.loads((HERE / "validation_data.json").read_text(encoding="utf-8"))
ev = EvaluatorAgent()
store = LessonStore()
lessons = store.load()


def run(use: list[dict]) -> dict:
    agent = AnsweringAgent(lessons=use)  # no store -> use_count not touched during validation
    out = {}
    for item in val:
        a = agent.answer(item["question"])
        e = ev.evaluate(item["question"], a["answer"])
        out[item["id"]] = {"question": item["question"], "answer": a["answer"], "pass": e.result == "PASS",
                           "patterns": e.patterns, "decline_expected": ev.requirements(item["question"])["decline"],
                           "lessons_used": a["lessons_used"]}
    return out


print("=== Part 4.3 validation | student Sreeramachandrasai Achutuni ===")
before = run([])
b = sum(v["pass"] for v in before.values())
print(f"BEFORE (no lessons): {b}/{len(val)} correct")
report = {"before": before, "lessons": {}}
for lesson in lessons:
    after = run([lesson])
    a = sum(v["pass"] for v in after.values())
    regress = [i for i in before if before[i]["pass"] and not after[i]["pass"]]
    fixed = [i for i in before if not before[i]["pass"] and after[i]["pass"]]
    new_unsupported = [i for i in before if after[i]["decline_expected"] and "unsupported_answer" in after[i]["patterns"]
                       and "unsupported_answer" not in before[i]["patterns"]]
    keep = (not regress) and a >= b and (not new_unsupported)
    lesson["status"] = "kept" if keep else "rejected"
    report["lessons"][lesson["lesson_id"]] = {"correct_after": a, "fixed": fixed, "regressed": regress,
                                          "new_unsupported": new_unsupported, "decision": lesson["status"], "after": after}
    print(f"\n{lesson['lesson_id']} [{lesson['pattern_key']}] AFTER: {a}/{len(val)} correct | fixed={fixed} regressed={regress} "
          f"new_unsupported={new_unsupported} -> {lesson['status'].upper()}")
store.save(lessons)
(RAW / "part4_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nlessons.json statuses:", {lesson["lesson_id"]: lesson["status"] for lesson in lessons})
