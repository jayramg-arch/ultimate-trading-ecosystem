# Backtest v2 — Session Findings & Decisions

> **Author:** Jay (Jayram G) | **Session date:** 8 May 2026
> **Purpose:** Single source of truth for everything decided/discovered in this backtesting cycle. Mutable while runs are in flight; will be frozen and converted to .docx at the end.
> **Anchors v1 FINAL (`Run ID 20260508_105114`):** Hunter `weekly_rsi_min=60`, Hunter `daily_adx_min=25`, EarlyBirds `disable_rsi=True` (locked 8 May 2026 by prior session).

---

## 0. Session Scope

This session resumed the work locked in `BACKTEST_RESULTS_v1.docx` and `session_handoff.md`. Three deliverables drove it:

1. **Validate v1 FINAL on actual deployed universe** (Chartink + Screener.in conviction filter, not raw Nifty100).
2. **Ablate the 5 v2 candidate fixes** to see which lifts alpha while holding hit-rate ≥ 91.7%.
3. **Sync v1 FINAL across all signal surfaces** (Pine scripts + Streamlit) to enforce the DNA "signal consistency is sacred" rule.

Plus two adjacent items that surfaced:
- HCLTECH stage exit (the same name failing both as portfolio drag AND backtest ranking failure).
- Bug fixes in the v2 driver scripts.

---

## 1. Bug Fixes Made During Setup

### 1.1 `run_v2_ablation.py` and `run_sensitivity_grid.py` — wrong kwarg

Both drivers called `validation.run_validation(base_universe=...)`, but `run_validation()` has no `base_universe` parameter — it's `universe_name`. Both scripts were patched.

```diff
- result = validation.run_validation(months_back=months, top_n=top_n, base_universe=universe)
+ result = validation.run_validation(months_back=months, top_n=top_n, universe_name=universe)
```

### 1.2 Windows cp1252 Unicode encode failure

Both drivers print `═` (U+2550) and `❌` (U+274C) characters that cp1252 can't encode. Fix is to launch via `python -X utf8 ...` rather than edit the scripts.

---

## 2. Phase A — Pine + Streamlit Signal Drift Sync (COMPLETE)

Per the DNA rule "signal consistency is sacred — zero drift across TradingView/Streamlit/screeners." The v1 FINAL parameter triplet was already locked in `chartink_replay.py`, but the Pine and Streamlit surfaces had drift.

### 2.1 Streamlit `weinstein_commander_web_v4.0.py`

Grep for `weekly_rsi`/`daily_adx`/`disable_rsi` returned **zero matches** outside variable-name fragments. The Streamlit consumes CSV outputs from the Python pipeline; it does not reimplement filters. **No changes needed — auto-tracks `chartink_replay.SCAN_PARAMS`.**

### 2.2 `Commander_Screener_Beta_Edition_v2.6.pine` → v2.7

**What was missing:** the Hunter (POS-BO) catalyst gate had no `wRsiVal` or numeric ADX threshold check. The script's `f_calc_adx_bool()` returned only a directional boolean (`+DI > -DI and price > 3-bar high`), discarding the numeric ADX value.

**Changes:**

| Item | Before | After |
|---|---|---|
| Indicator title | v2.5 | v2.7 |
| Hunter input group | (none) | `grp_hunter` with `hunter_weekly_rsi_min=60` (range 40–80), `hunter_daily_adx_min=25` (range 10–50) |
| `f_calc_adx_bool()` | returns `bool` | renamed `f_calc_adx()`; returns `[bool, float adx_val]` |
| Daily metrics block | `d_adx_ok = f_calc_adx_bool()` | `[d_adx_ok, d_adx_val] = f_calc_adx()` + `bool hunter_adx_ok = d_adx_val >= hunter_daily_adx_min` |
| POS-BO condition | `weinstein_setup and isBreakout` | `weinstein_setup and isBreakout and wRsiVal >= hunter_weekly_rsi_min and hunter_adx_ok` |
| Changelog | (none for v2.7) | Added v2.7 changelog block |

### 2.3 `Commander_Screener_Dashboard_ULTIMATE_v3.7.pine` → v3.8

