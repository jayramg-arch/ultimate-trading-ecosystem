"""intraday_replay.py - Step A of the entry-optimizer work (2-Oct-2026, Jay).

The GO gate fires on 75m/125m charts, yet every backtest of it so far ran on DAILY bars.
This replays the board's GO on the trigger timeframe itself, point-in-time:

  GO on a CLOSED 75m/125m bar j  =  PA     pa_patterns.detect_bull_patterns(intraday=True)
                                           with the DAILY EMA20/EMA10 as references (as the
                                           board and S4 do), any bull pattern fired on bar j
                                 AND LOC    price at a DAILY-or-higher PATTERN demand zone
                                           (zone_engine.zone_support D/W/M, built only from
                                           sessions completed BEFORE bar j's day; pivots off,
                                           trigger-TF zones excluded - today's settings)
                                 AND VOL    RV = bar volume / mean of the prior 50 bars >= 1.0,
                                           or >= 0.5 in pullback context (contraction pattern,
                                           no expansion pattern, in a demand zone; a SWG-PB
                                           catalyst counts as a known pullback) - S4/board rule
                                 AND BAR    green, or closed in the upper half of its range

Entries compared on the SAME qualified names (the cached 23-Jul catalyst set, as in step B):
  E0_close   from step B: buy at the anchor-day close, daily structural stop (the naive entry)
  I_close    market at the GO bar's close
  I_retest   buy-limit at the GO bar's close, first fill within 8 bars (live S4 default)
  I_buystop  buy-stop above the GO bar's high, within 5 bars
Stop for the I_ variants: the tightest structure below the entry - the daily zone's distal
or the 10-bar trigger-TF swing low - no farther than 3 x daily ATR14 (the daily replay's cap,
on the daily ATR as S4 caps). Exits: the rest of the entry day is checked bar by bar for the
stop; from the next session the standard daily simulator runs (2R/3R, 33/33 partials, 4.5x
trail, catalyst horizon, costs). Benchmark over each trade's actual hold. Scored in R.

    python intraday_replay.py              both TFs, all anchors (cached 25m bars after first run)
    python intraday_replay.py --tf 75      one TF
    python intraday_replay.py --limit 20   quick check on the first 20 names

Outputs validation_runs/intraday_replay/<variant>_<tf>.csv and report.txt. Read-only;
nothing here changes the live system. Run it once; a failed hypothesis is recorded.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
QCACHE = os.path.join(RUNS, "_ab_qual_cache")
ICACHE = os.path.join(RUNS, "_intraday_cache")
OUT = os.path.join(RUNS, "intraday_replay")
CATALYST_RUN = "20260723_063652"
ENTRY_WINDOW_DAYS = 40          # trading days to find a GO (the daily replay's window)
RETEST_BARS, BUYSTOP_BARS = 8, 5
RV_FLOOR, PB_RV_FLOOR = 1.0, 0.5

import data_provider as _dp          # noqa: E402
import dhan_ohlcv as _dh              # noqa: E402
import pa_patterns as _pap            # noqa: E402
import replay as _rp                  # noqa: E402
import zone_engine as _ze             # noqa: E402
from gm_trigger_board import PB_CONTRACTION, PB_EXPANSION   # noqa: E402
import entry_rebaseline as _eb        # noqa: E402

_ze.set_use_structural(False)          # pattern zones only (production since 25-Sep)


# ── data ─────────────────────────────────────────────────────────────────────
def _daily(sym: str) -> pd.DataFrame:
    df = _dp.fetch_ohlcv(sym, period="5y", interval="1d", use_cache=True)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def _base25(sym: str, anchor: str) -> pd.DataFrame:
    """25-min bars from ~25 calendar days before the anchor to ~85 after (one Dhan
    request, <=90-day window per call -> two calls), cached on disk."""
    os.makedirs(ICACHE, exist_ok=True)
    fp = os.path.join(ICACHE, "%s_%s.pkl" % (sym.replace("&", "_"), anchor))
    if os.path.exists(fp):
        return pickle.load(open(fp, "rb"))
    a = dt.date.fromisoformat(anchor)
    parts = []
    for f, t in ((a - dt.timedelta(days=25), a + dt.timedelta(days=30)),
                 (a + dt.timedelta(days=31), a + dt.timedelta(days=85))):
        try:
            p = _dh.fetch_intraday(sym, from_date=f.isoformat(), to_date=t.isoformat(), interval=25)
            if p is not None and not p.empty:
                parts.append(p)
        except Exception:
            pass
    df = pd.concat(parts).sort_index() if parts else pd.DataFrame()
    if not df.empty:
        df = df[~df.index.duplicated(keep="first")]
    pickle.dump(df, open(fp, "wb"))
    return df


def _tf_frame(base: pd.DataFrame, tf: int) -> pd.DataFrame:
    if base is None or base.empty:
        return pd.DataFrame()
    df = _pap.resample_intraday(base, tf)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df = df[df["Volume"] > 0]          # Dhan's 15:30 zero-volume stub (see live fix 9-Aug)
    return df


def _completed_resample(daily_sub: pd.DataFrame, rule: str, day: dt.date) -> pd.DataFrame:
    """Weekly/monthly bars from completed sessions, dropping the bucket that contains
    `day` (still forming at that point in time)."""
    if daily_sub.empty:
        return daily_sub
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    r = daily_sub.resample(rule).agg(agg).dropna()
    if r.empty:
        return r
    last = r.index[-1].date()
    if (rule.startswith("W") and day <= last) or (rule.startswith("M") and (day.year, day.month) == (last.year, last.month)):
        r = r.iloc[:-1]
    return r


# ── gates ────────────────────────────────────────────────────────────────────
def _location(daily: pd.DataFrame, day: dt.date, px: float, cache: dict) -> dict:
    """D/W/M pattern demand zone at px, from sessions completed before `day`."""
    key = day
    if key not in cache:
        sub = daily[daily.index.date < day]
        cache[key] = (sub, _completed_resample(sub, "W-FRI", day), _completed_resample(sub, "ME", day))
    sub, wk, mo = cache[key]
    best = {"ok": False, "distal": None, "tf": None}
    for tf, frame in (("D", sub), ("W", wk), ("M", mo)):
        if frame is None or len(frame) < 60:
            continue
        try:
            z = _ze.zone_support(frame, tf, px, daily_df=sub if tf != "D" else None) or {}
        except TypeError:
            z = _ze.zone_support(frame, tf, px) or {}
        except Exception:
            continue
        if z.get("at_support_pattern"):
            d = z.get("distal")
            if not best["ok"] or (d is not None and (best["distal"] is None or d > best["distal"])):
                best = {"ok": True, "distal": d, "tf": tf}
    return best


def _daily_refs(daily: pd.DataFrame, day: dt.date):
    sub = daily[daily.index.date < day]["Close"]
    if len(sub) < 25:
        return None, None, None
    e20 = float(sub.ewm(span=20, adjust=False).mean().iloc[-1])
    e10 = float(sub.ewm(span=10, adjust=False).mean().iloc[-1])
    d = daily[daily.index.date < day]
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - d["Close"].shift()).abs(),
                    (d["Low"] - d["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
    return e20, e10, atr


def find_go(itf: pd.DataFrame, daily: pd.DataFrame, anchor: str, known_pb: bool) -> dict | None:
    """First closed trigger-TF bar after the anchor day that passes all four gates."""
    a = dt.date.fromisoformat(anchor)
    days = sorted(set(itf.index.date))
    after = [d for d in days if d > a][:ENTRY_WINDOW_DAYS]
    if not after:
        return None
    v = itf["Volume"].astype(float)
    rv = v / v.shift(1).rolling(50).mean()
    rng = (itf["High"] - itf["Low"]).replace(0, np.nan)
    bar_ok = (itf["Close"] >= itf["Open"]) | (((itf["Close"] - itf["Low"]) / rng) >= 0.5)
    loc_cache, ref_cache = {}, {}
    pos_of = {ts: i for i, ts in enumerate(itf.index)}
    for ts in itf.index[(itf.index.date >= after[0]) & (itf.index.date <= after[-1])]:
        j = pos_of[ts]
        if j < 60 or not bool(bar_ok.iloc[j]) or not (rv.iloc[j] >= PB_RV_FLOOR):
            continue
        day = ts.date()
        if day not in ref_cache:
            ref_cache[day] = _daily_refs(daily, day)
        e20, e10, atr = ref_cache[day]
        if e20 is None:
            continue
        win = itf.iloc[max(0, j - 300): j + 1]
        try:
            pats = _pap.detect_bull_patterns(win, "", intraday=True, ema20_ref=e20, ema10_ref=e10)
        except Exception:
            continue
        fired = {n for (n, f, t, _d) in pats if f and t > 0}
        if not fired:
            continue
        px = float(itf["Close"].iloc[j])
        loc = _location(daily, day, px, loc_cache)
        if not loc["ok"]:
            continue
        pb = known_pb or (bool(fired & PB_CONTRACTION) and not (fired & PB_EXPANSION))
        if rv.iloc[j] < (PB_RV_FLOOR if pb else RV_FLOOR):
            continue
        return {"pos": j, "ts": ts, "fired": sorted(fired), "loc": loc, "pb": pb,
                "rv": round(float(rv.iloc[j]), 2), "atr_d": atr,
                "days_to_go": after.index(day) + 1}
    return None


# ── trade ────────────────────────────────────────────────────────────────────
def _stop(itf, go_pos, entry, loc, atr_d):
    cands = []
    if loc.get("distal") and loc["distal"] < entry:
        cands.append(float(loc["distal"]) * 0.999)
    swing = float(itf["Low"].iloc[max(0, go_pos - 9): go_pos + 1].min())
    if swing < entry:
        cands.append(swing * 0.999)
    cap = entry - 3.0 * atr_d if atr_d else entry * 0.90
    sl = max(cands) if cands else cap
    sl = max(sl, cap)
    return min(sl, entry * 0.999)


def simulate(itf, daily, go, variant, cand, bench) -> dict:
    j = go["pos"]
    go_c, go_h = float(itf["Close"].iloc[j]), float(itf["High"].iloc[j])
    if variant == "I_close":
        fpos, fpx = j, go_c
    elif variant == "I_retest":
        fpos = fpx = None
        for k in range(j + 1, min(j + 1 + RETEST_BARS, len(itf))):
            if float(itf["Low"].iloc[k]) <= go_c:
                fpos, fpx = k, min(float(itf["Open"].iloc[k]), go_c)
                break
    else:
        fpos = fpx = None
        for k in range(j + 1, min(j + 1 + BUYSTOP_BARS, len(itf))):
            if float(itf["High"].iloc[k]) >= go_h:
                fpos, fpx = k, max(float(itf["Open"].iloc[k]), go_h)
                break
    if fpos is None:
        return {"Status": "no fill"}
    sl = _stop(itf, j, fpx, go["loc"], go["atr_d"])
    risk = fpx - sl
    if risk <= 0:
        return {"Status": "bad stop"}
    entry_day = itf.index[fpos].date()
    det = None
    # rest of the entry day, bar by bar, for the stop
    for k in range(fpos + 1, len(itf)):
        if itf.index[k].date() != entry_day:
            break
        if float(itf["Low"].iloc[k]) <= sl:
            ex = min(float(itf["Open"].iloc[k]), sl)
            ret = (ex - fpx) / fpx * 100 - 2 * _rp.COST_PER_LEG_DEFAULT
            bm = _eb._bench_matched(bench, entry_day.isoformat(), 0) or 0.0
            return {"Status": "OK", "Entry_Date": entry_day.isoformat(), "Entry_Price": round(fpx, 2),
                    "SL_price": round(sl, 2), "SL_pct": round(risk / fpx * 100, 3), "Return_pct": round(ret, 3),
                    "Alpha_Matched_pct": round(ret - bm, 3), "Exit_Reason": "SL hit (entry day)",
                    "Days_Held": 0, "Hit_Initial_SL": True}
    dpos = int(np.where(daily.index.date == entry_day)[0][-1]) if (daily.index.date == entry_day).any() else None
    if dpos is None:
        return {"Status": "no daily bar"}
    try:
        det = _rp._pafv.compute_pa_detectors(daily.iloc[: dpos + 1])
    except Exception:
        det = None
    fwd = _rp._go_forward_days(cand, det, dpos) if det is not None else 60
    res = _rp._simulate_one_trade(daily, dpos, fpx, sl, fpx + 2 * risk, fpx + 3 * risk, t1_qty_pct=33,
                                  t2_qty_pct=33, max_bars=fwd, trail_atr_mult=4.5, cost_pct=_rp.COST_PER_LEG_DEFAULT)
    if res.get("realized_pct") is None:
        return {"Status": "no result"}
    bm = _eb._bench_matched(bench, entry_day.isoformat(), res["days_held"])
    return {"Status": "OK", "Entry_Date": entry_day.isoformat(), "Entry_Price": round(fpx, 2),
            "SL_price": round(sl, 2), "SL_pct": round(risk / fpx * 100, 3), "forward_days_used": fwd,
            "Return_pct": res["realized_pct"], "Alpha_Matched_pct": (round(res["realized_pct"] - bm, 3) if bm is not None else None),
            "Exit_Reason": res["exit_reason"], "Days_Held": res["days_held"],
            "Hit_Initial_SL": bool(res.get("hit_initial_sl", False))}


# ── run + report ─────────────────────────────────────────────────────────────
VARIANTS = ("I_close", "I_retest", "I_buystop")


def run(tfs, limit=None) -> dict:
    meta = json.load(open(os.path.join(RUNS, "validation_%s_meta.json" % CATALYST_RUN)))
    anchors = sorted(meta["anchors"])
    pairs = []
    for a in anchors:
        p = os.path.join(QCACHE, "qual_%s.pkl" % a)
        if os.path.exists(p):
            for m in pickle.load(open(p, "rb")).to_dict("records"):
                pairs.append((a, m))
    if limit:
        pairs = pairs[:limit]
    print("intraday replay: %d qualified names x TF %s" % (len(pairs), tfs), flush=True)
    bench = _eb._bench()
    rows = {(v, tf): [] for v in VARIANTS for tf in tfs}
    dcache = {}
    t0 = time.time()
    for n, (a, m) in enumerate(pairs, 1):
        sym = str(m.get("Symbol"))
        if sym not in dcache:
            dcache[sym] = _daily(sym)
        daily = dcache[sym]
        base = _base25(sym, a) if not daily.empty else pd.DataFrame()
        known_pb = str(m.get("Catalyst") or "").upper().startswith("SWG-PB")
        for tf in tfs:
            itf = _tf_frame(base, tf)
            go = find_go(itf, daily, a, known_pb) if (not itf.empty and not daily.empty) else None
            for v in VARIANTS:
                r = {"as_of": a, "Symbol": sym, "Catalyst": m.get("Catalyst"), "tf": tf}
                if itf.empty or daily.empty:
                    r["Status"] = "no data"
                elif go is None:
                    r["Status"] = "no GO in window"
                else:
                    r.update({"GO_ts": str(go["ts"]), "Days_To_GO": go["days_to_go"], "GO_PA": "+".join(go["fired"]),
                              "Loc_TF": go["loc"]["tf"], "PB": go["pb"], "RV": go["rv"]})
                    try:
                        r.update(simulate(itf, daily, go, v, m, bench))
                    except Exception as e:
                        r["Status"] = "err: %s" % str(e)[:80]
                rows[(v, tf)].append(r)
        if n % 25 == 0:
            print("  %d/%d names, %.0fs" % (n, len(pairs), time.time() - t0), flush=True)
    os.makedirs(OUT, exist_ok=True)
    res = {}
    for (v, tf), rr in rows.items():
        df = pd.DataFrame(rr)
        df.to_csv(os.path.join(OUT, "%s_%s.csv" % (v, tf)), index=False)
        res[(v, tf)] = df
    return res, anchors


def report(res, anchors, tfs) -> str:
    e0p = os.path.join(RUNS, "entry_rebaseline", "E0_close.csv")
    e0 = _eb.add_r(pd.read_csv(e0p)) if os.path.exists(e0p) else pd.DataFrame()
    cut = anchors[int(len(anchors) * 0.6)]
    L = ["INTRADAY GO REPLAY (75m/125m) vs the anchor-close entry - catalyst set %s, OOS from %s" % (CATALYST_RUN, cut),
         "R = realised %% / initial risk %%; benchmark over each trade's actual hold\n"]
    if not e0.empty:
        ok = e0[e0["R"].notna()]
        L.append("E0_close (daily, no gate): n=%d  mean %+.3fR  median %+.3fR  stop %.0f%%\n" % (
            len(ok), ok["R"].mean(), ok["R"].median(), 100 * ok["Hit_Initial_SL"].astype(bool).mean()))
    for tf in tfs:
        L.append("=== %sm ===" % tf)
        L.append("%-10s %5s %6s %7s %7s %6s %6s %8s" % ("variant", "fills", "fill%", "meanR", "medR", "win%", "stop%", "daysToGO"))
        for v in VARIANTS:
            d = res[(v, tf)].copy()
            d["SL_pct"] = pd.to_numeric(d.get("SL_pct"), errors="coerce")
            d["Return_pct"] = pd.to_numeric(d.get("Return_pct"), errors="coerce")
            d["R"] = np.where((d["Status"] == "OK") & (d["SL_pct"] > 0), d["Return_pct"] / d["SL_pct"], np.nan)
            ok = d[d["R"].notna()]
            if ok.empty:
                L.append("%-10s %5d" % (v, 0)); continue
            L.append("%-10s %5d %5.0f%% %+7.3f %+7.3f %5.1f%% %5.0f%% %8.1f" % (
                v, len(ok), 100 * len(ok) / max(len(d), 1), ok["R"].mean(), ok["R"].median(), 100 * (ok["R"] > 0).mean(),
                100 * ok["Hit_Initial_SL"].astype(bool).mean(), pd.to_numeric(ok["Days_To_GO"], errors="coerce").mean()))
            if not e0.empty:
                key = ["as_of", "Symbol"]
                mm = ok[key + ["R"]].merge(e0[e0["R"].notna()][key + ["R", "fam"]], on=key, suffixes=("_go", "_e0"))
                mm["diff"] = mm["R_go"] - mm["R_e0"]
                for lab, sub in (("ALL", mm), ("IS", mm[mm["as_of"] < cut]), ("OOS", mm[mm["as_of"] >= cut])):
                    lo, hi, pp = _eb.boot_paired(sub)
                    L.append("     paired %-3s n=%3d  GO %+.3fR  E0 %+.3fR  diff %+.3fR  CI95 [%+.3f, %+.3f]  P(>0) %.0f%%" % (
                        lab, len(sub), sub["R_go"].mean(), sub["R_e0"].mean(), sub["diff"].mean(), lo, hi, 100 * pp))
                for f, sub in mm.groupby("fam"):
                    L.append("       %-4s n=%3d  diff %+.3fR" % (f, len(sub), sub["diff"].mean()))
        st = res[("I_close", tf)]["Status"].astype(str).value_counts().to_dict()
        L.append("  GO funnel: %s\n" % st)
    L.append("Daily-bar exits after the entry day; intraday GO, entry and stop. One run, not re-sliced.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", choices=["75", "125"])
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    tfs = [int(a.tf)] if a.tf else [75, 125]
    res, anchors = run(tfs, a.limit)
    txt = report(res, anchors, tfs)
    if not a.limit:
        open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8").write(txt)
    print("\n" + txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
