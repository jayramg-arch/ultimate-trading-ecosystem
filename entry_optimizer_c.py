"""entry_optimizer_c.py - the single run of docs/PREREG_entry_optimizer_C.md (2-Oct-2026).

Qualifies the holdout anchors with the CURRENT production bull screener, replays the GO
on 75m/125m with intraday_replay (frozen at f214434d + the pre-registered --stop-floor
switch), computes the qualification-close baseline E0 on the same names, and judges H1,
H1b, H2 and H3 exactly as the pre-registration defines them. Writes
validation_runs/entry_optimizer_C/result.txt whatever it says. Run once.

    python entry_optimizer_c.py        (venv; qualification ~1-2 h first time, cached)
"""
from __future__ import annotations

import os
import pickle
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
QC = os.path.join(RUNS, "_c_qual_cache")
OUT = os.path.join(RUNS, "entry_optimizer_C")

# Holdout anchors (prereg): mid-month, moved to the next session where the 15th was not one.
EARLY = ["2023-07-17", "2023-08-16", "2023-09-15", "2023-10-16", "2023-11-15", "2023-12-15",
         "2024-01-15", "2024-02-15", "2024-03-15", "2024-04-15", "2024-05-15"]
LATE = ["2025-12-15", "2026-01-16", "2026-02-16", "2026-03-16", "2026-04-15"]
ANCHORS = EARLY + LATE

import data_provider as _dp          # noqa: E402
import validation as _val             # noqa: E402
import bull_screener as _bull         # noqa: E402
import intraday_replay as ir          # noqa: E402
import entry_rebaseline as eb         # noqa: E402


def qualify(anchor: str, universe: list) -> pd.DataFrame:
    os.makedirs(QC, exist_ok=True)
    cf = os.path.join(QC, "qual_%s.pkl" % anchor)
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    _dp.set_pinned_date(anchor)
    try:
        picks = _bull.run_bull_screener(symbols=universe, strict=True)
    except Exception as e:
        print("   qualify failed @ %s: %s" % (anchor, e), flush=True)
        picks = pd.DataFrame()
    finally:
        _dp.set_pinned_date(None)
    if picks is None or picks.empty:
        c = pd.DataFrame(columns=["Symbol", "Catalyst"])
    else:
        keep = [k for k in ("Symbol", "Catalyst", "Signal_Label", "Score") if k in picks.columns]
        c = picks[keep].copy()
        if "Catalyst" not in c.columns and "Signal_Label" in c.columns:
            c = c.rename(columns={"Signal_Label": "Catalyst"})
    pickle.dump(c, open(cf, "wb"))
    return c


def fam(cat) -> str:
    c = str(cat or "").upper()
    return "POS" if c.startswith("POS") else ("SWG" if c.startswith("SWG") else "OTHER")


def window(a: str) -> str:
    return "EARLY" if a in EARLY else "LATE"


def boot(d: pd.DataFrame, col="diff", n=5000, lo_pct=2.5, seed=11):
    if d.empty:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    syms = d["Symbol"].unique()
    g = {s: d.loc[d["Symbol"] == s, col].values for s in syms}
    m = [np.concatenate([g[s] for s in rng.choice(syms, len(syms), replace=True)]).mean() for _ in range(n)]
    return tuple(np.percentile(m, [lo_pct, 100 - lo_pct]))


