"""One-off script: turns Part 4/5's real captured raw/*.json evidence into
styled terminal-look HTML pages (shots_html/*.html) for Playwright to
screenshot. Not part of the graded deliverable -- the text inside each
page is the exact real output captured in raw/."""

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


def read_json(name):
    return json.loads((HERE / "raw" / name).read_text(encoding="utf-8"))


def format_scenario(d):
    lines = [f"stop_reason: {d['stop_reason']}  tool_call_count: {d.get('tool_call_count')}  total_time_ms: {d['total_time_ms']}", ""]
    for t in d["timeline"]:
        if t["type"] == "tool_call":
            lines.append(f"CALL  {t['tool']}({t['args']})")
        else:
            content = t["content"]
            if len(content) > 300:
                content = content[:300] + "... (truncated)"
            lines.append(f"OBS   {t['tool']} -> {content}")
    lines.append("")
    lines.append("FINAL ANSWER:")
    lines.append(d["final_answer"] or "(none)")
    return "\n".join(lines)


# --- Part 4 ---------------------------------------------------------
pay = read_json("bikeshare_pay_per_use.json")
write_page("p4_scenario_pay_per_use", "python run_scenarios.py -- scenario: pay_per_use (3 rides/mo, 8 min each)", format_scenario(pay))

mem = read_json("bikeshare_membership.json")
write_page("p4_scenario_membership", "python run_scenarios.py -- scenario: membership (40 rides/mo, 20 min each)", format_scenario(mem))

snapshot = json.loads((HERE.parent.parent / "Part-8" / "pricing_snapshots" / "snapshot_metadata.json").read_text(encoding="utf-8"))
write_page("p4_snapshot_metadata", "Part-8/pricing_snapshots/snapshot_metadata.json (real fetch, hashed)", json.dumps(snapshot, indent=2))

# --- Part 5 ----------------------------------------------------------
injection = read_json("prompt_injection_results.json")
lines = []
for cfg, data in injection.items():
    lines.append(f"=== config: {cfg} ===")
    lines.append(f"stop_reason: {data['stop_reason']}")
    for c in data["checks"]:
        status = "SUCCEEDED (attack got through)" if c["succeeded"] else "did not occur"
        lines.append(f"  {c['attack']}: {status}")
    lines.append(f"final answer (excerpt): {(data['final_answer'] or '')[:220]}")
    lines.append("")
write_page("p5_attack_results", "python run_prompt_injection_test.py -- 3 attacks x 3 defense configs", "\n".join(lines).strip())

print("done")
