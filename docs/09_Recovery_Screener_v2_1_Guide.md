# Commander Recovery Screener v2.1 — User & Trading Guide

> **Module Role:** The **rapid-fire discovery tool** for Recovery Strategy candidates. Load it on any NSE ticker in seconds and get an immediate read on whether it qualifies as a REV-CB, REV-RS, or REV-EARLY candidate. Run it as a screener across your NSE watchlist via TradingView's built-in Pine Screener, or use the Python web app's Recovery Screener tab for a full 500-stock scan.
>
> **Current file:** `Commander_Recovery_Screener_v2.0.pine` (renamed from `Commander_Recovery_Screener_v1.5.pine` and `Commander_Capitulation_Screener_v1.5.pine`).

---

## 🆕 v2.0.2 (June 2026) — Honest "no-setup" trade levels + Wyckoff docs

- **No-setup levels:** the compound `LEVELS` row now prints `P <price> · SL/T1/T2 — (no active setup)` when `SIGNAL = 0`, instead of a generic 10-bar-low stop and EMA20/52WH fallback targets that looked like a real plan. See **§4 → Section 4**.
- **Wyckoff fully documented:** this guide previously listed only signals 0–4 and omitted the four Wyckoff catalysts (signal_val **5–8**) that v2.0 added. **§2 (Signal Codes)**, **§4 (RECOVERY GATES — adaptive G6–G10)** and **§9 (Trading Guide)** now cover where the Wyckoff gates live and how to trade each Wyckoff signal.

---

## What's New in v1.6 / v2.0 — Decision-Mode Architecture

Two architectural principles aligned this Screener with the Dashboard's `v67.3.x` cross-tool architecture:

1. **Dashboard owns the Mansfield RS engine.** `f_mansfield()` ported to Dashboard's canonical dual-SMA (26w slope-Mansfield + 52w canonical level + 130-bar warm-up). Same `[level, momentum]` tuple signature so all consumers (`rs_val`, `rs_positive`, `rs_quadrant`, G4 gate) work unchanged. Only the internal math is more canonical now. See Dashboard guide §16.
2. **Each tool owns what's unique to it.** Rows that duplicated the Dashboard's display were removed. Recovery-unique metrics (4-pillar CB, RSI(3) FEAR, 60-bar drawdown) were kept and merged where possible.

### v2.0 — Wyckoff Phases & Physical DB Sync (current)

- **Wyckoff Accumulation Detection:** The recovery screener now includes a full Wyckoff analysis stack. It detects Phase B (Accumulation Base), Phase C (Spring / Shakeout), and Phase D (Sign of Strength / Jump Across the Creek). This provides a more robust institutional accumulation signal than pure reversal structure.
- **Physical 664-Symbol Sector Database:** Removed unreliable string-matching hacks. The Pine code now includes a hardcoded SQLite export block (`<DB_LOOKUP_START>`) guaranteeing 100% parity with the Python ecosystem.
- **JdK RRG Formula & Strike Parity:** The Mansfield slope computation was fully replaced by the JdK RS-Ratio model matched to Strike.Money, using a `+2` score for the LEADING quadrant only.

### v1.7 — Composite-merge pass

The table now uses composite cells for the verdict and trade-plan sections, and pairs the 10 recovery gates 2-per-row.

**Layout (~14 rows, was 25):**

```
TITLE + DATE                              (full-width)
── 🎯 RECOVERY VERDICT ──                 (header)
VERDICT compound: Signal · Score/Grade · Regime · RFF · Correction (52W DD)
── ≡ƒ¢í RECOVERY GATES X/10 [PRIME/WATCH/WEAK] ── (header with status pill)
G1 Regime OK            ✓  |  G2 Liquidity OK             ✓
G3 Fundamentals (1/2)   ┬╜  |  G4 RS Positive (+14.2)      ✓
G5 Stage 1/2            ✓  |  G6 60-bar DD               ✗
G7 Red Bars             ✗  |  G8 Climax Vol              ✗
G9 CB Turn Bar          ✗  |  G10 Climax Window           ✗
→ See Dashboard for: Stage · RS · Trend · Vol · RSI(14)   (full-width footer)
── 📋 TRADE PLAN ──                       (header)
LEVELS compound: P · SL (%) · T1 (% upside) · T2 · R:R to T1
CAPITULATION compound: RSI(3) FEAR · 60-bar DD %
── 🛠 HOW TO TRADE [status pill] ──       (header)
ENTRY    · SIZE
CONFIRM  · MANAGE
RISK     · ENTRY DETAIL
```

**Merger map** (every original datapoint preserved):

| Compound row | Encodes |
|---|---|
| `VERDICT` | Signal text · Score X/12 + letter grade · Regime status (In Recovery / Reclaim / Stock Corr / OFF) · RFF (X/2 with NI/OCF checkmarks) · Correction depth |
| Paired gate row | Two coloured ✓/✗ gate cells side-by-side. G3 carries RFF score inline; G4 carries the Mansfield value inline. |
| `LEVELS` | Price · SL with % distance · T1 with % upside · T2 · R:R to T1 |
| `CAPITULATION` | RSI(3) FEAR reading · 60-bar drawdown % (Recovery-unique; not in Dashboard) |

