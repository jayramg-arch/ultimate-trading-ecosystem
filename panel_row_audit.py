"""panel_row_audit.py — which S4 panel rows deserve a confluence vote?

Implements docs/PREREG_panel_row_audit.md EXACTLY. Written after the pre-registration,
before any row was computed on the sample.

NOT Jay's trades (his instruction, 24-Sep-2026): the sample is the Nifty 500 itself at
fixed biweekly dates, every row rebuilt point-in-time from the production engines.

MODES (the order is the protocol):
  --build     compute every row + Y60/Y20 for every name-date, cache to parquet. Prints
              coverage only (no ICs) — the plumbing check.
  --placebo   Y60 permuted across names within each date; every IC is noise by
              construction. Any passing row = a bug.
  --run       the single real run. Refuses a second time (marker file).
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

_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_DIR, "validation_runs")
PANEL = os.path.join(OUT, "_panel_rows.parquet")
MARKER = os.path.join(OUT, "_panel_audit_REAL_RUN_DONE.json")

MIN_HIST = 420
STEP = 10
H, H2 = 60, 20
IS_FRAC, PURGE_BARS = 0.6, 60
IC_BAR = 0.02
ALPHA_FW = 0.10
N_BOOT = 5000
BLOCK = 6
MIN_NAMES = 20
CLUSTER_RHO = 0.6

ROWS = ["C1_stage2", "C2_above200", "C3_off52", "C4_minervini", "C5_rs_ratio", "C6_rs_mom",
        "C7_rsi14", "C8_adx_di", "L1_zone_d", "L2_zone_w", "L3_near_sr", "L4_near_avwap",
        "L5_at_vp", "L6_ema_ext", "L7_room", "X1_pa_sigma", "X2_bar_ok", "X3_rv", "X4_arrival"]
# +1 = panel reads higher as favourable, -1 = lower, 0 = not declared
FAV = {"C1_stage2": 1, "C2_above200": 1, "C3_off52": 1, "C4_minervini": 1, "C5_rs_ratio": 1,
       "C6_rs_mom": 1, "C7_rsi14": 0, "C8_adx_di": 1, "L1_zone_d": 1, "L2_zone_w": 1,
       "L3_near_sr": 1, "L4_near_avwap": 1, "L5_at_vp": 1, "L6_ema_ext": -1, "L7_room": 1,
       "X1_pa_sigma": 1, "X2_bar_ok": 1, "X3_rv": 1, "X4_arrival": 1}
CONTEXT = [r for r in ROWS if r.startswith("C")]


# ── indicators ───────────────────────────────────────────────────────────────
def _weekly(d: pd.DataFrame) -> pd.DataFrame:
    w = d.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                 "Close": "last", "Volume": "sum"}).dropna()
    return w


def _rsi(c, n=14):
    dlt = c.diff()
    g = dlt.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    ls = (-dlt.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / ls.replace(0, np.nan))


def _adx_di(d, n=14):
    h, l, c = d["High"], d["Low"], d["Close"]
    up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pd.Series(pdm, index=d.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    ndi = 100 * pd.Series(ndm, index=d.index).ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    return adx * np.sign(pdi - ndi)


def symbol_rows(sym: str, bench_close: pd.Series, dates: list) -> list:
    """Every row for one symbol at every sample date — point-in-time (slice to t)."""
    import data_provider as dp
    import zone_engine as ze
    import pa_patterns as pp
    import bull_screener as bs
    import rrg_engine as rr

    try:
        d = dp.fetch_ohlcv(sym, period="5y", interval="1d")
    except Exception:
        return []
    if d is None or len(d) < MIN_HIST + H:
        return []
    d = d.copy()
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    d = d[["Open", "High", "Low", "Close", "Volume"]].dropna()
    d = d[~d.index.duplicated()]
    c = d["Close"]
    # causal full-series indicators (rolling / ewm only look back)
    sma50, sma150, sma200 = c.rolling(50).mean(), c.rolling(150).mean(), c.rolling(200).mean()
    hi52, lo52 = d["High"].rolling(252).max(), d["Low"].rolling(252).min()
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - c.shift()).abs(),
                    (d["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    rsi = _rsi(c)
    adxdi = _adx_di(d)
    v50p = d["Volume"].rolling(50).mean().shift(1)
    wk_all = _weekly(d)
    bw_all = _weekly(pd.DataFrame({"Open": bench_close, "High": bench_close, "Low": bench_close,
                                   "Close": bench_close, "Volume": 0.0}))

    out = []
    idx = d.index
    for t in dates:
        pos = idx.searchsorted(t, side="right") - 1
        if pos < MIN_HIST or idx[pos] != t or pos + H >= len(d):
            continue
        s = d.iloc[:pos + 1]
        px = float(c.iloc[pos])
        a = float(atr.iloc[pos])
        if not (a > 0):
            continue
        rec = {"Symbol": sym, "date": t}
        # outcomes (benchmark on the same calendar dates)
        try:
            f60, f20 = idx[pos + H], idx[pos + H2]
            b0 = float(bench_close.loc[:t].iloc[-1])
            rec["Y60"] = (c.iloc[pos + H] / px - 1) * 100 - (float(bench_close.loc[:f60].iloc[-1]) / b0 - 1) * 100
            rec["Y20"] = (c.iloc[pos + H2] / px - 1) * 100 - (float(bench_close.loc[:f20].iloc[-1]) / b0 - 1) * 100
        except Exception:
            continue
        # weekly: completed weeks only (the week containing t is dropped)
        wk_lab = t.to_period("W-FRI").end_time.normalize()
        w = wk_all[wk_all.index < wk_lab]
        bw = bw_all[bw_all.index < wk_lab]
        try:
            st, _ = bs.compute_weekly_stage_and_wks(w)
            rec["C1_stage2"] = float(int(st.iloc[-1]) == 2) if len(w) >= 35 else np.nan
        except Exception:
            rec["C1_stage2"] = np.nan
        rec["C2_above200"] = float(px > sma200.iloc[pos])
        rec["C3_off52"] = px / float(hi52.iloc[pos]) - 1
        legs = [px > sma150.iloc[pos] > sma200.iloc[pos],
                sma200.iloc[pos] > sma200.iloc[pos - 20],
                sma50.iloc[pos] > sma150.iloc[pos] and sma50.iloc[pos] > sma200.iloc[pos],
                px > sma50.iloc[pos],
                px >= 1.30 * lo52.iloc[pos],
                px >= 0.75 * hi52.iloc[pos],
                px > sma200.iloc[pos]]
        rec["C4_minervini"] = float(sum(bool(x) for x in legs))
        try:
            j = rr.calculate_jdk_rrg(w["Close"], bw["Close"], mode="strike_cal")
            rec["C5_rs_ratio"] = float(j["RS_Ratio"].iloc[-1]) if len(j) else np.nan
            rec["C6_rs_mom"] = float(j["RS_Momentum"].iloc[-1]) if len(j) else np.nan
        except Exception:
            rec["C5_rs_ratio"] = rec["C6_rs_mom"] = np.nan
        rec["C7_rsi14"] = float(rsi.iloc[pos])
        rec["C8_adx_di"] = float(adxdi.iloc[pos])
        # location
        try:
            rec["L1_zone_d"] = float(bool(ze.zone_support(s, "D").get("at_support")))
        except Exception:
            rec["L1_zone_d"] = np.nan
        try:
            rec["L2_zone_w"] = float(bool(ze.zone_support(w, "W", price=px).get("at_support")))
        except Exception:
            rec["L2_zone_w"] = np.nan
        try:
            rec["L3_near_sr"] = float(bool(ze.sr_support(s, "D").get("near_sr")))
        except Exception:
            rec["L3_near_sr"] = np.nan
        try:
            rec["L4_near_avwap"] = float(bool(ze.avwap_support(s).get("near_avwap")))
        except Exception:
            rec["L4_near_avwap"] = np.nan
        try:
            rec["L5_at_vp"] = float(bool(ze.vp_support(s).get("at_vp_support")))
        except Exception:
            rec["L5_at_vp"] = np.nan
        rec["L6_ema_ext"] = (px - float(ema20.iloc[pos])) / a
        try:
            ro = ze.overhead_room({"D": s})
            ob = ro.get("obstacle")
            rec["L7_room"] = (float(ob) - px) / a if ob is not None else np.nan
            rec["_clear"] = bool(ro.get("clear")) and ob is None
        except Exception:
            rec["L7_room"], rec["_clear"] = np.nan, False
        # execution (daily analogue)
        try:
            pats = pp.detect_bull_patterns(s, "")
            rec["X1_pa_sigma"] = float(sum(wt for (_n, f, wt, _d) in pats if f))
        except Exception:
            rec["X1_pa_sigma"] = np.nan
        o_, h_, l_ = float(d["Open"].iloc[pos]), float(d["High"].iloc[pos]), float(d["Low"].iloc[pos])
        rng = h_ - l_
        rec["X2_bar_ok"] = float(px >= o_ or (rng > 0 and (px - l_) / rng >= 0.5))
        vv = float(v50p.iloc[pos])
        rec["X3_rv"] = float(d["Volume"].iloc[pos]) / vv if vv > 0 else np.nan
        hh = d["High"].iloc[pos - 19:pos + 1]
        k = int(len(hh) - 1 - np.argmax(hh.values[::-1]))      # bars since the latest max
        rec["X4_arrival"] = ((float(hh.max()) - px) / a) / k if k > 0 else 0.0
        out.append(rec)
    return out


def build(workers=8):
    import data_provider as dp
    import validation as V
    syms = V.default_universe("nifty500")
    b = dp.fetch_ohlcv("^CRSLDX", period="5y", interval="1d")
    if getattr(b.index, "tz", None) is not None:
        b = b.copy(); b.index = b.index.tz_localize(None)
    bc = b["Close"].dropna()
    cal = bc.index
    dates = list(cal[MIN_HIST:len(cal) - H:STEP])
    print(f"universe {len(syms)}  sample dates {len(dates)} ({dates[0].date()}..{dates[-1].date()})")
    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(symbol_rows, s, bc, dates): s for s in syms}
        for f in as_completed(futs):
            try:
                rows.extend(f.result())
            except Exception as e:
                print("  fail", futs[f], e)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(syms)} symbols, {len(rows)} rows", flush=True)
    P = pd.DataFrame(rows)
    # L7 "clear": the 95th percentile of observed room on that date (prereg)
    q95 = P.groupby("date")["L7_room"].transform(lambda x: x.quantile(0.95))
    P.loc[P["_clear"] & P["L7_room"].isna(), "L7_room"] = q95
    P.to_parquet(PANEL)
    print(f"\nname-dates {len(P)}  symbols {P['Symbol'].nunique()}  dates {P['date'].nunique()}")
    print("coverage (non-missing %) and mean per row:")
    for r in ROWS:
        print(f"  {r:14} {P[r].notna().mean()*100:6.1f}%   mean {P[r].mean():+.3f}")
    print(f"  Y60 {P['Y60'].notna().mean()*100:.1f}%  Stage-2 share {P['C1_stage2'].mean()*100:.1f}%")


# ── statistics ───────────────────────────────────────────────────────────────
def daily_ic(P, row, y="Y60"):
    out = {}
    for t, g in P.groupby("date"):
        g = g[[row, y]].dropna()
        if len(g) < MIN_NAMES or g[row].nunique() < 2:
            continue
        out[t] = g[row].rank().corr(g[y].rank())
    return pd.Series(out).sort_index()


def block_boot_p(series, rng):
    """Two-sided p that the mean is 0, circular block bootstrap over dates."""
    x = series.dropna().values
    n = len(x)
    if n < BLOCK * 2:
        return np.nan
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, n, size=(N_BOOT, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]) % n
    m = x[idx.reshape(N_BOOT, -1)[:, :n]].mean(1)
    c = m - x.mean()                                 # null-centred
    return float(np.mean(np.abs(c) >= abs(x.mean())))


def split_dates(P):
    ds = sorted(P["date"].unique())
    n_is = int(round(len(ds) * IS_FRAC))
    oos0 = ds[n_is]
    purge = int(np.ceil(PURGE_BARS / STEP))
    return set(ds[:max(0, n_is - purge)]), set(ds[n_is:])


def holm(ps, alpha=ALPHA_FW):
    keys = [k for k, p in ps.items() if p == p]
    keys.sort(key=lambda k: ps[k])
    res, alive, m = {k: False for k in ps}, True, len(keys)
    for i, k in enumerate(keys):
        ok = alive and ps[k] <= alpha / (m - i)
        res[k] = ok
        alive = alive and ok
    return res


def fama_macbeth(P, rows, y="Y60"):
    coefs = {}
    for t, g in P.groupby("date"):
        g = g[rows + [y]].dropna()
        if len(g) < max(MIN_NAMES, len(rows) + 5):
            continue
        X = np.column_stack([(g[r].rank() - g[r].rank().mean()) / (g[r].rank().std() or 1) for r in rows])
        X = np.column_stack([np.ones(len(g)), X])
        yy = g[y].rank().values
        try:
            b = np.linalg.lstsq(X, yy, rcond=None)[0][1:]
        except Exception:
            continue
        coefs[t] = b
    return pd.DataFrame(coefs, index=rows).T.sort_index()


def analyse(P, label, rng):
    IS, OOS = split_dates(P)
    print(f"\n==== {label} ====")
    print(f"name-dates {len(P)}  IS dates {len(IS)}  OOS dates {len(OOS)} (purged {int(np.ceil(PURGE_BARS/STEP))})")
    s2 = P[P["C1_stage2"] == 1]
    res = {}
    for r in ROWS:
        pop = P if r in CONTEXT else s2
        other = s2 if r in CONTEXT else P
        ic = daily_ic(pop, r)
        ic_is, ic_oos = ic[ic.index.isin(IS)], ic[ic.index.isin(OOS)]
        oth = daily_ic(other, r)
        p = max(block_boot_p(ic_is, rng), block_boot_p(ic_oos, rng))
        res[r] = dict(row=r, pop="all" if r in CONTEXT else "stage2",
                      ic_is=ic_is.mean(), ic_oos=ic_oos.mean(), n_is=len(ic_is), n_oos=len(ic_oos),
                      p=p, ic_other=oth.mean(), ic_y20=daily_ic(pop, r, "Y20").mean())
    hp = holm({r: v["p"] for r, v in res.items()})
    for r, v in res.items():
        same = np.sign(v["ic_is"]) == np.sign(v["ic_oos"])
        big = abs(v["ic_is"]) >= IC_BAR and abs(v["ic_oos"]) >= IC_BAR
        v["q2"] = bool(same and big and hp[r])
        fav = FAV[r]
        v["backwards"] = bool(v["q2"] and fav != 0 and np.sign(v["ic_is"]) != fav)
    # Q3 among Q2 passers (population: stage2, where the panel is used)
    inf = [r for r, v in res.items() if v["q2"]]
    q3 = {}
    if len(inf) >= 2:
        FM = fama_macbeth(s2, inf)
        ps = {}
        for r in inf:
            ci, co = FM.loc[FM.index.isin(IS), r], FM.loc[FM.index.isin(OOS), r]
            ps[r] = max(block_boot_p(ci, rng), block_boot_p(co, rng))
            q3[r] = dict(fm_is=ci.mean(), fm_oos=co.mean())
        hq = holm(ps)
        for r in inf:
            q3[r]["p"] = ps[r]
            q3[r]["pass"] = bool(hq[r] and np.sign(q3[r]["fm_is"]) == np.sign(q3[r]["fm_oos"])
                                 == np.sign(res[r]["ic_is"]))
    elif len(inf) == 1:
        q3[inf[0]] = dict(fm_is=np.nan, fm_oos=np.nan, p=np.nan, pass_=True)
        q3[inf[0]]["pass"] = True
    # redundancy clusters (descriptive)
    C = P[ROWS].corr(method="spearman")
    partners = {r: [o for o in ROWS if o != r and abs(C.loc[r, o]) >= CLUSTER_RHO] for r in ROWS}
    for r, v in res.items():
        if not v["q2"]:
            v["verdict"] = "INFO-ONLY"
        elif v["backwards"]:
            v["verdict"] = "BACKWARDS"
        elif q3.get(r, {}).get("pass"):
            v["verdict"] = "VOTE"
        else:
            v["verdict"] = "MERGED"
        v.update({f"q3_{k}": x for k, x in q3.get(r, {}).items()})
        v["partners"] = ",".join(partners[r])
    print(f"\n  {'row':14}{'pop':>7}{'IC IS':>8}{'IC OOS':>8}{'p':>7}{'IC other':>9}{'IC Y20':>8}  verdict")
    for r in ROWS:
        v = res[r]
        extra = ""
        if r in q3 and not np.isnan(q3[r].get("fm_is", np.nan)):
            extra = f"  FM {q3[r]['fm_is']:+.3f}/{q3[r]['fm_oos']:+.3f}"
        if v["partners"]:
            extra += f"  ~{v['partners']}"
        print(f"  {r:14}{v['pop']:>7}{v['ic_is']:+8.3f}{v['ic_oos']:+8.3f}{v['p']:7.3f}"
              f"{v['ic_other']:+9.3f}{v['ic_y20']:+8.3f}  {v['verdict']}{extra}")
    return pd.DataFrame(res.values())


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--placebo", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rng = np.random.default_rng(11)
    if a.build:
        build(a.workers)
        return
    P = pd.read_parquet(PANEL)
    if a.placebo:
        P = P.copy()
        P["Y60"] = P.groupby("date")["Y60"].transform(lambda x: x.sample(frac=1, random_state=3).values)
        P["Y20"] = P.groupby("date")["Y20"].transform(lambda x: x.sample(frac=1, random_state=4).values)
        analyse(P, "PLACEBO (Y permuted within date — any pass is a bug)", rng)
        return
    if os.path.exists(MARKER):
        sys.exit(f"REFUSED: the real run has already been made ({MARKER}).")
    R = analyse(P, "REAL RUN", rng)
    R.to_csv(os.path.join(OUT, "_panel_audit_result.csv"), index=False)
    json.dump({"at": datetime.now().isoformat()}, open(MARKER, "w"))
    print("\nsaved validation_runs/_panel_audit_result.csv; marker written.")


if __name__ == "__main__":
    main()
