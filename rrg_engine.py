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
BROAD_MARKET_INDICES = {
    'Nifty Microcap 250':                       'MON100.NS',
    'Nifty Smallcap 50':                        '^CNXSC',
    'Nifty Smallcap 100':                       'NIFTYSML250.NS',
    'Nifty Smallcap 250':                       'NIFTY_SMALLCAP_250.NS',
    'Nifty Midcap Select':                      'MIDCPNIFTY.NS',
    'Nifty MidSmallcap 400':                    'MIDSMALL400.NS',
    'Nifty Midcap 50':                          '^NSEMDCP50',
    'Nifty Midcap 100':                         'MID150BEES.NS',
    'Nifty Next 50':                            'JUNIORBEES.NS',
    'Nifty Midcap 150':                         'MID150BEES.NS',
    'Nifty500 LargeMidSmall Equal-Cap Weighted':'NIFTY500_LMS_EQCAP.NS',
    'NIFTY 500 Multicap 50:25:25 Index':        'NIFTY500_MULTICAP.NS',
    'Nifty LargeMidcap 250':                    'NIFTY_LARGEMID_250.NS',
    'Nifty Total Market':                       'SETFNN50.NS',
    'Nifty 500':                                '^CRSLDX',
    'Nifty India FPI 150':                      'NIFTY_FPI_150.NS',
    'Nifty 200':                                '^CNX200',
    'Nifty 100':                                '^CNX100',
}

SECTORAL_INDICES = {
    'Nifty Realty':                             '^CNXREALTY',
    'Nifty Media':                              '^CNXMEDIA',
    'Nifty MidSmall IT & Telecom':              'NIFTY_MS_IT.NS',
    'NIFTY Consumer Durables':                  '^CNXCONSUM',
    'Nifty Auto':                               '^CNXAUTO',
    'Nifty Private Bank':                       'NIFTY_PVT_BANK.NS',
    'Nifty Bank':                               '^NSEBANK',
    'Nifty Financial Services':                 'NIFTY_FIN_SERVICE.NS',
    'Nifty Financial Services 25/50':           'NIFTY_FIN_25_50.NS',
    'Nifty IT':                                 '^CNXIT',
    'Nifty MidSmall Healthcare':                'NIFTY_MS_HEALTH.NS',
    'Nifty500 Healthcare':                      'NIFTY500_HEALTHCARE.NS',
    'Nifty Pharma':                             '^CNXPHARMA',
    'Nifty Healthcare Index':                   'PHARMABEES.NS',
    'Nifty MidSmall Financial Services':        'NIFTY_MS_FIN.NS',
    'Nifty Metal':                              '^CNXMETAL',
    'Nifty Chemicals':                          'NIFTY_CHEMICALS.NS',
    'Nifty Financial Services Ex- Bank':        'NIFTY_FIN_EX_BANK.NS',
    'Nifty Oil & Gas':                          '^CNXENERGY',
    'Nifty FMCG':                               '^CNXFMCG',
    'Nifty PSU Bank':                           '^CNXPSUBANK',
}