### Rows removed (Dashboard owns them — read them there)

`STAGE (Weekly)` · `RS N500` · `RS MOMENTUM` · `RSI(14)`

These are **still computed** (the gate logic consumes them) — just no longer displayed here. Cross-reference footer at the bottom-left points to the Dashboard for them.

---

## 1. What It Does

The screener evaluates each chart ticker against all three Recovery Strategy edges and outputs:
- A **Signal Code** (0ΓÇô4) and **Recovery Score** (0ΓÇô12) as Pine Screener columns
- A **25-column CSV export** for offline filtering (via the Pine Screener tab → Export)
- A **40-row visual table** on the main price chart summarising the regime state, 10 recovery gates, trade levels, and a signal-specific trading guide
- **Alert conditions** for each edge trigger

It uses the **identical logic** as the recovery edges in `Weinstein_Unified_Ecosystem_v2.2.pine` — same gates, same thresholds, same RFF checks. The only difference is visual output: the Strategy draws trade lines and manages positions; the Screener outputs a compact summary table for rapid multi-stock review.

---

## 2. Signal Codes

The screener emits a single `signal_val` (0–8). **Wyckoff catalysts (5–8) take priority over the legacy REV-* edges (2–4)** because they are the backtest-validated recovery edge.

| Signal Value | Code | Meaning |
|---|---|---|
| `0` | NONE | No signal — no edge active |
| `1` | WATCH | Climax detected — watching for Turn Bar (Pre-REV-CB) |
| `2` | **REV-CB** | Capitulation Bottom Bounce confirmed |
| `3` | **REV-RS** | RS Survivor Breakout |
| `4` | **REV-EARLY** | NR7 / Inside-3 compression reclaim |
| `5` | **WYC-SPRING** | Wyckoff Spring alone — false breakdown below base low + immediate recovery (Phase C, no Phase-D confirm yet) |
| `6` | **WYC-SOS** | Wyckoff Sign-of-Strength alone — volume-backed push (Phase D) with no qualifying spring/JAC this bar |
| `7` | **WYC-JAC** | Jump Across the Creek — decisive close above the base high (`wyc_base_high`) on ≥ `wyc_jac_vol_mult`× volume |
| `8` | **WYC-SPRING+SOS** | Highest conviction — Spring (Phase C) **and** SOS (Phase D) on the same base |

When multiple edges are simultaneously true, the **highest-value** signal wins (`8 > 7 > 6 > 5 > 4 > 3 > 2 > 1`). So a stock that qualifies for both a Wyckoff Spring and REV-CB reports `WYC-SPRING` (5), not `REV-CB` (2).

> **Answer to "where are the Wyckoff gates?":** there is **no separate Wyckoff gate panel**. The Wyckoff structural checks live inside the *same* adaptive **G6–G10** row of the RECOVERY GATES section (§4 → Section 2). When `signal_val ≥ 5`, those five gate cells **relabel themselves** to the Wyckoff phases (In Wyckoff Base / Spring / SOS / JAC / RS Positive). See the gate-mapping table in §4.

---

## 3. Inputs — Field-by-Field

### Master Filters (match Recovery Strategy settings)
| Input | Default | Explanation |
|---|---|---|
| **Min Daily Turnover (INR)** | `50,000,000` | Liquidity gate — tickers below this are skipped. 50M = Γé╣5 Cr daily. Calculated as Close ├ù Volume. Raise to 100ΓÇô200M for large-cap focus. |
| **Require Recovery Market Regime?** | `true` | Enables the 3-way regime gate. Toggle off for a full universe scan during strong bull markets. |
| **Min Correction from 52W High (%)** | `10.0` | Stock-correction branch of the regime gate — stock passes if it has corrected ΓëÑ this % from its 52W high. |
| **Signal Hold Window (Trading Days)** | `5` | How many bars a signal label stays visible before fading. Set to `1` for same-bar-only mode. |
| **Min Fundamental Score — RFF Lite** | `1` | `0`=disabled, `1`=NI>0, `2`=NI+OCF>0. **Important:** The Screener uses "RFF Lite" — a simplified version using `request.financial()` calls. The full RFF in the Strategy version also cross-checks TTM data; here it is one bar behind. Always verify high-scoring candidates with the full Strategy or the web screener's fundamental check. |

### Edge: REV-CB (Climax Bottom Bounce)
| Input | Default | Explanation |
|---|---|---|
| **Max Drawdown — 60-bar (%)** | `-25.0` | Pillar 1: 60-bar drawdown Γëñ this. Default ΓêÆ25 = 25% off the 60-day high. |
| **Min Red Bars in Lookback Window** | `5` | Pillar 2a: red bars in the lookback window. Default 5 of 10. |
| **Range / Red-Bar Lookback (Bars)** | `10` | Window for red-bar count, bottom-quartile and widest-range tests. |
| **Min Climax Volume Multiplier (├ù avg)** | `2.0` | Climax volume threshold (used inside Pillar 3 widest+bearish frame). |
| **Climax Detection Window (Bars)** | `10` | Bars after climax in which the Turn Bar signal can occur. |

