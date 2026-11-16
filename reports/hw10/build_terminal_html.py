"""Turns the real captured raw/*.txt evidence into terminal-look HTML pages (shots_html/*.html) that Playwright
(shots.mjs) screenshots as PNGs for the report. The text is the exact captured output (HuggingFace/progress-bar noise
lines removed, long runs shortened with a visible '...' marker); the only addition is the command line shown first."""

import html
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = (HERE / "shots_html" / "_template.html").read_text(encoding="utf-8")
NOISE = ("Loading weights", "HF_TOKEN", "unauthenticated requests", "Warning:")


def raw(name: str) -> list[str]:
    lines = (HERE / "raw" / name).read_text(encoding="utf-8", errors="replace").splitlines()
    return [ln for ln in lines if not any(n in ln for n in NOISE) and ln.strip() != ""]


def page(name: str, title: str, lines: list[str]) -> None:
    out = TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__BODY__", html.escape("\n".join(lines)))
    (HERE / "shots_html" / f"{name}.html").write_text(out, encoding="utf-8")
    print("wrote", name)


def clip(s: str, n: int = 190) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


# ---- infrastructure + agents
page("t0_infra", "docker ps / kafka topics / redis index -- stack", (HERE / "raw" / "p0_infra.txt").read_text(encoding="utf-8").splitlines())

# ---- Part 4.2 trace examples
tr = raw("trace_demo_run.txt")
i2 = next(i for i, ln in enumerate(tr) if ln.startswith("=== 2."))
page("t1_trace_miss", "python Part-15/trace_demo.py -- Part 4.2 (1/2): the cache-miss trace", ["$ python Part-15/trace_demo.py"] + tr[:i2])
page("t1_trace_hit_fail", "python Part-15/trace_demo.py -- Part 4.2 (2/2): cache-hit and failed traces", tr[i2:])

# ---- Part 4.3 latency experiment
lx = raw("latency_experiment_run.txt")
page("t2_latency_run", "python Part-15/latency_experiment.py -- Part 4.3 (50 confirmed misses)",
     ["$ python Part-15/latency_experiment.py"] + [clip(x) for x in lx[:9]] + [f"   ... {len(lx) - 14} more requests (full log: reports/hw10/raw/latency_experiment_run.txt) ..."] + [clip(x) for x in lx[-5:]])
lt = (HERE / "raw" / "latency_report_run.txt").read_text(encoding="utf-8").splitlines()
page("t2_latency_table", "python Part-15/latency_report.py -- Part 4.3 stage table", ["$ python Part-15/latency_report.py"] + lt)

# ---- Part 2 evaluator
ev = raw("evaluator_run.txt")
page("t3_evaluator", "python Part-15/evaluator.py --pending -- Part 2 (judge qwen3:8b)",
     ["$ python Part-15/evaluator.py --pending --only <50 latency-experiment trace_ids>"] + [clip(x, 175) for x in ev[:7]] + [f"   ... {len(ev) - 10} more traces ..."] + [clip(x, 175) for x in ev[-3:]])
ex = raw("evaluator_example_run.txt")
page("t3_evaluator_example", "python Part-15/evaluator.py --trace <miss trace_id> -- Part 2 end-to-end test question", ex)

# ---- Part 3
vj = raw("validate_judge_run.txt")
start = next(i for i, ln in enumerate(vj) if ln.startswith("{"))
page("t4_judge_validation", "python Part-15/validate_judge.py -- Parts 3.2 / 3.3",
     ["$ python Part-15/validate_judge.py"] + vj[:4] + [f"   ... {start - 4} more judge calls (full log: reports/hw10/raw/validate_judge_run.txt) ..."] + [x if x.startswith("VERDICT") else clip(x, 175) for x in vj[start:]])
page("t4_freeze", "git log / ls -- labels frozen before any judge score", (HERE / "raw" / "p3_freeze_evidence.txt").read_text(encoding="utf-8").splitlines())

# ---- Part 1.1 traffic mix + verification
page("t5_traffic", "python Part-15/traffic_demo.py -- Part 1.1 traffic mix", ["$ python Part-15/traffic_demo.py"] + [clip(x, 175) for x in raw("traffic_demo_run.txt")])
page("t6_verify", "python verify_hw10.py", ["$ python verify_hw10.py"] + raw("verify_run.txt"))
