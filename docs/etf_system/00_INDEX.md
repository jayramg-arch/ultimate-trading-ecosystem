# ETF Trading System — Documentation Index

> All per-module guides for Jay's ETF Trading System.
> **Master guide**: [`ETF_TRADING_BIBLE.md`](../../ETF_TRADING_BIBLE.md) in project root.
> Last refreshed: 12 May 2026.

---

## System Map

```
ETF Trading System
├── Foundation (Phase 1-2)
│   ├── 01 -- etf_universe.py        56 NSE ETFs + inception dates
│   ├── 02 -- etf_screener.py        4-axis scoring -> ETF_Screener_Results.csv
│   └── 03 -- etf_rotation.py        Sector + regime + RRG + picks (4 CSVs)
│
├── Validation & Analysis
│   ├── 04 -- etf_backtest.py        Walk-forward backtest w/ Sharpe gate
│   ├── 05 -- etf_calendar.py        RBI/FOMC/Budget overlay
│   └── 06 -- etf_validate.py        Python <-> Pine drift check
│
├── Config
│   └── 07 -- etf_config.json        Single source of truth for thresholds
│
├── Pine (TradingView)
│   ├── 08 -- Commander ETF Dashboard v1.2  Analysis panel + Stage bgcolor
│   └── 09 -- Commander ETF Strategy v1.1   Per-ETF executable strategy
│
└── Web UI
    └── 10 -- Commander Web ETF page (Streamlit)
```

## Quick Links

| # | Module | Guide |
|---|---|---|
| 01 | `etf_universe.py` | [Universe Guide](01_etf_universe_guide.md) |
| 02 | `etf_screener.py` | [Screener Guide](02_etf_screener_guide.md) |
| 03 | `etf_rotation.py` | [Rotation Guide](03_etf_rotation_guide.md) |
| 04 | `etf_backtest.py` | [Backtest Guide](04_etf_backtest_guide.md) |
| 05 | `etf_calendar.py` | [Calendar Guide](05_etf_calendar_guide.md) |
| 06 | `etf_validate.py` | [Validation Guide](06_etf_validate_guide.md) |
| 07 | `etf_config.json` | [Config Guide](07_etf_config_guide.md) |
| 08 | Pine Dashboard v1.2 | [Dashboard Guide](08_commander_etf_dashboard_guide.md) |
| 09 | Pine Strategy v1.1 | [Strategy Guide](09_commander_etf_strategy_guide.md) |
| 10 | Commander Web ETF page | [Web Page Guide](10_commander_web_etf_page_guide.md) |

## Use This Index When...

- **Looking up a module's behaviour** → its guide
- **Need a workflow** → see the trading guide section of each module
- **System-wide thinking, regime/risk/architecture** → the [Bible](../../ETF_TRADING_BIBLE.md)

## Production Config (Locked 12 May 2026)

```
freq          = monthly
top_n         = 8
min_hold_days = 28
benchmark     = ^CRSLDX (Nifty 500)
liq_min_cr    = 2.0 Cr/day
risk_per_trade = 1.0%
```

6.35-year backtest with this config:
- **CAGR 18.15%** vs NIFTYBEES 12.54%
- **Sharpe 1.63** | **Max DD -5.41%** | **Alpha +5.61%**
- **OOS Sharpe 2.08** (PASS the walk-forward gate)
