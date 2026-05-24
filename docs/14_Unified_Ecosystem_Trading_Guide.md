# Weinstein Unified Ecosystem [v3.4] — Trading Guide

**Script:** `Weinstein_Unified_Ecosystem_v3.4.pine`
**Companion to:** `13_Unified_Ecosystem_User_Guide.md`

---

## What's New in v2.6 → v3.4 — Decision-Mode Architecture

The v2.6+ line aligns this Strategy with the Dashboard's `v67.3.x` cross-tool architecture. **Trading workflow is unchanged** — the same 9 catalysts, same 4-pillar capitulation logic, same RFF fundamental gate. What changed is the on-chart panel: less duplicated info, denser composite cells, cross-references to the canonical tools.

### Practical impact on the trader

1. **Open the Dashboard alongside.** This Strategy no longer duplicates Stage / RS / Trend / PA / Vol — read them on the Dashboard. The Strategy's panel now focuses on what only it can tell you: which catalysts are firing, what's blocking them, and the cross-engine verdict.
2. **Use the right tool for the right question:**
   - "Should I be looking at this stock?" → **Dashboard** (Action Signal · Recommendation · Stage 2 Age)
   - "Why isn't a bull catalyst firing?" → **Bull Screener** (9 POS-BO gates with first-blocking-gate detail)
   - "Is this a capitulation setup?" → **Recovery Screener** (4 CB pillars + RSI(3) FEAR + 60-bar DD)
   - "Cross-engine consensus?" → **Unified Ecosystem** (this Strategy — catalyst diagnostic panel below the main panel)
3. **Catalyst-firing logic is unchanged.** Backtest results from v2.3+ remain valid. The architectural refactor is display-only.

### What the new panel shows

After v3.4 the on-chart panel renders ~14 rows in two zones, plus a stacked 4-column CATALYST DIAG section below:

```
🌿 BULL MARKET STRATEGY                   (header)
BULL SETUP             | ✓ BASE · Py 60/100
Positional Signals     | POS-BO ●  POS-AC ●            ← 🟢 FIRE / 🟡 HOLD / 🔵 ACTIVE / ⚫ WAIT
Swing Signals          | SWG-PB ●  SWG-BO ●  SWG-REV ●  GAP ●

🔄 RECOVERY MARKET STRATEGY               (header)
REC STATE              | Regime: OFF · RFF: 3/6✓
Recovery Signals       | REV-CB ●  REV-RS ●  REV-EAR ●

◈ CATALYST DIAG  (catalyst · ✓ FIRE / ✗ first-blocking-gate [hits])   (full-width)
── 🌿 BULL ──
POS-BO    | ✗ mkt_bull [0]      | POS-ACCUM   | ✗ mkt_bull [0]
SWG-PB    | ✗ mkt_bull [4]      | SWG-BO      | ✗ mkt_bull [0]
SWG-REV   | ✗ rev struct [0]    | SWG-GAP     | ✗ mkt_bull [0]
── 🔄 RECOVERY ──
REV-CB    | ✗ no climax [0]     | REV-RS      | ✗ RS slope ≤0 [0]
REV-EARLY | ✗ no HL+trend up [0]|             |
── 🛈 META ──
Sector Ticker     | NSE:CNX500 [AUTO] (S4) | WCL Gate | OFF
Base Confirm Path | WEINSTEIN (WStg:11w)   |          |

→ See Other Tools:  Dashboard (RS/Stage/PA)  ·  Bull Screener (Gates/Levels)  ·  Recovery Screener (Pillars/RFF)
```

### Why the diag panel is the headline value

Every catalyst row shows **the first failing gate** — the specific reason a setup isn't firing. This collapses what used to be "stare at 30 rows and figure out which constraint is binding" into "read one cell." When a stock looks promising on the Dashboard but the Strategy isn't firing, the diag panel tells you instantly which gate to fix (or accept).

---

## Inherited from v2.3 (still active — backtest-locked thresholds)

