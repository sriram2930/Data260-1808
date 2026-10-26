"""
Part-8/run_scenarios.py -- DATA-260 HW7, Part 4.IV (two acceptance-case runs)

Runs the real framework-based agent (bikeshare_agent.run_bikeshare_agent)
on the two real CSVs built by build_scenarios.py, against the real,
already-snapshotted Divvy pricing page, for the two required acceptance
cases:

  pay_per_use: a rider's STATED monthly usage (3 short rides/month) --
    few/short rides, pay-per-use should win on the real Divvy per-ride
    rate ($1 unlock + $0.20/min).
  membership:  a rider's STATED monthly usage (40 longer rides/month) --
    frequent/longer rides, membership should win since the real per-ride
    unlock fee alone (40 x $1) already beats the prorated annual price.

The uploaded CSV (800 real rows each, see build_scenarios.py) is real
public trip data the agent can query via csv_sql for supporting duration
statistics (e.g. what fraction of real trips in this month ran long
enough to risk the included-minutes cap) -- the exact monthly ride count
driving the decision comes from the user's stated usage in the question,
documented as an explicit assumption since anonymized public trip data
has no single-rider identity column to filter "my own rides" by.

Writes reports/hw07/raw/bikeshare_<scenario>.json (full timeline + answer)
for each scenario.

Run (pricing page must already be reachable):
    python run_scenarios.py
"""

from __future__ import annotations

import json
from pathlib import Path

from bikeshare_agent import run_bikeshare_agent

HERE = Path(__file__).parent
PRICING_URL = "https://divvybikes.com/pricing"
OUT_DIR = HERE.parent / "reports" / "hw07" / "raw"

SCENARIOS = {
    "pay_per_use": {
        "csv": "data/scenario_pay_per_use.csv",
        "ride_count": 3,
        "avg_duration_min": 8,
        "question": (
            "I'm a Divvy rider in Chicago. My usage: 3 rides per month, 8 minutes each, "
            "classic bikes only. Should I buy the annual membership or pay per ride?"
        ),
    },
    "membership": {
        "csv": "data/scenario_membership.csv",
        "ride_count": 40,
        "avg_duration_min": 20,
        "question": (
            "I'm a Divvy rider in Chicago. My usage: 40 rides per month, 20 minutes each, "
            "classic bikes only. Should I buy the annual membership or pay per ride?"
        ),
    },
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, cfg in SCENARIOS.items():
        print(f"=== scenario: {label} ===")
        result = run_bikeshare_agent(
            cfg["question"], str(HERE / cfg["csv"]), PRICING_URL,
            ride_count=cfg["ride_count"], avg_duration_min=cfg["avg_duration_min"],
        )
        print(f"stop_reason={result['stop_reason']} tool_call_count={result.get('tool_call_count')} "
              f"total_time_ms={result['total_time_ms']}")
        print(f"final_answer:\n{result['final_answer']}\n")

        out_path = OUT_DIR / f"bikeshare_{label}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"wrote {out_path}\n")


if __name__ == "__main__":
    main()
