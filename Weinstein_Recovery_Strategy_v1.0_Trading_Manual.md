# Weinstein Recovery Strategy v1.0 – Trading Manual

> [!WARNING]
> **LEGACY REFERENCE - ARCHIVAL USE ONLY**
> This standalone strategy guide (v1.0) has been superseded by the **Unified Ecosystem v2.2** documentation framework.
> For the current canonical source of truth and operational recovery logic, please refer to:
> - [13_Unified_Ecosystem_User_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/13_Unified_Ecosystem_User_Guide.md)
> - [14_Unified_Ecosystem_Trading_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/14_Unified_Ecosystem_Trading_Guide.md)
> - [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)

---

**Strategy:** Weinstein Recovery Strategy v1.0  
**File:** `Weinstein_Recovery_Strategy v1.0.pine`  
**Exchange:** NSE (National Stock Exchange, India)  
**Timeframe:** Daily chart only  
**Capital Base Used in Examples:** ₹5,00,000  
**Manual Version:** 1.0 | April 2026

---

> **How this manual differs from the User Guide**
>
> The User Guide explains *what each setting does*. This Trading Manual explains *how to trade* — the complete operational procedure from pre-market preparation to exit execution, including worked numerical examples, entry timing, order placement, daily management routines, journal templates, and the psychological discipline required to follow the system.

---

## Table of Contents

