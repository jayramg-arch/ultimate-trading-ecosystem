"""
sector_rotation_view.py - turn the Sector RRG coordinates into ROTATION DECISIONS.

Built 21-Aug-2026. The MACRO -> Sector RRG tab already drew the quadrant chart and a
coordinate cockpit, but it stopped at "here is where each sector sits". It never
answered the three questions Jay actually asks of it:

    1. Which sectors are working right now, and which are not?
    2. Given that, which of MY shortlisted names sit in the right sectors?
    3. Is my BOOK aligned to the rotation, or am I holding into decay?

This module answers those three, as pure functions over the summary_df that
rrg_engine.compute_universe_rrg() already returns. No Streamlit, no fetching, no
network - so it is testable and cannot slow the page down.

DESIGN NOTES / HONESTY RULES
----------------------------
* The quadrant is DESCRIPTIVE, never a veto. Jay's own measurement (20-Aug,
  rrg_cell_remeasure.py, 473 symbols / 93,745 weekly obs) found the RRG transition
  gate worth +0.12pp at 4w and +0.00pp at 12w, and IMPROVING->LEADING reliably
  NEGATIVE. Gate 5 was therefore DISABLED in S4. Nothing here re-introduces it as a
  filter - sector standing is CONTEXT that ranks and warns, and Jay eyeballs it.
* A symbol whose sector cannot be resolved is reported as UNMAPPED, never silently
  dropped and never defaulted into a quadrant. Coverage is visible.
* Concentration is measured against pre_trade_gate.SECTOR_CAP_PCT - imported, not
  copied, so the page and the order gate cannot drift.
"""

from __future__ import annotations

import pandas as pd

__all__ = [
    "QUADRANT_READ", "sector_leaderboard", "map_symbols_to_sectors",
    "candidates_by_sector", "holdings_by_sector", "rotation_summary_line",
]

# ---------------------------------------------------------------------------
# What each quadrant MEANS for a trader, in plain words, plus the standing action.
# Wording deliberately matches docs/25_Golden_Rules.md so the page and the doctrine
# do not say different things about the same quadrant.
# ---------------------------------------------------------------------------
QUADRANT_READ: dict = {
    "Leading": {
        "state":  "Working",
        "read":   "Outperforming the Nifty 500 and still gaining momentum.",
        "action": "Hunt here first. New entries are best sourced from this bucket.",
        "hold":   "Hold. Adds are legitimate if the name itself is at location.",
        "icon":   "\U0001F7E2",
        "rank":   1,
    },
    "Improving": {
        "state":  "Turning up",
        "read":   "Still behind the index, but momentum has turned up - an early turn.",
        "action": "Watch. Early, so demand more from the name's own setup.",
        "hold":   "Hold. The tape is turning your way.",
        "icon":   "\U0001F535",
        "rank":   2,
    },
    "Weakening": {
        "state":  "Rolling over",
        "read":   "Still ahead of the index, but momentum has rolled over - late-cycle.",
        "action": "Do not start new positions here. Leadership is being handed over.",
        "hold":   "Tighten. Trail stops; take partials into strength.",
        "icon":   "\U0001F7E0",
        "rank":   3,
    },
    "Lagging": {
        "state":  "Not working",
        "read":   "Underperforming the index with momentum still down.",
        "action": "Avoid for new entries. Recovery names need fundamentals, not hope.",
        "hold":   "Review for exit. A holding here fights both the name and the tape.",
        "icon":   "\U0001F534",
        "rank":   4,
    },
}

_UNKNOWN = {
    "state": "Unknown", "read": "Sector not resolved.",
    "action": "Map the symbol before leaning on sector context.",
    "hold": "No sector read available.", "icon": "⚪", "rank": 9,
}

# A sector that resolves fine but is not one of the indices this RRG universe
# charts. Distinct from Unknown on purpose: Unknown is a MAPPING failure, this is
# a UNIVERSE gap, and the two have different fixes.
_NOT_CHARTED = {
    "state": "Not charted", "read": "Sector resolves, but this RRG universe does not plot it.",
    "action": "No rotation read. Judge the name on its own merits.",
    "hold": "No rotation read for this sector.", "icon": "⬜", "rank": 8,
}

# sector_lookup and the RRG universe sometimes carry DIFFERENT tickers for the SAME
# sector (found 21-Aug: 5 board names fell out because lookup says ^CNXFIN while the
# universe plots NIFTY_FIN_SERVICE). Alias them rather than losing the rows.
# Only true synonyms belong here - never map a sector onto a DIFFERENT sector.
_INDEX_ALIASES = {
    "CNXFIN": "NIFTY_FIN_SERVICE",
    "CNXFINANCE": "NIFTY_FIN_SERVICE",
    "CNXBANK": "NSEBANK",
    "CNXPVTBANK": "NIFTY_PVT_BANK",
}


