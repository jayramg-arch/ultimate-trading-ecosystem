"""s4go_palookback_ab.py — how many candles back may a PA trigger be? (18 Aug 2026)

Jay: "we consider the last 3 candles. If PA/Bar is active on any of the last 3
candles (or how many?), we should consider it, right?"

A sticky PA window existed once and was REVERTED (S4 v5.0) for cause: it let ΣPA
accumulate across different bars, so the panel printed GO while the V/B chips
failed underneath — a total that described no single candle. This test does NOT
reintroduce that. The PA / volume / bar triple is always evaluated together on ONE
bar j; the only thing N relaxes is how far j may sit BEHIND the bar whose LOCATION
is tested. Location is "where is price now", so it is always read at the entry bar.

Controlled A/B — identical anchors, identical qualified names, identical entry and
exit machinery. ONLY pa_lookback changes:
    N=0  same bar (current behaviour; must reproduce the catalyst run)
    N=1,2,3  the qualifying bar may be up to 1/2/3 bars back

Reported per config: fills, mean/median matched alpha, win%, stop-out%, hold, and
the same split by catalyst family that every prior verdict here has turned on —
a pooled number has produced a wrong conclusion three times in this codebase.
"""
import os, sys, json, pickle, time
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")
os.makedirs(CACHE, exist_ok=True)

import data_provider as _dp
import replay as _replay
import bull_screener as _bull

CATALYST_RUN = "20260723_063652"     # the strict-catalyst GO run the cache was built for
UNIVERSE = "nifty500"
CONFIGS = [0, 1, 2, 3]


def anchors_from_run(run_id: str):
    p = os.path.join(RUNS, f"validation_{run_id}_summary.csv")
    d = pd.read_csv(p)
    col = "as_of" if "as_of" in d.columns else d.columns[0]
    return [str(x)[:10] for x in d[col].tolist()]


def qualify_anchor(anchor: str, universe):
    """Point-in-time catalyst qualification, cached — shared with the other A/Bs."""
    cf = os.path.join(CACHE, f"qual_{anchor}.pkl")
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    _dp.set_pinned_date(anchor)
    try:
        picks = _bull.run_bull_screener(symbols=universe, strict=True)
    except Exception as e:
        print(f"   qualify failed @ {anchor}: {e}", flush=True)
        picks = pd.DataFrame()
    finally:
        _dp.set_pinned_date(None)
    if picks is None or picks.empty:
        cands = pd.DataFrame(columns=["Symbol", "Catalyst", "Score"])
    else:
        keep = [c for c in ("Symbol", "Catalyst", "Score", "setup") if c in picks.columns]
        cands = picks[keep].copy()
    pickle.dump(cands, open(cf, "wb"))
    return cands


def main():
    anchors = anchors_from_run(CATALYST_RUN)
    print(f"anchors: {len(anchors)}  ({anchors[0]} .. {anchors[-1]})", flush=True)
    uni = json.load(open(os.path.join(HERE, "nifty500_symbols.json")))
    print(f"universe: {len(uni)}\n", flush=True)

    allrows = []
    for a in anchors:
        cands = qualify_anchor(a, uni)
        if cands is None or cands.empty:
            print(f"{a}: no candidates", flush=True); continue
        for N in CONFIGS:
            t0 = time.time()
            try:
                res = _replay.run_s4go_replay(a, cands, mode="bull", pa_lookback=N)
            except Exception as e:
                print(f"{a} N={N}: FAILED {e}", flush=True); continue
            perf = res.get("performance")
            if perf is None or len(perf) == 0:
                continue
            perf = perf.copy(); perf["N"] = N; perf["as_of"] = a
            allrows.append(perf)
            ok = perf[perf.get("Status", "") == "OK"] if "Status" in perf else perf
            print(f"{a} N={N}: {len(ok)}/{len(perf)} filled  "
                  f"({time.time()-t0:.0f}s)", flush=True)

    if not allrows:
        print("no rows"); return
    d = pd.concat(allrows, ignore_index=True)
    out = os.path.join(RUNS, "_pa_lookback_ab_details.csv")
    d.to_csv(out, index=False)
    print(f"\nwrote {out}  ({len(d)} rows)\n")

    ok = d[d["Status"] == "OK"].copy() if "Status" in d.columns else d.copy()
    ok["alpha"] = pd.to_numeric(ok.get("Alpha_Matched_pct"), errors="coerce")
    ok = ok.dropna(subset=["alpha"])
    fam = ok.get("Catalyst", pd.Series(index=ok.index, dtype=object)).fillna("NONE")
    ok["fam"] = ["POS" if str(x).startswith("POS") else "SWG" if str(x).startswith("SWG")
                 else "OTH" for x in fam]

    print(f"{'N':>2} {'fills':>6} {'mean α':>8} {'median':>8} {'win%':>6} {'SLhit%':>7} {'hold':>6}")
    print("-" * 52)
    for N in CONFIGS:
        s = ok[ok.N == N]
        if not len(s):
            print(f"{N:>2}   (none)"); continue
        sl = s.get("Exit_Reason", pd.Series(dtype=object)).astype(str).str.contains("SL", case=False)
        hold = pd.to_numeric(s.get("Days_Held"), errors="coerce")
        print(f"{N:>2} {len(s):>6} {s.alpha.mean():>8.2f} {s.alpha.median():>8.2f} "
              f"{(s.alpha > 0).mean()*100:>6.1f} {sl.mean()*100:>7.1f} {hold.mean():>6.1f}")

    print(f"\n{'N':>2} {'family':>7} {'n':>5} {'mean α':>8} {'median':>8} {'win%':>6}")
    print("-" * 46)
    for N in CONFIGS:
        for f in ("POS", "SWG"):
            s = ok[(ok.N == N) & (ok.fam == f)]
            if len(s) < 5:
                continue
            print(f"{N:>2} {f:>7} {len(s):>5} {s.alpha.mean():>8.2f} "
                  f"{s.alpha.median():>8.2f} {(s.alpha > 0).mean()*100:>6.1f}")
    print("\nN=0 must match the published catalyst run (+/- nothing) — if it does not, "
          "the cache or the machinery moved and the comparison is void.")


if __name__ == "__main__":
    main()
