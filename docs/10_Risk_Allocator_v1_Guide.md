# Commander Risk Allocator v1.0 — User & Trading Guide

> **Module Role:** The **trade execution engine** — the final step before pressing the buy button. After the Dashboard confirms a BUY/STRONG BUY and the Screener surfaces the candidate, the Risk Allocator calculates the exact quantity to buy, the rupee amount to deploy, the T1/T2 targets, and the Chandelier Exit trailing stop mode — all adjusted for current volatility, market regime, and your Kelly-fraction quality assessment. It also provides a Telegram alert integration for logging trades to your personal channel.

---

## 1. What It Does

The Risk Allocator is an **interactive trade setup panel** built directly inside TradingView. You enter your proposed entry price and stop-loss price via input fields, and the indicator instantly computes:

- **Position Size** (quantity in shares) using Kelly-adjusted risk
- **INR Deployment** (how much capital to use)
- **T1 and T2 Targets** (R-multiple based)
- **Stop Distance** (% and INR)
- **Chandelier Exit Mode** (Bull/Bear, based on market regime)
- **Risk-Adjusted R Multiples** (live as price moves)

---

## 2. Inputs — Field-by-Field

### Portfolio Settings
| Input | Default | Explanation |
|---|---|---|
| **Total Portfolio Capital (INR)** | `500,000` | Your full trading account value. The base denominator for all risk calculations. Update whenever you add or withdraw capital. |
| **Base Risk per Trade (%)** | `1.0` | The percentage of your total portfolio you are willing to risk on this single trade. Default 1% on ₹5L = ₹5,000 max risk. This is the **starting point** before Kelly and volatility adjustments. |
| **Max Allocation per Trade (INR)** | `50,000` | Hard ceiling on capital deployed regardless of what the formula returns. Prevents over-concentration in any single position. |
| **Min Allocation per Trade (INR)** | `5,000` | Hard floor — ensures every approved trade gets meaningful capital. Prevents Kelly from sizing a trade to negligible quantities. |

### Trade Setup
| Input | Default | Explanation |
|---|---|---|
| **Entry Price (INR)** | `0` | Your planned entry price. The system uses this (not the chart price) so you can plan entries at limit prices. |
| **Stop-Loss Price (INR)** | `0` | Your hard stop-loss. The distance between entry and stop defines your "1R" — the denominator for all target calculations. **This is the most critical input.** |
| **Asset Type** | `Stock` | `Stock`, `ETF`, or `Index`. ETF and Index carry lower base risk (see Kelly multipliers below). |
| **Trade Style** | `Swing` | `Positional` or `Swing`. Positional trades use a wider CE multiplier; Swing uses tighter. |

### Kelly Quality Assessment
These three toggles adjust the base risk up or down based on setup quality:

| Input | Default | Explanation |
|---|---|---|
| **Stage 2 Confirmed?** | `false` | Is this stock in a confirmed Weinstein Stage 2 uptrend on the Weekly? If yes, adds +0.25× to the Kelly multiplier. Check the Dashboard's STAGE row. |
| **RS Positive vs N500?** | `false` | Is the Mansfield RS vs CNX500 positive? If yes, adds +0.25× to the Kelly multiplier. Check the Dashboard's RS vs N500 row. |
| **Volume Above Average?** | `false` | Is the entry-day volume ≥ 1.5× the 50-bar average? If yes, adds +0.25× to the Kelly multiplier. |

**Kelly Multiplier Table:**
| Conditions True | Kelly Multiplier | Effective Risk |
|---|---|---|
| 3 of 3 | 1.25× | 1.25% of portfolio |
| 2 of 3 | 1.0× | 1.0% of portfolio (base) |
| 1 of 3 | 0.75× | 0.75% of portfolio |
| 0 of 3 | 0.5× | 0.5% of portfolio |

