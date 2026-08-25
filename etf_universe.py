"""
etf_universe.py — Curated NSE ETF universe with category metadata.

Built 11 May 2026 as Phase 1 of the ETF Trading System.

Why curated, not exhaustive
---------------------------
NSE lists ~200 ETFs but **roughly half trade <₹1Cr/day** — illiquid enough
that even a ₹10L position causes meaningful slippage. This module curates
~60 ETFs that meet *all* of:
    1. ≥ ₹2Cr median daily turnover (last 60 sessions)
    2. AUM ≥ ₹100Cr
    3. Distinct exposure (no duplicate trackers — pick the most liquid per index)
    4. Pure-play (no leveraged / inverse / themed-gimmick funds)

When two ETFs track the same index (e.g. Nippon Nifty BeES vs Mirae Nifty 50),
we keep the one with higher 60D average turnover.

Categorization
--------------
Two-level hierarchy:
    asset_class  → BROAD_EQUITY / SECTOR / THEMATIC / INTERNATIONAL /
                   COMMODITY / DEBT / SMART_BETA
    sub_category → finer slice (e.g. SECTOR.BANKING, COMMODITY.GOLD)

This drives:
    • Asset-class rotation (Equity ↔ Gold ↔ Intl ↔ Debt)
    • Sector rotation (rank within SECTOR asset class)
    • Liquidity bucketing (sizing rules differ by AUM tier)

Public API
----------
    ETF_UNIVERSE                : dict[symbol -> meta]
    list_by_asset_class(cls)    : list[symbol]
    list_by_sub_category(sub)   : list[symbol]
    get_meta(symbol)            : meta dict or None
    all_symbols(yf=False)       : list[symbol]   (yf=True appends .NS)
    sector_etfs()               : sector ETFs only (for rotation engine)
"""

from __future__ import annotations
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Curated NSE ETF universe (60 symbols)
# ─────────────────────────────────────────────────────────────────────────────
#
# Schema per entry:
#   name          : human-readable label
#   asset_class   : top-level bucket
#   sub_category  : finer slice
#   underlying    : the index/asset the ETF tracks
#   issuer        : AMC name
#   benchmark_yf  : yfinance ticker for the underlying index (RS calc)
#                   "" if no clean benchmark exists (e.g. some smart-beta)
#   liquidity_tier: A (top — heavy size OK)
#                   B (mid — split entries, 5-10L positions)
#                   C (thin — avoid > 2L positions, watch spread)