def main() -> int:
    t0 = time.time()
    universe = _val.default_universe("nifty500")
    cands = {}
    for a in ANCHORS:
        ta = time.time()
        cands[a] = qualify(a, universe)
        print("qualified %s: %d names (%.0fs)" % (a, len(cands[a]), time.time() - ta), flush=True)
    bench = eb._bench()
    rows = []
    dcache = {}
    pairs = [(a, m) for a in ANCHORS for m in cands[a].to_dict("records")]
    print("replaying %d names" % len(pairs), flush=True)
    for n, (a, m) in enumerate(pairs, 1):
        sym = str(m.get("Symbol"))
        f = fam(m.get("Catalyst"))
        base_row = {"as_of": a, "Symbol": sym, "Catalyst": m.get("Catalyst"), "fam": f, "window": window(a)}
        # E0 (qualification close)
        try:
            e0 = eb.e0_trade(sym, a, m, bench)
        except Exception as e:
            e0 = {"Status": "err %s" % e}
        rows.append(dict(base_row, variant="E0", tf="D", floor=0.0, **{k: e0.get(k) for k in ("Status", "SL_pct", "Return_pct", "Hit_Initial_SL")}))
        if sym not in dcache:
            dcache[sym] = ir._daily(sym)
        daily = dcache[sym]
        base = ir._base25(sym, a) if not daily.empty else pd.DataFrame()
        known_pb = str(m.get("Catalyst") or "").upper().startswith("SWG-PB")
        for tf in (75, 125):
            itf = ir._tf_frame(base, tf)
            go = ir.find_go(itf, daily, a, known_pb) if (not itf.empty and not daily.empty) else None
            specs = [("I_close", 0.0), ("I_buystop", 0.0)] + ([("I_close", 1.0)] if tf == 125 else [])
            for v, fl in specs:
                r = dict(base_row, variant=v, tf=tf, floor=fl)
                if go is None:
                    r["Status"] = "no GO" if not itf.empty else "no data"
                else:
                    try:
                        s = ir.simulate(itf, daily, go, v, m, bench, stop_floor=fl)
                    except Exception as e:
                        s = {"Status": "err %s" % str(e)[:60]}
                    r.update({k: s.get(k) for k in ("Status", "SL_pct", "Return_pct", "Hit_Initial_SL")})
                rows.append(r)
        if n % 50 == 0:
            print("  %d/%d (%.0f min)" % (n, len(pairs), (time.time() - t0) / 60), flush=True)
    df = pd.DataFrame(rows)
    df["R"] = np.where((df["Status"] == "OK") & (pd.to_numeric(df["SL_pct"], errors="coerce") > 0),
                       pd.to_numeric(df["Return_pct"], errors="coerce") / pd.to_numeric(df["SL_pct"], errors="coerce"), np.nan)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    txt = judge(df, len(pairs))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    txt = "STEP C RESULT - run %s, commit %s, %d qualified names over %d anchors\n\n" % (
        time.strftime("%Y-%m-%d %H:%M"), commit, len(pairs), len(ANCHORS)) + txt
    open(os.path.join(OUT, "result.txt"), "w", encoding="utf-8").write(txt)
    print("\n" + txt)
    return 0


def _paired(df, fam_, tf, variant, floor=0.0):
    e0 = df[(df["variant"] == "E0") & df["R"].notna()][["as_of", "Symbol", "R"]]
    g = df[(df["variant"] == variant) & (df["tf"] == tf) & (df["floor"] == floor) & df["R"].notna()]
    if fam_:
        g = g[g["fam"] == fam_]
    m = g[["as_of", "Symbol", "window", "R"]].merge(e0, on=["as_of", "Symbol"], suffixes=("_go", "_e0"))
    m["diff"] = m["R_go"] - m["R_e0"]
    return m


def _line(m, label):
    return "  %-6s n=%3d  GO %+.3fR  E0 %+.3fR  diff mean %+.3fR  median %+.3fR" % (
        label, len(m), m["R_go"].mean(), m["R_e0"].mean(), m["diff"].mean(), m["diff"].median())


