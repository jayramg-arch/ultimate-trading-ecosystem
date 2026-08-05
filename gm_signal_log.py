"""gm_signal_log — the FORWARD record of what GM+S4 actually signalled.

WHY THIS EXISTS (Jay, 5-Aug-2026): "you jump to conclusions very fast and retract from
them later on... I'm not very confident on your backtesting framework."

Both complaints have the same root. Every claim about this system so far has come from a
SIMULATION of what it would have done — reconstructed from history, with the assumptions
of whoever wrote the harness baked in. That is why the numbers kept moving: a
reconstruction can be re-specified, and each re-specification produced a new headline.

A forward log cannot be re-specified. The row is written the moment the signal fires,
before the outcome is knowable, and it is never edited afterwards. In eight weeks it is
Jay's own track record rather than my model of it — and the journal cannot be used for
this, because it mixes system trades with hand-picked ones and (per the loss-harvesting
correction) that mix cannot be separated retroactively.

WHAT IS LOGGED: every board row, not only the 4/4 GOs. Logging the near-misses is what
lets the later read answer the question that actually matters — does the GO gate
DISCRIMINATE? A 4/4 that runs and a 2/4 that also runs would say the gate adds nothing.
That comparison is impossible if only the GOs are kept, and it costs nothing to keep both.

DEDUP: one row per (date, tf, symbol, gate-bucket). A name that sits at 2/4 all day
writes once; when it reaches 4/4 that transition writes a second row. So the file records
STATE CHANGES, not rebuild frequency — the board can rebuild every 75 minutes without
inflating the sample.

NOT AN OUTCOME LOG YET. `fill_outcomes()` walks forward from each signal date and records
what happened. It is deliberately a SEPARATE pass: writing the signal and scoring it must
never happen in the same code path, or the scoring assumptions leak into the record.

Read-only guarantee: append and outcome-fill are the only writers, and neither ever
rewrites a signal field. If a row is wrong, it stays wrong and visible.
"""
from __future__ import annotations

import csv
import logging
import os
from datetime import date, datetime

_log = logging.getLogger("gm_signal_log")

_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_ROOT, "logs")
LOG_PATH = os.path.join(LOG_DIR, "gm_signal_log.csv")

# Signal fields are written once and never touched again. Outcome fields start blank and
# are filled by fill_outcomes(). The split is physical, not just conventional.
SIGNAL_COLS = [
    "signal_date", "signal_time", "tf", "symbol", "path", "playbook",
    "archetypes", "s4go", "gate_bucket", "category", "sigma_pa",
    "cmp", "entry", "sl", "t1", "rr", "stale",
]
# R-MULTIPLES ARE THE PRIMARY OUTCOME (5-Aug-2026, caught on the first 57 rows).
# hit_first resolves against the row's own T1 — and 13 of the first 57 rows carried a T1
# more than 25% away, because a positional plan targets 5R/10R structure rather than a
# first target. Those rows can only ever record SL or open: a wide-T1 name is
# structurally incapable of logging a win while a tight-T1 name is not. That is a BIAS
# (it sorts with playbook — breakouts run wider), not noise, and it would have quietly
# decided the comparison this log exists to settle.
# R is stop-relative, so it is comparable across every name whatever its target:
#   R = (price - entry) / (entry - sl)
# reached_2r is the setup-neutral stand-in for "hit its target". hit_first is KEPT, as a
# record of what the plan-as-written did — it is just no longer the metric.
# See the standing rule: stop and sizing results are read in R, never in per-trade %.
OUTCOME_COLS = [
    "outcome_asof", "bars_held", "hit_first", "mfe_pct", "mae_pct",
    "mfe_r", "mae_r", "reached_2r", "ret_20d_r",
    "ret_5d_pct", "ret_10d_pct", "ret_20d_pct",
]
COLS = SIGNAL_COLS + OUTCOME_COLS


def gate_bucket(s4go: str) -> str:
    """The leading n/4 — the state we dedup on. A name drifting between '2/4 · no vol'
    and '2/4 · no loc' within a session is the same state for our purposes; a name going
    2/4 -> 4/4 is not."""
    s = str(s4go or "").strip()
    return s.split(" ")[0] if s else "?"


