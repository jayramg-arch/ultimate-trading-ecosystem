# Weinstein SMC Zones v1.0 — User & Trading Guide

> **Module Role in Ecosystem:** The SMC (Smart Money Concepts) Zones module adds the **institutional footprint layer** to the Weinstein framework. While Weinstein uses weekly stages and moving averages to identify *what phase* the market is in, SMC pinpoints the *exact price zones* where institutional orders were placed — and therefore where price is most likely to react. This module provides the micro-precision entry and stop-level intelligence that the Zigzag's macro structure cannot.

---

## 1. What It Does

The indicator identifies and draws three types of institutional price zones:

### 1.1 Order Blocks (OB)
An **Order Block** is the last opposite-direction candle before a significant impulse move. The theory is that large institutions filled their orders on that candle, and when price returns to that zone, unfilled orders are likely to be waiting.

| OB Type | Formation | Color |
|---|---|---|
| **Bullish OB** | Last bearish (red) candle before a strong bullish impulse | Green box |
| **Bearish OB** | Last bullish (green) candle before a strong bearish impulse | Red box |

### 1.2 Fair Value Gaps (FVG)
A **Fair Value Gap** is a price inefficiency created when a candle moves so strongly that it leaves a gap between the previous candle's high and the next candle's low (for a bullish FVG) or vice versa. Price tends to return to "fill" these gaps.

| FVG Type | Structure | Meaning |
|---|---|---|
| **Bullish FVG** | `Low[0] > High[2]` — gap between bar-2 high and bar-0 low | Support zone; price tends to retrace and bounce |
| **Bearish FVG** | `High[0] < Low[2]` — gap between bar-2 low and bar-0 high | Resistance zone; price tends to retrace and reverse |

### 1.3 Liquidity Sweeps
A **Liquidity Sweep** occurs when price briefly pierces a prior swing high or low (taking out stop orders clustered there) before reversing sharply in the opposite direction. This is the SMC equivalent of a Wyckoff "Spring" or "Upthrust."

| Sweep Type | Condition | Signal |
|---|---|---|
| **Bullish Sweep** | Price briefly drops below a prior swing low then closes above it | Potential long entry after the wick |
| **Bearish Sweep** | Price briefly breaks above a prior swing high then closes below it | Potential short or exit trigger |

---

## 2. Inputs — Field-by-Field

### Group: Order Block Settings
| Input | Default | Explanation |
|---|---|---|
| **OB Lookback** | `50` | How many bars back to search for valid Order Block formations. A 50-bar window covers approximately 2–3 months of Daily data, capturing the most recent significant institutional activity. |
| **Impulse Move Threshold (ATR ×)** | `1.5` | The impulse move that follows the OB must be at least this multiple of the 14-period ATR. This filters out weak moves that don't suggest genuine institutional participation. Raise to 2.0 for stricter OB detection. |
| **Show Mitigated OBs** | `false` | When price revisits and **closes through** an Order Block, the OB is considered "mitigated" (its orders were filled). Toggle this to show mitigated zones as historical context. |

### Group: Fair Value Gap Settings
| Input | Default | Explanation |
|---|---|---|
| **Show FVGs** | `true` | Toggles FVG box drawing |
| **FVG Minimum Size (ATR ×)** | `0.3` | The FVG must be at least 0.3× the ATR in size to be displayed. Filters out trivially small gaps that have no practical significance. |
| **Show Filled FVGs** | `false` | When price fully closes the gap, the FVG is "filled." Toggle to show filled FVGs for historical study. |

### Group: Liquidity Settings
| Input | Default | Explanation |
|---|---|---|
| **Swing Lookback** | `10` | The prior swing high/low used as the liquidity target. A 10-bar lookback identifies recent swing extremes — the most likely clusters of retail stop orders. |
| **Sweep Confirmation Bars** | `1` | Number of bars after the sweep that must close back inside the prior range. A value of 1 means the sweep bar itself must close back inside (the wick is the sweep); a value of 2 allows the next bar to confirm the rejection. |

### Group: Mitigation Tracking
| Input | Default | Explanation |
|---|---|---|
| **Auto-Remove Mitigated Zones** | `true` | When an Order Block or FVG is fully mitigated (price closes through it), the indicator removes the box automatically. This keeps the chart clean and focused on active, unmitigated zones only. |
| **Mitigation Alert** | `false` | Fires a TradingView alert when price enters an unmitigated OB zone |

---

## 3. Detection Logic Deep-Dive

### 3.1 Order Block Formation
The script scans the lookback window for the following pattern (bullish OB):

```
Step 1: Find a bearish candle (close < open)
Step 2: Check if the NEXT move (up to impulse_lookback bars forward) 
        is bullish with range > ATR × impulse_threshold
Step 3: If yes → the bearish candle's body (open to close) is the Bullish OB zone
```

The OB box is drawn from the **candle's open** to its **close** (the body), not the full wick. The body is where the institutional orders were placed; the wick is noise.

### 3.2 FVG Detection
For each bar, the script checks:

```
Bullish FVG: high[2] < low[0]
  → Gap between bar-2's high and bar-0's low
  → Box drawn from low[0] to high[2] at bar_index[1]

Bearish FVG: low[2] > high[0]  
  → Gap between bar-2's low and bar-0's high
  → Box drawn from high[0] to low[2] at bar_index[1]
```

The FVG box extends from its creation bar to the right edge of the chart until it is filled.

### 3.3 Liquidity Sweep Detection
The script tracks recent swing highs and lows (using the `swingLookback` parameter). On each bar, it checks:

