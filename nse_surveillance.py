#!/usr/bin/env python3
"""NSE surveillance and price bands - which stocks v2 must not hold (Jay, 19-Oct-2026).

Clenow's exit is a Wednesday sale at the open. A stock that NSE has put under heavy surveillance
can lock at a 5 % band or trade only trade-for-trade, so that sale may not happen. Such names are
out of v2's pool: no buy, and a holding is sold at the next rebalance (the same treatment as the
ETF NAV-premium rule). Live only - NSE publishes today's lists, there is no history to backtest.

A stock is OUT when ANY of these holds (NSE's own lists, fetched daily):
  - ASM (long- or short-term) Stage II or higher          api/reportASM
  - any GSM stage                                          api/reportGSM
  - price band 5 % or 2 %                                  sec_list.csv
  - series other than EQ (BE / BZ = trade-for-trade)       sec_list.csv
ASM Stage I is NOT excluded - it only raises margin.

    python nse_surveillance.py            refresh and print today's list for the Nifty 500
    python nse_surveillance.py --check    print the cached list (no network)

If NSE cannot be reached, the last good list (up to MAX_AGE_DAYS old) is used and the result says
so; with no usable list, `excluded()` returns None - "unknown", never "nothing is excluded".
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "nse_surveillance.json")
ASM_API = "https://www.nseindia.com/api/reportASM"
GSM_API = "https://www.nseindia.com/api/reportGSM"
SEC_LIST = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"
MAX_AGE_DAYS = 4                     # a long weekend + one failed night
_STAGE = {"STAGE I": 1, "STAGE II": 2, "STAGE III": 3, "STAGE IV": 4}


def _stage(txt: str) -> int:
    t = str(txt or "").upper().strip()
    return _STAGE.get(t, 0)


def classify(asm: list, gsm: list, sec_list_rows: list) -> dict:
    """{symbol: reason} for every stock that is OUT under the rules above. Pure - no network."""
    out = {}
    for x in asm:
        st = _stage(x.get("asmSurvIndicator"))
        if st >= 2:
            out[str(x.get("symbol", "")).upper()] = "ASM Stage %s" % ("I" * st if st < 4 else "IV")
    for x in gsm:
        s = str(x.get("symbol", "")).upper()
        if s:
            out[s] = "GSM %s" % (x.get("gsmStage") or "")
    for r in sec_list_rows:
        s = str(r.get("Symbol", "")).strip().upper()
        band = str(r.get("Band", "")).strip()
        ser = str(r.get("Series", "")).strip().upper()
        why = []
        if band in ("2", "5"):
            why.append("%s%% price band" % band)
        if ser and ser != "EQ":
            why.append("series %s (trade-for-trade)" % ser)
        if why:
            out[s] = "; ".join(([out[s]] if s in out else []) + why)
    return out


def fetch() -> dict:
    """Today's lists from NSE -> {"fetched", "out": {symbol: reason}, "counts"}. Raises on failure."""
    import pandas as pd
    import nse_options as no                   # the NSE cookie session already lives there
    s = no._get_session()
    a = s.get(ASM_API, headers={"Referer": "https://www.nseindia.com/reports/asm"}, timeout=30)
    a.raise_for_status()
    aj = a.json()
    asm = (aj.get("longterm", {}).get("data") or []) + (aj.get("shortterm", {}).get("data") or [])
    g = s.get(GSM_API, headers={"Referer": "https://www.nseindia.com/reports/gsm"}, timeout=30)
    g.raise_for_status()
    gsm = g.json() or []
    r = s.get(SEC_LIST, timeout=30)
    r.raise_for_status()
    sl = pd.read_csv(io.StringIO(r.text))
    if len(sl) < 1000 or not len(asm):
        raise ValueError("NSE lists look truncated (sec_list %d rows, ASM %d)" % (len(sl), len(asm)))
    out = classify(asm, gsm, sl.to_dict("records"))
    return {"fetched": dt.datetime.now().isoformat(timespec="seconds"), "out": out,
            "counts": {"asm": len(asm), "gsm": len(gsm), "sec_list": len(sl)}}


def refresh() -> dict:
    data = fetch()
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(CACHE, json.dumps(data, indent=1))
    except Exception:
        json.dump(data, open(CACHE, "w", encoding="utf-8"), indent=1)
    return data


def load() -> dict | None:
    try:
        return json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        return None


def excluded(refresh_first: bool = False) -> tuple:
    """({symbol: reason} or None, note). Uses the cache when it is fresh enough; refreshes first
    when asked (the nightly run). None = no usable list (the caller says 'unknown')."""
    note = ""
    if refresh_first:
        try:
            data = refresh()
            return data["out"], "NSE surveillance lists of %s" % data["fetched"][:10]
        except Exception as e:
            note = "NSE unreachable (%s); " % str(e)[:80]
    data = load()
    if not data:
        return None, note + "no surveillance list on disk"
    age = (dt.datetime.now() - dt.datetime.fromisoformat(data["fetched"])).days
    if age > MAX_AGE_DAYS:
        return None, note + "surveillance list is %d days old - not used" % age
    return data["out"], note + "NSE surveillance lists of %s" % data["fetched"][:10]


def main() -> int:
    uni = set()
    try:
        uni = {x.replace(".NS", "") for x in json.load(open(os.path.join(HERE, "nifty500_symbols.json")))}
    except Exception:
        pass
    out, note = excluded(refresh_first="--check" not in sys.argv)
    print(note)
    if out is None:
        return 2
    mine = {s: w for s, w in out.items() if s in uni}
    print("%d stocks out market-wide; %d in the Nifty 500:" % (len(out), len(mine)))
    for s, w in sorted(mine.items()):
        print("  %-12s %s" % (s, w))
    return 0


if __name__ == "__main__":
    sys.exit(main())
