# Mansfield RS — Auto Sector v1.4 — User & Trading Guide

> **Module Role:** A drop-in replacement for the community *Mansfield Relative Strength indicator* with one core upgrade — the **sector benchmark auto-detects per symbol**, so you never hand-edit the sector in the settings again. It plots two Mansfield RS curves (vs the **Index / Nifty 500** and vs the **auto-detected sector**), paints a **Stage × RS confluence background**, and prints a one-line **Stage · RRG · Sector** verdict label on the last bar.
>
> **File:** `Mansfield_RS_AutoSector_v1.4.pine` · **Type:** Indicator (separate pane) · **Pine:** v6 · **Market:** NSE/BSE · **Index benchmark:** `NSE:CNX500`.
>
> **Design contract (zero-drift by intent):**
> - The **auto-sector map** is the *same hybrid lookup* as **Dashboard v67.4.12** (664-row DB switch auto-generated from `sectors.db` by `sector_manager.py`, then keyword fallback).
> - The **Stage** read is `f_sec_stage_lite()` — **verbatim** from Dashboard v67.4.12 (weekly 30-WMA position × 4-week slope).
> - The **RRG quadrant** in the label uses `f_calc_rs_logic()` — **verbatim** from Dashboard v67.4.12 (Strike-matched 1-pass JdK RS-Ratio / RS-Momentum, `jdkLen=12`), computed on the weekly `SYM/INDEX` spread. Live-verified byte-identical to the v67 RRG panel cell.
> - This indicator **does not** re-derive Stage or RRG from RS levels — that would create a second, drifting definition. Stage stays price-vs-30WMA; RRG stays JdK.

---

## Version history

| Version | Added |
|---|---|
| **v1.0** | Auto-sector detection (DB + keyword hybrid) + Index & Sector Mansfield RS lines + zero-line fill + detected-sector label. Manual-override checkbox. |
| **v1.1** | *(superseded)* RS-regime background from a level × slope proxy — disagreed with the canonical JdK RRG, dropped. |
| **v1.2** | *(superseded as paint)* Canonical JdK RRG quadrant as a 4-colour background. Correct, but the weekly-JdK stripes read as visually disconnected from the daily lines. |
| **v1.3** | *(superseded)* Simple RS-sign background (green above zero / red below) + RRG shown as text. Too thin. |
| **v1.4** | **Stage × RS confluence background** (the current design) + full **Stage · RRG · Sector** label. Purple weak-leadership colour (was amber — too close to Stage-3 orange). |

---

# PART A — USER GUIDE

## 1. What it does (in one breath)

For the symbol on the chart it:
1. **Auto-detects the sector** (e.g. `NETWEB → NSE:CNXIT`, `CAPLIPOINT → NSE:CNXPHARMA`) with no manual input.
2. Plots **two Mansfield RS lines** — vs Nifty 500 (blue) and vs that sector (orange).
3. Paints a **background** that fuses the canonical weekly **Weinstein Stage** with the **sign of the Index RS** — five distinct states.
4. Prints a **last-bar label** reading e.g. `✅ STAGE 2 (Bull) · RRG: LEADING · Sector: CNXPHARMA (DB)`.

The two questions it answers at a glance: *"What stage is this in?"* (background) and *"Is it a leader while doing it — vs the market AND its peers?"* (the two lines + RRG).

## 2. Installation

1. **Prerequisite (once):** the sector DB block inside the file is auto-generated. If tickers are missing or you've updated `sectors.db`, refresh it from the project root:
   ```
   python sector_manager.py export-pine "Mansfield_RS_AutoSector_v1.4.pine"
   ```
   This rewrites the `<DB_LOOKUP_START>…<DB_LOOKUP_END>` block (664 rows at last export, full Nifty 500 coverage) and writes a `.bak` backup.
