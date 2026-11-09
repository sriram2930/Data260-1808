"""
Part-14/agents.py -- DATA-260 HW9, Part 4 (Answering Agent + Evaluator Agent + lessons)

Two agents that talk only through plain dict messages:

  AnsweringAgent.answer(question, feedback=None, previous_answer=None)
      -> {"answer", "lessons_used", "attempt_ms"}
  EvaluatorAgent.evaluate(question, answer)
      -> Evaluation(result "PASS"|"REVISE", explanation, feedback, patterns)

The Answering Agent calls the local model through the shared HW1 ModelClient adapter and
sees live catalogue facts from s1808_rel (Part-13/domain_facts.py). The Evaluator Agent never
sees those facts: its ground truth is the exported reference_dataset.json, so the two
sources are independent. The Evaluator is deterministic (rules over the reference data), not
an LLM judge -- see the report's limitation section.

solve() is the repair workflow: attempt 1 -> evaluate -> (REVISE) attempt 2 with feedback ->
evaluate -> stop. Never more than max_attempts (2) answer attempts.
"""

from __future__ import annotations

import datetime
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "Part-4"))
sys.path.insert(0, str(REPO_ROOT / "Part-13"))

from domain_facts import facts_for  # noqa: E402
from src.model_client import ModelClient  # noqa: E402

COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,4})-(\d{5})\b")
DECLINE_PHRASES = (
    "don't have", "do not have", "no information", "cannot answer", "can't answer", "can only answer",
    "only answer", "not in the", "no course", "does not exist", "doesn't exist", "not exist", "unable to",
    "not found", "no record", "not available in the", "not able to", "outside",
)
# question keyword -> slot (used by the Evaluator to decide what a correct answer must contain,
# and, in a deliberately simpler form, by the Answering Agent to decide which lessons are relevant)
SLOT_KEYWORDS = {
    "seats": r"\bseats?\b|capacity",
    "title": r"\btitle\b|\bname\b|\bcalled\b",
    "department": r"\bdepartment\b",
    "instructor": r"\bteach|\binstructor\b",
    "semester": r"\bsemester\b|\bterm\b",
    "enrolled": r"\benrolled\b|\benrollment\b",
    "building": r"\bbuilding\b|\blocated\b|\bwhere\b|\bhoused\b|\blocation\b",
    "dept_code": r"\bcode\b",
    "compare": r"\bmore available seats\b|\bmore seats\b|\bwhich has more\b",
}
SLOT_LABEL = {
    "seats": "number of seats", "title": "course title", "department": "offering department",
    "instructor": "instructor", "semester": "semester", "enrolled": "enrolled count",
    "building": "building", "dept_code": "department code", "compare": "comparison",
}


def detect_slots(question: str) -> list[str]:
    q = question.lower()
    return [s for s, pat in SLOT_KEYWORDS.items() if re.search(pat, q)]


# ----------------------------------------------------------------------------
# Evaluator Agent
# ----------------------------------------------------------------------------
@dataclass
class Evaluation:
    result: str  # "PASS" | "REVISE"
    explanation: str
    feedback: str = ""
    patterns: list[str] = field(default_factory=list)


