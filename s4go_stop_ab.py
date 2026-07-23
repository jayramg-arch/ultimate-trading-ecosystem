"""s4go_stop_ab.py — Wider-GO-stop A/B (23 Jul 2026).

Tests the classifier->stop hypothesis from the GM+S4 GO backtest: the GO gate
cleanly separates runners from ~1-week shakeouts, but the buy-stop entry + tight
structural SL (67-69% stop out at ~8d) erases the +2.56% buy@close edge. Does an
ATR-FLOOR on the initial stop (don't let a razor-thin structure under a buy-stop
entry make a shakeout-prone stop) recover matched alpha?

Method (controlled A/B — identical qualified names & GO bars, ONLY the stop differs):
  1. For each catalyst-run anchor, re-qualify the catalyst universe ONCE
     (pinned, point-in-time) exactly as run_s4go_validation(qualify='catalyst')
     does -> cache the candidate frame to a pickle.
  2. Sim run_s4go_replay on the SAME cached candidates for 3 stop configs:
       A0 = None                      (control; reproduces the catalyst run)
       A1 = {'_default': 1.5}         (flat 1.5xATR floor)
       A2 = {'SWG':1.5,'POS':2.5,'POS-ACCUM':2.5,'REV':2.5,'WYC':2.5}  (catalyst-aware)
  3. Aggregate per-trade matched alpha per config, per family x direction.

Uses the venv python. No look-ahead: qualification is pinned, GO scan is unpinned
and forward-only (unchanged from the validated GO simulator).
"""
import os, sys, json, pickle, time
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(HERE, "validation_runs", "_ab_qual_cache")
os.makedirs(CACHE, exist_ok=True)

import data_provider as _dp
import validation as _val
import replay as _replay
import bull_screener as _bull

CATALYST_RUN = "20260723_063652"           # the strict-catalyst GO run we compare to
UNIVERSE = "nifty500"

CONFIGS = {
    "A0_control":       None,
    "A1_flat1.5":       {"_default": 1.5},
    "A2_catalyst_aware": {"SWG": 1.5, "POS": 2.5, "POS-ACCUM": 2.5, "REV": 2.5, "WYC": 2.5},
}


def qualify_anchor(anchor: str, universe: list) -> pd.DataFrame:
    """Reproduce run_s4go_validation(qualify='catalyst') qualification, cached."""
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
    print(f"A/B: {len(anchors)} anchors, {len(universe)} universe, configs={list(CONFIGS)}", flush=True)

    # anchor -> regime direction from the buy@close baseline details
    b = pd.read_csv(os.path.join(RUNS, "validation_20260722_135745_details.csv"))
    reg = b.groupby("as_of")["Regime"].agg(lambda s: s.mode().iat[0]).to_dict()

    # 1. qualify (cached) — deep 3y benchmark once, reused by every config
    t0 = time.time()
    per_anchor_cands = {}
    for i, a in enumerate(anchors, 1):
        c = qualify_anchor(a, universe)
        per_anchor_cands[a] = c
        print(f"[{i:2d}/{len(anchors)}] qualified {a}: {len(c)} names", flush=True)
    print(f"qualification done in {time.time()-t0:.0f}s\n", flush=True)

    # 2. sim each config on the SAME candidates
    all_rows = {}
    for cfg_name, floor in CONFIGS.items():
        print(f"==== sim {cfg_name}  floor={floor} ====", flush=True)
        frames = []
        tc = time.time()
        for a in anchors:
            cands = per_anchor_cands[a]
            if cands.empty:
                continue
            res = _replay.run_s4go_replay(a, cands, mode="bull", entry_window=40,
                                          rv_floor=1.0, sl_floor_by_family=floor)
            perf = res.get("performance", pd.DataFrame())
            if isinstance(perf, pd.DataFrame) and not perf.empty:
                pf = perf.copy(); pf.insert(0, "as_of", a)
                frames.append(pf)
        det = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        det.to_csv(os.path.join(RUNS, f"_ab_{cfg_name}_details.csv"), index=False)
        all_rows[cfg_name] = det
        print(f"   {cfg_name}: {len(det)} rows in {time.time()-tc:.0f}s", flush=True)

    # 3. aggregate
    print("\n" + "=" * 72)
    print("  WIDER-GO-STOP A/B — per-trade matched alpha (venv)")
    print("=" * 72)
    print("  BASELINE buy@close 20260722_135745: mean +2.56% | win 53.4% | n=464")
    for cfg_name, det in all_rows.items():
        if det.empty:
            print(f"\n### {cfg_name}: no trades"); continue
        ok = det[det["Status"].astype(str) == "OK"].copy()
        am = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
        ok = ok[am.notna()]; am = am[am.notna()]
        ok["fam"] = ok["forward_days_used"].map(fam_from_fwd)
        ok["dir"] = ok["as_of"].map(lambda x: "UP" if "BULL" in str(reg.get(x, "")).upper()
                                    else ("DOWN" if "BEAR" in str(reg.get(x, "")).upper() else "NB"))
        sl = (ok["Exit_Reason"].astype(str) == "SL hit").mean() * 100
        print(f"\n### {cfg_name}   n={len(ok)}  mean={am.mean():+.2f}%  median={am.median():+.2f}%  "
              f"win={(am>0).mean()*100:.1f}%  SLhit={sl:.0f}%  avgHold={ok['Days_Held'].mean():.1f}d")
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
