# gm_trigger_board.py — batch "Trigger Board" data layer for the Golden Matcher.
#
# Runs every watchlist name through the SAME GM engine (compute_workflow /
# compute_recovery_workflow) the single-symbol view uses, so the Category column
# is ZERO-DRIFT with what you see when you open a name. The Streamlit UI (button,
# data_editor, filters) stays in weinstein_commander_web; this module is the pure
# data layer: watchlist union, per-symbol classification, RRG-flag persistence.
#
# The GM engine functions live inside the web app (Streamlit-cached), so they are
# INJECTED into build_row() rather than imported — keeps this module import-safe
# and testable, and guarantees the board reuses the exact cached loaders.
#
# Watchlist tiers (per the pipeline analysis, 10 Jul 2026):
#   Rigorous  = Chartink + Screener.in vetted (Golden Matcher / Bull ALL / Rec ALL)
#   Discovery = raw Nifty-500 catalyst-only scans (Bull / Recovery Catalyst) —
#               NOT through the rigorous funnel, so lean on the GM QUALITY step.

from __future__ import annotations
import math
import os
import json
import re

# P1 (14-Jul-2026): shared GM logger — previously-swallowed errors now recorded.
# Fallback to a null logger so headless imports (run_pipeline) can never break.
try:
    from gm_log import gm_log as _log
except Exception:
    import logging as _logging
    _log = _logging.getLogger("golden_matcher_null")

_ROOT = os.path.dirname(os.path.abspath(__file__))


# atomic_write_text now lives in io_utils (shared with the matcher / catalyst
# history writers); re-exported here so the many `gm_trigger_board.atomic_write_text`
# and `from gm_trigger_board import atomic_write_text` callers keep working.
from io_utils import atomic_write_text  # noqa: E402,F401


_RRG_PATH = os.path.join(_ROOT, "gm_rrg_flags.json")
_BOARD_CACHE = os.path.join(_ROOT, "gm_board_cache.csv")     # persisted board (survives restarts)
_BOARD_META = os.path.join(_ROOT, "gm_board_cache.json")     # stamps sidecar

# RRG quadrants — the dropdown options (manually set from Strike.Money). "—" = unset.
RRG_QUADRANTS = ["—", "Leading", "Improving", "Weakening", "Lagging"]

# P1 (12 Jul 2026) — PER-STRATEGY sources so every name inherits its SETUP ARCHETYPE
# (the watchlist qualified it; the board only times it). A name in >1 list carries
# ALL its archetypes (show-all). FINAL_WATCHLIST is NOT an archetype source — it is
# the top-25-by-Combined_Score union, so its names already live in the per-strategy
# lists; membership is surfaced only as a ★ Top-Conviction badge.
# (file, label, tier, side, archetype)  side: 'bull' | 'recovery'
WATCHLISTS = [
    ("FINAL_Hunter_Picks.csv",                 "Hunter",     "Rigorous",  "bull",     "Breakout"),
    ("FINAL_EarlyBird_Picks.csv",              "EarlyBird",  "Rigorous",  "bull",     "Accumulation"),
    ("FINAL_Pullback_Picks.csv",               "Pullback",   "Rigorous",  "bull",     "Pullback"),
    ("FINAL_Leader_Picks.csv",                 "Leader",     "Rigorous",  "bull",     "Leader"),
    # At-value names from pullback_finder.py (13-Aug-2026). NOT a trigger list - it
    # ignores whether anything fired and ranks LOCATION, which is the half the board
    # structurally cannot supply. Carries the Pullback archetype, so these names get
    # pullback treatment in the timing gates rather than breakout treatment.
    ("Pullback_Candidates.csv",                "At Value",   "Discovery", "bull",     "Pullback"),
    # ETFs (24-Aug-2026). Same inherited-qualification model as every other row:
    # etf_screener QUALIFIES (liquidity, stage, RS, rotation), the board TIMES, S4
    # plans. S4 needs no change at all -- it reads the chart, and zones / S-R /
    # AVWAP / the PA battery are instrument-agnostic.
    # ONLY the liquid, non-downtrend subset arrives here; see
    # etf_screener.write_board_picks for why that gate lives upstream.
    ("FINAL_ETF_Picks.csv",                    "ETF",        "Rigorous",  "bull",     "ETF"),
    ("FINAL_CATALYST_WATCHLIST.csv",           "Bull Catalyst",     "Discovery", "bull",     "Catalyst-Scan"),
    ("FINAL_Recovery_RSLeaders.csv",           "Rec RS",     "Rigorous",  "recovery", "Recovery-RS"),
    ("FINAL_Recovery_ClimaxBounce.csv",        "Rec Climax", "Rigorous",  "recovery", "Recovery-Climax"),
    ("FINAL_Recovery_EarlyBirds.csv",          "Rec Early",  "Rigorous",  "recovery", "Recovery-Early"),
    ("FINAL_RECOVERY_CATALYST_WATCHLIST.csv",  "Recovery Catalyst", "Discovery", "recovery", "Rec-Catalyst-Scan"),
]
# Top-conviction union (top-25 by Combined_Score) — ★ badge + conviction/combined source.
STAR_SOURCE = "FINAL_WATCHLIST.csv"

# Which archetypes belong to which path (drives the still-valid guard + inherited setup).
# "Catalyst-Scan"/"Rec-Catalyst-Scan" = the discovery SOURCE (Nifty-500 catalyst-first
# scan), NOT the live catalyst field — renamed so the SETUP row no longer reads
# "Archetype Catalyst ✓ / Catalyst None ✗" (a confusing self-collision).
# PYRAMID (30-Jul-2026) — an ADD on a name already held. Same inherited-qualification
# model as every other archetype: the QUALIFIER is pyramid_logic.classify() == "ADD"
# (RRG leader + winning + pullback location), and the board TIMES it with the unchanged
# gm_evaluate(). Jay then goes to S4 for the trigger — the two-stage doctrine applied to
# adds. It is a BULL archetype so the still-valid break-down guard (Stage 3/4 or below
# 30WMA -> INVALIDATED) applies, which matters more for a position you already own.
PYRAMID_ARCHETYPE = "Pyramid"
# ARMED (31-Jul-2026) — a name you set a TV alert on. The board is a snapshot rebuilt
# from watchlists that churn nightly, so an alert firing three days later landed on a
# name with no row, no levels and no thesis. The register (gm_armed.py) keeps it, and
# it re-enters here carrying the archetypes it was ARMED with — same inherited-
# qualification model as Pyramid. The badge is in BOTH sets on purpose: it must never
# be the thing that decides bull-vs-recovery, since the armed record carries the path.
try:
    from gm_armed import ARMED_ARCHETYPE
except Exception:                       # pragma: no cover — headless/offline import
    ARMED_ARCHETYPE = "Armed"
ETF_ARCHETYPE = "ETF"
BULL_ARCHETYPES = {"Breakout", "Accumulation", "Pullback", "Leader", "Catalyst-Scan",
                   PYRAMID_ARCHETYPE, ARMED_ARCHETYPE, ETF_ARCHETYPE}
RECOVERY_ARCHETYPES = {"Recovery-RS", "Recovery-Climax", "Recovery-Early",
                       "Rec-Catalyst-Scan", ARMED_ARCHETYPE}

# STRUCTURAL archetypes = a setup that PERSISTS (a base/pullback/leadership structure)
# vs the catalyst-scan archetypes whose thesis was a time-localized event. The
# workflows use these to decide whether a name is "catalyst-scan-ONLY" (must have a
# live catalyst / fired PA to stay actionable). Defined HERE, next to the archetype
# names, so a rename can never silently drift the two hardcoded tuples the workflows
# used to carry (P0 fix, 14-Jul-2026). If you rename an archetype above, update it
# here in the same edit.
# ETF is STRUCTURAL: an index fund cannot be re-qualified by a live catalyst the
# way a stock can (it is in no Chartink scan), so it must inherit rather than
# expire -- and the break-down guard still applies, which is the point.
STRUCTURAL_BULL_ARCHETYPES = {"Breakout", "Accumulation", "Pullback", "Leader",
                              PYRAMID_ARCHETYPE, ARMED_ARCHETYPE, ETF_ARCHETYPE}
STRUCTURAL_RECOVERY_ARCHETYPES = {"Recovery-RS", "Recovery-Climax", "Recovery-Early",
                                  ARMED_ARCHETYPE}

# PLAYBOOK SPLIT (5-Aug-2026) — which archetypes are a STRUCTURAL PULLBACK (buy into
# support on a retracement) vs a MOMENTUM BREAKOUT (buy strength out of a base).
# The two are opposite trades and were being judged by one gate; see _pullback_ctx.
#   Pullback   = FINAL_Pullback_Picks (SWG-PB — the Stage-2 pullback screen).
#   Pyramid    = pyramid_logic.classify() == "ADD", which REQUIRES pullback location
#                (above a rising 200-DMA, price <= close_5d x 1.10, above EMA20). An add
#                is a pullback entry on a name already held, so it belongs here.
#   Breakout   = FINAL_Hunter_Picks (the breakout screen).
# Accumulation (EarlyBird) is deliberately in NEITHER: it is a fresh Stage-2 base
# breakout, so it is not a retracement, but it also coils rather than expanding — the
# pattern inference remains the right judge for it.
PULLBACK_ARCHETYPES = {"Pullback", PYRAMID_ARCHETYPE}
BREAKOUT_ARCHETYPES = {"Breakout"}


# Authoritative resolver (dhan_ohlcv.canonical_nse_symbol) — scrip-master-backed,
# separator-insensitive. Imported guarded so a headless/offline import can never
# hard-fail the board; when unavailable, _canon_key degrades to the cheap strip.
try:
    from dhan_ohlcv import canonical_nse_symbol as _canonical_nse_symbol
except Exception:  # pragma: no cover — offline / import failure
    _canonical_nse_symbol = None


def _canon_key_strip(s: str) -> str:
    """Cheap prefix/suffix strip — the offline fallback. Upper, no NSE:/BSE:
    prefix, no .NS/.BO suffix. Does NOT collapse '_'/'-'/'&' separators."""
    s = str(s or "").strip().upper()
    for p in ("NSE:", "BSE:"):
        if s.startswith(p):
            s = s[len(p):]
    for suf in (".NS", ".BO"):
        if s.endswith(suf):
            s = s[:-len(suf)]
    return s.strip()


def _canon_key(s: str) -> str:
    """Normalize a symbol to the union-KEY form. The Single Symbol page passes
    'APOLLOHOSP.NS' (TV/yfinance style) or 'BAJAJ_AUTO' (TV underscore) while the
    watchlist union keys are bare 'APOLLOHOSP' / 'BAJAJ-AUTO' — without a
    separator-insensitive resolve the lookup misses and inheritance silently fails
    (the board-vs-single disagreement, [[gm_symbol_ns_normalization]]).

    Delegates to the authoritative scrip-master resolver (canonical_nse_symbol) so
    '_'/'-'/'&' variants collapse to ONE key — the weaker prefix/suffix-only strip
    this replaced could disagree on separators. Falls back to the cheap strip when
    the resolver is unavailable (offline/import failure) so the board never hard-
    fails. One helper so union keys and lookups can never drift."""
    if _canonical_nse_symbol is not None:
        try:
            out = str(_canonical_nse_symbol(s) or "").strip().upper()
            if out:
                return out
        except Exception:
            pass
    return _canon_key_strip(s)


# P1 (14-Jul-2026): per-call record of watchlist source problems — an unreadable
# CSV used to be SILENTLY skipped, shrinking the board universe with no signal.
# Kept OUT of the returned union dict (run_pipeline Phase 4.8 iterates its keys).
LAST_UNION_ISSUES: list = []


def _g(d: dict, *keys, default=None):
    """dict getter treating None AND float NaN as missing.

    BUG FIX (3-Aug): this module CALLED _g but never defined or imported it — the name
    lives in weinstein_commander_web_v4.0.py. Every stage_path() attempt therefore raised
    NameError and was swallowed by the surrounding try/except, so the board fell back to
    category rank on EVERY row and the stage-based Bull-vs-Recovery resolution never ran
    at all. It logged 675 times in one session before anyone noticed, which is the real
    lesson: a warning that fires on every row reads as background noise, not a failure.

    Kept as a local copy rather than an import: the web app is a Streamlit script and
    cannot be imported from here (that is why the S/R engine, the batteries and everything
    else shared between the two surfaces live in modules, not in the app).
    Semantics mirror the canonical version exactly — NaN is not None, so an unscrubbed NaN
    would otherwise sail into comparisons where it comparesFalse everywhere."""
    for k in keys:
        if k in d and d[k] is not None:
            v = d[k]
            try:
                if isinstance(v, float) and math.isnan(v):
                    continue
            except Exception:
                pass
            return v
    return default


def _gm_setting(key: str, default):
    """Read one key from gm_settings.json. Module-level (no Streamlit) so the board can
    size adds during a headless build. Fully guarded — a missing/corrupt file must never
    break the board, it just costs the add-qty display."""
    try:
        import json
        p = os.path.join(_ROOT, "gm_settings.json")
        with open(p, encoding="utf-8") as f:
            v = (json.load(f) or {}).get(key, default)
        return v if v is not None else default
    except Exception:
        return default


PORTFOLIO_PICKS = "FINAL_Portfolio_Picks.csv"

