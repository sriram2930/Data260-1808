"""
Part-15/make_eval_cases.py -- DATA-260 HW10, Part 3.1 (freeze the evaluation cases)

Sends 20 fixed domain questions (course lookups, department lookups, comparisons, tricky/ambiguous, off-topic,
nonexistent-course) through the real traced pipeline and saves each Writer draft with the question, grounding facts
and plan it was written from. The questions are written before any draft exists and are not re-selected afterwards:
whatever the Writer produced is what gets labelled.

Outputs (reports/hw10/ + Part-15/):  eval_cases.json, human_labels.csv (blank), labeling_sheet.md
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_service import TracedQA  # noqa: E402

QUESTIONS = [
    ("c01", "How many seats are left in CS-00018?"),
    ("c02", "Tell me the title and department of DATA-00016."),
    ("c03", "Who is teaching BUS-00134 and when is it offered?"),
    ("c04", "What is the enrollment of CS-00185 and who is its instructor?"),
    ("c05", "Where is the Computer Science department housed?"),
    ("c06", "What building is Business Analytics in, and what is its department code?"),
    ("c07", "Compare the seat availability of DATA-00006 and DATA-00007."),
    ("c08", "Which course has more seats, CS-00005 or CS-00018, and by how many?"),
    ("c09", "List the sections of ENGR-00040 with instructor and enrollment."),
    ("c10", "I want to take DATA-00272. Who teaches it and is it full?"),
    ("c11", "What is CS-00121 about?"),
    ("c12", "Is DATA-00241 offered in Fall 2026?"),
    ("c13", "Summarize everything you know about BUS-00227."),
    ("c14", "Which department offers Advanced Database Systems?"),
    ("c15", "How many courses does the Engineering department offer?"),
    ("c16", "Who painted the Mona Lisa?"),
    ("c17", "Explain how a hash table handles collisions."),
    ("c18", "How many seats are available in CS-09999?"),
    ("c19", "Who teaches DATA-08888 in Spring 2027?"),
    ("c20", "What prerequisites does DATA-00006 have?"),
]


def main() -> None:
    qa = TracedQA(timeout_s=240)
    cases = []
    for cid, q in QUESTIONS:
        r = qa.ask(q, store_on_miss=False)
        print(cid, r["status"], f"{r.get('latency_ms')} ms", "| draft:", (r.get("draft") or "")[:90].replace("\n", " "), flush=True)
        if r["status"] != "ok" or not r.get("draft"):
            raise SystemExit(f"{cid} failed: {r.get('error')}")
        cases.append({"case_id": cid, "trace_id": r["trace_id"], "question": q, "facts": r["facts"],
                      "plan": r["plan"], "draft": r["draft"]})
    qa.close()
    (HERE / "eval_cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    with (HERE / "human_labels.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "human_label"])
        for c in cases:
            w.writerow([c["case_id"], ""])
    lines = ["# HW10 labeling sheet (not committed code; read this, then fill human_labels.csv)\n",
             "Score each DRAFT 1-5 for helpfulness: 1 = very poor, 5 = excellent. Judge accuracy against the FACTS.\n"]
    for c in cases:
        lines += [f"\n## {c['case_id']}\n", f"**Question:** {c['question']}\n", "**Facts the Writer was given:**\n"]
        lines += [f"- {x}" for x in c["facts"]] or ["- (none matched)"]
        lines += ["\n**Writer draft:**\n", f"> {c['draft']}\n"]
    (HERE / "labeling_sheet.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote eval_cases.json, human_labels.csv (blank), labeling_sheet.md")


if __name__ == "__main__":
    main()
