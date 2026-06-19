"""
validation.py — Multi-anchor backtest of the bull screener.

Runs `replay.run_bull_replay` at N monthly anchors over the last `months_back`
months on a *fixed* universe (Nifty 100 by default). Reports:

  • Per-anchor row: as_of, picks, win rate, avg return, benchmark, alpha
  • Aggregate: N anchors, total picks, weighted avg return, anchor-level
    hit rate (% of anchors with positive alpha), distribution of alphas

Why a fixed universe? Replaying against today's `FINAL_COMBINED_BULL_PICKS.csv`
would introduce look-ahead bias (we know which stocks were curated *today*,
not on each historical anchor date). A stable basket lets us measure the
screener's discrimination ability honestly.

Public API:
  monthly_anchors(months_back=12, day_of_month=15)  -> list[str]
  default_universe()                                 -> list[str]
  run_validation(...)                                -> dict
  load_last_validation()                             -> dict | None

CSV outputs land in `validation_runs/`:
  validation_<run_id>_summary.csv   — one row per anchor
  validation_<run_id>_details.csv   — every pick × every anchor with returns
  validation_<run_id>_meta.json     — config + aggregate
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

import data_provider as _dp


HERE       = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR   = os.path.join(HERE, "validation_runs")
os.makedirs(RUNS_DIR, exist_ok=True)

BENCHMARK_YF = "^CRSLDX"


# ─── Fixed universe (Nifty 100-ish — top liquid NSE stocks) ──────────────────
# Curated for stability across 12-month replays. Symbols here are NSE bare
# (no .NS) — data_provider normalizes either form.
_DEFAULT_UNIVERSE = [
    # Nifty 50
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFY","SBIN",
    "HINDUNILVR","ITC","LT","KOTAKBANK","AXISBANK","BAJFINANCE","MARUTI",
    "ASIANPAINT","TITAN","SUNPHARMA","ULTRACEMCO","WIPRO","ONGC","NESTLEIND",
    "POWERGRID","NTPC","HCLTECH","TECHM","TATASTEEL","JSWSTEEL","TATAMOTORS",
    "M&M","ADANIENT","ADANIPORTS","COALINDIA","BAJAJFINSV","INDUSINDBK",
    "DRREDDY","CIPLA","DIVISLAB","EICHERMOT","HEROMOTOCO","APOLLOHOSP",
    "BRITANNIA","BPCL","HINDALCO","SHREECEM","TATACONSUM","GRASIM","SBILIFE",
    "HDFCLIFE","PIDILITIND","BAJAJ-AUTO",
    # Nifty Next 50 sample (50 more highly-liquid mid/large caps)
    "DMART","ABB","ACC","AMBUJACEM","BANKBARODA","BERGEPAINT","BHEL","BOSCHLTD",
    "CANBK","CHOLAFIN","COLPAL","DLF","DABUR","GAIL","GODREJCP","GODREJPROP",
    "HAVELLS","HAL","HINDPETRO","ICICIGI","ICICIPRULI","IOC","IRCTC","IGL",
    "INDUSTOWER","NAUKRI","INDIGO","JINDALSTEL","LICI","LUPIN","MARICO",
    "MUTHOOTFIN","NMDC","OBEROIRLTY","OFSS","PIIND","PAGEIND","PFC","PNB",
    "RECLTD","SHRIRAMFIN","SIEMENS","SRF","SBICARD","TORNTPHARM","TRENT",
    "VEDL","ZYDUSLIFE","ALKEM","BEL",
]


_WATCHLIST_FILE_MAP = {
    # Bull-side
    "hunter":      "FINAL_Hunter_Picks.csv",
    "pullback":    "FINAL_Pullback_Picks.csv",
    "earlybird":   "FINAL_EarlyBird_Picks.csv",
    "leader":      "FINAL_Leader_Picks.csv",
    "combined":    "FINAL_COMBINED_BULL_PICKS.csv",
    "screener":    "Bull_Screener_Results.csv",
    # Recovery-side
    "rec_rs":      "FINAL_Recovery_RSLeaders.csv",
    "rec_eb":      "FINAL_Recovery_EarlyBirds.csv",
    "rec_cb":      "FINAL_Recovery_ClimaxBounce.csv",
    "rec_combined": "FINAL_COMBINED_RECOVERY_PICKS.csv",
}


def _load_watchlist(name: str) -> list[str]:
    """Read a curated watchlist CSV, return its symbol list (canonicalized).

    Look-ahead caveat: these files reflect TODAY's matcher run. Used as
    historical universes, they introduce survivorship bias — stocks that
    crashed and were removed from the curation since are absent. The
    measured alpha is therefore an *upper bound* on the screener's true
    historical edge on the production watchlists.
    """
    fname = _WATCHLIST_FILE_MAP.get(name.lower())
    if not fname:
        raise ValueError(f"unknown watchlist name {name!r}; "
                          f"valid: {sorted(_WATCHLIST_FILE_MAP)}")
    path = os.path.join(HERE, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    sym_col = next((c for c in df.columns
                      if c.lower() in ("symbol","nsecode","ticker","scrip")), None)
    if not sym_col:
        sym_col = df.columns[0]
    syms = (df[sym_col].dropna().astype(str).str.strip().str.upper()
              .str.replace("NSE:", "", regex=False)
              .str.replace(".NS", "", regex=False))
    return [s for s in syms.unique() if s and not s.isdigit()]


def default_universe(name: str = "nifty100") -> list[str]:
    """Return a fixed historical universe for validation runs.

    name='nifty100'        -> hardcoded Nifty 100-ish basket (~100 large caps)
    name='nifty500'        -> reads nifty500_symbols.json (production universe)
    name='fno'             -> reads fno_symbols.json (NSE F&O derivatives basket, ~210)
    name='nifty50'         -> first 50 entries of the nifty100 basket
    name='watchlist:<key>' -> read today's curated list (look-ahead biased)
                              keys: hunter, pullback, earlybird, leader,
                                    combined, screener, rec_rs, rec_eb,
                                    rec_cb, rec_combined
    """
    name = (name or "nifty100").lower().strip()
    if name.startswith("watchlist:"):
        return _load_watchlist(name.split(":", 1)[1])
    if name == "nifty500":
        import json as _json
        path = os.path.join(HERE, "nifty500_symbols.json")
        if not os.path.exists(path):
            print(f"[validation] {path} not found — falling back to nifty100 basket")
            return list(_DEFAULT_UNIVERSE)
        with open(path, "r", encoding="utf-8") as f:
            raw = _json.load(f)
        return [str(s).replace(".NS", "").strip() for s in raw if s]
    if name == "fno":
        # NSE F&O Basket — derivatives-eligible universe (~210 stocks).
        # Refresh fno_symbols.json from NSE periodically when constituents change.
        import json as _json
        path = os.path.join(HERE, "fno_symbols.json")
        if not os.path.exists(path):
            print(f"[validation] {path} not found — falling back to nifty100 basket")
            return list(_DEFAULT_UNIVERSE)
        with open(path, "r", encoding="utf-8") as f:
            raw = _json.load(f)
        # New format: {"_meta": {...}, "symbols": [...]}
        # Old/flat format: ["SYM1", "SYM2", ...]
        if isinstance(raw, dict) and "symbols" in raw:
            syms = raw["symbols"]
        else:
            syms = raw
        # Dedupe while preserving order (F&O JSON may contain repeats from manual edits)
        seen = set()
        out = []
        for s in syms:
            s = str(s).replace(".NS", "").strip().upper()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out
    if name == "nifty50":
        return list(_DEFAULT_UNIVERSE)[:50]
    return list(_DEFAULT_UNIVERSE)


# ─── Anchor generation ────────────────────────────────────────────────────────
def monthly_anchors(months_back: int = 12,
                      day_of_month: int = 15,
                      end_offset_days: int = 35) -> list[str]:
    """Return ISO-date strings for the 15th of each of the last N months,
    skipping the most recent one (so the forward window has data).

    `end_offset_days` ensures we stop ≥35 days short of today (forward-30d
    plus a small buffer). For forward_days > 30, increase this proportionally.
    """
    anchors: list[str] = []
    today = date.today()
    cutoff = today - timedelta(days=end_offset_days)
    cur = today.replace(day=1)
    for _ in range(months_back + 1):
        # Move to first day of previous month
        cur_prev_month_end = cur - timedelta(days=1)
        cur = cur_prev_month_end.replace(day=1)
        try:
            candidate = cur.replace(day=day_of_month)
        except ValueError:
            continue
        # Skip future or too-recent dates
        if candidate > cutoff:
            continue
        # Snap to the next weekday if it lands on Sat/Sun
        while candidate.weekday() >= 5:
            candidate = candidate + timedelta(days=1)
        anchors.append(candidate.isoformat())
        if len(anchors) >= months_back:
            break
    anchors.sort()
    return anchors


# ─── Main runner ──────────────────────────────────────────────────────────────
def run_chartink_validation(months_back: int = 12,
                              forward_days: int = 30,
                              base_universe: str = "nifty500",
                              scans: Optional[list[str]] = None,
                              top_n: Optional[int] = 10,
                              min_score: int = 0,
                              require_catalyst: bool = False,
                              use_fundamentals: bool = False,
                              min_conviction: float = 6.0,
                              progress_cb=None) -> dict:
    """Path-2-Phase-1 validation: regenerate the Chartink scan output
    historically at each anchor and run the bull screener on top.

    For each anchor:
      1. Pin data_provider
      2. Run all selected `scans` against `base_universe` -> historical candidates
      3. Combine (union, deduplicated)
      4. Run bull_screener.run_bull_screener on the historical candidates
      5. Apply top_n / min_score filter
      6. Compute forward returns, aggregate

    The pin + run + unpin sequence inside replay.run_bull_replay reuses our
    existing infrastructure cleanly.
    """
    import chartink_replay as _cr
    import replay as _replay
    import data_provider as _dp

    if scans is None:
        scans = list(_cr.SCAN_REGISTRY.keys())

    universe = default_universe(base_universe)
    anchors = monthly_anchors(months_back=months_back,
                                end_offset_days=max(forward_days + 5, 35))
    if not anchors:
        raise RuntimeError("No anchors generated")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows: list[dict] = []
    detail_frames: list[pd.DataFrame] = []
    universe_size_log: list[int] = []
    t0 = time.time()

    for i, anchor in enumerate(anchors, 1):
        if progress_cb:
            try: progress_cb(i, len(anchors), anchor)
            except Exception: pass
        print(f"[{i:2d}/{len(anchors)}]  validating @ {anchor} …", flush=True)

        # Phase 1A: regenerate historical candidates
        _dp.set_pinned_date(anchor)
        try:
            scan_outputs: dict[str, list[str]] = {}
            for s in scans:
                scan_outputs[s] = _cr.run_scan(s, universe)
            seen, combined = set(), []
            for syms in scan_outputs.values():
                for sym in syms:
                    if sym not in seen:
                        seen.add(sym); combined.append(sym)
            print(f"   scan candidates: "
                   + ", ".join(f"{s}={len(v)}" for s,v in scan_outputs.items())
                   + f"  combined={len(combined)}", flush=True)
        finally:
            _dp.set_pinned_date(None)

        # Phase 2: optionally apply the matcher's conviction filter
        if use_fundamentals and combined:
            try:
                import matcher_replay as _mr
                pre = len(combined)
                combined = _mr.filter_by_conviction(combined, anchor,
                                                       min_conviction=min_conviction)
                print(f"   fundamentals filter: {pre} -> {len(combined)} "
                      f"(min_conviction={min_conviction})", flush=True)
            except Exception as e:
                print(f"   fundamentals filter failed: {e}", flush=True)
        universe_size_log.append(len(combined))

        if not combined:
            summary_rows.append({
                "as_of":             anchor, "candidates":      0,
                "picks_filtered":     0,      "picks_with_data":  0,
                "win_rate_pct":       None,   "avg_return_pct":   None,
                "median_return_pct":  None,   "best_pct":         None,
                "worst_pct":          None,   "benchmark_pct":    None,
                "alpha_pct":          None,   "duration_s":       None,
            })
            continue

        # Phase 1B: bull screener on the historical candidate list
        try:
            result = _replay.run_bull_replay(anchor, forward_days, symbols=combined)
        except Exception as e:
            print(f"   ❌ replay failed: {e}")
            continue

        picks_full = result.get("picks", pd.DataFrame())
        bench = result.get("benchmark_pct")

        picks = picks_full.copy()
        if not picks.empty:
            cat_col = ("Catalyst" if "Catalyst" in picks.columns
                         else "Signal_Label" if "Signal_Label" in picks.columns else None)
            if require_catalyst and cat_col:
                picks = picks[picks[cat_col].astype(str).str.strip()
                                .isin(("None","nan","CB-Watch")) == False]
            if min_score > 0 and "Score" in picks.columns:
                picks = picks[pd.to_numeric(picks["Score"], errors="coerce")
                                .fillna(0) >= min_score]
            if top_n is not None and "Score" in picks.columns and not picks.empty:
                # v2 hook: sector cap + RS_Momentum tiebreak when v2 flags set;
                # falls back to plain Score-desc sort otherwise.
                try:
                    import v2_fixes as _v2
                    picks = _v2.select_top_n(picks, top_n)
                except Exception:
                    picks = picks.sort_values("Score", ascending=False).head(top_n)

        if picks.empty:
            perf = pd.DataFrame()
            s    = {"n": 0, "n_complete": 0,
                     "note": "no picks survived the filter"}
        else:
            syms = picks["Symbol"].astype(str).tolist()
            perf = _replay.forward_returns(syms, anchor, forward_days)
            s    = _replay._summarize(perf, bench)

        summary_rows.append({
            "as_of":             anchor,
            "candidates":         len(combined),
            "picks_full":         int(len(picks_full)),
            "picks_filtered":     int(len(picks)),
            "picks_with_data":    int(s.get("n_complete", 0)),
            "win_rate_pct":       s.get("win_rate_pct"),
            "avg_return_pct":     s.get("avg_return_pct"),
            "median_return_pct":  s.get("median_return_pct"),
            "best_pct":           s.get("best_pct"),
            "worst_pct":          s.get("worst_pct"),
            "benchmark_pct":      bench,
            "alpha_pct":          s.get("alpha_vs_bench"),
            "duration_s":         result.get("duration_s"),
        })

        if not picks.empty and not perf.empty and "Symbol" in picks.columns:
            combined_df = picks.merge(perf, on="Symbol", how="left")
            combined_df.insert(0, "as_of", anchor)
            detail_frames.append(combined_df)

    summary_df = pd.DataFrame(summary_rows)
    details_df = (pd.concat(detail_frames, ignore_index=True)
                    if detail_frames else pd.DataFrame())

    aggregate = {
        "n_anchors":            len(summary_rows),
        "scans":                scans,
        "base_universe":        base_universe,
        "base_universe_size":   len(universe),
        "use_fundamentals":     use_fundamentals,
        "min_conviction":       min_conviction if use_fundamentals else None,
        "avg_candidates_per_anchor": (round(sum(universe_size_log)/len(universe_size_log), 1)
                                          if universe_size_log else 0),
        "min_candidates":       (min(universe_size_log) if universe_size_log else 0),
        "max_candidates":       (max(universe_size_log) if universe_size_log else 0),
        "n_picks_total":        int(summary_df["picks_filtered"].fillna(0).sum())
                                    if not summary_df.empty else 0,
        "forward_days":         forward_days,
        "top_n":                top_n,
        "duration_s":           round(time.time() - t0, 2),
    }
    if not summary_df.empty:
        rets   = summary_df["avg_return_pct"].dropna()
        alphas = summary_df["alpha_pct"].dropna()
        winrt  = summary_df["win_rate_pct"].dropna()
        aggregate.update({
            "anchor_avg_return_pct":     round(float(rets.mean()), 2)   if len(rets)   else None,
            "anchor_median_return_pct":  round(float(rets.median()), 2) if len(rets)   else None,
            "anchor_avg_alpha_pct":      round(float(alphas.mean()), 2) if len(alphas) else None,
            "anchor_median_alpha_pct":   round(float(alphas.median()), 2) if len(alphas) else None,
            "alpha_hit_rate_pct":        round(float((alphas > 0).sum() / len(alphas) * 100), 1)
                                              if len(alphas) else None,
            "anchor_avg_winrate_pct":    round(float(winrt.mean()), 1)  if len(winrt)  else None,
            "best_anchor_alpha":        (float(alphas.max()) if len(alphas) else None),
            "worst_anchor_alpha":       (float(alphas.min()) if len(alphas) else None),
        })

    sum_path = os.path.join(RUNS_DIR, f"validation_{run_id}_summary.csv")
    det_path = os.path.join(RUNS_DIR, f"validation_{run_id}_details.csv")
    meta_path = os.path.join(RUNS_DIR, f"validation_{run_id}_meta.json")
    last_ptr = os.path.join(RUNS_DIR, "LAST_RUN.txt")
    summary_df.to_csv(sum_path, index=False)
    if not details_df.empty:
        details_df.to_csv(det_path, index=False)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "anchors": anchors,
                    "aggregate": aggregate, "mode": "chartink_replay"},
                   f, indent=2, default=str)
    with open(last_ptr, "w", encoding="utf-8") as f:
        f.write(run_id)

    return {
        "run_id":     run_id, "anchors": anchors,
        "summary_df": summary_df, "details_df": details_df,
        "aggregate":  aggregate,
        "paths": {"summary": sum_path,
                    "details": det_path if not details_df.empty else None,
                    "meta": meta_path},
    }


def run_validation(months_back: int = 12,
                     forward_days: int = 30,
                     basket: Optional[list[str]] = None,
                     universe_name: str = "nifty100",
                     screener: str = "bull",
                     min_score: int = 0,
                     require_catalyst: bool = False,
                     top_n: Optional[int] = None,
                     sector_cap: int = 0,
                     kill_switch_dd: float = 0.0,
                     kill_switch_losses: int = 0,
                     bootstrap_n: int = 0,
                     sector_rotation: str = "off",
                     catalyst_windows: bool = False,
                     progress_cb=None) -> dict:
    """Run the screener at each monthly anchor and aggregate results.

    Parameters
    ----------
    months_back      : how many monthly anchors to evaluate (default 12).
    forward_days     : trading-day forward window for return measurement.
    basket           : symbol list to screen at every anchor (default Nifty 100).
    screener         : "bull" (only one supported in v1).
    min_score        : keep only picks with Score >= this value (default 0).
    require_catalyst : keep only picks where Catalyst != "None" (default False).
    top_n            : after the above filters, keep only the top N by Score.
                       If None, keep all that pass the filters.
    progress_cb      : optional callable(idx, total, anchor_date) for UIs.

    Why filter? When `basket` is supplied, the bull screener forces tracker
    mode and emits every symbol regardless of catalyst. To measure the
    screener's *selection ability* (its edge), filter to catalyst-firing or
    high-Score picks only — what you'd actually have entered.
    """
    if screener not in ("bull", "recovery"):
        raise ValueError(f"screener must be 'bull' or 'recovery', got {screener!r}")
    import replay as _replay

    universe = list(basket) if basket else default_universe(universe_name)
    # v2.8: when catalyst_windows is on, anchors must end soon enough that
    # the longest catalyst window (POS-ACCUM=180d) still has forward data.
    if catalyst_windows:
        import replay as _r
        _longest = max(_r.FWD_DAYS_BY_CATALYST.values())
        end_off  = max(_longest + 5, 35)
    else:
        end_off  = max(forward_days + 5, 35)
    anchors = monthly_anchors(months_back=months_back,
                                end_offset_days=end_off)
    if not anchors:
        raise RuntimeError("No anchors generated — check months_back / today.")

    run_id   = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_rows: list[dict] = []
    detail_frames: list[pd.DataFrame] = []
    t0 = time.time()

    # v2.7 (Week 3): activate sector cap via v2_fixes flag when requested
    if sector_cap and sector_cap > 0:
        try:
            import v2_fixes as _v2cfg
            _v2cfg.V2_FLAGS["sector_cap_top_n"] = True
            _v2cfg.V2_PARAMS["sector_cap"] = int(sector_cap)
            print(f"  [Week-3] sector_cap enabled: max {sector_cap} picks/sector in Top-N")
        except Exception as _e:
            print(f"  [Week-3] sector_cap could not be enabled: {_e}")

    # v2.7 (Week 3): equity-curve kill switch state
    equity_curve     : list[float] = []          # cumulative anchor alpha
    consec_losses    : int = 0
    halt_engaged     : bool = False              # if True, skip picks at this anchor
    halt_anchors     : list[str] = []            # which anchors were halted
    # v2.7.1: peak tracker that resets after each halt — prevents DD re-arm cascade
    since_halt_peak  : float = float("-inf")

    # v2.8 (Week 4): sector rotation overlay
    sector_rotation = (sector_rotation or "off").lower()
    if sector_rotation not in ("off", "strict", "soft"):
        print(f"  [Week-4] unknown sector_rotation={sector_rotation!r}; disabling")
        sector_rotation = "off"
    if sector_rotation != "off":
        print(f"  [Week-4] sector_rotation enabled (mode={sector_rotation}) — "
              f"will keep only picks in {'LEADING' if sector_rotation=='strict' else 'LEADING+IMPROVING'} sectors")
    rotation_diag: list[dict] = []

    for i, anchor in enumerate(anchors, 1):
        if progress_cb:
            try: progress_cb(i, len(anchors), anchor)
            except Exception: pass
        print(f"[{i:2d}/{len(anchors)}]  validating @ {anchor} …", flush=True)

        # v2.7 (Week 3): equity-curve kill switch — skip picks if halted
        if halt_engaged:
            print(f"   [STOP] HALT engaged — skipping picks (kill switch active)")
            halt_anchors.append(str(anchor))
            summary_rows.append({
                "as_of":             anchor,
                "picks_universe":    0,
                "picks_filtered":    0,
                "picks_with_data":   0,
                "win_rate_pct":      None, "avg_return_pct": None,
                "median_return_pct": None, "best_pct": None, "worst_pct": None,
                "benchmark_pct":     None, "alpha_pct": 0.0,
                "avg_max_dd_pct":    None, "worst_max_dd_pct": None,
                "risk_reward":       None, "avg_max_runup_pct": None,
                "sharpe_ratio": None, "sortino_ratio": None, "calmar_ratio": None,
                "duration_s":        0.0,
                "halted":            True,
            })
            # v2.7.1: cooldown reset — append flat equity, reset loss-counter,
            # reset peak so next anchor starts fresh and DD doesn't re-trigger immediately.
            last_eq = equity_curve[-1] if equity_curve else 0.0
            equity_curve.append(last_eq)
            consec_losses   = 0
            since_halt_peak = last_eq
            halt_engaged    = False
            continue

        try:
            if screener == "recovery":
                result = _replay.run_recovery_replay(anchor, forward_days, symbols=universe)
            else:
                result = _replay.run_bull_replay(anchor, forward_days, symbols=universe)
        except Exception as e:
            print(f"   ❌ replay failed: {e}")
            continue

        picks_full = result.get("picks", pd.DataFrame())
        bench = result.get("benchmark_pct")

        # ── Apply selection filters ─────────────────────────────────────
        # Bull screener has columns: Catalyst (str), Score (0-100).
        # Recovery screener has:    Signal_Label (str), Score (0-20).
        # We treat them uniformly by detecting which is present.
        picks = picks_full.copy()
        if not picks.empty:
            cat_col = "Catalyst" if "Catalyst" in picks.columns else (
                       "Signal_Label" if "Signal_Label" in picks.columns else None)
            if require_catalyst and cat_col:
                picks = picks[picks[cat_col].astype(str).str.strip()
                                .isin(("None","nan","CB-Watch")) == False]
            if min_score > 0 and "Score" in picks.columns:
                picks = picks[pd.to_numeric(picks["Score"], errors="coerce")
                                .fillna(0) >= min_score]
            # v2.8 (Week 4): sector rotation overlay — drop picks in unfavorable sectors
            if sector_rotation != "off" and not picks.empty:
                try:
                    import sector_rotation as _sr
                    picks, _rdiag = _sr.filter_picks_by_rotation(
                        picks, as_of=anchor, mode=sector_rotation)
                    _rdiag["anchor"] = str(anchor)
                    rotation_diag.append(_rdiag)
                    print(f"   [rotation:{sector_rotation}] kept {_rdiag['n_out']}/"
                          f"{_rdiag['n_in']} picks "
                          f"(dropped: {_rdiag.get('dropped_by_sector', {})})")
                except Exception as _e:
                    print(f"   [rotation] failed: {_e}")
            if top_n is not None and "Score" in picks.columns and not picks.empty:
                # v2 hook: sector cap + RS_Momentum tiebreak when v2 flags set;
                # falls back to plain Score-desc sort otherwise.
                try:
                    import v2_fixes as _v2
                    picks = _v2.select_top_n(picks, top_n)
                except Exception:
                    picks = picks.sort_values("Score", ascending=False).head(top_n)

        # ── Recompute forward returns + summary on the filtered set ─────
        # v2.6 (2026-05-21): Use realistic simulator with SL/T1/T2/trail/commission
        # if picks have Entry+SL_pct+T1_pct cols (Bull screener output does).
        if picks.empty:
            perf = pd.DataFrame()
            s    = {"n": 0, "n_complete": 0,
                     "note": "no picks survived the filter"}
        else:
            if all(c in picks.columns for c in ["Entry", "SL_pct", "T1_pct"]):
                perf = _replay.forward_returns_with_exits(
                    picks, anchor, forward_days,
                    use_catalyst_windows=catalyst_windows)
            else:
                syms = picks["Symbol"].astype(str).tolist()
                perf = _replay.forward_returns(syms, anchor, forward_days)
            # v2.8: when catalyst-windows are active, use per-trade matched
            # alpha (Return_pct − benchmark over same horizon) rather than the
            # single anchor-level bench.
            if catalyst_windows and not perf.empty and "Alpha_Matched_pct" in perf.columns:
                # Per-trade alpha is already in perf; pass mean as the "bench"
                # for _summarize() so its alpha_vs_bench column reflects matched alpha.
                matched_mean = perf["Alpha_Matched_pct"].dropna().mean()
                ret_mean     = perf["Return_pct"].dropna().mean()
                # _summarize computes alpha = mean_ret - bench, so we pass
                # bench = ret_mean - matched_alpha_mean to recover matched_alpha.
                synthetic_bench = (float(ret_mean) - float(matched_mean)
                                    if pd.notna(ret_mean) and pd.notna(matched_mean) else bench)
                s = _replay._summarize(perf, synthetic_bench)
            else:
                s = _replay._summarize(perf, bench)

        summary_rows.append({
            "as_of":             anchor,
            "picks_universe":    int(len(picks_full)),
            "picks_filtered":    int(len(picks)),
            "picks_with_data":   int(s.get("n_complete", 0)),
            "win_rate_pct":      s.get("win_rate_pct"),
            "avg_return_pct":    s.get("avg_return_pct"),
            "median_return_pct": s.get("median_return_pct"),
            "best_pct":          s.get("best_pct"),
            "worst_pct":         s.get("worst_pct"),
            "benchmark_pct":     bench,
            "alpha_pct":         s.get("alpha_vs_bench"),
            # v2.3 E-5: drawdown quality metrics
            "avg_max_dd_pct":    s.get("avg_max_drawdown_pct"),
            "worst_max_dd_pct":  s.get("worst_max_drawdown_pct"),
            "risk_reward":       s.get("risk_reward_ratio"),
            "avg_max_runup_pct": s.get("avg_max_runup_pct"),
            # v2.6: risk-adjusted ratios from realistic simulator
            "sharpe_ratio":      s.get("sharpe_ratio"),
            "sortino_ratio":     s.get("sortino_ratio"),
            "calmar_ratio":      s.get("calmar_ratio"),
            "duration_s":        result.get("duration_s"),
        })

        # Wide details: combine picks + performance for this anchor
        if not picks.empty and not perf.empty and "Symbol" in picks.columns:
            combined = picks.merge(perf, on="Symbol", how="left")
            combined.insert(0, "as_of", anchor)
            detail_frames.append(combined)

        # v2.7 (Week 3): update equity curve and evaluate kill switch
        anchor_alpha = s.get("alpha_vs_bench") if isinstance(s, dict) else None
        if anchor_alpha is None:
            anchor_alpha = 0.0
        equity_curve.append(equity_curve[-1] + float(anchor_alpha) if equity_curve
                              else float(anchor_alpha))
        if float(anchor_alpha) < 0:
            consec_losses += 1
        else:
            consec_losses = 0

        # Trigger A: consecutive losing anchors
        if kill_switch_losses > 0 and consec_losses >= kill_switch_losses:
            print(f"   [!] kill-switch armed: {consec_losses} consecutive losing anchors "
                  f"(threshold {kill_switch_losses}) — next anchor halted")
            halt_engaged = True
        # Trigger B: peak-to-trough drawdown on cumulative alpha (since last halt)
        if kill_switch_dd > 0 and equity_curve:
            since_halt_peak = max(since_halt_peak, equity_curve[-1])
            dd = since_halt_peak - equity_curve[-1]
            if dd >= kill_switch_dd:
                print(f"   [!] kill-switch armed: equity DD {dd:.2f}% from since-halt peak "
                      f"{since_halt_peak:.2f}% (threshold {kill_switch_dd}%) — next anchor halted")
                halt_engaged = True

    summary_df = pd.DataFrame(summary_rows)
    details_df = (pd.concat(detail_frames, ignore_index=True)
                    if detail_frames else pd.DataFrame())

    # ─── Aggregate ───────────────────────────────────────────────────────
    aggregate = {
        "n_anchors":         len(summary_rows),
        "n_picks_total":     int(summary_df["picks_filtered"].fillna(0).sum())
                                if not summary_df.empty else 0,
        "n_picks_complete":  int(summary_df["picks_with_data"].fillna(0).sum())
                                if not summary_df.empty else 0,
        "screener":          screener,
        "forward_days":      forward_days,
        "universe_size":     len(universe),
        "min_score":         min_score,
        "require_catalyst":  require_catalyst,
        "top_n":             top_n,
        "duration_s":        round(time.time() - t0, 2),
    }
    if not summary_df.empty:
        rets   = summary_df["avg_return_pct"].dropna()
        alphas = summary_df["alpha_pct"].dropna()
        winrt  = summary_df["win_rate_pct"].dropna()
        aggregate.update({
            "anchor_avg_return_pct":   round(float(rets.mean()), 2)   if len(rets)   else None,
            "anchor_median_return_pct": round(float(rets.median()), 2) if len(rets)   else None,
            "anchor_avg_alpha_pct":    round(float(alphas.mean()), 2) if len(alphas) else None,
            "anchor_median_alpha_pct": round(float(alphas.median()), 2) if len(alphas) else None,
            "alpha_hit_rate_pct":      round(float((alphas > 0).sum() / len(alphas) * 100), 1)
                                          if len(alphas) else None,
            "anchor_avg_winrate_pct":  round(float(winrt.mean()), 1)  if len(winrt)  else None,
            "best_anchor_alpha":      (float(alphas.max()) if len(alphas) else None),
            "worst_anchor_alpha":     (float(alphas.min()) if len(alphas) else None),
        })
        # v2.3 E-5: aggregate drawdown quality across anchors
        dd_col = summary_df["avg_max_dd_pct"].dropna()
        rr_col = summary_df["risk_reward"].dropna()
        if len(dd_col):
            aggregate["anchor_avg_max_dd_pct"]   = round(float(dd_col.mean()), 2)
            aggregate["anchor_worst_max_dd_pct"] = round(float(dd_col.min()), 2)
        if len(rr_col):
            aggregate["anchor_avg_risk_reward"]  = round(float(rr_col.mean()), 2)
        # v2.6: risk-adjusted ratios (averaged across anchors)
        for k in ("sharpe_ratio", "sortino_ratio", "calmar_ratio"):
            if k in summary_df.columns:
                col = summary_df[k].dropna()
                if len(col):
                    aggregate[f"anchor_avg_{k}"] = round(float(col.mean()), 2)

    # v2.8 (Week 4): sector rotation telemetry
    aggregate["sector_rotation_mode"]         = sector_rotation
    if rotation_diag:
        total_in  = sum(d.get("n_in", 0)  for d in rotation_diag)
        total_out = sum(d.get("n_out", 0) for d in rotation_diag)
        aggregate["rotation_picks_kept_pct"]  = round(
            100 * total_out / total_in, 1) if total_in else None
        aggregate["rotation_total_dropped"]   = int(total_in - total_out)

    # v2.7 (Week 3): kill-switch + equity-curve telemetry
    aggregate["kill_switch_dd_threshold"]     = kill_switch_dd
    aggregate["kill_switch_losses_threshold"] = kill_switch_losses
    aggregate["halted_anchors"]               = halt_anchors
    aggregate["n_halted_anchors"]             = len(halt_anchors)
    if equity_curve:
        aggregate["final_cumulative_alpha_pct"] = round(float(equity_curve[-1]), 2)
        aggregate["peak_cumulative_alpha_pct"]  = round(float(max(equity_curve)), 2)
        aggregate["max_equity_drawdown_pct"]    = round(
            float(max(equity_curve) - min(equity_curve[equity_curve.index(max(equity_curve)):])
                  if len(equity_curve) > 1 else 0.0), 2)

    # v2.7 (Week 3): bootstrap CI on mean anchor alpha
    if bootstrap_n and bootstrap_n > 0 and not summary_df.empty:
        import numpy as _np
        alphas = summary_df["alpha_pct"].dropna().to_numpy(dtype=float)
        if len(alphas) >= 2:
            rng = _np.random.default_rng(42)
            n   = len(alphas)
            samples = rng.choice(alphas, size=(int(bootstrap_n), n), replace=True)
            means   = samples.mean(axis=1)
            aggregate["bootstrap_n"]            = int(bootstrap_n)
            aggregate["alpha_ci95_low"]         = round(float(_np.percentile(means, 2.5)), 2)
            aggregate["alpha_ci95_high"]        = round(float(_np.percentile(means, 97.5)), 2)
            aggregate["alpha_bootstrap_mean"]   = round(float(means.mean()), 2)
            aggregate["alpha_prob_positive_pct"]= round(float((means > 0).mean() * 100), 1)

    # ─── Persist ─────────────────────────────────────────────────────────
    sum_path = os.path.join(RUNS_DIR, f"validation_{run_id}_summary.csv")
    det_path = os.path.join(RUNS_DIR, f"validation_{run_id}_details.csv")
    meta_path = os.path.join(RUNS_DIR, f"validation_{run_id}_meta.json")
    last_ptr = os.path.join(RUNS_DIR, "LAST_RUN.txt")

    summary_df.to_csv(sum_path, index=False)
    if not details_df.empty:
        details_df.to_csv(det_path, index=False)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "anchors": anchors,
                    "aggregate": aggregate}, f, indent=2, default=str)
    with open(last_ptr, "w", encoding="utf-8") as f:
        f.write(run_id)

    return {
        "run_id":     run_id,
        "anchors":    anchors,
        "summary_df": summary_df,
        "details_df": details_df,
        "aggregate":  aggregate,
        "paths": {
            "summary": sum_path,
            "details": det_path if not details_df.empty else None,
            "meta":    meta_path,
        },
    }


def load_last_validation() -> Optional[dict]:
    """Reload the most recent validation run from disk for the dashboard."""
    last_ptr = os.path.join(RUNS_DIR, "LAST_RUN.txt")
    if not os.path.exists(last_ptr):
        return None
    try:
        with open(last_ptr, "r", encoding="utf-8") as f:
            run_id = f.read().strip()
    except Exception:
        return None
    sum_path  = os.path.join(RUNS_DIR, f"validation_{run_id}_summary.csv")
    det_path  = os.path.join(RUNS_DIR, f"validation_{run_id}_details.csv")
    meta_path = os.path.join(RUNS_DIR, f"validation_{run_id}_meta.json")
    if not os.path.exists(sum_path) or not os.path.exists(meta_path):
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    summary_df = pd.read_csv(sum_path)
    details_df = pd.read_csv(det_path) if os.path.exists(det_path) else pd.DataFrame()
    return {
        "run_id":     run_id,
        "anchors":    meta.get("anchors", []),
        "aggregate":  meta.get("aggregate", {}),
        "summary_df": summary_df,
        "details_df": details_df,
        "paths": {
            "summary": sum_path,
            "details": det_path if not details_df.empty else None,
            "meta":    meta_path,
        },
    }


def sweep_chartink_param(scan_name: str,
                            param_key: str,
                            values: list[float],
                            months_back: int = 12,
                            forward_days: int = 30,
                            base_universe: str = "nifty500",
                            scans: Optional[list[str]] = None,
                            top_n: Optional[int] = 10,
                            min_score: int = 0,
                            require_catalyst: bool = False,
                            use_fundamentals: bool = False,
                            min_conviction: float = 6.0) -> pd.DataFrame:
    """Sweep one Chartink scan parameter across a list of candidate values
    and return one summary row per value.

    For each value:
      1. Override chartink_replay.SCAN_PARAMS[scan_name][param_key] = v
      2. Run run_chartink_validation with the same kwargs across all anchors
      3. Capture the aggregate (avg alpha, hit-rate, picks total, etc.)
    The original parameter value is restored at the end.

    Returns a DataFrame indexed by value with the key aggregates as columns,
    plus persists each row's run_id so details can be re-loaded later.
    """
    import chartink_replay as _cr

    if scan_name not in _cr.SCAN_PARAMS:
        raise ValueError(f"unknown scan {scan_name!r}; "
                          f"valid: {list(_cr.SCAN_PARAMS)}")
    if param_key not in _cr.SCAN_PARAMS[scan_name]:
        raise ValueError(f"unknown param {param_key!r} for {scan_name!r}; "
                          f"valid: {list(_cr.SCAN_PARAMS[scan_name])}")

    original_val = _cr.SCAN_PARAMS[scan_name][param_key]
    rows: list[dict] = []
    sweep_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*68}\n  SWEEP  {scan_name}.{param_key}  values={values}"
            f"  base_universe={base_universe}  top_n={top_n}\n{'='*68}",
            flush=True)
    try:
        for v in values:
            _cr.SCAN_PARAMS[scan_name][param_key] = v
            print(f"\n--- {scan_name}.{param_key} = {v} ---", flush=True)
            try:
                res = run_chartink_validation(
                    months_back=months_back, forward_days=forward_days,
                    base_universe=base_universe, scans=scans, top_n=top_n,
                    min_score=min_score, require_catalyst=require_catalyst,
                    use_fundamentals=use_fundamentals,
                    min_conviction=min_conviction,
                )
                agg = res.get("aggregate", {})
                rows.append({
                    "scan":             scan_name,
                    "param":            param_key,
                    "value":            v,
                    "run_id":           res.get("run_id"),
                    "n_anchors":        agg.get("n_anchors"),
                    "avg_candidates":   agg.get("avg_candidates_per_anchor"),
                    "n_picks_total":    agg.get("n_picks_total"),
                    "avg_return_pct":   agg.get("anchor_avg_return_pct"),
                    "avg_alpha_pct":    agg.get("anchor_avg_alpha_pct"),
                    "median_alpha_pct": agg.get("anchor_median_alpha_pct"),
                    "alpha_hit_rate":   agg.get("alpha_hit_rate_pct"),
                    "avg_winrate_pct":  agg.get("anchor_avg_winrate_pct"),
                    "best_alpha":       agg.get("best_anchor_alpha"),
                    "worst_alpha":      agg.get("worst_anchor_alpha"),
                    "duration_s":       agg.get("duration_s"),
                })
            except Exception as e:
                print(f"   sweep value {v} failed: {e}", flush=True)
                rows.append({"scan": scan_name, "param": param_key,
                                "value": v, "error": str(e)})
    finally:
        _cr.SCAN_PARAMS[scan_name][param_key] = original_val
        print(f"\nrestored {scan_name}.{param_key} = {original_val}",
                flush=True)

    df = pd.DataFrame(rows)
    out_path = os.path.join(RUNS_DIR,
                              f"sweep_{sweep_id}_{scan_name}_{param_key}.csv")
    df.to_csv(out_path, index=False)
    print(f"\nSweep results saved: {out_path}")
    if not df.empty and "avg_alpha_pct" in df.columns:
        print("\n  Sweep summary:")
        cols = [c for c in ["value", "n_picks_total", "avg_return_pct",
                              "avg_alpha_pct", "alpha_hit_rate",
                              "avg_winrate_pct"] if c in df.columns]
        print(df[cols].to_string(index=False))
    return df


__all__ = ["monthly_anchors", "default_universe",
           "run_validation", "run_chartink_validation",
           "sweep_chartink_param",
           "load_last_validation", "RUNS_DIR"]


def main() -> int:
    import argparse, json as _json
    p = argparse.ArgumentParser(description="Multi-anchor screener validation")
    p.add_argument("--months",  type=int, default=12)
    p.add_argument("--forward", type=int, default=30)
    p.add_argument("--symbols", default=None,
                    help="Comma-separated custom basket; defaults to Nifty 100-ish")
    p.add_argument("--universe", default="nifty100",
                    help="Named universe: nifty100 | nifty500 | fno | watchlist:<name>")
    p.add_argument("--screener", default="bull",
                    help="Screener to validate: bull | recovery")
    # Week 3 (v2.7): risk discipline
    p.add_argument("--top_n", type=int, default=None,
                    help="Keep only top-N picks by Score (required for sector cap)")
    p.add_argument("--sector_cap", type=int, default=0,
                    help="Max picks per sector in Top-N (0 disables)")
    p.add_argument("--kill_switch_dd", type=float, default=0.0,
                    help="Halt next anchor when cum-alpha peak-to-trough DD >= X%% (0 disables)")
    p.add_argument("--kill_switch_losses", type=int, default=0,
                    help="Halt next anchor after N consecutive losing anchors (0 disables)")
    p.add_argument("--bootstrap_n", type=int, default=0,
                    help="Bootstrap iterations for alpha CI (e.g. 10000; 0 disables)")
    # Week 4 (v2.8): sector rotation overlay
    p.add_argument("--sector_rotation", default="off",
                    choices=["off", "strict", "soft"],
                    help="Drop picks whose sector isn't LEADING (strict) "
                         "or LEADING+IMPROVING (soft)")
    # v2.8 (2026-05-21): catalyst-aware forward windows
    p.add_argument("--catalyst_windows", action="store_true",
                    help="Use per-catalyst forward windows from "
                         "replay.FWD_DAYS_BY_CATALYST (POS/WYC=120-180d, "
                         "REV=90d, SWG=30d). Without this flag, all picks use --forward.")
    args = p.parse_args()

    basket = ([s.strip() for s in args.symbols.split(",") if s.strip()]
                if args.symbols else None)

    # ── Data-source assertion (19 Jun 2026) ────────────────────────────────
    # Backtests must not silently run on free yfinance data. Announce the
    # active feed; warn hard if the paid Dhan feed is OFF for a replay (mixing
    # Dhan + yfinance across symbols biases point-in-time results).
    try:
        print(f"  DATA FEED: {_dp.feed_status_banner()}")
        if not getattr(_dp, "DHAN_OK", False):
            print("  ⚠ WARNING: Dhan paid feed is OFF — this validation will run on "
                  "yfinance/nselib FALLBACK data. Point-in-time results may be "
                  "biased (different corporate-action adjustment & holiday calendar).")
    except Exception:
        pass

    def _cb(i, n, anchor):
        # printed inside run_validation; cb is here for future UIs
        pass

    result = run_validation(months_back=args.months,
                              forward_days=args.forward,
                              basket=basket,
                              universe_name=args.universe,
                              screener=args.screener,
                              top_n=args.top_n,
                              sector_cap=args.sector_cap,
                              kill_switch_dd=args.kill_switch_dd,
                              kill_switch_losses=args.kill_switch_losses,
                              bootstrap_n=args.bootstrap_n,
                              sector_rotation=args.sector_rotation,
                              catalyst_windows=args.catalyst_windows,
                              progress_cb=_cb)
    print()
    print("=" * 68)
    print(f"  VALIDATION COMPLETE  run_id={result['run_id']}")
    print("=" * 68)
    print(_json.dumps(result["aggregate"], indent=2, default=str))
    print()
    print("  Per-anchor summary:")
    print(result["summary_df"].to_string(index=False))
    print()
    print(f"  Saved to: {result['paths']['summary']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
