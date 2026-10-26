"""
Part-7/hw07_tasks.py -- DATA-260 HW7, Part 2.I/III fixed verification tasks

The same three fixed task prompts are reused by run_verification_tasks.py
(Part 2.I, run once each) and run_reliability_test.py (Part 2.III, run
repeatedly for the 20-attempt measurement) and reflexion.py /
run_reflexion_compare.py (Part 3), so all three parts are measuring the
exact same cases.
"""

from __future__ import annotations

TASK_A = (
    "Search the course catalogue for courses about 'data', then look up the "
    "full detail of the first search result and summarize it."
)

TASK_B = (
    "What are the aggregate stats (course count and average seats available) "
    "for the Data Science & AI department (department_id=2)? Then search the "
    "catalogue for one example course in that department and name it."
)

TASK_C = (
    "Compare the courses with codes 'CS-00005' and 'DATA-00006': search for "
    "each one, then get the full detail for both, and summarize the key "
    "differences between them (department, seats available, description)."
)

ERROR_RECOVERY_TASK = (
    "Get the full details for course_id 999999 and tell me what you find."
)

VERIFICATION_TASKS = {"A": TASK_A, "B": TASK_B, "C": TASK_C}