def _clean(sym) -> str:
    """Normalise an index/stock ticker to the bare form summary_df.Symbol uses."""
    if sym is None:
        return ""
    return (str(sym).strip().upper()
            .replace("NSE:", "").replace("^", "")
            .replace(".NS", "").replace(".BO", ""))


# ---------------------------------------------------------------------------
# 1. WHICH SECTORS ARE WORKING
# ---------------------------------------------------------------------------
def sector_leaderboard(summary_df: pd.DataFrame,
                       exclude: tuple = ("CRSLDX", "NSEI")) -> pd.DataFrame:
    """Rank the sector universe best-to-worst with a plain-English read per row.

    Ordering is quadrant first (Leading -> Lagging), then distance from the RRG
    centre inside a quadrant: far-from-centre is a STRONGER statement of the same
    quadrant, which is how the chart reads visually.
    """
    if summary_df is None or summary_df.empty:
        return pd.DataFrame()

    df = summary_df.copy()
    df["_c"] = df["Symbol"].map(_clean)
    df = df[~df["_c"].isin({_clean(x) for x in exclude})]
    if df.empty:
        return pd.DataFrame()

    meta = df["Quadrant"].map(_read_for)
    df["State"]  = [m["state"]  for m in meta]
    df["Read"]   = [m["read"]   for m in meta]
    df["Action"] = [m["action"] for m in meta]
    df["_rank"]  = [m["rank"]   for m in meta]
    df["Icon"]   = [m["icon"]   for m in meta]

    df = df.sort_values(["_rank", "Distance"], ascending=[True, False]).reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))
    df["Sector"] = df["Icon"] + " " + df["Symbol"].astype(str)

    cols = ["#", "Sector", "State", "Trajectory", "RS-Ratio", "RS-Momentum",
            "4W %", "Distance", "Read", "Action"]
    return df[[c for c in cols if c in df.columns]]


def rotation_summary_line(lb: pd.DataFrame) -> str:
    """One sentence naming where money is going and where it is leaving."""
    if lb is None or lb.empty:
        return "No sector rotation data."

    def _names(state, n=3):
        r = lb[lb["State"] == state]["Sector"].head(n).tolist()
        return ", ".join(x.split(" ", 1)[-1] for x in r) if r else "-"

    return ("**Money is in:** " + _names("Working") + "  ·  "
            "**Turning up:** " + _names("Turning up") + "  ·  "
            "**Rolling over:** " + _names("Rolling over") + "  ·  "
            "**Avoid:** " + _names("Not working"))


# ---------------------------------------------------------------------------
# 2 & 3. JOIN MY SYMBOLS TO THE ROTATION
# ---------------------------------------------------------------------------
def map_symbols_to_sectors(symbols, summary_df: pd.DataFrame) -> pd.DataFrame:
    """symbol -> (sector name, sector index, quadrant, distance).

    Unresolvable symbols come back with Quadrant='Unmapped' so coverage is visible.
    Never guesses a sector.
    """
    try:
        import sector_lookup as _sl
    except Exception:
        _sl = None

    quad_by_idx, dist_by_idx, traj_by_idx = {}, {}, {}
    if summary_df is not None and not summary_df.empty:
        for _, r in summary_df.iterrows():
            k = _clean(r.get("Symbol"))
            quad_by_idx[k] = r.get("Quadrant")
            dist_by_idx[k] = r.get("Distance")
            traj_by_idx[k] = r.get("Trajectory")

    rows = []
    for s in symbols:
        bare = _clean(s)
        sec_name = sec_idx = yf = None
        if _sl is not None:
            try:
                sec_idx = _sl.get_sector_index(bare)
                sec_name = _sl.get_sector_name(bare)
                yf = _sl.sector_to_yf(sec_idx) if sec_idx else None
            except Exception:
                pass
        key = _clean(yf) if yf else None
        if key:
            key = _INDEX_ALIASES.get(key, key)
        if not key:
            quad = "Unmapped"                       # lookup could not resolve a sector
        elif key in quad_by_idx:
            quad = quad_by_idx[key]                 # charted -> real quadrant
        else:
            quad = "NotCharted"                     # resolves, but absent from this universe
        rows.append({
            "Symbol": bare,
            "Sector": sec_name or "-",
            "Sector_Index": key or "-",
            "Quadrant": quad,
            "Sector_Traj": traj_by_idx.get(key, "-") if key else "-",
            "Sector_Dist": dist_by_idx.get(key) if key else None,
        })
    return pd.DataFrame(rows)


def _read_for(q):
    """Quadrant -> its read. NotCharted is a first-class state, not an error."""
    if q == "NotCharted":
        return _NOT_CHARTED
    return QUADRANT_READ.get(q, _UNKNOWN)


