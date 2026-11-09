"""One-off script: turns the real captured raw/*.txt evidence into styled terminal-look HTML pages
(shots_html/*.html) so Playwright (shots.mjs) can screenshot them as PNGs for the report. The text in
each page is the exact captured output; the only addition is the command line shown first."""

import html
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE = (HERE / "shots_html" / "_template.html").read_text(encoding="utf-8")


def raw(name: str) -> str:
    return (HERE / "raw" / name).read_text(encoding="utf-8").rstrip()


def page(name: str, title: str, body: str) -> None:
    out = TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__BODY__", html.escape(body))
    (HERE / "shots_html" / f"{name}.html").write_text(out, encoding="utf-8")
    print("wrote", name)


page("p1_counter", "python Part-12/counter_demo.py -- Part 1", "$ python Part-12/counter_demo.py\n" + raw("counter_demo.txt"))
page("p1_infra", "docker ps / redis-cli / mysql -- Part 1", raw("p1_infra.txt"))
page("p2_index", "redis-cli FT.INFO -- Part 2 vector index", raw("p2_index.txt"))

p2 = raw("part2_run.txt").splitlines()
cut = next(i for i, ln in enumerate(p2) if "best_sim=0.191" in ln)
page("p2_run_a", "python Part-13/part2_demo.py -- queries 1-7", "$ python Part-13/part2_demo.py\n" + "\n".join(p2[:cut]).rstrip())
page("p2_run_b", "python Part-13/part2_demo.py -- queries 8-14 + summary", "\n".join(p2[cut:]))

page("p3_sweep", "python Part-13/part3_sweep.py -- Part 3.2 threshold sweep", "$ python Part-13/part3_sweep.py\n" + raw("part3_sweep_run.txt"))
page("p3_stale", "python Part-13/part3_stale_demo.py -- Part 3.5", "$ python Part-13/part3_stale_demo.py\n" + raw("part3_stale_run.txt"))
page("p4_training", "python Part-14/run_training.py -- Part 4 training", "$ python Part-14/run_training.py\n" + raw("part4_training_run.txt"))
page("p4_validation", "python Part-14/run_validation.py -- Part 4.3", "$ python Part-14/run_validation.py\n" + raw("part4_validation_run.txt"))
page("p4_variants", "python Part-14/run_variants.py -- Part 4.4 final test", "$ python Part-14/run_variants.py\n" + raw("part4_variants_run.txt"))
page("p4_demo_revision", "python Part-14/demo_revision.py -- Part 4.1", "$ python Part-14/demo_revision.py\n" + raw("part4_demo_revision.txt"))
page("p4_demo_lesson", "python Part-14/demo_lesson_reuse.py -- Part 4.2", "$ python Part-14/demo_lesson_reuse.py\n" + raw("part4_demo_lesson_reuse.txt"))
page("verify", "python verify_hw09.py", "$ python verify_hw09.py\n" + raw("verify_run.txt"))
