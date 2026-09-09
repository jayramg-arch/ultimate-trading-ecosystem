# Commander Recovery Strategy: Positional/Swing Trading Playbook

> [!WARNING]
> **Market Regime Context: 0 / 100**
> A Market Regime score of 0/100 indicates a confirmed "Death-Cross" or severe bear market state. In this environment, breakout trading (Bull Screener) will suffer massive false positive rates. **The Recovery Strategy is the only mathematically viable approach**, focusing on deep capitulation, smart-money accumulation, and mean reversion.

When trading the Recovery theme, you are hunting for stocks that have been irrationally punished and are now showing evidence of institutional "smart money" stepping in to stop the bleeding. Here is your step-by-step workflow leveraging the Commander v2 ecosystem.

---

## Step 1: Rapid-Fire Discovery (Screening)

You have two powerful engines for finding these setups. For the best results, use them in tandem.

### The Wyckoff Engine (Primary)
The backtests show that pure RSI mean-reversion fails in protracted bear markets. However, the **Wyckoff Accumulation** framework delivered +6.39% cumulative alpha. 
* **Action**: Run `recovery_screener_v3_wyckoff.py` on your master watchlist.
* **Target Signals**: Look for the `WYC-*` prefix.

### The Pine Screener (Secondary / Live Validation)
Load `Commander_Recovery_Screener_v2.0.pine` onto any chart in TradingView. Open the Pine Screener tab to scan your NSE watchlists in real-time.

---

## Step 2: Signal Prioritization (The Hierarchy)

Not all recovery signals are created equal. When your screener outputs a CSV, filter and prioritize the candidates in this exact order:

### Tier 1: The "Smart Money" Accumulation (Highest Conviction)
1. **`WYC-SPRING+SOS` (Signal 8)**: The holy grail of recovery. The stock made a false breakdown below a base (Spring) and immediately reversed with a powerful bullish thrust (Sign of Strength).
2. **`WYC-JAC` (Signal 7)**: Jump Across the Creek. The stock has broken completely out of the accumulation base.

### Tier 2: The Structural Capitulation Reversals (Legacy Engine)
1. **`REV-EARLY` (Signal 4)**: Inside-3 or NR7 compression reclaim. The selling pressure has entirely dried up, forming a tight coil, followed by a bullish break.
2. **`REV-CB` (Signal 2)**: Capitulation Bottom Bounce. Only take this if you see massive climax volume (≥ 2.0x average) coupled with extreme fear (RSI(3) < 20).

> [!CAUTION]
> **The Watch-Only Trap (Signal 1)**
> If the screener outputs `Signal = 1 (Watch)`, do NOT enter. This means a climax volume event happened, but the "Turn Bar" (the green reversal candle) has not yet formed. The stock is still falling. Set a price alert at the previous bar's high instead.

---

## Step 3: The Validation Checklist (Dashboard)

Take your top 3-5 candidates from the screener and load them into the **Commander Dashboard v67.0** on TradingView. Verify the following:

1. **Recovery Score & Grade**: Must be `≥ 9 (Grade A)`. If it's a Grade B (6-8), you need extreme conviction in the volume. Ignore anything below 6.
2. **Deep Drawdown**: Check the 60-bar drawdown metric. You want stocks that are at least `-20% to -25%` down from their 60-bar high. The deeper the rubber band is stretched, the harder it snaps back.
3. **Fundamentals (RFF Lite)**: Verify the RFF Lite score is at least `1/2` (Net Income > 0). You do not want to buy the dip on a company that is actively going bankrupt.
4. **Volume Confirmation**: The signal bar *must* have Relative Volume `≥ 1.5x`. If a stock is recovering on low volume, it is a dead cat bounce, not institutional accumulation.

---

## Step 4: Execution & Sizing

Because the broader market is 0/100, the rising tide is NOT lifting all boats. You are fighting gravity.

* **Position Sizing**: Automatically cut your standard swing size in half. If you normally risk 1% of your portfolio per trade, risk 0.5%. Use your `Risk_Allocator_v1_Guide` to calculate the exact share count.
* **Entry**: Buy on the close of the confirmed Turn Bar / SOS, or the open of the next day. For `REV-EARLY`, use a buy-stop order just above the signal bar's high.

---

## Step 5: Trade Management (The 90-Day Horizon)

Recovery trades require a longer horizon (up to 90 days) compared to momentum breakouts because the stock has to chew through overhead supply.

### The Stop Loss (Non-Negotiable)
* **Anchor**: Your hard stop is placed slightly below the structural low (e.g., the exact bottom of the Wyckoff Spring or the Climax Low).
* **Volatility Floor**: If the structural low is too tight, ensure your stop is at least **2.5x the Daily ATR** away from your entry to avoid being chopped out by bear market volatility. *Never trail your stop down.*

### Profit Targets (Scaling Out)
1. **Target 1 (T1)**: The **EMA 20** or **2.5R** (whichever is closer). Overhead moving averages act as massive resistance in bear markets. You *must* scale out 50% to 75% of your position here to lock in risk-free profit.
2. **Target 2 (T2)**: The **200 DMA** or **52-Week High**. Leave a runner to capture the full mean reversion if the stock successfully transitions back into a Stage 1/2 uptrend. Trail this runner using the EMA 20.
