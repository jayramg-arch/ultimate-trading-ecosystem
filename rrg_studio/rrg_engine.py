"""
rrg_engine.py — Canonical JdK Relative Rotation Graph (RRG) Engine (Standalone RRG Studio)

Implements the official JdK Relative Rotation Graph math formula:
  1. RS = (Security Close / Benchmark Close)
  2. RS_SMA = Rolling Mean(RS, jdk_length) [Default: 12]
  3. RS_Ratio_Raw = 100.0 + ((RS - RS_SMA) / RS_SMA) * 100.0
  4. RS_Ratio = Rolling Mean(RS_Ratio_Raw, 5) [5-bar smoothing]
  5. RM1 = 100.0 * (RS_Ratio / Shift(RS_Ratio, 1))
  6. RS_Momentum = Rolling Mean(RM1, jdk_length)

Renders an interactive 2D Scatter Plot canvas in Plotly with:
  • 4 Shaded Quadrants (Leading 🟢, Weakening 🟠, Lagging 🔴, Improving 🔵)
  • (100, 100) Baseline Crosshairs
  • Historical Trajectory Tails showing clockwise rotation
  • Sector & Stock Drill-down capability
  • Strike.Money layout and interactive panning/scaling
"""

from __future__ import annotations

import math
import os
import sys
import json
import sqlite3
import glob
import logging
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# Add parent directory to sys.path to access data_provider & sectors.db
STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(STUDIO_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

SECTORS_DB_PATH = os.path.join(PARENT_DIR, "sectors.db")
WATCHLIST_DIR = os.path.join(PARENT_DIR, "Generated_Watchlists")
USER_WATCHLISTS_PATH = os.path.join(STUDIO_DIR, "rrg_watchlists.json")


# ─── MASTER NIFTY INDICES TAXONOMIES & FALLBACK RESOLVER ─────────────────────
# ─── NSE-AUTHORITATIVE INDEX MAPS (rebuilt 17-Aug-2026) ──────────────────────
#
# Source of NAMES: Nifty_Indices_Master_List.xlsx, downloaded from the NSE
# portal by Jay — 43 indices across the four official categories, with their
# full constituent lists (3,314 memberships, mirrored into
# nse_indices_constituents.json).
# Source of DATA: the Dhan Data API index segment (IDX_I), which carries 158
# NSE indices. All 43 resolve and return current weekly bars.
#
# WHAT THIS REPLACES, and why it matters more than a tidy-up:
# the previous maps held 108 entries whose names came from Strike.Money and
# whose TICKERS were hand-guessed yfinance symbols. Most of those symbols do not
# exist — yfinance does not carry NSE's thematic or factor indices at all — so
# 44 of 108 fetched nothing and were silently papered over by a fallback table
# that substituted a DIFFERENT index and drew it under the requested name. The
# survivors were not much better: 64 live names collapsed to 45 distinct series.
# Two measured examples of what that produced on the chart:
#   * 'Nifty Microcap 250' -> MON100.NS, whose weekly returns correlate +0.52
#     with the NASDAQ Composite and only +0.32..+0.36 with Indian indices. A US
#     tech ETF was being plotted as Indian microcaps, and it sat at the extreme
#     of the broad-market board. The REAL index (NIFTY MICROCAP250) was
#     available from Dhan the entire time.
#   * five STRATEGY names all pointed at MOM100.NS, which correlates +0.98 with
#     Midcap 50 — a midcap tracker wearing five different factor labels.
#
# The fallback table is GONE. With real symbols there is nothing to fall back
# for, and a fallback is not a resilience feature here: fetching a different
# index and labelling it with the name you asked for is worse than a gap,
# because a gap is visible and a mislabelled dot is not.
#
# ONE MAPPING IS INFERRED RATHER THAN CERTAIN: 'Nifty Quality 30' -> NIFTY200
# QUALTY30. Settled with the constituent lists, not by name similarity — of its
# 30 members, 12 sit outside the Nifty 100 but only 3 outside the Nifty 200.
# Strongly indicated, not proven (3 outside the 200 is unexplained); if this
# series ever looks wrong, check NIFTY100 QUALTY30 first.
BROAD_MARKET_INDICES = {
    'Nifty Microcap 250':                       'NIFTY MICROCAP250',
    'Nifty Smallcap 50':                        'NIFTY SMALLCAP 50',
    'Nifty Smallcap 100':                       'NIFTY SMALLCAP 100',
    'Nifty Smallcap 250':                       'NIFTY SMALLCAP 250',
    'Nifty Midcap Select':                      'MIDCPNIFTY',
    'Nifty MidSmallcap 400':                    'NIFTY MIDSMALLCAP 400',
    'Nifty Midcap 50':                          'NIFTYMCAP50',
    'Nifty Midcap 100':                         'NIFTY MID100 FREE',
    'Nifty Next 50':                            'NIFTYNXT50',
    'Nifty Midcap 150':                         'NIFTY MIDCAP 150',
    'Nifty500 LargeMidSmall Equal-Cap Weighted':'NIFTY500 LMS EQL',
    'NIFTY 500 Multicap 50:25:25 Index':        'NIFTY500 MULTICAP',
    'Nifty LargeMidcap 250':                    'NIFTY LARGEMID250',
    'Nifty Total Market':                       'NIFTY TOTAL MKT',
    'Nifty 500':                                'NIFTY 500',
    'Nifty 200':                                'NIFTY 200',
    'Nifty 100':                                'NIFTY 100',
}

SECTORAL_INDICES = {
    'Nifty Realty':                     'CNXREALTY',
    'Nifty Media':                      'CNXMEDIA',
    'Nifty MidSmall IT & Telecom':      'NIFTY MS IT TELCM',
    'NIFTY Consumer Durables':          'NIFTY CONSR DURBL',
    'Nifty Auto':                       'NIFTY AUTO',
    'Nifty Private Bank':               'NIFTY PVT BANK',
    'Nifty Bank':                       'NSEBANK',
    'Nifty Financial Services':         'CNXFIN',
    'Nifty Financial Services 25/50':   'NIFTY FINSRV25 50',
    'Nifty IT':                         'NIFTYIT',
    'Nifty MidSmall Healthcare':        'NIFTY MIDSML HLTH',
    'Nifty Pharma':                     'CNXPHARMA',
    'Nifty Healthcare Index':           'NIFTY HEALTHCARE',
    'Nifty MidSmall Financial Services':'NIFTY MS FIN SERV',
    'Nifty Metal':                      'CNXMETAL',
    'Nifty Financial Services Ex- Bank':'NIFTY FINSEREXBNK',
    'Nifty Oil & Gas':                  'NIFTY OIL AND GAS',
    'Nifty FMCG':                       'NIFTY FMCG',
    'Nifty PSU Bank':                   'NIFTY PSU BANK',
}

THEMATIC_INDICES = {
    'Nifty India Tourism':                            'NIFTY IND TOURISM',
    'Nifty EV and New Age Automotive':                'NIFTY EV',
    'Nifty India New Age Consumption':                'NIFTY NEW CONSUMP',
    'Nifty Core Housing':                             'NIFTY COREHOUSING',
    'NIFTY Transportation & Logistics':               'NIFTY TRANS LOGIS',
    'Nifty MidSmall India Consumption':               'NIFTY MS IND CONS',
    'Nifty Mobility':                                 'NIFTY MOBILITY',
    'Nifty India Digital':                            'NIFTY IND DIGITAL',
    'Nifty India Consumption':                        'NIFTY CONSUMPTION',
    'Nifty Non-Cyclical Consumer':                    'NIFTY NONCYC CONS',
    'Nifty 100 Liquid 15':                            'NIFTY100 LIQ 15',
    'Nifty Services Sector':                          'NIFTY SERV SECTOR',
    'Nifty IPO':                                      'NIFTY IPO',
    'Nifty India Defence':                            'NIFTY IND DEFENCE',
    'Nifty Capital Market':                           'NIFTY CAPITAL MKT',
    'Nifty Energy':                                   'NIFTY ENERGY',
    'Nifty Midcap Liquid 15':                         'NIFTY MID LIQ 15',
    'Nifty MNC':                                      'NIFTY MNC',
    'Nifty500 Multicap India Manufacturing 50:30:20': 'NIFTY MULTI MFG',
    'Nifty Commodities':                              'NIFTY COMMODITIES',
    'Nifty500 Multicap Infrastructure 50:30:20 index':'NIFTY MULTI INFRA',
    'Nifty India Manufacturing Index':                'NIFTY INDIA MFG',
    'Nifty India Select 5 Corporate Groups (MAATR)':  'NIFTY CORP MAATR',
    'Nifty Housing':                                  'NIFTY HOUSING',
    'Nifty Infrastructure':                           'NIFTYINFRA',
    'Nifty Rural':                                    'NIFTY RURAL',
    'Nifty CPSE':                                     'NIFTYCPSE',
    'Nifty PSE':                                      'NIFTYPSE',
    'Nifty Tata Group 25% Cap':                       'NIFTY TATA 25 CAP',
}

STRATEGY_INDICES = {
    'NIFTY Alpha Low Volatility 30':               'NIFTY ALPHALOWVOL',
    'Nifty Growth Sectors 15':                     'NIFTY GROWSECT 15',
    'Nifty 100 Low Volatility 30':                 'NIFTY100 LOW VOLATILITY 30',
    'Nifty500 Flexicap Quality 30':                'NIFTY500 QLTY50',
    'NIFTY Quality Low-Volatility 30':             'NIFTY QLTY LV 30',
    'Nifty Top 10 Equal Weight':                   'NIFTY TOP 10 EW',
    'Nifty Top 15 Equal Weight':                   'NIFTY TOP 15 EW',
    'Nifty Top 20 Equal Weight':                   'NIFTY TOP 20 EW',
    'Nifty Smallcap250 Momentum Quality 100 Index':'NIFTYSML250MQ 100',
    'Nifty Alpha 50':                              'NIFTY ALPHA 50',
    'Nifty500 Equal Weight':                       'NIFTY500 EW',
    'Nifty200 Alpha 30':                           'NIFTY200 ALPHA 30',
    'Nifty Total Market Momentum Quality 50':      'NIFTY MULTI MQ 50',
    'Nifty Midcap150 Quality 50':                  'NIFTY M150 QLTY50',
    'Nifty500 Momentum 50':                        'NIFTY500MOMENTM50',
    'Nifty100 Equal Weight':                       'NIFTY100 EQUAL WEIGHT',
    'Nifty500 Value 50':                           'NIFTY500 VALUE 50',
    'Nifty Smallcap250 Quality 50':                'NIFTY SML250 Q50',
    'NIFTY Midcap150 Momentum 50':                 'NIFTYM150MOMNTM50',
    'NIFTY100 Alpha 30':                           'NIFTY100 ALPHA 30',
    'Nifty 50 Equal Weight':                       'NIFTY50 EQL WGT',
    'Nifty200 Momentum 30 Index':                  'NIFTY200MOMENTM30',
    'Nifty500 Multifactor MQVLv 50':               'NIFTY500 MQVLV50',
    'NIFTY200 Quality 30':                         'NIFTY200 QUALTY30',
    'NIFTY100 Quality 30':                         'NIFTY100 QUALTY30',
    'Nifty500 Low Volatility 50':                  'NIFTY500 LOWVOL50',
    'Nifty200 Value 30':                           'NIFTY200 VALUE 30',
    'Nifty Dividend Opportunities 50':             'NIFTY DIV OPPS 50',
    'Nifty50 Value 20':                            'NIFTY50 VALUE 20',
}

# Every display-name -> Dhan-symbol pairing in one place, used by the dedup in
# compute_universe_rrg to answer "is this series actually THIS index?".
_ALL_INDEX_TICKERS: Dict[str, str] = {}
for _d in (BROAD_MARKET_INDICES, SECTORAL_INDICES, THEMATIC_INDICES, STRATEGY_INDICES):
    _ALL_INDEX_TICKERS.update(_d)

# INDEX_FALLBACK_CANDIDATES deleted 17-Aug-2026 — see the note above. Kept as an
# empty dict so any stale reference degrades to "no fallback" instead of raising.
INDEX_FALLBACK_CANDIDATES: Dict[str, List[str]] = {}

# Benchmarks offered in the dropdown. Same Dhan symbols; a benchmark that cannot
# be fetched is worse than one fewer choice, so only verified names appear.
ALL_BENCHMARK_INDICES = {
    'Nifty 500 (broadest)':         'NIFTY 500',
    'Nifty Total Market':           'NIFTY TOTAL MKT',
    'Nifty 50':                     'NIFTY',
    'Nifty 100':                    'NIFTY 100',
    'Nifty 200':                    'NIFTY 200',
    'Nifty Next 50':                'NIFTYNXT50',
    'Nifty Midcap 150':             'NIFTY MIDCAP 150',
    'Nifty Smallcap 250':           'NIFTY SMALLCAP 250',
    'Nifty Microcap 250':           'NIFTY MICROCAP250',
    'Nifty Bank':                   'NSEBANK',
    'Nifty Financial Services':     'CNXFIN',
    'Nifty IT':                     'NIFTYIT',
    'Nifty Auto':                   'NIFTY AUTO',
    'Nifty Pharma':                 'CNXPHARMA',
    'Nifty FMCG':                   'NIFTY FMCG',
    'Nifty Metal':                  'CNXMETAL',
    'Nifty Energy':                 'NIFTY ENERGY',
    'Nifty Realty':                 'CNXREALTY',
}

# Legacy SECTOR_INDICES alias
SECTOR_INDICES = SECTORAL_INDICES

# Color System for Quadrants (User-specified palette: Leading=Green, Improving=Purple, Weakening=Amber, Lagging=Red)
QUADRANT_COLORS = {
    'Leading':    {'bg': 'rgba(34, 197, 94, 0.14)',  'border': '#16a34a', 'badge': '#15803d', 'label': '🟢 Leading'},
    'Weakening':  {'bg': 'rgba(245, 158, 11, 0.14)', 'border': '#d97706', 'badge': '#b45309', 'label': '🟡 Weakening'},
    'Lagging':    {'bg': 'rgba(239, 68, 68, 0.14)',  'border': '#dc2626', 'badge': '#b91c1c', 'label': '🔴 Lagging'},
    'Improving':  {'bg': 'rgba(147, 51, 234, 0.14)', 'border': '#9333ea', 'badge': '#7e22ce', 'label': '🟣 Improving'},
}


# ─── UNIVERSE LOADER WITH AUTOMATIC FALLBACK RESOLUTION ─────────────────────
try:
    import streamlit as _st
    _cache = _st.cache_data(ttl=600, show_spinner=False)
except Exception:
    def _cache(fn):
        return fn


@_cache
def load_universe_data(symbols: tuple, period: str = "1y", interval: str = "1wk") -> dict:
    """Fetch OHLCV for symbols/indices with name resolution and fallback handling."""
    import data_provider as dp
    data_map = {}
    
    # Combined registry of all indices
    all_indices_map = {}
    all_indices_map.update(BROAD_MARKET_INDICES)
    all_indices_map.update(SECTORAL_INDICES)
    all_indices_map.update(THEMATIC_INDICES)
    all_indices_map.update(STRATEGY_INDICES)
    
    # PROVENANCE (17-Aug). Which ticker ACTUALLY supplied each series — the key
    # the fallback chain silently discards. Without it the broad-market view drew
    # three separate dots for Nifty Midcap 100 / Midcap 150 / MidSmallcap 400 that
    # were all one series (MID150BEES.NS), and a "Nifty500 LargeMidSmall Equal-Cap
    # Weighted" dot that was really ^CRSLDX — i.e. the benchmark, plotted against
    # itself under another name. Stored under a dunder key so the return type and
    # every existing caller are unchanged; consumers must skip "__"-prefixed keys.
    prov = {}

    for sym in symbols:
        ticker = all_indices_map.get(sym, sym)
        success = False

        def _store(_df, _src):
            data_map[sym] = _df
            data_map[ticker] = _df
            data_map[sym.replace('.NS', '').replace('^', '')] = _df
            prov[sym] = _src

        # ONE ATTEMPT, NO SUBSTITUTES (17-Aug). There used to be a second pass here
        # that, on failure, walked INDEX_FALLBACK_CANDIDATES and finally
        # ['^CRSLDX', '^NSEI'] — so a name that could not be fetched was drawn
        # using the BENCHMARK's data under its own label. Now every symbol is a
        # verified Dhan index, and a miss is left as a miss: the symbol simply does
        # not enter data_map, compute_universe_rrg reports it under "collapsed",
        # and the UI says how many of the requested names were plotted.
        try:
            df = dp.fetch_ohlcv(ticker, period=period, interval=interval, auto_adjust=True, use_cache=True)
            if df is not None and not df.empty and 'Close' in df.columns:
                _store(df, ticker)
                success = True
        except Exception as exc:
            logger.debug("load_universe_data: %s (%s) failed: %s", sym, ticker, exc)
        if not success:
            logger.warning("load_universe_data: no data for %s (%s) — not plotted", sym, ticker)

    # ── STALENESS GUARD (17-Aug-2026) ────────────────────────────────────────
    # THE BUG THIS FIXES: the cached weekly 'NIFTY 500' series was one bar behind
    # the stocks (bench last 2026-08-10, HFCL last 2026-08-17). calculate_jdk_rrg
    # inner-joins on the index, so the ENTIRE chart was silently computed at the
    # last COMMON bar — i.e. a week-old snapshot — while Strike showed the current
    # one. Measured on HFCL: ratio 154.02 vs Strike 148.57 (+5.45) stale, and
    # 150.77 (+2.20) once aligned. More than half the apparent calibration error
    # was this. Nothing warned, because a week-old chart looks exactly like a
    # current one.
    #
    # Index bars evidently refresh later than stock bars, so the benchmark is the
    # usual offender — but the rule is applied to EVERY symbol, since a stale
    # constituent is the same defect with a smaller blast radius.
    # One forced re-fetch per lagging symbol, then give up and report: a retry
    # loop against a provider that simply has not published yet is just latency.
    # Skipped entirely when a date is pinned — replay is SUPPOSED to be historical.
    stale = {}
    as_of = None
    try:
        if dp.get_pinned_date() is None:
            def _last(_d):
                try:
                    return _d.index[-1]
                except Exception:
                    return None
            dated = {k: _last(v) for k, v in data_map.items() if not k.startswith("__")}
            dated = {k: v for k, v in dated.items() if v is not None}
            if dated:
                as_of = max(dated.values())
                behind = sorted({k for k, v in dated.items() if v < as_of})
                for k in behind:
                    if k not in symbols:          # alias keys point at the same frame
                        continue
                    try:
                        dp.invalidate_symbol(all_indices_map.get(k, k))
                        df2 = dp.fetch_ohlcv(all_indices_map.get(k, k), period=period,
                                             interval=interval, auto_adjust=True, use_cache=False)
                        if df2 is not None and not df2.empty and 'Close' in df2.columns:
                            t2 = all_indices_map.get(k, k)
                            data_map[k] = df2
                            data_map[t2] = df2
                            data_map[k.replace('.NS', '').replace('^', '')] = df2
                            logger.info("staleness guard: refreshed %s -> %s", k, df2.index[-1].date())
                    except Exception as e:
                        logger.warning("staleness guard: refresh failed for %s: %s", k, e)
                # recompute after the refresh pass and report anything still behind
                dated = {k: _last(v) for k, v in data_map.items() if not k.startswith("__")}
                dated = {k: v for k, v in dated.items() if v is not None}
                as_of = max(dated.values())
                stale = {k: str(v.date()) for k, v in dated.items()
                         if v < as_of and k in symbols}
    except Exception as e:
        logger.warning("staleness guard failed (continuing): %s", e)

    data_map["__source__"] = prov
    data_map["__asof__"] = as_of
    data_map["__stale__"] = stale
    return data_map


# ─── WATCHLIST & SECTOR RESOLVER FUNCTIONS ──────────────────────────────────
def get_all_sectors_from_db() -> Dict[str, Dict[str, Any]]:
    """
    Queries sectors.db and nse_indices_constituents.json for all sector indices and their constituent stock lists.
    Returns dict: {sector_name: {'index': str, 'yf_ticker': str, 'stocks': [symbols]}}
    """
    sectors_map = {}
    
    # 1. Load from sectors.db
    if os.path.exists(SECTORS_DB_PATH):
        try:
            with sqlite3.connect(SECTORS_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                meta_rows = conn.execute("SELECT * FROM sector_meta").fetchall()
                for m in meta_rows:
                    s_idx = m["sector_index"]
                    d_name = m["display_name"]
                    yf = m["yf_ticker"] or s_idx
                    
                    # Fetch constituent stocks
                    stock_rows = conn.execute("SELECT symbol FROM stock_sector WHERE sector_index = ? ORDER BY symbol ASC", (s_idx,)).fetchall()
                    stocks = [r["symbol"] for r in stock_rows]
                    
                    sectors_map[d_name] = {
                        "index": s_idx,
                        "yf_ticker": yf,
                        "stocks": stocks
                    }
        except Exception as e:
            logger.warning("Failed to query sectors.db: %s", e)

    # 2. Enrich from nse_indices_constituents.json (Official NSE constituent listings)
    const_json_paths = [
        os.path.join(STUDIO_DIR, "nse_indices_constituents.json"),
        os.path.join(PARENT_DIR, "nse_indices_constituents.json"),
    ]
    for p in const_json_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    nse_map = json.load(f)
                    for nse_name, nse_stocks in nse_map.items():
                        if nse_name not in sectors_map:
                            yf = SECTORAL_INDICES.get(nse_name) or THEMATIC_INDICES.get(nse_name) or "^CRSLDX"
                            sectors_map[nse_name] = {
                                "index": f"NSE:{nse_name.upper().replace(' ', '_')}",
                                "yf_ticker": yf,
                                "stocks": nse_stocks
                            }
                        elif not sectors_map[nse_name]["stocks"]:
                            sectors_map[nse_name]["stocks"] = nse_stocks
            except Exception as e:
                logger.debug("Failed loading %s: %s", p, e)
            break

    if not sectors_map:
        for name, yf in SECTORAL_INDICES.items():
            sectors_map[name] = {"index": yf, "yf_ticker": yf, "stocks": []}

    return sectors_map


def load_custom_watchlists() -> Dict[str, List[str]]:
    """Loads user-created custom watchlists from rrg_watchlists.json."""
    if os.path.exists(USER_WATCHLISTS_PATH):
        try:
            with open(USER_WATCHLISTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Default initial custom watchlists
    defaults = {
        "🛡️ Defense & Aerospace": ["DATAPATTNS", "HAL", "BEL", "BDL", "COCHINSHIP", "MAZDOCK", "GRSE", "SOLARINDS", "ZENTEC", "MTARTECH", "BEML", "PARAS", "ASTRAMICRO", "BHARATFORG"],
        "🧪 Specialty Chemicals": ["DEEPAKNTR", "AARTIIND", "NAVINFLUOR", "ATUL", "SRF", "CLEAN", "FINEORG", "CHAMBLFERT", "COROMANDEL", "UPL", "PIIND", "TATACHEM"],
        "🏆 Nifty 50 Heavyweights": ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC", "SBIN", "LT", "HINDUNILVR", "AXISBANK", "M&M", "TATAMOTORS", "SUNPHARMA", "NTPC"],
        "⚡ Power & Energy": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "ADANIPOWER", "NHPC", "SJVN", "BHEL", "COALINDIA", "ONGC", "IOC", "BPCL"],
        "🏗️ Real Estate & Infra": ["DLF", "GODREJPROP", "OBEROIRLTY", "LODHA", "PHOENIXLTD", "BRIGADE", "PRESTIGE", "SOBHA", "NCC", "PNCINFRA", "KNRCON"]
    }
    save_custom_watchlists(defaults)
    return defaults


def save_custom_watchlists(watchlists: Dict[str, List[str]]) -> bool:
    """Saves user-created watchlists to rrg_watchlists.json."""
    try:
        with open(USER_WATCHLISTS_PATH, "w", encoding="utf-8") as f:
            json.dump(watchlists, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save custom watchlists: %s", e)
        return False


def get_latest_generated_watchlists() -> Dict[str, List[str]]:
    """Scans Generated_Watchlists directory for latest screeners."""
    screener_map = {}
    if not os.path.exists(WATCHLIST_DIR):
        return screener_map

    patterns = {
        "🎯 Bull Hunter Picks": "LATEST_Bull_Hunter.txt",
        "🌊 Bull Pullback Picks": "LATEST_Bull_Pullback.txt",
        "🐣 Bull EarlyBird Picks": "LATEST_Bull_EarlyBird.txt",
        "💪 Strong Leaders": "LATEST_Bull_StrongLeader.txt",
        "🪙 Golden Matcher Board": "LATEST_Golden_Matcher_Board.txt",
        "🌱 Recovery EarlyBird": "LATEST_Rec_Early_Bird.txt",
        "🛡️ Recovery RS Survivor": "LATEST_Rec_RS_Survivor.txt",
        "🔥 Catalyst Watchlist": "LATEST_Catalyst_Watchlist.txt",
        "💼 Current Portfolio": "LATEST_portfolio.txt",
    }

    for title, fname in patterns.items():
        fpath = os.path.join(WATCHLIST_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    symbols = [line.strip().replace("NSE:", "").replace("BSE:", "").replace(".NS", "") for line in f if line.strip()]
                    if symbols:
                        screener_map[title] = symbols
            except Exception:
                pass

    return screener_map


def get_all_universe_options() -> Dict[str, Dict[str, Any]]:
    """
    Consolidates all Watchlist Categories with exact counts:
      1. 18 Broad Market Indices
      2. 21 Sectoral Indices
      3. 33 Thematic Indices
      4. 36 Strategy Indices
      5. Sector Constituents Drilldowns (from sectors.db)
      6. Index Constituents Drilldowns (Nifty 50, Nifty Next 50, Nifty Midcap 100, Nifty Smallcap 100, Nifty 500)
      7. Commander Screeners (from Generated_Watchlists)
      8. Custom Watchlists (from rrg_watchlists.json)
    """
    options = {}

    # Category 1: 18 Broad Market Indices
    broad_syms = list(BROAD_MARKET_INDICES.keys())
    options[f"🌍 Broad Market ({len(broad_syms)})"] = {
        "category": "Broad Market",
        "benchmark": "NIFTY 500",
        "symbols": broad_syms
    }

    # Category 2: 21 Sectoral Indices
    sec_syms = list(SECTORAL_INDICES.keys())
    options[f"🏭 Sectoral ({len(sec_syms)})"] = {
        "category": "Sectoral",
        "benchmark": "NIFTY 500",
        "symbols": sec_syms
    }

    # Category 3: 33 Thematic Indices
    them_syms = list(THEMATIC_INDICES.keys())
    options[f"💡 Thematic ({len(them_syms)})"] = {
        "category": "Thematic",
        "benchmark": "NIFTY 500",
        "symbols": them_syms
    }

    # Category 4: 36 Strategy Indices
    strat_syms = list(STRATEGY_INDICES.keys())
    options[f"⚡ Strategy ({len(strat_syms)})"] = {
        "category": "Strategy",
        "benchmark": "NIFTY 500",
        "symbols": strat_syms
    }

    # Category 5: DRILL-DOWN — the real constituents of each of the 43 indices,
    # benchmarked against THAT index (17-Aug-2026).
    #
    # Replaces two blocks. The old "Sector Drilldown" read sectors.db, whose
    # membership is our own bookkeeping rather than NSE's. The old "Index
    # Drilldown" was worse: it sliced nifty500_symbols.json BY POSITION —
    # [:50] labelled "Nifty 50", [50:100] "Nifty Next 50", [100:200] "Nifty
    # Midcap 100" — which assumes that file is ordered by market cap in exactly
    # those bands. It is not, so those three universes listed the wrong stocks
    # under real index names, and benchmarked them against ETF proxies.
    #
    # Now sourced from nse_indices_constituents.json, generated from the NSE
    # master list (43 indices, 3,314 memberships). Symbols are passed bare: the
    # Dhan feed wants NSE symbols, and the ".NS" suffix the old code appended is
    # yfinance syntax left over from when this ran on yfinance.
    _members = {}
    for _p in (os.path.join(STUDIO_DIR, "nse_indices_constituents.json"),
               os.path.join(PARENT_DIR, "nse_indices_constituents.json")):
        if os.path.exists(_p):
            try:
                with open(_p, "r", encoding="utf-8") as f:
                    _members = json.load(f)
                break
            except Exception as e:
                logger.warning("constituents load failed (%s): %s", _p, e)

    for _idx_name, _stocks in sorted(_members.items()):
        if not _stocks:
            continue
        _own = _ALL_INDEX_TICKERS.get(_idx_name)
        options[f"🔍 {_idx_name} constituents ({len(_stocks)})"] = {
            "category": "Index Drilldown",
            # Benchmark against the index the stocks BELONG to — that is the
            # question a drill-down answers ("who leads inside this index?").
            # Falls back to the broadest available index, never to a proxy ETF.
            "benchmark": _own or "NIFTY 500",
            "symbols": list(_stocks),
        }

    # Category 7: Commander Screeners
    gen_wl = get_latest_generated_watchlists()
    for s_name, stocks in gen_wl.items():
        options[f"⚡ {s_name} ({len(stocks)} stocks)"] = {
            "category": "Screeners",
            "benchmark": "NIFTY 500",
            "symbols": list(stocks)
        }

    # Category 8: Custom Watchlists
    custom_wl = load_custom_watchlists()
    for c_name, stocks in custom_wl.items():
        options[f"💼 {c_name} ({len(stocks)} stocks)"] = {
            "category": "Custom",
            "benchmark": "NIFTY 500",
            "symbols": list(stocks)
        }
    return options


# ─── CANONICAL JDK RRG MATH ──────────────────────────────────────────────────
# ─── STRIKE.MONEY PARITY CALIBRATION (fitted 17-Aug-2026) ────────────────────
# Fitted against the ONLY Strike ground truth that exists: 17 names exported
# 2026-05-19 16:01 IST (weekly, vs Nifty 500). Read the caveats before trusting
# a coordinate to the decimal.
#
# WHY A FOURTH MODEL. Tuning the existing three plateaued because RS-Ratio and
# RS-Momentum want DIFFERENT treatment, and the UI offers one lookback and one
# smoothing per model — it structurally cannot express the answer. Measured on
# the 17 names, best single-config fits were:
#     strike/39      ratio corr +0.89   momentum corr +0.44
#     weinstein/12   ratio corr +0.26   momentum corr +0.88
# i.e. each model is right on ONE axis and useless on the other. Decoupling the
# axes lifts momentum from +0.44 to +0.93 while ratio holds at +0.93.
#
# The classical Z-score route was tested (48 lookback x window x span combos)
# and REFUTED: correlation falls and the scale collapses. A z-score spans about
# +/-2; Strike's ratio spans 100.6 to 125.7. Strike is percent-deviation based.
# Do not re-propose "Classical JdK" as the parity path.
#
# WHAT THE AFFINE MAP IS. After decoupling, both axes track Strike at ~0.93 but
# are mis-SCALED (ratio 1.53x too wide, momentum 0.43x too narrow). At that
# correlation the remainder is a pure linear rescale, so it is fitted as one
# rather than hunted for with more parameters:
#     ratio    MAE 8.65 -> 2.12
#     momentum MAE 2.22 -> 0.81
#
# THE MAP IS ORIGIN-PRESERVING: y = 100 + a*(x - 100), so `b` is DERIVED as
# 100*(1-a) and is not a free parameter. Only the slopes are fitted.
#
# This was not the first attempt and the reason matters. A free `y = a*x + b`
# fit scored slightly better on paper (ratio MAE 2.12 vs 2.16, momentum 0.81 vs
# 0.93) but it MOVED THE ORIGIN: it mapped 100 -> 99.43 on the ratio axis and
# 100 -> 100.70 on momentum. Caught by looking at the live Studio, where
# "Nifty 500" — plotted against itself as a constituent — read d:0.9 instead of
# sitting on the crosshair. A security identical to its benchmark has RS == 1 by
# construction and MUST land exactly on (100, 100); (100,100) is the definition
# of the RRG centre, so displacing it shifts every quadrant boundary with it.
# That displacement was also the whole of the quadrant-accuracy loss: the free
# fit scored 15/17 against Strike, the constrained one scores 16/17 — the same
# as the uncalibrated model. With a > 0, (x - 100) keeps its sign, so this form
# CANNOT change a quadrant; verified identical on all 17.
# Lesson: fit the scale, never the centre.
#
# HOW MUCH TO TRUST IT — NOW MEASURED OUT-OF-SAMPLE (18-Aug-2026).
# The fit itself is n=17 from ONE date (2026-05-19), all pre-selected strong names
# (every Strike ratio >= 100.56), so it was calibrated on the right-hand side of
# the plane and EXTRAPOLATING on laggards. That caveat has now been tested rather
# than assumed. Jay supplied 14 fresh Strike pairs on a different date, different
# names, EIGHT of them below 100 — the half the fit never saw:
#                       in-sample (n=17)      HELD OUT (n=14)
#     RS-Ratio  MAE           0.46                 0.74   (max 1.58)
#     RS-Mom    MAE           0.25                 0.52   (max 1.79)
#     correlation          0.93 / 0.93        0.9990 / 0.9962
#     quadrant               16/17                14/14
# Degradation is 1.6x / 2.0x — normal, and far better than the +/-2-3 points
# previously warned about here. Sub-100 names are among the most accurate in the
# set (Timken 0.01, Anuras 0.09, IDBI 0.63), so the extrapolation worry did not
# materialise.
# NO REFIT IS WARRANTED: the origin-preserving slope that best fits the held-out
# set is 1.006 (ratio) and 0.913 (momentum) — i.e. ~1.0, so the shipped constants
# have already done the scaling and there is nothing material left to correct.
# Known residual, deliberately NOT corrected: a +0.39 mean bias on ratio (we read
# slightly high on 10 of 14). Nulling it needs an OFFSET, and an offset moves 100
# off 100 — the exact defect fixed earlier the same day. Not worth breaking the
# origin for 0.39.
# Data: rrg_studio/strike_holdout_20260818.csv (pairs + per-name errors).
# REFITTED 17-Aug-2026 (2nd pass). The first parameters (32/5/8) were chosen by
# CORRELATION, before the origin-preserving rescale existed — so the lookbacks
# were never fitted against the error they actually produce. Re-gridded on the
# real objective (mean |coordinate error| AFTER the rescale, both axes weighted
# by Strike's own spread), 24-32 x 6-12 x 7-11:
#                    MAE ratio   MAE mom   leave-one-out   quadrant
#   32/5/8  (old)       2.27       0.97      2.44 / 1.04     15/16
#   25/10/7 (new)       0.47       0.25      0.51 / 0.26     16/16
# Ratio error -79%, momentum -74%. Not a spike: LOO degrades 8%/4%, and the
# neighbours (24,10,7) (26,10,7) (25,10,6) all sit at 0.47-0.54 — a plateau.
# The first grid capped smoothing at 8 and so never saw 10, which is where the
# ratio axis actually wants to be.
STRIKE_CAL = {
    "ratio_length": 25,     # SMA of the RS line
    "ratio_smooth": 10,     # SMA of the percent-deviation series
    "mom_length":   7,      # SMA of the ratio's bar-over-bar ROC
    # SLOPES ONLY. The intercept is DERIVED as 100*(1-a) so the map always passes
    # through (100,100) — do not add a "ratio_b"/"mom_b" key here, that is exactly
    # the free-fit form that displaced the origin (see above).
    "ratio_a": 0.796,
    "mom_a":   3.498,
    "fitted_on": "2026-05-19, n=17, Nifty 500 weekly",
}


def _cal_map(x, a):
    """Origin-preserving affine: 100 stays 100, the spread scales by `a`."""
    return 100.0 + a * (x - 100.0)


def calculate_jdk_rrg(
    sec_series: pd.Series,
    bench_series: pd.Series,
    jdk_length: int = 12,
    smooth_length: int = 5,
    mode: str = "strike"
) -> pd.DataFrame:
    """
    Computes JdK RS-Ratio and RS-Momentum series for a single security against a benchmark.
    
    Modes:
      - 'strike' (Strike.money Institutional 39-week / 200-day EMA parity):
          RS = sec / bench
          RS_MA = EMA(RS, jdk_length)
          RS_Ratio_Raw = 100.0 + ((RS - RS_MA) / RS_MA) * 100.0
          RS_Ratio = SMA(RS_Ratio_Raw, smooth_length)
          RS_Momentum = EMA(100.0 * (RS_Ratio / RS_Ratio[1]), 3)
      - 'weinstein' / 'percentage' (Weinstein Ecosystem / Pine Script v67.4 standard):
          RS = sec / bench
          RS_MA = SMA(RS, jdk_length)
          RS_Ratio_Raw = 100.0 + ((RS - RS_MA) / RS_MA) * 100.0
          RS_Ratio = SMA(RS_Ratio_Raw, smooth_length)
          RS_Momentum = SMA(100.0 * (RS_Ratio / RS_Ratio[1]), jdk_length)
      - 'classic' (StockCharts / Optuma / Classical Z-Score standard):
          RS = (sec / bench) * 100.0
          RS_Ratio = 100.0 + ((RS - SMA(RS, N)) / StDev(RS, N))
          RS_Momentum = 100.0 + ((ROC(RS_Ratio) - Mean(ROC)) / StDev(ROC))
    """
    if sec_series is None or sec_series.empty or bench_series is None or bench_series.empty:
        return pd.DataFrame()

    df = pd.DataFrame({'sec': sec_series, 'bench': bench_series}).dropna()
    # strike_cal has its own lookbacks and ignores jdk_length, so the shared guard
    # would let it through on ~19 bars and return an empty frame after dropna.
    _need = ((STRIKE_CAL["ratio_length"] + STRIKE_CAL["ratio_smooth"] + STRIKE_CAL["mom_length"] + 2)
             if mode == "strike_cal" else (jdk_length + smooth_length + 2))
    if len(df) < _need:
        return pd.DataFrame()

    if mode == "classic":
        # 1. Classical JdK Z-Score Normalization
        rs = (df['sec'] / df['bench']) * 100.0
        rs_sma = rs.rolling(window=jdk_length, min_periods=jdk_length).mean()
        rs_std = rs.rolling(window=jdk_length, min_periods=jdk_length).std(ddof=0).replace(0, np.nan)
        rs_ratio = 100.0 + ((rs - rs_sma) / rs_std)
        if smooth_length > 1:
            rs_ratio = rs_ratio.rolling(window=smooth_length, min_periods=1).mean()
            
        # Momentum Z-score
        roc = (rs_ratio / rs_ratio.shift(1) - 1.0) * 100.0
        roc_sma = roc.rolling(window=jdk_length, min_periods=jdk_length).mean()
        roc_std = roc.rolling(window=jdk_length, min_periods=jdk_length).std(ddof=0).replace(0, np.nan)
        rs_momentum = 100.0 + ((roc - roc_sma) / roc_std)
    elif mode == "strike_cal":
        # Strike.Money PARITY — decoupled axes + affine calibration. See STRIKE_CAL
        # above for the fit, the measured error, and the caveats. jdk_length /
        # smooth_length are IGNORED here on purpose: the whole point of this model
        # is that one shared lookback cannot serve both axes, so exposing the
        # single-N control would silently do nothing.
        _c  = STRIKE_CAL
        rs  = df['sec'] / df['bench']
        _ma = rs.rolling(window=_c["ratio_length"], min_periods=_c["ratio_length"]).mean()
        _raw = 100.0 + ((rs - _ma) / _ma) * 100.0
        _rat = _raw.rolling(window=_c["ratio_smooth"], min_periods=_c["ratio_smooth"]).mean()
        _mom = (100.0 * (_rat / _rat.shift(1))).rolling(
            window=_c["mom_length"], min_periods=_c["mom_length"]).mean()
        rs_ratio    = _cal_map(_rat, _c["ratio_a"])
        rs_momentum = _cal_map(_mom, _c["mom_a"])
    elif mode == "strike":
        # Strike.money 39-week EMA Institutional Model
        rs = df['sec'] / df['bench']
        rs_ema = rs.ewm(span=jdk_length, adjust=False).mean()
        rs_ratio_raw = 100.0 + ((rs - rs_ema) / rs_ema) * 100.0
        rs_ratio = rs_ratio_raw.rolling(window=smooth_length, min_periods=1).mean() if smooth_length > 1 else rs_ratio_raw
        rm1 = 100.0 * (rs_ratio / rs_ratio.shift(1))
        rs_momentum = rm1.ewm(span=3, adjust=False).mean()
    else:
        # Weinstein Ecosystem / Pine Script v67.4 Standard
        rs = df['sec'] / df['bench']
        rs_sma = rs.rolling(window=jdk_length, min_periods=jdk_length).mean()
        rs_ratio_raw = 100.0 + ((rs - rs_sma) / rs_sma) * 100.0
        rs_ratio = rs_ratio_raw.rolling(window=smooth_length, min_periods=smooth_length).mean() if smooth_length > 1 else rs_ratio_raw
        rm1 = 100.0 * (rs_ratio / rs_ratio.shift(1))
        rs_momentum = rm1.rolling(window=jdk_length, min_periods=jdk_length).mean()

    res = pd.DataFrame({
        'Close': df['sec'],
        'RS': rs,
        'RS_Ratio': rs_ratio,
        'RS_Momentum': rs_momentum
    }, index=df.index).dropna()

    if res.empty:
        return pd.DataFrame()

    def get_quadrant(r, m):
        if r >= 100.0 and m >= 100.0:
            return 'Leading'
        elif r >= 100.0 and m < 100.0:
            return 'Weakening'
        elif r < 100.0 and m < 100.0:
            return 'Lagging'
        else:
            return 'Improving'

    res['Quadrant'] = [get_quadrant(r, m) for r, m in zip(res['RS_Ratio'], res['RS_Momentum'])]
    return res


def compute_rrg_info(
    v: float, 
    m: float, 
    vt: float, 
    mt: float
) -> Tuple[str, str, str, str, int, bool]:
    """Exact Python implementation of Pine Script v67.4 f_rrg_info()."""
    dv = v - vt
    dm = m - mt

    # Current Quadrant
    if v >= 0.0 and m >= 0.0:
        cur = "LEADING"
    elif v >= 0.0 and m < 0.0:
        cur = "WEAKENING"
    elif v < 0.0 and m < 0.0:
        cur = "LAGGING"
    else:
        cur = "IMPROVING"

    # Predictive Next Quadrant (Threshold velocity = 0.3)
    nxt = cur
    if cur == "LEADING":
        if dm < -0.3:
            nxt = "WEAKENING"
        elif dv < -0.3 and dm < 0.3:
            nxt = "IMPROVING"
    elif cur == "WEAKENING":
        if dv < -0.3:
            nxt = "LAGGING"
        elif dm > 0.3 and dv > -0.3:
            nxt = "LEADING"
    elif cur == "LAGGING":
        if dm > 0.3:
            nxt = "IMPROVING"
        elif dv > 0.3 and dm > -0.3:
            nxt = "WEAKENING"
    else: # IMPROVING
        if dv > 0.3:
            nxt = "LEADING"
        elif dm < -0.3 and dv < 0.3:
            nxt = "LAGGING"

    # Rotational Vector Arrow Emoji
    if dv > 0.3:
        arrow = "↗️" if dm > 0.3 else ("↘️" if dm < -0.3 else "➡️")
    elif dv < -0.3:
        arrow = "↖️" if dm > 0.3 else ("↙️" if dm < -0.3 else "⬅️")
    else:
        arrow = "⬆️" if dm > 0.3 else ("⬇️" if dm < -0.3 else "•")

    traj = f"{cur} (stable)" if nxt == cur else f"{cur} → {nxt}"
    sc = 2 if cur == "LEADING" else 0

    tr = (
        (cur == "LEADING" and nxt in ["LEADING", "IMPROVING"]) or
        (cur == "IMPROVING" and nxt == "LEADING") or
        (cur == "LAGGING" and nxt == "IMPROVING") or
        (cur == "WEAKENING" and nxt == "LEADING")
    )

    return arrow, traj, cur, nxt, sc, tr


def compute_universe_rrg(
    data_dict: Dict[str, pd.DataFrame],
    benchmark_symbol: str = "NIFTY 500",
    active_symbols: Optional[List[str]] = None,
    jdk_length: int = 12,
    smooth_length: int = 5,
    tail_length: int = 6,
    mode: str = "percentage"
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Computes RRG trajectory for symbols against the benchmark.

    Symbols that resolved to the SAME underlying series are collapsed to one —
    see the dedup block below. The names dropped are reported on the returned
    frame as `summary_df.attrs["collapsed"]` so the UI can say so out loud
    rather than quietly plotting fewer series than the label claims.
    """
    bench_clean = benchmark_symbol.replace('.NS', '').replace('^', '')
    _prov = data_dict.get("__source__") or {}

    bench_df = data_dict.get(benchmark_symbol)
    if bench_df is None or bench_df.empty:
        bench_df = data_dict.get(bench_clean)
    if (bench_df is None or bench_df.empty) and "^NSEI" in data_dict:
        bench_df = data_dict.get("^NSEI")
    if (bench_df is None or bench_df.empty) and "NSEI" in data_dict:
        bench_df = data_dict.get("NSEI")
        
    if bench_df is None or bench_df.empty:
        if not data_dict:
            return pd.DataFrame(), {}
        bench_df = list(data_dict.values())[0]

    bench_close = bench_df['Close'].dropna() if 'Close' in bench_df.columns else bench_df.iloc[:, 0].dropna()

    # BENCHMARK LAG (17-Aug-2026). calculate_jdk_rrg inner-joins, so a benchmark
    # one bar behind the constituents silently moves the ENTIRE chart back to the
    # last common bar — a week-old picture that is indistinguishable from a
    # current one. load_universe_data now force-refreshes laggards; this is the
    # second line, for when the provider genuinely has not published yet.
    # Reported, never fatal: an old chart is still worth seeing IF you know it is
    # old. Surfaced on summary_df.attrs so the UI can say the date out loud.
    bench_lag_note = ""
    try:
        _uni_asof = data_dict.get("__asof__")
        _b_last = bench_close.index[-1] if len(bench_close) else None
        if _uni_asof is not None and _b_last is not None and _b_last < _uni_asof:
            bench_lag_note = (f"benchmark {bench_clean} last {_b_last.date()} but constituents "
                              f"have {_uni_asof.date()} — chart is computed at {_b_last.date()}")
            logger.warning("compute_universe_rrg: %s", bench_lag_note)
    except Exception:
        pass

    summary_rows = []
    tails_dict = {}

    # If active_symbols provided, only compute for active_symbols
    if active_symbols:
        symbols_to_process = active_symbols
    else:
        # Deduplicate keys
        seen = set()
        symbols_to_process = []
        for k in data_dict.keys():
            if k.startswith("__"):        # provenance / metadata keys
                continue
            k_clean = k.replace('.NS', '').replace('^', '')
            if k_clean not in seen and k_clean != bench_clean:
                seen.add(k_clean)
                symbols_to_process.append(k)

    # ── COLLAPSE SYMBOLS THAT RESOLVED TO THE SAME SERIES ────────────────────
    # Two ways the universe lists more names than it has data for:
    #   1. the map itself points two entries at one ticker (Nifty Midcap 100 AND
    #      Nifty Midcap 150 are both MID150BEES.NS);
    #   2. INDEX_FALLBACK_CANDIDATES substitutes a DIFFERENT index when the
    #      declared one will not download (NIFTY500_LMS_EQCAP.NS -> ^CRSLDX).
    # Either way the chart drew one series several times under different labels,
    # which reads as independent confirmation when it is a single line. Worse for
    # (2): the dot is labelled as an index it is not.
    #
    # Rule: a name keeps its dot only if the data came from ITS OWN declared
    # ticker. A name whose data arrived via a fallback is dropped, not relabelled
    # and not silently plotted — the same "unknown reads as unknown" rule used in
    # zone_engine.overhead_room. If several names share one source and NONE owns
    # it, the first is kept so the series is not lost entirely.
    # Fingerprint is by resolved source when provenance exists, else by the data.
    _bench_fp = (len(bench_close), float(bench_close.iloc[-1]), float(bench_close.iloc[0]))
    _fp_owner, _kept, collapsed = {}, [], []
    shortened = []   # plotted, but with fewer tail bars than requested

    def _fingerprint(_s, _df):
        src = _prov.get(_s)
        if src:
            return ("src", src)
        c = _df['Close'].dropna()
        if c.empty:
            return ("empty", _s)
        return ("data", len(c), round(float(c.iloc[-1]), 6), round(float(c.iloc[0]), 6))

    for sym in symbols_to_process:
        sym_clean = sym.replace('.NS', '').replace('^', '')
        df = data_dict.get(sym)
        if df is None or df.empty:
            df = data_dict.get(sym_clean)
        if df is None or df.empty or 'Close' not in df.columns:
            _kept.append(sym)          # let the main loop handle/skip it
            continue

        c = df['Close'].dropna()
        # IS the benchmark, whatever it is called. The old test compared the
        # DISPLAY NAME ("Nifty 500") against the resolved ticker ("CRSLDX") and so
        # never fired — which is why the benchmark appeared as its own constituent.
        if (len(c), float(c.iloc[-1]), float(c.iloc[0])) == _bench_fp:
            if sym != benchmark_symbol and sym_clean != bench_clean:
                collapsed.append(f"{sym} → is the benchmark ({bench_clean})")
            continue

        fp = _fingerprint(sym, df)
        if fp in _fp_owner:
            owner = _fp_owner[fp]
            collapsed.append(f"{sym} → same series as {owner}"
                             + (f" (via {_prov[sym]})" if _prov.get(sym) else ""))
            continue

        # Data came from a fallback, i.e. this is not this index — drop it rather
        # than draw a mislabelled dot, UNLESS nothing else claims that series.
        declared = _ALL_INDEX_TICKERS.get(sym, sym)
        src = _prov.get(sym)
        if src and src != declared and any(
                _ALL_INDEX_TICKERS.get(o, o) == src for o in symbols_to_process if o != sym):
            collapsed.append(f"{sym} → no data; fell back to {src}, which is another index")
            continue

        _fp_owner[fp] = sym
        _kept.append(sym)

    symbols_to_process = _kept

    for sym in symbols_to_process:
        sym_clean = sym.replace('.NS', '').replace('^', '')
        if sym == benchmark_symbol or sym_clean == bench_clean:
            continue

        df = data_dict.get(sym)
        if df is None or df.empty:
            df = data_dict.get(sym_clean)
        if df is None or df.empty or 'Close' not in df.columns:
            # Reported, not silent: otherwise the expander's arithmetic does not
            # close (21 requested - 6 collapsed rendered 14, not 15) and the user
            # is left to wonder which name vanished and why.
            collapsed.append(f"{sym} → no data from any provider")
            continue

        sec_close = df['Close'].dropna()
        rrg_df = calculate_jdk_rrg(sec_close, bench_close, jdk_length=jdk_length, smooth_length=smooth_length, mode=mode)

        if rrg_df.empty:
            collapsed.append(f"{sym} → too little history for this model "
                             f"({len(sec_close)} bars)")
            continue
        # SHORT TAIL != NO PLOT (18-Aug-2026, Jay: dropdown said Strategy 29 but the
        # constituent list showed 19). A name with fewer usable bars than the
        # requested tail used to be DROPPED ENTIRELY — so raising Tail Bars silently
        # deleted series. At tail=15 that cost Broad 1, Sectoral 1, Thematic 4 and
        # Strategy 10, because the newer indices carry only 52-61 weekly bars and the
        # calibrated model spends 42 of them on warm-up (25 + 10 + 7).
        # The tail is a DISPLAY preference; the head is the datum. Draw whatever tail
        # exists and say it was shortened, rather than discard a valid coordinate.
        _tl = min(tail_length, len(rrg_df))
        if _tl < 2:
            collapsed.append(f"{sym} → only {len(rrg_df)} usable bar; a trajectory needs 2")
            continue
        if _tl < tail_length:
            shortened.append(f"{sym}: {_tl}-bar tail (asked {tail_length})")

        tail_df = rrg_df.tail(_tl).copy()
        tails_dict[sym_clean] = tail_df
        tails_dict[sym] = tail_df

        curr = tail_df.iloc[-1]
        # Clamp against the ACTUAL tail, not the requested one — with a shortened
        # tail `-1 - min(tail_length-1, 4)` indexes past the start of the frame.
        prev_tail = tail_df.iloc[-1 - min(_tl - 1, 4)]

        v = curr['RS_Ratio'] - 100.0
        m = curr['RS_Momentum'] - 100.0
        vt = prev_tail['RS_Ratio'] - 100.0
        mt = prev_tail['RS_Momentum'] - 100.0

        arrow, traj, cur_q, nxt_q, rrg_sc, is_tradeable = compute_rrg_info(v, m, vt, mt)

        recent_chg = ((sec_close.iloc[-1] / sec_close.iloc[-5]) - 1) * 100.0 if len(sec_close) >= 5 else 0.0
        dist_from_center = math.sqrt(v**2 + m**2)

        dx = curr['RS_Ratio'] - prev_tail['RS_Ratio']
        dy = curr['RS_Momentum'] - prev_tail['RS_Momentum']
        heading_deg = (math.degrees(math.atan2(dy, dx)) + 360) % 360

        quad_title = curr['Quadrant']
        q_rank_map = {'Leading': 1, 'Improving': 2, 'Weakening': 3, 'Lagging': 4}
        q_rank = q_rank_map.get(quad_title, 5)

        summary_rows.append({
            'Symbol':           sym_clean,
            'RS-Ratio':         round(curr['RS_Ratio'], 2),
            'RS-Momentum':      round(curr['RS_Momentum'], 2),
            'Quadrant':         quad_title,
            'Quadrant_Rank':    q_rank,
            'Quadrant_Badge':   QUADRANT_COLORS[quad_title]['label'],
            '4W %':             round(recent_chg, 2),
            'Distance':         round(dist_from_center, 2),
            'Heading Deg':      round(heading_deg, 1),
            'Arrow':            arrow,
            'Trajectory':       traj,
            'Next Quadrant':    nxt_q,
            'RRG Score':        rrg_sc,
            'Tradeable Gate':   "✓ BUY OK" if is_tradeable else "✗ WAIT",
            'Is_Tradeable':     is_tradeable,
            'Last_Price':       round(curr['Close'], 2)
        })

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(by=['Quadrant_Rank', 'Distance'], ascending=[True, False])

    # Carried on .attrs so the UI can report what was collapsed. A view that
    # silently plots 14 of 18 requested names looks complete; this makes the
    # difference visible without changing the return signature.
    summary_df.attrs["collapsed"] = collapsed
    summary_df.attrs["shortened"] = shortened
    summary_df.attrs["bench_lag"] = bench_lag_note
    summary_df.attrs["stale"] = data_dict.get("__stale__") or {}
    # The date the coordinates are ACTUALLY computed at — the last bar shared by
    # the benchmark and the constituents, which is not necessarily today.
    try:
        summary_df.attrs["as_of"] = str(bench_close.index[-1].date())
    except Exception:
        summary_df.attrs["as_of"] = ""
    return summary_df, tails_dict


def smooth_curve_points(x_vals: List[float], y_vals: List[float], num_points: int = 60) -> Tuple[List[float], List[float]]:
    """
    Interpolates discrete (RS-Ratio, RS-Momentum) tail coordinates into a high-resolution,
    smooth Catmull-Rom / cubic parametric spline curve to eliminate jagged zigzag lines.
    """
    n = len(x_vals)
    if n < 3:
        return x_vals, y_vals
    
    t = np.linspace(0, 1, n)
    t_smooth = np.linspace(0, 1, num_points)
    
    try:
        deg = min(3, n - 1)
        poly_x = np.polyfit(t, x_vals, deg)
        poly_y = np.polyfit(t, y_vals, deg)
        x_smooth = np.polyval(poly_x, t_smooth).tolist()
        y_smooth = np.polyval(poly_y, t_smooth).tolist()
        
        # Lock exact endpoints
        x_smooth[0] = x_vals[0]
        y_smooth[0] = y_vals[0]
        x_smooth[-1] = x_vals[-1]
        y_smooth[-1] = y_vals[-1]
        return x_smooth, y_smooth
    except Exception:
        return x_vals, y_vals


# ─── INTERACTIVE PLOTLY RENDERING ───────────────────────────────────────────
def render_rrg_plotly(
    summary_df: pd.DataFrame,
    tails_dict: Dict[str, pd.DataFrame],
    title: str = "Relative Rotation Graph (RRG)",
    tail_length: int = 6,
    selected_symbols: Optional[List[str]] = None,
    label_mode: str = "Show All Tickers",
    chart_height: int = 680,
    theme: str = "light"
) -> go.Figure:
    """Renders an uncompressed, interactive 4-Quadrant Plotly Scatter Chart with smooth spline trails."""
    fig = go.Figure()

    if summary_df.empty:
        fig.update_layout(
            title="No RRG Data Available",
            template="plotly_white" if theme == "light" else "plotly_dark",
            height=chart_height
        )
        return fig

    if selected_symbols:
        summary_df = summary_df[summary_df['Symbol'].isin(selected_symbols)]

    all_r_vals = summary_df['RS-Ratio'].tolist()
    all_m_vals = summary_df['RS-Momentum'].tolist()

    for sym, t_df in tails_dict.items():
        if sym in summary_df['Symbol'].values:
            all_r_vals.extend(t_df['RS_Ratio'].tolist())
            all_m_vals.extend(t_df['RS_Momentum'].tolist())

    min_r, max_r = (min(all_r_vals), max(all_r_vals)) if all_r_vals else (98.0, 102.0)
    min_m, max_m = (min(all_m_vals), max(all_m_vals)) if all_m_vals else (98.0, 102.0)

    r_span = max(abs(max_r - 100.0), abs(100.0 - min_r), 2.0) * 1.15
    m_span = max(abs(max_m - 100.0), abs(100.0 - min_m), 1.0) * 1.25

    x_min, x_max = 100.0 - r_span, 100.0 + r_span
    y_min, y_max = 100.0 - m_span, 100.0 + m_span

    # Palette
    if theme == "dark":
        bg_leading   = "rgba(34, 197, 94, 0.24)"     # deepened 17-Aug (was 0.14)
        bg_weakening = "rgba(245, 158, 11, 0.14)"
        bg_lagging   = "rgba(239, 68, 68, 0.24)"     # deepened 17-Aug (was 0.14)
        bg_improving = "rgba(147, 51, 234, 0.14)"
        line_cross   = "#475569"
        paper_bg     = "#090d16"
        plot_bg      = "#0f172a"
        grid_color   = "rgba(148, 163, 184, 0.30)"
        text_color   = "#f8fafc"
    else:
        # LEADING / LAGGING deepened 17-Aug (Jay: "too faint"). Moved from the
        # -200 tints to -300 at higher alpha; WEAKENING / IMPROVING left alone so
        # the two he called out actually read as the strong signals.
        bg_leading   = "rgba(134, 239, 172, 0.60)"   # was rgba(187,247,208,0.45)
        bg_weakening = "rgba(254, 230, 138, 0.45)"
        bg_lagging   = "rgba(252, 165, 165, 0.60)"   # was rgba(254,202,202,0.45)
        bg_improving = "rgba(233, 213, 255, 0.45)"
        line_cross   = "#0f172a"
        paper_bg     = "#ffffff"
        plot_bg      = "#f8fafc"
        grid_color   = "rgba(100, 116, 139, 0.38)"
        text_color   = "#0f172a"

    # 1. QUADRANT BACKGROUND — UNBOUNDED (17-Aug-2026)
    # Was drawn to the DATA extent (x_max/y_min...), so zooming out or panning ran
    # off the end of the shading and the chart turned white outside it, and the
    # quadrant colours appeared to "compress". Strike keeps the four fields
    # filling the viewport at any zoom. The fix is to anchor each rectangle at the
    # 100/100 cross and extend it far beyond any reachable view: the quadrants are
    # half-planes, so they should be drawn as half-planes.
    # ±1e5 rather than a literal infinity — Plotly has no infinite shape, and the
    # explicit axis `range` set below means this never distorts the initial view
    # or the double-click reset.
    _INF = 100000.0
    for x0, y0, x1, y1, col in (
        (100.0,  100.0,  _INF,  _INF, bg_leading),     # upper-right
        (100.0, -_INF,   _INF, 100.0, bg_weakening),   # lower-right
        (-_INF, -_INF,  100.0, 100.0, bg_lagging),     # lower-left
        (-_INF,  100.0, 100.0,  _INF, bg_improving),   # upper-left
    ):
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
                      fillcolor=col, line=dict(width=0), layer="below")

    # 2. QUADRANT HEADERS — PINNED TO THE VIEWPORT, not to the data.
    # Previously placed at data coordinates derived from the current extent, so
    # panning left carried IMPROVING/LAGGING off-screen entirely. Paper refs keep
    # them in the corners at any zoom or pan, which is what Strike does.
    for _xa, _ya, _txt, _cd, _cl in (
        (0.985, 0.985, "LEADING",   "#16a34a", "#15803d"),
        (0.985, 0.015, "WEAKENING", "#d97706", "#b45309"),
        (0.015, 0.015, "LAGGING",   "#dc2626", "#b91c1c"),
        (0.015, 0.985, "IMPROVING", "#9333ea", "#7e22ce"),
    ):
        fig.add_annotation(
            x=_xa, y=_ya, xref="paper", yref="paper",
            xanchor="right" if _xa > 0.5 else "left",
            yanchor="top" if _ya > 0.5 else "bottom",
            text=f"<b>{_txt}</b>", showarrow=False,
            font=dict(size=15, color=_cd if theme == "dark" else _cl),
        )

    # 3. Crosshairs
    fig.add_hline(y=100.0, line=dict(color=line_cross, width=2.0, dash="solid"))
    fig.add_vline(x=100.0, line=dict(color=line_cross, width=2.0, dash="solid"))

    fig.add_trace(go.Scatter(
        x=[100.0], y=[100.0],
        mode="markers+text",
        marker=dict(size=14, color="#ffffff", symbol="cross", line=dict(width=2, color=line_cross)),
        text=["BENCHMARK (100, 100)"],
        textposition="top center",
        name="Benchmark Center",
        hoverinfo="text"
    ))

    # 4. Trailing Tails & Heads
    top_leader_syms = set(summary_df[summary_df['Quadrant'] == 'Leading'].head(5)['Symbol'].tolist())

    for _, row in summary_df.iterrows():
        sym = row['Symbol']
        quad = row['Quadrant']
        color = QUADRANT_COLORS[quad]['border']

        if sym not in tails_dict:
            continue

        tail_df = tails_dict[sym]
        x_vals = tail_df['RS_Ratio'].tolist()
        y_vals = tail_df['RS_Momentum'].tolist()

        # Connect every single discrete weekly dot smoothly via exact Catmull-Rom spline
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode='lines',
            line=dict(shape='spline', smoothing=0.65, color=color, width=2.5),
            hoverinfo='none',
            showlegend=False
        ))

        n_dots = len(tail_df)
        dot_sizes = np.linspace(4, 11, n_dots).tolist()
        
        tail_hover_texts = []
        for idx in range(n_dots - 1):
            row_hist = tail_df.iloc[idx]
            dt_str = row_hist.name.strftime('%d %b %Y') if hasattr(row_hist.name, 'strftime') else str(row_hist.name)
            bars_ago = n_dots - 1 - idx
            time_unit = "weeks" if "1wk" in str(tail_df.index.freq) or bars_ago > 1 else "bars"
            
            tail_hover_texts.append(
                f"<b>{sym}</b> ({bars_ago} {time_unit} ago · {dt_str})<br>"
                f"Quadrant: {QUADRANT_COLORS.get(row_hist['Quadrant'], {}).get('label', row_hist['Quadrant'])}<br>"
                f"RS-Ratio: {row_hist['RS_Ratio']:.2f}<br>"
                f"RS-Momentum: {row_hist['RS_Momentum']:.2f}"
            )

        fig.add_trace(go.Scatter(
            x=x_vals[:-1],
            y=y_vals[:-1],
            mode='markers',
            marker=dict(
                size=dot_sizes[:-1], 
                color=color, 
                opacity=0.7,
                line=dict(width=0.5, color='#ffffff')
            ),
            hovertext=tail_hover_texts,
            hoverinfo='text',
            showlegend=False
        ))

        head_x = x_vals[-1]
        head_y = y_vals[-1]
        head_dt = tail_df.index[-1].strftime('%d %b %Y') if hasattr(tail_df.index[-1], 'strftime') else str(tail_df.index[-1])
        
        hover_text = (
            f"<b>{sym}</b> (Current · {head_dt})<br>"
            f"Quadrant: {QUADRANT_COLORS[quad]['label']}<br>"
            f"RS-Ratio: {head_x:.2f}<br>"
            f"RS-Momentum: {head_y:.2f}<br>"
            f"4W Change: {row['4W %']:.1f}%<br>"
            f"Trajectory: {row['Trajectory']}<br>"
            f"Tradeable Gate: {row['Tradeable Gate']}"
        )

        if head_x >= 100.0 and head_y >= 100.0:
            text_pos = "top right"
        elif head_x >= 100.0 and head_y < 100.0:
            text_pos = "bottom right"
        elif head_x < 100.0 and head_y < 100.0:
            text_pos = "bottom left"
        else:
            text_pos = "top left"

        show_text_label = True
        if label_mode == "Top Leaders Only" and sym not in top_leader_syms:
            show_text_label = False
        elif label_mode == "Hover Only":
            show_text_label = False

        # Render prominent, high-visibility latest data point dot (enlarged with crisp border)
        fig.add_trace(go.Scatter(
            x=[head_x],
            y=[head_y],
            mode='markers+text' if show_text_label else 'markers',
            marker=dict(size=18, color=color, symbol='circle', line=dict(color='#ffffff', width=2.5)),
            text=[f" <b>{sym}</b>"] if show_text_label else None,
            textposition=text_pos,
            textfont=dict(size=12, color=text_color),
            hovertext=[hover_text],
            hoverinfo="text",
            name=sym
        ))

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=text_color)),
        # autorange=False is REQUIRED, not cosmetic: the quadrant half-planes above
        # extend to ±1e5, and Plotly includes axis-referenced shapes when it
        # autoranges — so the toolbar's Autoscale would otherwise zoom out to the
        # shapes and show four flat colours. The range set here is already derived
        # from the data (heads + tails, padded), which is what Autoscale would have
        # produced anyway; pinning it also makes double-click reset land on the
        # same framing every time. Pan and zoom are unaffected — they set `range`
        # directly rather than going through autorange.
        # layer="above traces" is what brings the GRID BACK (17-Aug, Jay: "the
        # grid lines have vanished"). Plotly paints background -> grid -> shapes
        # (layer="below") -> traces, so once the quadrant rectangles became
        # viewport-filling half-planes they covered every gridline. Shapes cannot
        # be placed between the grid and the traces, so the axes are lifted
        # instead. The grid therefore also crosses the markers — which is what
        # Strike does — so it is kept thin and translucent rather than solid.
        xaxis=dict(
            title="<b>JdK RS-Ratio (Trend) →</b>",
            range=[x_min, x_max],
            autorange=False,
            gridcolor=grid_color,
            gridwidth=1,
            layer="above traces",
            zeroline=False,
            showgrid=True
        ),
        yaxis=dict(
            title="<b>JdK RS-Momentum (Acceleration) →</b>",
            range=[y_min, y_max],
            autorange=False,
            gridcolor=grid_color,
            gridwidth=1,
            layer="above traces",
            zeroline=False,
            showgrid=True
        ),
        template="plotly_white" if theme == "light" else "plotly_dark",
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        height=chart_height,
        dragmode="pan",
        showlegend=False,
        # Hover text was inheriting the template default, which renders the
        # coordinates in a light grey that is hard to read against the tooltip's
        # white ground (Jay, 18-Aug: "make the tooltip font on the coordinates
        # darker"). Set explicitly per theme rather than leaving it to the
        # template, and give the tooltip a solid ground + border so the numbers
        # never sit on a translucent quadrant fill.
        hoverlabel=dict(
            font=dict(color="#0B1220" if theme == "light" else "#F8FAFC", size=12.5),
            bgcolor="#FFFFFF" if theme == "light" else "#111827",
            bordercolor="#64748B",
        ),
        margin=dict(l=50, r=50, t=50, b=50)
    )

    return fig


def render_benchmark_sparkline(
    benchmark_symbol: str, 
    data_map: Dict[str, pd.DataFrame], 
    timeframe: str = "Weekly"
) -> go.Figure:
    """Renders the Strike.Money style top timeline sparkline showing benchmark trajectory."""
    bench_clean = benchmark_symbol.replace('.NS', '').replace('^', '')
    fig = go.Figure()

    if bench_clean in data_map and not data_map[bench_clean].empty:
        df = data_map[bench_clean]
        dates = df.index
        prices = df['Close'] if 'Close' in df.columns else df.iloc[:, 0]
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=prices,
            mode='lines',
            line=dict(color='#2563eb', width=2),
            hoverinfo='x+y'
        ))

        fig.update_layout(
            height=90,
            margin=dict(l=10, r=10, t=5, b=5),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, showticklabels=True, tickfont=dict(size=9, color="#64748b")),
            yaxis=dict(showgrid=False, showticklabels=False),
            showlegend=False
        )
    else:
        fig.update_layout(height=90, margin=dict(l=10, r=10, t=5, b=5), paper_bgcolor="rgba(0,0,0,0)")

    return fig


# ─── SCREENER.IN FUNDAMENTALS & DHAN TECHNICALS INTEGRATION ───────────────────
@_cache
def get_screener_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Fetches institutional fundamental metrics directly from Screener.in with company alias fallback.
    Cached for fast repeated access.
    """
    import requests
    from bs4 import BeautifulSoup

    clean_sym = symbol.strip().upper().replace('.NS', '').replace('^', '').replace('.BO', '')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Try consolidated page first, then standalone
    urls_to_try = [
        f"https://www.screener.in/company/{clean_sym}/consolidated/",
        f"https://www.screener.in/company/{clean_sym}/"
    ]
    
    soup = None
    for u in urls_to_try:
        try:
            r = requests.get(u, headers=headers, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                break
        except Exception:
            pass

    # If direct URL 404s, try Screener Search API to resolve alias / demergers (e.g. Tata Motors -> TMCV)
    if not soup:
        try:
            sr = requests.get(f"https://www.screener.in/api/company/search/?q={clean_sym}", headers=headers, timeout=5)
            if sr.status_code == 200 and sr.json():
                url_path = sr.json()[0]['url']
                r = requests.get(f"https://www.screener.in{url_path}", headers=headers, timeout=5)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
        except Exception:
            pass

    res = {
        "Symbol": clean_sym,
        "Name": clean_sym,
        "Market_Cap_Cr": None,
        "PE": None,
        "ROCE_Pct": None,
        "ROE_Pct": None,
        "Book_Value": None,
        "Div_Yield_Pct": None,
        "Promoter_Pct": None,
        "Debt_to_Equity": None,
        "Sales_Growth_3Y": None,
        "Profit_Growth_3Y": None,
        "Source": "Screener.in"
    }

    if not soup:
        return res

    # Company name
    h1 = soup.find('h1')
    if h1:
        res["Name"] = h1.text.strip()

    # Top ratios card
    top = soup.find(id='top-ratios')
    if top:
        r_map = {}
        for li in top.find_all('li'):
            n = li.find('span', class_='name')
            v = li.find('span', class_='number')
            if n and v:
                r_map[n.text.strip().replace(':', '')] = v.text.strip().replace(',', '').replace('%', '')

        try:
            if "Market Cap" in r_map:
                res["Market_Cap_Cr"] = float(r_map["Market Cap"])
            if "Stock P/E" in r_map:
                res["PE"] = float(r_map["Stock P/E"])
            if "ROCE" in r_map:
                res["ROCE_Pct"] = float(r_map["ROCE"])
            if "ROE" in r_map:
                res["ROE_Pct"] = float(r_map["ROE"])
            if "Book Value" in r_map:
                res["Book_Value"] = float(r_map["Book Value"])
            if "Dividend Yield" in r_map:
                res["Div_Yield_Pct"] = float(r_map["Dividend Yield"])
        except Exception:
            pass

    # Promoter holding
    sh_sec = soup.find('section', id='shareholding')
    if sh_sec:
        table = sh_sec.find('table')
        if table:
            for row in table.find_all('tr'):
                cols = row.find_all('td')
                if cols and ('promoter' in cols[0].text.lower() or 'owners' in cols[0].text.lower()):
                    try:
                        res["Promoter_Pct"] = float(cols[-1].text.replace('%', '').replace(',', '').strip())
                    except Exception:
                        pass
                    break

    # Balance sheet D/E
    bs_sec = soup.find('section', id='balance-sheet')
    if bs_sec:
        table = bs_sec.find('table')
        if table:
            borrowings, equity_cap, reserves = 0.0, 0.0, 0.0
            for row in table.find_all('tr'):
                cols = row.find_all('td')
                if cols:
                    header = cols[0].text.strip().lower()
                    val = cols[-1].text.strip().replace(',', '')
                    try:
                        if 'borrowings' in header:
                            borrowings = float(val)
                        elif 'equity capital' in header or 'share capital' in header:
                            equity_cap = float(val)
                        elif 'reserves' in header:
                            reserves = float(val)
                    except Exception:
                        pass
            equity = equity_cap + reserves
            if equity > 0:
                res["Debt_to_Equity"] = round(borrowings / equity, 2)

    return res


def get_dhan_technicals(
    symbol: str, 
    data_dict: Dict[str, pd.DataFrame], 
    benchmark_symbol: str = "^CRSLDX"
) -> Dict[str, Any]:
    """
    Computes real-time institutional technical metrics from Dhan Data API OHLCV feed:
      • LTP, Day % Chg, 4W % Chg
      • 200 SMA, 50 SMA, 20 EMA
      • Volume & 20-Day Volume Surge Multiplier
      • 52-Week High/Low & Distance from 52W High
      • Mansfield Relative Strength
      • Weinstein Stage (Stage 1 Base, Stage 2 Markup, Stage 3 Distribution, Stage 4 Decline)
    """
    clean_sym = symbol.strip().upper().replace('.NS', '').replace('^', '')
    df = data_dict.get(symbol) if symbol in data_dict else data_dict.get(clean_sym)
    
    res = {
        "Symbol": clean_sym,
        "LTP": 0.0,
        "Day_Chg_Pct": 0.0,
        "4W_Chg_Pct": 0.0,
        "52W_High": 0.0,
        "52W_Low": 0.0,
        "Dist_52W_High_Pct": 0.0,
        "SMA_50": 0.0,
        "SMA_200": 0.0,
        "SMA_Alignment": "Neutral",
        "Volume": 0,
        "Avg_Vol_20D": 0,
        "Vol_Surge": 1.0,
        "Mansfield_RS": 0.0,
        "Weinstein_Stage": "Stage 1 (Base)",
        "Feed": "Dhan Data API"
    }

    if df is None or df.empty or 'Close' not in df.columns:
        return res

    close = df['Close'].dropna()
    if len(close) == 0:
        return res

    ltp = float(close.iloc[-1])
    res["LTP"] = round(ltp, 2)

    # Price Changes
    if len(close) >= 2:
        res["Day_Chg_Pct"] = round(((close.iloc[-1] / close.iloc[-2]) - 1) * 100.0, 2)
    if len(close) >= 5:
        res["4W_Chg_Pct"] = round(((close.iloc[-1] / close.iloc[-5]) - 1) * 100.0, 2)

    # 52-Week High / Low
    lookback_52w = min(len(df), 52 if len(df) < 150 else 252)
    high_52w = float(df['High'].tail(lookback_52w).max()) if 'High' in df.columns else float(close.tail(lookback_52w).max())
    low_52w = float(df['Low'].tail(lookback_52w).min()) if 'Low' in df.columns else float(close.tail(lookback_52w).min())
    res["52W_High"] = round(high_52w, 2)
    res["52W_Low"] = round(low_52w, 2)
    if high_52w > 0:
        res["Dist_52W_High_Pct"] = round(((ltp - high_52w) / high_52w) * 100.0, 2)

    # Moving Averages
    if len(close) >= 50:
        res["SMA_50"] = round(float(close.rolling(50).mean().iloc[-1]), 2)
    if len(close) >= 200:
        res["SMA_200"] = round(float(close.rolling(200).mean().iloc[-1]), 2)

    # SMA Alignment & Weinstein Stage
    sma50 = res["SMA_50"]
    sma200 = res["SMA_200"]
    if sma50 > 0 and sma200 > 0:
        if ltp > sma50 and sma50 > sma200:
            res["SMA_Alignment"] = "🟢 Bullish Stack (Price > 50 > 200)"
            res["Weinstein_Stage"] = "Stage 2 (Markup) 🚀"
        elif ltp < sma50 and sma50 < sma200:
            res["SMA_Alignment"] = "🔴 Bearish Stack (Price < 50 < 200)"
            res["Weinstein_Stage"] = "Stage 4 (Decline) ⚠️"
        elif ltp > sma200 and sma50 <= sma200:
            res["SMA_Alignment"] = "🔵 Base Breakout"
            res["Weinstein_Stage"] = "Stage 1 (Accumulation) 🌱"
        else:
            res["SMA_Alignment"] = "🟠 Top Topping"
            res["Weinstein_Stage"] = "Stage 3 (Distribution) ⏳"
    elif sma50 > 0:
        res["SMA_Alignment"] = "🟢 Above 50 SMA" if ltp > sma50 else "🔴 Below 50 SMA"

    # Volume Analysis
    if 'Volume' in df.columns:
        vol = df['Volume'].dropna()
        if len(vol) >= 20:
            avg20 = float(vol.tail(20).mean())
            cur_vol = float(vol.iloc[-1])
            res["Volume"] = int(cur_vol)
            res["Avg_Vol_20D"] = int(avg20)
            if avg20 > 0:
                res["Vol_Surge"] = round(cur_vol / avg20, 2)

    # Mansfield RS vs Benchmark
    clean_b = benchmark_symbol.replace('.NS', '').replace('^', '')
    bench_df = data_dict.get(benchmark_symbol) if benchmark_symbol in data_dict else data_dict.get(clean_b)
    if bench_df is not None and not bench_df.empty:
        b_close = bench_df['Close'].dropna() if 'Close' in bench_df.columns else bench_df.iloc[:, 0].dropna()
        common_idx = close.index.intersection(b_close.index)
        if len(common_idx) >= 20:
            rs_raw = close.loc[common_idx] / b_close.loc[common_idx]
            rs_base = rs_raw.rolling(20).mean()
            mrs = ((rs_raw / rs_base) - 1.0) * 100.0
            res["Mansfield_RS"] = round(float(mrs.iloc[-1]), 2)

    return res

