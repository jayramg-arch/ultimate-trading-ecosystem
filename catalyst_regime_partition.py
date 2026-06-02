# catalyst_regime_partition.py
# Phase 2 diagnostic — partition backtest trades by catalyst family, market
# direction, and exit reason, so a real edge in one slice isn't masked by
# pooling (per bull_market_base_rate_warning + the May catalyst-behaviour work).
# ---------------------------------------------------------------------------
# WHY
#   The pooled walk-forward says NO-EDGE (mean matched alpha -1.53%). But POS
#   (positional, trend-following) and SWG (swing) setups behave completely
#   differently — pooling can cancel a real edge in one family against noise in
#   another. And bearish/mean-reversion detectors can look fake-positive in a
#   bull regime. This splits the trades to find WHERE the (non-)edge lives.
#
# HONEST METRIC
#   Alpha_Matched_pct — return minus the benchmark over the trade's OWN
#   catalyst-matched forward window (POS 120-180d, SWG 30d). Trades with no
#   entry bar / no data (NaN) are dropped and reported, never zero-filled.
#
# DIRECTION
#   Per-trade, from sign(Benchmark_Matched_pct): the benchmark's move over that
#   trade's matched horizon. UP = trade lived in a rising tape, DOWN = falling.
#
# INVOCATION
#   python catalyst_regime_partition.py                  # LAST_RUN details
#   python catalyst_regime_partition.py --details <csv>
# ---------------------------------------------------------------------------

import os
import sys
import glob
import argparse

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(_DIR, "validation_runs")
METRIC = "Alpha_Matched_pct"   # the honest matched-horizon alpha


def _resolve_details(details_path=None):
    if details_path:
        return details_path
    ptr = os.path.join(RUNS_DIR, "LAST_RUN.txt")
    if os.path.exists(ptr):
        run_id = open(ptr).read().strip()
        cand = os.path.join(RUNS_DIR, f"validation_{run_id}_details.csv")
        if os.path.exists(cand):
            return cand
    cands = sorted(glob.glob(os.path.join(RUNS_DIR, "validation_*_details.csv")),
                   key=os.path.getmtime, reverse=True)
    return cands[0] if cands else None


def _family(cat):
    """Collapse catalyst label to its family."""
    c = str(cat).upper()
    if c.startswith("POS"):
        return "POS (positional)"
    if c.startswith("WYC"):
        return "WYC (wyckoff)"
    if c.startswith("REV"):
        return "REV (recovery)"
    if c.startswith("SWG"):
        return "SWG (swing)"
    return "OTHER"


def _stats(g):
    """Aggregate stats on the matched-alpha metric for a group."""
    a = g[METRIC].astype(float)
    wins = a[a > 0]; losses = a[a < 0]
    gp = wins.sum(); gl = abs(losses.sum())
    n = len(a)
    return {
        "n": n,
        "win_pct": round(100.0 * len(wins) / n, 1) if n else 0.0,
        "mean_alpha": round(float(a.mean()), 2) if n else np.nan,
        "median_alpha": round(float(a.median()), 2) if n else np.nan,
        "cum_alpha": round(float(a.sum()), 1),
        "profit_factor": round(gp / gl, 2) if gl > 1e-9 else (np.inf if gp > 0 else 0.0),
        "avg_days": round(float(g["Days_Held"].astype(float).mean()), 0) if "Days_Held" in g else np.nan,
    }


def _table(df, by):
    rows = []
    for key, g in df.groupby(by):
        s = _stats(g); s[by] = str(key)
        rows.append(s)
    out = pd.DataFrame(rows)
    cols = [by, "n", "win_pct", "mean_alpha", "median_alpha", "cum_alpha", "profit_factor", "avg_days"]
    return out[cols].sort_values("mean_alpha", ascending=False).reset_index(drop=True) if not out.empty else out


