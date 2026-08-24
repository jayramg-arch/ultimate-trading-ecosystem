# -*- coding: utf-8 -*-
"""ETF VEHICLE PICKER — which fund to own for a given exposure.

WHY THIS IS A SEPARATE SURFACE, and not three more columns on the Trigger Board.

AUM, expense ratio and multi-year returns answer a different question from
everything else in this stack. The board answers "should I buy gold NOW" and it
re-answers that every 75 minutes. These fields answer "WHICH gold ETF should I
own" — and that answer changes about once a year.

The need is concrete: GOLDBEES, GOLDIETF, GOLDETF and GOLD1 all track the same
metal and all scored 30/40 on the same day. Nothing on the board distinguishes
them, because on price-action terms they ARE the same instrument. What separates
them is cost of ownership: expense ratio, tracking difference, liquidity, and how
far the price sits from NAV. Put those on the board and you dilute a timing
surface with reference data that never changes; put them here and you make the
once-a-year decision properly, then trade whichever you chose.

So: pick the VEHICLE here, time the TRADE on the board, plan it on S4.

WHERE THE RETURNS COME FROM (traced 24-Aug-2026, not assumed)
    etf_vehicles.build -> etf_screener._fetch_history(period="5y")
                       -> data_provider.fetch_batch_ohlcv(auto_adjust=True)
                       -> DHAN historical daily closes  (source=dhan, verified)
  CAGR is first-close to last-close inside the window, annualised by the ACTUAL
  span rather than the nominal one, so a fund listed mid-window is not credited
  with time it did not trade.

  TWO PROPERTIES OF THAT CHAIN WORTH KNOWING:

  * `auto_adjust=True` is a NO-OP on the Dhan path. dhan_ohlcv.py does not mention
    auto_adjust anywhere; the flag only binds on the yfinance fallback. Dhan
    returns what it returns.
  * That is NOT, however, a systemic adjustment failure, and it was worth checking
    before saying so. Scanned for bar-over-bar ratios outside 0.55-1.9 across 5
    years: 49 ETF series -> 3 artifacts, ALL of them AUTOIETF; 70 watchlist stock
    series -> ZERO. So 118 of 119 series are clean and Dhan is adjusting corporate
    actions properly. AUTOIETF is a single bad instrument, not the tip of anything.

  These are PRICE returns, not total returns: a distributing ETF's payouts are not
  added back, so its CAGR here understates what a holder actually earned. Most
  Indian ETFs accumulate, which is why this is a footnote rather than a correction,
  but it is the reason a fund with an unusually poor Track_Diff deserves a look at
  its distribution history before being written off as a bad tracker.

WHAT IS COMPUTED vs WHAT MUST BE SUPPLIED
  computed  : CAGR 1Y / 3Y / 5Y, tracking difference within a group, turnover,
              premium to NAV
  supplied  : AUM and TER — see COSTS below. There is NO free machine-readable
              source for these in India. AMFI's NAVAll.txt carries NAV and ISIN
              only, its TER page 404s, and yfinance returns nothing at all for
              .NS ETFs (all three checked, 24-Aug-2026). They are therefore a
              curated table, NOT scraped, and deliberately left EMPTY rather than
              filled from memory — a plausible-looking wrong expense ratio is
              worse than a blank, because you would act on it.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = "ETF_Vehicle_Compare.csv"

# ─────────────────────────────────────────────────────────────────────────────
# COSTS — curated, because nothing publishes this in a machine-readable form.
#   {"SYMBOL": {"ter": 0.50, "aum_cr": 1234.0}}
# ter    = total expense ratio, PERCENT per year (0.50 means 0.50%)
# aum_cr = assets under management, RUPEES CRORE
# Source: the AMC factsheet or the scheme page. TER moves roughly annually and
# AUM quarterly, so a quarterly refresh is proportionate — this is not a feed.
# COSTS_AS_OF is printed on the output so a stale table is visible rather than
# assumed current. Leave a symbol out entirely if you have not checked it; the
# column will read blank, which is honest. Do NOT guess.
# ─────────────────────────────────────────────────────────────────────────────
COSTS_AS_OF = ""          # set to e.g. "2026-08" when the table below is filled
COSTS: Dict[str, Dict[str, float]] = {}


def _cagr(s: pd.Series, years: float, tol_days: int = 45) -> Optional[float]:
    """Annualised return over `years`, or None when the history is too short.

    None, never a shorter-window substitute: GOLDETF holds 3.0y and GOLD1 2.4y,
    so a "5Y CAGR" for either would be a 3-year number wearing a 5-year label and
    would compare directly against GOLDBEES' real one. tol_days allows for the
    listing date landing a few weeks inside the window."""
    if s is None or len(s) < 30:
        return None
    end = s.index[-1]
    start_target = end - pd.Timedelta(days=int(years * 365.25))
    if s.index[0] > start_target + pd.Timedelta(days=tol_days):
        return None
    seg = s[s.index >= start_target]
    if len(seg) < 20 or seg.iloc[0] <= 0:
        return None
    span = (seg.index[-1] - seg.index[0]).days / 365.25
    if span <= 0.5:
        return None

    # UNADJUSTED SPLIT GUARD. Found by this very table on its first run: AUTOIETF
    # printed a 3Y CAGR of -42.17% against AUTOBEES' +24.56% on the SAME index, a
    # 67pp gap that cannot be tracking. The series carries
    #     2023-09-01  -89.9%  159.50 -> 16.18   (bad print, reversed next session)
    #     2023-12-19  -90.1%  183.70 -> 18.23   (1:10 split, never adjusted back)
    # so everything after Dec-2023 is on a tenth of the earlier basis and any window
    # spanning it is arithmetic on two different units.
    # A ratio-based test, not a percent one: a real market move does not halve or
    # double an index fund in a session, while a split shows up as a clean ~1/N. The
    # answer is None -- flagging the number as unreliable while still printing it
    # would leave a -42% sitting in a column next to a +24%, and the eye takes the
    # number long before it takes the caveat.
    rel = (seg / seg.shift(1)).dropna()
    if len(rel) and ((rel > 1.9) | (rel < 0.55)).any():
        return None
    return round(((seg.iloc[-1] / seg.iloc[0]) ** (1.0 / span) - 1.0) * 100.0, 2)


def build(symbols=None) -> pd.DataFrame:
    """One row per ETF, grouped by what it actually tracks."""
    import etf_universe as U
    import etf_screener as S

    meta_all = U.ETF_UNIVERSE
    syms = list(symbols or meta_all.keys())
    close_df, vol_df = S._fetch_history([f"{s}.NS" for s in syms], period="5y")

    try:
        import etf_inav
        prem = etf_inav.premium_map()
    except Exception as e:
        logger.warning("premium unavailable: %s", e)
        prem = {}

    rows = []
    for sym in syms:
        col = sym if sym in close_df.columns else f"{sym}.NS"
        if col not in close_df.columns:
            continue
        close = close_df[col].dropna()
        if len(close) < 30:
            continue
        meta = meta_all.get(sym, {}) or {}
        vol = vol_df[col].dropna() if col in vol_df.columns else pd.Series(dtype=float)
        turnover_cr = np.nan
        if len(vol) >= 60:
            turnover_cr = round(float((close.tail(60) * vol.tail(60)).median()) / 1e7, 2)
        cost = COSTS.get(sym.upper(), {})
        rows.append({
            "Symbol": sym,
            "Underlying": meta.get("underlying") or meta.get("benchmark_yf") or "?",
            "Asset_Class": meta.get("asset_class", "?"),
            "Issuer": meta.get("issuer", "?"),
            "AUM_Cr": cost.get("aum_cr"),
            "TER_Pct": cost.get("ter"),
            "Turnover_60D_Cr": turnover_cr,
            "Premium_Pct": prem.get(sym.upper()),
            "CAGR_1Y": _cagr(close, 1.0),
            "CAGR_3Y": _cagr(close, 3.0),
            "CAGR_5Y": _cagr(close, 5.0),
            "History_Yrs": round((close.index[-1] - close.index[0]).days / 365.25, 1),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # TRACKING DIFFERENCE, the number that actually decides between two funds on
    # the same underlying. Measured against the BEST performer in the group rather
    # than an external index: these are the same exposure, so any gap between them
    # IS cost plus tracking slippage, and no benchmark series is needed to see it.
    # Only meaningful where 2+ funds share an underlying AND share a horizon, so
    # it is computed per horizon and left blank for a solitary fund.
    for horizon in ("CAGR_3Y", "CAGR_1Y"):
        col = "Track_Diff_" + horizon.split("_")[1]
        df[col] = np.nan
        for _, grp in df.groupby("Underlying"):
            vals = grp[horizon].dropna()
            if len(vals) < 2:
                continue
            best = vals.max()
            df.loc[vals.index, col] = (vals - best).round(2)

    df = df.sort_values(["Asset_Class", "Underlying", "CAGR_3Y"],
                        ascending=[True, True, False], na_position="last")
    return df.reset_index(drop=True)


def main():
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = build()
    if df.empty:
        print("No vehicles built - check data_provider connectivity.")
        return
    path = os.path.join(_DIR, OUTPUT_CSV)
    df.to_csv(path, index=False)
    print(f"\n{len(df)} ETFs -> {OUTPUT_CSV}")
    print(f"AUM / TER table: {'EMPTY - see COSTS in etf_vehicles.py' if not COSTS else COSTS_AS_OF or 'as-of not set'}")
    print()
    # Show only groups where a choice actually exists.
    multi = df.groupby("Underlying").filter(lambda g: len(g) > 1)
    if multi.empty:
        print("No underlying has competing funds in this universe.")
        return
    print("WHERE YOU HAVE A CHOICE (same exposure, different vehicle):")
    for und, grp in multi.groupby("Underlying"):
        print(f"\n  {und}")
        cols = ["Symbol", "TER_Pct", "AUM_Cr", "Turnover_60D_Cr", "Premium_Pct",
                "CAGR_1Y", "CAGR_3Y", "CAGR_5Y", "Track_Diff_3Y"]
        print(grp[cols].to_string(index=False, na_rep="-"))


if __name__ == "__main__":
    main()
