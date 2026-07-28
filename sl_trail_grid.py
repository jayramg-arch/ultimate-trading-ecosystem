"""sl_trail_grid.py — initial SL distance x Chandelier trail multiple, per family.

Jay's question, answered end-to-end: the stop-out forensics showed swing trades are
being cut at 1.14 x ATR while a 1.0-2.0 ATR early dip still carries POSITIVE forward
expectancy (+1.4% to +3.4% from bar 7, ~52-54% win). Expectancy only inverts at 3-4
ATR. That says the swing stop is inside the shakeout zone. This converts that
observation into an actual stop policy by simulating it end-to-end.

PRE-REGISTERED (see the header of the run output; fixed before execution):
  Grid, per family (bold = current live value):
    POS  SL k in {2.5, 3.0, 3.85*, 5.0, 6.5}   trail m in {2.5, 3.5, 4.5*, 6.0, 8.0}
    SWG  SL k in {1.15*, 1.75, 2.5, 3.0, 3.5}  trail m in {1.5, 2.5, 3.5, 4.5*, 6.0}
  Entries, targets and scale-out held CONSTANT. Only the stop varies.
  IS = anchors < 2024-06-01 ; OOS = anchors >= 2024-06-01. IS chooses, OOS confirms.

  ADOPT only if ALL of:
    A. PLATEAU  — the winning cell's grid neighbours also beat control in-sample
                  (a real parameter effect is smooth; an isolated spike is noise)
    B. OOS      — the same cell beats control out-of-sample
    C. STABLE   — bootstrap (B=500) picks that cell, or a neighbour, as winner in
                  >= 25% of resamples, AND the 5th percentile of (best - control)
                  is > 0. This is the multiple-comparison haircut: with 25 cells the
                  best one always looks good; the question is whether it survives
                  resampling.
    D. MEDIAN   — median alpha not worse than control by more than 1.0pp (the 23-Jul
                  trap: widening lifts the mean while converting quick small losses
                  into slow large ones)
  Otherwise: KEEP CURRENT.

BENCHMARK CORRECTNESS (fixed here, and a defect in exit_policy_study.py):
matched-horizon alpha requires the benchmark leg to exit WITH the trade. Using each
trade's recorded Benchmark_Matched_pct for every cell would charge a benchmark matched
to the CONTROL's hold length to cells that hold for very different durations — the
26-Jul horizon bug, reintroduced. Here the benchmark is recomputed per cell from that
cell's own days_held.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DETAILS = "validation_runs/validation_20260728_191035_details.csv"
BENCH = "^CRSLDX"
IS_END = pd.Timestamp("2024-06-01")
COST_PER_LEG = 0.10
BOOT_N = 500

# v2 (28-Jul, after the first pass returned a CORNER solution): the POS grid is widened
# so an optimum can be INTERIOR rather than pinned to the boundary, and the primary
# metric is now the R-MULTIPLE. Per-trade % return is the wrong yardstick for a stop
# study: position size = risk / (k x ATR), so doubling the stop halves the position and
# the same price move yields half the P&L. Measuring % return silently rewards wide
# stops for exposure they never paid for. R = return / initial-risk is sizing-correct.
GRID = {
    "POS": {"sl": [2.0, 2.5, 3.0, 3.85, 5.0, 6.5, 8.0],
            "tr": [2.5, 3.5, 4.5, 6.0, 8.0, 11.0], "cur": (3.85, 4.5)},
    "SWG": {"sl": [0.75, 1.15, 1.5, 1.75, 2.0, 2.5, 3.0],
            "tr": [1.0, 1.5, 2.0, 2.5, 3.5, 4.5], "cur": (1.15, 4.5)},
}
OOS_RETAIN = 0.50   # OOS margin must keep >= this share of the IS margin (was: >0)


def _catalyst_qty(cat):
    c = str(cat or "").upper()
    if c.startswith("SWG-GAP") or c == "SWG-REV":
        return 50, 50
    if c.startswith("SWG"):
        return 33, 33
    return 25, 25


def _sim(win, atr_col, entry, sl, t1, t2, t1q, t2q, trail_m):
    """Control-shaped simulator: Chandelier trail, fixed targets, breakeven after T1,
    same-bar priority SL -> T1 -> T2. Only sl and trail_m vary across the grid."""
    qty, realized = 100.0, 0.0
    trail, hi_close = sl, entry
    hit_t1 = hit_t2 = False
    days = 0
    reason = "Time expiry"
    lows = win["Low"].to_numpy(float)
    highs = win["High"].to_numpy(float)
    closes = win["Close"].to_numpy(float)
    for i in range(len(win)):
        days = i + 1
        a = atr_col[i]
        if np.isfinite(a):
            trail = max(trail, hi_close - a * trail_m)
        if lows[i] <= trail:
            realized += (trail - entry) / entry * 100 * (qty / 100.0)
            qty = 0
            reason = "SL hit" if trail == sl else "Trail SL"
            break
        if t1 and t1q > 0 and highs[i] >= t1 and not hit_t1:
            q = min(qty, float(t1q))
            realized += (t1 - entry) / entry * 100 * (q / 100.0)
            qty -= q
            hit_t1 = True
            trail = max(trail, entry)
        if t2 and t2q > 0 and highs[i] >= t2 and not hit_t2:
            q = min(qty, float(t2q))
            realized += (t2 - entry) / entry * 100 * (q / 100.0)
            qty -= q
            hit_t2 = True
        hi_close = max(hi_close, closes[i])
    if qty > 0:
        realized += (closes[-1] - entry) / entry * 100 * (qty / 100.0)
    realized -= (2 + (1 if hit_t1 else 0) + (1 if hit_t2 else 0)) * COST_PER_LEG
    return realized, days, reason


def main():
    import data_provider as dp

    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = np.where(d["Catalyst_used"].str.upper().str.startswith("SWG"), "SWG", "POS")

    bdf = dp.fetch_ohlcv(BENCH, period="10y", interval="1d")
    bclose = bdf["Close"]
    print(f"benchmark {BENCH}: {len(bdf)} bars")

    recs = []
    for sym, g in d.groupby("Symbol"):
        try:
            f = dp.fetch_ohlcv(sym, period="10y", interval="1d")
        except Exception:
            continue
        if f is None or len(f) < 60:
            continue
        h, l, c = f["High"], f["Low"], f["Close"]
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        for _, r in g.iterrows():
            try:
                cut = f.loc[:r["ts"]]
                if len(cut) < 30:
                    continue
                pos = len(cut) - 1
                a0 = float(atr.iloc[pos])
                if not np.isfinite(a0) or a0 <= 0:
                    continue
                fwd = int(r["forward_days_used"]) if pd.notna(r.get("forward_days_used")) else 30
                win = f.iloc[pos + 1: pos + 1 + fwd]
                if len(win) < 3:
                    continue
                acol = atr.iloc[pos + 1: pos + 1 + fwd].to_numpy(float)
                ep = float(r["Entry_Close"])
                t1 = float(r["T1_price"]) if pd.notna(r.get("T1_price")) else None
                t2 = float(r["T2_price"]) if pd.notna(r.get("T2_price")) else None
                t1q, t2q = _catalyst_qty(r["Catalyst_used"])
                # benchmark bars aligned to this trade's entry date
                bidx = bclose.index.searchsorted(r["ts"])
                recs.append(dict(fam=r["fam"], ts=r["ts"], ep=ep, a0=a0, win=win, acol=acol,
                                 t1=t1, t2=t2, t1q=t1q, t2q=t2q, bidx=bidx))
            except Exception:
                pass
    print(f"trades prepared: {len(recs)}")

    bvals = bclose.to_numpy(float)

    def bench_for(bidx, days):
        j0, j1 = bidx, min(bidx + days, len(bvals) - 1)
        if j0 >= len(bvals) or j1 <= j0:
            return 0.0
        return (bvals[j1] - bvals[j0]) / bvals[j0] * 100.0

    out = {}
    for fam in ("POS", "SWG"):
        sub = [r for r in recs if r["fam"] == fam]
        cells = [(k, m) for k in GRID[fam]["sl"] for m in GRID[fam]["tr"]]
        A = np.full((len(sub), len(cells)), np.nan)      # R-multiple (primary)
        AL = np.full((len(sub), len(cells)), np.nan)     # matched alpha % (secondary)
        for ci, (k, m) in enumerate(cells):
            for ri, r in enumerate(sub):
                sl = r["ep"] - k * r["a0"]
                ret, days, _ = _sim(r["win"], r["acol"], r["ep"], sl,
                                    r["t1"], r["t2"], r["t1q"], r["t2q"], m)
                risk_pct = k * r["a0"] / r["ep"] * 100.0     # what 1R costs, in %
                AL[ri, ci] = ret - bench_for(r["bidx"], days)
                A[ri, ci] = ret / risk_pct if risk_pct > 0 else np.nan
        out[fam] = (sub, cells, A, AL)
        print(f"  {fam}: {len(sub)} trades x {len(cells)} cells simulated")

    for fam in ("POS", "SWG"):
        sub, cells, A, AL = out[fam]
        ts = np.array([r["ts"] for r in sub])
        is_m, oos_m = ts < IS_END, ts >= IS_END
        cur = GRID[fam]["cur"]
        ci_cur = cells.index(cur)
        sls, trs = GRID[fam]["sl"], GRID[fam]["tr"]

        print(f"\n{'='*78}\n{fam}  —  IN-SAMPLE mean alpha (rows = SL xATR, cols = trail xATR)")
        print("        " + "".join(f"{m:>8.1f}" for m in trs))
        for k in sls:
            row = "".join(f"{A[is_m, cells.index((k, m))].mean():8.3f}" for m in trs)
            tag = "  <-- current SL" if k == cur[0] else ""
            print(f"  {k:5.2f} {row}{tag}")
        base_is = A[is_m, ci_cur].mean()
        base_oos = A[oos_m, ci_cur].mean()
        base_med = np.median(A[is_m, ci_cur])
        print(f"  current cell {cur}: IS {base_is:+.3f}R  OOS {base_oos:+.3f}R  "
              f"(alpha IS {AL[is_m, ci_cur].mean():+.2f}%)  n_is={is_m.sum()} n_oos={oos_m.sum()}")

        means_is = np.array([A[is_m, c].mean() for c in range(len(cells))])
        best = int(np.argmax(means_is))
        bk, bm = cells[best]
        # Gate E: a winner sitting on the grid boundary is not an optimum — it is the
        # edge of what was searched, and the true maximum lies outside. The first pass
        # returned exactly that (SL 6.5 x trail 8.0, both maxima) and I wrongly called
        # it ADOPT. An edge winner now fails outright.
        edge = (bk in (sls[0], sls[-1])) or (bm in (trs[0], trs[-1]))
        print(f"\n  best IS cell: SL {bk} x trail {bm}  ->  {means_is[best]:+.3f}R  "
              f"({means_is[best]-base_is:+.3f}R vs current)   alpha {AL[is_m, best].mean():+.2f}%"
              + ("   [!] ON GRID EDGE — optimum may lie outside" if edge else "   [interior]"))

        # A. plateau — neighbours in the grid must also beat control
        i_k, i_m = sls.index(bk), trs.index(bm)
        neigh = []
        for dk, dm in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nk, nm = i_k + dk, i_m + dm
            if 0 <= nk < len(sls) and 0 <= nm < len(trs):
                neigh.append(means_is[cells.index((sls[nk], trs[nm]))])
        plateau = all(n > base_is for n in neigh) if neigh else False
        print(f"  A. plateau  : {sum(n > base_is for n in neigh)}/{len(neigh)} neighbours beat control -> {'PASS' if plateau else 'FAIL'}")

        # B. OOS
        is_gain = means_is[best] - base_is
        oos_gain = A[oos_m, best].mean() - base_oos
        need = OOS_RETAIN * is_gain
        okB = (oos_gain > 0) and (oos_gain >= need)
        print(f"  B. OOS      : {A[oos_m, best].mean():+.3f}R vs {base_oos:+.3f}R ({oos_gain:+.3f}R); "
              f"needs >= {need:+.3f}R (50% of IS {is_gain:+.3f}R) -> {'PASS' if okB else 'FAIL'}")

        # C. bootstrap stability + haircut
        rng = np.random.default_rng(7)
        idx_is = np.where(is_m)[0]
        wins, gains = [], []
        for _ in range(BOOT_N):
            bs = rng.choice(idx_is, size=len(idx_is), replace=True)
            mm = A[bs].mean(axis=0)
            w = int(np.argmax(mm))
            wins.append(w)
            gains.append(mm[w] - mm[ci_cur])
        wc = pd.Series(wins).value_counts()
        share_best = wc.get(best, 0) / BOOT_N
        neigh_ids = {cells.index((sls[i_k + dk], trs[i_m + dm]))
                     for dk, dm in ((-1, 0), (1, 0), (0, -1), (0, 1), (0, 0))
                     if 0 <= i_k + dk < len(sls) and 0 <= i_m + dm < len(trs)}
        share_neigh = sum(wc.get(i, 0) for i in neigh_ids) / BOOT_N
        p5 = float(np.percentile(gains, 5))
        stable = (share_neigh >= 0.25) and (p5 > 0)
        print(f"  C. stability: best cell wins {share_best*100:.1f}% of bootstraps, "
              f"best-or-neighbour {share_neigh*100:.1f}%; 5th pct of (best-control) {p5:+.3f}R -> {'PASS' if stable else 'FAIL'}")

        # D. median
        med_gain = np.median(A[is_m, best]) - base_med
        print(f"  D. median   : {np.median(A[is_m, best]):+.3f}R vs {base_med:+.3f}R ({med_gain:+.3f}R) -> {'PASS' if med_gain >= -0.25 else 'FAIL'}")
        print(f"  E. interior : {'PASS' if not edge else 'FAIL — corner/edge solution, grid mis-specified'}")

        verdict = "ADOPT" if (plateau and okB and stable and med_gain >= -0.25 and not edge) else "KEEP CURRENT"
        print(f"\n  >>> {fam}: {verdict}" + (f"  (SL {bk} xATR, trail {bm} xATR)" if verdict == "ADOPT" else ""))


if __name__ == "__main__":
    main()
