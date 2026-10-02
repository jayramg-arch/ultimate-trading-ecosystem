"""entry_shadow.py - Step D of the entry-optimizer work (2-Oct-2026, Jay).

A SHADOW RECORD of live GOs. Every row of logs/ai_review_log.csv is a GO S4 fired (by
alert or by hand) with S4's own plan levels recorded on it (entry, stop, T1, T2 - since
22-Sep). For each one this asks, on the real 75m/125m (or daily) bars that followed:
where would each entry method have filled, and how did it do in R against S4's stop?

    V_close    market at the GO bar's close (what an instant fill gets)
    V_retest   buy-limit at the GO bar's close, first fill within 8 bars (live S4 default)
    V_buystop  buy-stop above the GO bar's high, within 5 bars (confirmation by breakout)
    V_plan     S4's planned entry (limit if below the close, stop if above), within 8 bars
    V_ema20    buy-limit at the daily EMA20 (value), within the 10-session horizon

STOP shadow (added 2-Oct-2026, Jay): the same V_plan fill, scored against two stops so
the STOP is the only thing that differs - each in R of its own risk:
    S_plan     S4's planned stop (the panel's ladder)
    S_4atrD    the lower of S4's stop and entry - 4 x ATR(14, DAILY) as of the GO bar -
               the positional floor commander_core.POS_STOP_FLOOR_ATR_D now applies.
On 166 Log triggers (11 Sep - 1 Oct) the S4 stops sat at a median 1.36 x ATR(D) and
stopped out 80%; this records, on triggers that arrive AFTER the change, whether the
floor keeps earning its place. Reported per plan type (the floor is positional only).

Scored at 5 and 10 sessions after the GO: R = (price - entry) / (entry - S4 stop), the
stop checked bar by bar after the fill (a gap through it fills at the open), plus the
worst (MAE) and best (MFE) excursion in R and whether it filled at all. Same stop for
every method, so the only thing that differs is the ENTRY. A row is 'pending' until its
10 sessions have passed; each run rescans the whole log, so it is deterministic.

This is evidence the backtest cannot give - real alerts, real bars, real order flow -
but it is small and short-horizon: it measures the ENTRY, not the whole trade. Nothing
here touches orders or the live system.

    python entry_shadow.py            score everything, write logs/entry_shadow.csv, print summary
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
OUT = os.path.join(HERE, "logs", "entry_shadow.csv")
HORIZONS = (5, 10)                 # sessions after the GO
WIN = {"V_retest": 8, "V_buystop": 5, "V_plan": 8}
ENTRY_VARIANTS = ("V_close", "V_retest", "V_buystop", "V_plan", "V_ema20")
STOP_VARIANTS = ("S_plan", "S_4atrD")
VARIANTS = ENTRY_VARIANTS + STOP_VARIANTS
STOP_FLOOR_ATR_D = 4.0             # mirrors commander_core.POS_STOP_FLOOR_ATR_D
STOP_FLOOR_SINCE = "2026-10-03"    # first session the floor applies; rows from here are the test

_cache: dict = {}


def _bars(sym: str, tf: str, start: dt.date) -> pd.DataFrame:
    """Bars on the review's timeframe from `start`, index = bar OPEN time (naive IST)."""
    key = (sym, tf, start)
    if key in _cache:
        return _cache[key]
    df = pd.DataFrame()
    try:
        if tf in ("75", "125"):
            import dhan_ohlcv as dh
            import pa_patterns as pap
            raw = dh.fetch_intraday(sym, from_date=(start - dt.timedelta(days=3)).isoformat(),
                                    to_date=dt.date.today().isoformat(), interval=25)
            if raw is not None and not raw.empty:
                df = pap.resample_intraday(raw, int(tf))
        else:
            import data_provider as dp
            df = dp.fetch_ohlcv(sym, period="6mo", interval="1d", use_cache=True)
    except Exception as e:
        print("  bars failed %s %s: %s" % (sym, tf, e), file=sys.stderr)
    if df is not None and not df.empty:
        df = df.copy()
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)
        df = df[["Open", "High", "Low", "Close"]].dropna()
    _cache[key] = df
    return df


