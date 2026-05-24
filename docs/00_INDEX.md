# Weinstein Commander — Documentation Index

> Complete User & Trading Guide for all 15 core modules of the Weinstein Commander ecosystem.
> **Last updated: 24 May 2026** | Dashboard **v67.4.12** (PA cascade fully re-validated on N500 × 5y) | Unified Ecosystem **v3.6** (file: `_v2.8.3.pine`) | Bull Screener Py **v1.11** · Pine **v3.3** | Recovery Screener Py **v1.6** · Pine **v2.0** | PA Field Validator **v1.0** (`pa_field_validator.py` + `validate_pa_field.py`) | Validation Framework **v2.8** (catalyst-aware horizons + bootstrap CI)
>
> **Single source of truth:** `Weinstein_Minervini_Trading_Bible.md` (root). All operational decisions flow through the Bible; the per-module guides below are the field-by-field references the Bible points to.

---

## Module Index

| # | Guide | Module | Type | Role |
|---|---|---|---|---|
| 01 | [Swing Zigzag Strict v6.0](./01_Swing_Zigzag_Strict_v6_Guide.md) | `Wesinstein Swing Zigzag [Strict v6.0].pine` | Pine | Structural foundation — HH/HL/LH/LL state machine |
| 02 | [Wyckoff Phases v1.0](./02_Wyckoff_Phases_v1_Guide.md) | `Weinstein_Wyckoff_Phases_v1.0.pine` | Pine | Narrative layer — SC/AR/SOS/LPS event labelling |
| 03 | [Volume Profile v1.0](./03_Volume_Profile_v1_Guide.md) | `Weinstein_Volume_Profile_v1.0.pine` | Pine | Value-area framework — POC/VAH/VAL levels |
| 04 | [SMC Zones v1.0](./04_SMC_Zones_v1_Guide.md) | `Weinstein_SMC_Zones_v1.0.pine` | Pine | Institutional footprint — OBs, FVGs, Liquidity Sweeps |
| 05 | [Recovery Strategy v1.4](./05_Recovery_Strategy_v1_4_Guide.md) | **🛑 DELETED — see Unified Ecosystem v2.3** | Pine | Legacy doc only — REV edges now live in Unified Ecosystem |
| 06 | [Minervini Strategy v4.53](./06_Minervini_Strategy_v4_53_Guide.md) | **🛑 DELETED — see Unified Ecosystem v2.3** | Pine | Legacy doc only — bull edges now live in Unified Ecosystem |
| 07 | [Commander Web v4.0](./07_Commander_Web_v4_Guide.md) | `weinstein_commander_web_v4.0.py` + modules | Python | Automation backbone — portfolio sync, screeners, **Run Full Auto-Pilot watchlist pipeline** |
| 08 | [Dashboard v67.4.12](./08_Dashboard_v67_Guide.md) | `Weinstein and Swing Pro Dashboard v67.4.12.pine` | Pine | **Mission control — canonical for RS engine, Stage anchors, Strict trend, Price Action, Portfolio.** Decision-Mode compression (~18 rows). **v67.4.5→4.12: complete PA cascade audit + N500 × 5y validation.** 6 detector bugs fixed (notably VCP_BO restored from 0 firings, FAILED_BREAKOUT made structurally possible). 5 new patterns added (Shooting Star, Gap-Up BO, Outside Bar, IB-NR7, Hammer-at-MA, 50SMA Undercut). BULL_ENGULF B6 quality gate (relvol>2.0 + RSI[1]<40). 4 bearish detectors neutralized to Tier 0 (data showed they predict wrong direction in both regimes). Tier-3 catalyst alphas: STAGE_2_LAUNCH +14.4%, GAP_UP_BO +6.7%, VCP_BO +5.3%, SPRING +4.1% — all P(α>0)=100%. |
| 09 | [Recovery Screener v1.7](./09_Recovery_Screener_v1_7_Guide.md) | `Commander_Recovery_Screener_v1.7.pine` | Pine | **Capitulation discovery — canonical for 4-pillar CB + REV-CB/RS/EARLY edges.** Composite-merged 14-row layout. RS engine mirrors Dashboard. |
| 10 | [Risk Allocator v1.0](./10_Risk_Allocator_v1_Guide.md) | `Commander_Risk_Allocator_v1.0.pine` | Pine | Execution layer — Kelly position sizing, CE trailing, Telegram alerts |
| 11 | [Bull Screener v3.1](./11_Bull_Screener_v3_1_Guide.md) | `Commander_Bull_Screener_v3.1.pine` | Pine | **Bull discovery — canonical for Catalyst engine + POS-BO 9-gate stack + Trade Levels.** Composite-merged 13-row layout. RS engine mirrors Dashboard. |
| 12 | [Context Layers v1.0](./12_Context_Layers_v1_Guide.md) | `Weinstein_Context_Layers_v1.0.pine` | Pine | Institutional context overlay — Wyckoff + Volume Profile + SMC unified panel |
| 13 | [Unified Ecosystem — User Guide](./13_Unified_Ecosystem_User_Guide.md) | `Weinstein_Unified_Ecosystem_v2.8.3.pine` | Pine | Input configuration. **v2.6+ aligned with cross-tool architecture**: RS mirrors Dashboard, removed duplicate display rows, 4-column stacked CATALYST DIAG panel. |
| 14 | [Unified Ecosystem — Trading Guide](./14_Unified_Ecosystem_Trading_Guide.md) | `Weinstein_Unified_Ecosystem_v2.8.3.pine` | Pine | 9-edge playbooks. **v3.5/v3.6 (2026-05-21):** POS-ACCUM + REV-* restored to triggers (rolled back from v3.4); catalyst-aware fallback ATR multipliers (POS=4×, WYC=3.5×, REV=2.5×, SWG=1.5×). |
| 16 | [Validation Framework](./16_Validation_Framework_Guide.md) | `validation.py` + `replay.py` + `sector_rotation.py` | Python | **NEW (2026-05-21):** backtest harness with realistic SL/T1/T2 simulation, catalyst-aware forward windows (POS=120-180d, WYC=120d, REV=90d, SWG=30d), matched-horizon alpha, bootstrap CI on alpha, optional risk overlays (sector cap / kill switch / sector rotation). |
| 17 | PA Field Validator (no dedicated guide yet) | `pa_field_validator.py` + `validate_pa_field.py` + `verify_bull_engulf_tightening.py` | Python | **NEW (2026-05-24):** faithful Python port of the Dashboard v67.4.12 PA cascade (29 detectors + base-count tracker + decorators) for offline N500 backtesting. Catalyst-aware horizons via `FWD_DAYS_BY_PA_STATE`. Direction-aware alpha (bullish = stock-bench; bearish = bench-stock). Regime-split capability (bull/bear vs CRSLDX 200d SMA). Bootstrap CI95 + P(α>0). N500 reports: `PA_FIELD_VALIDATION_v3/v4/v5_*.md`. |
| — | [Backtest v2 Results](../BACKTEST_RESULTS_v2.docx) (root) | — | docx | Institutional report — v2 LOCK evidence, ablation tables, cross-universe verification |

