"""PULLBACK FINDER — surface Stage-2 names sitting AT VALUE, right now.

WHY THIS EXISTS (Jay, 31-Jul-2026): "Almost all the 'Take it' trades are breakout
type, extended from EMA20, not with the ideal entry point. I have to manually mark
such trades as 'Wait for Pullback'."

He is right, and it is STRUCTURAL, not a bad gate. Measured on the live board:

    timing state          n    median ext(ATR)   at value (<=1.0)
    Buy Trigger Live      8         1.74            1 of 8
    Armed Wait            9         1.35            4 of 9
    Wait for Pullback    17         0.23           14 of 17

Every actionable name sat within 0.2-2.9% of its own 20-day high. That is what a
TRIGGER selects for: a PA pattern + RV >= floor + a strong close IS, by
construction, a wide-range up-bar near the recent high. Trigger-based timing can
only ever hand you extension. Meanwhile the names actually at value get filed
under "Wait for Pullback" — the board's location gate says "needs a pullback"
because they are not inside a detected demand ZONE, even though they are sitting
on the EMA20.

So this is not a verdict-wording problem and no amount of relabelling fixes it.
The board answers "what just triggered". Nothing answered "what is at value".
This module answers that, and it is deliberately a SEPARATE surface:

    Trigger Board   ->  WHEN (breakout-biased by construction — that is fine, it
                        is a stopwatch)
    Pullback Finder ->  WHERE (location quality, ignores whether anything fired)

It does NOT gate on a live trigger, and it does NOT gate on the screener.in
fundamental join (MASTER_scan_results.csv, 149 names) that costs the Chartink
Pullback list 13 of its 17 names. Both of those are exactly what was starving the
pullback supply.

ZERO DRIFT: every number comes from the canonical engines —
bull_screener.compute_indicators / compute_weekly_indicators (Stage, Mansfield RS,
RRG), zone_engine (demand zones + S/R), data_provider (Dhan-primary feed). Nothing
is reimplemented here; this module only RANKS.

USAGE
    python pullback_finder.py                     # nifty500, full scan
    python pullback_finder.py --universe watchlist
    python pullback_finder.py --max-ext 1.5 --top 40
    python pullback_finder.py --max-risk 12       # positional: allow a wider stop
    python pullback_finder.py --limit 60          # quick smoke run

Output: Pullback_Candidates.csv + a ranked console table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

# The console table and the gate banner use ·, →, ⚠. Under a cp1252 console
# (a piped/redirected run, or an unattended one) those raise UnicodeEncodeError
# and kill the whole scan at the final print - after all the work is done. Same
# guard brute_force_match_pro.py carries.
try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(_DIR, "Pullback_Candidates.csv")

# ── Tunables ─────────────────────────────────────────────────────────────────
# EXT is the S4 metric: (close - dailyEMA20) / ATR14. <= 1.0 ATR is "at value";
# S4 warns at 2.5 and vetoes at 4.0, so 1.5 is comfortably inside "not chasing".
CONFIG = {
    "max_ext_atr":       1.5,   # hard: how far above the EMA20 price may sit
    "min_depth_pct":     2.0,   # hard: must have actually pulled back off the 20d high
    "max_depth_pct":    18.0,   # hard: a pullback, not a breakdown
    "min_turnover_cr":   2.0,   # hard: tradeable size
    "vol_dry_mult":      1.00,  # score: today's volume vs its 50-SMA
    "vol_spike_max":     2.50,  # hard: a climax bar is not a quiet pullback
    "swing_lookback":      20,  # bars for the reference swing high
    "max_risk_pct":      8.0,   # hard: stop distance; DNA swing target is 5-8%
    "min_price":         20.0,
    # ── FUNDAMENTAL GATE (Jay, 13-Aug-2026: "I do not want to trade
    #    fundamentally weak stocks through pullback finder") ──────────────────
    # BFF = the Minervini growth leg (profit growth / sales growth / margin
    # expansion / return quality / profitable), screener.in-sourced, 24h cached,
    # with lender-appropriate thresholds for banks and NBFCs. It is DISPLAY-ONLY
    # on the Bull path by design; here it is a HARD gate, on instruction.
    #   >= 2 blocks BFF's own WEAK band. >= 4 is STRONG-only (14 of 48 on the
    #   12-Aug set, against 40 at >= 2) - use --min-bff 4 for that.
    "min_bff_score":       2,
    "bff_block_unknown": True,  # block a name whose fundamentals cannot be read
    "bff_retries":         3,   # see _bff_with_retry - INSUFFICIENT is usually rate-limiting
}


def _depth_pct(ind, lookback):
    hi = float(ind["high"].iloc[-(lookback + 1):-1].max())
    c = float(ind["close"].iloc[-1])
    return ((hi - c) / hi * 100.0) if hi > 0 else np.nan, hi


def _support_below(df_d, px, ema20, sma50):
    """Nearest real support STRICTLY BELOW price, from the canonical zone engine.

    Every candidate must be checked against `< px`, including the fallbacks. The
    first version fell back to the EMA20 unconditionally and reported BHEL's
    support as 407.60 against a 403.00 close — i.e. it quoted RESISTANCE as
    support, and then derived the stop from it. When price is under the EMA20
    (a negative Ext_ATR, which this module actively looks for) the EMA20 is
    overhead by definition.

    Never raises — a zone-engine miss degrades down the chain, it does not drop
    the candidate."""
    best, src = None, ""

    def _take(lvl, label):
        nonlocal best, src
        if lvl and lvl == lvl and lvl < px and (best is None or lvl > best):
            best, src = float(lvl), label

    try:
        import zone_engine as ze
        for tf in ("D", "W"):
            try:
                z = ze.zone_support(df_d, tf=tf, price=px)
            except Exception:
                continue
            _take((z or {}).get("distal") or (z or {}).get("proximal"), f"DZ·{tf}")
        try:
            _take((ze.sr_support(df_d, tf="D", price=px) or {}).get("level"), "S/R")
        except Exception:
            pass
    except Exception:
        pass

    if best is None:
        _take(ema20, "EMA20")
    if best is None:
        _take(sma50, "SMA50")
    if best is None:
        _take(float(df_d["Low"].iloc[-20:].min()), "20d low")
    return best, src


BFF_STATS = {"weak": [], "unknown": [], "pass": 0}


def _report_bff(cfg):
    """Say what the fundamental gate removed, and keep the two reasons apart.

    WEAK is a judgement about the COMPANY. UNREADABLE is a judgement about our
    DATA. Collapsing them into one "dropped" count is how a screener.in outage
    comes to look like a market with no quality left in it.
    """
    weak, unk = BFF_STATS["weak"], BFF_STATS["unknown"]
    if not (weak or unk):
        return
    print(f"\n  BFF gate (>= {cfg['min_bff_score']}): {BFF_STATS['pass']} passed · "
          f"{len(weak)} weak · {len(unk)} unreadable")
    if weak:
        print(f"    weak (below the bar): {' '.join(weak[:12])}"
              + (" …" if len(weak) > 12 else ""))
    if unk:
        verb = "BLOCKED" if cfg.get("bff_block_unknown", True) else "kept"
        print(f"    unreadable after {cfg.get('bff_retries', 3)} retries — {verb}, "
              f"NOT judged weak: {' '.join(unk[:12])}"
              + (" …" if len(unk) > 12 else ""))
        if len(unk) > max(3, len(weak)):
            print("    ⚠ that many unreadable suggests screener.in rate-limiting, "
                  "not a market-wide quality problem")


def _bff_with_retry(symbol, cfg):
    """BFF for one symbol, retrying an INSUFFICIENT read before believing it.

    MEASURED 13-Aug-2026, and the reason this wrapper exists: a batch of 48
    sequential screener.in calls returned 10 INSUFFICIENT - and ALL TEN resolved
    on an immediate retry. SUNPHARMA and ICICIBANK came back OK; IPCALAB STRONG 4;
    SOLARINDS STRONG 5. None were genuinely missing fundamentals; screener.in was
    rate-limiting the burst.

    Without this, a HARD gate on INSUFFICIENT would drop good names on network
    luck and the finder's output would not be reproducible run to run. The X-Ray
    scoring bug was the same missing-data-as-failure mistake, but X-Ray is a
    RANKER - there it only distorted the order, and a dragged-down grade was
    still visible and still tradeable. A hard gate has no such mercy: the name
    disappears, and nothing on the surface says a fetch failed rather than a
    company. That is why the retry sits here and why `unknown` is counted and
    reported separately from `weak` below.
    """
    import time as _t
    from bull_fundamental_filter import compute_bff

    bff = None
    for attempt in range(max(1, int(cfg.get("bff_retries", 3)))):
        try:
            bff = compute_bff(symbol)
        except Exception:
            bff = None
        if bff and bff.get("quality") != "INSUFFICIENT" and bff.get("score") is not None:
            return bff
        _t.sleep(0.6 * (attempt + 1))       # linear backoff; the burst is the problem
    return bff


def evaluate(symbol, df_bench_w, cfg):
    """One symbol -> a candidate dict, or None. Hard gates return None; everything
    else is scored so a near-miss still ranks rather than vanishing."""
    import bull_screener as bs
    import data_provider as dp

    try:
        df_d = bs._flatten_cols(dp.fetch_ohlcv(symbol, period="2y", interval="1d",
                                               use_cache=True, auto_adjust=True))
        if df_d is None or df_d.empty or len(df_d) < 220:
            return None
        df_w = bs._flatten_cols(dp.fetch_ohlcv(symbol, period="3y", interval="1wk",
                                               use_cache=True, auto_adjust=True))
    except Exception:
        return None

    try:
        ind = bs.compute_indicators(df_d)
        wk = bs.compute_weekly_indicators(df_w, df_bench_w)
    except Exception:
        return None

    c = float(ind["close"].iloc[-1])
    atr = float(ind["atr"].iloc[-1])
    ema20 = float(ind["ema20"].iloc[-1])
    sma50 = float(ind["sma50"].iloc[-1])
    sma200 = float(ind["sma200"].iloc[-1])
    vol = float(ind["volume"].iloc[-1])
    volma = float(ind["vol_ma"].iloc[-1])
    hi52 = float(ind["high52w"].iloc[-1])

    if not atr or atr != atr or c < cfg["min_price"]:
        return None
    if (c * vol) / 1e7 < cfg["min_turnover_cr"]:
        return None

    # ── CONTEXT (hard): only pull back INTO an uptrend ────────────────────────
    stage = wk.get("stage")
    if stage != 2:
        return None
    sma200_slope = (sma200 - float(ind["sma200"].iloc[-22])) / sma200 * 100.0
    if not (c > sma200 and sma200_slope > 0):
        return None
    mans = wk.get("mansfield")
    if mans is None or mans != mans or mans <= 0:
        return None                      # must be OUTPERFORMING, not just rising

    # ── LOCATION (hard): the whole point of this module ───────────────────────
    ext = (c - ema20) / atr
    if ext > cfg["max_ext_atr"]:
        return None                      # extended = the thing he is complaining about
    depth, swing_hi = _depth_pct(ind, cfg["swing_lookback"])
    if depth != depth or not (cfg["min_depth_pct"] <= depth <= cfg["max_depth_pct"]):
        return None                      # at the highs, or broken down
    if c < sma50 * 0.97:
        return None                      # deeper than a pullback

    # A quiet pullback does not print a climax bar. SYRMA came through the first
    # run at 7.05x its 50-day average volume and still scored 51 — that is news or
    # distribution, not a name resting at value. Dry-up is scored below; a SPIKE is
    # a hard reject.
    if volma and vol > volma * cfg["vol_spike_max"]:
        return None

    sup, sup_src = _support_below(df_d, c, ema20, sma50)
    if sup is None:
        return None                      # nothing under price to lean on

    # ── SCORE: nearer to value + drier + tighter + stronger = better ──────────
    s_value = max(0.0, 20.0 * (1.0 - max(ext, 0.0) / cfg["max_ext_atr"]))
    s_depth = 15.0 * (1.0 - abs(depth - 7.0) / 11.0)          # ~7% is the sweet spot
    s_dry = 15.0 if (volma and vol < volma * cfg["vol_dry_mult"]) else 0.0
    rng5 = float((ind["high"].iloc[-5:] - ind["low"].iloc[-5:]).mean())
    rng20 = float((ind["high"].iloc[-20:] - ind["low"].iloc[-20:]).mean())
    s_tight = 15.0 if (rng20 > 0 and rng5 < rng20 * 0.85) else 0.0
    s_rs = min(20.0, max(0.0, float(mans)))
    s_sup = 15.0 * max(0.0, 1.0 - abs(c - sup) / max(atr * 2.0, 1e-9))
    score = round(s_value + s_depth + s_dry + s_tight + s_rs + s_sup, 1)

    # ── THE PLAN (levels to act on, not a verdict) ────────────────────────────
    # Confirmation-before-entry is the house rule: the trigger is a CLOSE above the
    # prior bar's high, and you buy-STOP above THAT bar. Never a resting order here.
    trigger = float(ind["high"].iloc[-1])
    sl = min(sup, ema20) - 0.5 * atr
    risk = trigger - sl

    # A stop is only as good as the structure it sits under, and `min(sup, ema20)`
    # can land a long way below price when the nearest support is a distant zone.
    # GABRIEL came through the 12-Aug run at 13.69% risk and still ranked 7th of
    # 65, because nothing in the score above looks at stop distance at all.
    #
    # The default is anchored, not picked: the DNA's swing target is 5-8% per
    # trade, so a stop wider than 8% risks more than the trade is designed to make
    # - R:R below 1 by construction. Measured on that run: 8% keeps 48 of 65 (74%)
    # and removes a tail reaching 14.92%. Positional trades can justify more, so
    # this is a CONFIG value with a --max-risk override, not a constant.
    risk_pct = (risk / trigger * 100.0) if trigger else np.nan
    if not (risk_pct == risk_pct) or risk_pct <= 0 or risk_pct > cfg["max_risk_pct"]:
        return None

    # ── FUNDAMENTALS (hard) ───────────────────────────────────────────────────
    # LAST, deliberately: this is the only gate that costs a network call, so it
    # runs on the ~50 names that survived everything else rather than all 500.
    bff = _bff_with_retry(symbol, cfg) or {}
    bff_score, bff_q = bff.get("score"), bff.get("quality") or "INSUFFICIENT"
    if bff_score is None or bff_q == "INSUFFICIENT":
        BFF_STATS["unknown"].append(symbol)
        if cfg.get("bff_block_unknown", True):
            return None
    elif bff_score < cfg["min_bff_score"]:
        BFF_STATS["weak"].append(f"{symbol}({bff_score})")
        return None
    else:
        BFF_STATS["pass"] += 1

    return {
        "Symbol": symbol,
        "Value_Score": score,
        "CMP": round(c, 2),
        "Ext_ATR": round(ext, 2),
        "Depth_%": round(depth, 1),
        "Stage": stage,
        "RS": round(float(mans), 1),
        "RRG": wk.get("rrg_quadrant", ""),
        "Vol_vs_50": round(vol / volma, 2) if volma else np.nan,
        "Tight": "YES" if s_tight else "-",
        "Support": round(sup, 2),
        "Sup_Src": sup_src,
        "BFF": bff_score,
        "BFF_Q": bff_q,
        "BFF_Why": " · ".join((bff.get("drivers") or [])[:3]),
        "Trigger>": round(trigger, 2),
        "SL": round(sl, 2),
        "Risk_%": round(risk_pct, 2),
        "T1_2R": round(trigger + 2 * risk, 2),
        "Dist_52WH_%": round((hi52 - c) / hi52 * 100.0, 1) if hi52 else np.nan,
        "As_Of": str(df_d.index[-1].date()),
    }


def load_universe(kind):
    if kind == "watchlist":
        syms, seen = [], set()
        for f in ("FINAL_Pullback_Picks.csv", "FINAL_Hunter_Picks.csv",
                  "FINAL_Leader_Picks.csv", "FINAL_EarlyBird_Picks.csv",
                  "FINAL_CATALYST_WATCHLIST.csv", "FINAL_GOLDEN_MATCHER.csv"):
            p = os.path.join(_DIR, f)
            if not os.path.exists(p):
                continue
            try:
                d = pd.read_csv(p)
            except Exception:
                continue
            for s in d.get("Symbol", pd.Series(dtype=str)).dropna():
                s = str(s).strip().upper()
                if s and s not in seen:
                    seen.add(s)
                    syms.append(s)
        return syms
    p = os.path.join(_DIR, "nifty500_symbols.json")
    with open(p) as f:
        return [str(s).replace(".NS", "").strip().upper() for s in json.load(f)]


def run(universe="nifty500", top=30, limit=None, cfg=None):
    import bull_screener as bs
    import data_provider as dp

    cfg = dict(CONFIG, **(cfg or {}))
    syms = load_universe(universe)
    if limit:
        syms = syms[:limit]
    print("=" * 74)
    print("  PULLBACK FINDER — Stage-2 names AT VALUE")
    print(f"  {datetime.now().strftime('%A %d %b %Y  %H:%M')}   universe={universe} ({len(syms)})")
    print(f"  gates: ext <= {cfg['max_ext_atr']} ATR from EMA20 · depth "
          f"{cfg['min_depth_pct']}-{cfg['max_depth_pct']}% off the 20d high · Stage 2 · RS > 0 "
          f"· risk <= {cfg['max_risk_pct']}% · BFF >= {cfg['min_bff_score']}")
    print("=" * 74)

    df_bench_w = bs._flatten_cols(dp.fetch_ohlcv(bs.BENCHMARK_YF, period="3y",
                                                 interval="1wk", use_cache=True,
                                                 auto_adjust=True))
    BFF_STATS["weak"], BFF_STATS["unknown"], BFF_STATS["pass"] = [], [], 0
    out, errs = [], 0
    for i, s in enumerate(syms, 1):
        if i % 50 == 0:
            print(f"  ...{i}/{len(syms)}  ({len(out)} candidates)")
        try:
            r = evaluate(s, df_bench_w, cfg)
            if r:
                out.append(r)
        except Exception:
            errs += 1

    if not out:
        _report_bff(cfg)
        print("\n  No names at value right now. That is a real answer — in a tape "
              "that is running, nothing has pulled back yet.")
        return pd.DataFrame()

    d = pd.DataFrame(out).sort_values("Value_Score", ascending=False).reset_index(drop=True)
    d.to_csv(OUT_FILE, index=False)
    _report_bff(cfg)

    print(f"\n  {len(d)} candidates ({errs} symbols errored)   →  {OUT_FILE}\n")
    cols = ["Symbol", "Value_Score", "CMP", "Ext_ATR", "Depth_%", "RS", "RRG",
            "Vol_vs_50", "Tight", "Support", "Sup_Src", "Trigger>", "SL", "Risk_%"]
    print(d.head(top)[cols].to_string(index=False))
    print("\n  Ext_ATR   = (close - EMA20) / ATR14. 0 = ON the EMA20. Lower is better.")
    print("  Depth_%   = how far below the 20-day high price has pulled back.")
    print("  Trigger>  = confirmation level. Wait for a CLOSED bar above it, then")
    print("              buy-STOP above THAT bar. Never rest an order at the level.")
    print("  This is a LOCATION list. Take the name to S4 for the trigger.")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Find Stage-2 names sitting at value")
    ap.add_argument("--universe", default="nifty500", choices=["nifty500", "watchlist"])
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-ext", type=float, default=None, dest="max_ext")
    ap.add_argument("--max-risk", type=float, default=None, dest="max_risk",
                    help="ceiling on stop distance as %% of entry (default 8.0)")
    ap.add_argument("--min-bff", type=int, default=None, dest="min_bff",
                    help="BFF fundamental floor 0-5 (default 2 blocks WEAK; 4 = STRONG only)")
    ap.add_argument("--keep-unreadable", action="store_true",
                    help="keep names whose fundamentals could not be read (default: blocked)")
    ap.add_argument("--silent", action="store_true")
    a = ap.parse_args()
    cfg = {}
    if a.max_ext is not None:
        cfg["max_ext_atr"] = a.max_ext
    if a.max_risk is not None:
        cfg["max_risk_pct"] = a.max_risk
    if a.min_bff is not None:
        cfg["min_bff_score"] = a.min_bff
    if a.keep_unreadable:
        cfg["bff_block_unknown"] = False
    cfg = cfg or None
    run(universe=a.universe, top=a.top, limit=a.limit, cfg=cfg)
    if not a.silent:
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
