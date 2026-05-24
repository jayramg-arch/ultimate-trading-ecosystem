# 09 — Commander ETF Strategy v1.1 Guide (Pine)

> **Module role:** Executable Pine v6 strategy for NSE ETFs. Per-chart entry/exit logic with vol-profile sizing, Chandelier Exit trailing stop, T1 partial profits, and time-decay exits.
> **Phase:** Phase 5 of the ETF system (live execution).
> **Lines:** ~456.
> **File:** `Commander_ETF_Strategy_v1.0.pine` (title: v1.1).

---

## What it does

Single-symbol Pine strategy that mirrors the dashboard signal ladder but **executes trades**. Apply per ETF chart. Backtest in TradingView's Strategy Tester. Set alerts for live execution.

Best features ported from the Unified Stocks v2.3 strategy:
- Stage background colour
- Chandelier Exit (CE) trailing stop
- T1 partial profit + breakeven move
- Time-decay stop
- Volatility-discounted position sizing
- Active SL line on chart
- Pre-S2 early warning

---

## User Guide

### Loading on a chart

1. Open NSE ETF chart (NIFTYBEES, BANKBEES, GOLDBEES, etc.)
2. Indicators → Strategies tab → "Commander ETF Strategy v1.1"
3. Open Strategy Tester pane to see backtest

### Inputs (9 groups)

#### Backtest Window
| Input | Default | Purpose |
|---|---|---|
| Start Date | 2020-01-01 | Backtest start |
| End Date | 2030-01-01 | Backtest end (= future = full chart) |

#### Benchmark & RS
| Input | Default |
|---|---|
| RS Benchmark | NSE:CNX500 |
| Mansfield SMA Length | 200 |
| RS-Momentum Lookback | 20 bars (≈ 4 weeks) |

#### Stage & Trend
| Input | Default |
|---|---|
| Show 30W MA | true |
| Show 200-day SMA | true |
| Stage Background Colour | true |
| Min 200DMA Slope (Stage 2 gate) | 0.1% |

#### Liquidity
| Input | Default |
|---|---|
| Liquidity Lookback | 60 days |
| Min Median Turnover | ₹2 Cr/day (BUY-LEADER threshold) |
| Force-Exit Below | ₹1 Cr/day (liquidity collapse) |
| Min Liquidity Score for BUY-LEADER | 6 |

#### Entry / Exit Rules
| Input | Default | Purpose |
|---|---|---|
| Allow EARLY-BASE entries | false | Stage 1 + IMPROVING entries |
| EARLY-BASE Size Multiplier | 0.5 | Half-size for EB entries |
| Exit when RRG flips to LAGGING | true | Soft exit on rotation out |
| Exit on Stage 3 (aggressive) | false | Defensive variant |

#### Chandelier Exit
| Input | Default |
|---|---|
| Use Chandelier Exit | true |
| CE Lookback | 22 |
| CE ATR Multiplier | 3.0 |

#### T1 Partial Profit
| Input | Default |
|---|---|
| Take partial at T1 | true |
| T1 target (R multiple) | 2.5R |
| T1 Partial Qty (%) | 30% |

#### Time-Decay Stop
| Input | Default |
|---|---|
| Exit if no 0.5R progress | true |
| Time-stop window | 40 bars (~8 weeks) |

#### Position Sizing
| Input | Default | Purpose |
|---|---|---|
| Risk per Trade (%) | 1.0% | Risk budget per position |
| ATR Length | 14 |
| **Vol Profile** | **Med (broad equity)** | **Preset dropdown — recommended way to size** |
| Initial Stop ATR Mult (Custom) | 2.5 | Only used if Vol Profile = Custom |
| Vol-discount sizing | true | Shrinks qty for high-ATR ETFs |
| Target ATR pct (Custom) | 1.5 | Only used if Vol Profile = Custom |

#### Vol Profile presets