---

## Ecosystem Architecture (v2.3 / Backtest v2 LOCKED)

```
PYTHON BACKEND (Source of Truth)
├── chartink_replay.py             → Layer 1: 4 Bull scans + 3 Recovery scans
│                                     SCAN_PARAMS_VERSION = "v2_FINAL_20260510"
├── matcher_replay.py              → Layer 2: Screener.in conviction filter (≥6.0)
├── fundamental_replay.py          → yfinance-cached point-in-time fundamentals
├── bull_screener.py               → calculate_score() — composite quality score
│                                     hooks v2_fixes.adjust_catalyst_score + adjust_record_score
├── v2_fixes.py                    → V2_FLAGS["pos_accum_rsi_nullout"] = True (v2 LOCK default)
│                                     select_top_n() with fast-path no-op when all flags off
├── validation.py                  → walk-forward harness: run_validation (raw) + run_chartink_validation (filtered)
├── snapshot_archive.py            → forward archive of daily Chartink+Screener.in CSVs
├── recovery_screener.py           → REV-CB / REV-RS / REV-EARLY logic
├── brute_force_match_pro.py       → live Layer-2 conviction matcher (production)
├── watchlist_manager.py / _ranker → TradingView watchlist sync
└── master_portfolio_sync.py       → Dhan → Dashboard portfolio slot injection

DISCOVERY & WATCHLIST PIPELINE  (Run via Commander Web v4.0 → 🤖 Run Full Auto-Pilot)
├── Layer 1 outputs in Generated_Watchlists/
│   ├── Bull_Hunter-DDMMMYY.txt        Bull_Pullback-DDMMMYY.txt
│   ├── Bull_EarlyBird-DDMMMYY.txt     Bull_StrongLeader-DDMMMYY.txt
│   ├── Rec_Climax_Bounce-DDMMMYY.txt  Rec_RS_Survivor-DDMMMYY.txt
│   └── Rec_Early_Bird-DDMMMYY.txt
├── Layer 2 (conviction-filtered) outputs in project root
│   ├── FINAL_Hunter_Picks.csv         FINAL_Pullback_Picks.csv
│   ├── FINAL_EarlyBird_Picks.csv      FINAL_Leader_Picks.csv
│   └── FINAL_Recovery_*.csv           (and matching _RRG variants)
└── Layer 3 (combined + golden)
    ├── FINAL_COMBINED_BULL_PICKS.csv  FINAL_COMBINED_RECOVERY_PICKS.csv
    └── FINAL_WATCHLIST.csv            (matcher's golden watchlist)

PINE DISCOVERY (one-symbol-at-a-time validation in TradingView)
├── Beta Screener v2.9                  → Hunter v1 FINAL + v2 POS-ACCUM gate + pyScore (mirrors Python)
└── Capitulation Screener v1.5          → REV signal scanner (no Hunter/POS-ACCUM logic — unchanged)

CONTEXT LAYER (loaded on every chart)
├── Zigzag v6.0                         → HH/HL/LH/LL structural state
└── Context Layers v1.0                 → unified Wyckoff + Volume Profile + SMC + CONTEXT SCORE

VALIDATION LAYER
└── Dashboard v67.0                     → final go/no-go; OPEN portfolio slots only (NOT watchlist)

EXECUTION LAYER (live trading)
└── Unified Ecosystem v2.3              → all 9 edges
    ├── Bull (6): POS-AC, POS-BO, SWG-PB, SWG-BO, SWG-REV, GAP-GO
    │     POS-BO requires wRSI ≥ 60 + ADX ≥ 25 (v1 FINAL)
    │     POS-AC requires d_rsi ≤ 50 (v2 LOCK)
    ├── Recovery (3): REV-CB, REV-RS, REV-EARLY
    ├── Integrated Exit Engine (MTT trail + CE trailing + time-stop)
    └── Kelly Position Sizing

SIZING LAYER (optional overlay)
└── Risk Allocator v1.0                 → standalone Kelly sizing + Telegram alerts

AUTOMATION LAYER (Commander Web tabs)
└── Commander Web v4.0
    ├── Tab 1: Portfolio Sync (Dhan → Dashboard slots, OPEN positions only)
    ├── Tab 2: Watchlist Manager (TradingView import)
    ├── Tab 3: Recovery Screener (manual run)
    ├── Tab 4: Bull Screener (manual run)
    ├── Tab 4.5: 🤖 Run Full Auto-Pilot (Layer 1+2+3 in one click)
    └── Tab 5: Sector Dashboard (rotation heatmap)
```

