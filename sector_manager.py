#!/usr/bin/env python3
"""
sector_manager.py — Unified Sector DB Manager (v2.0, SQLite-backed)

Single source of truth for stock→sector mappings shared between the Pine
Dashboard family and the Python pipeline (Web Commander v4.0).

Schema (sectors.db):
  stock_sector(symbol PK, sector_index, sector_name, source, confidence,
               updated_at, notes)
  sector_meta (sector_index PK, display_name, yf_ticker, fallback_sector_index,
               color_hex, is_broad_market)
  alias       (alias_symbol PK, canonical_symbol)

CLI:
  python sector_manager.py                       # init + import-pine v67 + import-json + audit
  python sector_manager.py init                  # create schema + seed sector_meta
  python sector_manager.py import-pine <file>    # ingest <DB_LOOKUP_START>...<DB_LOOKUP_END> block
  python sector_manager.py import-json [file]    # merge sector_db.json (default: ./sector_db.json)
  python sector_manager.py export-pine <file>    # rewrite the DB_LOOKUP block in <file> in place
  python sector_manager.py refresh-yf [--symbols X,Y]   # update yfinance-sourced rows
  python sector_manager.py lookup <SYMBOL>       # show sector for a symbol
  python sector_manager.py audit                 # stats: counts, sources, missing F&O
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import closing
from typing import Iterable, Optional

# ─── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(DATA_DIR, "sectors.db")
JSON_LEGACY_PATH = os.path.join(DATA_DIR, "sector_db.json")

# Default Pine source — the curated v67 dashboard
DEFAULT_PINE_SOURCE = os.path.join(
    DATA_DIR, "Weinstein and Swing Pro Dashboard v67.3.pine"
)

# ─── Sector metadata seed (NSE indices + yfinance tickers + fallbacks) ────────
# yf_ticker: None means yfinance has no clean equivalent — consumers fall back to
# the fallback_sector_index. is_broad_market=1 marks the universe-level sector.
SECTOR_META_SEED = [
    # sector_index,                display_name,         yf_ticker,        fallback,            color,     broad
    ("NSE:CNX500",                  "Nifty 500",          "^CRSLDX",        None,                "#64748b", 1),
    ("NSE:BANKNIFTY",               "Bank Nifty",         "^NSEBANK",       None,                "#3b82f6", 0),
    ("NSE:CNXFINANCE",              "Financial Services", "^CNXFIN",        "NSE:BANKNIFTY",     "#2563eb", 0),
    ("NSE:CNXIT",                   "Nifty IT",           "^CNXIT",         None,                "#a855f7", 0),
    ("NSE:CNXPHARMA",               "Pharma",             "^CNXPHARMA",     None,                "#22c55e", 0),
    ("NSE:CNXAUTO",                 "Auto",               "^CNXAUTO",       None,                "#f97316", 0),
    ("NSE:CNXFMCG",                 "FMCG",               "^CNXFMCG",       None,                "#ec4899", 0),
    ("NSE:CNXMETAL",                "Metal",              "^CNXMETAL",      None,                "#71717a", 0),
    ("NSE:CNXENERGY",               "Energy",             "^CNXENERGY",     None,                "#eab308", 0),
    ("NSE:CNXREALTY",               "Realty",             "^CNXREALTY",     None,                "#84cc16", 0),
    ("NSE:CNXINFRA",                "Infra",              "^CNXINFRA",      None,                "#0ea5e9", 0),
    ("NSE:CNXMEDIA",                "Media",              "^CNXMEDIA",      None,                "#f43f5e", 0),
    ("NSE:CNXSERVICE",              "Services",           "^CNXSERVICE",    "NSE:CNX500",        "#14b8a6", 0),
    ("NSE:NIFTY_OIL_AND_GAS",       "Oil & Gas",          "^CNXENERGY",     "NSE:CNXENERGY",     "#facc15", 0),
    # BSE Capital Goods has no clean yfinance NSE equivalent — fall back to Infra.
    ("BSE:CG",                      "Capital Goods (BSE)", None,            "NSE:CNXINFRA",      "#6366f1", 0),
]

# Yahoo-sector → NSE-index mapping (used by refresh-yf for new symbols)
YF_SECTOR_FALLBACK = {
    "Financial Services":      "NSE:CNXFINANCE",
    "Technology":              "NSE:CNXIT",
    "Energy":                  "NSE:CNXENERGY",
    "Basic Materials":         "NSE:CNXMETAL",
    "Consumer Cyclical":       "NSE:CNXAUTO",
    "Consumer Defensive":      "NSE:CNXFMCG",
    "Healthcare":              "NSE:CNXPHARMA",
    "Utilities":               "NSE:CNXINFRA",
    "Real Estate":             "NSE:CNXREALTY",
    "Industrials":             "NSE:CNXINFRA",
    "Communication Services":  "NSE:CNXMEDIA",
}

# Aliases — Pine encodes "M&M" as "M_M" because Pine identifiers can't contain `&`.
# Canonical form lives on the trading symbol (NSE uses M&M).
DEFAULT_ALIASES = [
    ("M_M",     "M&M"),
    ("M_MFIN",  "M&MFIN"),
]

# ─── Connection helper ────────────────────────────────────────────────────────
def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ─── Schema ───────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stock_sector (
    symbol         TEXT PRIMARY KEY,
    sector_index   TEXT NOT NULL,
    sector_name    TEXT NOT NULL,
    source         TEXT NOT NULL,
    confidence     TEXT NOT NULL DEFAULT 'auto',
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_stock_sector_index ON stock_sector(sector_index);
CREATE INDEX IF NOT EXISTS idx_stock_sector_source ON stock_sector(source);

CREATE TABLE IF NOT EXISTS sector_meta (
    sector_index           TEXT PRIMARY KEY,
    display_name           TEXT NOT NULL,
    yf_ticker              TEXT,
    fallback_sector_index  TEXT,
    color_hex              TEXT,
    is_broad_market        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alias (
    alias_symbol      TEXT PRIMARY KEY,
    canonical_symbol  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alias_canonical ON alias(canonical_symbol);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """Create schema and seed sector_meta + default aliases (idempotent)."""
    with closing(get_conn(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
        # Seed sector_meta
        conn.executemany(
            "INSERT OR IGNORE INTO sector_meta "
            "(sector_index, display_name, yf_ticker, fallback_sector_index, color_hex, is_broad_market) "
            "VALUES (?,?,?,?,?,?)",
            SECTOR_META_SEED,
        )
        # Seed aliases
        conn.executemany(
            "INSERT OR IGNORE INTO alias (alias_symbol, canonical_symbol) VALUES (?,?)",
            DEFAULT_ALIASES,
        )
        conn.commit()
    print(f"[init] Schema ready at {db_path}")


# ─── Sector display-name helper ───────────────────────────────────────────────
def _display_name_for(sector_index: str, conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT display_name FROM sector_meta WHERE sector_index = ?",
        (sector_index,),
    ).fetchone()
    return row["display_name"] if row else sector_index.split(":")[-1]


# ─── Symbol normalization ─────────────────────────────────────────────────────
_DHAN_SUFFIXES = ("-EQ", "-BE", "-SM", "-ST", "-BZ")
# Pine encodes M&M as M_M etc. The reverse is done via alias table.
def normalize_symbol(raw: str) -> str:
    """Strip exchange prefix, .NS suffix, Dhan series suffixes. Upper-cases.

    Output is the *canonical* form (matches NSE trading symbol).
    Does NOT consult the alias table — caller resolves aliases after.
    """
    if not raw:
        return ""
    s = str(raw).strip().upper()
    if s.startswith("NSE:"):
        s = s[4:]
    elif s.startswith("BSE:"):
        s = s[4:]
    if s.endswith(".NS"):
        s = s[:-3]
    elif s.endswith(".BO"):
        s = s[:-3]
    for suf in _DHAN_SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s


# ─── Pine block import ────────────────────────────────────────────────────────
_PINE_ROW_RE = re.compile(r'^\s*"([A-Z0-9_\-]+)"\s*=>\s*"([^"]+)"\s*$')
_PINE_START  = "<DB_LOOKUP_START>"
_PINE_END    = "<DB_LOOKUP_END>"


def parse_pine_block(pine_path: str) -> list[tuple[str, str]]:
    """Extract (pine_symbol, sector_index) pairs from a Pine file's DB_LOOKUP block."""
    if not os.path.exists(pine_path):
        raise FileNotFoundError(pine_path)
    with open(pine_path, "r", encoding="utf-8") as f:
        text = f.read()
    if _PINE_START not in text or _PINE_END not in text:
        raise ValueError(
            f"{os.path.basename(pine_path)} has no <DB_LOOKUP_START>...<DB_LOOKUP_END> block"
        )
    block = text.split(_PINE_START, 1)[1].split(_PINE_END, 1)[0]
    pairs = []
    for line in block.splitlines():
        m = _PINE_ROW_RE.match(line)
        if m:
            pairs.append((m.group(1), m.group(2)))
    return pairs