class EvaluatorAgent:
    def __init__(self, reference_path: Path = HERE / "reference_dataset.json"):
        ref = json.loads(Path(reference_path).read_text(encoding="utf-8"))
        self.courses = {c["course_code"].upper(): c for c in ref["courses"]}
        self.depts = {d["name"].lower(): d for d in ref["departments"]}

    # what a correct answer must contain, derived from the reference dataset only
    def requirements(self, question: str) -> dict:
        q = question.lower()
        codes = [f"{m.group(1).upper()}-{m.group(2)}" for m in COURSE_CODE_RE.finditer(question)]
        dnames = [d for n, d in self.depts.items() if n in q]
        slots = detect_slots(question)
        if any(c not in self.courses for c in codes) or not (codes or dnames):
            return {"decline": True, "facts": []}
        facts: list[tuple[str, str]] = []
        for code in codes:
            c = self.courses[code]
            sec = c["sections"]
            for term in ("fall 2026", "spring 2027", "summer 2027"):
                if term in q:
                    sec = [s for s in sec if s["semester"].lower() == term]
            s0 = sec[0] if sec else None
            if "compare" in slots:
                if "seats" not in [f[0] for f in facts]:
                    pass
                facts.append(("seats", f"{code}|{c['seats_available']}"))
                continue
            if "seats" in slots:
                facts.append(("seats", str(c["seats_available"])))
            if "title" in slots:
                facts.append(("title", c["course_title"]))
            if "department" in slots:
                facts.append(("department", c["department"]))
            if s0 and "instructor" in slots:
                facts.append(("instructor", s0["instructor"]))
            if s0 and "semester" in slots:
                facts.append(("semester", s0["semester"]))
            if s0 and "enrolled" in slots:
                facts.append(("enrolled", str(s0["enrolled_count"])))
        for d in dnames:
            if "building" in slots:
                facts.append(("building", d["building"]))
            if "dept_code" in slots:
                facts.append(("dept_code", d["dept_code"]))
        return {"decline": False, "facts": facts, "compare": "compare" in slots, "codes": codes}

    @staticmethod
    def _contains(answer: str, value: str) -> bool:
        a = answer.lower()
        v = value.lower()
        if v.isdigit():
            return re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", a) is not None
        return v in a

    def evaluate(self, question: str, answer: str) -> Evaluation:
        req = self.requirements(question)
        a = answer.lower()
        if req["decline"]:
            if any(p in a for p in DECLINE_PHRASES):
                return Evaluation("PASS", "Correctly declined: the question is outside the catalogue or names a record that does not exist.")
            return Evaluation(
                "REVISE",
                "The answer gives unsupported content for a question the reference dataset cannot answer.",
                "This question is not about a course or department in the reference dataset (or names a course "
                "that does not exist). Do not answer from general knowledge; say you can only answer course "
                "catalogue questions and do not have that information.",
                ["unsupported_answer"],
            )
        missing: list[tuple[str, str]] = []
        if req.get("compare"):
            vals = [f[1].split("|") for f in req["facts"]]
            winner = max(vals, key=lambda cv: int(cv[1]))
            for code, seats in vals:
                pair = rf"{re.escape(code.lower())}.{{0,70}}?(?<![\d.]){seats}(?!\d)|(?<![\d.]){seats}(?!\d).{{0,70}}?{re.escape(code.lower())}"
                if not re.search(pair, a):
                    missing.append(("seats", f"{code} has {seats} seats"))
            if winner[0].lower() not in a:
                missing.append(("compare", f"{winner[0]} has more available seats ({winner[1]})"))
            else:
                ties = [cv for cv in vals if int(cv[1]) == int(winner[1])]
                if len(ties) == 1:
                    # the winner must be the first course named in a sentence that says "more"
                    first_code = min(vals, key=lambda cv: a.find(cv[0].lower()) if cv[0].lower() in a else 10**6)[0]
                    if "more" in a and first_code != winner[0] and not re.search(rf"{re.escape(winner[0].lower())}[^.]*\bmore\b", a):
                        missing.append(("compare", f"{winner[0]} has more available seats ({winner[1]})"))
        else:
            for slot, value in req["facts"]:
                if not self._contains(answer, value):
                    missing.append((slot, value))
        if not missing:
            return Evaluation("PASS", "Every required fact from the reference dataset appears in the answer.")
        parts = [f"{SLOT_LABEL[s]} = '{v}'" for s, v in missing]
        return Evaluation(
            "REVISE",
            "The answer is missing or misstates: " + ", ".join(f"{SLOT_LABEL[s]}" for s, _ in missing) + ".",
            "Revise the answer. The reference dataset says: " + "; ".join(parts) + ". State each of these explicitly.",
            [f"missing_fact:{s}" for s, _ in missing],
        )


# ----------------------------------------------------------------------------
# Lessons
# ----------------------------------------------------------------------------
LESSON_TEMPLATES = {
    "unsupported_answer": (
        "The answer gives general-knowledge or unsupported content for a question the catalogue cannot answer.",
        "If no catalogue facts are provided, or the facts say a course does not exist, reply that you can only answer "
        "course catalogue questions and do not have that information. Never answer from general knowledge.",
        "no_facts",
    ),
}


def _slot_lesson(slot: str) -> tuple[str, str, str]:
    label = SLOT_LABEL[slot]
    return (
        f"The answer omits the {label}.",
        f"When the question asks about the {label}, read it from the catalogue facts and state it explicitly in the "
        f"answer, together with every other item the question asks for.",
        slot,
    )