| Profile | atr_stop_mult | target_atr_pct | Use for |
|---|--:|--:|---|
| Low (gold/debt) | 1.8 | 1.0% | GOLDBEES, SILVERBEES, LIQUIDBEES, BBETF, GILT5YBEES |
| **Med (broad equity)** | **2.5** | **1.5%** | **NIFTYBEES, JUNIORBEES — default** |
| High (sector/smallcap) | 3.0 | 2.0% | All sector ETFs, MID150BEES, smallcap ETFs |
| Intl (Nasdaq/FANG) | 2.5 | 1.8% | MAFANG, MON100, NASDBEES, MASPTOP50 |
| Custom | (from custom inputs) | | Override manually |

#### Instrument Guard
| Input | Default |
|---|---|
| Block entries on non-ETF symbols | true |

#### Mini Dashboard
6-row panel (top-left default to avoid collision with the analysis Dashboard panel which defaults top-right):

| Row | What |
|---|---|
| 0 | Header (red bg if not an ETF) |
| 1 | SIGNAL |
| 2 | Position (FLAT or LONG NN sh @ price) |
| 3 | Active SL (with BE+CE flag after T1 hit) |
| 4 | T1 Hit? (YES locked / NO) |
| 5 | Open P/L |

### Signal ladder (extended for strategy)

When in a position, the strategy adds exit-signals to the standard ladder:
- **LIQ-EXIT** — turnover dropped below force-exit threshold
- **STAGE-EXIT** — Stage 4 entered
- **RRG-EXIT** — RRG flipped to LAGGING

These take precedence over BUY-LEADER etc. when held.

### Plots on chart

- 30W MA, 200-day SMA, optional 50-day SMA
- Stage background colour (yellow/green/orange/red)
- **CE Trail (raw)** — fuchsia step-line, always visible
- **Active SL** — red step-line, only visible when in a position
- Entry markers: `BL` triangle (BUY-LEADER), `EB` triangle (EARLY-BASE), `PRE-S2` circle
- Exit markers: red triangle on hard exits

### Alerts via `alert()` function

5 messages fire (all `alert.freq_once_per_bar_close`):
1. BUY-LEADER entry
2. EARLY-BASE entry
3. Stage-Exit
4. RRG-Exit
5. Time-decay stop

**To wire alerts in TradingView:**
- Right-click chart → Add Alert
- Condition = `Commander ETF Strategy v1.1`
- Under "Alert actions" → select **"alert() function calls only"**

### Strategy properties

```pine
strategy(...,
  initial_capital            = 1,000,000,
  default_qty_type           = strategy.percent_of_equity,
  default_qty_value          = 10,
  pyramiding                 = 0,
  commission_type            = strategy.commission.percent,
  commission_value           = 0.03,   // 0.03% per side
  slippage                   = 2,       // 2 ticks
  calc_on_every_tick         = true,
  process_orders_on_close    = true,    // NSE EOD accuracy
)
```

---

## Trading Guide

### Setup before first run

1. **Pick the right Vol Profile** for the ETF you're loading
2. **Set the backtest window** to your testing horizon (or leave as default)
3. **Decide on EARLY-BASE** — leave OFF initially (more conservative)
4. **Set risk %** — 1.0% standard for ₹10L+ accounts; smaller accounts may want 0.5%

### How a single trade flows

1. **Setup detected** — SIGNAL turns BUY-LEADER (green tint on chart)
2. **Order placed** — strategy.entry fires at next bar close (process_orders_on_close=true)
3. **Position open** — Active SL appears as red line (initial = entry − ATR × stop_mult)
4. **CE ratchets up** as the trend extends — never down
5. **T1 hit (2.5R)** — 30% sold, T1_hit flag set, SL floors at breakeven
6. **Runner rides CE trail** until:
   - CE level breached (trailing stop hit)
   - Stage 4 entered (hard exit)
   - RRG flips to LAGGING (soft exit)
   - Time-decay stop (no 0.5R after 40 bars)
   - Liquidity collapse

### Vol Profile choice — practical guide

The Vol Profile drives both stop distance and position sizing. Pick by the ETF's typical character:

| ETF | Profile |
|---|---|
| NIFTYBEES, JUNIORBEES | Med |
| MID150BEES | Med (borderline High) |
| ITBEES, BANKBEES, PSUBNKBEES, METAL, REALTY | High |
| GOLDBEES, SILVERBEES, LIQUIDBEES, BBETF, GILT5YBEES | Low |
| MAFANG, MON100, NASDBEES, MASPTOP50, HNGSNGBEES | Intl |
| CPSEETF, INFRABEES, DEFENCE, MAKEINDIA, CONSUMBEES | High (treat like sector) |

**Wrong profile = wrong stop**: too tight on a volatile ETF whipsaws you out; too loose on a low-vol ETF wastes risk budget.

### Active SL — what it tells you

| State | Active SL display |
|---|---|
| Position just opened | Red line at entry - (ATR × stop_mult) |
| Trend extends | Red line ratchets up to track CE |
| T1 hit | Red line floors at breakeven (entry price) |
| Strong trend after T1 | Red line tracks CE above breakeven |

**Trade management rule:** never move the Active SL down manually. If you can't accept the system's stop, you sized too large.

### T1 partial — when it fires

- T1 target = entry + (initial_risk × 2.5R)
- When `high >= T1 target` and `not t1_hit yet`:
  - 30% of position sold at T1 target
  - `t1_hit` flag = true
  - SL floors at breakeven (locks in zero-loss minimum)
  - Remaining 70% rides the CE trail to whatever happens

The runner can ride to 5R, 8R, 10R+ in strong rotations. T1 just guarantees you don't give back the meat of the move.

### Time-decay stop — when it fires

- Only active before T1 hits (after T1, position is "free" and rides freely)
- If `bars_open >= time_stop_bars (40 default)` AND `unrealized_R < 0.5`:
  - Force close — position is dead weight
  - Frees capital for fresh setups

Defaults to 40 bars (~8 weeks for daily, longer for ETF advances which are slower than stocks).

### EARLY-BASE — when to enable

Leave OFF unless:
- You're systematic and can stomach more whipsaws
- You have data showing EARLY-BASE entries pay off in your specific ETF universe
- You're sized smaller (50% via `early_size`) per Stage-1 risk

Generally OFF is the default. Stage 2 + LEADING is where the bulk of alpha lives.

### Reading the mini dashboard

```
Header: ETFS v1.1     NIFTYBEES
SIGNAL: BUY-LEADER (green)
Position: 1200 sh @ 245.30
Active SL: 234.10 (CE)        ← Trailing
T1 Hit?: NO
Open P/L: +13,440 INR (green)
```

After T1:
```
Active SL: 245.30 (BE+CE)     ← Breakeven floor active
T1 Hit?: YES (BE locked)
Open P/L: +18,200 INR
```

### Common pitfalls

1. **Loading on a stock** — instrument guard blocks entries. Header turns red. Switch chart.
2. **Wrong Vol Profile** — Med profile on GOLDBEES = 2.5× too wide stop = qty too small to matter. Use Low.
3. **Disabling instrument guard "to test"** — defeats the purpose. Don't.
4. **Tightening time_stop to 15 bars** — ETFs trend slower than stocks. 40 default is right.
5. **Using on intraday timeframes** — Stage logic is daily/weekly. Strategy will fire wrong signals.

### Backtest interpretation

| Metric in TradingView Strategy Tester | Read as |
|---|---|
| Net Profit | Your INR return |
| Profit Factor | > 1.5 healthy, > 2.0 excellent |
| Max Drawdown | < 15% controlled, > 25% concerning |
| Win Rate | 50-70% normal for trend systems |
| Avg Trade | Should be 2-5R for an ETF rotation strategy |

### When to use this vs the Python backtest

| Question | Use |
|---|---|
| Backtest a single ETF | This Pine strategy |
| Backtest the full rotation system | `python etf_backtest.py` |
| Forward-test a setup | Pine alerts on this strategy |
| Generate institutional report | `python etf_backtest.py` + `summary.md` |

### Maintenance

- Quarterly: re-run on top 10 ETFs to verify metrics
- After threshold changes in `etf_config.json`: update Pine input defaults to match
- After universe edits: nothing required (strategy is per-symbol)
