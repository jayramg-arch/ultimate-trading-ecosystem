# CLAUDE.md — Jay (Jayram G) | Trading System DNA & Agent Context

> **Purpose:** Persistent context file for Claude across Chat, Cowork, and Code.
> Place this file in the root of any project folder used with Cowork or Code.
> Last updated: 23 Jul 2026 (Gemini audit review → remediation: symbol-normalization consolidation, manual-webhook hardening, stale-feed + daily-PnL alarms, orphan-DB/atomic-write cleanup)

---

## Identity & Role

- **Name:** Jay (Jayram G)
- **Location:** India
- **Languages:** English (primary), Hindi
- **Role:** Independent systematic quantitative & technical trader
- **Operating style:** Institutional-grade risk management, solo operator

---

## Core Methodology

### Weinstein Stage Analysis (Primary Framework)
- **Anchor:** 30-week Moving Average (Weekly chart)
- Stage 1 (Basing) → Stage 2 (Advancing) → Stage 3 (Topping) → Stage 4 (Declining)
- Only trade Stage 2 breakouts; avoid/exit Stage 3–4
- Weekly-anchored Stage and Relative Strength (RS) logic is the foundation

### Minervini-Style Growth Stock Selection
- RS/VCP (Volatility Contraction Pattern) setups
- Relative Strength benchmarked against: **Nifty 50, Nifty 500, and Sector Indices**
  - 52-week RS: primary ranking
  - 3-month & 6-month RS: tactical/timing

### Alpha Score (5-Star Grading System)
- Composite score based on: **Stage + RS + Volatility**
- Drives stock selection and portfolio priority

---

## Trading Styles (NSE)

### Swing Trading
- **Timeframe:** 8–12 weeks
- **Target:** 5–8% per trade
- **Strategy:** Supply/Demand zones, S&R, Price Action
- **Charts:** Daily, 125-min, 75-min

### Positional Trading
- **Timeframe:** 6–8 months
- **Target:** 10–30% per trade
- **Strategy:** Weinstein Stage Analysis, RRG charts, Mansfield RS for sector/stock selection

### Common Rules
- **Risk per trade:** 1% of capital
- **Higher Timeframe (HTF):** Demand/Supply Zones (Weekly/Monthly)
- **Lower Timeframe (LTF):** Daily, 125-min, 75-min
- **Approach:** Pure price action — indicators for confluence only

---

## Risk Management (Institutional Grade)

- **Position Sizing:** Volatility-adjusted using 14-day ATR
- **Stop-Loss:** Mandatory 14-day ATR-based trailing stops
- **Formula:** Position Size = (Risk Amount) / (ATR × Multiplier)
- **No discretionary overrides** — system rules are final

---

## Structural Indicators (Unified Across All Platforms)

> **CRITICAL RULE:** All structural indicators MUST be mathematically identical across TradingView, Streamlit, screeners, and any other platform. Zero signal drift tolerance.

| Indicator | Specification |
|-----------|--------------|
| EMA 20 | On chart (Daily and above); EMA20(Daily) overlaid on 125/75-min |
| SMA 50 | Volume baseline |
| 30-Week MA | Weinstein Stage anchor (Weekly) |
| RS (Relative Strength) | Mansfield RS vs Nifty 50/500/Sector; 52-wk primary, 3/6-mo tactical |
| Volume Baselines | 50-SMA of volume |
| Stage Classification | Weekly-anchored, derived from 30-WMA slope + price position |

Additional confluence: Trendlines, Fibonacci, Order Flow, RSI, ATR

---

## The ULTIMATE Ecosystem

### [ULTIMATE] Indicator (TradingView / Pine Script)
- **Version:** v60.0+ (Pine Script v6)
- Alpha Screener (v60.4) — stock screening engine
- Unified Hybrid Trading Engine — synchronized signals across platforms
- Screener User Guide — logic and threshold documentation

### Weinstein Commander Web App
- **File:** `weinstein_commander_web_v2.5.py`
- **Stack:** Python / Streamlit
- Real-time portfolio health vitals dashboard
- Indian currency formatting: **₹1,23,456** (mandatory across all financial displays)

### GTT_Auto_Shield
- Automated stop-loss management system
- Built for **Dhan** brokerage platform
- Enforces ATR-based trailing stops programmatically

### TradingView Automation
- Watchlist synchronization engine
- Data scraping via Playwright/Selenium
- Keeps TradingView watchlists aligned with screener outputs

---

## Tech Stack

| Domain | Tools |
|--------|-------|
| Charting / Indicators | Pine Script v6 (TradingView) |
| Web Apps / Dashboards | Python, Streamlit |
| Browser Automation | Playwright, Selenium |
| Broker Integration | Dhan API |
| Data Analysis | Python (pandas, numpy) |

---

## Working Rhythm

| Day | Activity |
|-----|----------|
| **Weekend** | Strategic planning — Hunter Picks, EarlyBird Picks (fresh Stage 2 breakouts) |
| **Weekday** | Tactical execution — Pullback Picks (entries on retracements within existing setups) |

---

## Portfolio Context

- Active portfolio: ~21 stocks (variable)
- Exit strategy analysis during market drawdowns
- **Sell-to-Buy Capital Rotation Matrix** — systematic capital recycling from exits into new setups

---

## Output & Communication Preferences

### Analysis Output Requirements
- In-depth Technical Analysis with catalysts, thematic rationale, fundamentals, and sentiment
- Structured trade plans: **Entry / Stop-Loss / Target**
- Pure price action narrative — indicators referenced for confluence only

### Formatting Rules
- Indian currency: ₹1,23,456 (always, no exceptions)
- Use structured tables for comparisons and data
- Code outputs: well-commented, production-grade
- Pine Script: always v6 syntax (v60.0+)

### Tone
- Direct, professional, trader-to-trader
- No hand-holding — assume institutional-level understanding
- Flag risks and edge cases proactively

---

## Standing Instructions for All Modes

1. **Signal consistency is sacred.** Never introduce indicator calculations that diverge from the unified specifications above.
2. **Risk management is non-negotiable.** All trade plans must include ATR-based stops and volatility-adjusted sizing.
3. **Indian market context.** Default exchange is NSE. Default currency is INR (₹). Trading hours: 9:15 AM – 3:30 PM IST.
4. **Pine Script discipline.** Always use v6 syntax. Test for `na` values. Handle `request.security()` correctly for MTF logic.
5. **When building tools or dashboards:** Apply ₹ formatting, use the 5-star Alpha Score system, and align with Weinstein Stage logic.
6. **When analyzing stocks:** Lead with Stage + RS assessment, then price action, then fundamentals/catalysts.
7. **Portfolio decisions:** Reference the Sell-to-Buy rotation matrix and current portfolio context when relevant.

---

## File Placement Guide

```
your-project-folder/
├── CLAUDE.md          ← This file (root of any project)
├── scripts/
├── data/
└── ...
```

- **Cowork:** Select the folder containing this file as your working directory
- **Code:** Open the folder in VS Code or point Claude Code CLI to it
- **Chat:** Memory handles this automatically (but keep this file as the canonical source of truth)

---

## Current Project State — Live Memory (10 May 2026)

> Everything below this line is mutable session state. The DNA above is canonical and should not be edited without explicit instruction.

### Active Workstream: Screener Backtesting & Tuning (v2 LOCKED)

**Status:** v2 FINAL configuration locked on 10 May 2026. Promoted to live code in `chartink_replay.py` (`SCAN_PARAMS_VERSION = "v2_FINAL_20260510"`) and `v2_fixes.py` (`pos_accum_rsi_nullout` flag default flipped to `True`). Pine v2.7 / v3.8 + Streamlit verified in sync.

**Engine:** `validation.py` + `chartink_replay.py` (Layer 1) → `matcher_replay.py` conviction filter (Layer 2, min_conviction=6.0) → `bull_screener` Top-N=10 (Layer 3). 12 monthly anchors from 2025-04-15 through 2026-03-16, 30-day forward window, benchmark = `^CRSLDX` (Nifty 500). Average ~23 candidates per anchor survive both filters.

### v2 LOCK summary (single change from v1)

- **`v2_fixes.V2_FLAGS["pos_accum_rsi_nullout"] = True`** — POS-ACCUM catalyst score nullified when daily RSI > 50 (avoids late-stage chase trap).
- v1 Hunter / EarlyBirds parameters preserved exactly: `hunter.weekly_rsi_min=60`, `hunter.daily_adx_min=25`, `early_birds.disable_rsi=True`.

### v2 Aggregate Results (Filtered universe, Run ID 20260508_224037)

| Metric | v1 FINAL (filtered baseline) | **v2 FINAL** | Δ |
|---|---:|---:|---:|
| Alpha | 4.37% | **4.63%** | +0.26pp |
| Hit rate | 83.3% (10/12) | **83.3%** | held |
| Win rate | 59.2% | **60.0%** | +0.8pp |
| Median anchor α | 4.68% | **5.00%** | +0.32pp |

(v1 FINAL alpha 4.45 from original Run 20260508_105114; reproduced this session at 4.37 — 0.08pp drift attributed to data-cache refresh, well within noise.)

### Cross-universe verification

`pos_accum_rsi_nullout` was the **only** v2 candidate fix to clear both universes:
- Raw universe (`run_validation`, Nifty500): α 2.81 → 2.95 (+0.14pp), hit 91.7% held.
- Filtered universe (`run_chartink_validation`): α 4.37 → 4.63 (+0.26pp), hit 83.3% held, median α jumps 4.68 → 5.00.

Other 4 v2 candidates rejected:
- `tiebreak_rs_momentum`: drops hit-rate on both universes (raw 91.7→83.3, filtered 83.3→75.0).
- `vcp_score_multiplier` (0.5×): too aggressive — drops α on both.
- `sector_cap_top_n` (3-per-sector hard): forces lower-conviction picks at strong-sector anchors.
- `days_since_pivot_penalty`: universe-dependent (raw +0.65pp, filtered −0.42pp). **Kept as runtime defensive-mode flag**, not default.

### Resolved: §8.1 baseline drift incident

Apparent gap of 4.45 (v1 FINAL) vs 2.61 (initial v2 ablation baseline) was decomposed into:
- **Apples-to-oranges (1.64pp):** v1 FINAL ran via `run_chartink_validation` (filtered); initial ablation ran via `run_validation` (raw). Different validators, different baselines.
- **Real hook drift (0.20pp):** `v2_fixes.select_top_n` used `kind="mergesort"` + `reset_index()` even with all flags off, vs the validation.py fallback's plain quicksort. Tiebreak winners differed at tied Scores.
- **Fix:** added fast-path early-return at the top of `select_top_n` so an all-flags-off invocation is byte-identical to the fallback expression.

### Authoritative Artifacts (canonical for v2)

| File | Role |
|---|---|
| `validation_runs/v2_ablation_results.csv` | Raw universe ablation (6 cells) |
| `validation_runs/v2_ablation_filtered_results.csv` | Filtered universe ablation (6 cells) |
| `validation_runs/validation_20260508_224037_*` | v2 FINAL filtered run (Top-N=10, 12 anchors) |
| `validation_runs/validation_20260510_064122_*` | Clean baseline reproduction (hook-neutered, raw) |
| `BACKTEST_RESULTS_v2.docx` | Institutional report locking v2 (10 May 2026 deliverable) |
| `BACKTEST_RESULTS_v2_SESSION.md` | Full mutable session findings (markdown source for the docx) |
| `BACKTEST_RESULTS_v1.docx` | Prior v1 lock report (preserved) |
| `validation_runs/LAST_RUN.txt` | Pointer (still v1 FINAL `20260508_105114`; bump after confirming filtered run is the canonical artifact) |

### v2 Pine + Streamlit signal-surface sync (10 May 2026)

Both v1 FINAL Hunter parameters AND the v2 LOCK (`pos_accum_rsi_nullout`) are now propagated to **all** Pine surfaces — screeners AND the unified strategy. Zero signal drift between Python and TradingView.

**Screeners (display indicators):**
- **`Commander_Screener_Beta_Edition_v2.9.pine`** (file renamed from v2.6 → v2.9) — Cumulative chain: v2.7 added Hunter inputs + ADX numeric gate on POS-BO; v2.8 added POS-ACCUM RSI gate; **v2.9 added Python-aligned `pyScore` (mirrors `bull_screener.calculate_score()` exactly: catalyst tier + Stage 2 + Mansfield RS + Mansfield 4w momentum + RRG + volume + sector strength + trend template + 52W distance, clamped [0,100]) plus a defensive `days_since_pivot_penalty` toggle**. New input `use_python_aligned_score` (default TRUE) overwrites the displayed `score` with `pyScore` for cross-platform consistency; native Pine `score` preserved when toggle is OFF.
- `Commander_Screener_Dashboard_ULTIMATE_v3.7.pine` → **v3.9** — v3.8 same Hunter sync (uses `RSI(70)` as weekly proxy); v3.9 POS-ACCUM (catId=1) gated on `_rsi <= pos_accum_rsi_max`.
- `Commander_Capitulation_Screener_v1.5.pine` → no change (no Hunter/POS-BO logic).

**Strategy (live execution):**
- `Weinstein_Unified_Ecosystem_v2.2.pine` (file) → indicator title **v2.3**. Single canonical strategy file (Minervini Bull + Recovery, merged). Three changes:
  - New input group "Bull: v1+v2 Locked Filters" surfaces `hunter_weekly_rsi_min=60`, `hunter_daily_adx_min=25`, `pos_accum_rsi_max=50`.
  - Numeric ADX added via `ta.dmi(14, 14)` — `adx_val` captured; existing `adx_strong` boolean preserved for backward compatibility with `alpha_score`.
  - `pos_bo_trigger` now requires `wRSI >= hunter_weekly_rsi_min AND adx_val >= hunter_daily_adx_min`.
  - `pos_ac_trigger` now requires `d_rsi <= pos_accum_rsi_max`.

**Streamlit / watchlist tools:**
- `weinstein_commander_web_v4.0.py` → no change required (consumes CSV outputs of the Python pipeline; auto-tracks).
- `watchlist_manager.py` / `watchlist_ranker.py` → no change required (CSV-driven).

**Legacy file cleanup (10 May 2026):** All standalone `Weinstein_Minervini_Strategy*.pine` and `Weinstein_Recovery_Strategy*.pine` files deleted from project root. The Unified Ecosystem v2.2 is the sole canonical strategy file.

**Architectural note on the POS-ACCUM mirror:** Python implements the v2 fix as a score nullification (Score += 0 instead of +15) while keeping the POS-ACCUM label. Pine's `alphaScore` has no equivalent +15 catalyst boost, so all three Pine surfaces (Beta v2.8, Dashboard v3.9, Unified v2.3) gate the trigger condition itself — slightly stricter (suppresses the label too) but produces the same downstream effect on pick selection. Each Pine surface exposes `pos_accum_rsi_max` as a tunable input so the threshold stays in sync if Python's `V2_PARAMS["pos_accum_rsi_threshold"]` is ever changed.

### Current Repo Structure (top level)

```
GeminiVSCode/
├── CLAUDE.md                                  ← this file
├── BACKTEST_RESULTS_v1.docx                   ← v1 lock report (NEW)
├── validation.py                              ← walk-forward harness
├── chartink_replay.py                         ← Python port of 4 bull Chartink scans
├── data_provider.py                           ← pinnable date-aware OHLCV provider
├── weinstein_commander_web_v4.0.py            ← Streamlit dashboard
├── weinstein_xray_screener.py                 ← X-ray screener
├── watchlist_manager.py / watchlist_ranker.py ← TV watchlist sync
├── Commander_Capitulation_Screener_v1.5.pine  ← Pine: capitulation/recovery
├── Commander_Screener_Beta_Edition_v2.6.pine  ← Pine: bull screener
├── Commander_Screener_Dashboard_ULTIMATE_v3.7.pine ← Pine: dashboard
├── Commander_Risk_Allocator_v1.0.pine         ← Pine: position sizer
├── My Portfolio.csv                           ← 21 active holdings
├── MASTER_Golden_Picks.csv                    ← latest top-conviction picks
├── FINAL_*.csv                                ← matcher output watchlists
│
├── validation_runs/                           ← all backtest outputs (10+ runs today)
├── replay_runs/                               ← per-anchor candidate snapshots
├── logs/                                      ← run logs (final_candidate_config, ablation, sweeps, scheduler)
├── docs/                                      ← 14 component user guides (00_INDEX.md is master)
├── data/                                      ← cached OHLCV
├── reports/                                   ← generated analysis output
├── Generated_Watchlists/                      ← daily TV-importable .txt files
├── pages/                                     ← Streamlit multi-page extras
└── (browser automation: Strike/, TV/, dhan_session/, *_user_data/)
```

### Active Portfolio Snapshot (read-only context)

21 holdings, mixed equity + ETFs. Notable distress for Stage 3/4 review: **HCLTECH −19%**, **HINDCOPPER −15%**, **SILVERBEES −28%**, **ITBEES −24%**, **CITYUNIONBK −12%**, **BHARTIARTL −11%**, **L&T −11%**. HCLTECH appearing as both a portfolio drag AND the #1 ranking failure in the Jan-15-26 forensic is the most actionable signal: same name failing in two independent ways argues for explicit exit.

### Today's Master Golden Picks (8 May 2026)

17 names from `MASTER_Golden_Picks.csv`: **WOCKPHARMA, NETWEB, NAM-INDIA, GRSE, GRANULES, ACUTAAS, NAVINFLUOR, GVT&D, ENRIN, CGPOWER, RADICO, VIJAYA, DIVISLAB, RRKABEL, ELGIEQUIP, GABRIEL, LALPATHLAB.** Conviction range 5.0–8.5. WOCKPHARMA, NETWEB, ACUTAAS, NAVINFLUOR, GVT&D, ENRIN top the list at 8.5.

---

## Next Specific Implementation Steps

### Phase A — Promote FINAL config to live signal surfaces (signal-drift critical)

Per the DNA's "signal consistency is sacred" rule, the v1 parameter triplet must be applied identically everywhere signals are generated:

1. **`Commander_Screener_Beta_Edition_v2.6.pine`** — locate Hunter scan inputs and update:
   - `weekly_rsi_min` input default from `55` → `60`
   - `daily_adx_min` input default from `20` → `25`
   - Locate Early Birds scan and add/toggle the `disable_rsi` flag to `true` (or comment out the RSI gate).
   - Bump version comment to `v2.7` and tag commit.

2. **`Commander_Capitulation_Screener_v1.5.pine`** — apply same Hunter parameter changes if it shares Hunter logic; verify EB section matches.

3. **`Commander_Screener_Dashboard_ULTIMATE_v3.7.pine`** — propagate the same triplet so dashboard cells render against the new thresholds. Bump to `v3.8`.

4. **`weinstein_commander_web_v4.0.py`** — update Streamlit defaults block AND any UI input widgets so analysts see/use the v1 thresholds. Search for `weekly_rsi_min`, `daily_adx_min`, `disable_rsi` and align defaults.

5. **`watchlist_manager.py` / `watchlist_ranker.py`** — confirm they consume the updated Pine alert/CSV outputs without hard-coded thresholds. If they reimplement filters, bring those in line.

6. **Sanity check via diff:** Run a single-symbol comparison across Pine alerts, Streamlit screen, and `chartink_replay.qualifies_hunter()` on one or two known qualifiers. Outputs MUST agree (zero signal drift).

7. **Commit message:** `feat(screener): lock v1 FINAL config — Hunter RSI=60, ADX=25, EB.disable_rsi=True`

### Phase B — v2 candidate fixes (next backtest iteration)

Drafted in `BACKTEST_RESULTS_v1.docx` Section 7. To test sequentially as ablation cells against the v1 FINAL baseline:

