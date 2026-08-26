"""Location-rule A/B: any-zone vs A2 vs pattern-only.

Pre-registered in validation_runs/_prereg_location_rule.md -- READ THAT FIRST. The
question, the primary metric, the adoption rule and the "uninterpretable" conditions
were all fixed before this was run.

Identical candidates across all three arms (the July qualification cache), identical
entry convention (retest, the production default since 5f3e151), identical stops.
The ONLY thing that varies is replay.LOCATION_RULE.
"""
import os, sys, json, pickle, time
import pandas as pd, numpy as np
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")

import validation as _val
import replay as _replay

CATALYST_RUN = "20260723_063652"
ARMS = ["any", "a2", "pattern"]


def fam_from_fwd(fw):
    try: fw = int(float(fw))
    except Exception: return "NA"
    if fw >= 180: return "POS-ACCUM"
    if fw >= 120: return "POS"
    if fw >= 90:  return "REV"
    return "SWG"


def main():
    anchors = json.load(open(os.path.join(RUNS, f"validation_{CATALYST_RUN}_meta.json")))["anchors"]
    cands = {}
    for a in anchors:
        cf = os.path.join(CACHE, f"qual_{a}.pkl")
        if os.path.exists(cf):
            cands[a] = pickle.load(open(cf, "rb"))
    print(f"anchors with cached candidates: {len(cands)}/{len(anchors)}", flush=True)
    if not cands:
        print("no cache -- refusing to run a half-populated A/B"); return

    out = {}
    for arm in ARMS:
        _replay.LOCATION_RULE = arm
        t = time.time(); frames = []
        for a in sorted(cands):
            c = cands[a]
            if c is None or c.empty: continue
            try:
                res = _replay.run_s4go_replay(a, c, mode="bull", entry_window=40, rv_floor=1.0)
            except Exception as e:
                print(f"   {arm} @ {a} failed: {e}", flush=True); continue
            perf = res.get("performance", pd.DataFrame())
            if isinstance(perf, pd.DataFrame) and not perf.empty:
                pf = perf.copy(); pf.insert(0, "as_of", a); frames.append(pf)
        det = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        det.to_csv(os.path.join(RUNS, f"_locab_{arm}_details.csv"), index=False)
        out[arm] = det
        print(f"[{arm:8}] {len(det)} rows in {time.time()-t:.0f}s", flush=True)

    print("\n" + "=" * 74)
    print("  LOCATION RULE A/B — matched-horizon alpha (benchmark = actual hold)")
    print("=" * 74)
    summ = {}
    for arm, det in out.items():
        if det.empty:
            print(f"\n### {arm}: no trades"); continue
        ok = det[det["Status"].astype(str) == "OK"].copy()
        am = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
        ok = ok[am.notna()]; am = am[am.notna()]
        sl = (ok["Exit_Reason"].astype(str) == "SL hit").mean() * 100
        summ[arm] = dict(n=len(ok), mean=am.mean(), med=am.median(),
                         win=(am > 0).mean() * 100, sl=sl, hold=ok["Days_Held"].mean(),
                         armed=len(det))
        print(f"\n### {arm:8}  armed={len(det):4d}  filled={len(ok):4d}  "
              f"mean={am.mean():+.2f}%  median={am.median():+.2f}%  "
              f"win={(am>0).mean()*100:.1f}%  SLhit={sl:.0f}%  hold={ok['Days_Held'].mean():.0f}d")
        ok["fam"] = ok["forward_days_used"].map(fam_from_fwd)
        for f, g in ok.groupby("fam"):
            ga = pd.to_numeric(g["Alpha_Matched_pct"], errors="coerce")
            print(f"      {f:10} n={len(g):4d}  mean={ga.mean():+.2f}%  win={(ga>0).mean()*100:5.1f}%")

    # the pre-registered decision, applied mechanically
    print("\n" + "-" * 74)
    if "a2" in summ and "pattern" in summ:
        a2, pt = summ["a2"], summ["pattern"]
        fill_ratio = pt["n"] / a2["n"] if a2["n"] else 0
        print(f"PRE-REGISTERED RULE: adopt 'pattern' iff mean >= a2 AND fills >= 60% of a2")
        print(f"   pattern mean {pt['mean']:+.2f}%  vs  a2 {a2['mean']:+.2f}%   "
              f"| fills {pt['n']}/{a2['n']} = {fill_ratio*100:.0f}%")
        thin = [k for k, v in summ.items() if v["n"] < 40]
        spread = max(v["mean"] for v in summ.values()) - min(v["mean"] for v in summ.values())
        if thin:
            print(f"   UNINTERPRETABLE — arms under 40 fills: {thin}")
        elif spread < 0.3:
            print(f"   NULL — all arms within {spread:.2f}pp; these share most trades, so this is noise")
        elif pt["mean"] >= a2["mean"] and fill_ratio >= 0.60:
            print("   -> ADOPT pattern-only")
        elif pt["mean"] >= a2["mean"]:
            print("   -> better per trade, TOO RARE to run. Do not adopt; keep A2.")
        else:
            print("   -> KEEP A2")


if __name__ == "__main__":
    main()