```
Bullish Sweep: 
  low < prior_swing_low AND close > prior_swing_low
  → Price swept below the level but rejected and closed above it
  → Label: "BSL Swept" (Buy-Side Liquidity Swept)

Bearish Sweep:
  high > prior_swing_high AND close < prior_swing_high
  → Price swept above the level but rejected and closed below it
  → Label: "SSL Swept" (Sell-Side Liquidity Swept)
```

### 3.4 Mitigation Tracking
Mitigation is checked on every bar for all active zones:

- **Order Block mitigated:** `close > OB_high` (for bearish OB) or `close < OB_low` (for bullish OB) — price closed *through* the zone
- **FVG filled:** The gap is completely closed — `close` covers both boundaries
- Mitigated zones are either removed (if `auto_remove=true`) or recolored to show they are spent

---

## 4. Practical Trading Workflow

### Step 1 — Identify Active Unmitigated OBs
After loading the indicator, note all green (bullish) OB boxes above the current price (not relevant as resistance) and **below** the current price (potential support on pullback). These are your high-probability pullback targets.

### Step 2 — Evaluate Zone Quality
Not all OBs are equal. Rank them by:
1. **Confluence with Volume Profile** — Is the OB at or near the POC or VAH? Higher conviction.
2. **Confluence with Weinstein levels** — Is the OB near the 50 DMA or 30-week SMA?
3. **Recency** — Older OBs (formed 100+ bars ago) are progressively less reliable.
4. **Impulse strength** — The larger the move that followed the OB, the more institutional orders were placed there.

### Step 3 — FVG as Entry Precision
When you have identified a valid OB and price is pulling back:
- Look for a **Bullish FVG within the OB zone** — this is the highest precision entry
- Enter as price touches the FVG within the OB, with a stop below the OB low

### Step 4 — Liquidity Sweep as Entry Trigger
The most powerful setups occur when:
1. Price sweeps below a prior swing low (BSL Swept label appears)
2. The sweep wick lands inside or near a Bullish OB
3. Price closes back above the sweep level

This is the **BSL Sweep + OB combination** — the same as Wyckoff's "Spring" — and is the highest-probability entry in the SMC framework.

### Step 5 — Bearish OBs as Exit Targets
When managing a long position, note all **Bearish OBs** above the current price. These are natural take-profit targets because institutions placed sell orders there. If the Minervini Strategy's T1 or T2 target coincides with a Bearish OB, use it as your exit level.

---

## 5. Integration with Other Modules

| Connected Module | Integration Point |
|---|---|
| **Zigzag v6.0** | Liquidity Sweeps in SMC occur at the same price levels as the Zigzag's prior swing highs/lows — they are the same liquidity pools |
| **Volume Profile v1.0** | OBs that coincide with HVNs (high-volume nodes) are the strongest support zones; LVNs within OBs suggest the price will move through them quickly |
| **Wyckoff Phases v1.0** | ST (Secondary Test) in Wyckoff = retest of Bullish OB; Spring = Bullish Liquidity Sweep; SOS = price clearing all nearby Bearish OBs |
| **Minervini Strategy v4.53** | The SMC Liquidity Sweep detection (`liq_sweep = dLow5 < dMA50 and dClose > dMA50 and dVol > avg*1.5`) in the Beta Screener is a direct SMC integration; adds +20 to the quality score |
| **Weinstein and Swing Pro Dashboard v67.0** | The SMC Sweep detection logic contributes to the Dashboard's `SMCLIQ` catalyst signal and quality scoring |
| **Recovery Strategy v1.4** | REV-CB Pillar 4 (the "turn bar" — green close after climax) is structurally identical to a Bullish Liquidity Sweep confirmation |

---

## 6. The SMC + Weinstein Framework Integration

The power of this module comes from using SMC as **micro-precision within Weinstein's macro framework**:

```
MACRO FILTER (Weinstein):
  ✅ Weekly Stage 2 (Uptrend)
  ✅ Price above 30-week SMA
  ✅ Mansfield RS > 0

TIMING FILTER (Minervini):
  ✅ Daily MA alignment (50 > 150 > 200)
  ✅ VCP compression or pullback

ENTRY PRECISION (SMC):
  ✅ Price at unmitigated Bullish OB
  ✅ Bullish FVG within the OB
  ✅ OR: Bullish Liquidity Sweep at/below the OB
```

This three-layer approach prevents the common mistake of using SMC in isolation (taking SMC setups in Stage 4 downtrends) and maximizes the probability of every entry.

---

## 7. Configuration Recommendations

### Conservative (Fewer, Higher-Quality Zones)
| Setting | Recommended |
|---|---|
| OB Lookback | `30` |
| Impulse Threshold | `2.0` |
| FVG Min Size | `0.5` |
| Auto-Remove Mitigated | `true` |

### Standard (Balanced — Default)
| Setting | Recommended |
|---|---|
| OB Lookback | `50` |
| Impulse Threshold | `1.5` |
| FVG Min Size | `0.3` |
| Auto-Remove Mitigated | `true` |

### Aggressive (More Zones, Lower Threshold)
| Setting | Recommended |
|---|---|
| OB Lookback | `100` |
| Impulse Threshold | `1.0` |
| FVG Min Size | `0.2` |
| Show Filled FVGs | `true` |

---

## 8. Common Mistakes

1. **Trading every OB** — Only trade OBs in the direction of the Weinstein stage. Bullish OBs in Stage 4 downtrends are traps.
2. **Ignoring mitigation** — A mitigated OB has no predictive value. If price closed through it and is now pulling back again, the zone is spent.
3. **Setting stop inside the OB** — The stop belongs *below* the OB low (for bullish OB longs), not inside the zone. Inside the zone is where smart money is absorbing; being stopped out inside the OB means you were taken out by normal volatility.
4. **Chasing after a Liquidity Sweep** — Enter on the close of the sweep bar or the first bar after rejection, not 5 bars later when the move is already underway.
