"""
Part-14/make_datasets.py -- DATA-260 HW9, Part 4 (input datasets + reference dataset)

Writes training_data.json / validation_data.json / test_data.json (questions ONLY -- no
expected answers anywhere in them) and builds reference_dataset.json (the ground truth the
Evaluator checks against) from s1808_rel: every department, plus every course (and its
sections) whose code appears in any of the three question files.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Part-1"))
from db import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

TRAIN = [
    "Who teaches CS-00020 and in which semester?",
    "Who is the instructor for ENGR-00040, and how many students are enrolled in that section?",
    "Which semester is BUS-00065 offered, and who teaches it?",
    "What is the title of CS-00121 and which department offers it?",
    "What is the title of ENGR-00003, and which department offers it?",
    "How many seats are available in CS-00005?",
    "How many seats are available in DATA-00006, and what is its title?",
    "Where is the Computer Science department located, and what is its department code?",
    "What is the department code and building for Business Analytics?",
    "Which has more available seats, DATA-00006 or DATA-00007?",
    "How many students are enrolled in the Fall 2026 section of CS-00020, and who teaches it?",
    "What is the capital of France?",
    "Who won the 2018 FIFA World Cup?",
    "How do I bake sourdough bread?",
    "How many seats are available in course CS-09999?",
    "Who teaches DATA-09001 in Fall 2026?",
    "What is the title and seat count of CS-00018?",
    "Who teaches BUS-00134, and what is the term?",
    "Which department offers DATA-00016 and what is its title?",
    "What building is the Engineering department in, and what is its department code?",
]
VALID = [
    "Who teaches BUS-00180 and in which semester?",
    "Who is the instructor for CS-00185, and how many students are enrolled?",
    "What is the title of DATA-00211 and which department offers it?",
    "What is the title of BUS-00002, and which department offers it?",
    "How many seats are available in DATA-00007?",
    "How many seats are available in CS-00018, and what is its title?",
    "Where is the Data Science & AI department located, and what is its department code?",
    "What is the department code and building for Engineering?",
    "Which has more available seats, CS-00005 or CS-00018?",
    "How many students are enrolled in the Spring 2027 section of DATA-00241, and who teaches it?",
    "Which semester is BUS-00220 offered, and who teaches it?",
    "What is the tallest mountain in the world?",
    "Write a haiku about autumn rain.",
    "What is a good recipe for vegetable curry?",
    "How many seats are available in course ENGR-09999?",
    "Who teaches CS-08888 in Fall 2026?",
    "What is the title and seat count of ENGR-00004?",
    "Who teaches BUS-00227 and how many students are enrolled?",
    "Which department offers CS-00024, and what is its title?",
    "Where is the Business Analytics department located?",
]
TEST = [
    "Who teaches DATA-00272 and in which semester?",
    "Who is the instructor for ENGR-00327, and how many students are enrolled in that section?",
    "Who teaches BUS-00265, and in which semester is it offered?",
    "What is the title of DATA-00015, and which department offers it?",
    "What is the title of CS-00025 and which department offers it?",
    "How many seats are available in DATA-00007, and what is its title?",
    "How many seats are available in CS-00020?",
    "Where is the Engineering department located, and what is its department code?",
    "What are the building and department code for Data Science & AI?",
    "Which has more available seats, CS-00018 or DATA-00006?",
    "How many students are enrolled in the Fall 2026 section of BUS-00065, and who teaches it?",
    "Who painted the Mona Lisa?",
    "How does a blockchain reach consensus?",
    "Explain how photosynthesis works.",
    "How many seats are available in course DATA-09999?",
    "Who teaches BUS-07777 in Spring 2027?",
    "What is the title and seat count of DATA-00028?",
    "Who teaches CS-00121 and how many students are enrolled?",
    "Which department offers DATA-00241, and what is its title?",
    "Where is the Computer Science department located?",
]


def write(name: str, qs: list[str], prefix: str) -> None:
    data = [{"id": f"{prefix}{i:02d}", "question": q} for i, q in enumerate(qs, 1)]
    (HERE / name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


write("training_data.json", TRAIN, "tr")
write("validation_data.json", VALID, "va")
write("test_data.json", TEST, "te")

codes = sorted({m.group(0).upper() for q in TRAIN + VALID + TEST for m in re.finditer(r"\b[A-Za-z]{2,4}-\d{5}\b", q)})
with engine.connect() as conn:
    depts = [dict(r._mapping) for r in conn.execute(text("SELECT name, dept_code, building FROM departments ORDER BY id"))]
    courses = []
    for code in codes:
        row = conn.execute(
            text("SELECT id, course_code, course_title, department, seats_available FROM courses WHERE course_code=:c"), {"c": code}
        ).first()
        if not row:
            continue  # nonexistent codes are deliberately absent from the reference
        c = dict(row._mapping)
        cid = c.pop("id")
        c["sections"] = [
            dict(r._mapping)
            for r in conn.execute(
                text("SELECT semester, instructor, enrolled_count FROM sections WHERE course_id=:i ORDER BY id"), {"i": cid}
            )
        ]
        courses.append(c)
ref = {
    "description": "Ground truth for the HW9 Part 4 Evaluator Agent: course catalogue facts exported from s1808_rel. "
                   "Course codes not listed here do not exist in the catalogue.",
    "departments": depts,
    "courses": courses,
}
(HERE / "reference_dataset.json").write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"train={len(TRAIN)} valid={len(VALID)} test={len(TEST)} | reference: {len(depts)} departments, {len(courses)} courses")