def _read_keys() -> set:
    """Existing (date, tf, symbol, bucket) keys, so a rebuild cannot duplicate a row."""
    if not os.path.exists(LOG_PATH):
        return set()
    keys = set()
    try:
        with open(LOG_PATH, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                keys.add((r.get("signal_date", ""), r.get("tf", ""),
                          r.get("symbol", ""), r.get("gate_bucket", "")))
    except Exception as e:
        # A damaged log must not block today's logging — degrade to "no keys known",
        # which risks a duplicate row. A duplicate is recoverable; a silent gap is not.
        _log.warning(f"gm_signal_log: key read failed, dedup disabled this run: {e}")
    return keys


def _playbook(path: str, archetypes, s4go: str) -> str:
    """Which playbook graded this row — the thing the two surfaces used to disagree on.
    Recorded explicitly so a later read can compare pullback and breakout signals
    separately. Pooling them is what produced three wrong conclusions already."""
    if str(path).lower() == "recovery":
        return "recovery"
    if "·PB" in str(s4go) or "· PB" in str(s4go):
        return "pullback"
    try:
        from gm_trigger_board import PULLBACK_ARCHETYPES, BREAKOUT_ARCHETYPES
        a = set(archetypes or [])
        if (a & PULLBACK_ARCHETYPES) and not (a & BREAKOUT_ARCHETYPES):
            return "pullback"
        if a & BREAKOUT_ARCHETYPES:
            return "breakout"
    except Exception as e:
        _log.warning(f"gm_signal_log: playbook resolution degraded: {e}")
    return "breakout"


def _num(v):
    try:
        if v is None or v == "":
            return ""
        f = float(v)
        return "" if f != f else round(f, 2)      # NaN -> blank, never 0
    except Exception:
        return ""


def append_board(df, tf: str, today=None) -> int:
    """Append one row per NEW (date, tf, symbol, bucket) from a built board frame.

    Called at the end of every board build. Fully guarded by the caller: a logging
    failure must never break a rebuild, because a board that will not build is a much
    worse problem than a missing log row.

    Returns the number of rows written.
    """
    if df is None or not len(df):
        return 0
    os.makedirs(LOG_DIR, exist_ok=True)
    d0 = (today or date.today()).isoformat()
    now = datetime.now().strftime("%H:%M")
    seen = _read_keys()
    new = []
    for _, r in df.iterrows():
        try:
            sym = str(r.get("Symbol") or "").strip().upper()
            if not sym:
                continue
            s4go = str(r.get("S4-GO") or "")
            # "n/a" = no read attempted or no data. Logging it would record our own
            # plumbing, not a market signal.
            if not s4go or s4go.startswith("n/a"):
                continue
            bucket = gate_bucket(s4go)
            key = (d0, str(tf), sym, bucket)
            if key in seen:
                continue
            seen.add(key)
            arche = [a.strip() for a in str(r.get("Archetype") or "").split(",") if a.strip()]
            path = "recovery" if "Recovery" in str(r.get("Path") or "") else "bull"
            new.append({
                "signal_date": d0, "signal_time": now, "tf": str(tf), "symbol": sym,
                "path": path, "playbook": _playbook(path, arche, s4go),
                "archetypes": "|".join(arche), "s4go": s4go, "gate_bucket": bucket,
                "category": str(r.get("Category") or ""),
                "sigma_pa": _num(r.get("ΣPA") if "ΣPA" in r else r.get("Sigma_PA")),
                "cmp": _num(r.get("CMP")), "entry": _num(r.get("Entry")),
                "sl": _num(r.get("SL")), "t1": _num(r.get("T1")),
                "rr": _num(r.get("R:R")), "stale": str(r.get("Stale") or ""),
            })
        except Exception as e:
            _log.warning(f"gm_signal_log: row skipped: {e}")
    if not new:
        return 0
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        if not exists:
            w.writeheader()
        for row in new:
            w.writerow({**{c: "" for c in COLS}, **row})
    return len(new)


def load():
    """The log as a DataFrame (pandas imported lazily — the board path must stay light)."""
    import pandas as pd
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(LOG_PATH)


def summary() -> dict:
    """Counts only. Deliberately NOT a performance verdict — with a handful of rows and
    no filled outcomes there is nothing to conclude, and stating a number here is exactly
    the premature-conclusion habit this file exists to break."""
    try:
        df = load()
    except Exception as e:
        return {"error": str(e)}
    if not len(df):
        return {"rows": 0, "symbols": 0, "days": 0, "filled": 0}
    go = df[df["gate_bucket"].astype(str).str.startswith("4/4")]
    return {
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "days": int(df["signal_date"].nunique()),
        "go_rows": int(len(go)),
        "go_pullback": int((go["playbook"] == "pullback").sum()) if len(go) else 0,
        "go_breakout": int((go["playbook"] == "breakout").sum()) if len(go) else 0,
        "go_recovery": int((go["playbook"] == "recovery").sum()) if len(go) else 0,
        "filled": int(df["outcome_asof"].notna().sum()),
        "first": str(df["signal_date"].min()),
        "last": str(df["signal_date"].max()),
    }


def fill_outcomes(min_bars: int = 5, today=None) -> int:
    """Walk each unfilled signal forward and record what happened.

    Separate pass, on purpose (see the module docstring). Uses the SAME data provider the
    board reads, and the entry/SL the row carried — not a re-derived one, or the scoring
    would measure a plan the signal never made.

    hit_first: 'SL' / 'T1' / 'open' — resolved bar by bar so an SL and a T1 in the same
    session cannot both be claimed. When one bar spans both, SL is recorded: assuming the
    favourable order is how a backtest flatters itself.
    """
    import pandas as pd
    import data_provider as dp

    if not os.path.exists(LOG_PATH):
        return 0
    df = pd.read_csv(LOG_PATH)
    if not len(df):
        return 0
    d_today = today or date.today()
    todo = df[df["outcome_asof"].isna() | (df["outcome_asof"].astype(str) == "")]
    filled = 0
    for idx, r in todo.iterrows():
        try:
            sd = pd.to_datetime(r["signal_date"]).date()
            if (d_today - sd).days < min_bars:
                continue                       # too soon — leave it blank, never estimate
            px = dp.fetch_ohlcv(str(r["symbol"]), period="1y", interval="1d",
                                use_cache=True, auto_adjust=True)
            if px is None or not len(px):
                continue
            fwd = px[px.index.date > sd]
            if not len(fwd):
                continue
            base = float(r["cmp"]) if str(r.get("cmp") or "") else float(fwd["Open"].iloc[0])
            sl = float(r["sl"]) if str(r.get("sl") or "") else None
            t1 = float(r["t1"]) if str(r.get("t1") or "") else None
            # One R = the distance to the row's own stop. Guarded: a stop at or above
            # entry is a broken plan, and dividing by it would manufacture enormous R
            # values on exactly the rows whose levels are least trustworthy.
            risk = (base - sl) if (sl and sl < base) else None
            hit, bars = "open", 0
            mfe, mae = 0.0, 0.0
            for i, (_, b) in enumerate(fwd.iterrows(), start=1):
                bars = i
                mfe = max(mfe, (float(b["High"]) - base) / base * 100.0)
                mae = min(mae, (float(b["Low"]) - base) / base * 100.0)
                if sl and float(b["Low"]) <= sl:
                    hit = "SL"
                    break
                if t1 and float(b["High"]) >= t1:
                    hit = "T1"
                    break

            def _ret(n):
                if len(fwd) < n:
                    return ""
                return round((float(fwd["Close"].iloc[n - 1]) - base) / base * 100.0, 2)

            df.loc[idx, "outcome_asof"] = d_today.isoformat()
            df.loc[idx, "bars_held"] = bars
            df.loc[idx, "hit_first"] = hit
            df.loc[idx, "mfe_pct"] = round(mfe, 2)
            df.loc[idx, "mae_pct"] = round(mae, 2)
            # R-multiples: mfe/mae are % of entry, so scale by entry/risk to convert.
            if risk:
                _r20 = _ret(20)
                df.loc[idx, "mfe_r"] = round(mfe / 100.0 * base / risk, 2)
                df.loc[idx, "mae_r"] = round(mae / 100.0 * base / risk, 2)
                df.loc[idx, "reached_2r"] = int((mfe / 100.0 * base / risk) >= 2.0)
                df.loc[idx, "ret_20d_r"] = ("" if _r20 == ""
                                            else round(_r20 / 100.0 * base / risk, 2))
            df.loc[idx, "ret_5d_pct"] = _ret(5)
            df.loc[idx, "ret_10d_pct"] = _ret(10)
            df.loc[idx, "ret_20d_pct"] = _ret(20)
            filled += 1
        except Exception as e:
            _log.warning(f"gm_signal_log: outcome fill failed for {r.get('symbol')}: {e}")
    if filled:
        df.to_csv(LOG_PATH, index=False)
    return filled


def main():
    import argparse
    ap = argparse.ArgumentParser(description="GM+S4 forward signal log")
    ap.add_argument("--fill", action="store_true", help="fill outcomes for matured signals")
    ap.add_argument("--min-bars", type=int, default=5)
    a = ap.parse_args()
    if a.fill:
        print(f"outcomes filled: {fill_outcomes(min_bars=a.min_bars)}")
    s = summary()
    print("\n".join(f"{k:14s} {v}" for k, v in s.items()))


if __name__ == "__main__":
    main()
