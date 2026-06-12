# Commander Chart Markup v2.0 — User & Trading Guide

> **Module Role:** A self-contained, **timeframe-agnostic chart-reading engine**. Drop it on any NSE symbol (or any timeframe, or use it in the TV screener) and it auto-detects the structure — Weinstein Stage, Mansfield RS, trendlines, channels/wedges, support/resistance, gaps, classical patterns, anchored VWAP, Fibonacci — and renders a **decision-brief panel + descriptive annotations**. It is the *breadth scanner* of the markup workflow; you hand-draw the one tradeable trendline (see §Trading Guide).
>
> **File:** `Commander_Chart_Markup_v2.0.pine` · **Type:** Indicator (overlay) · **Pine:** v6 · **Market:** NSE/BSE (any), benchmark `NSE:CNX500`.
>
> **Design contract:** RS and Stage reuse the same maths as the Mansfield RS pane and the Unified Ecosystem; AVWAP is ported from **Dashboard v67.4.12**; Fib from **Zigzag [Strict v6.2]** — zero-drift by intent, the other tools untouched.

---

## Version history
| Version | Added |
|---|---|
| **v1.0** | Stage + Mansfield RS + auto trendlines (touch-validated, non-pierced) + geometry/apex + gaps + 52W levels + verdict panel |
| **v1.1** | Classical patterns (S/R zones, flags, double/triple top & bottom) |
| **v1.2** | Head & Shoulders (+ inverse) and Cup & Handle as **candidates** (heuristic tier) |
| **v1.3** | **Anchored VWAP** (Dashboard port) + **Fibonacci** retrace/extension (Zigzag port); S/R min-touch input |
| **v1.4** | Panel reorganised into a **decision brief**: conviction score, RS trend arrow, bars-in-stage, auto nearest support/resistance, computed Entry/Stop/Target |
| **v1.5** | **Descriptive annotations** — full-sentence notes at Resistance / Support / AVWAP (the MCP narrative voice, native). Headline omitted (that read lives in the panel) |
| **v1.6** | **Selectable colors** (new "Colors" input group for every drawn element); auto **trendlines no longer extend rightwards** (drawn only to the current bar) |
| **v1.7** | **Timeframe-adaptive pivot length** — ported from Zigzag [Strict v6.2] (Monthly 1 · Weekly 5 · Daily 2 · Intraday 2), replacing the flat "8". Four tunable inputs |
| **v1.8** | **Trendline close-respect rule** — a line is accepted only if no candle *closed* beyond it (above resistance / below support) within tolerance. Toggle "reject if a candle closes through it" |
| **v1.9** | **Trendline recency bias** — selection scores touches + a bonus for how recent the anchor is, so it prefers lines connecting recent pivots over long lines reaching far back. Tunable (0 = most-touched) |
| **v2.0** | **EMA20 confluence + ideal-angle biases** in line selection; **EMA20 plotted & timeframe-aware** (Monthly→M · Weekly→W · Daily & intraday 125/75-min→D, per the DNA spec). EMA20 confluence = line touches the EMA20 near CMP (break together) + parallel travel |

---

# PART A — USER GUIDE

## 1. What it does (the 4-stage pipeline)
1. **Detect** — swing pivots (`ta.pivothigh/low`), breakaway gaps (gap% + volume), rolling 52-week extremes.
2. **Classify** — Weinstein **Stage** (weekly 30-WMA anchor) and **Mansfield RS** vs Nifty 500 (TF-aware).
3. **Annotate** — best-fit **trendlines** (touch-validated, non-pierced), **geometry** (channel/wedge/triangle), **S/R zones**, **classical patterns**, **AVWAP** curve, **Fibonacci** levels.
4. **Verdict** — a panel + descriptive labels giving setup, conviction, nearest levels, and a computed trade plan.

## 2. Installation
1. Add to any chart. Defaults are tuned for **daily**; scale pivot inputs up on intraday / down on weekly (see §3.1).
2. Confirm the benchmark is correct (`NSE:CNX500`) for RS.
3. For a deep-dive chart, keep it **alone** (other heavy studies clutter the canvas). For screening, leave it on and read the panel/data-window.

## 3. Inputs — field by field