### Market Regime Adjustments
| Input | Default | Explanation |
|---|---|---|
| **Bear Market Discount** | `true` | When CNX500 is below its 200 SMA, automatically reduces effective risk by 0.25%. Protects capital in adverse macro conditions. |
| **ATR Volatility Check** | `true` | If the current ATR/Close > 3%, applies an additional volatility discount to keep the INR risk constant despite wider price swings. Formula: `adjusted_qty = base_qty × (0.03 / (ATR/Close))`. |

### Target Settings
| Input | Default | Explanation |
|---|---|---|
| **T1 R-Multiple** | `2.5` | First target = `Entry + (Risk × 2.5)`. Default matches the Minervini Strategy's bull-market T1. Change to 2.0 in bear markets. |
| **T2 R-Multiple** | `4.0` | Second target = `Entry + (Risk × 4.0)`. For positional trades in Stage 2. |
| **T1 Exit %** | `50` | Percentage of the position to sell at T1. Default 50% ensures you lock in meaningful gains while letting the rest run. |
| **T2 Exit %** | `25` | Percentage of the position to sell at T2. The remaining 25% is the trailing portion. |

### Chandelier Exit (CE) Mode
| Input | Default | Explanation |
|---|---|---|
| **CE Mode** | `Auto` | `Auto` selects the multiplier based on market regime and trade style. `Bull` = 3.0× ATR14. `Bear` = 3.5× ATR14. `Tight` = 2.5× ATR14 (for short-duration swings). Manual = user-defined. |
| **CE Manual Multiplier** | `3.0` | Only used when CE Mode = `Manual`. |

### Telegram Integration
| Input | Default | Explanation |
|---|---|---|
| **Enable Telegram Alert** | `false` | When enabled, clicking the "Send to Telegram" button (or triggering the Pine alert) sends a formatted trade setup summary to your Telegram bot. |
| **Telegram Bot Token** | `""` | Your Telegram bot's API token. Get from @BotFather. Store as a TradingView alert message variable for security — **do not hardcode** in Pine inputs. |
| **Telegram Chat ID** | `""` | Your personal Telegram chat ID or group ID where trade alerts are sent. |

---

## 3. The Calculation Logic

### Step 1: Raw Risk in INR
```
base_risk_pct = base_risk% × kelly_multiplier
bear_discount  = (cnx500 < sma200_cnx500) ? -0.25% : 0
effective_risk_pct = base_risk_pct + bear_discount
raw_risk_inr = total_capital × effective_risk_pct / 100
```

### Step 2: Volatility Adjustment
```
atr_ratio = ATR14 / close
if atr_ratio > 0.03:
    vol_adjustment = 0.03 / atr_ratio  (scale down)
else:
    vol_adjustment = 1.0  (no adjustment needed)
adjusted_risk_inr = raw_risk_inr × vol_adjustment
```

### Step 3: Per-Share Risk and Quantity
```
risk_per_share = entry_price - stop_loss_price
raw_quantity   = floor(adjusted_risk_inr / risk_per_share)
```

### Step 4: Apply Allocation Caps
```
total_deployment = raw_quantity × entry_price
if total_deployment > max_alloc:
    quantity = floor(max_alloc / entry_price)
if total_deployment < min_alloc:
    quantity = ceil(min_alloc / entry_price)
final_quantity = constrained_quantity
```

### Step 5: Compute Targets and CE
```
risk_1R     = entry_price - stop_loss_price
T1          = entry_price + risk_1R × t1_mult
T2          = entry_price + risk_1R × t2_mult
CE_stop     = highest_high(14) - ATR14 × ce_multiplier  (trailing)
```

---

## 4. The On-Chart Panel

The Allocator renders an interactive panel (right side of chart) with:

| Section | Content |
|---|---|
| **SETUP** | Entry / SL / T1 / T2 prices with horizontal lines |
| **QUANTITY** | Final adjusted quantity in shares |
| **DEPLOYMENT** | Total INR to deploy (qty × entry) |
| **RISK** | INR at risk (qty × risk_per_share) — confirmed vs. planned |
| **KELLY MULT** | Active multiplier (0.5× – 1.25×) |
| **CE MODE** | Active CE mode and multiplier |
| **CURRENT R** | Live R-multiple based on current chart price |
| **ATR** | Current ATR14 and ATR% |
| **TELEGRAM** | "Send Alert" button (when Telegram is enabled) |

