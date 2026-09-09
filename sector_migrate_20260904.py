# -*- coding: utf-8 -*-
"""One-off migration of sectors.db — 4 Sep 2026.

Acts on the Gemini mapping audit AFTER verifying every concrete claim against the
Pine sources (all confirmed: the ARE_M conflict, four redundant duplicates, the
LMSYMBOL placeholder, the typos, TITAN/TRENT on FMCG, zero ETF entries, 676 rows).

WHY THE DATABASE AND NOT THE PINE FILES. The same 676-row table is copy-pasted into
v67 and the Unified Ecosystem, S4Core holds a third copy, and sectors.db's `source`
column reads `pine_v1.7` — the database was seeded FROM the Pine table and inherited
its errors. gen_sector_map.py already exists and says "Regenerate, never hand-edit".
So the fix is: correct the DB once, then emit all three.

DECISIONS TAKEN HERE, and why:

  ARE&M    -> NSE:CNXAUTO. Amara Raja Energy & Mobility is auto components. The
             CNXINFRA row was the stale half of a separator-variant pair.
  LT       -> NSE:CNXINFRA, not BSE:CG. BSE:CG has NO benchmark ticker at all and
             falls back to CNXINFRA anyway, so this is the same measurement stated
             honestly instead of through a silent fallback.
  RENAMES  -> the `alias` table, never DELETE. TATAMOTORS, ZOMATO, LTIM and the rest
             still appear in watchlists, the journal and every backtest artifact;
             deleting them turns historical lookups into silent CNX500 fallbacks.
  TATAMOTORS -> LEFT ALONE. TMPV/TMCV is a demerger producing two instruments, not a
             misclassification. Which one is traded is Jay's decision.
  JUNK     -> deleted only where the symbol cannot exist (a template placeholder, an
             unlisted subsidiary, a delisted penny stock).

CANONICAL FORM: the DB keeps the NSE symbol (M&M), and the Pine emitter renders the
TRADINGVIEW form (M_M) because that is what syminfo.ticker returns. Getting this
backwards is a live bug today — S4Core carries "M&M", which never matches.

    python sector_migrate_20260904.py            # dry run
    python sector_migrate_20260904.py --apply
"""
from __future__ import annotations
import argparse
import re
import sqlite3
import sys

DB = "sectors.db"

# --- 1. separator-variant collapses; value = the sector that survives ----------
COLLAPSE = {
    "ARE&M":     "NSE:CNXAUTO",      # conflict: CNXINFRA was the stale half
    "LT":        "NSE:CNXINFRA",     # conflict: BSE:CG has no benchmark
    "GVT&D":     "NSE:CNXINFRA",
    "J&KBANK":   "NSE:BANKNIFTY",
    "M&M":       "NSE:CNXAUTO",
    "M&MFIN":    "NSE:CNXFINANCE",
    "NAM-INDIA": "NSE:CNXFINANCE",
}

# --- 2. renames: old -> new. The OLD symbol becomes an alias, never a deletion --
RENAME = {
    "AMARAJABAT": "ARE&M",      "GMRINFRA":  "GMRAIRPORT", "ZOMATO":  "ETERNAL",
    "LTIM":       "LTM",        "MINDTREE":  "LTM",        "GUJGASLTD": "GUJENERGY",
    "GSPL":       "GUJENERGY",  "PEL":       "PIRAMALFIN", "IIFLSEC": "IIFLCAPS",
    "PUNJABALK":  "PRIMO",      "PRICOL":    "PRICOLLTD",  "GANESHHOUC": "GANESHHOU",
    "L_TFH":      "LTF",        "IDFC":      "IDFCFIRSTB",
    # typos and unofficial abbreviations
    "SAREHGAMA":  "SAREGAMA",   "OLAEC":     "OLAELEC",    "DCXIND":  "DCXINDIA",
    "CHOLAHLD":   "CHOLAHLDNG", "GARDENREACH": "GRSE",     "LAXMACH": "LAXMIMACH",
    "OBERREALTY": "OBEROIRLTY", "ADANITOTAL": "ATGL",      "ADANIWILL": "AWL",
    "AEGISCHEM":  "AEGISLOG",   "BIRLASOFT": "BSOFT",
}