def import_pine(pine_path: str, db_path: str = DB_PATH,
                 source_label: Optional[str] = None) -> int:
    """Import the Pine sector block. Pine wins over auto sources but defers to manual."""
    init_db(db_path)
    pairs = parse_pine_block(pine_path)
    if not pairs:
        print(f"[import-pine] No mappings parsed from {pine_path}")
        return 0
    if source_label is None:
        m = re.search(r"v(\d+\.?\d*)", os.path.basename(pine_path), re.IGNORECASE)
        source_label = f"pine_v{m.group(1)}" if m else "pine"

    inserted = updated = skipped = 0
    with closing(get_conn(db_path)) as conn:
        meta_keys = {r["sector_index"] for r in
                     conn.execute("SELECT sector_index FROM sector_meta").fetchall()}
        for pine_sym, sector_index in pairs:
            # Resolve alias: prefer canonical NSE form for storage
            alias_row = conn.execute(
                "SELECT canonical_symbol FROM alias WHERE alias_symbol = ?",
                (pine_sym,),
            ).fetchone()
            symbol = alias_row["canonical_symbol"] if alias_row else pine_sym
            if sector_index not in meta_keys:
                # Unknown sector — record it but flag low confidence
                print(f"[import-pine] WARN unknown sector_index '{sector_index}' "
                      f"for {symbol}; storing anyway")
            sector_name = _display_name_for(sector_index, conn)

            existing = conn.execute(
                "SELECT source, confidence FROM stock_sector WHERE symbol = ?",
                (symbol,),
            ).fetchone()
            if existing and existing["source"] == "manual":
                skipped += 1
                continue
            if existing:
                conn.execute(
                    "UPDATE stock_sector SET sector_index=?, sector_name=?, "
                    "source=?, confidence='curated', updated_at=CURRENT_TIMESTAMP "
                    "WHERE symbol=?",
                    (sector_index, sector_name, source_label, symbol),
                )
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO stock_sector "
                    "(symbol, sector_index, sector_name, source, confidence) "
                    "VALUES (?,?,?,?, 'curated')",
                    (symbol, sector_index, sector_name, source_label),
                )
                inserted += 1
        conn.commit()
    print(f"[import-pine] {os.path.basename(pine_path)} -> "
          f"+{inserted} new, ~{updated} updated, -{skipped} kept-manual")
    return inserted + updated