### 3.1 Detection
| Input | Default | Meaning / values |
|---|---|---|
| **Monthly / Weekly / Daily / Intraday pivot length** (v1.7) | 1 / 5 / 2 / 2 | Bars each side that define a swing pivot, **resolved by the chart's timeframe** — ported from Zigzag [Strict v6.2] so pivots stay in sync with the swing engine. Lower = more/finer pivots; raise *Daily* (4–6) for cleaner markup trendlines. |
| **Pivots tracked per side** | 12 | How many recent pivot highs/lows are held in memory for fitting. |
| **Trendline: fit only last N pivots** | 5 | The trendline searches **only the last N pivots** so it hugs current price (not a year-old anchor). Lower (3–4) = tighter to CMP / steeper recent leg; higher = longer, shallower base. **This is your "drag substitute"** — tune N to slide the line's anchor along the swing structure (every result is still touch-validated + unbroken). |
| **Min touches for a VALID trendline** | 3 | ≥ this many touches → solid "VALID" line; exactly 2 → dashed "prov." (provisional). |
| **Touch tolerance (× ATR14)** | 0.7 | How close a pivot must be to the line to count as a touch. Also the allowance for the close-respect rule. |
| **Trendline: reject if a candle CLOSES through it** (v1.8) | ✓ | Classical valid-trendline test — only accept a line if **no candle in its span closed beyond it** (above resistance / below support) within the touch tolerance. Off = pivots-only validation. |
| **Trendline recency bias** (v1.9) | 1.0 | Prefers lines anchored on **recent** pivots over long lines reaching far back. 0 = pick the most-touched line regardless of age; higher = each pivot of recency outweighs that many touches. |
| **Trendline EMA20-confluence bias** (v2.0) | 1.0 | Rewards lines that **touch the EMA20 near CMP** (so a break of the line coincides with a break of the EMA20) **and** travel parallel with it (70% proximity-at-CMP + 30% slope-match). 0 = off. |
| **Trendline ideal-angle bias / target slope** (v2.0) | — | Nudges the line toward a balanced ~45°-feel slope (an `ideal slope ≈ K × ATR` per bar) — avoids near-flat or near-vertical fits. 0 = off. |
| **Breakaway gap % min** | 4.0 | Minimum overnight gap to flag a breakaway. |
| **Gap volume × avg min** | 2.0 | Gap must come on ≥ this × the 50-bar average volume. |

### 3.2 Context
| Input | Default | Meaning |
|---|---|---|
| **RS Benchmark** | `NSE:CNX500` | Index for Mansfield RS (Nifty 500). |
| **Mansfield RS MA length** | 52 | Lookback for the RS ratio's moving average (52 = ~1y on daily). |
| **'At highs' threshold (% from 52WH)** | 3.0 | Within this % of the 52-week high → setup reads "Stage 2 at highs". |
| **'Pullback to MA' band (× ATR)** | 1.5 | Price within this ATR-band of the 50-MA → setup reads "SWG-PB (pullback to MA)". |

### 3.3 Visuals
| Input | Default | Toggles |
|---|---|---|
| Auto trendlines + geometry | ✓ | the two best-fit lines + geometry classification |
| Apex marker (converging lines) | ✓ | dotted vertical + label where the lines cross |
| 52W High / Low levels | ✓ | purple (high) / gray (low) dotted lines |
| Breakaway-gap markers | ✓ | green ▲ below / red ▼ above the gap bar |
| Stage MAs (50/150/200) | ✓ | orange / blue / gray MAs |
| **EMA20 (TF-aware)** (v2.0) | ✓ | the EMA20 the confluence bias rides — Monthly→M · Weekly→W · Daily & intraday 125/75-min→**Daily** EMA20 (via `request.security`, per the DNA spec). On intraday it renders as a stepped daily line |
| Verdict panel | ✓ | the decision-brief table |
| **Descriptive annotations** | ✓ | the full-sentence notes at Resistance / Support / AVWAP |
| Panel position | Top Right | 5 positions |

