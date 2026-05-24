# 01 — etf_universe.py Guide

> **Module role:** The curated NSE ETF universe. Single source of truth for which ETFs the system trades, how they're classified, and when each one was listed (survivorship correction).
> **Phase:** Foundation (Phase 1 of the ETF system).
> **Lines:** ~350.
> **Last audit:** 12 May 2026 — 56 ETFs, 100% inception coverage.

---

## Why this module exists

NSE lists ~200 ETFs but roughly half trade under ₹1Cr/day — illiquid enough that even a ₹10L position causes meaningful slippage. This module curates **56 ETFs that meet all of:**

1. ≥ ₹2Cr median daily turnover (60-session rolling) for tier A
2. AUM ≥ ₹100Cr
3. Distinct exposure (no duplicate trackers — pick the most liquid per index)
4. Pure-play (no leveraged / inverse / themed-gimmick funds)

When two ETFs track the same index (e.g. Nippon Nifty BeES vs Mirae Nifty 50), we keep the one with higher 60-day average turnover.

---

## User Guide

### Quick start

```python
from etf_universe import (
    ETF_UNIVERSE, get_meta, all_symbols, sector_etfs,
    list_by_asset_class, available_at, inception_date,
)

# Get metadata for a symbol
meta = get_meta("NIFTYBEES")
# {'name': 'Nippon Nifty 50 BeES', 'asset_class': 'BROAD_EQUITY',
#  'sub_category': 'BROAD.LARGECAP', 'underlying': 'Nifty 50',
#  'issuer': 'Nippon', 'benchmark_yf': '^NSEI', 'liquidity_tier': 'A'}

# All sector ETFs (for the rotation engine)
sectors = sector_etfs()   # 18 names

# All international ETFs
intl = list_by_asset_class("INTERNATIONAL")   # 5 names

# Universe available on a specific date (survivorship-corrected)
universe_2020 = available_at("2020-01-01")    # 36 ETFs
universe_today = available_at("2026-05-12")   # 55 ETFs
```

### Schema per entry

| Field | Type | Example |
|---|---|---|
| `name` | str | "Nippon Nifty 50 BeES" |
| `asset_class` | str | BROAD_EQUITY / SECTOR / SMART_BETA / INTERNATIONAL / COMMODITY / DEBT / THEMATIC |
| `sub_category` | str | BROAD.LARGECAP / SECTOR.BANKING / COMMODITY.GOLD / THEME.CPSE etc. |
| `underlying` | str | "Nifty 50" |
| `issuer` | str | "Nippon" / "ICICI" / "Kotak" / "Mirae" etc. |
| `benchmark_yf` | str | "^NSEI" — yfinance ticker for documentation (NOT used in RS scoring; see note below) |
| `liquidity_tier` | str | A (top — heavy size OK) / B (mid — ₹5-10L positions) / C (thin — < ₹2L) |

### Asset class distribution (12 May 2026)

| Class | Count | Examples |
|---|--:|---|
| BROAD_EQUITY | 8 | NIFTYBEES, JUNIORBEES, MID150BEES |
| SECTOR | 18 | BANKBEES, ITBEES, PHARMABEES, BFSI |
| SMART_BETA | 6 | NV20IETF, MOM30IETF, LOWVOLIETF, ALPHAETF |
| INTERNATIONAL | 5 | MAFANG, MON100, NASDBEES, HNGSNGBEES, MASPTOP50 |
| COMMODITY | 7 | GOLDBEES, SILVERBEES, GOLDIETF |
| DEBT | 4 | LIQUIDBEES, BBETF, GILT5YBEES |
| THEMATIC | 8 | CPSEETF, INFRABEES, CONSUMBEES, MAKEINDIA, DEFENCE |

### Helper functions