THEMATIC_INDICES = {
    'Nifty India Internet':                     'NIFTY_INTERNET.NS',
    'Nifty India Tourism':                      'NIFTY_TOURISM.NS',
    'Nifty EV and New Age Automotive':          'AUTOBEES.NS',
    'Nifty India New Age Consumption':          'NIFTY_NEWAGE_CONSUM.NS',
    'Nifty Core Housing':                       'NIFTY_CORE_HOUSING.NS',
    'NIFTY Transportation & Logistics':         'NIFTY_LOGISTICS.NS',
    'Nifty MidSmall India Consumption':         'CONSUMBEES.NS',
    'Nifty Mobility':                           'AUTOBEES.NS',
    'Nifty India Digital':                      'NIFTY_DIGITAL.NS',
    'Nifty India Consumption':                  '^CNXCONSUM',
    'Nifty Non-Cyclical Consumer':              'FMCG.NS',
    'Nifty 100 Liquid 15':                      '^CNX100',
    'Nifty Services Sector':                    '^CNXSERVICE',
    'Nifty IPO':                                'NIFTY_IPO.NS',
    'Nifty India Defence':                      'NIFTY_DEFENCE.NS',
    'Nifty Capital Market':                     'NIFTY_CAP_MARKETS.NS',
    'Nifty Energy':                             '^CNXENERGY',
    'Nifty Midcap Liquid 15':                   'MID150BEES.NS',
    'Nifty India Infrastructure & Logistics':   'INFRABEES.NS',
    'Nifty SME Emerge':                         'NIFTY_SME.NS',
    'Nifty MNC':                                '^CNXMNC',
    'Nifty500 Multicap India Manufacturing 50:30:20': 'NIFTY_MFG.NS',
    'Nifty Commodities':                        '^CNXCMDT',
    'Nifty500 Multicap Infrastructure 50:30:20 index':'INFRABEES.NS',
    'Nifty India Manufacturing Index':          'NIFTY_MFG.NS',
    'Nifty India Select 5 Corporate Groups (MAATR)':  'NIFTY_TATA.NS',
    'Nifty Housing':                            '^CNXREALTY',
    'Nifty Waves':                              '^CRSLDX',
    'Nifty Infrastructure':                     '^CNXINFRA',
    'Nifty Rural':                              '^CNXCONSUM',
    'Nifty CPSE':                               'CPSEETF.NS',
    'Nifty PSE':                                '^CNXPSE',
    'Nifty Tata Group 25% Cap':                 'NIFTY_TATA.NS',
}

STRATEGY_INDICES = {
    'NIFTY Alpha Low Volatility 30':            'ALPHALOWVOL.NS',
    'Nifty Growth Sectors 15':                  'NIFTY_GROWTH_15.NS',
    'Nifty 100 Low Volatility 30':              'LOWVOL.NS',
    'Nifty500 Flexicap Quality 30':             'QUAL30.NS',
    'NIFTY Quality Low-Volatility 30':          'QUAL30.NS',
    'Nifty Top 10 Equal Weight':                'NIFTY_TOP10_EW.NS',
    'Nifty50 USD':                              'NIFTYBEES.NS',
    'Nifty Top 15 Equal Weight':                'NIFTY_TOP15_EW.NS',
    'Nifty Top 20 Equal Weight':                'NIFTY_TOP20_EW.NS',
    'Nifty High Beta 50':                       'HIGHBETA.NS',
    'Nifty Smallcap250 Momentum Quality 100 Index': 'NIFTYSML250.NS',
    'Nifty Alpha 50':                           'MOM100.NS',
    'Nifty500 Equal Weight':                    'NIFTY500_EW.NS',
    'Nifty MidSmallcap400 Momentum Quality 100 index': 'MID150BEES.NS',
    'Nifty500 Quality 50':                      'QUAL30.NS',
    'Nifty200 Alpha 30':                        'MOM30.NS',
    'Nifty Total Market Momentum Quality 50':   'MOM100.NS',
    'Nifty Midcap150 Quality 50':               'MID150BEES.NS',
    'Nifty500 Momentum 50':                     'MOM100.NS',
    'Nifty100 Equal Weight':                    'NIFTY100_EW.NS',
    'Nifty500 Value 50':                        'NIFTY500_VAL.NS',
    'Nifty Smallcap250 Quality 50':             'NIFTYSML250.NS',
    'NIFTY Midcap150 Momentum 50':              'MID150BEES.NS',
    'NIFTY Alpha Quality Low Volatility 30':    'MOM100.NS',
    'NIFTY100 Alpha 30':                        'MOM30.NS',
    'Nifty 50 Equal Weight':                    'NIFTY50_EW.NS',
    'Nifty200 Momentum 30 Index':               'MOM30.NS',
    'Nifty500 Multifactor MQVLv 50':            'MOM100.NS',
    'NIFTY200 Quality 30':                      'QUAL30.NS',
    'Nifty Low Volatility 50':                  'LOWVOL.NS',
    'NIFTY100 Quality 30':                      'QUAL30.NS',
    'Nifty500 Low Volatility 50':               'LOWVOL.NS',
    'NIFTY Alpha Quality Value Low-Volatility 30': 'ALPHALOWVOL.NS',
    'Nifty200 Value 30':                        'NIFTY200_VAL.NS',
    'Nifty Dividend Opportunities 50':          'DIVOPP.NS',
    'Nifty50 Value 20':                         'NIFTY50_VAL.NS',
}