class LessonStore:
    def __init__(self, path: Path = HERE / "lessons.json"):
        self.path = Path(path)

    def load(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def save(self, lessons: list[dict]) -> None:
        self.path.write_text(json.dumps(lessons, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_from_pattern(self, pattern: str, status: str = "candidate") -> Optional[dict]:
        lessons = self.load()
        if any(lesson["pattern_key"] == pattern for lesson in lessons):
            return None
        if pattern == "unsupported_answer":
            fp, corr, trig = LESSON_TEMPLATES[pattern]
        elif pattern.startswith("missing_fact:"):
            fp, corr, trig = _slot_lesson(pattern.split(":", 1)[1])
        else:
            return None
        lesson = {
            "lesson_id": f"lesson_{len(lessons) + 1:03d}",
            "failure_pattern": fp,
            "correction": corr,
            "created_at": datetime.date.today().isoformat(),
            "use_count": 0,
            "trigger": trig,
            "pattern_key": pattern,
            "status": status,
        }
        lessons.append(lesson)
        self.save(lessons)
        return lesson

    @staticmethod
    def relevant(lessons: list[dict], question: str, facts_missing: bool) -> list[dict]:
        slots = set(detect_slots(question))
        out = []
        for lesson in lessons:
            if lesson["trigger"] == "no_facts":
                if facts_missing:
                    out.append(lesson)
            elif lesson["trigger"] in slots:
                out.append(lesson)
        return out

    def mark_used(self, lesson_ids: list[str]) -> None:
        if not lesson_ids:
            return
        lessons = self.load()
        for lesson in lessons:
            if lesson["lesson_id"] in lesson_ids:
                lesson["use_count"] += 1
        self.save(lessons)


# ----------------------------------------------------------------------------
# Answering Agent
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a helpful assistant for a university course catalogue. Answer the user's question in one to "
    "three sentences. Catalogue facts retrieved for the question are listed below the question."
)


class AnsweringAgent:
    def __init__(self, model: Optional[ModelClient] = None, lessons: Optional[list[dict]] = None,
                 store: Optional[LessonStore] = None):
        self.model = model or ModelClient(temperature=0)
        self.lessons = lessons or []
        self.store = store

    def answer(self, question: str, feedback: Optional[str] = None, previous_answer: Optional[str] = None,
               forced_answer: Optional[str] = None) -> dict:
        t0 = time.perf_counter()
        f = facts_for(question)
        facts_missing = (not f["facts"]) or any("No course with code" in x for x in f["facts"])
        used = LessonStore.relevant(self.lessons, question, facts_missing) if self.lessons else []

        sys_prompt = SYSTEM_PROMPT
        if used:
            sys_prompt += "\n\nLessons learned from earlier mistakes (follow them):\n" + "\n".join(
                f"- [{lesson['lesson_id']}] {lesson['correction']}" for lesson in used)
        facts_block = "Catalogue facts:\n" + ("\n".join(f"- {x}" for x in f["facts"]) if f["facts"] else "(none found)")
        user = f"QUESTION: {question}\n\n{facts_block}"
        messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]
        if feedback:
            # Multi-turn: the model sees its own previous answer as an assistant turn, then the evaluator's
            # feedback as a new user turn. (A single prompt that embedded both made the 1.5B model repeat
            # itself verbatim in development -- see METRICS.md.)
            messages += [
                {"role": "assistant", "content": previous_answer},
                {"role": "user", "content": f"An evaluator rejected your answer.\nFeedback: {feedback}\nWrite a corrected answer."},
            ]

        if forced_answer is not None:  # controlled test case: a deliberately bad first attempt
            text = forced_answer
        else:
            text = self.model.complete(messages)["content"].strip()
        if used and self.store is not None:
            self.store.mark_used([lesson["lesson_id"] for lesson in used])
        return {"answer": text, "lessons_used": [lesson["lesson_id"] for lesson in used],
                "attempt_ms": (time.perf_counter() - t0) * 1000.0}


# ----------------------------------------------------------------------------
# Workflow
# ----------------------------------------------------------------------------
def solve(question: str, answerer: AnsweringAgent, evaluator: EvaluatorAgent, max_attempts: int = 2,
          forced_first_answer: Optional[str] = None) -> dict:
    """attempt -> evaluate -> (REVISE and attempts left) -> revise -> evaluate -> stop."""
    t0 = time.perf_counter()
    trace, feedback, prev = [], None, None
    for attempt in range(1, max_attempts + 1):
        forced = forced_first_answer if attempt == 1 else None
        out = answerer.answer(question, feedback=feedback, previous_answer=prev, forced_answer=forced)
        ev = evaluator.evaluate(question, out["answer"])
        trace.append({"attempt": attempt, "answer": out["answer"], "result": ev.result,
                      "explanation": ev.explanation, "feedback": ev.feedback, "patterns": ev.patterns,
                      "lessons_used": out["lessons_used"]})
        if ev.result == "PASS":
            break
        feedback, prev = ev.feedback, out["answer"]
    final = trace[-1]
    return {
        "question": question, "final_answer": final["answer"], "final_result": final["result"],
        "attempts": len(trace), "first_attempt_result": trace[0]["result"],
        "first_attempt_patterns": trace[0]["patterns"], "trace": trace,
        "latency_ms": (time.perf_counter() - t0) * 1000.0,
    }