> **Hunter / POS-ACCUM trigger gates (locked 10 May 2026):**
>
> | Trigger | Added gate (v2.3) |
> |---|---|
> | `pos_bo_trigger` | + **wRSI ≥ 60** + **adx_val ≥ 25** |
> | `pos_ac_trigger` | + **d_rsi ≤ 50** |
>
> Practical impact:
> - **POS-BO** fires only when weekly RSI shows real momentum (≥60) AND daily ADX confirms a trending move (≥25). This is the v1 FINAL Hunter scan ported into the strategy.
> - **POS-AC** refuses to fire on stocks with already-elevated daily RSI (>50). Reason: late-stage POS-ACCUM at high RSI is a documented chase trap (HCLTECH-style failure, see `BACKTEST_RESULTS_v2.docx` §6).
> - All three thresholds are exposed as `input.int` and can be tuned per chart, but defaults match the locked Python pipeline. **Do not change without re-running the backtest.**

---

## 1. Ecosystem Architecture — The 9 Edges

The script routes each trade into one of 9 named **edges** (catalysts). Each edge has its own entry logic, stop-loss type, trail method, and profit-taking rules.

```
BULL MARKET STRATEGY (6 Edges)
├── POSITIONAL GROUP
│   ├── POS-BO   — Positional Breakout (Stage 2 momentum breakout)
│   └── POS-AC   — Positional Accumulation (OBV-gated base entry)
└── SWING GROUP
    ├── SWG-PB   — Swing Pullback (EMA20 bounce, VCP-tight)
    ├── SWG-BO   — Swing Breakout (VCP pattern breakout)
    ├── SWG-REV  — Swing Reversion (SMA200 mean-reversion)
    └── GAP-GO   — Gap & Go (institutional gap held into close)

RECOVERY MARKET STRATEGY (3 Edges)
├── REV-CB    — Climax Bottom (panic washout reversal)
├── REV-RS    — RS Survivor (corrected market, RS-positive breakout)
└── REV-EARLY — Early Bird (trendline reclaim + compressed base)
```

---

## 2. Prerequisites — Market Conditions Required Per Edge

Before any edge fires, a **hierarchy of filters** must pass from top to bottom.

### 2.1 Universal Pre-Checks (All Edges)
| Check | Requirement |
|---|---|
| Date Filter | Bar must be within the configured backtest window (if enabled) |
| Max Open Positions | `strategy.opentrades < max_open_positions` |
| No Existing Position | `strategy.position_size == 0` |
| Fundamental Filter (RFF) | Score ≥ min_rff_score (recovery edges only; bull edges bypass) |

### 2.2 Bull Strategy Prerequisites
| Check | Requirement |
|---|---|
| Market Health | CNX500 close > SMA200 AND SMA50 > SMA200 |
| Weinstein Stage (Weekly) | Stage 2 (or Early Stage 2 for POS edges) |
| Base Confirmed | Stage 2 + Market Bull + MPA Pass (close > SMA150 > SMA200) |
| Alpha Score | ≥ Min Alpha Score (default 50) |
| RS Quadrant | LEADING or IMPROVING (if Require Positive RS is ON) |
| Micro Edge | Close > Daily CPR Pivot AND Close > Monthly VWAP (if enabled) |

### 2.3 Recovery Strategy Prerequisites
| Check | Requirement |
|---|---|
| Regime Gate | Market corrected ≥7% from 52W high OR stock corrected 10%–40% |
| Sector Stage | Sector ETF must be in Stage 1 or Stage 2 (REV-RS and REV-EARLY only) |
| RS Positive | RS slope > 0 (REV-RS and REV-EARLY only) |
| RFF Score | ≥ configured minimum (default 3/6) |

---

## 3. The 6 Bull Market Edges — Entry Criteria

### 3.1 POS-BO — Positional Breakout

**Concept:** Price breaks above the N-bar (default 20) resistance high in a confirmed Stage 2 uptrend on above-average volume. The cleanest institutional signal — stock is escaping a base into open air.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. POS-BO Edge Toggle: ON
3. Base Confirmed: Stage 2 + Market Bull + MPA Pass
4. Alpha Score ≥ Min Alpha
5. RS Quadrant: LEADING or IMPROVING
6. Micro Edge: Close > CPR + Monthly VWAP
7. Close (or High, if Intraday mode) > 20-bar High (prior bar)
8. Volume > 1.5× 50-bar average
9. **VWMA20 > VWMA50** (volume shelf gate — rules out false spikes)

**Stop Loss:** 10-bar structural low − 0.2× ATR14