1. **VCP_Valid as 0.5x score multiplier** — penalize the structural-failure mode that put 9/10 of Jan-15-26 picks through with `VCP_Valid=False`.
2. **Days_Since_Pivot > 30 → −10 score penalty** — de-rank chases of extended bases (HCLTECH 38d, EMCURE 33d, AIIL 48d, SBILIFE 115d).
3. **Sector cap of 3 picks per sector in Top-N** — force diversification; would have surfaced the metals/PSU-bank rotation in Jan-Feb 26.
4. **POS-ACCUM null-out when RSI > 50** — prevents late-stage catalyst trap (HCLTECH-style #1 ranking failure).
5. **Tiebreak by RS_Momentum_4W (descending)** when Score is tied — replaces what currently looks like insertion-order tiebreak.

Each fix should be a separate ablation cell with its own run_id; only commit a fix to FINAL if it preserves hit-rate ≥ 91.7% AND lifts alpha.

### Phase C — Sensitivity grid around v1 optimum

To confirm the converged point isn't a noisy local maximum, run a 3×3 grid:

| | ADX 20 | ADX 25 | ADX 30 |
|---|---|---|---|
| **RSI 55** | (baseline-ish) | | |
| **RSI 60** | | **FINAL** | |
| **RSI 65** | | | |

Pass/fail criterion: FINAL must remain at or near the joint optimum on (alpha, hit-rate). If a neighboring cell beats it materially, re-locate.

### Phase D — Forensic close-out on HCLTECH

The same name (HCLTECH) is currently the #1 portfolio drag (−19%) AND the #1 ranking failure in the Jan-15-26 forensic. Before this becomes Phase A's first regression test, run:

1. Weinstein stage classification of HCLTECH on weekly chart today (likely Stage 3 or early Stage 4).
2. Apply the Sell-to-Buy Capital Rotation Matrix: which of the 17 Master Golden Picks would receive freed capital? (Top candidates by conviction: WOCKPHARMA 8.5, NETWEB 8.5, ACUTAAS 8.5, NAVINFLUOR 8.5, GVT&D 8.5, ENRIN 8.5.)
3. Stage exit memo with ATR-trailed stop confirming the position is in violation of "no Stage 3 holds."

### Phase E — Schedule the validation as a recurring task

Make the 12-anchor walk-forward run automatically on a monthly cadence (1st trading day of each month), so the FINAL config is continuously stress-tested against fresh out-of-sample anchors. Use `mcp__scheduled-tasks__create_scheduled_task` once Phase A is committed.

---

## Open Questions / Decisions Pending

- Is HCLTECH a held-on-thesis position or a forced exit? (Phase D resolves.)
- Should v2 fixes (Phase B) be batched into a single ablation pass or applied sequentially with intermediate locks?
- Top-N=10 vs Top-N=15: the Jan-15-26 counterfactual showed N=15 would have flipped that anchor to a win. Worth a dedicated experiment — but increases position count and capital fragmentation.

---

---

## 11 May 2026 — Major Updates

### A. Recovery Screener RFF Strengthened to v2.0

`recovery_screener.py` `compute_rff()` rewritten to match (and exceed) the
Pine Unified Ecosystem strategy v2.2 fundamental gate. Pine **Capitulation
Screener** (`Commander_Capitulation_Screener_v1.5.pine`) is constrained by
TradingView's 5-call `request.financial()` ceiling to a 2-check "RFF Lite"
(NI>0 + OCF>0); Python is the only place with no platform constraint and
now carries the heaviest fundamental check.

**Tier A (0-6) — Pine-parity fundamental gate (exact match to strategy v2.2):**

| Check | Threshold | Source |
|---|---|---|
| NI > 0 | net income positive | yf TTM cashflow |
| **FCF > 0** | OCF − \|CapEx\| (was OCF>0 — upgraded) | yf TTM cashflow + `quarterly_cashflow` walk |
| **ICR > 3.5** | EBITDA / interest (was >2 — tightened to Pine) | yf info |
| D/E < 2 | debt / equity | yf info |
| CR > 1 | current ratio | yf info |
| ROA > 5% | return on assets | yf info |

**Tier B (0-4) — recovery-specific bonus (Python-only; Pine cannot compute):**

| Check | Captures |
|---|---|
| **Sales↑** Qtr Sales Var > 0 | Top-line turning |
| **Profit↑** Qtr Profit Var > 0 | Bottom-line turning |
| **OpLev↑** Profit growth > Sales growth (or OPM expanding) | Margins recovering |
| **Deleverage** D/E now < D/E prior year | Balance-sheet repair |

**New output columns:** `RFF_Base` (0-6), `RFF_Bonus` (0-4), `RFF_Total` (0-10),
`RFF_Quality` (FULL / PARTIAL / INSUFFICIENT). `RFF_Score` preserved as alias
for `RFF_Base` (back-compat). Composite `compute_score()` fundamentals slot
expanded **6 → 8** to absorb up to +2 of the bonus.

**Data-sufficiency gate added:** if <3 of the 6 base fields are populated, returns
quality=INSUFFICIENT and base=0 instead of letting NaN→0 silently bias the score.
This is the same gate Pine uses (`rff_has_data ≥ 3`).

**TTM data alignment:** Python now sums last 4 quarters of `quarterly_cashflow`
for OCF + CapEx — matches Pine Capitulation Screener's TTM window choice
(v1.3+), beats yfinance's stale point-in-time `info` snapshots.

### B. ETF Trading System (Phases 1-4 SHIPPED)

Full parallel pipeline to the stock system, dedicated to NSE ETFs. All four
phases complete and syntax-clean.

| Phase | File(s) | Lines | Purpose |
|---|---|---|---|
| **P1 Universe** | `etf_universe.py` | ~190 | 55 curated NSE ETFs with category metadata (BROAD_EQUITY 9 / SECTOR 20 / SMART_BETA 5 / INTERNATIONAL 5 / COMMODITY 7 / DEBT 5 / THEMATIC 4). Each entry: `asset_class / sub_category / underlying / issuer / benchmark_yf / liquidity_tier`. |
| **P1 Screener** | `etf_screener.py` | ~340 | Per-ETF 4-axis scoring (Liquidity / Trend / RS / Rotation, each 0-10, total 0-40). Outputs `ETF_Screener_Results.csv`. Signal labels: 🟢 BUY-LEADER / 🟡 ACCUMULATE / 🟡 EARLY-BASE / 🟠 HOLD-WATCH / 🔴 AVOID-DOWNTREND / ⚠ ILLIQUID / ⚪ NEUTRAL. |
| **P2 Rotation** | `etf_rotation.py` | ~400 | Sector rotation table (composite RS 60% 12W + 40% 4W) + asset-class regime detector (RISK_ON / GOLD_LED / INTL_LED / RISK_OFF / MIXED) + RRG coordinates (8-week tail) + unified top-picks per regime. Outputs 4 CSVs. |
| **P3 Pine Dashboard** | `Commander_ETF_Dashboard_v1.0.pine` | ~280 | TradingView v6 dashboard. Stage badge, 30W MA overlay (weekly via `request.security`), Mansfield RS (×100), RRG quadrant, liquidity score, 52WH distance, 4 alerts. **Signal logic identical to Python** per zero-drift rule. |
| **P4 Commander Web** | `weinstein_commander_web_v4.0.py` (new ETF page) | ~280 | New 🪙 ETF entry under DISCOVERY group. 4 tabs: 🎯 Top Picks · 🔄 Sector Rotation · 📊 Asset-Class Regime (with allocation donut) · 💧 Liquidity & Universe (filterable). File-status strip + 🔄 Run-All button. |

**Why ETFs got a parallel pipeline (not a re-skin):**
- Alpha source = sector/asset-class rotation, not stock picking
- No fundamentals (RFF doesn't apply)
- Liquidity is the #1 risk (half of NSE ETFs trade <₹1Cr/day)
- Stage analysis is **cleaner** on ETFs (no idiosyncratic news noise)
- Sizing should be volatility-bucket based (gold 0.6% vol ≠ smallcap 1.8% vol)

**Benchmark choice:** `^CRSLDX` (Nifty 500) — same as stock system, so RS
comparisons are cross-comparable.

**Asset-class flagships (regime engine anchors):** NIFTYBEES, JUNIORBEES,
MID150BEES, GOLDBEES, SILVERBEES, MON100, MAFANG, LIQUIDBEES, BBETF.

**Operational cadence:** Run `python etf_screener.py && python etf_rotation.py`
weekly (Sunday evening) OR click 🔄 Run All in Commander Web.

### C. Hedge-Fund Analyst Critique + 6-Phase Fine-Tuning Roadmap

Independent assessment of the ecosystem produced this scorecard:

| Dimension | Grade |
|---|---|
| Architecture & UX | A− |
| Signal generation | B |
| Backtest rigor | C+ |
| Risk management | C |
| Data integrity | C |
| Execution quality | B− |
| Performance attribution | D+ |
| **Overall** | **B− system, A potential** |

**Five silent killers identified:**
1. Silent fallbacks biasing every signal upward (NaN→0 patterns)
2. Scoring weights are folklore, not fitted (50/50 Conviction:Tech_Score asserted, never optimized)
3. Zero correlation control in 21-stock book (effective N may be ~4)
4. Backtest has no walk-forward and no slippage model
5. ET/MC sentiment is regex over prose — needs validation before promotion to scoring input

**6-phase fine-tuning roadmap (~108 hours over 18 weeks):**

| Phase | Weeks | Deliverable | Impact |
|---|---|---|---|
| **0 — Attribution** | 1-2 | `performance_attribution.py` — P&L decomposition by Stage/RS/Sector/Hold/Score/Regime | Visibility |
| **1 — Data Integrity** | 3-4 | Audit silent fallbacks, add `data_quality` column, fix survivorship bias | −10-15% false positives |
| **2 — Backtest Rigor** | 5-8 | Slippage model, walk-forward harness, survivorship-correct rebalance | True Sharpe revealed |
| **3 — Fitted Weights** | 9-11 | Constrained grid search per setup type; lock per-setup `weights_*.json` | +20% Sharpe (OOS) |
| **4 — Portfolio Risk** | 12-14 | `correlation_gate.py`, sector cap 25%, regime-conditional sizing | −25% max DD |
| **5 — Sentiment + Ops** | 15-18 | Hand-label parser validation (≥85% precision), execution audit, nightly health monitor | Sentiment promoted from noise → veto |

**Hard gate after Phase 2:** if OOS Sharpe < 60% of in-sample across walk-forward
windows → **stop**. System is overfit; re-architect screener before continuing.

**The single sentence to remember:** *I am not adding features. I am compounding rigor.*

### D. Bug Fixes & UI Improvements (10-11 May 2026 batch)

**`weinstein_commander_web_v4.0.py`:**
- Removed duplicate Sentiment panel (KeyError on missing `consensus`); helper-based panel at line ~2406 retained
- Added `generate_portfolio_review` to top-level `gemini_reporter` imports (NameError fix in AI Lab)
- Smart Rank: 2-decimal formatting on numeric columns
- Portfolio Overview: live-price fallback tracking (`fallback_symbols`) + UI warning + "—" for unrealised P&L when ALL positions failed (was showing "+0.00%")
- Macro → Global Indices: 2-decimal formatting on LTP / 52WHigh / 52WLow
- Breadth → McClellan: stale warning reading `mcclellan_state.json` ("Last calc DD-MMM (Xd ago, MSI=±N)") + amber banner if >7 days
- Fetch GTTs: changed `get_gtt_list()` → `get_forever()` (Dhan SDK rename), updated response shape mapping (`tradingSymbol`, `transactionType`, `orderType`, `legName`, `triggerPrice`)
- Options Live Chain: empty-data fallback in `nse_options.py` (live fetch returning empty now falls back to cache OR shows off-hours message)
- Autopsy → Sectors: added Sector Coverage view (all 19 NSE sectors, ✅ Traded / ⚪ Untraded badges + trade counts)
- **NEWS / PRE-MARKET / POST-MARKET pages:** new shared helper `_render_paid_news_grid()` (200 lines) + tabs added:
  - NEWS → 💎 ET Prime + MC Pro tab (full feed, 4-column grid)
  - PRE-MARKET → 💎 ET + MC Pro tab (filtered to opening/overnight/GIFT Nifty/morning brief headlines)
  - POST-MARKET → 💎 ET + MC Pro tab (filtered to closing-bell/EOD/market-wrap headlines)
  - Cookie status row (🟢 fresh / 🟡 stale / 🔴 missing) with age in days
  - Cards colour-coded by analyst action (Strong Buy → green; Sell → red), brokerage badge, stock pills

**`watchlist_ranker.py`:**
- Fixed Stage 1 ↔ Stage 3 label swap (was incorrectly classifying basing as topping)
- Added explicit NaN-SMA200 check (was silently dropping stocks with <200d history into Stage 4)

**`portfolio_analytics.py`:**
- Live-price fallback tracking (`live_price_failures`, `live_price_ok_count`) + per-position `price_source` flag

### E. Focused Resources for Continued Learning

Curated reading list provided (Tier 1 = Carver *Systematic Trading*, López de
Prado *Advances in Financial Machine Learning*, Clenow *Stocks on the Move*,
Pedersen *Efficiently Inefficient*, Ilmanen *Expected Returns*). Free
institutional-grade research at AQR (`aqr.com/Insights/Research`) and Newfound
Research (Hoffstein) bookmarked. CMT credential noted as best-ROI for the
profile. **Reading cadence aligned to roadmap phases** so each month's reading
reinforces that month's implementation work.

### F. Architectural State — End of 11 May 2026

| Layer | Status |
|---|---|
| Stock System (Bull / Recovery / Golden / X-Ray) | ✅ Production, v2 LOCKED |
| Recovery RFF | ✅ v2.0 — Pine-parity + Tier-B bonus |
| ETF System (Universe / Screener / Rotation / Pine / Web) | ✅ Production, P1-P4 shipped |
| ET + MC paid news integration | ✅ Wired into 4 surfaces (Bull, Recovery, X-Ray, Golden + NEWS/PRE/POST) |
| Pine ↔ Python ↔ Web zero-drift sync | ✅ Verified (Stock + ETF) |
| Performance Attribution module | ⏳ Phase 0 of 6-phase roadmap |
| Walk-forward backtest harness | ⏳ Phase 2 of 6-phase roadmap |
| Correlation gating | ⏳ Phase 4 of 6-phase roadmap |

**Next priority work:** Phase 0 of the fine-tuning roadmap —
`performance_attribution.py`. Should attribute P&L across **both** stock and
ETF closed-trades logs in a unified view.

---

## 13 May 2026 — Institutional Zone Engine v4.2 + Dashboard Panel Dedup

### A. Institutional Zone Engine v4.2 (NEW Pine indicator)

**File:** `Institutional Zone Engine & Webhook Trigger.pine`
**Status:** Production-ready (Pine v6). Full coverage of the documented zone-marking methodology.
**Purpose:** Automates the right-to-left supply/demand zone marking + qualification workflow.

**Methodology coverage — END TO END:**

| Spec area | Implementation |
|---|---|
| Leg candle | body ≥ 0.75 × range AND TR > ercMult × ATR. Average legs (0.60-0.75) accepted with strong follow-through rescue (cumulative post-leg-out move > 1 × ATR) |
| Base candle | body ≤ 0.50 × range OR small range (TR < 0.6 × ATR). 1-6 candles, sweet-spot 2-4 weighted highest in score |
| Leg-In validation | Must qualify as leg candle in correct direction. Rejects small candles even with full body |
| 4 patterns | DBR / RBR / RBD / DBD — identified from leg-in's color |
| Per-pattern distal | DBR & RBD → full formation (incl. leg-in); RBR & DBD → base + leg-out only |
| Invisible candles | Single checkbox drives BOTH zone classification (gap-bridged OHLC) AND chart display (plotcandle overlay) |
| Multi-Timeframe | Daily / Weekly / Monthly zones via `request.security`. HTF visible on LTF only — auto-gated by `timeframe.in_seconds()` comparison |
| Strong-Zone criteria (all 4) | (a) strong leg-out gate, (b) avg leg + strong FT rescue path, (c) gap bonus, (d) multi-pivot break bonus |
| Controlling-Zone criteria (all 3) | (1) new ATH/ATL print, (2) 50-SMA trend shift after 20 bars, (3) breaks opposing controlling zone (cross-zone check) |
| Controlling treatment | 2 max touches (vs 1 for normal), thicker border, label prefix "Controlling Weekly DZ" / "Controlling Monthly SZ" etc. |
| EMA20 directional confluence | DZ near/below EMA20 = full bonus, over-extended above = no bonus. SZ mirror. "Just above the DZ" classified as nearby (configurable threshold). |
| Zone violations | Red ✗ marker at breakage bar + red border + faint red fill |
| Reversal patterns at touches | Hammer / BullEngulf / Doji / ShootStar / BearEngulf — triangle marker + alert |

**Zone label format:** `          Monthly DZ` / `          Controlling Weekly SZ` etc. — left-aligned, 10-space indent per spec.

**Trade Intelligence Panel** (right-side, configurable position):
- **Price & Context**: LTP · Daily EMA20 ↑/↓ · RS vs N500 ↑/↓ · Bias (BULLISH/BEARISH/MIXED)
- **Active Zones**: counts per TF (Chart/Daily/Weekly/Monthly) split DZ vs SZ, plus Controlling total
- **Demand Below + Supply Above**: nearest zone in each direction with quality grade (EXCELLENT 90+ / STRONG 75-89 / GOOD 60-74 / AVERAGE 45-59 / WEAK <45), prox/distal levels, distance %, fresh/tested status
- **Setup Analysis**: position (IN DZ / IN SZ / APPROACHING / BETWEEN / NO ZONES) + action recommendation (🟢 STRONG LONG / 🔴 STRONG SHORT / 👀 WATCH / ⚪ NEUTRAL / 💤 WAIT) + reason
- **Trade Plan** (conditional on fresh actionable setup): Entry / SL with risk % / T1-T3 (1R-3R) / R:R to opposing zone (color-coded ≥2 green, ≥1 yellow, <1 red)

**Webhook payload schema** (alert frequency: once per bar close):

```json
{
  "ticker": "RELIANCE",
  "event": "DEMAND_TOUCH",
  "tf": "W",
  "controlling": true,
  "breaksOpposing": false,
  "touch": 1, "of": 2,
  "strength": 92, "raw": 78, "confluenceBoost": 14,
  "pattern": "DBR",
  "reversal": "Hammer", "confirmed": true,
  "proximal": 1234.50, "distal": 1218.20,
  "entry": 1234.50, "sl": 1210.85,
  "t1": 1258.20, "t2": 1281.90, "t3": 1305.60,
  "riskPerUnit": 23.65, "riskPct": 1.92,
  "chartTf": "75",
  "ts": 1747200000000
}
```

**Architectural choices:**
- Universal `f_detectZone()` function called both natively AND via `request.security()` for Daily/Weekly/Monthly — **single source of truth** across TFs
- Per-TF `var` state (ATH, ATL, pivots, signal-time) maintained per call context
- Cross-zone "breaks opposing controlling" check runs at zone creation against the chart-level `activeZones` array
- na-guards on all UDT field accesses from `request.security` (Pine v6 warmup-bar quirk)

**Interpretive choices documented in file header (lines 5-90):**
- Right-to-left scan = natural via Pine series indexing (`high[1]` IS the prior bar)
- "Nearby" and "much below" EMA20 collapse into single full-bonus tier
- RBD distal uses leg-in (symmetric with DBR exhaustion-print rule, NOT the "base only" override)
- Proximal/distal drawn as box edges, functionally identical to lines

### B. Dashboard Panel Dedup (4 Pine files)

Cross-module panel dedup pass to eliminate fields shown redundantly when multiple indicators load on the same chart:

| File | Fields removed | Rationale |
|---|---|---|
| `Weinstein_Unified_Ecosystem_v2.3.pine` | Market Health, RS Quadrant, Sector Stage, Inst. Accumulation, VCP / Tight Base, CPR / MVWAP | Already shown in v67 Dashboard (more detailed) |
| `Commander_Screener_Beta_Edition_v2.9.pine` | PERSONA, STYLE | Already shown in v67 Dashboard |
| `Commander_Capitulation_Screener_v1.5.pine` | REL VOLUME | Already shown in Screener Beta |

`Weinstein and Swing Pro Dashboard v67.0.pine` was preserved unchanged as the **primary trade dashboard** — authoritative source for all the removed fields.

**Untouched files (per explicit instruction):** `Wesinstein Swing Zigzag [Strict v6.0].pine`, `Weinstein_Context_Layers_v1.0.pine`, `Commander_Risk_Allocator_v1.0.pine`.

The Unified Ecosystem retains its unique composite fields: Alpha Score, Stage 2 Freshness, Base Confirmed, Trend Coiling, Volatility Squeeze, Positional Signals, Swing Signals, plus the entire Recovery section.

### C. Architectural state — End of 13 May 2026

| Layer | Status |
|---|---|
| Stock System (Bull / Recovery / Golden / X-Ray) | ✅ Production, v2 LOCKED |
| Recovery RFF | ✅ v2.0 — Pine-parity + Tier-B bonus |
| ETF System (Universe / Screener / Rotation / Pine / Web) | ✅ Production, P1-P4 shipped |
| **Institutional Zone Engine** | ✅ **v4.2 SHIPPED — full methodology coverage** |
| **Dashboard Panel Dedup** | ✅ **4-file pass complete** |
| ET + MC paid news integration | ✅ Wired into 4 surfaces |
| Pine ↔ Python ↔ Web zero-drift sync | ✅ Verified (Stock + ETF) |
| Performance Attribution module | ⏳ Phase 0 of 6-phase roadmap (still pending) |
| Walk-forward backtest harness | ⏳ Phase 2 of 6-phase roadmap |
| Correlation gating | ⏳ Phase 4 of 6-phase roadmap |

**Next priority work** (unchanged from 11 May): Phase 0 — `performance_attribution.py`. The Zone Engine work was a parallel deliverable, not a substitute for the fine-tuning roadmap.

---

## 21–22 May 2026 — Validation Framework Campaign

### Scope
A 3-day campaign on `validation.py` / `replay.py` to give the screener honest, properly-windowed measurement — and a series of rollbacks of premature catalyst removals that had been based on the broken (single 30-day forward window) measurement.

### What landed (KEEP — these are operational improvements)

1. **Realistic execution simulator** — `replay.py v2.6` → bar-by-bar SL/T1/T2/Chandelier-trail with 0.10%/leg commission. Adds `Sharpe`, `Sortino`, `Calmar` per anchor.
2. **Catalyst-aware forward windows** — `replay.py v2.8` exports `FWD_DAYS_BY_CATALYST` (POS-BO=120d, POS-ACCUM=180d, WYC-*=120d, REV-*=90d, SWG-*=30d). Activate in CLI via `--catalyst_windows`. Per-trade matched-horizon alpha in `Alpha_Matched_pct` column.
3. **Bootstrap CI** — `validation.py v2.7` → `--bootstrap_n 10000` produces `alpha_ci95_low`, `alpha_ci95_high`, `alpha_prob_positive_pct`. Every alpha claim now ships with a CI.
4. **Catalyst-aware SL discipline** — `bull_screener.py v1.11`: ATR multiplier scales with horizon (POS=4.0×, WYC=3.5×, REV=2.5×, SWG=1.5×). `recovery_screener.py v1.6`: safety-floor widened 1.5×→2.5× for REV-*. `Weinstein_Unified_Ecosystem_v2.8.3.pine v3.6`: catalyst-aware fallback ATR multipliers when structural SL is invalid.
5. **Split SL flags** — `replay.py v2.9`: simulator now distinguishes `Hit_Initial_SL` (true loss) from `Hit_Trail_SL` (often profit-protect exit). Legacy `Hit_SL` retained for back-compat but is over-broad — don't use it as primary failure metric.
6. **Sector DB backfill** — `sectors.db` got 128 missing mappings (HYUNDAI, IREDA, NTPCGREEN, OLAELEC, JSWCEMENT, etc.) plus 2 new sector_meta rows (`NSE:CNXCONSUM` → `^CNXCONSUM`, `NSE:CNXCOMMODITIES` → `^CNXCMDT`). Coverage now 100% of nifty500.
7. **Opt-in risk overlays** (instrumented but not recommended as defaults):
   - `--top_n N` + `--sector_cap K` — max picks/sector
   - `--kill_switch_dd PCT` + `--kill_switch_losses N` — equity-curve kill switch with per-halt peak reset (fixed the v1 cascade bug)
   - `--sector_rotation strict|soft` — drop picks whose sector isn't LEADING (or LEADING+IMPROVING) per JdK 1-pass RRG
8. **New module** — `sector_rotation.py v1.0` — RRG-based sector overlay using canonical `bull_screener.compute_weekly_indicators` (zero formula drift).

### What got ROLLED BACK (these had been wrong)

| Module | Was | Now | Why rollback |
|---|---|---|---|
| `bull_screener.py` v1.8 | POS-ACCUM disabled (`False and …`) | **POS-ACCUM RE-ENABLED** (v1.10) | v1.8 disable was based on 30d forward window measuring a 180d Stage 1→2 setup |
| `recovery_screener.py` v1.4 | "RETIRED — coin flip" header | **v1.5 RE-INSTATED** | Same 30d-window error; REV-* needs 90d to play out |
| `Weinstein_Unified_Ecosystem` v3.4 | POS-ACCUM + REV-* removed from `trigger_bull_raw`/`trigger_rec_raw` | **v3.5 RE-ADDED** (Wyckoff stays additive) | Same root cause |
| `Commander_Bull_Screener` v3.2 | `if false and is_pos_accum` guard | **v3.3 trigger active** | Same |

The Wyckoff implementation (`recovery_screener_v3_wyckoff.py`, `WYC-SPRING/SOS/JAC`) is **preserved and additive** alongside REV-*, not a replacement.

### The Lesson (saved to permanent memory)

`~/.claude/projects/.../memory/validation_window_mismatch_warning.md` captures this: **NEVER recommend catalyst removal from a 30-day backtest.** Positional/Wyckoff/recovery setups need 90-180d forward windows. If the window doesn't match the trade's design horizon, the test is invalid — state that and stop, do not propose removals. Gemini independently confirmed: Minervini+VCP is highly viable on Indian midcap/smallcap; rigid algorithmic backtests can't validate discretionary visual patterns.

### Honest Performance Baseline (current — for comparison later)

`python -u validation.py --months 18 --universe nifty500 --catalyst_windows --bootstrap_n 10000` on the rolled-back screener (n=132 trades, 14 anchors, 8 active):
- Mean matched alpha: **+0.90% to +1.10%** per trade
- Cumulative alpha: **+8.84%**
- Sharpe: **−1.90** (with catalyst-aware SLs; was −2.71 before SL fix)
- Bootstrap CI95: **[−1.66%, +3.63%]** — straddles zero; small-sample
- **Probability of positive true alpha: ~74%** — directional but not statistically confirmed
- POS trades now hold ~40-46 days average (was ~5 days before SL fix) — initial SL hit rate is **0%** for POS family; all POS exits are via trail SL with ~25-30% win rate (consistent with trend-following profile)

### Failed Experiments — Do NOT Repeat

- Week-3 risk overlays (sector cap + kill switch + bootstrap) collectively REDUCED alpha and worsened Sharpe. Left in code as opt-in CLI flags only, not defaults.
- Strict sector rotation (LEADING-only) cut alpha by removing winners faster than losers.
- Hit_SL=True panic — was a labeling bug (now split into Initial vs Trail).

### Saved Memory Files
- `bull_v1_9_baseline.md` — pre-Week-3 reference numbers
- `validation_window_mismatch_warning.md` — the discipline rule
- `etf_symbol_corrections.md` — REALTY (not REALTYBEES) — pre-existing

### Documentation Updated
- `docs/11_Bull_Screener_v3_1_Guide.md` §15 — SL discipline + rollback
- `docs/09_Recovery_Screener_v1_7_Guide.md` §13 — rollback + Wyckoff variant note
- `docs/14_Unified_Ecosystem_Trading_Guide.md` §13 — v3.5/v3.6 changes
- `docs/16_Validation_Framework_Guide.md` — **NEW** complete guide for `validation.py` + `replay.py` + `sector_rotation.py`
- `docs/00_INDEX.md` — version stamps + row 16 added

### Next Priority Work
Unchanged from 11 May: Phase 0 — `performance_attribution.py`. The validation-framework work was foundational tooling and a correction of measurement, not a replacement for the broader 6-phase fine-tuning roadmap.

---

## 2 June 2026 — Phase 0 SHIPPED: Performance Attribution + Lean Journal Signal Snapshot

### Scope
Closed the long-pending Phase 0 of the 6-phase fine-tuning roadmap. Two coupled deliverables: a P&L attribution engine, and the entry-signal snapshot the engine needs to attribute by Stage / RS / Alpha / Setup.

### A. `performance_attribution.py` (NEW)
Decomposes **realized** P&L from the journal across 11 dimensions: System, Sector, Trade Type, Hold Period, Exit Reason, Trade Quality, **Setup/Catalyst, Entry Stage, Entry Alpha band, Entry RS band, Entry Conviction band**. Per-bucket n / win% / total ₹ / expectancy / profit-factor / signed-contribution.

- **Canonical P&L** byte-identical to `ai_mentor_engine.py:51-52` (zero drift). Derived metrics (realized_pnl, roi, hold_days) computed on read, never stored.
- **Honesty layer** (enforces the critique's anti-NaN→0 rule): rows with missing/zero exit price or qty are **quarantined and reported**, never zero-filled. On the real journal: only **20 of 40 CLOSED rows attributable** (3 missing buy, 17 missing exit price) — `ai_reconcile_engine.reconcile_journal_exit_prices()` would recover most.
- **contribution_pct** = signed share of **gross** |P&L| (not net) — avoids the sign-inversion that net-share produces on a net-negative book.
- Returns a dict for Streamlit; `main()` for `launch_script()`. Writes `reports/performance_attribution_*.csv` + per-trade drill-down.
- Signal dimensions read "Unspecified" for trades closed before snapshots existed — a **shrinking** coverage gap (reported via `signal_snapshot_coverage`), not imputed.

### B. Lean journal entry-signal snapshot
**Decision (Jay):** single table, no companion table, no `signal_json` blob, live data stays at display-time. Added only the **6 most important monitoring/review fields** (journal 22 → 28 cols, non-destructive migration, all 46 rows intact):
`setup · entry_stage · entry_alpha · entry_rs · entry_conviction · snapshot_meta`

- **`journal_enrichment.py` (NEW)** — `--mode migrate|backfill|symbol`. Signal values from `bull_screener.screen_symbol()` (zero-drift Pine-v67 mirror; no TradingView dependency). `snapshot_meta = "<date>|<source>"` distinguishes true-entry `recompute` from as-of-today `backfill`.
- **`dhan_journal_v7.py` synced** — `init_db` CREATE TABLE, `migrate_db` ALTER guards, `load_db` rename_map all carry the 6 fields. **Entry hook added in `upsert_trade()`**: new OPEN inserts auto-capture a true `recompute` snapshot AFTER commit/close (no lock held), fully guarded so a fetch failure never blocks the save.
- **6 open trades backfilled.** Surfaced two live **"no Stage 3/4 holds" violations**: **RELIANCE (Stage 4, alpha 20)** and **DMART (Stage 3, alpha 20)**. COALINDIA/ANANDRATHI/SAILIFE/LAURUSLABS all Stage 2.

### Known limitation (by design, not a gap)
`setup`/Catalyst is only meaningful at **true entry** (the label is live at trigger time). Backfilled open positions re-screen today and show `setup=NONE` when not currently triggering. Only new trades entered *because they triggered* will carry a setup label.

### ETF side
No real ETF closed-trades log exists yet (`etf_backtest.py` is a simulator, not fills). The attribution engine detects `ETF_Closed_Trades.csv`'s absence and reports it — does NOT fabricate ETF trades.

### Architectural state delta
| Layer | Status |
|---|---|
| **Performance Attribution module (Phase 0)** | ✅ **SHIPPED** (was ⏳ since 11 May) |
| **Journal entry-signal snapshot** | ✅ **SHIPPED — lean 6-col, auto-capture on new trades** |

### Next Priority Work
Phase 1 (Data Integrity) of the roadmap. Immediate quick win: run `reconcile_journal_exit_prices()` to recover the 17 missing-exit-price closed trades, ~doubling the attributable sample. Then revisit RELIANCE/DMART Stage-violation exits per the Sell-to-Buy rotation matrix.

---

## 2 June 2026 (cont.) — Phase 1 Data Integrity: Journal Exit Reconcile + 2 silent-bug fixes

### What happened
Ran `ai_reconcile_engine.reconcile_journal_exit_prices()` against the live Dhan API to recover the 17 missing-exit closed trades flagged by Phase 0. **Recovered 17/17 — attributable sample 20 → 37** (only 3 quarantined now, all missing buy-price).

### Two silent bugs found & fixed (both were masking the Dhan API)
1. **`ai_reconcile_engine.fetch_trade_history()` — token call outside `try`.** A stale/expired Dhan token raised out of the function and **crashed the entire reconcile** instead of degrading to local logs. Moved `ensure_valid_token()` inside the `try`; it now returns an empty frame on failure (local-log path still runs).
2. **Same function — symbol column never existed.** The trade-history API returns only `securityId` + `customSymbol` (full company NAME, e.g. "Avenue Supermarts DMart"), **no ticker**. Old code did `df['tradingSymbol'].fillna(...)` → `KeyError` → swallowed by a bare `except` → silent empty. Added **`dhan_symbols.get_nse_secid_to_symbol()`** (full NSE scrip master, equities + ETFs, cached) to resolve `securityId → tradingSymbol`. All 49 traded securityIds resolve; all 17 missing names matched.

### The finding that matters — missing data was flattering the book by ~₹4.4L
The recovered exits are dominated by the distress names (HCLTECH, HINDCOPPER, ITBEES/BANKBEES/GOLDIETF/SILVERIETF, LT, AXISBANK, CUB…), i.e. the painful exits were the ones with no recorded price. True closed-trade baseline:

| Metric | Partial (20) | **True (37)** |
|---|---:|---:|
| Total realized | −₹39,311 | **−₹4,76,150** |
| Win rate | 45% | **27%** |
| Profit factor | 0.71 | **0.23** |
| Worst trade | −₹43,239 | **−₹85,232** |

This is the critique's "silent fallbacks bias every signal upward" made concrete. **−₹4.76L realized / 27% win / 0.23 PF is the real baseline.** Reinforces the pending Stage-3/4 exits (RELIANCE, DMART + the BEES ETFs).

### Caveats / state
- **Backups preserved:** `trade_journal_v6.backup_20260602.db`, `…_prereconcile.db`. OPEN positions untouched (6).
- 2 symbols (METALIETF, HDFCSML250) had existing exits overwritten with the authoritative live-API value (more correct).
- **Known reconcile quirk (pre-existing, not introduced):** the UPDATE writes the latest exit to *all* same-symbol CLOSED rows — a symbol traded in multiple distinct lots collapses to one exit price. Harden if same-name repeat trading becomes common.
- **Cash-park exclusion:** liquid ETFs (KOTAKNIFTYLIQUIDETF / any `LIQUID*`) used to park funds when regime score = 0 are now excluded from attribution (risk-off carry, not alpha). Alpha-only baseline tightens to **36 trades / 25% win / −₹4,76,159** (the lone liquid-ETF trade was the only thing holding win-rate at 27%).

### Buy-side reconcile + tranche reconstruction (complete dataset)
Recovered the 3 remaining missing-**buy**-price rows from the authoritative Dhan raw fills:
- **DATAPATTNS (id 3):** buy ₹2,919.00 @ 2025-11-13 (qty 17) — single clean round-trip.
- **METALIETF & HDFCSML250 were sold in TRANCHES** (Jay's note) — so ids 41/42 were NOT phantom duplicates (an early read), they are the 2nd exit tranches. Raw fills confirm: METALIETF bought 17,200 @ ₹8.72 → 8,600 @ ₹10.84 (Dec) + 8,600 @ ₹12.80 (Apr); HDFCSML250 bought 4,120 (wtd-avg ₹168.31) → 2,060 @ ₹156.80 (Jan) + 2,060 @ ₹144.19 (Mar). Mapped each symbol's 2 journal rows to its 2 tranches via UPDATEs (no deletes), which also corrected the exits the symbol-wide reconcile had overwritten.
- **A DELETE of ids 41/42 was attempted then correctly blocked** by the safety classifier before the tranche fact was known — reinforces: never delete journal rows on inference.
- **Final fully-reconciled baseline: 40 closed / 0 missing / 39 attributable → −₹4,99,283 realized / 25.6% win / 0.24 PF.** (Loss grew vs −₹4.76L because HDFCSML250's full 2-tranche −₹73,405 is now captured + DATAPATTNS −₹3,602.)
- Backups: `…backup_20260602_buyrecon.db` (pre buy-side). Journal DB is data (not git-tracked); preserved via the dated backups.
- Corrected baseline saved: `reports/performance_attribution_20260602_183447.csv`.

### Full-book live Stage audit (Dhan holdings, authoritative)
Pulled the live Dhan book (token working) and ran the Stage audit across all holdings — NOT just the journal's 6 OPEN. Findings:
- **Live book = 8 equity/ETF holdings + LIQUID1 (cash park):** RELIANCE, GESHIP, NESTLEIND, NAM-INDIA, ANANDRATHI, COALINDIA, SAILIFE, LAURUSLABS.
- **Only RELIANCE violates "no Stage 3/4 holds"** — Stage 4, Alpha 20, RS 97.5 (lagging), −7.7% vs 30-WMA. Freed capital ~₹1,91,900 → rotate into 8.5-conviction Stage-2-Pullback Golden Picks (NAVINFLUOR, ACUTAAS, NEULANDLAB, POWERINDIA, NYKAA). Exit plan: hard stop ₹1,300 (20d swing low), sell into any bounce toward 30-WMA ₹1,431.
- **DMART already exited** (not in live book) — earlier journal-based DMART rec was moot; underscores trusting the broker over the journal.
- **⚠️ Journal is out of sync with the broker** (data-integrity item): live holds GESHIP/NESTLEIND/NAM-INDIA absent from journal; DMART stale-OPEN; quantities wrong (SAILIFE live 47 vs journal 163). A journal↔holdings sync routine is the next Phase-1 cleanup.

### Attribution wired into Web Commander
`performance_attribution.run_attribution()` now renders as a **5th "📐 Attribution" tab** in the AUTOPSY page (`weinstein_commander_web_v4.0.py`) — headline metrics + data-quality/honesty line (cash-park, quarantine, snapshot coverage) + per-dimension tables led by the entry-signal drivers (setup/stage/alpha/RS/conviction). Self-contained (reads the journal DB, no network).

### Journal↔Dhan daily sync — SHIPPED + SCHEDULED
`journal_sync.py` (NEW) reconciles the journal's OPEN positions to the live Dhan book every run:
- **ADD** live holdings missing from the journal (+ one as-of-today `backfill` snapshot).
- **UPDATE** qty/avg where they drift from Dhan.
- **CLOSE** journal OPENs no longer held — but ONLY with a completing SELL in the Dhan trade history (authoritative exit price/date); otherwise FLAG, never force.
- **Safety:** aborts entirely if the holdings fetch fails OR returns an empty book (an API hiccup must never read as "all sold"). Cash-park `LIQUID*` ignored both sides. `--dry-run` / `--no-close` flags.

First apply (2 Jun): ADD GESHIP/NESTLEIND/NAM-INDIA, UPDATE ANANDRATHI/SAILIFE/LAURUSLABS quantities, **CLOSE DMART @ ₹4,137.20 (2026-05-20** — recovered from trade history; it had been sold in May, stale-OPEN in the journal). Journal OPEN now = live book exactly (8 positions). Backup: `…backup_20260602_presync.db`.

**Scheduled daily:** Windows Task Scheduler task **`TradingJournal_DhanSync`** runs `run_journal_sync.bat` (→ `.venv` python → `journal_sync.py`) **daily at 4:30 PM IST** (post-close), `StartWhenAvailable` to catch up if the machine was off. Every run logs to `logs/journal_sync.log`. Verified end-to-end (idempotent: 8 live = 8 OPEN, 0 changes on re-run).

### Phase 2 (Backtest Rigor) — IS/OOS overfit HARD GATE shipped
The May campaign already had the realistic execution sim (commission+slippage 0.10%/leg), catalyst-aware forward windows, walk-forward monthly anchors, Sharpe/Sortino/Calmar, and bootstrap CI. The one missing Phase-2 deliverable — the roadmap's **hard gate** — is now built:

**`walkforward_oos.py` (NEW)** consumes a validation `*_summary.csv` (default LAST_RUN), splits anchors chronologically into in-sample (earlier 60%) and out-of-sample (later 40%), treats each anchor's `alpha_pct` as a period return, and applies the gate **OOS Sharpe ≥ 60% of IS** (with NO-EDGE / PASS / STOP verdicts; no-pick anchors dropped & reported, never zero-filled).

**First verdict (on LAST_RUN `20260521_213721`, confirmed catalyst-aware: POS-ACCUM 180d / POS-BO 120d / swing 30d — NOT a window-mismatch artifact):**
- IN-SAMPLE (2024-10 → 2025-08, 5 anchors): mean α **+2.56%**, Sharpe **+0.67**, hit 80%.
- OUT-SAMPLE (2025-09 → 2025-11, 3 anchors): mean α **−1.87%**, Sharpe **−0.59**, hit 33%.
- **VERDICT: 🔴 STOP** — edge flips negative OOS. Per the roadmap's post-Phase-2 gate, do NOT proceed to Phase 3 (fitted weights) until the edge demonstrably persists OOS.

**Caveat (important):** only 8 anchors had picks (5 IS / 3 OOS); the OOS window is a 3-month slice — directional, not final. So the gate was re-run on a wider sample (below), which SUPERSEDES this preliminary STOP.

**AUTHORITATIVE re-run — `validation.py --months 24 --universe nifty500 --catalyst_windows --bootstrap_n 10000` (run `20260602_200514`, 19 anchors, 12 with picks, 117 trades):**
- IN-SAMPLE (2024-06 → 2024-12, 7 anchors): mean α **−0.51%**, Sharpe −0.11, hit 28.6%.
- OUT-SAMPLE (2025-07 → 2025-11, 5 anchors): mean α **−2.95%**, Sharpe −0.95, hit 20.0%.
- Pooled: mean α **−1.53%**, win 21.7%, only **3/12 anchors positive-alpha**.
- **VERDICT: ⚪ NO-EDGE** — in-sample alpha is already ≤ 0, so there's nothing to overfit. The smaller run's +2.56% IS was small-sample noise. **The honest conclusion: the locked v2 config does not demonstrate a positive matched-horizon edge on a 24-month nifty500 walk-forward.** Consistent with the −₹4.99L realized journal baseline and the May campaign's Sharpe −1.90.
- **Two data flags:** (1) 7 of 19 anchors produced ZERO picks — a 6-month drought (Jan–Jun 2025) suggests the screener gates are mis-calibrated for some regimes (or a threshold/data issue). (2) Many anchors have 1–2 picks → noisy per-anchor alpha.

**Implication:** Phase 3 (fitted weights) is **premature** — fitting weights to a no-edge signal fits noise. The roadmap's hard gate did its job: STOP and diagnose the edge before weight-fitting.

### Phase 2 diagnostic — `catalyst_regime_partition.py` (NEW): the "no edge" is misleading
Partitioned the 117 matched-alpha trades by catalyst family / market direction / exit reason. Three findings that REDIRECT the work (this is NOT "re-architect everything"):

1. **Only SWG (swing) was tested.** The 24mo nifty500 run emitted ZERO POS/WYC/REV picks — so the NO-EDGE verdict applies only to **swing breakouts**. Your **core positional/Weinstein thesis was never exercised** in this run. Must investigate why the screener emitted no POS picks (gate calibration / universe / anchor spacing) before concluding the system has no edge.

2. **The SL is the smoking gun — premature stop-outs destroy the edge.** By exit reason:
   - **SL hit: 79 trades (68% of all), 16.5% win, −5.12% alpha, PF 0.08, avg 8 days.** ← all the bleeding.
   - **Time expiry: 27 trades, 77.8% win, +8.88% alpha, PF 11.32, 30 days.**
   - **Trail SL: 9 trades, 66.7% win, +4.47% alpha.**
   The 36 trades that AREN'T stopped out are hugely profitable; the 79 knocked out at ~8 days bleed it all away. The **SWG stop (1.5×ATR) is too tight** — same failure mode the May campaign fixed for POS (100% SL hit at ~5d). **Widening the SWG SL is the #1 experiment.**

3. **Alpha is concentrated in DOWN-tape windows** (per matched-horizon benchmark): DOWN tape 44 trades, 50% win, **+2.54% alpha, PF 3.46**; UP tape 73 trades, 27% win, **−3.05% alpha, PF 0.49**. The breakouts behave defensively (relative strength when the market falls, lag when it rallies) — exactly `bull_market_base_rate_warning` made concrete.

### CRITICAL BUG FOUND & FIXED — squeeze gates killed the entire positional book
Jay challenged the "zero POS picks in 24 months" claim (POS-BO is the CORE positional strategy). He was right — it was a **signal-drift bug**, not market reality.

**Root cause:** `bull_screener.weinstein_setup` (the base gate for POS-BO AND POS-ACCUM) AND-ed in `ma_sqz_ok` + `bb_sqz_ok` — a tight 10% coil + NR7 contraction. The canonical Pine (`Weinstein_Unified_Ecosystem_v3.4` line 1622) does **NOT** include these (they're display/VCP flags only). A squeeze is mutually exclusive with the POS-BO breakout requirement (breakout = wide-range bar = opposite of NR7), so it nullified the positional book entirely.
**Proof:** nifty500 @ 2024-08-15, `weinstein_setup` 0/440 WITH squeeze vs **25/440** without. The funnel diagnostic had been *hiding* `ma_sqz`/`bb_sqz` (now exposed).
**Fix:** removed `ma_sqz_ok and bb_sqz_ok` from `weinstein_setup` to match Pine (commit on branch). Diagnostic counters added.

**This was a RECENT regression (post-May-21), NOT present during the v2-LOCK campaign** — the May runs had POS-BO firing 8–12 picks/run (verified across all `validation_20260521_*` details). So the v2 FINAL baseline stands; the bug crept in between 21 May and 2 Jun (untracked `bull_screener.py` edits — "R5/R6" squeeze rewrite). The "POS-BO rarely fires on N500" code comment described POS being the *minority* catalyst (~8%), not zero.

**Post-fix re-run (`20260603_190808`, 24mo nifty500 catalyst-aware) — POS-BO has a STRONG edge:**
| Catalyst | n | win% | mean matched α | PF | avg days |
|---|---:|---:|---:|---:|---:|
| **POS-BO (core)** | 14 | **78.6%** | **+7.67%** | **3.14** | 52 |
| POS family | 17 | 70.6% | +6.09% | 2.72 | 49 |
| SWG-BO | 101 | 36.6% | −1.31% | 0.71 | 14 |
| SWG-REV | 14 | 21.4% | −4.70% | 0.19 | 17 |

**The pooled "NO-EDGE" verdict was a composition artifact** — 17 POS winners drowned by 115 bleeding swing trades (78 SL-hits at ~8d, 15% win). Per-family is the correct lens: **POS-BO is your real edge; the swing book (esp. SWG-BO/REV with the too-tight 1.5×ATR stop) is the drag.** The OOS gate must be run PER FAMILY, not pooled (POS n=17 still too small for its own gate — needs more anchors).

### Second regression still open
SWG-PB (Stage-2 Pullback) was the DOMINANT catalyst in May (56–66 picks/run) but is **0** in the June runs — a separate, undiagnosed regression (SWG-PB doesn't use `weinstein_setup`, so the squeeze fix doesn't touch it). Must trace its gate chain (`cpr_ok`/`mvwap_ok`/`rsi_pb_pocket`/`vol_drying`) vs Pine.

### Next Priority Work
(a) **Diagnose the SWG-PB regression** (dominant catalyst, now zero). (b) **Widen the SWG-BO/REV stop** (1.5×→2.5-3×ATR) — 78 SL-hits at 8d/15% win are the swing drag. (c) Re-run + gate PER FAMILY once SWG-PB is restored. (d) POS-BO edge (+7.67%, PF 3.14) is real but n=14 — accumulate more anchors before Phase 3. (e) RELIANCE Stage-4 exit.

---

## 4–5 June 2026 — MEGA SESSION: PA Conversion + Recovery Strengthening + Docs (HANDOFF)

> This was an enormous multi-thread session. Everything below is the authoritative state. Branch **`phase0-1-attribution-journal-snapshot`** (~50 commits, all PUSHED to origin, **NOT merged to main**).

### A. Phase 0/1 SHIPPED (journal/attribution)
- `performance_attribution.py` — realized-P&L decomposition across 11 dims incl. entry-signal drivers; quarantines incomplete rows (no NaN→0); signed-share-of-gross contribution. Wired into AUTOPSY page (5th "📐 Attribution" tab in `weinstein_commander_web_v4.0.py`).
- `journal_enrichment.py` — lean 6-col entry snapshot (setup/entry_stage/entry_alpha/entry_rs/entry_conviction/snapshot_meta) via `bull_screener.screen_symbol()`. Auto-captures on new OPEN trades (hook in `dhan_journal_v7.upsert_trade`).
- **Journal exit reconcile** — recovered 17 missing exits via Dhan API; fixed 2 silent bugs in `ai_reconcile_engine.fetch_trade_history` (token-outside-try; securityId→ticker via new `dhan_symbols.get_nse_secid_to_symbol`). True baseline: **−₹4,99,283 / 25.6% win / 0.24 PF** (was flattered to −₹39k by missing data). METALIETF/HDFCSML250 tranche reconstruction. Cash-park (LIQUID*) excluded.
- `journal_sync.py` — daily journal↔Dhan holdings reconcile (ADD/UPDATE/CLOSE-with-verified-exit; aborts if book empty). **Scheduled: Windows Task `TradingJournal_DhanSync`, daily 4:30 PM IST**, logs `logs/journal_sync.log`. Journal OPEN now = live book (8 positions; DMART closed @4137.20).
- **RELIANCE = Stage 4 violation, still OPEN** — Jay's trade to exit (~₹1.92L → rotate to Golden Picks). DMART already exited.

### B. THE BIG ONE — Bull catalyst blackout + Pure Price-Action conversion
- **Root cause of "catalysts disappeared":** `bull_screener.weinstein_setup` AND-ed `ma_sqz+bb_sqz` (squeeze) into the POS base gate — mutually exclusive with breakout → **0 POS picks for 24 months** (recent regression vs Pine line 1622). Also SWG-PB stripped of quality gates; SWG-REV had a logic contradiction.
- **Jay's directive (CANONICAL):** replace lagging indicators (RSI/MACD/BB/ADX) with **pure price action wherever possible**; don't break logic; don't over-tighten (multi-level funnel compounds).
- **Direction reconciled:** Python price-action is CANONICAL; Pine synced UP to it (not the reverse). I initially mis-synced (imported Pine's ADX/RSI) and reverted to PA.
- **Indicator→PA map:** RSI>60/50 → close>close[10]&[5]; ADX → ≥7/14 up-bars w/ higher highs; weekly RSI → wClose>wClose[5]; POS-ACCUM RSI≤50 → close≤close[5]×1.05; SWG-PB RSI-pocket → 38-62% retrace; SWG-REV RSI<35 → prior 3-bar-down + reversal bar.
- **Synced across:** `bull_screener.py` + `Weinstein_Unified_Ecosystem_v3.4.pine` + `Commander_Bull_Screener_v3.2.pine` + `Weinstein and Swing Pro Dashboard v67.4.12.pine`. **Pine files were INCONSISTENT with each other** (Commander alpha was already PA; Unified+v67 weren't) — now harmonized. **Jay confirmed he recompiled all 3 in TradingView — they compiled clean.**
- Macro-edge volume term added to Python alpha for parity. Catalyst FUNNEL diagnostics added (bull + recovery) — the tool that found every blackout.
- **Validated edge (24mo nifty500, matched windows, per-family):** POS-ACCUM +3.20%, SWG-BO +1.80%, SWG-REV +0.95%, POS-BO +0.60%. Pooled looks weak only due to composition (SWG-PB drag). Edge concentrated in DOWN tapes (defensive profile).

### C. SWG-PB — PARKED (Jay's favourite, but regime-mismatched)
Diagnosed exhaustively: signal finds upside (+9.84% runup) but 90% stopped early; tried wider stop (worse), quality gates (alpha_ok over-restricts pullbacks), confirmation bar, 60d window, EMA20-structural-floor stop. **Robustly negative — it's a momentum-continuation setup in a corrective regime (wrong tool now).** Current gates: minervini + bull_pullback + is_vcp_tight + pb_pocket_pa(38-62%) + pb_vol_dry + close>prior-high; stop = EMA20 floor; window 60d. Needs regime-conditioning (only fire in confirmed up-trends) — future work.

### D. Recovery STRENGTHENED (Jay: "only fundamentally strong beaten-down stocks")
- **RFF hard gate 1→4/6** (`rff_min_score`) — only fundamentally strong; INSUFFICIENT blocked. RFF Tier-A 6 checks + Tier-B bonus. (recovery_screener.py)
- **REV-CB drawdown 25% → 15–35% BAND** (`cb_drawdown_pct`=15, `cb_drawdown_max_pct`=35) — quality on sale not falling knives. Climax detect 0.5%→5.2%.
- **REV-EARLY un-blackouted (0→firing):** breakout AND→OR, vol-dry-up demoted to optional, `vol_confirm_mult` 1.5→1.25, and **strict-trend-UP gate DROPPED** (binary → made it "late"; breakout is now the early turn-confirm).
- **REV-RS stop widened** low10-0.2ATR → low20-0.5ATR (62% SL-hit on 90d hold before +9.84% runup). Shares SL with REV-EARLY.
- **Edge validated (90d windows): positive in DOWN/recovering tapes** — REV-CB +1.72%, REV-EARLY +0.68%, REV-RS -1.07% (weak link). Negative in up-tapes (correct — don't run recovery in a bull market). **Live screen: 7 signals, all RFF≥4.**
- **Pine = intentional RFF-Lite** (TradingView 5-call ceiling). Trade recovery off PYTHON, not Pine.

### E. Infra: `data_provider.py` hard download timeout
`yf.download` wrapped in daemon thread + `join(timeout)` (30s/60s) — a stalled yfinance connection froze a run ~15h. Now aborts → fallback. Protects all runs + the daily journal sync. **New params: `YF_DOWNLOAD_TIMEOUT_S`.**

### F. ⏳ DETACHED RUN IN FLIGHT
`nohup python validation.py --months 24 --universe nifty500 --screener recovery --catalyst_windows` (PID 2205) → **log: `validation_runs/_rev_rs_rerun.log`**. Confirms the REV-RS stop fix (alpha by tape + SL-hit% drop). Recovery runs take ~2-3h (per-anchor fundamental fetches). **Next session: read that log, run `catalyst_regime_partition.py` on the new LAST_RUN.**

### G. Docs (in progress — Jay: "rewrite all guides by reading modules")
- ✅ DONE (rewritten from code): `docs/11_Bull_Screener_v3_3_Guide.md` (new, removed v3_2), `docs/09_Recovery_Screener_v2_1_Guide.md` (new, removed v2_0), `docs/16_Validation_Framework_Guide.md` (rewritten in place), `docs/00_INDEX.md` (updated). `01_Swing_Zigzag` was already done by Jay.
- ⏳ REMAINING: `13_Unified_Ecosystem` (~1040L) + `08_Dashboard_v67` (~1030L) — agreed plan: **targeted PA-sync** of catalyst/alpha sections (not full rewrite — most content still valid). `07_Commander_Web_v4` (add Attribution tab). `19` NEW Journal/Attribution guide. `18_Trade_Checklist` (stale POS-ACCUM RSI refs → PA). Verify unchanged: 02/03/04/10/12/15 (didn't change this session).

### H. THE RECURRING LESSON (saved to memory)
Across POS-BO, SWG-PB, REV-RS: **the signals find edge; tight stops on long holds give it back.** Signal generation > exit calibration. Always read backtest verdicts PER-FAMILY × DIRECTION, never pooled. Never judge a positional/recovery setup on a 30-day window. Price-action is canonical; sync Pine UP to Python.

### Next Priority Work
(a) Read `_rev_rs_rerun.log`, confirm REV-RS, partition. (b) Finish docs (13/08 targeted PA-sync, 07, new 19, 18). (c) RELIANCE Stage-4 exit. (d) REV-RS weak-link + SWG-PB regime-conditioning. (e) Merge branch → main. (f) Optional: strip diagnostic funnels; per-family OOS gate before Phase 3.

---

## 14 June 2026 — Swing Zigzag [Strict] audit → v6.3

Deep audit of `Wesinstein Swing Zigzag [Strict v6.2].pine` (standalone discretionary visual
indicator — NOT a zero-drift parity surface; its `trendState` is local to the script). Shipped
**v6.3** (file renamed v6.2 → v6.3 per convention; **compiled clean in TradingView, Jay-confirmed**).
Untracked file — no git history.

**Real bug fixed (A) — asymmetric bootstrap.** Section 1 (pivot-high) handled the first-ever
pivot via `na(activePivotType)`, but Section 2 (pivot-low) did not. Consequence: on any chart
opening in a **downtrend, the first swing low was silently dropped** (not locked/labelled) until
a high formed. Fix: added the `na` seed branch to Section 2, with the high-locking work guarded
by `if activePivotType == "H"` so the seed only establishes state — mirrors Section 1 exactly.
Same-bar ph+pl is safe (Section 1 runs first, seeds "H", Section 2 then takes the normal H→L path).
Behaviour-neutral everywhere except the intended early-history low.

**Perf (C):** `flipBars` array now trimmed to the choppiness window each bar (`while`+`array.shift`;
lookback hoisted to one `chopBarsBack` const reused by the panel) — was unbounded. Daily anchor
securities (`ema20_daily`/`atr14_daily`) gated behind `_isIntradayTF` (na on D/W/M). MTF2 reuses
`mtfTrendState` when there's no 2nd HTF (no duplicate `request.security` on Monthly).

**Enhancements:** (6) Hidden `plot()` outputs — `trendState`, `confirmedTrend`, `bosUp`, `bosDn`
(`display=display.none`) — so a screener/another script can consume this engine via
`request.security` (no visual change). (7) New input **"Confirmed-bar projection (non-repainting)"**
(default OFF = live behaviour); ON gates Section 3's developing-BoS + projection behind
`barstate.isconfirmed` for a calm/non-repainting alert path.

**Doc/cleanup:** BoS alert messages note the live-projection repaint nature ("Once Per Bar Close").
`pivot_len` de-`var`'d; panel colour literals `#1A237E`/`#131722` → consts `C_PANEL_HDR`/`C_PANEL_BG`.

Plan file: `~/.claude/plans/please-validate-and-deep-functional-sifakis.md`.

---

## 2–3 July 2026 — Reliability Campaign: Catalyst Gates + Data Integrity + Pine Parity (CLOSED)

### A. Catalyst gate review (all 6 bull catalysts) — philosophy: structure fires, quality is STATUS
- **POS-BO 2→8**: stage2_fresh removed from gate (eyeball), 3-session breakout+vol window (was single-bar), pa_dir relaxed to ≥5/14 up-closes (dropped higher-highs clause), **alpha demoted from veto to status** (biggest lever).
- **POS-ACCUM 2→12**: alpha demoted + new `accum_base` (Stage 1/2 + >200DMA + RS + vol-accum) replacing base_confirmed whose near-52wH trend_template CONTRADICTED accumulation. Python had demanded near-52wH while Pine demanded price-lagging — opposites; all 4 surfaces now share one definition (coil near 30-bar high).
- **SWG-BO 4→1 (intended)**: the validated drag (37% win) — Python synced UP to Pine quality (minervini + VCP1.5 + 15-bar pivot + vol>1.25 + anti-algo). Unified had the weak version; upgraded.
- **SWG-PB 12→0 in NOT-BULL (intended)**: hard mkt_bull regime gate (momentum-continuation fails in corrections). Synced to Unified only (Commander/v67 lack a regime var — accepted drift).
- **SWG-GAP / SWG-REV**: left as-is (rare / validated drag).
- Current NOT-BULL profile: POS-BO 8 · POS-ACCUM 12 · SWG-BO 1 · rest 0 — correct defensive shape.

### B. Data integrity — cache-poisoning ROOT CAUSE fixed (data_provider.py)
Deep-period fallback copied old frames into the requested key with a FRESH timestamp → stale data self-renewed forever; 15 portfolio/golden symbols stuck on Jun-24 bars for 9 days (VIJAYA "fired" POS-ACCUM on a dead bar). Fixed: `_content_stale_for_live()` (freshness judged by the DATA'S LAST BAR, live mode only; replay/pinned exempt) + fallback no longer re-timestamps. Defense-in-depth in bull_screener: RUN_FRESHNESS tracking → `As_Of`+`Stale_Data` result columns → DATA FRESHNESS AUDIT printed per run → STALE-DATA RETRY self-heal pass → stale picks excluded from sentinel counts.

### C. NEW `catalyst_sentinel.py` — blackout detector
Per-family counts logged every run (`logs/catalyst_counts_history.csv`); ⛔ BLACKOUT when a family that fired ≥30% of trailing 20 runs goes zero for 5+ runs; SWG-PB zero excused in NOT-BULL. Wired into run_bull_screener at both exits (guarded — can never break a run).

### D. Pine parity — EMPIRICALLY CLOSED (method: TV replay to Python's As_Of bar + read Unified CATALYST DIAG table)
3 real Pine bugs found by bar-aligned OUTPUT comparison (code inspection had missed all 3):
1. **MTF bug (Unified + v67)**: `wClose[5]` on the daily chart = weekly close 5 trading DAYS ago, not 5 weeks → weekly-momentum gate tested the wrong bar. Fixed via `wClose5wAgo` returned from inside the weekly security bundle. (Commander was already correct.)
2. **Unified OBV drift**: linreg-slope vs the canonical acc-bars (≥8/20 up-close on rising vol) used by Python/Commander/v67 → fixed.
3. **Unified pa_dir off-by-one**: loop `1..14` excluded the current bar vs `0..13` everywhere else → fixed.
Final verify: GRANULES fires `POS-BO ✓ FIRE ½⚠ ctr-trend ·mature` on the aligned bar = exact Python match (incl. counter-trend + mature status tags). Remaining Pine↔Python gaps are FEED DATA only (TV vs Dhan volume on marginal vwma5<sma50 tests, e.g. AXISBANK VCP-accum; formulas verified identical). All 3 Pine surfaces recompiled clean by Jay.

### E. NEW second-screen tools
- `golden_matcher_dashboard.py` (+ `LAUNCH_GOLDEN_DASHBOARD.bat`, port 8510, uses `python -m streamlit` — the venv's streamlit.exe shim is broken): single-symbol Golden Matcher command center — 6-step guided DECISION PATH (CONTEXT→QUALITY→SETUP→LOCATION→TRIGGER→EXECUTE) with hard gates, "← NOW" highlight, tick-as-you-go execution checklist; graphical technical board; Pine-panel mirror cards; fundamentals; full panels in an expander. Reuses `bull_screener.screen_one()` (NEW additive single-symbol entry that mirrors run_bull_screener's benchmark+regime plumbing).
- One-pagers: `Chart_Annotation_SOP_OnePager.html` (level-marking SOP), `Daily_Operating_Cadence_OnePager.html` (scanner→scope→sniper funnel).

### Pending (also in memory: catalyst_gate_philosophy, cache_poisoning_fix)
Commit branch changes · re-baseline validation with the new gates · RELIANCE Stage-4 exit (Jay) · optional: recovery-side sentinel, fuller parity sweep, sector-gate wiring in golden dashboard, docs refresh (11/13/08).

---

## 7 July 2026 — Pyramid/Trim 5-rung ladder + Section 4 Entry-Trigger Pine

### A. Pyramid/Trim Manager reworked → full ADD→HOLD→REDUCE→TRIM→EXIT ladder
- **`pyramid_logic.py`** (shared brain, single source of truth for inline Web Commander page AND `pages/5_pyramid.py`) — 5-rung `classify()`, priority order EXIT→TRIM→REDUCE→ADD→HOLD, **best-of-each** across the three engines:
  - **EXIT (full):** at-SL `(ltp−stop)≤1.5×ATR & pnl≤0` · underwater ≤−8% · Stage 4 · price-structure (positional `ltp<30-WMA`, swing `ltp<swing_low`) · Chandelier stop-out · time-stop (60d swing / 180d positional & R<0.5).
  - **TRIM (partial, winners only):** R≥3→book ½+trail, R≥2→book ⅓+lock 0.5R · target hit · over-extended `(ltp−EMA20)/ATR≥4.0` · earnings ≤3d (guarded).
  - **REDUCE (soft):** RRG LAGGING · `ltp<50-DMA` (positional) · score≤25.
  - **ADD (pyramid):** leader AND pullback-location (above rising 200-DMA, `ltp≤close_5d×1.10`, `ltp>EMA20`) — both required.
  - Constants: `EXT_ATR_MULT=4.0`, `SWING_DAYS=60`, `POS_DAYS=180`, `TIME_STOP_R=0.5`, `MIN_RISK_FRAC=0.005` (guards garbage-R when stop≈buy).
- **`risk_common.py`** (NEW) — `trail_mult_for(setup,bear)` + `chandelier_exit(...)`, catalyst-aware Chandelier (POS 4.5·WYC 3.5·REV 2.5·SWG 1.5, +0.5 bear, cap-protect 2.5; level = 22-bar max close − ATR(22, EWM α=1/22)×mult). **Verified byte-identical to old Risk Shield formula.** Risk Shield page refactored to call it → zero drift.
- **Web Commander:** inline `elif page=='PYRAMID'` page (NOT a new screen), NAV button ⚖️ PYRAMID / TRIM under CONTROL CENTER. Verified on live 14-position book (EXIT 4 / TRIM 2 / ADD 2 / HOLD 6). `inr()` NaN/inf-safe.
- Bugs fixed: journal status casing (`UPPER(status)='OPEN'`), NaN target (`pd.to_numeric coerce`), garbage-R guard, time-stop realigned 10/42→60/180d per DNA.
- **DEFERRED (Jay):** making Risk Shield + `exit_signal_engine.py` also call the shared `classify()` brain (3-engine full reconciliation) — they still use own logic for now.
- **STANDING ACTION:** restart Web Commander for all Python changes (pyramid_logic, risk_common, recovery wiring, catalyst gates, nav) to take effect.

### B. Golden-Matcher §4 decision-tree gap → NEW Pine indicator
Reviewed `modern_trading_plan.md` §4 (Entry Trigger & Price Memory). Decision (Jay): don't compute AVWAPs for all stocks — build a **Pine indicator** applied on TradingView to names filtered to Step 5 on the Golden Matcher.
- **`Section4_Entry_Trigger_v1.0.pine` (NEW, SHIPPED, compiles clean, verified live on CAPLIPOINT 125-min):**
  - 3 anchored VWAPs — Low (52wk/Stage-1 bottom), BO (last N-bar-high breakout day), Gap (last high-vol gap-up). Anchor DATES from **daily** structure via `request.security`; VWAP accumulates on chart TF.
  - Pinch detection (bg shade + panel), nearest-support, AVWAP trigger (bounce off support OR R2G reclaim > AVWAP-BO), intraday trigger (rising-10-EMA reclaim + TTM squeeze fires up on 75/125-min), entry panel with buy-stop/SL plan line, 3 alertconditions.
  - **KEY PINE BUG (memory-worthy):** AVWAP accumulator sentinel seeded to `na` → `anchor_t != na` returns `na` (falsy) → anchor never latched, all AVWAPs `na`. Fix: seed sentinel to `0`, guard `last>0`. (Chart Markup AVWAP used `1` for this exact reason.) Also: dynamic historical indexing `time[math.abs(ta.lowestbars(...))]` unreliable inside `request.security` → use `ta.valuewhen(cond, time, 0)` for all anchors.
  - Untracked .pine (no git history). In-file header documents it. Doc `docs/22_...` NOT yet written (offered).

### Next Priority Work
Docs for Section 4 (optional) · commit branch `phase0-1-attribution-journal-snapshot` · restart Web Commander · deferred 3-engine reconciliation · RELIANCE Stage-4 exit.

---

## 8–9 July 2026 — S4 Entry Trigger ecosystem + Golden Matcher trigger wiring + Dhan date fix

### A. Section 4 Entry Trigger Pine — v1.2 → v1.8 (Jay compiles each rev; title bumped per rev to avoid stale-table reuse)
`Section4_Entry_Trigger_v1.0.pine` (filename unchanged; in-file title = version). Evolution:
- **v1.2** PA battery re-based to the canonical Golden-Matcher 11 (v67.4.12 mirror) with Σ-tier; correct `ta.vwma(volume,5)` dry-up.
- **v1.3** "Confirmed daily only" toggle (default ON) — daily PA reads the LAST CLOSED daily bar. `request.security(D)` on ANY intraday TF returns the FORMING daily bar → NR7/coils repaint early-session (RV~0.1 = the tell); only real at daily close. Consolidated TRIGGER row; Plan gated; dark-theme panel (#131722 bg, #2a2e39 grid, brighter labels).
- **v1.4** battery 11→17: + Wyckoff Spring, Gap-Up BO, 50SMA Undercut, Hammer@50, Hammer@200, Breakout-Confirmed. Compact grid shows ALL conditions ✓/· (nothing aggregated away).
- **v1.5** TRIGGER = COMBINED gate `E✓V✓I·` — **GO = (Event OR Intraday) AND Volume** (NOT all 3 — anti-Holy-Grail, per Jay). `rv_floor` input (default 1.0). RV its own colour-coded field (≥1.25 green / ≥1.0 amber / <1 red). Plan prints ONLY on GO. New "S4 GO" alert.
- **v1.6** UNIFIED Bull/Recovery — `Mode` input swaps battery (Bull 17 ↔ Recovery 10); shared AVWAP/RV/intraday plumbing; mode-aware grid + header (`PA · BULL` / `PA · RECOVERY`).
- **v1.7→v1.8** `Mode: Auto` (default) infers path from price structure. v1.7 rule (`off52≥15 AND below SMA150`) was **self-defeating** — Step-5 recoveries have confirmed the turn/reclaimed SMA150 → resolved Bull (CIPLA). **v1.8 fix: `off52 ≥ 10 AND (below SMA150 OR SMA150 10-day slope falling)`** — slope catches reclaimed-but-unrepaired recoveries; fully repaired (rising 30WMA, <10% off) = genuinely Bull. Jay confirmed flipping correctly; accepts the Pine-can't-see-RFF approximation (header shows resolution; manual override remains).

### B. Golden Matcher — CANONICAL SURFACE = Web Commander page (memory: golden_matcher_canonical_surface)
**Mistake caught by Jay:** I'd been editing the standalone `golden_matcher_dashboard.py` which he NEVER uses. All logic ported to `weinstein_commander_web_v4.0.py` (Execution → 🎯 Golden Matcher, Auto-Sync TV, Bull + Recovery paths); **standalone + LAUNCH_GOLDEN_DASHBOARD.bat archived to `_archive/legacy/`**.
- **Bull path:** `_detect_pa_patterns` 11→17 + VCP dry-up bug fixed (`(c*v)`→`(v*v)` — old leg was a no-op firing ~96% of bars; fix halves VCP-BO fires, verified GRANULES 57→15, RELIANCE 53→13). Step-5 wired to the battery (metrics: PA trigger names + Σ + confirm-on) with verdict split **BUY — TRIGGER LIVE / ARMED · AWAIT TRIGGER**; 3-gate banner aligned (STRONG BUY · TRIGGER LIVE / READY · AWAIT TRIGGER); counter-trend warning widened.
- **Recovery path (new):** `_detect_recovery_pa_patterns` — **10 conditions**: Climax Reversal(SC+AR)+3 · Wyckoff Spring+3 · Higher-Low/2B+3 · Base Breakout(SOS/JAC)+3 · Bull Engulf+2 · Hammer-at-support+2 · 3-Bar Rev+2 · Pocket+2 · VDU+1 · 30-WMA Reclaim+3. Wired into recovery Step-5 (same verdict split, "· Recovery" suffix) + **PA Σ chip added to recovery Step-3** (Jay caught the asymmetry). **RS-turning-up (Mansfield/RRG IMPROVING-LEADING) added to recovery Step-2 QUALITY** — Jay trusts Mansfield RS; deliberately in Quality, NOT the PA battery.
- **Path symmetry doctrine (agreed):** symmetric in FORM (6-step skeleton, TRIGGER LIVE/ARMED language, PA chips at Steps 3+5), deliberately asymmetric in SUBSTANCE (bull=technical leadership vs recovery=RFF fundamentals; bull SETUP soft vs recovery SETUP hard; bull location=at-value/not-extended vs recovery=turn-confirmed/not-chased). PA in both Step 3 (context chip, non-gating) and Step 5 (decision) is intentional; coil-vs-trigger split offered, declined per build-freeze.

### C. Dhan daily date-shift bug — FIXED (memory: dhan_daily_date_shift)
`dhan_ohlcv.py:396` read IST-midnight epochs as UTC → **every Dhan daily bar dated 1 day early** (Monday sessions showed as impossible "Sunday" — the tell). Surfaced as GM "stuck 2 days stale" / GM-vs-S4 NR7 mismatch on RADICO. Fixed with UTC→IST convert before normalize; cache backed up (`data/market_cache.backup_20260708`, 7,614 files) and cleared; verified Dhan Jul-7 == yfinance Jul-7 exactly. NOTE: pre-fix validation/replay artifacts were built on −1-shifted dates (re-baseline when next touching validation).

### D. Trading discipline established this session (RADICO + VIJAYA walk-throughs)
- GM Step-5 first, THEN S4 — S4 times entries, never qualifies names. Even at Step 5: **GO = one trigger (AVWAP event OR intraday 10EMA+squeeze) WITH volume (RV≥floor)**; a coil (NR7/IB-NR7) is compression, NOT a trigger; dead-volume reclaims (VIJAYA RV 0.2 fade-bounce) are skips. Chart-read retains VETO power (can talk you OUT, never INTO). TV alert per Step-5 name: "S4 GO" / any-alert()-call, Once Per Bar Close → act on the ping, never the touch.
- PA conditions are Bull/Recovery-specific by design; recovery qualification = RFF+drawdown (fundamentals), PA batteries are entry-timing only.

### E. Docs
- **`docs/22_Section4_Entry_Trigger_Guide.md`** (NEW) — full user+trading guide, updated through v1.8.
- **`docs/23_Golden_Matcher_Guide.md`** (NEW) — user+trading guide; repointed to the Web Commander page after the standalone was archived.
- `docs/00_INDEX.md` rows 22+23 added/updated.

### Open items
- TV alert bulk-creation for Step-5 shortlist (offered, not requested yet).
- Two formal verifications blocked by a classifier outage (web-commander parse after the one-line Step-3 chip edit; v1.8 auto-rule synthetic check) — both functionally confirmed by Jay's live usage.
- Coil-vs-trigger split of the PA chip roles (declined for now, revisit if the duplication nags).
- Unchanged: commit branch `phase0-1-attribution-journal-snapshot` · RELIANCE Stage-4 exit (Jay) · deferred 3-engine reconciliation · re-baseline validation post date-fix.

---

## 9–10 July 2026 — Golden Matcher audit + S4 Entry Trigger v1.9→v2.8 + Dhan freshness/intraday

Big multi-thread session. Branch still **`phase0-1-attribution-journal-snapshot`** (uncommitted). Two surfaces evolved in lockstep: the **Golden Matcher page** (`weinstein_commander_web_v4.0.py`) and the **Section 4 Entry Trigger Pine** (`Section4_Entry_Trigger_v1.0.pine`), with the shared **`pa_patterns.py`** (NEW module) as their zero-drift battery source.

### A. Golden Matcher audit + enhancements
- **Correctness fixes:** batch-CSV recovery Stage/RFF float→digit normalization (`_stg_digit`); confirmed-week guard on the two weekly-crossover PA patterns; **Higher-Low/2B base-proximity ceiling** (was firing every green day); one `_cat_on()` catalyst-normaliser; `compute_decision` displayed-thresholds aligned to enforced; dead `render_decision`/`render_pine_mirror` removed; `relvol` NaN guard; `_rec_cfg()` reads floor/RFF from `recovery_screener.CONFIG`.
- **Enhancements:** **E1** guided-checklist → `dhan_journal_v7.upsert_trade` (logs OPEN + auto entry-snapshot); **E2** position sizer (Capital/Risk% → shares, persisted to `gm_settings.json`); **E3** session shortlist + TV-watchlist export; **E4** Refresh clears only GM caches; **E5** batteries extracted to shared `pa_patterns.py` (`detect_bull_patterns`/`detect_recovery_patterns`).

### B. pa_patterns.py (NEW, canonical Python battery)
`detect_bull_patterns` (17) · `detect_recovery_patterns` (10) · `detect_support_zones` + `detect_support_zones_dw` (OB/FVG/pivot on Daily+Weekly) · `resample_intraday` (session-anchored 25m→75/125m). Flags: `intraday=True` suppresses weekly-anchored patterns (HTF, Stage-2 Launch, 30-WMA Reclaim); `ema20_ref/ema10_ref` = **EMA20 is a DAILY anchor** overlaid on intraday (DNA rule).

### C. Support-zone lifecycle (GM Python + S4 Pine, mirrored)
FRESH → **TESTED** (entered+left = grey, excluded from trigger) → **VIOLATED** (close below distal = deleted). **Pivot lines never deleted** — a violated pivot **flips to resistance** (`pivot_res`, "Pivot S→R"), cleared on reclaim. Zones drawn on **Daily + Weekly**, and (v2.4) each box **starts at its FORMATION candle** (OB down-candle / FVG 3-bar gap / pivot-low bar) + extends right.

### D. Dhan feed fixes (`dhan_ohlcv.py`, `data_provider.py`) — memory: [[dhan_daily_date_shift]]
- **`fetch_intraday` wrong response key** (`start_Time`→`timestamp`) — intraday was silently empty; now works (90-day window, 25m=~900 bars). *Don't trust "intraday unavailable" — check `resp["data"].keys()`.*
- **Dhan daily endpoint publishes a session NEXT-DAY** → `fetch_daily` now back-fills the just-closed session from intraday (`_append_completed_session_from_intraday`, session-aware, no-op during market hours).
- **`data_provider.invalidate_symbol()`** (NEW) — Refresh + GM auto-heal force a real re-fetch (beats the 24h daily-TTL). GM freshness banner + auto-heal now **session-aware** (after 15:30 IST expects today's bar). Fixed the "one day behind after close" + "Refresh does nothing".
- **Symbol canonicalization** — `dhan_ohlcv.canonical_nse_symbol` (scrip-master, separator-insensitive: `BAJAJ_AUTO`→`BAJAJ-AUTO`, `M_M`→`M&M`) + GM `_canon_sym` at both TV-sync commit and manual box.

### E. GM intraday Trigger-TF + S4 chart-TF (75/125m)
- **GM:** Trigger-TF selector (**75m default** / 125m / Daily) recomputes the Step-5 PA battery **+ momentum board** (RSI/ADX/RelVol/Vol-dry) on the intraday TF; **context/quality/setup/location (Stage/RS/Alpha/catalyst/zones) stay Daily/Weekly**. Step-5 text is TF-aware ("fired on the 75m"). `gm_load_intraday` cached (180s).
- **S4:** Gemini added v2.5 (`require_squeeze` toggle, relaxed squeeze window, TF-aware volume) + v2.6 (`use_chart_tf`). I reviewed → **v2.7** parity fixes (HTF suppressed on chart-TF; engulf keeps **daily EMA20** via `f_daily_pa(ema10_ref,ema20_ref)`) → **v2.8** `use_chart_tf` defaults **ON** to match the GM. S4 is now v2.8.

### F. Gemini second-opinion audit (report reviewed)
- **REJECTED** its "double-shift lag" fix (the `timeframe.isdaily` gate reintroduces the intraday repaint; the `[1]` offset is TF-independent).
- **FIXED** `bull_screener.py:278` VCP dry-up `(v*c)`→`(v*v)` (dry leg was a no-op → VCP-BO fired without contraction; **re-baseline validation**).
- **FLAGGED, not fixed:** `technical_enrichment._calc_mansfield_rs` computes a 52-**day** SMA on daily closes while its docstring claims weekly — RS/RRG-adjacent, shifts matcher rankings; Jay's separate call.
- **S4 v2.3:** Auto path ↔ GM Bull/Recovery parity via the **200-DMA discriminant** (Bull above 200-DMA; Recovery = beaten-down below it).

### G. Workflow decisions & memory
- **90-day build freeze LIFTED** by Jay (do not push back on builds citing it). [[build-as-avoidance-execution-gap]] updated.
- **GM "TRIGGER LIVE" (early/armed) vs S4 "GO" (strict execution gate) is INTENTIONAL — do NOT align them.** [[gm_early_s4_execute_twostage]]. GM arms → focus → wait for the S4 GO.
- **Jay's standing feedback:** great from-scratch builds, but I miss adjacent "key aspects" → he burns time validating. Run a **second-order review before done** (DNA rules, consistency/defaults/twin-surface parity, edge cases, verify end-to-end, flag unknowns). [[second-order-review-before-done]].
- **S4 alerts bind to the compiled version at creation** — after recompiling, DELETE & RE-CREATE the "S4 GO" alerts (this was why SOBHA's GO alert stayed silent).

### Docs updated
`docs/22_Section4_Entry_Trigger_Guide.md` (→ v2.8), `docs/23_Golden_Matcher_Guide.md`, `docs/00_INDEX.md`.

### Next Priority Work
(a) **Recompile S4 v2.8 in TradingView** + delete/recreate the GO alerts (75m & 125m). (b) **Re-baseline validation** after the bull_screener VCP fix. (c) Decide on the **Mansfield daily-vs-weekly** flag (technical_enrichment). (d) The "DZ/Resistance" zones on Jay's chart come from OTHER indicators (Institutional Zone Engine / Chart Markup) — apply formation-anchored drawing there if wanted. (e) Commit branch `phase0-1-attribution-journal-snapshot` → main (many uncommitted changes). (f) RELIANCE Stage-4 exit (Jay).

---

---

## 12 July 2026 — Trigger Board redesign: Bull Step-3 fix + P1 Inherited Qualification

Branch **`phase0-1-attribution-journal-snapshot`**, both commits PUSHED **and ff-merged to `main`** (main = `e1096f8`).

### The flaw addressed
The Golden Matcher **Trigger Board** re-qualified (hard Context+Quality via the screeners) what each source watchlist already qualified. Consequence: only the Nifty-500 **catalyst** scan produced actionable output; the **rigorous** Chartink+Screener watchlists (Bull Hunter/EarlyBird/Pullback/Leader + Recovery RS/Climax/Early) dead-ended at "no catalyst" (bull) or "SKIP · weak fundamentals" (recovery, because fast-mode RFF=INSUFFICIENT). Universe is **all Nifty 500** — all 7 Chartink scans share group `{57960}` = Nifty 500 (Jay confirmed the 4 Bull scripts; Recovery has no saved Chartink scan, the Python submits the clause via API on the same group). So the rigorous lists add value not by out-of-universe reach but by **arm-before-trigger** (they're the armed setup universe; the catalyst scan is the trigger-instant snapshot).

### A. Interim working fix — Bull Step-3 "trigger wins" (`c1561f8`)
Mirror of the Step-4 fix: in `compute_workflow`, a fired Step-5 PA trigger is no longer vetoed by a missing catalyst (Step-3) or weak location (Step-4). Context+Quality stay hard. Pre-qualified Bull names now reach `BUY — TRIGGER LIVE · no catalyst`. Zero-drift (shared workflow).

### B. P1 — INHERITED QUALIFICATION (`e1096f8`) — the structural fix Jay approved
Doctrine: **watchlists QUALIFY; the board TIMES** — stop re-qualifying. Behind `INHERIT_QUALIFICATION=True` (A/B flag at `weinstein_commander_web_v4.0.py:2529`).
- **`gm_trigger_board.py`**: sources → the **per-strategy lists** so every name inherits its **archetype(s)** (show-all). `FINAL_WATCHLIST` demoted to a **★ Top-Conviction badge** (top-25 by Combined_Score). New `load_watchlist_union` (returns `archetypes`/`star`), `resolve_archetypes()`, `BULL_ARCHETYPES`/`RECOVERY_ARCHETYPES` sets, `Archetype`+`★` columns, INVALIDATED category. Empty-sides ★-only name → runs both paths (never dropped).
- **`compute_workflow` (bull) + `compute_recovery_workflow` (recovery)**: when a source archetype is present, Context/Quality stop being hard vetoes → **still-valid break-down guard** (bull: Stage 3/4 or below 30WMA → `INVALIDATED`; recovery: Stage 4 or collapsed >50% off-high). **Fundamentals → ranking overlay, never a block** (this unblocks Recovery's RFF dead-end). Setup = inherited archetype (no live catalyst needed). Category = pure timing state (`INVALIDATED`/`WAIT`/`ARMED`/`Buy Trigger Live`). Honesty rule: missing `sma150` never flips a name to INVALIDATED (only observed break-down does).
- **Zero-drift**: the Single Symbol page calls `resolve_archetypes(symbol)` and times identically, with **separate ctx copies per path** so a bull archetype can't spoof the recovery inherited-branch.
- Verified pure layer (standalone, no Streamlit): 50 names, 100% archetype coverage, 23 stars, multi-archetype (NYKAA=Breakout+Catalyst), INVALIDATED mapping correct. Both modules `py_compile` clean.

### Target architecture (agreed, migrate slowly) — `docs/Trigger_Board_Redesign_Proposal.md`
Jay's call: keep Chartink + Screener.in as the **qualifiers** (paid, rich; Dhan may not replace Chartink scans). Long-term target = **one unified Python engine, two cadences**: QUALIFY (daily/on-demand, heavy — chartink_replay technicals + screener.in fundamentals, narrow-then-fetch) → TIME (live board). Eliminates Chartink/Screener browser automation + CSV handoff + batch/live divergence. `chartink_replay.py` already ports the Bull scans (validation gate before trusting it live). **Not now** — P1 is the first real step; migrate over time.

### STANDING ACTIONS for next session
1. **RESTART Web Commander** (all Python changes) + click **Build** on the Trigger Board (old `gm_board_cache.csv` predates the `★`/`Archetype` cols).
2. Watch P1 live a few sessions; if timing states behave, drop the `INHERIT_QUALIFICATION` flag to permanent and start **P2** (archetype-aware Location/Trigger for Breakout/Pullback/Recovery).
3. Still open (unchanged): RELIANCE Stage-4 exit (Jay's trade); recompile S4 v2.8 + recreate GO alerts; re-baseline validation after the bull_screener VCP `(v*v)` fix + Dhan date-shift fix; Mansfield daily-vs-weekly flag decision.

---

## 13–14 July 2026 — GM hardening: category-drift fixes → architectural review → P0+P1 remediation

Branch `phase0-1-attribution-journal-snapshot`, all PUSHED, **main = `249590f`**.

### A. Board-vs-Single category drift — ROOT-CAUSED and closed (13 Jul)
Three successive real causes (each verified, not guessed):
1. **`.NS` suffix** not stripped in `resolve_archetypes` → inheritance silently off on Single Symbol only → `_canon_key` used on BOTH union keys and lookups (memory: [[gm_symbol_ns_normalization]]).
2. **Second `.NS` leak**: Single Symbol passed `SYM.NS` → `gm_load_intraday` → Dhan needs bare → intraday failed → daily PA vs board's 75m PA. Fix: canonicalize at the TOP of `gm_evaluate` so every loader gets one key.
3. **Data-vintage split**: per-symbol "Refresh Data" made Single fresher than the board snapshot. Fix: ONE shared "Refresh Data (fresh · both surfaces)" button on both views (`_gm_reload_market_data`) + TF-staleness guard (board records `built_tf`). Also: `gm_evaluate()` extracted as the SINGLE evaluator both surfaces call — categories now agree by construction. Confirmed matching by Jay.

### B. Decision-path corrections (13 Jul, all on main)
- **Inherited decision-tree display**: Steps 1-3 relabel for inherited names (STILL VALID? / QUALITY·overlay / SETUP·inherited archetype) — the tree now says what the engine does.
- **Catalyst-Scan strictness**: catalyst-scan-ONLY names need a live catalyst OR fired PA → else `WATCHLIST · catalyst expired` (archetype renamed Catalyst→Catalyst-Scan to kill the "Archetype Catalyst ✓ / Catalyst None ✗" self-collision).
- **DLF-class bug**: Guided-Execution path radio now defaults to the MORE-ACTIONABLE path (was always Bull).
- **EMA20 dynamic-S/R location fallback** (both paths): no zone nearby + no engine SL → EMA20 = the stop, target = 52WH else 2R — location/R:R always computed. Recovery rr-recompute ordering bug fixed.
- **Unified Trigger-TF selector** (one `gm_trig_tf` key + gm_settings, both views). X-Ray checked by default. Overall pinned left in AG-Grid (was scrolling off); ★ tooltip (= FINAL_WATCHLIST top-25 badge). Guided-exec in an expander (expands on location or live BUY). Board Maximize-in-new-window (`?view=gm_board_maximized`) added by Jay/Gemini — preserved.

### C. Architectural review (14 Jul) + P0/P1 SHIPPED
Full review in `~/.claude/plans/glittery-jumping-scone.md` (3 parallel audits, file:line-verified). Verdict: decision core sound (gm_evaluate SSOT, inherited model, zero-drift); wrapped in ~20 silent-failure paths + correctness bugs + sequential build + UNVALIDATED decision layer.
**P0 shipped (10 fixes):** error-dict guard (phantom "NOT A RECOVERY CONTEXT" off `{"_error"}` dicts — now renders "Recovery evaluation FAILED"); `_g()` NaN-safe (closes every missed-scrub site); `cmp_px` is-None fallback; `EMA20_RECLAIM_BAND_PCT` wired to **8.0** (Jay's call — was dead at 6.0, live gate hardcoded 8); `get_security_meta` → `canonical_nse_symbol` fallback (separator variants no longer silently defect to yfinance); `built_tf` persisted in board cache (staleness guard survives restarts); STRUCTURAL_*_ARCHETYPES constants in gm_trigger_board (rename-drift killed); NSE delivery join canonicalized; fetch_intraday docstring fixed (5-day cap = interval-1 only; 25m serves ~90d); **dhan_marketfeed REWRITTEN** — it NEVER worked (import-time None globals + meta-dicts passed as raw secids); now call-time resolution + O(1) secid→symbol reverse map, verified off-hours.
**P1 shipped:** NEW `gm_log.py` → rotating `logs/gm_errors.log`; ~20 bare excepts converted to logged fallbacks; board build failures COUNTED + rendered ("Built 47/50 — 3 failed: …"); PA-detection crash renders "⚠ DETECTION ERROR" (not "none yet"); inheritance-resolver failure shows a "LEGACY verdict" banner; `LAST_UNION_ISSUES` surfaces unreadable/empty watchlist CSVs on the board header — **immediately caught a REAL issue: FINAL_Hunter_Picks.csv + FINAL_Recovery_ClimaxBounce.csv are header-only from the last auto-pilot (Hunter names silently missing from the board)**; `atomic_write_text` (tmp+os.replace) for board cache/RRG flags/gm_settings; provenance strips (Single: "src dhan/yfinance/cache" per get_last_source; board: built-TF + source-mix counts). Note: RerunException inherits BaseException, not Exception — `except Exception` can't swallow st.rerun (verified streamlit 1.53.1).

### P2-P4 ROADMAP (documented in the plan file, NOT yet built)
**P2 perf/staleness:** `_ttl_for` keys on period not interval (2y/1d frame gets 24h TTL — root cause of most staleness) · cache `load_watchlist_union` on CSV mtimes · ThreadPoolExecutor board build (2-5min → ~30-60s; verify parallel==sequential output) · split gm_load_symbol so live ticks stop re-invoking fundamentals.
**P3 testability:** move-only extract of the pure decision core → `gm_core.py` importable without Streamlit · golden-snapshot characterization tests · journal upsert dedup (pyramid/update/cancel instead of silent OPEN-row overwrite).
**P4 effectiveness (value order):** decision audit trail (JSONL per evaluation) → config-as-data (the magic numbers: Alpha 40/50/70, Minervini 5v6, 26w, corr≤50, 2.5×ATR…) → validate the decision layer via validation.py replay (the only edge-improving item) → auto-pilot headless board rebuild (today the 16:30 run does NOT refresh the board cache) → TV alert automation in guided-exec → UX debt (shortlist persistence, checklist tick keys on symbol+trigger-date, AG-Grid filter/staleness parity).

### NEXT SESSION FIRST ACTIONS
1. **Restart Web Commander → shared Refresh → Rebuild**; confirm failure counts + provenance strips render; spot-check 3 symbols board vs single.
2. **Investigate why FINAL_Hunter_Picks.csv came out empty** from the last auto-pilot (the new observability caught it — is the Hunter Chartink scan returning nothing, or a pipeline bug?).
3. During market hours: confirm the (now actually working) MarketFeed LTP overlay flashes on the streaming board.
4. Then P2 (start with the `_ttl_for` interval-keying fix — biggest staleness win).

---

## 14 July 2026 (evening) — GM board UX batch + RISK SHIELD audit → P0+P1 SHIPPED

Branch `phase0-1-attribution-journal-snapshot`, all PUSHED (ff `main` pending for the risk-shield commits).

### A. GM board UX batch (all on main through `019bdb4`)
- **75m/125m bar-close auto-refresh** (Jay trades 75m): board rebuilds ONCE per NSE session bar (10:30·11:45·13:00·14:15·15:30 +75s settle; 125m: 11:20·13:25·15:30) — the definitive fix for the forming-bar fade (board built 13:51 mid-session showed PA that faded by close → "Buy Trigger Live" vs single's "catalyst expired"). Default Live mode = bar-close matching the Trigger-TF. `_gm_bar_close_times`/`_gm_last_passed_boundary` unit-tested.
- **Single Symbol bleed under the board FIXED for good**: st.stop() is unreliable after the streaming AgGrid custom component (proof: works fine on the fragment-only single page) — the whole Single Symbol section is now a REAL conditional `if _gm_view != "📋 Trigger Board":` (~686 lines re-indented via script; TV SIDECAR elif intact). Browser reload does NOT reload code — full process restart required (that confusion recurred twice).
- **Maximize Board = table-only pop-out** (`?view=gm_board_maximized`): no controls/sub-header, slim Rebuild + status caption, grid 880px, settings from gm_settings, auto-refreshes on bar close. **Open-in-new-window** (`?view=gm_window`) = full GM (view switch intact, sidebar hidden) for keeping GM open while using other pages.
- **CSV download regression fixed** (bar-close default → AG-Grid → data_editor toolbar gone): explicit "⬇️ CSV" download_button in a SHARED header (warnings + filters + download rendered once for both render paths; `_board_apply_filters()` = the one filter definition for static editor + streaming grid + CSV). **Grid sort/filter**: floatingFilter row under every header; decision numbers coerced numeric + agNumberColumnFilter (CSV round-trip left them as text → lexicographic sort).
- **AGE staleness guard** (41e1af9): warns when viewing a mid-session snapshot after close / a >15-min-old snapshot during market hours.

### B. RISK SHIELD comprehensive audit (3 parallel agents, file:line-verified)
**Verdict: B- design, D+ operational integrity.** Decision core intent right (risk_common shared brain, catalyst-aware trails), but: TWO headline features silently dead, the broker never received trailed stops, FIVE stop engines (not 3) computing different stops (A Risk Shield + B Pyramid share risk_common; C exit_signal_engine 22-high−3.0×ATR14; D Command E-02 ADR-bucket; E GTT=raw entry SL), zero alerts, zero automation.

**RS-P0 shipped (`6d26907`):**
1. **JOURNAL_RENAME_MAP** (web:214) was missing setup/entry_*/manual_sl_override/custom_ce_mult/pyramid_status → the ENTIRE override layer was write-only AND the catalyst-aware trail NEVER engaged (setup always blank → heuristic 4.5/5.0 guess). Map now mirrors dhan_journal_v7's.
2. **_ws_above200 use-before-assignment** → chandelier always got above200=False (bear=True when regime down → +0.5 loosening). Computed before the call now.
3. **_pyr_reason NameError** crashes on technicals miss (2 sites) — init outside guards.
4. **% Port divided by CASH** not equity (per-row; headline was fixed 05-Jul) → `_equity_rp`.
5. **GTT dedup status mismatch**: shield counted only ACTIVE, Risk Shield reads PENDING → duplicate-OCO risk. Now: any non-terminal status = live.
6. Direct `_tech[...]` KeyError paths → .get with defaults.

**RS-P1 shipped (`e8908d0` + exit-alert commit):**
- **gtt_auto_shield --trail** (Jay: auto-trail, tighten-only): parses live OCO SL legs, computes catalyst-aware Chandelier via risk_common (journal setup → POS/WYC/REV/SWG mult; manual_sl_override=floor; custom_ce_mult; bear=market_regime≤5), modify_forever's the SL leg UP when >0.1% better. NEVER loosens; Chandelier≥LTP = BREACHED (reported, never auto-sold). Journal write-back to manual_sl_override (same as Risk Shield tighten). Token sanity-check; --yes headless; rotating logs/gtt_shield.log.
- **CRITICAL FOUND DURING IMPL**: `dhan_helpers` imports `DhanContext` which does NOT exist in the venv's dhanhq 2.0.x → **gtt_auto_shield has been CRASHING AT LAUNCH** (the COMMAND button spawned a dead script). Guarded check_margin fallback revives it. Same discovery invalidated marketfeed rewrite #1 → **dhan_marketfeed REWRITE #2** on the real 2.0.x API (`dhanhq.marketfeed.DhanFeed`, asyncio thread-bound: construct+connect+poll in ONE daemon worker, get_data() polling, generation token for restarts).
- **Scheduler jobs** (run while the app is up): `gtt_trail` 15:45 IST Mon-Fri (post-close, reads completed bar, Telegrams summary) · `exit_scan` 16:00 (exit_signal_engine --silent; the engine itself now Telegrams ACTION rows — stop hits/stage-decay used to be silent CSV-only).
- **Chandelier ruling (Jay, refined 15-Jul)**: TRADE-TYPE-AWARE clock — **swing = 14-bar (highest-close-14 − ATR14×mult), positional = 22-bar** (anchor + ATR paired on one clock). Sensing: journal `Timeframe` (explicit) wins → setup prefix (SWG→14; POS/WYC/REV→22) → unknown = positional 22 (prior behavior). `risk_common.trail_window_for()` + `chandelier_exit(swing=)`; threaded through all 3 callers (Risk Shield page via journal_overrides Timeframe, pyramid_logic via load_open_positions timeframe, gtt_auto_shield --trail). **BONUS audit fix**: pyramid `classify()` horizon parse read `trade_type` (='LONG', never matched) → everything silently defaulted positional; now reads `timeframe` first, so swing structure exits (swing-low / 60d time-stop) actually engage. Anchor stays highest-CLOSE; changing that needs a replay.py A/B. P2 = converge engines C/D/E onto risk_common.

### RS roadmap (documented, NOT built): P2 = 5-engine reconciliation (C/D consume risk_common+pyramid classify; align at-SL 1.5-vs-1.0×ATR, time-stop 60/180-vs-10/42d, one regime source; propagate cap-protect) · P3 = "Exact" manual-SL mode vs no-discretionary-overrides DNA ruling; catalyst-fallback warning; config-as-data for ~15 magic numbers; uncached broker calls per rerun; entry_stage usage.

### NEXT SESSION (risk-shield verification, market hours)
1. Jay checks GM live (bar-close refresh, maximized table, sort/filter, CSV) — pending from morning.
2. **First scheduled gtt_trail run 15:45** — watch Telegram summary + logs/gtt_shield.log; verify a real tighten landed at Dhan (Risk Shield hard-SL should move up).
3. **exit_scan 16:00** — verify Telegram ACTION alert.
4. NOTE: journal setups are mostly 'NONE' (backfilled positions) → trail uses heuristic-bull 4.5× until positions carry real setup labels (new entries via GM guided-exec do).
5. Then RS-P2 (engine reconciliation) or GM-P2 (perf) per Jay's pick.

---

---

## 16 July 2026 — S4 v3.0 Zone Engine + GM S4-GO preview + lean Pine screener (HANDOFF)

Long multi-thread session. Branch **`phase0-1-attribution-journal-snapshot`** (uncommitted). **Rule reaffirmed: NEVER auto-compile on TradingView — hand Jay the file, he compiles & reverts** ([[never_autocompile_tradingview]]).

### A. NEW FILE `Section4_Entry_Trigger_v3.0.pine` (was v1.0/internal v2.9.1)
Ported the **Institutional Zone Engine v4.2** demand/supply subsystem WHOLESALE into S4: `f_detectZone` (RBR/DBR/RBD/DBD patterns) + `f_structZone` (pivot structural, NEW — refactored to a ZoneSig fn so it runs via request.security like patterns) on **Chart+Daily+Weekly+Monthly**. OB removed as support source (zones replace it); FVG + pivots kept. IZE panel NOT ported. Key tuning landed this session:
- **MTF propagation FIXED** (was broken): (1) HTF zones wrongly age-expired in CHART bars → now calendar ageing per-TF (M 4y/W 2y/D 6mo/125m 4w/75m 3w, by FORMATION time, DELETE not grey); (2) same-TF dedup only (was any-TF → dropped monthly structural — pattern zones bypass dedup, structural didn't → asymmetry killed monthly).
- **Per-TF width band** (× ATR14): M 0.5–4.0 · W 0.4–3.5 · D 0.3–3.0 · 125m 0.25–2.5 · 75m 0.2–2.0 (native picks by chart TF). Too-tight 75/125 max is the #1 knob if intraday zones vanish.
- **Tested rule** (Jay's): reaction (wick pierced proximal / closed inside, then next bar moved out) THEN any of: travel ≥ testedTravelMult(2)×width / close crossed daily EMA20 / close crossed nearest HTF pivot (strongPivotTF Daily/Weekly). Tested → DELETED (no grey).
- **Visuals:** near-transparent fills (bgAlpha 93–96), thin borders (1px/2px controlling), **box-text labels** (left, vertically centred, 10-space indent, size.small), **per-TF label colours** (M amber/W white/D yellow/125 cyan/75 green), violation mark = tiny faint dot (was ✗). **Exclusive controlling** (only the DZ nearest ATH; demote prior on new-ATH). Controlling assessed on OWN TF only (native), HTF-via-security never controlling in LTF.
- **FVG Polygraph = Option C** (`require_intraday_fvg` default OFF): all intraday zones draw; FVG-backed (leg-out FVG) get ⚡ + brighter border, NOT filtered. Structural suppressed on intraday. LTF levels never shown on HTF, HTF shown on LTF (TF guardrails on f_zones FVG/pivot drawing too).
- **GO logic REDESIGNED** (Jay's Option A): `go = any_pa (PA battery, mode) AND support_pass (location) AND vol_ok AND bar_ok`. AVWAP/intraday now OPTIONAL timing (⏱). **bar_ok** (lenient) = green OR close in upper half (kills big-red distribution/upthrust GOs; a structural pattern like 3BR/VCP/BC can fire on a red new-high-then-close-red bar — bar_ok vetoes it). **use_closed_candle** (default ON) shifts TRIGGER/PA-grid/STATUS/RV/Support/markers to the LAST CLOSED bar ([_so]). Panel: TRIGGER/STATUS = `P·L·V·B` (+⏱); verdict "GO — arm buy-stop > bar high".
- **Plan SL fixed** (was ~24% far-AVWAP bug): now structural = demand-zone distal (in-zone→nearest below) → recent swing low → 2.5×ATR, capped 3×ATR, shows % risk.
- Panel rows: Support Zone (DZ⚡/FVG/Piv/AVWAP/EMA/~Fib), Zones (MTF) + `natC d/f/m/L` funnel diagnostic (still in — strip when zone tuning done), Room for Trade (overhead = nearest supply zone/flipped-pivot/HTF-pivot), Price vs EMA20, per-TF ageing/width inputs.

### B. GM Python — S4-GO preview + structural SL (weinstein_commander_web_v4.0.py + gm_trigger_board.py)
- **`_plan_structural_sl()`** (NEW) wired into compute_workflow + compute_recovery_workflow — nearest FRESH zone distal (OB/FVG/pivot D+W) below entry, 3×ATR cap. Fixes the GM's far-SL (EMA20-fallback on extended names).
- **`s4go_status()`** (NEW, shared in gm_trigger_board.py — zero-drift) = the S4 stage-2 gate mirrored → **gates-passed closeness score** `4/4 GO / 3/4 · no vol / 2/4 · no loc / n/a` (leading n/4 sorts desc). **S4-GO column** on the board (pinned by Category, coloured) + matching chip on Single Symbol. Two-stage kept: Category = stage-1 ARM (pa_fired, NO bar_ok); S4-GO = stage-2 (PA·loc·vol·bar). Location = GM's OB/FVG twin (S4 uses IZE) → strong predictor, not identical.
- **`gm_load_intraday` drops the FORMING bar** → reads last CLOSED bar (relvol/bar_ok/cmp). Added `bar_ok` (close-strength) to its return.
- **Maximized board** default-sorts by S4-GO closeness (single-glance monitor). Enables dropping the redundant auto-refresh board window (workflow #3).

### C. NEW FILE `Commander_S4_Trigger_Screener_v1.0.pine`
Lean, **ZERO request.security** Pine-Screener sibling of S4. Computes GO gate on chart TF (patterns copied verbatim; HTF+Stage-2-Launch dropped; location = EMA20/pivot proxy). Plots **Gates(0-4)·GO·Sigma·RV·Loc·Bar·FVG·LTP** columns + "S4 Screener GO" alertcondition. Bull/Recovery mode input. Apply on 75/125m, sort by Gates, one watchlist alert.

### Workflow optimizations shipped (all 3): #1 S4-GO preview on both GM surfaces · #2 lean Pine screener + alert · #3 maximized board as single monitor. Location-accuracy ceiling = GM/screener use OB/FVG/EMA proxy vs S4's IZE zones (port IZE→Python is the future big lever).

### NEXT STEP (Jay): **fine-tune the zone MARKINGS** — "some zones not drawn correctly, logic not followed" (proximal/distal on wrong candle, leg-in inclusion, width/offset, RBR-vs-DBR mislabels, spurious/missing zones). Awaiting a chart screenshot of a specific wrong zone + what it should be. Also pending: commit branch → main; RELIANCE Stage-4 exit; recompile S4 v3.0 + screener in TV (Jay); re-baseline validation (post bull_screener VCP (v*v) + Dhan date-shift fixes).

---

## 18 July 2026 — S4 Entry Trigger issues-list sweep (v3.5 → v3.9)

Worked `S4 Entry Trigger Issues.txt` end-to-end in `Section4_Entry_Trigger_v3.0.pine` (in-file title now **v3.9**). Rule reaffirmed: [[never_autocompile_tradingview]] — hand Jay the file, he compiles. Jay confirmed **v3.5 compiled clean**; v3.6→v3.9 are staged for one compile (each detection change has its own off-switch to isolate a regression). New memory: **[[s4_zone_tf_mismatch_and_diagnostics]]** (judge a zone on its OWN timeframe; the 3-lever diagnostic toolkit).

**Panel-restructuring decision:** v3.4 PANEL REBUILD is KEPT (Jay: "keep v3.4, resume other issues"). Did NOT redo the panel.

**Shipped by version:**
- **v3.5** — #1 trigger path-specificity (GO always needed PA; the 4 SHARED patterns Spring/Engulf/3-Bar/Pocket make it hold across a Bull↔Recovery flip → TRIGGER row now tags `⇄both` / `Bull-only` / `Rec-only`). #4 Daily zone label → light blue.
- **v3.6** — #47 load no longer forces a Trendline draw (removed all 12 `confirm=true` from manual box/TL → numeric inputs). #37 zone fill transparency = input `zoneFillTransp` (88, was 93-96). #41 "Show tested zones in grey" toggle (new `Zone.tested` field; greys+freezes instead of deleting, excluded from trigger/counts). #61 TRIGGER amber-when-waiting. #62 ANALYSIS row slimmed to VERDICT-only (`show_analysis`).
- **v3.7** — #34 narrow-zone wick-to-wick rescue (`narrowWickToWick`). #27 recency: displayed score decays formation→ageing-cap (`recencyDecay`/`recencyMaxDrop=20`, label + panel grade). Verified already-correct: #2 (ftLag/ftMaxRescue split), #3 (all 3 Controlling criteria), #5 (`use_closed_candle`), #29 (40-pivot pool per TF, M/W/D), #43 (wicky-FT cancel via noRevBull/noRevBear).
- **v3.8** (screenshot-driven, from CoalIndia-W/Caplipoint-W/Anandrathi-M/Acutaas) — **#25/#40/#42 HTF OVER-REMOVAL FIX**: the tested EMA/level cross referenced the DAILY EMA20 for W/M zones → a weekly zone died on a daily EMA cross (CoalIndia 3 of 37 weekly alive). Now EMA/level applies to DAILY zones only; W/M judged by TRAVEL (own-TF ATR) + VIOLATION. #59 phantom geometry → geometry connectors DRAWN (`drawGeomLines`). Pivot-zone toggle surfaced (relabelled `useStructural` → "Draw Pivot (Structural) zones" for isolation). **Daily/intraday under-marking → per-TF leg-in**: split the global `legin_atr` (raised 0.3→1.0 on 17-Jul, the recent tighten) into `legin_ltf` (0.6, intraday+daily) / `legin_htf` (1.2, weekly+monthly) — resolves the #35 tension (monthly strict, daily/intraday loose).
- **v3.9** — #30 S/R wick-pierce touches (`sr_wick_touch`: a level counts a pivot when its line threads the pivot's wick, not only the extreme; pierce-touch counted but doesn't drag the mean; feeds MTTWR). #31 rectangles drawn as a box for the "Range/rectangle" geometry. **#36/#40 D/W/M PATTERN FUNNEL** added to the diagnostics row (`pat D d/c·L  W d/c·L  M d/c·L`) — a missing daily/weekly/monthly pattern zone is now self-diagnosing (d=0 detection gate / d>0 c=0 EMA-RS-dedup / c>0 low-L removal).

**Answered (no code):** #26 (3 Controlling criteria present), #28 (HTF=High Tight Flag is in the bull battery; Bull Flag ≠ HTF), #32 (pivot zones share the pattern lifecycle; no volume profile anywhere), #33 (pivot = weaker secondary shelf; location/stop confluence, not standalone), #39 (pivot zones NEVER override pattern zones — pattern created first, wins dedup), #58 (Nearest-AVWAP vs S/R-nearest vs Support-Zone are 3 different fields), #60 (Structure basis says "above 30WMA", deliberately not "reclaimed").

**Still open (as of the v3.9 sweep):** #57 (needs Acutaas **75m** chart). Superseded below: the arrival/order-flow items shipped in v4.0.

### v4.0 (18 Jul) — Arrival Style + Order-Flow Footprint (quality-of-zones #4/#5)
- **Arrival Style** (pure geometry): velocity of the approach leg into the zone (ATR/bar) → FAST (sharp rejection likely) / GRIND (absorbing → bleed-through) / NORMAL. Inputs `arr_look` 20 · `arr_vel_fast` 0.5 · `arr_vel_slow` 0.22.
- **Order-Flow Δ** (bar-level PROXY, NOT true tick/aggressor delta — no TV plan exposes that to Pine): intrabar up/down-volume via `request.security_lower_tf` (`of_ltf` default 1-min; must be < chart TF), summed over `of_win` 5 bars + delta-divergence → ABSORBING Δ+ / BLEEDING Δ− / NEUTRAL.
- New **"Arrival · Δ" panel row** (row 26) + two confluence weights `cf_w_arrival`/`cf_w_absorb` (default 1, gated by `show_arrival`; they GRADE not GATE). Guide rewritten to **v4.0** (`Section4_Entry_Trigger_Guide.md`, comprehensive — 21 sections + Arrival section 6a).
- **Jay confirmed v4.0 compiled clean.**

### GM Board ↔ S4 GO mismatch — DIAGNOSED (not a bug), then the "big lever" started
Jay: board shows 5 names 4/4 GO but S4 shows no GO. Diagnosis (4 = "No PA", 1 = "No Location"):
- **Battery diff done — the 17 bull PA formulas are BYTE-IDENTICAL** between S4 `f_daily_pa` (chart-TF via `loc_*` when `use_chart_tf` ON) and Python `pa_patterns.detect_bull_patterns(intraday=True)`; both run on 75m bars. So the batteries are **NOT drifted** and S4's GO isn't broken. The "PA vs no-PA" gap is (a) **mode/path mismatch** (board's workflow path vs S4 Auto → different battery evaluated; the documented "Pine can't see GM's live Bull/Recovery decision" — set S4 Mode manually), (b) **feed data** (Dhan board vs TV S4 75m OHLCV, esp. volume on rv-gated patterns), (c) **snapshot staleness**. The 1 "No Location" = the OB/FVG/pivot-proxy vs IZE-zones ceiling.
- Jay's call: don't force agreement; instead do the pending **"port the S4 zone engine to Python"** (the big lever).

### **NEW `zone_engine.py`** — S4 IZE zone engine ported to Python (the big lever, phase 1)
Faithful port of the S4 Pine `f_detectZone` + lifecycle so the GM LOCATION gate uses the SAME leg-base-leg zones S4 draws (not the OB/FVG/pivot proxy). Ported: gap-bridged (invisible) candles, RBR/DBR/RBD/DBD, **per-TF leg-in (#35)**, wick distals + **narrow wick-to-wick (#34)**, per-TF width band, FVG-Polygraph tag, base/body/volume score, lifecycle (reaction → travel-tested in own-TF ATR + **daily-EMA-tested DAILY-only per the #25 HTF fix** → violation → calendar ageing), same-dir overlap dedup. Public API `detect_zones(df, tf)` + `zone_support(df, tf, px)`.
- **Smoke-tested (venv):** DBR/RBD detection, `at_support` inside a fresh zone (score 93) + the 1.5% "near" path, violation + reaction-travel lifecycle — all pass. Both `zone_engine.py` and `weinstein_commander_web_v4.0.py` `py_compile` clean.
- **Wired into the GM** location gate behind flag **`GM_USE_IZE_ZONES = False`** (weinstein_commander_web_v4.0.py, near `INHERIT_QUALIFICATION`): ON = an IZE demand zone (Daily + confirmed-Weekly) containing/near price ALSO satisfies `at_support` (superset with the proxy, toward S4 z_inDZ parity); OFF (default) = legacy proxy only. Fully guarded — any failure leaves the proxy untouched.
- **PHASE 2 DONE — the LOCATION HALF of S4's `support_pass` is fully ported.** Added to zone_engine.py: `detect_sr_levels`/`sr_support` (S/R horizontal levels — #30 wick-pierce touches + MTTWR grade + R↔S flip) and `avwap_support` (the 3 anchors Low/BO/Gap → `near_avwap`). Wired both into the GM gate under `GM_USE_IZE_ZONES`. **GM location gate (flag on) now = IZE zones + FVG/pivot proxy + `near_sr` + `near_avwap`.** All smoke-tested on real Dhan data (merged table verified: each source contributes distinctly — RELIANCE via IZE zone, COALINDIA via proxy+AVWAP). **Deliberately EXCLUDED `near_ema`** — it fires near the daily EMA20 most of the time and would make the board OVER-predict 4/4 GO (the board is a predictor; precise sources = better predictor; S4 includes near_ema only because the S4 chart is final).
- **STILL DEFERRED — display/scoring ONLY (NOT location):** recency-decay display, Controlling 3-criteria promotion, geometry/rectangles, manual trendlines.
- **NEXT:** A/B-validate `GM_USE_IZE_ZONES=True` against S4 on a few live names (Jay reads S4, compares the board's location), then flip the flag on + decide OR-vs-replace on the proxy merge.

### Late-session (18 Jul, evening) — "zero GOs" investigation → CRITICAL v4.1 bugfix + v4.2 verdict

**Jay's complaint:** GM board dropped from multiple S4-GOs (60-70% converting on S4) to ONE (CDSL), S4 showing none — "the levers are meant to strengthen identification, not filter everything out."

**Diagnosis chain (each step measured, several early hypotheses corrected by Jay):**
1. Funnel on the REAL 39-name board universe (`FINAL_GOLDEN_MATCHER.csv` — NOT the 11-name union I first measured): PA 31% · location 46% · RV≥1.0 only **26%** (median RV 0.70, quiet Friday) · clean bar 56% → exactly 1 GO. Chartink scans genuinely thin (Hunter **1**, EarlyBird 1, Leaders 2 — auto-pilot log shows ✅ success, market breadth is real). Weekend = one frozen bar. **The levers were NOT the cause.**
2. De-tightenings shipped anyway (both measured): `legin_htf` 1.2→**1.0** (the 1.2 was a global tighten off one Acutaas chart); `sr_mttwr_n` 4→**6** in BOTH Pine and zone_engine.py (measured: 40-45% of all levels graded MTTWR → near_sr effectively never fired; at 6, RELIANCE's 5-touch shelf 0.2% below price is usable again). #30 wick-pierce was tested and exonerated (identical MTTWR counts ON/OFF).
3. **CDSL Σ mismatch (GM Rec Σ+3 "Higher-Low/2B" vs S4 Σ0, SAME Recovery path) → REAL BUG FOUND, v4.1:** `f_daily_pa`'s `_o = confirm_daily ? 1 : 0` shift was applied to BOTH the daily security call (correct) AND the chart-TF `loc_*` call (WRONG) → with defaults (use_chart_tf ON + confirm_daily ON) the S4 battery evaluated the bar BEFORE the last closed one; live it compounded with `[_so]` → up to 2 bars stale, silently eating triggers. Proof: CDSL 2B=+3 on last bar, 0 on bar[-2], daily AND 75m. Fix: `confirmShift` param (daily call true, chart-TF call false). **Likely the true cause of the GM→S4 conversion collapse.** Jay recompiled v4.1 → S4 CDSL now shows Rec Σ+3 ✓ (parity restored), blocked only by volume (RV 0.72, legit).
   *Memory lesson updated ([[zone_engine_port]]): when two surfaces disagree, diff the EVALUATED BAR/offset, not just the formulas; I had only diffed the BULL battery while claiming parity generally — the failing case was RECOVERY.*
4. **v4.2 — VERDICT now RULES (Jay: "give a clear direction from ALL the key metrics"):** 5 rulings — TAKE IT / SKIP (GO but in-supply·<1R room, or neither house gate) / **NOT TRADEABLE** (blocked AND in-supply — "clearing that gate alone will NOT make this a trade", the CDSL case: volume-blocked but INSIDE supply with −0.1R) / LOW QUALITY (GRIND arrival Δ−) / ARM (names the one missing gate + what to watch). **Multi-line** (`\n` in one cell — a single long sentence was stretching the panel over the chart): headline / reason / disqualifier / metrics digest / action. Digest line = Loc sources (DZ/S-R/AVWAP/EMA20 +★ctrl ×NTF) · room R · arrival+Δ · RV · conf · path Σ. **Arrival · Δ row moved to row 14 (directly above TRIGGER)**; rows 14-25 shifted +1 (TRIGGER 15 · Plan 16 · Entry 17 · Qty 18 · PA 19-22 · Structure 23 · STATUS 24 · VERDICT 25 · Diag 26); verified rows 0-26 unique, both f_row AND raw table.cell forms. `_mx` built with successive assignments (wrapped-expression indent trap). `_roomTag`/`_arrTag` retired.

**PENDING: Jay to compile v4.2** (carries: multi-line ruling verdict + Arrival row move; v4.1 stale-bar fix + de-tightenings already compiled in). Then Monday live session = the real conversion test. Infra bugs spotted in logs, unfixed: dhan_marketfeed asyncio "no current event loop in thread" crash (recurring), NSEFetcher archive failure.

---

## 19 July 2026 — S4 review batch (v4.1→v4.7) + zone/S-R Python port + infra

> **▶ NEXT SESSION — START HERE (state as of session end):**
> - **S4 `Section4_Entry_Trigger_v3.0.pine` = v4.7, COMPILED CLEAN by Jay.** No pending Pine edits. 14-item review essentially closed (code: 1,2,2b,3,4,7,8,10,12a,12b,13 + ABBOTINDIA/APOLLOHOSP fixes; answered: 5,6,9,14).
> - **`dhan_marketfeed.py` fixed (asyncio loop) — proven, Python, no compile.** LTP overlay should stream in market hours.
> - **RELIANCE Stage-4 exit DONE.** Jay working 2 other red holdings.
> - **Immediate open items (Jay's call):** (1) **re-baseline validation** — worth running given all the detection changes (v4.1 stale-bar fix, de-tightenings, zone/S-R); ~2-3h. (2) **A/B `GM_USE_IZE_ZONES` vs S4 then flip** (default False, inert now). (3) **#11 rectangles** — Jay to test `geo_flat` 0.5-0.6; if an obvious range still won't draw, upgrade the 2-pivot classifier to multi-pivot. (4) commit branch → main.
> - **Do NOT re-chase "the batteries drifted"** — formulas are identical; disagreements are evaluated-bar (fixed v4.1), feed (Dhan vs TV), or mode/path. See [[zone_engine_port]].
> - **Jay = advisor/coach relationship, NOT a tip service** — sharpen the tool + pressure-test his read; his eyes win over the mechanical verdict.
>
> **PYRAMID / RISK SHIELD work (end of session, Python — RESTART Web Commander):**
> - Jay: Risk Shield's AI Analysis contradicts the pyramid module + no revised SL shown on the add. ROOT CAUSE: two brains that never talked — `pyramid_logic.classify()` (deterministic ADD rule) vs the Active-Exits LLM (`get_stock_context_and_ai_review`, prompted ONLY for hold/trail/exit, never told the module verdict).
> - **Fix 1** (`pyramid_logic.py` classify ADD branch): surface the revised stop — the catalyst-aware **Chandelier** (via `risk_common`) was ALREADY computed in the row (`row['chandelier']`), just not shown. ADD reason now says `RAISE stop → ₹X (from ₹Y)` — GUARDED: only when Chandelier > current stoploss (else `keep stop ₹Y`, never a silent lower).
> - **Fix 2** (`weinstein_commander_web_v4.0.py` ~14252 + `get_stock_context_and_ai_review` OCO path): pass the module's `pyr_class`/`pyr_reason`/Chandelier into the AI prompt → the AI now RECONCILES (agree, or say why not; for ADD judge extended-or-not + confirm raise-stop) instead of contradicting.
> - **Both compile clean.** The dedicated **Pyramid/Trim tab (Tab 2)** was already well-built — `render_section` shows a `chandelier` column (= the revised stop) + the trigger reason; the AI-contradiction was only in the Active-Exits tab (Tab 1).
> - **NOT done (offered):** ADD-table column-clarity pass (rename/highlight `chandelier` → "Revised Stop / Raise-to"); an add-SIZE / combined-risk helper (needs Jay's capital + risk% — deliberately not guessed). ADD size stays the trader's discretionary call.
>
> **VALIDATION RE-BASELINE — DONE, and it's a MILESTONE (22-Jul run `20260722_135745`, bull, 24mo nifty500, catalyst-aware, 20 anchors/464 picks):** the VCP `(v*v)` fix + Dhan date-shift fix turned a NO-EDGE screener into one that clears the overfit gate. Mean matched alpha **−1.53% → +2.56%**, win **21.7% → 53.4%**, anchor hit **25% → 65%**, bootstrap prob-positive 80.2%. **Both families positive: POS +2.38% (120d), SWG +2.76%/61%win (60d) — SWG was the June −1.31% DRAG, now a contributor** (the VCP fix cleaned up the bleeding swing book). **OOS hard gate now ✅ PASSES** (was FAIL in June): IS α +0.66% / OOS α +1.41%, OOS/IS Sharpe 3.34 — edge persists & strengthens OOS → **Phase 3 (fitted weights) is UNBLOCKED**. Caveats: bootstrap CI95 [−1.44,+3.08] still straddles zero (20-anchor small sample); POS median −1.17% (lumpy, big-winner-carried, correct trend profile); RECOVERY screener NOT re-baselined (the slow ~2-3h run).


Long session driven by Jay's 14-item S4 review, then live-trade reconciliations. All S4 changes in `Section4_Entry_Trigger_v3.0.pine` (now **v4.7**, Jay compiles each). Every scripted edit runs an odd-quote + row-uniqueness sweep (new memory [[bash-heredoc-de-escapes-backslash]] — Bash heredoc de-escapes `\n` → corrupts Pine strings; build escapes with chr(92) or use Edit/Write).

### S4 versions this session
- **v4.1 CRITICAL** — PA battery read a STALE bar: `_o = confirm_daily?1:0` was applied to BOTH the daily-security call AND the chart-TF `loc_*` call → with defaults the 75m battery evaluated the bar BEFORE last-closed (compounded with `use_closed_candle` [_so] → up to 2 bars stale, eating triggers). Fixed via `confirmShift` param. **The likely cause of the GM→S4 GO conversion collapse.** ([[zone_engine_port]] lesson: diff the EVALUATED BAR, not just the formula; the failing case was RECOVERY, which I hadn't diffed.)
- **v4.2** — VERDICT rules (TAKE IT/SKIP/NOT TRADEABLE/LOW QUALITY/ARM), multi-line, weighs full panel; Arrival·Δ row moved to 14 (above TRIGGER).
- **v4.3** — #1 draw the "must clear" obstacle on chart; #2 controlling zones were STRUCTURALLY DEAD (D/W/M passed ctrlAllowed=false — real bug, trend-reversal never counted); #3 over-extension → verdict; #4 EMA20-far zone-quality malus; #13 round numbers +1 confluence.
- **v4.4** — #2b controlling M/W/D only (never intraday-native); #7 same-base zone dedup (`dedupSameBase`); #8 S/R wick-fit line placement (`sr_wick_fit`); #10 daily-battery-agreement +1 confluence (NOT a gate — Jay agreed); #12a dynamic risk (Kelly×vol×regime, Risk Allocator §9 port) in Qty row.
- **v4.5** — #8 refine (count is pivots-only; line stays on max-wick set, no mean-drift); #12b TRADE-TYPE plan (Risk Shield is_swing: ATR%>4 / off52>30% / below-200 → SWING else POSITIONAL → sets SL cap 2.5×/4.0× ATR + R-targets swing 3R/5R · pos 5R/10R · Recovery T2=52WH).
- **v4.6** — ABBOTINDIA: ext-ATR unit bug (daily-EMA20 distance ÷ 75m ATR inflated ~3×; use atrD_tf); WEAK-LOCATION guard (GO on AVWAP/EMA only, no zone/S-R → "CAUTION momentum/chase", not TAKE IT — this is why GM read "No location", both now consistent).
- **v4.7** — APOLLOHOSP: BLUE-SKY/BREAKOUT-PIVOT ruling. A Stage-2 leader (above 30WMA+200DMA) within `ath_prox_pct` (3%) of its 52W high sitting in a supply band is a CONTINUATION pivot, not distribution — verdict reframes "SKIP·no room" → "BREAKOUT PIVOT: don't buy here, arm buy-STOP above the band ceiling, blue sky above". Only Stage-2 (a Stage 3/4 lower high stays a real SKIP). **Trading doctrine agreed:** ATH-pullbacks = often the best Minervini setups; buy the breakout ABOVE the pivot (never in the resistance), trail (blue sky, no fixed target); confirmation-before-entry = alert at the level → wait for a CLOSED 75m bar above on volume → buy-STOP above THAT bar (never a resting GTT at the level → false-breakout trap). GTT is for the SL once in.

### Python (all inert until Jay flips flag / re-baselines)
- `zone_engine.py` LOCATION port now complete: IZE zones + S/R levels (`detect_sr_levels`/`sr_support`, #30 wick-pierce + MTTWR) + AVWAPs (`avwap_support`, Low/BO/Gap → near_avwap). Wired into GM gate behind `GM_USE_IZE_ZONES=False`. near_ema deliberately excluded (over-predicts). `sr_mttwr_n` 4→6 (Pine+Py; 40-45% of levels were MTTWR → near_sr never fired). **A/B-validate vs S4, then flip.**
- **`dhan_marketfeed.py` FIXED (19-Jul):** the recurring "no current event loop in thread 'dhan-marketfeed-gN'" crash = DhanFeed.__init__ calls asyncio.get_event_loop() (SDK marketfeed.py:48), which raises off the main thread (Py 3.10+). Fix: `asyncio.new_event_loop()+set_event_loop()` in the worker before constructing the feed. **PROVEN** (repro without / clean with). LTP overlay should stream during market hours now.

### Jay's framing (this session)
"You are my advisor and coach" — NOT a tip service. He does his own analysis; only trades on his own conviction. My role = make the tool honest/sharp so his read has better inputs, and pressure-test his analysis. When the verdict and his chart-read diverge, his eyes win. Don't over-trust the mechanical verdict.

### Done / open
- **RELIANCE Stage-4 exit DONE** (Jay, GTT sell, 18-Jul) — long-pending litmus finally closed. Two more red holdings he works today.
- **Open:** #11 rectangles (Jay to test geo_flat 0.5-0.6; classifier+draw verified sound, only-2-pivots may be too coarse → multi-pivot upgrade if his chart shows an obvious range not firing) · flip GM_USE_IZE_ZONES after A/B · re-baseline validation (post the many detection changes) · commit branch `phase0-1-attribution-journal-snapshot` → main.

---

## 23 July 2026 — GM+S4 GO-gate backtest: the GO gate is a CLASSIFIER, not an entry optimizer

Branch `phase0-1-attribution-journal-snapshot` (uncommitted). Ran the two 24mo nifty500 bull S4-GO validations built last session (`validation.py --gate s4go`, catalyst-aware windows, bootstrap 10k) — ARMED (`20260723_062636`, Stage-2+RS qualify) and CATALYST (`20260723_063652`, strict catalyst). Compared per-trade **matched-horizon alpha** vs the buy-at-anchor-close baseline `20260722_135745` (+2.56% mean, the VCP-fix milestone).

### Verdict — GO-timing ERASES the entry edge (per-family × direction, never pooled)
| | Baseline buy@close | S4GO-ARMED | S4GO-CATALYST |
|---|---:|---:|---:|
| Fill % | 100 | 66.3 | 64.9 |
| n trades | 464 | 1942 | 268 |
| **Mean matched α** | **+2.56%** | **−0.03%** | **−0.02%** |
| Win % | 53.4 | 32.4 | 34.3 |
| Bootstrap prob(α>0) | 80.2% | 33.2% | 18.9% |
| OOS gate | ✅ PASS (Sharpe 3.34) | ⚪ NO-EDGE (IS α −0.32) | ⚪ NO-EDGE (IS α −1.06) |

Per-family: POS/WYC·UP +3.47%→−0.13%, SWG·UP +2.80%→−0.09%, SWG·DOWN +2.54%→−0.2%. Only POS-ACCUM·DOWN survives (n=6-7, +2.3%). Not a composition artifact — holds cell-by-cell. Both OOS runs are un-gateable (IS α ≤ 0 → "fix the edge, not overfitting").

### Mechanism (the recurring lesson, re-measured) — [[s4go_timing_gate_backtest]], [[pa_conversion_and_signal_lessons]]
GO entry = **buy-STOP above the confirmed breakout bar** → higher entry against the SAME structural SL (distal / 10-bar swing low, 3×ATR cap in `replay._structural_sl`) → thin R → **67-69% stop out at ~7-8 days for −2% mean / 6-10% win**. The 33% survivors (trail-SL + time-expiry) are excellent (+3.4% to +13.8%, 84-100% win). Stop-outs bleed the mean to zero. **The GO gate cleanly classifies runners vs shakeouts; the SL geometry is what's broken.** Signal generation > exit calibration, again.

### Follow-up A/B IN FLIGHT — wider GO stop
Added a backward-compatible `sl_floor_by_family` knob to `replay._structural_sl` / `s4go_forward_trade` / `run_s4go_replay` (default None = reproduces the catalyst run byte-for-byte). Harness `s4go_stop_ab.py` qualifies each catalyst anchor ONCE (cached) then sims 3 stop configs on identical candidates: A0 control (no floor) · A1 flat 1.5×ATR floor · A2 catalyst-aware (SWG 1.5, POS/WYC/REV 2.5). Testing the classifier→stop hypothesis: does an ATR-floor stop (don't let tiny structures make razor-thin stops) recover the buy@close edge on GO-timed entries.

**A/B RESULT — hypothesis REFUTED (wider stop does NOT recover the edge):**
| config | mean α | median | win% | SLhit% | hold |
|---|---:|---:|---:|---:|---:|
| A0 control | −0.02% | −1.19% | 34.3% | 69% | 8.4d |
| A1 flat 1.5× | −0.23% | −2.63% | 30.6% | 68% | 16.8d |
| A2 catalyst-aware | +0.16% | −2.92% | 30.2% | 58% | 24.4d |

The floor worked mechanically (SLhit 69→58%, hold 8→24d) but mean barely moved while **win% dropped (34→30) and median got much worse (−1.19→−2.92)** — widening the stop just converts quick −2% shakeouts into slow, LARGER losses. **The GO penalty is the buy-STOP ENTRY (buying higher after confirmation), not stop width — you can't stop-tune out of it.** Only exception: **POS-ACCUM** (180d accumulation) genuinely wants the long leash — A2 lifts it +0.69→+2.87% (win 42→45%), POS-ACCUM·DOWN +2.32→+6.69% — but n=38 and still below its +1.93% buy@close baseline. SWG gets WORSE with a wide stop (−0.10→−0.43%; short-horizon books bigger losses); POS·DOWN −0.49→−3.97%. **Conclusion: GO gate stays a trade CLASSIFIER, not an entry optimizer. Don't promote as entry filter, don't flip GM_USE_IZE_ZONES.** All A/B code inert by default (`sl_floor_by_family=None`). Artifacts: `validation_runs/_ab_{A0,A1,A2}_details.csv`, log `_s4go_stop_ab.log`.

### Fix-1 A/B — RETEST ENTRY (the real fix candidate: attack the ENTRY, not the stop)
Diagnosis: the GO penalty is the buy-STOP entry (chasing the breakout extension above the confirmed bar's high) — a permanently higher entry vs buy@close. Fix-1 (`replay.s4go_forward_trade` new `entry_mode`; default `"buystop"`=unchanged, `"retest"`=buy-LIMIT at the confirmed GO-bar CLOSE, fill on first pullback within `retest_window`, forward-only) buys VALUE not the extension. Harness `s4go_entry_ab.py` (reuses `_ab_qual_cache`).
| config | mean α | median | win% | SLhit | hold | fill (OK) |
|---|---:|---:|---:|---:|---:|---:|
| B0 buystop (control) | −0.02% | −1.19% | 34.3 | 69% | 8.4d | 268 |
| **R_retest** | **+0.38%** | **−0.73%** | 33.8 | 64% | 8.4d | **320** |
| R_retest+POS-floor | +0.29% | −2.76% | 32.2 | 54% | 25.8d | 320 |

**Retest is a genuine, consistent improvement over buystop across EVERY family** (POS-ACCUM +0.69→+2.60 even w/o floor; SWG·DOWN −0.18→+0.89 win 27→52%) and fills 52 MORE names (buy-stop rejected 63 that never made a new high; retest only skips 11). It also matches Jay's own [[confirmation-before-entry]] doctrine (confirm→enter on the pullback, NOT chase). **BUT it recovers only ~0.4 of the 2.6pp gap to buy@close** — the residual is the structural **confirmation-wait tax** (waiting entry_window days for the GO to fire means winners already moved; not fixable by entry tweaks). Stacking the POS floor on retest again wrecks the median/SWG → floor is POS-ACCUM-only.
**Net verdict: adopt RETEST as the GO entry convention (strictly better than buy-stop). Default flipped to `entry_mode="retest"` (`replay.py`, commit 5f3e151; validation inherits).** GO-timing's matched-alpha ceiling is buy@close minus the wait tax.

### THE REFRAME — GO-confirmation is a strong SELECTION FILTER (GM+S4 is NOT a laggard, it was scored in the wrong job)
Scored GO on the right axis: split the SAME catalyst picks (buy@close baseline) by whether a confirming GO fired within the window.
| cohort | n | buy@close mean α | win% |
|---|---:|---:|---:|
| **GO-CONFIRMED** | 331 | **+3.36%** | 53.5% |
| **GO-NEVER** | 82 | **−1.32%** | 43.9% |
| **edge** | | **+4.68pp** | **+9.6pp** |

Concentrated in the positional DNA: **POS-ACCUM +10.57pp** (conf +3.72 vs never −6.85), **POS/WYC +8.45pp** (+4.15 vs −4.30), **SWG +0.43pp** (no selection value on swing). Caveat: partial endogeneity (never-trigger = never-momentum), but confirmation needs only a trigger in ≤40d vs full-horizon return, and the +9.6pp WIN-rate gap says it's real. **GM+S4's alpha is real but lives in SELECTION (which positional catalyst names to trust/size), NOT entry timing (wait tax kills it).** Architectural repositioning: GO = conviction/quality filter on positional picks (confirm=high-trust hold, never-confirm=fizzle to drop/shrink), entries at/near signal (retest), don't run the filter on swing. **This VINDICATES the GM+S4 build — a discriminator that was being measured as a stopwatch.** [[s4go_timing_gate_backtest]].

### GO-as-filter OOS VALIDATION — PASS, edge STRENGTHENS out-of-sample (`s4go_filter_oos.py`)
60/40 chrono split (robust at 50/50). The discrimination does NOT decay OOS — it grows (opposite of overfitting):
| window | confirmed | never | edge | win-edge |
|---|---:|---:|---:|---:|
| IN-SAMPLE (11a) | +3.78% | −0.00% | +3.78pp | −1.6pp |
| **OUT-SAMPLE (7a)** | +2.52% | **−4.01%** | **+6.54pp** | **+32.5pp** |

POSITIONAL subgroup looked clean in both windows (+8.34pp IS / +9.56pp OOS). **⚠️ THIS RESULT WAS SUPERSEDED — see the next block.**

### GO-as-filter CLEAN HARNESS — thesis LARGELY FAILED (`s4go_confirm_ledger.py`); do NOT wire it
The `s4go_filter_oos.py` "PASS" was ENDOGENOUS: forward-detected confirmation ([D, D+40]) overlapped the outcome window ([D, D+H]) → "it rallied so it both confirmed and returned." The clean harness detects confirmation in the DISJOINT TRAILING window [D−w, D] (also the true live semantic), then measures forward alpha [D, D+H]. Result: the edge was mostly artifact.
- Pooled "edge" tracks WINDOW LENGTH not filter strength (cw5 +2.04pp / cw10 +2.57 / cw20 +4.09 / cw40 +5.57) — longer window shrinks the never-cohort to a tiny extreme tail that inflates the number.
- **On clean OOS POSITIONAL data (the real use case) confirmation does NOT help — the never-cohort BEAT confirmed at every window with any never-names (cw5 −2.07pp, cw10 −11.61, cw20 −16.24; all tiny-n).** At the live-realistic cw5 ("GO fired this week") positional edge ≈ +1.4pp, ZERO win-rate edge, negative OOS.
- GO-confirmation is largely REDUNDANT with catalyst qualification for positional names (~90% confirm within 40 bars). A modest SWING win-rate edge (+8–12pp win) partially survives — opposite of the endogenous claim, and not where the filter would run.
- **Verdict: do NOT wire a positional conviction/size flag on this.** Honest walk-back of the "vindicated" call. The harness now STANDS to accrue genuinely-prospective rows (schedule `s4go_confirm_ledger.py --mode record` live, no `--as_of`); revisit in months with a PRE-REGISTERED short window + minimum never-cohort — do not act on 4–16 name cells. [[s4go_timing_gate_backtest]]. Commit chain: 66a9e89 stop-A/B · ed9c719 entry-A/B · 5f3e151 retest-default · a6c3a28 filter-value · 5018c03 filter-OOS(endogenous) · cb9f983 clean-harness+correction.

### ⚠️ JOURNAL BASELINE CORRECTION (Jay, 23 Jul) — the −₹4.99L/−₹5.55L is NOT the system
Every prior note that cites the reconciled journal loss (−₹4.99L / 25% win / 0.24 PF, "true baseline") as a system indictment is WRONG. Two corrections from Jay: (1) it's substantially TAX-LOSS HARVESTING — 21 of ~25 harvest exits were a single 2026-03-30 FY-end batch (March −₹6.46L); (2) **those harvested names were RANDOM/discretionary picks that NEVER came from the Catalyst/GM+S4 system** (ETFs + large-cap defensives: SILVERIETF/BANKBEES/ITBEES/HINDUNILVR/ICICIBANK/LT/HCLTECH…). They are out of scope for any system assessment. The journal mixes system + hand-picked trades and **cannot be separated retroactively → NO clean live system track record exists.** The ONLY clean evidence on the system is the backtest (+2.56% selection alpha, OOS PASS), and it's positive. Forward fix: only GM/Catalyst-entered trades carry a true entry snapshot (`snapshot_meta='recompute'`+`setup`) — build the system-only live record from THOSE going forward; `performance_attribution.py` should segment SYSTEM-tagged vs discretionary. [[journal_loss_harvesting_correction]]. Do NOT prioritize exit-architecture on the strength of the journal loss — it never measured the system.

### Standing conclusions / DO-NOT
- Do NOT promote the GO gate as a matched-alpha entry filter and do NOT flip `GM_USE_IZE_ZONES` on these numbers — location isn't the weak link, stop geometry is.
- GO gate stays a live *arming/focus* tool (the [[gm_early_s4_execute_twostage]] doctrine is intact — GM arms, S4 GO times); the backtest is about matched-alpha entry optimization, a different question.

### Open (unchanged + new)
- Wider-GO-stop A/B (in flight, above) → if it recovers the edge, that's the real Phase-3 unblock path for the timed entry.
- Prior open: #11 rectangles · flip GM_USE_IZE_ZONES after A/B · commit branch → main · RELIANCE done.

---

## 23 July 2026 — Gemini audit review + remediation (memo + cheap wins + data cleanup)

Jay had Gemini run an "unbiased institutional audit" of the GM + S4 ecosystem (report at
`~/.gemini/antigravity-ide/brain/.../institutional_trading_ecosystem_audit.md`) and asked for MY
recommendations, not implementation. Fact-checked every concrete claim (file:line), then — on Jay's
go-ahead — shipped the small filtered-to-context subset. Branch `phase0-1-attribution-journal-snapshot`.

### The audit's verdict: a generic HFT-infra review that graded a positional/swing desk as a low-latency execution desk
**4 of 9 concrete claims FALSE:** Pine "v5" (all v6); MTF "look-ahead bias" (every `request.security`
uses `lookahead_off` + confirm/closed-candle guards); "no slippage" (`replay.py` has 0.10%/leg cost +
bar-by-bar SL/T1/T2 + gap-fill + armed-vs-filled); "heavy iterrows/apply" (zero in bull_screener).
**2 TRUE-but-already-disclosed:** survivorship (`validation.py:92-96` labels alpha an "upper bound");
Section4 332KB (real, but nowhere near TV's token/scope limit). **3 real:** dual-feed drift (already
mitigated via As_Of/Stale_Data), the manual webhook, no drawdown circuit-breaker. The audit **never
assessed EDGE** — Jay's own work already did that far more rigorously (matched-horizon WF + bootstrap
CI + OOS gate → +2.56% selection alpha, OOS PASS; GO-gate-is-a-classifier). REJECTED as category error:
Kafka/Redis-Celery/FIX/OMS-EMS/NautilusTrader/Mumbai-VPS/Docker-Grafana/Polars/full-DuckDB — none fit
8-week-to-8-month holds with confirmed-bar buy-stop entries. Memo lives in the plan file
`~/.claude/plans/i-asked-gemini-to-generic-noodle.md`.

### Shipped (all zero-drift, no signal/backtest/Pine changes → NO re-baseline, NO TV recompile)
1. **Symbol normalization consolidated (1A):** `gm_trigger_board._canon_key` was a WEAKER duplicate
   (prefix/suffix strip only, disagreed on `_`/`-`/`&`) — the [[gm_symbol_ns_normalization]] bug class.
   Now delegates to the authoritative `dhan_ohlcv.canonical_nse_symbol` (scrip-master, separator-
   insensitive) with a guarded fallback to the cheap strip if the resolver is unavailable (board never
   hard-fails offline). Verified: `BAJAJ_AUTO`/`BAJAJ-AUTO`→`BAJAJ-AUTO`, `M&M`/`M_M`→`M&M`.
2. **Manual webhook HARDENED, kept manual-launch (1B) — `dhan_tv_webhook.py`:** `DRY_RUN` default→**True**
   (live is now explicit opt-in `DRY_RUN=False`); margin check is now **BLOCKING** (was "continuing
   anyway" — placed orders with balance unverified); NEW hard pre-trade risk gate `pre_trade_risk_check()`
   before `place_forever` (max open positions / single-sector cap via `ai_risk_manager.analyze_sector_
   concentration` + `sector_lookup` / per-trade risk-% of equity — rejects on breach, degrades OPEN only
   when a sub-check genuinely can't compute); NEW in-memory idempotency dedup (same ticker+entry inside
   `WEBHOOK_DEDUP_WINDOW_S` → rejected). Env knobs: `WEBHOOK_MAX_OPEN_POSITIONS`=15, `WEBHOOK_SECTOR_CAP_PCT`
   =25, `WEBHOOK_MAX_RISK_PCT`=1.5, `WEBHOOK_DEDUP_WINDOW_S`=120. Archived the weaker duplicate
   `webhook_daemon.py` (a 2nd FastAPI handler with `place_order` and NO risk check) → `_archive/legacy/`.
   **Also fixed a latent launch crash:** `dhan_helpers.py` did a HARD `from dhanhq import DhanContext`
   which does NOT exist in dhanhq 2.0.x → crashed EVERY consumer (incl. the webhook) at import. Guarded
   it (DhanContext used only by `get_client()`, which no webhook path calls; now raises a clear error if
   actually needed). This is the [[dhan_data_feed_wiring]] "DhanContext missing" issue at the dhan_helpers
   root, not just the gtt_auto_shield wrapper.
3. **Operator risk ALARMS (1C) — `scheduler_daemon.py`, notify-only, NEVER liquidate:**
   `job_stale_feed_check` (every 15m in market hours; pulls a bellwether LTP via `data_provider.get_ltp`,
   checks `get_last_source` ∈ {dhan-ws, dhan-ltp}; EDGE-triggered — one alarm on DOWN, one on RECOVER =
   the audit's "stale feed disconnect guard") and `job_daily_pnl_alarm` (book unrealised-PnL drawdown from
   live Dhan holdings, `PNL_DD_ALARM_PCT` default −3%, once-per-day latch, cash-park `LIQUID*` excluded =
   the manual-desk form of the audit's circuit-breaker). Both reuse the existing `send_telegram` proxy sink.
4. **Data cleanup (Tier 2, honestly scoped — NOT a DuckDB migration; state was already clean):**
   deleted 3 zero-reference orphan DBs (`dhan_journal.db`, `weinstein_base.db`, `journal.db` — all 0-byte;
   the `load_journal_db` refs are a FUNCTION name reading trade_journal_v6.db, not the file) → backed up to
   `_archive/orphan_dbs_20260723/`. NEW shared `io_utils.atomic_write_text` (hoisted from gm_trigger_board,
   which now re-exports it); routed the 4 plain-`to_csv` state writes through it (matcher's single
   `save_with_golden_schema` choke-point → every `FINAL_*.csv`; `gmail_dispatcher` MASTER_Golden_Picks;
   `catalyst_sentinel` both history CSVs). Deliberately did NOT migrate the Parquet OHLCV cache (already
   the right shape) and recommended AGAINST the full DuckDB consolidation Jay initially picked (busywork).

All verified with mock-Dhan unit tests (dedup, 3 risk gates, feed edge-trigger, PnL latch, atomic
round-trip, re-export, canon). 9 files `py_compile` clean incl. the web app. **STANDING: restart the
scheduler daemon (new jobs) + Web Commander (Python changes).** Committed on the branch.

### Relationship note (reaffirmed)
Jay = advisor/coach, not a tip service. He wanted the audit pressure-tested, not obeyed — the value was
separating the 3 real gaps from the institutional-cargo-cult, and refusing the DuckDB busywork even though
he'd selected it. [[second-order-review-before-done]] applied throughout.

### Open (unchanged)
- #11 S4 rectangles (Jay to test geo_flat) · flip `GM_USE_IZE_ZONES` after A/B vs S4 · merge branch → main
  · recompile S4 v4.7 already done · RECOVERY-side validation re-baseline still pending (slow run).

---

## 26 July 2026 — Institutional benchmark audit → CRITICAL horizon bug → P0/P1/P2 remediation

Jay asked how the ecosystem compares to professional trading operations. Audited the CODE (3 parallel
explorations: backtest rigor, risk/portfolio construction, scale) rather than these notes — and
verifying the headline number found a material measurement bug.

### ⚠️ SUPERSEDES the 22-Jul "MILESTONE" block above
`replay.py:430` (`forward_returns_with_exits`) benchmarked the catalyst's **full design window**
(120/180d) against a stock leg that had usually exited far earlier. **428 of 464 trades (92%) closed
before their benchmark window did**; the 180d bucket held a MEDIAN of 29 days vs a 180d index return.
The same file already did it correctly in `s4go_forward_trade` (`xb = eb + res["days_held"]`).

**Same 464 trades, both conventions (run `20260726_225547`, deterministic re-run):**

| | OLD full-window (bug) | NEW actual-hold (fixed) |
|---|---:|---:|
| Mean matched α | +2.57% | **+0.80%** |
| Median | +0.63% | **−2.38%** |
| Win rate | 53.4% | **32.1%** |

Consequences: (a) the "+2.56% milestone" was ~2/3 artifact — the real edge is **~+0.7–1.0%/trade**,
bootstrap CI `[−0.8, +2.5]`, prob-positive 81.9%, and **the MEDIAN trade loses to the index** (a
big-winner-carried trend profile, not a 53%-win system); (b) **"breakouts behave defensively in DOWN
tapes" WAS this artifact** — an 8-day stop-out at −3% vs a 120d index at −10% books +7% of fake alpha;
stops truncate the stock leg but never the benchmark leg. **Retire that interpretation.** Memory:
[[matched-horizon-means-actual-hold]].

### OOS gate re-derived (+ NEW purge/embargo)
`walkforward_oos.py` gained `--embargo_days` (default 45; 0 = old leaky behaviour, 252 = strict
no-overlap). Anchors are 30d apart but windows run 30–180d, so IS/OOS trades overlapped in calendar
time with zero gap. Corrected run: **PASS at 0d (ratio 1.55) and 45d (1.21); STOP at 252d (0.17).**
Read that carefully — **OOS alpha is +0.69% and identical at every embargo setting; only the IS
baseline moves** (252d leaves 4 anchors with a freak 100%-hit Sharpe of 1.58). The 252d STOP is a
small-sample denominator artifact, NOT edge decay. Real lesson: the "60% of IS Sharpe" gate is
poorly conditioned at n≈10 — it compares two noisy point estimates with no standard error.

### The benchmark answer (assessment, full text in `~/.claude/plans/for-my-trader-profile-sparkling-treehouse.md`)
- **Exceeds most professionals:** point-in-time discipline (`_apply_pin` on every return path +
  runtime assertions), zero-drift multi-surface parity, and the habit of killing your own
  conclusions (SWG-PB parked, S4-GO walked back, journal-loss corrected).
- **At parity:** execution realism; pre-trade risk gates — **NOTE the roadmap was STALE: correlation
  gating IS built and enforced** (`sniper_trigger.py:299`, r≥0.90) alongside heat/sector/loss-streak.
- **Below professional standard:** (1) **no live track record** — see below; (2) **uncorrected
  multiple testing** — 98 validation runs, 4 alpha-selected sweeps, 2 ablation tables, 3 A/Bs whose
  winners became production defaults, zero Bonferroni/FDR/deflated-Sharpe/PBO (grep-verified absent).
  *The "hundreds of iterations" strength is also the largest statistical liability.* (3) survivorship
  on nifty500/fno (disclosed only for watchlist universes); (4) corporate-action look-ahead
  (`auto_adjust=True` + row-only pin slicing); (5) six stop engines / four formulas; (6) 0.27% test
  coverage, no CI; (7) ungated order surfaces.
- **One-line read: the infrastructure is running well ahead of the evidence.**

### SHIPPED this session
- **P0 horizon fix** — `replay.py:430` + `validation.py` `benchmark_pct` now self-consistent with
  `alpha_pct` in catalyst mode (was reporting the full-window bench beside a matched alpha).
- **P0 order surfaces** — NEW **`pre_trade_gate.py`**: the hardened webhook gate MOVED out of the
  FastAPI module (logic unchanged, re-exported so `dhan_tv_webhook` call sites are intact) so every
  surface can reuse it. Wired into **`n8n_order_handler.py`** (new `--entry`/`--sl`, LTP fallback),
  **`dhan_mcp_server.dhan_place_order`** (the LLM-callable one), and the **Streamlit "Execute CNC
  Order" button**. Design rule: **ENTRIES are gated, EXITS never are** — blocking a SELL is more
  dangerous than allowing an entry. Fail-closed on BUY. Verified against a mock broker: SELL passes
  with a full book · max-positions blocks · sector cap blocks · risk-% blocks at 2.67% / passes at
  0.67% · holdings-fetch failure blocks.
- **P1 purge/embargo** in `walkforward_oos.py` (+ reported/persisted embargoed anchors).
- **P1 provenance hardened** — `performance_attribution.py` now requires `snapshot_meta ~ 'recompute'`
  for SYSTEM. The old "any non-empty setup" rule counted a `backfill` row that re-screens well TODAY
  (the real `2026-07-18|backfill` + `POS-BO`) as system provenance. **Live system record: 2 → 1
  closed trade.** That is the honest number.
- **P2 tests** — NEW `tests/test_pa_patterns_regression.py` (10 tests): battery-composition stability
  (the blackout guard), two-sided NR7, intraday HTF suppression, flat-tape silence, and a **VCP
  dry-up regression proven to have teeth** (the old `(c*v)` yields 100 vs a 2.7M volume threshold →
  trivially true; the test goes red on revert). **Suite: 19 passed.**
  ⚠️ **pytest is NOT installed in the TradingData venv** — tests run under global Python 3.14
  (`python -m pytest tests/ -q`), which has pandas 3.0.3. Worth installing pytest into the venv.

### Re-partition on the corrected run (`catalyst_regime_partition.py`, 464 trades)
**By family:** POS n=246 win 35.0% α **+1.24%** PF 1.25 (41d) · SWG n=218 win 28.9% α +0.30% PF 1.14
(14d). Per-catalyst: POS-ACCUM +2.09% · POS-BO +1.01% · SWG-PB +0.52% · **SWG-REV −0.44% (the one
negative family, n=74)**. Every family's MEDIAN is negative (−1.6 to −3.4%) — confirms the
big-winner-carried profile.

**By exit reason — this is the actionable one, and it re-confirms the standing lesson:**
| exit | n | win% | mean α | PF | avg days |
|---|---:|---:|---:|---:|---:|
| Time expiry | 17 | 100.0 | **+23.77%** | inf | 72 |
| Trail SL | 242 | 42.1 | +2.08% | 1.51 | 42 |
| **SL hit** | **186 (40%)** | **5.9** | **−3.78%** | **0.02** | **7** |
40% of trades die at the initial stop in ~7 days with a 5.9% win rate and PF 0.02. **Signal
generation is not the problem; stop geometry is** — same conclusion as POS-BO/SWG-PB/REV-RS, now
measured honestly.

**⚠️ NEW methodological catch — the direction partition is now ENDOGENOUS.** "DOWN tape" is
`sign(Benchmark_Matched_pct)`, and after the fix that window's LENGTH is `days_held` — an OUTCOME.
Fast stop-outs (7d) in a falling market self-select into DOWN; long runners (72d) into UP. Hence
DOWN n=328 vs UP n=136. The old "defensive in DOWN tapes" claim is dead either way — the win-rate
asymmetry that was its main evidence has **vanished** (31.7% DOWN vs 33.1% UP, was 50% vs 27%) and
the alpha gap shrank (+1.14% vs −0.01%, was +2.54% vs −3.05%) — but do NOT replace it with "a
smaller defensive tilt." **Fix before quoting any direction result: label direction from an EX-ANTE
window (trailing regime, or the benchmark over the catalyst's design window) while keeping
matched-horizon alpha.** The fix made the ALPHA honest and the DIRECTION LABEL endogenous.

### Next
(a) De-endogenise the direction label (above) before any per-direction conclusion is used.
(b) Attack the 186-trade / 7-day SL bucket — that is where the edge leaks, and per
[[s4go_timing_gate_backtest]] widening alone did NOT work, so this needs structure-aware stops, not
a wider multiplier. (c) P1 research protocol (held-out period + variant ledger + deflated-Sharpe
haircut) before ANY Phase-3 weight fitting. (d) Install pytest into the TradingData venv.
Unchanged: #11 S4 rectangles · `GM_USE_IZE_ZONES` A/B · merge branch → main · recovery re-baseline.

---

## 28 July 2026 — WCL integration review + FIVE ideas tested and rejected

Branch `phase0-1-attribution-journal-snapshot`, commits `eb19c5f` · `9cd9eaf` · `1d973d9` ·
`6f07073` · `bf05e44` (+ this). **Not pushed, not merged.** Jay compiled S4 v5.2 clean.

### A. S4 v5.0 (Gemini's WCL integration) → v5.2. Compiled clean.
v5.0 never compiled (101,338 tokens vs a 100,256 limit) and **3 of the 5 features its header
advertised were declared but never wired**. Fixed:
- **REVERTED a 5-bar "sticky" PA window.** It claimed to match `pa_patterns.py`, but that module
  evaluates the LAST BAR ONLY — the window CREATED drift (ΣPA summed patterns from different bars)
  and printed GO while the V/L/B gate chips read fail beneath it. Markers/alerts used raw `go`.
- **`cf_w_wcl` was in `cf_max` but never added to `cf`** — the ceiling rose while the score could
  not reach it, so every name was understated and ★strong was harder than v4.7. Now wired.
- **`near_vp_val`/`near_vp_poc` were computed and referenced nowhere.** VP VAL/POC now join
  `support_pass` behind `en_wcl_loc` (fires on ~18% of names) and are named in the Support Zone row.
  **This is the one WCL component that earns its place.**
- VP moved to last-bar-only (a 100×40 nested loop per confirmed bar would trip TV's time limit);
  `nz(d_bel30, 0.0)` returned MAX BULLISH on missing data → `nz(..., 1.0)`.
- **v5.2:** the panel gave TWO entry instructions ~4% apart (CLEAR-TO-BREAK hardcoded "buy-STOP"
  while Plan/STATUS follow `entry_method`, defaulted to RETEST since the 23-Jul A/B), and T1 was
  set to the very level the verdict said not to target (now tagged `·lvl` when structural).

### B. NEW `wcl_context.py` — Wyckoff + SMC ported properly
The GM/board previously showed WCL from *proxies*: Wyckoff was `acc_ok and stage in (1,2)`, SMC was
`2 if path=="bull" else -2` (literally the path name, penalising every Recovery name by 4), and
`choch_count_20` was read with `default=0` and **produced nowhere** → Structure Health permanently
`CLEAN (0)` feeding a constant 100 into the board's `overall_score`. Now a 1:1 port, computed ONCE
in the ctx builder and read by both surfaces, **following the Trigger TF (75m/125m/Daily)** because
S4 computes these on the chart TF; stage stays daily via stashed flags. 18 regression tests pin the
three load-bearing Pine quirks (pivots resolve on the CONFIRMATION bar; the bearish ladder is a
second `if` so DISTRIBUTION wins ties; `choch_up` tests the PRIOR bar's trend) — each verified to go
red under mutation.

### C. FIVE ideas tested, FIVE rejected (this is the session's real content)
| # | idea | verdict |
|---|---|---|
| 1 | Wyckoff DISTRIBUTION as a GO veto | **BACKWARDS** — vetoed cohort +5.60% vs kept +0.52% |
| 2 | Wyckoff as a SCORE input | **NULL** — held-out ρ +0.013, p 0.74; both windows null |
| 3 | Dhan Trailing Target / TSL exit scheme (Gemini's AND mine) | **LOSES to current** |
| 4 | POS stop re-tuning | **KEEP CURRENT** (3rd failed attempt) |
| 5 | SWG stop re-tuning | **KEEP CURRENT** — no OOS edge to tune |

Mechanism behind #1: **49% of qualified picks read DISTRIBUTION at signal time** because Wyckoff
events fire at high-volume pivot highs — structurally what a breakout looks like. Faithful port; the
concept just doesn't transfer to a pre-qualified breakout universe.

### D. THE METHOD LESSON — R-multiples, and a conclusion I had to invert
The SL×trail grid FIRST returned "ADOPT SL 6.5 × trail 8.0, +5.84pp". **Wrong, three ways:**
(a) it was a **corner solution** — the surface climbed monotonically to the grid edge, so the
"optimum" was just the widest cell allowed; (b) OOS retained **+0.19pp of a +5.84pp** IS margin
(97% collapse) yet passed a gate that only required "positive"; (c) **the metric was wrong** —
position size = risk / (k × ATR), so per-trade % return silently rewards wide stops for exposure
they never bought. **Re-run in R-multiples the answer INVERTED**: best SL became 2.0–2.5 (TIGHTER
than the current 3.85), and the whole SL axis declines as the stop widens. It still failed on OOS
collapse and a −0.907R median.
> **Standing rule: any stop/sizing study must be measured in R (return ÷ initial risk), never in
> per-trade %.** A % metric structurally favours wide stops.

Gates now used for any parameter sweep: **A** plateau (neighbours must also beat control) · **B**
OOS retains ≥50% of the IS margin · **C** bootstrap stability (winner-or-neighbour ≥25% of 500
resamples AND 5th pct of best−control > 0) · **D** median not worse by >0.25R · **E** interior (an
edge winner FAILS — the grid is mis-specified).

### E. Diagnostics that DID hold (use these)
- **Stop-out forensics (`stopout_forensics.py`)** — of trades stopped at the initial SL:
  **POS** only **1.9%** ever reached T1 and holding through averaged **−6.65%** → the 3.85×ATR stop
  is doing its job, leave it alone. **SWG 36.4%** eventually reached T1 → genuine shakeouts.
- **Early-dip vs later outcome (disjoint windows, non-circular):** SWG dipping 1.0–2.0 ATR in the
  first 7 bars still returns **+1.4% to +3.4%** afterwards at ~52-54% win; expectancy only inverts
  at **3–4 ATR**. The SWG stop at **1.14×ATR sits inside the shakeout zone**.
- **SWG median is −1.049R** — the typical swing trade loses a full unit of risk. Widening to SL 2.5
  flips the median to **+0.222R** in-sample… but **every SWG cell is negative OOS**.
  **→ The swing problem is the SIGNAL, not the stop.** You cannot tune the stop of a book with no
  out-of-sample edge. Consistent with SWG-PB parked (regime-mismatched) and SWG-BO as the drag.
- **The trail wants to be WIDE** — every surface in every study climbs monotonically toward the
  widest trail. The one consistent directional signal. Don't tighten trails.
- **Chandelier > Dhan's ratchet for POS** (−1.85pp IS / −0.49pp OOS): a ratchet can't move until
  price advances a full jump and can never tighten below its starting gap; **29.7% of OOS positional
  trades died on an UNTOUCHED initial stop** under it vs 9.8%. Swing indistinguishable.

### F. Two defects I introduced and corrected — do not repeat
1. **`exit_policy_study.py` charged every config the benchmark matched to E0's hold length.** The
   alternatives held far shorter (POS 43 vs 54d, SWG 6 vs 16d) so they were billed a longer
   benchmark than they ran — the 26-Jul horizon bug, reintroduced, biasing **in favour of** the
   conclusion I reported. `sl_trail_grid.py` recomputes the benchmark per cell from that cell's own
   `days_held`. **The exit study needs re-running with per-config benchmarks before anyone leans on
   its magnitudes.**
2. **Same-bar sequencing** — stepping a ratchet on the current bar's HIGH and then testing the stop
   against the same bar's LOW uses an intrabar order that may not have occurred. Lagging the step to
   the prior bar's high shrank the POS gap from −3.05pp to −1.85pp; ~40% of the reported penalty was
   harness bias. Real intraday behaviour lies between the two runs — report the bracket.

### G. Dhan Trailing Target — mechanics established (manual use only)
Trail Jump is a **STEP, not a distance**: price advances by the jump → the order moves the same
amount, so **the gap is preserved**. Consequences: (a) with TT on, the target is **unreachable by
construction** in any sustained trend — the runner leg's entire exit policy is the stop;
(b) **a LARGER target jump makes premature capping MORE likely** (the jump is how close price gets
before the target steps away) — Gemini's "1.5×ATR filters noise" rationale is inverted for targets;
(c) Dhan's TSL **preserves the initial gap and can never tighten below it**, so initial SL distance
IS the trail distance. Available on **Investing (delivery) with 365-day validity**; TG Trail works
**without** SL Trail. **BUT: a TRAIL order is a different order CLASS** — the installed `dhanhq`
2.0.x has no super/trail methods, so `modify_forever()` cannot touch one and `gtt_auto_shield
--trail` would run clean and change nothing. **TRAIL orders are manual-only and invisible to the
risk tooling.**

### H. Shipped fixes
- `gtt_trail` disabled (my suggestion, while trialling TRAIL orders) then **RE-ENABLED on evidence**
  — default on, `GTT_TRAIL_ENABLED=0` kill switch retained.
- **`pyramid_logic.py`** (live on Risk Shield via `_pyr_reason`, and injected into the AI prompt):
  the TRIM rungs had **silently doubled** (R≥2 went from "book ⅓" to "OCO-1 (50%) exit") and
  `trail_jump` was a hardcoded `atr14 * 1.5` — the SWING multiplier on every position — sitting
  beside a correctly catalyst-aware Chandelier in the same dict. Rungs restored; `trail_jump` routed
  through `risk_common.trail_mult_for()`; rungs now surface the Chandelier level.
- `Commander_Risk_Allocator_v2.0.pine` **left uncommitted** — it encodes the 2-OCO scheme the study
  rejected. Revert or fix before use.

### Next
(a) **Restart** the scheduler daemon (trail) + Web Commander. (b) GM spot-check: board vs Single
Symbol, `en_wcl_loc` ~18%, confluence up, WCL row showing the right TF. (c) Re-run
`exit_policy_study.py` with per-config benchmarks. (d) **The real question: does the swing book have
an edge in the current regime at all?** If SWG-PB/SWG-BO are OOS-negative, gate them by regime or
stop trading them — that is worth more than any exit parameter. (e) Push/merge the branch.
Unchanged: #11 S4 rectangles · recovery re-baseline · pytest into the venv.

---

## 28–29 July 2026 (cont.) — the diagnosis chain: what is actually wrong, and what is not

Branch merged to **main** (`054ac84`). Everything below came AFTER the SL×trail grid, and
it supersedes several conclusions in the section above. Read this one.

### THE HEADLINE — the selection edge is REAL, and the planning number is +1%
`beta_adjusted_alpha.py` tested the last remaining "it's all an artifact" story: every
alpha number here is RAW excess return with no beta adjustment, and Stage-2 breakouts are
high-beta by construction, so in a rising tape they outperform mechanically.

**REFUTED. Median ex-ante beta is 1.11, not the ~1.5 I assumed** (250d ending AT the
anchor; no holding-period data). The adjustment moves almost nothing:

| | bench | RAW α | BETA-ADJ α |
|---|---:|---:|---:|
| POS-BO IS | +4.17% | +5.61% | **+5.03%** |
| POS-BO OOS | −1.59% | +1.01% | **+1.11%** |
| SWG IS / OOS | +0.37 / −0.84% | +0.46 / +0.30% | **+0.41 / +0.48%** |

Only **15%** of the POS-BO IS→OOS gap was beta. **Selection survives in both windows.**
OOS α *improves* under adjustment because the benchmark was negative — beta>1 predicts you
lose MORE than the index, and the picks did not.

> **PLAN AROUND +1% MATCHED ALPHA PER TRADE, NOT +5.6%.** The in-sample figure comes from
> one exceptional stretch (below). The beta-adjusted MEDIAN is negative (POS-BO −2.49% IS /
> −3.44% OOS): the edge is real AND it is a low-hit-rate, big-winner profile. Sizing and
> drawdown tolerance matter more than the mean implies.

### POS-BO's "18% edge decay" is REGIME AMPLIFICATION, not decay (`pos_bo_decay.py`)
- **H2 outliers — REJECTED.** Trimming winners WIDENS the gap (drop top-10: IS +2.81% vs
  OOS −2.00%). IS is *less* concentrated (top-10 = 25% of gross) than OOS (51%).
- **H3 broad deterioration — confirmed:** median −1.92→−3.29, win 43.2→34.7%, avg win
  +24.87→+16.80, avg loss −7.60→−9.01, payoff 3.27→1.87.
- **H1 regime — THE CAUSE.** Benchmark over matched holds went **+4.17% → −1.59%**; the
  stock leg **+9.78% → −0.58%**. In a rising tape these breakouts return ~2.3× the index;
  flat-to-falling, they roughly match it. With beta excluded as the mechanism, this is
  **conditional skill**, not leverage: breakouts follow through when the market cooperates.
- **THE IS/OOS BOUNDARY IS ARBITRARY.** The strong stretch is **2023-05 → 2024-01** (+8% to
  +16%/anchor) and it rolls over at **2024-02 — four months BEFORE the split**. The real
  division is "that 8-month bull run vs everything since".
- Exit machinery here is HEALTHY: 85–90% of POS-BO exits are trail-SL, 7–9% initial-stop.

### Swing: the "broken book" was a POOLING ARTIFACT (`catalyst_breakdown.py`)
| catalyst | IS | OOS | verdict |
|---|---:|---:|---|
| **SWG-PB** | +0.42% (n=171) | **+0.52%** (n=141) | KEEP — positive in BOTH |
| SWG-REV | +0.54% (n=43) | **−0.44%** (n=74) | the drag |
| POS-BO | +5.61% | +1.01% | KEEP |
| POS-ACCUM | +5.23% | +2.09% | KEEP |

**SWG-PB is the most STABLE catalyst in the book** — edge retained ~124% across windows vs
POS-ACCUM 40% and POS-BO 18%. My earlier "swing has no OOS edge" / "swing is flat inside
its own regime" statements POOLED SWG-PB with SWG-REV and were **wrong**. That is the third
time pooling two families produced a false conclusion (cf. the pooled 40% stop-out figure,
and June's pooled NO-EDGE verdict). **Always split by catalyst before concluding.**

### SWG-REV: payoff geometry, not stop-outs (`swg_rev_diagnostic.py`)
My premise ("it stops out 69%, so it's catching knives") was FALSE — **SWG-PB stops out 78%
and is profitable**. Stop-out RATE is not the discriminator. SWG-REV *wins more often*
(27.0% vs 22.0%) and still loses. OOS decomposition:

| | SWG-REV | SWG-PB |
|---|---:|---:|
| avg win / avg loss | +7.93% / −4.90% | +10.08% / −3.21% |
| payoff ratio | **1.62** | **3.14** |
| stop distance | 1.55×ATR | 1.08×ATR |
| winner max runup | +14.68% | +25.28% |
| exits at INITIAL SL | **89.3%** | 74.0% |
| exits via trail SL | **6.0%** | 17.9% |

Two problems compounding: (1) the stop is 43% wider and buys nothing — it does NOT reduce
stop-outs (89.3% vs 74.0%, worse), it just makes each cost more; (2) a reversal bounce is
structurally a smaller move than a trend continuation. **The trail is effectively INERT
here (6% of exits).** Rejected: volatility expansion (median realised/entry ATR = 0.990 —
vol *contracts*) and early-entry (losers went green at similar rates, 39% vs 41%).
**Retire rather than tune** — no stop setting fixes "the move isn't big enough". Caveat:
n=74 OOS / 43 IS and IS was positive, so it does not clear the pre-registered bar.

### Regime gating swing — already applied, and it doesn't save it (`swing_regime_partition.py`)
NOT SUPPORTED on all four criteria. **SWG-PB fires 301 BULL / 11 NEUTRAL / 0 BEAR** — the
hard `mkt_bull` gate added 2-Jul is binding, so this fix was NOT "never acted on"; it was
made weeks ago. **You cannot measure whether a gate helps once it has removed its own
counterfactual.** Also confounded: 36 of the 48 NOT-BULL swing trades are SWG-REV.

### The "thinning funnel" is NOT a bug — it is regime
`picks_with_data` by regime: **BEAR 5.5/anchor · NEUTRAL 16.7 · BULL 30.3**. Every thin
anchor (2025-02: 3, 2025-03: 2, 2025-04: 5) is a bear tape. And
`picks_universe == picks_filtered == picks_with_data` at **every** anchor — no stage
silently drops candidates, which is exactly what distinguishes this from June's real bug
(which showed as zero picks *in bull regimes*). Aggregate drop is 26.6→23.2/anchor (13%),
not the 28% I quoted — that was POS-BO-specific, larger because the MIX shifts to
swing/recovery in weak tapes.
**Filed, not actioned:** `corr(picks_per_anchor, benchmark fwd-60d) = −0.19` — high-pick
anchors preceded WEAKER markets (2024-12: 46 picks → −13.1%; 2025-02: 3 → +10.1%). Breadth
peaking before tops. A surge in pick count is more plausibly a caution flag than an
opportunity. Weak (n=44); do not trade it without its own test.

### Scoreboard: six additions tested, six rejected; one foundation validated
Wyckoff veto · Wyckoff score · Dhan trailing exits · POS stop re-tune · SWG stop re-tune ·
swing regime gate — **all rejected**. The only thing validated is the **core selection
edge**, which you already had. **The system does not need more parts.** It needs the parts
it has to be sized and expected correctly.

### GM buttons (`054ac84`) — press ONE
`🔨 Rebuild board · N names` reuses CACHED data (fast — the right button after a Trigger-TF
or X-Ray change). `🔄 Fetch fresh data + rebuild · ~N fetches` invalidates the whole
universe AND sets `gm_force_rebuild`, so **it rebuilds by itself** — pressing both just
rebuilds twice on identical data. Do not delete Rebuild: every TF switch would then cost
~50 fetches.

### Next
(a) GM spot-check (WCL header must read `… · 75m · S4 parity`, NOT `(PROXY — engine
unavailable)`; board vs Single agreement; ~18% VP location; Struct Health `CLEAN` on ~90%
is EXPECTED; Overall has shifted — compare fresh, not cached). (b) SWG-REV: retire or leave
as-is; do not tune it. (c) Re-run `exit_policy_study.py` with per-config benchmarks before
trusting its magnitudes. (d) Any future stop/sizing study is measured in **R**, never
per-trade % — see [[r-multiples-not-percent-for-stop-studies]].

---

## 29 July 2026 — S4 v5.2 → v5.9: the mode classifier was the root cause

All on **main** (`66d8c5d`). File RENAMED `Section4_Entry_Trigger_v5.0.pine` →
**`Section4_Entry_Trigger_v5.9.pine`** (git mv, history follows). Jay compiled v5.9 clean.

### THE HEADLINE — Bull/Recovery was classified wrongly; everything else was a symptom
Jay kept forcing **Manual = Recovery** because Auto never resolved CRISIL / GLAXO / COLPAL.
Three successive diagnoses, each correcting the last:

1. **Manual mode was never broken.** `is_rec = mode=="Recovery" or (mode=="Auto" and auto_rec)`
   honours the override. The blocker was `auto_require_below_200` (default ON) — Auto→Recovery
   demanded price BELOW the 200-DMA, and all three are above it.
2. **v5.8 replicated Python's drawdown band** (`recovery_screener` Pillar 1: drawdown off the
   rolling **60-bar** high, 15–35%). S4 had used off-52W-high plus three gates Python does not
   have. Better — but still wrong, because the band is a *qualification*, not a classifier.
3. **v5.9 — classify by WEINSTEIN STAGE.** A drawdown number cannot separate a Stage-2 leader
   in a 15–20% correction, a Stage-4 name still falling, and a Stage-1 base turning up. The
   2×2, from two flags the file already computed (`d_bel30`, `d_s150dn`):

   | below 30WMA | 30WMA falling | stage | path |
   |---|---|---|---|
   | no | no | 2 | BULL |
   | yes | no | 1 | RECOVERY |
   | no | yes | 3 | **NO TRADE** |
   | yes | yes | 4 | **NO TRADE** |

   GLAXO → Stage 2 → **Bull** (a pullback in an uptrend, NOT a recovery — the instinct to call
   it recovery was the misread). COLPAL → Stage 3 → **NO TRADE**.

### THE THIRD STATE was the actual missing piece
`mode` offered only two *tradeable* paths, so a Stage-3/4 name was forced into one and the
verdict then reasoned faithfully inside a frame it should never have entered — exactly how
COLPAL (30WMA FALLING) reached "TAKE IT — Recovery ★strong". New `stage_skip` outranks every
verdict branch and **applies under MANUAL mode too** (the stage is a fact, not a preference).
`stage_gate` (default ON) restores the old behaviour. **Every patch below was downstream of this.**

### Real bugs found and fixed in S4 (v5.2–v5.9)
- **v5.3 Σ PARITY** (Jay: "GM Σ 6, S4 Σ 9"). `kLAU` (Stage-2 Launch, +3) and `kRECLAIM` (+3) had
  NO intraday guard. Both key off `w_cross`, a WEEKLY crossover that stays true all week — so on
  75m they added +3 on EVERY bar (~26 bars). `pa_patterns.py` suppresses both under
  `intraday=True`. The old comment claimed "they already stay weekly, so HTF is the only leak" —
  backwards. Also fixed `kHTF` (`not use_chart_tf` wrongly suppressed it on DAILY).
- **`_stage2ok` was a SECOND definition of Stage 2** (above 30WMA AND above 200DMA) that never
  checked whether the anchor was RISING → TRUE for Stage 3, so `_blueSky` / `_clearToBreak` could
  fire while their own text says "Only valid Stage-2". Now `stage_n == 2`.
- **Confluence paid points for SELLERS.** `arr_fav` rewarded ANY fast arrival; and `of_absorb` at
  SUPPLY means *sellers* absorbing, yet it earned `cf_w_absorb`. New `of_bull` (long-side read)
  now drives both terms and `_qBleed`. `of_absorb` kept for DISPLAY only.
- **v5.4 "retest" was lying.** The limit sits AT the trigger close, so on the trigger bar it fills
  as a MARKET entry. The Plan row now distinguishes a true retest from a market fill.
- **4 entry-conflict instances** (CLEAR-TO-BREAK, BLUE-SKY, RECOVERY, never-buy-the-touch): the
  verdict said buy-STOP while the Plan row followed `entry_method` (retest). Each now either
  follows the input or states it OVERRIDES the Plan row.
- **EXTENDED warning** (`ext_warn_atr`, default 2.5, below the 4.0 veto) names where a pullback
  entry sits (highest structure below price).
- **DOWNGRADE** when ≥2 of: EMA20 chop / FAST-bleeding arrival. (30WMA-falling was dropped from
  it — now redundant with `stage_skip`.)
- **`ta.cross` / `math.sum` were inside `if … barstate.islast`** → ran on the last bar only, so
  the chop count was GARBAGE, not merely non-idiomatic. Hoisted to global (`ema20_x40`).
  **Rule: compute in global scope, display in the panel block.**

### X-Ray — missing data was scored as FAILED (why everything read C FAIR / D WEAK)
TWO modules, and the first fix was on the wrong one:
- `fundamental_xray.py` (`b2a62d2`) — EBITDA margin ← screener OPM%, FCF ← screener cash-flow;
  score renormalised over evaluable checks; new `data_coverage` / `overall_rating_raw`.
- **`weinstein_xray_screener.py` (`3a8242a`) is what the BOARD uses.** Its data source was already
  screener-primary; the bug was scoring. `miner_score` / `pio_score` SKIP unresolved criteria and
  were then divided by the FULL 8 and 9 — so 4-of-9 resolved capped that term at 44% even if all
  four PASSED, and the two terms carry 40% of the weight. Now normalised over RESOLVED criteria.
  `Data_Quality` was RETURNED and never consumed → the board now appends **⚠** (PARTIAL) / **?**
  (INSUFFICIENT). Expect grades to RISE and Overall to shift.
- COMPELLING-REASON exceptions (documented in code — do not "fix"): CurrentRatio and GrossMargin
  are NOT derivable from screener.in's public page; ROA / EpsFwd / EvToEbitda are broker fields.

### GM board — two buttons, press ONE (`054ac84`)
`🔨 Rebuild board` uses CACHED data (fast — the right button after a Trigger-TF or X-Ray change).
`🔄 Fetch fresh data + rebuild` invalidates the universe AND sets `gm_force_rebuild`, so **it
rebuilds by itself**. Do not delete Rebuild — every TF switch would then cost ~50 fetches.

### SCRIPTED-EDIT TRAPS THAT BIT TWICE THIS WEEK
1. Bash-heredoc de-escapes a backslash-n into a REAL newline → broken Pine strings. Build the
   escape with `chr(92)` or use Edit/Write. (See the bash-heredoc memory.)
2. **Line-anchored regex is unsafe on Pine** — inputs routinely wrap, so a `^name = input…$`
   pattern deletes the first line and orphans the `tooltip=…")` continuation → "Extra closing
   parenthesis". Delete the whole STATEMENT, or use Edit.
Always run the odd-quote + paren-balance + orphan-continuation sweep after a scripted edit.

### Token ceiling — S4 sits permanently near it (100,256)
String-concat code expands ~3.7 compiled tokens per source token. Removed to buy budget: the
zone-detection DIAGNOSTICS row (default-off instrumentation, `show_diag`), Wyckoff's
PSY/BC/UT/LPSY tiers (→ one DIST), setups **S3/S6** and the SMC liquidity-sweep block (S3 was its
only reader), and `d_dd60` + the drawdown inputs. **A newline INSIDE a string literal costs
NOTHING** — that is how the panel was narrowed (long verdict lines now self-break).

### Settings to hold
`stage_gate` ON · `mk_bars` 5–10 (marker declutter) · `auto_require_below_200` no longer exists.

### Open
- **RESTART Web Commander** — the X-Ray fixes landed after the last restart and are NOT live.
- Rebuild the board; expect higher X-Ray grades, ⚠/? markers, and a shifted Overall.
- **SWG-REV**: retire or leave — diagnosis complete (payoff ratio 1.62 vs 3.14; trail engages on
  only 6% of exits). A decision, not more analysis.
- Re-run `exit_policy_study.py` with per-config benchmarks before trusting its magnitudes.
- Multi-pivot rectangle classifier (item #11) — the 2-pivot version calls rectangles "symmetrical
  triangles" (confirmed on APOLLOHOSP and GLAXO).
- `data_coverage` on the X-Ray CARD (the board column is done).
- `Section4_Entry_Trigger_v3.0.pine` is still misnamed (it holds v4.7) — pre-WCL reference copy.

---

## 29 July 2026 (cont.) — S4 v6.0: the Plan never latched the trigger bar (found on PFC)

In-file title **v6.0 (Trigger-Bar Latch)**; filename stays `Section4_Entry_Trigger_v5.9.pine`
(Jay's call — no rename). **Compiled clean.** Found by Jay reading a live PFC 75m panel:
"this is not the trigger candle, the trigger was one bar below."

### THE BUG — a plan anchored to "signal still true" ratchets with price
`pl_entry := use_retest ? close[_so] : high[_so]` ran on EVERY bar `go_v` was true. `_so` is
only the forming-bar shift, so a multi-bar GO sequence re-based the "retest limit" upward bar
after bar. **A retest limit that follows price is a market entry wearing a limit's clothes** —
the exact habit buy-stop confirmation was built to fix. On PFC it had drifted from the GO★ bar
(~low-420s) up to 425.00.
- The guard meant to catch it was **measuring the wrong thing**: `_retestLive` tested
  `close > pl_entry * 1.0015` — price vs the QUOTED bar, never asking whether that bar was the
  trigger. Any advancing bar satisfies it, so it printed "(true retest)" *precisely when the
  anchor was most stale*.
- **Fix:** `var trigBar/trigCls/trigHi` latched on the GO EDGE (`go_v and not go[_so + 1]`), in
  GLOBAL scope (the v5.9 `ta.cross`-inside-`barstate.islast` lesson). `_retestLive` now requires
  `trigAge > 0` AND price above. New `· trig Nb ago` tag on the Plan row. New input
  **"Plan: re-latch the trigger after N bars"** (12) — a limit far behind an advancing market
  never fills, so a stale anchor re-latches rather than quoting fiction.
- **`_cl` changed from `close[_so]` to `pl_entry`** (necessary, not cosmetic): it is the basis
  for the structural test AND the ATR cap. With a latched entry below the current close, capping
  from the current close would put the stop too high and **inflate R**. Also fixes the
  pre-existing buy-stop case, which paired a `high[_so]` entry with a `close[_so]` stop basis.

### `_ovh2` separation — T1 and T2 were one obstacle printed twice
PFC showed `T1 444.80 (1.4R ·lvl) · T2 445.75 (1.4R ·lvl)` — 95 paise apart. The `_ovh2` sources
cluster (supply proximal / flipped pivot / pivot high within a rupee). Now
`_ovhMin = _ovh + max(ATR × ovh2_gap_atr, _ovh × 0.002)` gates all six comparisons; new input
**"T2: min gap above T1 (× ATR)"** (0.5). Anything inside the gap is the same obstacle.

### Why 433.85 was NOT the target (asked, answered — working as designed)
Both 433.85 and 448.65 are graded **MTTWR** and MTTWR levels are deliberately excluded from the
S/R picker (`s.a1t < mttwrEff`, line ~3916) — hence `sr_above` = 485.20 ·W. Doctrine in the
header ~line 400: *tests WEAKEN a level; one tested that often is a breakout candidate, not a
ceiling.* Do not "fix" this. **Also note: the CLEAR-TO-BREAK verdict was correct regardless** —
the SL cap pins risk at 4.0×ATR, so a perfect trigger-bar entry only moves T1 from ~1.38R to
~1.65R, and the positional 20%-ROI gate fails anyway at +4.7% to T1. The latch fixes ~0.3R of
drift; **it does not change any verdict.**

### GM Python — the same text-vs-number split, reworded not rebuilt
`compute_workflow` sets `entry = cmp_px` (current price) and never latches, while
`_gm_entry_instruction` promised "the trigger bar's close". Per the two-stage doctrine
([[gm_early_s4_execute_twostage]]) **GM arms, S4 is the plan of record** — so the fix is
provenance, not a duplicate latch: new `_GM_ENTRY_SRC` caveat ("take that price off S4 — it
latches the trigger bar; levels here are at CURRENT price"), `src_note` param, short forms now
say "the S4 trigger close". Also **consolidated a hardcoded second copy** of the step-4 fill
wording (~line 13244) that had already drifted — it now routes through the helper. py_compile clean.

### Standing
- **Restart Web Commander** for the GM wording (still stacked with the pending X-Ray restart).
- Alerts bind to the compiled version — **delete & re-create the "S4 GO" alerts** after v6.0.
- Scripted-edit traps bit again: the Bash-heredoc backslash de-escape broke a checker script
  (write the script to a FILE). Post-edit sweep run: 0 odd-quote, paren depth 0, no orphaned
  tooltip continuations, 24 unique `f_row` ids.

---

*This file is the persistent memory and strategic DNA of Jay's trading environment. All Claude interactions should remain consistent with these established systems. The "Current Project State" section above is mutable and should be refreshed at the close of each substantive work session.*