### 3.4 Classical Patterns
| Input | Default | Meaning |
|---|---|---|
| Support/Resistance zones | ✓ | horizontal levels from pivot clustering |
| S/R cluster tolerance (× ATR) | 0.6 | how close pivots must be to form one zone |
| **S/R min touches** | 2 | a zone needs ≥ this many pivot touches to draw |
| Flags | ✓ | impulse leg + tight consolidation box |
| Flag consolidation / impulse bars | 6 / 10 | window sizes |
| Flag impulse size (× ATR) | 4.0 | minimum impulse leg |
| Flag consolidation max (× ATR) | 2.5 | maximum consolidation range (tightness) |
| Double / Triple Top & Bottom | ✓ | equal pivots + neckline, "✓break" on neckline break |
| Equal-pivot tolerance (× ATR) | 0.5 | how equal the tops/bottoms must be |

### 3.5 Batch 2 — heuristic CANDIDATES (false-positive-prone)
| Input | Default | Meaning |
|---|---|---|
| Head & Shoulders (+ inverse) | ✓ | 3-pivot H&S; neckline; `(cand)` → `✓break` |
| H&S shoulder symmetry tol (× ATR) | 0.9 | how equal the shoulders must be |
| Cup & Handle | ✓ | two rims ~level + rounded low + shallow handle |
| Cup depth min / max % | 12 / 50 | valid cup depth band |

> These are **eyeball candidates**, labelled `(cand)`. Turn them off if they flicker on choppy names.

### 3.6 Anchored VWAP (ported from Dashboard v67.4.12)
| Input | Default | Meaning |
|---|---|---|
| Anchored VWAP (curve) | ✓ | the real evolving AVWAP curve (orange) |
| Use manual anchor date instead | off | override the auto anchor |
| Manual anchor | 01 Jan 2026 | the manual anchor timestamp |

**Auto anchor = the current Stage-2 start** (`hlc3 × volume` cumulative from there), exactly the Dashboard's logic — the cost basis of the *whole* current Stage 2.

### 3.7 Fibonacci (ported from Zigzag v6.2)
| Input | Default | Meaning |
|---|---|---|
| Fib retrace 50% & 61.8% | ✓ | `high − r×range` (purple / orange) |
| Fib ext 1.272 & 1.618 (targets) | ✓ | `low + r×range` (teal / lime) |
| Fib swing lookback (bars) | 120 | dominant swing = highest-high & lowest-low over this window |
| Fib line extend (bars right) | 15 | how far the fib lines project right |

## 4. The verdict panel — row by row
The panel is a **decision brief** in four sections (STATE · LEVELS · PLAN · VERDICT).

| Row | Field | Possible values / format |
|---|---|---|
| 0 | Header | `◧ MARKUP` · `SYMBOL · TF` |
| 1 | **Stage** | `Stage 2 ✓` / `Stage 1` / `Stage 3 ⚠` / `Stage 4 ✗` · `Nb` (bars in stage). Colour: green/yellow/orange/red |
| 2 | **RS (Mansfield)** | e.g. `+15.6 ↑ leads` — value + trend arrow (↑ rising / ↓ falling) + `leads` (>0, green) / `lags` (<0, red) |
| 3 | **Setup** | see §5 — STAGE 4 decline / Stage 4→2 reversal / SWG-PB / Stage 2 at highs / Stage 2 uptrend / Stage 1 base / Neutral |
| 4 | **Trend** | geometry (see §6) + `· apex <px> in N bars` when converging |
| 5 | **Conviction** | `STRONG (6/7)` / `MODERATE (4–5/7)` / `WEAK (≤3/7)` — see §7. Colour green/yellow/red |
| 6 | ── LEVELS ── | separator |
| 7 | **Resistance** | nearest level above price (from 52WH / Fib ext) + `+x%` away |
| 8 | **Support** | nearest level below price (from AVWAP / 50-MA / Fib / 52WL) + `−x%` away |
| 9 | **AVWAP** | value + `✓` (price above) / `✗` (price below) |
| 10 | **Patterns** | detected patterns joined by `·` (Bull flag, Double Top ✓break, H&S (cand)…), or `none` |
| 11 | ── PLAN ── | separator |
| 12 | **Entry** | suggested entry (current close) — or `—` for non-bullish setups |
| 13 | **Stop** | just under nearest support + `(−x%)` risk — or `—` |
| 14 | **Target · R:R** | nearest resistance + `(x.xR)` reward-to-risk — or `—` |
| 15 | **VERDICT** | the plain-English action (see §5). Colour green (buy/long) / red (EXIT) / silver (wait) |

