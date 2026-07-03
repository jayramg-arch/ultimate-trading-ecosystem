"""
catalyst_sentinel.py — Catalyst blackout detector (reliability layer)
=====================================================================

The ecosystem's recurring silent failure: a catalyst family stops firing for
weeks and nobody notices (squeeze-in-POS bug: 0 POS picks for 24 months;
SWG-PB regression: dominant catalyst -> 0). This module makes that failure
LOUD within days instead of months.

How it works
------------
After every bull-screener run, call `record_and_check()` (wired into
run_bull_screener, guarded so a sentinel failure never breaks the screener):

1. Appends a per-family count snapshot to  logs/catalyst_counts_history.csv
2. Checks each family against its trailing history and reports:
     - BLACKOUT: family fired in >=30% of the trailing window but has now
       been zero for `blackout_runs` consecutive runs
     - REGIME-GATED: SWG-PB zero while regime is NOT BULL -> expected, no alarm
     - NEW-SILENCE: family has NEVER fired in the whole history (worth a look
       once history is deep enough)
3. Writes the verdict to  logs/catalyst_sentinel.log  and returns it as a
   string so callers (Streamlit / CLI) can surface it.

Standalone:  python catalyst_sentinel.py          -> check latest history
             python catalyst_sentinel.py --history -> dump the history table

No network. No dependencies beyond pandas. Append-only history (never deletes).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
HISTORY_CSV = os.path.join(LOG_DIR, "catalyst_counts_history.csv")
SENTINEL_LOG = os.path.join(LOG_DIR, "catalyst_sentinel.log")

FAMILIES = ["POS-BO", "POS-ACCUM", "SWG-BO", "SWG-GAP", "SWG-PB", "SWG-REV"]
# Families whose zero-count is EXPECTED when the market regime is not bull
# (SWG-PB is hard-gated on mkt_bull as of 2026-07-02).
REGIME_GATED = {"SWG-PB"}

# A family is in BLACKOUT when it fired in >= base_rate of the trailing window
# but has been zero for the last `blackout_runs` consecutive runs.
DEFAULTS = dict(window=20, base_rate=0.30, blackout_runs=5)


def record_and_check(df_results: pd.DataFrame, regime_bull: bool,
                     universe_size: int | None = None,
                     window: int = DEFAULTS["window"],
                     base_rate: float = DEFAULTS["base_rate"],
                     blackout_runs: int = DEFAULTS["blackout_runs"]) -> str:
    """Append a snapshot from a screener results frame, then run the check.

    Parameters
    ----------
    df_results : the bull screener output frame (needs a 'Catalyst' column).
    regime_bull : the run's mkt_bull flag (regime-gated families are excused
        from blackout alarms while it is False).
    universe_size : optional, number of symbols screened (context column).

    Returns the human-readable verdict (also appended to the sentinel log).
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    counts = {f: 0 for f in FAMILIES}
    if df_results is not None and len(df_results) and "Catalyst" in df_results.columns:
        vc = df_results["Catalyst"].fillna("None").replace("", "None").value_counts()
        for f in FAMILIES:
            counts[f] = int(vc.get(f, 0))

    row = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "regime": "BULL" if regime_bull else "NOT_BULL",
           "universe": universe_size if universe_size is not None else
                       (len(df_results) if df_results is not None else 0)}
    row.update(counts)

    hist = _load_history()
    hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    hist.to_csv(HISTORY_CSV, index=False)

    verdict = check(hist, window=window, base_rate=base_rate,
                    blackout_runs=blackout_runs)
    try:
        with open(SENTINEL_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"\n[{row['ts']}] regime={row['regime']} "
                     f"counts={counts}\n{verdict}\n")
    except OSError:
        pass
    return verdict


def check(hist: pd.DataFrame | None = None,
          window: int = DEFAULTS["window"],
          base_rate: float = DEFAULTS["base_rate"],
          blackout_runs: int = DEFAULTS["blackout_runs"]) -> str:
    """Evaluate the trailing history and return a verdict string."""
    if hist is None:
        hist = _load_history()
    if hist.empty:
        return "SENTINEL: no history yet — run the bull screener first."

    lines = []
    latest_regime = str(hist.iloc[-1].get("regime", "NOT_BULL"))
    n = len(hist)
    for f in FAMILIES:
        if f not in hist.columns:
            continue
        series = pd.to_numeric(hist[f], errors="coerce").fillna(0)
        trail = series.iloc[-window:]
        fired_rate = float((trail > 0).mean()) if len(trail) else 0.0
        recent = series.iloc[-blackout_runs:]
        zero_streak = int((recent == 0).all()) if len(recent) >= blackout_runs else 0

        if f in REGIME_GATED and latest_regime != "BULL" and series.iloc[-1] == 0:
            lines.append(f"  {f:<10} 0 — regime-gated (NOT BULL): expected, no alarm")
        elif zero_streak and fired_rate >= base_rate:
            lines.append(f"  {f:<10} ⛔ BLACKOUT — zero for {blackout_runs}+ runs "
                         f"but fired in {fired_rate:.0%} of trailing {len(trail)} runs. "
                         f"Investigate the gate chain (Bull_Screener_Funnel.log).")
        elif n >= window and (series > 0).sum() == 0:
            lines.append(f"  {f:<10} ⚠ NEVER fired in {n} recorded runs — verify the "
                         f"gate chain isn't structurally impossible.")
        else:
            lines.append(f"  {f:<10} {int(series.iloc[-1])} (fired {fired_rate:.0%} "
                         f"of trailing {len(trail)})")

    hdr = f"SENTINEL @{hist.iloc[-1]['ts']} — {n} runs on record, regime {latest_regime}"
    alarms = sum(1 for l in lines if "BLACKOUT" in l)
    tail = "  ✅ no blackouts" if alarms == 0 else f"  ⛔ {alarms} BLACKOUT alarm(s)"
    return "\n".join([hdr] + lines + [tail])


def _load_history() -> pd.DataFrame:
    if os.path.exists(HISTORY_CSV):
        try:
            return pd.read_csv(HISTORY_CSV)
        except Exception:
            # Never let a corrupt history kill the screener — start fresh but
            # preserve the corrupt file for inspection.
            try:
                os.replace(HISTORY_CSV, HISTORY_CSV + ".corrupt")
            except OSError:
                pass
    return pd.DataFrame(columns=["ts", "regime", "universe"] + FAMILIES)


if __name__ == "__main__":
    if "--history" in sys.argv:
        h = _load_history()
        print(h.to_string(index=False) if not h.empty else "no history yet")
    else:
        print(check())
