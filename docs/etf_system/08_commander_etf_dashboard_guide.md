# 08 — Commander ETF Dashboard v1.2 Guide (Pine)

> **Module role:** On-chart confluence dashboard for NSE ETFs. Mirrors the Python screener exactly (zero drift). Adds visual layer for stage-at-a-glance trading.
> **Phase:** Phase 3 of the ETF system.
> **Lines:** ~370 (Pine v6).
> **File:** `Commander_ETF_Dashboard_v1.0.pine` (title: v1.2).

---

## What it adds to the system

The Python screener gives you a daily ranked CSV. The dashboard gives you:

1. **Real-time on-chart confluence** — same signals as the CSV but updating tick by tick
2. **Visual stage indicator** — background tint by Weinstein stage
3. **Chandelier Exit preview line** — where a stop would sit if you entered now
4. **Sized Qty preview** — what 1% risk sizing produces for this specific ETF

Per CLAUDE.md zero-drift rule: paste any ETF on TradingView + run `python etf_screener.py` → SIGNAL field must match.

---

## User Guide

### Loading on a chart

1. Open TradingView → load any NSE ETF chart (NIFTYBEES, BANKBEES, GOLDBEES, etc.)
2. Indicators → search "Commander ETF Dashboard v1.2" → add
3. Default benchmark `NSE:CNX500` (Nifty 500) — change to `NIFTY` for large-cap-only comparisons

### Inputs (8 groups)

#### Benchmark & RS

| Input | Default | Purpose |
|---|---|---|
| RS Benchmark | NSE:CNX500 | Denominator for Mansfield RS |
| Mansfield SMA Length | 200 | Textbook; lower = more reactive |
| RS-Momentum Lookback (bars) | 20 | ≈ 4 weeks for RRG quadrant |

#### Trend & Stage

| Input | Default | Purpose |
|---|---|---|
| Show 30W MA | true | Weekly Weinstein anchor overlay |
| Show 200-day SMA | true | Daily proxy |
| Show 50-day SMA | false | Optional |

#### Stage Background (NEW v1.1)

| Input | Default |
|---|---|
| Tint chart background by stage | true |

Green tint = Stage 2 / amber = Stage 1 / orange = Stage 3 / red = Stage 4.

#### ATR & CE Preview (NEW v1.1)

| Input | Default | Used for |
|---|---|---|
| ATR Length | 14 | Sizing + CE |
| Initial Stop ATR Mult | 2.5 | Stop distance |
| CE Lookback | 22 | Chandelier Exit window |
| CE ATR Multiplier | 3.0 | Trail distance |

#### Sized Qty Preview (NEW v1.1)

| Input | Default | Purpose |
|---|---|---|
| Account Capital (Rs) | 1,000,000 | Drives qty preview |
| Risk per Trade (%) | 1.0 | Risk budget |
| Vol-discount sizing | true | Shrinks qty for high-ATR ETFs |
| Target ATR pct | 1.5 | Vol-disc baseline |

#### Liquidity

| Input | Default | Purpose |
|---|---|---|
| Liquidity Lookback | 60 | 60-day median turnover window |
| Min Median Turnover Rs Cr/day | 2.0 | ILLIQUID threshold |

#### Dashboard

| Input | Default |
|---|---|
| Show table | true |
| Position | top_right |
| Text size | small |

### Dashboard table (19 rows in v1.2)

| Row | Cell | What |
|---|---|---|
| 0 | Header | "ETF DASH v1.2" + ticker (red bg if not a fund) |
| 1 | SIGNAL | BUY-LEADER / ACCUMULATE / EARLY-BASE / PRE-S2 WARN / HOLD-WATCH / NEUTRAL / ILLIQUID / AVOID / NOT AN ETF |
| 2 | Stage | 1 BASE / 2 ADVANCE / 3 TOP / 4 DECLINE / INSUFFICIENT |
| 3 | RRG Quadrant | LEADING / IMPROVING / WEAKENING / LAGGING |
| 4 | Mansfield RS | Value + (mom 4W) |
| 5 | vs 30W MA | Distance % |
| 6 | vs 200 DMA | Distance % |
| 7 | 200DMA Slope | % over 20D |
| 8 | vs 52W High | Distance % (green if within 3%, amber within 10%, red beyond) |
| 9 | Liquidity | Turnover ₹Cr/day + tier label |
| 10 | Liq Score | x / 10 |
| **11** | **Total Score** | **NEW v1.2: x / 40 + axis breakdown (T7 R8 Ro7 L6)** |
| **12** | **Grade** | **NEW v1.2: A+/A/B/C/D** |
| 13 | Rel Volume | Today vs 50D avg (×) |
| 14 | ATR (14) | Absolute + % of price |
| 15 | CE Trail (preview) | Price + distance from close |
| 16 | Sized Qty (1%) | Shares + vol-disc % |
| 17 | Last Bar | IST timestamp |
| 18 | Bench | Active benchmark symbol |

### Data window pins (12 numeric fields)

