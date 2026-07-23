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
import os
import json

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
BULL_ARCHETYPES = {"Breakout", "Accumulation", "Pullback", "Leader", "Catalyst-Scan"}
RECOVERY_ARCHETYPES = {"Recovery-RS", "Recovery-Climax", "Recovery-Early", "Rec-Catalyst-Scan"}

# STRUCTURAL archetypes = a setup that PERSISTS (a base/pullback/leadership structure)
# vs the catalyst-scan archetypes whose thesis was a time-localized event. The
# workflows use these to decide whether a name is "catalyst-scan-ONLY" (must have a
# live catalyst / fired PA to stay actionable). Defined HERE, next to the archetype
# names, so a rename can never silently drift the two hardcoded tuples the workflows
# used to carry (P0 fix, 14-Jul-2026). If you rename an archetype above, update it
# here in the same edit.
STRUCTURAL_BULL_ARCHETYPES = {"Breakout", "Accumulation", "Pullback", "Leader"}
STRUCTURAL_RECOVERY_ARCHETYPES = {"Recovery-RS", "Recovery-Climax", "Recovery-Early"}


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
                  rr=None, rs=None, weights=None):
    """4-DIMENSION opportunity score (0-100), category/path-independent, each raw
    signal used ONCE, re-weighted for missing inputs. `weights` overrides the
    dimension weights (e.g. an OVERALL_PRESETS entry). `minervini` = mpass/8 (0-1)."""
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

    # 3. SETUP / TRIGGER — ΣPA (8+ = strong) + live catalyst + VCP base
    setup = _blend([
        (_clamp(min(sigma_pa / 8.0, 1.0) * 100, 0, 100) if sigma_pa is not None else None, W["setup_pa"]),
        ((100.0 if catalyst_live else 0.0) if catalyst_live is not None else None, W["setup_cat"]),
        ((100.0 if vcp else 0.0) if vcp is not None else None, W["setup_vcp"]),
    ])

    # 4. RISK / REWARD — R:R (3R = full). Location is already gated at GM Step 4.
    risk = _clamp(min(rr / 3.0, 1.0) * 100, 0, 100) if rr is not None else None

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


def save_board_cache(df, stamp=None, tech_stamp=None, built_tf=None) -> None:
    """Persist the built board to disk so it survives a Web Commander restart /
    browser reload (session_state is in-memory only). CSV (no pyarrow dep).
    built_tf (P0 fix, 14-Jul-2026): the Trigger-TF the snapshot was computed at —
    without it the TF-staleness guard couldn't fire after a restart, silently
    showing a 75m snapshot against a Daily selector."""
    try:
        if df is None or getattr(df, "empty", True):
            return
        import datetime
        atomic_write_text(_BOARD_CACHE, df.to_csv(index=False))
        atomic_write_text(_BOARD_META, json.dumps(
            {"stamp": stamp, "tech_stamp": tech_stamp, "built_tf": built_tf,
             "saved": datetime.datetime.now().isoformat()}))
    except Exception as e:
        _log.warning(f"save_board_cache failed (board won't survive restart): {e}")