# Minimum PYRAMID add size, as a fraction of the position already held (Jay, 30-Jul:
# "it makes no sense to buy just 2 shares — it should be at least 50%"). Acts as a FLOOR
# under the 1%-risk size, which goes small on winners precisely because the raised
# Chandelier stop is close to price. When the floor binds, the Pos column says so and
# flags the risk multiple, since the add then exceeds one risk unit by construction.
PYR_ADD_MIN_FRAC = 0.50
# #addcap (31-Jul, Jay): hard ceiling on a pyramid add, as a fraction of the position
# held. 1.0 = an add can at most DOUBLE the position. This binds AFTER the risk-based
# size and the 50% floor, so the effective band is 50%..100% of held. It exists because
# q_risk = risk_rupees / (price - raised_stop) grows without bound as the Chandelier
# tightens on a winner — the sizer's most dangerous direction, and previously uncapped.
PYR_ADD_MAX_FRAC = 1.00

# Correlation-gate thresholds for the Pos column. Imported from sniper_trigger so the
# board, the sniper gate and the producer all judge an add by ONE rule.
try:
    from sniper_trigger import (CORRELATION_BLOCK as PYR_CORR_BLOCK,
                                CORRELATION_WARN as PYR_CORR_WARN)
except Exception:                                    # pragma: no cover
    PYR_CORR_BLOCK, PYR_CORR_WARN = 0.90, 0.75


def load_pyramid_adds() -> dict:
    """Holdings the auto-pilot flagged ADD, from FINAL_Portfolio_Picks.csv.

    Reads the CSV rather than recomputing: `pyramid_logic.export_portfolio_watchlist()`
    produces it in the auto-pilot run, so a board build stays a file read (the other nine
    sources work the same way) instead of re-fetching technicals for every holding.

    Only the ADD rung becomes a Pyramid row. TRIM / REDUCE / EXIT are in the file — it is
    a full portfolio watchlist — but they are sells and belong on the Pyramid and Risk
    Shield pages, not on a buy board.

    Add SIZE is NOT computed here and NOT in the CSV. Capital and `pyr_risk_pct` are UI
    settings that change without re-running the pipeline, and the risk unit must be
    measured against the LIVE price — so sizing happens in `_pos_text()` at row-build
    time, where the board already holds the CMP it just fetched. Sizing off the held
    average instead silently produced no quantity on every winner, because a raised
    Chandelier sits ABOVE the average by definition. Jay's convention (30-Jul): 1% per
    add, against the raised stop the file carries in Add_SL — bounded (31-Jul) to the
    band 50%..100% of the held quantity (PYR_ADD_MIN_FRAC / PYR_ADD_MAX_FRAC), so an add
    is never a token order and never exceeds the position it reinforces.

    Returns {} on any failure — a portfolio-source problem must never take the board down.
    """
    import pandas as pd
    out: dict = {}
    p = os.path.join(_ROOT, PORTFOLIO_PICKS)
    if not os.path.exists(p):
        return out                       # absent = auto-pilot has not produced it yet
    try:
        df = pd.read_csv(p)
    except Exception as e:
        LAST_UNION_ISSUES.append(f"{PORTFOLIO_PICKS}: unreadable ({type(e).__name__})")
        _log.warning(f"portfolio picks unreadable: {e}")
        return out
    if df.empty:
        LAST_UNION_ISSUES.append(f"{PORTFOLIO_PICKS}: empty (no open positions)")
        return out
    if "Pyr_Class" not in df.columns:
        LAST_UNION_ISSUES.append(f"{PORTFOLIO_PICKS}: missing Pyr_Class — stale format")
        return out

    cap = _to_num(_gm_setting("capital", 0.0)) or 0.0
    rpc = _to_num(_gm_setting("pyr_risk_pct", 1.0)) or 1.0
    # Hard rupee ceiling per position (S4 size_max_alloc parity). An ADD is still money
    # going into one name, so the same ceiling applies.
    mxa = _to_num(_gm_setting("max_alloc", 0.0)) or 0.0
    adds = df[df["Pyr_Class"].astype(str).str.upper() == "ADD"]
    for _, r in adds.iterrows():
        s = _canon_key(r.get("Symbol"))
        if not s or s == "NAN":
            continue
        out[s] = {"qty": _to_num(r.get("Qty")), "avg": _to_num(r.get("Avg")),
                  "r_mult": _to_num(r.get("R_Mult")), "add_sl": _to_num(r.get("Add_SL")),
                  "reason": str(r.get("Pyr_Trigger") or ""),
                  "capital": cap, "risk_pct": rpc, "max_alloc": mxa,
                  # Correlation gate, precomputed by the auto-pilot producer against the
                  # REST of the book (self excluded). Absent column = older CSV format;
                  # reported as n/a rather than defaulting to safe.
                  "corr_max": _to_num(r.get("Corr_Max")) if "Corr_Max" in df.columns else None,
                  "corr_with": (str(r.get("Corr_With") or "") if "Corr_With" in df.columns else "")}
    return out


def _armed_text(rec) -> str:
    """Board cell for an armed name: "4d · trg 1284.50". Blank for everything else.
    Guarded — a malformed register record must degrade to blank, never break a row."""
    if not isinstance(rec, dict):
        return ""
    try:
        import gm_armed as _a
        return _a.summary_line(rec)
    except Exception:
        return "armed"


def _inr(x) -> str:
    """Indian digit grouping (₹1,23,456) per the DNA formatting rule. A local copy on
    purpose — the canonical `inr()` lives in the Streamlit app, and the board must stay
    importable headless (the auto-pilot builds it with no Streamlit in the process)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if x != x or x in (float("inf"), float("-inf")):
        return "—"
    s = str(int(round(abs(x))))
    if len(s) > 3:
        rest, last3 = s[:-3], s[-3:]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:]); rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        s = ",".join(parts) + "," + last3
    return ("-₹" if x < 0 else "₹") + s


def _pos_text(pyr: dict | None, cmp_px=None) -> str:
    """The one new board column: what is already held, and what an add would be.
    Blank for every non-Pyramid row so the column costs nothing on a new-entry name.

    Sizes the add HERE because this is the first point that knows the live price. Each
    failure mode is NAMED rather than collapsing to one blank: no capital set, a raised
    stop that has caught up to price (not a viable add — the pyramid page should be
    showing a tighten), and a risk unit too small for a single share."""
    if not pyr:
        return ""
    bits = []
    if pyr.get("qty") and pyr.get("avg"):
        # Held size, then its CURRENT value at the live price (Jay, 31-Jul). The value is
        # what the 50%-of-position add floor is actually a fraction of, so showing
        # qty @ avg without it left the add quantity unanchored to anything on screen.
        # Deliberately valued at CMP, not at avg: the add is bought at CMP.
        _held = f"{int(pyr['qty'])} @ {pyr['avg']:.1f}"
        _ref0 = _to_num(cmp_px)
        if _ref0:
            _held += f" = {_inr(pyr['qty'] * _ref0)}"
        bits.append(_held)
    if pyr.get("r_mult") is not None:
        bits.append(f"{pyr['r_mult']:+.1f}R")
    sl = pyr.get("add_sl")
    if sl:
        bits.append(f"SL→{sl:.1f}")
    cap = pyr.get("capital") or 0.0
    rpc = pyr.get("risk_pct") or 1.0
    ref = _to_num(cmp_px)
    if not cap:
        bits.append("set Capital")
    elif not (sl and ref):
        bits.append("no price/stop")
    elif ref <= sl:
        bits.append("⚠ stop ≥ price")
    else:
        # RISK-BASED size: 1% of capital against the distance to the RAISED stop.
        q_risk = int((cap * rpc / 100.0) // (ref - sl))
        # #addfloor (30-Jul, Jay: "it makes no sense to buy just 2 shares, it should be at
        # least 50%"). Floor the add at half the existing position, and report which rule
        # bound so the number is never mysterious. The floor can EXCEED the 1% risk unit —
        # that is the point, and it is flagged (⚠risk) rather than hidden.
        # CORRECTION 31-Jul: the original note here claimed a tight raised stop makes the
        # risk formula "return a token size". That is BACKWARDS — q_risk divides by
        # (ref - sl), so a TIGHTER stop returns MORE shares, without bound. A token size
        # comes from small CAPITAL (the ₹50,000 placeholder), not from a tight stop.
        # #addcap (31-Jul, Jay): an add may never exceed the position it is adding TO.
        # Without it, max() was unbounded ABOVE — at ₹15L capital a 24-share SAILIFE add
        # sized to 85 shares (₹1.12L on a ₹31,680 position), and at a ₹6 stop gap to
        # 2,500 shares (₹28.75L), more than the whole account. The band is now explicit:
        #   floor  50% of held  ≤  add  ≤  100% of held   (cap wins over the floor)
        # A pyramid is a REINFORCEMENT, so 1.0x held is the natural ceiling — the add can
        # at most double the position. Which rule bound is always named.
        held = int(pyr.get("qty") or 0)
        q_floor = int(held * PYR_ADD_MIN_FRAC)
        q_cap = int(held * PYR_ADD_MAX_FRAC)
        q_want = max(q_risk, q_floor)
        # #maxalloc (5-Aug): a hard rupee ceiling OUTRANKS every share-count rule here,
        # including the 50%-of-held floor. The floor is a convenience ("don't buy 2
        # shares"); the cap is money the trader has said will not go into one name, and a
        # convenience rule must never spend past it. Reported explicitly when it binds —
        # an add quietly smaller than the floor would otherwise look like a bug.
        mxa = pyr.get("max_alloc") or 0.0
        q_money = int(mxa // ref) if (mxa > 0 and ref) else None
        # Compare against the size the OTHER rules would have chosen, so "binds" means
        # it actually changed the answer — not merely that a cap exists.
        _q_other = q_risk if held <= 0 else min(q_want, q_cap)
        _money_binds = q_money is not None and q_money < _q_other
        # held<=0 is not a real ADD row (no position to pyramid into) — leave the cap off
        # rather than silently sizing to zero, and say so.
        if _money_binds:
            bits.append(f"add {q_money} (capped ₹{mxa:,.0f}/trade)" if q_money > 0
                        else f"add <1 sh — ₹{mxa:,.0f}/trade cap below 1 share")
        elif held <= 0:
            bits.append(f"add {q_risk} @{rpc:g}% (no held qty — uncapped)" if q_risk > 0
                        else f"add <1 sh @{rpc:g}%")
        elif q_want > q_cap:
            bits.append(f"add {q_cap} (capped ≤{PYR_ADD_MAX_FRAC:.0%} of {held}) "
                        f"⚠risk {q_cap / max(q_risk, 1):.1f}×" if q_cap > q_risk
                        else f"add {q_cap} (capped ≤{PYR_ADD_MAX_FRAC:.0%} of {held})")
        elif q_floor > q_risk:
            bits.append(f"add {q_floor} (≥{PYR_ADD_MIN_FRAC:.0%} of {held}) ⚠risk {q_floor / max(q_risk, 1):.1f}×")
        elif q_risk > 0:
            bits.append(f"add {q_risk} @{rpc:g}%")
        else:
            bits.append(f"add <1 sh @{rpc:g}%")
    # CORRELATION GATE — same thresholds as sniper_trigger E7 (block 0.90 / warn 0.75),
    # measured against the REST of the book. It is surfaced, never used to hide the row:
    # correlation is a RISK read and Category is a TIMING read, so suppressing the row
    # would lose the timing information to make a risk point. Per the catalyst-gate
    # philosophy, structure fires and quality is status Jay eyeballs.
    r, w = pyr.get("corr_max"), (pyr.get("corr_with") or "")
    if r is None:
        bits.append("corr n/a")
    elif abs(r) >= PYR_CORR_BLOCK:
        bits.append(f"⛔ r{abs(r):.2f} {w}")
    elif abs(r) >= PYR_CORR_WARN:
        bits.append(f"⚠ r{abs(r):.2f} {w}")
    return " · ".join(bits)


def load_watchlist_union() -> dict:
    """Union of the per-strategy watchlists, deduped by symbol. Returns
    {SYMBOL: {'sources':[labels], 'archetypes':[…], 'tier':…, 'sides':set,
              'conviction':…, 'combined':…, 'star':bool}}.
    Each name INHERITS every archetype whose list it appears in (show-all).
    Source problems (unreadable / empty CSVs) are recorded in LAST_UNION_ISSUES."""
    import pandas as pd
    uni: dict = {}
    LAST_UNION_ISSUES.clear()

    def _read(fname):
        p = os.path.join(_ROOT, fname)
        if not os.path.exists(p):
            return None                      # absent = normal (list not generated)
        try:
            df = pd.read_csv(p)
            if df.empty:
                LAST_UNION_ISSUES.append(f"{fname}: empty (header-only)")
            return df
        except Exception as e:
            LAST_UNION_ISSUES.append(f"{fname}: unreadable ({type(e).__name__})")
            _log.warning(f"watchlist union: {fname} unreadable: {e}")
            return None

    for fname, label, tier, side, archetype in WATCHLISTS:
        df = _read(fname)
        if df is None:
            continue
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        has_conv = "Conviction" in df.columns
        has_comb = "Combined_Score" in df.columns
        for _, r in df.iterrows():
            s = _canon_key(r[col])
            if not s or s == "NAN":
                continue
            e = uni.setdefault(s, {"sources": [], "archetypes": [], "tier": "Discovery",
                                   "sides": set(), "conviction": None, "combined": None,
                                   "star": False})
            if label not in e["sources"]:
                e["sources"].append(label)
            if archetype not in e["archetypes"]:
                e["archetypes"].append(archetype)
            e["sides"].add(side)
            if tier == "Rigorous":
                e["tier"] = "Rigorous"
            if has_conv:
                cv = _to_num(r["Conviction"])
                if cv is not None and (e["conviction"] is None or cv > e["conviction"]):
                    e["conviction"] = cv
            if has_comb:
                cb = _to_num(r["Combined_Score"])
                if cb is not None and (e["combined"] is None or cb > e["combined"]):
                    e["combined"] = cb

    # ★ Top-Conviction badge (+ conviction/combined for names present ONLY here).
    star = _read(STAR_SOURCE)
    if star is not None:
        col = "Symbol" if "Symbol" in star.columns else star.columns[0]
        has_conv = "Conviction" in star.columns
        has_comb = "Combined_Score" in star.columns
        for _, r in star.iterrows():
            s = _canon_key(r[col])
            if not s or s == "NAN":
                continue
            e = uni.get(s)
            if e is None:
                # In the top-25 union but not resolvable to a per-strategy list —
                # keep it (Golden Matcher pick) with no archetype, timed generically.
                e = uni.setdefault(s, {"sources": [], "archetypes": [], "tier": "Rigorous",
                                       "sides": set(), "conviction": None, "combined": None,
                                       "star": False})
                if "Golden Matcher" not in e["sources"]:
                    e["sources"].append("Golden Matcher")
            e["star"] = True
            if has_conv:
                cv = _to_num(r["Conviction"])
                if cv is not None and (e["conviction"] is None or cv > e["conviction"]):
                    e["conviction"] = cv
            if has_comb:
                cb = _to_num(r["Combined_Score"])
                if cb is not None and (e["combined"] is None or cb > e["combined"]):
                    e["combined"] = cb

    # PYRAMID adds — a 10th source, sourced from the JOURNAL rather than a CSV. journal_sync
    # keeps the journal's OPEN rows == the live Dhan book, so these are the real holdings.
    # Tier "Rigorous": already owning a name that pyramid_logic rates ADD is a stronger
    # qualification than any scan. A held name can also appear on a watchlist — it then
    # carries BOTH archetypes, which is the show-all behaviour every other source gets.
    for s, pyr in load_pyramid_adds().items():
        e = uni.setdefault(s, {"sources": [], "archetypes": [], "tier": "Discovery",
                               "sides": set(), "conviction": None, "combined": None,
                               "star": False})
        if "Portfolio" not in e["sources"]:
            e["sources"].append("Portfolio")
        if PYRAMID_ARCHETYPE not in e["archetypes"]:
            e["archetypes"].append(PYRAMID_ARCHETYPE)
        e["sides"].add("bull")
        e["tier"] = "Rigorous"
        e["pyr"] = pyr

    # ARMED names — the register is the 11th source and the ONLY one that can keep a
    # name on the board after every watchlist has dropped it. That is the point: the
    # alert you set on Monday fires Thursday. Archetypes and path come from the RECORD
    # (what the name was when you armed it), so it keeps its original thesis and the
    # still-valid guard applies exactly as before.
    try:
        import gm_armed as _armed
        for s, rec in (_armed.active() or {}).items():
            e = uni.setdefault(s, {"sources": [], "archetypes": [], "tier": "Discovery",
                                   "sides": set(), "conviction": None, "combined": None,
                                   "star": False})
            if "Armed" not in e["sources"]:
                e["sources"].append("Armed")
            for _a in (rec.get("archetypes") or []):
                if _a not in e["archetypes"]:
                    e["archetypes"].append(_a)
            if ARMED_ARCHETYPE not in e["archetypes"]:
                e["archetypes"].append(ARMED_ARCHETYPE)
            e["sides"].add("recovery" if rec.get("path") == "recovery" else "bull")
            e["tier"] = "Rigorous"
            e["armed"] = rec
    except Exception as _ae:
        # A register failure must never shrink the board silently.
        LAST_UNION_ISSUES.append(f"gm_armed: register unavailable ({type(_ae).__name__})")
        _log.warning(f"watchlist union: armed register unavailable: {_ae}")
    return uni


def resolve_archetypes(symbol: str, uni: dict = None) -> dict:
    """Look up a symbol's inherited setup (for the Single Symbol page to stay in
    sync with the board). Returns {'archetypes':[…], 'sides':set, 'star':bool} or {}."""
    s = _canon_key(symbol)
    if not s:
        return {}
    if uni is None:
        try:
            uni = load_watchlist_union()
        except Exception:
            return {}
    e = uni.get(s)
    if not e:
        return {}
    return {"archetypes": list(e.get("archetypes") or []),
            "sides": set(e.get("sides") or set()),
            "star": bool(e.get("star"))}


def _to_num(v):
    try:
        import math
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _clamp(x, lo, hi):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return lo


def _vol_fmt(v):
    """Compact share-count format (fallback when delivery % is unavailable)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return ""
    if v >= 1e7:
        return f"{v / 1e7:.1f}Cr"
    if v >= 1e5:
        return f"{v / 1e5:.1f}L"
    if v >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


