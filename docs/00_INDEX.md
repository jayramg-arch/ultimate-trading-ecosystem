# Weinstein Commander — Documentation Index

> Complete User & Trading Guide for all core modules of the Weinstein Commander ecosystem.
> **Last updated: 9 June 2026** — *Pine panel pass: Wyckoff catalysts surfaced on the Unified panel; honest "no active setup" trade levels on the Bull & Recovery screeners; **Risk Allocator v2.0 — auto-detect catalyst, auto structural SL, 3-leg scale-out, Dhan GTT export** (catalyst+regime targets/trail synced to Unified v3.4).*
> **Major change:** all bull catalyst gates and the Alpha Score are now **pure price action** (RSI/MACD/BB/ADX → PA momentum / directional-bars / retrace pockets), synced across `bull_screener.py` and all three bull Pine files. Recovery screener gained a **fundamental hard gate** (RFF ≥ 4) + 15–35% drawdown band + un-blackouted REV-EARLY. New validation modules: `walkforward_oos.py` (overfit gate) + `catalyst_regime_partition.py` (per-family/regime edge). New journal modules: `performance_attribution.py`, `journal_enrichment.py`, `journal_sync.py` (Phase 0/1). `data_provider.py` gained a hard download timeout.
> | Bull Screener **v3.3.1 (PA, honest no-setup levels)** | Recovery Screener **v2.0.2 (RFF-gated, PA, Wyckoff-documented)** | Unified Ecosystem **v3.4.2 (PA-synced, Wyckoff panel)** | Dashboard **v67.4.12 (PA-synced)** | Validation Framework **(OOS gate + partition + timeout)**
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
| 09 | [Recovery Screener v2.1 (RFF-gated, PA)](./09_Recovery_Screener_v2_1_Guide.md) | `recovery_screener.py` (Py, full RFF) + `Commander_Recovery_Screener_v2.0.pine` (RFF-Lite) | Python/Pine | **Beaten-down-quality discovery — fundamentally strong (RFF ≥ 4) stocks down 15–35%, turning up.** REV-CB/RS/EARLY **+ Wyckoff (signal 5–8: SPRING/SOS/JAC/SPR+SOS)** edges; validated positive in down/recovering tapes. **v2.0.2:** Wyckoff signal codes + adaptive G6–G10 gate mapping + per-signal trading playbooks now documented; honest "no active setup" levels. |
| 10 | [Risk Allocator v2.0](./10_Risk_Allocator_v2_Guide.md) | `Commander_Risk_Allocator_v2.0.pine` | Pine | Discretionary chart-click sizer + trade planner. **v2.0 (9 Jun):** (1) **auto-detect catalyst** from Weekly Stage + RS + price-action; (2) **auto-suggest structural SL** (catalyst-aware, click to override); (3) **3-leg scale-out T1/T2/T3 + runner** with per-leg share qty + chart lines; (4) **Dhan GTT JSON export** for GTT_Auto_Shield. Catalyst+regime targets/trail (zero-drift mirror of Unified v3.4). *v1.1 guide retained at `10_Risk_Allocator_v1_Guide.md` as the 2-leg fallback.* |
| 11 | [Bull Screener v3.3 (Pure Price Action)](./11_Bull_Screener_v3_3_Guide.md) | `bull_screener.py` (Py) + `Commander_Bull_Screener_v3.3.pine` | Python/Pine | **Bull discovery — 6 catalysts (POS-BO/ACCUM, SWG-BO/PB/GAP/REV) + 0–100 Alpha Score, now fully PURE PRICE ACTION.** Catalyst FUNNEL diagnostics. Validated: 4/5 catalysts positive matched-alpha. **v3.3.1:** compound LEVELS row now prints "SL/T1/T2 — (no active setup)" when no catalyst fires (no more fake −5% placeholder plan). |
| 12 | [Context Layers v1.0](./12_Context_Layers_v1_Guide.md) | `Weinstein_Context_Layers_v1.0.pine` | Pine | Institutional context overlay — Wyckoff + Volume Profile + SMC unified panel |
| 13 | [Unified Ecosystem v3.4.2 — User + Trading Guide](./13_Unified_Ecosystem_v3.4_Guide.md) | `Weinstein_Unified_Ecosystem_v3.4.pine` (title `[v3.4.2]`) | Pine | **Combined input-config + 9-edge playbooks** (User Guide §1–7, Trading Guide §1–13 in the same file). RS mirrors Dashboard; 4-column stacked CATALYST DIAG panel. **v3.5/v3.6:** POS-ACCUM + REV-* restored; catalyst-aware fallback ATR multipliers (POS=4×, WYC=3.5×, REV=2.5×, SWG=1.5×). **v3.4.2 (9 Jun):** Wyckoff catalysts (SPR+SOS/JAC/SOS/SPRING) now surfaced — new "Wyckoff Signals" panel row + WYCKOFF block in CATALYST DIAG (display-only; previously the v3.4 port took the trades but never showed them). |
| 14 | *(merged into #13)* | — | — | The standalone Trading Guide is now §1–13 inside `13_Unified_Ecosystem_v3.4_Guide.md`. |
| 16 | [Validation & Backtest Framework](./16_Validation_Framework_Guide.md) | `validation.py` + `replay.py` + `walkforward_oos.py` + `catalyst_regime_partition.py` + `data_provider.py` | Python | **The honesty layer.** Walk-forward harness, realistic execution sim (commission+slippage), **matched-horizon alpha** + up/down-tape split, **OOS overfit gate** (Sharpe ≥60% IS), **per-family/regime partition**, bootstrap CI, hard download timeout. |
| 19 | [Journal & Attribution (Phase 0/1)](./19_Journal_Attribution_Guide.md) | `performance_attribution.py` + `journal_enrichment.py` + `journal_sync.py` + `dhan_journal_v7.py` | Python | **NEW (June 2026):** realized-P&L attribution across 11 dimensions; lean entry-signal snapshot on the journal; daily journal↔Dhan holdings sync (scheduled 4:30 PM IST). True baseline −₹4.99L / 25.6% win. |
| 17 | PA Field Validator (no dedicated guide yet) | `pa_field_validator.py` + `validate_pa_field.py` + `verify_bull_engulf_tightening.py` | Python | **NEW (2026-05-24):** faithful Python port of the Dashboard v67.4.12 PA cascade (29 detectors + base-count tracker + decorators) for offline N500 backtesting. Catalyst-aware horizons via `FWD_DAYS_BY_PA_STATE`. Direction-aware alpha (bullish = stock-bench; bearish = bench-stock). Regime-split capability (bull/bear vs CRSLDX 200d SMA). Bootstrap CI95 + P(α>0). N500 reports: `PA_FIELD_VALIDATION_v3/v4/v5_*.md`. |
| 18 | [Trade Checklist](./18_Trade_Checklist.md) | all modules (funnel) | — | **NEW (2026-06-01):** operational pre-trade checklist for swing + positional, **grounded in Bible v6.0**. Tick-box 9-Step Confluence Sequence with exact hard floors + confluence-boost levels per step, master prerequisites, Kelly/vol/regime sizing, Trade-Quality Scorecard, and full Bull + Recovery per-edge exit tables (§8/§9). Flags that POS-ACCUM is enabled across all surfaces (Bull Screener in-file v3.3 / Py v1.10 / Unified v3.6, gated RSI≤50 — the .pine v3.2 header "disabled" comment is stale) and the exit-table doc-lag (legacy 3.0×/2.5R vs v3.6's claimed 4.5×/3R-5R). **Step 8 has two entry paths:** Path A = automated trigger fires; Path B = discretionary entry when the strict Pine trigger stays silent but the edge is visible and Steps 1–7 floors hold (discretion on timing only, never on regime/conviction/risk). **Step 3.5** = weekend RRG pre-filter on Strike.Money (keep LEADING/IMPROVING stocks tiered by RS-Ratio, bias to LEADING/IMPROVING sectors, weekly TF + N500 benchmark, read the tail not just the dot). **Execution Toolkit — D&S price-action entries** (new): 10 demand/supply zone setups + 1 Testing setup from the pro-trainer pure-price-action method (RBR/DBR zones, Controlling WCDZ, TL/Rectangle BO, Engulf/IC/FTF, EMA20 dynamic S/R, fib-EMA confluence, ≥20% room rule) recast as named **Path B** triggers each tagged to the catalyst it satisfies — long-only & swing-focused (intraday Setup 9 excluded, short branches de-scoped to exit/trim), with zone-distal SL → Step 9 and room → Gate-3 R:R wiring. |
| 20 | [Chart Markup v1.8](./20_Chart_Markup_v1_8_Guide.md) | `Commander_Chart_Markup_v1.8.pine` | Pine | **NEW (June 2026):** self-contained, timeframe-agnostic chart-reading **scanner** — Stage + Mansfield RS + auto trendlines/channels/wedges + S/R + gaps + classical patterns (flags, double/triple tops, H&S/Cup candidates) + **Anchored VWAP** (Dashboard v67.4.12 port) + **Fibonacci** (Zigzag v6.2 port). Outputs a **decision-brief panel** (Stage · RS↑↓ · setup · conviction 0–7 · nearest S/R · Entry/Stop/Target · verdict) + **descriptive sentence-notes** at each level. **TF-adaptive pivots** (M1/W5/D2/I2, Zigzag-synced); **close-respect** trendline validation (no candle closes through); selectable colors; trendlines don't extend right. Read-only guides — hand-draw / tune `N pivots` for the tradeable line. |
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
| **Pure Price-Action Conversion + Recovery Strengthening** | **5 June 2026** | **Bull:** found & fixed the catalyst blackout (squeeze gate killed the positional book for 24 months) + pervasive Python↔Pine drift; converted ALL catalyst gates + Alpha Score to pure price action (RSI/MACD/BB/ADX → PA), synced across Python + 3 Pine files; catalyst-aware stops (SWG-PB structural EMA20 floor). Validated 4/5 catalysts positive matched-alpha. **Recovery:** RFF fundamental hard gate (1→4/6 — only strong companies); REV-CB 15–35% drawdown band; REV-EARLY un-blackouted + true early-bird; REV-RS stop widened. Validated positive in down/recovering tapes. **Infra:** new `walkforward_oos.py` (overfit gate) + `catalyst_regime_partition.py`; Phase 0/1 journal modules (attribution, entry-snapshot, daily Dhan sync); `data_provider` hard download timeout. **Guides rewritten from modules:** 09, 11, 16 (this pass). |
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
