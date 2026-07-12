# CLAUDE.md — Jay (Jayram G) | Trading System DNA & Agent Context

> **Purpose:** Persistent context file for Claude across Chat, Cowork, and Code.
> Place this file in the root of any project folder used with Cowork or Code.
> Last updated: 22 May 2026 (Validation framework campaign — catalyst-aware horizons, realistic execution sim, bootstrap CI, catalyst-aware SL discipline, rolled-back premature catalyst removals)

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

*This file is the persistent memory and strategic DNA of Jay's trading environment. All Claude interactions should remain consistent with these established systems. The "Current Project State" section above is mutable and should be refreshed at the close of each substantive work session.*