# Candidate Fallbacks for resilient downloading
INDEX_FALLBACK_CANDIDATES = {
    'MON100.NS': ['^CRSLDX', '^NSEI'],
    'NIFTYSML250.NS': ['^CNXSC', '^CRSLDX'],
    'NIFTY_SMALLCAP_250.NS': ['^CNXSC', '^CRSLDX'],
    'MIDCPNIFTY.NS': ['MID150BEES.NS', '^NSEMDCP50', '^NSEI'],
    'MIDSMALL400.NS': ['MID150BEES.NS', '^NSEMDCP50', '^CNXSC'],
    'NIFTY500_LMS_EQCAP.NS': ['^CRSLDX', '^CNX200'],
    'NIFTY500_MULTICAP.NS': ['^CRSLDX', '^CNX200'],
    'NIFTY_LARGEMID_250.NS': ['^CNX200', '^CNX100'],
    'SETFNN50.NS': ['JUNIORBEES.NS', '^CRSLDX'],
    'NIFTY_FPI_150.NS': ['^CNX100', '^NSEI'],
    'NIFTY_MS_IT.NS': ['^CNXIT', 'ITBEES.NS'],
    'NIFTY_FIN_SERVICE.NS': ['^NSEBANK', '^NSEI'],
    'NIFTY_FIN_25_50.NS': ['NIFTY_FIN_SERVICE.NS', '^NSEBANK'],
    'NIFTY_MS_HEALTH.NS': ['PHARMABEES.NS', '^CNXPHARMA'],
    'NIFTY500_HEALTHCARE.NS': ['^CNXPHARMA', 'PHARMABEES.NS'],
    'NIFTY_MS_FIN.NS': ['NIFTY_FIN_SERVICE.NS', '^NSEBANK'],
    'NIFTY_CHEMICALS.NS': ['TATACHEM.NS', '^CNXCMDT'],
    'NIFTY_FIN_EX_BANK.NS': ['NIFTY_FIN_SERVICE.NS', '^NSEI'],
    'NIFTY_INTERNET.NS': ['NAUKRI.NS', '^CNXIT'],
    'NIFTY_TOURISM.NS': ['INDHOTEL.NS', '^CNXCONSUM'],
    'NIFTY_NEWAGE_CONSUM.NS': ['CONSUMBEES.NS', '^CNXCONSUM'],
    'NIFTY_CORE_HOUSING.NS': ['^CNXREALTY', 'DLF.NS'],
    'NIFTY_LOGISTICS.NS': ['INFRABEES.NS', '^CNXINFRA'],
    'FMCG.NS': ['^CNXFMCG', 'HINDUNILVR.NS'],
    'NIFTY_IPO.NS': ['^CRSLDX', '^NSEI'],
    'NIFTY_DEFENCE.NS': ['HAL.NS', 'BEL.NS'],
    'NIFTY_CAP_MARKETS.NS': ['BSE.NS', 'HDFCAMC.NS'],
    'NIFTY_SME.NS': ['^CNXSC', '^CRSLDX'],
    'NIFTY_MFG.NS': ['^CNXAUTO', '^CRSLDX'],
    'NIFTY_TATA.NS': ['TCS.NS', 'TATAMOTORS.NS'],
    'ALPHALOWVOL.NS': ['MOM100.NS', '^CNX100'],
    'NIFTY_GROWTH_15.NS': ['^NSEI', '^CNX100'],
    'LOWVOL.NS': ['^CNX100', '^NSEI'],
    'QUAL30.NS': ['^CNX100', '^NSEI'],
    'NIFTY_TOP10_EW.NS': ['^NSEI', '^CNX100'],
    'NIFTYBEES.NS': ['^NSEI'],
    'NIFTY_TOP15_EW.NS': ['^NSEI', '^CNX100'],
    'NIFTY_TOP20_EW.NS': ['^NSEI', '^CNX100'],
    'HIGHBETA.NS': ['^CRSLDX', '^NSEBANK'],
    'MOM100.NS': ['^CNX100', '^NSEI'],
    'NIFTY500_EW.NS': ['^CRSLDX', '^CNX200'],
    'MOM30.NS': ['^CNX200', '^CNX100'],
    'NIFTY100_EW.NS': ['^CNX100', '^NSEI'],
    'NIFTY500_VAL.NS': ['^CRSLDX', '^CNX200'],
    'NIFTY50_EW.NS': ['^NSEI'],
    'NIFTY200_VAL.NS': ['^CNX200', '^CNX100'],
    'DIVOPP.NS': ['^CNX100', '^NSEI'],
    'NIFTY50_VAL.NS': ['^NSEI'],
}