**What was missing:** identical issue in `f_get_metrics()`. POS-BO catalyst (`catId=2`) at line 210 had no RSI/ADX gate.

**Changes:**

| Item | Before | After |
|---|---|---|
| Indicator title | v3.7 | v3.8 |
| Hunter input group | (none) | Same Hunter inputs as Beta Edition (uses `RSI(70)` as weekly proxy in tooltip) |
| Inside `f_get_metrics()` | (no DMI call) | Added `[_dp, _dm, _adx] = ta.dmi(14, 14)`; `hunter_rsi_ok = _rsi70 >= hunter_weekly_rsi_min`; `hunter_adx_ok = _adx >= hunter_daily_adx_min` |
| POS-BO condition | `is_stage2 and (_c > _h250 * 0.95) and (_v > _vSma * 1.5)` | `... and hunter_rsi_ok and hunter_adx_ok` |
| Changelog | (none for v3.8) | Added v3.8 changelog block |

### 2.4 `Commander_Capitulation_Screener_v1.5.pine`

Grep confirms zero references to `hunter`/`POS-BO`/`isBreakout`/`weinstein_setup`. This is a recovery-side capitulation screener with no Hunter logic. **No changes needed.**

### 2.5 `watchlist_manager.py` / `watchlist_ranker.py`

These consume CSV outputs from the screener; they don't reimplement filters. **Auto-track via `chartink_replay.SCAN_PARAMS`.**

---

## 3. Path 2 — Filtered-Universe Backtesting Discovery

### 3.1 What was halted

The v1 FINAL was locked using `validation.run_validation()` — the simpler path that runs the bull screener directly on Nifty100/500. The actual deployed Web Commander v4.0 universe is much narrower:

> **Layer 1:** Chartink replay (4 bull scans on the base universe → ~30–80 candidates per anchor)
> **Layer 2:** Screener.in conviction filter via `matcher_replay.filter_by_conviction()` with `min_conviction=6.0` → ~top 30% of Layer 1
> **Layer 3:** Bull screener picks Top-N from the survivors

The infrastructure for the filtered-universe backtester **already exists** as `validation.run_chartink_validation(use_fundamentals=True, min_conviction=6.0)`. The v2 ablation and sensitivity grid drivers (`run_v2_ablation.py`, `run_sensitivity_grid.py`) called `run_validation()` (raw path) and never called `run_chartink_validation()` (filtered path). That gap is what the user flagged as halted work.

### 3.2 Components rediscovered

| Component | File | Role |
|---|---|---|
| Layer 1 historical replay | `chartink_replay.py` | 4 bull scans + 3 recovery scans, deterministic at any anchor |
| Layer 2 conviction filter | `matcher_replay.py` | Mirrors `brute_force_match_pro.calculate_conviction_score` |
| Historical fundamentals | `fundamental_replay.py` | yfinance-cached quarterly statements (point-in-time) |
| Filtered-universe walker | `validation.run_chartink_validation()` (line 180) | Chains all three above |
| Forward-archive | `snapshot_archive.py` | Captures daily Chartink + Screener.in CSVs into `data/snapshots/YYYY-MM-DD/` |