# ─── JSON legacy import ───────────────────────────────────────────────────────
def import_json(json_path: str = JSON_LEGACY_PATH, db_path: str = DB_PATH) -> int:
    """Merge the legacy sector_db.json. Only inserts symbols not already in DB."""
    init_db(db_path)
    if not os.path.exists(json_path):
        print(f"[import-json] {json_path} not found — skipping")
        return 0
    with open(json_path, "r", encoding="utf-8") as f:
        legacy = json.load(f)
    inserted = skipped = 0
    with closing(get_conn(db_path)) as conn:
        for raw_key, sector_index in legacy.items():
            symbol = normalize_symbol(raw_key)
            if not symbol:
                continue
            existing = conn.execute(
                "SELECT 1 FROM stock_sector WHERE symbol = ?", (symbol,)
            ).fetchone()
            if existing:
                skipped += 1
                continue
            sector_name = _display_name_for(sector_index, conn)
            conn.execute(
                "INSERT INTO stock_sector "
                "(symbol, sector_index, sector_name, source, confidence) "
                "VALUES (?,?,?, 'json_seed', 'auto')",
                (symbol, sector_index, sector_name),
            )
            inserted += 1
        conn.commit()
    print(f"[import-json] +{inserted} merged from JSON, -{skipped} already in DB")
    return inserted


