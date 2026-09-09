# -*- coding: utf-8 -*-
"""Sector structure, translated into ETF prices (30-Aug-2026).

THE PROBLEM (Jay): "S4 should mark zones, levels, location on the index, however S4
also marks zones and levels differently on the ETF chart. So I see two different sets."

Both sets are real, and they answer different questions:
    INDEX levels  where the SECTOR has support - the analysis question.
    ETF levels    where the VEHICLE's own buyers and sellers sat - the execution
                  question, and the one that matters for a stop, because the stop is
                  hit by the ETF's prints, not the index's. An ETF with a thin book
                  gaps where its index does not.
So neither can be suppressed. What was missing is the BRIDGE: on the ETF chart there
was no way to see where the sector's structure lands in ETF prices, so you could not
tell whether the ETF zone you were about to lean on was the SAME zone the sector was
leaning on, or a different one.

WHAT THIS DOES
Takes the index's nearest support and resistance - computed with zone_engine's
detect_sr_levels, the same engine S4 draws its own S/R with, so the two are comparable
rather than merely similar - and converts them to ETF prices:

    etf_price = index_level x (etf_close / index_close)

WHY NOT IN PINE. S4 cannot do this itself. Reading the paired index from the ETF chart
needs request.security(sym, ...) with a SIMPLE string, but the paired symbol arrives
from the bundle through fundStr as a SERIES string. GM already holds both series, so
the translation happens here and travels as data.

HOW TO READ THE RESULT - AND HOW NOT TO
A translated level is an APPROXIMATION. The ratio drifts with tracking error and with
the NAV premium/discount (ITIETF has run +2.95%), so this is a reference marker, never
a price to place an order at:
  * levels COINCIDE with an ETF zone  -> real confluence, the sector and the vehicle
                                         are leaning on the same thing;
  * levels DIVERGE                    -> the ETF zone is vehicle microstructure and
                                         deserves less weight.
It must never be drawn as a zone box and never used as a stop; that would give it a
precision it does not have. `ratio` is emitted alongside so the approximation is
visible rather than implied.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_CSV = os.path.join(_DIR, "ETF_Index_Levels.csv")


def build(period: str = "1y") -> Optional["object"]:
    """Compute translated sector levels for every ETF with a paired index."""
    import pandas as pd

    try:
        import etf_index_map as eim
        import zone_engine as ze
        import data_provider as dp
    except Exception as e:
        logger.warning("etf_levels: dependencies unavailable: %s", e)
        return None

    if not os.path.exists(eim.MAP_CSV):
        eim.build()
    try:
        mp = pd.read_csv(eim.MAP_CSV)
    except Exception as e:
        logger.warning("etf_levels: index map unreadable: %s", e)
        return None

    pairs = [(str(r["trade_symbol"]).strip().upper(), str(r.get("dhan_index") or "").strip())
             for _, r in mp.iterrows()
             if str(r.get("dhan_index") or "").strip()
             and str(r.get("chart_mode") or "") == "index"]
    if not pairs:
        logger.warning("etf_levels: no paired exposures")
        return None

    want = sorted({p[1] for p in pairs} | {p[0] for p in pairs})
    try:
        bd = dp.fetch_batch_ohlcv(want, period=period, interval="1d",
                                  use_cache=True, auto_adjust=True)
    except Exception as e:
        logger.warning("etf_levels: batch fetch failed: %s", e)
        return None
    if not bd:
        return None

    def _col(sym):
        """data_provider keys results through clean_symbol, which rewrites index
        aliases (NIFTY -> ^NSEI) and uppercases the rest. Resolving by the raw name
        silently missed the biggest indices when etf_screener did it."""
        if sym in bd:
            return sym
        try:
            c = dp.clean_symbol(sym)
            if c in bd:
                return c
        except Exception:
            pass
        up = {str(k).upper(): k for k in bd}
        return up.get(str(sym).upper())

    rows = []
    for etf, idx in pairs:
        ke, ki = _col(etf), _col(idx)
        if not ke or not ki:
            continue
        de, di = bd[ke], bd[ki]
        if de is None or di is None or de.empty or di.empty or len(di) < 60:
            continue
        try:
            etf_c = float(de["Close"].dropna().iloc[-1])
            idx_c = float(di["Close"].dropna().iloc[-1])
        except Exception:
            continue
        if not (idx_c > 0 and etf_c > 0):
            continue
        ratio = etf_c / idx_c

        try:
            lv = ze.detect_sr_levels(di, "D") or []
        except Exception as e:
            logger.debug("etf_levels: S/R failed for %s: %s", idx, e)
            lv = []
        # Nearest on each side of the index's own last close. MTTWR levels are left in
        # deliberately -- S4 excludes them from its picker because a many-times-tested
        # level is a breakout candidate rather than a ceiling, but as a REFERENCE for
        # "where is the sector leaning" they still say something.
        below = [x["price"] for x in lv if x.get("price") and x["price"] < idx_c]
        above = [x["price"] for x in lv if x.get("price") and x["price"] > idx_c]
        sup = max(below) if below else None
        res = min(above) if above else None
        rows.append({
            "Symbol":      etf,
            "Index":       idx,
            "Index_Close": round(idx_c, 2),
            "ETF_Close":   round(etf_c, 2),
            "Ratio":       round(ratio, 8),
            "Idx_Sup":     round(sup, 2) if sup else None,
            "Idx_Res":     round(res, 2) if res else None,
            # The two numbers S4 shows: sector structure, in ETF prices.
            "Sup_ETF":     round(sup * ratio, 2) if sup else None,
            "Res_ETF":     round(res * ratio, 2) if res else None,
            "N_Levels":    len(lv),
        })

    if not rows:
        logger.warning("etf_levels: nothing computed")
        return None
    df = pd.DataFrame(rows)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT_CSV, df.to_csv(index=False))
    except Exception:
        df.to_csv(OUT_CSV, index=False)
    logger.info("etf_levels: %d ETFs -> %s", len(df), OUT_CSV)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    d = build()
    if d is None:
        raise SystemExit("nothing computed")
    print(f"{len(d)} ETFs -> {OUT_CSV}")
    print(d[["Symbol", "Index", "Index_Close", "ETF_Close",
             "Idx_Sup", "Sup_ETF", "Idx_Res", "Res_ETF"]].head(12).to_string(index=False))