def _decorate(df: pd.DataFrame, verdict_key: str) -> pd.DataFrame:
    meta = df["Quadrant"].map(_read_for)
    df = df.copy()
    df["Sector Standing"] = [m["icon"] + " " + m["state"] for m in meta]
    df["Rotation Says"]   = [m[verdict_key] for m in meta]
    df["_rank"]           = [m["rank"] for m in meta]
    return df


def candidates_by_sector(board_df: pd.DataFrame, summary_df: pd.DataFrame,
                         symbol_col: str = "Symbol") -> pd.DataFrame:
    """Shortlist names, ordered so the ones in working sectors surface first.

    This is the bridge the page was missing: the rotation view and the shortlist
    were two screens that never spoke. Sector standing RANKS candidates; it does
    not remove them (the transition gate measured ~zero - see module docstring).
    """
    if board_df is None or board_df.empty or symbol_col not in board_df.columns:
        return pd.DataFrame()

    m = map_symbols_to_sectors(board_df[symbol_col].tolist(), summary_df)
    keep = [c for c in (symbol_col, "Overall", "Category", "S4-GO", "Archetype",
                        "Path", "CMP") if c in board_df.columns]
    out = board_df[keep].merge(m, left_on=symbol_col, right_on="Symbol", how="left",
                               suffixes=("", "_m"))
    out["Quadrant"] = out["Quadrant"].fillna("Unmapped")
    out = _decorate(out, "action")

    sort_cols, asc = ["_rank"], [True]
    if "Overall" in out.columns:
        sort_cols.append("Overall")
        asc.append(False)
    out = out.sort_values(sort_cols, ascending=asc).reset_index(drop=True)

    cols = ([symbol_col, "Sector", "Sector Standing", "Sector_Traj"]
            + [c for c in ("Overall", "S4-GO", "Category", "Archetype") if c in out.columns]
            + ["Rotation Says"])
    seen, ordered = set(), []
    for c in cols:
        if c in out.columns and c not in seen:
            ordered.append(c)
            seen.add(c)
    return out[ordered]


def holdings_by_sector(holdings_df: pd.DataFrame, summary_df: pd.DataFrame,
                       symbol_col: str = "Symbol",
                       value_col=None):
    """(per-holding rotation view, per-sector concentration view).

    Concentration is checked against pre_trade_gate.SECTOR_CAP_PCT so this page and
    the order gate cannot disagree about what "too concentrated" means.
    """
    empty = pd.DataFrame()
    if holdings_df is None or holdings_df.empty or symbol_col not in holdings_df.columns:
        return empty, empty

    m = map_symbols_to_sectors(holdings_df[symbol_col].tolist(), summary_df)
    keep = [c for c in (symbol_col, "Qty", "Avg", "LTP", "PnL", "PnL_Pct", "R_Mult",
                        "Pyr_Class", value_col) if c and c in holdings_df.columns]
    out = holdings_df[keep].merge(m, left_on=symbol_col, right_on="Symbol",
                                  how="left", suffixes=("", "_m"))
    out["Quadrant"] = out["Quadrant"].fillna("Unmapped")
    out = _decorate(out, "hold")
    # worst-standing sectors FIRST - this table exists to surface decay, not to praise.
    out = out.sort_values("_rank", ascending=False).reset_index(drop=True)

    cap = 25.0
    try:
        from pre_trade_gate import SECTOR_CAP_PCT as _cap
        cap = float(_cap)
    except Exception:
        pass

    if value_col and value_col in out.columns:
        out["_val"] = pd.to_numeric(out[value_col], errors="coerce").fillna(0.0)
    elif "Qty" in out.columns:
        q = pd.to_numeric(out["Qty"], errors="coerce")
        px_col = "LTP" if "LTP" in out.columns else ("Avg" if "Avg" in out.columns else None)
        px = pd.to_numeric(out[px_col], errors="coerce") if px_col else 1.0
        out["_val"] = (q * px).fillna(0.0)
    else:
        out["_val"] = 1.0

    total = float(out["_val"].sum()) or 1.0
    conc = (out.groupby(["Sector", "Sector Standing", "_rank"], dropna=False)
               .agg(Positions=(symbol_col, "count"), Value=("_val", "sum"))
               .reset_index())
    conc["% of Book"] = (conc["Value"] / total * 100).round(1)
    conc["Cap Status"] = conc["% of Book"].map(
        lambda p: ("⛔ over %.0f%%" % cap) if p > cap
        else ("⚠ near cap" if p > cap * 0.8 else "✓"))
    conc = conc.sort_values(["_rank", "% of Book"], ascending=[True, False])

    per_cols = ([symbol_col, "Sector", "Sector Standing", "Sector_Traj"]
                + [c for c in ("Qty", "PnL_Pct", "R_Mult", "Pyr_Class") if c in out.columns]
                + ["Rotation Says"])
    conc_cols = ["Sector", "Sector Standing", "Positions", "% of Book", "Cap Status"]
    return out[[c for c in per_cols if c in out.columns]], conc[conc_cols]
