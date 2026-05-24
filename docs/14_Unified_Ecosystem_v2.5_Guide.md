# Weinstein Unified Ecosystem v2.5 — User Guide

> **Module Role:** The execution-layer strategy of the Weinstein Commander ecosystem. Combines 9 catalyst edges (6 Bull + 3 Recovery), institutional-grade position sizing, multi-stage exits, and a new diagnostic panel that shows in real-time why each catalyst is or isn't firing.

> **Status:** Bug-fixed and enhanced over v2.3 → v2.4 → v2.5. Backtest-aligned with `chartink_replay.SCAN_PARAMS` and `v2_fixes.V2_PARAMS`.

---

## 0. What Changed Across v2.3 → v2.4 → v2.5

### v2.4 — Bug-Fix Pass (compliance + correctness)
| ID | Fix |
|---|---|
| B1a | Hunter v1 FINAL gates ACTUALLY wired into `pos_bo_trigger` (v2.3 declared but never applied). |
| B1b | v2 LOCK gate ACTUALLY wired into `pos_ac_trigger` (same compliance break). |
| B2 | REV-CB `climax_bar` tautology fixed (`bar_range_max_cb` now uses `[1]` offset). |
| B3 | `vol_acc_ok` comment reconciled with code (threshold = 3). |
| B4 | `mkt_bull` regime gate added to POS-BO and POS-ACCUM. |
| B5 | SWG-REV now excludes Stage 4 stocks. |
| B6 | `stage2_fresh_ok` na-safe via `nz(wStageWks, 999)`. |
| B13 | Mansfield RS ticker concat de-duplicates pre-existing `NSE:` prefix. |

### v2.5 — Enhancement Pass
| ID | Enhancement |
|---|---|
| **E1** | Catalyst Diagnostic Panel — floating 16-row table, per-catalyst first-blocking-gate attribution + hit count. |
| **E2** | Hunter v1 FINAL gates (delivered in v2.4 as B1a + B1b; noted here for traceability). |
| **E3** | `stage2_fresh_max` is now an input (was hardcoded 26). |
| **E4** | `trend_template_low_mult` + `trend_template_high_pct` inputs (defaults preserved). |
| **E5** | Mature Trend Exemption — `mature_trend_ok` bypass path for established LEADING stocks. |
| **E6** | Per-catalyst hit counters plotted to Data Window. |
| **E7** | Sector lookup diagnostics (ticker + path + stage) in diag panel. |
| **E8** | `cb_vol_mult` tooltip clarified (1.8–3.0 typical). |
| **E9** | RFF FY → FQ fallback for sparse small/midcap data. |
| **E10** | `calc_on_every_tick = false` for backtest perf. |
| **E11** | Optional WCL Context Layers gate via `input.source`. |
| **E12** | 11 alertconditions (9 per-catalyst + 2 composites). |

---

## 1. The Catalyst Funnel — What Has to Happen for an Entry

```
              ┌────────────┐
              │ Master Tog │  use_bull_mode / use_rec_mode
              └─────┬──────┘
                    ↓
        ┌───────────────────────┐
        │ Per-catalyst trigger  │  9 candidates: POS-BO, POS-ACCUM,
        │  (granular booleans)  │   SWG-PB, SWG-BO, SWG-REV, SWG-GAP,
        └──────────┬────────────┘   REV-CB, REV-RS, REV-EARLY
                   ↓
        ┌───────────────────────┐
        │ trigger_bull / _rec   │  composite OR
        └──────────┬────────────┘
                   ↓
        ┌───────────────────────┐
        │ WCL Gate (E11)        │  optional Context Layers cross-confirm
        └──────────┬────────────┘
                   ↓
        ┌───────────────────────┐
        │ Routing: trigger_any  │  + position not already open + date range
        └──────────┬────────────┘
                   ↓
        ┌───────────────────────┐
        │ strategy.entry()      │  Kelly-adjusted size, ATR-stop-anchored
        └───────────────────────┘
```

---

## 2. The 9 Catalysts

### Bull Catalysts (6) — fire only when `mkt_bull == true`

#### POS-BO (Positional Breakout)
**Trigger:** `close > 20-bar high AND volume > 1.25×avg AND wRSI ≥ 60 AND ADX ≥ 25`
**Plus:** `base_confirmed AND alpha_ok AND mkt_bull`
**Time stop:** 6 weeks (default `pos_time_stop_weeks`)
**Use case:** Hunter mode — classic Stage 2 breakout from sound base.

