"""s4go_entry_ab.py — Fix-1: retest-entry A/B (23 Jul 2026).

The wider-stop A/B (s4go_stop_ab.py) refuted "just widen the stop" — the GO penalty
is the buy-STOP ENTRY (chasing the breakout extension above the confirmed bar's high),
not stop width. Fix-1 attacks the ENTRY: instead of a buy-stop above the high, place a
buy-LIMIT at the confirmed GO-bar CLOSE and fill on the first pullback (retest of value).
Entry price lands near the +2.56% buy@close baseline while keeping the confirmation
filter — the hypothesis is this recovers most of the lost edge.

Controlled A/B (identical qualified names & GO bars from the cached catalyst
qualification; ONLY the entry mechanic differs):
  B0_buystop        entry_mode='buystop'  (control == catalyst run 20260723_063652)
  R_retest          entry_mode='retest'   (structural stop, unchanged)
  R_retest_floorPOS entry_mode='retest' + catalyst-aware ATR floor (SWG1.5/POS2.5) —
                    stacks Fix-1 with the one stop pocket that helped (POS-ACCUM).

Reuses validation_runs/_ab_qual_cache (built by s4go_stop_ab.py). Venv python.
"""
import os, json, pickle, time
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")

import data_provider as _dp
import validation as _val
import replay as _replay
import bull_screener as _bull

CATALYST_RUN = "20260723_063652"
UNIVERSE = "nifty500"
FLOOR_CA = {"SWG": 1.5, "POS": 2.5, "POS-ACCUM": 2.5, "REV": 2.5, "WYC": 2.5}

# (name, entry_mode, sl_floor_by_family)
CONFIGS = [
    ("B0_buystop",        "buystop", None),
    ("R_retest",          "retest",  None),
    ("R_retest_floorPOS", "retest",  FLOOR_CA),
]


def qualify_anchor(anchor, universe):
    cf = os.path.join(CACHE, f"qual_{anchor}.pkl")
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    _dp.set_pinned_date(anchor)
    try:
        picks = _bull.run_bull_screener(symbols=universe, strict=True)
    except Exception as e:
        print(f"   qualify failed @ {anchor}: {e}", flush=True); picks = pd.DataFrame()
    finally:
        _dp.set_pinned_date(None)
    if picks is None or picks.empty:
        cands = pd.DataFrame(columns=["Symbol", "Catalyst", "Score"])
    else:
        keep = [c for c in ("Symbol", "Catalyst", "Signal_Label", "Score") if c in picks.columns]
        cands = picks[keep].copy()
        if "Signal_Label" in cands.columns and "Catalyst" not in cands.columns:
            cands = cands.rename(columns={"Signal_Label": "Catalyst"})
    pickle.dump(cands, open(cf, "wb"))
    return cands


def fam_from_fwd(fw):
    try: fw = int(float(fw))
    except Exception: return "NA"
    if fw >= 180: return "POS-ACCUM"
    if fw >= 120: return "POS"
    if fw >= 90:  return "REV"
    return "SWG"


def main():
    anchors = json.load(open(os.path.join(RUNS, f"validation_{CATALYST_RUN}_meta.json")))["anchors"]
    universe = _val.default_universe(UNIVERSE)
    b = pd.read_csv(os.path.join(RUNS, "validation_20260722_135745_details.csv"))
    reg = b.groupby("as_of")["Regime"].agg(lambda s: s.mode().iat[0]).to_dict()

    per_anchor = {a: qualify_anchor(a, universe) for a in anchors}
    n_q = sum(len(c) for c in per_anchor.values())
    print(f"Fix-1 entry A/B: {len(anchors)} anchors, {n_q} qualified rows, configs={[c[0] for c in CONFIGS]}\n", flush=True)

    results = {}
    for name, emode, floor in CONFIGS:
        print(f"==== sim {name}  entry_mode={emode} floor={floor} ====", flush=True)
        frames = []; tc = time.time()
        for a in anchors:
            cands = per_anchor[a]
            if cands.empty:
                continue
            res = _replay.run_s4go_replay(a, cands, mode="bull", entry_window=40, rv_floor=1.0,
                                          entry_mode=emode, sl_floor_by_family=floor)
            perf = res.get("performance", pd.DataFrame())
            if isinstance(perf, pd.DataFrame) and not perf.empty:
                pf = perf.copy(); pf.insert(0, "as_of", a); frames.append(pf)
        det = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        det.to_csv(os.path.join(RUNS, f"_entryab_{name}_details.csv"), index=False)
        results[name] = det
        print(f"   {name}: {len(det)} rows in {time.time()-tc:.0f}s", flush=True)

    print("\n" + "=" * 74)
    print("  FIX-1 RETEST-ENTRY A/B — per-trade matched alpha (venv)")
    print("=" * 74)
    print("  BASELINE buy@close 20260722_135745: mean +2.56% | win 53.4% | n=464")
    print("  GO control (buystop)              : mean -0.02% | win 34.3% | n=268")
    for name, det in results.items():
        if det.empty:
            print(f"\n### {name}: no trades"); continue
        ok = det[det["Status"].astype(str) == "OK"].copy()
        # fill/skip funnel
        stt = det["Status"].astype(str).value_counts().to_dict()
        am = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
        ok = ok[am.notna()]; am = am[am.notna()]
        ok["fam"] = ok["forward_days_used"].map(fam_from_fwd)
        ok["dir"] = ok["as_of"].map(lambda x: "UP" if "BULL" in str(reg.get(x, "")).upper()
                                    else ("DOWN" if "BEAR" in str(reg.get(x, "")).upper() else "NB"))
        sl = (ok["Exit_Reason"].astype(str) == "SL hit").mean() * 100
        print(f"\n### {name}   n={len(ok)}  mean={am.mean():+.2f}%  median={am.median():+.2f}%  "
              f"win={(am>0).mean()*100:.1f}%  SLhit={sl:.0f}%  avgHold={ok['Days_Held'].mean():.1f}d")
        print(f"   status funnel: {stt}")
        print("   -- family --")
        for f, g in ok.groupby("fam"):
            ga = pd.to_numeric(g["Alpha_Matched_pct"], errors="coerce")
            print(f"     {f:10} n={len(g):4d}  mean={ga.mean():+.2f}%  win={(ga>0).mean()*100:5.1f}%")
        print("   -- family x dir --")
        for (f, dr), g in ok.groupby(["fam", "dir"]):
            if len(g) < 3: continue
            ga = pd.to_numeric(g["Alpha_Matched_pct"], errors="coerce")
            print(f"     {f:10} {dr:4} n={len(g):4d}  mean={ga.mean():+.2f}%  win={(ga>0).mean()*100:5.1f}%")


if __name__ == "__main__":
    main()
