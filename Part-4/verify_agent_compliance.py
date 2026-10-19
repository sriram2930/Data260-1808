"""
Part-4/verify_agent_compliance.py -- DATA-260 HW6, Part 4.4

Asks the local model to generate one new function for this project, giving
it AGENT.md's actual content as the instructions to follow, then checks the
generated code against a few of those instructions automatically (does it
have a docstring, does it avoid importing ollama directly instead of going
through ModelClient, does it avoid opening a second database connection).
This is a smoke-level check, not a full static-analysis pass, but it's a
real generation against real instructions, not a canned example.

Run:
    python verify_agent_compliance.py
"""

from __future__ import annotations

import re

import file_memory

GENERATION_PROMPT = """Here are this project's AGENT.md instructions:

{agent_md}

Following these instructions, write ONE Python function (with a short
docstring) that takes a MongoDB database handle and returns the titles of
the 3 most recently created published announcements. Use the project's
existing conventions. Reply with ONLY the Python code, no explanation
outside it."""


def generate_function() -> str:
    agent_md = file_memory.load_agent_md()
    prompt = GENERATION_PROMPT.format(agent_md=agent_md)
    result = file_memory.get_model_client().complete([{"role": "user", "content": prompt}])
    return result["content"]


def check_compliance(code: str) -> list[tuple[str, bool, str]]:
    checks = []

    has_docstring = bool(re.search(r'"""[\s\S]+?"""', code) or re.search(r"'''[\s\S]+?'''", code))
    checks.append((
        "has a docstring (AGENT.md: 'short module-level docstring explaining what the file is for')",
        has_docstring,
        "found a triple-quoted string" if has_docstring else "no triple-quoted docstring found",
    ))

    imports_ollama_directly = bool(re.search(r"^\s*import ollama\b", code, re.MULTILINE))
    checks.append((
        "does not import ollama directly (AGENT.md: 'always called through ModelClient')",
        not imports_ollama_directly,
        "no direct 'import ollama'" if not imports_ollama_directly else "found 'import ollama' directly",
    ))

    opens_new_mongo_client = bool(re.search(r"MongoClient\s*\(", code))
    checks.append((
        "does not open a new MongoClient (AGENT.md: 'reuse existing adapters ... instead of opening new, parallel connections')",
        not opens_new_mongo_client,
        "no direct MongoClient(...) call" if not opens_new_mongo_client else "found a direct MongoClient(...) call",
    ))

    return checks


def main() -> None:
    code = generate_function()
    print("=== Generated function ===")
    print(code)
    print("\n=== AGENT.md compliance checks ===")
    all_pass = True
    for label, ok, detail in check_compliance(code):
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"[{status}] {label}\n       {detail}")
    print(f"\noverall: {'PASS' if all_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
