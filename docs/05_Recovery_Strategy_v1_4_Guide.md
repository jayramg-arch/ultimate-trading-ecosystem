# Weinstein Recovery Strategy v1.4 — User & Trading Guide [DEPRECATED — DOCUMENT-ONLY REFERENCE]

> **🛑 DEPRECATED — File deleted from project root on 10 May 2026.**
> The standalone `Weinstein_Recovery_Strategy v1.4.pine` file no longer exists. The 3 Recovery edges (REV-CB / REV-RS / REV-EARLY) have been **fully consolidated** into the canonical strategy file:
>
> - **`Weinstein_Unified_Ecosystem_v2.2.pine`** (in-file `strategy()` title now `[v2.3]`)
>
> **For active trading**, use:
> - **[14_Unified_Ecosystem_Trading_Guide.md](./14_Unified_Ecosystem_Trading_Guide.md)** — the operational playbook for all 9 edges
> - **[13_Unified_Ecosystem_User_Guide.md](./13_Unified_Ecosystem_User_Guide.md)** — input-by-input field reference
>
> This document is retained only as a historical record of the standalone v1.4 logic. None of its parameter recommendations should be considered current — the consolidated v2.3 implementation is the source of truth.

> **Module Role:** The contrarian arm of the suite. Targets beaten-down, fundamentally sound stocks showing early reversal signals — not stage-2 leaders, but stage-1 survivors preparing to re-emerge. Use the **Capitulation Screener v1.5** to find candidates, then load each on the **Dashboard v67.0** to confirm the full signal stack.

---

## 1. The Three Recovery Edges

| Edge | Code | Signal Value | Description |
|---|---|---|---|
| Capitulation Bottom Bounce | **REV-CB** | 2 | 4-pillar capitulation + reversal bar |
| RS Survivor Breakout | **REV-RS** | 3 | Positive-RS stock breaking 20-day high in uptrend |
| Early Trend Reclaim | **REV-EARLY** | 4 | NR7/inside-3 compression + 20-bar reclaim |

All edges must pass through a **5-layer gate** before an entry is generated:
1. **Liquidity Gate** — daily turnover ≥ `min_daily_turnover`
2. **Regime Gate** — macro environment favours recovery trades
3. **Fundamental Gate (RFF)** — company is profitable (NI/OCF positive)
4. **Structural Gate** — price action confirms reversal structure
5. **Edge Trigger** — specific pillar conditions are all true

---

## 2. Inputs — Field-by-Field

### Master Filters
| Input | Default | Explanation |
|---|---|---|
| **Min Daily Turnover (INR)** | `50,000,000` | Liquidity gate — `close × volume`. Raise to ₹10 Cr for large-cap focus. |
| **Require Recovery Market Regime?** | `true` | At least ONE of three macro conditions must hold (see Regime Gate below). |
| **Min Correction from 52W High (%)** | `10.0` | Stock must have fallen ≥10% from its 52W high to pass the "stock corrected" regime branch. |
| **Signal Hold Window (Trading Days)** | `5` | After a signal fires, how many bars the label stays visible. |
| **Min Fundamental Score (RFF)** | `1` | `0`=Off, `1`=Net Income>0, `2`=NI + Operating Cash Flow both positive. **Always use 2 for real trades.** |

### REV-CB Settings
| Input | Default | Explanation |
|---|---|---|
| **Max Drawdown — 60-bar (%)** | `-25.0` | Pillar 1: Stock must be ≥25% off its 60-bar high. Confirms genuine capitulation. |
| **Min Red Bars in Lookback** | `5` | Pillar 2a: At least 5 of the last 10 bars must be bearish closes. |
| **Range / Red-Bar Lookback** | `10` | Window for Pillar 2 (red-bar count + bottom-quartile) and Pillar 3 (widest-range). |
| **Min Climax Volume Multiplier** | `2.0` | Pillar 3: Climax bar must be widest-range, bearish, AND ≥2× average volume. |
| **Climax Detection Window** | `10` | Bars after the climax in which the turn bar (Pillar 4) must appear. |

### REV-RS / REV-EARLY Settings
| Input | Default | Explanation |
|---|---|---|
| **RS Breakout Lookback (Days)** | `20` | REV-RS: stock must close above its 20-day high. |
| **Strict-Trend Confirmation Lag** | `2` | `piv_d_right` for `f_getStrictTrend()`. **Must match the Zigzag indicator's right-bar setting.** |
| **Volume Confirmation** | `1.5` | RS and EARLY breakouts require ≥1.5× average volume. |
| **Volume Average Length** | `50` | Baseline for all volume comparisons. |

---

## 3. Detection Logic