def load_board_cache(max_age_hours: float = 24.0):
    """Load the persisted board (df, meta) if present and not older than
    max_age_hours. Returns (None, None) when absent/stale/unreadable. Used for
    instant-on after a restart — and by Auto-pilot to pre-populate the board."""
    try:
        import time as _t
        if not os.path.exists(_BOARD_CACHE):
            return None, None
        if (_t.time() - os.path.getmtime(_BOARD_CACHE)) / 3600.0 > max_age_hours:
            return None, None
        import pandas as pd
        df = pd.read_csv(_BOARD_CACHE, encoding="utf-8")
        meta = {}
        try:
            with open(_BOARD_META, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as e:
            _log.warning(f"load_board_cache: meta sidecar unreadable (stamps/TF lost): {e}")
            meta = {}
        return (df if not df.empty else None), meta
    except Exception as e:
        # P1: a truncated/corrupt cache used to read as "no board" silently.
        _log.warning(f"load_board_cache: {_BOARD_CACHE} unreadable — board starts empty: {e}")
        return None, None


def trigger_category(verdict: str, path: str) -> str:
    """Map a GM workflow verdict → the user's trigger category. Zero-drift: the
    verdict strings are exactly those compute_workflow/compute_recovery_workflow
    produce."""
    v = (verdict or "").upper()
    p = "Recovery" if path == "recovery" else "Bull"
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


def s4go_status(sigma_pa, ctx, intra_ok) -> str:
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
    if not intra_ok:
        return "n/a"
    _rv = ctx.get("relvol")
    _bar = ctx.get("bar_ok")
    g_pa  = bool(sigma_pa and sigma_pa > 0)
    g_loc = bool((ctx.get("support") or {}).get("at_support"))
    g_vol = bool(_rv is not None and _rv >= 1.0)
    g_bar = (_bar is None) or bool(_bar)          # unknown bar = don't penalize
    n = int(g_pa) + int(g_loc) + int(g_vol) + int(g_bar)
    if n == 4:
        return "4/4 GO"
    _miss = ("no PA" if not g_pa else "no loc" if not g_loc
             else "no vol" if not g_vol else "weak bar")
    return f"{n}/4 · {_miss}"


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
_CAT_RANK = {"Buy Trigger Live": 5, "Armed Wait": 4, "Wait for Pullback": 3,
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

    sides = info["sides"]
    # Empty sides = a ★-only Golden Matcher name not resolvable to a per-strategy
    # list — time it on BOTH paths, so it's never silently dropped.
    _no_side = not sides
    run_bull = ("bull" in sides) or ("both" in sides) or _no_side
    run_rec = ("recovery" in sides) or ("both" in sides) or _no_side

    cands = []          # (category, path, wf)
    if run_bull and _wfb is not None:
        cands.append((trigger_category(_wfb.get("verdict"), "bull"), "bull", _wfb))
    if run_rec and _wfr is not None:
        cands.append((trigger_category(_wfr.get("verdict"), "recovery"), "recovery", _wfr))
    if not cands:
        return None

    cands.sort(key=lambda c: _cat_rank(c[0]), reverse=True)   # most-actionable wins
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
        s4go = s4go_status(sigma_pa, ctx, ev.get("intra_ok"))
        # Record WHY this row previews as "n/a" so the header can name the cause
        # instead of the user staring at a dead column. gm_evaluate leaves
        # intra_reason None when the read SUCCEEDED or was never attempted (Daily
        # trigger-TF) — so a by-design "n/a" is never miscounted as a failure.
        if s4go == "n/a" and ev.get("intra_reason"):
            note_intra_issue(sym, ev.get("intra_reason_code"), ev.get("intra_reason"))
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
    if loaders.get("use_xray") and loaders.get("xray"):
        try:
            _xr = loaders["xray"](sym) or {}
            if not _xr.get("error"):
                pio = _xr.get("Piotroski_Score")
                xray_grade = str(_xr.get("Overall_Grade", "") or "")
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
            rr=rr, rs=mansfield, weights=loaders.get("overall_weights"))

    # Inherited archetype(s) for the WINNING path (show-all) + ★ top-conviction badge.
    _win_arche = _inh_rec if path == "recovery" else _inh_bull
    # Fallback to the union's full archetype list when the winning path inherited
    # nothing (e.g. a ★-only name, or a symbol that didn't resolve). Never crash.
    _arche = list(info.get("archetypes") or [])
    arche_txt = ", ".join(_win_arche) if _win_arche else ", ".join(_arche)

    return {
        "Symbol":     sym,
        "★":          ("★" if info.get("star") else ""),
        "Overall":    overall,
        "Category":   cat,                        # stage-1 ARM verdict (pa_fired; no bar_ok)
        "S4-GO":      s4go,                        # stage-2 preview: PA·loc·vol·bar_ok (S4 chart is final)
        "Archetype":  arche_txt,                 # inherited setup thesis (Hunter=Breakout, …)
        "Loc":        _loc_col,                  # Step-4 location caveat (blank when fine)
        "Path":       "Recovery" if path == "recovery" else "Bull",
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
        "RRGeng":     rrg_eng,
        "Tier":       info["tier"],
        "Sources":    ", ".join(dict.fromkeys(info["sources"])),
        "Stale":      ("⚠" if _stale else ""),
    }
