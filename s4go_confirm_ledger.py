"""s4go_confirm_ledger.py — live-forward GO-confirmation harness (23 Jul 2026).

Seals the two gaps the in-sample filter test couldn't: partial ENDOGENEITY and
SMALL SAMPLE. It does so with a disjoint-window, forward-only, append-only design.

WHY IT'S CLEAN (no endogeneity, no look-ahead):
  At a DECISION DATE D, a catalyst pick is 'confirmed' iff a GM+S4 GO fired in the
  TRAILING window [D-conf_window, D] — decided using ONLY data up to D. The OUTCOME
  is the matched-horizon alpha measured FORWARD from D over the catalyst window
  [D, D+fwd]. Signal window and outcome window are DISJOINT (share only D), so the
  "it rallied, so it both confirmed and returned over the same span" coupling that
  muddied s4go_filter_value.py is structurally impossible here.

TWO USES:
  • SEED (immediate, clean): --mode record over historical decision dates (pinned,
    point-in-time) → clean rows now, on fresh disjoint windows. --mode seed runs the
    18 cached catalyst anchors then scores.
  • LIVE-FORWARD (prospective): schedule --mode record with no --as_of → records
    TODAY's qualified picks + their trailing-window confirmation into the ledger.
    Weeks later --mode score joins the matured rows to realized forward alpha. This
    is genuinely out-of-sample: the decision is logged before the outcome exists.

LEDGER: validation_runs/go_confirm_ledger.csv (append-only, idempotent per
  (decision_date, symbol)). Columns: decision_date, symbol, catalyst, family,
  positional, confirmed, confirm_date, conf_window, ref_close, fwd_days, recorded_at.
SCORED: validation_runs/go_confirm_ledger_scored.csv (adds fwd_alpha_pct once matured).

Venv python. Reuses replay's GO internals (zero drift with the backtest/live gate).
"""
import os, sys, json, argparse, glob, pickle
from datetime import datetime
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")
LEDGER = os.path.join(RUNS, "go_confirm_ledger.csv")
SCORED = os.path.join(RUNS, "go_confirm_ledger_scored.csv")
CATALYST_RUN = "20260723_063652"          # for the seed anchor list

import data_provider as _dp
import validation as _val
import bull_screener as _bull
import replay as _r

LEDGER_COLS = ["decision_date", "symbol", "catalyst", "family", "positional",
               "confirmed", "confirm_date", "conf_window", "ref_close",
               "fwd_days", "recorded_at"]


def _family(cat):
    c = str(cat).upper().strip()
    if c.startswith("POS-ACCUM"): return "POS-ACCUM"
    if c.startswith("POS") or c.startswith("WYC"): return "POS/WYC"
    if c.startswith("SWG"): return "SWG"
    if c.startswith("REV"): return "REV"
    return c or "NONE"


def detect_confirmation(df, t_pos, conf_window=40, rv_floor=1.0):
    """Point-in-time: did a GM+S4 GO fire in the trailing [t_pos-conf_window+1, t_pos]?
    Uses ONLY bars up to t_pos (location lifecycle sees df.iloc[:i+1]). Returns
    (confirmed: bool, confirm_iso: str|None)."""
    try:
        det = _r._pafv.compute_pa_detectors(df)
    except Exception:
        return False, None
    go_pa = _r._go_pa_series(det, _r.GO_BULL_TRIGGERS)
    vol_ok = (det["cur_rel_vol"] >= rv_floor).fillna(False)
    bar_ok = _r._bar_ok_series(det)
    lo = max(0, t_pos - conf_window + 1)
    last = None
    for i in range(lo, t_pos + 1):
        if not (bool(go_pa.iloc[i]) and bool(vol_ok.iloc[i]) and bool(bar_ok.iloc[i])):
            continue
        loc = _r._location_at(df.iloc[:i + 1], float(df["Close"].iloc[i]))
        if loc.get("ok"):
            last = df.index[i]                 # most-recent confirming GO in the window
    return (last is not None), (last.strftime("%Y-%m-%d") if last is not None else None)