The **T1, T2, Entry, and SL lines** are drawn as horizontal lines on the chart with labelled price tags for visual reference.

---

## 5. Telegram Alert Format

When triggered, the Telegram message is formatted as:

```
🚀 TRADE SETUP — [TICKER]
─────────────────────
Entry:    ₹[entry_price]
Stop:     ₹[sl_price]  (−[sl_pct]%)
T1:       ₹[t1_price]  (+[t1_pct]%)
T2:       ₹[t2_price]  (+[t2_pct]%)
─────────────────────
Qty:      [quantity] shares
Deploy:   ₹[deployment]
Risk:     ₹[risk_inr] ([risk_pct]%)
Kelly:    [kelly_mult]×
CE Mode:  [ce_mode]  (ATR × [ce_mult])
─────────────────────
Stage: [stage] | RS: [rs_state] | Alpha: [score]
```

---

## 6. Ecosystem Integration

| Module | Connection |
|---|---|
| **Unified Ecosystem v2.2** | The ecosystem's inline risk panel replicates this logic — Risk Allocator is the standalone version for manual trade analysis outside the strategy |
| **Dashboard v67.0** | Quick-Check inputs (`quick_ent`, `quick_sl`) feed from this tool — set entry/SL in the Allocator, then copy to Dashboard for full analysis |
| **Capitulation Screener v1.5** | The Screener's SL Price output (`sl_price`) is the direct input for this allocator |
| **Beta Screener v2.6** | The Screener's recommended SL (ATR-based) feeds the Allocator's stop input |
| **Python Portfolio Sync** | Post-trade, the allocated quantity and entry price are reflected in the next Dhan → Pine sync |

---

## 7. Practical Trading Workflow

### Complete Trade Setup Flow

**Step 1 — Candidate Identification:**
- Run Bull/Recovery Screener → identify ticker
- Load on Dashboard → confirm BUY/STRONG BUY

**Step 2 — Trade Planning:**
- Open the Risk Allocator indicator on the same chart
- Set `entry_price` = your limit order price
- Set `stop_loss_price` = the strategy's computed SL (from Dashboard's STOP row)
- Toggle the Kelly quality assessment checkboxes based on Dashboard data

**Step 3 — Size Verification:**
- Read the `QUANTITY` and `DEPLOYMENT` values
- Confirm `RISK` is within your daily loss limit (e.g., max 2R total per day)
- Check `CURRENT R` row to verify the setup is not already past T1 (stale signal)

**Step 4 — Execute:**
- Place the limit order in Dhan for the computed `QUANTITY`
- Enable Telegram and click "Send Alert" to log the setup

**Step 5 — Post-Entry:**
- Run `master_portfolio_sync.py` to update the Dashboard Pine file with the new position

---

## 8. Common Mistakes

1. **Setting SL too wide "just to be safe"** — A wider SL reduces the `risk_per_share`, which increases the quantity, increasing total deployment and actual INR risk. If anything, a wide SL should **reduce** size, not increase it. The Kelly discount handles this: a poor setup gets 0.5× multiplier.
2. **Ignoring the Max Allocation cap** — When a high-quality setup (`1.25×` Kelly) in a high-priced stock produces a huge deployment number, the cap saves you. Do not override it.
3. **Not updating Total Portfolio Capital** — If you've had significant wins or losses, the capital base becomes stale. Update it weekly.
4. **Using CE Mode = Manual with wrong multiplier** — Using 1.5× ATR in a volatile stock will cause constant stop-outs from normal volatility. Use `Auto` or at minimum 3.0× for most setups.
5. **Forgetting to reset entry/SL between tickers** — The indicator retains last inputs. When flipping between charts for analysis, the old entry/SL from the previous stock will still show. Always update both inputs first.