### Edge: REV-RS / REV-EARLY
| Input | Default | Explanation |
|---|---|---|
| **RS Breakout Lookback (Days)** | `20` | REV-RS 20-day high breakout lookback. |
| **Strict-Trend Confirmation Lag (bars)** | `2` | Right-bars for `f_getStrictTrend()` pivot confirmation. **Keep consistent with Zigzag v6.0.** |
| **Volume Confirmation — RS/EARLY Breakouts (├ù avg)** | `1.5` | Breakout volume minimum for both REV-RS and REV-EARLY. |

### VCP Settings (REV-EARLY)
| Input | Default | Explanation |
|---|---|---|
| **Volume Average Length** | `50` | Baseline period for all relative-volume comparisons. |

### Display
| Input | Default | Explanation |
|---|---|---|
| **Table Position** | `Top Right` | Where the 40-row visual table renders on the main price chart. Options: Top Right/Left/Center, Middle Right/Center/Left, Bottom Right/Left/Center. Drag your chart layout to see the table without obstruction. |

---

## 4. The Visual Table — Section-by-Section

> **Where to see it:** The table renders on the **main price chart** (`overlay=true`). It does **not** appear in the Pine Screener tab — that tab shows CSV columns only. Load the indicator on a standard chart, navigate to a ticker, and the table appears on the price bars.

The table has **40 rows** across 4 sections.

### Section 1 — SETUP (rows 2ΓÇô8)
| Row | What It Shows |
|---|---|
| **SIGNAL** | Active edge name — `WYC-SPRING+SOS` / `WYC-JAC` / `WYC-SOS` / `WYC-SPRING` / `REV-EARLY` / `REV-RS` / `REV-CB` / `WATCH (Climax)` / `NONE`. Colour-coded: yellow=EARLY, green=RS, red=CB, orange=WATCH (Wyckoff signals render in the priority/positive colour). |
| **SCORE / GRADE** | Recovery Score 0ΓÇô12 with grade (ΓëÑ9=A green, ΓëÑ6=B orange, <6=C/D red). |
| **STAGE (Weekly)** | Weinstein weekly stage 1ΓÇô4. Green if Stage 1 or 2 (recovery-eligible). |
| **REGIME** | ✓/✗ + market state string (Bull Market / In Recovery / Post-Shock Reclaim / Neutral/Bear). |
| **RFF SCORE** | Fundamental gate: `x / 2  NI✓  OCF✓` breakdown. Green=2/2, orange=1/2, red=0/2. |
| **CORRECTION** | % off 52W High. Green ΓëÑ25%, orange ΓëÑ10%, red <10%. |
| **MARKET** | Market state narrative from the CNX500 regime gate. |

### Section 2 — RECOVERY GATES (rows 10ΓÇô19)
Shows **10 gates** as ✓/✗ with a pass count header (`x/10`). Header shows PRIME (ΓëÑ8), WATCH (ΓëÑ5), or WEAK (<5).

**G1ΓÇôG5 are universal across all signals:**

| Gate | What It Tests |
|---|---|
| G1 — Regime OK | 3-way regime gate passes (market corrected / reclaiming / stock corrected) |
| G2 — Liquidity OK | Close ├ù Volume ΓëÑ min daily turnover input |
| G3 — Fundamentals | RFF score ΓëÑ your input threshold; shows `(x/2)` detail |
| G4 — RS Positive | Mansfield RS vs CNX500 > 0 (stock outperforming index) |
| G5 — Stage 1 / 2 | Weekly Weinstein stage is 1 (Base) or 2 (Uptrend) |

**G6ΓÇôG10 adapt their labels based on the active signal** — this is where the Wyckoff structural gates live. When `signal_val ≥ 5`, the five cells relabel to the Wyckoff phases:

| Signal (signal_val) | G6 | G7 | G8 | G9 | G10 |
|---|---|---|---|---|---|
| **WYC-* (5–8)** | In Wyckoff Base (`wyc_in_base`) | Spring — Phase C (`wyc_has_spring`) | SOS — Phase D (`wyc_has_sos`) | JAC — cross creek (`wyc_has_jac`) | RS Positive |
| **REV-CB / WATCH (1–2)** | P1 — 60-bar DD | P2 — Red Bars | P3 — Climax Vol | CB Turn Bar | Climax Window |
| **REV-RS (3)** | Strict Trend Up | Higher-Low | RS Breakout Lvl | Volume ΓëÑ1.5├ù | RS Positive |
| **REV-EARLY (4)** | NR7 / Inside-3 | 20-bar Reclaim | Volume ΓëÑ1.5├ù | Volume ΓëÑ1.5├ù | RS Positive |

> **Reading a Wyckoff candidate's gates:** the *combo* signals share this one gate row, so for `WYC-SPRING+SOS` (8) you should see **both** G7 (Spring) **and** G8 (SOS) showing ✓. For `WYC-SOS` (6) alone, G7 will be ✗ (no spring) but G8 ✓ — that's expected, and explains why the standalone SOS is lower-conviction than the combo. G6 (In Wyckoff Base) must be ✓ for *any* Wyckoff signal; if it's ✗, the stock has no qualifying accumulation range and the Wyckoff thesis doesn't apply.

