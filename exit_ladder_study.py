"""exit_ladder_study.py — trim, or let it run? Implements docs/PREREG_exit_policy.md
(+ Amendment 1) EXACTLY. Written after the pre-registration, before any result.

Supersedes exit_policy_study.py (28-Jul), which charged every config E0's hold length for
its benchmark and measured in per-trade %. Both defects are fixed here by construction:
every number is in R, and each config's benchmark spans that config's OWN days_held.

Entries are FROZEN: the same 515 trades of run 20260819_112959, same entry bar, same
initial stop. Only the exit changes.

MODES (the order is the protocol):
  --placebo    shuffled, demeaned returns per symbol. Every exit rule has the same expected
               return on a driftless series, so any "edge" here is a bug. Prints freely.
  --validate   E0 must reproduce the recorded Return_pct. Prints ONLY that check.
  --run        the single real run. Refuses unless --validate has passed, and refuses a
               second time (marker file) — the stopping rule is "runs once".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_DIR = os.path.dirname(os.path.abspath(__file__))
DETAILS = os.path.join(_DIR, "validation_runs", "validation_20260819_112959_details.csv")
OUT_DIR = os.path.join(_DIR, "validation_runs")
MARKER = os.path.join(OUT_DIR, "_exit_ladder_REAL_RUN_DONE.json")
VALID_MARK = os.path.join(OUT_DIR, "_exit_ladder_VALIDATED.json")

COST = 0.10              # % per leg (replay.COST_PER_LEG_DEFAULT)
ATR_LEN = 14
TRAIL = 4.5              # replay's Chandelier multiple — on EVERY family (Amendment 1a)
MAX_BARS = 400           # replay.MAX_HOLD_BARS (NO_TIME_STOP)
EXT_ATR = 4.0            # E4: close >= 4.0 x ATR14 above daily EMA20
WMA_WEEKS = 30           # E5
IS_FRAC, EMBARGO_DAYS = 0.6, 45
BAR_R, MED_R = 0.10, 0.10
MIN_N = 40
ALPHA_FW = 0.10
N_BOOT = 5000
FAMILIES = ("POS-BO", "POS-ACCUM", "SWG-PB")
POS_FAMILIES = ("POS-BO", "POS-ACCUM")
E3_GRID = (3.375, 4.5, 5.625, 6.75)


def _qty(cat):
    s = str(cat or "").upper()
    if s.startswith("SWG-GAP") or s == "SWG-REV":
        return 50.0, 50.0
    if s.startswith("SWG"):
        return 33.0, 33.0
    return 25.0, 25.0


# ── configurations (FIXED by the prereg) ─────────────────────────────────────
def configs():
    c = {
        "E0": dict(kind="control", trail=TRAIL),
        "E1": dict(kind="trail", trail=TRAIL),
        "E2": dict(kind="ladder", trail=TRAIL),
        "E4": dict(kind="ext", trail=TRAIL),
        "E5": dict(kind="weinstein", trail=None),
    }
    for m in E3_GRID:
        if m != TRAIL:
            c[f"E3_{m}"] = dict(kind="trail", trail=m)
    return c


# ── one trade ────────────────────────────────────────────────────────────────
def simulate(df, atr, ema20, wk_exit, pos, entry, sl, t1, t2, cat, cfg) -> dict:
    """Bar-by-bar, mirroring replay._simulate_one_trade's ordering for the control:
    trail update (off the PRIOR highest close) -> stop -> T1 -> T2 -> end-of-bar rules."""
    kind, mult = cfg["kind"], cfg["trail"]
    r_unit = entry - sl
    q1, q2 = _qty(cat)
    qty, pnl, legs = 100.0, 0.0, 2
    stop, hc = sl, entry
    hit_t1 = hit_t2 = False
    rung2 = rung3 = ext_done = False
    reason, days = "", 0
    pending_open_exit = False
    n = len(df)
    end = min(pos + 1 + MAX_BARS, n)
    O, H, L, C = (df[k].values for k in ("Open", "High", "Low", "Close"))

    def sell(px, q):
        nonlocal pnl, qty
        q = min(q, qty)
        pnl += (px - entry) / entry * 100.0 * (q / 100.0)
        qty -= q

    for p in range(pos + 1, end):
        days = p - pos
        # E5: exit at this session's open, decided at last week's close.
        if pending_open_exit:
            sell(O[p], qty)
            reason = "Weekly <30WMA"
            break
        a = atr[p]
        if mult is not None and not np.isnan(a):
            stop = max(stop, hc - a * mult)
        if L[p] <= stop and qty > 0:
            sell(stop, qty)
            reason = "SL hit" if stop == sl else "Trail SL"
            break
        if kind == "control":
            if not hit_t1 and H[p] >= t1:
                sell(t1, q1); legs += 1; hit_t1 = True
                stop = max(stop, entry)
            if not hit_t2 and H[p] >= t2 and qty > 0:
                sell(t2, q2); legs += 1; hit_t2 = True
        elif kind == "ladder":
            if not rung2 and H[p] >= entry + 2 * r_unit:
                sell(entry + 2 * r_unit, qty / 3.0); legs += 1; rung2 = True
                stop = max(stop, entry + 0.5 * r_unit)
            if rung2 and not rung3 and H[p] >= entry + 3 * r_unit and qty > 0:
                sell(entry + 3 * r_unit, qty / 2.0); legs += 1; rung3 = True
        elif kind == "ext":
            e, a2 = ema20[p], atr[p]
            if (not ext_done and not np.isnan(e) and not np.isnan(a2)
                    and C[p] >= e + EXT_ATR * a2):
                sell(C[p], qty / 2.0); legs += 1; ext_done = True
        elif kind == "weinstein":
            if wk_exit[p]:
                pending_open_exit = True
        hc = max(hc, C[p])
        if qty <= 1e-9:
            reason = reason or "Targets"
            break
    if qty > 1e-9:
        sell(C[end - 1], qty)
        reason = reason or "Still open"
    pnl -= legs * COST
    risk_pct = r_unit / entry * 100.0
    return {"ret": pnl, "R": pnl / risk_pct, "days": days, "reason": reason}


# ── data ─────────────────────────────────────────────────────────────────────
def _indicators(df):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(ATR_LEN).mean().values
    ema20 = c.ewm(span=20, adjust=False).mean().values
    # Completed weeks only: a bar is a week-END if the NEXT bar falls in another week.
    wk = df.index.to_period("W-FRI")
    is_end = np.zeros(len(df), bool)
    is_end[:-1] = (wk[1:] != wk[:-1])
    wclose = c[is_end]
    wsma = wclose.rolling(WMA_WEEKS).mean()
    wk_exit = np.zeros(len(df), bool)
    below = (wclose < wsma).values
    wk_exit[np.where(is_end)[0]] = below
    return atr, ema20, wk_exit


def _placebo(df, rng):
    """Demeaned, shuffled daily log returns; each bar's O/H/L kept RELATIVE to its close
    and shuffled with it. Volatility survives, drift and serial structure do not."""
    c = df["Close"].values.astype(float)
    r = np.diff(np.log(c))
    r = r - r.mean()
    rel = np.column_stack([df["Open"].values[1:] / c[1:], df["High"].values[1:] / c[1:],
                           df["Low"].values[1:] / c[1:]])
    idx = rng.permutation(len(r))
    r, rel = r[idx], rel[idx]
    nc = np.empty(len(c)); nc[0] = c[0]
    nc[1:] = c[0] * np.exp(np.cumsum(r))
    out = df.copy()
    out["Close"] = nc
    out.iloc[1:, out.columns.get_loc("Open")] = rel[:, 0] * nc[1:]
    out.iloc[1:, out.columns.get_loc("High")] = np.maximum(rel[:, 1] * nc[1:], nc[1:])
    out.iloc[1:, out.columns.get_loc("Low")] = np.minimum(rel[:, 2] * nc[1:], nc[1:])
    return out


def load(placebo=False, seed=7):
    import data_provider as dp
    d = pd.read_csv(DETAILS)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    frames, rng = {}, np.random.default_rng(seed)
    for s in sorted(d["Symbol"].unique()):
        try:
            f = dp.fetch_ohlcv(s, period="3y", interval="1d")
            if f is None or f.empty:
                continue
            f = f.copy()
            if getattr(f.index, "tz", None) is not None:
                f.index = f.index.tz_localize(None)
            f = f[["Open", "High", "Low", "Close"]].dropna()
            frames[s] = _placebo(f, rng) if placebo else f
        except Exception:
            pass
    b = dp.fetch_ohlcv("^CRSLDX", period="5y", interval="1d")
    if getattr(b.index, "tz", None) is not None:
        b = b.copy(); b.index = b.index.tz_localize(None)
    return d, frames, b["Close"]


def simulate_all(d, frames, bench, placebo=False):
    cfgs = configs()
    rows = []
    for _, r in d.iterrows():
        f = frames.get(r["Symbol"])
        if f is None:
            continue
        pos = f.index.searchsorted(r["ts"], side="right") - 1
        if pos < 30:
            continue
        rec_e = float(r["Entry_Close"])
        entry = float(f["Close"].iloc[pos])
        # Levels by their recorded DISTANCE from entry, so the placebo keeps each trade's
        # geometry. On real data this reproduces the recorded prices.
        sl = entry * float(r["SL_price"]) / rec_e
        t1 = entry * float(r["T1_price"]) / rec_e
        t2 = entry * float(r["T2_price"]) / rec_e
        if not (0 < sl < entry):
            continue
        atr, ema20, wk_exit = _indicators(f)
        bpos = bench.index.searchsorted(f.index[pos], side="right") - 1
        rec = {"Symbol": r["Symbol"], "ts": r["ts"], "fam": r["Catalyst_used"],
               "rec_ret": r["Return_pct"], "entry_err": abs(entry - rec_e) / rec_e * 100}
        for name, cfg in cfgs.items():
            o = simulate(f, atr, ema20, wk_exit, pos, entry, sl, t1, t2, r["Catalyst_used"], cfg)
            be = min(bpos + o["days"], len(bench) - 1)
            bret = (bench.iloc[be] / bench.iloc[bpos] - 1) * 100 if bpos >= 0 else np.nan
            rec[f"{name}_R"] = o["R"]
            rec[f"{name}_ret"] = o["ret"]
            rec[f"{name}_days"] = o["days"]
            rec[f"{name}_alpha"] = o["ret"] - bret
            rec[f"{name}_why"] = o["reason"]
        rows.append(rec)
    return pd.DataFrame(rows)


# ── statistics ───────────────────────────────────────────────────────────────
def split(R, d):
    anchors = sorted(d["ts"].unique())
    n_is = int(round(len(anchors) * IS_FRAC))
    oos0 = anchors[n_is]
    cutoff = oos0 - pd.Timedelta(days=EMBARGO_DAYS)
    is_a = [a for a in anchors[:n_is] if a <= cutoff]
    return R[R["ts"].isin(is_a)], R[R["ts"] >= oos0], is_a, anchors[n_is:]


def boot_p(sub, a, b, rng):
    """One-sided p that mean(a - b) <= 0, resampling SYMBOLS."""
    diff = (sub[f"{a}_R"] - sub[f"{b}_R"]).values
    sy = sub["Symbol"].values
    u, inv = np.unique(sy, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    cnts = np.bincount(inv).astype(float)
    k = len(u)
    idx = rng.integers(0, k, size=(N_BOOT, k))
    m = sums[idx].sum(1) / cnts[idx].sum(1)
    return float((m <= 0).mean())


def contrast(IS, OOS, fam, a, b, rng):
    out = {"fam": fam, "cfg": a, "ref": b}
    thin = False
    ps = []
    ok_all = True
    for lab, W in (("IS", IS), ("OOS", OOS)):
        s = W[W["fam"] == fam]
        n = len(s)
        dm = float((s[f"{a}_R"] - s[f"{b}_R"]).mean()) if n else np.nan
        md = float(s[f"{a}_R"].median() - s[f"{b}_R"].median()) if n else np.nan
        out[f"{lab}_n"], out[f"{lab}_dmean"], out[f"{lab}_dmed"] = n, dm, md
        if n < MIN_N:
            thin = True
        else:
            ps.append(boot_p(s, a, b, rng))
        ok_all &= (n >= MIN_N) and dm >= BAR_R and md >= -MED_R
    out["thin"] = thin
    out["p"] = max(ps) if (ps and not thin) else np.nan
    out["size_pass"] = bool(ok_all)
    return out


def holm(rows):
    tested = [r for r in rows if not r["thin"] and not np.isnan(r["p"])]
    tested.sort(key=lambda r: r["p"])
    m = len(tested)
    alive = True
    for i, r in enumerate(tested):
        thr = ALPHA_FW / (m - i)
        r["holm_pass"] = alive and r["p"] <= thr
        if not r["holm_pass"]:
            alive = False
    for r in rows:
        r.setdefault("holm_pass", False)
        r["verdict"] = ("THIN" if r["thin"] else
                        "PASS" if (r["size_pass"] and r["holm_pass"]) else
                        "suggestive" if (r["size_pass"] or r["holm_pass"]) else "FAIL")
    return rows


def report(R, d, title, rng):
    IS, OOS, is_a, oos_a = split(R, d)
    print(f"\n==== {title} ====")
    print(f"IS anchors {len(is_a)} ({is_a[0].date()}..{is_a[-1].date()}), "
          f"OOS anchors {len(oos_a)} ({oos_a[0].date()}..{oos_a[-1].date()}), "
          f"embargo {EMBARGO_DAYS}d")
    names = list(configs())
    for lab, W in (("IS", IS), ("OOS", OOS)):
        for fam in FAMILIES:
            s = W[W["fam"] == fam]
            print(f"\n-- {lab} · {fam}  n={len(s)}{'  THIN' if len(s) < MIN_N else ''}")
            print(f"   {'cfg':9}{'meanR':>7}{'medR':>7}{'P>=2R':>7}{'initSL%':>8}{'days':>6}{'alpha%':>8}")
            for nm in names:
                if len(s) == 0:
                    continue
                Rv = s[f"{nm}_R"]
                print(f"   {nm:9}{Rv.mean():+7.3f}{Rv.median():+7.3f}{(Rv >= 2).mean()*100:7.1f}"
                      f"{(s[f'{nm}_why'] == 'SL hit').mean()*100:8.1f}{s[f'{nm}_days'].median():6.0f}"
                      f"{s[f'{nm}_alpha'].mean():+8.2f}")

    rows = []
    for fam in FAMILIES:
        rows.append(dict(contrast(IS, OOS, fam, "E0", "E1", rng), H="H1"))
        rows.append(dict(contrast(IS, OOS, fam, "E2", "E0", rng), H="H2"))
        rows.append(dict(contrast(IS, OOS, fam, "E4", "E1", rng), H="H3"))
        # H4: best-of-grid (by IS mean) vs current. Edge winner = grid mis-specified.
        s_is = IS[IS["fam"] == fam]
        grid = {m: ("E1" if m == TRAIL else f"E3_{m}") for m in E3_GRID}
        if len(s_is):
            best_m = max(E3_GRID, key=lambda m: s_is[f"{grid[m]}_R"].mean())
            c = dict(contrast(IS, OOS, fam, grid[best_m], "E1", rng), H="H4")
            c["best_mult"] = best_m
            c["edge"] = best_m in (E3_GRID[0], E3_GRID[-1])
            if best_m == TRAIL:
                c.update(thin=c["thin"], p=np.nan, size_pass=False)
            rows.append(c)
    for fam in POS_FAMILIES:
        rows.append(dict(contrast(IS, OOS, fam, "E5", "E0", rng), H="H5"))
    rows = holm(rows)
    print("\n==== HYPOTHESES (bar +0.10R mean, median not worse by 0.10R, IS and OOS; Holm α=0.10) ====")
    for r in rows:
        extra = ""
        if r["H"] == "H4":
            extra = f"  best×{r.get('best_mult')}" + ("  EDGE→fails" if r.get("edge") and r["size_pass"] else "")
        print(f"  {r['H']} {r['fam']:10} {r['cfg']:>8}−{r['ref']:<3} "
              f"IS {r['IS_dmean']:+.3f}R (med {r['IS_dmed']:+.3f}, n{r['IS_n']})  "
              f"OOS {r['OOS_dmean']:+.3f}R (med {r['OOS_dmed']:+.3f}, n{r['OOS_n']})  "
              f"p={r['p']:.3f}  → {r['verdict']}{extra}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--placebo", action="store_true")
    g.add_argument("--validate", action="store_true")
    g.add_argument("--run", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    if a.run:
        if os.path.exists(MARKER):
            sys.exit(f"REFUSED: the real run has already been made ({MARKER}). The prereg says once.")
        if not os.path.exists(VALID_MARK):
            sys.exit("REFUSED: run --validate first; E0 must reproduce the recorded trades.")

    d, frames, bench = load(placebo=a.placebo, seed=a.seed)
    R = simulate_all(d, frames, bench, placebo=a.placebo)
    print(f"trades simulated {len(R)} of {len(d)}  symbols {R['Symbol'].nunique()}")

    if a.validate:
        err = (R["E0_ret"] - R["rec_ret"]).abs()
        med, within = err.median(), (err <= 1.0).mean()
        print(f"entry-price mismatch >0.5%: {(R['entry_err'] > 0.5).sum()}")
        print(f"E0 vs recorded: median |err| {med:.3f}pp, within 1.0pp {within*100:.1f}%")
        ok = med <= 0.25 and within >= 0.95
        print("VALID" if ok else "FAIL — study void until the control reproduces production")
        if not ok:
            bad = R.assign(err=err).sort_values("err", ascending=False)
            print(bad[["Symbol", "ts", "fam", "rec_ret", "E0_ret", "E0_why", "entry_err"]].head(12).to_string())
        else:
            json.dump({"at": datetime.now().isoformat(), "median_err": med, "within": within},
                      open(VALID_MARK, "w"))
        return

    rows = report(R, d, "PLACEBO (shuffled, demeaned — any edge is a bug)" if a.placebo else "REAL RUN", rng)
    if a.run:
        R.to_csv(os.path.join(OUT_DIR, "_exit_ladder_trades.csv"), index=False)
        pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "_exit_ladder_hypotheses.csv"), index=False)
        json.dump({"at": datetime.now().isoformat(), "details": DETAILS}, open(MARKER, "w"))
        print("\nsaved _exit_ladder_trades.csv + _exit_ladder_hypotheses.csv; marker written.")


if __name__ == "__main__":
    main()
