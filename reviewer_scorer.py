"""reviewer_scorer — does the AI reviewer's TAKE beat its PASS/WAIT? Scored from forward prices.

Jay, 25-Sep-2026: "you have all the Reviewer logs with those take-it trades. They can be
used as the filtered trades." No manual s4_take needed to grade the REVIEWER: every review
row already carries a ruling and (from the review file) the levels, so forward prices can
say what each ruling would have earned. s4_take stays for the other question - whether
JAY's own call beats the reviewer's - which needs his decision and cannot be inferred.

Per review (first review per symbol+TF+day, so one setup re-alerted three times counts once):
  ruling  TAKE / WAIT / PASS / NO   (from ai_review_log.csv, else the review file)
  levels  TAKE -> the reviewer's own PLAN levels (it may have moved them);
          WAIT/PASS/NO -> S4's panel plan: the COUNTERFACTUAL "what if you had taken S4's GO"
  fill    a bar AFTER the review trades at or through the entry within FILL_BARS
  exit    first of stop / T1 on 25-minute Dhan bars; a bar touching both counts the STOP
          (conservative, the replay.py convention); a gap through the stop fills at the open
  R       in R-multiples, never % (a % metric rewards wide stops). Still-open trades are
          marked to the last close and reported SEPARATELY - never mixed into closed R.

Honest limits, printed with the result: small n (reviews began 11-Sep), T1-only exit (no
partials or trail), 25-minute granularity, and outcomes still open. It describes, it does
not validate - no rule changes on this until the closed sample is large.

    python reviewer_scorer.py            print the scorecard, write reports/reviewer_scorecard.csv
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
OUT = os.path.join(HERE, "reports", "reviewer_scorecard.csv")
FILL_BARS = 30          # 25m bars ~ 2 sessions: an entry not traded by then did not fill
RULE_RX = re.compile(r"RULING:\W*(TAKE|WAIT|PASS|NO)\b", re.I)


def _read(path: str) -> str:
    p = path if os.path.isabs(path) else os.path.join(HERE, path.replace("\\", os.sep))
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def _ruling(row, md: str) -> str | None:
    for src in (str(row.get("ai_ruling") or ""), md):
        m = RULE_RX.search(src)
        if m:
            return m.group(1).upper()
    return None


def _levels(row, md: str, ruling: str) -> dict:
    import s4_review as sr
    lv = {}
    if ruling == "TAKE":
        lv = sr._model_levels(md)
    if not all(k in lv for k in ("entry", "stop", "t1")):
        csv = {k: row.get(k) for k in ("entry", "stop", "t1", "t2")}
        if all(pd.notna(csv[k]) for k in ("entry", "stop", "t1")):
            lv = {k: float(v) for k, v in csv.items() if pd.notna(v)}
    if not all(k in lv for k in ("entry", "stop", "t1")):
        try:
            d = sr.deriv_fields(md)
            lv = {k: d[k] for k in ("entry", "stop", "t1", "t2") if d.get(k) not in (None, "")}
        except Exception:
            pass
    out = {}
    for k, v in lv.items():            # deriv_fields returns text; the CSV may too
        try:
            out[k] = float(str(v).replace(",", ""))
        except ValueError:
            pass
    return out


def _canon(sym: str) -> str:
    try:
        from dhan_ohlcv import canonical_nse_symbol
        return canonical_nse_symbol(sym) or sym
    except Exception:
        return sym


_BARS: dict = {}


def _bars(sym: str, since: str) -> pd.DataFrame:
    if sym not in _BARS:
        from dhan_ohlcv import fetch_intraday
        try:
            df = fetch_intraday(sym, from_date=since, to_date=dt.date.today().isoformat(), interval=25)
        except Exception:
            df = pd.DataFrame()
        if df is not None and not df.empty:
            df = df.rename(columns=str.lower)
            if not isinstance(df.index, pd.DatetimeIndex):
                tcol = next((c for c in ("timestamp", "datetime", "date", "time") if c in df.columns), None)
                df = df.set_index(pd.to_datetime(df[tcol])) if tcol else df
            if df.index.tz is not None:
                df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
        _BARS[sym] = df if df is not None else pd.DataFrame()
    return _BARS[sym]


def simulate(bars: pd.DataFrame, ts: pd.Timestamp, e: float, s: float, t1: float) -> dict:
    """Fill at the entry, then first of stop / T1. Bars are labelled by their OPEN."""
    risk = e - s
    if risk <= 0 or t1 <= e:
        return {"status": "BAD_LEVELS"}
    fwd = bars[bars.index >= ts]
    if fwd.empty:
        return {"status": "NO_DATA"}
    fill_at = None
    for i, (t, b) in enumerate(fwd.iterrows()):
        if i >= FILL_BARS:
            break
        if b["low"] <= e:
            fill_at = t
            break
    if fill_at is None:
        return {"status": "NO_FILL"}
    after = fwd[fwd.index >= fill_at]
    for t, b in after.iterrows():
        if b["low"] <= s:                       # stop first when both touch
            px = min(b["open"], s) if t != fill_at else s
            return {"status": "STOP", "R": (px - e) / risk, "exit_ts": t}
        if b["high"] >= t1:
            return {"status": "T1", "R": (t1 - e) / risk, "exit_ts": t}
    last = after["close"].iloc[-1]
    return {"status": "OPEN", "R": (last - e) / risk, "exit_ts": after.index[-1]}


def run() -> pd.DataFrame:
    log = pd.read_csv(LOG)
    log["ts"] = pd.to_datetime(log["ts"], errors="coerce")
    log = log.dropna(subset=["ts"]).sort_values("ts")
    log["day"] = log["ts"].dt.date
    log = log.drop_duplicates(subset=["symbol", "tf", "day"], keep="first")
    rows = []
    for _, r in log.iterrows():
        md = _read(str(r.get("file") or ""))
        ru = _ruling(r, md)
        if not ru:
            continue
        lv = _levels(r, md, ru)
        rec = {"ts": r["ts"], "symbol": r["symbol"], "tf": r["tf"], "ruling": ru,
               "entry": lv.get("entry"), "stop": lv.get("stop"), "t1": lv.get("t1")}
        if not all(rec[k] is not None for k in ("entry", "stop", "t1")):
            rec["status"] = "NO_LEVELS"
        else:
            sym = _canon(str(r["symbol"]))
            bars = _bars(sym, (log["ts"].min() - pd.Timedelta(days=1)).date().isoformat())
            rec.update(simulate(bars, r["ts"], rec["entry"], rec["stop"], rec["t1"]) if not bars.empty
                       else {"status": "NO_DATA"})
        rows.append(rec)
    return pd.DataFrame(rows)


def report(df: pd.DataFrame) -> None:
    print(f"reviews scored: {len(df)} (first review per symbol+TF+day) · "
          f"{df['ts'].min():%d %b} -> {df['ts'].max():%d %b}")
    print(df["status"].value_counts().to_string(), "\n")
    print(f"{'ruling':6} {'n':>4} {'filled':>6} {'closed':>6} {'T1%':>6} {'closedR':>8} {'medR':>6} "
          f"{'open':>5} {'openR(mtm)':>10}")
    for ru in ("TAKE", "WAIT", "PASS", "NO"):
        g = df[df["ruling"] == ru]
        if g.empty:
            continue
        filled = g[g["status"].isin(["STOP", "T1", "OPEN"])]
        closed = g[g["status"].isin(["STOP", "T1"])]
        op = g[g["status"] == "OPEN"]
        t1p = 100 * (closed["status"] == "T1").mean() if len(closed) else np.nan
        print(f"{ru:6} {len(g):4d} {len(filled):6d} {len(closed):6d} {t1p:6.0f} "
              f"{closed['R'].mean() if len(closed) else np.nan:8.2f} "
              f"{closed['R'].median() if len(closed) else np.nan:6.2f} "
              f"{len(op):5d} {op['R'].mean() if len(op) else np.nan:10.2f}")
    print("\nTAKE uses the reviewer's own levels; WAIT/PASS/NO use S4's plan (what taking the GO would"
          "\nhave done). Exit = first of stop/T1 on 25m bars, stop first on a shared bar. Small n,"
          "\nno partials, open trades kept out of closed R. Describes; does not validate.")


if __name__ == "__main__":
    d = run()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    d.to_csv(OUT, index=False)
    report(d)
    print(f"\nwritten {OUT}")