---

## Daily Workflow Reference

### Pre-Market (15–20 min)
1. **Start** `weinstein_commander_web_v4.0.py` → open `http://localhost:5000`
2. **Sector Dashboard** tab → identify Stage 2 + LEADING sectors; avoid Stage 3/4
3. **Portfolio Sync** tab → click "Sync from Dhan" → Dashboard Pine file updates
4. **Bull Screener** tab → run scan on NSE Top 500 → sort by Alpha Score
5. **Recovery Screener** tab (if applicable) → run if CNX500 corrected ≥ 7%
6. Open TradingView → load **Unified Ecosystem v2.2** + **Dashboard v67.0** → positions updated

### For Each Candidate (2–3 min per stock)
1. Load on **Dashboard v67.0** → confirm STAGE 2, RS = LEADING, ALPHA ≥ 60
2. Check **Beta Screener table** → verify 9-gate status (≥ 7/9 for POS-BO)
3. Check **Context Layers** → CONTEXT SCORE ≥ BULL (≥ 3) before any entry
4. Add context layers: **Volume Profile** (entry near POC/VAL?), **SMC** (OB support?)
5. Check **Recovery section** in Dashboard (if applicable — REV candidate)
6. **Unified Ecosystem v2.2** handles entry triggers, sizing, and exit automatically