### Section 3 — RS & QUALITY (rows 21ΓÇô26)
| Row | What It Shows |
|---|---|
| **RS N500 (Mansfield)** | Mansfield RS ├ù100 value + RRG quadrant (LEADING/WEAKENING/LAGGING/IMPROVING) |
| **RS MOMENTUM** | 4-bar ROC of Mansfield (RRG y-axis). Positive = accelerating RS. |
| **REL VOLUME** | Volume / 50D avg. Green ΓëÑ2├ù, orange ΓëÑ1.5├ù, grey <1.5├ù. |
| **RSI(14)** | 14-period RSI. Highlighted green if <30 (oversold = CB setup zone). |
| **RSI(3)** | 3-period RSI fear gauge. Green <10, orange <20. |
| **60-BAR DRAWDOWN** | % drawdown from the 60-bar high. Green if Γëñ your Pillar 1 threshold. |

### Section 4 — TRADE LEVELS (compound `LEVELS` row)
The stop and targets are consolidated into **one compound `LEVELS` row** under the `── 📋 TRADE PLAN ──` header. What it prints depends on whether a recovery signal is active.

**When a signal is active (`SIGNAL > 0` — REV-CB / REV-RS / REV-EARLY / Wyckoff):**

```
P 512.40 · SL 478.10 (6.7%) · T1 548.90 (7.1%) · T2 591.20 · R:R 1.9:1
```

| Field | What It Shows | Possible values |
|---|---|---|
| **P** | Current close (reference entry) | price `#.00` |
| **SL (x.x%)** | Signal-specific stop-loss with % distance in the label | price `#.00`, `(x.x%)` distance below P |
| **T1 (x.x%)** | Target 1 with % upside. **REV-CB** = EMA20 reclaim; **REV-RS / REV-EARLY** = entry + 5R *(widened from 2.5R in v2.0 — "let winners run")*; **Wyckoff (5–8)** = entry + 5R | price `#.00`, `(x.x%)` upside |
| **T2** | Target 2. **REV-CB** = 200 DMA; **REV-RS / REV-EARLY** = 52W High; **Wyckoff (5–8)** = max(entry + 10R, 52W High) | price `#.00` |

*SL anchor: REV-CB uses the climax-bar structural stop; all other signals (incl. Wyckoff) use the **10-bar-low − 0.2× ATR** anchor (floored at close − 1.5× ATR if that would invert). For live Wyckoff entries prefer the tighter base-low stop shown by the Unified Ecosystem strategy.*
| **R:R** | Risk:Reward to T1. Row colour: green ≥ 2.0, orange ≥ 1.0, red < 1.0 | `x.x:1` |

**When NO signal is active (`SIGNAL = 0`) — v2.0.2 change:**

```
P 512.40 · SL/T1/T2 — (no active setup)
```

> **Why this changed (v2.0.2, June 2026):** with no recovery signal firing, the displayed SL was just the generic 10-day-low structural anchor and T1/T2 fell back to EMA20 / 52W-High — *not* a vetted plan tied to a real capitulation or Wyckoff trigger. Printing those numbers made an un-triggered watch candidate look tradeable. The row now shows **`SL/T1/T2 — (no active setup)`** so you only ever act on the numeric plan when a signal code is live. In this state the screener's purpose is the **WATCH MODE** guide (Section 5), not the levels.

### Section 5 — SIGNAL GUIDE (rows 34ΓÇô39)
Signal-adaptive 6-row trading guide. Header shows "WATCH MODE (x/10 gates)" when no signal, or "HOW TO TRADE [signal-name]" when active.

| Row | What It Shows |
|---|---|
| **ENTRY** | Specific entry instruction for the active signal |
| **SIZE** | Position sizing guidance (Full/Half/Swing/0) |
| **CONFIRM** | What must happen after entry to validate the trade |
| **MANAGE** | Target management instructions |
| **RISK** | Exit rule — when the thesis is broken |
| **KEY LEVEL** | The single most important price level for the active signal |

---

## 5. Recovery Score Components (0ΓÇô12)

| Condition | Points |
|---|---|
| Net Income > 0 (RFF part 1) | +2 |
| Operating Cash Flow > 0 (RFF part 2) | +1 |
| Mansfield RS vs CNX500 > 0 | +1 |
| Mansfield RS ΓëÑ 10.0 (strong positive) | +1 |
| Correction depth ΓëÑ 25% from 52W High | +2 |
| Correction depth ΓëÑ 15% from 52W High | +1 |
| Market in recovery regime | +1 |
| Weekly stage = 1 or 2 | +1 |
| Edge signal = REV-CB or REV-RS/EARLY triggered | +2 |
| Volume on signal bar ΓëÑ 3├ù avg (exceptional) | +1 |

**Interpretation:**
- **ΓëÑ 9 (Grade A):** Highest priority candidate — immediate pipeline to Risk Allocator
- **6ΓÇô8 (Grade B):** Strong candidate — verify on Dashboard before entering
- **3ΓÇô5 (Grade C):** Monitor only — wait for additional confirmation
- **< 3 (Grade D):** Ignore — insufficient quality

---

## 6. Alert Conditions

| Alert Name | Trigger |
|---|---|
| `REV-CB Signal` | Turn Bar (Pillar 4) confirmed on current bar |
| `REV-RS Signal` | RS Survivor Breakout on current bar |
| `REV-EARLY Signal` | NR7/Inside-3 reclaim on current bar |
| `Capitulation Detected` | Pillar 3 (climax bar) detected — advance warning |