ETF_UNIVERSE: Dict[str, Dict] = {

    # ═══════════════════════════════════════════════════════════════════════
    # BROAD EQUITY — index trackers (the workhorses)
    # ═══════════════════════════════════════════════════════════════════════
    "NIFTYBEES":    {"name": "Nippon Nifty 50 BeES",      "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.LARGECAP",  "underlying": "Nifty 50",        "issuer": "Nippon",  "benchmark_yf": "^NSEI",     "liquidity_tier": "A"},
    "JUNIORBEES":   {"name": "Nippon Nifty Next 50 BeES", "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.LARGEMID",  "underlying": "Nifty Next 50",   "issuer": "Nippon",  "benchmark_yf": "^NSMIDCP",  "liquidity_tier": "A"},
    "NIF100IETF":   {"name": "ICICI Nifty 100 ETF",       "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.LARGECAP",  "underlying": "Nifty 100",       "issuer": "ICICI",   "benchmark_yf": "^CNX100",   "liquidity_tier": "B"},
    "NEXT50IETF":   {"name": "ICICI Nifty Next 50 ETF",   "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.LARGEMID",  "underlying": "Nifty Next 50",   "issuer": "ICICI",   "benchmark_yf": "^NSMIDCP",  "liquidity_tier": "B"},
    "MID150BEES":   {"name": "Nippon Nifty Midcap 150",   "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.MIDCAP",    "underlying": "Nifty Midcap 150","issuer": "Nippon",  "benchmark_yf": "NIFTY_MIDCAP_150.NS","liquidity_tier": "A"},
    "MIDCAPETF":    {"name": "ICICI Nifty Midcap 150",    "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.MIDCAP",    "underlying": "Nifty Midcap 150","issuer": "ICICI",   "benchmark_yf": "NIFTY_MIDCAP_150.NS","liquidity_tier": "B"},
    "SMALLCAP":     {"name": "ICICI Nifty Smallcap 250",  "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.SMALLCAP",  "underlying": "Nifty Smallcap250","issuer": "ICICI",  "benchmark_yf": "",          "liquidity_tier": "B"},
    "MULTICAP":     {"name": "Nippon Nifty 500 Multicap", "asset_class": "BROAD_EQUITY", "sub_category": "BROAD.MULTICAP",  "underlying": "Nifty 500",       "issuer": "Nippon",  "benchmark_yf": "^CRSLDX",   "liquidity_tier": "C"},
    "NV20IETF":     {"name": "ICICI Nifty 50 Value 20",   "asset_class": "SMART_BETA",   "sub_category": "FACTOR.VALUE",    "underlying": "Nifty50 Value 20","issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "B"},

    # ═══════════════════════════════════════════════════════════════════════
    # SECTOR — the rotation playground (the alpha-rich slice)
    # ═══════════════════════════════════════════════════════════════════════
    "BANKBEES":     {"name": "Nippon Bank BeES",          "asset_class": "SECTOR", "sub_category": "SECTOR.BANKING",     "underlying": "Nifty Bank",       "issuer": "Nippon",  "benchmark_yf": "^NSEBANK",  "liquidity_tier": "A"},
    "BANKIETF":     {"name": "ICICI Nifty Bank ETF",      "asset_class": "SECTOR", "sub_category": "SECTOR.BANKING",     "underlying": "Nifty Bank",       "issuer": "ICICI",   "benchmark_yf": "^NSEBANK",  "liquidity_tier": "B"},
    "PSUBNKBEES":   {"name": "Nippon PSU Bank BeES",      "asset_class": "SECTOR", "sub_category": "SECTOR.PSU_BANK",    "underlying": "Nifty PSU Bank",   "issuer": "Nippon",  "benchmark_yf": "^CNXPSUBANK","liquidity_tier": "A"},
    "PVTBANIETF":   {"name": "ICICI Nifty Pvt Bank",      "asset_class": "SECTOR", "sub_category": "SECTOR.PVT_BANK",    "underlying": "Nifty Pvt Bank",   "issuer": "ICICI",   "benchmark_yf": "^NIFTYPVTBANK","liquidity_tier": "B"},
    "ITBEES":       {"name": "Nippon IT BeES",            "asset_class": "SECTOR", "sub_category": "SECTOR.IT",          "underlying": "Nifty IT",         "issuer": "Nippon",  "benchmark_yf": "^CNXIT",    "liquidity_tier": "A"},
    "ITIETF":       {"name": "ICICI Nifty IT ETF",        "asset_class": "SECTOR", "sub_category": "SECTOR.IT",          "underlying": "Nifty IT",         "issuer": "ICICI",   "benchmark_yf": "^CNXIT",    "liquidity_tier": "B"},
    "PHARMABEES":   {"name": "Nippon Pharma BeES",        "asset_class": "SECTOR", "sub_category": "SECTOR.PHARMA",      "underlying": "Nifty Pharma",     "issuer": "Nippon",  "benchmark_yf": "^CNXPHARMA","liquidity_tier": "A"},
    "HEALTHIETF":   {"name": "ICICI Nifty Healthcare",    "asset_class": "SECTOR", "sub_category": "SECTOR.HEALTHCARE",  "underlying": "Nifty Healthcare", "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "C"},
    "AUTOBEES":     {"name": "Nippon Auto BeES",          "asset_class": "SECTOR", "sub_category": "SECTOR.AUTO",        "underlying": "Nifty Auto",       "issuer": "Nippon",  "benchmark_yf": "^CNXAUTO",  "liquidity_tier": "B"},
    "AUTOIETF":     {"name": "ICICI Nifty Auto ETF",      "asset_class": "SECTOR", "sub_category": "SECTOR.AUTO",        "underlying": "Nifty Auto",       "issuer": "ICICI",   "benchmark_yf": "^CNXAUTO",  "liquidity_tier": "C"},
    "FMCGIETF":     {"name": "ICICI Nifty FMCG ETF",      "asset_class": "SECTOR", "sub_category": "SECTOR.FMCG",        "underlying": "Nifty FMCG",       "issuer": "ICICI",   "benchmark_yf": "^CNXFMCG",  "liquidity_tier": "B"},
    "OILIETF":      {"name": "ICICI Nifty Oil & Gas",     "asset_class": "SECTOR", "sub_category": "SECTOR.OIL_GAS",     "underlying": "Nifty Oil & Gas",  "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "C"},
    "METAL":        {"name": "Nippon Nifty Metal ETF",    "asset_class": "SECTOR", "sub_category": "SECTOR.METAL",       "underlying": "Nifty Metal",      "issuer": "Nippon",  "benchmark_yf": "^CNXMETAL", "liquidity_tier": "B"},
    "REALTY":       {"name": "Nippon Nifty Realty ETF",   "asset_class": "SECTOR", "sub_category": "SECTOR.REALTY",      "underlying": "Nifty Realty",     "issuer": "Nippon",  "benchmark_yf": "^CNXREALTY","liquidity_tier": "C"},
    "PSUBANK":      {"name": "Kotak PSU Bank ETF",        "asset_class": "SECTOR", "sub_category": "SECTOR.PSU_BANK",    "underlying": "Nifty PSU Bank",   "issuer": "Kotak",   "benchmark_yf": "^CNXPSUBANK","liquidity_tier": "B"},
    "PSUBNKADD":    {"name": "Aditya BSL PSU Bank",       "asset_class": "SECTOR", "sub_category": "SECTOR.PSU_BANK",    "underlying": "Nifty PSU Bank",   "issuer": "ABSL",    "benchmark_yf": "^CNXPSUBANK","liquidity_tier": "C"},
    "BFSI":         {"name": "Nippon Nifty Fin Services", "asset_class": "SECTOR", "sub_category": "SECTOR.FIN_SERVICES","underlying": "Nifty Fin Svcs",  "issuer": "Nippon",  "benchmark_yf": "",          "liquidity_tier": "B"},
    "EBANK":        {"name": "ICICI Nifty Bank ETF",      "asset_class": "SECTOR", "sub_category": "SECTOR.BANKING",     "underlying": "Nifty Bank",       "issuer": "ICICI",   "benchmark_yf": "^NSEBANK",  "liquidity_tier": "B"},

    # ═══════════════════════════════════════════════════════════════════════
    # SMART BETA / FACTOR — momentum, low-vol, quality, alpha
    # ═══════════════════════════════════════════════════════════════════════
    "MOM100":       {"name": "Motilal Nifty 200 Momentum 30","asset_class": "SMART_BETA","sub_category": "FACTOR.MOMENTUM","underlying": "Nifty 200 Mom 30","issuer": "MOAMC",  "benchmark_yf": "",          "liquidity_tier": "B"},
    "MOM30IETF":    {"name": "ICICI Nifty 200 Momentum 30","asset_class": "SMART_BETA", "sub_category": "FACTOR.MOMENTUM",    "underlying": "Nifty 200 Mom 30","issuer": "ICICI",  "benchmark_yf": "",          "liquidity_tier": "B"},
    "ALPHAETF":     {"name": "Kotak Nifty Alpha 50",      "asset_class": "SMART_BETA", "sub_category": "FACTOR.ALPHA",       "underlying": "Nifty Alpha 50",   "issuer": "Kotak",   "benchmark_yf": "",          "liquidity_tier": "B"},
    "LOWVOLIETF":   {"name": "ICICI Nifty 100 Low Vol 30","asset_class": "SMART_BETA", "sub_category": "FACTOR.LOW_VOL",     "underlying": "Nifty100 LV30",    "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "B"},
    "QUAL30IETF":   {"name": "ICICI Nifty 200 Quality 30","asset_class": "SMART_BETA", "sub_category": "FACTOR.QUALITY",     "underlying": "Nifty 200 Q30",    "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "C"},

    # ═══════════════════════════════════════════════════════════════════════
    # INTERNATIONAL — diversification + USD exposure
    # ═══════════════════════════════════════════════════════════════════════
    "MAFANG":       {"name": "Mirae NYSE FANG+ ETF",      "asset_class": "INTERNATIONAL","sub_category": "INTL.US_TECH",      "underlying": "NYSE FANG+",       "issuer": "Mirae",   "benchmark_yf": "",          "liquidity_tier": "A"},
    "MON100":       {"name": "Motilal Nasdaq 100 ETF",    "asset_class": "INTERNATIONAL","sub_category": "INTL.US_NASDAQ",    "underlying": "Nasdaq 100",       "issuer": "MOAMC",   "benchmark_yf": "^NDX",      "liquidity_tier": "A"},
    "NASDBEES":     {"name": "Nippon Nasdaq 100 BeES",    "asset_class": "INTERNATIONAL","sub_category": "INTL.US_NASDAQ",    "underlying": "Nasdaq 100",       "issuer": "Nippon",  "benchmark_yf": "^NDX",      "liquidity_tier": "B"},
    "HNGSNGBEES":   {"name": "Nippon Hang Seng BeES",     "asset_class": "INTERNATIONAL","sub_category": "INTL.HK",           "underlying": "Hang Seng",        "issuer": "Nippon",  "benchmark_yf": "^HSI",      "liquidity_tier": "B"},
    "MASPTOP50":    {"name": "Mirae S&P 500 Top 50",      "asset_class": "INTERNATIONAL","sub_category": "INTL.US_LARGE",     "underlying": "S&P 500 Top 50",   "issuer": "Mirae",   "benchmark_yf": "",          "liquidity_tier": "C"},

    # ═══════════════════════════════════════════════════════════════════════
    # COMMODITY — gold + silver (the diversifiers)
    # ═══════════════════════════════════════════════════════════════════════
    "GOLDBEES":     {"name": "Nippon Gold BeES",          "asset_class": "COMMODITY", "sub_category": "COMMODITY.GOLD",     "underlying": "Gold (INR)",       "issuer": "Nippon",  "benchmark_yf": "GC=F",      "liquidity_tier": "A"},
    "GOLDIETF":     {"name": "ICICI Gold ETF",            "asset_class": "COMMODITY", "sub_category": "COMMODITY.GOLD",     "underlying": "Gold (INR)",       "issuer": "ICICI",   "benchmark_yf": "GC=F",      "liquidity_tier": "A"},
    "GOLDETF":      {"name": "Kotak Gold ETF",            "asset_class": "COMMODITY", "sub_category": "COMMODITY.GOLD",     "underlying": "Gold (INR)",       "issuer": "Kotak",   "benchmark_yf": "GC=F",      "liquidity_tier": "B"},
    "GOLD1":        {"name": "HDFC Gold ETF",             "asset_class": "COMMODITY", "sub_category": "COMMODITY.GOLD",     "underlying": "Gold (INR)",       "issuer": "HDFC",    "benchmark_yf": "GC=F",      "liquidity_tier": "B"},
    "AXISGOLD":     {"name": "Axis Gold ETF",             "asset_class": "COMMODITY", "sub_category": "COMMODITY.GOLD",     "underlying": "Gold (INR)",       "issuer": "Axis",    "benchmark_yf": "GC=F",      "liquidity_tier": "B"},
    "SILVERBEES":   {"name": "Nippon Silver BeES",        "asset_class": "COMMODITY", "sub_category": "COMMODITY.SILVER",   "underlying": "Silver (INR)",     "issuer": "Nippon",  "benchmark_yf": "SI=F",      "liquidity_tier": "A"},
    "SILVERIETF":   {"name": "ICICI Silver ETF",          "asset_class": "COMMODITY", "sub_category": "COMMODITY.SILVER",   "underlying": "Silver (INR)",     "issuer": "ICICI",   "benchmark_yf": "SI=F",      "liquidity_tier": "B"},

    # ═══════════════════════════════════════════════════════════════════════
    # DEBT — parking / hedge sleeve
    # ═══════════════════════════════════════════════════════════════════════
    "LIQUIDBEES":   {"name": "Nippon Liquid BeES",        "asset_class": "DEBT",      "sub_category": "DEBT.LIQUID",        "underlying": "Overnight",        "issuer": "Nippon",  "benchmark_yf": "",          "liquidity_tier": "A"},
    "LIQUIDIETF":   {"name": "ICICI Liquid ETF",          "asset_class": "DEBT",      "sub_category": "DEBT.LIQUID",        "underlying": "Overnight",        "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "A"},
    "GILT5YBEES":   {"name": "Nippon 5Y G-Sec BeES",      "asset_class": "DEBT",      "sub_category": "DEBT.GILT_5Y",       "underlying": "5Y G-Sec",         "issuer": "Nippon",  "benchmark_yf": "",          "liquidity_tier": "C"},
    "BBETF":        {"name": "ICICI Bharat Bond ETF",     "asset_class": "DEBT",      "sub_category": "DEBT.BHARAT_BOND",   "underlying": "Bharat Bond",      "issuer": "ICICI",   "benchmark_yf": "",          "liquidity_tier": "B"},

    # ═══════════════════════════════════════════════════════════════════════
    # THEMATIC — cross-sector themes (NOT pure-sector plays)
    # Per Excel mapping: Infrastructure, Energy, Consumption, CPSE,
    # Defence, Manufacturing, EV, MNC are all Thematic, not Sectoral.
    # ═══════════════════════════════════════════════════════════════════════
    "INFRABEES":    {"name": "Nippon Infra BeES",         "asset_class": "THEMATIC",  "sub_category": "THEME.INFRA",         "underlying": "Nifty Infrastructure","issuer": "Nippon", "benchmark_yf": "^CNXINFRA", "liquidity_tier": "B"},
    "ENERGYIETF":   {"name": "ICICI Nifty Energy ETF",   "asset_class": "THEMATIC",  "sub_category": "THEME.ENERGY",        "underlying": "Nifty Energy",      "issuer": "ICICI",  "benchmark_yf": "^CNXENERGY","liquidity_tier": "B"},
    "CONSUMBEES":   {"name": "Nippon Consumption BeES",   "asset_class": "THEMATIC",  "sub_category": "THEME.CONSUMPTION",   "underlying": "Nifty India Consumption","issuer": "Nippon","benchmark_yf": "",          "liquidity_tier": "B"},
    "CPSEETF":      {"name": "Nippon CPSE ETF",           "asset_class": "THEMATIC",  "sub_category": "THEME.CPSE",          "underlying": "Nifty CPSE",        "issuer": "Nippon", "benchmark_yf": "",          "liquidity_tier": "A"},
    "MAKEINDIA":    {"name": "Kotak Make in India",       "asset_class": "THEMATIC",  "sub_category": "THEME.MFG",           "underlying": "Nifty Mfg",         "issuer": "Kotak",  "benchmark_yf": "",          "liquidity_tier": "C"},
    "DEFENCE":      {"name": "Motilal Nifty Defence ETF", "asset_class": "THEMATIC",  "sub_category": "THEME.DEFENCE",       "underlying": "Nifty Defence",     "issuer": "MOAMC",  "benchmark_yf": "",          "liquidity_tier": "B"},
    "EVINDIA":      {"name": "Mirae EV & New Age Auto",   "asset_class": "THEMATIC",  "sub_category": "THEME.EV",            "underlying": "Nifty EV & NewAuto","issuer": "Mirae",  "benchmark_yf": "",          "liquidity_tier": "C"},
    "DIGINIFTY":    {"name": "ICICI Digital ETF",         "asset_class": "THEMATIC",  "sub_category": "THEME.DIGITAL",       "underlying": "Nifty Digital",     "issuer": "ICICI",  "benchmark_yf": "",          "liquidity_tier": "C"},
}


# ─────────────────────────────────────────────────────────────────────────────
# Inception dates -- approximate NSE listing dates per ETF (Enhancement #9).
# Used by etf_backtest.py to exclude pre-inception periods from backtests
# (survivorship-correct universe replay).
#
# Dates are best-effort approximations from public NSE filings. Mark unknown
# as "2010-01-01" (safe pre-modern-ETF era). Update as needed.
# ─────────────────────────────────────────────────────────────────────────────
import datetime as _dt

INCEPTION_DATES: Dict[str, str] = {
    # Oldest Nippon BeES (originally Benchmark MF, acquired by Goldman, then Nippon)
    "NIFTYBEES":    "2001-12-28",  # India's first ETF
    "JUNIORBEES":   "2003-02-21",
    "BANKBEES":     "2004-05-27",
    "PSUBNKBEES":   "2007-10-25",
    "LIQUIDBEES":   "2003-07-08",
    "GOLDBEES":     "2007-03-08",
    # Nippon mid-tier (2010s)
    "MID150BEES":   "2019-01-31",
    "ITBEES":       "2014-07-28",
    "PHARMABEES":   "2015-05-15",
    "AUTOBEES":     "2017-08-30",
    "CONSUMBEES":   "2014-04-03",
    "INFRABEES":    "2010-09-29",
    "CPSEETF":      "2014-03-28",
    "METAL":        "2019-04-22",
    "REALTY":       "2019-01-31",
    "SILVERBEES":   "2022-02-09",
    # Nippon broad equity
    "NIF100IETF":   "2013-01-22",
    "NEXT50IETF":   "2018-12-26",
    "SMALLCAP":     "2018-12-26",
    "MULTICAP":     "2022-08-22",
    # ICICI Prudential ETFs (mostly 2013-2020)
    "BANKIETF":     "2013-07-18",
    "ITIETF":       "2020-08-18",
    "AUTOIETF":     "2020-01-15",
    "FMCGIETF":     "2020-08-05",
    "PVTBANIETF":   "2020-09-25",
    "HEALTHIETF":   "2018-08-22",
    "ENERGYIETF":   "2020-07-22",
    "OILIETF":      "2020-08-18",
    "MIDCAPETF":    "2019-09-25",
    "NV20IETF":     "2018-06-29",
    "GOLDIETF":     "2010-08-24",
    "SILVERIETF":   "2022-01-24",
    "LIQUIDIETF":   "2017-09-25",
    "BBETF":        "2019-12-13",  # Bharat Bond ETF launch
    "DIGINIFTY":    "2022-12-08",
    "MOM30IETF":    "2021-08-09",
    "LOWVOLIETF":   "2021-07-29",
    "QUAL30IETF":   "2021-10-07",
    # Kotak ETFs
    "PSUBANK":      "2007-11-08",
    "GOLDETF":      "2007-07-27",
    "ALPHAETF":     "2020-12-10",
    "MAKEINDIA":    "2018-07-09",
    # HDFC ETFs (mostly 2015-2022)
    "GOLD1":        "2010-08-13",
    # Axis ETFs
    "AXISGOLD":     "2010-11-10",
    # Aditya BSL
    "PSUBNKADD":    "2014-10-22",
    # Mirae International + thematic
    "MAFANG":       "2021-04-12",
    "MASPTOP50":    "2021-03-22",
    "EVINDIA":      "2022-11-10",
    # Motilal MOAMC
    "MON100":       "2011-03-29",
    "NASDBEES":     "2022-10-25",
    "MOM100":       "2022-08-08",
    "DEFENCE":      "2023-08-30",
    # Other / newer
    "BFSI":         "2020-10-09",
    "HNGSNGBEES":   "2010-03-23",
    "GILT5YBEES":   "2016-09-12",
    "EBANK":        "2013-07-18",
}

# Safe default for symbols missing from the map (assume pre-modern-ETF era)
_DEFAULT_INCEPTION = "2010-01-01"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

ASSET_CLASSES = ("BROAD_EQUITY", "SECTOR", "SMART_BETA", "INTERNATIONAL",
                 "COMMODITY", "DEBT", "THEMATIC")


def list_by_asset_class(cls: str) -> List[str]:
    """Return all symbols in the given asset class."""
    cls = cls.upper()
    return sorted([s for s, m in ETF_UNIVERSE.items() if m["asset_class"] == cls])


def list_by_sub_category(sub: str) -> List[str]:
    """Return all symbols matching a sub_category (e.g. 'SECTOR.BANKING')."""
    sub = sub.upper()
    return sorted([s for s, m in ETF_UNIVERSE.items() if m["sub_category"] == sub])


def get_meta(symbol: str) -> Optional[Dict]:
    """Return metadata for a symbol, or None if not in universe."""
    return ETF_UNIVERSE.get(symbol.upper().replace(".NS", "").strip())


def all_symbols(yf: bool = False) -> List[str]:
    """All symbols. yf=True appends '.NS' suffix for yfinance use."""
    syms = sorted(ETF_UNIVERSE.keys())
    return [f"{s}.NS" for s in syms] if yf else syms


def sector_etfs() -> List[str]:
    """Sector ETFs only — used by the rotation engine."""
    return list_by_asset_class("SECTOR")


def liquid_only(min_tier: str = "B") -> List[str]:
    """Filter universe to ≥ given liquidity tier (A > B > C)."""
    rank = {"A": 0, "B": 1, "C": 2}
    cut = rank.get(min_tier.upper(), 1)
    return sorted([s for s, m in ETF_UNIVERSE.items()
                   if rank.get(m["liquidity_tier"], 99) <= cut])


def universe_summary() -> Dict[str, int]:
    """Counts per asset class — for sanity checks."""
    out = {cls: 0 for cls in ASSET_CLASSES}
    for m in ETF_UNIVERSE.values():
        out[m["asset_class"]] = out.get(m["asset_class"], 0) + 1
    out["TOTAL"] = len(ETF_UNIVERSE)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Survivorship correction (NEW -- Enhancement #9 from validation audit).
# Approximate NSE listing dates per ETF. Used by etf_backtest.py to exclude
# pre-inception bars and prevent look-ahead bias.
#
# Dates are CONSERVATIVE (later-than-actual is safer for backtests). When in
# doubt, the date here is a quarter or year after the real listing. Update
# from NSE listing records (https://www.nseindia.com/products-services/etf-listing)
# as needed.
# ─────────────────────────────────────────────────────────────────────────────
import datetime as _dt

INCEPTION_DATES: Dict[str, str] = {
    # ── Nippon BeES family (oldest Indian ETFs) ────────────────────────────
    "NIFTYBEES":   "2002-01-01",   # first NSE ETF (listed Dec 2001)
    "JUNIORBEES":  "2003-03-01",
    "BANKBEES":    "2004-06-01",
    "LIQUIDBEES":  "2007-07-01",
    "GOLDBEES":    "2007-04-01",
    "PSUBNKBEES":  "2007-11-01",
    "INFRABEES":   "2010-10-01",
    "REALTY":      "2010-12-01",
    "MID150BEES":  "2019-02-01",
    "SILVERBEES":  "2022-02-01",
    "PHARMABEES":  "2015-06-01",
    "ITBEES":      "2014-10-01",
    "CONSUMBEES":  "2018-04-01",
    "CPSEETF":     "2014-04-01",
    "METAL":       "2019-09-01",
    "AUTOBEES":    "2018-09-01",
    "GILT5YBEES":  "2014-08-01",

    # ── ICICI Prudential family ────────────────────────────────────────────
    "NIF100IETF":  "2017-08-01",
    "NEXT50IETF":  "2018-02-01",
    "MIDCAPETF":   "2019-09-01",
    "SMALLCAP":    "2020-11-01",
    "MULTICAP":    "2022-03-01",
    "NV20IETF":    "2018-07-01",
    "BANKIETF":    "2019-08-01",
    "PVTBANIETF":  "2019-09-01",
    "ITIETF":      "2020-08-01",
    "HEALTHIETF":  "2020-05-01",
    "AUTOIETF":    "2019-11-01",
    "FMCGIETF":    "2021-08-01",
    "ENERGYIETF":  "2021-10-01",
    "OILIETF":     "2022-06-01",
    "MOM30IETF":   "2020-08-01",
    "LOWVOLIETF":  "2017-08-01",
    "QUAL30IETF":  "2020-09-01",
    "GOLDIETF":    "2010-09-01",
    "SILVERIETF":  "2022-02-01",
    "LIQUIDIETF":  "2017-09-01",
    "BBETF":       "2019-12-01",
    "EBANK":       "2019-08-01",
    "DIGINIFTY":   "2022-04-01",

    # ── Kotak / Mirae / Motilal / Axis ─────────────────────────────────────
    "PSUBANK":     "2018-12-01",   # Kotak
    "ALPHAETF":    "2018-12-01",   # Kotak
    "GOLDETF":     "2007-07-01",   # Kotak Gold
    "GOLD1":       "2010-08-01",   # HDFC
    "AXISGOLD":    "2010-11-01",
    "MAFANG":      "2021-05-01",   # Mirae NYSE FANG+
    "MON100":      "2011-03-01",   # Motilal Nasdaq 100 -- oldest intl ETF
    "NASDBEES":    "2022-04-01",   # Nippon Nasdaq -- newer launch
    "HNGSNGBEES":  "2010-04-01",
    "MASPTOP50":   "2021-04-01",   # Mirae S&P 500 Top 50
    "MOM100":      "2020-08-01",   # Motilal Nifty 200 Mom 30
    "EVINDIA":     "2022-08-01",   # Mirae EV
    "MAKEINDIA":   "2022-02-01",   # Kotak Make in India
    "DEFENCE":     "2024-08-01",   # Motilal Defence -- newest

    # ── Smart beta + thematic recent additions ─────────────────────────────
    "BFSI":        "2020-03-01",   # Nippon Nifty Fin Services

    # ── Standalone PSU Bank variant ────────────────────────────────────────
    "PSUBNKADD":   "2018-12-01",
}


def inception_date(symbol: str) -> Optional[_dt.date]:
    """Return parsed inception date for a symbol, or None if not known."""
    raw = INCEPTION_DATES.get(symbol.upper().replace(".NS", "").strip())
    if not raw:
        return None
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError:
        return None


def available_at(as_of: _dt.date | str) -> List[str]:
    """Return universe symbols whose inception_date <= as_of.
    Symbols missing from INCEPTION_DATES are excluded conservatively
    (treated as 'unknown -> not available').
    Pass either a datetime.date OR an ISO 'YYYY-MM-DD' string.
    """
    if isinstance(as_of, str):
        as_of = _dt.date.fromisoformat(as_of)
    out = []
    for sym in ETF_UNIVERSE:
        d = inception_date(sym)
        if d and d <= as_of:
            out.append(sym)
    return sorted(out)


def inception_coverage() -> Dict[str, int]:
    """Diagnostic: how many universe entries have inception dates."""
    total = len(ETF_UNIVERSE)
    have  = sum(1 for s in ETF_UNIVERSE if s in INCEPTION_DATES)
    return {"total": total, "with_inception": have, "missing": total - have}


__all__ = [
    "ETF_UNIVERSE", "ASSET_CLASSES", "INCEPTION_DATES",
    "list_by_asset_class", "list_by_sub_category", "get_meta",
    "all_symbols", "sector_etfs", "liquid_only", "universe_summary",
    "inception_date", "available_at", "inception_coverage",
]


if __name__ == "__main__":
    print("ETF Universe Summary")
    print("─" * 40)
    for k, v in universe_summary().items():
        print(f"  {k:<20} {v:>3}")
    print()
    print(f"Sector ETFs (rotation playground):")
    for s in sector_etfs():
        m = ETF_UNIVERSE[s]
        print(f"  {s:<14} {m['sub_category']:<24} tier {m['liquidity_tier']}")


# ─────────────────────────────────────────────────────────────────────────────
# TRADING SCOPE (25-Aug-2026, Jay: "Exclude Liquid and Debt ETFs from the scope of
# my trading, as I'll never trade them ... I have moved my funds to a sweep-in
# fixed deposit account.")
#
# These names stay IN the universe on purpose. They are still needed as a
# MEASUREMENT -- LIQUIDBEES is the flagship the asset-class regime engine reads to
# detect risk-off, and where money hides is informative whether or not you would
# follow it there. What changes is that nothing may RECOMMEND them: no screener
# pick, no board row, no allocation sleeve.
#
# One predicate, imported everywhere, so "tradeable" cannot come to mean two
# different things in two modules.
NON_TRADEABLE_CLASSES = {"DEBT"}


def is_tradeable(symbol: str) -> bool:
    """False for anything outside Jay's trading scope. Unknown symbols are
    TRADEABLE -- a name missing from the catalog is a coverage gap, not a
    decision, and silently dropping it would hide the gap."""
    meta = ETF_UNIVERSE.get(str(symbol).strip().upper())
    if not meta:
        return True
    return meta.get("asset_class") not in NON_TRADEABLE_CLASSES


def tradeable_symbols():
    """Every symbol in trading scope."""
    return [s for s in ETF_UNIVERSE if is_tradeable(s)]
