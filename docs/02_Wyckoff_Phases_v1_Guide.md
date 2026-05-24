# Weinstein Wyckoff Phases v1.0 — User & Trading Guide

> **Module Role in Ecosystem:** This indicator adds a **narrative layer** on top of the structural data provided by the Zigzag and Volume Profile. While the Zigzag tells you *where* the market is structurally, Wyckoff tells you *why* — is this a base forming under distribution, or an accumulation structure about to launch? It works in tandem with the Volume Profile (identifying POC/VAH/VAL levels near Wyckoff events) and the SMC Zones module (Order Blocks often coincide with Wyckoff Spring or Test events).

---

## 1. What It Does

The indicator automatically detects and labels the key **Wyckoff market cycle events** on your chart. It identifies two complete cycle sequences:

### Accumulation Phase (Markup Setup)
| Event | Code | Description |
|---|---|---|
| Preliminary Support | **PS** | First significant buying after a downtrend; volume increases |
| Selling Climax | **SC** | Panic selling, wide spread, high volume; potential bottom |
| Automatic Rally | **AR** | Price bounces after SC; defines top of the trading range |
| Secondary Test | **ST** | Retest of SC area on lower volume; supply drying up |
| Sign of Strength | **SOS** | Break above AR with wide spread and volume; institutional buying |
| Last Point of Support | **LPS** | Pullback after SOS; low volume, tight range; optimal entry |

### Distribution Phase (Markdown Setup)
| Event | Code | Description |
|---|---|---|
| Preliminary Supply | **PSY** | First significant selling after an uptrend |
| Buying Climax | **BC** | Frenzied buying at top; wide spread, huge volume; potential top |
| Automatic Reaction | **AR** | Decline after BC; defines bottom of trading range |
| Upthrust | **UT** | False breakout above BC; tests supply above the range |
| Sign of Weakness | **SOW** | Break below AR with wide spread and volume |
| Last Point of Supply | **LPSY** | Weak rally after SOW; optimal short entry (not used in long-only system) |

---

## 2. Inputs — Field-by-Field

### Group: Detection Parameters
| Input | Default | Explanation |
|---|---|---|
| **Pivot Left Bars** | `3` | Left-side confirmation bars for swing detection. Must match or be close to the Zigzag indicator's left setting for consistent pivot identification. |
| **Pivot Right Bars** | `3` | Right-side confirmation bars. Higher values = fewer, more significant Wyckoff events labeled; lower values = more granular but noisier event detection. |
| **Volume Multiplier — Climax Events** | `2.0` | The SC and BC events require volume to be at least this multiple of the average volume. Default 2.0× means the bar must have twice the average volume. Increase to 2.5–3.0 for stricter climax detection. |
| **Volume Average Length** | `50` | The lookback period for calculating average volume used in the climax multiplier check. Consistent with other modules that use a 50-bar volume baseline. |
| **Volume Multiplier — SOS/SOW** | `1.5` | Sign of Strength and Sign of Weakness events require 1.5× average volume to confirm institutional participation. |

### Group: Display
| Input | Default | Explanation |
|---|---|---|
| **Show Accumulation Labels** | `true` | Toggle PS, SC, AR, ST, SOS, LPS labels |
| **Show Distribution Labels** | `true` | Toggle PSY, BC, AR, UT, SOW, LPSY labels |
| **Label Size** | `Small` | Size of the event labels on the chart |
| **Show Phase Background** | `true` | Shades the accumulation zone (blue) and distribution zone (red) between key Wyckoff levels |
| **Highlight Optimal Entries** | `true` | Draws an arrow or box at LPS (accumulation) and LPSY (distribution) events — the highest-probability entry/exit zones |

---

## 3. Detection Logic Deep-Dive

### 3.1 How Events Are Mapped to Pivots
The script uses the same pivot engine as the Zigzag indicator (`ta.pivothigh` / `ta.pivotlow`) but then applies **contextual filters** to label each pivot as a Wyckoff event:

```
Pivot Low + Volume > 2× avg + No prior confirmed AR → Label as SC
Pivot High + After SC + Lower Volume → Label as AR
Pivot Low + After AR + Lower Volume than SC → Label as ST
...
```

Events are **sequential and stateful** — a `PS` must be detected before a `SC` can be labeled, and so on. This prevents random labeling on mid-trend bars.

### 3.2 The AR Level — The Range Boundary
After a Selling Climax (SC) or Buying Climax (BC), the Automatic Rally/Reaction price is stored. This becomes the **upper boundary of the accumulation range** (or lower boundary of distribution). Every subsequent pivot is evaluated against this level:
- Pivot **above the AR** in an accumulation phase → potential **SOS**
- Pivot **below the AR** in a distribution phase → potential **SOW**

### 3.3 Volume-Based Event Confirmation
The volume multiplier is the critical differentiator. Without volume, Wyckoff events lose their meaning. The script enforces:

| Event | Volume Requirement |
|---|---|
| SC / BC | `volume >= vol_avg * climax_vol_mult` (default 2.0×) |
| SOS / SOW | `volume >= vol_avg * sos_vol_mult` (default 1.5×) |
| ST / LPS / UT / LPSY | No strict volume gate — structural position is primary |

---

## 4. Practical Trading Workflow

### Phase 1 — Accumulation Setup
**Look for:** SC → AR → ST sequence
1. **SC appears:** A capitulation-style candle with 2× volume at a new low. This is the potential bottom. Do **not** buy here — risk is still high.
2. **AR appears:** Price bounces to form the top of the range. Note this price level.
3. **ST appears:** Price retests the SC area on lower volume. This confirms supply is drying up. Begin watching for SOS.

**Action at ST:** This is your **first early-entry zone** (maps to the Recovery Strategy's REV-CB pillar). Risk is defined below the SC low.

### Phase 2 — Markup Confirmation
**Look for:** SOS → LPS
4. **SOS appears:** Price breaks above the AR level with expanding volume and closes in the upper portion of its range. Institutional buyers are active.
5. **LPS appears:** A low-volume pullback to the breakout area. This is the **highest-probability long entry** in the Wyckoff methodology.

**Action at LPS:** This maps directly to the Minervini Strategy's **pullback entry (SWG-PB)** — tight stop below the LPS low, target the measured move above the trading range.

### Phase 3 — Distribution Warning
**Look for:** BC → UT → SOW
1. **BC appears:** A climax bar at highs with extreme volume. Begin tightening stops on existing longs.
2. **UT appears:** False breakout above BC; if your long position was entered in the base, use UT as your **exit signal** or apply the Chandelier Exit trailing stop aggressively.
3. **SOW appears:** Structural confirmation of distribution. Close any remaining longs.

---

## 5. Integration with Other Modules

### With Volume Profile (v1.0)
- The **SC price** should coincide with or be near the **VAL (Value Area Low)** from the Volume Profile
- The **SOS breakout** has higher conviction if it clears the **POC (Point of Control)** with volume
- An **LPS** near the POC or VAH is a very high-probability setup

### With SMC Zones (v1.0)
- Wyckoff **SC areas** often coincide with **Bullish Order Blocks** (the last bearish candle before a major rally)
- A **Spring** (which occurs when price briefly dips below the ST low) is frequently the same bar that sweeps a **Liquidity Level** in the SMC module
- **SOS** breakouts align with **Fair Value Gap** fill on the upside

### With Weinstein Dashboard
- A stock showing **Stage 1 (BASE)** on the Dashboard is in an accumulation phase — look for PS/SC/AR/ST labels here
- **Stage 2 (UP)** initiation corresponds to when SOS is confirmed and the Dashboard upgrades the recommendation to BUY

### With Recovery Strategy v1.4
- The **REV-CB pillar** (Capitulation Bottom Bounce) is essentially a quantified Wyckoff SC detection with stricter criteria
- The `cb_climax_window` input in the Recovery Strategy and Screener mirrors the concept of "time within the trading range after the climax"

---

## 6. Reading the Visual Output

| Visual Element | What It Means |
|---|---|
| **Blue shaded zone** | Active accumulation range (between SC and AR levels) |
| **Red shaded zone** | Active distribution range (between BC and AR levels) |
| **Green arrow ↑** at LPS | High-probability long entry signal |
| **Red arrow ↓** at LPSY | Potential exit or short signal (if applicable) |
| **White dashed line** | The AR level — the critical range boundary |

---

## 7. Configuration Recommendations

### For Identifying Major Cycles (Positional / Weekly Chart)
| Setting | Recommended |
|---|---|
| Pivot Left | `5` |
| Pivot Right | `5` |
| Climax Volume Multiplier | `2.5` |
| Show Phase Background | `true` |

### For Swing Trading (Daily Chart)
| Setting | Recommended |
|---|---|
| Pivot Left | `3` |
| Pivot Right | `3` |
| Climax Volume Multiplier | `2.0` |
| SOS Volume Multiplier | `1.5` |

---

## 8. Common Mistakes

1. **Labeling every pivot as a Wyckoff event** — The indicator applies strict sequential rules. Do not force Wyckoff labels onto every consolidation; many bases are not valid Wyckoff structures.
2. **Buying at SC** — The SC marks potential capitulation, but the reversal is not confirmed until ST + SOS. Entering at SC means accepting very wide risk.
3. **Ignoring volume on SOS** — A "breakout" above the AR without volume expansion is a **failed SOS** and often leads to a UT (upthrust) in the distribution framework.
4. **Overlooking the timeframe** — Wyckoff cycles are most reliable on higher timeframes (Weekly for positional, Daily for swing). Intraday Wyckoff is much noisier.
