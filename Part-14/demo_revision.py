"""
Part-14/demo_revision.py -- DATA-260 HW9, Part 4.1 required demonstration #1 (controlled revision)

A CONTROLLED test case: the first attempt is deliberately incomplete (injected, not model output)
so the evaluator-feedback -> revision path is shown reliably. The revision itself is real model
output produced from the evaluator's feedback. Prints the full sequence, then a second
controlled case where the revision is skipped because attempt 1 already passes.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import AnsweringAgent, EvaluatorAgent, solve  # noqa: E402

Q = "Who teaches ENGR-00040 and how many students are enrolled in that section?"
BAD = "ENGR-00040 is taught in the Fall semester by one of the faculty members."

print("=== Part 4.1 controlled revision | student Sreeramachandrasai Achutuni ===\n")
r = solve(Q, AnsweringAgent(lessons=[]), EvaluatorAgent(), max_attempts=2, forced_first_answer=BAD)
print(f"QUESTION: {Q}\n")
for t in r["trace"]:
    kind = "initial answer (INJECTED incomplete answer)" if t["attempt"] == 1 else "revised answer (model, using feedback)"
    print(f"--- attempt {t['attempt']}: {kind}")
    print(f"  answer     : {t['answer']}")
    print(f"  evaluation : {t['result']}")
    print(f"  explanation: {t['explanation']}")
    if t["feedback"]:
        print(f"  feedback   : {t['feedback']}")
    print()
print(f"FINAL RESULT  : {r['final_result']}")
print(f"ATTEMPTS      : {r['attempts']} (maximum 2)")
print(f"FINAL RESPONSE: {r['final_answer']}")
