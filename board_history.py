"""board_history.py - a daily record of what the three GM boards found (6-Oct-2026, Jay).

WHY: on 5 Oct the boards showed 0 / 1 / 0 names at 5/5 and there was no way to say whether
that was the market or a gate gone wrong - nothing kept yesterday's count. This keeps one
row per board per day, so a quiet day can be read against the last few weeks:

    logs/board_counts_history.csv
    date, tf, built, rows, go5, go4, go3, blocked, clock, no_pa, no_loc, no_vol, weak_bar,
    regime_score, go5_names

  * go5 / go4 / go3 - rows at that gate count, on the right clock (⏱ rows excluded);
  * blocked         - ⛔ rows (fundamentals / first test);
  * clock           - rows on the wrong clock for their plan (⏱D / ⏱75/125);
  * no_pa ... weak_bar - the FIRST missing gate named on rows short of 5/5, on the right
    clock: the reason a board was quiet;
  * regime_score    - the composite market regime that evening (0-10).

The date is the board file's own build date (IST), and a re-run on the same day replaces that
day's rows, so running it twice never double-counts. Called by evening_digest (auto-pilot
Phase 14); `python board_history.py` records and prints the comparison by hand.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(HERE, "logs", "board_counts_history.csv")
TFS = ("Daily", "125m", "75m")
REASONS = (("no_pa", "no PA"), ("no_loc", "no loc"), ("no_vol", "no vol"), ("weak_bar", "weak bar"))


def _stats(tf: str) -> dict | None:
    p = os.path.join(HERE, "gm_board_cache_%s.csv" % tf)
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p)
    s = d["S4-GO"].astype(str)
    built = dt.datetime.fromtimestamp(os.path.getmtime(p))
    clock = s.str.startswith("⏱")
    right = s[~clock]
    row = {"date": built.date().isoformat(), "tf": tf, "built": built.strftime("%H:%M"), "rows": len(d)}
    for n in (5, 4, 3):
        row["go%d" % n] = int(right.str.startswith("%d/5" % n).sum())
    row["blocked"] = int(s.str.startswith("⛔").sum())
    row["clock"] = int(clock.sum())
    short = right[~right.str.startswith("5/5") & ~right.str.startswith("⛔")]
    for key, tag in REASONS:
        row[key] = int(short.str.contains(tag, regex=False).sum())
    try:
        import house_policy as hp
        row["regime_score"] = hp.regime().get("score")
    except Exception:
        row["regime_score"] = None
    row["go5_names"] = " ".join(d.loc[(~clock) & s.str.startswith("5/5"), "Symbol"].astype(str).tolist())
    return row


def record() -> pd.DataFrame:
    """Write today's rows (replacing any already there for the same date + board)."""
    new = [r for r in (_stats(tf) for tf in TFS) if r]
    if not new:
        return pd.DataFrame()
    nd = pd.DataFrame(new)
    if os.path.exists(HIST):
        old = pd.read_csv(HIST)
        keys = set(zip(nd["date"], nd["tf"]))
        old = old[[(a, b) not in keys for a, b in zip(old["date"], old["tf"])]]
        nd = pd.concat([old, nd], ignore_index=True)
    nd = nd.sort_values(["date", "tf"])
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    nd.to_csv(HIST, index=False)
    return nd


def compare(tf: str, hist: pd.DataFrame | None = None, days: int = 20) -> str:
    """'' until there is history; else ' · 20d median 5/5 x, 4/5 y (n days)'."""
    h = hist if hist is not None else (pd.read_csv(HIST) if os.path.exists(HIST) else pd.DataFrame())
    if h.empty:
        return ""
    h = h[h["tf"] == tf].sort_values("date")
    prev = h.iloc[:-1].tail(days)          # the days BEFORE the latest one
    if prev.empty:
        return " · history starts today"
    return " · %dd median 5/5 %g, 4/5 %g" % (len(prev), prev["go5"].median(), prev["go4"].median())


def main() -> int:
    h = record()
    if h.empty:
        print("no board caches found")
        return 1
    last = h.groupby("tf").tail(1)
    for _, r in last.iterrows():
        print("%-5s %s  5/5 %d · 4/5 %d · 3/5 %d · blocked %d · clock %d · short on: no PA %d, no loc %d, no vol %d, weak bar %d%s" % (
            r["tf"], r["date"], r["go5"], r["go4"], r["go3"], r["blocked"], r["clock"],
            r["no_pa"], r["no_loc"], r["no_vol"], r["weak_bar"], compare(r["tf"], h)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