# ── Overall score — 4-DIMENSION model (de-duplicated; each raw signal used ONCE) ──
# Maps to the GM funnel: Leadership (technical quality) · Fundamentals · Setup/
# Trigger · Risk-Reward. Dimension weights are tunable here; sub-weights blend the
# raw signals inside each dimension. Presets skew the mix by intent.
OVERALL_WEIGHTS = {
    "leadership":   0.35,   # Alpha + Minervini trend template (RS already in Alpha)
    "fundamentals": 0.25,   # Conviction / BFF-or-RFF / Piotroski (counted once)
    "setup":        0.25,   # ΣPA + live catalyst + VCP
    "risk":         0.15,   # R:R
    # sub-weights (constant across presets)
    "lead_alpha": 0.6, "lead_min": 0.4,
    "setup_pa": 0.5, "setup_cat": 0.3, "setup_vcp": 0.2,
}
OVERALL_PRESETS = {          # only the 4 dimension weights change per mode
    "Balanced":  {"leadership": 0.35, "fundamentals": 0.25, "setup": 0.25, "risk": 0.15},
    "Hunting":   {"leadership": 0.20, "fundamentals": 0.15, "setup": 0.40, "risk": 0.25},   # find live triggers
    "Watchlist": {"leadership": 0.45, "fundamentals": 0.35, "setup": 0.12, "risk": 0.08},   # rank by quality
}
USE_LEGACY_OVERALL = False   # flip True to fall back to the old flat formula


def _blend(parts):
    """Weighted mean over the (value_0_100, weight) pairs that are present — None
    values drop out and the weights renormalize (no zero-fill). None if all missing."""
    p = [(v, w) for v, w in parts if v is not None and w]
    if not p:
        return None
    return sum(v * w for v, w in p) / sum(w for _, w in p)


def overall_score(alpha=None, minervini=None, conviction=None, bff=None, rff_base=None,
                  piotroski=None, sigma_pa=None, catalyst_live=None, vcp=None,
                  rr=None, rs=None, wcl_total=None, choch_count=None, vp_s=None, weights=None):
    """4-DIMENSION opportunity score (0-100), enhanced with WCL v1.2 & S4 v5.0 Context,
    Structure Health, and Volume Profile. Each raw signal used ONCE, re-weighted for missing inputs."""
    W = dict(OVERALL_WEIGHTS)
    if weights:
        W.update(weights)

    # 1. LEADERSHIP — Alpha + Minervini trend template (RS lives inside Alpha)
    lead = _blend([
        (_clamp(alpha, 0, 100) if alpha is not None else None, W["lead_alpha"]),
        (_clamp(minervini * 100, 0, 100) if minervini is not None else None, W["lead_min"]),
    ])
    if lead is None and rs is not None:          # fallback: momentum tilt if Alpha absent
        lead = _clamp(50 + rs, 0, 100)

    # 2. FUNDAMENTALS — Conviction / BFF-or-RFF / Piotroski, counted ONCE (equal blend)
    _fp = []
    if conviction is not None:
        _fp.append((_clamp(conviction * 10, 0, 100), 1.0))
    _fnd = None
    if bff and bff.get("score") is not None:
        _fnd = bff["score"] / 5.0 * 100
    elif rff_base is not None:
        _fnd = rff_base / 6.0 * 100
    if _fnd is not None:
        _fp.append((_clamp(_fnd, 0, 100), 1.0))
    if piotroski is not None:
        _fp.append((_clamp(piotroski / 9.0 * 100, 0, 100), 1.0))
    fund = _blend(_fp)

    # 3. SETUP / TRIGGER — ΣPA + live catalyst + VCP base + WCL Context Score
    wcl_score_norm = _clamp((wcl_total + 10) / 20.0 * 100, 0, 100) if wcl_total is not None else None
    setup = _blend([
        (_clamp(min(sigma_pa / 8.0, 1.0) * 100, 0, 100) if sigma_pa is not None else None, 0.40),
        ((100.0 if catalyst_live else 0.0) if catalyst_live is not None else None, 0.20),
        ((100.0 if vcp else 0.0) if vcp is not None else None, 0.15),
        (wcl_score_norm, 0.25),
    ])

    # 4. RISK / QUALITY — R:R (3R = full) + SMC Structure Health + Volume Profile Location
    rr_score = _clamp(min(rr / 3.0, 1.0) * 100, 0, 100) if rr is not None else None
    struct_score = (100.0 if choch_count <= 1 else (50.0 if choch_count <= 3 else 0.0)) if choch_count is not None else None
    vp_score = (100.0 if vp_s >= 3 else (75.0 if vp_s >= 1 else (35.0 if vp_s >= -1 else 0.0))) if vp_s is not None else None
    
    risk = _blend([
        (rr_score, 0.60),
        (struct_score, 0.20),
        (vp_score, 0.20),
    ])

    overall = _blend([
        (lead, W["leadership"]),
        (fund, W["fundamentals"]),
        (setup, W["setup"]),
        (risk, W["risk"]),
    ])
    return None if overall is None else round(overall, 1)


def overall_score_legacy(combined=None, conviction=None, alpha=None, bff=None,
                         rff_base=None, rr=None, rs=None, piotroski=None):
    """OLD flat formula (kept for comparison; Combined double-counts Conviction).
    Combined 0.40 · Conviction 0.15 · Alpha 0.15 · Fundamentals 0.15 · R:R 0.10 ·
    RS 0.05 · Piotroski 0.10, reweighted for missing."""
    parts = []
    if combined is not None:
        parts.append((_clamp(combined, 0, 100), 0.40))
    if conviction is not None:
        parts.append((_clamp(conviction * 10, 0, 100), 0.15))
    if alpha is not None:
        parts.append((_clamp(alpha, 0, 100), 0.15))
    fnd = None
    if bff and bff.get("score") is not None:
        fnd = bff["score"] / 5.0 * 100
    elif rff_base is not None:
        fnd = rff_base / 6.0 * 100
    if fnd is not None:
        parts.append((_clamp(fnd, 0, 100), 0.15))
    if rr is not None:
        parts.append((_clamp(rr / 3.0 * 100, 0, 100), 0.10))
    if rs is not None:
        parts.append((_clamp(50 + rs, 0, 100), 0.05))
    if piotroski is not None:
        parts.append((_clamp(piotroski / 9.0 * 100, 0, 100), 0.10))
    if not parts:
        return None
    return round(sum(v * w for v, w in parts) / sum(w for _, w in parts), 1)


