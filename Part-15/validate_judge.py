"""
Part-15/validate_judge.py -- DATA-260 HW10, Parts 3.2 and 3.3 (validate the judge)

Pre-conditions enforced here (the script refuses to run otherwise):
  * human_labels.csv has a hand-assigned 1-5 label for every one of the 20 cases in eval_cases.json;
  * eval_cases.json and human_labels.csv are COMMITTED and unmodified (git), i.e. frozen before any judge score exists.

Then: run the helpfulness judge (Part-15/judge.py, qwen3:8b, fixed settings) on the same 20 drafts THREE times
  3.2  Spearman rank correlation and mean absolute difference, human vs judge (run 1 is the scored run);
  3.3  repeatability across the 3 runs: how often scores change, and by how much.
Progress is saved after every judge call (reports/hw10/raw/judge_runs.json) so an interrupted run resumes.
Outputs: reports/hw10/raw/judge_scores.csv (raw per-case data), judge_validation.json, judge_runs.json.
Student: Sreeramachandrasai Achutuni (SID4 1808).
"""

from __future__ import annotations

import csv
import itertools
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from judge import JUDGE_SETTINGS, judge  # noqa: E402
from tracing import RAW_DIR  # noqa: E402

CASES, LABELS = HERE / "eval_cases.json", HERE / "human_labels.csv"
RUNS_PATH = RAW_DIR / "judge_runs.json"
N_RUNS = 3


def require_frozen() -> None:
    for p in (CASES, LABELS):
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO, capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=REPO, capture_output=True, text=True).stdout.strip()
        if tracked.returncode != 0 or dirty:
            raise SystemExit(f"REFUSING to run: {rel} must be committed and unmodified before any judge score is produced.")


