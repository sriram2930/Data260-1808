"""
Part-13/domain_facts.py -- DATA-260 HW9, Parts 2-3 (grounding facts + data-version marker)

The HW8 pipeline is a generic Q&A pipeline with no database access, so a
"domain answer that depends on a s1808_rel record" needs the record put in
front of it. facts_for(question) resolves the course codes / department
names in a question against s1808_rel and returns:

  facts    -- plain-text lines handed to the pipeline as the only allowed source
  version  -- sha1 of the full content of every row those facts came from.
              This is the "data-version marker" stored with each cache entry:
              change any of those rows and the marker changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Part-1"))
from db import engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,4})-(\d{5})\b")


def _rows(conn, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def facts_for(question: str) -> dict:
    lines: list[str] = []
    row_dump: list[dict] = []
    with engine.connect() as conn:
        depts = _rows(conn, "SELECT id, name, building, dept_code, updated_at FROM departments ORDER BY id")
        q_low = question.lower()
        wanted_depts = {d["id"]: d for d in depts if d["name"].lower() in q_low}

        for m in COURSE_CODE_RE.finditer(question):
            code = f"{m.group(1).upper()}-{m.group(2)}"
            for c in _rows(
                conn,
                "SELECT id, course_code, course_title, department, department_id, seats_available "
                "FROM courses WHERE course_code = :c",
                c=code,
            ):
                row_dump.append({"courses": c})
                lines.append(
                    f"Course {c['course_code']}: title '{c['course_title']}', offered by the "
                    f"{c['department']} department, seats_available = {c['seats_available']}."
                )
                for s in _rows(
                    conn,
                    "SELECT id, semester, instructor, enrolled_count FROM sections WHERE course_id = :i ORDER BY id",
                    i=c["id"],
                ):
                    row_dump.append({"sections": s})
                    lines.append(
                        f"Section of {c['course_code']}: {s['semester']}, instructor {s['instructor']}, "
                        f"enrolled_count = {s['enrolled_count']}."
                    )
            if not lines or not any(code in ln for ln in lines):
                lines.append(f"No course with code {code} exists in the catalogue.")

        for d in wanted_depts.values():
            row_dump.append({"departments": {k: str(v) for k, v in d.items()}})
            lines.append(
                f"Department {d['name']}: department code {d['dept_code']}, located in {d['building']}."
            )

    version = hashlib.sha1(json.dumps(row_dump, sort_keys=True, default=str).encode()).hexdigest()[:12] if row_dump else "none"
    return {"facts": lines, "version": version, "depends_on_db": bool(row_dump)}


if __name__ == "__main__":
    for q in sys.argv[1:] or ["How many seats are available in course CS-00005?"]:
        print(json.dumps(facts_for(q), indent=2))