### REV-CB: The Four Pillars
```
Pillar 1: (close - highest_60) / highest_60 × 100 ≤ -25%
Pillar 2: red_bars_in_10 ≥ 5  AND  close in bottom 25% of 10-bar range
Pillar 3: widest range in 10 bars  AND  bearish close  AND  volume ≥ 2× avg
→ Climax bar identified; window opens for 10 bars

Pillar 4 (Turn Bar — within cb_climax_window):
  close > open  (green bar)
  AND close in top 40% of bar range
  AND close > high[1]  (breaks prior bar's high)
→ Signal fires. SL = lowest_5_bar_low - ATR14 × 0.5
```

### REV-RS: Trend-Gated Breakout
```
dTrend == 1  (Strict uptrend: HH+HL confirmed)
AND lowest_5_bar_low > lowest_10_bar_low[5]  (higher-low structure)
AND close > highest_high_20_bars[1]  (20-day breakout)
AND volume ≥ 1.5× avg
AND Mansfield RS vs CNX500 > 0
→ Signal fires. SL = lowest_5_bar_low - ATR14 × 0.2
```

### REV-EARLY: Compression + Reclaim
```
NR7: today's range = narrowest of last 7 bars
OR Inside-3: last 3 bars are all inside bars

AND close > highest_high_20_bars[1]  (20-bar range reclaim)
AND volume ≥ 1.5× avg
AND Mansfield RS > 0
→ Signal fires. SL = lowest_5_bar_low × 0.998
```

---

## 4. The Regime Gate — 3-Way Logic

```
mkt_idx_corrected:  CNX500 fell ≥ 7% from its 52W high
         OR
mkt_reclaim:        CNX500 > SMA50 AND was below SMA50 within last 30 bars
         OR
stock_corrected:    This stock fell ≥ 10% from its own 52W high

At least ONE must be true.
```

The three-way gate covers broad corrections (`mkt_idx_corrected`), post-shock momentum phases (`mkt_reclaim`), and individual sector/stock dislocations (`stock_corrected`).

---

## 5. Exit Logic

| Target | REV-CB | REV-RS / REV-EARLY |
|---|---|---|
| T1 (exit 50%) | 20-period EMA | Entry + 2.5× actual risk |
| T2 (exit 25%) | 200 SMA | 52-week high |
| Trail (25%) | Chandelier Exit ×3.0 ATR | Same |

After T1 is hit → move stop to breakeven on remaining position.

---

## 6. Targets per Edge — Signal Priority
```
signal_val = 4 → REV-EARLY (highest conviction)
signal_val = 3 → REV-RS
signal_val = 2 → REV-CB
signal_val = 1 → Climax detected, waiting for turn bar (Watch mode)
signal_val = 0 → No signal
```

The Composite Recovery Score (0–12) adds: fundamental quality (0–2), RS quality (0–2), correction depth (0–2), market alignment (0–1), weekly stage (0–1), edge confirmation (0–2), exceptional volume (0–1). **Only trade scores ≥ 6.**

---

## 7. Weekly Multi-Timeframe Stage Check

`f_get_weekly_bundle()` is called via `request.security()` to evaluate the stock's Weinstein Stage on the **Weekly timeframe**:

- **Stage 1 or 2** → ideal for all three edges
- **Stage 3 or 4** → REV-CB may still fire, but conviction drops significantly; reduce position size by 50%

---

## 8. Ecosystem Integration

| Module | How It Connects |
|---|---|
| **Unified Ecosystem v2.2** | REV edges are now fully integrated here — this standalone script is legacy only |
| **Capitulation Screener v1.5** | Exact screener port of the REV edges — use it to scan 100+ tickers daily |
| **Dashboard v67.0** | RECOVERY section runs inline pillar checks; shows 4-dot grid (●●●●) |
| **Zigzag v6.0** | `f_getStrictTrend()` shared with REV-RS gate — keep `piv_d_right` consistent |
| **Risk Allocator v1.0** | Feed the SL price into the Allocator for exact quantity |
| **Wyckoff v1.0** | REV-CB ≈ Wyckoff SC→ST; REV-EARLY ≈ LPS entry |

---

## 9. Common Mistakes

1. **Buying on the climax bar** — Wait for Pillar 4 (the turn bar). The climax can extend lower.
2. **Skipping RFF** — Companies with negative earnings recover far less reliably. Never set RFF to 0.
3. **Ignoring regime gate** — In full bull markets, individual-stock REV signals can be traps. Keep the gate on.
4. **REV-RS without strict trend** — `dTrend == 1` is mandatory; entering a breakout in a LH/LL structure leads to false breakout traps.
5. **Not moving stop to breakeven at T1** — The strategy is specifically designed as a T1→trail structure. Failing to do this converts a risk-managed trade into a wide-stop guessing game.