def load_labels() -> dict[str, int]:
    with LABELS.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    labels = {}
    for r in rows:
        v = (r["human_label"] or "").strip()
        if not v.isdigit() or not 1 <= int(v) <= 5:
            raise SystemExit(f"REFUSING to run: {r['case_id']} has no valid 1-5 human label ({v!r}).")
        labels[r["case_id"]] = int(v)
    return labels


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    labels = load_labels()
    assert set(labels) == {c["case_id"] for c in cases} and len(cases) == 20, "labels must match the 20 cases"
    require_frozen()

    runs = json.loads(RUNS_PATH.read_text(encoding="utf-8")) if RUNS_PATH.exists() else {}
    print(f"=== Part 3 judge validation | student Sreeramachandrasai Achutuni | {JUDGE_SETTINGS['model']} | {N_RUNS} runs x {len(cases)} drafts", flush=True)
    for run in range(1, N_RUNS + 1):
        store = runs.setdefault(str(run), {})
        for c in cases:
            if c["case_id"] in store and store[c["case_id"]]["score"] is not None:
                continue
            r = judge("helpfulness", c["question"], c["draft"], c["facts"])
            store[c["case_id"]] = {"score": r["score"], "reason": r["reason"], "error": r["error"], "latency_ms": r["latency_ms"]}
            RUNS_PATH.write_text(json.dumps(runs, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"run{run} {c['case_id']} human={labels[c['case_id']]} judge={r['score']} ({r['latency_ms'] / 1000:.0f}s) {r['error'] or ''}", flush=True)

    ids = [c["case_id"] for c in cases]
    human = np.array([labels[i] for i in ids], dtype=float)
    mat = np.array([[runs[str(r)][i]["score"] for i in ids] for r in range(1, N_RUNS + 1)], dtype=float)  # runs x cases
    j1 = mat[0]
    rho, p = spearmanr(human, j1)
    rho = None if np.isnan(rho) else float(rho)
    mad = float(np.mean(np.abs(human - j1)))
    pairs = list(itertools.combinations(range(N_RUNS), 2))
    diffs = np.array([np.abs(mat[a] - mat[b]) for a, b in pairs])  # pairs x cases
    case_changed = int((mat.max(axis=0) != mat.min(axis=0)).sum())
    rep = {
        "n_runs": N_RUNS, "cases_changed": case_changed, "pct_cases_changed": round(100 * case_changed / len(ids), 1),
        "pair_comparisons": int(diffs.size), "pairs_with_change": int((diffs > 0).sum()),
        "pct_pairs_changed": round(100 * float((diffs > 0).mean()), 1),
        "mean_abs_change": round(float(diffs.mean()), 3), "max_abs_change": int(diffs.max()),
        "mean_abs_change_when_changed": round(float(diffs[diffs > 0].mean()), 3) if (diffs > 0).any() else 0.0,
    }
    # per-run agreement with the human labels (does the conclusion depend on which run is used?)
    per_run = []
    for r in range(N_RUNS):
        rr, _ = spearmanr(human, mat[r])
        per_run.append({"run": r + 1, "spearman": None if np.isnan(rr) else round(float(rr), 3),
                        "mean_abs_diff": round(float(np.mean(np.abs(human - mat[r]))), 3)})
    bias = float(np.mean(mat[0] - human))
    exact = int((mat[0] == human).sum())
    within1 = int((np.abs(mat[0] - human) <= 1).sum())

    per_case = [{"case_id": i, "question": next(c["question"] for c in cases if c["case_id"] == i), "human": int(labels[i]),
                 "judge_run1": int(mat[0][k]), "judge_run2": int(mat[1][k]), "judge_run3": int(mat[2][k]),
                 "abs_diff_run1": int(abs(human[k] - mat[0][k])), "range_across_runs": int(mat[:, k].max() - mat[:, k].min())}
                for k, i in enumerate(ids)]

    trust_rho = rho is not None and rho >= 0.8
    trust_mad = mad <= 0.5
    trust_rep = rep["max_abs_change"] == 0
    verdict_bits = [f"rho={rho if rho is None else round(rho, 3)} (bar >= 0.80: {'met' if trust_rho else 'NOT met'})",
                    f"MAD={mad:.2f} (bar <= 0.50: {'met' if trust_mad else 'NOT met'})",
                    f"repeatability max change {rep['max_abs_change']} (bar 0: {'met' if trust_rep else 'NOT met'})"]
    verdict = ("Would NOT use this judge alone to gate a deployment yet. " if not (trust_rho and trust_mad and trust_rep)
               else "Would use it only as one signal, not the sole gate, until the extra evidence below exists. ") + \
        "Bars: " + "; ".join(verdict_bits) + \
        ". Evidence still required: a larger labeled set (>= 100 cases, several labelers with inter-annotator agreement), " \
        "cases with known-bad drafts to measure false passes, a second judge model or prompt to test sensitivity, and a score-vs-outcome " \
        "check on real failures; with n=20 the Spearman confidence interval is wide."
    out = {"n_cases": len(ids), "judge_settings": JUDGE_SETTINGS, "spearman_rho": rho, "spearman_p": None if np.isnan(p) else float(p),
           "mean_abs_diff": round(mad, 3), "mean_signed_diff_judge_minus_human": round(bias, 3), "exact_agreement": exact, "within_one": within1,
           "per_run_agreement": per_run, "repeatability": rep, "per_case": per_case, "verdict": verdict}
    (RAW_DIR / "judge_validation.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    with (RAW_DIR / "judge_scores.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "human", "judge_run1", "judge_run2", "judge_run3", "abs_diff_run1", "range_across_runs"])
        for r in per_case:
            w.writerow([r["case_id"], r["human"], r["judge_run1"], r["judge_run2"], r["judge_run3"], r["abs_diff_run1"], r["range_across_runs"]])
    print(json.dumps({k: out[k] for k in ("spearman_rho", "spearman_p", "mean_abs_diff", "mean_signed_diff_judge_minus_human", "exact_agreement", "within_one", "repeatability", "per_run_agreement")}, indent=2))
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