**Position Size:** Kelly-adjusted, capped at Max Allocation
- Full Kelly (1.25×): Stage 2 + RS Positive + Volume > 50-bar SMA
- Half Kelly (0.75×): Fewer conditions met

**Dashboard Signal State:** POS-BO turns 🟢 on the trigger bar

---

### 3.2 POS-AC — Positional Accumulation

**Concept:** Buy during the base-building phase itself — before the breakout — when OBV confirms smart money is quietly accumulating. Lower risk entry than POS-BO but requires the stock to be in a tightening VCP-like structure.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. POS-AC Edge Toggle: ON
3. Base Confirmed: Stage 2 + Market Bull + MPA Pass
4. Accumulation Structure: Close > EMA20 > SMA50
5. Accumulation Action: Close > Open AND Close in top 30% of bar
6. Volume > 1.2× average
7. Alpha Score ≥ Min Alpha
8. RS Quadrant: LEADING or IMPROVING
9. Micro Edge: Close > CPR + MVWAP
10. **VCP Loose**: ATR < 2× Average ATR AND Volume < 50-bar SMA (consolidation)
11. **OBV Rising**: OBV > OBV[1] > OBV[2] (2-bar momentum)
12. **OBV > OBV SMA20** (above its 20-bar moving average)
13. **VWMA20 > VWMA50** (volume shelf gate)

**Stop Loss:** Same as POS-BO (10-bar low − 0.2× ATR)

**Trail:** Chandelier Exit ratchet (CE-POS). Once T1 is hit, the SL floor becomes the entry price (breakeven lock).

---

### 3.3 SWG-PB — Swing Pullback

**Concept:** Price pulls back from a Stage 2 advance into the EMA20, tightens (VCP Tight), and closes back above the EMA20 with a bullish bar. This is a continuation entry after an established trend.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. SWG-PB Edge Toggle: ON
3. Market Health: BULL
4. Close > SMA50 (price is above its trend MA)
5. Low touched or pierced EMA20 (pullback reached the EMA)
6. Close > EMA20 (recovered above the EMA)
7. Close > Open (bullish close)
8. **VCP Tight**: ATR < 1.0× Average ATR (very narrow range)
9. **MA Stack**: SMA150 > SMA200 (Minervini structural filter)
10. **RSI Pocket**: RSI > 30 AND RSI < 70 (not extreme overbought/oversold)
11. **Volume Dry-Up**: 3-bar volume SMA[1] < 50-bar volume average (prior consolidation on thin volume)

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**Trail:** EMA20 ratchet. The SL rises each bar to: max(current SL, EMA20 × (1 − trail buffer %)). Breakeven lock after T1.

**Time Stop:** 10 days (if gain < 0.5R at day 10, close position)

**Contextual Exit:** Immediate close if price falls below SMA50

---

### 3.4 SWG-BO — Swing VCP Breakout

**Concept:** A very tight VCP base (ATR < 1× average) breaks above the N-bar high on volume. Unlike POS-BO, this is a shorter-hold swing trade without the full positional prerequisite stack.

**Entry Conditions:**
1. Bull Master Toggle: ON
2. SWG-BO Edge Toggle: ON
3. Market Health: BULL
4. VCP Tight: ATR < 1.0× Average ATR AND Volume < 50-bar SMA
5. Close (or High) > 20-bar prior High
6. Volume > 1.5× average

> Note: SWG-BO does **not** require Base Confirmed or Alpha Score. It is a pure momentum/pattern trade.

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**Trail:** EMA20 ratchet (same as SWG-PB)

---

### 3.5 SWG-REV — Swing Reversion

**Concept:** A mean-reversion trade when the stock is severely oversold (RSI < 35) but above its SMA200 (trend intact). Price must close above the prior bar's high (reversal confirmation).

