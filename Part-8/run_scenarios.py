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
        "question": (
            "I'm a Divvy rider in Chicago deciding between an annual membership and paying "
            "per ride. My typical usage: about 3 rides per month, each around 8 minutes, "
            "always on classic bikes. Use csv_sql on the uploaded trip data to check real "
            "classic-bike trip duration patterns this month (for example, what share of "
            "real trips run under 45 minutes, since that's the usual included-minutes "
            "threshold), use policy_retriever on the pricing page to get the exact single-ride "
            "and annual membership prices, and use calculator to compute my monthly "
            "pay-per-use cost vs. the prorated monthly cost of the annual membership. Give me "
            "a decision (Buy Monthly Membership or Pay Per Ride/Minute), a 3-6 sentence "
            "justification citing the pricing passages, a cost breakdown (total pay-per-use "
            "cost, membership cost plus any residual charges, break-even rides vs my actual "
            "usage), a small table by week (ride count, average duration, spend), and any "
            "assumptions or caveats."
        ),
    },
    "membership": {
        "csv": "data/scenario_membership.csv",
        "question": (
            "I'm a Divvy rider in Chicago deciding between an annual membership and paying "
            "per ride. My typical usage: about 40 rides per month (commuting + errands), "
            "each around 20 minutes, mostly on classic bikes. Use csv_sql on the uploaded "
            "trip data to check real classic-bike trip duration patterns this month (for "
            "example, what share of real trips run under 45 minutes), use policy_retriever "
            "on the pricing page to get the exact single-ride and annual membership prices, "
            "and use calculator to compute my monthly pay-per-use cost vs. the prorated "
            "monthly cost of the annual membership. Give me a decision (Buy Monthly "
            "Membership or Pay Per Ride/Minute), a 3-6 sentence justification citing the "
            "pricing passages, a cost breakdown (total pay-per-use cost, membership cost "
            "plus any residual charges, break-even rides vs my actual usage), a small table "
            "by week (ride count, average duration, spend), and any assumptions or caveats."
        ),
    },
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, cfg in SCENARIOS.items():
        print(f"=== scenario: {label} ===")
        result = run_bikeshare_agent(cfg["question"], str(HERE / cfg["csv"]), PRICING_URL)
        print(f"stop_reason={result['stop_reason']} tool_call_count={result.get('tool_call_count')} "
              f"total_time_ms={result['total_time_ms']}")
        print(f"final_answer:\n{result['final_answer']}\n")

        out_path = OUT_DIR / f"bikeshare_{label}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"wrote {out_path}\n")


if __name__ == "__main__":
    main()
