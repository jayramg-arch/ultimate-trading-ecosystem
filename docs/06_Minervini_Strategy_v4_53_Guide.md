# Weinstein Minervini Strategy v4.53 — User & Trading Guide [DEPRECATED — DOCUMENT-ONLY REFERENCE]

> **🛑 DEPRECATED — Files deleted from project root on 10 May 2026.**
> All standalone `Weinstein_Minervini_Strategy*.pine` files (v2.0, v3.0, v4.0, v4.53, unversioned) have been removed. The 6 bull edges (POS-AC, POS-BO, SWG-PB, SWG-BO, SWG-REV, GAP-GO) have been **fully consolidated** into the canonical strategy file:
>
> - **`Weinstein_Unified_Ecosystem_v2.2.pine`** (in-file `strategy()` title now `[v2.3]`)
>
> The v2.3 lock (10 May 2026) added two new gates from the Backtest v2 results:
> - `pos_bo_trigger` now requires `wRSI ≥ 60 AND adx_val ≥ 25` (v1 FINAL Hunter sync)
> - `pos_ac_trigger` now requires `d_rsi ≤ 50` (v2 LOCK — POS-ACCUM late-stage chase trap suppression)
>
> **For active trading**, use:
> - **[14_Unified_Ecosystem_Trading_Guide.md](./14_Unified_Ecosystem_Trading_Guide.md)** — the operational playbook for all 9 edges
> - **[13_Unified_Ecosystem_User_Guide.md](./13_Unified_Ecosystem_User_Guide.md)** — input-by-input field reference
>
> This document is retained only as a historical record of the standalone v4.53 logic. None of its parameter recommendations should be considered current — the consolidated v2.3 implementation is the source of truth.

> **Module Role:** The primary **trend-following, growth-momentum arm** of the suite. This is the core trade engine that combines Stan Weinstein's stage analysis with Mark Minervini's Trend Template and VCP pattern to identify the highest-quality breakout and pullback entries in Stage 2 uptrends. Every other module either feeds into this strategy (Dashboard, Screeners, Zigzag) or supports its execution (Risk Allocator, SMC Zones for entry precision).

---

## 1. What It Does

The strategy operates across **six distinct trade catalysts** (called "edges"), each with its own entry, stop, and target logic, unified by an overarching **Alpha Quality Score** that gates all entries:

| Catalyst ID | Code | Description |
|---|---|---|
| 1 | **POS-ACCUM** | OBV breakout with institutional accumulation in a base |
| 2 | **POS-BO** | Weinstein Stage 2 breakout above 21-day high with volume |
| 3 | **SWG-PB** | Minervini EMA-20 pullback in a strong uptrend |
| 4 | **SWG-BO** | VCP momentum breakout above 15-day pivot with anti-algo filter |
| 5 | **SWG-REV** | RSI(3) mean-reversion in Stage 1/2 with weekly RSI > 40 |
| 6 | **SWG-GAP** | Gap-and-Go (≥4% gap, 3× volume, intraday close ≥60% of range) |

---

## 2. The Alpha Quality Score (0–100)

Every entry is gated by an **Alpha Score ≥ 60**. This is the strategy's primary intelligence filter:

| Condition | Points |
|---|---|
| Close > EMA20 | +15 |
| Close > SMA50 | +15 |
| RSI(14) > 60 | +20 |
| RSI(14) > 50 (partial) | +10 |
| ADX > 20 with +DI > -DI | +10 |
| Green bar with volume > 1.5× avg | +20 |
| Green bar with volume > avg (partial) | +10 |
| Distance to EMA20 < 5% | +20 |
| Distance to EMA20 < 10% (partial) | +10 |
| Macro Edge (VWMA50 > SMA50) | +10 |
| Macro Edge OFF but volume < avg | −20 |

**Maximum: 100 points. Threshold: 60+ to qualify for any trade.**

---

