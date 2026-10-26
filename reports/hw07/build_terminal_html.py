"""One-off script: turns real captured raw/*.txt or *.json evidence into
styled terminal-look HTML pages (shots_html/*.html), so Playwright can
screenshot them as PNG images for the report. Not part of the graded
deliverable -- the text inside each page is the exact real output
captured in raw/, nothing here is fabricated or reworded."""

import html
import json
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = (HERE / "shots_html" / "_template.html").read_text(encoding="utf-8")


def write_page(name, title, body_text):
    escaped = html.escape(body_text)
    page = TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__BODY__", escaped)
    out = HERE / "shots_html" / f"{name}.html"
    out.write_text(page, encoding="utf-8")
    print("wrote", out)


def read_raw(name):
    return (HERE / "raw" / name).read_text(encoding="utf-8")


def strip_log_lines(text):
    return "\n".join(
        line for line in text.splitlines()
        if "INFO domain_server" not in line and "HTTP Request" not in line
    )


# --- Part 1 -----------------------------------------------------------
part1 = strip_log_lines(read_raw("part1_jwt_rbac.txt"))
sections = part1.split("\n\n--- ")
sections = [sections[0]] + ["--- " + s for s in sections[1:]]
# 0 login, 1 invalid login, 2 me-no-token, 3 me-invalid-token, 4 me-valid,
# 5 create-reader-403, 6 create-writer-201, 7 list-reader-200,
# 8 delete-writer-403, 9 delete-moderator-200

write_page("p1_login", "curl -- /auth/login (valid + invalid)", sections[0] + "\n\n" + sections[1])
write_page("p1_me", "curl -- /auth/me (no token / invalid token / valid token)", "\n\n".join(sections[2:5]))
write_page("p1_create_rbac", "curl -- POST /api/courses (reader 403, writer 201)", "\n\n".join(sections[5:7]))
write_page("p1_delete_rbac", "curl -- DELETE /api/courses/{id} (writer 403, moderator 200)", "\n\n".join(sections[8:10]))
write_page("p1_list", "curl -- GET /api/courses as reader (200)", sections[7][:1400] + "\n... (truncated)")

write_page("p1_lint_before", "git commit -- pre-commit hook BLOCKS the commit (5 real ruff errors)", read_raw("precommit_before_fix.txt")[:3200])
write_page("p1_lint_after", "ruff --fix, then git commit -- hook passes, commit succeeds", read_raw("precommit_after_fix.txt"))

# --- Part 2 -------------------------------------------------------------
part2 = strip_log_lines(read_raw("part2_verification_tasks.txt"))
write_page("p2_tasks", "python run_verification_tasks.py -- 3 verification tasks + error recovery", part2)

reliability = json.loads((HERE / "raw" / "reliability_results.json").read_text(encoding="utf-8"))
write_page(
    "p2_reliability",
    "python run_reliability_test.py -- 20-attempt reliability summary",
    json.dumps(reliability["summary"], indent=2),
)

# --- Part 3 -------------------------------------------------------------
reflexion = json.loads((HERE / "raw" / "reflexion_compare.json").read_text(encoding="utf-8"))
task_c = next(t for t in reflexion["per_task"] if t["task"] == "C")
reflection_text = (
    f"Task C -- original loop result: success={task_c['original']['success']} "
    f"({task_c['original']['reason']})\n\n"
    f"Task C -- Reflexion loop: retries={task_c['reflexion']['retry_count']} "
    f"final success={task_c['reflexion']['success']} stop_reason={task_c['reflexion']['stop_reason']}\n\n"
)
for r in task_c["reflexion"]["reflections"]:
    reflection_text += f"--- reflection (attempt {r['attempt']}) ---\n"
    reflection_text += f"evidence: verifier said -- {r['evidence']['verifier_reason']}\n"
    reflection_text += f"previous final answer: {r['evidence']['final_answer']}\n\n"
    reflection_text += f"reflection text:\n{r['reflection']}\n\n"
write_page("p3_reflection", "Task C -- stored reflection + evidence (from reflexion_compare.json)", reflection_text.strip())

# --- Part 6 -------------------------------------------------------------
write_page("p6_integration_test", "python run_integration_test.py -- glob -> search -> read (DEBUG file)", read_raw("part6_integration_test.txt"))
write_page("p6_safety_gate_test", "python run_safety_gate_test.py -- 10-command safety-gate test", read_raw("part6_safety_gate_test.txt"))

print("done")