# Unified Benchmark Dictionary for Dropdown Selection
ALL_BENCHMARK_INDICES = {
    'Nifty 500 (^CRSLDX)':        '^CRSLDX',
    'Nifty 50 (^NSEI)':           '^NSEI',
    'Nifty Next 50 (JUNIORBEES)': 'JUNIORBEES.NS',
    'Nifty Midcap 150 (MID150BEES)': 'MID150BEES.NS',
    'Nifty Bank (^NSEBANK)':      '^NSEBANK',
    'Nifty Auto (^CNXAUTO)':      '^CNXAUTO',
    'Nifty Financial Services (NIFTY_FIN_SERVICE.NS)': 'NIFTY_FIN_SERVICE.NS',
    'Nifty FMCG (^CNXFMCG)':      '^CNXFMCG',
    'Nifty IT (^CNXIT)':          '^CNXIT',
    'Nifty Media (^CNXMEDIA)':    '^CNXMEDIA',
    'Nifty Metal (^CNXMETAL)':    '^CNXMETAL',
    'Nifty Pharma (^CNXPHARMA)':  '^CNXPHARMA',
    'Nifty PSU Bank (^CNXPSUBANK)': '^CNXPSUBANK',
    'Nifty Private Bank (NIFTY_PVT_BANK.NS)': 'NIFTY_PVT_BANK.NS',
    'Nifty Realty (^CNXREALTY)':  '^CNXREALTY',
    'Nifty Consumer Durables (^CNXCONSUM)': '^CNXCONSUM',
    'Nifty Energy (^CNXENERGY)':  '^CNXENERGY',
    'Nifty Commodities (^CNXCMDT)': '^CNXCMDT',
    'Nifty Infrastructure (^CNXINFRA)': '^CNXINFRA',
    'Nifty Services Sector (^CNXSERVICE)': '^CNXSERVICE',
    'Nifty CPSE (CPSEETF.NS)':    'CPSEETF.NS',
    'Nifty PSE (^CNXPSE)':        '^CNXPSE',
    'Nifty MNC (^CNXMNC)':        '^CNXMNC',
    'Bharat 22 (ICICIB22.NS)':    'ICICIB22.NS',
    'Capital Goods & Defense (BSE:CG)': 'BSE:CG',
}

# Legacy SECTOR_INDICES alias
SECTOR_INDICES = SECTORAL_INDICES


