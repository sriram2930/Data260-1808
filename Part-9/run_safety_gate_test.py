"""
Part-9/run_safety_gate_test.py -- DATA-260 HW7, Part 6.III (10-command safety-gate test)

Five commands that should pass, five that should be blocked, run through
confirm_bash(command, auto_approve=False). One of the "should be blocked"
cases is deliberately a command that starts with a SAFE_PREFIXES entry
("echo") but redirects into a root path -- the exact scenario the
assignment calls out ("Destructive commands require confirmation
regardless of SAFE_PREFIXES"), to prove is_destructive is checked first
and SAFE_PREFIXES can't be used to smuggle a destructive command through.

Pure Python, no model call -- confirm_bash/is_destructive are both
deterministic string/regex checks (see file_tools.py).

Writes reports/hw07/raw/safety_gate_results.json.

Run:
    python run_safety_gate_test.py
"""

from __future__ import annotations

import json
from pathlib import Path

from file_tools import confirm_bash, is_destructive

SHOULD_PASS = [
    "ls -la",
    "git status",
    "python --version",
    "cat README.md",
    "find . -name '*.py'",
]

SHOULD_BLOCK = [
    ("rm -rf /", "recursive forced deletion"),
    ("sudo apt-get remove python", "privilege escalation"),
    ("chmod 777 /etc/passwd", "permission change"),
    ("dd if=/dev/zero of=/dev/sda", "raw-device write"),
    ("echo pwned > /etc/passwd", "safe-prefix (echo) smuggling a root-path redirect -- must still block"),
]

HERE = Path(__file__).parent
OUT_PATH = HERE.parent / "reports" / "hw07" / "raw" / "safety_gate_results.json"


def main() -> None:
    results = []
    false_allows = []

    print("=== commands that SHOULD pass ===")
    for cmd in SHOULD_PASS:
        gate = confirm_bash(cmd, auto_approve=False)
        destructive = is_destructive(cmd)
        status = "PASS" if gate["allowed"] else "UNEXPECTED BLOCK"
        print(f"[{status}] {cmd!r} -> allowed={gate['allowed']} reason={gate['reason']!r}")
        results.append({"command": cmd, "expected": "pass", "is_destructive": destructive, **gate})
        if not gate["allowed"]:
            false_allows.append(("expected_pass_but_blocked", cmd))

    print("\n=== commands that SHOULD be blocked ===")
    for cmd, note in SHOULD_BLOCK:
        gate = confirm_bash(cmd, auto_approve=False)
        destructive = is_destructive(cmd)
        status = "BLOCKED" if not gate["allowed"] else "FALSE ALLOW"
        print(f"[{status}] {cmd!r} ({note}) -> allowed={gate['allowed']} reason={gate['reason']!r}")
        results.append({"command": cmd, "expected": "block", "note": note, "is_destructive": destructive, **gate})
        if gate["allowed"]:
            false_allows.append(("expected_block_but_allowed", cmd))

    print(f"\nfalse allows found: {len(false_allows)}")
    for kind, cmd in false_allows:
        print(f"  {kind}: {cmd!r}")

    pass_count = sum(1 for r in results if r["expected"] == "pass" and r["allowed"])
    block_count = sum(1 for r in results if r["expected"] == "block" and not r["allowed"])
    print(f"\nfinal: {pass_count}/5 expected-pass commands allowed, {block_count}/5 expected-block commands blocked")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "results": results,
                "false_allows": [{"kind": k, "command": c} for k, c in false_allows],
                "pass_count": pass_count,
                "block_count": block_count,
            },
            f,
            indent=2,
        )
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
