"""Part-4/run_consolidation_test.py -- DATA-260 HW6, Part 4.5 test runner.

Runs consolidate_memory_md() on a fresh copy of test_memory_before.md (the
deliberately messy 56-line fixture with 3+ duplicates and 3+ contradictions)
and writes a structured JSON result plus the final file for the report.

Run:
    python run_consolidation_test.py
"""
import json
import shutil

import file_memory as fm

shutil.copy(fm.HERE / "test_memory_before.md", fm.HERE / "test_memory_after.md")
result = fm.consolidate_memory_md(fm.HERE / "test_memory_after.md")

out = {
    "before_count": result["before_count"],
    "after_count": result["after_count"],
    "duplicate_groups": result["duplicate_groups"],
    "contradictions": result["contradictions"],
    "rejected_duplicate_candidates": result["rejected_duplicate_candidates"],
    "contradiction_resolutions": result["contradiction_resolutions"],
    "unresolved_flags": result["unresolved_flags"],
}
with open(fm.HERE / "consolidation_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print(json.dumps(out, indent=2))
print("\nwrote consolidation_result.json and test_memory_after.md")