# ─── Pine block export ────────────────────────────────────────────────────────
def _build_pine_block(rows: list[sqlite3.Row]) -> str:
    """Generate the <DB_LOOKUP_START>...<DB_LOOKUP_END> Pine snippet.

    Reverse-applies M&M → M_M etc. for Pine syntax compatibility.
    """
    lines = [
        "// <DB_LOOKUP_START>",
        "// This function is AUTO-GENERATED by sector_manager.py",
        "f_db_sector_lookup(string t) =>",
        "    string s = \"\"",
        "    // Ticker format in text is usually just the name (e.g. RELIANCE)",
        "    // We match against the DB keys which are NSE:RELIANCE",
        "    s := switch t",
    ]
    for r in rows:
        sym = r["symbol"]
        # Reverse-encode for Pine: replace `&` with `_` (Pine identifiers).
        pine_sym = sym.replace("&", "_")
        lines.append(f'        "{pine_sym}" => "{r["sector_index"]}"')
    lines.append('        => ""')
    lines.append("    s")
    lines.append("// <DB_LOOKUP_END>")
    return "\n".join(lines)


def export_pine(pine_path: str, db_path: str = DB_PATH) -> int:
    """Replace the DB_LOOKUP block in <pine_path> with current DB contents."""
    if not os.path.exists(pine_path):
        raise FileNotFoundError(pine_path)
    with open(pine_path, "r", encoding="utf-8") as f:
        text = f.read()
    if _PINE_START not in text or _PINE_END not in text:
        raise ValueError(f"{pine_path} has no DB_LOOKUP block to replace")

    with closing(get_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT symbol, sector_index FROM stock_sector ORDER BY symbol"
        ).fetchall()

    new_block = _build_pine_block(rows)
    before, _, rest = text.partition(_PINE_START)
    _, _, after = rest.partition(_PINE_END)
    new_text = f"{before}{new_block}{after}"

    backup = pine_path + ".bak"
    with open(backup, "w", encoding="utf-8") as f:
        f.write(text)
    with open(pine_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"[export-pine] Wrote {len(rows)} rows to {pine_path} (backup: {backup})")
    return len(rows)


# ─── yfinance refresh ─────────────────────────────────────────────────────────
def refresh_yf(symbols: Optional[Iterable[str]] = None,
               db_path: str = DB_PATH, sleep_s: float = 0.5) -> int:
    """Update sector_index for rows where source='yfinance' or 'json_seed'.

    Never overwrites curated (source LIKE 'pine_%') or manual rows.
    If `symbols` is None, refreshes all auto/json_seed rows.
    """
    init_db(db_path)
    try:
        import yfinance as yf
    except ImportError:
        print("[refresh-yf] yfinance not installed; skipping")
        return 0

    with closing(get_conn(db_path)) as conn:
        if symbols:
            target = [normalize_symbol(s) for s in symbols if s]
            target = [s for s in target if s]
        else:
            rows = conn.execute(
                "SELECT symbol FROM stock_sector "
                "WHERE source IN ('yfinance', 'json_seed', 'manual_pending')"
            ).fetchall()
            target = [r["symbol"] for r in rows]
        if not target:
            print("[refresh-yf] No symbols to refresh")
            return 0
        meta_keys = {r["sector_index"] for r in
                     conn.execute("SELECT sector_index FROM sector_meta").fetchall()}

        updated = 0
        for sym in target:
            yf_sym = f"{sym}.NS"
            try:
                info = yf.Ticker(yf_sym).info
                yf_sector = info.get("sector", "") if info else ""
            except Exception as e:
                print(f"[refresh-yf]   {sym}: error {e}")
                time.sleep(sleep_s)
                continue
            sector_index = YF_SECTOR_FALLBACK.get(yf_sector, "NSE:CNX500")
            if sector_index not in meta_keys:
                sector_index = "NSE:CNX500"
            sector_name = _display_name_for(sector_index, conn)
            existing = conn.execute(
                "SELECT source FROM stock_sector WHERE symbol = ?", (sym,)
            ).fetchone()
            if existing and existing["source"].startswith("pine_"):
                continue  # never overwrite curated
            if existing and existing["source"] == "manual":
                continue
            if existing:
                conn.execute(
                    "UPDATE stock_sector SET sector_index=?, sector_name=?, "
                    "source='yfinance', confidence='auto', "
                    "updated_at=CURRENT_TIMESTAMP, notes=? WHERE symbol=?",
                    (sector_index, sector_name, f"yf:{yf_sector or 'unknown'}", sym),
                )
            else:
                conn.execute(
                    "INSERT INTO stock_sector "
                    "(symbol, sector_index, sector_name, source, confidence, notes) "
                    "VALUES (?,?,?, 'yfinance', 'auto', ?)",
                    (sym, sector_index, sector_name, f"yf:{yf_sector or 'unknown'}"),
                )
            updated += 1
            if updated % 10 == 0:
                conn.commit()
            time.sleep(sleep_s)
        conn.commit()
    print(f"[refresh-yf] Updated {updated} rows")
    return updated


