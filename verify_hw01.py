"""
verify_hw01.py — DATA-260 HW1 self-check script.

Runs a handful of basic structural/environment checks and writes the results
to reports/hw01/verification.json. Not exhaustive — just enough to confirm the
repo is internally consistent and the local environment can actually run the
homework (required files present, Python version compatible, Ollama reachable
with the target model pulled, raw experiment data well-formed).

Usage:
    python verify_hw01.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
MODEL = "qwen2.5:1.5b-instruct"
OLLAMA_HOST = "http://localhost:11434"

checks: list[dict] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def file_exists(rel_path: str) -> bool:
    return (HERE / rel_path).is_file()


# --- Required files present -------------------------------------------------
for rel in [
    "Part-1/index.html", "Part-1/app.js", "Part-1/Dockerfile",
    "Part-1/nginx.conf", "Part-1/DOMAIN_SCHEMA.md",
    "Part-2/agents_demo.py", "Part-3/run_nondeterminism.py",
    "Part-4/src/model_client.py", "Part-4/hw1_client.py", "Part-4/AGENT.md",
    "requirements.txt",
    "reports/hw01/METRICS.md", "reports/hw01/AI_USE.md",
    "reports/hw01/PART2_AGENTIC_AI.md", "reports/hw01/RUN_LOG.txt",
    "reports/hw01/cases/nondeterminism_input.json",
    "reports/hw01/raw/nondeterminism_runs.json",
    "reports/hw01/raw/nondeterminism_runs.csv",
    "reports/hw01/raw/nondeterminism_summary.json",
]:
    check(f"file exists: {rel}", file_exists(rel))

# --- Python version ----------------------------------------------------------
py_ok = (3, 11) <= sys.version_info[:2] <= (3, 12)
check("python version in [3.11, 3.12]", py_ok, f"running {sys.version.split()[0]}")

# --- index.html has the required form elements --------------------------------
try:
    html = (HERE / "Part-1" / "index.html").read_text(encoding="utf-8")
    check("index.html has <title>HW1-", "HW1-" in html)
    check("index.html has autofocus input", "autofocus" in html)
    check("index.html has email input", 'type="email"' in html)
    check("index.html has textarea", "<textarea" in html)
    check("index.html has 4 <option> department values",
          html.count("<option value=") == 4, f"found {html.count('<option value=')}")
    check("index.html has terms checkbox", 'type="checkbox"' in html and "terms and conditions" in html)
except FileNotFoundError:
    check("index.html readable", False)

# --- app.js has the required JS patterns --------------------------------------
try:
    js = (HERE / "Part-1" / "app.js").read_text(encoding="utf-8")
    check("app.js uses arrow function validation", "=>" in js and "validateForm" in js)
    check("app.js uses JSON.stringify", "JSON.stringify" in js)
    check("app.js uses destructuring", "const {" in js)
    check("app.js uses spread operator", "..." in js)
    check("app.js uses a closure counter", "createSubmissionCounter" in js)
except FileNotFoundError:
    check("app.js readable", False)

# --- Ollama reachable + model present -----------------------------------------
try:
    with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
        tags = json.loads(resp.read())
    model_names = [m.get("name", "") for m in tags.get("models", [])]
    check("ollama reachable", True)
    check(f"model pulled: {MODEL}", any(MODEL in m for m in model_names), f"models: {model_names}")
except Exception as exc:
    check("ollama reachable", False, str(exc))
    check(f"model pulled: {MODEL}", False, "skipped, ollama unreachable")

# --- Non-determinism raw data well-formed -------------------------------------
try:
    runs = json.loads((HERE / "reports/hw01/raw/nondeterminism_runs.json").read_text(encoding="utf-8"))
    check("nondeterminism_runs.json has 40 records", len(runs) == 40, f"found {len(runs)}")
    check("every run has tags + latency_ms", all("tags" in r and "latency_ms" in r for r in runs))
except Exception as exc:
    check("nondeterminism_runs.json well-formed", False, str(exc))

# --- Summary ------------------------------------------------------------------
passed_count = sum(1 for c in checks if c["passed"])
result = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "total_checks": len(checks),
    "passed": passed_count,
    "failed": len(checks) - passed_count,
    "checks": checks,
}

out_path = HERE / "reports" / "hw01" / "verification.json"
out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

print(json.dumps(result, indent=2))
print(f"\n{passed_count}/{len(checks)} checks passed. Written to {out_path}")
