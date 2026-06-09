# Commander Risk Allocator v2.0 — User & Trading Guide

> **File:** `Commander_Risk_Allocator_v2.0.pine` · **Type:** Indicator (overlay) · **Market:** NSE/BSE
> **Role:** Discretionary, chart-click position sizer + trade planner. It is the manual-execution companion to the automated Unified Ecosystem engine — same catalyst targets, same regime-aware trail, but you place the trade by hand.
> Supersedes v1.1 (`Commander_Risk_Allocator_v1.0.pine`), which remains as a simpler 2-leg fallback.

---

## What's new in v2.0 (the four big features)

| # | Feature | What it does |
|---|---|---|
| 1 | **Auto-detect catalyst + context** | Reads Weekly Stage (30-WMA), Mansfield RS/RRG and price-action to **pre-select** the catalyst family, so you don't have to classify the setup manually. Manual selector remains the override. |
| 2 | **Auto-suggest structural SL** | Proposes the stop from the catalyst-aware structural rule. A clicked SL overrides it. No more eyeballing the stop. |
| 3 | **3-leg scale-out (T1/T2/T3) + runner** | Three target levels with **exact share quantity per leg**, all drawn on the chart, plus the trailed runner. |
| 4 | **Dhan GTT / broker export** | Emits a structured JSON payload (entry, SL, 3 target legs w/ qty, trail) for the GTT_Auto_Shield workflow — alongside the Telegram + Pine-Log notes. |

> **Canonical-source note:** the auto-detect layer is a *faithful suggestion* for sizing convenience. The **Bull/Recovery screeners and the Unified strategy remain the canonical signal source.** If the on-chart detector and a screener ever disagree, the screener wins.

---

## 1. Installation & first use

1. Add the indicator to a chart on your trade timeframe (Daily for positional/Wyckoff/recovery; 75/125-min or Daily for swing).
2. Set your capital + risk in **Portfolio & Risk** (one-time).
3. Leave **Auto-detect Catalyst** and **Auto-suggest Structural SL** ON (defaults).
4. Click **Entry** on the chart. That's the only mandatory click — SL and T1 auto-fill from the catalyst. Click SL/T1 only to override.

---

## 2. Inputs — field by field

### Master Configuration
| Input | Default | Values / meaning |
|---|---|---|
| Asset Type | Auto | `Auto` (ETF if `syminfo.type==fund`, else Stock) · `ETF` · `Stock`. Picks which capital/risk/max-alloc tier applies. |

### Portfolio & Risk
| Input | Default | Meaning |
|---|---|---|
| Total Portfolio Capital | ₹40,00,000 | Reference only. |
| ETF / Stock Portfolio Capital | ₹12L / ₹28L | Capital base used in the risk-amount math, per asset class. |
| ETF / Stock Risk % | 1.00% / 0.75% | Base risk per trade before adjustments. |
| Max Alloc per ETF / Stock Trade | ₹2.4L / ₹2.8L | Hard capital ceiling per position (caps Quantity regardless of risk math). |
| Lot Multiplier | 1 | 1 for cash equity; set to F&O lot size to size in lots. |

### v2.0 Automation
| Input | Default | Meaning |
|---|---|---|
| **Auto-detect Catalyst** | ON | When ON and a setup is detected, the catalyst is chosen automatically. Falls back to the manual selector when no setup is found, or when OFF. |
| **Auto-suggest Structural SL** | ON | When ON, the stop is derived from the catalyst's structural rule. A clicked SL always overrides. |

### Interactive Trade Setup
| Input | Default | Meaning |
|---|---|---|
| Catalyst (manual / override) | POS-BO / POS-ACCUM | Used when auto-detect is OFF or finds nothing. Options: `POS-BO / POS-ACCUM`, `WYC (Wyckoff)`, `SWG-BO / SWG-PB`, `SWG-GAP`, `SWG-REV`, `REV-CB / RS / EARLY`. |
| Entry Price | 0 (click) | Your intended entry. If 0, the current close is used for previews. |
| Stop Loss — OPTIONAL override | 0 (click) | Leave 0 → auto-structural SL. Click → manual override. |
| Target (T1) — OPTIONAL override | 0 (click) | Leave 0 → catalyst T1. Click → manual T1. T2/T3 are always catalyst-based. |
| Price Tick Size | 0.10 | Rounds every price to the nearest tick. Use 0.05 for 5-paise ticks. |

### v2.0 Scale-Out (3-leg)
| Input | Default | Meaning |
|---|---|---|
| T2 exit % | 25 | Share % to sell at T2. |
| T3 exit % | 25 | Share % to sell at T3. |
| *(T1 %)* | catalyst | Not an input — set by the catalyst (POS/WYC/REV 25%, SWG 33%, GAP/SWG-REV 50%). |
| *(Runner %)* | derived | `100 − T1% − T2% − T3%`, floored at 0. |

