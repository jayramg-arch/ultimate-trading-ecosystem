# -*- coding: utf-8 -*-
"""ETF universe selection from the AUM-curated candidate pool (30-Aug-2026).

THE TWO-STAGE SPLIT
-------------------
Building the tradeable ETF list asks two questions with different answers, different
data sources and different refresh rates. Conflating them is what made the old
hand-curated list drift:

  STAGE 1 - the CANDIDATE POOL.  "Which funds are viable and will track their index?"
      Slow, structural, genuinely needs AUM, and cannot be automated: NSE ETFs share
      series 'EQ' with ordinary stocks in the Dhan scrip master, so there is no
      instrument flag to enumerate them by. This stays a human file (Jay's top-3-by-AUM
      per category workbook) refreshed occasionally.

  STAGE 2 - WHICH ONE YOU TRADE.  Fast, mechanical, recomputed every run. That is
      this module.

MEASURED, ON THE 125-NAME POOL (30-Aug-2026): AUM IS REDUNDANT AS A FILTER.
    >= Rs 2 Cr/day turnover ....... 53 of 125
    >= Rs 100 Cr AUM .............. 96 of 125
    >= BOTH ....................... 53
Not one ETF clears the turnover floor while failing the AUM floor, so screening on AUM
after screening on turnover removes nothing. AUM's real job is upstream, in Stage 1.

WHY CHEAPEST-OF-THE-LIQUID, NOT MOST-LIQUID
-------------------------------------------
The old rule was "keep the tracker with higher 60D turnover". For positional holds of
6-8 months that is the wrong objective past the point where liquidity is sufficient:

    Gold    GOLDBEES   Rs 328 Cr/day  TER 0.69%   vs  GOLDIETF   Rs 80 Cr/day  TER 0.42%
    Silver  SILVERBEES Rs 610 Cr/day  TER 0.49%   vs  SILVERIETF Rs 87 Cr/day  TER 0.34%

At Rs 2-10 L positions, Rs 80 Cr/day and Rs 328 Cr/day are indistinguishable - you
cannot use the difference. Paying 0.27pp a year for liquidity you never touch is pure
cost. So: filter on liquidity, then rank on EXPENSE RATIO. Turnover decides who is
ELIGIBLE; TER decides who WINS.

Expense ratio is used nowhere else in the ecosystem. It is a guaranteed drag, unlike
every other input, which makes it the one input that does not need a backtest.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))

# Repo snapshot, so a run never depends on an external drive being mounted. Refresh it
# with `python etf_candidates.py --import "<path to xlsx>"`.
POOL_CSV = os.path.join(_DIR, "etf_candidate_pool.csv")
PROPOSED_CSV = os.path.join(_DIR, "ETF_Universe_Proposed.csv")

# ADMISSION FLOOR - deliberately far below etf_config's Rs 2 Cr, because COVERAGE OF
# EVERY KEY SECTOR MATTERS MORE THAN THE LIQUIDITY OF ANY ONE VEHICLE. Jay works the
# INDEX chart first and then picks an ETF to express it, so a sector with no vehicle is
# a rotation he simply cannot take; a thin vehicle sized down is strictly better than a
# missing one. MEASURED sector coverage against the 21 sector exposures in the pool:
#     Rs 2.00 Cr/day .... 12 of 21   <- the inherited floor. Deleted 9 sectors silently.
#     Rs 1.00 Cr/day .... 17 of 21
#     Rs 0.50 Cr/day .... 19 of 21   <- here
#     Rs 0.25 Cr/day .... 19 of 21   (no coverage gain, thinner names)
# The Rs 2 Cr floor was excluding Finnifty at Rs 1.86 Cr and Healthcare at Rs 1.99 Cr -
# whole sectors lost for missing a round number by a lakh.
# At Rs 0.50 Cr a Rs 2 L position is 4% of daily turnover, inside the usual
# 10%-of-ADV rule; liquidity_tier then caps size per name.
MIN_TURNOVER_CR = 0.50

# DELIBERATELY NOT a share-count rule. A fixed 20k-shares/day threshold is not
# comparable across ETFs - the same 20k is Rs 2.0 L on one fund and Rs 321 L on another,
# decided purely by unit price - so it penalises high-priced ETFs for nothing and waves
# through cheap ones that trade almost no money. Rupee turnover is the quantity that
# maps onto "can I get my position out", which is the only thing the floor is for.

# AMPLE liquidity is an ABSOLUTE level, not a relative band. A first cut used
# "within 25% of the most liquid tracker", which quietly re-privileged turnover and
# defeated the whole rationale: GOLDIETF at Rs 80 Cr/day falls outside 25% of
# GOLDBEES' Rs 328 Cr, so the dearer fund won anyway. Sufficiency does not scale with
# the leader - it scales with YOUR position size.
#
# At Rs 5 Cr/day a Rs 10 L position is 2% of daily turnover, comfortably inside the
# usual 10%-of-ADV rule of thumb, and Indian ETF spreads at that level are tight. So
# above this, extra turnover buys nothing and TER decides. Below it, the most liquid
# wins - a marginal name's wider SPREAD can easily exceed the fee saving:
#   TER edge of 0.13pp on Rs 10 L over 8 months .... ~Rs 870
#   spread 0.1% wider on a Rs 10 L round trip ...... ~Rs 2,000
# Spread is per-trade and certain; TER is annual and certain. Neither is measurable
# from the candidate pool, which is why this threshold is conservative rather than
# pushed down to the Rs 2 Cr admission floor.
AMPLE_TURNOVER_CR = 5.0

# STRUCTURAL EXEMPTIONS - kept regardless of turnover or TER, because they are not
# rotation candidates at all. LIQUIDBEES is where capital PARKS when the regime score
# is zero; ranking it against equity ETFs on liquidity is a category error, and it is
# already excluded from performance attribution as risk-off carry rather than alpha.
EXEMPT: Dict[str, str] = {
    # LIQUID1, not LIQUIDBEES. Both are liquid-fund ETFs, but LIQUIDBEES is the
    # DIVIDEND variant: NAV is pinned at Rs 1,000 and the return is paid out daily, so
    # its price series is economically empty - measured over one year, +0.00% price
    # return across SIX distinct closes. Feeding that to the regime engine scores the
    # debt leg at a permanent zero, so risk-off could never compete with equity: a
    # structural bias nobody chose. LIQUID1 is the GROWTH variant - the accrual shows
    # in the price (+12.04% over the same year, 513 distinct closes) - and at
    # Rs 87 Cr/day it is far past any size Jay trades.
    "LIQUID1": "cash park (growth variant) - not a rotation candidate",
}

# NOT TRADED (Jay, 30-Aug-2026) - excluded from the UNIVERSE, not merely from the index
# map. Defined here because this is where the universe is built; etf_index_map imports
# it rather than keeping a second copy, which is how the two drifted to 57 vs 51.
#   EQUAL50ADD / TOP10ADD  equal-weight variants. NOTE their indices DO exist
#                          (NIFTY50 EQL WGT, NIFTY TOP 10 EW) - they were dropped on my
#                          incorrect report that they did not, and Jay left them dropped.
#   EBBETF0430/0431        Bharat Bond
#   GILT5YBEES             5-Yr G-Sec
#   GROWWRAIL              Railways PSU
DROP_SYMBOLS = {
    "EQUAL50ADD", "TOP10ADD", "EBBETF0430", "EBBETF0431", "GILT5YBEES", "GROWWRAIL",
}

# Workbook Category -> the asset_class taxonomy etf_rotation and etf_screener use.
CATEGORY_MAP = {
    "Broad Index":       "BROAD_EQUITY",
    "Sectoral Index":    "SECTOR",
    "Thematic Index":    "THEMATIC",
    "Commodities Index": "COMMODITY",
    "Debt Index":        "DEBT",
    "Global Index":      "INTERNATIONAL",
    "Strategy Index":    "SMART_BETA",
}

# Derived from LIVE turnover rather than hand-assigned. The old liquidity_tier was set
# once at curation and never re-checked, so a fund whose turnover had halved kept
# saying "heavy size OK" - and it is the field that decides position size.
# Thresholds mirror etf_screener.LIQ_BANDS.
def tier_for(turnover_cr: float) -> str:
    """Tier IS the position-size rule. With the floor lowered for coverage, a thin
    sector vehicle is admitted and then capped here rather than dropped - which is the
    whole point: the tier is what makes low-turnover coverage safe to hold."""
    if turnover_cr >= 10.0:
        return "A"      # heavy size OK
    if turnover_cr >= 5.0:
        return "B"      # split entries, 5-10L
    if turnover_cr >= 2.0:
        return "C"      # avoid > 2L, watch spread
    return "D"          # starter size only (<= 1L), expect to work the order


def import_workbook(path: str) -> pd.DataFrame:
    """Read Jay's candidate workbook and snapshot it into the repo."""
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    df.to_csv(POOL_CSV, index=False)
    logger.info("etf_candidates: imported %d rows -> %s", len(df), POOL_CSV)
    return df


