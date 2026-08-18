"""Re-measure the RRG cell-level alpha on the NEW (strike_cal) formula.

WHY: `_rrg_tradeable`'s whitelist is justified by a May backtest (n=5,020) that was
run on the OLD 12/5/12 RRG pair. On 18-Aug-2026 every surface moved to the RRG Studio
calibration (25/10/7 + origin-preserving affine), so the cells are now produced by a
different function than the one whose alpha justified them. The file's own history
records this exact situation once before ("v1.7: RRG_Tradeable recalibrated on new
1-pass formula"), so a re-fit is the precedent, not an innovation.

METHOD, following the house rules the earlier studies settled on:
  * MATCHED-HORIZON alpha - the benchmark leg spans the SAME window as the stock leg.
  * Weekly bars, resampled from daily with pa_patterns._confirmed_weekly_ohlcv, so the
    cells here are the same ones the board and S4 compute (never a native 1wk fetch -
    the two anchor differently and the join silently empties).
  * Chronological IS/OOS split. A whitelist fitted on all the data is a whitelist
    fitted to noise; a cell has to survive out-of-sample to earn a place.
  * BLOCK-BOOTSTRAP BY SYMBOL. Consecutive weekly observations share almost all of
    their forward window, so raw n hugely overstates independence. Resampling symbols
    (not rows) is the honest interval - the same correction the RV study needed.
  * Cells are reported with n; a cell with a handful of symbols decides nothing.

Run:  python rrg_cell_remeasure.py [--horizon 4] [--universe nifty500] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_provider as dp                     # noqa: E402
import pa_patterns as pap                      # noqa: E402
from rrg_engine import calculate_jdk_rrg       # noqa: E402

BENCH = "NIFTY 500"
THRESH = 0.30          # noise floor, identical to bull_screener._rrg_trajectory
TRAIL = 4              # RRG tail length in weeks


def weekly_close(sym: str):
    """Weekly closes via the SAME path the board uses (daily -> confirmed weekly)."""
    try:
        d = dp.fetch_ohlcv(sym, period="5y", interval="1d", use_cache=True,
                           auto_adjust=True)
        if d is None or d.empty:
            return None
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        w = pap._confirmed_weekly_ohlcv(d)
        if w is None or len(w) < 80:
            return None
        return w["Close"].dropna()
    except Exception:
        return None


def quadrant(v: float, m: float) -> str:
    if v >= 100 and m >= 100:
        return "LEADING"
    if v >= 100:
        return "WEAKENING"
    if m < 100:
        return "LAGGING"
    return "IMPROVING"


def next_quadrant(cur: str, dv: float, dm: float) -> str:
    """Verbatim transition logic from v67 f_rrg_info / S4Core.rrgInfo."""
    if cur == "LEADING":
        return "WEAKENING" if dm < -THRESH else (
            "IMPROVING" if (dv < -THRESH and dm < THRESH) else cur)
    if cur == "WEAKENING":
        return "LAGGING" if dv < -THRESH else (
            "LEADING" if (dm > THRESH and dv > -THRESH) else cur)
    if cur == "LAGGING":
        return "IMPROVING" if dm > THRESH else (
            "WEAKENING" if (dv > THRESH and dm > -THRESH) else cur)
    return "LEADING" if dv > THRESH else (
        "LAGGING" if (dm < -THRESH and dv < THRESH) else cur)


def observations(sym: str, sec: pd.Series, bench: pd.Series, horizon: int):
    """One row per week: the cell occupied, and the matched-horizon forward alpha."""
    rrg = calculate_jdk_rrg(sec, bench, mode="strike_cal")
    if rrg is None or rrg.empty:
        return []
    j = rrg.join(pd.DataFrame({"px": sec, "bx": bench}), how="inner").dropna()
    if len(j) < TRAIL + horizon + 2:
        return []
    r = j["RS_Ratio"].to_numpy()
    m = j["RS_Momentum"].to_numpy()
    px = j["px"].to_numpy()
    bx = j["bx"].to_numpy()
    idx = j.index
    out = []
    for i in range(TRAIL, len(j) - horizon):
        cur = quadrant(r[i], m[i])
        nxt = next_quadrant(cur, r[i] - r[i - TRAIL], m[i] - m[i - TRAIL])
        # MATCHED horizon: both legs span exactly i -> i+horizon.
        sr = px[i + horizon] / px[i] - 1.0
        br = bx[i + horizon] / bx[i] - 1.0
        if not np.isfinite(sr) or not np.isfinite(br):
            continue
        out.append({"symbol": sym, "date": idx[i], "cell": f"{cur} -> {nxt}",
                    "cur": cur, "stable": cur == nxt,
                    "alpha": (sr - br) * 100.0})
    return out


def block_bootstrap(df: pd.DataFrame, n_boot: int = 2000, seed: int = 7):
    """Resample SYMBOLS, not rows - overlapping windows are not independent."""
    syms = df["symbol"].unique()
    if len(syms) < 5:
        return (np.nan, np.nan)
    by = {s: g["alpha"].to_numpy() for s, g in df.groupby("symbol")}
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(syms, size=len(syms), replace=True)
        means[b] = np.concatenate([by[s] for s in pick]).mean()
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=4, help="forward weeks")
    ap.add_argument("--universe", default="nifty500")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    uni = json.load(open(f"{a.universe}_symbols.json", encoding="utf-8"))
    if isinstance(uni, dict):
        uni = uni.get("symbols") or list(uni.values())[0]
    uni = [str(s).replace(".NS", "").strip().upper() for s in uni]
    if a.limit:
        uni = uni[:a.limit]

    bench = weekly_close(BENCH)
    if bench is None:
        print("benchmark unavailable"); return
    print(f"universe {len(uni)} · benchmark {len(bench)} weekly bars · "
          f"horizon {a.horizon}w · MATCHED")

    rows, done, skipped = [], 0, 0
    for i, s in enumerate(uni, 1):
        sec = weekly_close(s)
        if sec is None:
            skipped += 1
            continue
        obs = observations(s, sec, bench, a.horizon)
        if obs:
            rows.extend(obs); done += 1
        if i % 50 == 0:
            print(f"  {i}/{len(uni)}  symbols kept {done}  rows {len(rows)}", flush=True)

    if not rows:
        print("no observations"); return
    df = pd.DataFrame(rows)
    print(f"\nsymbols {done} (skipped {skipped}) · observations {len(df)} · "
          f"{df.date.min():%Y-%m} -> {df.date.max():%Y-%m}")

    # chronological IS/OOS
    cut = df["date"].quantile(0.6)
    IS, OOS = df[df.date <= cut], df[df.date > cut]
    print(f"IS <= {cut:%Y-%m} ({len(IS)})  |  OOS > {cut:%Y-%m} ({len(OOS)})\n")

    hdr = (f"{'cell':30s}{'n':>7s}{'sym':>5s}{'ALL a%':>9s}{'IS':>8s}{'OOS':>8s}"
           f"{'win%':>7s}{'CI95 (all)':>20s}   verdict")
    print(hdr); print("-" * len(hdr))
    res = []
    for cell, g in sorted(df.groupby("cell"), key=lambda kv: -kv[1]["alpha"].mean()):
        gi, go = IS[IS.cell == cell], OOS[OOS.cell == cell]
        lo, hi = block_bootstrap(g)
        a_all = g["alpha"].mean()
        a_is = gi["alpha"].mean() if len(gi) else np.nan
        a_oos = go["alpha"].mean() if len(go) else np.nan
        win = (g["alpha"] > 0).mean() * 100
        nsym = g["symbol"].nunique()
        # A cell earns BUY OK only if it is positive overall, positive OOS, and its
        # symbol-block CI excludes zero. Anything else is "not shown to be positive" -
        # which is not the same as negative, and is reported as such.
        if np.isnan(a_oos) or nsym < 20:
            v = "insufficient"
        elif a_all > 0 and a_oos > 0 and lo > 0:
            v = "BUY OK"
        elif a_all < 0 and a_oos < 0 and hi < 0:
            v = "WAIT (neg)"
        else:
            v = "unproven"
        res.append({"cell": cell, "n": len(g), "symbols": nsym, "alpha_all": a_all,
                    "alpha_is": a_is, "alpha_oos": a_oos, "win_pct": win,
                    "ci_lo": lo, "ci_hi": hi, "verdict": v})
        print(f"{cell:30s}{len(g):>7d}{nsym:>5d}{a_all:>+9.2f}{a_is:>+8.2f}"
              f"{a_oos:>+8.2f}{win:>7.1f}   [{lo:+6.2f},{hi:+6.2f}]   {v}")

    out = a.out or f"validation_runs/rrg_cells_h{a.horizon}.csv"
    os.makedirs("validation_runs", exist_ok=True)
    pd.DataFrame(res).to_csv(out, index=False)
    print(f"\nwritten: {out}")

    old = {"LEADING -> IMPROVING", "LEADING -> LEADING", "IMPROVING -> LEADING",
           "LAGGING -> IMPROVING", "WEAKENING -> LEADING"}
    new = {r["cell"] for r in res if r["verdict"] == "BUY OK"}
    print("\nCURRENT whitelist (fitted on the OLD formula):")
    print("   " + " · ".join(sorted(old)))
    print("MEASURED on the new formula:")
    print("   " + (" · ".join(sorted(new)) if new else "(no cell clears the bar)"))
    if new:
        print("   dropped:", ", ".join(sorted(old - new)) or "none")
        print("   added  :", ", ".join(sorted(new - old)) or "none")


if __name__ == "__main__":
    main()
