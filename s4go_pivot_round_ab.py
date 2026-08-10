#!/usr/bin/env python3
"""TWO standing tests in one run, sharing one qualification pass.

  A. PIVOT ABLATION  — zone_engine.USE_STRUCTURAL_ZONES on vs off.
     Jay, 10-Aug: "disable pivot zones and perform the test." Pine has had
     `useStructural` since v3.8; Python had none until today, so this could not be run.

  B. ROUND-NUMBER PARTITION — Jay, 10-Aug: "make sure that you test the round number logic."
     Scoped to ENTRY EXECUTION, not positional alpha. Osler measures a 15-MINUTE bounce and
     Bhattacharya/Holden/Jacobsen a 24-HOUR one; POS-BO holds 120 days. Reading a
     minutes-to-hours microstructure effect over a 120-day window returns a confident null
     that is an artifact of the design. So the headline metrics here are initial-SL-hit rate,
     days-held and max adverse excursion — what happens just after the fill.

WHY --gate s4go AND NOT THE STANDARD PATH: zone_engine is only reached by the GO replay
(replay._location_at) and by replay.STRUCTURAL_SL (False). A standard catalyst-gate run never
imports it, so ablating there returns a null BY CONSTRUCTION rather than by measurement.

Verified before writing: neither zone_engine nor replay memoises, so flipping the module flag
between arms inside one process is safe (a cache would have served arm A's zones to arm B).

Everything is read-only w.r.t. the live system: cached qualification, pinned dates, no orders.
"""
import os, sys, json, time, pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")          # shared with s4go_stop_ab / s4go_entry_ab
os.makedirs(CACHE, exist_ok=True)

import data_provider as _dp
import validation as _val
import replay as _replay
import bull_screener as _bull
import zone_engine as _ze

CATALYST_RUN = "20260723_063652"      # same anchor set the earlier s4go A/Bs used
UNIVERSE = "nifty500"

# Round-number grid for NSE rupees, graded by roundness. BHJ found the buy-sell imbalance
# MONOTONIC in roundness (integers > halves > ...), so this is a tier, not a boolean.
ROUND_TIERS = [(100.0, "R100"), (50.0, "R50"), (10.0, "R10"), (5.0, "R5")]
# The inversion band is UNDEFINED for NSE (Osler's is ~10 pips on a 4-decimal quote), so it
# is swept rather than assumed.
BANDS_PCT = [0.10, 0.25, 0.50, 1.00]


def qualify_anchor(anchor: str, universe: list) -> pd.DataFrame:
    """Reproduce run_s4go_validation(qualify='catalyst') qualification, cached on disk.
    Identical to s4go_stop_ab.qualify_anchor so the cache is shared and the candidate set
    is byte-identical to the earlier A/Bs."""
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


MIN_PX_FOR_ROUND = 20.0     # below this the R100/R50 grids are degenerate — see below


def round_dists(px: float) -> dict:
    """Distance (% of price) to the nearest multiple of EACH tier, independently.

    NOT "the nearest round number and its tier". That first design was wrong twice, and the
    unit test caught both before an hour-long run depended on it:

      * At px=2.50 every tier rounds to 0, so the distance came out 100% — degenerate for
        any low-priced name. Guarded by MIN_PX_FOR_ROUND.
      * More fundamentally, taking the MINIMUM distance across tiers lets the DENSEST grid
        win almost every time (an R5 multiple is at most 2.5 away; an R100 multiple can be
        50 away). The tier column was therefore ~always "R5", which makes it impossible to
        test the one claim worth testing: BHJ found the imbalance MONOTONIC in roundness
        (integers > halves > ...). Measuring each tier separately is what can answer that.

    Returns {"R100": pct, "R50": pct, "R10": pct, "R5": pct} — a trade can be near several.
    """
    out = {tag: np.nan for _s, tag in ROUND_TIERS}
    if not px or px != px or px < MIN_PX_FOR_ROUND:
        return out
    for step, tag in ROUND_TIERS:
        nearest = round(px / step) * step
        if nearest <= 0:
            continue
        out[tag] = abs(px - nearest) / px * 100.0
    return out


def _sim(anchors, per_anchor_cands, tag):
    frames = []
    t0 = time.time()
    for a in anchors:
        cands = per_anchor_cands[a]
        if cands.empty:
            continue
        res = _replay.run_s4go_replay(a, cands, mode="bull", entry_window=40, rv_floor=1.0)
        perf = res.get("performance", pd.DataFrame())
        if isinstance(perf, pd.DataFrame) and not perf.empty:
            pf = perf.copy(); pf.insert(0, "as_of", a)
            frames.append(pf)
    det = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    det.to_csv(os.path.join(RUNS, f"_pivot_ab_{tag}_details.csv"), index=False)
    print(f"   {tag}: {len(det)} rows in {time.time()-t0:.0f}s", flush=True)
    return det


def _clean(det):
    if det.empty:
        return det
    ok = det[det["Status"].astype(str) == "OK"].copy()
    am = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
    ok = ok[am.notna()].copy()
    ok["fam"] = ok["forward_days_used"].map(fam_from_fwd)
    rd = ok["Entry_Price"].map(round_dists)
    for _s, tag in ROUND_TIERS:
        ok[f"d_{tag}"] = [x.get(tag, np.nan) for x in rd]
    ok["initSL"] = ok.get("Hit_Initial_SL", False).astype(bool)
    return ok


def _hdr(s):
    print("\n" + "=" * 78); print("  " + s); print("=" * 78)


