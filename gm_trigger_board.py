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

_ROOT = os.path.dirname(os.path.abspath(__file__))
_RRG_PATH = os.path.join(_ROOT, "gm_rrg_flags.json")

# RRG quadrants — the dropdown options (manually set from Strike.Money). "—" = unset.
RRG_QUADRANTS = ["—", "Leading", "Improving", "Weakening", "Lagging"]

# (file, label, tier, side)  side: 'bull' | 'recovery' | 'both'
WATCHLISTS = [
    ("FINAL_WATCHLIST.csv",                    "Golden Matcher",    "Rigorous",  "both"),
    ("FINAL_COMBINED_BULL_PICKS.csv",          "Bull ALL",          "Rigorous",  "bull"),
    ("FINAL_COMBINED_RECOVERY_PICKS.csv",      "Recovery ALL",      "Rigorous",  "recovery"),
    ("FINAL_CATALYST_WATCHLIST.csv",           "Bull Catalyst",     "Discovery", "bull"),
    ("FINAL_RECOVERY_CATALYST_WATCHLIST.csv",  "Recovery Catalyst", "Discovery", "recovery"),
]


def load_watchlist_union() -> dict:
    """Union of the watchlists, deduped by symbol. Returns
    {SYMBOL: {'sources': [labels], 'tier': 'Rigorous'|'Discovery', 'sides': set}}.
    Rigorous membership upgrades the tier tag (a name in both is Rigorous)."""
    import pandas as pd
    uni: dict = {}
    for fname, label, tier, side in WATCHLISTS:
        p = os.path.join(_ROOT, fname)
        if not os.path.exists(p):
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        for s in df[col].dropna().astype(str):
            s = s.strip().upper().replace("NSE:", "").replace("BSE:", "")
            if not s:
                continue
            e = uni.setdefault(s, {"sources": [], "tier": "Discovery", "sides": set()})
            if label not in e["sources"]:
                e["sources"].append(label)
            e["sides"].add(side)
            if tier == "Rigorous":
                e["tier"] = "Rigorous"
    return uni


def rrg_load() -> dict:
    try:
        with open(_RRG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def rrg_save(d: dict) -> None:
    try:
        with open(_RRG_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass


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
    if v.startswith("WATCHLIST"):
        return f"Watchlist · {p}"
    if "AVOID" in v or "EXIT" in v:
        return f"Avoid · {p}"
    return f"Other · {p}"


# category rank for picking the primary path when a name qualifies on both sides
_CAT_RANK = {"Buy Trigger Live": 5, "Armed Wait": 4, "Wait for Pullback": 3,
             "No Catalyst": 2, "Watchlist": 1, "Avoid": 0, "Other": 0}


def _cat_rank(cat: str) -> int:
    return _CAT_RANK.get(cat.split(" · ")[0], 0)


def _r1(x):
    try:
        return round(float(x), 1)
    except (TypeError, ValueError):
        return None


def build_row(sym: str, info: dict, loaders: dict, g) -> dict | None:
    """Classify ONE symbol using the injected GM engine (zero-drift).

    loaders = dict(load_symbol=gm_load_symbol, load_recovery=gm_load_recovery,
                   bull_wf=compute_workflow, rec_wf=compute_recovery_workflow)
    g       = the web app's `_g` getter helper.
    Returns a row dict, or None if the name can't be loaded.
    """
    data = loaders["load_symbol"](sym) or {}
    rec = dict(data.get("rec") or {})
    ctx = dict(data.get("ctx") or {})
    ctx["bff"] = data.get("bff")
    if not rec and not ctx:
        return None

    cmp_px = g(ctx, "cmp") or g(rec, "Entry")
    rs_ratio = g(rec, "JdK_RS_Ratio")
    mansfield = (rs_ratio - 100.0) if rs_ratio is not None else None

    sides = info["sides"]
    run_bull = ("bull" in sides) or ("both" in sides)
    run_rec = ("recovery" in sides) or ("both" in sides)

    cands = []          # (category, path, wf)
    rec_r = None
    if run_bull:
        try:
            wf = loaders["bull_wf"](rec, ctx, cmp_px, mansfield)
            cands.append((trigger_category(wf.get("verdict"), "bull"), "bull", wf))
        except Exception:
            pass
    if run_rec:
        try:
            rec_r = loaders["load_recovery"](sym) or {}
            wf = loaders["rec_wf"](rec_r, ctx, cmp_px)
            cands.append((trigger_category(wf.get("verdict"), "recovery"), "recovery", wf))
        except Exception:
            pass
    if not cands:
        return None

    cands.sort(key=lambda c: _cat_rank(c[0]), reverse=True)   # most-actionable wins
    cat, path, wf = cands[0]

    # BFF (bull growth) status
    bff = data.get("bff") or {}
    bff_txt = ""
    if bff.get("source") == "screener.in":
        _sc = bff.get("score"); _q = bff.get("quality", "")
        bff_txt = f"{_q} {_sc}/5" if _sc is not None else str(_q)

    # RFF (recovery fundamentals) — prefer the recovery record when we have it
    _rsrc = rec_r if rec_r else rec
    rff_b = g(_rsrc, "RFF_Base")
    rff_q = g(_rsrc, "RFF_Quality")
    rff_txt = ""
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
        except Exception:
            mpass = None
    _bat = "recovery_pa_patterns" if path == "recovery" else "pa_patterns"
    _pp = g(ctx, _bat, default=[]) or []
    try:
        sigma_pa = sum(t for _n, _f, t, _x in _pp if _f)
    except Exception:
        sigma_pa = None

    _stale = g(rec, "Stale_Data")

    return {
        "Symbol":     sym,
        "Category":   cat,
        "Path":       "Recovery" if path == "recovery" else "Bull",
        "RRG":        "—",                       # filled from json by the caller
        "Conviction": _r1(g(rec, "Conviction")),
        "Combined":   _r1(g(rec, "Combined_Score")),
        "Alpha":      _r1(g(rec, "Alpha")),
        "RS":         _r1(mansfield),
        "Stage":      str(g(rec, "Stage", default="—")),
        "MLProb%":    _r1(ml),
        "Minervini":  (f"{int(mpass)}/8" if mpass is not None else ""),
        "Catalyst":   str(g(rec, "Catalyst", default="—")),
        "VCP":        ("✓" if vcp else "·"),
        "ΣPA":        sigma_pa,
        "BFF":        bff_txt,
        "RFF":        rff_txt,
        "Sector":     str(g(rec, "Sector", default="") or ""),
        "CMP":        _r1(cmp_px),
        "Chg%":       _r1(chg_pct),
        "52WH%":      _r1(d52),
        "TurnovrCr":  _r1(g(ctx, "turnover_cr")),
        "Entry":      _r1(entry),
        "SL":         _r1(sl),
        "SL%":        _r1(sl_pct),
        "T1":         _r1(t1),
        "R:R":        _r1(rr),
        "RRGeng":     rrg_eng,
        "Step":       wf.get("current"),
        "Tier":       info["tier"],
        "Sources":    ", ".join(dict.fromkeys(info["sources"])),
        "Stale":      ("⚠" if _stale else ""),
    }