## 3. Inputs — Field-by-Field

### Portfolio & Risk
| Input | Default | Explanation |
|---|---|---|
| **Total Portfolio Capital** | `100,000` | Used as the base for Kelly-adjusted position sizing. Update to your actual portfolio value. |
| **ETF Risk %** | `1.0` | Percentage of portfolio risked on each ETF trade before adjustments. |
| **Stock Risk %** | `0.75` | Percentage of portfolio risked on each stock trade. Lower than ETF due to higher idiosyncratic risk. |
| **Max Allocation per Trade** | `25,000` | Hard cap on INR deployed into any single position, regardless of what the Kelly formula suggests. Prevents over-concentration. |
| **Asset Type** | `Auto` | `Auto` detects ETF vs. Stock using `syminfo.type`. Override manually if needed. |

### Strategy Inputs
| Input | Default | Explanation |
|---|---|---|
| **Weinstein SMA Length (Weekly)** | `30` | The canonical 30-week SMA from Stan Weinstein's "Secrets for Profiting." Never change this. |
| **30 WMA Slope Lookback** | `4` | How many weeks back to measure the 30-week SMA slope. 4 weeks (1 month) balances responsiveness with noise. |
| **30WMA Slope Threshold** | `0.0005` | A slope smaller than `MA × 0.0005` is classified as "flat" (Stage 1 or 3 base). |
| **Benchmark 1 (Nifty 50)** | `NSE:NIFTY` | Used for RS calculations vs. the large-cap index. |
| **Benchmark 2 (Nifty 500)** | `NSE:CNX500` | Breadth index — the primary RS benchmark for Mansfield RS. |
| **RS Slope Length** | `26` | Weeks for the Mansfield RS calculation (6-month window). |
| **RS Slope Lookback** | `8` | Weeks for measuring RS momentum direction. |
| **RS Slope Sensitivity** | `0.2` | On the ×100 Mansfield scale, an RS-Momentum ROC > 0.2 registers as "Rising." |

### Daily MA Settings
| Input | Default | Explanation |
|---|---|---|
| **50 DMA Length** | `50` | Core trend MA for daily structure. Price > SMA50 = bullish daily bias. |
| **150 DMA Length** | `150` | Mid-term trend. Part of the Minervini Trend Template alignment gate. |
| **200 DMA Length** | `200` | Long-term trend. Stage 2 requires price > SMA200 at minimum. |
| **50DMA Slope Lookback** | `21` | Days used to assess 50 DMA slope direction (rising = Stage 2 confirmation). |

### Technical Settings
| Input | Default | Explanation |
|---|---|---|
| **ATR Length** | `14` | Standard ATR used for stop-loss calculation and volatility assessment. |
| **Pivot Lookback Left/Right** | `2/2` | Pivot detection parameters — **keep consistent with the Zigzag indicator**. |
| **VP Lookback** | `100` | Volume Profile lookback fed into the inline VP calculation in the strategy. |

### Mathematical Edges
| Input | Default | Explanation |
|---|---|---|
| **Macro Edge (Institutional Vol Bias)** | `true` | Requires VWMA(50) > SMA(50) for STRONG BUY signals, confirming institutional volume is above the baseline trend. Disabling this reduces signal quality but increases signal frequency. |
| **Micro Edge (Price & Squeeze Validation)** | `true` | Requires price > CPR and Monthly VWAP AND a 20/50 MA squeeze for PULLBACK signals. Confirms the pullback is within an institutional value zone. |