Set these in TradingView's Alert system with `Once Per Bar Close` frequency to avoid intra-bar noise.

---

## 7. Using as a TradingView Pine Screener

1. Add the screener to any chart as an indicator
2. Open TradingView's **Screener** panel (bottom toolbar)
3. Add the indicator's `Signal` and `Recovery Score` outputs as screener columns
4. Filter: `Signal >= 2` to show all active REV candidates
5. Sort by `Recovery Score` (descending) to see best candidates first
6. Click **Export** to download the 25-column CSV

The screener works across any NSE watchlist you have in TradingView — no API calls needed.

> **Note:** The visual table only appears on the main chart layout — it is suppressed in the Pine Screener tab. Load a candidate on a standard chart to see the full 40-row table.

---

## 8. CSV Export — Field-by-Field Reference & Trading Use

### 8.1 Column Legend

| # | CSV Column Name | Decoded Values | Trading Use |
|---|---|---|---|
| 1 | **Signal (4=EARLY \| 3=RS \| 2=CB \| 1=Watch \| 0=None)** | 0=No signal, 1=Climax forming (pre-CB), 2=REV-CB active, 3=REV-RS active, 4=REV-EARLY active | Primary filter: `ΓëÑ2` for actionable signals. `=1` means watch but do not enter. |
| 2 | **Recovery Score (0-12)** | 0ΓÇô12 composite quality score | Sort descending after signal filter. Grade A=ΓëÑ9, B=ΓëÑ6, C=ΓëÑ3, D=<3. Only trade A/B grades. |
| 3 | **RFF Lite Score (0/1/2)** | 0=No positives, 1=NI>0 only, 2=NI+OCF both positive | Discard any stock with RFF=0. 2/2 preferred. One bar behind full RFF — confirm in Dashboard. |
| 4 | **Market Recovery Regime** | 1=market SMA50 < SMA200 (death-cross regime), 0=otherwise | Context flag. Signal=1 means market is in a confirmed bear — recovery setups most relevant here. |
| 5 | **Market Reclaim (post-shock momentum)** | 1=market reclaimed SMA50 within 30 bars, 0=no | Indicates post-shock momentum bounce. Regime gate passes when this=1 even if not in full recovery. |
| 6 | **Weinstein Weekly Stage (1-4)** | 1=Base, 2=Uptrend, 3=Top, 4=Downtrend | Stage 1 or 2 preferred for entries. Stage 4 stocks showing signal: wait for Stage 1 confirmation. |
| 7 | **Mansfield RS ├ù100 vs CNX500** | Positive = outperforming CNX500, negative = underperforming. Scaled ├ù100 (textbook Mansfield). | REV-RS requires RS>0. Values ΓëÑ10 = strong; ΓëÑ5 = moderate. CB stocks may have negative RS — acceptable. |
| 8 | **RS-Momentum (4-bar ROC of Mansfield)** | Positive = RS improving (RRG y-axis). Negative = RS decelerating. | A positive RS-Momentum is an early leading indicator before price breaks out. Look for turning from negative to positive. |
| 9 | **RRG Quadrant (1=LEAD 2=WEAK 3=LAG 4=IMPROV)** | 1=Leading, 2=Weakening, 3=Lagging, 4=Improving | LEADING (1) = best RS setup. IMPROVING (4) = emerging RS — acceptable for REV-RS. LAGGING (3) = avoid for RS entries. |
| 10 | **60-bar Drawdown (%, neg = below)** | Negative = % below 60-bar high. E.g. ΓêÆ28.5 = down 28.5% | Pillar 1 gate: must be Γëñ your input (default ΓêÆ25%). Deeper = more capitulation evidence. |
| 11 | **Correction from 52W High (%)** | 0ΓÇô100, positive = % off 52W high | Stock-leg of regime gate: ΓëÑ10% passes. Also scores the composite: ΓëÑ25%=+2, ΓëÑ15%=+1. |
| 12 | **Relative Volume (├ù 50D avg)** | 1.0=average day. >1.5=elevated. >3.0=exceptional | Must be ΓëÑ1.5├ù on REV-RS/EARLY signals. ΓëÑ2.0├ù on REV-CB climax bar. ΓëÑ3.0├ù adds +1 to score. |
| 13 | **RSI(3) — Fear Gauge** | 0ΓÇô100. Very low values (<10) = extreme fear/capitulation | Use to time CB entries: RSI(3) < 10 = deep fear, ideal for Turn Bar watch. High values = avoid buying. |
| 14 | **RSI(14)** | 0ΓÇô100. <30=oversold, >70=overbought | Context indicator. CB setups often show RSI(14) 20ΓÇô35 at the climax low. |
| 15 | **Red Bars in Lookback** | Count of down-close bars in the lookback window (default 10) | Pillar 2a: must be ΓëÑ5 of 10 for CB. High count = sustained selling = capitulation quality. |
| 16 | **CB: Climax Detected** | 1=All 3 CB pillars true on this or recent bar (within climax window), 0=no | Watch state trigger. When 1: set price alert at prior high for Turn Bar confirmation. |
| 17 | **RS: Positive Mansfield** | 1=Mansfield RS > 0, 0=negative | Gate for REV-RS and REV-EARLY. Required for both. CB is the only edge that tolerates RS<0. |
| 18 | **Strict Trend (1=Up 0=Side -1=Down)** | 1=HH+HL pivot structure, 0=sideways, -1=LH+LL | REV-RS requires Strict Trend = 1. REV-CB does not. Trend=-1 = avoid REV-RS regardless of other signals. |
| 19 | **Entry Price** | Current close | The price at which the signal fired. Use as reference for sizing and R calculation only. |
| 20 | **Stop Loss Price** | Calculated SL: CB=climax low ΓêÆ 0.5 ATR; RS/EARLY=10-bar low ΓêÆ 0.2 ATR | Your hard exit. If close < SL, thesis is broken — exit. Never move SL down. |
| 21 | **T1 Target Price** | CB=EMA20; RS/EARLY=entry + 2.5 ├ù risk | First profit target. Exit 50ΓÇô75% of position here to lock in R. |
| 22 | **T2 Target Price** | CB=200 DMA; RS/EARLY=52W High | Full target. Trail remaining position with EMA20. |
| 23 | **R/R Ratio to T1** | (T1 ΓêÆ Entry) / (Entry ΓêÆ SL). ΓëÑ2.0 = minimum threshold | Only enter when R:R ΓëÑ 2.0. Below 2.0 the trade is not worth the risk. |
| 24 | **T1 Upside (%)** | % gain if T1 is reached from entry price | Quick scan to discard low-upside setups. REV-CB typically shows 8ΓÇô20% to T1. |
| 25 | **Stop Loss Distance (%)** | % from entry to stop loss | Cap at 8ΓÇô10% per your risk rules. SL% ├ù position weight = portfolio risk per trade. |