1. [The Strategy in One Page](#1-the-strategy-in-one-page)
2. [Market Regime Assessment — The Foundation of Every Decision](#2-market-regime-assessment--the-foundation-of-every-decision)
3. [The Three Edges — Trading Logic & Decision Rules](#3-the-three-edges--trading-logic--decision-rules)
   - [REV-CB: Climax Bottom Bounce](#31-rev-cb-climax-bottom-bounce)
   - [REV-RS: RS Survivor Breakout](#32-rev-rs-rs-survivor-breakout)
   - [REV-EARLY: Early Bird VCP](#33-rev-early-early-bird-vcp)
4. [Position Sizing — The Complete Calculation](#4-position-sizing--the-complete-calculation)
5. [Entry Execution — Order Types, Timing, and Triggers](#5-entry-execution--order-types-timing-and-triggers)
6. [Stop Loss Placement — Every Scenario](#6-stop-loss-placement--every-scenario)
7. [Partial Profit Taking — T1 and T2 Rules](#7-partial-profit-taking--t1-and-t2-rules)
8. [Trailing Stop Management — Bar by Bar](#8-trailing-stop-management--bar-by-bar)
9. [Mandatory Exit Rules](#9-mandatory-exit-rules)
10. [The Complete Trade Lifecycle — Three Worked Examples](#10-the-complete-trade-lifecycle--three-worked-examples)
    - [Example A: REV-CB Trade (Swing)](#example-a-rev-cb-trade-swing)
    - [Example B: REV-RS Trade (Positional)](#example-b-rev-rs-trade-positional)
    - [Example C: REV-EARLY Trade (Positional)](#example-c-rev-early-trade-positional)
11. [Daily Trading Routine](#11-daily-trading-routine)
12. [Weekly Review Routine](#12-weekly-review-routine)
13. [Portfolio Heat Management — Running Multiple Positions](#13-portfolio-heat-management--running-multiple-positions)
14. [The Fundamental Filter (RFF) — How to Verify Manually](#14-the-fundamental-filter-rff--how-to-verify-manually)
15. [Edge-Specific Trading Rules Summary](#15-edge-specific-trading-rules-summary)
16. [What the Chart is Telling You — Reading Every Visual](#16-what-the-chart-is-telling-you--reading-every-visual)
17. [Pre-Trade Checklist](#17-pre-trade-checklist)
18. [Trade Journal Template](#18-trade-journal-template)
19. [Scenario Decision Guide — "What Do I Do When..."](#19-scenario-decision-guide--what-do-i-do-when)
20. [Transitioning Back to the Bull Market Strategy](#20-transitioning-back-to-the-bull-market-strategy)

---

## 1. The Strategy in One Page

**Purpose:** Capture NSE stocks that have corrected from highs due to macro/geo-political fear but remain fundamentally sound businesses. Three distinct edges cover the full spectrum from deep panic bottoms to early trend recovery.

**The three edges and their roles:**

```
REV-CB  ─ "The Ambulance"
  Deeply stretched stock (≥15% below SMA200) hits panic capitulation volume,
  then shows a reversal bar. Swing trade to EMA20 (T1) and potentially SMA200 (T2).
  Hold: 1–3 weeks.

REV-RS  ─ "The Survivor Leader"
  Stock outperformed the index during the correction (positive RS), now breaking
  above its 20-day high while in recovery state (close > SMA50, SMA50 < SMA200).
  Positional trade to 52-week high (T2).
  Hold: 4–12 weeks.

REV-EARLY ─ "The Early Mover"
  SMA50 approaching or crossing SMA200. VCP base complete, pivot breakout.
  Positional trade to 52-week high (T2).
  Hold: 6–16 weeks.
```

**The three gates every trade must pass:**

```
Gate 1 — REGIME:  Mandatory 10% correction floor (Stock ≥10% below 52W high)
Gate 2 — QUALITY: RFF score ≥ 3/6 (stock is profitable, not a value trap)
Gate 3 — EDGE:    Specific technical trigger for the relevant edge
```

**Risk architecture:**

```
Risk per trade:     0.50% of capital
Max positions:      4 simultaneous
Portfolio heat cap: 4 × 0.50% = 2.0% maximum simultaneous exposure
Max allocation:     ₹25,000 per trade (prevents oversizing in low-priced stocks)
```

**Capital example (₹5,00,000 portfolio):**

```
Risk per trade:  ₹5,00,000 × 0.50% = ₹2,500 maximum loss per trade
Max 4 trades:    ₹2,500 × 4 = ₹10,000 maximum portfolio loss if all 4 stop out simultaneously
```

---

## 2. Market Regime Assessment — The Foundation of Every Decision

Before looking at any individual stock, assess the market regime. The entire strategy is calibrated for specific regime conditions.

### Step 1: Load NSE:CNX500 on a daily chart

Look for two moving averages:
- **Blue line (SMA50)** — 50-day simple moving average
- **Red line (SMA200)** — 200-day simple moving average

### Step 2: Identify which regime you are in

| SMA Relationship | Regime | Strategy Action |
|-----------------|--------|-----------------|
| SMA50 < SMA200 AND price < SMA200 | **BEAR** | Maximum caution. Only REV-CB on the most extreme stretches. Reduce position sizes to 0.25%. Max 2 positions. |
| SMA50 < SMA200 AND price > SMA200 | **RECOVERY** ← Target zone | Full strategy runs. Standard 0.50% risk. Up to 4 positions. |
| SMA50 just crossed above SMA200 | **TRANSITION** | Recovery still running for laggard stocks. Reduce REV-CB. Increase REV-EARLY. Begin transitioning to v4.51. |
| SMA50 > SMA200 AND price > SMA200 | **BULL** | Switch primary tool to `Weinstein_Minervini_Strategy v4.51`. Recovery v1.0 remains active for laggards only (max 2 positions). |

### Step 3: Check how deep the recovery is

Pull up the Strategy's Risk Allocator table on any chart. The "Regime" row shows RECOVERY / BULL / BEAR in real time. Do not trust your memory — verify this daily.

### Step 4: Check the correction depth on your watchlist stocks

Even in a full BULL regime, a stock that has corrected ≥10% from its 52-week high can still trigger recovery entries. Crucially, as of April 2026, the regime gate is now a strict filter: for any Recovery signal (RS/CB/EARLY) to fire, the stock ITSELF must be ≥10% corrected from its 52-week high. Market-wide recovery (index down) no longer overrides this individual stock requirement. This ensures we are only buying "turnaround" plays and not ATH momentum leaders in this strategy.

### Regime-based parameter adjustments

| Regime | Risk % | Max Positions | REV-CB | REV-RS | REV-EARLY |
|--------|--------|--------------|--------|--------|-----------|
| BEAR | 0.25% | 2 | ON (only extreme CB ≥20%) | OFF | OFF |
| RECOVERY | 0.50% | 4 | ON | ON | ON |
| TRANSITION | 0.50% | 3 | Reduce (CB ≥18%) | ON | ON |
| BULL | 0.40% | 2 | OFF | ON (laggards) | OFF |

---

## 3. The Three Edges — Trading Logic & Decision Rules

### 3.1 REV-CB: Climax Bottom Bounce

**What the algorithm is detecting:**

The market has subjected a fundamentally strong stock to panic selling. Institutions who understand the business value are absorbing this supply at distressed prices. The result is a textbook capitulation pattern: extreme stretch below the 200-day MA, dual RSI collapse, abnormal volume on a bearish/wide bar, followed by a green reversal bar that breaks above the previous session's high.

**The mental model:** This is NOT a trend-following trade. It is a mean-reversion trade. You are buying at maximum fear and targeting the EMA20, which is where panic-sold stocks tend to stabilise before the next decision point. The thesis is not "this stock will make new all-time highs" — the thesis is "this stock was sold 25% below its natural mean and will snap back to that mean."

**Four pillars you must see on the chart:**

**Pillar 1 — The Stretch:** Visually, price should be noticeably below the red SMA200 line. The chart will have a pronounced gap between price and the SMA200. For the default 15% threshold: on a ₹500 stock with SMA200 at ₹600, the price must be at or below ₹510 (15% below ₹600). The orange EMA20 will be even further above — often 20–35% above the current price in severe cases.

**Pillar 2 — The Washout:** Check the RSI indicator if you have it separately, or trust the algorithm. You are looking for a period of sustained, relentless selling with no meaningful bounces. Multiple consecutive red bars with increasing volume declining to exhaustion.

**Pillar 3 — The Climax Bar:** On the capitulation bar, volume should be visually striking — a bar whose volume column towers above the surrounding bars. The bar itself will typically be red (bearish) or have an unusually long range (long-legged doji or spinning top at the lows). This is the panic sell-off bar where weak hands exit and institutions absorb.

**Pillar 4 — The Turn (your entry bar):** A green bar that:
- Closes above its own open (bullish close)
- Closes in the upper 40% of the bar's range (body in the upper portion)
- Closes above the previous bar's high (breaks prior resistance)

When all four are present within the 5-bar window, the "CB" triangle appears below the bar.

**Key decision question before entering a CB signal:** "Is the EMA20 meaningfully above current price?" 

If the EMA20 is only 3–5% above the entry, the R:R is poor. You want to see EMA20 at least 8–10% above the entry for a worthwhile CB trade. Check the "T1 CB (EMA20)" row in the allocator table — the R-multiple shown there tells you immediately. A T1 showing "1.2R" means poor R:R. A T1 showing "2.5R" or above is an attractive setup.

**What a strong CB setup looks like:**
- Price: ₹350 (currently)
- SMA200: ₹500 (stock is 30% below SMA200 — extreme stretch)
- EMA20: ₹430 (T1 is 22.9% above entry)
- SL: ₹320 (climax low − ATR)
- Risk: ₹350 − ₹320 = ₹30
- T1 R-multiple: (₹430 − ₹350) / ₹30 = 2.7R — excellent

**What a weak CB setup looks like:**
- Price: ₹470 (currently)  
- SMA200: ₹510 (only 8.5% below — barely meets the 15% threshold — marginal)
- EMA20: ₹495 (T1 is only 5.3% above entry)
- SL: ₹450
- Risk: ₹470 − ₹450 = ₹20
- T1 R-multiple: (₹495 − ₹470) / ₹20 = 1.25R — poor, skip

**Decision rule:** If T1 R-multiple is below 1.5R for a CB trade, do not enter. The asymmetry is insufficient to justify the risk of a bounce that stalls.

---

### 3.2 REV-RS: RS Survivor Breakout

**What the algorithm is detecting:**

During the correction, most stocks fell sharply. Some fell less — these are the stocks with genuine institutional conviction. Funds that believe in the business kept buying into weakness, preventing the stock from falling as much as the index. When the market begins to recover, these RS leaders are the first to break to new relative highs, and they are the ones that eventually make new absolute highs.

**The mental model:** You are identifying the strongest stocks in a recovering market and buying their first meaningful breakout after the correction. This is a trend-initiation trade — you are buying strength, not weakness. The thesis is "this stock outperformed during the storm and will lead during the recovery."

**The five conditions you must verify on the chart:**

**Condition 1 — Positive RS:** Check the "RS vs CNX500" row in the allocator table. It must show a positive number. If it shows −2.3, the stock has underperformed during the correction — skip entirely. If it shows +1.8, the stock outperformed.

**Condition 2 — Recovery State:** The SMA50 (blue) must be below the SMA200 (red), but price must be above the SMA50 (blue). Visually: price is above the blue line, blue line is below the red line. This is the "recovery formation" — the stock is rebuilding from below, not yet in a full bull market.

**Condition 3 — Corrected Enough:** The 52-week high is shown in the allocator table as "T2 RS/Early." The stock must currently be ≥10% below that level. If the T2 level shows ₹800 and the stock is at ₹720 (10% below), it barely qualifies. If it is at ₹620 (22.5% below), it is a strong candidate.

**Condition 4 — The Breakout:** Price closes above the highest high of the last 20 days. On the chart, this will typically look like price clearing a horizontal resistance zone that formed during the base-building period. Volume on the breakout bar must be above average (the algorithm checks for 1.5× 50-day average volume).

**Condition 5 — Sector Stage:** Open the sector index chart (shown in the allocator table's sector ticker). The sector should show a yellow (Stage 1) or green (Stage 2) background — not red (Stage 4). Buying a stock recovering when the whole sector is still collapsing is fighting the tide.

**What a strong RS setup looks like:**
- Stock: HCLTECH
- RS vs CNX500: +2.4 (clear outperformer during IT sector correction)
- Price: ₹1,580 (above SMA50 of ₹1,520)
- SMA50 (₹1,520) < SMA200 (₹1,680) — recovery state confirmed
- 52W High: ₹1,920 — stock is 17.7% below → correction qualifies
- Breakout: Price closes above 20-day high of ₹1,565 → confirmed
- CNXIT sector: Stage 1 (yellow background) → sector not in Stage 4
- RFF: 4/6 → passes
- Signal fires: "RS" triangle appears

**Decision rule:** If the stock barely cleared the 20-day high (breakout by < 0.5%) with weak volume (< 1.2× average), treat it as a marginal setup and wait for the next day's confirmation close. A marginal breakout with average volume often fails. A clear breakout with 2× volume rarely does.

---

### 3.3 REV-EARLY: Early Bird VCP

**What the algorithm is detecting:**

This is the most forward-looking edge. It targets stocks where the moving average structure is almost fully healed — SMA50 approaching or crossing SMA200 — and the stock has formed a tight VCP (Volatility Contraction Pattern) base just below or at this golden-cross zone. These stocks are compressing energy for the next leg up.

**The mental model:** You are identifying stocks that are transitioning from recovery to a new bull market before the transition is officially confirmed. The risk is highest here because the macro backdrop is weakest, but the reward potential is also highest — these stocks become the first bull-market leaders.

**VCP identification on the chart:** A VCP base looks like a series of contracting price swings with declining volume. Bars become shorter (smaller high-to-low range), and volume dries up. The stock "goes quiet" — this is the compression before the breakout. The Chandelier trail (magenta line) will be very close to price during a true VCP because volatility has contracted.

**The five conditions you must verify:**

**Condition 1 — Near Golden Cross:** The blue SMA50 must be within 5% of the red SMA200, or already above it. If SMA50 = ₹480 and SMA200 = ₹500, the gap is 4% → qualifies. If SMA50 = ₹450 and SMA200 = ₹500, the gap is 10% → does not qualify. A stock far from the golden cross still has too much overhead to clear in the short term.

**Condition 2 — Emerging Trend Structure:** Price above SMA50 AND above SMA150. This ensures the stock is already rebuilding its moving average stack, not just bouncing from the bottom.

**Condition 3 — VCP Tightness:** The most subjective condition to visualise, but on the chart you should see: (a) bars becoming progressively smaller over the last 3–6 weeks, (b) volume clearly declining during this consolidation. The magenta Chandelier line being very close to price is a proxy indicator for this.

**Condition 4 — Pivot Breakout on Volume:** Price closes above the highest high of the last 15 bars, on volume ≥ 1.5× average. Unlike REV-RS (20-day lookback), REV-EARLY uses a 15-day pivot to be slightly more sensitive — the base may be tighter and shorter.

**Condition 5 — Positive RS AND Sector Stage:** Same requirements as REV-RS. The stock must have outperformed during the correction and the sector must not be in Stage 3/4.

**Key question before entering EARLY:** "Is the VCP base clearly visible?" If you cannot see the contraction on the chart — if the last 3 weeks look choppy and wide rather than tight and quiet — the VCP condition may have fired statistically but the setup is not clean. In those cases, wait for a cleaner configuration.

**The timing risk of EARLY setups:** Because the macro backdrop is still in recovery (SMA50 < SMA200 for most stocks), a macro shock can reset all EARLY setups quickly. Size these more conservatively — 0.35–0.40% risk rather than the full 0.50% — especially during early recovery phases.

---

## 4. Position Sizing — The Complete Calculation

Position sizing is the single most important mechanical skill in this strategy. Every trade uses the same formula. You must be able to calculate this in under 60 seconds.

### The Formula

```
Risk Amount (₹)   = Portfolio Capital × Risk %
                  = ₹5,00,000 × 0.50% = ₹2,500

SL Distance (₹)  = Entry Price − Stop Loss Price

Shares (risk-based) = Risk Amount ÷ SL Distance

Shares (cap-based)  = Max Allocation ÷ Entry Price

Final Shares      = MIN(risk-based shares, cap-based shares)
```

### Worked Calculation — REV-CB Example

```
Stock:              SUNPHARMA
Entry Price:        ₹850
Stop Loss Price:    ₹790  (climax zone low − 0.5 × ATR)
SL Distance:        ₹850 − ₹790 = ₹60

Portfolio Capital:  ₹5,00,000
Risk %:             0.50%
Risk Amount:        ₹5,00,000 × 0.0050 = ₹2,500

Risk-based Shares:  ₹2,500 ÷ ₹60 = 41.6 → 41 shares
Cap-based Shares:   ₹25,000 ÷ ₹850 = 29.4 → 29 shares

Final Shares:       MIN(41, 29) = 29 shares  ← cap limit applied

Actual Position:    29 × ₹850 = ₹24,650
Actual Risk:        29 × ₹60 = ₹1,740  (under ₹2,500 — cap-limited)
```

In this example, the Max Allocation cap of ₹25,000 overrides the risk formula. The actual rupee risk is ₹1,740, which is less than the maximum ₹2,500 — this is fine. The cap prevents a single position from becoming disproportionately large.

### Worked Calculation — REV-RS Example

```
Stock:              HCLTECH
Entry Price:        ₹1,580
Stop Loss Price:    ₹1,490  (10-bar low − 0.2 × ATR)
SL Distance:        ₹1,580 − ₹1,490 = ₹90

Risk Amount:        ₹2,500

Risk-based Shares:  ₹2,500 ÷ ₹90 = 27.7 → 27 shares
Cap-based Shares:   ₹25,000 ÷ ₹1,580 = 15.8 → 15 shares

Final Shares:       MIN(27, 15) = 15 shares  ← cap limit applied

Actual Position:    15 × ₹1,580 = ₹23,700
Actual Risk:        15 × ₹90 = ₹1,350
```

### When the Calculation Tells You to Skip

```
Stock:              RELIANCE (high-price stock)
Entry Price:        ₹2,500
Stop Loss Price:    ₹2,380
SL Distance:        ₹120

Risk Amount:        ₹2,500
Risk-based Shares:  ₹2,500 ÷ ₹120 = 20.8 → 20 shares
Cap-based Shares:   ₹25,000 ÷ ₹2,500 = 10 shares

Position Value:     10 × ₹2,500 = ₹25,000  (hits cap)
Actual Risk:        10 × ₹120 = ₹1,200

This is fine. But if the stop were only ₹50 wide:
Cap-based Shares:   10 shares
Risk-based Shares:  ₹2,500 ÷ ₹50 = 50 shares
→ 10 shares is the cap limit
→ Actual risk = 10 × ₹50 = ₹500 (only 0.10% of capital)
→ The trade is valid but undersized due to both the cap and the high price
→ Consider whether the R:R is worth it at 10 shares
```

### Adjusting Risk % for Different Scenarios

| Scenario | Adjustment | Reasoning |
|----------|-----------|-----------|
| Market in deep bear (BEAR regime) | 0.25% | Correlation risk — if macro deteriorates, all positions hit simultaneously |
| EARLY setup in early recovery | 0.35% | Higher risk of macro reset before the trade works |
| Standard RECOVERY regime, strong RFF (5/6) | 0.50% | Full sizing — high-quality setup in target regime |
| CB setup with T1 R-multiple ≥ 3.0 | 0.60% | Optional upsize for exceptional asymmetry (only if capital allows) |

---

## 5. Entry Execution — Order Types, Timing, and Triggers

### The Fundamental Rule: All Signals Fire on Bar Close, Fill on Next Bar Open

The strategy uses `process_orders_on_close=true` in Pine Script. This means:
- **Signal evaluation:** Occurs on the close of the signal bar (after market close, ~3:30 PM IST)
- **Order execution:** Placed before the open of the next trading day (before 9:15 AM IST)
- **Fill price:** The next day's opening price

You are never chasing price intraday. You are acting on last night's closed signal and entering at the next morning's open.

### Step-by-Step Entry Execution

**Evening routine (after 3:30 PM):**

1. Check TradingView. The signal triangle appears on today's bar if conditions were met at close.
2. Note the signal type (CB / RS / EARLY).
3. Read the allocator table for:
   - Qty (shares to buy)
   - Stop Price (where to place your stop)
   - T1 and T2 targets

**Morning routine (before 9:15 AM):**

1. Check if anything has changed overnight (futures price, major news about the stock or sector).
2. If futures suggest the stock will gap up significantly (>3% above last close) on open:
   - For REV-CB: Recalculate — a gap up reduces the R:R. If the gap takes price significantly above the SL, reassess. A 5% gap up on a CB entry with a 7% initial stop means the stop is now proportionally much tighter relative to the entry. Often better to let the gap settle and look for an intraday pullback.
   - For REV-RS/EARLY: A moderate gap up (1–2%) on the breakout day is acceptable and common — it confirms strength. A gap of 5%+ may mean you are chasing. Skip and watch.
3. If no adverse gap, place your market order at open.

### Order Types by Edge

**REV-CB (Swing):**

Use a **market order at open** the day after the signal bar. Do not use limit orders to try to get a better price — you risk missing the bounce entirely if you are too aggressive with your limit. The whole thesis is that the reversal is underway; paying 0.5–1% more at market is acceptable.

Place your stop loss order simultaneously:
- Order type: **Stop-Loss Market Order** (SL-M) at your calculated stop price
- This ensures automatic execution if the stop level is breached

**REV-RS (Positional):**

Acceptable to use either:
- **Market at open** — if the breakout is clearly through resistance with strong pre-market interest
- **Buy-Stop Limit** at the 20-day high + ₹1 (if you want the breakout to continue developing intraday before entering) — more patient approach, may miss some entries

For the stop loss:
- Place SL order at the 10-bar low − ATR × 0.2 level
- This is a wide stop — typically 5–8% for most NSE stocks. Accept this upfront; do not narrow the stop trying to reduce risk. Instead, reduce share count.

**REV-EARLY (Positional):**

Same as REV-RS. Consider using a **Buy-Stop Limit** at the 15-day pivot + ₹1, especially in early recovery when whipsaws are common. The breakout must be real, not just a tick above resistance.

### Gap-Open Adjustments

**Gap DOWN on entry day** (stock opens lower than last close):

- For REV-CB: A small gap down (< 1%) is acceptable. A large gap down (> 2%) means the capitulation may be continuing — wait for the day to develop. If by 10:30 AM the stock is recovering and making intraday higher highs, re-evaluate. If it continues falling, the signal is invalid — do not enter.
- For REV-RS/EARLY: A gap down below the 20-day (or 15-day) breakout level invalidates the breakout. The signal has failed. Do not enter.

**Gap UP on entry day** (stock opens significantly above last close):

- Evaluate by recalculating R:R with the new open as your entry. Open the allocator table, mentally update the entry price, and re-examine whether the T1 R-multiple still makes sense.
- For REV-CB: If the gap takes price 10–15% closer to EMA20, the remaining upside to T1 shrinks. A setup with 3R to EMA20 at yesterday's close but only 1.2R to EMA20 at today's open is no longer worth taking.
- For REV-RS/EARLY: A gap up is generally positive confirmation of the breakout. Accept entries up to 3% above yesterday's close without adjustment. Above 3%, recalculate and decide.

---

## 6. Stop Loss Placement — Every Scenario

Stop loss placement is fixed by the strategy algorithm, but you must understand the logic to place manual stop orders correctly.

### REV-CB Stop Loss

**Formula:** `Climax Zone Low (5-bar low) − 0.5 × ATR14`

**How to find it manually:**
1. Identify the capitulation bar (the pillar 3 bar — large bearish/wide bar with volume spike)
2. Look at the 5 bars ending on or near the capitulation bar
3. Find the lowest low of those 5 bars → this is the "climax zone low"
4. Subtract half of the current ATR14 value

**Example:**
- Capitulation low: ₹792 (lowest of the 5 bars around the climax)
- ATR14: ₹38
- Stop = ₹792 − (0.5 × ₹38) = ₹792 − ₹19 = ₹773

**Why this level?** This stop is below the entire panic zone. If the stock falls through ₹773, the panic selling is not over — the bounce thesis is wrong. The ATR buffer accounts for wick noise at the lows.

**What to do if the stop seems excessively wide (> 10% from entry):**

A 10%+ stop on a REV-CB trade produces a very small position (due to the risk formula). This is the correct response — the position sizing automatically compensates. Do not artificially narrow the stop. Narrowing the stop to ₹10 below the entry is not protecting you — it is guaranteeing you get stopped out by normal intraday noise.

If the stop is wider than 15% from entry and the resulting position is smaller than ₹5,000 in value, the trade is too small to be worth the commission and slippage. Skip it.

### REV-RS and REV-EARLY Stop Loss

**Formula:** `10-bar Low − 0.2 × ATR14`

**How to find it manually:**
1. Find the lowest low of the last 10 trading days (2 calendar weeks)
2. Subtract 20% of the ATR14 value

**Example:**
- 10-bar low: ₹1,465
- ATR14: ₹55
- Stop = ₹1,465 − (0.2 × ₹55) = ₹1,465 − ₹11 = ₹1,454

**Fallback (if 10-bar low is above entry price):**

This rarely happens but can occur in a gap-up breakout scenario. If `10-bar low − ATR×0.2 ≥ entry price`, the strategy uses `entry − ATR × 1.5` as the stop. This gives 1.5 ATR of room below entry as a minimum.

**Example fallback:**
- Entry (breakout): ₹1,620
- 10-bar low: ₹1,630 (higher than entry — gap-up scenario)
- ATR14: ₹55
- Fallback stop = ₹1,620 − (1.5 × ₹55) = ₹1,620 − ₹82.50 = ₹1,537.50

### Never Move a Stop Down

The only direction a stop moves is **up** (in the direction of profit). Once placed, a stop loss level is never lowered to "give the trade more room." This is the single most dangerous mistake a trader can make. If you feel the stop is too tight, the correct action is:
- Reduce position size (already handled by the formula)
- Do not enter the trade if the setup is marginal
- Accept the stop and manage it going forward

---

## 7. Partial Profit Taking — T1 and T2 Rules

The strategy takes partial profits at two levels. This is mandatory — not optional. Partial profits serve three critical functions:
1. They lock in real money on winning trades
2. They unlock the breakeven stop (eliminating downside risk on the remaining position)
3. They provide capital to enter new setups

### T1 Rules — The First Partial (30% of Position)

**REV-CB T1:** Close 30% of position at EMA20 price

The EMA20 is the mean-reversion magnet. When price reaches EMA20 from below, it has fully completed the mean-reversion thesis. At this point:
- 30% of shares are sold at market (or limit order at EMA20)
- The breakeven flag is set → the trailing stop moves to no lower than entry price
- The remaining 70% now has **zero monetary risk** — the worst outcome is breaking even

**REV-RS / REV-EARLY T1:** Close 30% of position at Entry + 2.5R

Where R = Entry − Initial Stop Loss Price.

Example:
- Entry: ₹1,580
- Stop: ₹1,490
- R = ₹90
- T1 = ₹1,580 + (2.5 × ₹90) = ₹1,580 + ₹225 = ₹1,805

When the stock reaches ₹1,805:
- Place a limit sell order for 30% of shares at ₹1,805
- Once filled: the stop ratchets up to no lower than entry price (₹1,580)

**Practical execution of T1:**

The strategy fires `strategy.exit("T1", "Long", qty_percent=30, limit=t1_price)` automatically in the backtest. For **live trading**, you must place this manually:

1. Immediately after entry is confirmed: Calculate T1 price from the allocator table
2. Place a **limit sell order** for 30% of your shares at the T1 price, Good-Till-Cancelled (GTC)
3. This order sits waiting. When price reaches T1, it fills automatically.

**Never cancel the T1 order** because "the stock might go higher." The T1 is not the maximum target — T2 still holds for the remaining 70%. The T1 is a mechanical exit that should execute without emotional intervention.

### T2 Rules — The Second Partial (50% of Remaining = 35% of Original)

T2 only executes after T1 has been hit and the breakeven stop is active.

**REV-CB T2:** Close 50% of remaining position at SMA200 price

The SMA200 is the major institutional moving average. For a stock that was 15–30% below SMA200, reaching SMA200 is a significant recovery milestone. Some stocks stall here; others blast through. By taking 50% of remaining (35% of original position) at SMA200, you:
- Book substantial profit on what was originally the deepest fear purchase
- Leave a 35% runner in place in case the stock continues beyond SMA200

**REV-RS / REV-EARLY T2:** Close 50% of remaining position at 52-Week High (snapped at entry date)

The 52-week high is the key resistance level for recovery stocks. A stock that breaks above its 52-week high is transitioning from recovery into a new bull market phase. This is a natural exit for the recovery thesis — the recovery is complete.

Note: The 52-week high used is the one **snapped at entry** (captured when the trade opened). This prevents the target moving away from you if the broader index makes a new high while you are in the trade.

**Practical execution of T2:**

Same as T1 — place a limit sell order for 50% of remaining shares at the T2 price, GTC, immediately after entry.

### After Both Partials — The Runner (35% of Original)

After T1 and T2 have both fired, you have approximately 35% of your original position remaining. This runner is managed entirely by the trailing stop:
- REV-CB: EMA20 × (1 − 1%) trailing stop
- REV-RS/EARLY: Chandelier Exit ratchet

The runner continues until either the trailing stop is hit or a mandatory exit condition fires (Stage 4, 50MA fail). You do not set a T3 limit for the runner — let it run as far as the trailing stop allows.

### Complete Profit Table

| Event | Shares Closed | Remaining | Monetary Risk |
|-------|--------------|-----------|---------------|
| Entry (100%) | 0 | 100% | Full initial risk |
| T1 hit | 30% | 70% | Zero (breakeven stop active) |
| T2 hit | 35% (50% of 70%) | 35% | Zero (runner) |
| Trail stop hit | 35% | 0% | Zero |

**Numerical example (HCLTECH REV-RS, 15 shares):**

| Event | Price | Shares | Proceeds | Cumulative P&L |
|-------|-------|--------|----------|---------------|
| Entry | ₹1,580 | Buy 15 | −₹23,700 | −₹23,700 |
| T1 (2.5R) | ₹1,805 | Sell 5 | +₹9,025 | −₹14,675 |
| T2 (52W High) | ₹1,920 | Sell 5 | +₹9,600 | −₹5,075 |
| Trail Stop | ₹1,870 | Sell 5 | +₹9,350 | +₹4,275 |
| **Net Profit** | | | | **+₹4,275** |
| **Initial Risk** | | | | ₹1,350 |
| **R-Multiple** | | | | **+3.17R** |

---

## 8. Trailing Stop Management — Bar by Bar

### REV-CB Trailing Stop (EMA20 Trail)

**Before T1:**
- Active stop = Initial SL (climax zone low − 0.5 × ATR)
- This stop does NOT move up yet — it stays at the initial level
- The EMA20 is far above price; the trail mechanism has not activated

**After T1 (EMA20 reached):**
- Active stop = MAX(current cb_sl_live, EMA20 × 0.99)
- The stop ratchets up each day as EMA20 rises
- After T1, stop is ALSO forced to be ≥ entry price (breakeven protection)

**Practical management:**

Check the red stop line on the chart each morning. Your manual stop order should be at or just below this level. As the stop rises, update your stop order with your broker — cancel the old stop and replace with the new level.

**Important:** The EMA20 itself falls during pullbacks. During a pullback after T1, the EMA20 trail stop will be: MAX(yesterday's stop, today's EMA20 × 0.99). If EMA20 dips temporarily, the stop cannot go down — only the MAX of the historical high or current EMA20 × 0.99 is used. This ratchet effect means the stop only ever increases, never decreases.

### REV-RS / REV-EARLY Trailing Stop (Chandelier Exit)

**Before T1:**
- Active stop = Positional SL (10-bar low − 0.2 × ATR)
- Does not change unless Chandelier rises above this level
- Chandelier formula: Highest(High, 22) − ATR14 × 3.5

**After T1:**
- Active stop = MAX(Chandelier ratchet, entry price)
- Stop can never go below entry price once T1 is hit

**Practical management:**

The magenta step-line on the chart is the live Chandelier trailing stop. Your mental model: the stop rises with every new 22-day high the stock makes. In a strong rally, the Chandelier will step up frequently. In a sideways consolidation, it holds steady. If the stock pulls back sharply, the Chandelier remains at its highest ratcheted level — it does not fall back with price.

**The Chandelier multiplier:** In recovery/bear regime, the strategy uses 3.5× ATR (vs 3.0× in a bull market). This means the trail is deliberately wider in recovery conditions — giving the trade more breathing room given the higher volatility environment. Do not attempt to tighten this manually. The wider trail is by design.

---

## 9. Mandatory Exit Rules

These exits are non-negotiable. When these conditions are met, the position is closed regardless of any other consideration.

### REV-CB Mandatory Exits

| Exit | Trigger | Why |
|------|---------|-----|
| **50MA Fail** | Daily close < SMA50 | The bounce has lost its primary structural support. The mean-reversion thesis is invalidated. A stock that cannot hold above SMA50 after a bounce is likely resuming its downtrend. Exit immediately, not "give it another day." |
| **CB Time Stop** | 10 trading days open AND T1 not hit | The bounce has failed to reach the mean-reversion target in a reasonable time. Capital tied up in a stagnant position has an opportunity cost. Exit on bar close when both conditions are met. |
| **Initial SL Hit** | Low ≤ Initial Stop Price | The capitulation low was broken — panic selling has resumed. Exit at the stop price (or market if slippage is severe). |

### REV-RS / REV-EARLY Mandatory Exits

| Exit | Trigger | Why |
|------|---------|-----|
| **Stage 4 Exit** | Weekly Weinstein stage = 4 | The weekly stage machine has confirmed a downtrend at the macro level. This is the highest-conviction sell signal in the Weinstein framework. No other consideration overrides this. Exit next open. |
| **Time Decay Exit** | 40+ trading days open AND unrealised R < 0.5R AND T1 not hit | The stock has absorbed 8 weeks of capital with no meaningful progress toward T1. The thesis has stalled. Exit to free capital for better opportunities. |
| **Chandelier Stop Hit** | Low ≤ Chandelier trailing stop | Standard trailing stop execution. |

### The Psychology of Mandatory Exits

The most dangerous moment in any strategy is when a mandatory exit fires but you tell yourself "just one more day." The mandatory exits exist precisely for situations that feel uncertain. In a recovering market, a stock dropping below SMA50 might look like "just a normal pullback" — but statistically, stocks that close below SMA50 during an attempted recovery bounce have a significantly higher probability of continuing lower. The rule exists because historical patterns support it, not because every single instance will prove correct.

**Mental model for handling exits:** "The strategy has a process. The process fires mandatory exit X. I execute the exit. I do not override the process based on today's news, gut feel, or hope. If the process is wrong in individual cases, it will be right in aggregate. Protecting the aggregate is more important than saving any single trade."

---

## 10. The Complete Trade Lifecycle — Three Worked Examples

### Example A: REV-CB Trade (Swing)

**Stock:** SUNPHARMA  
**Date of Signal:** Tuesday  
**Portfolio Capital:** ₹5,00,000

**Day 0 (Signal Bar — Tuesday close):**

Chart shows:
- Price: ₹842 (closes)
- SMA200: ₹1,020 (stock is 17.4% below SMA200 ✓ — stretch > 15%)
- EMA20: ₹948
- 5-bar low: ₹810
- ATR14: ₹38
- Volume: 4.2× average ✓ — climax volume
- Bar: bearish bar (₹842 close < ₹865 open), wide range ✓
- RSI14: 24 ✓, RSI3: 8 ✓ — washout
- RFF: 4/6 ✓ — PASS
- Regime: RECOVERY ✓

This evening: Pillar 1 (stretch), Pillar 2 (washout), Pillar 3 (climax volume) ALL met. `last_climax_bar` is set to today's bar_index. No entry yet — Pillar 4 (turn) not fired.

**Day 1 (Wednesday — turn bar):**

Price opens at ₹838, rallies through the day, closes at ₹878.
- Close (₹878) > Open (₹838) ✓ — green bar
- Close (₹878) is in the top 70% of the bar's range (₹838–₹890 range of 52, close at 40 above low = 77%) ✓
- Close (₹878) > Yesterday's high (₹868) ✓ — broke prior high

**"CB" triangle appears.** Signal fired.

Evening calculation:
- Climax zone low (5-bar): ₹810
- Stop = ₹810 − (0.5 × ₹38) = ₹810 − ₹19 = **₹791**
- Entry (next day open ≈): ₹878
- SL distance: ₹878 − ₹791 = ₹87
- Risk amount: ₹5,00,000 × 0.50% = ₹2,500
- Shares (risk): ₹2,500 ÷ ₹87 = 28.7 → 28 shares
- Shares (cap): ₹25,000 ÷ ₹878 = 28.5 → 28 shares
- **Final: 28 shares**

Targets:
- T1 = EMA20 = ₹948 → R-multiple = (₹948 − ₹878) / ₹87 = **0.8R** → this is LOW

**Decision point:** T1 R-multiple is 0.8R — below the 1.5R minimum rule. The EMA20 is too close to entry for an acceptable CB setup.

**Action: SKIP this setup.** The rubber band has not been stretched enough, or EMA20 has already declined toward price. The trade does not offer sufficient reward for the risk.

This illustrates a critical principle: the signal fires ≠ the trade is worth taking. Always check T1 R-multiple before acting.

---

**Let us redo with a better scenario:**

**Stock:** SUNPHARMA (deeper correction scenario)  
Price: ₹720 (close), SMA200: ₹1,020 (29.4% below — extreme), EMA20: ₹930

Evening calculation:
- Climax zone low: ₹695
- ATR14: ₹42
- Stop = ₹695 − ₹21 = **₹674**
- Entry ≈ ₹725 (next day open estimate)
- SL distance: ₹725 − ₹674 = ₹51
- Shares (risk): ₹2,500 ÷ ₹51 = 49 → 49 shares
- Shares (cap): ₹25,000 ÷ ₹725 = 34.5 → 34 shares
- **Final: 34 shares**

Targets:
- T1 = EMA20 = ₹930 → R-multiple = (₹930 − ₹725) / ₹51 = **4.0R** → excellent
- T2 = SMA200 = ₹1,020 → R-multiple = (₹1,020 − ₹725) / ₹51 = **5.8R** → outstanding

**Action: ENTER — strong CB setup with excellent R:R.**

**Day 2 (Thursday): Entry**

- Open: ₹728 (slight gap up from ₹725 estimate — acceptable)
- Place market order: Buy 34 shares at ₹728
- Place SL order: SL-M at ₹674
- Place T1 limit sell: 10 shares (30% of 34) at ₹930 GTC
- Place T2 limit sell: 12 shares (50% of remaining 24) at ₹1,020 GTC

Actual entry: ₹728. Actual SL distance: ₹728 − ₹674 = ₹54. Actual risk: 34 × ₹54 = ₹1,836.

**Days 3–7: Trade development**

Stock bounces. Day 5: ₹780 (9.3% above entry, 0.97R unrealised). EMA20 still at ₹930. SL stays at ₹674. No T1 yet.

**Day 8: T1 Hit**

Stock rallies sharply. High of day touches ₹935 (above EMA20 of ₹932).
- T1 order fills: 10 shares sold at ₹930
- Profit on T1 partial: (₹930 − ₹728) × 10 = ₹2,020
- Breakeven flag set: Stop upgrades to entry price ₹728 (cannot go below entry now)
- EMA20 trail activates: Stop = MAX(₹728, ₹932 × 0.99) = MAX(₹728, ₹922.7) = ₹922.7

Remaining: 24 shares. T2 order (12 shares at ₹1,020) still live.

**Days 9–15: Continued rally**

Stock continues to ₹1,010 (17 days after entry). EMA20 has risen to ₹965. Chandelier trail not applicable (CB uses EMA20 trail). Stop = MAX(₹922.7, ₹965 × 0.99) = MAX(₹922.7, ₹955.4) = ₹955.4

**Day 18: T2 Hit**

Stock high touches ₹1,025. T2 order fills: 12 shares at ₹1,020.
- Profit on T2 partial: (₹1,020 − ₹728) × 12 = ₹3,504
- Remaining: 12 shares (runner, all profit)

**Day 22: Trail Stop Hit**

Stock pulls back. Closes at ₹978, low of ₹962 (below trail stop of ₹975 × 0.99 = ₹965 — approximate).
- Runner exits: 12 shares at ₹970 (market fill)
- Profit on runner: (₹970 − ₹728) × 12 = ₹2,904

**Trade Summary:**

| Tranche | Shares | Entry | Exit | P&L |
|---------|--------|-------|------|-----|
| T1 | 10 | ₹728 | ₹930 | +₹2,020 |
| T2 | 12 | ₹728 | ₹1,020 | +₹3,504 |
| Runner | 12 | ₹728 | ₹970 | +₹2,904 |
| **Total** | **34** | | | **+₹8,428** |
| Initial Risk | | | | ₹1,836 |
| **R-Multiple** | | | | **+4.59R** |

---

### Example B: REV-RS Trade (Positional)

**Stock:** HCLTECH  
**Scenario:** IT sector corrected 22% from highs due to global macro fears. HCLTECH fell only 12% — clear RS leader.

**Signal Bar (Monday close):**

- Price: ₹1,583 (closes above 20-day high of ₹1,565)
- Volume: 2.1× average ✓
- SMA50: ₹1,525 (price > SMA50 ✓)
- SMA200: ₹1,682 (SMA50 < SMA200 → recovery state ✓)
- RS vs CNX500: +2.3 ✓ (outperformed during correction)
- 52W High: ₹1,920 (stock is 17.5% below → corrected ≥10% ✓)
- Sector (CNXIT): Stage 1 ✓
- RFF: 5/6 ✓ (PASS — strong fundamentals)
- Regime: RECOVERY ✓
- "RS" triangle appears

**Calculation:**

- 10-bar low: ₹1,480
- ATR14: ₹58
- Stop = ₹1,480 − (0.2 × ₹58) = ₹1,480 − ₹11.6 = **₹1,468**
- Entry ≈ ₹1,590 (next day open estimate)
- SL distance: ₹1,590 − ₹1,468 = ₹122
- Risk amount: ₹2,500
- Shares (risk): ₹2,500 ÷ ₹122 = 20.5 → 20 shares
- Shares (cap): ₹25,000 ÷ ₹1,590 = 15.7 → 15 shares
- **Final: 15 shares**
- Actual risk: 15 × ₹122 = ₹1,830

**Targets:**

- T1 = Entry + 2.5R = ₹1,590 + (2.5 × ₹122) = ₹1,590 + ₹305 = **₹1,895**
- T2 = 52W High snap = **₹1,920**
- R-multiple to T1: 2.5R
- R-multiple to T2: (₹1,920 − ₹1,590) / ₹122 = **2.7R** — note T2 is only slightly above T1 for this stock (52W high is not far above T1). Consider whether T2 is meaningful here.

In this case, T2 is ₹25 above T1, which is a very small additional upside. The real prize is the trailing runner after T2 — if HCLTECH breaks above its 52-week high and re-enters a bull market, the runner position can generate substantial additional profit.

**Day 2 (Tuesday): Entry**

- Open: ₹1,595
- Buy 15 shares at ₹1,595
- SL order at ₹1,468
- T1 limit sell: 5 shares (30% of 15) at ₹1,895 GTC
- T2 limit sell: 5 shares (50% of remaining 10 after T1) at ₹1,920 GTC

**Weeks 1–3: Trade develops**

Stock consolidates between ₹1,560–₹1,640. Chandelier trail at approximately ₹1,440 (well below stop of ₹1,468 at this point). Active stop = max(₹1,468, ₹1,440) = ₹1,468.

Week 3 check: Bars open = 15 days. Unrealised R = (₹1,600 − ₹1,595) / ₹122 = 0.04R. Well below 0.5R. Time decay clock ticking — 40 days until time stop triggers if T1 not hit.

**Week 6: T1 Hit**

HCLTECH rallies to ₹1,900 (close). T1 fills: 5 shares at ₹1,895.
- Profit on T1: (₹1,895 − ₹1,595) × 5 = ₹1,500
- Breakeven flag: Stop upgrades to ≥ ₹1,595 (entry price)
- Chandelier trail now = MAX(ratchet, entry price)

**Week 7: T2 Hit**

Stock gaps up, opens at ₹1,928. T2 limit order fills at ₹1,920.
- Profit on T2: (₹1,920 − ₹1,595) × 5 = ₹1,625

**Weeks 8–14: Runner management**

Remaining 5 shares trail the Chandelier stop. HCLTECH makes a run toward ₹2,100.
- Chandelier stop ratchets up with each new 22-day high
- By week 14, Chandelier is at approximately ₹1,950

**Week 14: Stage 4 Exit** (macro deteriorates)

Weekly stage machine reads Stage 4. Mandatory exit fires.
- Sell 5 shares at next open: ₹1,985
- Profit on runner: (₹1,985 − ₹1,595) × 5 = ₹1,950

**Trade Summary:**

| Tranche | Shares | Entry | Exit | P&L |
|---------|--------|-------|------|-----|
| T1 | 5 | ₹1,595 | ₹1,895 | +₹1,500 |
| T2 | 5 | ₹1,595 | ₹1,920 | +₹1,625 |
| Runner | 5 | ₹1,595 | ₹1,985 | +₹1,950 |
| **Total** | **15** | | | **+₹5,075** |
| Initial Risk | | | | ₹1,830 |
| **R-Multiple** | | | | **+2.77R** |

---

### Example C: REV-EARLY Trade (Positional)

**Stock:** TCS  
**Scenario:** Post-correction. CNX500 has recovered to near SMA200. TCS shows early golden cross approaching.

**Signal Bar:**

- Price: ₹3,820
- SMA50: ₹3,765 (price > SMA50 ✓)
- SMA200: ₹3,870 — gap = (₹3,870 − ₹3,765) / ₹3,870 × 100 = 2.7% → near GC (< 5%) ✓
- SMA150: ₹3,740 (price > SMA150 ✓)
- VCP: bars contracting, volume drying up ✓
- 15-day pivot: ₹3,802 → price close ₹3,820 > ₹3,802 ✓ (pivot break)
- Volume: 1.8× average ✓
- RS vs CNX500: +1.6 ✓
- CNXIT sector: Stage 2 ✓ (sector leading)
- RFF: 5/6 ✓
- Regime: RECOVERY ✓ (TCS is 14% below 52W high of ₹4,450)
- "EARLY" triangle appears

**Calculation:**

- 10-bar low: ₹3,690
- ATR14: ₹95
- Stop = ₹3,690 − (0.2 × ₹95) = ₹3,690 − ₹19 = **₹3,671**
- Entry ≈ ₹3,830
- SL distance: ₹3,830 − ₹3,671 = ₹159
- Shares (risk): ₹2,500 ÷ ₹159 = 15.7 → 15 shares
- Shares (cap): ₹25,000 ÷ ₹3,830 = 6.5 → 6 shares ← cap dominates
- **Final: 6 shares**
- Actual risk: 6 × ₹159 = ₹954 (only 0.19% of capital — high-priced stock naturally limits position)

**Targets:**

- T1 = Entry + 2.5R = ₹3,830 + (2.5 × ₹159) = ₹3,830 + ₹397.50 = **₹4,227**
- T2 = 52W High snap = **₹4,450**
- T1 R-multiple: 2.5R
- T2 R-multiple: (₹4,450 − ₹3,830) / ₹159 = 3.9R

For high-priced stocks like TCS, the Max Allocation cap limits position size significantly. This is by design — it prevents overconcentration in expensive stocks.

**Entry and Orders:**

- Buy 6 shares at ₹3,838 (market open)
- SL at ₹3,671
- T1 sell: 2 shares (30% of 6) at ₹4,227 GTC
- T2 sell: 2 shares (50% of remaining 4) at ₹4,450 GTC

**Outcome:** TCS reaches T1 in week 5, T2 in week 9, runner exits on trail at ₹4,380 in week 12.

Total P&L: (₹4,227−₹3,838)×2 + (₹4,450−₹3,838)×2 + (₹4,380−₹3,838)×2 = ₹778 + ₹1,224 + ₹1,084 = **₹3,086** on a ₹23,028 position. R-multiple: ₹3,086 / ₹954 = **3.23R**.

---

## 11. Daily Trading Routine

### Pre-Market (8:30 AM – 9:15 AM IST)

**Step 1 — Global Check (5 minutes)**

Check Nifty Futures, SGX Nifty, and relevant global indices (Dow, Nasdaq, Asia) for overnight direction. This does not override your strategy rules, but it informs expectation:
- Strong positive global cues: Gap-up likely. Recalculate entries for any pending signals.
- Strong negative cues: Review all open positions. Are any stops close to being hit?

**Step 2 — Open Position Review (10 minutes)**

For each open position:
- Is the active stop still valid? Has the Chandelier moved? (For RS/EARLY positions)
- Is the EMA20 trail still above the stop? (For CB positions)
- Does the expected open threaten any stop prices?
- Has any target (T1/T2) been approached or hit?

Update stop orders at your broker to match the current strategy stop levels if they have moved.

**Step 3 — Pending Signal Execution (5 minutes)**

For any signal that fired yesterday after market close:
- Confirm the signal is still valid (check the chart — triangle still present on yesterday's bar)
- Confirm no overnight news that invalidates the thesis (company-specific disaster, regulatory action)
- Calculate exact position size with today's expected open price
- Prepare the market order, stop order, T1 limit order, T2 limit order

**Step 4 — Order Placement (before 9:15 AM)**

Enter all orders before market open:
1. Entry market order
2. Stop-loss order (SL-M)
3. T1 limit sell order (GTC)
4. T2 limit sell order (GTC)

Do not wait until the market opens and "see how it trades first." By that point, the price may have moved significantly, your orders will be less organised, and emotional decision-making creeps in.

### Market Hours (9:15 AM – 3:30 PM IST)

**Most days: Nothing to do.** The strategy is end-of-day — signals fire on close, execute on open. Your orders are placed. Let them run.

**When to monitor intraday:**
- A stock is approaching a target level (T1 or T2) and you want to confirm the limit order is live
- A major macro event is unfolding (RBI announcement, index-level news) that could cause a flash crash through stops
- A stop loss has been triggered — verify the exit was executed correctly

**What NOT to do intraday:**
- Do not cancel stop orders because the stock is "looking strong"
- Do not move stops down to "give it more room"
- Do not enter on intraday signals — the strategy is daily close based only
- Do not add to a position intraday based on price action (no pyramiding)

### Post-Market (3:30 PM – 5:00 PM IST)

**Step 1 — Check Order Execution (5 minutes)**

Verify all orders placed that morning:
- Entry: Did it fill? At what price? Note actual entry price.
- T1/T2: Did any targets fill today?
- Stop: Did it get hit? Verify the exit was clean.

**Step 2 — Scan for New Signals (15–20 minutes)**

Load each stock on your watchlist onto the daily chart. Look for:
- CB triangle (red) — note the stock and calculate sizing for tomorrow
- RS triangle (lime) — note and calculate
- EARLY triangle (yellow) — note and calculate

**Priority order for new signals if portfolio heat is at maximum (4 positions):**
1. Close any position that is showing a mandatory exit condition → creates a slot
2. If no mandatory exits, check if any existing position has reached T1 → breakeven → potentially add the freed capital to a higher-quality new signal

**Step 3 — Journal Update (5 minutes)**

Log any trades that opened, closed, or hit targets today. See Section 18 for the journal format.

---

## 12. Weekly Review Routine

Every weekend (Saturday), perform a structured review. This is the most important learning loop in the system.

### Section 1: Performance Review (30 minutes)

For each trade closed during the week:

1. **Was the signal clean?** Review the chart from the signal bar. Did the four pillars / five conditions clearly align, or was it borderline?
2. **Did you execute correctly?** Compare intended entry/stop/target with actual execution. Any slippage? Any missed orders?
3. **Did mandatory exits fire as expected?** If a 50MA Fail or Stage 4 exit fired, was it actually the right call in hindsight? (Hindsight analysis only — do not second-guess future rule-following based on one outcome.)
4. **R-multiple achieved:** Record in journal. Compare to expected (2.5R for T1, 3–6R for full trade).

### Section 2: Open Position Review (20 minutes)

For each open position:

1. Check current stage background on the chart. Any deterioration toward Stage 3 or 4?
2. Is the stock still above the relevant structure? (SMA50 for CB, weekly MA for RS/EARLY)
3. How many days/weeks has the position been open? Time decay check.
4. Has the Chandelier trail moved significantly this week? Update your records.

### Section 3: Market Regime Update (10 minutes)

Load CNX500 daily chart:
1. Is SMA50 still below SMA200? If it has crossed above: update regime to TRANSITION or BULL.
2. If crossed: begin reducing CB positions, preparing to shift primary tool to v4.51.
3. How many stocks on your watchlist now have their SMA50 crossing above SMA200? If >30%, the recovery is maturing.

### Section 4: Watchlist Curation (20 minutes)

- Remove stocks from watchlist that have fundamentally deteriorated (earnings collapse, RFF score fallen to 1/6)
- Add new candidates that have recently corrected ≥10% and have RFF ≥ 3/6
- Note any stocks approaching conditions: capitulation zones, RS breakout levels, near golden cross levels

### Section 5: Configuration Adjustment (10 minutes)

Based on the regime update, consider whether any settings need adjustment:
- If recovery is maturing → begin raising `Min Correction from 52W High %` (fewer CB setups, focus on RS/EARLY)
- If correction re-accelerated → reduce risk to 0.25%, max 2 positions
- If sector rotation is visible → verify sector stage settings are correct

---

## 13. Portfolio Heat Management — Running Multiple Positions

### The 4-Position Architecture

With 4 positions at 0.50% risk each, you are risking 2.0% of total capital simultaneously. This is the maximum "heat" the strategy carries. Here is how to manage it as a portfolio:

### Correlation Risk

The biggest danger in recovery trading is buying 4 positions in the same sector during what appears to be a sector recovery. If that sector gets hit by specific news (e.g., IT sector regulation announcement, pharma FDA import alert), all 4 positions can hit stops on the same day.

**Anti-correlation rules:**
- Maximum 2 positions in the same sector simultaneously
- Attempt to mix CB swing positions with RS/EARLY positional positions — they have different hold periods and respond to different catalysts
- Avoid having all 4 positions in highly-correlated sectors (e.g., 2 IT stocks + 1 IT-adjacent ITES stock + 1 tech platform = effectively 4 correlated IT positions)

**Ideal portfolio composition example:**
| Position | Edge | Sector | Hold Type |
|----------|------|--------|-----------|
| SUNPHARMA | REV-CB | Pharma | Swing (1–3 wks) |
| HCLTECH | REV-RS | IT | Positional (4–12 wks) |
| TATASTEEL | REV-CB | Metal | Swing (1–3 wks) |
| ICICIBANK | REV-RS | Banking | Positional (4–12 wks) |

Two swing + two positional across four different sectors — maximum diversification within the 4-position limit.

### Opening New Positions

**Before adding a 5th position (if you are tempted):**

The strategy hard-limits to 4 (via `max_open_positions`). There is no override for "this is a really great setup." The limit is architectural, not conservative estimation. If you want to add a 5th position:
- Close the weakest existing position (most stagnant, furthest from T1, most correlation with the new one) to free the slot
- Never exceed 4 positions

**When to prioritise a new signal over an existing stagnant position:**

If a new REV-RS signal appears and you already have 4 positions, but one of those positions is on Day 38 of a 40-day time decay stop with only 0.2R of unrealised profit — close that position proactively and use the freed slot for the new signal. The new signal offers better timing and momentum than a stagnant position that is about to exit anyway.

### Tracking Portfolio Heat in Real Time

Keep a simple spreadsheet:

| Stock | Edge | Entry | Stop | Shares | ₹ Risk | % Risk | Days Open | T1 Hit? |
|-------|------|-------|------|--------|--------|--------|-----------|---------|
| SUNPHARMA | CB | ₹728 | ₹674 | 34 | ₹1,836 | 0.37% | 8 | No |
| HCLTECH | RS | ₹1,595 | ₹1,468 | 15 | ₹1,830 | 0.37% | 22 | No |
| ICICIBANK | RS | ₹1,100 | ₹1,040 | 20 | ₹1,200 | 0.24% | 5 | No |
| **Total** | | | | | **₹4,866** | **0.97%** | | |

Update this spreadsheet daily. The "% Risk" column tells you your total portfolio heat at any moment.

---

## 14. The Fundamental Filter (RFF) — How to Verify Manually

The strategy calculates RFF automatically via `request.financial()` in TradingView. However, TradingView's financial data can be delayed or incorrect for some NSE stocks. Always verify manually for any trade larger than ₹15,000.

### Where to Find the Data

**TradingView:** Click the stock name → Financials tab → Income Statement / Balance Sheet / Cash Flow. Select TTM or Annual as relevant.

**NSE website (nseindia.com):** Company filings section — quarterly results, annual reports.

**Screener.in:** Very clean interface for all 6 RFF metrics for NSE stocks. Most reliable source.

### RFF Verification Checklist

| # | Metric | Where to Find | Pass Condition | Common Issues |
|---|--------|--------------|----------------|---------------|
| 1 | **Net Income (TTM)** | P&L statement, last 4 quarters summed | > 0 | Check for one-time exceptional gains — if NI is positive only due to an asset sale, the operating business may still be loss-making |
| 2 | **Free Cash Flow (TTM)** | Cash Flow statement: OCF − Capex | > 0 | Some capital-intensive sectors (infra, metals) have high capex that consistently drags FCF negative — context matters |
| 3 | **Interest Coverage** | EBITDA ÷ Interest Expense | > 2.0× | Banks and NBFCs do not have "interest expense" in the traditional sense — use Net Interest Margin instead for financials |
| 4 | **Debt/Equity** | Total Debt ÷ Total Equity (latest annual) | < 2.0 | For capital-intensive industries (real estate, infrastructure), D/E of 2–3 may be normal — sector context required |
| 5 | **Current Ratio** | Current Assets ÷ Current Liabilities (latest quarter) | > 1.0 | Watch for seasonal fluctuations — some businesses have legitimate CR < 1 at quarter-end due to timing |
| 6 | **ROA** | Net Income ÷ Total Assets × 100 | > 5% | Asset-light businesses (software, financials) typically have ROA 10–30%; asset-heavy (steel, cement) may show 3–8% even when healthy |

### Sector-Specific RFF Interpretation

**Banking/NBFC stocks:**
- Ignore Interest Coverage (D/E of ICR) — these are banks; debt is their operating material
- Use Net NPA < 2% as a substitute for financial health
- Focus on: Net Profit > 0 (C1), ROA > 1.2% for banks (substitute for 5% general threshold for C6), Current Ratio > 1.0 (C5)

**Infrastructure/Real Estate:**
- D/E > 2.0 is common and acceptable if Interest Coverage is strong
- FCF may be negative due to large project capex — check if OCF is positive separately
- Focus on: Net Income (C1), ICR > 1.5 (slightly relaxed), CR > 1.0 (C5)

**Manufacturing/Metals:**
- Cyclical sectors may show negative NI at the bottom of cycles — this is exactly when you want to buy them
- If the last quarter shows a return to profitability, consider raising your RFF minimum by 1 to compensate for the recent historical losses

---

## 15. Edge-Specific Trading Rules Summary

A quick-reference card for each edge.

### REV-CB Rules

| Rule | Detail |
|------|--------|
| **Minimum T1 R-multiple** | Skip if T1 (EMA20) is less than 1.5R from entry |
| **Maximum stop width** | If stop > 15% below entry → position too small → skip |
| **50MA Fail: mandatory exit** | No exceptions. Close immediately on close below SMA50. |
| **Time stop** | 10 trading days. If T1 not hit → exit. No extensions. |
| **Stage allowed** | Stage 1, 2, or 4 — CB can occur in any stage |
| **Do not enter** | If EMA20 is below entry price (common in recovering markets — unusual but check) |
| **Do not enter** | If RFF shows red background (FAIL) |
| **Do not enter** | If the last climax bar is more than 5 bars ago (window expired) |

### REV-RS Rules

| Rule | Detail |
|------|--------|
| **Mandatory positive RS** | If RS vs CNX500 is negative → skip. No exceptions. |
| **Recovery state required** | SMA50 MUST be below SMA200 (close > SMA50 AND SMA50 < SMA200) |
| **Breakout quality** | If close is only 0.1–0.3% above 20-day high with average volume → wait for next day confirmation |
| **Stage 4 exit: mandatory** | No exceptions. Close at next open when weekly stage = 4. |
| **Time decay: firm** | 8 weeks. If T1 not reached and unrealised < 0.5R → exit. No extensions. |
| **Do not enter** | If sector is Stage 3 or Stage 4 |
| **Do not enter** | If stock correction < 10% from 52W high (regime gate not met) |
| **Do not enter** | If 4 positions already open |

### REV-EARLY Rules

| Rule | Detail |
|------|--------|
| **Near GC required** | SMA50 must be within 5% of SMA200 (below or above) |
| **VCP must be visible** | If the last 3–4 weeks look choppy/wide, not quiet/tight → skip even if algorithm fires |
| **Higher risk of failure** | Size at 0.35–0.40% risk in early recovery phases |
| **Same exits as REV-RS** | Stage 4 exit, time decay stop, Chandelier trail — identical rules |
| **Do not enter** | If sector is Stage 3 or Stage 4 |
| **Do not enter** | If RS vs CNX500 is negative |

---

## 16. What the Chart is Telling You — Reading Every Visual

When you open any NSE chart with this strategy loaded, here is what to read in sequence:

### Reading Sequence (30 seconds per chart during scanning)

**1. Background colour (first look):**
- Green → Stage 2 uptrend. Good for RS/EARLY entries.
- Yellow → Stage 1 basing. Good for CB entries and watching for RS/EARLY.
- Orange → Stage 3 topping. Caution — exits likely imminent.
- Red → Stage 4 downtrend. No new entries. Existing positions should exit on Stage 4 trigger.

**2. Chart tint (RFF status):**
- Faint green wash → RFF PASS. Fundamentals OK. Trading allowed.
- Faint red wash → RFF FAIL. Fundamentals insufficient. Do NOT enter regardless of technical signal.
- No tint → RFF filter is disabled (rff_min_score = 0) — should only be in backtesting.

**3. Moving averages (price relationship):**
- Price well below all three lines (EMA20 orange, SMA50 blue, SMA200 red) → Deep correction territory. CB setups possible.
- Price above blue (SMA50) but blue below red (SMA200) → Recovery state. RS setups possible.
- Blue line approaching red line → Near golden cross. EARLY setups possible.
- Price above all three AND blue above red → Bull market state. Switch to v4.51.

**4. Magenta step-line (Chandelier Trail):**
- Close to price → Low volatility, VCP-like compression. Favourable for EARLY breakouts.
- Far below price → Wide trail from recent high. Normal positional trail in a recovering stock.
- ABOVE price → The stock has closed below its Chandelier stop. If in a trade, this means the exit fired.

**5. Solid red line (Active Stop — only visible when in a trade):**
- This is your live stop loss level at the current bar.
- Should match your broker stop order exactly.
- If the red line has moved up since you last checked, your stop order needs to be updated.

**6. Signal triangles:**
- Red triangle "CB" → CB entry condition met at this bar's close.
- Lime triangle "RS" → RS entry condition met.
- Yellow triangle "EARLY" → EARLY entry condition met.
- Multiple triangles on the same bar → Priority: CB > RS > EARLY. The strategy takes the first valid one.

---

## 17. Pre-Trade Checklist

Use this checklist before entering every trade. It takes 2–3 minutes but prevents the most common execution mistakes.

### Gate 1: Regime ✓

- [ ] Regime table row shows RECOVERY or BULL (not BEAR)
- [ ] If BULL: Stock correction depth ≥ 10% from 52W high (confirmed in allocator table)

### Gate 2: Fundamental Quality ✓

- [ ] RFF background is green (faint) — not red
- [ ] Allocator table "RFF: X/6 [PASS]" confirmed
- [ ] Manually verified 2 key metrics: Net Income > 0 AND FCF > 0 (on Screener.in)

### Gate 3: Technical Signal ✓

**For REV-CB:**
- [ ] Signal bar (CB triangle) appeared on yesterday's close
- [ ] Background was NOT red (Stage 4) on signal bar
- [ ] T1 R-multiple ≥ 1.5R (visible in allocator table "T1 CB" row)
- [ ] EMA20 is meaningfully above current price (visible on chart)
- [ ] SMA200 is visible and above EMA20 (viable T2 path)
- [ ] Signal bar is within 5 bars of today (not a stale signal from 2 weeks ago)

**For REV-RS:**
- [ ] RS vs CNX500 is positive (allocator table bottom row)
- [ ] Stage background is yellow or green (not red)
- [ ] SMA50 (blue) is below SMA200 (red) on chart
- [ ] Price is above SMA50 (blue) on chart
- [ ] Breakout was clear — price visibly above horizontal resistance on the signal bar
- [ ] Volume on signal bar was elevated (tower above adjacent bars visible in volume panel)
- [ ] Sector check: loaded sector index — Stage 1 or 2 background (not red)

**For REV-EARLY:**
- [ ] SMA50 is visibly close to SMA200 on chart (lines nearly merged)
- [ ] VCP pattern visible: last 3–4 weeks show contracting bars and drying volume
- [ ] RS vs CNX500 is positive
- [ ] Sector Stage 1 or 2 confirmed

### Gate 4: Position Sizing ✓

- [ ] Entry price noted
- [ ] Stop price calculated and noted
- [ ] SL distance calculated: Entry − Stop
- [ ] Shares calculated: min(₹2,500 ÷ SL distance, ₹25,000 ÷ Entry)
- [ ] Actual rupee risk confirmed ≤ ₹2,500
- [ ] Allocator table "Qty" matches your manual calculation (within 1–2 shares — rounding differences acceptable)

### Gate 5: Portfolio Heat ✓

- [ ] Current open positions: ___ (must be ≤ 3 to open a new one)
- [ ] Sector of new trade: ___ — not duplicating an existing sector (max 2 per sector)
- [ ] Running total portfolio risk after new trade: ___% (must be ≤ 2.0%)

### Gate 6: Order Preparation ✓

- [ ] Entry order type determined (market / buy-stop limit)
- [ ] T1 price noted: ₹___
- [ ] T2 price noted: ₹___
- [ ] T1 partial quantity calculated: 30% of total shares = ___ shares
- [ ] T2 partial quantity calculated: 50% of (70% of total shares) = ___ shares

---

## 18. Trade Journal Template

Complete this for every trade, immediately after entry and updated on each significant event.

---

**TRADE RECORD**

**Date Opened:** _______________  
**Stock:** _______________  
**Edge:** REV-CB / REV-RS / REV-EARLY (circle one)  
**Signal Bar Date:** _______________

**ENTRY DETAILS**

| Field | Planned | Actual |
|-------|---------|--------|
| Entry Price | ₹___ | ₹___ |
| Stop Price | ₹___ | ₹___ |
| SL Distance | ₹___ | ₹___ |
| Shares | ___ | ___ |
| Position Value | ₹___ | ₹___ |
| ₹ Risk | ₹___ | ₹___ |
| % Risk | ___% | ___% |
| T1 Target | ₹___ | — |
| T2 Target | ₹___ | — |

**SETUP QUALITY NOTES** (written before entry — your reasons for taking the trade)

```
Regime: ___________
Stage: ___________
RFF Score: ___/6
RS vs CNX500: ___
Key strength of this setup:
________________________________________
Any concerns / borderline conditions:
________________________________________
```

**TRADE EVENTS LOG**

| Date | Event | Price | Shares | Cumulative P&L |
|------|-------|-------|--------|---------------|
| | Entry | | | |
| | T1 Hit (if applicable) | | | |
| | T2 Hit (if applicable) | | | |
| | Exit | | | |

**EXIT DETAILS**

| Field | Value |
|-------|-------|
| Exit Type | T1/T2/StopLoss/50MAFail/Stage4/TimeDecay/CBTimeStop |
| Date Closed | |
| Final P&L (₹) | ₹___ |
| R-Multiple | ___R |
| Days Held | ___ |

**POST-TRADE REVIEW** (written after exit)

```
What worked:
________________________________________

What could be improved:
________________________________________

Was the signal clear or borderline?
________________________________________

Did I follow the rules exactly? (Y/N)
If N — what did I deviate from and why?
________________________________________

Would I take this same trade again?
________________________________________
```

---

**MONTHLY SUMMARY** (complete at end of each month)

| Metric | Value |
|--------|-------|
| Trades opened | ___ |
| Trades closed | ___ |
| Win rate | ___% |
| Average winner (R) | ___R |
| Average loser (R) | ___R |
| Profit factor | ___ |
| Best trade | ___ / ___R |
| Worst trade | ___ / ___R |
| Exits by type: Stop/T1/T2/TimeDecay/Stage4/50MA | ___ / ___ / ___ / ___ / ___ / ___ |
| Most common setup quality issue | ___ |

---

## 19. Scenario Decision Guide — "What Do I Do When..."

### "The stock gapped up 5% above my planned entry level on the signal day"

For REV-CB: Recalculate T1 R-multiple with the new entry. If EMA20 is now only 1.0R away, skip the trade — the asymmetry is gone. If still ≥ 1.5R, enter at market.

For REV-RS/EARLY: Calculate R-multiple to T1 (2.5R target fixed, so R-multiple = 2.5 always). The gap just means you are entering with a tighter stop relative to the gap distance. Accept if the setup is clean. The primary concern is whether the stop (10-bar low) is still valid — a 5% gap up means your stop is now proportionally much further below. If stop distance is > 12%, the position size will be very small. Consider skipping.

### "My stop was hit but the stock immediately reversed and is now above entry"

Do not re-enter the same stock on the same day. The stop was hit because the price structure that defined the stop was broken. The reversal may be real or it may be a trap. Wait at minimum 3–5 trading days. If the stock sets up cleanly again — forms a new base, shows the appropriate signal — it can be re-entered as a fresh trade with a fresh stop calculation.

### "I missed the entry — the stock already moved 8% above the signal bar"

For REV-CB: If the stock has already moved 8% above the signal bar, the T1 R-multiple is now marginal at best. Skip.

For REV-RS/EARLY: A breakout that has already run 8% before you could enter is typically too extended. The position sizing will be punishing (stop is still at the 10-bar low, but entry is now 8% higher → smaller position, worse R:R). Wait and watch. Sometimes these stocks pull back to the breakout level and re-test — that becomes a clean second-chance entry.

### "The stock is showing Stage 3 on the chart but I still have 2 weeks of time stop remaining"

Do NOT wait for the time stop to fire if Stage 3 is showing on the weekly chart. Stage 3 (orange background) is a warning that the uptrend is weakening. Proactively tighten the stop to breakeven (or recent swing low), and plan to exit on the first sign of confirmation of Stage 4. The time stop is a backstop, not a mandatory holding period.

### "Two signals fired on the same day and I am at maximum 4 positions"

Rank them:
1. Fundamental quality: higher RFF score wins
2. R-multiple to T1: higher R-multiple wins
3. RS strength: higher positive RS wins

Choose the highest-ranked signal. Let the other one go. There will always be more signals.

### "The allocator table shows FAIL for RFF but the technicals look perfect"

Do not trade. The RFF filter exists to prevent buying value traps — stocks that are cheap because the business is genuinely deteriorating. A perfect technical setup on a fundamentally impaired company is a trap. The technical setup in a recovery market often forms because institutions are distributing (selling into retail buying) before the fundamental deterioration becomes visible. The RFF FAIL is your early warning system. Trust it.

### "My REV-CB position has been open for 9 days and T1 (EMA20) is still 12% away"

The time stop fires at 10 days if T1 is not hit. You have 1 day left. Do not extend the stop — let it fire on Day 10. The position has failed to generate momentum in 10 days. The 12% remaining distance to EMA20 will not be covered in a day without exceptional circumstances. Exit cleanly and free the capital.

### "All 4 positions are profitable and a new high-quality signal appeared"

You cannot take the 5th position — the maximum is 4. Document the signal in your journal for reference. Note whether it subsequently worked. Over time, track "signals missed due to full portfolio" — if you are consistently missing great setups because you are full, that is a signal to review whether one of your current 4 positions is worth holding (especially those that are stagnant).

### "The market has suddenly crashed 4% on a global macro shock — all 4 positions are close to their stops"

Do nothing differently. Your stops are your stops. If they are hit, they are hit. This is what the 2% total portfolio heat limit is for — even if all 4 stop out simultaneously, you lose 2% of capital in a single day. That is a bad day, not a catastrophe. Do not try to proactively exit all positions before stops are hit — you might save 20% on one trade but miss a recovery on two others.

The only exception: if a position is at Stage 4 AND the stock has broken below SMA50 AND the macro shock is clearly sector-specific and severe — consider a proactive exit at the next bar's open to avoid gap-risk slippage through the stop on the following day.

---

## 20. Transitioning Back to the Bull Market Strategy

The Recovery Strategy is a temporary tool for a specific market condition. You must recognise when that condition has ended and transition back to `Weinstein_Minervini_Strategy v4.51`.

### The Transition Signal

The primary transition indicator is the **CNX500 Golden Cross**: SMA50 crosses above SMA200.

When this occurs:
1. The "Regime" row in the allocator table changes from RECOVERY to BULL
2. The `active_risk_pct` in the strategy automatically reduces by 0.10% (mild self-adjustment)
3. REV-CB signals become increasingly rare (stocks near 52W highs no longer qualify as "corrected")
4. REV-EARLY signals become increasingly common (more stocks crossing their golden cross)

### Transition Protocol

**Week of Golden Cross:**
1. Do not immediately close all positions — let them continue under their existing exit rules
2. Stop taking new REV-CB entries (the correction is over; mean-reversion thesis has weaker edge now)
3. Begin reviewing your watchlist for Stage 2 breakouts using the v4.51 criteria
4. Add `Weinstein_Minervini_Strategy v4.51` back to your chart alongside Recovery v1.0

**Two Weeks After Golden Cross:**
1. Close any REV-CB positions not yet at T1 (the swing trade thesis is weakened in a bull regime)
2. Continue managing REV-RS and REV-EARLY positions under their existing exit rules — these naturally graduate into bull-market setups
3. Begin taking new entries exclusively from v4.51

**One Month After Golden Cross:**
1. Recovery v1.0 can remain active with max_open_positions = 1–2 as a background scanner for late-recovering laggards
2. Primary trading capital shifts fully to v4.51
3. Update portfolio capital in v4.51 settings to full allocation

### False Recovery / Double Correction

Sometimes the market appears to recover (CNX500 crosses above SMA200 briefly) and then pulls back again — a "failed golden cross" or "double dip." Signs of this:
- SMA50 crosses above SMA200 but reverses within 2–3 weeks
- CNX500 fails to make new highs above the previous recovery peak
- REV-CB setups start reappearing at lower prices

If a failed golden cross occurs:
1. Reactivate Recovery v1.0 fully
2. Proactively close any v4.51 positions that have not yet reached T1 (the bull market has not confirmed)
3. Reduce position sizes to 0.25% risk until the regime clarifies

---

*Trading Manual version: 1.0*  
*Strategy file: Weinstein_Recovery_Strategy v1.0.pine*  
*Last updated: April 2026*  
*This manual should be reviewed and updated when the strategy is modified.*