### Risk Adjustment (Kelly Sizing)
| Input | Default | Explanation |
|---|---|---|
| **Enable Kelly Probability Sizing** | `true` | Scales the base risk % between 0.75× and 1.25× based on three quality conditions: (1) Stage 2 alignment, (2) Positive RS, (3) Above-average volume. All three = 1.25× (increase size); two = 1.0× (neutral); one or zero = 0.75× (reduce size). |
| **Reduce Risk if ATR > 3%** | `true` | Applies a volatility discount. If daily ATR/close > 3%, position size is reduced proportionally to keep the actual INR risk constant regardless of how volatile the stock is. |
| **Bear-Market Risk Discount (−0.25%)** | `true` | When CNX500 is below its 200 SMA, the base risk % is reduced by 0.25% automatically. Enforces capital protection in adverse macro conditions. |

### Time Stops
| Input | Default | Explanation |
|---|---|---|
| **Positional Time Stop (Weeks Stagnant)** | `6` | If a positional trade has been open for ≥6 weeks with unrealised profit < 0.5R, it is closed. Frees capital from dead-money positions. |
| **Swing Time Stop (Days Stagnant)** | `10` | Same logic for swing trades — close after 10 days of stagnation below 0.5R. |

---

## 4. The Weinstein Stage State Machine

The strategy uses a hysteresis-based state machine (not a one-shot calculation) to determine the Weinstein Stage on the Weekly timeframe:

```
Stage 4 → Stage 1:  30W MA flattens (slope < threshold) AND price above MA
Stage 1 → Stage 2:  30W MA starts rising AND price above MA
Stage 2 → Stage 3:  30W MA flattens AND price drops below MA
Stage 2 → Stage 4:  30W MA falls AND price below MA (sharp breakdown)
Stage 3 → Stage 4:  30W MA begins falling
Stage 3 → Stage 2:  30W MA rises AND price reclaims MA
```

**Why hysteresis?** Without it, the stage would flip on every minor wobble of the 30-week SMA. The state machine requires **sustained** conditions before transitioning — preventing false stage readings during brief consolidations.

`wStageWks` tracks how many weeks the stock has been in the current stage. POS entries require `wStageWks ≤ 26` (fresh Stage 2, not late-cycle).

---

## 5. POS-BO: The Full 9-Gate Weinstein Setup Check

The most selective entry in the strategy. All nine gates must be true:

```
Gate 1: Weekly stage = Stage 2 (UP) or Stage 1 (BASE)
Gate 2: Close > 200 DMA
Gate 3: Sector RS not "Lagging" (auto-detected sector index)
Gate 4: Sector itself in Stage 1 or 2 (sector_stage_ok)
Gate 5: Trend Template — within 25% of ATH AND >30% above 52W low
Gate 6: vol_acc_ok — ≥6 of last 20 bars: green close, upper 60% of range, vol > avg
Gate 7: stage2_fresh_ok — wStageWks ≤ 26 (not late-cycle Stage 2)
Gate 8: ma_sqz_ok — SMA20 and SMA50 within 5% of each other (coiling)
Gate 9: bb_sqz_ok — Bollinger Band width below its 120-bar SMA (squeeze active)
```

Then additionally: `close > 21-day high + close in top 25% of range + volume ≥ 1.25× avg + alpha_ok (≥60)`.

---

## 6. SWG-PB: The EMA-20 Pullback

The highest-precision swing entry:

```
Minervini Trend Template active (50 > 150 > 200 DMA alignment)
AND Distance to EMA20 ≤ ±1.5%  (tight EMA20 proximity zone)
AND RSI(14) in 40–60 range  (not overbought, not oversold)
AND Weekly RSI > 60  (strong weekly momentum)
AND Volume < 70% of average (Volume Dry-Up — VDU)
AND Close < prior close  (price actually pulling back)
AND Alpha Score ≥ 60
```

The VDU (Volume Dry-Up) condition is critical: a low-volume pullback to EMA20 signals that sellers are absent, not aggressive — a genuine rest in a strong trend.

---

## 7. Dynamic Risk/Reward Targets

The strategy adjusts targets based on market regime:

| Market | T1 R-Multiple | T2 R-Multiple | Exit Split |
|---|---|---|---|
| Bull (CNX500 > SMA200 + golden cross) | 2.5R | 3.0R | 50% T1, 25% T2, 25% trail |
| Bear (CNX500 < SMA200) | 2.0R | 3.5R | 50% T1, 25% T2, 25% trail |

In a bear market, T2 is set higher because trades that survive the first target in a headwind environment have cleared significant resistance — let them run further.

---

## 8. Chandelier Exit (Trailing Stop)

The strategy uses an adaptive Chandelier Exit for the trailing 25% of the position:

```
Bull market: CE multiplier = 3.0 × ATR14
Bear market: CE multiplier = 3.5 × ATR14
Special timeframes (75min/125min): CE multiplier = 2.5 × ATR14
```

The Chandelier Exit is **purely trailing** — it tightens behind the position as price rises, and never moves back down. When price closes below the CE level, the trailing position is exited.

---

## 9. Overhead Resistance Check

Before confirming any trade, the strategy checks if T1 is blocked by overhead resistance:

```
overhead_res = min(52W_high, SMA200)
If T1 > overhead_res → WARNING: "T1 > Overhead Res" displayed
```

This prevents entering trades where the profit target is immediately capped by significant resistance. When this warning appears, either select a different entry point or reduce T1 to below the resistance.

---

## 10. Ecosystem Integration

| Module | How It Connects |
|---|---|
| **Unified Ecosystem v2.2** | All 6 bull edges are now integrated here — this standalone script is legacy only |
| **Beta Screener v2.6** | Exact screener port of all 6 catalysts — scan 100+ stocks, load candidates on Dashboard |
| **Dashboard v67.0** | Shows Alpha Score, Catalyst ID, Style (Positional/Swing/Both), and Recommendation |
| **Risk Allocator v1.0** | Standalone version of the strategy's position sizing panel — use for manual trades |
| **Zigzag v6.0** | `f_getStrictTrend()` shared — trend consistency across all modules |
| **Volume Profile v1.0** | VCP coiling in POS-ACCUM and SWG-BO should occur near the POC |
| **SMC Zones v1.0** | LPS pullback to a Bullish OB within the EMA20 zone = highest-precision SWG-PB entry |

---

## 11. Daily Trading Workflow

> For the current live workflow, see **[Guide 14 — Unified Ecosystem Trading Guide](./14_Unified_Ecosystem_Trading_Guide.md)**. The steps below are the legacy standalone flow.

1. **Pre-market:** Run Beta Screener v2.6 → find stocks with `catalyst_id > 0` AND `alphaScore ≥ 60`
2. **Shortlist:** Filter for `stage ≥ 1.0` AND `rs500State contains "Leading"` AND `conf_score ≥ 4`
3. **Load on Dashboard v67.0:** Verify the recommendation is BUY or STRONG BUY (not BUY*)
4. **Check Risk Allocator / inline risk panel:** Confirm position size, T1, T2, CE mode
5. **Entry:** On signal bar close (or next open for gap-prone stocks)
6. **Management:** Update the Dashboard's portfolio slot with ticker, entry, SL, date

---

## 12. Common Mistakes

1. **Ignoring Alpha Score gate** — Every catalyst requires `alpha_ok = score ≥ 60`. Trading below 60 means fighting the momentum filter.
2. **Entering POS-BO late** — POS-BO requires fresh Stage 2 (`wStageWks ≤ 26`). Entering a stock in late Stage 2 (week 30–40) captures the tail end of the move.
3. **Skipping sector gate** — `sector_stage_ok` requires the auto-detected sector to also be in Stage 1/2. Buying a stock in a Stage 4 sector almost never works.
4. **Ignoring VDU on SWG-PB** — A pullback to EMA20 with heavy volume is a distribution signal, not an entry. Volume must dry up.
5. **Moving the T1/T2 arbitrarily** — The R-multiple targets are backtested. Don't move them "because it feels like it will run further" — take the defined exit and redeploy.