### 8.2 Filter Recipes

**Recipe 1 — Prime Recovery Candidates (highest priority)**
```
Signal >= 2
AND Recovery Score >= 9
AND RFF Lite Score >= 1
AND Mansfield RS ├ù100 >= 0
```
→ Immediate pipeline to Risk Allocator. These are Grade A, multi-gate passes.

**Recipe 2 — REV-CB Entries (capitulation plays)**
```
Signal = 2
AND CB: Climax Detected = 1
AND RSI(3) < 20
AND Relative Volume >= 1.5
AND Stop Loss Distance (%) <= 8
```
→ Sort by 60-bar Drawdown (most negative = deepest capitulation first).

**Recipe 3 — REV-RS Entries (RS survivor breakouts)**
```
Signal = 3
AND RS: Positive Mansfield = 1
AND Strict Trend = 1
AND RRG Quadrant <= 2  (Leading or Weakening → Improving)
AND R/R Ratio to T1 >= 2.0
```
→ Sort by Mansfield RS ├ù100 descending (strongest RS leaders first).

**Recipe 4 — REV-EARLY Entries (compression reclaims)**
```
Signal = 4
AND Weinstein Weekly Stage <= 2
AND Relative Volume >= 1.5
AND Recovery Score >= 6
```
→ Sort by Recovery Score descending. NR7 > Inside-3 for tighter stops.

**Recipe 5 — Watchlist (climax forming — set alerts)**
```
Signal = 1
AND CB: Climax Detected = 1
AND Recovery Score >= 6
AND RFF Lite Score >= 1
```
→ These stocks have structural capitulation but no Turn Bar yet. Set price alert at prior high.

### 8.3 CSV → Trade Workflow

1. Export CSV from Pine Screener tab
2. Filter to Signal ΓëÑ 2 (or Signal=1 for watchlist building)
3. Sort by Recovery Score descending
4. Discard any row with RFF Lite Score = 0 or R:R Ratio < 2.0
5. Load top candidates on the main chart to see the 40-row visual table
6. Validate on Commander Dashboard v67.0 before entering
7. Feed SL Price and Entry Price into Risk Allocator for position sizing

### 8.4 Common CSV Pitfalls

1. **Acting on Signal=1** — Climax detected but no Turn Bar yet. This is watch-only. Enter only at Signal=2.
2. **Ignoring R:R column** — A stock with Signal=3 but R:R=1.2 is a bad trade. The R:R filter is non-negotiable.
3. **Using Entry Price as market order** — The CSV captures close price. Always verify next-day open before committing.
4. **RFF Lite Γëá Full RFF** — The screener uses TTM financials from `request.financial()` which is one period behind. A Score=2/2 is necessary but not sufficient — verify in the Dashboard.
5. **Stale CSV data** — Pine Screener exports the last bar's values. Re-run the screener on the day of entry to get fresh values.
6. **RRG Quadrant interpretation** — LEADING (1) stocks are already outperforming. IMPROVING (4) are turning. Both are valid for REV-RS. LAGGING (3) stocks need a longer recovery runway — reduce size.

---

## 9. Signal-Adaptive Trading Guide

### Signal 0 — NONE (No Edge)
Watch mode. The table shows how many of the 10 gates are blocked. When gate count reaches 8+, begin watching for a catalyst trigger.

### Signal 1 — WATCH (Climax Forming)
All 3 structural CB pillars have fired but no Turn Bar yet.