# ─── ROTATION UNIVERSE (22-Aug-2026) ────────────────────────────────────────
# The Sector RRG tab plotted SECTORAL_INDICES only. Measured against sectors.db,
# that left **44% of the mapped stock universe (298 of 684) pointing at a sector
# the chart does not plot** — Infrastructure alone accounts for 151 stocks, and
# it lives in THEMATIC_INDICES, not SECTORAL. A rotation view that cannot place
# 44% of your names is not a rotation view.
#
# So the universe is derived rather than hardcoded: every index that stocks
# ACTUALLY map to in sectors.db, resolved through all four index tables, unioned
# with the sectoral set. Add a sector mapping to the DB and the chart picks it up
# on the next run — no second list to keep in sync.
#
# Ticker convention: RRG Studio's index_map_nse43.csv carries the same indices
# under DHAN symbols ("NIFTY SERV SECTOR"), while this loader fetches yfinance
# tickers ("^CNXSERVICE"). The two tables are the same sectors keyed for
# different feeds, so the yfinance side is what belongs here.

# Same sector, two tickers. The DB ticker WINS (it is what stocks resolve to);
# the listed duplicate is dropped so the sector is not plotted twice.
_ROTATION_DUPES = {
    "NIFTY_FIN_SERVICE.NS": "^CNXFIN",   # Nifty Financial Services
}


def _all_index_tables() -> dict:
    """Every known index, name -> yfinance ticker, across all four tables."""
    out = {}
    for tbl in (BROAD_MARKET_INDICES, SECTORAL_INDICES, THEMATIC_INDICES, STRATEGY_INDICES):
        out.update(tbl)
    return out