def analyze(details_path=None):
    path = _resolve_details(details_path)
    if not path or not os.path.exists(path):
        return {"ok": False, "message": "No validation details CSV found."}
    df = pd.read_csv(path)
    total = len(df)
    df = df[df[METRIC].notna()].copy()
    dropped = total - len(df)
    if df.empty:
        return {"ok": False, "message": f"All {total} rows have NaN {METRIC} (no entry/data)."}

    df["family"] = df["Catalyst_used"].apply(_family)
    if "Benchmark_Matched_pct" in df.columns:
        df["direction"] = np.where(df["Benchmark_Matched_pct"].astype(float) >= 0, "UP tape", "DOWN tape")
    else:
        df["direction"] = "n/a"

    res = {
        "ok": True, "details_path": path, "total": total, "dropped": dropped,
        "by_family":    _table(df, "family"),
        "by_catalyst":  _table(df, "Catalyst_used"),
        "by_direction": _table(df, "direction"),
        "by_exit":      _table(df, "Exit_Reason") if "Exit_Reason" in df.columns else pd.DataFrame(),
    }
    # cross-tab: family x direction (mean alpha, n)
    ct_mean = df.pivot_table(index="family", columns="direction", values=METRIC, aggfunc="mean").round(2)
    ct_n = df.pivot_table(index="family", columns="direction", values=METRIC, aggfunc="count")
    res["cross_mean"] = ct_mean
    res["cross_n"] = ct_n
    return res


def _show(t):
    if t is None or t.empty:
        return "    (none)"
    return t.to_string(index=False)


def _print(res):
    print("\n" + "═" * 74)
    print("  CATALYST × REGIME PARTITION — Phase 2 edge diagnostic (matched alpha)")
    print("═" * 74)
    if not res.get("ok"):
        print("\n⚠️  " + res["message"] + "\n")
        return
    print(f"\n  Source: {os.path.basename(res['details_path'])}")
    print(f"  Trades: {res['total'] - res['dropped']} analyzed ({res['dropped']} dropped — no entry/data)")

    print("\n▸ BY CATALYST FAMILY")
    print(_show(res["by_family"]))
    print("\n▸ BY CATALYST (label)")
    print(_show(res["by_catalyst"]))
    print("\n▸ BY MARKET DIRECTION (benchmark over matched horizon)")
    print(_show(res["by_direction"]))
    print("\n▸ BY EXIT REASON")
    print(_show(res["by_exit"]))
    print("\n▸ CROSS-TAB — mean matched alpha (family × direction)")
    print(res["cross_mean"].to_string() if not res["cross_mean"].empty else "    (none)")
    print("\n▸ CROSS-TAB — trade count")
    print(res["cross_n"].to_string() if not res["cross_n"].empty else "    (none)")

    # Verdict: any family with positive mean alpha AND a non-trivial sample?
    fam = res["by_family"]
    edge = fam[(fam["mean_alpha"] > 0) & (fam["n"] >= 10)]
    print("\n" + "─" * 74)
    if not edge.empty:
        names = ", ".join(f"{r['family']} (n={int(r['n'])}, α {r['mean_alpha']:+.2f}%)" for _, r in edge.iterrows())
        print(f"  ↳ Candidate edge (positive matched alpha, n≥10): {names}")
        print("    Worth a focused OOS test on this family before re-architecting.")
    else:
        print("  ↳ No catalyst family shows positive matched alpha at n≥10.")
        untested = {"POS (positional)", "WYC (wyckoff)", "REV (recovery)"} - set(fam["family"])
        if untested:
            print(f"  ⚠ NOT EXERCISED in this run: {', '.join(sorted(untested))} — "
                  "the core thesis these represent was never tested here. Widen the "
                  "universe/anchors or check why the screener emitted no such picks.")
    print("═" * 74 + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 2 catalyst × regime edge partition.")
    ap.add_argument("--details", default=None, help="validation *_details.csv (default LAST_RUN)")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args(argv)
    res = analyze(args.details)
    _print(res)
    if args.save and res.get("ok"):
        out = os.path.join(RUNS_DIR, "catalyst_regime_partition.csv")
        res["by_family"].assign(_dim="family").rename(columns={"family": "bucket"}).to_csv(out, index=False)
        print(f"📄 Saved family partition → {os.path.relpath(out, _DIR)}\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
