#!/usr/bin/env python3
"""Should the low-RV pullback branch widen beyond `z_inDZ`?

THE QUESTION (Jay, 14 Aug 2026). S4's `pb_aware` drops the volume floor from
1.00 to 0.50 only when a contraction pattern fires with no expansion pattern AND
price is INSIDE a demand zone. On TITAN the branch never engaged because the
engine read "between zones", so RV 0.61 vetoed. Jay: a name pulling back to a
rising EMA20 or onto a tested D/W level is a real pullback too - widen it.

That is plausible and it is not free: widening admits a larger, lower-volume
population, and the last RV idea I proposed (invert the test so DRY beats WET)
was REFUTED by exactly this kind of measurement - the dry bucket returned +0.84
against +1.30 for RV 1.0-1.5. So measure before shipping.

METHOD
  Universe : nifty500 daily bars.
  Context  : PULLBACK = above a rising 200-DMA, ext <= 1.0 ATR from EMA20, not a
             new 20-day high (S4's own at-value definition).
  Split    : each qualifying bar is labelled by its LOCATION -
               DZ    - inside/near a demand zone      (zone_engine, the current gate)
               EMA20 - within `ema_band` ATR of EMA20 (the proposed widening)
               LEVEL - near an S/R level              (the proposed widening)
               NONE  - none of the above
             crossed with RV < 1.0 (what the floor rejects) vs RV >= 1.0.
  Outcome  : matched-horizon alpha - forward return minus the benchmark over the
             SAME window, the convention this repo settled on.
  Stats    : block-bootstrap over SYMBOLS. With a 20-day window on daily bars,
             consecutive rows share ~95% of their outcome window, so a row-level
             bootstrap claims precision the data does not have.

WHAT WOULD SHIP IT
  The widened cells (EMA20/LEVEL at RV < 1.0) must return alpha comparable to the
  DZ cell at RV < 1.0 - i.e. the location, not the zone specifically, is what
  makes a dry bar tradeable. If they are materially worse, `z_inDZ` is doing real
  work and stays.

    python pullback_location_ab.py                  # 250 names, 3y, 20d horizon
    python pullback_location_ab.py --limit 120 --horizon 10
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_DIR = os.path.dirname(os.path.abspath(__file__))
BENCH = "^CRSLDX"


def _indicators(df):
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["c"] = c
    out["ema20"] = c.ewm(span=20, adjust=False).mean()
    out["sma200"] = c.rolling(200).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["atr"] = tr.rolling(14).mean()
    out["rv"] = v / v.rolling(50).mean().shift(1)
    out["hi20"] = h.rolling(20).max()
    return out


def _label_locations(df_d, ind, idx_positions, ema_band, lvl_band):
    """LOCATION label per bar position, using the SAME engines the gate uses.

    zone_engine is called ONCE per symbol on the full frame and the resulting
    zones are tested against each bar, rather than re-detecting per bar - the
    zones are structural, and re-running detection 700 times per symbol would
    make this study unrunnable without changing the answer materially.
    """
    labels = {}
    zones, levels = [], []
    try:
        import zone_engine as ze
        for tf in ("D", "W"):
            try:
                zones += [z for z in (ze.detect_zones(df_d, tf=tf) or [])
                          if bool(getattr(z, "is_demand", False))]
            except Exception:
                pass
        try:
            levels = ze.detect_sr_levels(df_d, tf="D") or []
        except Exception:
            levels = []
    except Exception:
        pass

    def _zone_hit(px):
        for z in zones:
            try:
                prox = float(getattr(z, "proximal", np.nan))
                dist = float(getattr(z, "distal", np.nan))
            except Exception:
                continue
            if np.isnan(prox) or np.isnan(dist):
                continue
            lo, hi = min(prox, dist), max(prox, dist)
            w = max(hi - lo, 1e-9)
            if lo - 0.5 * w <= px <= hi + 0.5 * w:      # zone_engine's TOUCH_TOL_WIDTH
                return True
        return False

    def _lvl_hit(px, atr):
        for lv in levels:
            try:
                v = float(lv.get("level", lv.get("price", np.nan)))   # detect_sr_levels -> list[dict]
            except Exception:
                continue
            if not np.isnan(v) and abs(px - v) <= lvl_band * atr:
                return True
        return False

    for i in idx_positions:
        px = float(ind["c"].iloc[i])
        atr = float(ind["atr"].iloc[i])
        ema = float(ind["ema20"].iloc[i])
        if _zone_hit(px):
            labels[i] = "DZ"
        elif atr > 0 and abs(px - ema) <= ema_band * atr:
            labels[i] = "EMA20"
        elif atr > 0 and _lvl_hit(px, atr):
            labels[i] = "LEVEL"
        else:
            labels[i] = "NONE"
    return labels


def run(limit, years, horizon, ema_band, lvl_band):
    import json
    import bull_screener as bs
    import data_provider as dp

    syms = [s.replace(".NS", "") for s in
            json.load(open(os.path.join(_DIR, "nifty500_symbols.json")))]
    if limit:
        syms = syms[:limit]

    bench = bs._flatten_cols(dp.fetch_ohlcv(BENCH, period=f"{years}y", interval="1d", use_cache=True))
    if bench is None or bench.empty:
        print("benchmark unavailable — cannot compute alpha")
        return pd.DataFrame()
    bc = bench["Close"]
    bfwd = (bc.shift(-horizon) / bc - 1.0) * 100.0

    rows = []
    for n, s in enumerate(syms, 1):
        if n % 25 == 0:
            print(f"  {n}/{len(syms)}…", flush=True)
        try:
            df = bs._flatten_cols(dp.fetch_ohlcv(s, period=f"{years}y", interval="1d", use_cache=True))
            if df is None or len(df) < 260:
                continue
            ind = _indicators(df)
            fwd = (ind["c"].shift(-horizon) / ind["c"] - 1.0) * 100.0
            ext = (ind["c"] - ind["ema20"]) / ind["atr"]
            ctx = ((ind["c"] > ind["sma200"])
                   & (ind["sma200"] > ind["sma200"].shift(22))
                   & (ext.abs() <= 1.0)
                   & (df["High"] < ind["hi20"].shift(1)))
            pos = [i for i, ok in enumerate(ctx.values) if ok and not np.isnan(fwd.values[i])]
            if not pos:
                continue
            labels = _label_locations(df, ind, pos, ema_band, lvl_band)
            b = bfwd.reindex(ind.index).values
            for i in pos:
                if np.isnan(b[i]):
                    continue
                rows.append({"sym": s, "zone_loc": labels.get(i, "NONE"),
                             "rv": float(ind["rv"].iloc[i]),
                             "alpha": float(fwd.values[i] - b[i])})
        except Exception:
            continue

    return pd.DataFrame(rows).dropna()


def report(d, horizon, n_boot=2000):
    print(f"\n  {len(d):,} at-value bars · horizon {horizon} sessions · "
          f"alpha = fwd return − benchmark over the SAME window\n")
    print(f"  {'location':<9}{'RV band':<12}{'n':>8}{'mean α':>9}{'med α':>8}{'win%':>7}")
    print("  " + "-" * 55)
    for loc in ("DZ", "EMA20", "LEVEL", "NONE"):
        for lab, m in (("RV < 1.0", d[(d.zone_loc == loc) & (d.rv < 1.0)]),
                       ("RV >= 1.0", d[(d.zone_loc == loc) & (d.rv >= 1.0)])):
            if len(m) < 40:
                print(f"  {loc:<9}{lab:<12}{len(m):>8}   (too few)")
                continue
            print(f"  {loc:<9}{lab:<12}{len(m):>8}{m.alpha.mean():>9.2f}"
                  f"{m.alpha.median():>8.2f}{(m.alpha > 0).mean() * 100:>6.0f}%")

    print("\n  THE SHIPPING TEST — do the WIDENED dry cells match the DZ dry cell?")
    base = d[(d.zone_loc == "DZ") & (d.rv < 1.0)]
    if len(base) < 40:
        print("    DZ/dry too thin to use as a baseline — inconclusive.")
        return
    print(f"    DZ    · RV<1.0 (current gate) : n={len(base):>6}  mean α {base.alpha.mean():+.2f}")
    rng = np.random.default_rng(11)
    syms_u = d["sym"].unique()
    for loc in ("EMA20", "LEVEL"):
        m = d[(d.zone_loc == loc) & (d.rv < 1.0)]
        if len(m) < 40:
            print(f"    {loc:<6}· RV<1.0 (proposed)     : n={len(m):>6}  (too few)")
            continue
        diff = m.alpha.mean() - base.alpha.mean()
        boots = []
        for _ in range(n_boot):
            pick = set(rng.choice(syms_u, len(syms_u), replace=True))
            a = d[(d.zone_loc == loc) & (d.rv < 1.0) & (d.sym.isin(pick))].alpha
            bq = d[(d.zone_loc == "DZ") & (d.rv < 1.0) & (d.sym.isin(pick))].alpha
            if len(a) > 25 and len(bq) > 25:
                boots.append(a.mean() - bq.mean())
        ci = np.percentile(boots, [2.5, 97.5]) if boots else (np.nan, np.nan)
        verdict = ("comparable — widening SUPPORTED" if ci[0] > -0.5
                   else "materially worse — z_inDZ is doing real work")
        print(f"    {loc:<6}· RV<1.0 (proposed)     : n={len(m):>6}  mean α {m.alpha.mean():+.2f}"
              f"  vs DZ {diff:+.2f}pp  CI95 [{ci[0]:+.2f}, {ci[1]:+.2f}]  → {verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--ema-band", type=float, default=0.5, dest="ema_band",
                    help="ATR multiple counting as 'at the EMA20'")
    ap.add_argument("--lvl-band", type=float, default=0.5, dest="lvl_band",
                    help="ATR multiple counting as 'at an S/R level'")
    a = ap.parse_args()
    d = run(a.limit, a.years, a.horizon, a.ema_band, a.lvl_band)
    if d.empty:
        print("no qualifying bars")
        return 1
    report(d, a.horizon)
    out = os.path.join(_DIR, "validation_runs", f"pullback_location_ab_h{a.horizon}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    d.to_csv(out, index=False)
    print(f"\n  rows → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