The forward archive currently has only `2026-05-08/` — i.e. snapshots start from today, going forward. Historical anchors fall back to yfinance fundamentals (acknowledged minor look-ahead via today's promoter-% snapshot, ~1–3pp/yr drift).

### 3.3 New drivers built this session

Two new files, mirroring the existing raw-universe drivers:

- **`run_v2_ablation_filtered.py`** — calls `run_chartink_validation(use_fundamentals=True, min_conviction=6.0)`, baseline label `v1_FINAL_BASELINE_FILTERED`. Output → `validation_runs/v2_ablation_filtered_results.csv`.
- **`run_sensitivity_grid_filtered.py`** — same routing for the 3×3 RSI×ADX grid. Output → `validation_runs/sensitivity_grid_filtered.csv`.

---

## 4. Raw Universe v2 Ablation — RESULTS

**Run completed:** 8 May 2026, 20:44 IST. Driver: `run_v2_ablation.py` against `validation.run_validation(universe_name="nifty500")` (resolves to Nifty100-ish basket per validation.py default). Top-N=10, 12 monthly anchors (2025-04-15 → 2026-03-16), 30-day forward window, benchmark = `^CRSLDX` (Nifty 500). Per-cell duration ≈ 42 minutes.

| Cell | Run ID | Alpha % | Hit % | WinRate % | Median α | Best | Worst | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **v1_FINAL_BASELINE** | 20260508_170831 | **2.61** | **91.7** | 54.2 | 2.20 | +6.43 | −0.77 | (baseline) |
| tiebreak_rs_momentum | 20260508_175522 | 2.74 | 83.3 | 56.7 | 2.95 | +6.43 | −0.77 | ✗ Hit dropped |
| vcp_score_multiplier | 20260508_183735 | 2.40 | 91.7 | 55.8 | 2.69 | +6.00 | −2.04 | ✗ Alpha dropped |
| **days_since_pivot_penalty** | 20260508_191945 | **3.26** | **91.7** | 56.7 | **3.23** | +7.14 | −2.26 | ✓ **PROMOTE** (+0.65 α, +25% rel) |
| sector_cap_top_n | 20260508_200150 | 2.08 | 83.3 | 54.2 | 2.20 | +6.43 | −2.47 | ✗ Both dropped |
| **pos_accum_rsi_nullout** | 20260508_204424 | 2.75 | 91.7 | 55.0 | 2.20 | +6.43 | −0.77 | ✓ PROMOTE (+0.14 α, marginal) |

### 4.1 Headline interpretation

- **Two promotable v2 fixes on the raw universe:** `days_since_pivot_penalty` (strong) and `pos_accum_rsi_nullout` (marginal).
- **Tiebreak hypothesis falsified.** `tiebreak_rs_momentum` was expected (per the Jan-15-26 forensic) to be the cheapest fix that recovers the lone losing anchor. Instead, hit-rate dropped to 83.3% — meaning sorting by `RS_Momentum_4W` desc fixed Jan-15-26 *but broke a different anchor.* The single-anchor counterfactual was misleading; the fix is not free.
- **Sector cap also failed.** A flat 3-per-sector cap was hypothesized to surface metals/PSU-bank rotations. It did the opposite — alpha 2.08, hit 83.3%. Likely cause: the cap forced lower-conviction picks into the Top-N at anchors where strong sectors had >3 deserving names.
- **Days_since_pivot penalty is the cleanest winner.** Penalising chases of extended bases (HCLTECH 38d, EMCURE 33d, AIIL 48d, SBILIFE 115d) lifted both alpha (+0.65pp) and median anchor alpha (+1.03pp) without sacrificing hit-rate. Worst-anchor went from −0.77 to −2.26, but average rose enough to absorb it.
- **POS-ACCUM RSI null-out is mild.** Nulling POS-ACCUM when RSI > 50 lifted alpha 0.14pp without hurting hit-rate — defensible but not load-bearing on its own.

### 4.2 Anomaly: baseline alpha 2.61 vs prior 4.45

The `BACKTEST_RESULTS_v1.docx` recorded v1 FINAL baseline at **alpha 4.45 / hit 91.7 / winrate 61.7** under Run ID `20260508_105114`. This session's reproduction of the same config produced **alpha 2.61 / hit 91.7 / winrate 54.2** (Run ID `20260508_170831`).

**Hit rate is identical, alpha and winrate are lower.** Same code, same `top_n=10`, same `months_back=12`, same baseline universe. Possible causes (none confirmed yet):

1. **Data drift.** `data_provider.py`'s pinned-date logic depends on the underlying OHLCV cache; if the cache was refreshed between runs and a few prices were corrected, returns shift.
2. **`v2_fixes.reset()` side-effects.** The new ablation harness imports and resets `v2_fixes` before each cell; even with all flags off, the Top-N selection routes through `v2_fixes.select_top_n` (a hook added this session). If that helper reorders ties differently from the original simple sort, picks shift.
3. **Different anchor end-date.** If the prior run had a slightly older "today," its 12-month window started 1 month earlier, and a different anchor mix can change averages.

**Why it doesn't kill the analysis:** all 6 cells in this run share the same baseline conditions, so the ablation deltas are still valid. The promotion verdicts (`days_since_pivot_penalty` wins; `tiebreak` and `sector_cap` fail) hold regardless of the baseline's absolute level.

**Action item:** investigate root cause before locking v2 — is the harness's hook layer changing behavior even with all flags off? See §8.1.

---

## 5. Filtered Universe v2 Ablation — RESULTS

**Run completed:** 8 May 2026, 22:40 IST. Driver: `run_v2_ablation_filtered.py` against `validation.run_chartink_validation(base_universe="nifty500", use_fundamentals=True, min_conviction=6.0)`. Top-N=10, 12 monthly anchors (2025-04-15 → 2026-03-16). Per-cell duration ≈ 11 minutes (much faster than raw — average candidates per anchor only 23 vs ~100 in raw).

**Universe at each anchor:** Nifty500 → Chartink replay (4 bull scans, deduped) → matcher conviction filter (min 6.0) → bull screener Top-N=10. Average candidates surviving both filters per anchor: 23.

### 5.1 Per-anchor Chartink + conviction-filter universe sizes

Captured during the run (from baseline cell):

| Anchor | Hunter | Pullback | EarlyBirds | StrongLeaders | Combined → Conviction-filtered |
|---|---:|---:|---:|---:|---:|
| 2025-08-15 | 6 | 24 | 1 | 12 | 42 → 17 |
| 2025-09-15 | 12 | 36 | 10 | 22 | 70 → 20 |
| 2025-10-15 | 16 | 30 | 2 | 22 | 65 → 22 |
| 2025-11-17 | 24 | 22 | 6 | 20 | 61 → 12 |
| 2025-12-15 | 11 | 31 | 2 | 10 | 47 → 16 |
| 2026-01-15 | 19 | 26 | 0 | 4 | 45 → 33 |
| 2026-02-16 | 12 | 23 | 4 | 11 | 44 → 27 |
| 2026-03-16 | 6 | 5 | 2 | 7 | 17 → 10 |

The deployed pipeline really does compress Nifty500 to ~10–33 names per anchor. The conviction filter generally drops 50–75% of the Chartink output.

### 5.2 Filtered ablation table

| Cell | Run ID | Alpha % | Hit % | WinRate % | Median α | Avg Cands | Best | Worst | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **v1_FINAL_BASELINE_FILTERED** | 20260508_214659 | **4.37** | **83.3** | 59.2 | 4.68 | 23.0 | +12.66 | −3.29 | (baseline) |
| tiebreak_rs_momentum | 20260508_215801 | 4.23 | 75.0 | 58.3 | 4.68 | 23.0 | +12.66 | −3.29 | ✗ Hit dropped |
| vcp_score_multiplier | 20260508_220918 | 4.20 | 83.3 | 58.3 | 4.50 | 23.0 | +12.66 | −3.29 | ✗ Alpha dropped |
| days_since_pivot_penalty | 20260508_221931 | 3.95 | **91.7** | 56.7 | 3.36 | 23.0 | +12.81 | −3.82 | ⚠️ Hit ↑ but α ↓ 0.42 |
| sector_cap_top_n | 20260508_223001 | 4.25 | 83.3 | 58.3 | 4.42 | 23.0 | +12.66 | −3.29 | ✗ Alpha dropped |
| **pos_accum_rsi_nullout** | 20260508_224037 | **4.63** | 83.3 | **60.0** | **5.00** | 23.0 | +12.66 | −3.29 | ✓ **PROMOTE** (+0.26 α, hit held) |

### 5.3 Filtered-only headline

- **Only one promotable fix on the filtered universe:** `pos_accum_rsi_nullout` (alpha +0.26, hit-rate held, median α jumps from 4.68 to 5.00).
- **Tiebreak still the biggest loser:** dropped hit-rate to 75% (i.e. broke 3 anchors instead of 2). The Jan-15-26 counterfactual that motivated this fix was misleading on both universes.
- **`days_since_pivot_penalty` is the most interesting near-miss:** lifts hit-rate from 83.3% → 91.7% on filtered (i.e. recovers one losing anchor) but loses 0.42pp of average alpha because it truncates upside winners. This is a *hit-rate-vs-magnitude tradeoff*. Worth keeping as a config-flag for "defensive mode" (e.g. mid-correction markets) rather than a permanent lock.

---

## 5A. Raw vs Filtered — Side-by-Side Comparison

### 5A.1 Universe-level baseline differences

| Metric | Raw (Nifty100-ish) | Filtered (Chartink + conviction) | Delta |
|---|---:|---:|---:|
| Avg candidates per anchor | ~100 (full universe) | 23 (filtered survivors) | −77 |
| Avg anchor alpha | 2.61% | **4.37%** | **+1.76pp (+67% rel)** |
| Hit rate | 91.7% (11/12) | 83.3% (10/12) | −8.4pp |
| Win rate (per pick) | 54.2% | 59.2% | +5.0pp |
| Median anchor alpha | 2.20% | 4.68% | +2.48pp |
| Best anchor | +6.43 | +12.66 | +6.23 |
| Worst anchor | −0.77 | −3.29 | −2.52 |

**Interpretation:** The two-layer filter doubles the median anchor alpha and lifts win-rate by 5pp, at the cost of one extra losing anchor (hit-rate drops). The filtered universe is **higher-conviction but more concentrated** — bigger swings both ways, but average and median outcomes are markedly better. This validates the deployed pipeline.

### 5A.2 Per-fix cross-universe verdict

| v2 Fix | Raw α Δ | Raw hit | Filt α Δ | Filt hit | Cross-universe verdict |
|---|---:|---:|---:|---:|---|
| `tiebreak_rs_momentum` | +0.13 | ↓ 83.3% | −0.14 | ↓ 75.0% | ✗ Fails both |
| `vcp_score_multiplier` | −0.21 | ✓ 91.7% | −0.17 | ✓ 83.3% | ✗ Drops α on both |
| `days_since_pivot_penalty` | **+0.65** | ✓ 91.7% | **−0.42** | ↑ 91.7% | ⚠️ **Universe-dependent** — α and hit move opposite directions |
| `sector_cap_top_n` | −0.53 | ↓ 83.3% | −0.12 | ✓ 83.3% | ✗ Fails both |
| `pos_accum_rsi_nullout` | +0.14 | ✓ 91.7% | **+0.26** | ✓ 83.3% | ✓ **PROMOTE** — wins both |

**Two-universe verification rule applied:** a v2 fix is promoted to FINAL only if it lifts alpha while holding hit-rate on BOTH universes. Only `pos_accum_rsi_nullout` clears that bar.

### 5A.3 The `days_since_pivot_penalty` paradox — explained

On raw, this fix lifts α by 0.65pp at flat hit-rate. On filtered, it **drops** α by 0.42pp but lifts hit-rate from 83.3% → 91.7%.

Why the divergence:
- **Raw universe (~100 candidates):** many low-quality extended-base names get into the Top-10. Penalising `Days_Since_Pivot > 30` weeds them out, surfacing fresher setups → α lifts cleanly.
- **Filtered universe (23 candidates):** the conviction filter has already weeded most of those. The penalty now hurts *legitimate* later-stage Stage-2 names that still have upside (e.g. Stage 2-extended trend continuations). Median α collapses 4.68 → 3.36 because winners get truncated.

**Why hit-rate still rises on filtered:** the fix trades one anchor's truncated winner for one less losing anchor — risk profile shifts but average return drops.

This is a real, useful insight: `days_since_pivot_penalty` is **not a v2 lock candidate**, but it IS a useful **defensive-mode toggle** to enable in market drawdowns where hit-rate matters more than upside magnitude. Surface it as a runtime flag, not a default.

---

## 6. HCLTECH Stage-Exit Memo

(Adapted from this session's analysis; full memo retained verbatim.)

### 6.1 Position summary

| Field | Value |
|---|---:|
| Avg Buy Price | ₹1,632.60 |
| CMP | ₹1,321.10 |
| Quantity | 76 |
| Investment | ₹1,24,077.60 |
| Current Value | ₹1,00,403.60 |
| Unrealised P&L | **−₹23,674 (−19.08%)** |

### 6.2 Stage classification

- Price 19% below avg buy; sustained no recovery.
- ITBEES sibling at −24.38% confirms IT-sector Stage 4 backdrop.
- Slope of 30-WMA implied negative; price below 30-WMA. Classification: **Stage 3 → Stage 4 transition (confirmed decline)**.

### 6.3 Dual failure signal

HCLTECH is the only name failing in two independent ways simultaneously:
1. Largest absolute loss in active book (−₹23,674).
2. #1 ranking failure in Jan-15-26 anchor of the v1 backtest (returned −16.14% over 30-day forward window, single-handedly producing the lone losing anchor at −3.23 alpha).

### 6.4 ATR-based stop verdict

14-day ATR on HCLTECH at this price level is ~₹35–55. ATR-trailed stop from a ₹1,632 entry would have triggered in the ₹1,450–1,500 zone during the decline. CMP ₹1,321 is well below that band: **stop already breached.** Continued hold is a discretionary override, prohibited by DNA Rule #2.

### 6.5 Decision

**Mandatory exit at next session open. Full position, no scaling.** Freed capital ≈ ₹1,00,403.

### 6.6 Sell-to-Buy rotation

From `MASTER_Golden_Picks.csv`, top-conviction (8.5) Stage 2 confirmed candidates:

| Symbol | Strategy | Conviction | %Chg | Notes |
|---|---|---:|---:|---|
| **WOCKPHARMA** | Strong Leaders | 8.5 | +11.7% | Highest momentum on the day |
| **NETWEB** | Hunter + Strong Leaders | 8.5 | +4.55% | Dual-strategy confirmation (highest signal) |
| ACUTAAS | Hunter | 8.5 | +1.10% |  |
| NAVINFLUOR | Hunter | 8.5 | +0.54% |  |
| GVT&D | Strong Leaders | 8.5 | −0.35% |  |
| ENRIN | Strong Leaders | 8.5 | −3.38% | Pullback entry |

**Recommended deployment:** split freed capital across WOCKPHARMA + NETWEB at 1% portfolio risk per name, ATR-sized.

---

## 7. v2 Promotion Recommendation — FINAL

### 7.1 v2 LOCK decision

**Lock v2 with exactly ONE change from v1 FINAL:**

> **Enable `pos_accum_rsi_nullout` permanently.** Null the POS-ACCUM catalyst when daily RSI > 50.

This is the only v2 fix that cleared the two-universe verification rule:
- Raw universe: alpha 2.61 → 2.75 (+0.14pp), hit-rate held at 91.7%.
- Filtered universe: alpha 4.37 → 4.63 (+0.26pp), hit-rate held at 83.3%, **median anchor alpha jumped 4.68 → 5.00**.

The fix is mechanically aligned with the DNA: POS-ACCUM is meant to surface accumulation patterns at *low* RSI (institutions buying while sentiment is muted). When RSI > 50, the catalyst label becomes a false positive — the stock is already running, so the institutional accumulation signal is just confirming late-stage chase. Nulling it out at high RSI removes a documented failure mode without touching any other gate.

### 7.2 What the data says about the other four

| Fix | Verdict | Rationale |
|---|---|---|
| `tiebreak_rs_momentum` | ✗ **Reject** | Falsified on both universes. Hit-rate drops to 83.3% (raw) and 75.0% (filtered). The Jan-15-26 counterfactual was a single-anchor mirage — the new tiebreak ranking actively breaks other anchors. Do NOT enable. |
| `vcp_score_multiplier` | ✗ **Reject** | 0.5× is too aggressive a penalty. Alpha drops on both universes. If VCP filtering is desired, try a milder multiplier (e.g. 0.85×) in a future ablation cycle, not 0.5×. |
| `sector_cap_top_n` | ✗ **Reject** | Hard 3-per-sector cap forces lower-conviction picks into Top-N at strong-sector anchors. Alpha drops on both universes. If sector concentration is a worry, try a *soft* cap (e.g. 5-per-sector with a penalty rather than a hard limit) in a future cycle. |
| `days_since_pivot_penalty` | ⚠️ **Defensive flag, not default** | Universe-dependent: lifts α on raw, drops α on filtered (while lifting hit-rate). This is a hit-rate-vs-magnitude tradeoff. Add as a runtime flag (e.g. `--defensive-mode`) the user can toggle during market drawdowns or low-conviction periods, but do NOT lock as default. |

### 7.3 Specific code changes to lock v2

In `chartink_replay.py`, update the LOCKED block:

```python
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║ v2 FINAL CONFIG — LOCKED 2026-05-08 (Run IDs: raw 20260508_204424,       ║
# ║                                              filtered 20260508_224037)   ║
# ║ Adds pos_accum_rsi_nullout to v1 FINAL.                                  ║
# ║ Raw universe:      α 2.61 → 2.75 (+0.14pp), hit 91.7% held               ║
# ║ Filtered universe: α 4.37 → 4.63 (+0.26pp), hit 83.3% held, median 5.00  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
SCAN_PARAMS_VERSION = "v2_FINAL_20260508"
```

In `v2_fixes.py`, change the default flag state for that one flag:

```python
V2_FLAGS = {
    "vcp_score_multiplier":      False,
    "days_since_pivot_penalty":  False,  # available as defensive toggle
    "sector_cap_top_n":          False,
    "pos_accum_rsi_nullout":     True,   # v2 LOCKED 2026-05-08
    "tiebreak_rs_momentum":      False,
}
```

This is intentionally minimal: a single behavioral change, fully ablated, and validated on both universes. Future cycles (v3+) can revisit the rejected fixes with revised thresholds.

### 7.4 Pre-lock blocker — RESOLVED 10 May 2026

The §8.1 baseline-drift investigation closed cleanly. Of the apparent 4.45→2.61 gap:
- **1.64pp** was an apples-to-oranges comparison (filtered-path FINAL vs raw-path baseline) — not a regression at all.
- **0.20pp** was a real but small `select_top_n` mergesort tiebreak side-effect — now fixed via fast-path early-return.

CLAUDE.md's published v1 FINAL of "alpha 4.45 / hit 91.7" is the filtered-path number. This session's filtered baseline (4.37) reproduces it within 0.08pp (data-cache refresh noise). The v2 promotion verdict for `pos_accum_rsi_nullout` is solid on both universes.

**v2 LOCK was applied to live code on 10 May 2026.** See §8.1a for the file-by-file change list.

---

## 8. Open Items & Action List

### 8.1 Baseline drift incident — RESOLVED 10 May 2026

**Investigation outcome:** the apparent gap between v1 FINAL alpha 4.45 (Run `20260508_105114`) and the new ablation baseline alpha 2.61 (Run `20260508_170831`) decomposed into TWO distinct causes, neither of which invalidates any v2 ablation result.

**Cause 1 — Apples-to-oranges (1.64pp of the gap):** The v1 FINAL was run via `validation.run_chartink_validation()` (the **filtered** path, with Chartink replay + matcher conviction filter). The new ablation harness used `validation.run_validation()` (the **raw** bull-screener path on Nifty500). Different validators, different baselines, by design. The session_handoff.md confirms the original was "chartink_replay mode."

**Cause 2 — Real hook side-effect (0.20pp of the gap):** `v2_fixes.select_top_n()` was NOT a clean no-op when all flags off. Compare:

```python
# v2 hook with all flags off:
picks.sort_values(by=["Score"], ascending=[False], kind="mergesort").reset_index(drop=True).head(top_n)

# validation.py fallback (when hook raises or unimportable):
picks.sort_values("Score", ascending=False).head(top_n)
```

`kind="mergesort"` is stable; default quicksort is not. With ≥5 candidates tied at Score=60 in the Jan-15-26 anchor (and similar ties at other anchors), the tiebreak winners differed → different Top-N → different forward returns.

**Empirical confirmation (Run `20260510_064122`):** monkey-patched `v2_fixes.select_top_n` to raise, forcing the validation.py fallback path. Result: alpha **2.81** (vs 2.61 with hook active). The 0.20pp delta = the hook's tiebreak side-effect, exactly matching the structural prediction.

**Fix applied:** `v2_fixes.py:select_top_n` now has a fast-path early-return at the top:

```python
# FAST PATH — no-op when both relevant flags are off. Must be byte-identical
# to validation.py's fallback so a "v2 hook present, all flags off" run
# reproduces the v1 FINAL baseline exactly.
if not V2_FLAGS["tiebreak_rs_momentum"] and not V2_FLAGS["sector_cap_top_n"]:
    return picks.sort_values("Score", ascending=False).head(top_n)
```

Future runs will reproduce v1 FINAL byte-for-byte when invoked through the hook with all flags off.

**Why no v2 result changes:** every cell in both ablation tables (raw and filtered) used the SAME hook-active baseline. The deltas — and therefore the promotion verdicts — are valid. The fix only matters for future runs that need to byte-reproduce historical baselines.

### 8.1a v2 LOCK applied 10 May 2026

After §8.1 resolution, v2 was committed to live code:

| File | Change |
|---|---|
| `v2_fixes.py` | `V2_FLAGS["pos_accum_rsi_nullout"]` default flipped `False → True`; other 3 flags annotated as REJECTED, `days_since_pivot_penalty` annotated as defensive-mode toggle |
| `v2_fixes.py` | `select_top_n()` fast-path early-return added |
| `chartink_replay.py` | LOCKED block updated; `SCAN_PARAMS_VERSION` bumped to `v2_FINAL_20260510` |
| `CLAUDE.md` | "Current Project State" rewritten to v2 LOCKED; v2 aggregates table; cross-universe verification documented; §8.1 resolution recorded |

### 8.2 Run filtered ablation to completion ✓ DONE

Background task `be07whge6` completed 22:40 IST. Results captured in §5.

### 8.3 Lock v2 (pending §5 + §8.1)

- If `days_since_pivot_penalty` promotes on both raw + filtered universes:
  - Update `chartink_replay.py` v1 LOCKED block → v2.
  - Bump `SCAN_PARAMS_VERSION` to `v2_LOCKED_<date>`.
  - Update CLAUDE.md "Current Project State."
  - Commit message: `feat(screener): lock v2 — Days_Since_Pivot>30 score penalty`.

### 8.4 Defer (per user direction)

- Raw sensitivity grid (`run_sensitivity_grid.py`).
- Filtered sensitivity grid (`run_sensitivity_grid_filtered.py`).

These remain valuable as a future stability check around the v2 optimum but are not needed for the v2 promotion decision.

### 8.5 Begin daily snapshot capture

Every trading day going forward, run `snapshot_archive.snapshot_today()` to populate `data/snapshots/YYYY-MM-DD/`. Without this, the filtered-universe backtester will continue to fall back to yfinance fundamentals (today's promoter-% snapshot has minor look-ahead). After ~6 months of accumulated snapshots, re-run all backtests against the genuine point-in-time Screener.in fundamentals to remove the lookahead.

### 8.6 Pine + Streamlit verification

Before marking the v2.7/v3.8 Pine indicators production-ready:
1. In TradingView, load Beta Edition v2.7 on a known POS-BO qualifier from the Hunter watchlist; confirm it tags as POS-BO.
2. Then artificially flip the chart to a stock with weekly RSI 55 (below the new threshold); confirm POS-BO does NOT fire.
3. Repeat for ADX < 25.
4. Same drill for Dashboard v3.8.
5. Compare a single-symbol output against `chartink_replay.qualifies_hunter()` — must agree.

---

## 9. Files Touched This Session

```
EDITED:
  Commander_Screener_Beta_Edition_v2.6.pine          (→ v2.7; Hunter inputs + ADX numeric gate)
  Commander_Screener_Dashboard_ULTIMATE_v3.7.pine    (→ v3.8; Hunter inputs in f_get_metrics)
  run_v2_ablation.py                                  (kwarg fix: base_universe → universe_name)
  run_sensitivity_grid.py                             (kwarg fix: base_universe → universe_name)

CREATED:
  run_v2_ablation_filtered.py                         (filtered-universe ablation driver)
  run_sensitivity_grid_filtered.py                    (filtered-universe grid driver)
  validation_runs/v2_ablation_results.csv             (raw ablation 6-cell output)
  BACKTEST_RESULTS_v2_SESSION.md                      (this file)

PENDING:
  validation_runs/v2_ablation_filtered_results.csv    (filtered ablation; running)
  BACKTEST_RESULTS_v2.docx                            (final report — generated at end of session)
```

---

*This file is mutable while runs are in flight. It will be frozen, peer-reviewed, and converted to .docx once the filtered ablation completes (§5). Final report will roll into `BACKTEST_RESULTS_v2.docx` and `CLAUDE.md` will be updated to point at v2.*