def load_candidates(path: Optional[str] = None) -> Optional[pd.DataFrame]:
    """The candidate pool, normalised. None when it cannot be read (never a guess)."""
    src = path or POOL_CSV
    try:
        df = pd.read_excel(src) if str(src).lower().endswith((".xlsx", ".xls")) \
            else pd.read_csv(src)
    except Exception as e:
        logger.warning("etf_candidates: pool unreadable (%s): %s", src, e)
        return None
    df.columns = [str(c).strip() for c in df.columns]
    ren = {"Asset (Cr.)": "AUM_Cr", "Expense Ratio %": "TER_frac",
           "60 day average Volume": "Vol_60D", "Based on": "Underlying"}
    df = df.rename(columns={k: v for k, v in ren.items() if k in df.columns})
    for c in ("AUM_Cr", "TER_frac", "Vol_60D", "LTP"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()

    # THE COLUMN IS A FRACTION DESPITE ITS NAME: NIFTYBEES reads 0.0003, i.e. 0.03%,
    # not 0.0003%. Anything treating it as a percentage is wrong by 100x.
    df["TER_pct"] = df["TER_frac"] * 100.0

    # Turnover here is LTP x AVERAGE volume, which is the pool's own approximation.
    # etf_screener computes per-day price x volume and takes the MEDIAN, which is the
    # honest number (a single block deal cannot lift a thin ETF over the floor). Good
    # enough to RANK candidates; the screener still measures the live figure.
    df["Turnover_Cr"] = (df["LTP"] * df["Vol_60D"] / 1e7).round(2)
    df["asset_class"] = df["Category"].map(CATEGORY_MAP).fillna("THEMATIC")
    return df


def select_universe(min_turnover_cr: float = MIN_TURNOVER_CR,
                    path: Optional[str] = None) -> Optional[Dict[str, dict]]:
    """One tracker per exposure: liquid enough to trade, then cheapest to hold."""
    df = load_candidates(path)
    if df is None or df.empty:
        return None

    liquid = df[df["Turnover_Cr"] >= float(min_turnover_cr)].copy()
    out: Dict[str, dict] = {}

    liquid = liquid[~liquid["Symbol"].isin(DROP_SYMBOLS)]
    for underlying, grp in liquid.groupby("Underlying"):
        # VEHICLE CHOICE uses all three of Jay's criteria, lexicographically rather
        # than as a weighted score - a score would need weights nobody has fitted.
        #   volume GATES (floor, then the ample test)
        #   TER    DECIDES (the only certain, recurring cost)
        #   AUM    BREAKS TIES (larger fund tracks its index more tightly)
        ample = grp[grp["Turnover_Cr"] >= AMPLE_TURNOVER_CR]
        # Ample => liquidity stops being a differentiator, so the cheapest wins.
        # Nothing ample => the most liquid, because down here spread still bites.
        contenders = ample if not ample.empty else grp
        pick = contenders.sort_values(["TER_pct", "Turnover_Cr", "AUM_Cr"],
                                      ascending=[True, False, False]).iloc[0]
        basis = ("cheapest of the amply liquid" if not ample.empty
                 else "most liquid (none ample)")
        # issuer is consumed downstream; the workbook embeds it in Name
        # ("Nippon Silver ETF (SILVERBEES)", "ICICI Pru Gold ETF").
        _nm = str(pick.get("Name", ""))
        _iss = next((a for a in ("Nippon", "ICICI", "HDFC", "SBI", "Kotak", "Axis",
                                 "Mirae", "Motilal", "UTI", "Aditya", "Edelweiss",
                                 "Groww", "Bandhan", "Zerodha", "DSP", "Tata")
                     if a.lower() in _nm.lower()), "")
        out[pick["Symbol"]] = {
            "name":           _nm,
            "issuer":         _iss,
            # documentation-only downstream: RS is locked to ^CRSLDX universally
            # (etf_screener:429), so an empty string costs nothing.
            "benchmark_yf":   "",
            "asset_class":    pick["asset_class"],
            "sub_category":   f"{pick['asset_class']}.{str(underlying).upper()}",
            "underlying":     underlying,
            "liquidity_tier": tier_for(pick["Turnover_Cr"]),
            "turnover_cr":    float(pick["Turnover_Cr"]),
            "aum_cr":         float(pick["AUM_Cr"]) if pd.notna(pick["AUM_Cr"]) else None,
            "ter_pct":        round(float(pick["TER_pct"]), 3),
            "selected_from":  int(len(grp)),
            "reason":         basis,
        }

    # Exemptions last so nothing above can drop them.
    for sym, why in EXEMPT.items():
        if sym not in out:
            row = df[df["Symbol"] == sym]
            meta = {"name": (row.iloc[0].get("Name", "") if len(row) else sym),
                    # same field contract as a selected entry - a consumer must not
                    # have to know an exemption was built by a different branch
                    "issuer": "Nippon", "benchmark_yf": "",
                    "asset_class": "DEBT", "sub_category": "DEBT.LIQUID",
                    "underlying": "Overnight / Liquid", "liquidity_tier": "A",
                    "turnover_cr": float(row.iloc[0]["Turnover_Cr"]) if len(row) else None,
                    "aum_cr": None, "ter_pct": None, "selected_from": 0,
                    "reason": f"STRUCTURAL EXEMPTION - {why}"}
            out[sym] = meta
    return out


def main(argv=None):
    import argparse, sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--import", dest="imp", help="path to the candidate workbook (.xlsx)")
    ap.add_argument("--min-turnover", type=float, default=MIN_TURNOVER_CR)
    a = ap.parse_args(argv)

    if a.imp:
        import_workbook(a.imp)

    uni = select_universe(a.min_turnover)
    if not uni:
        print("candidate pool unavailable - nothing selected")
        return 1

    rows = [dict(Symbol=s, **m) for s, m in uni.items()]
    out = pd.DataFrame(rows).sort_values(["asset_class", "turnover_cr"],
                                         ascending=[True, False])
    out.to_csv(PROPOSED_CSV, index=False)
    print(f"\nproposed universe: {len(out)} ETFs (floor Rs {a.min_turnover:g} Cr/day) -> {PROPOSED_CSV}")
    print(out["asset_class"].value_counts().to_dict())
    print("  tier mix:", out["liquidity_tier"].value_counts().sort_index().to_dict())

    # COVERAGE IS THE DESIGN GOAL, so it is reported rather than left to be inferred.
    pool = load_candidates()
    if pool is not None:
        for cat in ("Sectoral Index", "Broad Index", "Commodities Index",
                    "Global Index", "Debt Index", "Thematic Index", "Strategy Index"):
            have = set(out[out["underlying"].isin(
                pool[pool["Category"] == cat]["Underlying"])]["underlying"])
            want = set(pool[pool["Category"] == cat]["Underlying"])
            miss = sorted(want - have)
            print(f"  {cat:<18} {len(have)}/{len(want)}")
            # NAME the reason, with the evidence. An uncovered sector must be a VISIBLE
            # decision, not an absence you notice months later -- and the honest answer
            # is sometimes "no tradeable vehicle exists". Forcing coverage would put you
            # in FMCGADD: Rs 4.8 L/day, Rs 6.2 Cr AUM, TER 1.29% (dearest of all 125).
            # A position you cannot exit, at triple the median fee, is worse than no
            # exposure -- and the stock book can express that sector instead.
            for m in miss:
                g = pool[pool["Underlying"] == m]
                if g.empty:
                    continue
                b = g.sort_values("Turnover_Cr", ascending=False).iloc[0]
                print(f"      no vehicle: {m:<32} best {b['Symbol']:<12} "
                      f"Rs {b['Turnover_Cr']:.2f} Cr/day  TER {b['TER_pct']:.2f}%  "
                      f"AUM Rs {b['AUM_Cr']:.0f} Cr")

    try:
        import etf_universe as eu
        cur = set(eu.ETF_UNIVERSE)
        new = set(uni)
        print(f"\nvs current universe ({len(cur)}): kept {len(cur & new)}, "
              f"dropped {len(cur - new)}, added {len(new - cur)}")
        print("  dropped:", ", ".join(sorted(cur - new)) or "-")
        print("  added  :", ", ".join(sorted(new - cur)) or "-")
    except Exception as e:
        logger.warning("diff vs current universe unavailable: %s", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
