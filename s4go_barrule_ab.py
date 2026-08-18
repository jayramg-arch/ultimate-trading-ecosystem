"""s4go_barrule_ab.py — which Bar (B) rule actually works? (18 Aug 2026)

Jay: "we have to look at both the PA and bar together. For instance, a bullish
Inside Bar is still bullish, despite forming a small candle after a momentum
candle." Research (Al Brooks; CLV; inside-bar literature) says the same thing:
a bar is a TREND bar (big body, small tails) or a DOJI, and which one you NEED
depends on what the pattern is claiming. A breakout must BE the move; an inside
bar is supposed to be small and only has to HOLD what the mother bar won.

Four rules, identical anchors / qualified names / entry / exit — only B differs:

  V0 legacy        green OR close in upper half            (what replay has always
                                                            used, and what S4 ran
                                                            until 17-Aug)
  V1 current Pine  CLV >= 0 AND upper wick <= 20%          (S4 today)
  V2 regime        expansion  -> body >= 50% of range AND CLV >= 0 AND wick <= 20%
                   contraction-> CLV vs the PRIOR bar's range >= 0 AND close >=
                                 prior low   (the inside-bar case)
                   neither    -> V1
  V3 trend-bar     body >= 50% AND CLV >= 0 AND wick <= 20%  (V2's expansion arm
                                                              applied to everything —
                                                              the naive "add body
                                                              size" fix, included so
                                                              the context term is
                                                              tested on its own)

CLV = ((C-L) - (H-C)) / (H-L), the standard Close Location Value; CLV >= 0 is
identical to close-in-upper-half, kept in that form because it is the canonical
measure and makes the prior-bar variant natural.
"""
import os, sys, json, pickle, time
import pandas as pd, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
CACHE = os.path.join(RUNS, "_ab_qual_cache")

import data_provider as _dp
import replay as _replay
import bull_screener as _bull

CATALYST_RUN = "20260723_063652"
_ORIG_BAR = _replay._bar_ok_series

# S4's own sets (Section4 :3540-3541), mapped to pa_field_validator columns.
WICK = 0.20
EXPAND   = ["pa_gap_up_bo", "pa_true_breakout", "pa_s2_launch", "pa_htf",
            "pa_liq_sweep", "pa_power_strong", "pa_outside_bull"]
CONTRACT = ["pa_vcp_bo", "pa_pocket", "pa_50sma_undercut", "pa_hammer_at_50",
            "pa_hammer_at_200", "pa_inside", "pa_inside3", "pa_nr7", "pa_ib_nr7"]


def _parts(det):
    o, h, l, c = det["open"], det["high"], det["low"], det["close"]
    rng = (h - l).replace(0, np.nan)
    clv = ((c - l) - (h - c)) / rng                    # -1..+1
    upw = (h - np.maximum(c, o)) / rng
    body = (c - o).abs() / rng
    ph, pl = h.shift(1), l.shift(1)
    prng = (ph - pl).replace(0, np.nan)
    clv_prev = ((c - pl) - (ph - c)) / prng            # position in the MOTHER bar
    return o, h, l, c, clv, upw, body, clv_prev, pl


def bar_v0(det):
    o, h, l, c, *_ = _parts(det)
    rng = (h - l).replace(0, np.nan)
    return ((c >= o) | ((c - l) / rng >= 0.5)).fillna(False)


def bar_v1(det):
    _, _, _, _, clv, upw, _, _, _ = _parts(det)
    return ((clv >= 0) & (upw <= 0.20)).fillna(False)


def bar_v3(det):
    _, _, _, _, clv, upw, body, _, _ = _parts(det)
    return ((clv >= 0) & (upw <= 0.20) & (body >= 0.50)).fillna(False)


def bar_v2(det):
    o, h, l, c, clv, upw, body, clv_prev, pl = _parts(det)
    exp = np.zeros(len(det), dtype=bool)
    con = np.zeros(len(det), dtype=bool)
    for k in EXPAND:
        if k in det:
            exp |= det[k].fillna(False).to_numpy(dtype=bool)
    for k in CONTRACT:
        if k in det:
            con |= det[k].fillna(False).to_numpy(dtype=bool)
    exp_only = exp & ~con
    trend  = (clv >= 0) & (upw <= WICK) & (body >= 0.50)
    held   = (clv_prev >= 0) & (c >= pl)
    plain  = (clv >= 0) & (upw <= WICK)
    out = pd.Series(np.where(exp_only, trend.fillna(False),
                    np.where(con, held.fillna(False), plain.fillna(False))),
                    index=det.index)
    return out.fillna(False)


