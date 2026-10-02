"""review_priority.py - which Reviewer Log entries count, and in what order (2-Oct-2026, Jay).

    tier 1  s4-alert   S4's own GO alert fired in the session          (top priority)
    tier 2  board      a 5/5 GO on an evening GM board (Phase 13)      (backfilled "board/cli" rows too)
    tier 3  manual     REVIEW.bat, and single-name command-line runs   (lowest)

THE UNIT IS THE TRIGGER BAR, not the day (Jay: "a stock at 10:30 might be the right trigger
and the same stock at 14:30 may not be the right fit"). A review reads the last CLOSED bar of
its timeframe at the moment it runs, so:
  * two reviews of the SAME closed bar are one setup seen twice - e.g. the 15:30 alert read
    at 15:35 and the evening board review read at 17:10 - and only the HIGHEST-priority one
    counts (earliest within a tier);
  * reviews of DIFFERENT bars are different setups and all count, even on the same day.
Results are reported per tier, tier 1 first, never pooled. Repeated triggers on one name are
correlated, so any interval must bootstrap by symbol, not by row. One helper so the scorers
cannot drift apart on the rule.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

TIER = {"s4-alert": 1, "board": 2, "board/cli": 2, "manual": 3, "cli": 3}
LABEL = {1: "tier 1 · S4 alert", 2: "tier 2 · board", 3: "tier 3 · manual"}
_OPEN = 9 * 60 + 15
_CLOSE = 15 * 60 + 30


def tier(source) -> int:
    s = str(source or "").strip().lower()
    return TIER.get(s, 2 if not s else 3)


def _prev_session(d: dt.date) -> dt.date:
    try:
        import nse_calendar as nc
        return nc.prev_trading_day(d)
    except Exception:
        d -= dt.timedelta(days=1)
        while d.weekday() >= 5:
            d -= dt.timedelta(days=1)
        return d


def trigger_bar(ts, tf) -> str:
    """The last CLOSED bar of `tf` at review time `ts`, as 'YYYY-MM-DD|k' (k = bar number in
    the session, 1-based) or 'YYYY-MM-DD|D' for daily. NSE 09:15-15:30 tiles exactly into
    5 x 75m and 3 x 125m bars."""
    t = pd.Timestamp(ts)
    d, m = t.date(), t.hour * 60 + t.minute
    s = str(tf).upper().replace("1D", "D")
    if s == "D":
        return "%s|D" % (d if m >= _CLOSE else _prev_session(d))
    try:
        n = int(s)
    except ValueError:
        return "%s|%s" % (d, s)
    nbars = (_CLOSE - _OPEN) // n
    k = (min(m, _CLOSE) - _OPEN) // n          # bars fully closed by m
    if k < 1:                                   # before the first close: last bar of yesterday
        return "%s|%d" % (_prev_session(d), nbars)
    return "%s|%d" % (d, min(k, nbars))


def pick(df: pd.DataFrame, ts_col: str = "ts", keys=("symbol", "tf")) -> pd.DataFrame:
    """One review per (symbol, tf, trigger bar): the highest-priority one, earliest within its
    tier. Adds `tier` and `trigger_bar` columns. Rows need `source` (missing reads as tier 2)."""
    d = df.copy()
    d["_ts"] = pd.to_datetime(d[ts_col], errors="coerce")
    d = d.dropna(subset=["_ts"])
    d["trigger_bar"] = [trigger_bar(t, f) for t, f in zip(d["_ts"], d["tf"])]
    d["tier"] = d["source"].map(tier) if "source" in d.columns else 2
    d = d.sort_values(["tier", "_ts"]).drop_duplicates(subset=list(keys) + ["trigger_bar"], keep="first")
    return d.sort_values("_ts").drop(columns="_ts")