#### POS-ACCUM (Positional Accumulation)
**Trigger:** `OBV rising AND VCP tight AND close > 0.9 × 30d high AND d_rsi ≤ 50`
**Plus:** `base_confirmed AND alpha_ok AND mkt_bull`
**Use case:** Smart money accumulation before breakout. RSI cap suppresses HCLTECH-style chase trap.

#### SWG-PB (Swing Pullback)
**Trigger:** `close > SMA50 AND low ≤ EMA20 AND close > EMA20 AND green bar AND VCP tight AND MA stack 150>200 AND RSI 30–70 AND volume dry-up`
**Plus:** `mkt_bull`
**Time stop:** 10 days (default `swg_time_stop_days`)
**Use case:** Pullback entry in confirmed uptrend.

#### SWG-BO (Swing VCP Breakout)
**Trigger:** `VCP tight AND breakout AND volume > 1.5×avg`
**Plus:** `mkt_bull`
**Use case:** Minervini VCP breakout — tighter than POS-BO.

#### SWG-REV (Swing Reversion)
**Trigger:** `close > SMA200 AND close < EMA20 AND RSI < 35 AND green bar AND close > prev high`
**Plus:** NOT Stage 4 (v2.4 fix)
**Use case:** Mean-reversion bounce. Strict 2R T1.

#### SWG-GAP (Gap & Go)
**Trigger:** `gap ≥ 4% AND volume > 3×avg AND close in top 40% of bar`
**Plus:** `mkt_bull`
**Use case:** Catalyst-driven gap-and-go. Very rare — high conviction.

### Recovery Catalysts (3) — fire when market or stock is corrected

#### REV-CB (Climax Bottom)
**Trigger:** `recent climax bar (high vol, wide range, close near low) AND turn bar (green, close > prev high)`
**Plus:** `rff_ok AND regime_ok`
**Use case:** Capitulation reversal — buy the panic low.
**v2.4 fix:** `climax_bar` no longer self-compares — most REV-CB blockers eliminated.

#### REV-RS (RS Survivor)
**Trigger:** `RS slope rising AND higher low AND stock corrected AND RS breakout AND sector S1/S2`
**Use case:** Stocks holding RS strength through correction — first to recover.

#### REV-EARLY (Early Bird)
**Trigger:** `trendline reclaim AND NR7/inside-bar compression AND early breakout AND RS positive`
**Use case:** Earliest base-emergence signal.

---

## 3. Base Confirmation (`base_confirmed`)

The single biggest gate for POS-BO and POS-ACCUM. v2.5 adds an exemption path.

### Strict Path (`weinstein_setup`) — 6 conditions
1. `stage2_uptrend OR stage1_base`
2. `close > SMA200`
3. `rs_quadrant != LAGGING`
4. `vol_acc_ok` — ≥3 of last 20 bars are accumulation candles (green, vol > avg, close in upper 60%)
5. `stage2_fresh_ok` — `wStageWks ≤ stage2_fresh_max` (E3 input, default 26)
6. `trend_template_ok` — `close ≥ low52w × 1.30 AND close ≥ high52w × 0.75` (E4 inputs)

PLUS `mpa_pass`: `close > SMA150 AND SMA150 > SMA200`

### Mature Trend Exemption (`mature_trend_ok`) — E5, default ON
Bypasses Weinstein gate for established leaders:
- `stage2_uptrend`
- `rs_quadrant == LEADING` (must be top quadrant)
- `wStageWks > stage2_fresh_max` (explicitly beyond freshness window)
- `close > EMA20 AND close > SMA200` (trend intact)

PLUS `mpa_pass`.

### Final Logic
```pine
base_confirmed = (weinstein_setup OR mature_trend_ok) AND mpa_pass
```

The diag panel shows which path qualified: `WEINSTEIN` / `MATURE EXEMPT` / `BLOCKED`.

---

## 4. The Diagnostic Panel (E1) — The Most Important New Feature

Default position: **Bottom Right**. Toggle via `Diagnostics → Show Catalyst Diagnostic Panel`.

### Layout

| NAME | STATUS | HITS |
|---|---|---|
| **── BULL ──** | | |
| POS-BO | `✗ wRSI (52<60)` | 3 |
| POS-ACCUM | `✓ FIRE` | 17 |
| SWG-PB | `✗ pullback shape` | 8 |
| SWG-BO | `✗ VCP not tight` | 12 |
| SWG-REV | `✗ RSI not <35 (54)` | 2 |
| SWG-GAP | `✗ no gap up` | 0 |
| **── RECOVERY ──** | | |
| REV-CB | `✗ no climax (last 10b)` | 1 |
| REV-RS | `✗ regime` | 0 |
| REV-EARLY | `✗ no NR7/inside` | 0 |
| **── META ──** | | |
| Sector Ticker | `NSE:CNXIT [AUTO]` | S2 |
| WCL Gate | `OFF` | |
| Base Confirm Path | `WEINSTEIN` | WStg:18w |