def bar_v2_w30(det):
    """V2 with the wick cap relaxed 20% -> 30% (Jay, 18-Aug). Same regime logic.

    `global WICK`, NOT `import s4go_barrule_ab as _self`. Run directly the script
    is __main__, so importing itself by name builds a SECOND module object: the
    rebind landed on that copy while bar_v2 kept reading __main__.WICK. Both
    configs silently ran at 20% and the first w30 result came back identical to
    w20 to every decimal — which is the tell, not a finding.
    """
    global WICK
    _o = WICK
    WICK = 0.30
    try:
        return bar_v2(det)
    finally:
        WICK = _o


RULES = {"V0_legacy": bar_v0, "V2_regime_w20": bar_v2, "V2_regime_w30": bar_v2_w30}


def anchors_from_run(run_id):
    d = pd.read_csv(os.path.join(RUNS, f"validation_{run_id}_summary.csv"))
    col = "as_of" if "as_of" in d.columns else d.columns[0]
    return [str(x)[:10] for x in d[col].tolist()]


def qualify_anchor(anchor, universe):
    cf = os.path.join(CACHE, f"qual_{anchor}.pkl")
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    _dp.set_pinned_date(anchor)
    try:
        picks = _bull.run_bull_screener(symbols=universe, strict=True)
    finally:
        _dp.set_pinned_date(None)
    keep = [c for c in ("Symbol", "Catalyst", "Score") if c in getattr(picks, "columns", [])]
    cands = picks[keep].copy() if keep else pd.DataFrame(columns=["Symbol"])
    pickle.dump(cands, open(cf, "wb"))
    return cands


def main():
    anchors = anchors_from_run(CATALYST_RUN)
    uni = json.load(open(os.path.join(HERE, "nifty500_symbols.json")))
    print(f"anchors {len(anchors)} | universe {len(uni)}\n", flush=True)
    rows = []
    for a in anchors:
        cands = qualify_anchor(a, uni)
        if cands is None or cands.empty:
            continue
        for name, fn in RULES.items():
            _replay._bar_ok_series = fn                  # swap the rule, nothing else
            try:
                res = _replay.run_s4go_replay(a, cands, mode="bull")
            except Exception as e:
                print(f"{a} {name}: FAILED {e}", flush=True); continue
            finally:
                _replay._bar_ok_series = _ORIG_BAR
            p = res.get("performance")
            if p is None or not len(p):
                continue
            p = p.copy(); p["rule"] = name; p["as_of"] = a
            rows.append(p)
        print(f"{a} done", flush=True)

    d = pd.concat(rows, ignore_index=True)
    out = os.path.join(RUNS, "_bar_rule_ab_details.csv")
    d.to_csv(out, index=False)
    print(f"\nwrote {out} ({len(d)} rows)\n")

    cat = {}
    import glob
    for f in glob.glob(os.path.join(CACHE, "qual_*.pkl")):
        a = os.path.basename(f)[5:-4]
        c = pickle.load(open(f, "rb"))
        if "Catalyst" in getattr(c, "columns", []):
            for _, r in c.iterrows():
                cat[(a, str(r["Symbol"]))] = str(r["Catalyst"])
    ok = d[d.Status == "OK"].copy()
    ok["alpha"] = pd.to_numeric(ok["Alpha_Matched_pct"], errors="coerce")
    ok = ok.dropna(subset=["alpha"])
    ok["Catalyst"] = [cat.get((str(a)[:10], str(s)), "") for a, s in zip(ok.as_of, ok.Symbol)]
    ok["fam"] = ["POS" if x.startswith("POS") else "SWG" if x.startswith("SWG") else "OTH"
                 for x in ok["Catalyst"]]

    print(f"{'rule':>16} {'fills':>6} {'mean α':>8} {'median':>8} {'win%':>6} {'initSL%':>8} {'hold':>6}")
    print("-" * 64)
    for name in RULES:
        s = ok[ok.rule == name]
        if not len(s):
            print(f"{name:>16}   (none)"); continue
        ini = s["Hit_Initial_SL"].astype(str).str.lower().isin(["true", "1"]).mean() * 100
        print(f"{name:>16} {len(s):>6} {s.alpha.mean():>8.2f} {s.alpha.median():>8.2f} "
              f"{(s.alpha > 0).mean()*100:>6.1f} {ini:>8.1f} "
              f"{pd.to_numeric(s.Days_Held, errors='coerce').mean():>6.1f}")
    print(f"\n{'rule':>16} {'fam':>4} {'n':>5} {'mean α':>8} {'win%':>6}")
    print("-" * 46)
    for f in ("POS", "SWG"):
        for name in RULES:
            s = ok[(ok.rule == name) & (ok.fam == f)]
            if len(s) < 5:
                continue
            print(f"{name:>16} {f:>4} {len(s):>5} {s.alpha.mean():>8.2f} {(s.alpha > 0).mean()*100:>6.1f}")
        print()


if __name__ == "__main__":
    main()
