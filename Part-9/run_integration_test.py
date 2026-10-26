"""
Part-9/run_integration_test.py -- DATA-260 HW7, Part 6.II (glob -> search -> read)

Creates three small Python files in a fresh temporary course sandbox
directory (one of which contains the string DEBUG), then follows the
single instruction "find the file containing DEBUG and show its contents"
by chaining glob_files -> search_in_files -> read_file -- the same sequence
a model-driven agent would take, done here directly to prove the tool
chain itself works end to end.

Run:
    python run_integration_test.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from file_tools import glob_files, read_file, search_in_files

FILES = {
    "settings.py": 'APP_NAME = "campus_catalogue"\nPORT = 8008\n',
    "utils.py": 'def add(a, b):\n    return a + b\n',
    "server.py": 'DEBUG = True\n\ndef run():\n    print("server running, DEBUG =", DEBUG)\n',
}


def main() -> None:
    sandbox = Path(tempfile.mkdtemp(prefix="s1808_hw7_sandbox_"))
    print(f"sandbox: {sandbox}\n")
    try:
        for name, content in FILES.items():
            (sandbox / name).write_text(content, encoding="utf-8")
            print(f"created {name}")

        print("\nInstruction: find the file containing DEBUG and show its contents.\n")

        print("step 1: glob_files('*.py', root=sandbox)")
        glob_result = glob_files("*.py", root=str(sandbox))
        print(f"  -> {glob_result['count']} files: {[Path(m).name for m in glob_result['matches']]}")

        print("\nstep 2: search_in_files('DEBUG', root=sandbox, file_pattern='*.py')")
        search_result = search_in_files("DEBUG", root=str(sandbox), file_pattern="*.py")
        print(f"  -> {search_result['count']} hits:")
        for hit in search_result["hits"]:
            print(f"     {Path(hit['file']).name}:{hit['line']}: {hit['text']}")

        target_file = search_result["hits"][0]["file"]
        print(f"\nstep 3: read_file({Path(target_file).name!r})")
        read_result = read_file(target_file)
        print("  -> contents:")
        for line in read_result["content"].splitlines():
            print(f"     {line}")

        assert search_result["count"] >= 1, "expected at least one DEBUG hit"
        assert Path(target_file).name == "server.py", "expected server.py to be the DEBUG file"
        print("\nPASS: glob -> search -> read chain found server.py via DEBUG and read its contents.")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        print(f"\ncleaned up sandbox: {sandbox}")


if __name__ == "__main__":
    main()