**Entry Conditions:**
1. Bull Master Toggle: ON
2. SWG-REV Edge Toggle: ON
3. Close > SMA200 (long-term trend intact)
4. Close < EMA20 (short-term depressed)
5. RSI < 35 (oversold)
6. Close > Open (bullish bar)
7. Close > High[1] (breaks prior bar's high)

**Stop Loss:** 5-bar swing low × (1 − SL Padding %)

**T1:** Fixed 2.0R (strict for mean-reversion — no dynamic adjustment)

**Time Stop:** 5 days maximum (mean-reversion trades are short-duration by design — if not moving in 5 days, exit)

**Contextual Exit:** Immediate close if price falls below SMA50

---

### 3.6 GAP-GO — Gap & Go

**Concept:** An institutional-grade gap-up where a stock opens above the prior day's high, gaps at least 4%, and closes in the top 40% of the gap bar on ≥3× volume. This signals conviction buying, not a fade.

**Entry Conditions (all must be true):**
1. Bull Master Toggle: ON
2. GAP-GO Edge Toggle: ON
3. Market Health: BULL
4. **Gap Confirmed**: Open > High[1] AND Close > Open
5. **Gap Size ≥ 4%**: (Open − High[1]) / High[1] ≥ 0.04
6. **Intraday Position ≥ 60%**: (Close − Open) / (High − Open) ≥ 0.60 — price must close in the top 40% of the gap bar's range
7. **Volume ≥ 3× average**

**Stop Loss:** Gap bar's low × (1 − SL Padding %)

**Trail:** EMA20 ratchet (same as other swing trades)

**Time Stop:** 10 days (same as SWG-PB)

---

## 4. The 3 Recovery Market Edges — Entry Criteria

### 4.1 REV-CB — Climax Bottom

**Concept:** Identifies a panic capitulation event followed by an institutional reversal. The sequence is: Stretched stock → Panic selling (washout) → Climax bar (highest volume down-day) → Turn bar (bullish close above prior high). This is a high-risk, high-reward counter-trend entry.

**Entry Conditions — 4 Pillars (all must pass):**

| Pillar | Condition | Dashboard |
|---|---|---|
| P1 — Stretched | Stock down ≥15% from 60-bar high | ✓ / ✗ |
| P2 — Oversold | ≥5 red bars in 7-bar window AND close in bottom 25% of 10-bar range | ✓ / ✗ |
| P3 — Climax Bar | Volume ≥ 2× average ON widest-range down bar within 20-bar lookback | ✓ / ✗ |
| P4 — Turn Bar | Close > Open, Close > High[1], Close in top 40% of bar | ✓ / ✗ |

**Additional Gates:**
- Recent Climax: Climax bar occurred within last 10 bars
- RFF Score ≥ minimum
- Regime Gate: Market corrected ≥7% OR stock corrected 10–40%

**Stop Loss:** Climax structural low − 0.5× ATR14 (snapped at climax event)

**T1 Target:** EMA20 reclaim
**T2 Target:** SMA200 reclaim

**Trail (after T1):** EMA20 ratchet trail. Pre-T1, stop stays at the climax low snap.

**Time Stop:** 15 trading days if gain < 0.5R

---

### 4.2 REV-RS — RS Survivor

**Concept:** During a market correction, most stocks fall. An RS Survivor is one that holds up relatively well (RS slope positive) and forms a higher low, then breaks out of its own local resistance on volume. These stocks often lead the next bull leg.

**Entry Conditions (all must be true):**
1. Recovery Master Toggle: ON
2. REV-RS Edge Toggle: ON
3. RS Slope > 0 (Mansfield RS relative to Nifty 500 benchmark)
4. Higher Low Structure: Recent 5-bar low > Prior 10-bar low[5]
5. Daily Trend: Strict pivot trend = Uptrend
6. Stock corrected: 10%–40% from 52W high
7. Breakout: Close > 20-bar prior High
8. Volume > 1.5× average
9. Sector Stage: Stage 1 or Stage 2
10. RFF Score ≥ minimum
11. Regime Gate: Market or stock in correction

**Stop Loss:** Recent higher low × (1 − SL Padding %)

**Trail:** Chandelier Exit ratchet (CE-REC). Once T1 hit, breakeven lock.

**T1:** Entry + 2.5R
**T2:** 52-Week High

**Time Stop:** 15 days if gain < 0.5R

---

### 4.3 REV-EARLY — Early Bird

**Concept:** The earliest possible recovery entry — before RS turns fully positive and before the breakout is confirmed by volume. The stock must show a compressed base (NR7 or inside-bar series) AND reclaim its downtrend trendline. This is the highest-risk recovery edge.

**Entry Conditions (all must be true):**
1. Recovery Master Toggle: ON
2. REV-EARLY Edge Toggle: ON
3. Trendline Reclaim: Close > highest high from bar[10] to bar[20] (downtrend resistance)
4. RS Recovery Structure: Higher Low AND Daily trend Uptrend
5. Base Compressed: NR7 (narrowest range in 7 bars) OR ≥3 inside bars in 10-bar lookback
6. Pivot Break: Close > 15-bar prior high with volume > 1.5× average
7. RS Slope > 0
8. Sector Stage: Stage 1 or Stage 2
9. RFF Score ≥ minimum
10. Regime Gate: Market or stock in correction

**Stop Loss:** Lowest low within NR7 window × (1 − SL Padding %)

**Trail:** Chandelier Exit ratchet (same as REV-RS)

**T1:** Entry + 2.5R
**T2:** 52-Week High

---

## 5. Exit Engine — Complete Rules

### 5.1 T1 Partial Exit (Breakeven Trigger)

| Edge Group | T1 Target | Exit % |
|---|---|---|
| POS-BO / POS-AC | Entry + 2.5R | 30% of position |
| SWG-PB / SWG-BO / GAP-GO | Entry + 2.5R (bull) or 2.0R (bear) | 50% of position |
| SWG-REV | Entry + 2.0R (fixed) | 50% of position |
| REV-CB | EMA20 reclaim price | 50% of position |
| REV-RS / REV-EARLY | Entry + 2.5R | 50% of position |

> **Breakeven Lock:** Once T1 is hit, `is_breakeven = true`. All trailing stops are immediately floored at the entry price — you cannot lose on the remaining runner.

### 5.2 T2 Runner Exit

| Edge Group | T2 Target | Exit % |
|---|---|---|
| SWG-PB / SWG-BO / GAP-GO | Entry + 3.5R (bull) or 3.0R (bear) | 50% of remaining |
| REV-CB | SMA200 reclaim | 50% of remaining |
| REV-RS / REV-EARLY | 52-Week High | 50% of remaining |
| POS-BO / POS-AC | No fixed T2 — full CE trail | Trail to exit |

### 5.3 Trailing Stop Logic by Position Type

**Position A — POS-BO / POS-AC (Chandelier Exit Ratchet):**
- Initial SL: 10-bar low − 0.2× ATR
- Trail: `max(current SL, CE trailing stop)` — only ratchets upward, never down
- CE = `Highest Close[22] − ATR[22] × 3.0` (bull) or `× 3.5` (bear)
- Stage 4 Exit: Immediate close if Weekly Stage turns to 4

**Position B — SWG Trades (EMA20 Ratchet):**
- Initial SL: 5-bar swing low × (1 − SL Padding %)
- Trail: `max(current SL, EMA20 × (1 − trail buffer %))`
- Contextual Kill Switch: Close below SMA50 → immediate exit
- SWG-REV Kill: 5-day time limit regardless of P&L

**Position C — REV-CB (EMA20 Trail after T1):**
- Initial SL: Climax structural low − 0.5× ATR (snapped at climax bar)
- Pre-T1: Fixed at climax low snap
- Post-T1: `max(snapped SL, EMA20 × (1 − trail buffer %), entry price)`

**Position D — REV-RS / REV-EARLY (Chandelier Exit Ratchet):**
- Initial SL: Higher low × (1 − SL Padding %)
- Trail: `max(current SL, CE trailing stop)` — same CE as Position A
- Breakeven lock applied after T1

### 5.4 Time-Decay Exits

| Edge Group | Max Hold | Condition |
|---|---|---|
| POS-BO / POS-AC | 6 weeks (30 trading days) | Unrealised gain < 0.5R AND not yet breakeven |
| SWG Trades | 10 trading days | Same |
| Recovery Trades | 15 trading days | Same |

> Time stops exist to free capital from stagnant positions. They do **not** fire if the trade has already hit breakeven — the runner is protected and can be held via the trailing stop.

---

## 6. Position Sizing Logic

### 6.1 Base Risk Calculation
```
Risk Amount     = Portfolio Capital × (Risk % / 100)
SL Distance     = Entry Price − Initial Stop Loss
Qty by Risk     = Risk Amount / SL Distance
Qty by Capital  = Max Allocation / Entry Price
Final Qty       = min(Qty by Risk, Qty by Capital)
```

### 6.2 Regime Discount
- In a bear market (Market Health ≠ BULL), the risk % is reduced:
  `Regime Risk = max(Base Risk − 0.25%, 0.25%)`

### 6.3 Recovery Edge Discount
- Recovery trades always use the **Recovery Risk %** (default 0.5%), which is typically lower than the Bull Risk % to account for higher uncertainty.

### 6.4 Kelly Multiplier (Bull Trades Only)
| Conditions Met | Kelly Multiplier |
|---|---|
| All 3: Stage 2 + RS Positive + Volume > SMA50 | 1.25× (Full Kelly) |
| Any 2 of 3 | 1.0× (Standard) |
| Only 1 of 3 | 0.75× (Half Kelly) |

### 6.5 Volatility Discount
- ATR % of price is calculated: `atr_pct = ATR / Close × 100`
- High-volatility stocks get a discount: `vol_disc = min(3.0 / atr_pct, 1.0)`
- Final position: `Qty = Qty × max(vol_disc × kelly_mult, 0.75)`

---

## 7. Signal Quality Filters — The 4 Gate System

These filters were added specifically to prevent low-quality signal fires that inflate trade count without improving edge.

### Gate 2 — POS-AC OBV Momentum Filter
**Problem solved:** Accumulation signals firing when price is quiet but no institutional buying is detectable.
**Solution:** OBV must show 2-bar consecutive rises AND OBV must be above its 20-bar SMA.
**Effect:** Confirms that volume-weighted buying (smart money) is actually increasing before calling accumulation.

### Gate 3 — SWG-PB Quality Stack
**Problem solved:** Pullback entries firing in weak or structurally broken trends.
**Solution:** Three additional checks:
- **MA Stack** (SMA150 > SMA200): Confirms Minervini-style structural alignment
- **RSI Pocket** (30–70): Avoids entries at RSI extremes (overextended or crashing)
- **Volume Dry-Up** (3-bar vol SMA < 50-bar avg): Prior bars must show consolidation, not distribution

### Gate 4 — GAP-GO Quality Filter
**Problem solved:** Small gaps or gaps that immediately fade triggering entries.
**Solution:** Three additional checks:
- **4% Minimum Gap**: Rules out tiny overnight moves
- **Intraday Position ≥ 60%**: Close must be in the upper 40% of the gap bar (held its gains)
- **3× Volume**: Confirms institutional participation, not retail noise

### Gate 5 — Volume Shelf Filter (POS-BO / POS-AC)
**Problem solved:** Volume spikes on a single bar triggering breakout signals without sustained volume interest.
**Solution:** `VWMA(volume, 20) > VWMA(volume, 50)` — the 20-bar volume-weighted average must be above the 50-bar average, confirming that elevated volume has been sustained across multiple recent bars.

---

## 8. Market Regime Decision Tree

Use this tree at the start of each trading day to frame your session context:

```
Check CNX500 vs SMA200
│
├── CNX500 > SMA200 AND SMA50 > SMA200?
│   └── BULL MARKET → Focus on Bull edges (POS-BO, POS-AC, SWG-PB, SWG-BO, GAP-GO)
│       └── Recovery edges remain armed — look for REV-RS / REV-EARLY leaders
│
└── CNX500 < SMA200?
    ├── CNX500 down ≥7% from recent high?
    │   └── CORRECTION → Prioritise REV-CB, REV-RS, REV-EARLY
    │       └── Bull edges still fire but use reduced sizing (regime discount applies)
    │
    └── CNX500 far below SMA200?
        └── BEAR → Recovery edges only. Disable Bull edges OR accept reduced sizing.
            └── Watch for market reclaim (recent low > prior low) as recovery signal
```

---

## 9. Workflow Integration with the Weinstein Commander

The Unified Ecosystem is designed to work alongside the rest of the Weinstein Commander suite:

| Tool | Role |
|---|---|
| **Weinstein and Swing Pro Dashboard v67.0** | Provides day-to-day multi-stock overview, entry date tracking, portfolio slot management |
| **Web Commander (Bull + Recovery Screeners)** | Weekly/daily scan to shortlist candidates; outputs a watchlist |
| **Weinstein_Unified_Ecosystem_v2.2.pine** | Applied per stock from the shortlist for final signal confirmation and position sizing |
| **Context Layers v1.0** | Provides Wyckoff, Volume Profile, SMC, and CONTEXT SCORE overlay on the same chart for institutional context confirmation |

### Recommended Workflow

**Step 1 (Weekend / Any Day):**
Run the Web Commander Bull Screener and Recovery Screener to get the candidate shortlist.

**Step 2 (Daily Pre-Market):**
Load the Unified Ecosystem on each shortlisted stock. Check:
- Market Health, Stage, RS Quadrant (top 3 rows)
- Any 🟢 signal in the Bull or Recovery sections

**Step 3 (Entry Decision):**
- 🟢 on POS-BO or SWG-BO → Place a buy-stop limit order above the breakout level at the open
- 🟢 on POS-AC or SWG-PB → Place a market order at the open or a limit order at EMA20
- 🟢 on GAP-GO → Only valid on the gap day itself; confirm volume by 11:30 AM before acting
- 🟢 on REV-CB → Enter on the next bar open after the turn bar

**Step 4 (Position Management):**
- Note the Initial SL from the dashboard or strategy tester
- Log the `active_catalyst` label (shown on chart as the entry comment) — this determines your trail type
- Watch for T1 target (🟡 label on chart) — set a limit sell order at T1 price
- After T1, your stop is automatically at breakeven — hold the runner via the CE or EMA trail

**Step 5 (Exit Review):**
Each day, check:
- Is the trailing stop still valid? (CE step-line rising = yes)
- Has Stage 4 been reached? → Close POS trades immediately
- Has price closed below SMA50? → Close SWG trades immediately
- Has the time stop been triggered? → Close if < 0.5R and not breakeven

---

## 10. Edge Selection Cheat Sheet

| Market Condition | Best Edges | Avoid |
|---|---|---|
| Strong Bull, Stage 2 | POS-BO, POS-AC | REV-CB (counterproductive) |
| Bull with tight VCP | SWG-PB, SWG-BO | REV-EARLY (low reward) |
| Bull gap-up day | GAP-GO | SWG-REV (wrong direction) |
| Oversold in bull | SWG-REV | REV-CB (need correction context) |
| Market correction | REV-RS, REV-EARLY | POS-BO (no base confirmed) |
| Panic/capitulation | REV-CB | All bull edges |
| Stage 4 confirmed | None | All edges — stay flat |

---

## 11. R-Multiple Reference Table

| Edge | T1 (exit %) | T2 (exit %) | Remainder |
|---|---|---|---|
| POS-BO | 2.5R → 30% out | No T2 (CE trail) | 70% runs |
| POS-AC | 2.5R → 30% out | No T2 (CE trail) | 70% runs |
| SWG-PB | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| SWG-BO | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| SWG-REV | 2.0R → 50% out | No T2 | 50% closed |
| GAP-GO | 2.5R → 50% out | 3.5R → 50% of rest | ~25% runs |
| REV-CB | EMA20 → 50% out | SMA200 → 50% of rest | ~25% runs |
| REV-RS | 2.5R → 50% out | 52W High → 50% of rest | ~25% runs |
| REV-EARLY | 2.5R → 50% out | 52W High → 50% of rest | ~25% runs |

> **Note:** The `SWG-REV` has a hard 5-day time stop and only a T1 target. It is designed as a quick mean-reversion trade, not a runner.

---

## 12. Troubleshooting Signals

| Symptom | Likely Cause | Fix |
|---|---|---|
| No bull signals on any stock | Market Health = CORRECTION/BEAR | Check CNX500 — regime discount may be suppressing signals |
| POS-BO fires but not POS-AC | OBV gate blocking POS-AC | Normal — POS-AC needs OBV confirmation; wait for OBV to trend up |
| SWG-PB not firing on obvious pullbacks | MA Stack (150 > 200) failing | Check if SMA150 has crossed below SMA200 — stock may be weakening |
| REV-CB firing on every bounce | CB Pillar thresholds too loose | Increase Min Climax Volume Mult or Min Red Bars in Washout |
| Recovery signals fire in bull market | Regime gate not blocking | Confirm "Require Recovery Market Regime?" is ON |
| Alpha Score shows 🔴 on quality stocks | Min Alpha Score too high | Lower from 50 to 40, or disable Macro Edge requirement |
| Stage shows Stage 1 but looks like Stage 2 | Slope threshold too tight | Reduce `slopeThresh` input slightly |
| RFF shows "NO DATA" | TradingView lacks financials for this ticker | Set Min RFF Score to 0 for this stock, or skip |

---

## 13. May 2026 Update — v3.5 + v3.6 Changes

This section documents the May 2026 changes to `Weinstein_Unified_Ecosystem_v3.4.pine`.

### 13.1 What Changed

| Version | Date | Change |
|---|---|---|
| **v3.4** | 2026-05-20 | Added Wyckoff Spring/SOS/JAC entries to `trigger_rec_raw`; POS-ACCUM and REV-CB/RS/EARLY temporarily removed from triggers. **[Superseded]** |
| **v3.5** | 2026-05-21 | **POS-ACCUM and REV-* RE-ADDED to triggers.** The v3.4 removals were based on a 30-day forward-window backtest (wrong horizon for positional / accumulation / recovery setups). Wyckoff catalysts remain **additive** alongside REV-*, not replacements. |
| **v3.6** | 2026-05-21 | **Catalyst-aware fallback ATR multipliers** when the structural SL anchor is above close. POS=4.0×, WYC=3.5×, REV-RS/EARLY=2.5×, SWG=1.5×. Previously all catalysts fell back to 1.5×, which knocked positional trades out within the first 2 weeks. |
| **v4.0** | 2026-05-22 | **ML & DB Integration**: Added Machine Learning Logistic Regression Probability model and RSI 47-54 Dead Zone filter. Replaced all sector/string mapping hacks with a physical 664-symbol `sectors.db` sync. |

### 13.2 Triggers Currently Active (v4.0+)

```
trigger_bull_raw = pos_bo_trigger OR pos_ac_trigger OR swing_pb_trg
                   OR swing_bo_trg OR swing_rev_trg OR gap_go_trg

trigger_rec_raw  = trigger_wyc_spring_sos OR trigger_wyc_jac
                   OR trigger_wyc_sos OR trigger_wyc_spring
                   OR trigger_rev_cb OR trigger_rev_rs OR trigger_rev_early
```

Both Wyckoff (5 triggers) and REV-* (3 triggers) fire simultaneously. The strategy enters on whichever fires first (priority order: WYC > REV per Commander_Recovery v2.0).

### 13.3 SL Discipline (v3.6)

Initial SL anchors are **structural** (unchanged):
- POS-*: `lowest_low_10 − 0.2×ATR14`
- WYC-*: `wyc_base_low × 0.98` (Spring) or `wyc_base_low − 0.3×ATR14`
- REV-CB: `climax_low_snap − 0.5×ATR14`
- REV-RS / REV-EARLY: structural low − pad
- SWG-*: `lowest_low_5 × (1 − sl_pad_pb)` or gap-bar low

**Fallbacks** (when structural anchor is above close) now scale with the trade horizon:
| Catalyst | Fallback | Was |
|---|---|---|
| POS-BO, POS-ACCUM | `close − 4.0×ATR14` | `close − 1.5×ATR14` |
| WYC-* | `close − 3.5×ATR14` | `close − 1.5×ATR14` |
| REV-RS, REV-EARLY | `close − 2.5×ATR14` | `close − 1.5×ATR14` |
| SWG-* | `close × 0.99` | (unchanged) |
| REV-CB | `nz(cb_sl_raw, close × 0.92)` | (unchanged) |

### 13.4 Pine Recompile Required

After updating from v3.4 (or earlier) to v3.6, you must:
1. Open `Weinstein_Unified_Ecosystem_v3.4.pine` in TradingView Pine Editor
2. Save (Ctrl+S) and `Add to Chart` to recompile

### 13.5 Catalyst Behavior You Should Expect

- **POS-BO / POS-ACCUM trades will have wider initial SL** (~6-12% rather than ~3%) when the fallback path triggers. Position sizing at 1% risk automatically halves the share count — this is correct discipline.
- **Wyckoff trades fire alongside REV-***; you may see WYC and REV signals on the same chart, with WYC taking precedence in the priority cascade.
- **No catalyst is suppressed**. If a setup qualifies, it fires.