def main():
    anchors = json.load(open(os.path.join(RUNS, f"validation_{CATALYST_RUN}_meta.json")))["anchors"]
    universe = _val.default_universe(UNIVERSE)
    print(f"anchors={len(anchors)} universe={len(universe)}", flush=True)

    t0 = time.time()
    per_anchor_cands = {}
    for i, a in enumerate(anchors, 1):
        c = qualify_anchor(a, universe)
        per_anchor_cands[a] = c
        print(f"[{i:2d}/{len(anchors)}] qualified {a}: {len(c)} names", flush=True)
    print(f"qualification done in {time.time()-t0:.0f}s\n", flush=True)

    arms = {}
    for tag, flag in (("P_on", True), ("P_off", False)):
        _ze.USE_STRUCTURAL_ZONES = flag
        print(f"==== sim {tag}  USE_STRUCTURAL_ZONES={flag} ====", flush=True)
        arms[tag] = _clean(_sim(anchors, per_anchor_cands, tag))
    _ze.USE_STRUCTURAL_ZONES = True                       # leave the module as we found it

    # ── A. PIVOT ABLATION ────────────────────────────────────────────────────
    _hdr("A. PIVOT ABLATION — structural zones ON vs OFF")
    for tag, d in arms.items():
        if d.empty:
            print(f"  {tag}: no trades"); continue
        am = pd.to_numeric(d["Alpha_Matched_pct"], errors="coerce")
        print(f"  {tag:6} n={len(d):4d}  meanA={am.mean():+.2f}%  medA={am.median():+.2f}%  "
              f"win={(am>0).mean()*100:5.1f}%  initSL={d['initSL'].mean()*100:4.1f}%  "
              f"hold={d['Days_Held'].mean():5.1f}d")
    if all(not d.empty for d in arms.values()):
        # WHICH SOURCE carried the location gate — the mechanism behind any difference.
        for tag, d in arms.items():
            print(f"  {tag} Location_Src: {d['Location_Src'].value_counts().to_dict()}")
        on, off = arms["P_on"], arms["P_off"]
        delta = len(off) - len(on)          # was len(on)-len(off) and printed with a + sign,
                                            # so a LOSS of 14 fills rendered as "(+14)"
        print(f"\n  fills: P_on {len(on)} -> P_off {len(off)}  ({delta:+d})")
        print("  NOTE a LOWER fill count with pivots off means those trades only ever had a")
        print("  pivot shelf as their location — the ablation removed the setup, not a cap.")
        print("\n  -- per family --")
        for f in sorted(set(on["fam"]) | set(off["fam"])):
            a1 = pd.to_numeric(on[on.fam == f]["Alpha_Matched_pct"], errors="coerce")
            a2 = pd.to_numeric(off[off.fam == f]["Alpha_Matched_pct"], errors="coerce")
            if len(a1) < 3 and len(a2) < 3: continue
            print(f"    {f:10} ON n={len(a1):4d} {a1.mean():+6.2f}%   |   "
                  f"OFF n={len(a2):4d} {a2.mean():+6.2f}%")

    # ── B. ROUND NUMBERS ─────────────────────────────────────────────────────
    _hdr("B. ROUND NUMBERS — entry execution (control arm = P_on)")
    d = arms.get("P_on", pd.DataFrame())
    if d.empty:
        print("  no trades"); return 0
    usable = d[d["d_R5"].notna()]
    print(f"  usable (entry >= Rs{MIN_PX_FOR_ROUND:.0f}): {len(usable)}/{len(d)}")
    for _s, tag in ROUND_TIERS:
        print(f"    median distance to nearest {tag:5}: {d[f'd_{tag}'].median():.3f}%")
    # EACH TIER SEPARATELY — this is the monotonicity test. If BHJ transfers, the near-band
    # effect should be strongest at R100, weaker at R50, weakest at R5. If every tier shows
    # the same number, what is being measured is not roundness.
    for _s, tag in ROUND_TIERS:
        col = f"d_{tag}"
        print(f"\n  -- {tag} --")
        print(f"  {'band':>7} {'n_at':>6} {'n_off':>6} {'initSL_at':>10} {'initSL_off':>11} "
              f"{'hold_at':>8} {'hold_off':>9} {'MAE_at':>8} {'MAE_off':>8} {'A_at':>7} {'A_off':>7}")
        for b in BANDS_PCT:
            at = d[d[col] <= b]; off = d[d[col] > b]
            if len(at) < 5 or len(off) < 5:
                print(f"  {b:5.2f}%  n_at={len(at):4d} n_off={len(off):4d} — too few to read")
                continue
            f = lambda g, c: pd.to_numeric(g[c], errors="coerce").median()
            aa = pd.to_numeric(at["Alpha_Matched_pct"], errors="coerce").mean()
            ao = pd.to_numeric(off["Alpha_Matched_pct"], errors="coerce").mean()
            print(f"  {b:5.2f}% {len(at):6d} {len(off):6d} {at['initSL'].mean()*100:9.1f}% "
                  f"{off['initSL'].mean()*100:10.1f}% {at['Days_Held'].mean():7.1f}d "
                  f"{off['Days_Held'].mean():8.1f}d {f(at,'Max_Drawdown_pct'):7.2f}% "
                  f"{f(off,'Max_Drawdown_pct'):7.2f}% {aa:+6.2f}% {ao:+6.2f}%")
    d.to_csv(os.path.join(RUNS, "_round_number_partition.csv"), index=False)
    print("\n  saved: validation_runs/_round_number_partition.csv")
    print("\n  READ THIS AS A TILT, NOT AN EDGE. Osler's published-level bounce advantage was")
    print("  4.6pp on a ~56% base; BHJ put the COST of round-number behaviour near $1bn/yr —")
    print("  the crowd trading there is the harvested side. A surviving effect earns a fitted")
    print("  confluence weight, not a gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