# --- 3. symbols that cannot exist on NSE/BSE ---------------------------------
DELETE = ["LMSYMBOL", "ACKO", "ASKASIAN", "SBIGLI", "KOTAKAMC",
          "FALCONTYRE", "FERV", "SAFEWELL"]

# --- 4. reclassifications ----------------------------------------------------
# Consumer discretionary / durables wrongly on FMCG (staples) or BSE:CG (heavy industry).
RECLASS = {
    # discretionary & retail -> Nifty India Consumption
    "TITAN": "NSE:CNXCONSUM", "TRENT": "NSE:CNXCONSUM", "KALYANKJIL": "NSE:CNXCONSUM",
    "BATAINDIA": "NSE:CNXCONSUM", "RELAXO": "NSE:CNXCONSUM", "CAMPUS": "NSE:CNXCONSUM",
    "VIPIND": "NSE:CNXCONSUM", "VAIBHAVGBL": "NSE:CNXCONSUM", "SFL": "NSE:CNXCONSUM",
    "JSWDULUX": "NSE:CNXCONSUM", "ASIANPAINT": "NSE:CNXCONSUM",
    # consumer electricals & appliances -> Consumption, not capital goods
    "VOLTAS": "NSE:CNXCONSUM", "BLUESTARCO": "NSE:CNXCONSUM", "HAVELLS": "NSE:CNXCONSUM",
    "CROMPTON": "NSE:CNXCONSUM", "WHIRLPOOL": "NSE:CNXCONSUM", "BAJAJELEC": "NSE:CNXCONSUM",
    "AMBER": "NSE:CNXCONSUM", "DIXON": "NSE:CNXCONSUM", "PGEL": "NSE:CNXCONSUM",
    # sector corrections
    "PIDILITIND": "NSE:CNXCOMMODITIES",   # specialty chemicals, not infra
    "ACUTAAS": "NSE:CNXPHARMA",           # healthcare, not commodities
    "IKS": "NSE:CNXIT", "SAGILITY": "NSE:CNXIT",   # US healthcare IT/BPO
    "RKFORGE": "NSE:CNXAUTO",             # automotive forgings
    "CENTURYTEX": "NSE:CNXREALTY",        # Birla Estates
    # PSU banks: Bank Nifty is private-bank weighted, so RS against it is misleading
    "BANKINDIA": "NSE:CNXPSUBANK", "CENTRALBK": "NSE:CNXPSUBANK",
    "INDIANB": "NSE:CNXPSUBANK", "IOB": "NSE:CNXPSUBANK",
    "MAHABANK": "NSE:CNXPSUBANK", "UCOBANK": "NSE:CNXPSUBANK",
}

# --- 5. sector_meta benchmark corrections (measured today, not guessed) -------
# NIFTY_DEFENCE.NS is not a valid symbol anywhere - eight candidates tested, all
# empty. ^CNXPSUBANK resolves via yfinance with THIRTY-TWO bars, which cannot carry
# a 52-week Mansfield RS. Dhan's scrip master has proper index series for both.
META = {
    "NSE:NIFTY_DEFENCE": "NIFTY IND DEFENCE",   # 450 bars via Dhan
    "NSE:CNXPSUBANK":    "NIFTY PSU BANK",      # 1240 bars vs 32
}


def norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def main(apply: bool) -> int:
    c = sqlite3.connect(DB)
    cur = c.cursor()
    have = {r[0] for r in cur.execute("SELECT symbol FROM stock_sector")}
    plan: list[tuple[str, str, str]] = []

    for keep, sector in COLLAPSE.items():
        variants = [s for s in have if norm(s) == norm(keep)]
        for v in variants:
            if v != keep:
                plan.append(("DROP-VARIANT", v, f"collapses into {keep}"))
        plan.append(("SET", keep, sector))

    for old, new in RENAME.items():
        if old in have:
            plan.append(("ALIAS", old, f"-> {new}"))
            if new not in have and new not in COLLAPSE:
                plan.append(("CARRY", new, f"inherits {old}'s sector"))

    for d in DELETE:
        if d in have:
            plan.append(("DELETE", d, "cannot exist on NSE/BSE"))

    for sym, sector in RECLASS.items():
        cur.execute("SELECT sector_index FROM stock_sector WHERE symbol=?", (sym,))
        row = cur.fetchone()
        if row and row[0] != sector:
            plan.append(("RECLASS", sym, f"{row[0]} -> {sector}"))
        elif not row:
            plan.append(("SKIP", sym, "not in DB"))

    for si, yf in META.items():
        cur.execute("SELECT yf_ticker FROM sector_meta WHERE sector_index=?", (si,))
        row = cur.fetchone()
        if row and row[0] != yf:
            plan.append(("META", si, f"{row[0]} -> {yf}"))

    by = {}
    for kind, sym, note in plan:
        by.setdefault(kind, []).append((sym, note))
    for kind in ("DROP-VARIANT", "SET", "ALIAS", "CARRY", "DELETE", "RECLASS", "META", "SKIP"):
        items = by.get(kind, [])
        print(f"\n{kind}  ({len(items)})")
        for sym, note in items:
            print(f"   {sym:<14} {note}")

    if not apply:
        print("\nDRY RUN — nothing written. Re-run with --apply.")
        return 0

    # stock_sector.sector_name is NOT NULL, and it is the human label that pairs with
    # sector_index. Take it from sector_meta so the two can never disagree.
    names = {r[0]: (r[1] or r[0]) for r in
             cur.execute("SELECT sector_index, display_name FROM sector_meta")}

    for kind, sym, note in plan:
        if kind == "DROP-VARIANT":
            cur.execute("DELETE FROM stock_sector WHERE symbol=?", (sym,))
        elif kind == "SET":
            cur.execute(
                "INSERT INTO stock_sector(symbol,sector_index,sector_name,source,confidence,updated_at) "
                "VALUES(?,?,?,'migrate_20260904','curated',datetime('now')) "
                "ON CONFLICT(symbol) DO UPDATE SET sector_index=excluded.sector_index,"
                "sector_name=excluded.sector_name,source=excluded.source,updated_at=excluded.updated_at",
                (sym, note, names.get(note, note)))
        elif kind == "ALIAS":
            cur.execute("INSERT OR REPLACE INTO alias(alias_symbol,canonical_symbol) VALUES(?,?)",
                        (sym, note.split("-> ")[1]))
        elif kind == "CARRY":
            old = [k for k, v in RENAME.items() if v == sym][0]
            cur.execute("SELECT sector_index FROM stock_sector WHERE symbol=?", (old,))
            r = cur.fetchone()
            if r:
                cur.execute(
                    "INSERT INTO stock_sector(symbol,sector_index,sector_name,source,confidence,updated_at) "
                    "VALUES(?,?,?,'migrate_20260904','curated',datetime('now')) "
                    "ON CONFLICT(symbol) DO UPDATE SET sector_index=excluded.sector_index,"
                    "sector_name=excluded.sector_name",
                    (sym, r[0], names.get(r[0], r[0])))
        elif kind == "DELETE":
            cur.execute("DELETE FROM stock_sector WHERE symbol=?", (sym,))
        elif kind == "RECLASS":
            _si = note.split("-> ")[1]
            cur.execute("UPDATE stock_sector SET sector_index=?, sector_name=?,"
                        "source='migrate_20260904', updated_at=datetime('now') "
                        "WHERE symbol=?", (_si, names.get(_si, _si), sym))
        elif kind == "META":
            cur.execute("UPDATE sector_meta SET yf_ticker=? WHERE sector_index=?",
                        (note.split("-> ")[1], sym))
    c.commit()
    n = cur.execute("SELECT COUNT(*) FROM stock_sector").fetchone()[0]
    a = cur.execute("SELECT COUNT(*) FROM alias").fetchone()[0]
    print(f"\nAPPLIED. stock_sector={n} rows, alias={a} rows.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(main(ap.parse_args().apply))