| Function | Returns | Purpose |
|---|---|---|
| `get_meta(symbol)` | dict or None | Metadata lookup |
| `all_symbols(yf=False)` | list[str] | All universe symbols (yf=True appends ".NS") |
| `sector_etfs()` | list[str] | Sector-only list — used by rotation engine |
| `list_by_asset_class(cls)` | list[str] | Filter by class |
| `list_by_sub_category(sub)` | list[str] | Filter by sub-cat (e.g. "SECTOR.BANKING") |
| `liquid_only(min_tier="B")` | list[str] | Filter by tier |
| `inception_date(symbol)` | date or None | NSE listing date |
| `available_at(date)` | list[str] | Universe available on/before that date |
| `inception_coverage()` | dict | Diagnostic — how many entries have dates |
| `universe_summary()` | dict | Counts per asset class |

### Running standalone

```bash
python etf_universe.py
```

Prints summary + sector ETF roster with tiers.

### When to edit

1. **New ETF launch**: add the entry + `INCEPTION_DATES` row. Confirm liquidity tier from NSE listings.
2. **Issuer delists a fund**: remove the entry but **never** rewrite inception dates retroactively.
3. **Wrong asset_class**: see Bug #1-7 audit notes in CLAUDE.md changelog. Use the Excel mapping as authority; corroborate with NSE listing's category.

> ⚠ **Symbol verification gotcha**: Always verify the exact NSE ticker before adding. The "ETF to Sector Mapping.xlsx" had listed `REALTYBEES` but the actual NSE symbol is `REALTY`. See `memory/etf_symbol_corrections.md`.

---

## Trading Guide

### Why classification matters operationally

- **Rotation engine** uses `sector_etfs()` to rank pure-sector ETFs. Mis-classifying a thematic (e.g. INFRABEES) as SECTOR pollutes the rotation table with names that don't rotate cleanly.
- **Regime detector** uses 9 hardcoded flagships across asset classes. The classes themselves come from this module.
- **Strategy vol-profile preset** picks ATR multipliers based on broad characteristics (Low for gold/debt, High for sector/smallcap). The user picks the profile manually but the dropdown options map to these classes.
- **Backtest survivorship** uses `available_at()` to exclude pre-inception periods — without this, the system would "trade" ETFs that didn't exist yet (look-ahead bias).

### Liquidity tier — practical sizing rules

| Tier | Threshold | Max INR position | Rationale |
|---|---|--:|---|
| **A** | ≥ ₹10Cr/day | ₹25-50L | Slippage < 5bps round-trip |
| **B** | ₹2-10Cr/day | ₹5-15L | Slippage 5-15bps |
| **C** | < ₹2Cr/day | ₹1-3L | Avoid except in special cases |

The strategy's `vol_disc` formula naturally sizes positions smaller for high-ATR ETFs. Tier is the **second** sizing gate (the first being ATR-based risk sizing).

### Sub-category granularity — when it pays off

| Use case | Granularity needed |
|---|---|
| Sector rotation top picks | `asset_class == "SECTOR"` is enough |
| Avoid two PSU banks in same top-8 | `sub_category == "SECTOR.PSU_BANK"` filter |
| Find an Intl USD hedge for GOLD_LED regime | `sub_category` starts with "INTL." |
| Calendar overlay (Budget Day) | `sub_category` mapping in `etf_calendar.py` |

### What the system **won't** do for you

- It won't update inception dates from a live API (they're conservatively hard-coded — update the dict if NSE re-classifies a fund)
- It won't compute "asset class allocation" by itself — that's `etf_rotation.asset_class_regime()`'s job
- It won't fetch prices — that's `data_provider` / `etf_screener._fetch_history`

### Maintenance cadence

| When | What |
|---|---|
| **Monthly** | Verify the universe count (should be ~56). Run `python etf_universe.py`. |
| **On new NSE listing** | Add entry + inception date + tier. |
| **Quarterly** | Audit `liquidity_tier` against current 60-day turnover (data drifts). |
| **Annually** | Walk the universe for delistings / fund mergers. |