def judge(df, n_names) -> str:
    L = []
    # descriptive table
    L.append("Fills and R by cell (descriptive):")
    for (v, tf, fl), g in df.groupby(["variant", "tf", "floor"]):
        ok = g[g["R"].notna()]
        L.append("  %-9s %-3s floor %.0f  fills %3d/%3d  meanR %+.3f  medR %+.3f  stop %3.0f%%" % (
            v, tf, fl, len(ok), len(g), ok["R"].mean(), ok["R"].median(),
            100 * ok["Hit_Initial_SL"].astype(bool).mean() if len(ok) else float("nan")))
    L.append("")

    def verdict(name, ok, detail):
        L.append("%s: %s" % (name, "PASS" if ok else "FAIL"))
        L.extend(detail)
        L.append("")

    # H1 / H1b
    for name, var, lo in (("H1  POS x 125m x I_close", "I_close", 2.5), ("H1b POS x 125m x I_buystop (Bonferroni)", "I_buystop", 1.25)):
        m = _paired(df, "POS", 125, var)
        ci = boot(m, lo_pct=lo)
        e, l = m[m["window"] == "EARLY"], m[m["window"] == "LATE"]
        thin = len(m) < 40
        ok = (not thin and m["diff"].mean() >= 0.15 and m["diff"].median() >= 0
              and len(e) and len(l) and e["diff"].mean() > 0 and l["diff"].mean() > 0 and ci[0] > 0)
        verdict(name + (" [THIN]" if thin else ""), ok,
                [_line(m, "ALL"), _line(e, "EARLY"), _line(l, "LATE"),
                 "  interval (%.1f%%-%.1f%%): [%+.3f, %+.3f]" % (lo, 100 - lo, ci[0], ci[1])])
    # H2
    det, ok_all = [], True
    for tf in (125, 75):
        m = _paired(df, "SWG", tf, "I_close")
        e, l = m[m["window"] == "EARLY"], m[m["window"] == "LATE"]
        ok_tf = (len(m) >= 40 and m["diff"].mean() <= -0.10 and len(e) and len(l)
                 and e["diff"].mean() < 0 and l["diff"].mean() < 0)
        ok_all = ok_all and ok_tf
        det += ["  %sm%s" % (tf, " [THIN]" if len(m) < 40 else ""), _line(m, "ALL"), _line(e, "EARLY"), _line(l, "LATE")]
    verdict("H2  SWG: waiting for GO is worse (125m and 75m, I_close)", ok_all, det)
    # H3
    g0 = df[(df["variant"] == "I_close") & (df["tf"] == 125) & (df["floor"] == 0.0) & df["R"].notna()]
    g1 = df[(df["variant"] == "I_close") & (df["tf"] == 125) & (df["floor"] == 1.0) & df["R"].notna()]
    m = g0[["as_of", "Symbol", "window", "R", "Hit_Initial_SL"]].merge(
        g1[["as_of", "Symbol", "R", "Hit_Initial_SL"]], on=["as_of", "Symbol"], suffixes=("_0", "_1"))
    det, ok3 = [], len(m) >= 40
    for lab, sub in (("ALL", m), ("EARLY", m[m["window"] == "EARLY"]), ("LATE", m[m["window"] == "LATE"])):
        s0 = 100 * sub["Hit_Initial_SL_0"].astype(bool).mean(); s1 = 100 * sub["Hit_Initial_SL_1"].astype(bool).mean()
        mr0, mr1 = sub["R_0"].mean(), sub["R_1"].mean()
        md0, md1 = sub["R_0"].median(), sub["R_1"].median()
        det.append("  %-6s n=%3d  stop %3.0f%% -> %3.0f%%  meanR %+.3f -> %+.3f  medR %+.3f -> %+.3f" % (lab, len(sub), s0, s1, mr0, mr1, md0, md1))
        if lab != "ALL":
            ok3 = ok3 and len(sub) > 0 and (s1 - s0) <= -10 and mr1 >= mr0 and md1 >= md0 - 0.25
    verdict("H3  1x daily-ATR stop floor (125m, I_close, all names)" + (" [THIN]" if len(m) < 40 else ""), ok3, det)
    L.append("One run against docs/PREREG_entry_optimizer_C.md. Not re-sliced.")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
