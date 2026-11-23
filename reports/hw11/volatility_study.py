"""Threshold-justification study (HW11 Part 2): one year of daily closes per watchlist ticker from Yahoo's public
chart endpoint (used only for this offline study; the monitor itself uses Stooq/EDGAR). Prints and saves how often each
ticker moves by at least X% in a day, so the per-ticker thresholds in policy.md rest on measured data."""
import json
import urllib.request
from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "raw" / "volatility.json"
TICKERS = ["KO", "AAPL", "NVDA", "PLTR"]
LEVELS = [2, 3, 4, 5, 7, 10]


def closes(t):
    req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=1y&interval=1d",
                                 headers={"User-Agent": "student-homework-script/1.0"})
    r = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    c = [x for x in r["indicators"]["quote"][0]["close"] if x is not None]
    return np.array(c)


res = {}
for t in TICKERS:
    c = closes(t)
    ret = np.abs(np.diff(c) / c[:-1] * 100)
    res[t] = {"days": int(len(ret)), "std_pct": round(float(np.std(np.diff(c) / c[:-1] * 100)), 2),
              "p95_abs_pct": round(float(np.percentile(ret, 95)), 2), "max_abs_pct": round(float(ret.max()), 2),
              "days_ge": {str(x): int((ret >= x).sum()) for x in LEVELS}}
    print(t, res[t])
OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
