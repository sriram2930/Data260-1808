"""
Part-1/run_memory_experiments.py -- DATA-260 HW6, Part 3 (what memory costs)

Runs the same fixed 30-message conversation in fresh sessions at
SHORT_TERM_N = 4, 12, 30, then once more at N=12 with the eviction/
compression policy (message truncation) turned on. After each 30-message
run, asks the five memory_probes.yaml questions in the same session and
scores each reply with the heuristic documented there. Logs every turn's
token/latency metrics, and writes a summary table (mean prompt tokens/turn,
mean latency, mean probe-quality score) per setting.

Calls memory.chat_turn() directly (not over HTTP) so SHORT_TERM_N and the
compression flag can be set per run without restarting the server.

Run (backend's MongoDB connection must be reachable; the FastAPI server
itself does not need to be running since this calls the functions directly):
    python run_memory_experiments.py
"""

from __future__ import annotations

import csv
import json
import time
import uuid
from pathlib import Path

import yaml

import sys

from db_mongo import get_db
import memory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Part-7"))
from retry_policy import call_with_retry  # noqa: E402


def _chat_turn_resilient(user_id, session_id, msg, short_term_n, compress_short_term):
    """Saves the user message once (not retried, so a retry can't double-
    save it), then wraps the rest of the turn -- the part that actually
    calls the model, which is where this sweep hit two real Ollama hangs
    on this machine (CPU froze completely; a fresh request from a
    different process still got served, but the in-flight request from
    this script never returned) -- in HW5's retry policy. A timeout +
    bounded retry here means a future hang gets one retry automatically
    instead of killing a multi-hour run. (Not fully idempotent: if a retry
    does fire, maybe_summarize/extract_episodes could in principle run
    twice for that one turn; accepted as a rare, bounded trade-off rather
    than building full checkpointing for an issue hit twice in ~2 hours.)"""
    session_id = session_id or memory.new_session_id()
    memory.save_message(user_id, session_id, "user", msg)
    return call_with_retry(
        lambda: memory._run_turn_after_save(user_id, session_id, msg, short_term_n, compress_short_term),
        max_retries=2,
        base_delay_s=3.0,
        timeout_s=240.0,
    )[0]

HERE = Path(__file__).parent
REPORT_DIR = HERE.parent / "reports" / "hw06"
RAW_DIR = REPORT_DIR / "raw"

# 30 fixed user messages. Facts are planted at indices 0, 1, 2 (name,
# student id, favorite subject) and 15 (birthplace), matching
# memory_probes.yaml's planted_in_message. The rest are plausible campus
# course-catalogue small talk/questions, long enough to be a realistic
# 30-turn conversation without being probe-relevant themselves.
CONVERSATION = [
    "Hi, my name is Priya.",
    "My student ID is 012345678.",
    "My favorite subject is Machine Learning.",
    "What departments does this campus course catalogue cover?",
    "Can you list a few Computer Science courses?",
    "What about Business Analytics courses?",
    "How does course enrollment work here?",
    "Is there a waitlist system for popular courses?",
    "What is the difference between a course and a section?",
    "Can one course have multiple sections?",
    "Who do I contact about adding a course late?",
    "Are there prerequisites for most graduate courses?",
    "What is the usual course load per semester?",
    "Do you track seats available per course?",
    "Can seats available ever go to zero?",
    "I was born in Chennai, India.",
    "Do international students have different enrollment rules?",
    "What departments exist besides Computer Science and Data Science?",
    "Is Business Analytics its own department?",
    "What does the Engineering department offer?",
    "Are course codes unique across departments?",
    "What format do course codes usually follow?",
    "Can a course belong to more than one department?",
    "How do you decide which department owns a new course?",
    "What happens if two departments want the same course code?",
    "Do announcements get sent out for new courses?",
    "What categories of announcements exist?",
    "Can announcements be scheduled for a future date?",
    "Can announcements be archived instead of deleted?",
    "Thanks, that covers most of what I wanted to know today.",
]

PROBES_PATH = REPORT_DIR / "memory_probes.yaml"