def _daily_ema20(sym: str, on: dt.date):
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        d = d[d.index.date <= on]
        return float(d["Close"].ewm(span=20, adjust=False).mean().iloc[-1]) if len(d) > 25 else None
    except Exception:
        return None


def _daily_atr(sym: str, cut: dt.date):
    """ATR(14, Wilder) on DAILY bars up to and including `cut` (no look-ahead)."""
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
        d = d[d.index.date <= cut]
        if len(d) < 20:
            return None
        h, l, c = d["High"], d["Low"], d["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        return float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    except Exception:
        return None


def _plan_type(md_path) -> str:
    """POSITIONAL / SWING from the review's Plan row; '' when unknown."""
    try:
        p = str(md_path or "")
        p = p if os.path.isabs(p) else os.path.join(HERE, p.replace("\\", os.sep))
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("Plan |"):
                return "positional" if "POSITIONAL" in line else "swing" if "SWING" in line else ""
    except OSError:
        pass
    return ""


def _go_pos(df: pd.DataFrame, tf: str, ts: dt.datetime):
    """Index of the last bar that had CLOSED by the review time."""
    if tf in ("75", "125"):
        closes = df.index + pd.Timedelta(minutes=int(tf))
        ok = np.where(closes <= pd.Timestamp(ts))[0]
    else:
        cut = ts.date() if (ts.hour, ts.minute) >= (15, 30) else ts.date() - dt.timedelta(days=1)
        ok = np.where(df.index.date <= cut)[0]
    return int(ok[-1]) if len(ok) else None


def _fill(df, start, end, level, kind):
    """First fill of a limit (kind='limit': low <= level) or stop (high >= level) on bars
    [start, end). Returns (pos, price) or (None, None). Gaps fill at the open."""
    for j in range(start, min(end, len(df))):
        o, h, l = float(df["Open"].iloc[j]), float(df["High"].iloc[j]), float(df["Low"].iloc[j])
        if kind == "limit" and l <= level:
            return j, min(o, level)
        if kind == "stop" and h >= level:
            return j, max(o, level)
    return None, None


def _score(df, fill_pos, entry, stop, hz_end: dict):
    """Walk bars after the fill; stop first. R at each horizon end, MAE/MFE over 10."""
    risk = entry - stop
    if risk <= 0:
        return None
    out = {}
    stopped_at = None
    mae = mfe = 0.0
    last_end = max(hz_end.values())
    for j in range(fill_pos + 1, min(last_end + 1, len(df))):
        o, h, l, c = (float(df[k].iloc[j]) for k in ("Open", "High", "Low", "Close"))
        if stopped_at is None:
            mfe = max(mfe, (h - entry) / risk)
            if l <= stop:
                stopped_at = j
                ex = min(o, stop)
                mae = min(mae, (ex - entry) / risk)
                for k, e in hz_end.items():
                    if j <= e and k not in out:
                        out[k] = (ex - entry) / risk
            else:
                mae = min(mae, (l - entry) / risk)
        for k, e in hz_end.items():
            if j == e and k not in out:
                out[k] = (c - entry) / risk
    if any(k not in out for k in hz_end):
        return None
    out.update({"mae": mae, "mfe": mfe, "stopped": stopped_at is not None})
    return out


def score_row(r) -> list[dict]:
    sym, tf = str(r["symbol"]), str(r["tf"]).replace("1D", "D")
    ts = dt.datetime.strptime(str(r["ts"])[:16], "%Y-%m-%d %H:%M")
    entry_plan, stop = float(r["entry"]), float(r["stop"])
    base = {"ts": r["ts"], "symbol": sym, "tf": tf, "ruling": str(r.get("ai_ruling", ""))[:40],
            "s4_entry": entry_plan, "s4_stop": stop, "plan_type": _plan_type(r.get("file"))}
    df = _bars(sym, tf, ts.date())
    if df is None or df.empty:
        return [dict(base, variant=v, status="no bars") for v in VARIANTS]
    g = _go_pos(df, tf, ts)
    if g is None:
        return [dict(base, variant=v, status="no GO bar") for v in VARIANTS]
    go_c, go_h = float(df["Close"].iloc[g]), float(df["High"].iloc[g])
    dates = sorted(set(df.index.date[g + 1:]))
    if len(dates) < min(HORIZONS):
        return [dict(base, variant=v, status="pending", go_close=go_c) for v in VARIANTS]
    hz_end = {}
    for hz in HORIZONS:                         # each horizon scored once it has elapsed
        if len(dates) >= hz:
            hz_end["R%d" % hz] = int(np.where(df.index.date == dates[hz - 1])[0][-1])
    end10 = int(np.where(df.index.date == dates[min(len(dates), max(HORIZONS)) - 1])[0][-1])
    ema = _daily_ema20(sym, ts.date())
    plans = {
        "V_close": (g, go_c),
        "V_retest": _fill(df, g + 1, g + 1 + WIN["V_retest"], go_c, "limit"),
        "V_buystop": _fill(df, g + 1, g + 1 + WIN["V_buystop"], go_h, "stop"),
        "V_plan": _fill(df, g + 1, g + 1 + WIN["V_plan"], entry_plan, "limit" if entry_plan <= go_c else "stop"),
        "V_ema20": (_fill(df, g + 1, end10, ema, "limit") if (ema and ema < go_c) else (None, None)),
    }
    plans["S_plan"] = plans["S_4atrD"] = plans["V_plan"]
    cut = ts.date() if (ts.hour, ts.minute) >= (15, 30) else ts.date() - dt.timedelta(days=1)
    atr_d = _daily_atr(sym, cut)
    rows = []
    for v in VARIANTS:
        pos, px = plans[v]
        row = dict(base, variant=v, go_close=go_c, go_high=go_h)
        v_stop = stop
        if v == "S_4atrD":
            if not atr_d or pos is None:
                row["status"] = "no daily ATR" if pos is not None else "no fill"
                rows.append(row)
                continue
            v_stop = min(stop, px - STOP_FLOOR_ATR_D * atr_d)
            row["atr_d"] = round(atr_d, 2)
            row["stop_used"] = round(v_stop, 2)
        if pos is not None and v in STOP_VARIANTS and atr_d:
            row["s4_stop_atrD"] = round((px - stop) / atr_d, 2)
        if pos is None:
            row["status"] = "no fill"
            rows.append(row)
            continue
        if px <= v_stop:
            row["status"] = "entry at/below stop"
            rows.append(row)
            continue
        s = _score(df, pos, px, v_stop, hz_end)
        if s is None:
            row["status"] = "pending"
        else:
            row.update({"status": "scored", "entry_px": round(px, 2), "bars_to_fill": pos - g,
                        "MAE_R": round(s["mae"], 3), "MFE_R": round(s["mfe"], 3), "stopped": s["stopped"]})
            for k in ("R5", "R10"):
                if k in s:
                    row[k] = round(s[k], 3)
        rows.append(row)
    return rows


def summary(df: pd.DataFrame) -> str:
    L = []
    for k in ("R5", "R10", "MAE_R", "stopped", "variant"):
        if k not in df.columns:
            df[k] = np.nan
    gos = df.drop_duplicates(["ts", "symbol", "tf"])
    sc = df[df["status"] == "scored"]
    L.append("ENTRY SHADOW - %d GOs logged, %d with >= 5 sessions elapsed, %d with 10" % (
        len(gos), sc.drop_duplicates(["ts", "symbol", "tf"]).shape[0],
        sc[sc["R10"].notna()].drop_duplicates(["ts", "symbol", "tf"]).shape[0]))
    L.append("%-10s %5s %6s %7s %7s %7s %7s %6s" % ("variant", "fills", "fill%", "R5", "R10", "medR10", "MAE", "stop%"))
    n_ready = df[df["status"] != "pending"].drop_duplicates(["ts", "symbol", "tf"]).shape[0] or 1
    for v in VARIANTS:
        s = sc[sc["variant"] == v]
        if s.empty:
            L.append("%-10s %5d" % (v, 0))
            continue
        L.append("%-10s %5d %5.0f%% %+7.3f %+7.3f %+7.3f %+7.3f %5.0f%%" % (
            v, len(s), 100 * len(s) / n_ready, s["R5"].mean(), s["R10"].mean(), s["R10"].median(),
            s["MAE_R"].mean(), 100 * s["stopped"].astype(bool).mean()))
    # paired: each method vs market-at-close on the same GOs
    hk = "R10" if sc["R10"].notna().sum() >= 10 else "R5"
    base = sc[sc["variant"] == "V_close"].set_index(["ts", "symbol", "tf"])[hk]
    L.append("\npaired vs V_close on the same GOs (%s difference):" % hk)
    for v in ENTRY_VARIANTS[1:]:
        s = sc[sc["variant"] == v].set_index(["ts", "symbol", "tf"])[hk]
        j = pd.concat([s, base], axis=1, keys=["v", "c"]).dropna()
        if len(j):
            L.append("  %-10s n=%3d  mean %+.3fR  median %+.3fR" % (v, len(j), (j["v"] - j["c"]).mean(), (j["v"] - j["c"]).median()))
    # STOP pair: same fill, two stops, each in R of its own risk; split by plan type.
    if "plan_type" in sc.columns:
        L.append("\nSTOP pair on the same V_plan fill (%s; each in its own R). 'all' includes the"
                 "\n  rows the floor was proposed FROM; only 'after' rows test it:" % hk)
        _after = pd.to_datetime(sc["ts"], errors="coerce") >= pd.Timestamp(STOP_FLOOR_SINCE)
        for (pt, win) in [(p, w) for w in ("all", "after") for p in ("positional", "swing", "")]:
            g = sc[(sc["plan_type"].fillna("") == pt) & (_after if win == "after" else True)]
            pt = "%s/%s" % (pt or "unknown", win)
            a = g[g["variant"] == "S_plan"].set_index(["ts", "symbol", "tf"])
            b = g[g["variant"] == "S_4atrD"].set_index(["ts", "symbol", "tf"])
            j = pd.concat([a[hk], b[hk], a["stopped"], b["stopped"]], axis=1,
                          keys=["p", "f", "ps", "fs"]).dropna(subset=["p", "f"])
            if len(j):
                L.append("  %-17s n=%3d  S4 stop %+.3fR (stopped %3.0f%%)  4xATR(D) %+.3fR (stopped %3.0f%%)"
                         "  diff mean %+.3fR median %+.3fR" % (
                             pt, len(j), j["p"].mean(), 100 * j["ps"].astype(bool).mean(),
                             j["f"].mean(), 100 * j["fs"].astype(bool).mean(),
                             (j["f"] - j["p"]).mean(), (j["f"] - j["p"]).median()))
    L.append("\nSmall sample, short horizon: this grades the ENTRY, not the whole trade.")
    return "\n".join(L)


def main() -> int:
    log = pd.read_csv(LOG)
    log = log[pd.to_numeric(log["entry"], errors="coerce").notna() & pd.to_numeric(log["stop"], errors="coerce").notna()]
    log = log[log["tf"].astype(str).isin(["75", "125", "1D", "D"])]
    # PRIORITY (2-Oct-2026, Jay): one review per symbol+TF+day - S4 alert > board > manual.
    import review_priority as _rpr
    log = _rpr.pick(log)
    rows = []
    for _, r in log.iterrows():
        try:
            rr = score_row(r)
        except Exception as e:
            rr = [{"ts": r["ts"], "symbol": r["symbol"], "tf": r["tf"], "status": "err: %s" % str(e)[:60]}]
        for x in rr:
            x["tier"] = int(r["tier"]); x["source"] = r.get("source", "")
        rows.extend(rr)
    out = pd.DataFrame(rows)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT, out.to_csv(index=False))
    except Exception:
        out.to_csv(OUT, index=False)
    # Per priority tier, tier 1 first, never pooled.
    for t in sorted(int(x) for x in out["tier"].dropna().unique()):
        print("=== %s ===" % _rpr.LABEL.get(t, t))
        print(summary(out[out["tier"] == t].copy()))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
