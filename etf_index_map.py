# -*- coding: utf-8 -*-
"""Exposure -> index symbol map for the ETF stack (30-Aug-2026).

WHY
---
Jay analyses ETFs on the INDEX chart, not the ETF chart: the index is a clean,
stock-like series while the ETF's wicks are vehicle microstructure rather than sector
information. Spot-for-analysis / futures-for-execution, applied to ETFs. The trade is
then planned and taken on the ETF.

That needs a mapping the ecosystem did not have: for each exposure the universe
selects a vehicle for, WHICH INDEX is it, and what is that index called on each feed.
The two feeds disagree on naming and neither is derivable from the other:

    exposure "Nifty Auto"  ->  Dhan "NIFTY AUTO"  ->  TradingView "NSE:CNXAUTO"
    exposure "Nifty 50"    ->  Dhan "NIFTY"       ->  TradingView "NSE:NIFTY"

Dhan drives GM (technicals via data_provider, per the standing data-provider rule);
TradingView drives S4, where Jay actually charts.

VOLUME IS NEVER BORROWED. THIS MAP ROUTES PRICE STRUCTURE ONLY.
---------------------------------------------------------------
An earlier design borrowed the ETF's volume onto the index chart so S4's V gate could
still fire. Jay rejected it on technical-analysis grounds and he was right: volume
confirmation asserts that THIS volume accompanied THIS price move, and ETF volume did
not produce the index's move - the constituents did. The two genuinely diverge (a thin
ETF prints a spike because one investor sent a large order on a day the index barely
moved; an index breaks out on heavy constituent turnover while its ETF trades nothing).

Fused, the volume-derived constructs stop meaning anything:
    AVWAP / VWAP    sum(price x volume)/sum(volume) over index prices and ETF volumes
                    describes no transaction that happened anywhere - synthetic, not
                    approximate.
    Volume Profile  claims "this much volume traded at this price"; false on both halves.
    VCP dry-up/VDU  contraction is about THAT instrument's own supply drying up.
    OBV/accumulation signing the ETF's volume by the index's direction is incoherent.

The one legitimate use is RV as an EXECUTION-READINESS check - "is the thing I am about
to buy actively trading" - which is liquidity confirmation, not price-action
confirmation. S4's V gate was quietly doing both jobs; only the second survives.

So the two stages stay SEPARATED rather than fused:
    stage 1  INDEX chart  structure, stage, trend, S/R, zones, RS. Price-based only.
                          No volume claim is made, because an index chart cannot
                          honestly make one for a vehicle you have not bought yet.
    stage 2  ETF chart    S4's GO, with price and volume FROM THE SAME INSTRUMENT, so
                          RV, VCP, AVWAP and VP all mean what they say - and the levels
                          are real order prices.

The ETF's wicks are not a defect to route around: if the stop sits on the ETF, the
ETF's wicks are what will hit it. Stage 2 has to see them.

For reference, index volume is unusable anyway - measured on Dhan daily bars:
    NIFTY ..................... 1238 / 1240 bars      NIFTY IND DEFENCE .. 0 / 446
    NIFTY AUTO/METAL/FMCG ...... 517 / 1239 (~42%)    NIFTY EV ........... 0 / 253
TradingView agrees (NSE:NIFTY ~98M/bar, NSE:CNXAUTO ~12.9M/bar, NIFTY_IND_DEFENCE flat
zero), so the feeds will not contradict each other - but "sometimes" is the worst case
for any threshold, which is a second reason stage 1 makes no volume claim at all.

Nothing here is inferred at runtime - the map is data, reviewable in a CSV.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
MAP_CSV = os.path.join(_DIR, "etf_index_map.csv")

# TradingView names that no normalisation can reach from the exposure text. Everything
# else is resolved by matching against the Dhan scrip master and then this table; an
# unresolved TV symbol is left BLANK rather than guessed, because a wrong chart symbol
# would send S4 to the wrong instrument silently.
TV_OVERRIDES: Dict[str, str] = {
    "NIFTY":             "NSE:NIFTY",
    "BANKNIFTY":         "NSE:BANKNIFTY",
    "FINNIFTY":          "NSE:FINNIFTY",
    "MIDCPNIFTY":        "NSE:MIDCPNIFTY",
    "NIFTY AUTO":        "NSE:CNXAUTO",
    "NIFTY IT":          "NSE:CNXIT",
    "NIFTY METAL":       "NSE:CNXMETAL",
    "NIFTY PHARMA":      "NSE:CNXPHARMA",
    "NIFTY FMCG":        "NSE:CNXFMCG",
    "NIFTY REALTY":      "NSE:CNXREALTY",
    "NIFTY ENERGY":      "NSE:CNXENERGY",
    "NIFTY INFRA":       "NSE:CNXINFRA",
    "NIFTY MEDIA":       "NSE:CNXMEDIA",
    "NIFTY PSU BANK":    "NSE:CNXPSUBANK",
    "NIFTY PVT BANK":    "NSE:NIFTYPVTBANK",
    "NIFTY CONSUMPTION": "NSE:CNXCONSUMPTION",
    "NIFTY COMMODITIES": "NSE:CNXCOMMODITIES",
    "NIFTY IND DEFENCE": "NSE:NIFTY_IND_DEFENCE",
    "NIFTY 100":         "NSE:CNX100",
    "NIFTY 200":         "NSE:CNX200",
    "NIFTY 500":         "NSE:CNX500",
    "NIFTY NEXT 50":     "NSE:NIFTYJUNIOR",
    "NIFTY MIDCAP 150":  "NSE:NIFTYMIDCAP150",
    "NIFTY SMLCAP 250":  "NSE:NIFTYSMLCAP250",
    "NIFTY HEALTHCARE":  "NSE:NIFTY_HEALTHCARE",

    # ── RESOLVED 30-Aug-2026 via TradingView symbol_search ────────────────────
    # Every one read back from TradingView's own symbol table, not inferred. TV
    # matches Dhan's spelling for some (NIFTY200MOMENTM30) and diverges sharply for
    # others (Dhan "NIFTYCPSE" is TV "CPSE"; Dhan "NIFTYNXT50" is TV "NIFTYJR"), so
    # neither side can be derived from the other - which is why this table exists.
    "NIFTY ALPHA 50":              "NSE:NIFTYALPHA50",
    "NIFTY200 ALPHA 30":           "NSE:NIFTY200_ALPHA_30",
    "NIFTYCPSE":                   "NSE:CPSE",
    "NIFTY EV":                    "NSE:NIFTY_EV",
    "NIFTY FINSEREXBNK":           "NSE:NIFTY_FINSEREXBNK",
    "Nifty Capital Mkt":           "NSE:NIFTY_CAPITAL_MKT",
    "NIFTY SMALLCAP 250":          "NSE:NIFTYSMLCAP250",
    "NIFTY SMALLCAP 100":          "NSE:CNXSMALLCAP",
    "NIFTYSML250MQ 100":           "NSE:NIFTYSML250MQ_100",
    "NIFTYINFRA":                  "NSE:CNXINFRA",
    "NIFTYIT":                     "NSE:CNXIT",
    "NIFTY100 LOW VOLATILITY 30":  "NSE:NIFTY100LOWVOL30",
    "NIFTY INDIA MFG":             "NSE:NIFTY_INDIA_MFG",
    "NIFTY IND DIGITAL":           "NSE:NIFTY_IND_DIGITAL",
    "NIFTY MIDSMALLCAP 400":       "NSE:NIFTYMIDSML400",
    "NIFTY200MOMENTM30":           "NSE:NIFTY200MOMENTM30",
    "NIFTY500MOMENTM50":           "NSE:NIFTY500MOMENTM50",
    "NIFTYM150MOMNTM50":           "NSE:NIFTYM150MOMNTM50",
    "NIFTYNXT50":                  "NSE:NIFTYJR",
    "NIFTY50 VALUE 20":            "NSE:NIFTY50_VALUE_20",
    "NIFTY OIL AND GAS":           "NSE:NIFTY_OIL_AND_GAS",
}

# ─────────────────────────────────────────────────────────────────────────────
# CONFIRMED BY JAY, 30-Aug-2026. Every entry below was answered directly rather than
# inferred, so it is encoded as an OVERRIDE: the fuzzy matcher never gets to touch it,
# and cannot quietly resolve it differently after a scrip-master change.
# All six verified fetchable from Dhan before being written here.
# KEYS ARE _norm() OUTPUT, not raw exposure text: _norm expands aliases (INFRA ->
# INFRASTRUCTURE) and no longer strips "NIFTY". Print _norm(exposure) before adding one.
DHAN_OVERRIDES = {
    # "Nifty Capital Market" and "Nifty Capital Markets" are the SAME index spelled two
    # ways in the source workbook. Both vehicles map to the one Dhan index; the exposure
    # is also normalised below so the selector stops treating it as two sectors and
    # picking two ETFs for it.
    "NIFTY CAPITAL MARKET":                    "Nifty Capital Mkt",
    "NIFTY CAPITAL MARKETS":                   "Nifty Capital Mkt",
    # INFRAIETF tracks Nifty Infrastructure, NOT Nifty Multi Infra - the matcher had
    # picked the latter, which is a different index.
    "NIFTY INFRASTRUCTURE":                    "NIFTYINFRA",
    # Both were reported as "no Dhan index" on my first pass; the full 119-name list
    # shows they are there, under names no normalisation would have reached.
    "NIFTY SMALLCAP250 MOMENTUM QUALITY 100":  "NIFTYSML250MQ 100",
    "NIFTY MIDCAP 150 MOMENTUM":               "NIFTYM150MOMNTM50",
    "NIFTY MIDCAP 150 MOMENTUM 50":            "NIFTYM150MOMNTM50",
    # Dhan's shorthand for Nifty EV & New Age Automotive.
    "NIFTY EV AND NEW AGE AUTO":               "NIFTY EV",
}

# Exposure spellings that denote ONE index. Normalised before grouping so a spelling
# variant cannot split one sector into two and consume two vehicle slots.
EXPOSURE_ALIASES = {
    "Nifty Capital Markets": "Nifty Capital Market",
}

# Imported, not redefined: etf_candidates owns this list because that is where the
# universe is built. Keeping a second copy here is exactly how the universe came to
# hold 57 names while this map held 51.
try:
    from etf_candidates import DROP_SYMBOLS
except Exception:
    DROP_SYMBOLS = set()

# TradingView carries these even where Dhan does not, so S4 can still chart the index
# in stage 1 while GM falls back to the ETF for structure. The two feeds are
# INDEPENDENT - availability on one says nothing about the other.
TV_ONLY = {
    "Nifty Chemicals": "NSE:NIFTY_CHEMICALS",
}

# EXPOSURES WITH NO NSE INDEX AT ALL. These are not matcher failures - there is no
# Indian index to chart, so the ETF chart is the only option and that is CORRECT, not a
# fallback. Kept separate from "unresolved" because conflating the two would hide real
# gaps behind a pile of expected ones.
NO_NSE_INDEX = {
    "GOLD", "SILVER",                                    # commodities
    "NASDAQ 100", "NASDAQ QUALITY 50", "NYSE FANG",      # US
    "S P 500 TOP 50", "HANG SENG",                       # US / HK
    "OVERNIGHT LIQUID",                                  # cash park (LIQUID1)
}

# Dhan ships some indices under trade-desk shorthand. Canonicalise BOTH sides to the
# long form, rather than stripping "NIFTY" as a stop-word: that stripping turned
# "Nifty 50" into "50" while Dhan's "NIFTY" became the empty string, and left
# "Nifty Bank" ("BANK") unable to ever meet "BANKNIFTY".
_CANON = {
    "NIFTY":      "NIFTY 50",
    "BANKNIFTY":  "NIFTY BANK",
    "FINNIFTY":   "NIFTY FINANCIAL SERVICES",
    "MIDCPNIFTY": "NIFTY MIDCAP SELECT",
}

_STOP = {"NSE", "INDEX", "THE"}
_ALIAS = {
    "IND": "INDIA", "PVT": "PRIVATE", "SMLCAP": "SMALLCAP", "MIDCP": "MIDCAP",
    "CONSR": "CONSUMER", "DURBL": "DURABLES", "SERV": "SERVICES", "FIN": "FINANCIAL",
    "MFG": "MANUFACTURING", "INFRA": "INFRASTRUCTURE", "COMMODITIES": "COMMODITY",
    "GS": "GSEC", "QLTY": "QUALITY", "MOM": "MOMENTUM", "MKT": "MARKET",
    "FINSEREXBNK": "FINANCIAL SERVICES EX BANK", "EXBNK": "EX BANK",
    "FINNIFTY": "NIFTY FINANCIAL SERVICES", "NIFTY50": "NIFTY 50",
}


def _norm(s: str) -> str:
    """Comparable form: drop punctuation, expand abbreviations, drop filler words."""
    raw = _CANON.get(str(s).strip().upper(), str(s))
    t = re.sub(r"[^A-Za-z0-9 ]", " ", raw.upper())
    t = re.sub(r"\s+", " ", t).strip()
    words = [_ALIAS.get(w, w) for w in t.split()]
    return " ".join(w for w in words if w not in _STOP)


def dhan_indices() -> Dict[str, str]:
    """{normalised name: Dhan trading symbol} for every NSE INDEX instrument."""
    try:
        import pandas as pd, requests
        from io import BytesIO
        df = pd.read_csv(BytesIO(requests.get(
            "https://images.dhan.co/api-data/api-scrip-master.csv", timeout=60).content),
            low_memory=False)
        idx = df[(df["SEM_EXM_EXCH_ID"] == "NSE")
                 & (df["SEM_INSTRUMENT_NAME"].astype(str).str.upper() == "INDEX")]
        out = {}
        for s in idx["SEM_TRADING_SYMBOL"].astype(str).str.strip().unique():
            out.setdefault(_norm(s), s)
        return out
    except Exception as e:
        logger.warning("etf_index_map: Dhan scrip master unavailable: %s", e)
        return {}


def build(cutoff: float = 0.86):
    """Match every selected exposure to its index on both feeds.

    An exposure that does not match is left UNRESOLVED rather than matched loosely:
    a near-miss index is a different sector, and it would flow silently into GM's
    structure read. `cutoff` is deliberately high for that reason.
    """
    import pandas as pd
    try:
        import etf_candidates as ec
        uni = ec.select_universe()
    except Exception as e:
        logger.warning("etf_index_map: universe unavailable: %s", e)
        return None
    if not uni:
        return None

    dh = dhan_indices()
    keys = list(dh)
    rows = []
    for sym, meta in sorted(uni.items()):
        if sym in DROP_SYMBOLS:
            continue
        exp = str(meta.get("underlying", "")).strip()
        exp = EXPOSURE_ALIASES.get(exp, exp)
        n = _norm(exp)
        no_index = n in NO_NSE_INDEX
        dhan_sym = DHAN_OVERRIDES.get(n, "")          # confirmed answers win outright
        if not dhan_sym and not no_index:
            dhan_sym = dh.get(n, "")
        if not dhan_sym and not no_index and keys:
            near = difflib.get_close_matches(n, keys, n=1, cutoff=cutoff)
            if near:
                dhan_sym = dh[near[0]]
        rows.append({
            "exposure":      exp,
            "trade_symbol":  sym,                      # the ETF - always what you buy
            "dhan_index":    dhan_sym,                 # GM structure, via data_provider
            # TV first from the Dhan name, then from the TV-only table: an index can
            # exist on TradingView and not on Dhan (Nifty Chemicals), so S4 may chart
            # what GM cannot compute.
            "tv_index":      TV_OVERRIDES.get(dhan_sym, "") or TV_ONLY.get(exp, ""),
            # Volume is NEVER taken from the index and NEVER borrowed onto it. Named
            # explicitly so the column cannot be mistaken for a routing instruction.
            "volume_source": f"{sym} (stage 2, ETF chart only)",
            "asset_class":   meta.get("asset_class", ""),
            "liquidity_tier": meta.get("liquidity_tier", ""),
            # "no NSE index"  = correct and final; the ETF chart IS the right chart.
            # "unresolved"    = a real gap for review, defaulting to the ETF chart so
            #                   nothing silently charts the wrong instrument.
            "index_status":  ("no NSE index" if no_index
                              else "matched" if dhan_sym
                              else "tv only" if TV_ONLY.get(exp) else "unresolved"),
        })
    df = pd.DataFrame(rows)
    df["chart_mode"] = df.apply(
        lambda r: "index" if (r["dhan_index"] and r["tv_index"]) else "etf_only", axis=1)
    df.to_csv(MAP_CSV, index=False)
    return df


def for_symbol(etf: str) -> Optional[dict]:
    """Map row for one ETF, or None. Never raises."""
    try:
        import pandas as pd
        if not os.path.exists(MAP_CSV):
            return None
        d = pd.read_csv(MAP_CSV)
        r = d[d["trade_symbol"].astype(str).str.upper() == str(etf).strip().upper()]
        return None if r.empty else r.iloc[0].to_dict()
    except Exception as e:
        logger.warning("etf_index_map.for_symbol(%s): %s", etf, e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    d = build()
    if d is None:
        raise SystemExit("universe unavailable")
    print(f"{len(d)} exposures -> {MAP_CSV}")
    print("  chart_mode:", d["chart_mode"].value_counts().to_dict())
    print(f"  Dhan index resolved: {(d['dhan_index'] != '').sum()}/{len(d)}")
    print(f"  TV index resolved  : {(d['tv_index'] != '').sum()}/{len(d)}")
    print("  index_status:", d["index_status"].value_counts().to_dict())
    un = d[d["index_status"] == "unresolved"]
    if len(un):
        print("\n  UNRESOLVED - needs a look (ETF chart used meanwhile):")
        for _, r in un.iterrows():
            print(f"     {r['trade_symbol']:<12} {r['exposure']}")
    ni = d[d["index_status"] == "no NSE index"]
    if len(ni):
        print(f"\n  NO NSE INDEX EXISTS ({len(ni)}) - ETF chart is correct, not a fallback:")
        print("     " + ", ".join(ni["trade_symbol"]))
    nt = d[(d["dhan_index"] != "") & (d["tv_index"] == "")]
    if len(nt):
        print("\n  Dhan index found, TV symbol UNKNOWN (fill in TV_OVERRIDES):")
        for _, r in nt.iterrows():
            print(f"     {r['trade_symbol']:<12} {r['dhan_index']:<22} {r['exposure']}")