## 5. Setup → Verdict logic (exact)
| Condition | Setup | Verdict |
|---|---|---|
| Stage 4 **and** RS < 0 | STAGE 4 decline | **EXIT / avoid — no new longs** |
| 30-WMA reclaimed (was below in last 25 bars) **and** Stage 1/2 **and** RS > 0 | Stage 4→2 reversal | Emerging long — confirm RS rising |
| Stage 2 **and** Minervini up (50>150>200) **and** RS > 0 **and** near 50-MA | SWG-PB (pullback to MA) | Buy-the-dip — entry on MA reclaim, stop < MA |
| Stage 2 + Minervini up + RS > 0 + within `nearHi%` of 52WH | Stage 2 at highs | Breakout/continuation — buy strength, watch extension |
| Stage 2 + Minervini up + RS > 0 (else) | Stage 2 uptrend | Hold / add on pullback to MA |
| Stage 1 | Stage 1 base | Watch — needs breakout + RS > 0 |
| anything else | Neutral / mixed | No edge — wait |

## 6. Geometry classification
Two best-fit lines (upper = resistance, lower = support), each non-pierced and touch-validated:
- **Rising / Falling channel** — only when the two lines are roughly **parallel** (slope diff ≤ 25%).
- **Falling wedge / Rising wedge / Triangle (converging)** — when the lines **narrow** (apex ahead).
- **Uptrend / Downtrend (not parallel)** or **Broadening** — when they **widen**.
- **Apex** (the cross point) shows price + bars-ahead when the lines converge.

## 7. The Conviction score (0–7)
One point each: **Stage = 2 · RS > 0 · RS rising · close > 50-MA · close > AVWAP · close > 200-MA · volume rising** (SMA10 > SMA50).
- **≥ 6 STRONG** (green) · **4–5 MODERATE** (yellow) · **≤ 3 WEAK** (red).
This is the single fastest read of *how many forces align* behind the move.

## 8. On-chart visuals
- **Trendlines** — `Resistance/Support VALID Nx` (solid) or `prov. 2x` (dashed). Red = falling, green = rising.
- **52W High / Low** — purple / gray dotted.
- **Gaps** — green ▲ (gap-up) / red ▼ (gap-down) on volume.
- **MAs** — SMA50 (orange) / 150 (blue) / 200 (gray).
- **S/R zones** — `R Nx` (red) / `S Nx` (teal) horizontals, clamped to the 52W range.
- **Patterns** — flag box, double/triple-top neckline, H&S neckline, cup label — `✓break` when confirmed, `(cand)` for the heuristic tier.
- **AVWAP** — orange evolving curve.
- **Fib** — 50% (purple), 61.8% (orange), 1.272 (teal), 1.618 (lime), with price labels.
- **Descriptive notes** (v1.5) — full sentences at Resistance / Support / AVWAP explaining *what the level means*.

> **Important:** every line/label above is **indicator output — not draggable.** See the Trading Guide for how trendlines fit the workflow.

---

# PART B — TRADING GUIDE

## 1. Where this tool sits in your workflow
This is the **breadth scanner**: it tells you, on *any* chart in seconds, *"what is this, and is it worth my time?"* It does **not** replace the deep-dive — you still hand-draw the one tradeable trendline and (optionally) run the MCP markup driver on the 2–3 names you'll actually size.

| Layer | Tool | When |
|---|---|---|
| **Breadth** | this indicator (read-only guides) | sweep your universe / a watchlist / the TV screener |
| **Depth** | your hand-drawn trendline + the MCP driver | the handful you'll trade |

