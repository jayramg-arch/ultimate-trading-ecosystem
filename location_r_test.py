"""location_r_test.py — does LOCATION buy better risk geometry?

Implements docs/PREREG_location_R.md EXACTLY. Written after the pre-registration, before
any stop was placed. Not Jay's trades: Stage-2 Nifty 500 name-dates from the panel-row
audit's sample (validation_runs/_panel_rows.parquet), every level point-in-time.

WHY THREE NUMBERS ARE ENOUGH. The trade is: enter at the close, exit at the stop the first
time a low touches it (fill at the stop), else at the close N bars later (120 POSITIONAL,
60 SWING). So for ANY stop
distance k (in ATR) the result depends only on
    mdd   = max over the next N bars of (entry - low) / ATR   -> hit iff mdd >= k
    ret   = % return close-to-close over N bars                -> the exit if not hit
    atrp  = ATR as % of entry                                   -> converts k to risk %
which lets H2 evaluate 20 permuted distances per trade exactly, without re-walking paths.

MODES:  --build   compute levels + paths, print coverage
        --placebo labels / distances permuted; prints the MDE per cell
        --run     the single real run (marker-guarded)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import panel_row_audit as A

OUT = A.OUT
DATA = os.path.join(OUT, "_location_r.parquet")
MARKER = os.path.join(OUT, "_location_r_REAL_RUN_DONE.json")

COST_RT = 0.20            # 0.10% x 2 legs
BUF_ZONE, BUF_LINE = 0.10, 0.25
# Amendment 1 (24-Sep-2026): POSITIONAL is primary, SWING is the option. Jay does not day trade.
STYLES = {
    "POSITIONAL": dict(hold=120, mae=40, dmin=1.0, dmax=6.0, purge=120),
    "SWING":      dict(hold=60,  mae=20, dmin=0.25, dmax=4.0, purge=60),
}
H = 60                    # a sample date needs at least the SWING hold of forward bars
N_PERM = 20
H1_BAR, H2_BAR, H2_MED = -0.15, 0.10, -0.10
MIN_N = 100
ROWS = ["L1_zone_d", "L2_zone_w", "L3_near_sr", "L4_near_avwap", "L5_at_vp"]


def symbol_levels(sym: str, dates: list) -> list:
    import data_provider as dp
    import zone_engine as ze
    try:
        d = dp.fetch_ohlcv(sym, period="5y", interval="1d")
    except Exception:
        return []
    if d is None or len(d) < A.MIN_HIST + H:
        return []
    d = d.copy()
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    d = d[~d.index.duplicated()]
    c, lo = d["Close"], d["Low"]
    tr = pd.concat([d["High"] - lo, (d["High"] - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    wk_all = A._weekly(d)
    idx = d.index
    out = []
    for t in dates:
        pos = idx.searchsorted(t, side="right") - 1
        if pos < A.MIN_HIST or idx[pos] != t or pos + H >= len(d):
            continue
        px, a = float(c.iloc[pos]), float(atr.iloc[pos])
        if not (a > 0):
            continue
        s = d.iloc[:pos + 1]
        rec = {"Symbol": sym, "date": t, "atrp": a / px * 100}
        for st, sp in STYLES.items():
            hb = sp["hold"]
            if pos + hb < len(d):
                fl = lo.iloc[pos + 1:pos + 1 + hb].values
                rec[f"mae_{st}"] = max(0.0, (px - fl[:sp["mae"]].min()) / a)
                rec[f"mdd_{st}"] = max(0.0, (px - fl.min()) / a)
                rec[f"ret_{st}"] = (float(c.iloc[pos + hb]) / px - 1) * 100
            else:
                rec[f"mae_{st}"] = rec[f"mdd_{st}"] = rec[f"ret_{st}"] = np.nan

        def put(row, at, level, buf):
            rec[f"{row}_at"] = float(bool(at))
            # RAW distance; each style applies its own valid range at analysis time
            rec[f"{row}_dist"] = (px - (level - buf * a)) / a if (at and level is not None) else np.nan

        try:
            z = ze.zone_support(s, "D")
            put("L1_zone_d", z.get("at_support"), z.get("distal"), BUF_ZONE)
        except Exception:
            rec["L1_zone_d_at"], rec["L1_zone_d_dist"] = np.nan, np.nan
        try:
            wk_lab = t.to_period("W-FRI").end_time.normalize()
            w = wk_all[wk_all.index < wk_lab]
            z = ze.zone_support(w, "W", price=px)
            put("L2_zone_w", z.get("at_support"), z.get("distal"), BUF_ZONE)
        except Exception:
            rec["L2_zone_w_at"], rec["L2_zone_w_dist"] = np.nan, np.nan
        try:
            r = ze.sr_support(s, "D")
            put("L3_near_sr", r.get("near_sr"), r.get("level"), BUF_LINE)
        except Exception:
            rec["L3_near_sr_at"], rec["L3_near_sr_dist"] = np.nan, np.nan
        try:
            r = ze.avwap_support(s)
            put("L4_near_avwap", r.get("near_avwap"), r.get("nearest"), BUF_LINE)
        except Exception:
            rec["L4_near_avwap_at"], rec["L4_near_avwap_dist"] = np.nan, np.nan
        try:
            r = ze.vp_support(s)
            cands = []
            if r.get("near_vp_poc") and r.get("vp_poc") is not None and r["vp_poc"] <= px:
                cands.append(r["vp_poc"])
            if r.get("near_vp_val") and r.get("vp_val") is not None and r["vp_val"] <= px:
                cands.append(r["vp_val"])
            put("L5_at_vp", bool(r.get("at_vp_support")), max(cands) if cands else None, BUF_LINE)
        except Exception:
            rec["L5_at_vp_at"], rec["L5_at_vp_dist"] = np.nan, np.nan
        out.append(rec)
    return out


def build(workers=8):
    P = pd.read_parquet(A.PANEL)
    s2 = P[P["C1_stage2"] == 1]
    jobs = s2.groupby("Symbol")["date"].apply(list).to_dict()
    print(f"Stage-2 name-dates {len(s2)} across {len(jobs)} symbols")
    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(symbol_levels, s, ds): s for s, ds in jobs.items()}
        for f in as_completed(futs):
            try:
                rows.extend(f.result())
            except Exception as e:
                print("  fail", futs[f], e)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)}", flush=True)
    D = pd.DataFrame(rows)
    D.to_parquet(DATA)
    print(f"\nrows {len(D)}")
    for st, sp in STYLES.items():
        print(f"  -- {st}: dates with a {sp['hold']}-bar path {D[f'ret_{st}'].notna().mean()*100:.1f}%")
        for r in ROWS:
            at = D[f"{r}_at"] == 1
            dd = D.loc[at, f"{r}_dist"]
            ok = dd.between(sp["dmin"], sp["dmax"])
            print(f"     {r:14} at {at.mean()*100:5.1f}%   valid stop {ok.mean()*100:5.1f}%"
                  f"   median dist {dd.median():.2f} ATR")


# ── statistics ───────────────────────────────────────────────────────────────
def r_at(k, mdd, ret, atrp):
    """R for a stop k ATR below entry (vectorised)."""
    risk = k * atrp
    hit = mdd >= k
    gross = np.where(hit, -risk, ret)
    return (gross - COST_RT) / risk


def _boot_ratio(sums: pd.Series, cnts: pd.Series, rng):
    """Date-block bootstrap of sum/count, circular blocks of A.BLOCK dates."""
    s, n = sums.values, cnts.values
    L = len(s)
    nb = int(np.ceil(L / A.BLOCK))
    st = rng.integers(0, L, size=(A.N_BOOT, nb))
    ix = ((st[:, :, None] + np.arange(A.BLOCK)[None, None, :]) % L).reshape(A.N_BOOT, -1)[:, :L]
    return s[ix].sum(1) / n[ix].sum(1)


def split_dates_style(P, purge_bars):
    ds = sorted(P["date"].unique())
    n_is = int(round(len(ds) * A.IS_FRAC))
    purge = int(np.ceil(purge_bars / A.STEP))
    return set(ds[:max(0, n_is - purge)]), set(ds[n_is:])


def h1_cell(D, row, dates, rng, st, permute=False):
    x, n_at = {}, 0
    sub = D[D["date"].isin(dates) & D[f"mae_{st}"].notna()]
    for t, g in sub.groupby("date"):
        lab = g[f"{row}_at"].values
        if permute:
            lab = rng.permutation(lab)
        a, b = g[f"mae_{st}"].values[lab == 1], g[f"mae_{st}"].values[lab == 0]
        n_at += len(a)
        if len(a) >= 5 and len(b) >= 5:
            x[t] = np.median(a) - np.median(b)
    s = pd.Series(x).sort_index()
    if len(s) < A.BLOCK * 2:
        return np.nan, np.nan, np.nan, n_at
    boot = _boot_ratio(s, pd.Series(1.0, index=s.index), rng)
    p = float(np.mean((boot - s.mean()) <= s.mean()))      # one-sided, H: mean < 0
    return s.mean(), p, boot.std(), n_at


def h2_cell(D, row, dates, rng, st, placebo=False):
    sp = STYLES[st]
    g = D[D["date"].isin(dates) & (D[f"{row}_at"] == 1) & D[f"ret_{st}"].notna()
          & D[f"{row}_dist"].between(sp["dmin"], sp["dmax"])].copy()
    n = len(g)
    if n < 10:
        return dict(n=n, mean=np.nan, med=np.nan, p=np.nan, se=np.nan)
    k = g[f"{row}_dist"].values
    if placebo:
        k = rng.permutation(k)
    mdd, ret, atrp = g[f"mdd_{st}"].values, g[f"ret_{st}"].values, g["atrp"].values
    r_s = r_at(k, mdd, ret, atrp)
    r_p = np.mean([r_at(rng.permutation(k), mdd, ret, atrp) for _ in range(N_PERM)], axis=0)
    diff = r_s - r_p
    g["diff"] = diff
    sums, cnts = g.groupby("date")["diff"].sum(), g.groupby("date")["diff"].count().astype(float)
    obs = diff.mean()
    if len(sums) < A.BLOCK * 2:
        return dict(n=n, mean=obs, med=float(np.median(r_s) - np.median(r_p)), p=np.nan, se=np.nan)
    boot = _boot_ratio(sums, cnts, rng)
    p = float(np.mean((boot - obs) >= obs))                  # one-sided, H: mean > 0
    return dict(n=n, mean=obs, med=float(np.median(r_s) - np.median(r_p)), p=p, se=boot.std(),
                r_struct=r_s.mean(), r_perm=r_p.mean(), hit=(mdd >= k).mean(),
                dist=float(np.median(k)))


def analyse_style(D, st, label, rng, placebo=False):
    P = pd.read_parquet(A.PANEL)
    IS, OOS = split_dates_style(P, STYLES[st]["purge"])
    sp = STYLES[st]
    print(f"\n==== {label} · {st} (hold {sp['hold']}, MAE {sp['mae']}, stop {sp['dmin']}-{sp['dmax']} ATR) ====")
    print(f"     IS dates {len(IS)}  OOS dates {len(OOS)}")
    cells, ps = [], {}
    for row in ROWS:
        h1 = {w: h1_cell(D, row, W, rng, st, permute=placebo) for w, W in (("IS", IS), ("OOS", OOS))}
        h2 = {w: h2_cell(D, row, W, rng, st, placebo=placebo) for w, W in (("IS", IS), ("OOS", OOS))}
        thin1 = min(h1["IS"][3], h1["OOS"][3]) < MIN_N
        size1 = all(h1[w][0] == h1[w][0] and h1[w][0] <= H1_BAR for w in ("IS", "OOS"))
        mde1 = max(2.8 * h1[w][2] for w in ("IS", "OOS")) if all(h1[w][2] == h1[w][2] for w in ("IS", "OOS")) else np.nan
        cells.append(dict(style=st, H="H1", row=row, IS=h1["IS"][0], OOS=h1["OOS"][0],
                          n_is=h1["IS"][3], n_oos=h1["OOS"][3], p=max(h1["IS"][1], h1["OOS"][1]),
                          size=size1, thin=thin1, mde=mde1, bar=abs(H1_BAR)))
        thin2 = min(h2["IS"]["n"], h2["OOS"]["n"]) < MIN_N
        size2 = all(h2[w]["mean"] == h2[w]["mean"] and h2[w]["mean"] >= H2_BAR and h2[w]["med"] >= H2_MED
                    for w in ("IS", "OOS"))
        mde2 = max(2.8 * h2[w]["se"] for w in ("IS", "OOS")) if all(h2[w]["se"] == h2[w]["se"] for w in ("IS", "OOS")) else np.nan
        c2 = dict(style=st, H="H2", row=row, IS=h2["IS"]["mean"], OOS=h2["OOS"]["mean"],
                  n_is=h2["IS"]["n"], n_oos=h2["OOS"]["n"], p=max(h2["IS"]["p"], h2["OOS"]["p"]),
                  size=size2, thin=thin2, mde=mde2, bar=H2_BAR,
                  med_is=h2["IS"]["med"], med_oos=h2["OOS"]["med"])
        for w in ("IS", "OOS"):
            for kk in ("r_struct", "r_perm", "hit", "dist"):
                c2[f"{kk}_{w}"] = h2[w].get(kk)
        cells.append(c2)
    for i, c in enumerate(cells):
        if not c["thin"] and c["p"] == c["p"]:
            ps[i] = c["p"]
    hp = A.holm(ps)
    for i, c in enumerate(cells):
        c["holm"] = bool(hp.get(i, False))
        passed = c["size"] and c["holm"]
        c["verdict"] = ("THIN" if c["thin"] else
                        "PASS" if passed else
                        "UNDERPOWERED" if (c["mde"] != c["mde"] or c["mde"] > c["bar"]) else
                        "suggestive" if (c["size"] or c["holm"]) else "FAIL")
    print(f"  {'':3}{'row':14}{'IS':>9}{'OOS':>9}{'n IS/OOS':>13}{'p':>7}{'MDE':>7}  verdict")
    for c in cells:
        u = "A" if c["H"] == "H1" else "R"
        extra = ""
        if c["H"] == "H2" and c.get("r_struct_IS") is not None and c.get("r_struct_OOS") is not None:
            extra = (f"   R struct/perm IS {c['r_struct_IS']:+.2f}/{c['r_perm_IS']:+.2f}"
                     f" OOS {c['r_struct_OOS']:+.2f}/{c['r_perm_OOS']:+.2f}"
                     f"  hit {c['hit_IS']*100:.0f}/{c['hit_OOS']*100:.0f}%  dist {c['dist_IS']:.2f} ATR"
                     f"  med {c['med_is']:+.2f}/{c['med_oos']:+.2f}")
        print(f"  {c['H']} {c['row']:14}{c['IS']:+8.3f}{u}{c['OOS']:+8.3f}{u}"
              f"{c['n_is']:>7}/{c['n_oos']:<5}{c['p']:7.3f}{c['mde']:7.3f}  {c['verdict']}{extra}")
    return cells


def analyse(D, label, rng, placebo=False):
    out = []
    for st in STYLES:                     # POSITIONAL first: it is the primary family
        out += analyse_style(D, st, label, rng, placebo=placebo)
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--placebo", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rng = np.random.default_rng(23)
    if a.build:
        build(a.workers)
        return
    D = pd.read_parquet(DATA)
    if a.placebo:
        analyse(D, "PLACEBO (labels / distances permuted — any pass is a bug)", rng, placebo=True)
        return
    if os.path.exists(MARKER):
        sys.exit(f"REFUSED: the real run has already been made ({MARKER}).")
    R = analyse(D, "REAL RUN", rng)
    R.to_csv(os.path.join(OUT, "_location_r_result.csv"), index=False)
    json.dump({"at": datetime.now().isoformat()}, open(MARKER, "w"))
    print("\nsaved validation_runs/_location_r_result.csv; marker written.")


if __name__ == "__main__":
    main()