# ─── Lookup ───────────────────────────────────────────────────────────────────
def lookup(symbol: str, db_path: str = DB_PATH) -> Optional[dict]:
    """Return the sector record for a symbol (post alias + normalization)."""
    s = normalize_symbol(symbol)
    if not s:
        return None
    with closing(get_conn(db_path)) as conn:
        # First try canonical
        row = conn.execute(
            "SELECT * FROM stock_sector WHERE symbol = ?", (s,)
        ).fetchone()
        if not row:
            # Then try alias resolution (input may itself be an alias)
            ar = conn.execute(
                "SELECT canonical_symbol FROM alias WHERE alias_symbol = ?", (s,)
            ).fetchone()
            if ar:
                row = conn.execute(
                    "SELECT * FROM stock_sector WHERE symbol = ?",
                    (ar["canonical_symbol"],),
                ).fetchone()
        if not row:
            return None
        meta = conn.execute(
            "SELECT * FROM sector_meta WHERE sector_index = ?",
            (row["sector_index"],),
        ).fetchone()
    out = dict(row)
    if meta:
        out["display_name"]          = meta["display_name"]
        out["yf_ticker"]              = meta["yf_ticker"]
        out["fallback_sector_index"] = meta["fallback_sector_index"]
    return out


# ─── Audit ────────────────────────────────────────────────────────────────────
def audit(db_path: str = DB_PATH) -> dict:
    """Print and return DB statistics."""
    if not os.path.exists(db_path):
        print(f"[audit] No DB at {db_path} — run init first")
        return {}
    with closing(get_conn(db_path)) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM stock_sector").fetchone()["c"]
        by_source = {r["source"]: r["c"] for r in
                     conn.execute("SELECT source, COUNT(*) AS c "
                                  "FROM stock_sector GROUP BY source").fetchall()}
        by_sector = {r["sector_index"]: r["c"] for r in
                     conn.execute("SELECT sector_index, COUNT(*) AS c "
                                  "FROM stock_sector GROUP BY sector_index "
                                  "ORDER BY c DESC").fetchall()}
        meta_count = conn.execute("SELECT COUNT(*) AS c FROM sector_meta").fetchone()["c"]
        alias_count = conn.execute("SELECT COUNT(*) AS c FROM alias").fetchone()["c"]
        last_update = conn.execute(
            "SELECT MAX(updated_at) AS u FROM stock_sector"
        ).fetchone()["u"]

    print(f"[audit] sectors.db @ {db_path}")
    print(f"  Total symbols: {total}")
    print(f"  Sector-meta rows: {meta_count}")
    print(f"  Aliases: {alias_count}")
    print(f"  Last update: {last_update}")
    print(f"  By source:")
    for src, c in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {src:<14} {c}")
    print(f"  Top 10 sectors:")
    for idx, (sec, c) in enumerate(by_sector.items()):
        if idx >= 10:
            break
        print(f"    {sec:<28} {c}")
    return {
        "total": total, "by_source": by_source, "by_sector": by_sector,
        "meta_count": meta_count, "alias_count": alias_count,
        "last_update": last_update,
    }