def load_probes() -> list[dict]:
    with open(PROBES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["questions"]


def score_reply(reply: str, expected_keywords: list[str]) -> int:
    """Automated heuristic scoring (documented in memory_probes.yaml): 5 if
    any expected keyword appears (case-insensitive), 1 if the reply
    explicitly disclaims knowing, otherwise 3 (vague/partial)."""
    low = reply.lower()
    if any(kw.lower() in low for kw in expected_keywords):
        return 5
    if any(p in low for p in ["i don't know", "i do not know", "not sure", "no information", "not mentioned"]):
        return 1
    return 3


def run_one_setting(label: str, short_term_n: int, compress_short_term: bool) -> dict:
    user_id = f"exp_{label}_{uuid.uuid4().hex[:8]}"
    session_id = None
    rows = []

    print(f"\n=== Setting: {label} (SHORT_TERM_N={short_term_n}, compress={compress_short_term}) ===")
    print(f"user_id={user_id}")

    for i, msg in enumerate(CONVERSATION, start=1):
        result = _chat_turn_resilient(user_id, session_id, msg, short_term_n, compress_short_term)
        session_id = result["session_id"]
        row = {"setting": label, "turn": i, "kind": "conversation", **result["metrics"]}
        rows.append(row)
        print(f"  turn {i:2d}: prompt={row['prompt_tokens']:4d} completion={row['completion_tokens']:3d} "
              f"latency_ms={row['latency_ms']:8.1f}")

    probes = load_probes()
    probe_scores = []
    for q in probes:
        result = _chat_turn_resilient(user_id, session_id, q["question"], short_term_n, compress_short_term)
        session_id = result["session_id"]
        score = score_reply(result["reply"], q["expected_keywords"])
        probe_scores.append(score)
        rows.append({
            "setting": label, "turn": q["id"], "kind": "probe",
            "question": q["question"], "reply": result["reply"], "score": score,
            **result["metrics"],
        })
        print(f"  probe {q['id']}: score={score}  reply={result['reply'][:80]!r}")

    conv_rows = [r for r in rows if r["kind"] == "conversation"]
    mean_prompt_tokens = sum(r["prompt_tokens"] for r in conv_rows) / len(conv_rows)
    mean_latency = sum(r["latency_ms"] for r in conv_rows) / len(conv_rows)
    mean_probe_score = sum(probe_scores) / len(probe_scores)

    summary = {
        "setting": label,
        "short_term_n": short_term_n,
        "compress_short_term": compress_short_term,
        "mean_prompt_tokens_per_turn": round(mean_prompt_tokens, 1),
        "mean_latency_ms": round(mean_latency, 1),
        "mean_probe_quality": round(mean_probe_score, 2),
        "probe_scores": probe_scores,
        "user_id": user_id,
    }
    return {"rows": rows, "summary": summary}


def _save_incremental(all_rows: list[dict], summaries: list[dict]) -> None:
    """Writes the raw/summary files after EVERY setting, not just at the
    end -- a crash partway through (this experiment hit a real Ollama hang
    requiring a restart) no longer loses already-completed settings."""
    if all_rows:
        fieldnames = sorted({k for r in all_rows for k in r.keys()})
        with open(RAW_DIR / "memory_experiment_turns.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        with open(RAW_DIR / "memory_experiment_turns.json", "w", encoding="utf-8") as f:
            json.dump(all_rows, f, indent=2)
    with open(RAW_DIR / "memory_experiment_summary.json", "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)


def main() -> None:
    import sys

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== run_memory_experiments.py started {time.strftime('%Y-%m-%dT%H:%M:%S')} ===")

    all_rows = []
    summaries = []

    # Setting 1 (SHORT_TERM_N=4) already completed in an earlier run that
    # crashed on an Ollama restart before it could write output; its data
    # was recovered from RUN_LOG.txt into raw/setting1_recovered.json and
    # is merged back in here rather than rerun.
    recovered_path = RAW_DIR / "setting1_recovered.json"
    if recovered_path.exists() and "--skip-recovered" not in sys.argv:
        with open(recovered_path, encoding="utf-8") as f:
            recovered = json.load(f)
        for t in recovered.pop("turns"):
            all_rows.append({"setting": recovered["setting"], "turn": t["turn"], "kind": "conversation",
                              "prompt_tokens": t["prompt"], "completion_tokens": t["completion"],
                              "latency_ms": t["latency_ms"]})
        summaries.append(recovered)
        print(f"Recovered setting from log: {recovered['setting']}")

    settings_to_run = [("SHORT_TERM_N=12", 12), ("SHORT_TERM_N=30", 30)]
    for label, n in settings_to_run:
        out = run_one_setting(label, n, compress_short_term=False)
        all_rows.extend(out["rows"])
        summaries.append(out["summary"])
        _save_incremental(all_rows, summaries)

    out = run_one_setting("eviction_compression_policy", 12, compress_short_term=True)
    all_rows.extend(out["rows"])
    summaries.append(out["summary"])
    _save_incremental(all_rows, summaries)

    print("\n=== Summary ===")
    print(f"{'Setting':<28}{'Mean prompt tok/turn':<22}{'Mean latency (ms)':<20}{'Probe quality':<15}")
    for s in summaries:
        print(f"{s['setting']:<28}{s['mean_prompt_tokens_per_turn']:<22}{s['mean_latency_ms']:<20}{s['mean_probe_quality']:<15}")

    print(f"\n=== finished {time.strftime('%Y-%m-%dT%H:%M:%S')} ===")


if __name__ == "__main__":
    main()