### How to Read It

- **Green cell + `✓ FIRE`** — catalyst fired this bar
- **Red cell + `✗ <gate>`** — catalyst blocked by that gate
- **HITS column** — running count of firings over backtest history
- **Sector row** — confirms which sector ticker was used + stage
- **WCL row** — current state of E11 gate
- **Base Confirm Path** — which exemption (if any) qualified `base_confirmed`

### Diagnostic Workflow

1. Open chart with strategy applied.
2. Read STATUS column — first `✗` shows the first failing gate per catalyst.
3. If a gate looks unreasonable (e.g., `✗ wRSI (58<60)` for a stock you're confident is qualifying), tune the input (`hunter_weekly_rsi_min`).
4. Re-check. Next blocking gate will surface.
5. Repeat until catalyst fires or you accept the block.

### Common Diagnostic Patterns

| Status | Meaning | Action |
|---|---|---|
| `✗ mkt_bull (regime)` | Market not in confirmed uptrend | Wait for CNX500 to reclaim |
| `✗ base_confirmed` | Weinstein gate failed | Drill down: check `wStageWks` (freshness) or trend template inputs |
| `✗ alpha (45<50)` | Alpha score below threshold | Lower `min_alpha` or accept the block |
| `✗ wRSI (52<60)` | Weekly RSI too weak | Lower `hunter_weekly_rsi_min` (loses Hunter discipline) |
| `✗ ADX (22<25)` | Trend not yet strong enough | Lower `hunter_daily_adx_min` |
| `✗ RSI (62>50)` | POS-ACCUM RSI too high | Raise `pos_accum_rsi_max` (loses v2 LOCK protection) |
| `✗ rff_ok` | Fundamentals filter | Lower `rff_min_score` or enable E9 FQ fallback |
| `✗ regime` | Recovery gate failed | Either market not corrected enough or stock not corrected |

---

## 5. Inputs Reference (v2.5 NEW / changed)

### `Bull: v1+v2 Locked Filters (Backtest-Verified)`
| Input | Default | Notes |
|---|---|---|
| Hunter Weekly RSI Min (POS-BO) | 60 | v1 FINAL. Mirrors `chartink_replay.SCAN_PARAMS[hunter][weekly_rsi_min]` |
| Hunter Daily ADX Min (POS-BO) | 25 | v1 FINAL. Mirrors `chartink_replay.SCAN_PARAMS[hunter][daily_adx_min]` |
| POS-ACCUM Daily RSI Max | 50 | v2 LOCK. Mirrors `v2_fixes.V2_PARAMS[pos_accum_rsi_threshold]` |

### `Bull: Base Confirmation Tuning (v2.5)` ← NEW
| Input | Default | Range | Notes |
|---|---|---|---|
| **E3** — Stage 2 Freshness Cap (Weeks) | 26 | 4–104 | Was hardcoded. Widen to 52+ for positional mode. |
| **E4** — Min Distance Above 52w Low (×) | 1.30 | 1.0–2.5 | Minervini default. Lower to 1.15 for recovery candidates. |
| **E4** — Min % of 52w High | 0.75 | 0.50–0.95 | Minervini default. Lower to 0.60 for early-base setups. |
| **E5** — Enable Mature Trend Exemption | true | bool | Allows LEADING Stage 2 stocks beyond freshness window. |

### `Recovery: RFF FY→FQ Fallback (v2.5)` ← NEW
| Input | Default | Notes |
|---|---|---|
| **E9** — Backfill RFF FY gaps with FQ | true | Improves coverage on sparse NSE listings. |

### `WCL Context Layers Gate (v2.5)` ← NEW
| Input | Default | Notes |
|---|---|---|
| **E11** — Require WCL setup ≥ threshold | false | When ON, all catalysts require WCL setup priority ≥ min. |
| WCL Setup Source | close | `input.source` — wire to WCL `_setup_pri` plot. |
| WCL Setup Min Priority | 3 | 0–5. 3 = S1/S3/S7. 5 = S2 (Spring/LPS Reversal) only. |

### `Diagnostics (v2.5)` ← NEW
| Input | Default | Notes |
|---|---|---|
| **E1** — Show Catalyst Diagnostic Panel | true | The most useful new feature. |
| Diagnostic Panel Position | Bottom Right | 5 positions |
| Diagnostic Panel Text Size | Small | Tiny / Small / Normal |

---

## 6. Wiring WCL Gate (E11)

### Step 1 — Modify `Weinstein_Context_Layers_v1.1.pine`

Add at the end of the file (after the setup detection block, where `_setup_pri` is computed):

```pine
plot(_setup_pri, "WCL_Setup_Pri", display=display.data_window, color=color.new(color.gray, 80))
```

This exports the setup priority as a Data Window plot (priority value 0–5).

### Step 2 — Apply both indicators

Add the WCL v1.1 indicator AND the v2.5 strategy to the same chart.

### Step 3 — Configure the gate

In strategy settings → `WCL Context Layers Gate (v2.5)`:
1. Set `WCL Setup Source` to `Weinstein Context Layers v1.1: WCL_Setup_Pri` (from the dropdown).
2. Toggle `Require WCL setup ≥ threshold` ON.
3. Set `WCL Setup Min Priority`:
   - `3` = require S1/S3/S7 or higher (default — practical)
   - `5` = require S2 only (Spring/LPS Reversal — max conviction, rarest)

### Step 4 — Verify

Open the diag panel. WCL Gate row should show `PASS (n)` or `FAIL (n<min)`. Catalysts will only fire when WCL Gate passes.

---

## 7. Tuning Workflow

### When catalysts aren't firing on stocks you'd expect

1. **Apply strategy to the stock.** Open diag panel.
2. **Find the catalyst you expected.** Read its STATUS.
3. **Identify the first blocking gate.** Use the diagnostic patterns table (Section 4).
4. **Tune one input at a time.** Don't loosen everything globally.
5. **Re-test on 10 similar stocks** before locking in.

### When catalysts fire too often (false positives)

1. **Run with `Hits` column visible.** Look at the over-firing catalyst.
2. **Tighten the relevant input:**
   - POS-BO too loose → raise `hunter_weekly_rsi_min` to 65
   - SWG-REV chasing → raise `pos_accum_rsi_max` to 45
   - REV-RS firing on weak setups → set `rff_min_score = 3`
3. **Or enable WCL Gate (E11)** to require Context Layers cross-confirm.

### When backtest is too slow

1. Set `calc_on_every_tick = false` (already default in v2.5).
2. Use `Daily Close` breakout confirmation (not Intraday Penetration).
3. Disable the diagnostic panel during long backtest runs (saves table rendering).
4. Limit date range with `use_date = true` + start/end dates.

---

## 8. Expected Catalyst Hit Rates (rule of thumb)

On a typical NSE large/mid cap over 3 years (≈750 bars):

| Catalyst | Typical hits | High range | Notes |
|---|---|---|---|
| POS-BO | 5–15 | 25 | Strictest of all — high conviction |
| POS-ACCUM | 8–20 | 40 | Looser than POS-BO |
| SWG-PB | 15–40 | 80 | Common — pullback to EMA20 |
| SWG-BO | 10–25 | 50 | Requires VCP |
| SWG-REV | 3–10 | 20 | RSI<35 is rare in uptrends |
| SWG-GAP | 0–3 | 8 | Mega-gaps only |
| REV-CB | 1–5 | 15 | Per market correction |
| REV-RS | 5–15 | 30 | Per recovery phase |
| REV-EARLY | 2–8 | 20 | Per base formation |

If your numbers are far below these, check:
- Diag panel STATUS column for systematic blocks
- Whether `base_confirmed` is the choke point (Mature Trend Exemption helps)
- Whether `regime_ok` is blocking all Recovery catalysts (no market correction)

---

## 9. Alerts (E12)

11 `alertcondition()` entries. To create an alert:
1. Right-click chart → Add alert
2. Condition: `Weinstein Unified Ecosystem [v2.5]`
3. Pick:

| Alert | When it fires |
|---|---|
| POS-BO Fired | POS-BO trigger true (independent of position state) |
| POS-ACCUM Fired | POS-ACCUM trigger true |
| SWG-PB Fired | SWG-PB trigger true |
| SWG-BO Fired | SWG-BO trigger true |
| SWG-REV Fired | SWG-REV trigger true |
| SWG-GAP Fired | SWG-GAP trigger true |
| REV-CB Fired | REV-CB trigger true |
| REV-RS Fired | REV-RS trigger true |
| REV-EARLY Fired | REV-EARLY trigger true |
| ANY Bull Catalyst | Any of the 6 Bull catalysts (post-WCL gate) |
| ANY Recovery Catalyst | Any of the 3 Recovery catalysts (post-WCL gate) |

Each alert includes `{{ticker}}` in the message — useful for Telegram routing.

---

## 10. Common Mistakes

1. **Loosening multiple gates without retesting.** Always tune one input at a time and benchmark against the prior baseline.

2. **Enabling Mature Trend Exemption (E5) on Stage 3 stocks.** E5 requires `stage2_uptrend == true`. Stocks transitioning to Stage 3 won't qualify — by design.

3. **Setting `min_alpha` too high in choppy markets.** Alpha score depends on momentum + RSI + ADX. In sideways markets, scores stay 30–55. If you require ≥60, nothing fires.

4. **Forgetting WCL Gate is OFF by default.** The diagnostic panel will show `WCL Gate: OFF`. To activate, follow Section 6.

5. **Reading `Hits` column as recent activity.** It's a running cumulative count from script start. Reset by recompiling.

6. **Misinterpreting `MATURE EXEMPT` as a worse signal.** It's not worse — it's the same path with relaxed freshness. Verify via your backtest equity curve before trusting it long-term.

7. **Using `Intraday Penetration` with `process_orders_on_close=true`.** These contradict — entry intended mid-bar but fill at close. Either flip `process_orders_on_close=false` (changes baseline) or use `Daily Close` mode.

---

## 11. Integration with the Broader Ecosystem

| Component | Integration |
|---|---|
| **Dashboard v67.0** | Provides Stage + Alpha Score + Recommendation. Strategy uses same `alpha_score` formula. |
| **Context Layers v1.1 (WCL)** | NEW v2.5 — wire WCL setup priority via E11 input.source. Cross-confirms catalysts with Wyckoff + VP + SMC + Stage. |
| **Risk Allocator v1.0** | Strategy outputs catalyst type via `strategy.entry comment`. Map catalyst → Kelly multiplier in Risk Allocator. |
| **Beta Screener v2.6 / Capitulation Screener v1.5** | Screeners surface candidates; strategy executes. v2.5 alpha + v1+v2 gates match screener invariants exactly. |
| **GTT_Auto_Shield** | Strategy emits per-position ATR stops; GTT_Auto_Shield enforces them at broker level. |

---

## 12. Quick Reference — v2.5 Defaults

| Group | Parameter | Default |
|---|---|---|
| Master | Bull mode | ON |
| Master | Recovery mode | ON |
| Bull POS | bo_conf | Daily Close |
| Bull POS | bo_len | 20 |
| Bull POS | pos_time_stop_weeks | 6 |
| v1+v2 | hunter_weekly_rsi_min | 60 |
| v1+v2 | hunter_daily_adx_min | 25 |
| v1+v2 | pos_accum_rsi_max | 50 |
| **Base Tuning** | stage2_fresh_max | 26 |
| **Base Tuning** | trend_template_low_mult | 1.30 |
| **Base Tuning** | trend_template_high_pct | 0.75 |
| **Base Tuning** | use_mature_trend_exempt | ON |
| Bull Filters | min_alpha | 50 |
| Bull Filters | bull_hold_days | 3 |
| Bull Filters | use_rs | ON |
| **RFF Fallback** | use_rff_fq_fallback | ON |
| **WCL Gate** | use_wcl_gate | OFF |
| **WCL Gate** | wcl_score_min | 3 |
| **Diagnostics** | use_diag_panel | ON |
| **Diagnostics** | diag_pos | Bottom Right |
| Recovery CB | cb_climax_window | 10 |
| Strategy | calc_on_every_tick | false (E10) |
| Strategy | process_orders_on_close | true |
| Strategy | pyramiding | 6 |

---

## 13. Migration Path v2.3 → v2.5

1. **Save v2.3 chart settings** before swapping.
2. **Add v2.5** to chart.
3. **Re-set inputs** that don't auto-migrate:
   - Mature Trend Exemption: ON (default)
   - Diagnostic Panel: ON (default)
   - WCL Gate: OFF (default — wire later)
4. **Run backtest** and compare equity curve to v2.3 baseline.
5. **Expect differences:**
   - POS-BO firings ↓ (Hunter gates now wired — B1a)
   - POS-ACCUM firings ↓ (RSI cap now wired — B1b)
   - REV-CB firings ↑ (tautology fixed — B2)
   - SWG-REV firings ↓ (Stage 4 exclusion — B5)
   - POS-* in mature uptrends ↑ (Mature Exemption — E5)
6. **Tune via diag panel** until equity curve stabilizes.
7. **Commit v2.5 as your live strategy.**

---

*Last updated: 2026-05-17. v2.5 is the canonical Unified Ecosystem strategy reference. v2.3 and v2.4 files remain for historical backtest comparison.*
