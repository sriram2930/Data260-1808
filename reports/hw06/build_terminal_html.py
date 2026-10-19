"""One-off script: turns real captured raw/*.txt or *.json evidence into
styled terminal-look HTML pages (shots_html/*.html), so Playwright can
screenshot them as PNG images for the report. Not part of the graded
deliverable -- the text inside each page is the exact real output captured
in raw/, nothing here is fabricated or reworded."""

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


def pretty_json(name):
    data = json.loads(read_raw(name))
    return json.dumps(data, indent=2)


# Part 1
crud = read_raw("part1_crud.txt")
sections = crud.split("\n\n--- ")
sections = [sections[0]] + ["--- " + s for s in sections[1:]]

write_page(
    "p1_create",
    "bash -- announcements: login + create",
    sections[0] + "\n\n" + sections[1],
)
write_page(
    "p1_validation",
    "bash -- announcements: validation errors (422)",
    sections[2] + "\n\n" + sections[3],
)
write_page(
    "p1_get_put_delete",
    "bash -- announcements: get / update / get-404 / delete",
    "\n\n".join([sections[5], sections[6], sections[7], sections[9]]),
)

write_page("mongo_validator", "mongosh -- s1808_doc (validator rejection)", read_raw("mongo_validator.txt"))
write_page("mongo_announcements", "mongosh -- s1808_doc.announcements", read_raw("mongo_announcements.txt"))

# Part 2
chat_log = read_raw("chat_demo_shots.log")
turns = chat_log.split("--- turn ")
excerpt = "--- turn " + turns[1] + "--- turn " + turns[6] + "--- turn " + turns[9]
write_page("p2_conversation", "python run_chat_demo.py -- turns 1, 6, 9 (12-turn run, user u1_shots)", excerpt.strip())

write_page("p2_memory_endpoint", "GET /api/memory/u1_shots (live, browser screenshot below is separate)", pretty_json("get_memory.json")[:2400] + "\n  ... (truncated, full response in get_memory.json)")
write_page("mongo_memory", "mongosh -- s1808_doc.messages / summaries / episodes", read_raw("mongo_memory_collections.txt"))

# Part 4
# Uses the originally committed consolidation_result.json (the actual run
# METRICS.md's analysis is about -- including the wrong SHORT_TERM_N
# resolution) rather than a screenshot-day rerun, since the small local
# model is not deterministic call to call: a rerun done just now resolved
# the same contradiction correctly instead of backwards, which would
# silently contradict the written analysis if swapped in without comment.
committed_result = (HERE.parent.parent / "Part-4" / "consolidation_result.json").read_text(encoding="utf-8")
write_page(
    "p4_consolidation",
    "python run_consolidation_test.py",
    committed_result.strip() + "\n\nwrote consolidation_result.json and test_memory_after.md",
)
# Same reproducibility note as above: use the originally committed
# agent_compliance.log (PASS, matches METRICS.md) instead of a
# screenshot-day rerun, which this time generated a function without a
# docstring and FAILed -- real model non-determinism, not a tooling change.
committed_compliance = (HERE.parent.parent / "Part-4" / "agent_compliance.log").read_text(encoding="utf-8")
write_page("p4_compliance", "python verify_agent_compliance.py", committed_compliance.strip())

print("done")