| Step | Action |
|---|---|
| Entry | Do NOT enter. Zero size. |
| Alert | Set price alert at prior bar's high (the level a green Turn Bar must break). |
| KEY LEVEL | Climax low — if price makes new lows, the climax resets. |
| Exit Watch | If price closes below climax low, remove from watchlist. |

### Signal 2 — REV-CB (Capitulation Bottom Bounce)
Turn Bar confirmed — all 4 pillars complete.

| Step | Action |
|---|---|
| Entry | Buy on Turn Bar close or next-day open. |
| Size | Half initial position; scale to full after EMA20 reclaim. |
| Confirm | Close above EMA20 next session = thesis validated. |
| T1 | EMA20 (exit 50ΓÇô70% of position here). |
| T2 | 200 DMA (trail remainder with EMA20). |
| Exit | Close below the climax low = thesis broken, full exit. |

### Signal 3 — REV-RS (RS Survivor Breakout)
Stock showing relative strength breakout above 20-day high with strict uptrend structure.

| Step | Action |
|---|---|
| Entry | Buy stop above today's high (stop order, not market). |
| Size | Full size if Mansfield RS ΓëÑ10; Half if RS 0ΓÇô10. |
| Confirm | HH/HL pivot structure must hold; volume ΓëÑ1.5├ù through close. |
| T1 | 2.5R from entry. |
| T2 | 52W High. |
| Exit | If strict trend breaks (a lower-low forms), exit in full. |

### Signal 4 — REV-EARLY (NR7 / Inside-3 Compression Reclaim)
Highest quality recovery signal — compression + reclaim of the 20-bar high.

| Step | Action |
|---|---|
| Entry | Buy above today's high on next bar open. |
| Size | Swing allocation. NR7 bars have tighter stops — use full swing if SL distance Γëñ5%. |
| Confirm | Volume ΓëÑ1.5├ù + reclaim level must hold as support. |
| T1 | 5R; trail with EMA20. |
| T2 | 52W High. |
| Exit | If price drops back below the 20-bar high reclaim level. |

### Signals 5–8 — WYCKOFF (priority recovery edge)
These are the **highest-priority** recovery signals — when a Wyckoff structure is present it overrides any REV-* code. All four target **5R (T1) / max(10R, 52W High) (T2)** and are *positional* in character (base breakouts run far when institutional accumulation is real). Read them in conviction order.

**Signal 8 — WYC-SPRING+SOS (highest conviction)**
Spring (Phase C shakeout) **and** Sign-of-Strength (Phase D) on the same base.

| Step | Action |
|---|---|
| Entry | Buy on the SOS close or next-day open — the spring already gave you the low-risk reference. |
| Size | Full positional allocation. This is the one to size to your normal 1% risk. |
| Confirm | Price holds above `wyc_base_high`; volume stayed ≥ `wyc_jac_vol_mult`× on the SOS bar. |
| T1 / T2 | 5R / max(10R, 52W High) — partial at T1, trail the runner. |
| Exit | Close back **below the base low** (spring failed) = thesis broken, full exit. |

**Signal 7 — WYC-JAC (Jump Across the Creek)**
Decisive, volume-backed close above the base resistance ("the creek").

| Step | Action |
|---|---|
| Entry | Buy on the JAC close / next open. Strong continuation entry. |
| Size | Full or 3/4 size — confirmed breakout but you have no spring low to lean on. |
| Confirm | `close > wyc_base_high` holds; no immediate failback into the base. |
| T1 / T2 | 5R / max(10R, 52W High). |
| Exit | Failback below `wyc_base_high` on volume = failed JAC, exit. |

**Signal 6 — WYC-SOS (Sign-of-Strength alone)**
Phase-D push with no qualifying spring this bar — medium conviction.

| Step | Action |
|---|---|
| Entry | Buy the SOS close, but accept a wider stop (no spring low to anchor on). |
| Size | Half size; add on a subsequent JAC or higher-low retest. |
| Confirm | G6 "In Wyckoff Base" must be ✓ — if not, skip; the base isn't real. |
| T1 / T2 | 5R / max(10R, 52W High). |
| Exit | Loss of the 10-bar-low − 0.2×ATR stop. |

**Signal 5 — WYC-SPRING (Spring alone — earliest, least confirmed)**
False breakdown below the base low + immediate recovery, but Phase D hasn't printed.

| Step | Action |
|---|---|
| Entry | Earliest, lowest-price entry — but unconfirmed. Buy *half* on the recovery bar. |
| Size | Half / probe. Add the other half only when an SOS or JAC follows (upgrades to signal 6–8). |
| Confirm | Price must reclaim and hold inside the base within ~3 bars of the spring. |
| T1 / T2 | 5R / max(10R, 52W High). |
| Exit | A *second* close below the spring low = it wasn't a spring, exit. |

> **How to leverage on the panel:** a `WYC-*` SIGNAL with G6 ✓ (In Wyckoff Base) is your green light; the specific code tells you how much to commit (8 = full, 7 = full/three-quarter, 6 = half + add, 5 = half probe). Because Wyckoff now also surfaces on the **Unified Ecosystem** panel (v3.4.2), cross-check there: a `🔵 ACTIVE TRADE` on the Wyckoff row means the strategy already holds that position.

