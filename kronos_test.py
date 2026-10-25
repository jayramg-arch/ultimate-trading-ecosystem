#!/usr/bin/env python3
"""Kronos volatility / ranking test - pre-registered in docs/PREREG_kronos_vol.md (25-Oct-2026).

Steps (see the pre-registration for the rules; the run is ONE-SHOT):
    python kronos_test.py --prepare                 main venv: origins, samples, inputs, baselines (no outcomes)
    python kronos_test.py --placebo                 main venv: random forecasts through the scoring, must FAIL
    <kronos venv>\\python kronos_test.py --forecast --plumbing 3     3 origins x 10 names, timing only
    <kronos venv>\\python kronos_test.py --forecast                  all origins, cached + resumable
    python kronos_test.py --run                     main venv: score once -> data/kronos_test/result.json

The forecast step needs the Kronos repo (MIT, github.com/shiyu-coder/Kronos) on disk: set KRONOS_REPO
to its folder (it holds the `model` package). It never needs the panel: it reads only the .npz inputs,
so the two venvs share no pickles.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "kronos_test")
INP = os.path.join(OUT, "inputs")
FC = os.path.join(OUT, "fc")
META = os.path.join(OUT, "meta.json")
RESULT = os.path.join(OUT, "result.json")

START = "2024-07-01"            # first origin: after Kronos's June-2024 pre-training cutoff
STEP, H, LOOKBACK = 10, 20, 400
N_NAMES = 120                   # may be lowered in plumbing only (amendment)
K_PATHS = 10
MODEL_ID, TOK_ID = "NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base"
T_SAMPLE, TOP_P = 1.0, 0.9
MIN_ORIGINS, MIN_NAMES = 40, 80
BOOT, BLOCK = 5000, 2
H1_MIN, H2_RATIO, H3_MIN = 0.03, 0.95, 0.03


# ---------------------------------------------------------------- prepare (main venv)
def _wilder_atr(h, l, c, n=14):
    import pandas as pd
    prev = c.shift()
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _clenow90(C):
    """v2's rank score - the same formula as pro_systems_backtest.pro_features (clenow90):
    annualised exponential-regression slope x R^2 over 90 sessions."""
    import pandas as pd
    lb = 90
    y = np.log(C)
    t = pd.Series(np.arange(len(C), dtype=float), index=C.index)
    my, mt = y.rolling(lb).mean(), t.rolling(lb).mean()
    cov = y.mul(t, axis=0).rolling(lb).mean() - my.mul(mt, axis=0)
    var_t = t.rolling(lb).var(ddof=0)
    sd_y = y.rolling(lb).std(ddof=0)
    slope = cov.div(var_t, axis=0)
    r = cov.div(sd_y.mul(np.sqrt(var_t), axis=0))
    return (np.exp(slope * 252) - 1) * r ** 2


def prepare() -> int:
    import pandas as pd
    sys.path.insert(0, HERE)
    import survivorship_backtest as sb
    p, mem = sb.load()
    C, Hh, L, O, V = p["Close"], p["High"], p["Low"], p["Open"], p["Volume"]
    idx = C.index
    has_hist = C.notna().cumsum() >= LOOKBACK + 1
    first = idx.searchsorted(pd.Timestamp(START))
    last = len(idx) - 1 - H
    origins = list(range(first, last + 1, STEP))
    os.makedirs(INP, exist_ok=True)
    meta = {"registered": "docs/PREREG_kronos_vol.md", "start": START, "step": STEP, "H": H,
            "lookback": LOOKBACK, "n_names": N_NAMES, "origins": []}
    for oi, t in enumerate(origins):
        d = idx[t]
        elig = [s for s in mem.columns if mem.iat[t, mem.columns.get_loc(s)] and has_hist.iat[t, C.columns.get_loc(s)]]
        rng = np.random.default_rng(d.toordinal())
        pick = sorted(rng.choice(elig, size=min(N_NAMES, len(elig)), replace=False).tolist())
        g = {"clenow90": _clenow90(C[pick])}
        x = np.zeros((len(pick), LOOKBACK, 6), dtype=np.float32)
        base = {}
        keep = []
        for j, s in enumerate(pick):
            w = slice(t - LOOKBACK + 1, t + 1)
            o, hi, lo, cl, vo = O[s].iloc[w], Hh[s].iloc[w], L[s].iloc[w], C[s].iloc[w], V[s].iloc[w]
            arr = np.column_stack([o, hi, lo, cl, vo.fillna(0), (cl * vo).fillna(0)]).astype(np.float32)
            if not np.isfinite(arr[:, :4]).all():
                continue                                    # a gap in the input window: skip the name
            x[len(keep)] = arr
            keep.append(s)
            atr = float(_wilder_atr(Hh[s].iloc[:t + 1], L[s].iloc[:t + 1], C[s].iloc[:t + 1]).iloc[-1])
            lr = np.log(C[s].iloc[t - 20:t + 1]).diff().dropna()
            base[s] = {"atr": atr / float(C[s].iat[t]), "rv20": float(np.sqrt((lr ** 2).sum())),
                       "clenow": float(g["clenow90"][s].iat[t]) if np.isfinite(g["clenow90"][s].iat[t]) else None}
        x = x[:len(keep)]
        dates_in = [str(z.date()) for z in idx[t - LOOKBACK + 1:t + 1]]
        dates_out = [str(z.date()) for z in idx[t + 1:t + 1 + H]]
        np.savez_compressed(os.path.join(INP, "%s.npz" % d.date()), x=x)
        meta["origins"].append({"i": oi, "date": str(d.date()), "symbols": keep, "dates_in": dates_in,
                                "dates_out": dates_out, "baseline": base, "eligible": len(elig)})
        print("  %s  eligible %d  sampled %d  inputs %d" % (d.date(), len(elig), len(pick), len(keep)), flush=True)
    json.dump(meta, open(META, "w"))
    print("prepared %d origins -> %s" % (len(origins), META))
    return 0


# ---------------------------------------------------------------- forecast (Kronos venv)
def forecast(plumbing: int = 0) -> int:
    import pandas as pd
    import torch
    repo = os.environ.get("KRONOS_REPO", "")
    if not repo or not os.path.isdir(os.path.join(repo, "model")):
        print("set KRONOS_REPO to the Kronos repo folder (it holds the `model` package)")
        return 2
    sys.path.insert(0, repo)
    from model import Kronos, KronosPredictor, KronosTokenizer
    tok = KronosTokenizer.from_pretrained(TOK_ID)
    mdl = Kronos.from_pretrained(MODEL_ID)
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=512)
    meta = json.load(open(META))
    os.makedirs(FC, exist_ok=True)
    todo = meta["origins"][:plumbing] if plumbing else meta["origins"]
    for o in todo:
        path = os.path.join(FC, "%s.csv" % o["date"])
        if os.path.exists(path) and not plumbing:
            continue
        x = np.load(os.path.join(INP, "%s.npz" % o["date"]))["x"]
        syms = o["symbols"][:10] if plumbing else o["symbols"]
        x = x[:len(syms)]
        xt = pd.Series(pd.to_datetime(o["dates_in"]))
        yt = pd.Series(pd.to_datetime(o["dates_out"]))
        cols = ["open", "high", "low", "close", "volume", "amount"]
        dfs = [pd.DataFrame(x[j], columns=cols) for j in range(len(syms))]
        closes = np.zeros((K_PATHS, len(syms), H))
        t0 = time.time()
        for k in range(K_PATHS):
            torch.manual_seed(o["i"] * 1000 + k)
            np.random.seed(o["i"] * 1000 + k)
            out = pred.predict_batch(df_list=dfs, x_timestamp_list=[xt] * len(syms),
                                     y_timestamp_list=[yt] * len(syms), pred_len=H,
                                     T=T_SAMPLE, top_p=TOP_P, sample_count=1, verbose=False)
            for j, f in enumerate(out):
                closes[k, j] = f["close"].to_numpy()[:H]
        c0 = x[:, -1, 3].astype(float)
        path_c = np.concatenate([np.broadcast_to(c0, (K_PATHS, len(syms)))[..., None], closes], axis=2)
        lr = np.diff(np.log(np.clip(path_c, 1e-9, None)), axis=2)
        kv = np.sqrt((lr ** 2).sum(axis=2).mean(axis=0))
        kr = np.log(np.clip(closes[:, :, -1], 1e-9, None) / c0).mean(axis=0)
        dt = time.time() - t0
        if plumbing:
            print("  %s  %d names x %d paths  %.1fs  KV median %.4f  KR median %+.4f  (no outcomes)"
                  % (o["date"], len(syms), K_PATHS, dt, float(np.median(kv)), float(np.median(kr))), flush=True)
            continue
        with open(path + ".tmp", "w") as fh:
            fh.write("symbol,kv,kr\n")
            for s, a, b in zip(syms, kv, kr):
                fh.write("%s,%.8f,%.8f\n" % (s, a, b))
        os.replace(path + ".tmp", path)
        print("  %s  %d names  %.0fs" % (o["date"], len(syms), dt), flush=True)
    return 0


# ---------------------------------------------------------------- scoring (main venv)
def _spearman(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return float("nan")
    ra = np.argsort(np.argsort(a[ok])).astype(float)
    rb = np.argsort(np.argsort(b[ok])).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def _outcomes(meta) -> dict:
    sys.path.insert(0, HERE)
    import pandas as pd
    import survivorship_backtest as sb
    p, _ = sb.load()
    C = p["Close"]
    out = {}
    for o in meta["origins"]:
        t = C.index.get_loc(pd.Timestamp(o["date"]))
        rv, r = {}, {}
        for s in o["symbols"]:
            seg = C[s].iloc[t:t + H + 1].to_numpy(float)
            if len(seg) == H + 1 and np.isfinite(seg).all() and (seg > 0).all():
                lr = np.diff(np.log(seg))
                rv[s] = float(np.sqrt((lr ** 2).sum()))
                r[s] = float(np.log(seg[-1] / seg[0]))
        out[o["date"]] = (rv, r)
    return out


def _block_boot(vals, rng, stat=np.mean):
    v = np.asarray(vals, float)
    n = len(v)
    nb = int(math.ceil(n / BLOCK))
    res = np.empty(BOOT)
    for b in range(BOOT):
        st = rng.integers(0, n, nb)
        ix = np.concatenate([(np.arange(BLOCK) + s) % n for s in st])[:n]
        res[b] = stat(v[ix])
    return float(np.percentile(res, 2.5)), float(np.percentile(res, 97.5))


def score(fc: dict, meta, outc, label: str) -> dict:
    """fc: {date: {sym: (kv, kr)}}. Returns the H1/H2/H3 verdicts and their numbers."""
    rng = np.random.default_rng(20261025)
    rows = []
    for o in meta["origins"]:
        d = o["date"]
        rv, r = outc[d]
        f = fc.get(d, {})
        syms = [s for s in o["symbols"] if s in rv and s in f]
        if len(syms) < 10:
            continue
        kv = [f[s][0] for s in syms]
        kr = [f[s][1] for s in syms]
        atr = [o["baseline"][s]["atr"] for s in syms]
        rv20 = [o["baseline"][s]["rv20"] for s in syms]
        cl = [o["baseline"][s]["clenow"] if o["baseline"][s]["clenow"] is not None else np.nan for s in syms]
        y = [rv[s] for s in syms]
        ry = [r[s] for s in syms]
        q = np.nanpercentile(cl, 75) if np.isfinite(cl).sum() >= 10 else np.nan
        top = [i for i, c in enumerate(cl) if np.isfinite(c) and c >= q]
        rows.append({"date": d, "n": len(syms),
                     "rho_k": _spearman(kv, y), "rho_a": _spearman(atr, y), "rho_r": _spearman(rv20, y),
                     "ic_k": _spearman(kr, ry), "ic_c": _spearman(cl, ry),
                     "ic_k_top": _spearman([kr[i] for i in top], [ry[i] for i in top]) if len(top) >= 10 else np.nan,
                     "kv": kv, "atr": atr, "rv20": rv20, "y": y})
    n_or = len(rows)
    avg_n = float(np.mean([z["n"] for z in rows])) if rows else 0.0
    res = {"label": label, "origins": n_or, "avg_names": round(avg_n, 1)}
    if n_or < MIN_ORIGINS or avg_n < MIN_NAMES:
        res["verdict"] = "THIN"
        return res
    half = n_or // 2
    # H1
    diff = np.array([z["rho_k"] - z["rho_a"] for z in rows])
    lo, hi = _block_boot(diff, rng)
    h1 = (diff.mean() >= H1_MIN and lo > 0 and diff[:half].mean() > 0 and diff[half:].mean() > 0)
    res["H1"] = {"rho_kronos": round(float(np.nanmean([z["rho_k"] for z in rows])), 4),
                 "rho_atr": round(float(np.nanmean([z["rho_a"] for z in rows])), 4),
                 "rho_rv20": round(float(np.nanmean([z["rho_r"] for z in rows])), 4),
                 "diff": round(float(diff.mean()), 4), "ci": [round(lo, 4), round(hi, 4)],
                 "diff_half1": round(float(diff[:half].mean()), 4), "diff_half2": round(float(diff[half:].mean()), 4),
                 "pass": bool(h1)}
    # H2 - one scale constant per method fitted on the first 25 % of origins
    cut = max(1, n_or // 4)

    def _scale(key):
        rat = np.concatenate([np.asarray(z["y"]) / np.asarray(z[key]) for z in rows[:cut]])
        rat = rat[np.isfinite(rat) & (rat > 0)]
        return float(np.median(rat))

    def _qlike(key, s):
        out = []
        for z in rows[cut:]:
            f2 = (np.asarray(z[key]) * s) ** 2
            y2 = np.asarray(z["y"]) ** 2
            ok = (f2 > 0) & (y2 > 0) & np.isfinite(f2) & np.isfinite(y2)
            q = y2[ok] / f2[ok]
            out.append(float(np.mean(q - np.log(q) - 1)))
        return np.array(out)

    qk, qa, qr = _qlike("kv", _scale("kv")), _qlike("atr", _scale("atr")), _qlike("rv20", _scale("rv20"))
    ratio_lo, ratio_hi = _block_boot(np.arange(len(qk)), rng,
                                     stat=lambda ix: qk[ix.astype(int)].mean() / qa[ix.astype(int)].mean())
    ratio = float(qk.mean() / qa.mean())
    h2 = ratio <= H2_RATIO and ratio_hi < 1.0
    res["H2"] = {"qlike_kronos": round(float(qk.mean()), 4), "qlike_atr": round(float(qa.mean()), 4),
                 "qlike_rv20": round(float(qr.mean()), 4), "ratio": round(ratio, 4),
                 "ci": [round(ratio_lo, 4), round(ratio_hi, 4)], "pass": bool(h2)}
    # H3
    ick = np.array([z["ic_k"] for z in rows])
    ict = np.array([z["ic_k_top"] for z in rows])
    ict = ict[np.isfinite(ict)]
    lo3, _ = _block_boot(ick, rng)
    lo3t, _ = _block_boot(ict, rng) if len(ict) >= MIN_ORIGINS else (float("nan"), float("nan"))
    h3 = (ick.mean() >= H3_MIN and lo3 > 0 and ick[:half].mean() > 0 and ick[half:].mean() > 0
          and len(ict) >= MIN_ORIGINS and ict.mean() >= H3_MIN and lo3t > 0)
    res["H3"] = {"rankic_kronos": round(float(ick.mean()), 4), "ci": [round(lo3, 4), None],
                 "half1": round(float(ick[:half].mean()), 4), "half2": round(float(ick[half:].mean()), 4),
                 "rankic_kronos_clenow_top25": round(float(ict.mean()), 4) if len(ict) else None,
                 "ci_top25_lo": round(lo3t, 4) if np.isfinite(lo3t) else None,
                 "rankic_clenow": round(float(np.nanmean([z["ic_c"] for z in rows])), 4),
                 "pass": bool(h3), "thin": len(ict) < MIN_ORIGINS}
    res["verdict_vol"] = "PASS" if (h1 and h2) else "FAIL"
    res["verdict_rank"] = "THIN" if len(ict) < MIN_ORIGINS else ("PASS" if h3 else "FAIL")
    return res


def _load_fc(meta) -> dict:
    fc = {}
    for o in meta["origins"]:
        path = os.path.join(FC, "%s.csv" % o["date"])
        if not os.path.exists(path):
            continue
        d = {}
        for line in open(path).read().splitlines()[1:]:
            s, a, b = line.split(",")
            d[s] = (float(a), float(b))
        fc[o["date"]] = d
    return fc


def placebo() -> int:
    if os.path.exists(FC) and os.listdir(FC):
        print("Kronos forecasts already exist - the placebo must run before them (see the pre-registration).")
        return 2
    meta = json.load(open(META))
    rng = np.random.default_rng(7)
    fc = {o["date"]: {s: (float(rng.lognormal(-3, 0.5)), float(rng.normal(0, 0.05))) for s in o["symbols"]}
          for o in meta["origins"]}
    res = score(fc, meta, _outcomes(meta), "PLACEBO (random forecasts)")
    print(json.dumps({k: v for k, v in res.items()}, indent=1))
    ok = res.get("verdict") == "THIN" or (res.get("verdict_vol") == "FAIL" and res.get("verdict_rank") != "PASS")
    print("placebo", "FAILED as required" if ok else "PASSED - the scoring is broken, do not run")
    return 0 if ok else 1


def run() -> int:
    if os.path.exists(RESULT):
        print("already run - result is in %s (the pre-registration allows one run)" % RESULT)
        return 2
    meta = json.load(open(META))
    fc = _load_fc(meta)
    missing = [o["date"] for o in meta["origins"] if o["date"] not in fc]
    if missing:
        print("forecasts missing for %d origins (first %s) - finish --forecast first" % (len(missing), missing[0]))
        return 2
    res = score(fc, meta, _outcomes(meta), "KRONOS-small")
    res["run_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(RESULT, "w"), indent=1)
    print(json.dumps(res, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--forecast", action="store_true")
    ap.add_argument("--plumbing", type=int, default=0)
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.prepare:
        return prepare()
    if a.placebo:
        return placebo()
    if a.forecast:
        return forecast(a.plumbing)
    if a.run:
        return run()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