## 2. Read the panel top-to-bottom — it's a trade card
1. **Stage + RS** — the gate. You want **Stage 2 + RS > 0 (and ↑)**. Stage 4 + RS < 0 = exit/avoid, full stop.
2. **Conviction** — `STRONG 6/7` means stage, RS, MAs, AVWAP and volume all agree. `WEAK ≤3` = stand aside even if the headline looks bullish.
3. **Setup** — tells you *which* play: breakout-continuation, buy-the-dip, reversal, or exit.
4. **Levels** — Support is your **stop reference**, Resistance your **first target**, AVWAP your **trend line-in-the-sand**.
5. **Plan** — the computed Entry / Stop / Target / R:R. **Only take trades where R:R ≥ 2** and the plan isn't `—`.
6. **Verdict** — the one-line action.

## 3. The setups, and how to leverage each
- **Stage 2 at highs → "buy strength, watch extension."** A leader breaking to new highs. Enter on the break; respect that it's extended — size for volatility, trail under the rising MA / AVWAP.
- **SWG-PB (pullback to MA) → "buy-the-dip, stop < MA."** The highest-quality entry: a Stage-2 leader resting on its rising 50-MA / AVWAP. Tight stop just below Support; target Resistance then Fib ext.
- **Stage 4→2 reversal → "emerging long, confirm RS rising."** Early — wait for RS to actually turn up (the ↑ arrow) and price to hold above the reclaimed 30-WMA before committing.
- **Stage 2 uptrend → "hold / add on pullback."** Already trending; add on dips to the MA, don't chase mid-range.
- **Stage 4 decline → "EXIT / avoid."** Negative RS, below a falling 30-WMA. No new longs; if held, this is your exit signal.
- **Stage 1 base → "watch."** Needs a breakout *and* RS > 0 to graduate. Alert, don't pre-position.

## 4. Conviction-based sizing (suggested)
| Conviction | Action |
|---|---|
| **STRONG (6–7/7)** | Full position at your standard 1% risk; this is a leader with everything aligned. |
| **MODERATE (4–5/7)** | Half / probe; add only when a missing factor confirms (e.g. RS turns ↑, reclaims AVWAP). |
| **WEAK (≤3/7)** | No trade. The structure isn't there yet. |

## 5. Using the levels
- **AVWAP** is the institutional cost basis of the current Stage 2. **Price above = bulls in control; a decisive loss of AVWAP is the first real crack.** Use it as a trailing line-in-the-sand.
- **Fib retrace (50% / 61.8%)** = where a healthy pullback should hold. A leader that holds the 50% on light volume and turns up is a textbook add.
- **Fib ext (1.272 / 1.618)** = profit objectives once the swing extends.
- **Support / Resistance (panel)** auto-pick the *nearest relevant* level from all of the above — that's your stop and first target without hunting.

## 6. Reading geometry
- **Rising channel** in Stage 2 = orderly trend; buy the lower rail, trim the upper.
- **Falling wedge** in a decline = the down-move is exhausting (watch for the up-break, like a base completing).
- **Apex** tells you a converging pattern is near resolution — set alerts on both rails; let price pick the door.
- **Broadening** = rising volatility / indecision — lower conviction, wider stops.

## 7. Workflow per timeframe
- **Weekly** — the *Stage* truth (30-WMA). Confirm a daily setup is a real stage change, not a bear bounce. Raise pivot strength.
- **Daily** — the primary canvas; defaults are tuned here.
- **75/125-min** — entry timing within a confirmed daily setup. Lower pivot strength; treat patterns as faster/noisier.

## 8. Honest limitations (read these)
1. **Auto-trendlines are read-only guides** (Pine can't make draggable lines). They get you ~80% there — **hand-draw the line you'll trade** and touch-validate it yourself. That's better discipline anyway.
2. **Candidates (H&S, Cup) are heuristic** — they fire on noise; never trade them blind, confirm by eye.
3. **The plan is mechanical** (Entry=close, Stop≈nearest support, Target≈nearest resistance). It's a *starting* plan — refine with your structure and ATR sizing.
4. **RS/Stage need a clean data feed.** On delayed/illiquid feeds the panel can mis-read (verify the symbol/exchange).
5. **It finds; you decide.** The indicator's job is to surface candidates fast and frame them — the trade decision, sizing, and execution remain yours.

> **The one-sentence summary:** *Scan with the panel, gate on Stage + RS + Conviction, trade only the STRONG ones with R:R ≥ 2, and draw the final trendline by hand.*