### Post-Trade Management
- Update Dashboard portfolio slot with ticker, entry, SL, date
- Re-run `master_portfolio_sync.py` after any position change
- Monitor **TIME WARN** — follow time-stop discipline at T+10 days (swing) or T+6 weeks (positional)

---

## Key Cross-Module Parameters (Keep Consistent)

These values appear in multiple modules and **must be identical** across all for correct operation:

| Parameter | Value | Used In |
|---|---|---|
| Weinstein SMA Length | `30` weeks | Unified Ecosystem, Dashboard, Screeners |
| Pivot Lookback Left | `2` | Zigzag, Unified Ecosystem, Dashboard, Screeners |
| Pivot Lookback Right | `2` | Zigzag, Unified Ecosystem, Dashboard, Screeners |
| Volume Average Length | `50` bars | All Pine modules |
| ATR Length | `14` | All Pine modules |
| Benchmark 1 | `NSE:NIFTY` | Unified Ecosystem, Dashboard, Screeners |
| Benchmark 2 | `NSE:CNX500` | Unified Ecosystem, Dashboard, Screeners |
| RS Slope Length | `26` weeks | Unified Ecosystem, Dashboard, Screeners |
| VP Lookback | `100` bars | Unified Ecosystem, Dashboard, SMC |
| 50 DMA | `50` | Unified Ecosystem, Dashboard, Screeners |
| 150 DMA | `150` | Unified Ecosystem, Dashboard, Screeners |
| 200 DMA | `200` | Unified Ecosystem, Dashboard, Screeners |
| Mansfield RS Scale | `×100` | All RS calculations |

> **Critical:** When the Unified Ecosystem v2.2 inputs are changed, the same changes must be applied to `bull_screener.py` and `master_portfolio_sync.py` to maintain Python-Pine synchronization.

---

## Version History

| Version | Date | Key Change |
|---|---|---|
| **PA Field Overhaul (Dashboard v67.4.5 → v67.4.12)** | **24 May 2026** | **8 commits across 1 session, 6 detector revisions, all data-driven.** Complete PA cascade audit + new validation framework (`pa_field_validator.py`, `validate_pa_field.py`). 6 detector bugs fixed; 5 new patterns added; 2 cascade demotions; 1 quality-gate tightening; 4 bearish detectors neutralized to Tier 0. N500 × 5y validation (180k trades, bootstrap CI, regime split). Tier +3 catalysts (STAGE_2_LAUNCH, GAP_UP_BO, VCP_BO, SPRING) all show P(α>0) = 100% in production. See Dashboard guide §"What's New in v67.4.5 → v67.4.12" for the full breakdown. |
| **v2.3 / Backtest v2 LOCKED** | **10 May 2026** | `pos_accum_rsi_nullout` locked as v2 default in `v2_fixes.py`; Beta Screener bumped to v2.9 (Hunter v1 FINAL gates + POS-ACCUM RSI gate + Python-aligned `pyScore`); Dashboard ULTIMATE bumped to v3.9 (Hunter + POS-ACCUM gates); Unified Ecosystem in-file title bumped to v2.3 (POS-BO + POS-AC trigger gates added). Legacy `Weinstein_Minervini_Strategy*.pine` and `Weinstein_Recovery_Strategy*.pine` files **deleted from project root** — Unified Ecosystem v2.2 file (with v2.3 in-file title) is sole canonical strategy. |
| v2.2 / Backtest v1 LOCKED | 8 May 2026 | Minervini Strategy + Recovery Strategy merged into Unified Ecosystem v2.2; Dashboard upgraded to v67.0; Context Layers v1.0 introduced; Backtest v1 FINAL locked (`SCAN_PARAMS_VERSION = "v1_FINAL_20260508"` — Hunter `weekly_rsi_min=60`, `daily_adx_min=25`, EarlyBirds `disable_rsi=True`) |
| v2.1 | May 2026 | Commander Web v4.0 launched; integrated Sector Dashboard and Portfolio Sync |
| v2.0 | Apr 2026 | Minervini Strategy v4.53 and Recovery Strategy v1.4 released as separate scripts |
| v1.x | Mar 2026 | Dashboard v65.0; standalone screeners |

---

## Excluded Modules (Out of Scope)

The following modules were explicitly excluded from this documentation cycle:
- `Weinstein Fundamental X-Ray` — covered separately
- `Ultimate Screener Dashboard` — covered separately

---

*Documentation generated May 2026. For updates to any module, re-run the corresponding guide update workflow and update this index.*