---

## 10. Ecosystem Integration

| Module | Connection |
|---|---|
| **Recovery Strategy v2.2** | Exact same logic — the Screener finds candidates, the Unified Ecosystem manages trades |
| **Dashboard v67.0** | Load screener candidates on the Dashboard for full validation before entry |
| **Risk Allocator v1.0** | Feed the screener's `SL Price` and `Entry Price` CSV columns into the Allocator for position sizing |
| **Python Recovery Screener** | `recovery_screener.py` is the batch Python version of this exact script |
| **Zigzag v6.0** | `piv_d_right` must match for consistent `f_getStrictTrend()` output (default: 2) |

---

## 11. v1.5 Changes vs. v1.3

| Feature | v1.3 | v1.5 |
|---|---|---|
| Climax Volume Threshold | `2.5├ù` avg | `2.0├ù` avg (more inclusive) |
| Weekly Stage Check | Not included | MTF check via `f_getStrictTrend()` |
| RRG Quadrant in table | Not included | Added (LEADING/WEAKENING/LAGGING/IMPROVING) |
| Recovery Score | 8-point max | 12-point max (expanded) |
| REV-EARLY Detection | Inside-3 only | NR7 OR Inside-3 |
| Drawdown Display | Not in table | Added with colour grading |
| Visual table | None (blank pane) | 40-row dark-theme table on main price chart |
| Overlay mode | Separate lower pane | `overlay=true` — table on price chart |
| Table Position | Fixed | Configurable: 9 position options |
| Histogram plot | Shown in pane | Suppressed (`display.none`) — overlay mode |

---

## 12. Common Mistakes

1. **Using as standalone trade trigger** — The Screener is a discovery tool. Always validate on the Dashboard before entering.
2. **Ignoring Grade D** — A score < 3 means multiple gates failed. Do not enter regardless of how attractive the chart looks.
3. **Acting on Signal=1** — Signal 1 is watch state only. Wait for the Turn Bar (Signal=2) before any action.
4. **Mismatching `piv_d_right`** — If the Zigzag uses `right=2` but the Screener uses `right=3`, the REV-RS trend gate will produce inconsistent results.
5. **Reading the table in Pine Screener tab** — The table only appears on the main chart layout. The Pine Screener tab shows CSV column values only.
6. **Using stale CSV for entry** — Re-run the screener fresh on the day of entry. CSV snapshots age as price moves.

---

## 13. May 2026 Update — Roll-back + Wyckoff Additive Layer

This section documents the May 2026 changes during the validation-framework campaign.

### 13.1 What Changed

| File | Version | Change |
|---|---|---|
| `recovery_screener.py` | v1.5 | **RE-INSTATED** the REV-CB / REV-RS / REV-EARLY engine. The v1.4 "RETIRED" verdict was based on a 30-day forward-window backtest, which is the wrong horizon for recovery / mean-reversion catalysts (designed for multi-month base-building per Weinstein Stage 1→2 transition). |
| `recovery_screener.py` | v1.6 | **SL safety-floor widened** from 1.5├ù → 2.5├ù daily ATR for REV-*. The 90-day recovery horizon needs more room than a swing-sized stop. |
| `recovery_screener_v3_wyckoff.py` | (preserved) | The Wyckoff v3.0 implementation (Spring / SOS / JAC pattern detection) lives alongside the v1.5 REV-* engine. **Both are valid; choose by trade thesis.** Wyckoff is a base-pattern engine; REV-* is a catalyst-triggered engine. |
| `Commander_Recovery_Screener_v2.0.pine` | v2.0 | **No live-logic change** — REV-* was already present as a fallback (signal_val 2-4) when Wyckoff was added as priority. Continues to fire all four legacy catalysts plus Wyckoff. |

### 13.2 Which Recovery Engine Do I Use?

**Default: `recovery_screener.py` (v1.5 — REV-* engine).** This is the canonical recovery screener and what the Full workflow now runs. Picks come labeled with `REV-CB`, `REV-RS`, or `REV-EARLY`.

**Alternative: `recovery_screener_v3_wyckoff.py` (Wyckoff).** Run this in parallel when you want explicit Wyckoff Spring / SOS / JAC pattern recognition. Picks come labeled `WYC-SPRING+SOS`, `WYC-JAC`, `WYC-SOS`, `WYC-SPRING`.

The Pine Commander Recovery Screener shows all of them — the priority order in v2.0 is WYC > REV. Both pick types appear in the same table.

### 13.3 SL Discipline

- Primary SL anchor: **structural** — climax-zone low for REV-CB, 10-day low for REV-RS/EARLY (unchanged).
- v1.6 fallback (when structural anchor is above close): **2.5├ù daily ATR** (was 1.5├ù).

### 13.4 What Was Rolled Back

Γ¥î ~~"Recovery screener retired"~~ — RESTORED. The v1.4 retirement was based on wrong-horizon measurement and is withdrawn.

### 13.5 Live Trading vs Backtest Numbers

The properly-windowed validation (90d horizon for REV-*) shows mean matched alpha consistent with the bull screener — small positive per-trade alpha that requires more anchors to confirm statistically. Run the system and accumulate live picks.
