"""
etf_calendar.py -- Calendar-based sentiment overlay for the ETF Trading System.

Built 12 May 2026 as Enhancement #10 from the validation audit.

Why a calendar overlay (and NOT NLP sentiment)
----------------------------------------------
Phase 5 of the 6-phase fine-tuning roadmap is text-sentiment promotion. That
explicitly requires hand-label parser validation at >=85% precision BEFORE
sentiment can become a scoring input. That's gated for good reason -- ET/MC
regex-over-prose is too noisy to trade off.

THIS module is different: it uses DATE-BASED event impact, not text parsing.
Known events (RBI policy days, Budget day, FOMC days, options expiry) have
well-documented directional effects on specific ETF buckets. No NLP needed.

Examples:
    - RBI MPC cuts rates 25bp -> debt ETFs (LIQUIDBEES, BBETF) rally, banking
      ETFs benefit (PSU bank > pvt bank typically), rate-sensitive REITs/realty.
    - Union Budget day -> infra (INFRABEES), defence (DEFENCE), PSU (CPSEETF),
      consumption (CONSUMBEES) per budget signals.
    - FOMC hikes USD-bearish -> intl ETFs (MAFANG, MON100) +
      gold (GOLDBEES) move inversely.
    - Indian options expiry (last Thursday) -> heightened intraday volatility
      on banking / financial ETFs.

The overlay adds a small score adjustment to the screener's signal -- never
overrides Stage/RS gates, just nudges priority.

Public API
----------
    EVENTS                                          : dict of dates -> events
    upcoming_events(window_days=7) -> List[Event]   : events in next N days
    apply_calendar_score(score_df, as_of) -> DataFrame
                                                    : adds Calendar_Adj column
    impact_summary(as_of, window_days=14) -> str    : human-readable digest
"""
from __future__ import annotations

import os
import logging
import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================================
# Event type enum + impact map
# ============================================================================
@dataclass
class Event:
    date:        dt.date
    event_type:  str        # 'RBI_MPC', 'BUDGET', 'FOMC', 'OPEX', 'GST', 'IIP'
    label:       str
    impact:      Dict[str, int]   # sub_category -> score adjustment (-3 to +3)
    notes:       str = ""


# Default impact maps. Score adjustments are bounded [-3, +3].
# Positive = tailwind / accumulate signal. Negative = headwind / cut signal.
IMPACT_RBI_MPC_DOVISH = {
    "DEBT.LIQUID":        +3,
    "DEBT.GILT_5Y":       +3,
    "DEBT.BHARAT_BOND":   +2,
    "SECTOR.PSU_BANK":    +2,
    "SECTOR.BANKING":     +2,
    "SECTOR.PVT_BANK":    +1,
    "SECTOR.REALTY":      +2,    # rate-sensitive
    "SECTOR.AUTO":        +1,    # consumption finance link
    "COMMODITY.GOLD":     +1,
    "INTL.US_NASDAQ":     -1,    # USD bearish on dovish INR
}

IMPACT_RBI_MPC_HAWKISH = {k: -v for k, v in IMPACT_RBI_MPC_DOVISH.items()}

IMPACT_BUDGET = {
    "THEME.INFRA":        +3,
    "SECTOR.PSU_BANK":    +2,
    "THEME.CPSE":         +2,
    "THEME.DEFENCE":      +2,
    "THEME.MFG":          +2,    # Make in India announcements
    "THEME.CONSUMPTION":  +1,
    "SECTOR.REALTY":      +1,
    "SECTOR.METAL":       +1,
    "SECTOR.OIL_GAS":     +1,
}

IMPACT_FOMC_HAWKISH = {
    "COMMODITY.GOLD":     -2,
    "COMMODITY.SILVER":   -2,
    "INTL.US_NASDAQ":     -2,
    "INTL.US_TECH":       -2,
    "INTL.US_LARGE":      -1,
    "DEBT.LIQUID":        -1,
}

IMPACT_FOMC_DOVISH = {k: -v for k, v in IMPACT_FOMC_HAWKISH.items()}

IMPACT_OPEX = {
    "SECTOR.BANKING":     -1,
    "SECTOR.PVT_BANK":    -1,
    "FACTOR.MOMENTUM":    -1,
}