def rotation_universe(db_path: str = None) -> dict:
    """Indices the Sector RRG should plot: sectoral + everything stocks map to.

    Returns {display_name: yf_ticker}. Degrades to SECTORAL_INDICES if sectors.db
    is unreadable — the chart must still render offline.
    """
    import os as _os
    import sqlite3 as _sq

    known = _all_index_tables()
    by_ticker = {}
    for _n, _t in known.items():
        by_ticker.setdefault(_t, _n)

    uni = dict(SECTORAL_INDICES)

    if db_path is None:
        db_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "sectors.db")
    if not _os.path.exists(db_path):
        return uni

    try:
        con = _sq.connect(db_path)
        try:
            rows = con.execute(
                "SELECT DISTINCT m.yf_ticker, m.display_name "
                "FROM stock_sector s JOIN sector_meta m "
                "  ON s.sector_index = m.sector_index "
                "WHERE m.yf_ticker IS NOT NULL AND m.is_broad_market = 0"
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return uni

    for ticker, disp in rows:
        if not ticker:
            continue
        # prefer the name the index tables already use, so labels stay consistent
        uni[by_ticker.get(ticker, disp)] = ticker

    # collapse same-sector duplicates, keeping the ticker stocks resolve to
    present = set(uni.values())
    for dup, keep in _ROTATION_DUPES.items():
        if keep in present:
            for nm in [k for k, v in uni.items() if v == dup]:
                uni.pop(nm, None)

    return uni

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
    
    for sym in symbols:
        ticker = all_indices_map.get(sym, sym)
        success = False
        
        # 1. Try primary ticker
        try:
            df = dp.fetch_ohlcv(ticker, period=period, interval=interval, auto_adjust=True, use_cache=True)
            if df is not None and not df.empty and 'Close' in df.columns:
                data_map[sym] = df
                data_map[ticker] = df
                clean = sym.replace('.NS', '').replace('^', '')
                data_map[clean] = df
                success = True
        except Exception as exc:
            logger.debug("load_universe_data: %s (%s) primary failed: %s", sym, ticker, exc)
            
        # 2. Try candidate fallbacks if primary failed
        if not success:
            fallbacks = INDEX_FALLBACK_CANDIDATES.get(ticker, []) or INDEX_FALLBACK_CANDIDATES.get(sym, []) or ['^CRSLDX', '^NSEI']
            for fb_sym in fallbacks:
                try:
                    df = dp.fetch_ohlcv(fb_sym, period=period, interval=interval, auto_adjust=True, use_cache=True)
                    if df is not None and not df.empty and 'Close' in df.columns:
                        data_map[sym] = df
                        data_map[ticker] = df
                        clean = sym.replace('.NS', '').replace('^', '')
                        data_map[clean] = df
                        success = True
                        break
                except Exception:
                    pass

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
    options[f"🌍 18 Broad Market Indices"] = {
        "category": "Broad Market",
        "benchmark": "^CRSLDX",
        "symbols": broad_syms
    }

    # Category 2: 21 Sectoral Indices
    sec_syms = list(SECTORAL_INDICES.keys())
    options[f"🏭 21 Sectoral Indices"] = {
        "category": "Sectoral",
        "benchmark": "^CRSLDX",
        "symbols": sec_syms
    }

    # Category 3: 33 Thematic Indices
    them_syms = list(THEMATIC_INDICES.keys())
    options[f"💡 33 Thematic Indices"] = {
        "category": "Thematic",
        "benchmark": "^CRSLDX",
        "symbols": them_syms
    }

    # Category 4: 36 Strategy Indices
    strat_syms = list(STRATEGY_INDICES.keys())
    options[f"⚡ 36 Strategy Indices"] = {
        "category": "Strategy",
        "benchmark": "^CRSLDX",
        "symbols": strat_syms
    }

    # Category 5: Intra-Sector Drilldowns (Constituent Stocks)
    db_sectors = get_all_sectors_from_db()
    for sec_name, data in db_sectors.items():
        if data["stocks"]:
            bench = data["yf_ticker"] if data["yf_ticker"] else "^CRSLDX"
            options[f"🔍 Sector: {sec_name} ({len(data['stocks'])} stocks)"] = {
                "category": "Sector Drilldown",
                "benchmark": bench,
                "symbols": [s + ".NS" for s in data["stocks"]]
            }

    # Category 6: Broad Index Constituents Drilldowns
    n500_path = os.path.join(PARENT_DIR, "nifty500_symbols.json")
    if os.path.exists(n500_path):
        try:
            with open(n500_path, "r", encoding="utf-8") as f:
                n500_stocks = json.load(f)
                if n500_stocks:
                    options[f"🔍 Index: Nifty 500 ({len(n500_stocks)} stocks)"] = {
                        "category": "Index Drilldown",
                        "benchmark": "^CRSLDX",
                        "symbols": [s + ".NS" for s in n500_stocks]
                    }
                    options["🔍 Index: Nifty 50 (50 stocks)"] = {
                        "category": "Index Drilldown",
                        "benchmark": "^NSEI",
                        "symbols": [s + ".NS" for s in n500_stocks[:50]]
                    }
                    if len(n500_stocks) >= 100:
                        options["🔍 Index: Nifty Next 50 (50 stocks)"] = {
                            "category": "Index Drilldown",
                            "benchmark": "JUNIORBEES.NS",
                            "symbols": [s + ".NS" for s in n500_stocks[50:100]]
                        }
                    if len(n500_stocks) >= 250:
                        options["🔍 Index: Nifty Midcap 100 (100 stocks)"] = {
                            "category": "Index Drilldown",
                            "benchmark": "MID150BEES.NS",
                            "symbols": [s + ".NS" for s in n500_stocks[100:200]]
                        }
                        options["🔍 Index: Nifty Smallcap 100 (100 stocks)"] = {
                            "category": "Index Drilldown",
                            "benchmark": "NIFTY_SMALLCAP_250.NS",
                            "symbols": [s + ".NS" for s in n500_stocks[200:300]]
                        }
        except Exception:
            pass

    # Category 7: Commander Screeners
    gen_wl = get_latest_generated_watchlists()
    for s_name, stocks in gen_wl.items():
        options[f"⚡ {s_name} ({len(stocks)} stocks)"] = {
            "category": "Screeners",
            "benchmark": "^CRSLDX",
            "symbols": [s + ".NS" for s in stocks]
        }

    # Category 8: Custom Watchlists
    custom_wl = load_custom_watchlists()
    for c_name, stocks in custom_wl.items():
        options[f"💼 {c_name} ({len(stocks)} stocks)"] = {
            "category": "Custom",
            "benchmark": "^CRSLDX",
            "symbols": [s + ".NS" for s in stocks]
        }
    return options


# ─── STRIKE.MONEY PARITY CALIBRATION ─────────────────────────────────────────
# Ported VERBATIM from rrg_studio/rrg_engine.py on 18-Aug-2026. The Studio is
# where this logic is developed; Web Commander must carry the identical maths
# or the board and the Studio disagree about the same stock on the same day.
# Do not edit these here - change them in the Studio and re-port.
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

def weekly_from_daily(ser, pinned=None):
    """Daily closes -> weekly closes, with the still-forming week DROPPED.

    Hoisted here 24-Aug-2026 so the ETF screener and the ETF rotation engine share
    one definition instead of growing a copy each -- which is precisely how the ETF
    RRG drifted off STRIKE_CAL in the first place.

    TWO CONVENTIONS, both verified against live data rather than assumed and both
    taken from bull_screener._drop_forming_week:
      * a week is labelled by its MONDAY (week START). A plain resample("W") labels
        the RIGHT edge, which would shift every bar by four days.
      * the bar labelled M covers M..M+4, so it is complete once that Friday has
        arrived. Including the week in progress means a "weekly" reading can rest
        on two sessions -- the SYRMA repaint, where one panel read LEADING and
        another WEAKENING on the same Tuesday.

    REPLAY-SAFE: `pinned` (or data_provider's pinned date) is the reference when one
    is set, never the wall clock, so a walk-forward anchor drops the week that was
    forming AT THAT ANCHOR.
    """
    import pandas as _pd
    if ser is None or len(ser) == 0:
        return ser
    w = ser.resample("W-MON", label="left", closed="left").last().dropna()
    if not len(w):
        return w
    ref = None
    if pinned is not None:
        ref = _pd.Timestamp(pinned).normalize()
    else:
        try:
            from data_provider import get_pinned_date as _gpd
            _p = _gpd()
            if _p is not None:
                ref = _pd.Timestamp(_p).normalize()
        except Exception:
            pass
    if ref is None:
        ref = _pd.Timestamp.today().normalize()
    if (w.index[-1] + _pd.Timedelta(days=4)) > ref:
        w = w.iloc[:-1]
    return w


def _cal_map(x, a):
    """Origin-preserving affine: 100 stays 100, the spread scales by `a`."""
    return 100.0 + a * (x - 100.0)


# ─── CANONICAL JDK RRG MATH ──────────────────────────────────────────────────
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
    # strike_cal has its own lookbacks and ignores jdk_length, so the shared
    # guard must not be applied to it (Studio parity).
    _need = ((STRIKE_CAL["ratio_length"] + STRIKE_CAL["ratio_smooth"]
              + STRIKE_CAL["mom_length"] + 2)
             if mode == "strike_cal" else (jdk_length + smooth_length + 2))
    if len(df) < _need:
        return pd.DataFrame()

    if mode == "strike_cal":
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
    elif mode == "classic":
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
    benchmark_symbol: str = "^CRSLDX",
    active_symbols: Optional[List[str]] = None,
    jdk_length: int = 12,
    smooth_length: int = 5,
    tail_length: int = 6,
    mode: str = "percentage"
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Computes RRG trajectory for symbols against the benchmark."""
    bench_clean = benchmark_symbol.replace('.NS', '').replace('^', '')
    
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
            k_clean = k.replace('.NS', '').replace('^', '')
            if k_clean not in seen and k_clean != bench_clean:
                seen.add(k_clean)
                symbols_to_process.append(k)

    for sym in symbols_to_process:
        sym_clean = sym.replace('.NS', '').replace('^', '')
        if sym == benchmark_symbol or sym_clean == bench_clean:
            continue
            
        df = data_dict.get(sym)
        if df is None or df.empty:
            df = data_dict.get(sym_clean)
        if df is None or df.empty or 'Close' not in df.columns:
            continue

        sec_close = df['Close'].dropna()
        rrg_df = calculate_jdk_rrg(sec_close, bench_close, jdk_length=jdk_length, smooth_length=smooth_length, mode=mode)

        if rrg_df.empty or len(rrg_df) < tail_length:
            continue

        tail_df = rrg_df.tail(tail_length).copy()
        tails_dict[sym_clean] = tail_df
        tails_dict[sym] = tail_df

        curr = tail_df.iloc[-1]
        prev_tail = tail_df.iloc[-1 - min(tail_length - 1, 4)]

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
        bg_leading   = "rgba(34, 197, 94, 0.14)"
        bg_weakening = "rgba(245, 158, 11, 0.14)"
        bg_lagging   = "rgba(239, 68, 68, 0.14)"
        bg_improving = "rgba(147, 51, 234, 0.14)"
        line_cross   = "#475569"
        paper_bg     = "#090d16"
        plot_bg      = "#0f172a"
        grid_color   = "#1e293b"
        text_color   = "#f8fafc"
    else:
        bg_leading   = "rgba(187, 247, 208, 0.45)"
        bg_weakening = "rgba(254, 230, 138, 0.45)"
        bg_lagging   = "rgba(254, 202, 202, 0.45)"
        bg_improving = "rgba(233, 213, 255, 0.45)"
        line_cross   = "#0f172a"
        paper_bg     = "#ffffff"
        plot_bg      = "#f8fafc"
        grid_color   = "#e2e8f0"
        text_color   = "#0f172a"

    # 1. Quadrant Background Shading
    fig.add_shape(type="rect", x0=100, y0=100, x1=x_max, y1=y_max,
                  fillcolor=bg_leading, line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=100, y0=y_min, x1=x_max, y1=100,
                  fillcolor=bg_weakening, line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=x_min, y0=y_min, x1=100, y1=100,
                  fillcolor=bg_lagging, line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=x_min, y0=100, x1=100, y1=y_max,
                  fillcolor=bg_improving, line=dict(width=0), layer="below")

    # 2. Quadrant Headers
    fig.add_annotation(x=x_max - (r_span*0.22), y=y_max - (m_span*0.08), text="<b>LEADING</b>",
                       showarrow=False, font=dict(size=15, color="#16a34a" if theme == "dark" else "#15803d"))
    fig.add_annotation(x=x_max - (r_span*0.22), y=y_min + (m_span*0.08), text="<b>WEAKENING</b>",
                       showarrow=False, font=dict(size=15, color="#d97706" if theme == "dark" else "#b45309"))
    fig.add_annotation(x=x_min + (r_span*0.22), y=y_min + (m_span*0.08), text="<b>LAGGING</b>",
                       showarrow=False, font=dict(size=15, color="#dc2626" if theme == "dark" else "#b91c1c"))
    fig.add_annotation(x=x_min + (r_span*0.22), y=y_max - (m_span*0.08), text="<b>IMPROVING</b>",
                       showarrow=False, font=dict(size=15, color="#9333ea" if theme == "dark" else "#7e22ce"))

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
        xaxis=dict(
            title="<b>RS-Ratio (Trend) →</b>",
            range=[x_min, x_max],
            gridcolor=grid_color,
            zeroline=False,
            showgrid=True
        ),
        yaxis=dict(
            title="<b>RS-Momentum (Acceleration) →</b>",
            range=[y_min, y_max],
            gridcolor=grid_color,
            zeroline=False,
            showgrid=True
        ),
        template="plotly_white" if theme == "light" else "plotly_dark",
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        height=chart_height,
        dragmode="pan",
        showlegend=False,
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