def rrg_load() -> dict:
    try:
        with open(_RRG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        # P1: a corrupt flags file used to read as {} and the next save WIPED all
        # RRG flags silently. Log it loudly — the flags are hand-curated state.
        _log.warning(f"rrg_load: {_RRG_PATH} unreadable (flags may be lost on next save): {e}")
        return {}


def rrg_save(d: dict) -> None:
    try:
        atomic_write_text(_RRG_PATH, json.dumps(d, indent=2))
    except Exception as e:
        _log.warning(f"rrg_save failed (RRG flags not persisted): {e}")


def board_cache_paths(tf: str = None):
    """(csv, json) cache paths for a Trigger-TF. PER-TF (30-Jul) because two pop-out
    windows on different TFs shared ONE file: the 125m window displayed the 75m board and
    each rebuild clobbered the other's snapshot. A 75m main window and a 75m pop-out still
    share, which is correct — same TF, same board. tf=None keeps the legacy paths."""
    if not tf:
        return _BOARD_CACHE, _BOARD_META
    sfx = str(tf).replace(".", "").replace("/", "")
    return (os.path.join(_ROOT, f"gm_board_cache_{sfx}.csv"),
            os.path.join(_ROOT, f"gm_board_cache_{sfx}.json"))


def save_board_cache(df, stamp=None, tech_stamp=None, built_tf=None, tf=None) -> None:
    """Persist the built board to disk so it survives a Web Commander restart /
    browser reload (session_state is in-memory only). CSV (no pyarrow dep).
    built_tf (P0 fix, 14-Jul-2026): the Trigger-TF the snapshot was computed at —
    without it the TF-staleness guard couldn't fire after a restart, silently
    showing a 75m snapshot against a Daily selector."""
    try:
        if df is None or getattr(df, "empty", True):
            return
        import datetime
        _csv, _meta = board_cache_paths(tf or built_tf)
        atomic_write_text(_csv, df.to_csv(index=False))
        atomic_write_text(_meta, json.dumps(
            {"stamp": stamp, "tech_stamp": tech_stamp, "built_tf": built_tf,
             "saved": datetime.datetime.now().isoformat()}))
    except Exception as e:
        _log.warning(f"save_board_cache failed (board won't survive restart): {e}")


def load_board_cache(max_age_hours: float = 24.0, tf: str = None):
    """Load the persisted board (df, meta) if present and not older than
    max_age_hours. Returns (None, None) when absent/stale/unreadable. Used for
    instant-on after a restart — and by Auto-pilot to pre-populate the board."""
    try:
        import time as _t
        _csv, _meta = board_cache_paths(tf)
        # Fall back to the legacy shared file so an existing board is not lost the first
        # time a TF-specific cache is asked for.
        if tf and not os.path.exists(_csv) and os.path.exists(_BOARD_CACHE):
            _csv, _meta = _BOARD_CACHE, _BOARD_META
        if not os.path.exists(_csv):
            return None, None
        if (_t.time() - os.path.getmtime(_csv)) / 3600.0 > max_age_hours:
            return None, None
        import pandas as pd
        df = pd.read_csv(_csv, encoding="utf-8")
        meta = {}
        try:
            with open(_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            _log.warning(f"load_board_cache: meta sidecar unreadable (stamps/TF lost): {e}")
            meta = {}
        return (df if not df.empty else None), meta
    except Exception as e:
        # P1: a truncated/corrupt cache used to read as "no board" silently.
        _log.warning(f"load_board_cache: {_BOARD_CACHE} unreadable — board starts empty: {e}")
        return None, None


def trigger_category(verdict: str, path: str, pyramid: bool = False) -> str:
    """Map a GM workflow verdict → the user's trigger category. Zero-drift: the
    verdict strings are exactly those compute_workflow/compute_recovery_workflow
    produce.

    PYRAMID ADDS DO NOT WAIT FOR A GM TRIGGER (Jay, 10-Aug-2026): "as long as the
    portfolio stock satisfies the basic criteria like stage-2 structure etc. — instead
    of waiting for a full GO from GM. However, S4 will follow its own course."

    The reasoning: a pyramid row is a position you ALREADY OWN, and `pyramid_logic`
    only rates it ADD after its own gates pass — leader (RRG + score + winning) AND
    pullback location (above a rising 200-DMA, within 10% of the 5-day close, above the
    EMA20). Re-gating that on a fresh entry TRIGGER asks a second, unrelated question.
    The structural break-down guard still applies (Pyramid is in
    STRUCTURAL_BULL_ARCHETYPES), so Stage 3/4 or a lost 30-WMA still INVALIDATES.

    Live example this made wrong: LAURUSLABS, Stage 2, structure intact, rated ADD by
    pyramid_logic, read "Armed Wait" solely because no PA pattern fired that bar.

    The S4-GO column is untouched — it keeps showing the timing detail, and S4 on the
    chart keeps its own verdict. This changes what the CATEGORY calls it, not what any
    engine computed.
    """
    v = (verdict or "").upper()
    p = "Recovery" if path == "recovery" else "Bull"
    if pyramid and not (v.startswith("INVALIDATED") or v.startswith("WATCHLIST")):
        return f"ADD ready · {p}"
    if "TRIGGER LIVE" in v:
        return f"Buy Trigger Live · {p}"
    if v.startswith("ARMED"):
        return f"Armed Wait · {p}"
    if "WAIT FOR PULLBACK" in v:
        return f"Wait for Pullback · {p}"
    if "NO CATALYST" in v or "NO RECOVERY CATALYST" in v or v.startswith("BUY-WATCH"):
        return f"No Catalyst · {p}"
    if v.startswith("INVALIDATED"):
        return f"Invalidated · {p}"
    if v.startswith("WATCHLIST"):
        return f"Watchlist · {p}"
    if "AVOID" in v or "EXIT" in v:
        return f"Avoid · {p}"
    return f"Other · {p}"


# ── PULLBACK-AWARE GO GATE — mirrors Section 4 Entry Trigger (3-Aug) ─────────────
# S4's volume and bar gates became setup-aware: a pullback is DEFINED by entering on
# volume DRY-UP with a weak-but-holding bar at support, which the old setup-blind gate
# read as failure. This mirror MUST carry the same rule, because Jay takes only 4/4
# entries off this column — an unaligned mirror would show "3/4 · no vol" on exactly the
# pullbacks S4 now calls GO, and the setups he is hunting would never reach him.
# Names are the pa_patterns.py bull battery verbatim.
PB_CONTRACTION = {
    "VCP Breakout", "Pocket Pivot", "True NR7", "★ IB-NR7 Coil", "Inside-3 (Coil)",
    "50SMA Undercut & Reclaim", "Hammer at 50-SMA", "Hammer at 200-SMA",
}
PB_EXPANSION = {
    "★★ Power Play (HTF)", "Power Play (Strong Close)", "Gap-Up Breakout",
    "Breakout Confirmed", "Stage-2 Launch", "Liq Sweep Reclaim",
}
PB_RV_FLOOR = 0.5      # S4 pb_rv_floor
RV_FLOOR    = 1.0      # S4 rv_floor

# One switch for the recovery-book warning, so turning it off after the re-baseline is a
# one-line change in a findable place rather than a hunt through the tag chain. See the
# comment at the tag site for the evidence.
RECOVERY_UNVALIDATED = True


def _pullback_ctx(ctx: dict, path: str, archetypes=None) -> bool:
    """True when S4 would take its pullback branch: a CONTRACTION pattern fired, NO
    expansion pattern did, and price sits inside a demand zone. The zone requirement is
    what stops the relaxation applying to any random quiet bar — a pullback must be AT a
    location. Recovery path is excluded: its battery is a different set entirely.

    KNOWN ARCHETYPE OVERRIDES THE INFERENCE (5-Aug-2026). The pattern test is how S4
    GUESSES the setup, because a Pine script has no archetype. The board does not have
    to guess — a name off FINAL_Pullback_Picks.csv was QUALIFIED as a pullback by the
    screen, which is information no price rule can recover. When the archetype says
    pullback, the inference is skipped.

    That matters because the inference has a real hole: a reversal bar off a demand
    zone that closes strong fires "Power Play (Strong Close)", which sits in
    PB_EXPANSION — so the textbook pullback entry disqualified ITSELF from pullback
    treatment and was then judged on a breakout's volume floor. The zone requirement
    is NOT relaxed: a known pullback still has to be AT a location, which is the whole
    discipline of the setup."""
    if path == "recovery":
        return False
    _arche = set(archetypes or [])
    _known_pb = bool((_arche & PULLBACK_ARCHETYPES) and not (_arche & BREAKOUT_ARCHETYPES))
    fired = {n for (n, f, _t, _d) in (ctx.get("pa_patterns") or []) if f}
    if not _known_pb:
        if not fired or not (fired & PB_CONTRACTION) or (fired & PB_EXPANSION):
            return False
    sup = ctx.get("support") or {}
    # Include the NATIVE TRIGGER-TF zone (3-Aug). S4's pb_ctx tests z_inDZ, which on a
    # 75/125m chart is a chart-TF zone. Checking only the D/W/M terms here meant the
    # mirror could not fire where S4 did — the board said "no vol" on exactly the
    # pullbacks S4 called GO, which is the disagreement Jay hit on ZYDUSLIFE.
    return _in_demand_zone(ctx)


def _in_demand_zone(ctx: dict) -> bool:
    """Price is AT/INSIDE a demand zone — as opposed to at a level, an AVWAP or the
    EMA20. Hoisted out of _pullback_ctx so the role check below reads the identical
    definition; two private copies of one test is exactly how the drift class starts."""
    sup = (ctx or {}).get("support") or {}
    return bool(sup.get("in_fresh_dz") or sup.get("ize_at_support")
                or sup.get("tf_zone_in") or sup.get("tf_zone_at"))


def _htf_rank(ctx: dict) -> int:
    """Rank (0-3) of the highest timeframe ABOVE the chart that also holds price in a
    demand zone — Monthly 3 · Weekly 2 · Daily 1. Mirrors S4 v9.0's `_htfNest`.

    Resolved HERE rather than in the loader because the rank is TF-RELATIVE: a daily
    zone shelters a 75m read but is merely native on a Daily board. gm_load_symbol
    stores the raw flags; `_trigger_tf` is what turns them into a rank.
    """
    sup = (ctx or {}).get("support") or {}
    flags = sup.get("htf_at")
    if not isinstance(flags, dict):
        return 0
    try:
        from zone_engine import htf_nesting
    except Exception:
        return 0
    return int(htf_nesting(flags, chart_tf=str((ctx or {}).get("_trigger_tf") or "Daily"))
               .get("htf_rank") or 0)


def _role_mismatch(ctx: dict, path: str = "bull") -> bool:
    """The fired pattern's ROLE does not match WHERE price is.

    A pattern's role says what it claims is happening; the location says where.
    IGNITION is expansion AWAY from value (a volume thrust, a gap, a strong close);
    inside a demand zone price is being ABSORBED at value. Both can be arithmetically
    true of one bar while describing opposite things, and the pair still reads as a
    clean GO.

    Measured on the live 75m board (6-Aug-2026): 3 of 7 armed names were IGNITION-only
    inside a zone — TITAN, UNOMINDA, HINDALCO. n=7, so this TAGS and never gates: it
    cannot remove a signal. It earns a gate only after a Sigma-matched measurement,
    the way the combos were tested — and the combos failed that test.

    Only the in-zone case is flagged. The converse (TENSION alone at a level) had zero
    live instances, so tagging it would assert a rule nothing supports.

    Mirrors S4's `roleMismatch`; roles come from pa_combos.ROLE, the one definition.
    """
    if not _in_demand_zone(ctx):
        return False
    try:
        from pa_combos import ROLE
    except Exception:
        return False
    fired = {n for (n, f, _t, _d) in ((ctx or {}).get("pa_patterns") or []) if f}
    roles = {ROLE[n] for n in fired if n in ROLE}
    # Unknown-role patterns (recovery-side names absent from ROLE) must not be read as
    # agreement OR as mismatch — an empty role set means we simply do not know.
    return bool(roles) and roles == {"IGNITION"}


# GATE 5 (R) — RRG "BUY OK" (Jay, 18-Aug-2026). The stock's OWN RRG vs N500 must be
# tradeable, using bull_screener._rrg_tradeable, which is the same cell-level whitelist
# as v67's f_rrg_info and S4Core.rrgInfo: LEADING->LEADING/IMPROVING, IMPROVING->LEADING,
# LAGGING->IMPROVING, WEAKENING->LEADING. Strictly narrower than "the quadrant is green".
#
# Modelled as an UPSTREAM VETO, exactly like the Stage gate below it, rather than as a
# 5th slot in the n/4 count. Two reasons: RRG is WEEKLY context, not a trigger mechanic
# like PA/loc/vol/bar; and the "n/4" string is parsed by gm_signal_log.gate_bucket and
# by the S4-GO colour rules, so re-denominating it would silently reinterpret every
# historical log row. A blocked name still shows its gate count, so nothing is hidden.
#
# RE-MEASURED AND TURNED OFF, 18-Aug-2026. The whitelist was fitted in May on the OLD
# 12/5/12 RRG pair; that morning every surface moved to the RRG Studio calibration, so
# the cells were being produced by a different function than the one whose alpha
# justified them (the file's own history records the same thing happening at v1.7).
#
# Re-measure: 473 symbols, 93,745 weekly observations, 2022-06..2026-07, matched-horizon
# alpha, chronological IS/OOS, bootstrapped by SYMBOL (overlapping windows are not
# independent, so raw n hugely overstates it). Cell alpha is reported as a DEVIATION from
# the +0.97% (4w) / +3.20% (12w) universe drift - in absolute terms almost every cell is
# "positive" and that is the equal-weighted universe, not the RRG.
#
#   whitelist                          passes    edge 4w    edge 12w
#   current 5 cells                      49%     +0.12pp     +0.00pp   <- worth nothing
#   drop IMPROVING->LEADING              33%     +0.31pp     +0.37pp
#   only LEADING->LEADING, WEAKENING->LEADING  20%  +0.54pp  +0.83pp
#
# IMPROVING->LEADING (n~15,000) is reliably NEGATIVE at both horizons (-0.33 [-0.61,-0.06]
# and -0.87 [-1.55,-0.14]) and cancels what LEADING->LEADING earns - the whitelist
# contained its own antidote. Only LEADING->LEADING and WEAKENING->LEADING are positive at
# both horizons in both windows.
#
# Jay's call: no mechanical veto; he eyeballs those two cases. R is DISPLAY-ONLY - a
# non-tradeable name is tagged "· RRG·" and still shows its gate count. Set RRG_GATE=True
# to restore the veto (and narrow the whitelist first if you do).
# Artifacts: validation_runs/rrg_cells_h{4,12}_full.csv, rrg_cell_remeasure.py.
RRG_GATE = False       # OFF 18-Aug-2026 - re-measured, see above


_RRG_BENCH_W = {}          # benchmark weekly closes, fetched once per process


def _bench_weekly_closes(bench: str = "NIFTY 500"):
    """Benchmark weekly closes, memoised. One fetch serves the whole board."""
    if bench in _RRG_BENCH_W:
        return _RRG_BENCH_W[bench]
    out = None
    try:
        import pandas as _pd, data_provider as _dp, pa_patterns as _pap
        # DAILY + the SAME resampler the stock side uses. A native 1wk fetch anchors its
        # bars differently from _confirmed_weekly_ohlcv, so the inner join in
        # calculate_jdk_rrg dropped EVERY row and the gate failed open on all 8 test
        # symbols while looking healthy. Same resampler on both legs or no alignment.
        d = _dp.fetch_ohlcv(bench, period="3y", interval="1d", use_cache=True,
                            auto_adjust=True)
        if d is not None and not d.empty:
            if isinstance(d.columns, _pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            w = _pap._confirmed_weekly_ohlcv(d)
            if w is not None and not w.empty:
                out = w["Close"].dropna()
    except Exception as e:
        _log.warning("RRG gate: benchmark weekly fetch failed (%s) - R fails open", e)
    _RRG_BENCH_W[bench] = out
    return out


def rrg_tradeable_live(daily_df):
    """Compute the stock's own RRG "BUY OK" from the DAILY frame the board already has.

    WHY THIS EXISTS: only FINAL_CATALYST_WATCHLIST.csv carries an RRG_Tradeable column.
    FINAL_GOLDEN_MATCHER.csv - 49 of the 51 board rows - does not, so a CSV-only gate
    would fail open on ~96% of the board and read as "shipped" while doing nothing.
    Computing it here makes the gate independent of which watchlist produced the row.

    Parity by construction: the weekly bars come from the same _confirmed_weekly_ohlcv
    the zone engine uses, the RS pair from rrg_engine.calculate_jdk_rrg(mode="strike_cal")
    - the RRG Studio maths - and the verdict from bull_screener._rrg_trajectory, the same
    whitelist v67 and S4Core apply. Nothing is reimplemented here.

    Returns True / False / None, where None means "could not compute" and fails OPEN.
    """
    try:
        import pandas as _pd
        import pa_patterns as _pap
        from rrg_engine import calculate_jdk_rrg as _jdk
        from bull_screener import _rrg_trajectory as _traj
        if daily_df is None or len(daily_df) < 260:      # ~52 weekly bars minimum
            return None
        w = _pap._confirmed_weekly_ohlcv(daily_df)
        if w is None or len(w) < 45:
            return None
        sec = w["Close"].dropna()
        bench = _bench_weekly_closes()
        if bench is None or sec.empty:
            return None
        rrg = _jdk(sec, bench, mode="strike_cal")
        if rrg is None or rrg.empty:
            return None
        r = rrg["RS_Ratio"].dropna()
        m = rrg["RS_Momentum"].dropna()
        if len(r) < 6 or len(m) < 6:
            return None
        rv, mv = float(r.iloc[-1]), float(m.iloc[-1])
        cur = ("LEADING" if rv >= 100 and mv >= 100 else
               "WEAKENING" if rv >= 100 else
               "LAGGING" if mv < 100 else "IMPROVING")
        return bool(_traj(r, m, cur, 4)[4])
    except Exception as e:
        _log.warning("RRG gate: live compute failed (%s) - R fails open", e)
        return None


def _rrg_ok_raw(v) -> bool:
    """The coercion ONLY - ignores RRG_GATE. Used for the display tag, which must keep
    working after the veto is switched off."""
    if v is None:
        return True
    t = str(v).strip().lower()
    if t in ("", "nan", "none", "-", "—", "n/a"):
        return True
    return t not in ("false", "0", "no", "wait", "✗ wait")


def _rrg_ok(v) -> bool:
    """Fail-OPEN. None/blank/unparseable = unknown, and an unknown must never read as a
    verdict (the ICICIAMC lesson: absent data is not a signal). CSV round-trips turn the
    bool into "True"/"False" strings, so coerce rather than trusting the type."""
    if not RRG_GATE:
        return True
    return _rrg_ok_raw(v)


def s4go_status(sigma_pa, ctx, intra_ok, path: str = "bull", archetypes=None,
                stage=None, rrg_tradeable=None) -> str:
    """The S4 Pine STAGE-2 gate mirrored → a GATES-PASSED CLOSENESS score, so near-
    triggers rank cleanly (a name one gate short of GO is a WATCH candidate, not a
    reject). Shared by BOTH the Trigger Board 'S4-GO' column and the Single Symbol page.
    Four gates: PA fired · at a location · RV ≥ 1.0 · trigger-bar closed strong (bar_ok).
      4/4 GO          — all four align (the precise entry instant; catch via the alert)
      3/4 · no vol    — armed + at location + clean bar, just needs volume  (watch)
      2/4 · no loc    — armed + one more, needs a pullback to a location    (watch)
      1/4 · no PA / …
      n/a             — no intraday trigger-TF read (can't preview)
    The leading n/4 sorts descending so the closest-to-GO float to the top. Location =
    the GM's OB/FVG/pivot twin (S4 uses IZE zones) → a strong predictor, not identical;
    the S4 chart is final. Reads the LAST CLOSED bar (gm_load_intraday drops the forming
    bar)."""
    ctx = ctx or {}
    # #dailygo (30-Jul, Jay): Daily returned "n/a" ALWAYS, because intra_ok is only ever
    # set on the 75m/125m path. But the four gates don't need intraday data — they need a
    # CLOSED bar, and the daily loader already reads the last closed daily candle. PA and
    # location were always present for Daily; relvol was too; only bar_ok was missing and
    # is now computed there with the identical formula. So: trust intra_ok when we have it,
    # and otherwise fall through IF the daily ctx actually carries the ingredients. A ctx
    # with neither relvol nor bar_ok is a genuine no-read and still returns "n/a" — the
    # distinction that matters is "no data" vs "not attempted", not the timeframe.
    if not intra_ok and ctx.get("relvol") is None and ctx.get("bar_ok") is None:
        return "n/a"
    # STAGE VETO — parity with S4's `stage_skip` (Pine: stage_gate and stage_n >= 3),
    # which outranks every verdict branch on the chart. Without it this column previewed
    # "4/4 GO" for names S4 prints as NO TRADE, and because the board sorts on this
    # column those names floated to the TOP of the GO list (Jay, 5-Aug: "why are some
    # Invalidated entries coming into S4-GO?"). The four gates are mechanical — a
    # Stage-3/4 chart can absolutely fire a pattern at a location on volume — so nothing
    # here contradicts them. The stage is simply upstream of all four.
    # Reported, never blanked: the gate count still shows, so a name one gate from GO in
    # a topping structure is still visible for what it is.
    _stg = str(stage or "")
    _stg_n = next((int(c) for c in _stg if c.isdigit()), None)
    _stage_blocked = _stg_n is not None and _stg_n >= 3
    _rv = ctx.get("relvol")
    _bar = ctx.get("bar_ok")
    g_pa  = bool(sigma_pa and sigma_pa > 0)
    # PA RECENCY (Jay, 31-Jul-2026). An NSE session is 5 x 75-min bars, so a pattern
    # that fires at 10:30 is invisible to a last-bar-only read by 11:45 — and this
    # column is where the S4-GO shortlist gets FILTERED, so that name is simply lost.
    # A PA is a STRUCTURAL event (a pattern that formed and still stands); volume,
    # location and bar-strength are CURRENT-STATE and stay strictly on the live bar.
    # So recency is allowed to satisfy the PA gate alone, and the age is ALWAYS
    # printed — a 2-bar-old trigger must never read as though it just fired.
    _recent = ctx.get("recovery_pa_recent" if path == "recovery" else "pa_recent")
    _pa_age = None
    if not g_pa and isinstance(_recent, dict) and (_recent.get("sigma") or 0) > 0:
        g_pa = True
        _pa_age = int(_recent.get("age") or 0)
    g_loc = bool((ctx.get("support") or {}).get("at_support"))
    # Pullback context relaxes the volume floor and swaps the bar test, exactly as S4
    # does. Dry-up CONFIRMS a pullback; demanding average volume is what kept them off
    # this column. It stays a floor, not a cap — a reversal bar on heavy volume is the
    # best case and must not be vetoed either.
    _pb = _pullback_ctx(ctx, path, archetypes)
    g_vol = bool(_rv is not None and _rv >= (PB_RV_FLOOR if _pb else RV_FLOOR))
    # BAR GATE — mirror S4, do not hand it out (24-Aug-2026, Jay: "a discrepancy of 1
    # or 2 gates is ok, but not 3 out of 4 failing"). This line used to return a free
    # True on every pullback row, on the reasoning that a pullback bar only has to HOLD
    # the zone — but "still in the zone" is g_loc, so the gate was counting one fact
    # twice and the board could never disagree with itself. S4:3660 is a real test:
    #     bar_ok = pb_ctx ? (close > z_inDZdist or close >= open)
    #                     : (close >= open or _bqClpos >= 0.5)
    # ctx carries no zone distal, so the closest honest mirror is the bar-strength read
    # we already have. That makes the board very slightly STRICTER than S4 on the pb
    # branch (S4 also passes a RED bar that closes above the distal) and identical off
    # it. Deliberate direction: this column is a PREDICTOR of the S4 chart, so erring
    # loose costs a false 4/4 every session while erring tight costs a rare row.
    # MEASURED before the change: 13 of 16 4/4 rows on the 125m board carried "· PB",
    # i.e. were taking this free pass.
    #
    # An UNKNOWN bar no longer passes either. "Don't penalize" was written for missing
    # data, but a missing bar read is exactly the ⧖D daily-fallback case, and there it
    # inflated the count on the timeframe that had failed to load.
    g_bar = bool(_bar)
    n = int(g_pa) + int(g_loc) + int(g_vol) + int(g_bar)
    # RECENCY DOES NOT REACH 4/4. The PA gate above accepts a pattern that fired a few
    # bars back (31-Jul); S4 has no such allowance and reads the current bar only. So a
    # recency row differs from the chart by the PA gate BY CONSTRUCTION — and "4/4" is
    # the one label that promises the chart will agree. Cap it at 3/4 and keep the age
    # tag: the name still ranks as a watch, it just stops claiming to be a GO. Without
    # this, recency + the free bar pass + the location proxy stacked to a 3-gate gap.
    if _pa_age is not None:
        n = min(n, 3)
    # KNIFE-EDGE tag. Patterns sitting on their threshold flip on a difference smaller
    # than the routine Dhan-vs-TradingView gap — NAM-INDIA read Σ6 here and Σ2 on the
    # chart for the same bar. Marking them stops that reading as a bug and stops a
    # coin-flip Σ reading as conviction. It never changes the gate count: a marginal
    # pattern still fired, and the S4 chart is still the plan of record.
    _marg = [m for m in (ctx.get("pa_marginal") or []) if m]
    _mtag = f" · {len(_marg)}⚖" if (_marg and g_pa) else ""
    # DAILY-FALLBACK TAG. If the trigger-TF read failed, the PA behind this verdict
    # is the DAILY battery, not the timeframe named on the board. Say so — an
    # unmarked fallback is how "no PA" on the 75m board meant "no PA on Daily".
    _pasrc = str((ctx or {}).get("_pa_src") or "")
    if _pasrc == "daily" and str((ctx or {}).get("_trigger_tf") or "Daily") != "Daily":
        _mtag += " · ⧖D"   # PA from the DAILY battery — intraday read failed
    # ROLE COHERENCE — display only, and it never touches the gate count. See
    # _role_mismatch: in a demand zone with nothing but an expansion pattern behind it.
    _mtag += " · ⚠role" if (g_pa and _role_mismatch(ctx, path)) else ""
    # HTF NESTING — the board's answer to S4's TF-ranked confluence term. A location
    # sheltered by a higher-timeframe demand zone is the stronger one, and the board
    # previously had no cross-TF term at all. Grading only: it never moves the gate
    # count, and it is never written back into a zone's score (so it cannot earn a
    # nested zone the 2nd test the v8.8 retention budget grants at score >= 75).
    _hr = _htf_rank(ctx)
    if g_loc and _hr:
        _mtag += " · ↑" + {1: "D", 2: "W", 3: "M"}.get(_hr, "")
    # UNVALIDATED BOOK (10-Aug-2026). The recovery side has no valid backtest behind it:
    # the only run that ever COMPLETED (validation_20260729_202824) used a 30-day forward
    # window for all 503 trades, and recovery setups are designed for 90-180 — the exact
    # window mismatch that invalidates a test outright. The fix (replay.catalyst_label_of,
    # which reads recovery's `Signal_Label` and not only `Catalyst`) landed four days
    # later, and the one post-fix attempt died at anchor 14 of 19.
    #
    # So ~22% of this board rests on no measurement. Jay's call was TAG, don't suppress:
    # the rows stay tradeable on his own read, they just stop looking measured. Display
    # only, like ⧖D and ⚠role — it never touches the gate count.
    # REMOVE THIS the moment the re-baseline reports; a permanent warning becomes wallpaper.
    if path == "recovery" and RECOVERY_UNVALIDATED:
        _mtag += " · ⚠unval"
    _age_tag = (f" · PA {_pa_age}b" if _pa_age else "") + (" · PB" if _pb else "") + _mtag
    # GATE 5 (R). DISPLAY and VETO are deliberately separate: with the veto off the tag
    # must still print, or a disabled gate silently removes the very information Jay is
    # now eyeballing. _rrg_ok() answers the GATE (and is always True when RRG_GATE is
    # False), so the tag is driven off the raw value instead.
    _rrg_raw = rrg_tradeable
    if _rrg_raw is not None and not _rrg_ok_raw(_rrg_raw):
        _mtag += " · RRG·"          # not tradeable — LEADING->LEADING / WEAKENING->LEADING is what to look for
        _age_tag += " · RRG·"
    if not _rrg_ok(rrg_tradeable) and not _stage_blocked:
        return f"⛔ RRG WAIT · gates {n}/4{_mtag}"
    if _stage_blocked:
        # Sorts BELOW every live gate count (the column sorts on the leading number) —
        # a topping structure must not head the GO list however clean its trigger looks.
        #
        # _mtag CARRIES (10-Aug-2026). This branch used to return bare, dropping the whole
        # tag chain — and 11 of 14 recovery rows land here, so most of the board's tags were
        # invisible on stage-blocked names. The one that actually cost something is ⧖D: a
        # daily-fallback row that happened to be Stage 3 could never show its fault, and
        # "count the ⧖ in the cache" is the check used to certify a whole tab as clean. It
        # was blind to every blocked row. The recency/PB tags are deliberately still omitted
        # — they describe a trigger nobody should act on here — but the DATA-QUALITY and
        # context tags must survive, because a blocked row is still a row you diagnose from.
        return f"⛔ Stage {_stg_n} · gates {n}/4{_mtag}"
    if n == 4:
        # "4/4 GO" stays reserved for all four aligning on the LIVE bar. A recent-PA
        # name scores 4/4 and sorts with them, but says so — the entry then anchors
        # to the bar that fired (S4 latches trigBar/trigHi), not to this one.
        # Tag PULLBACK 4/4s explicitly. This is the setup Jay is hunting and the one the
        # relaxed gate exists to surface, so it must be identifiable at a glance among the
        # breakout GOs — not silently mixed in with them.
        _pbt = (" · PB" if _pb else "") + _mtag
        return f"4/4 GO{_pbt}" if not _pa_age else f"4/4 · PA {_pa_age}b{_pbt}"
    _miss = ("no PA" if not g_pa else "no loc" if not g_loc
             else "no vol" if not g_vol else "weak bar")
    return f"{n}/4 · {_miss}{_age_tag}"



# ── S4-GO "n/a" observability ────────────────────────────────────────────────
# P1 (17-Jul-2026): s4go_status returns "n/a" whenever the intraday trigger-TF
# read failed. gm_load_intraday KNOWS why (auth / no data / thin history / not
# closed yet) and the Single Symbol caption shows it — but the BOARD discarded
# the reason, so an all-"n/a" column left the user with a misleading symptom: it
# reads as a scoring problem when it is a data/feed problem. Same contract as
# LAST_UNION_ISSUES — module-level, reset per build, rendered in the header strip
# — and deliberately NOT a row column (it is a build-health fact, not per-name
# decision data, and would otherwise leak into the grid and the CSV export).
LAST_INTRA_ISSUES: dict = {}       # reason_code -> {"count", "reason", "symbols"}


def reset_intra_issues() -> None:
    """Clear the intraday-failure record. Call ONCE before a board build loop."""
    LAST_INTRA_ISSUES.clear()


def note_intra_issue(sym: str, code: str, reason: str = "") -> None:
    """Record one symbol's intraday-load failure, bucketed by its stable `code`
    (gm_load_intraday's contract). Prose `reason` carries per-symbol specifics —
    bar counts, exception text — so it is kept only as ONE representative sample
    per bucket; bucketing on it would shatter the count into one row per name."""
    c = str(code or "unknown").strip() or "unknown"
    e = LAST_INTRA_ISSUES.setdefault(c, {"count": 0, "reason": str(reason or c), "symbols": []})
    e["count"] += 1
    if len(e["symbols"]) < 10:            # bounded: a sample names it, a list floods it
        e["symbols"].append(sym)


def intra_issue_summary() -> list:
    """Buckets, most-common first: [{code, count, reason, symbols}]. `symbols` is
    a sample (≤10), so it may be shorter than `count`."""
    return [{"code": c, "count": v["count"], "reason": v["reason"], "symbols": list(v["symbols"])}
            for c, v in sorted(LAST_INTRA_ISSUES.items(),
                               key=lambda kv: kv[1]["count"], reverse=True)]


# category rank for picking the primary path when a name qualifies on both sides
_CAT_RANK = {"Buy Trigger Live": 5, "ADD ready": 4.5, "Armed Wait": 4, "Wait for Pullback": 3,
             "No Catalyst": 2, "Watchlist": 1, "Invalidated": 0, "Avoid": 0, "Other": 0}


def _cat_rank(cat: str) -> int:
    return _CAT_RANK.get(str(cat).split(" · ")[0], 0)


def diff_boards(prev_df, new_df) -> list:
    """Per-symbol changes between two board snapshots (for the live 'Changed'
    strip). Returns a list of dicts, most-significant first:
        {symbol, path, cat_from, cat_to, cat_dir(+1/-1), to_go(bool),
         overall_from, overall_to, overall_dir, cmp_dir, cmp_from, cmp_to}
    Only the fields that actually changed are populated. `to_go` = entered
    'Buy Trigger Live' this tick (the toast-worthy event)."""
    if prev_df is None or new_df is None or getattr(prev_df, "empty", True) or getattr(new_df, "empty", True):
        return []
    try:
        p = prev_df.set_index("Symbol")
    except Exception as e:
        _log.warning(f"diff_boards: prev snapshot unusable (change strip empty): {e}")
        return []
    changes = []
    for _, r in new_df.iterrows():
        sym = r.get("Symbol")
        if sym is None or sym not in p.index:
            continue
        pr = p.loc[sym]
        ch = {"symbol": sym, "path": r.get("Path"), "score": 0}
        hit = False
        cf, ct = str(pr.get("Category", "")), str(r.get("Category", ""))
        if cf != ct:
            hit = True
            rf, rt = _cat_rank(cf), _cat_rank(ct)
            ch.update(cat_from=cf, cat_to=ct, cat_dir=(1 if rt > rf else -1),
                      to_go=(rt == 5 and rf < 5))
            ch["score"] += 100 + (50 if ch["to_go"] else 0)     # category flips rank highest
        of, ot = _to_num(pr.get("Overall")), _to_num(r.get("Overall"))
        if of is not None and ot is not None and abs(ot - of) >= 0.1:
            hit = True
            ch.update(overall_from=of, overall_to=ot, overall_dir=(1 if ot > of else -1))
            ch["score"] += min(50, abs(ot - of))
        cmf, cmt = _to_num(pr.get("CMP")), _to_num(r.get("CMP"))
        if cmf is not None and cmt is not None and cmf != cmt:
            hit = True
            ch.update(cmp_from=cmf, cmp_to=cmt, cmp_dir=(1 if cmt > cmf else -1))
            ch["score"] += 1
        if hit:
            changes.append(ch)
    changes.sort(key=lambda c: c["score"], reverse=True)
    return changes


def _r1(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def compute_conviction(symbol, tech_score, path):
    """Compute Conviction (0-10) + Combined (0-100) the SAME way the matcher does
    — `conviction_passthrough` → `brute_force_match_pro.calculate_conviction_score`
    fed by screener.in-primary fundamentals (`fundamental_hub`) — so it's zero-drift
    with FINAL_WATCHLIST. Used to FILL names whose source list lacked a Conviction
    (an absent conviction would otherwise distort the Overall score). Returns
    (None, None) on any failure. fundamental_hub caches, so this is cheap on rebuild.
    """
    try:
        import conviction_passthrough as cp
        conv_fn = cp._get_conviction_fn("recovery" if path == "recovery" else "bull")
        if conv_fn is None:
            return None, None
        from fundamental_hub import fetch_stock_fundamentals
        fh = fetch_stock_fundamentals(f"{symbol}.NS") or {}
        row = {                                    # golden keys the conv_fn expects
            "Debt to equity":     fh.get("debt_equity"),
            "ROCE %":             fh.get("roce"),
            "ROE %":              fh.get("roe"),
            "Promoter holding %": fh.get("promoter_holding"),
            "Div Yld %":          fh.get("dividend_yield"),
            "Qtr Profit Var %":   fh.get("earnings_growth"),
            "Mar Cap Rs.Cr.":     fh.get("market_cap"),
        }
        if not any(v is not None for v in row.values()):
            return None, None
        conv = conv_fn(row)
        # tech normalization mirrors add_conviction_and_combined_score:
        # bull Score is already 0-100; recovery Score is 0-22 → ×100/22.
        tech = _to_num(tech_score)
        if tech is not None and path == "recovery":
            tech = tech / 22.0 * 100.0
        return conv, cp._calc_combined_score(conv, tech)
    except Exception as e:
        # P1: a missing Conviction distorts the Overall score (reweighted) — log why.
        _log.warning(f"compute_conviction({symbol}): failed — Overall loses the "
                     f"conviction input: {e}")
        return None, None


def build_row(sym: str, info: dict, loaders: dict, g) -> dict | None:
    """Classify ONE symbol using the injected GM engine (zero-drift).

    loaders = dict(load_symbol=gm_load_symbol, load_recovery=gm_load_recovery,
                   bull_wf=compute_workflow, rec_wf=compute_recovery_workflow)
    g       = the web app's `_g` getter helper.
    Returns a row dict, or None if the name can't be loaded.
    """
    # SINGLE SOURCE OF TRUTH — the board evaluates a name via the EXACT same
    # gm_evaluate() the Single Symbol page uses (injected as loaders["evaluate"]).
    # This is what guarantees the two surfaces can never disagree: identical
    # cmp_px, intraday overlay, inherited setup, and workflows. build_row only
    # SELECTS which path is primary (per the name's sides) and formats the row.
    _tf = loaders.get("trigger_tf") or "75m"
    ev = loaders["evaluate"](sym, _tf) or {}
    data = ev.get("data") or {}
    rec = ev.get("rec") or {}
    ctx = ev.get("ctx") or {}
    fun = ev.get("fun") or {}
    if not rec and not ctx:
        return None
    cmp_px = ev.get("cmp_px")
    mansfield = ev.get("mansfield")
    rec_r = ev.get("rec_r") or {}
    _wfb = ev.get("wf_bull")
    _wfr = ev.get("wf_rec")
    _inh_bull = ev.get("inherited_bull") or []
    _inh_rec = ev.get("inherited_rec") or []

    sides = info.get("sides") or []
    # Empty sides = a ★-only Golden Matcher name not resolvable to a per-strategy
    # list — time it on BOTH paths, so it's never silently dropped.
    _no_side = not sides
    run_bull = ("bull" in sides) or ("both" in sides) or _no_side
    run_rec = ("recovery" in sides) or ("both" in sides) or _no_side

    # A pyramid ADD is a holding, not a candidate entry — it does not wait for a GM
    # trigger. See trigger_category() for the reasoning and the LAURUSLABS case.
    _is_pyr = PYRAMID_ARCHETYPE in set(info.get("archetypes") or [])
    cands = []          # (category, path, wf)
    if run_bull and _wfb is not None:
        cands.append((trigger_category(_wfb.get("verdict"), "bull", _is_pyr), "bull", _wfb))
    if run_rec and _wfr is not None:
        cands.append((trigger_category(_wfr.get("verdict"), "recovery", _is_pyr), "recovery", _wfr))
    if not cands:
        return None

    # 29-Jul (Jay: "we have to have same logic for the mode on both GM and S4").
    # The primary path was picked purely by which side had the more actionable CATEGORY,
    # so GM and S4 could label the same name differently. Now the SHARED Weinstein 2x2
    # (wcl_context.stage_path — the single definition both surfaces use) decides first;
    # the category rank only breaks ties or acts when stage is not decisive.
    # Stage 3/4 returns "none" and is left to the break-down guards, which already
    # INVALIDATE it on both paths.
    _sp = None
    try:
        from wcl_context import stage_path
        _s150v = _g(ctx, "sma150"); _cmpv = _g(ctx, "cmp")
        _b30v = (_cmpv < _s150v) if (_cmpv is not None and _s150v) else None
        _s150p = _g(ctx, "sma150_prev")
        _dnv = (_s150v <= _s150p) if (_s150v and _s150p) else None
        _, _sp = stage_path(_b30v, _dnv)
    except Exception as e:
        _log.warning(f"{sym}: stage_path failed, falling back to category rank: {e}")
    cands.sort(key=lambda c: (1 if (_sp and c[1] == _sp) else 0, _cat_rank(c[0])), reverse=True)
    cat, path, wf = cands[0]
    # Step-4 location caveat (e.g. "extended / thin R:R") — surfaced in its own Loc
    # column so it annotates a live trigger WITHOUT fragmenting the Category filter.
    # Location never blocks the trigger; ⚠ only shows when the trigger fired at a
    # weak location.
    _loc = wf.get("loc_note") or ""
    _loc_col = (f"⚠ {_loc}" if (_loc and cat.startswith("Buy Trigger Live")) else _loc)

    # Path-appropriate fundamentals: BFF (growth) on Bull rows, RFF (recovery
    # fundamentals) on Recovery rows. Both are computed broadly, but showing only
    # the path-relevant one removes the "why both?" confusion.
    bff_txt = ""
    rff_txt = ""
    if path == "bull":
        bff = data.get("bff") or {}
        if bff.get("source") == "screener.in":
            _sc = bff.get("score"); _q = bff.get("quality", "")
            bff_txt = f"{_q} {_sc}/5" if _sc is not None else str(_q)
    else:
        _rsrc = rec_r if rec_r else rec
        rff_b = g(_rsrc, "RFF_Base")
        rff_q = g(_rsrc, "RFF_Quality")
        if rff_b is not None:
            try:
                rff_txt = f"{int(rff_b)}/6" + (f" {str(rff_q)[:4]}" if rff_q else "")
            except (TypeError, ValueError):
                rff_txt = ""

    # --- Trade plan + risk (the numbers that actually decide the trade) ---
    entry = wf.get("plan_entry") or g(rec, "Entry") or cmp_px
    sl = wf.get("plan_sl")
    t1 = wf.get("plan_t1")
    sl_pct = ((entry - sl) / entry * 100.0) if (entry and sl and entry > 0) else None
    rr = ((t1 - entry) / (entry - sl)) if (entry and sl and t1 and entry > sl) else None

    # ── ROOM — what actually stands in the way (7-Aug-2026) ────────────────────
    # The board advertised HINDALCO at "R:R 1.9, T1 1163.5" on the same bar S4
    # called it NO ROOM. R:R above measures to the PLAN's T1 — a 2R projection or
    # the 52-week high — and never asks what sits between here and there. So a
    # large number meant "the target is far", not "the path is open": ULTRACEMCO
    # read 11.6 with a pivot high 1.1% overhead.
    #
    # zone_engine.overhead_room is the port of S4's own six-source obstacle scan
    # (supply band / supply zone / non-MTTWR S/R / daily + weekly flipped pivots /
    # last pivot high). Measured over the 13 live GOs it reproduced S4 exactly:
    # ten names under 1R (HINDALCO 0.05R, GLAXO 0.0R) and three genuinely clear.
    # That gap is why nothing was reading TAKE IT on the chart while the board
    # showed 1.9R to 11.6R.
    #
    # R:R is now measured to the FIRST OBSTACLE when one exists — a target you
    # cannot reach is not a target. The plan's own T1 is kept as "T1" so the
    # numbers stay auditable against each other; only the ratio changes meaning,
    # and it changes toward the honest reading.
    room = {}
    try:
        import zone_engine as _zre
        _fr = {}
        _dfd = (data or {}).get("df")
        if _dfd is not None and len(_dfd) >= 60:
            _fr["D"] = _dfd
            try:
                import pa_patterns as _pap
                _fr["W"] = _pap._confirmed_weekly_ohlcv(_dfd)
            except Exception:
                pass
        if _fr:
            room = _zre.overhead_room(_fr, cmp_px, entry=entry,
                                      risk=(entry - sl) if (entry and sl and entry > sl) else None) or {}
    except Exception as e:
        _log(f"{sym}: overhead_room failed: {e}", "warning")
    _room_r = room.get("room_r")
    if room.get("clear"):
        room_txt = "clear"
    elif _room_r is not None:
        # When a PIVOT is what caps the trade, also show how far the next REAL
        # structure sits. CASTROLIND is 0.28R to a pivot and 2.21R to the next
        # pattern zone — that reads as a breakout-pivot setup, not a no-room one,
        # and the two numbers together say so. A pivot is a single swing high with a
        # pad, not a leg-base-leg zone; excluding pivots outright was tested and
        # rejected (three names lost their ONLY obstacle and would have read "clear"
        # with a swing high overhead), so they are kept, named, and ranked last.
        _src = str(room.get("source") or "")
        room_txt = f"{_room_r:.2f}R · {_src}".strip(" ·")
        if _src.startswith("Pv") and room.get("obstacle_real") and entry and sl and entry > sl:
            _rr = (float(room["obstacle_real"]) - float(entry)) / (float(entry) - float(sl))
            room_txt += f"  ({_rr:.2f}R to {room.get('source_real')})"
    else:
        room_txt = ""                      # unknown stays BLANK, never "clear"
    # Obstructed: the ratio that decides is the one to the obstacle, not to T1.
    if _room_r is not None and not room.get("clear"):
        rr = _room_r

    # --- Location / extension / liquidity ---
    prev = g(ctx, "prev")
    chg_pct = ((cmp_px - prev) / prev * 100.0) if (cmp_px and prev) else None
    d52 = g(ctx, "dist52wh")                    # % from 52W high (negative = below)

    # --- Quality confirmations ---
    ml = g(rec, "ML_Prob")
    vcp = bool(g(rec, "VCP_Valid"))
    rrg_eng = str(g(rec, "RRG_Quadrant", default="—"))     # engine RRG (reference)
    mpass = None
    if loaders.get("minervini"):
        try:
            mpass = loaders["minervini"](ctx, cmp_px, mansfield)[0]
        except Exception as e:
            mpass = None
            _log.warning(f"{sym}: minervini_checks failed (Minervini col blank): {e}")
    _bat = "recovery_pa_patterns" if path == "recovery" else "pa_patterns"
    _pp = g(ctx, _bat, default=[]) or []
    try:
        sigma_pa = sum(t for _n, _f, t, _x in _pp if _f)
    except Exception as e:
        sigma_pa = None
        _log.warning(f"{sym}: ΣPA aggregation failed (Setup dimension degrades): {e}")

    # --- S4-GO PREVIEW (shared s4go_status → zero-drift with the Single Symbol page):
    # the STAGE-2 gate mirrored from the S4 Pine (pa_fired · location · volume · bar_ok),
    # so the board previews what the S4 chart will show WITHOUT opening each name on TV.
    try:
        s4go = s4go_status(sigma_pa, ctx, ev.get("intra_ok"), path,
                           archetypes=info.get("archetypes"),
                           stage=g(rec, "Stage", default=""),
                           rrg_tradeable=(g(rec, "RRG_Tradeable")
                                          if g(rec, "RRG_Tradeable") is not None
                                          else rrg_tradeable_live((data or {}).get("df"))))
        # Record WHY this row previews as "n/a" so the header can name the cause
        # instead of the user staring at a dead column. gm_evaluate leaves
        # intra_reason None when the read SUCCEEDED or was never attempted (Daily
        # trigger-TF) — so a by-design "n/a" is never miscounted as a failure.
        if s4go == "n/a" and ev.get("intra_reason"):
            note_intra_issue(sym, ev.get("intra_reason_code"), ev.get("intra_reason"))

        # FUNDAMENTAL BLOCK suppresses the preview (14 Aug 2026, Jay's call).
        # S4-GO and QUALITY are independent by design - GO mirrors S4's execution
        # gate (PA · location · volume · bar) and knows nothing about BFF or size.
        # So a name the engine has REJECTED could still print 4/4, the most
        # eye-catching cell on the board, and the maximised view sorts by it. The
        # Category said SKIP but the eye went to the GO. Timing stays true; it is
        # simply not on offer, and the cell says which floor rejected it.
        if (wf or {}).get("fund_block"):
            s4go = "⛔ funda"
    except Exception as e:
        s4go = "·"
        _log.warning(f"{sym}: S4-GO preview failed: {e}")

    _stale = g(rec, "Stale_Data")

    # --- Delivery % (NSE bhavcopy, one bulk fetch) — fallback to total volume ---
    # P0 fix (14-Jul-2026): the bhavcopy dict is keyed by the RAW exchange Symbol;
    # canonicalize BOTH sides of the join so separator-variant names don't silently
    # blank to the volume fallback.
    nse = loaders.get("nse_metrics") or {}
    _k = _canon_key(sym)
    _nse_row = nse.get(sym) or nse.get(_k) or {}
    if not _nse_row:
        _nse_row = next((v for kk, v in nse.items() if _canon_key(kk) == _k), {})
    _dp = _nse_row.get("Delivery_Pct")
    vol_txt = ""
    if _dp is not None:
        try:
            vol_txt = f"{float(_dp):.0f}%"
        except (TypeError, ValueError):
            vol_txt = ""
    if not vol_txt:                              # no delivery data → total volume
        try:
            vol_txt = _vol_fmt(float(data.get("df")["Volume"].iloc[-1]))
        except Exception:
            vol_txt = ""

    # --- VCP (clear glyphs; blank only when the field is truly absent) ---
    _vcp_raw = g(rec, "VCP_Valid")
    vcp_txt = "✓" if _vcp_raw else ("—" if _vcp_raw is not None else "")

    # --- X-Ray fundamental enrichment (OPT-IN; heavy yfinance statements) ---
    #     Piotroski F-Score (0-9), X-Ray grade, P/E — the unique fields the
    #     X-Ray screener adds beyond BFF/RFF. Guarded + only when toggled on.
    pio = None
    xray_grade = ""
    pe_val = None
    _xray_loader = loaders.get("xray")
    if _xray_loader is not None:
        try:
            _xr = _xray_loader(sym) or {}
            if not _xr.get("error"):
                pio = _xr.get("Piotroski_Score")
                xray_grade = str(_xr.get("Overall_Grade", "") or "")
                # Data_Quality was RETURNED by the scorecard but never consumed here, so a
                # grade computed from 3 resolved criteria looked identical to one computed
                # from 9. Mark it: "⚠" = PARTIAL (4-6 of 9), "?" = INSUFFICIENT (<4). A
                # grade is only trustworthy at FULL.
                _xq = str(_xr.get("Data_Quality", "") or "")
                if xray_grade and _xq == "PARTIAL":
                    xray_grade += " ⚠"
                elif xray_grade and _xq == "INSUFFICIENT":
                    xray_grade += " ?"
                _pe = str((_xr.get("Raw_Metrics") or {}).get("P/E Ratio", "") or "")
                pe_val = _to_num(_pe) if _pe and _pe != "N/A" else None
        except Exception as e:
            _log.warning(f"{sym}: X-Ray enrichment failed (Piotroski/grade/P-E blank): {e}")

    # --- Conviction / Combined — CSV value (matcher-authoritative) preferred;
    #     COMPUTE the ones the source list lacked, the same way the matcher does,
    #     so an absent conviction can't distort the Overall score. ---
    conv = info.get("conviction")
    comb = info.get("combined")
    if conv is None:
        conv, _comb_c = compute_conviction(sym, g(rec, "Score"), path)
        if comb is None:
            comb = _comb_c

    # --- WCL v1.2 & S4 v5.0 Context metrics ---
    _stage_str = str(g(rec, "Stage", default=""))
    _wyk_b = ("ACCUMULATION" if (g(ctx, "acc_ok") and ("1" in _stage_str or "2" in _stage_str)) else "DISTRIBUTION" if "3" in _stage_str else "NEUTRAL")
    _vp_pos_r = g(ctx, "vp_pos", default="—")
    _dpoc_val = g(ctx, "dist_poc")
    _poc_val  = g(ctx, "poc")
    
    _wyk_s = 3 if _wyk_b == "ACCUMULATION" else (-3 if _wyk_b == "DISTRIBUTION" else 0)
    if _vp_pos_r == "ABOVE VAH":
        _vp_s = 3
        _vp_disp = "✓ ABOVE VAH"
    elif _vp_pos_r == "INSIDE VA":
        if (_dpoc_val or 0) >= 0:
            _vp_s = 1
            _vp_disp = "✓ IN VA (upper)"
        else:
            _vp_s = -1
            _vp_disp = "✗ IN VA (lower)"
    elif _vp_pos_r == "BELOW VAL":
        _vp_s = -3
        _vp_disp = "✗ BELOW VAL"
    else:
        _vp_s = 0
        _vp_disp = "—"

    # 28-Jul-2026: read the REAL WCL engine (wcl_context.py) out of the shared ctx,
    # computed once in gm_load_symbol. Previously this block scored SMC as
    # `2 if path == "bull" else -2` — literally the path name, not structure, which
    # penalised every Recovery name by 4 points by definition and could never agree
    # with the Single Symbol panel. `_choch_c` was likewise read with default=0 and
    # produced nowhere, so Struct Health was permanently CLEAN (0).
    _wcl = g(ctx, "wcl")
    _wcl = _wcl if isinstance(_wcl, dict) else None
    if _wcl:
        _wyk_b = _wcl["wyckoff"]["bias"]
        _wyk_s = _wcl["wyckoff"]["score_comp"]
        _smc_s = _wcl["smc"]["score"]
        _stg_s = _wcl["stage_score"]
        _wcl_tot = _wcl["total_final"]
        _wcl_band = _wcl["band"]
        _choch_c = _wcl["choch_count_20"]
        _struct_disp = _wcl["struct"]
        _setup_tag = _wcl["setup"].replace("✓ ", "").replace("✗ ", "").replace("● ", "")
    else:
        _smc_s = 0
        _stg_s = 3 if "2" in _stage_str else (1 if "1" in _stage_str else (-1 if "3" in _stage_str else -3))
        _wcl_tot = _wyk_s + _vp_s + _smc_s + _stg_s
        _wcl_band = "STRONG BULL" if _wcl_tot >= 9 else ("BULL" if _wcl_tot >= 4 else ("NEUTRAL" if _wcl_tot >= -3 else ("CAUTION" if _wcl_tot >= -6 else "BEAR")))
        _choch_c = None                      # unknown, NOT zero — see overall_score
        _struct_disp = "n/a"
        _setup_tag = "—"

    _wcl_disp = f"{_wcl_band} ({_wcl_tot:+d}) · {_setup_tag}"

    # --- Overall opportunity score (0-100, path/category-independent) ---
    _rff_for_score = (g(rec_r, "RFF_Base") if rec_r else g(rec, "RFF_Base"))
    _cat_up = str(g(rec, "Catalyst", default="")).upper()
    _cat_live = _cat_up not in ("", "NONE", "—", "NAN", "NA")
    _vcp_flag = True if _vcp_raw else (False if _vcp_raw is not None else None)
    if USE_LEGACY_OVERALL:
        overall = overall_score_legacy(combined=comb, conviction=conv, alpha=g(rec, "Alpha"),
                                       bff=data.get("bff"), rff_base=_rff_for_score,
                                       rr=rr, rs=mansfield, piotroski=pio)
    else:
        overall = overall_score(
            alpha=g(rec, "Alpha"),
            minervini=(mpass / 8.0 if mpass is not None else None),
            conviction=conv, bff=data.get("bff"), rff_base=_rff_for_score, piotroski=pio,
            sigma_pa=sigma_pa, catalyst_live=_cat_live, vcp=_vcp_flag,
            rr=rr, rs=mansfield, wcl_total=_wcl_tot, choch_count=_choch_c, vp_s=_vp_s,
            weights=loaders.get("overall_weights"))

    # Inherited archetype(s) for the WINNING path (show-all) + ★ top-conviction badge.
    _win_arche = _inh_rec if path == "recovery" else _inh_bull
    # Fallback to the union's full archetype list when the winning path inherited
    # nothing (e.g. a ★-only name, or a symbol that didn't resolve). Never crash.
    _arche = list(info.get("archetypes") or [])
    arche_txt = ", ".join(_win_arche) if _win_arche else ", ".join(_arche)

    return {
        "Symbol":        sym,
        "★":             ("★" if info.get("star") else ""),
        "Overall":       overall,
        "Category":      cat,                        # stage-1 ARM verdict (pa_fired; no bar_ok)
        "S4-GO":         s4go,                        # stage-2 preview: PA·loc·vol·bar_ok (S4 chart is final)
        "WCL Context":   _wcl_disp,
        "Struct Health": _struct_disp,
        "VP Position":   _vp_disp,
        "Archetype":     arche_txt,                 # inherited setup thesis (Hunter=Breakout, …)
        # Held position + the add, for Pyramid rows only (blank elsewhere). ONE column
        # rather than four: the board already has 43, and Entry/SL/R:R above carry the
        # ADD's own plan for these rows, so the only genuinely new information is what
        # is already owned.
        "Pos":           _pos_text(info.get("pyr"), cmp_px),
        # ARMED — age + the trigger level AS ARMED. The alert fires days after the
        # board that produced the plan is gone, so this cell is the bridge: it says
        # how long you have been waiting and what level you were waiting FOR. The
        # Entry/SL/T1 columns beside it are LIVE (recomputed this rebuild), so the
        # pair reads as "armed at X, now Y" — which is the comparison you need.
        # Checkbox — arm/disarm straight from the grid. Editable in BOTH render
        # paths (data_editor and the streaming AG-Grid), exactly like the RRG flag.
        "Arm":           bool(info.get("armed")),
        "Armed":         _armed_text(info.get("armed")),
        "Loc":           _loc_col,                  # Step-4 location caveat (blank when fine)
        "Path":          "Recovery" if path == "recovery" else "Bull",
        "RRG":        "—",                       # filled from json by the caller
        "Step":       wf.get("current"),
        "Conviction": _r1(conv),
        "Combined":   _r1(comb),
        "Alpha":      _r1(g(rec, "Alpha")),
        "RS":         _r1(mansfield),
        "Stage":      str(g(rec, "Stage", default="—")),
        "MLProb%":    _r1(ml),
        "Minervini":  (f"{int(mpass)}/8" if mpass is not None else ""),
        "Catalyst":   str(g(rec, "Catalyst", default="—")),
        "VCP":        vcp_txt,
        "ΣPA":        sigma_pa,
        "BFF":        bff_txt,
        "RFF":        rff_txt,
        "Piotroski":  (f"{int(pio)}/9" if pio is not None else ""),
        "XRay":       xray_grade,
        "Sector":     str(g(fun, "sector", default="") or g(rec, "Sector", default="") or ""),
        "CMP":        _r1(cmp_px),
        "PrevClose":  _r1(prev),                 # hidden; lets the live tick recompute Chg% from streaming LTP
        "Chg%":       _r1(chg_pct),
        "52WH%":      _r1(d52),
        "P/E":        _r1(pe_val),
        "Deliv%/Vol": vol_txt,
        "Entry":      _r1(entry),
        "SL":         _r1(sl),
        "SL%":        _r1(sl_pct),
        "T1":         _r1(t1),
        "R:R":        _r1(rr),
        "Room":       room_txt,
        "RRGeng":     rrg_eng,
        "Tier":       info.get("tier", "Discovery"),
        "Sources":    ", ".join(dict.fromkeys(info.get("sources") or [])),
        "Stale":      ("⚠" if _stale else ""),
    }


def s4_recovery_list(uni: dict | None = None) -> str:
    """The GM's Bull-vs-Recovery answer, as a comma-separated string to paste into S4's
    "Auto: GM Recovery list" input.

    WHY THIS EXISTS (Jay, 2-Aug-2026): "for each stock, for each timeframe, I need to
    check the mode and switch from auto to that mode. Then I might forget to change it
    back." S4 cannot ask the GM anything, and it cannot INFER the GM's answer either --
    the path is inherited from whichever screen qualified the name (REV-CB / REV-RS /
    REV-EARLY), on RFF fundamentals and watchlist history that price structure does not
    contain. TechM sits 2% off its 60-day high; no price-based rule will ever call that a
    recovery. So the GM hands S4 the answer instead of S4 guessing it.

    A name is listed when it carries ANY recovery archetype and NO bull archetype. The
    exclusion matters: a name in both lists is genuinely ambiguous, and S4's own heuristic
    (stage + drawdown) is a better tie-breaker there than an arbitrary preference here --
    forcing those to Recovery would swap one silent misclassification for another.

    Pasted ONCE per watchlist refresh; the path is a property of the NAME, so the same
    paste is correct on every timeframe.
    """
    try:
        uni = uni if uni is not None else load_watchlist_union()
    except Exception as e:                      # a board problem must not break the page
        _log.warning(f"s4_recovery_list: union unavailable: {e}")
        return ""
    out = []
    for sym, rec in (uni or {}).items():
        arche = set(rec.get("archetypes") or [])
        if not arche:
            continue
        if (arche & RECOVERY_ARCHETYPES) and not (arche & BULL_ARCHETYPES):
            out.append(str(sym).upper().strip())
    return ",".join(sorted(set(out)))


def s4_rrg_lists(uni: dict | None = None) -> dict:
    """Your MANUAL Strike.Money RRG reads, for S4's "GM RRG" inputs. (10-Aug-2026)

    Same handoff shape as s4_recovery_list / s4_pullback_list, third axis. The reason it
    is needed is the same reason those two exist: S4 cannot ask the GM anything, and it
    cannot derive this from price. S4's own RRG comes from v67's RS-Ratio/RS-Momentum
    pair — a computed quadrant. Yours is READ OFF STRIKE.MONEY on the weekly chart and
    typed into the board, and it is the one you actually trade off. Those two can and do
    disagree, and when they do the manual read wins.

    Returns FOUR lists keyed by quadrant rather than one encoded blob. Two reasons:
      * S4 parses a plain comma list with str.contains — no split loop, no per-symbol
        parsing, which matters because S4 sits ~190 compiled tokens under the ceiling.
      * A quadrant is not a boolean. Collapsing to "leading-ish" would throw away the
        IMPROVING/WEAKENING distinction, which is the whole point of an RRG.

    Only names present in `gm_rrg_flags.json` appear — an unflagged symbol is absent
    from every list and S4 falls back to its computed quadrant. Silence is not "Lagging".

    Refresh cadence is WEEKLY (you read RRG off the weekly chart), so unlike the
    pullback/recovery lists this does NOT need re-pasting after every auto-pilot run.
    """
    try:
        flags = rrg_load() or {}
    except Exception as e:
        _log.warning(f"s4_rrg_lists: flags unavailable: {e}")
        return {}
    if uni is None:
        try:
            uni = load_watchlist_union()
        except Exception:
            uni = None
    # Restrict to the current union when we have one, so the pasted strings stay short
    # and only carry names S4 could actually be looking at. No union -> emit everything.
    keys = {_canon_key(s) for s in (uni or {})} if uni else None
    out = {"Leading": [], "Improving": [], "Weakening": [], "Lagging": []}
    for sym, q in flags.items():
        qq = str(q or "").strip().capitalize()
        if qq not in out:
            continue
        s = str(sym).upper().strip()
        if keys is not None and _canon_key(s) not in keys:
            continue
        out[qq].append(s)
    return {k: ",".join(sorted(set(v))) for k, v in out.items()}


def s4_fund_lists(tf: str = None) -> dict:
    """The GM's BFF and RFF SCORES, for S4's two fundamental-score inputs. (25-Aug-2026)

    FOURTH handoff on the same pattern as s4_recovery_list / s4_pullback_list /
    s4_rrg_lists, and it exists for the strongest version of the same reason: S4 cannot
    ask the GM anything, and unlike the path or the setup it cannot even approximate
    these from price. RFF needs six fundamental fields plus Tier-B growth history against
    a request.financial() ceiling of five calls per script -- a budget the Capitulation
    Screener already spends on a two-check "RFF Lite". BFF reads screener.in's compounded
    growth table, which no Pine surface can reach at all. The numbers exist only here.

    FORMAT is "SYM:n" pairs rather than the bare symbol lists the other three use,
    because these are SCORES, not membership. A name being on a list is the whole message
    for Recovery/Pullback; for BFF/RFF the number IS the message.

    SOURCE is the BUILT BOARD, not a fresh fetch. Two reasons: it is what the board
    actually decided (so the chart cannot disagree with the row you clicked through
    from), and re-deriving would mean a screener.in page per name -- the burst that
    needed a circuit breaker. A name the board has not scored is simply absent, which S4
    renders as an em-dash: unscored and scored-badly must not look the same.

    Returns {"BFF": ..., "RFF": ..., "RANK": ...}; an empty string for any side the
    board has no scores on. Never raises -- a board problem must not take the GM
    page down.
    """
    out = {"BFF": "", "RFF": "", "RANK": ""}
    try:
        df, _meta = load_board_cache(max_age_hours=24.0, tf=tf)
    except Exception as e:
        _log.warning(f"s4_fund_lists: board cache unreadable: {e}")
        return out
    if df is None or getattr(df, "empty", True):
        return out

    def _num(v):
        """First integer in the board's display string. BFF renders 'STRONG 5/5' and
        RFF renders '6/6 FULL', so the leading number is the score in both. Returns
        None for '', nan, or a quality-only cell -- never 0, which S4 would colour as
        a hard fail on a name nothing was measured for."""
        t = str(v or "").strip()
        if not t or t.lower() == "nan":
            return None
        m = re.search(r"(\d+)", t)
        return int(m.group(1)) if m else None

    # RANK (#10) is the board's Overall composite and is a FLOAT, so it is emitted
    # whole rather than through _num -- 72.8 must not reach the chart as 72. It is the
    # one field here S4 cannot even approximate: S4 grades one chart and has no idea
    # where that chart sits among the other forty on the list.
    if "Overall" in df.columns:
        rk = []
        for _, row in df.iterrows():
            sym = _canon_key(row.get("Symbol"))
            try:
                v = float(row.get("Overall"))
            except (TypeError, ValueError):
                continue
            if sym and v == v:                       # NaN check without importing math
                rk.append(f"{sym}:{round(v, 1)}")
        out["RANK"] = ",".join(sorted(set(rk)))

    for col in ("BFF", "RFF"):
        if col not in df.columns:
            continue
        pairs = []
        for _, row in df.iterrows():
            sym = _canon_key(row.get("Symbol"))
            n = _num(row.get(col))
            if sym and n is not None:
                pairs.append(f"{sym}:{n}")
        out[col] = ",".join(sorted(set(pairs)))
    return out


def s4_bundle(uni: dict | None = None, tf: str = None) -> str:
    """EVERY handoff as ONE line, for S4's single "GM: ONE-PASTE bundle" input.

    WHY (Jay, 25-Aug-2026: "combine all five paste lists into one block"). The page
    had grown five things to copy after every rebuild. That is a CORRECTNESS problem
    rather than a convenience one: a missed paste does not blank the field in S4, it
    leaves the PREVIOUS list sitting there -- so the chart goes on applying last
    week's answer to this week's board, and nothing announces it. Five chances to
    forget, each one silent. One field is one chance.

    FORMAT  pipe-separated TAG=value, single line:
        REC=..|PB=..|RRGL=..|RRGI=..|RRGW=..|BFF=..|RFF=..|RANK=..

    EVERY tag is emitted even when its list is empty, and that is the point: an
    empty section CLEARS the corresponding input in S4. Omitting the tag would leave
    whatever was there before, which is the exact failure this replaces.

    Never raises; a section that cannot be built comes back empty rather than
    taking the page down with it.
    """
    def _safe(fn, *a, **k):
        try:
            return fn(*a, **k) or ""
        except Exception as e:
            _log.warning(f"s4_bundle: {getattr(fn, '__name__', fn)} failed: {e}")
            return ""

    try:
        uni = uni if uni is not None else load_watchlist_union()
    except Exception as e:
        _log.warning(f"s4_bundle: union unavailable: {e}")
        uni = {}

    rrg = _safe(s4_rrg_lists, uni) or {}
    if not isinstance(rrg, dict):
        rrg = {}
    fund = _safe(s4_fund_lists, tf=tf) or {}
    if not isinstance(fund, dict):
        fund = {}

    parts = [
        ("REC",  _safe(s4_recovery_list, uni)),
        ("PB",   _safe(s4_pullback_list, uni)),
        ("RRGL", rrg.get("Leading", "")),
        ("RRGI", rrg.get("Improving", "")),
        ("RRGW", rrg.get("Weakening", "")),
        ("BFF",  fund.get("BFF", "")),
        ("RFF",  fund.get("RFF", "")),
        ("RANK", fund.get("RANK", "")),
    ]
    # A pipe inside a payload would split the bundle at the wrong place. Nothing
    # upstream can produce one today (symbols and SYM:n pairs), but a stray pipe
    # would corrupt EVERY later section rather than just its own, so it is removed
    # here rather than trusted not to appear.
    return "|".join("%s=%s" % (t, str(v).replace("|", "")) for t, v in parts)


def s4_pullback_list(uni: dict | None = None) -> str:
    """The GM's PULLBACK-vs-BREAKOUT answer, for S4's "Auto: GM Pullback list" input.

    Same handoff as s4_recovery_list, one axis over. S4 has no archetype, so it infers
    the setup from the pattern mix — and that inference is what made the two surfaces
    disagree on Volume and Bar: they were grading the same candle against two different
    setups' standards. A breakout must expand on heavy volume and close strong; a
    pullback enters on volume DRY-UP with a bar that merely holds the zone. One gate
    cannot be neutral between them, so the GM hands over which one this is.

    Listed = a pullback archetype (SWG-PB screen, or a pyramid ADD, which requires
    pullback location by construction) and NO breakout archetype. The exclusion is the
    same reasoning as the recovery list: a name on both screens is genuinely ambiguous,
    and S4's pattern inference is a better tie-break there than a coin-flip here.

    Pasted ONCE per watchlist refresh — the setup is a property of the NAME.
    """
    try:
        uni = uni if uni is not None else load_watchlist_union()
    except Exception as e:
        _log.warning(f"s4_pullback_list: union unavailable: {e}")
        return ""
    out = []
    for sym, rec in (uni or {}).items():
        arche = set(rec.get("archetypes") or [])
        if not arche:
            continue
        if (arche & PULLBACK_ARCHETYPES) and not (arche & BREAKOUT_ARCHETYPES):
            out.append(str(sym).upper().strip())
    return ",".join(sorted(set(out)))