### Risk Adjustment
| Input | Default | Meaning |
|---|---|---|
| Enable Kelly Probability Sizing | ON | Scales risk ×0.75–1.25 from a 3-point score (Stage-2 + RS>0 + Volume>1.1×avg): 3pts→1.25×, 2→1.0×, ≤1→0.75×. |
| Reduce Risk if ATR > 3% | ON | Scales risk down by `min(3/ATR%, 1)` for high-volatility names. |
| Bear-Market Risk Discount (−0.25%) | ON | Deducts 0.25% from base risk in a bear regime (floored at 0.25%). |

### Alerts / Export
| Input | Default | Meaning |
|---|---|---|
| 🔔 SEND TO TELEGRAM | off | Fires the trade-plan note to Telegram (if Chat ID set) + Pine Log. Check, click OK, uncheck. |
| 📤 EXPORT DHAN GTT JSON | off | Fires the structured GTT JSON to the alert + Pine Log. Check, OK, uncheck. |
| Telegram Chat ID | "" | Numeric Telegram user id (from @userinfobot). |

### Visuals
| Input | Default | Meaning |
|---|---|---|
| Show Allocator Table | ON | Toggles the 16-row panel. |
| Table Position | Bottom Right | 6 positions. |
| Show Entry/Stop/Target Lines | ON | Draws Entry (blue), SL (red), T1 (green), T2 (lime), T3 (aqua dotted). |
| Line Extension (Bars) | 8 | How far the lines extend right. |

---

## 3. Catalyst → Target / SL / Trail matrix (the engine)

