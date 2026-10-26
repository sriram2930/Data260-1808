"""
Part-8/build_scenarios.py -- DATA-260 HW7, Part 4.IV (build the two scenario CSVs)

Builds two uploaded-CSV scenarios out of real public Divvy (Chicago) trip
data, downloaded from the official S3 bucket:
  https://s3.amazonaws.com/divvy-tripdata/202401-divvy-tripdata.zip (5.5 MB)
  https://s3.amazonaws.com/divvy-tripdata/202407-divvy-tripdata.zip (29.2 MB)
not synthesized. The downloaded zips/CSVs are gitignored (Part-8/
raw_downloads/, ~208MB combined) -- re-download from the URLs above to
regenerate; only the derived <=800-row scenario CSVs in Part-8/data/ are
committed. Both are real calendar months, picked for a genuine seasonal
contrast rather than hand-selected rows:

  scenario_pay_per_use: January 2024 (cold-weather month, short/sparse
    casual rides) -- first 800 rows of the real month, as downloaded.
  scenario_membership:  July 2024 (peak season, frequent/longer rides)
    -- first 800 rows of the real month, as downloaded.

"First N rows of the file as Divvy wrote it" rather than a random sample,
so the raw/ CSVs stay a traceable, unmodified prefix of the official
files (raw_downloads/*.csv, not committed -- too large) rather than a
hand-curated selection.

Run:
    python build_scenarios.py
"""

from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).parent
N_ROWS = 800

SCENARIOS = {
    "scenario_pay_per_use.csv": "raw_downloads/202401-divvy-tripdata.csv",
    "scenario_membership.csv": "raw_downloads/202407-divvy-tripdata.csv",
}


def main() -> None:
    out_dir = HERE / "data"
    out_dir.mkdir(exist_ok=True)

    for out_name, src_name in SCENARIOS.items():
        src_path = HERE / src_name
        out_path = out_dir / out_name
        with open(src_path, encoding="utf-8", newline="") as f_in:
            reader = csv.reader(f_in)
            header = next(reader)
            rows = []
            for row in reader:
                if len(rows) >= N_ROWS:
                    break
                rows.append(row)

        with open(out_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(header)
            writer.writerows(rows)

        print(f"{out_name}: {len(rows)} rows (source: {src_name})")


if __name__ == "__main__":
    main()