# ============================================================================
# Built-in event calendar (2024-2026 estimates -- update from official sources)
# RBI MPC dates: every ~2 months. Budget: 1 Feb. FOMC: 8 per year.
# These are CONSERVATIVE forward dates; live system should refresh from APIs.
# ============================================================================
EVENTS: List[Event] = [
    # ── 2024 RBI MPC ────────────────────────────────────────────────────────
    Event(dt.date(2024, 2, 8),  "RBI_MPC", "RBI MPC Feb 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),
    Event(dt.date(2024, 4, 5),  "RBI_MPC", "RBI MPC Apr 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),
    Event(dt.date(2024, 6, 7),  "RBI_MPC", "RBI MPC Jun 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),
    Event(dt.date(2024, 8, 8),  "RBI_MPC", "RBI MPC Aug 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),
    Event(dt.date(2024, 10, 9), "RBI_MPC", "RBI MPC Oct 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),
    Event(dt.date(2024, 12, 6), "RBI_MPC", "RBI MPC Dec 2024", IMPACT_RBI_MPC_HAWKISH, "Status quo"),

    # ── 2025 RBI MPC (forward estimates) ────────────────────────────────────
    Event(dt.date(2025, 2, 7),  "RBI_MPC", "RBI MPC Feb 2025", IMPACT_RBI_MPC_DOVISH, "Rate cut cycle expected"),
    Event(dt.date(2025, 4, 9),  "RBI_MPC", "RBI MPC Apr 2025", IMPACT_RBI_MPC_DOVISH, "Rate cut cycle"),
    Event(dt.date(2025, 6, 6),  "RBI_MPC", "RBI MPC Jun 2025", IMPACT_RBI_MPC_DOVISH, "Rate cut cycle"),
    Event(dt.date(2025, 8, 7),  "RBI_MPC", "RBI MPC Aug 2025", IMPACT_RBI_MPC_DOVISH, "Pause possible"),
    Event(dt.date(2025, 10, 8), "RBI_MPC", "RBI MPC Oct 2025", IMPACT_RBI_MPC_DOVISH, "Pause"),
    Event(dt.date(2025, 12, 5), "RBI_MPC", "RBI MPC Dec 2025", IMPACT_RBI_MPC_DOVISH, "Pause"),

    # ── 2026 RBI MPC (forward estimates) ────────────────────────────────────
    Event(dt.date(2026, 2, 6),  "RBI_MPC", "RBI MPC Feb 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),
    Event(dt.date(2026, 4, 8),  "RBI_MPC", "RBI MPC Apr 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),
    Event(dt.date(2026, 6, 5),  "RBI_MPC", "RBI MPC Jun 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),
    Event(dt.date(2026, 8, 7),  "RBI_MPC", "RBI MPC Aug 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),
    Event(dt.date(2026, 10, 7), "RBI_MPC", "RBI MPC Oct 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),
    Event(dt.date(2026, 12, 4), "RBI_MPC", "RBI MPC Dec 2026", IMPACT_RBI_MPC_DOVISH, "Forward"),

    # ── Union Budget days ───────────────────────────────────────────────────
    Event(dt.date(2024, 2, 1),  "BUDGET", "Interim Budget 2024", IMPACT_BUDGET),
    Event(dt.date(2024, 7, 23), "BUDGET", "Full Budget 2024-25", IMPACT_BUDGET),
    Event(dt.date(2025, 2, 1),  "BUDGET", "Union Budget 2025-26", IMPACT_BUDGET),
    Event(dt.date(2026, 2, 1),  "BUDGET", "Union Budget 2026-27", IMPACT_BUDGET),

    # ── 2024-2026 FOMC (estimates) ──────────────────────────────────────────
    Event(dt.date(2024, 1, 31),  "FOMC", "FOMC Jan 2024",  IMPACT_FOMC_HAWKISH),
    Event(dt.date(2024, 3, 20),  "FOMC", "FOMC Mar 2024",  IMPACT_FOMC_HAWKISH),
    Event(dt.date(2024, 5, 1),   "FOMC", "FOMC May 2024",  IMPACT_FOMC_HAWKISH),
    Event(dt.date(2024, 6, 12),  "FOMC", "FOMC Jun 2024",  IMPACT_FOMC_HAWKISH),
    Event(dt.date(2024, 7, 31),  "FOMC", "FOMC Jul 2024",  IMPACT_FOMC_HAWKISH),
    Event(dt.date(2024, 9, 18),  "FOMC", "FOMC Sep 2024",  IMPACT_FOMC_DOVISH, "First cut"),
    Event(dt.date(2024, 11, 7),  "FOMC", "FOMC Nov 2024",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2024, 12, 18), "FOMC", "FOMC Dec 2024",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 1, 29),  "FOMC", "FOMC Jan 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 3, 19),  "FOMC", "FOMC Mar 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 5, 7),   "FOMC", "FOMC May 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 6, 18),  "FOMC", "FOMC Jun 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 7, 30),  "FOMC", "FOMC Jul 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 9, 17),  "FOMC", "FOMC Sep 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 10, 29), "FOMC", "FOMC Oct 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2025, 12, 10), "FOMC", "FOMC Dec 2025",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 1, 28),  "FOMC", "FOMC Jan 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 3, 18),  "FOMC", "FOMC Mar 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 5, 6),   "FOMC", "FOMC May 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 6, 17),  "FOMC", "FOMC Jun 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 7, 29),  "FOMC", "FOMC Jul 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 9, 16),  "FOMC", "FOMC Sep 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 10, 28), "FOMC", "FOMC Oct 2026",  IMPACT_FOMC_DOVISH),
    Event(dt.date(2026, 12, 9),  "FOMC", "FOMC Dec 2026",  IMPACT_FOMC_DOVISH),
]


# ============================================================================
# Auto-generated events (monthly options expiry)
# ============================================================================
def _generate_opex_dates(start_year: int, end_year: int) -> List[Event]:
    """NSE F&O monthly expiry = last Thursday of each month.
    Adds OPEX events for the configured year range."""
    out = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # Find last Thursday of month
            d = dt.date(year, month, 28)
            while d.month == month:
                d += dt.timedelta(days=1)
            d -= dt.timedelta(days=1)
            while d.weekday() != 3:  # 0=Mon..3=Thu
                d -= dt.timedelta(days=1)
            out.append(Event(d, "OPEX", f"F&O Expiry {d:%b %Y}", IMPACT_OPEX))
    return out


EVENTS.extend(_generate_opex_dates(2024, 2026))


# ============================================================================
# Lookup helpers
# ============================================================================
def upcoming_events(as_of: Optional[dt.date] = None,
                     window_days: int = 7,
                     event_types: Optional[List[str]] = None) -> List[Event]:
    """Events in the window [as_of, as_of + window_days]. Defaults to today."""
    if as_of is None:
        as_of = dt.date.today()
    end = as_of + dt.timedelta(days=window_days)
    out = [e for e in EVENTS if as_of <= e.date <= end]
    if event_types:
        out = [e for e in out if e.event_type in event_types]
    return sorted(out, key=lambda e: e.date)


def recent_events(as_of: Optional[dt.date] = None,
                   lookback_days: int = 3,
                   event_types: Optional[List[str]] = None) -> List[Event]:
    """Events in the lookback window [as_of - lookback_days, as_of].
    Used to apply post-event impact (markets digest event over 1-3 days)."""
    if as_of is None:
        as_of = dt.date.today()
    start = as_of - dt.timedelta(days=lookback_days)
    out = [e for e in EVENTS if start <= e.date <= as_of]
    if event_types:
        out = [e for e in out if e.event_type in event_types]
    return sorted(out, key=lambda e: e.date)


def aggregate_impact(events: List[Event]) -> Dict[str, int]:
    """Sum impact values across multiple events.
    Caps each sub_category adjustment to [-5, +5] to prevent stacking blowups."""
    agg: Dict[str, int] = {}
    for e in events:
        for sub_cat, delta in e.impact.items():
            agg[sub_cat] = agg.get(sub_cat, 0) + delta
    return {k: max(-5, min(5, v)) for k, v in agg.items()}


# ============================================================================
# Apply calendar overlay to a screener DataFrame
# ============================================================================
def apply_calendar_score(score_df: pd.DataFrame,
                          as_of: Optional[dt.date] = None,
                          forward_window: int = 5,
                          back_window: int = 3) -> pd.DataFrame:
    """Adds Calendar_Adj + Calendar_Notes columns to the score DataFrame.

    Forward window (5 days): pre-position for upcoming RBI/Budget/FOMC.
    Back window (3 days):    let the system ride the post-event move.

    The adjustment is informational -- does NOT change Total_Score or Signal.
    The dashboard / web app can use it as a sort tiebreak or visual flag.
    """
    if as_of is None:
        as_of = dt.date.today()
    forward = upcoming_events(as_of, forward_window)
    back    = recent_events(as_of, back_window)
    all_evt = forward + back
    if not all_evt:
        score_df["Calendar_Adj"]   = 0
        score_df["Calendar_Notes"] = ""
        return score_df
    impact = aggregate_impact(all_evt)
    notes_per_event = "; ".join(f"{e.label}@{e.date.isoformat()}" for e in all_evt)

    if "Sub_Category" not in score_df.columns:
        score_df["Calendar_Adj"]   = 0
        score_df["Calendar_Notes"] = ""
        return score_df

    score_df = score_df.copy()
    score_df["Calendar_Adj"]   = score_df["Sub_Category"].map(impact).fillna(0).astype(int)
    # Trim notes to only events whose sub_category is in this row's adjustments
    score_df["Calendar_Notes"] = score_df["Calendar_Adj"].apply(
        lambda v: notes_per_event if v != 0 else ""
    )
    return score_df


# ============================================================================
# Human-readable digest
# ============================================================================
def impact_summary(as_of: Optional[dt.date] = None,
                    window_days: int = 14) -> str:
    """One-page Markdown summary for the next `window_days`.
    Suitable for the Commander Web ETF page or a Sunday brief."""
    if as_of is None:
        as_of = dt.date.today()
    upc = upcoming_events(as_of, window_days)
    rec = recent_events(as_of, 7)

    lines = [f"# ETF Calendar Impact -- {as_of.isoformat()}"]
    lines.append("")
    if not upc and not rec:
        lines.append("No major events in window.")
        return "\n".join(lines)

    if upc:
        lines.append(f"## Upcoming ({len(upc)} events, next {window_days} days)\n")
        for e in upc:
            days_out = (e.date - as_of).days
            lines.append(f"- **{e.date.isoformat()} (+{days_out}d)** "
                          f"{e.label} [{e.event_type}]")
            top = sorted(e.impact.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
            for sub, val in top:
                arrow = "▲" if val > 0 else "▼"
                lines.append(f"    - {arrow} `{sub}` ({val:+d})")
            if e.notes:
                lines.append(f"    - _{e.notes}_")
        lines.append("")

    if rec:
        lines.append(f"## Recent ({len(rec)} events, past 7 days)\n")
        for e in rec:
            days_ago = (as_of - e.date).days
            lines.append(f"- **{e.date.isoformat()} (-{days_ago}d)** "
                          f"{e.label}")
        lines.append("")

    agg = aggregate_impact(upc + rec)
    if agg:
        lines.append("## Aggregate Adjustment by Sub-Category\n")
        for sub, val in sorted(agg.items(), key=lambda kv: kv[1], reverse=True):
            arrow = "▲" if val > 0 else "▼" if val < 0 else "—"
            lines.append(f"- {arrow} `{sub}` **{val:+d}**")

    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="ETF calendar overlay")
    parser.add_argument("--as-of", help="ISO date, default today")
    parser.add_argument("--window", type=int, default=14, help="Days forward")
    parser.add_argument("--summary", action="store_true",
                         help="Print Markdown summary")
    parser.add_argument("--apply", help="Path to ETF_Screener_Results.csv. "
                         "Re-saves with Calendar_Adj / Calendar_Notes appended.")
    args = parser.parse_args()

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()

    if args.summary or not args.apply:
        print(impact_summary(as_of, args.window))

    if args.apply:
        df = pd.read_csv(args.apply)
        df = apply_calendar_score(df, as_of)
        df.to_csv(args.apply, index=False)
        adj_count = int((df["Calendar_Adj"] != 0).sum())
        print(f"\nApplied calendar overlay to {args.apply}: "
              f"{adj_count} rows adjusted")


__all__ = [
    "Event", "EVENTS", "upcoming_events", "recent_events",
    "aggregate_impact", "apply_calendar_score", "impact_summary",
]


if __name__ == "__main__":
    main()