Mirrored byte-for-byte from `Weinstein_Unified_Ecosystem_v3.4.pine` §7 (targets) + the shared SL/Chandelier blocks. **T3 is allocator-specific** (a stretch runner beyond the strategy's open trail) and is clearly tagged as such.

| Catalyst | T1 | T1 % | T2 | T3 (stretch) | Structural SL anchor | Trail (Bull / Bear) |
|---|---|---|---|---|---|---|
| **POS-BO / POS-ACCUM** | 5R | 25% | 10R | 15R | 10-bar low − 0.2 ATR | Chandelier 4.5× / 5.0× |
| **WYC (Wyckoff)** | 5R | 25% | max(10R, 52wH) | max(15R, 52wH) | base low × 0.98 | 3.5× / 4.0× |
| **SWG-BO / SWG-PB** | 3R | 33% | 5R | 8R | min(EMA20, 5-bar low) | EMA20 ≈ 1.5× / 2.0× |
| **SWG-GAP** | 2R | 50% | 4R | 6R | min(EMA20, 5-bar low) | EMA20 ≈ 1.5× / 2.0× |
| **SWG-REV** | 2R | 50% | 2R | 3R | min(EMA20, 5-bar low) | EMA20 ≈ 1.5× / 2.0× |
| **REV-CB / RS / EARLY** | 5R | 25% | 52W-High | max(52wH×1.05, 10R) | 20-bar low − 0.5 ATR | Chandelier 2.5× / 3.0× |

**SL fallback:** if the structural anchor is invalid (≥ entry), the SL falls back to `entry − ATR × {POS 4.0 / WYC 3.5 / REV 2.5 / SWG 1.5}`.
**Regime** = CNX500 above its 200-SMA **and** 50 > 200 → "Bull"; otherwise "Bear" (widens trail +0.5×, applies the −0.25% risk discount).

---

## 4. Auto-detect logic (how the catalyst is suggested)

Computed on each bar from daily structure + weekly Stage + RS. Priority order (first match wins):

| Order | Detected catalyst | Trigger condition (suggestion heuristic) |
|---|---|---|
| 1 | **SWG-GAP** | Gap-up > 4% over prior close **and** bar closes green |
| 2 | **WYC** | Drawdown ≥ 15% from 52wH **and** tight 40-bar base (range ≤ 25%) **and** close > close[5] (turning up) |
| 3 | **REV** | Drawdown ≥ 15% **and** close > close[5] **and** RS momentum > 0 |
| 4 | **POS** | Stage-2 uptrend **and** close at/near the 40-day closing high |
| 5 | **SWG** (PB) | Stage-2 **and** price within 3% of daily EMA20 **and** green bar |
| 6 | **SWG-REV** | 3 consecutive lower closes then an up close (oversold bounce) |
| — | **none → MANUAL** | If nothing matches, the panel uses your manual selector and the "Catalyst src" row shows `AUTO→none, using MANUAL` |

The panel header shows `AUTO POS` / `MAN SWG` etc. so you always know whether the targets came from detection or your selector.

---

## 5. Panel reference (16 rows)

| Row | Label | Meaning / values |
|---|---|---|
| 0 | Risk Allocator v2 / `Stock · AUTO POS` | Asset class + catalyst source (`AUTO`/`MAN`) + family |
| 1 | Context | `Stage 2 ✓ · LEADING` — weekly Stage (1–4) + RRG quadrant; colour-coded by stage |
| 2 | Entry | Clicked entry, tick-rounded |
| 3 | Stop `[AUTO]`/`[MANUAL]` | SL price + (% distance). `— set SL` if neither clicked nor auto |
| 4 | Adjusted Risk % | Final risk % after Kelly/vol/regime, with base in brackets |
| 5 | **Quantity** | Shares to buy (the primary output) |
| 6 | Invested | Quantity × Entry |
| 7 | Risk Amt | Quantity × (Entry − SL) |
| 8 | T1 `n`% (xR) `[MAN]?` | T1 price **× leg qty**. n% = catalyst T1 size |
| 9 | T2 `m`% (xR) `[52wH]`/`[≥10R/52wH]`? | T2 price × leg qty |
| 10 | T3 `k`% (xR) | T3 stretch price × leg qty |
| 11 | Runner `r`% | Remaining shares trailed to exit |
| 12 | Trade Validation | `✅ Clear Room to T1` or `⚠️ T1 > Overhead Res (price)` (52wH or 200-DMA) |
| 13 | Trail (`Chandelier`/`EMA20 (≈ATR)`) | `Bull/Bear ×N.N ATR` — catalyst width, regime-adjusted |
| 14 | RRG `<quadrant>` | RS value / momentum |
| 15 | Catalyst src | `AUTO-detected` / `AUTO→none, using MANUAL` / `MANUAL (auto off)` |

---

## 6. Dhan GTT export payload

When you tick **📤 EXPORT DHAN GTT JSON**, this fires to the alert + Pine Log (one line). Feed it into the GTT_Auto_Shield mapper:

```json
{"source":"RiskAllocator_v2","symbol":"NAVINFLUOR","exchange":"NSE","instrument":"Stock",
 "side":"BUY","catalyst":"POS","catalyst_src":"AUTO","stage":2,
 "qty":140,"entry":4520.00,"stop_loss":4395.50,"risk_pct":0.75,"risk_amt":17430.00,
 "legs":[{"tag":"T1","price":5142.50,"qty":35,"r":5.0},
         {"tag":"T2","price":5765.00,"qty":35,"r":10.0},
         {"tag":"T3","price":6387.50,"qty":35,"r":15.0}],
 "runner_qty":35,
 "trail":{"kind":"Chandelier","atr_mult":4.5,"regime":"bull"}}
```

> Set up a TradingView alert with the message left blank (the script supplies the JSON via `alert()`), point the webhook at your GTT_Auto_Shield endpoint, then tick the export box. Untick after firing.

---

# Trading Guide — how to leverage v2.0

## The workflow (catalyst-first)

1. **Open the chart, read the panel.** With auto-detect ON, the header already tells you the suggested catalyst and the Context row tells you Stage + RRG. If `Catalyst src = AUTO-detected` and Stage is 2 (or 1 for recovery/Wyckoff), you have a coherent setup.
2. **Sanity-check the suggestion against the screener.** The detector is a convenience; confirm the same name is a live pick in the Bull/Recovery screener before committing real risk. If they disagree, trust the screener and set the catalyst manually.
3. **Click Entry.** SL and T1/T2/T3 auto-fill. If you see a hard structural stop tighter than the auto SL (a clean demand-zone low), click it to override — the whole ladder re-sizes.
4. **Read Quantity → place the order.** That single number is risk-first: it already respects your risk %, the volatility discount, the Kelly tilt, and the max-alloc ceiling.
5. **Place the scale-out.** Use the per-leg share counts (T1 ×q1 / T2 ×q2 / T3 ×q3 / runner). Fire the GTT export to push them to GTT_Auto_Shield.

## Reading the catalyst → how aggressively to trade
- **POS / WYC (positional):** widest targets (10R/15R), 25% at T1, big runner on a 4.5×/3.5× Chandelier. These are your "let it run" trades — don't choke them with a tight manual stop.
- **SWG-BO/PB (swing):** 3R/5R, 33% at T1, EMA20 trail. 1–4 week holds — take profit faster.
- **SWG-GAP / SWG-REV:** 2R targets, 50% off at T1. Quick, mean-reversion-ish — bank early, small runner.
- **REV (recovery):** 5R then 52W-high. Beaten-down quality turning up; confirm RFF ≥ 4 in the Recovery screener first.

## When to override
- **Override the SL** when a visible structure (demand zone, swing low) gives a tighter, cleaner stop than the catalyst's mechanical anchor — it improves R:R and shrinks risk-per-share (more shares for the same ₹ risk).
- **Override T1** only when a hard resistance sits *before* the catalyst's R-target. Watch the **Trade Validation** row: `⚠️ T1 > Overhead Res` means even the auto-T1 runs into the 52wH/200-DMA — consider trimming T1 to just under that level.

## Regime awareness
- A **Bear** Trail tag means the market is below its 200-SMA: trail wider (whipsaw protection) **and** your risk % is already discounted. In a confirmed bear tape, prefer REV/defensive catalysts and smaller size — the panel does the sizing, but the decision to trade at all is yours.

## Guardrails (from the trading DNA)
- Risk-first always: the **Quantity is the output, never the input.** Don't round it up.
- No Stage 3/4 entries: if the Context row shows **Stage 3 ⚠ / Stage 4 ✗**, do not initiate a long regardless of what the targets say.
- The allocator sizes a trade; it does not validate the *thesis*. Entry/stop quality is on you.