2. In TradingView: **Pine Editor → paste the file → Save → Add to chart**. It opens in its **own pane** below price (it is not an overlay).
3. Confirm the **Index** input is `NSE:CNX500` (the ecosystem's canonical breadth benchmark).
4. Leave **Manual Sector Override** unchecked — auto-detect is the whole point.
5. (Optional) Stack it below **Dashboard v67** so the RS pane's Stage background lines up block-for-block with v67's price-pane Stage background.

## 3. Inputs — field by field

### 3.1 Benchmarks
| Input | Default | Meaning / values |
|---|---|---|
| **Index** | `NSE:CNX500` | The broad-market benchmark for the **blue Index RS line** and for the **RRG quadrant** calc. Keep it `CNX500` (Nifty 500) to stay consistent with the rest of the ecosystem. |
| **[Enable] Manual Sector Override** | ✗ (off) | When **on**, the sector benchmark is forced to *Manual Sector* below and auto-detection is bypassed. Use only for an off-list symbol the mapper gets wrong, or to compare against a custom index. |
| **Manual Sector** | `NSE:CNX500` | The sector symbol used **only** when the override is on. |
| **Plot Sector RS** | ✓ (on) | Toggles the **orange Sector RS line**. Turn off if you want a pure vs-Nifty-500 view. Auto-suppressed anyway when the sector resolves to the Index itself (see §4.1). |

### 3.2 Moving Average (the Mansfield normalisation MA)
These are identical to the original indicator's defaults — the MA length auto-selects by the chart's timeframe.

| Input | Default | Meaning |
|---|---|---|
| **Which moving average to use?** | `SMA` | `SMA` or `EMA` for the RS-ratio smoothing baseline. SMA = the classic Mansfield. |
| **MA length for Daily** | 200 | MA length applied when the chart is on the **Daily** timeframe. |
| **MA length for Weekly** | 26 | MA length on the **Weekly** timeframe (26 weeks = ~6 months, the classic Mansfield weekly). |
| **MA length for Monthly** | 10 | MA length on the **Monthly** timeframe. |
| **MA length for all other periods** | 52 | Fallback MA length for every other timeframe (intraday, 2-day, etc.). |

> **Note:** the two *plotted* RS lines use the **chart-timeframe** MA above. The **background Stage** and the **label RRG** are always computed on the **Weekly** timeframe regardless of chart TF (see §4.3–4.4), so those two reads never change when you flip the chart between Daily and 125-min.

### 3.3 Display
| Input | Default | Meaning |
|---|---|---|
| **Show detected-sector label** | ✓ | Toggles the last-bar label (Stage · RRG · Sector · detection source). |
| **Index RS** (colour) | blue `#2962ff` | Colour of the vs-Nifty-500 line. |
| **Sector RS** (colour) | orange `#ff9800` | Colour of the vs-sector line. |

### 3.4 Background — Stage × RS confluence
| Input | Default | Meaning |
|---|---|---|
| **Stage × RS background** | ✓ | Master toggle for the background paint. |
| **S2 + RS+** | teal-green `#26a69a` | Stage 2 **and** Index RS > 0 → full confluence. |
| **S2 + RS−** | purple `#ab47bc` | Stage 2 **but** Index RS ≤ 0 → weak leadership (purple, deliberately distinct from Stage-3 orange). |
| **Stage 1** | faint yellow `#ffee58` | Basing. |
| **Stage 3** | orange `#ff9800` | Topping. |
| **Stage 4** | red `#ef5350` | Declining. |

### 3.5 RRG label (canonical JdK, weekly — v67 parity)
| Input | Default | Meaning |
|---|---|---|
| **JdK RRG Length** | 12 | Normalisation length for the JdK RS-Ratio / RS-Momentum. **12** matches v67 / Unified Ecosystem (Strike-matched, 1-pass + 5-bar smooth). **Keep in sync with the dashboard** — changing it here breaks label↔dashboard parity. |
| **RRG Trajectory Tail (Weeks)** | 4 | How many weeks back the RRG rotation vector is measured. Standard tail = 4. (Reserved for trajectory use; the v1.4 label prints the current quadrant.) |

## 4. How it works (the logic)

### 4.1 Auto-sector detection — 3-tier hybrid (mirrors Dashboard v67)
Resolved in this order; first hit wins:
1. **DB lookup** (`f_db_sector_lookup`) — the auto-generated 664-row switch on the cleaned ticker (`NSE:`/`BSE:` stripped, upper-cased). Highest accuracy; full Nifty 500 coverage. Example rows: `NETWEB → NSE:CNXIT`, `RELIANCE → NSE:CNXENERGY`, `CAPLIPOINT → NSE:CNXPHARMA`.
2. **Keyword fallback** (`f_get_sector_ticker`) — for off-list tickers, maps TradingView's `syminfo.sector` / `syminfo.industry` metadata to an index (e.g. contains "Pharma" → `NSE:CNXPHARMA`, "Bank"/"Finance" → `NSE:BANKNIFTY`).
3. **Default** — `NSE:CNX500` if neither resolves.

The label's parenthetical tags the source: **`(DB)`**, **`(keyword)`**, or **`(manual)`**.

> If the resolved sector equals the Index (e.g. a symbol that maps to CNX500), the **Sector line is auto-suppressed** — plotting RS-vs-itself is meaningless. The label then reads "… — not plotted".

### 4.2 Mansfield RS formula (the two plotted lines)
Identical to the original indicator:
```
RP  = close / benchmark_close          (the price ratio / spread)
MRS = (RP / MA(RP, len) − 1) × 100      (deviation from its own MA, in %)
```
- `MA` = SMA or EMA per §3.2; `len` = the timeframe-selected length.
- **> 0** = the stock is outperforming that benchmark relative to its own recent norm; **< 0** = underperforming.
- The benchmark close is pulled via `request.security` with `lookahead_off` (no repaint bias).

### 4.3 Stage read (drives the background) — `f_sec_stage_lite`, verbatim from v67
Computed on the **Weekly** timeframe on the symbol itself:
```
ma30  = SMA(weekly close, 30)           (the 30-week MA — Weinstein anchor)
slope = ma30 − ma30[4]                   (4-week slope)

close > ma30 & slope > 0   → STAGE 2 (Bull)
close > ma30 & slope ≤ 0   → STAGE 3 (Top)
close < ma30 & slope < 0   → STAGE 4 (Bear)
otherwise                  → STAGE 1 (Base)
```
This is the **canonical price-vs-30WMA** definition — the same one v67 paints on the price pane.

### 4.4 RRG quadrant (drives the label) — `f_calc_rs_logic`, verbatim from v67
Computed on the **Weekly** `SYM / INDEX` spread with the JdK method (`jdkLen=12`, 5-bar smooth, centred so >0 keeps its meaning). The quadrant is:
```
RS-Ratio ≥ 0 & RS-Momentum ≥ 0 → LEADING
RS-Ratio ≥ 0 & RS-Momentum < 0 → WEAKENING
RS-Ratio < 0 & RS-Momentum ≥ 0 → IMPROVING
RS-Ratio < 0 & RS-Momentum < 0 → LAGGING
```
Because the formula and inputs are byte-identical to v67, **this label always matches the RRG cell in the v67 panel** on the same bar (live-verified on CAPLIPOINT: label `RRG: LEADING` = panel `RRG (vs N500) | LEADING`).

## 5. The colour scheme (read this once)

The background is a **5-state Stage × RS map**. Only **Stage 2** splits on RS (leadership matters most when the trend qualifies); Stages 1/3/4 use the v67 colour vocabulary directly.

| Background | Condition | What it means |
|---|---|---|
| 🟢 **Green** | Stage 2 + Index RS > 0 | **Full confluence** — advancing *and* outperforming the market. The buy context. |
| 🟣 **Purple** | Stage 2 + Index RS ≤ 0 | **Weak leadership** — trend intact but lagging the market. Caution / not a fresh-buy. |
| 🟡 **Yellow** (faint) | Stage 1 | **Basing** — watch for the breakout, not yet actionable. |
| 🟧 **Orange** | Stage 3 | **Topping** — tighten, don't add. |
| 🔴 **Red** | Stage 4 | **Declining** — exit / no-touch. |

The two **lines** add the peer-group dimension the background can't: **blue** = vs Nifty 500, **orange** = vs sector. All five colours + the two line colours are editable (§3.3–3.4).

> **Edge case:** during the Mansfield MA warm-up (first ~200 daily bars of a fresh listing) the RS value is `na`, so early Stage-2 bars paint **purple** (conservative) until the RS line is valid.

## 6. The label (the one-line brief)

On the last bar (when *Show detected-sector label* is on):
```
✅ STAGE 2 (Bull) · RRG: LEADING · Sector: CNXPHARMA (DB)
```
- **Stage token** — from §4.3.
- **RRG token** — from §4.4 (v67-parity quadrant).
- **Sector + source** — the auto-detected sector and how it was found (`DB` / `keyword` / `manual`).

---

# PART B — TRADING GUIDE

> This indicator's job in the workflow is **RS leadership confirmation**, layered on top of the Stage read. It does **not** generate entries — the Dashboard v67, the screeners, and your hand-drawn zones do. Use it as the fast "is this a leader?" filter and as the RS-context pane while you work a chart.

## 1. Where it sits in the funnel

Per the DNA "lead with Stage + RS" rule:
1. **Stage** (background) — is it even in an advance? (Only Stage 2 is buyable.)
2. **RS vs market** (blue line / RRG) — is it leading the Nifty 500?
3. **RS vs sector** (orange line) — is it leading *within its own group*?

A stock that clears all three (green background + both lines rising above zero + RRG LEADING) is a **true leader** — the Minervini/Weinstein ideal. This tool makes that three-part check a one-glance read.

## 2. The confluence playbook (by background)

| Background | RRG (label) | Read & action |
|---|---|---|
| 🟢 Green | LEADING | **A-grade.** Stage 2, leading the market. Proceed to your entry checklist (location, trigger, size). |
| 🟢 Green | WEAKENING | Stage 2, still positive but **momentum rolling** — leadership fading. Manage existing longs tighter; be pickier on new adds. |
| 🟣 Purple | LAGGING / IMPROVING | Stage 2 **but lagging the market.** Not a fresh-buy. If IMPROVING, it may be an early turn — watch, don't chase. |
| 🟡 Yellow | IMPROVING | **EarlyBird watch.** Basing *and* RS turning up before price confirms — the classic pre-Stage-2 setup. Alert, don't buy yet. |
| 🟡 Yellow | LAGGING | Basing with no RS interest — leave it alone. |
| 🟧 Orange | any | **Topping.** No new longs; trail/exit existing per your stop rules. |
| 🔴 Red | any | **Declining.** No-touch. Exit confluence. |

## 3. Reading the two lines together

- **Both above zero, both rising** = leading the market *and* its sector — strongest state. The clean "true leader."
- **Blue up, orange flat/down** = beating the market but only *average within a hot sector* — the sector is doing the work; there may be a stronger name in the same group. Compare peers.
- **Orange up, blue flat/down** = leading its sector but the sector itself lags the market — sector-relative winner in a weak group; size down or wait for the group to turn (check sector Stage on v67).
- **Both below zero** = a laggard on both counts — the background will already be purple (if Stage 2) or a lower-stage colour.

## 4. The purple warning — the single most useful signal

Purple = **Stage 2 with negative market RS**. This is your DNA's *"Stage 2 (Weak Leadership)"* flagged visually. A trend that isn't leading is the one that fails first in a correction. On a held position, purple is a prompt to:
- tighten the stop (per your ATR-trail rules),
- stop adding,
- and rank it against greener alternatives in the Sell-to-Buy rotation.

## 5. Multi-timeframe use

- **Daily chart** — the lines use the 200-day MA; use it for day-to-day RS tracking. Background/label stay weekly (stable).
- **Weekly chart** — the lines use the 26-week MA (canonical Mansfield). This is the cleanest RS-leadership read for positional decisions.
- The **background and RRG never change** between Daily and intraday charts (both weekly-anchored), so you get a consistent Stage/RRG context on any TF you happen to be working.

## 6. Cross-checks (parity discipline)

- The **RRG label must equal the v67 panel's RRG cell** on the same bar. If it ever diverges, that's a bug (or a mismatched `JdK RRG Length` input) — not a tuning choice. Keep `jdkLength = 12` and `Index = NSE:CNX500`.
- The **background Stage must match v67's price-pane Stage background** block-for-block. Stack the two and confirm on any symbol.
- After editing `sectors.db`, **re-export the DB block** (§2) so the auto-sector map stays in sync with v67.

## 7. What it deliberately does NOT do

- It does **not** infer Stage from RS levels (that would be a second stage definition — forbidden by the zero-drift rule).
- It does **not** paint the JdK RRG quadrant as a background (tried in v1.2; the weekly-JdK stripes read as disconnected from the daily lines — demoted to the label).
- It does **not** produce entries, stops, or targets — that's the screeners / Risk Allocator / your hand-drawn zones.

---

*Guide generated from `Mansfield_RS_AutoSector_v1.4.pine`. Auto-sector map, Stage read, and RRG calc are verbatim ports from Dashboard v67.4.12 — refresh the DB block via `sector_manager.py export-pine` whenever `sectors.db` changes.*
