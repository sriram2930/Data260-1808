"""
Part-9/file_tools.py -- DATA-260 HW7, Part 6 (file tools and a safety gate)

Six file tools (read_file, write_file, edit_file, glob_files,
search_in_files, bash) plus a safety gate that stands between any model
output and an actual shell command. All file-tool tests run only inside a
temporary course sandbox directory (see run_integration_test.py /
run_safety_gate_test.py) -- nothing here ever touches the real repo.

Safety gate design (Part 6.I):
  - SAFE_PREFIXES is an allow-list of command prefixes considered routine
    (listing, reading, searching, running tests/python, git status/diff).
  - is_destructive(command) is a SEPARATE, independent deny-list check:
    recursive deletion, privilege escalation, permission/ownership changes,
    raw-device writes, filesystem creation, and redirection into a root
    path. It does not consult SAFE_PREFIXES at all.
  - confirm_bash(command, auto_approve=False) is the single gate every bash
    call goes through: a destructive command is blocked unless the caller
    explicitly passes auto_approve=True, REGARDLESS of whether the command
    also happens to start with a safe prefix (is_destructive always wins).
    A non-destructive command is allowed if it matches SAFE_PREFIXES, or if
    auto_approve=True; otherwise it is blocked pending confirmation.

Both is_destructive and confirm_bash are pure Python (regex/string checks
only) -- no model call, so they're deterministic and testable offline
(run_safety_gate_test.py).
"""

from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path
from typing import Optional

# --------------------------------------------------------------------- #
# Safety gate
# --------------------------------------------------------------------- #

SAFE_PREFIXES = (
    "ls",
    "dir",
    "cat",
    "type",
    "head",
    "tail",
    "pwd",
    "echo",
    "python",
    "pytest",
    "git status",
    "git diff",
    "git log",
    "find",
    "grep",
)

# Each pattern is matched case-insensitively against the whole command
# string. These are independent of SAFE_PREFIXES by design -- a command
# that starts with a safe prefix (e.g. "python") can still be destructive
# further along the line (e.g. "python -c \"import os; os.system('rm -rf /')\""),
# so is_destructive always gets the full command, never just the prefix.
_DESTRUCTIVE_PATTERNS = [
    (r"\brm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*)\b", "recursive forced deletion (rm -rf / -fr)"),
    (r"\bremove-item\b.*-recurse\b.*-force\b", "recursive forced deletion (Remove-Item -Recurse -Force)"),
    (r"\bremove-item\b.*-force\b.*-recurse\b", "recursive forced deletion (Remove-Item -Force -Recurse)"),
    (r"\brd\s+/s\b|\brmdir\s+/s\b|\bdel\s+/s\b", "recursive deletion (rd/rmdir/del /s)"),
    (r"\bsudo\b|\bsu\s+-|\brunas\b", "privilege escalation (sudo/su/runas)"),
    (r"\bchmod\b|\bchown\b|\bicacls\b|\btakeown\b", "permission/ownership change (chmod/chown/icacls/takeown)"),
    (r"\bdd\s+if=.*\bof=/dev/", "raw-device write (dd if=... of=/dev/...)"),
    (r">\s*/dev/sd\w*\b", "raw-device write (redirect to /dev/sdX)"),
    (r"\bmkfs\b|\bformat\s+[a-zA-Z]:", "filesystem creation (mkfs / format)"),
    (r">\s*/(etc|bin|boot|sys|root)\b", "redirection into a root-level path (> /etc, /bin, ...)"),
    (r">\s*[a-zA-Z]:\\\\?(windows|program\s*files)\b", "redirection into a root-level path (> C:\\Windows, ...)"),
]
_DESTRUCTIVE_COMPILED = [(re.compile(p, re.IGNORECASE), reason) for p, reason in _DESTRUCTIVE_PATTERNS]


def is_destructive(command: str) -> bool:
    """Returns True if `command` matches any deny-list pattern. Pure
    string/regex check -- no subprocess, no model call."""
    return any(pattern.search(command) for pattern, _reason in _DESTRUCTIVE_COMPILED)


def _destructive_reason(command: str) -> Optional[str]:
    for pattern, reason in _DESTRUCTIVE_COMPILED:
        if pattern.search(command):
            return reason
    return None


def confirm_bash(command: str, auto_approve: bool = False) -> dict:
    """Returns {"allowed": bool, "reason": str}. A destructive command is
    blocked unless auto_approve=True is explicitly passed, no matter what
    SAFE_PREFIXES says. A non-destructive command is allowed if it matches
    SAFE_PREFIXES or if auto_approve=True; otherwise it is blocked pending
    confirmation."""
    reason = _destructive_reason(command)
    if reason is not None:
        if auto_approve:
            return {"allowed": True, "reason": f"destructive ({reason}), explicitly confirmed"}
        return {"allowed": False, "reason": f"blocked: destructive command ({reason}); requires auto_approve=True"}

    if auto_approve:
        return {"allowed": True, "reason": "auto_approve=True"}

    if any(command.strip().lower().startswith(p) for p in SAFE_PREFIXES):
        return {"allowed": True, "reason": "matches a SAFE_PREFIXES entry"}

    return {"allowed": False, "reason": "not in SAFE_PREFIXES and not confirmed; pass auto_approve=True to run it"}


# --------------------------------------------------------------------- #
# File tools
# --------------------------------------------------------------------- #


def read_file(path: str, max_lines: Optional[int] = None) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    truncated = False
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    return {"ok": True, "content": "".join(lines), "line_count": len(lines), "truncated": truncated}


def write_file(path: str, content: str) -> dict:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(p), "bytes_written": len(content.encode("utf-8"))}


def edit_file(path: str, old_text: str, new_text: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    before = p.read_text(encoding="utf-8")
    if old_text not in before:
        return {"ok": False, "error": "old_text not found in file"}
    after = before.replace(old_text, new_text, 1)
    p.write_text(after, encoding="utf-8")
    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(), after.splitlines(), fromfile=path, tofile=path, lineterm=""
        )
    )
    return {"ok": True, "diff": diff}


def glob_files(pattern: str, root: str = ".") -> dict:
    matches = [str(p) for p in sorted(Path(root).rglob(pattern))]
    return {"ok": True, "matches": matches, "count": len(matches)}


def search_in_files(query: str, root: str = ".", file_pattern: str = "*") -> dict:
    hits = []
    for p in sorted(Path(root).rglob(file_pattern)):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if query in line:
                hits.append({"file": str(p), "line": lineno, "text": line.strip()})
    return {"ok": True, "hits": hits, "count": len(hits)}


def bash(command: str, cwd: Optional[str] = None, auto_approve: bool = False) -> dict:
    gate = confirm_bash(command, auto_approve=auto_approve)
    if not gate["allowed"]:
        return {"ok": False, "blocked": True, "reason": gate["reason"]}
    try:
        proc = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return {
            "ok": proc.returncode == 0,
            "blocked": False,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "blocked": False, "error": "command timed out after 30s"}
