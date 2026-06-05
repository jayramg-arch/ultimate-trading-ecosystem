# Recovery Screener v2.1 (Fundamentally-Gated, Pure Price Action) — User & Trading Guide

> **Module Role:** The **beaten-down-quality discovery engine.** Where the Bull Screener finds the market's leaders breaking out, the Recovery Screener finds **fundamentally strong companies that have been beaten down** and are showing the first signs of turning up. It is the regime-appropriate tool for corrective / recovering markets — exactly the kind of tape where the asymmetric opportunity lives.
>
> **Canonical implementation:** `recovery_screener.py` (Python — the only place the **full** fundamental filter runs). **Pine companion:** `Commander_Recovery_Screener_v2.0.pine` (capped to a 2-check "RFF Lite" by TradingView's 5-call `request.financial()` ceiling — see §8).

---

## 0. What Changed — the June 2026 Strengthening Pass

Driven by the directive *"for recovery, only pick fundamentally strong stocks that are beaten down — not any stock."* The screener had silently over-tightened (the recovery analog of the bull-catalyst blackout) and the fundamental gate was far too weak. All four issues fixed:

| Issue | Was | Now |
|---|---|---|
| **RFF fundamental gate too weak** | `rff_min_score = 1` (passed ~any non-bankrupt stock) | **4/6** — only genuinely strong companies; `INSUFFICIENT` (unverifiable) is blocked |
| **REV-CB starved** | drawdown ≥ 25% (only extreme crashes, ~2% of stocks) | **15–35% band** (quality on sale, not falling knives) → climax detection 10× |
| **REV-EARLY blackout** | fired 0 (over-specified breakout chain + a "confirmed-uptrend" gate that defeated *early*) | un-blackouted; **true early-bird** (breakout = the turn confirmation, not a lagging strict-trend) |
| **REV-RS underperforming** | 10-day-low stop (too tight for a 90-day hold → 62% stopped before the +9.84% runup) | **20-day-low structural stop** |

**Validated edge (24-month nifty500, 90-day windows):** recovery is **regime-appropriate** — positive matched alpha in **down/recovering tapes** (REV-CB **+1.72%**, REV-EARLY **+0.68%**), negative in up-tapes (you wouldn't run recovery in a bull market). This is the mirror image of swing-pullback: recovery *works* because the current regime is right for it.

---

## 1. What It Does

For each candidate it:
1. Computes the **market regime** (is the broad tape corrected / reclaiming?).
2. Computes the **RFF** (Recovery Fundamental Filter) — the hard fundamental-strength gate.
3. Evaluates three recovery **signals** (price-action only) in priority order.
4. Emits a Buy signal **only if** the technical signal fires AND `rff_ok` AND (for REV-CB) the regime is open.

---

## 2. The RFF — Fundamental Strength Hard Gate

> **This is the heart of the strategy: no RFF pass → no recovery signal, regardless of how good the bounce looks.**

### Tier A — base score (0–6), the hard gate
| Check | Threshold |
|---|---|
| Net Income > 0 | profitable (TTM) |
| Free Cash Flow > 0 | OCF − \|CapEx\| (TTM) |
| Interest Coverage > 3.5 | EBITDA / interest |
| Debt/Equity < 2 | not over-levered |
| Current Ratio > 1 | liquid |
| ROA > 5% | efficient |

**Gate:** `rff_ok` requires `RFF_Quality ≠ INSUFFICIENT` **and** `RFF_Base ≥ 4` (`rff_min_score`). At ≥4, a stock must be profitable with a sound balance sheet. A **data-sufficiency** rule (≥3 of 6 base fields populated) prevents NaN→0 from silently passing weak names.

### Tier B — turnaround bonus (0–4, Python-only)
Sales↑ · Profit↑ · Operating-leverage↑ · Deleveraging. Adds up to +4 to `RFF_Total` (0–10) for ranking; does **not** lower the Tier-A hard gate.

---

## 3. The Three Recovery Signals (pure price action)

Priority: **REV-EARLY (4) > REV-RS (3) > REV-CB-Buy (2) > CB-Watch (1)**. All Buy signals require `rff_ok`.

### REV-CB — Four-Pillar Climax Bottom Bounce
A genuine capitulation climax + reversal:
- **P1 Drawdown:** **15–35%** below the 60-bar high (the band — quality on sale, not a falling knife).
- **P2 Washout:** ≥5 of last 10 bars red AND close in the bottom 25% of the 10-day range.
- **P3 Climax Volume:** volume ≥ 2× 50-day avg AND close < open AND the widest range bar in N.
- **P4 Turn:** green bar, top 40% of range, breaks prior-day high (fires the Buy).
- SL = climax-zone low − 0.5 ATR · T1 = EMA20 · T2 = SMA200. Window **90 days**.

### REV-RS — RS-Survivor Structural Breakout
A relative-strength survivor that held up and breaks out:
- RS-positive + stock corrected (10–40%) + higher-low + confirmed strict-trend UP + **20-day-high breakout on ≥1.25× volume**.
- SL = **20-day low − 0.5 ATR** (widened — survives normal consolidation on a 90-day hold) · T1 = 2.5R · T2 = 52-week high.

### REV-EARLY — Early-Bird Trendline Reclaim
The earliest entry — catches the turn *before* the uptrend confirms:
- RS-positive + higher-low + **breakout (trendline reclaim OR 15-day high)** + base compression (NR7 or ≥3 inside bars) + volume ≥ 1.25× · vol-dry-up optional.
- **No strict-trend-UP requirement** (that gate is binary and made it *late*) — the **breakout itself is the turn confirmation**. False positives held down by the RS-positive + higher-low + breakout-above-resistance + compression + volume stack.
- SL = 20-day low − 0.5 ATR · T1 = 2.5R · T2 = 52-week high. Window 90 days.

---

## 4. The Market Regime Gate

`mkt_in_recovery = mkt_corrected OR mkt_reclaim`
- `mkt_corrected` = Nifty 500 ≥ 7% off its 52-week high.
- `mkt_reclaim` = Nifty 500 reclaimed its SMA50 within the last 30 bars.

REV-CB additionally requires `regime_ok`. This self-selects the right environment — recovery only opens when the broad tape is corrected/recovering (which is when it has edge).

---

## 5. Output Columns (`Recovery_Screener_Results.csv`)

`Symbol · Edge_Hint · Signal · Signal_Label · Signal_Date · Score · RFF_Base (0-6) · RFF_Bonus (0-4) · RFF_Total (0-10) · RFF_Quality (FULL/PARTIAL/INSUFFICIENT) · Weinstein_Stage · Mansfield_RS_x100 · RS_Momentum_4W · RRG_Quadrant · Entry · SL · T1 · T2 · RR_T1 · Details`

Per-signal Chartink lists: `Recovery_RS_Survivors.csv` (REV-RS) · `Recovery_Climax_Bounce.csv` (REV-CB) · `Recovery_Early_Birds.csv` (REV-EARLY).

---

## 6. How to Use

- **Trade off the Python screen, not Pine** — only Python runs the full RFF. The Pine RFF-Lite is an on-chart "is this not bleeding cash" sanity badge.
- **Use it when the regime is right** (corrected/recovering tape — your current market). The regime gate enforces this automatically.
- **Every pick is fundamentally strong** (RFF ≥ 4) — that's the guard against catching a falling knife in a junk stock.

---

## 7. Calibration Notes & Diagnostics

- **Don't over-tighten:** the pipeline has multiple layers (signal gate → matcher conviction → Top-N). Over-tight individual gates compound and starve the funnel. REV-CB's drawdown band and REV-EARLY's relaxations were calibrated against this.
- **Pillar funnels** (`_CB_FUNNEL`, `_EARLY_FUNNEL`) count per-gate pass rates — read them when a signal stops firing to find the collapsing gate (the tool that pinpointed every recovery fix this session).

---

## 8. Python ↔ Pine: an *intentional* asymmetry (not drift)

The full fundamental filter lives **only in Python** — TradingView's 5-call `request.financial()` ceiling limits the Pine Capitulation Screener to a 2-check **RFF-Lite** (NI>0 + OCF>0). This is a **platform constraint, not signal drift**: the technical recovery gates should match Python, but the fundamental filtering is authoritative in Python by design. Always source recovery *picks* from the Python output.