def _qualify(as_of, universe):
    """Catalyst qualification as-of `as_of` (cache if present, else pinned live)."""
    cf = os.path.join(CACHE, f"qual_{as_of}.pkl")
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    live = as_of is None
    if not live:
        _dp.set_pinned_date(as_of)
    try:
        picks = _bull.run_bull_screener(symbols=universe, strict=True)
    finally:
        if not live:
            _dp.set_pinned_date(None)
    if picks is None or picks.empty:
        return pd.DataFrame(columns=["Symbol", "Catalyst"])
    keep = [c for c in ("Symbol", "Catalyst", "Signal_Label", "Score") if c in picks.columns]
    cands = picks[keep].copy()
    if "Signal_Label" in cands.columns and "Catalyst" not in cands.columns:
        cands = cands.rename(columns={"Signal_Label": "Catalyst"})
    return cands


def record(as_of, universe_name="nifty500", conf_window=40, rv_floor=1.0):
    """Record one decision-date snapshot into the ledger (idempotent)."""
    universe = _val.default_universe(universe_name)
    dstr = as_of if as_of else datetime.now().strftime("%Y-%m-%d")
    cands = _qualify(as_of, universe)
    if cands.empty:
        print(f"[record {dstr}] no qualified names"); return
    rows = []
    for _, c in cands.iterrows():
        sym = str(c["Symbol"]).strip()
        cat = str(c.get("Catalyst", "")).strip()
        fam = _family(cat)
        try:
            df = _dp.fetch_ohlcv(sym, period="3y", interval="1d")
        except Exception:
            df = pd.DataFrame()
        if df is None or df.empty or len(df) < 60:
            continue
        idx = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
        df = df.copy(); df.index = idx
        t_pos = df.index.searchsorted(pd.Timestamp(dstr), side="right") - 1
        if t_pos < 30:
            continue
        confirmed, cdate = detect_confirmation(df, t_pos, conf_window, rv_floor)
        rows.append({
            "decision_date": dstr, "symbol": sym, "catalyst": cat, "family": fam,
            "positional": fam in ("POS-ACCUM", "POS/WYC"),
            "confirmed": bool(confirmed), "confirm_date": cdate,
            "conf_window": conf_window,
            "ref_close": round(float(df["Close"].iloc[t_pos]), 2),
            "fwd_days": _r.fwd_days_for_catalyst(cat, default=60),
            "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    new = pd.DataFrame(rows, columns=LEDGER_COLS)
    if os.path.exists(LEDGER):
        old = pd.read_csv(LEDGER)
        key = ["decision_date", "symbol"]
        old = old[~old.set_index(key).index.isin(new.set_index(key).index)]
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    out.to_csv(LEDGER, index=False)
    nconf = int(new["confirmed"].sum())
    print(f"[record {dstr}] {len(new)} picks  confirmed {nconf}  never {len(new)-nconf}  "
          f"(positional {int(new['positional'].sum())}) -> {os.path.basename(LEDGER)} (total {len(out)})")


def _fwd_matched_alpha(sym, ref_iso, fwd_days, df_bench):
    """Buy&hold matched alpha from ref date forward `fwd_days` (pure selection measure,
    no exit sim). Returns None if not yet matured / no data."""
    try:
        df = _dp.fetch_ohlcv(sym, period="3y", interval="1d")
    except Exception:
        return None
    if df is None or df.empty:
        return None
    idx = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
    df = df.copy(); df.index = idx
    e = df.index.searchsorted(pd.Timestamp(ref_iso), side="right") - 1
    x = e + int(fwd_days)
    if e < 0 or x >= len(df):                 # not matured yet
        return None
    r = 100.0 * (float(df["Close"].iloc[x]) - float(df["Close"].iloc[e])) / float(df["Close"].iloc[e])
    eb = df_bench.index.searchsorted(pd.Timestamp(ref_iso), side="right") - 1
    xb = eb + int(fwd_days)
    if eb < 0 or xb >= len(df_bench):
        return None
    b = 100.0 * (float(df_bench["Close"].iloc[xb]) - float(df_bench["Close"].iloc[eb])) / float(df_bench["Close"].iloc[eb])
    return round(r - b, 2)


def score():
    if not os.path.exists(LEDGER):
        print("no ledger yet — run --mode record first"); return
    led = pd.read_csv(LEDGER)
    dbr = _dp.fetch_ohlcv(_r.BENCHMARK_YF, period="3y", interval="1d")
    bidx = dbr.index.tz_localize(None) if getattr(dbr.index, "tz", None) is not None else dbr.index
    df_bench = dbr.copy(); df_bench.index = bidx
    led["fwd_alpha_pct"] = [
        _fwd_matched_alpha(r.symbol, r.decision_date, r.fwd_days, df_bench)
        for r in led.itertuples()
    ]
    led.to_csv(SCORED, index=False)
    m = led[led["fwd_alpha_pct"].notna()].copy()
    n_pending = len(led) - len(m)
    print(f"scored {len(m)} matured rows ({n_pending} still pending horizon) -> {os.path.basename(SCORED)}")
    if m.empty:
        print("  (nothing matured yet — re-run --mode score after the horizons elapse)"); return

    def rep(name, d):
        C, N = d[d.confirmed]["fwd_alpha_pct"], d[~d.confirmed]["fwd_alpha_pct"]
        print(f"\n-- {name}  n={len(d)} (confirmed {len(C)} / never {len(N)}) --")
        if len(C): print(f"  CONFIRMED  mean={C.mean():+.2f}%  win={C.gt(0).mean()*100:5.1f}%")
        if len(N): print(f"  NEVER      mean={N.mean():+.2f}%  win={N.gt(0).mean()*100:5.1f}%")
        if len(C) and len(N):
            print(f"  EDGE (forward-from-decision, endogeneity-free)  "
                  f"{C.mean()-N.mean():+.2f}pp mean | {C.gt(0).mean()*100-N.gt(0).mean()*100:+.1f}pp win")

    print("\n" + "=" * 70)
    print("  GO-CONFIRMATION FILTER — DISJOINT-WINDOW (clean) forward alpha")
    print("=" * 70)
    rep("ALL", m)
    rep("POSITIONAL", m[m.positional])
    rep("SWING/OTHER", m[~m.positional])
    # chronological OOS split once there are enough decision dates
    dates = sorted(m["decision_date"].unique())
    if len(dates) >= 6:
        k = max(1, int(round(len(dates) * 0.6)))
        oos = m[m["decision_date"].isin(dates[k:])]
        rep(f"OUT-OF-SAMPLE ({dates[k]}..{dates[-1]})", oos)
        rep(f"  OOS-POSITIONAL", oos[oos.positional])


def seed(conf_window=40):
    """Seed the ledger from the 18 cached catalyst anchors (clean disjoint windows), then score."""
    anchors = json.load(open(os.path.join(RUNS, f"validation_{CATALYST_RUN}_meta.json")))["anchors"]
    print(f"seeding {len(anchors)} historical decision dates (conf_window={conf_window})…")
    for a in anchors:
        record(a, conf_window=conf_window)
    print("\n--- scoring the seeded ledger ---")
    score()


def main():
    ap = argparse.ArgumentParser(description="Live-forward GO-confirmation ledger harness.")
    ap.add_argument("--mode", choices=["record", "score", "seed"], default="record")
    ap.add_argument("--as_of", default=None, help="decision date YYYY-MM-DD (record mode; omit = today/live)")
    ap.add_argument("--conf_window", type=int, default=40)
    ap.add_argument("--rv_floor", type=float, default=1.0)
    ap.add_argument("--universe", default="nifty500")
    a = ap.parse_args()
    if a.mode == "record":
        record(a.as_of, a.universe, a.conf_window, a.rv_floor)
    elif a.mode == "score":
        score()
    else:
        seed(a.conf_window)


if __name__ == "__main__":
    main()