For the standalone TradingView screener:
- Stage (1-4)
- Mansfield RS
- RS Momentum 4W
- Liquidity Score 0-10
- Turnover RsCr/day
- Dist 200DMA %
- Dist 52WH %
- 200DMA Slope %
- Is ETF (1/0)
- **Trend Score 0-10** (v1.2)
- **RS Score 0-10** (v1.2)
- **Rotation Score 0-10** (v1.2)
- **Total Score 0-40** (v1.2)

### Alerts (4 conditions)

1. **ETF entered Stage 2** — Weinstein breakout
2. **ETF flipped to LEADING quadrant** — RRG rotation in
3. **ETF BUY-LEADER signal** — Stage 2 + LEADING + liquid (highest conviction)
4. **ETF entered Stage 4** — exit signal

### Plots on chart

- 30W MA (amber, linewidth 2) — Weinstein anchor
- 200-day SMA (blue, linewidth 2)
- 50-day SMA (grey, linewidth 1, off by default)
- Stage background tint
- CE Trail preview (fuchsia step-line)

---

## Trading Guide

### Pre-trade checklist (use dashboard to verify)

Before clicking BUY on any ETF:

| Check | Required value |
|---|---|
| Header bg | Blue (= it's a fund) — NOT red |
| SIGNAL | BUY-LEADER (preferred) or ACCUMULATE |
| Stage | 2 ADVANCE (green tint visible behind candles) |
| RRG Quadrant | LEADING or IMPROVING |
| Mansfield RS | Positive value |
| Liquidity | ≥ ₹2 Cr/day, score ≥ 6 |
| Total Score | ≥ 26 (A grade) |
| vs 52W High | Better than −10% |
| CE Trail | Already meaningfully below close (room to ride) |

### Reading the signal at a glance

- 🟢 **BUY-LEADER** — all four axes green. Highest conviction. Strategy fires.
- 🟡 **ACCUMULATE** — Stage 2 + RRG IMPROVING. Stage 2 isn't confirmed by full LEADING yet. Half-size.
- 🟠 **HOLD-WATCH** — Stage 2 but rotation weakening. Don't add. Trim if held.
- 🟡 **EARLY-BASE** — Stage 1 + IMPROVING. Speculative; only if strategy `allow_early=true`.
- 🟡 **PRE-S2 WARN** — Stage 1 + RS momentum positive. *Not* a trade signal — flags potential rotation IN before any actual entry.
- 🔴 **AVOID-DOWNTREND** — Stage 4. Sell or skip.
- ⚠ **ILLIQUID** — turnover < ₹2Cr/day. Skip regardless of other axes.
- ⚪ **NEUTRAL** — no clear setup.

### Using Total Score / Grade

| Grade | Score | When to act |
|---|---|---|
| *** A+ | 32-40 | Top conviction — eligible for full strategy size |
| ** A | 26-31 | Strong — start partial size, wait for A+ promotion |
| * B | 20-25 | Watchlist — not yet a trade |
| C | 14-19 | Skip |
| D | < 14 | Avoid |

### CE Trail preview line — how to use

The fuchsia step-line on the chart shows where a Chandelier Exit (22-bar high - 3×ATR) would sit if you were in a long trade.

**As an entry filter:** If the CE line is *above* current close, the ETF is structurally in trouble — don't enter even if SIGNAL says ACCUMULATE.

**As a stop preview:** If you enter today, your initial stop would be roughly where the CE line is. If that distance is more than 8-10% from your entry, the position is too risky for 1% risk sizing — qty would be tiny and slippage would eat the trade.

### Sized Qty preview — how to use

Reads: `1200 sh (vol-disc 75%)` means:
- At 1% risk on ₹10L capital
- With ATR-based stop distance
- Vol-disc scaled by 75% (because ATR% > target)
- Buy 1200 shares = ₹X position

If the qty preview is very small (< ₹50k position size on a ₹10L account), the ETF is too volatile to size meaningfully. Consider a lower-vol alternative.

### Stage background colour quick read

- **Solid green** = Stage 2, ride the trend
- **Amber** = Stage 1, basing — early-base candidates
- **Orange** = Stage 3, distribution — exit longs
- **Red** = Stage 4, decline — avoid / short (if you do that)
- **No tint** = data insufficient or transition

### Common pitfalls

1. **Loading on a stock** — header turns red. SIGNAL says NOT AN ETF. **Stop and switch chart.**
2. **PRE-S2 WARN ≠ buy** — it's a watchlist nudge. Wait for actual Stage 2.
3. **Using on intraday charts** — the Stage logic is daily/weekly. Intraday TF shows the same signal but it lags the proper bar close.
4. **Ignoring the bench** — if your benchmark input is NIFTY but you're in a sectoral ETF, RS will look strong artificially. Use CNX500 for cross-sector comparability.

### Version differences

| Version | Key change |
|---|---|
| v1.0 | Initial release (Phase 3 of ETF system) |
| v1.1 | Stage bgcolor + CE Trail + ATR + Sized Qty rows + PRE-S2 warn signal |
| v1.2 | Total_Score + Grade rows + axis breakdown + 4 new data window pins |

### Cross-platform verification

Once a quarter (or after any threshold edit), confirm zero drift:
```bash
python etf_validate.py
# Manually export Pine data window for 5-10 ETFs into pine_export.csv
python etf_validate.py --compare pine_export.csv
```