# ─── SYNC FROM OFFICIAL NSE ARCHIVES ──────────────────────────────────────────
def sync_nse(verbose: bool = True) -> dict:
    """
    Downloads official constituent lists from NSE Archives and syncs them into sectors.db
    and nse_indices_constituents.json.
    """
    import urllib.request, csv, io
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    sector_csv_map = {
        "NSE:BANKNIFTY":              ("Nifty Bank", "ind_niftybanklist.csv"),
        "NSE:CNXAUTO":                ("Auto", "ind_niftyautolist.csv"),
        "NSE:CNXFINANCE":             ("Financial Services", "ind_niftyfinancialservices25_50list.csv"),
        "NSE:CNXFMCG":                ("FMCG", "ind_niftyfmcglist.csv"),
        "NSE:CNXIT":                  ("Nifty IT", "ind_niftyitlist.csv"),
        "NSE:CNXMEDIA":               ("Media", "ind_niftymedialist.csv"),
        "NSE:CNXMETAL":               ("Metal", "ind_niftymetallist.csv"),
        "NSE:CNXPHARMA":              ("Pharma", "ind_niftypharmalist.csv"),
        "NSE:CNXPSUBANK":             ("PSU Bank", "ind_niftypsubanklist.csv"),
        "NSE:CNXREALTY":              ("Realty", "ind_niftyrealtylist.csv"),
        "NSE:CNXENERGY":              ("Energy", "ind_niftyenergylist.csv"),
        "NSE:CNXINFRA":               ("Infra", "ind_niftyinfralist.csv"),
        "NSE:CNXCONSUM":              ("Consumption", "ind_niftyconsumptionlist.csv"),
        "NSE:CNXSERVICE":             ("Services", "ind_niftyservicelist.csv"),
        "NSE:CNXCOMMODITIES":         ("Commodities", "ind_niftycommoditieslist.csv"),
        "NSE:NIFTY_HEALTHCARE":       ("Healthcare", "ind_niftyhealthcarelist.csv"),
        "NSE:NIFTY_CONSUMER_DURABLES":("Consumer Durables", "ind_niftyconsumerdurableslist.csv"),
        "NSE:NIFTY_OIL_AND_GAS":      ("Oil & Gas", "ind_niftyoilgaslist.csv"),
        "NSE:NIFTY_DEFENCE":          ("Defence", "ind_niftyindiadefence_list.csv"),
        "NSE:NIFTY_TOURISM":          ("Tourism", "ind_niftyindiatourism_list.csv"),
        "NSE:NIFTY_DIGITAL":          ("Digital", "ind_niftyindiadigital_list.csv"),
        "NSE:NIFTY_MFG":              ("Manufacturing", "ind_niftyindiamanufacturing_list.csv"),
        "NSE:CNX500":                 ("Nifty 500", "ind_nifty500list.csv"),
    }
    
    conn = get_conn()
    added = 0
    refreshed = 0
    indices_data = {}
    
    for sec_idx, (sec_name, fname) in sector_csv_map.items():
        url = f"https://nsearchives.nseindia.com/content/indices/{fname}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                reader = csv.DictReader(io.StringIO(data))
                stock_list = []
                for row in reader:
                    sym = row.get("Symbol") or row.get("symbol") or row.get("SYMBOL")
                    if sym:
                        clean_sym = sym.strip().replace("NSE:", "").replace("BSE:", "").replace(".NS", "")
                        if clean_sym:
                            if clean_sym not in stock_list:
                                stock_list.append(clean_sym)
                            
                            existing = conn.execute("SELECT sector_index FROM stock_sector WHERE symbol = ?", (clean_sym,)).fetchone()
                            if not existing:
                                conn.execute("""
                                    INSERT INTO stock_sector(symbol, sector_index, sector_name, source, confidence, updated_at, notes)
                                    VALUES (?, ?, ?, 'nse_official', 0.95, datetime('now'), 'Synced from NSE Archives')
                                """, (clean_sym, sec_idx, sec_name))
                                added += 1
                            else:
                                refreshed += 1
                if stock_list:
                    indices_data[sec_name] = stock_list
                    if verbose:
                        print(f"  [NSE Sync] {sec_name:<25}: {len(stock_list)} stocks")
        except Exception as e:
            if verbose:
                print(f"  [NSE Sync Error] {sec_name} ({fname}): {e}")
                
    conn.commit()
    conn.close()
    
    # Save cache json
    json_path = os.path.join(DATA_DIR, "nse_indices_constituents.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(indices_data, f, indent=2)
        
    studio_json_path = os.path.join(DATA_DIR, "rrg_studio", "nse_indices_constituents.json")
    if os.path.exists(os.path.dirname(studio_json_path)):
        with open(studio_json_path, "w", encoding="utf-8") as f:
            json.dump(indices_data, f, indent=2)
            
    if verbose:
        print(f"\n[sync-nse] Complete. Added {added} new stocks, refreshed {refreshed} mappings. Saved to {json_path}")
        
    return {"added": added, "refreshed": refreshed, "indices_count": len(indices_data)}


# ─── CLI ──────────────────────────────────────────────────────────────────────
def _default_run() -> None:
    """No-arg invocation: init + import-pine v67 + import-json + sync-nse + audit."""
    init_db()
    if os.path.exists(DEFAULT_PINE_SOURCE):
        import_pine(DEFAULT_PINE_SOURCE)
    else:
        print(f"[default] {DEFAULT_PINE_SOURCE} not found; skipping import-pine")
    if os.path.exists(JSON_LEGACY_PATH):
        import_json(JSON_LEGACY_PATH)
    sync_nse(verbose=True)
    audit()


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Sector DB Manager (SQLite)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Create schema + seed sector_meta and aliases")
    sub.add_parser("sync-nse", help="Fetch & sync official sector mappings from NSE Archives")

    p_imp_pine = sub.add_parser("import-pine", help="Ingest Pine DB_LOOKUP block")
    p_imp_pine.add_argument("file", help="Path to .pine file")
    p_imp_pine.add_argument("--source", default=None,
                             help="Override source label (default: pine_v<version>)")

    p_imp_json = sub.add_parser("import-json", help="Merge legacy sector_db.json")
    p_imp_json.add_argument("file", nargs="?", default=JSON_LEGACY_PATH)

    p_exp = sub.add_parser("export-pine", help="Rewrite DB_LOOKUP block in a .pine file")
    p_exp.add_argument("file", help="Path to .pine file")

    p_ref = sub.add_parser("refresh-yf", help="Refresh yfinance-sourced rows")
    p_ref.add_argument("--symbols", default=None,
                        help="Comma-separated symbols (default: all auto rows)")

    p_lu = sub.add_parser("lookup", help="Show sector for a symbol")
    p_lu.add_argument("symbol")

    sub.add_parser("audit", help="Print DB statistics")

    args = p.parse_args(argv)

    if args.cmd is None:
        _default_run()
        return 0
    if args.cmd == "init":
        init_db()
        return 0
    if args.cmd == "sync-nse":
        sync_nse()
        return 0
    if args.cmd == "import-pine":
        import_pine(args.file, source_label=args.source)
        return 0
    if args.cmd == "import-json":
        import_json(args.file)
        return 0
    if args.cmd == "export-pine":
        export_pine(args.file)
        return 0
    if args.cmd == "refresh-yf":
        syms = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
        refresh_yf(syms)
        return 0
    if args.cmd == "lookup":
        rec = lookup(args.symbol)
        if rec:
            print(f"{rec['symbol']}  ->  {rec['sector_index']} ({rec['sector_name']})")
            print(f"  source={rec['source']}  confidence={rec['confidence']}")
            print(f"  yf_ticker={rec.get('yf_ticker')}  "
                  f"fallback={rec.get('fallback_sector_index')}")
        else:
            print(f"{args.symbol}: not found")
        return 0
    if args.cmd == "audit":
        audit()
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
