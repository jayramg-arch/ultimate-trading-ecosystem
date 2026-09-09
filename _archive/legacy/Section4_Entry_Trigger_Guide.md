# Section 4 — Entry Trigger & Price Memory · v4.0 — The Comprehensive Manual

This is the exhaustive reference for the **Section 4 Entry Trigger & Price Memory** Pine indicator (`Section4_Entry_Trigger_v3.0.pine`, in-file title **v4.0**). It covers the philosophy, the decision engine, every subsystem's logic in depth, every input parameter, the panel row-by-row, the diagnostics, the alerts, and the full version history from v3.5 to v3.9.

> **What this tool is.** S4 is the **entry-timing layer** that sits *after* the Golden Matcher has already filtered a name to "Step 5". The Golden Matcher (GM) qualifies *which* names to watch; S4 times *when* to pull the trigger on one of them. It is a rigid, mechanical gatekeeper — it can talk you **out** of a bad entry, and it will only say **GO** when four independent things line up at once.

> **Two-stage relationship with the GM (intentional, do not collapse).** GM fires *early* ("TRIGGER LIVE / ARMED" the moment a PA pattern appears) so you focus on a name. S4's **GO** is the *strict* execution gate (a pattern **at a location, with volume, on a clean bar**). GM arms → you focus → you wait for the S4 **GO**. They are deliberately not aligned.

---

## Table of Contents

1. [Core philosophy — the four gates & "hide = ignore"](#1-core-philosophy)
2. [Auto mode — Bull vs Recovery resolution](#2-auto-mode)
3. [The GO gate in depth (P · L · V · B)](#3-the-go-gate)
4. [The PA battery — 17 Bull / 10 Recovery patterns](#4-the-pa-battery)
5. [Anchored VWAPs — price memory](#5-anchored-vwaps)
6. [The intraday trigger — 10-EMA + TTM squeeze](#6-the-intraday-trigger)
6a. [Arrival Style & Order-Flow Footprint (v4.0)](#6a-arrival-order-flow)
7. [The Zone Engine — anatomy of a demand/supply zone](#7-the-zone-engine)
8. [Zone scoring, confluence & Controlling zones](#8-zone-scoring)
9. [Zone lifecycle — Fresh → Tested → Violated, ageing](#9-zone-lifecycle)
10. [Structural (pivot) zones](#10-structural-pivot-zones)
11. [Multi-timeframe propagation](#11-mtf-propagation)
12. [S/R Levels — clustering, MTTWR, R↔S flip](#12-sr-levels)
13. [Trendlines — manual & machine-readable](#13-trendlines)
14. [Geometry & rectangles](#14-geometry)
15. [The Plan — Entry / SL / Targets / R:R / sizing](#15-the-plan)
16. [The Panel — row by row](#16-the-panel)
17. [Diagnostics & the 3-lever toolkit](#17-diagnostics)
18. [Alerts](#18-alerts)
19. [Complete parameter reference](#19-parameter-reference)
20. [Version history v3.5 → v3.9](#20-version-history)
21. [Trading workflow & FAQ](#21-workflow-faq)

---

<a name="1-core-philosophy"></a>
## 1. Core Philosophy — the four gates & "hide = ignore"

S4 answers four mandatory questions before it will say **GO**. Internally these are the letters **P · L · V · B** on the TRIGGER row:

| Gate | Question | Panel letter | What satisfies it |
|---|---|---|---|
| **Event** | *What is happening?* | **P** (PA) | A PA pattern fired (one of the 17 Bull or 10 Recovery patterns). |
| **Location** | *Where are we?* | **L** | Price is at a fresh demand zone, FVG, pivot support, a fresh S/R level, a manual trendline, the EMA20, or an AVWAP. |
| **Volume** | *Is anyone there?* | **V** | Relative Volume ≥ the floor (`rv_floor`, default 1.0). |
| **Bar quality** | *Did the bar close clean?* | **B** | The trigger bar is green **or** closed in its upper half (kills big-red distribution/upthrust bars that a structural pattern could otherwise fire on). |

```
GO = P and L and V and B
```

The **Plan** (Entry / SL / Targets / R:R) is computed *only* once GO is live — it is the fifth question, *"is it worth the risk?"*, answered with numbers rather than a gate.

### The "hide = ignore" rule (critical)

Under **Display — layers**, every master switch is wired to the **decision**, not just the chart. Turning a layer OFF removes it from the support gate, the Plan's stop/target, **and** the confluence score. This is deliberate: a layer you have judged untrustworthy must not keep quietly steering trades from behind a hidden drawing. **"Not shown" and "not counted" mean the same thing.** (The one exception is *Chart markers* — that toggle is purely visual; the PA battery and panel keep calculating.)

---

<a name="2-auto-mode"></a>
## 2. Auto Mode — Bull vs Recovery resolution

The **Mode** input (`Auto` / `Bull` / `Recovery`) selects which PA battery runs. **Auto** (default) infers the path from price structure, mirroring the Golden Matcher's recovery CONTEXT gate:

```
Recovery  ⇔  off52 ≥ auto_dd_floor (10%)  AND  (below the 30-WMA proxy OR its 10-day slope falling)
                                          AND  (auto_require_below_200 ⇒ price < 200-DMA)
Bull      ⇔  everything else
```

- `auto_dd_floor` (default **10%**) — how far off the 52-week high before Recovery is considered. Keep in sync with the GM's `min_stock_correction_pct`.
- `auto_require_below_200` (default **ON**) — Recovery also requires price **below** the 200-DMA. This is why Auto stays on the **Bull** path for most names: a shallow bull pullback (10% off highs but still above the 200-DMA) is *not* a capitulation, and shouldn't flip to Recovery. Turn OFF to let early recoveries that have *already reclaimed* the 200-DMA resolve Recovery.

The panel header shows the resolution: `PA · BULL (auto·75)` or `PA · RECOVERY (auto·EOD)`. The **Structure basis** row explains it in words (off52% · 30-WMA state · 200-DMA state → auto-picked Bull/Recovery).

> **Pine can't see the GM's live decision.** For a name where GM and Auto disagree, set **Mode = Bull or Recovery manually** when you create the alert — that override is authoritative.

The **200-DMA discriminant** is the structural spine: bull/accumulation lives *above* the 200-DMA; a beaten-down recovery lives *below* it.

---

<a name="3-the-go-gate"></a>
## 3. The GO Gate in Depth

### 3.1 The anti-Holy-Grail rule

GO fires on **P · L · V · B** — *not* on "everything at once." Historically an early version tried to require the AVWAP event **and** the intraday leg **and** volume simultaneously; that yields a trigger that almost never fires, which is a *different* failure, not a safer one. So **AVWAP/intraday timing events are optional** (shown with a ⏱), and the confluence score *grades* how strong a GO is rather than gating it.

### 3.2 Last-closed-candle (no intraday repaint) — `use_closed_candle` (default ON)

Before the market opens you shortlist names on their S4 signals; the moment the market opens, a naïve indicator's triggers drop because the *forming* bar has little volume and an undeveloped pattern. With `use_closed_candle` ON, the **TRIGGER / GO / RV / STATUS**, the on-chart GO markers, and the alert all read the **last CLOSED chart bar** (`[_so]` shift). The signal only updates when the current bar closes. This is the fix for "triggers fade at the open." Turn OFF for a live forming-bar view.

### 3.3 Trigger path-specificity (v3.5) — `⇄both` / `Bull-only` / `Rec-only`

The Bull and Recovery batteries **share four patterns** — **Spring, Engulf, 3-Bar Reversal, Pocket**. When the fired pattern is one of those four, `any_pa` is true in *both* modes, so a GO legitimately **holds** across a Bull↔Recovery flip. That used to look like "the trigger ignores the path." It is now made explicit on the TRIGGER row:

- **`⇄both`** — the GO rests only on a shared pattern; it holds in either path.
- **`Bull-only` / `Rec-only`** — the GO carries a path-exclusive pattern (VCP-BO, HTF, Stage-2 Launch, Climax, Wyckoff SOS, …); it drops if you flip away from that path.

GO always requires a PA pattern (`go = any_pa and support_pass and vol_ok and bar_ok`) — it was **never** location-only.

---

<a name="4-the-pa-battery"></a>
## 4. The PA Battery — 17 Bull / 10 Recovery patterns

The battery is a 1:1 port of the Golden Matcher's `_detect_pa_patterns` / `_detect_recovery_pa_patterns` (which mirror Dashboard v67.4.12) — **zero drift**: when a name reaches Step 5, this Pine panel shows the identical patterns firing. Patterns are **bonuses** that sum to a **Σ tier** (Jay's rule: 11/11 is *not* the benchmark — a single high-quality trigger at a location is enough).

The PA grid on the panel shows **every** condition as fired (✓) or quiet (·) — nothing is aggregated away. The header reads `PA · BULL (…)` / `PA · RECOVERY (…)` and the right cell shows `Sum +N` colour-coded (≥4 purple / ≥2 green / ≥1 amber / 0 grey).

### 4.1 Bull battery (17) with weights

| Group | Pattern | Weight | Meaning |
|---|---|---:|---|
| Power Play | **HTF** — High Tight Flag | +4 | The rare, explosive Minervini/O'Neil pattern (near-vertical pole, tight 3-5 wk flag). *Not* a generic bull flag. |
| Power Play | **SC** — Strong Close | +2 | Close in the top of the range on expansion. |
| Momentum | **VCP-BO** — Volatility Contraction breakout | +3 | Breakout out of a VCP with volume dry-up (`ta.vwma(volume,5) < sma(volume,50)`). |
| Momentum | **LAU** — Stage-2 Launch | +3 | True **weekly** close crossover of a rising 30-WMA (+ volume gate) — mirrors Python's `"2" in stage`. Won't fire on a Stage-4 dead-cat bounce. |
| Momentum | **PP** — Pocket Pivot | +2 | Pocket-pivot volume signature. *(shared)* |
| Momentum | **LIQ** — Liquidity Sweep | +2 | Stop-run below support then reclaim. |
| Momentum | **GAP** — Gap-up breakout | +3 | Gap-up breakout day. |
| Momentum | **BC** — Breakout-Confirmed | +2 | A confirmed follow-through on a prior breakout. |
| Reversal | **ENG** — Bull Engulfing (gated) | +2 | Bullish engulfing at the daily EMA20 anchor. *(shared)* |
| Reversal | **3BR** — 3-Bar Reversal | +2 | Three-bar reversal structure. *(shared)* |
| Reversal | **SPR** — Wyckoff Spring | +3 | Spring below support then reclaim. *(shared)* |
| Reversal | **U50** — 50-SMA Undercut & rally | +2 | Undercut of the 50-SMA then reclaim. |
| Reversal | **H50** — Hammer at 50-SMA | +2 | Hammer reversal at the 50-SMA. |
| Reversal | **H200** — Hammer at 200-DMA | +2 | Hammer reversal at the 200-DMA. |
| Coil | **IN3** — Inside-3 | +2 | Three inside bars (compression). |
| Coil | **NR7** — True NR7 | +1 | Narrowest range of 7 bars. |
| Coil | **IBN** — IB-NR7 | +2 | Inside-bar NR7 (tightest coil). |

### 4.2 Recovery battery (10) with weights

| Pattern | Weight | Meaning |
|---|---:|---|
| **CLIMAX** — Climax reversal (SC + AR) | +3 | Selling climax + automatic rally. |
| **SPR** — Wyckoff Spring | +3 | Spring below support then reclaim. *(shared)* |
| **2B** — Higher-Low / 2B | +3 | Higher low / 2B reversal (near base). |
| **SOS** — Base Breakout (Sign Of Strength / JAC) | +3 | Break out of the accumulation base. |
| **ENG** — Bull Engulfing | +2 | *(shared)* |
| **HSUP** — Hammer at support | +2 | Hammer reversal at support. |
| **3BR** — 3-Bar Reversal | +2 | *(shared)* |
| **PP** — Pocket Pivot | +2 | *(shared)* |
| **VDU** — Volume Dry-Up | +1 | Volume drying into the base. |
| **30WMA** — 30-WMA reclaim | +3 | Weekly reclaim of the 30-week MA. |

### 4.3 Evaluation timeframe

- `use_chart_tf` (default ON) — the battery runs on the **chart timeframe** (75/125m) to match the GM's 75m default. HTF-anchored patterns (HTF, Stage-2 Launch, 30-WMA reclaim) stay suppressed on intraday; the engulf keeps its **daily** EMA20 anchor (EMA20 is always a daily reference by DNA).
- `confirm_daily` (default ON) — when reading Daily (i.e. `use_chart_tf` OFF), read the **last closed** daily bar. The `[_o]` offset is applied *inside* the daily-context function, so it is measured in **daily bars** and is timeframe-independent (works correctly on a 75/125m chart).

---

<a name="5-anchored-vwaps"></a>
## 5. Anchored VWAPs — Price Memory

Three AVWAP curves mark where the *average institutional participant* is positioned since a structural event:

| Anchor | Input | Anchored to |
|---|---|---|
| **Low** | `show_low` | The lowest low in the last `low_look` days (default **252** = one trading year) — the Stage-1 bottom. |
| **BO** | `show_bo` | The start of the current breakout move (last `bo_look` days, default **40**). |
| **Gap** | `show_gap` | The most recent significant gap-up (≥ `gap_pct` = **3%** on ≥ `gap_volx` = **1.5×** the 50-day average volume). |

**Panel reads:**
- **AVWAP L-BO-Gap** — the three anchor prices, one row (clubbed).
- **Pinch** — how tightly the three AVWAPs are coiled (`pinch_pct`, default **2.5%** spread). A pinch is a compression-into-a-decision read; it earns a confluence point.
- **AVWAP trigger** — a **bounce** off an AVWAP support, or a **R2G** (return-to-green) reclaim above the breakout AVWAP. This is a *timing* event (+2 confluence, ⏱).
- **Nearest AVWAP** — the closest AVWAP below price and the distance.

> AVWAP anchor implementation note: the accumulator sentinel is seeded to `0` (not `na`), and anchor **dates** come from `ta.valuewhen`, so the anchors latch reliably (a known Pine gotcha the code guards against).

---

<a name="6-the-intraday-trigger"></a>
## 6. The Intraday Trigger — 10-EMA + TTM Squeeze

Apply on **75/125-min**. The intraday trigger is a *timing* leg (+2 confluence, ⏱); it is optional to GO but strengthens it:

```
Intraday GO ⇔ price reclaims a RISING 10-EMA  AND (require_squeeze ⇒ a TTM squeeze fires UP)
```

- `ema_len` (default **10**) — the reclaim EMA.
- `require_squeeze` (default **ON**) — require a TTM Squeeze **release** (volatility expansion). OFF = a high-volume 10-EMA reclaim alone suffices.
- TTM Squeeze math: Bollinger Bands (`bb_mult` **2.0**) inside Keltner Channels (`kc_mult` **1.5**) over `sqz_len` (**20**). Squeeze *on* = BB inside KC (compression); *fires* = BB expands back outside KC.

> `request.security(D)` on an intraday chart returns the **forming** daily bar — so intraday reads of daily structure (NR7, coils) repaint early-session (RV ~0.1 is the tell) and are only real at the daily close. This is why `confirm_daily` / `use_closed_candle` exist.

---

<a name="6a-arrival-order-flow"></a>
## 6a. Arrival Style & Order-Flow Footprint (v4.0)

*"How price returns to a zone matters as much as the zone."* Two quality reads for a zone price is currently at, surfaced on the **"Arrival · Δ"** panel row and as two opt-in confluence points.

### 6a.1 Arrival Style (pure geometry — fully real)

The **approach leg** into the zone is measured: for a demand zone, the drop from the swing high (`arr_look` **20** bars back) to the current low; for supply, the rally from the swing low. The core metric is **velocity in ATR/bar** = distance covered (in ATR) ÷ bars taken.

| Style | Condition | Read |
|---|---|---|
| **FAST** | velocity ≥ `arr_vel_fast` (**0.5**) | High-velocity impulsive arrival → **sharp rejection likely** (favourable). |
| **GRIND** | velocity ≤ `arr_vel_slow` (**0.22**) | Slow stair-step → momentum **absorbing** the level → **bleed-through risk** (caution). |
| **NORMAL** | between the two | Ordinary approach. |

A **FAST** arrival at a zone earns a confluence point (`cf_w_arrival`).

### 6a.2 Order-Flow Footprint — an intrabar volume-delta *proxy*

Pine has **no access to true tick/aggressor order-flow on any TradingView plan** — so this is an honest **proxy**: `request.security_lower_tf` pulls the lower-timeframe sub-bars (`of_ltf`, default **1-min**) inside each chart bar and classifies each sub-bar's volume **buy** (closed up) or **sell** (closed down). This chart bar's **delta** = `sum(up) − sum(down)` — exactly the method behind TradingView's built-in *Up/Down Volume*.

The read (over `of_win` **5** bars):
- **ABSORBING Δ+** — net buying at the demand zone, **or** a **bullish delta divergence** (price made a *lower low* while delta made a *higher low* — sellers pushing price down on shrinking net supply = buyers absorbing).
- **BLEEDING Δ−** — net selling with no absorption (price bleeding through).
- **NEUTRAL Δ** — no clear signal.

(Mirror at a supply zone: absorbing Δ− = sellers in control.) An absorbing read earns a confluence point (`cf_w_absorb`).

> **Honest limits:** (1) the delta is volume *classified by sub-bar direction*, **not** true bid/ask aggressor delta. (2) `request.security_lower_tf` caps total intrabars (~100k), so the delta is reliable on **recent** bars — which is all the arrival read needs. (3) `of_ltf` **must be lower than the chart TF** (default 1-min is safe on 75/125m/D/W/M; for Premium **seconds** delta set `1S`/`5S`; do not apply on a ≤1-min chart).

### 6a.3 Panel & scoring

- **"Arrival · Δ" row** — e.g. `FAST 0.63 ATR/bar · absorbing Δ+`, or `— (not at a zone)` in open space. Green when sharp **and** absorbing, teal when absorbing, amber on GRIND.
- **Confluence** — `cf_w_arrival` (sharp arrival) and `cf_w_absorb` (absorbing), each default **1**, independent, gated by `show_arrival` (hide = ignore). They **grade** the GO, they do **not** gate it.

---

<a name="7-the-zone-engine"></a>
## 7. The Zone Engine — Anatomy of a Demand/Supply Zone

Ported wholesale from the **Institutional Zone Engine v4.2**. A zone is a **leg-in → base → leg-out** formation. Four patterns, named from the leg-in's colour and the leg-out's direction:

| Pattern | Structure | Distal spans |
|---|---|---|
| **DBR** — Drop-Base-Rally | down leg-in, base, up leg-out (demand) | full formation incl. leg-in |
| **RBR** — Rally-Base-Rally | up leg-in, base, up leg-out (demand) | base + leg-out only |
| **RBD** — Rally-Base-Drop | up leg-in, base, down leg-out (supply) | full formation incl. leg-in |
| **DBD** — Drop-Base-Drop | down leg-in, base, down leg-out (supply) | base + leg-out only |

### 7.1 Invisible (gap-bridged) candles

Zone detection **always** reads gap-bridged OHLC: each bar's open is re-anchored at the previous close and the high/low expanded to cover any gap. *A small-bodied gap day is really a big leg candle*, and this is how the engine sees that. It's the marking methodology, not a preference. Turn on **"Draw Invisible Candles"** (`drawInvCandles`, Visual group) to *see* them; the detection is identical whether or not you draw them.

### 7.2 Leg candles

- **Leg-out strength** — a leg's True Range must exceed `ercMult` (**1.2**) × ATR14. A **Strong** leg has body/range ≥ `legBodyRatio` (**0.75**). An **Average** leg has body/range ≥ `legBodyAvg` (**0.55**) but below Strong — it is rejected unless *rescued* by follow-through.
- **Follow-through rescue** — an Average leg-out may be rescued by up to `ftMaxRescue` (**2**) bars whose net displacement > `strongFTMult` (**0.75**) × ATR **with no close back through the leg-out's opposite extreme** (`noRevBull`/`noRevBear`). A wicky follow-through bar that *pierces* but closes back inside is fine. When rescued, the follow-through bar *becomes* the leg-out → the zone is **narrower**.
- **Confirmation lag** — `ftLagBars` (**1**, min 1). A zone is drawn 1 closed bar after the leg-out (non-repainting). At 0 the leg-out would be the forming bar and the FVG couldn't be measured — hence the min of 1.

### 7.3 Leg-in — and the per-TF strictness (#35)

The **leg-in** must itself *be a leg*, its max wick/body ≤ `legInMaxWickR` (**1.0**). Its minimum range is now **per-timeframe** (v3.8), resolving the tension between over-marking on fast TFs and spurious HTF bases:

- `legin_ltf` (**0.6** × ATR) — intraday + daily → *more zones* (fixes "many daily/intraday zones not being marked").
- `legin_htf` (**1.2** × ATR) — weekly + monthly → no spurious bases (e.g. the Acutaas monthly double-zone).

The native (chart-TF) call picks by chart TF; the D/W/M security calls hardcode their tier. Lower `legin_ltf` for even more daily/intraday zones; watch `natC d` / `pat D d` on the diagnostics row.

### 7.4 Base candles

A candle is a **base** when its body/range ≤ `bodyRatio` (**0.65**) **or** its true range < `base_rng_atr` (**0.6**) × ATR — and always < `maxBaseTR` (**2.5**) × ATR (the hard veto). Base runs are `minBase` (**1**) to `maxBase` (**6**) candles, tolerating `baseStreak` (**0**) non-base interruptions.

### 7.5 Proximal, distal, and narrow wick-to-wick (#34)

- **Distal** (far edge / stop side) — **always a wick** (house rule, 17-Jul): the min low over the pattern-aware scan range for demand, max high for supply.
- **Proximal** (near edge / entry side) — the **body extreme** by default (`proxLineMode = "Body Extreme"`; can be "Wick Extreme").
- **#34 narrow-zone wick-to-wick** (`narrowWickToWick`, ON) — when a thin-bodied base makes the body-to-wick zone *narrower than the width floor*, the proximal is widened to the base's own **wick** (upper wick for demand, lower wick for supply), rescuing a precise zone that would otherwise be rejected as too narrow.

### 7.6 Width band (per timeframe)

A zone is accepted only when its width (proximal − distal) is within `[Min, Max] × ATR14` of its **own** timeframe:

| TF | Min | Max |
|---|---:|---:|
| Monthly | 0.5 | 4.0 |
| Weekly | 0.4 | 3.5 |
| Daily | 0.3 | 3.0 |
| 125-min | 0.25 | 2.5 |
| 75-min | 0.2 | 2.0 |

Tighter maxima on LTF force crisp entries; wider maxima on HTF allow broad institutional bases. The **#34** rescue widens sub-floor zones up into this band rather than dropping them.

### 7.7 FVG Polygraph & the provisional preview

- **FVG Polygraph** — a zone whose leg-out left a **Fair Value Gap** (imbalance) is `hasFVG` → tagged **⚡** with a brighter border. On intraday, `require_intraday_fvg` (default **OFF**, "Option C") *draws all* qualifying zones and only *tags* the FVG-backed ones; turn ON ("Option A") to draw *only* FVG-backed native zones on 75/125m.
- **Provisional preview** — `prov_zone` (ON) draws a **dashed** preview of a *Strong* leg-out on the last closed bar, before follow-through/FVG can be measured. It does **not** gate GO/support and is **not** in the zone counts — the real zone is created on the next bar. This matters at a **Friday close**, when the next real bar is the whole weekend away (exactly when you mark zones).

### 7.8 Native-TF filters (optional, default off)

`volMult` (leg-out volume surge, 0 = off), `useEMA` (require daily EMA20 alignment), `useRS` (require Nifty-500 RS positive), `requireBOS` (require a break of structure). All default off so the pure geometry stands alone.

---

<a name="8-zone-scoring"></a>
## 8. Zone Scoring, Confluence & Controlling Zones

### 8.1 The base score

Each zone gets a raw score from: leg-out body strength (up to +40), volume surge (floored at 0, up to +30 — a below-average leg-out no longer *subtracts*), base-candle count (sweet spot 2-4 weighted highest), plus a gap bonus and an FVG bonus. On top of that a **confluence boost** (`f_confluenceBoost`, capped `maxConfBoost` **50**) is added:

| Bonus | Input | Default | When |
|---|---|---:|---|
| HTF overlap | `htfBoost` | 15 | A zone nested inside a higher-TF zone. |
| Same-TF overlap | `sameTfBoost` | 5 | Two zones overlap on the same TF. |
| EMA20 proximity | `emaProxBoost` | 10 | Zone is **within** `emaProxThreshATR` (**0.5** ATR) of the daily EMA20. *(Proximity only — the old half-plane clause that gave every uptrend demand zone +10 was removed, which is why ★ used to read a uniform ★10.)* |
| Leg-out gap | `gapBonus` | 10 | Leg-out gapped away from the base (measured on **raw** prices — the gap-bridge erases the gap). |
| FVG | `fvgBonus` | 15 | Leg-out left an FVG (measured on **raw** prices). |

The label shows `<Pattern> <score>pts <nBase>B ★<bonus>` (e.g. `RBR 81pts 3B ★10`), with a ⚡ if FVG-backed.

### 8.2 Recency decay (#27) — Age vs Recency

Two factors measure a zone: **Age** (how long until it ages off — §9.4) and **Recency** (a fresh zone is a stronger zone). With `recencyDecay` (ON), the **displayed** score decays *linearly from formation to the TF's ageing cap*, floored at 0, losing up to `recencyMaxDrop` (**20**) points at full age. So a 90-pt fresh zone reads ~80 at half-life and ~70 near aged-out — enough to break score ties toward the fresher zone without demoting a genuinely strong old base. The decay is reflected in **both** the on-chart label and the panel's Support-Zone grade. The intrinsic score (`z.strength`) is preserved internally; recency is a display/ranking overlay.

### 8.3 Controlling zones — all three criteria

A **Controlling** zone is the dominant structural zone. A demand zone is Controlling only if it satisfies (`markControlling` ON, `controllingMinTf` = Daily):

1. **Leads to a new ATH** — not *continues* one. Requires `ctrlMinLowerHighs` (**2**) bars of lower highs between the prior ATH and the zone's leg-in (price came *off* the high before the zone formed), the base below the prior ATH, and the leg-out closing through it. Expect Controlling to be **rare** on a strong trender — that's the rule working.
2. **Trend reversal** — the zone reversed the trend (was below the 50-SMA for the prior 20 bars, leg-out closes back above).
3. **Breaks an opposing controlling zone** — the zone's leg-out broke through an existing opposing controlling zone.

**Exclusive-controlling:** only the demand zone *nearest the ATH* stays Controlling; a new qualifying zone demotes the incumbent. Controlling zones draw with a thicker border and a "Controlling" label prefix, and earn a confluence point (`cf_w_ctrl`).

---

<a name="9-zone-lifecycle"></a>
## 9. Zone Lifecycle — Fresh → Tested → Violated

A zone is **fuel**: it is *consumed* by a test. (Contrast an S/R **level**, §12, which is *price memory* and survives a test, weakened.) All lifecycle transitions are judged on **closed bars only** (nothing permanent happens on an unconfirmed bar — the live chart and a reloaded chart must agree).

### 9.1 Reaction

A zone `reacted` when a prior candle touched/closed-within it and a later candle moved back out past the proximal (Jay's definition of a reaction).

### 9.2 The three Tested rules (OR'd — loosest wins)

Once reacted, a zone is **tested** (and removed, unless grey-tested is on) if **any** of:

1. **Travel** — price travels `testedTravelATR` (**2.0**) × the zone's **own TF's ATR** from the reaction reference (`testedTravelMode = "ATR"`; the legacy "Zone width" mode is inverted — it retired the *narrowest, most precise* zones fastest, so ATR is the default). A Monthly zone is judged in *monthly* ATR even when drawn on a 75m chart.
2. **EMA cross** — a close across the daily EMA20 (from the pre-cross side).
3. **Level cross** — a close across the nearest strong HTF pivot (`strongPivotTF` = Daily).

**#25/#40/#42 fix (v3.8):** rules 2 & 3 use *daily* references, so they are same-TF-appropriate **only for a daily zone**. They used to apply to **weekly and monthly** zones too, retiring a weekly zone the instant price closed above the *daily* EMA20 — far too fast (CoalIndia showed 3 of 37 weekly zones alive). Now, with `tested_tf_match` ON (default), rules 2 & 3 apply to **daily zones only**; **weekly and monthly** zones are judged by **travel + violation only**, exactly like native intraday zones. Set `tested_tf_match` OFF for the pre-v3.2 behaviour (daily references judge every TF).

### 9.3 Violation

A zone is **violated** (deleted) when price closes through the **distal** per `mitBasis` (`Body Close` / `Wick Close` / `50% Penetration`). A faint red **dot** (`markViolations`) marks the break — the only trace left behind.

### 9.4 Ageing (calendar, per TF)

A zone ages out this many **calendar days after formation**: Monthly `age_monthly_days` **1460** (4y) · Weekly **730** (2y) · Daily **182** (6mo) · 125-min **28** (4wk) · 75-min **21** (3wk). So intraday zones stop populating indefinitely to the left while HTF zones persist for years.

### 9.5 Grey-tested (#41) & transparency (#37)

- **`show_tested_grey`** (default **OFF**) — instead of *deleting* a tested zone, recolour it **grey + dotted** and **freeze** it (a `Zone.tested` flag). Grey zones are excluded from the trigger, support, and the live DZ/SZ counts — they're a **verification overlay** so you can confirm *every* zone that ever formed was marked correctly. This is the tool for "why isn't this zone drawn?"
- **`zoneFillTransp`** (default **88**, was hard-wired 93-96) — the base fill transparency (lower = more visible), with a per-TF spread (Monthly most opaque). Controlling zones read 4 steps more opaque.

---

<a name="10-structural-pivot-zones"></a>
## 10. Structural (Pivot) Zones

Beyond the leg-base-leg **pattern** zones, the engine also draws **structural (pivot)** zones (`PvH`/`PvL`) from a bare swing high/low — a **weaker, secondary shelf** with no departure impulse.

- **Master toggle:** **"Draw Pivot (Structural) zones"** (`useStructural`, ON). Uncheck to hide *all* pivot zones on all TFs — the isolation lever for "why isn't a pattern DZ/SZ marking?" (turn pivots off → see only pattern zones).
- **Drawn dashed**, capped score **75** (so a genuine pattern zone, 95-100, always out-ranks a pivot zone).
- **They never override pattern zones** — pattern zones are created *first* (native → D/W/M) and always survive the dedup; a pivot zone is *skipped* when it overlaps a same-TF, same-direction pattern zone.
- **Width floor:** `structMinWMult` (**0.5**) scales the band floor down for pivots (a pivot zone is body-to-low of *one* candle, legitimately narrower). If pivots vanish, *lower* this, don't disable the band.
- **Same lifecycle** as pattern zones (ageing, tested, violation). **No volume profile** anywhere in the engine.
- **How to trade them:** as location/stop confluence, not standalone — best when they stack with an HTF pivot or the EMA20. Prefer a pattern zone when both exist.

---

<a name="11-mtf-propagation"></a>
## 11. Multi-Timeframe Propagation

Zones are detected natively on the chart TF **and** via `request.security` on **Daily / Weekly / Monthly**. The universal `f_detectZone` runs identically in every context (single source of truth). HTF zones show on the chart and every *lower* TF, never upward. Toggles: `showChartZones`, `showDaily`, `showWeekly`, `showMonthly`.

- **Cross-TF overlaps are KEPT** (they are confluence — a daily zone inside a weekly one) — dedup is **same-TF only**. This was the fix for HTF (esp. Monthly) zones failing to propagate.
- **Native structural** stays suppressed on an intraday chart (minor LTF pivots = noise); on Daily+ it draws.

---

<a name="12-sr-levels"></a>
## 12. S/R Levels — Clustering, MTTWR, and the R↔S Flip

Horizontal levels, absorbed from the retired Commander Chart Markup. A **level is price memory** — the opposite of a zone.

### 12.1 Clustering (`f_srLevels`)

Confirmed pivots (length `sr_pv` **5** each side) are clustered into **persistent level objects**: a new pivot either *merges* into the nearest level within `sr_tol` (**0.6** × that TF's ATR) — updating a running-mean price and a **cumulative** touch count — or *creates* a new level. Each TF keeps a deep **40-pivot pool** (`sr_pool`) at its own ATR scale, so a level from 8 months back stays reachable (the single biggest reason the old S/R felt immature). Levels are first-class objects, so a touch count **never decays** as old pivots evict (which used to silently downgrade an MTTWR level back to "fresh").

### 12.2 Wick-pierce touches (#30) — `sr_wick_touch` (ON)

A pivot counts toward a level not only when its **extreme** is within tolerance, but also when the level line **pierces the pivot's wick** (upper wick of a high, lower wick of a low). One line can then thread the wicks of *more* pivots, so the touch count reflects the real number it holds. A wick-pierce touch is **counted but does not drag** the level's price (the line stays where it threads the wicks); only a near-extreme touch nudges the mean. Still **pivot wicks only** — never arbitrary bars.

### 12.3 Grade — tests WEAKEN a level (MTTWR)

The house rule, opposite to most tools:

- `sr_min_touch` (**2**) touches = **FRESH** (strongest as support — just proved itself, unspent).
- `2 … n-1` = **TESTED** (valid, weakening).
- ≥ `mttwrEff` (from `sr_mttwr_n` **4**, clamped above min-touch) = **MTTWR / MTTWS** (Multiple Times Tested Weak) — *primed to break*, drawn dashed and **excluded** from the support picker (leaning a stop on a level primed to break is the mistake the grade exists to prevent).
- `sr_minspace` (**5** bars) — two touches closer than this count as **one** test (Bulkowski), stopping a wick cluster from inflating the grade.

### 12.4 Role is derived; the R↔S flip

A level's **role** (Support vs Resistance) is derived from price *live*, never fixed at detection — so a level **flips** Support↔Resistance when price closes through it. Its **origin** (born from pivot highs or lows) is kept so the flip is knowable. The panel's **S/R (nearest)** row shows the nearest level each side, its TF tag (the TF *is* the conviction — a weekly-level stop is a deeper distal → wider stop → size down), distance %, and the R:R to it.

### 12.5 Timeframe scoping & manual tiers

Every level shows on its own TF and **every lower one, never upward** (Monthly everywhere · Weekly on W and below · Daily on D and below). `sr_show_M/W/D` toggle per TF.

**Manual levels** (`sr_on`) **outrank** auto on any side you've marked — your hand-drawn levels *are* the location layer (Gate 2); auto is the fallback for a side you haven't marked. Up to 4 prices each for **Monthly** (`mv1-4`, shows on all TFs), **Weekly** (`wv1-4`, W and below), **Daily** (`dv1-4`, D and below). A marked side suppresses its auto pair.

---

<a name="13-trendlines"></a>
## 13. Trendlines — Manual & Machine-Readable

There is **no auto-fitter** — the Chart Markup fitter was rewritten nine times and never converged, because "which two pivots" is chart-specific, not a global setting. Instead the trendlines are **manual but machine-readable**: the engine *reads* your line to feed the nearest-S/R pickers, the Plan's stop/target, and the confluence score (`cf_w_tl`), and it updates live as you drag the slope.

**#47 fix (v3.6):** the anchors were `input.time/input.price(confirm=true)`, which forced a click-to-place on **every** add and cancelled the whole indicator on **Esc** ("it forces me to draw a Trendline first, else it closes"). Pine has no conditional confirm, so the 12 box/trendline anchors are now plain **numeric inputs (0 = off)** — type the two time/price pairs in the settings dialog. Loading is instant; the line is still draggable once drawn. One support + one resistance pair, each with its own TF tag; shows on its own TF and below.

---

<a name="14-geometry"></a>
## 14. Geometry & Rectangles

A pivot-based geometry read (`show_geom`, pivot length `geo_pv` **5**, flat tolerance `geo_flat` **0.3** ATR, max pivot age `geo_maxage` **120**) classifies the last two pivot highs + lows into a shape:

| Highs \ Lows | Flat | Up | Down |
|---|---|---|---|
| **Flat** | Range / rectangle | Ascending triangle → *(flat highs, rising lows)* | Broadening (descending) |
| **Down** | Descending triangle | Symmetrical triangle | Falling channel / wedge |
| **Up** | Broadening (ascending) | Rising channel / wedge | Broadening |

**#59 fix (v3.8) — no more phantom shape.** The panel used to *name* "Rising channel/wedge" (which fires on almost any trend) without drawing anything. Now, with `drawGeomLines` (ON), the two pivot connectors that produced the classification are **drawn** (dashed, extended right) so the named shape is visible.

**#31 (v3.9) — rectangles as patterns.** A **"Range / rectangle"** classification is drawn as a **box** (flat top/bottom at the mean of the two highs/lows, from the earliest pivot, extended right) rather than two lines; every other shape keeps its connector lines.

**Bull flag** detection (separate from geometry): `pole_look`, `cons_bars`, min pole size, max flag retrace (else it's a reversal not a flag), volume dry-up, and required counter-trend drift — feeds `cf_w_flag`, not the PA battery (no double-count).

---

<a name="15-the-plan"></a>
## 15. The Plan — Entry / SL / Targets / R:R / Sizing

Computed **only when GO is live**:

- **Entry** (`pl_entry`) — the trigger/breakout level. On a confirmed GO, arm a **buy-STOP above the trigger bar's high** (confirmation before entry — never a buy-limit at the zone).
- **Stop-Loss** (`pl_sl`, source `pl_slsrc`) — **structural**: the nearest demand-zone **distal** below entry (OB/FVG/pivot, Daily + Weekly), else the recent swing low, else `2.5 × ATR`, **capped at 3 × ATR** (flagged ⚠ when capped — the structural level is further and the stop is tighter than the invalidation). A `plan_slbuf_pct` (**0.5%**) buffer is placed below the level to survive wick-hunts. When no zone/engine SL exists, the **EMA20** is the dynamic-support fallback stop.
- **Targets** — **T1** = the nearest overhead obstacle (supply zone / flipped pivot / HTF pivot), **T2** = the *second* overhead (`_ovh2`; reads "open — no 2nd obstacle" rather than inventing one). Each shows its **R** multiple and % move.
- **Room for Trade** — the distance to the nearest overhead: `BLUE SKY` (clear) / `NO ROOM x% · yR` (an obstacle is too close). This is the honest ceiling check.
- **R:R** — colour-coded (≥2 green / ≥1 yellow / <1 red).

**Position sizing** (`grpSize`): `size_cap` (Capital ₹) and `size_risk` (**0.25%** house rule). Qty = Capital × Risk% / (Entry − SL) — the **same** trade the plan describes.

**The VERDICT** (§16) applies both house rules: **swing needs ≥ 2.0R**, **positional needs ≥ 20% ROI to T1**, and says plainly when a clean entry is *not* worth the risk.

---

<a name="16-the-panel"></a>
## 16. The Panel — Row by Row

The panel (`show_panel`, position `panel_pos`) renders in a fixed, deduplicated order (renumbered 0-29 in the v3.4 rebuild so no two writes collide). Reading top to bottom:

| Row | Shows |
|---|---|
| **Header** | Ticker + `S4 ENTRY TRIGGER`. |
| **AVWAP L-BO-Gap** | The three AVWAP anchor prices (clubbed). |
| **Pinch** | AVWAP pinch state + spread %. |
| **AVWAP trigger** | Bounce / R2G reclaim / waiting. |
| **Nearest AVWAP** | Closest AVWAP + distance. |
| **Support Zone** | The zone price is in: DZ/SZ, ⚡ FVG, TF, quality grade (EXCELLENT 90+ / STRONG 75-89 / GOOD 60-74 / AVERAGE 45-59 / WEAK <45, **recency-adjusted**), Fib tag. |
| **Zones (MTF)** | The tradeable read: `IN DEMAND ★ctrl ⚡ ×2TF · N DZ / M SZ live`. |
| **S/R (nearest)** | Nearest level each side (price · TF · dist% · R:R), grade (fresh/tested/MTTWR). |
| **Price vs EMA20** | Distance to the daily EMA20 (BELOW / ABOVE / OvrExt). |
| **Room for Trade** | Nearest overhead obstacle / BLUE SKY / NO ROOM. |
| **Pattern \| Shape** | Bull flag + the geometry shape (now drawn, §14). |
| **Intraday** | 10-EMA / squeeze state (chart-TF). |
| **RV** | Relative volume (colour: ≥1.25 green / ≥1.0 amber / <1 red). |
| **Confluence** | `N/max` + which confluences fired. |
| **TRIGGER** | The GO gate: `GO / no PA / no location / no volume / weak-red bar` · `P✓ L✓ V✓ B✓ ⏱` · **`⇄both`/`Bull-only`/`Rec-only`** · confluence. Amber when waiting (**#61**), green/bright-green on GO/GO★. |
| **Plan** | The method in words (structural stop, targets). |
| **Entry · SL · T1 · T2** | The numbers (SL % risk, T1/T2 R and %). |
| **Qty @ risk%** | Shares from Capital/Risk. |
| **PA · BULL/RECOVERY** | Header + `Sum +N`. |
| **PA grid** | Every pattern ✓/· (mode-aware). |
| **Structure basis** | off52% · 30-WMA · 200-DMA → auto-picked path (always written). |
| **STATUS** | One-line verbatim summary of every gate + the blocking reason (amber waiting / green GO). |
| **VERDICT** | (**#62**, `show_analysis`) the one synthesized line: swing-vs-positional per the house rules. |
| **Diagnostics** | (`show_diag`, off) the funnel — see §17. |

---

<a name="17-diagnostics"></a>
## 17. Diagnostics & the 3-Lever Toolkit

Turn on **"Show engine diagnostics row"** (`show_diag`). The row reads:

```
natC d<detected> f<fvg-pass> m<created> L<live>
   |  pat D d/c·L   W d/c·L   M d/c·L
   |  struct D<det> C<created> L<live>
   |  removed: age · travel · emaX · lvlX · violated
```

- **`natC`** — the **native chart-TF** pattern funnel: detected → passed the FVG gate → created → live.
- **`pat D/W/M`** (**#36/#40**, v3.9) — the **per-TF pattern funnel** for the Daily/Weekly/Monthly `request.security` zones (which the native funnel is blind to). For a zone that isn't marking:
  - **`d = 0`** → a **detection gate** rejected it (leg / base / width / leg-in) → tune `legin_ltf`/`legin_htf` or the width band.
  - **`d > 0, c = 0`** → EMA/RS gate or dedup in `f_createZone`.
  - **`c > 0`, low `L`** → **removal** — read the `removed:` split.
- **`struct`** — the structural (pivot) funnel.
- **`removed:`** — attribution of every deletion (age / travel / EMA-cross / level-cross / violation). Counts overlap (rules are OR'd), so the sum can exceed the removal count.

### The 3-lever diagnostic toolkit

To answer *"why isn't this zone marking / why so many?"*:

1. **Diagnostics row** (above) — detection vs removal, per TF.
2. **"Draw Pivot (Structural) zones" OFF** — isolate to see *only* pattern DZ/SZ.
3. **"Show tested zones in grey" ON** — every zone that ever formed stays visible (grey), so you can confirm it was marked correctly and just consumed.

---

<a name="18-alerts"></a>
## 18. Alerts

- **`alertcondition(go …)`** — "S4 GO (PA + Location + Volume)" — fires on a confirmed GO (gated by `use_closed_candle`, once per bar close).
- **`alert(…)`** — a self-describing GO alert naming the mode (Bull/Recovery), which PA fired, timing, the zone, RV and Σ, with the reminder *"confirm the closed bar → buy-STOP above its high."*
- **Σ-strengthening alert** — fires when *another* pattern joins while one is already live (`pa_fire` only caught the first).

> **Alerts bind to the compiled version at creation.** After you recompile, **delete and re-create** the "S4 GO" alerts, or an old alert keeps evaluating the previous code.

---

<a name="19-parameter-reference"></a>
## 19. Complete Parameter Reference

### Display — layers (master triage; OFF = removed from the decision)
`d_zones` · `d_sr` · `d_tl` · `d_lvls` · `d_avwap` · `d_markers` (visual-only) · `d_pat` · `d_panel`.

### Anchored VWAPs
`show_low/bo/gap` · `low_look` 252 · `bo_look` 40 · `gap_pct` 3.0 · `gap_volx` 1.5.

### Daily PA battery
`mode` Auto · `show_pa` · `use_chart_tf` ON · `confirm_daily` ON · `rv_floor` 1.0 · `auto_dd_floor` 10 · `auto_require_below_200` ON.

### Pinch & entry zone
`pinch_pct` 2.5 · `plan_slbuf_pct` 0.5 · `tol_pct` 1.0 · `require_support` ON · `show_zones` ON.

### Intraday trigger
`show_intraday` · `require_squeeze` ON · `ema_len` 10 · `bb_mult` 2.0 · `kc_mult` 1.5 · `sqz_len` 20.

### Display (2)
`use_closed_candle` ON · `show_panel` · `panel_pos` bottom_right · anchor colours.

### Zones — Geometry
`ercMult` 1.2 · `legBodyRatio` 0.75 · `legBodyAvg` 0.55 · `legInMaxWickR` 1.0 · **`legin_ltf` 0.6** · **`legin_htf` 1.2** · `base_rng_atr` 0.6 · `strongFTMult` 0.75 · `bodyRatio` 0.65 · `maxBaseTR` 2.5 · `minBase` 1 · `maxBase` 6 · `baseStreak` 0 · `ftLagBars` 1 · `ftMaxRescue` 2 · `prov_zone` ON · `proxLineMode` Body Extreme · **`narrowWickToWick` ON**.

### Zones — Width Band (× ATR14)
M 0.5/4.0 · W 0.4/3.5 · D 0.3/3.0 · 125m 0.25/2.5 · 75m 0.2/2.0.

### Zones — Native-TF Filters
`volMult` 0 · `useEMA` off · `useRS` off · `requireBOS` off.

### Zones — Multi-Timeframe
`showChartZones` · `showDaily` · `showWeekly` · `showMonthly` · `require_intraday_fvg` off.

### Zones — Confluence Scoring
`htfBoost` 15 · `sameTfBoost` 5 · `emaProxBoost` 10 · `emaProxThreshATR` 0.5 · `gapBonus` 10 · `fvgBonus` 15 · `maxConfBoost` 50.

### Zones — Controlling
`markControlling` ON · `controllingMinTf` Daily · `ctrlMinLowerHighs` 2.

### Zones — State & Tested Rule
`mitBasis` Body Close · `markViolations` ON · `testedTravelMode` ATR · `testedTravelATR` 2.0 · `testedTravelMult` 2.0 (legacy) · `tested_tf_match` ON · `strongPivotTF` Daily.

### Zones — Ageing (days)
Monthly 1460 · Weekly 730 · Daily 182 · 125m 28 · 75m 21.

### Zones — Visual
`showZonesIZE` · `showLabels` · **`zoneFillTransp` 88** · **`show_tested_grey` off** · **`recencyDecay` ON** · **`recencyMaxDrop` 20** · `drawInvCandles` off + candle colours.

### Zones — Structural (Pivot)
**`useStructural` ON** ("Draw Pivot (Structural) zones") · `pivotLeft` 5 · `pivotRight` 3 · `pivotMinMoveATR` 1.0 · `structPadBars` 3 · `structTopThrATR` 1.5 · `structDeepThrATR` 1.5 · `structMinWMult` 0.5.

### Trigger — Confluence Score
`show_cf` · `show_diag` off · `show_analysis` ON · `cf_strong` 6 · weights: `cf_w_avwap` 2 · `cf_w_intra` 2 · `cf_w_fvg` 1 · `cf_w_ctrl` 1 · `cf_w_sr` 1 · `cf_w_ema` 1 · `cf_w_avwl` 1 · `cf_w_fib` 1 · `cf_w_pinch` 1 · `cf_w_rv` 1 · `cf_w_mtf` 1 · `cf_w_tl` 1 · `cf_w_flag` 1 · **`cf_w_arrival` 1** · **`cf_w_absorb` 1** · `cf_rv_strong` 1.25.

### Arrival & Order-Flow (v4.0)
`show_arrival` ON · `arr_look` 20 · `arr_vel_fast` 0.5 · `arr_vel_slow` 0.22 · `of_ltf` 1-min · `of_win` 5.

### Position Sizing
`size_cap` 0 · `size_risk` 0.25.

### S/R Levels — Auto
`show_sr_lv` · `sr_pool` 40 · `sr_tol` 0.6 · **`sr_wick_touch` ON** · `sr_pv` 5 · `sr_min_touch` 2 · `sr_minspace` 5 · `sr_mttwr_n` 4 · `sr_show_M/W/D`.

### S/R Levels — Manual
`sr_on` ON · Monthly `mv1-4` · Weekly `wv1-4` · Daily `dv1-4` (0 = off).

### Trendlines — Manual
`tl_on` ON · Support `tls_tf/t1/p1/t2/p2` · Resistance `tlr_tf/t1/p1/t2/p2` (numeric, 0 = off).

### Consolidation Box — Manual
`box_on` · `box_t1/t2/hi/lo` (numeric, 0 = off).

### Patterns
`d_pat` · flag detector inputs · `show_geom` · **`drawGeomLines` ON** · `geo_pv` 5 · `geo_flat` 0.3 · `geo_maxage` 120.

---

<a name="20-version-history"></a>
## 20. Version History (v3.5 → v3.9)

**v3.5** — #1 trigger path-specificity (`⇄both` / `Bull-only` / `Rec-only`); #4 Daily zone label → light blue.

**v3.6** — #47 load no longer forces a Trendline draw (removed 12 `confirm=true`); #37 fill transparency input (`zoneFillTransp`); #41 "Show tested zones in grey"; #61 TRIGGER amber-when-waiting; #62 ANALYSIS → VERDICT-only (`show_analysis`).

**v3.7** — #34 narrow-zone wick-to-wick (`narrowWickToWick`); #27 recency decay (`recencyDecay`/`recencyMaxDrop`); verified #2 (FT split), #3 (Controlling criteria), #5 (`use_closed_candle`), #29 (40-pivot pool per TF), #43 (wicky-FT cancel rule).

**v3.8** — **#25/#40/#42** HTF over-removal fix (weekly/monthly judged by travel + violation, not the daily EMA/level cross); #59 phantom geometry → connectors drawn (`drawGeomLines`); pivot-zone toggle surfaced (`useStructural` relabelled); **daily/intraday under-marking** → per-TF leg-in (`legin_ltf` / `legin_htf`).

**v3.9** — #30 S/R wick-pierce touches (`sr_wick_touch`); #31 rectangles drawn as a box; **#36/#40** D/W/M pattern funnel on the diagnostics row (`pat D/W/M`).

**v4.0** — **Arrival Style** (velocity-based FAST/GRIND/NORMAL arrival read) + **Order-Flow Footprint** (intrabar up/down-volume delta *proxy* via `request.security_lower_tf`, with delta-divergence); new "Arrival · Δ" panel row and two confluence weights (`cf_w_arrival`, `cf_w_absorb`). Quality-of-zones #4 (arrival) & #5 (order-flow).

---

<a name="21-workflow-faq"></a>
## 21. Trading Workflow & FAQ

### The workflow

1. **Golden Matcher first.** Only run S4 on a name the GM has filtered to **Step 5**. S4 *times* entries; it never *qualifies* names.
2. **Set the mode.** Auto is fine for most; override to Bull/Recovery manually if the GM disagrees (Pine can't see GM's live decision).
3. **Wait for the zone.** Let price pull into a **fresh** demand zone / FVG / pivot support / manual level (Gate L). A coil (NR7/IB-NR7) is *compression*, not a trigger.
4. **Wait for GO.** The TRIGGER row must read **GO** — a PA pattern (P) at a location (L) with volume (V) on a clean bar (B). Dead-volume reclaims (RV < floor) are skips.
5. **Read the VERDICT.** Swing needs ≥ 2.0R; positional needs ≥ 20% ROI to T1. If NEITHER GATE, the entry may be clean but the trade isn't worth the risk.
6. **Confirmation before entry.** On the alert ping, wait for the **closed** trigger bar and arm a **buy-STOP above its high** — never a buy-limit at the zone. The chart retains veto power: it can talk you *out*, never *into*, a trade.
7. **Size it** at 0.25% risk (the Qty row) and place the GTT.

### FAQ

**Q: Why does the trigger stay when I flip Bull ↔ Recovery?**
Because the fired pattern is one of the four **shared** patterns (Spring/Engulf/3-Bar/Pocket) — it's valid in both paths. The TRIGGER row now says `⇄both`. A path-exclusive pattern shows `Bull-only`/`Rec-only` and *does* drop when you flip.

**Q: A zone I expected isn't drawn.**
Turn on the diagnostics row and read the funnel for its TF (`natC` for the chart TF, `pat D/W/M` for HTF). `d = 0` → detection gate (loosen `legin_ltf`/`legin_htf` or the width band). `c > 0` but gone → it was **removed**; turn on **"Show tested zones in grey"** to see it and read the `removed:` split. As of v3.8, weekly/monthly zones persist far longer (they're no longer retired by the daily EMA cross).

**Q: The panel names a pattern (e.g. Rising channel/wedge) that isn't on the chart.**
As of v3.8 it **is** drawn (`drawGeomLines`) — the two pivot connectors, or a box for a Range/rectangle.

**Q: Loading the indicator forces me to draw a Trendline.**
Fixed in v3.6 — the anchors are numeric now. Enter trendline/box coordinates in the settings dialog (0 = off).

**Q: Bull Flag vs High Tight Flag — same thing?**
No. HTF (in the bull battery, weight +4) is the rare explosive Minervini/O'Neil pattern. A generic Bull Flag is handled by the flag detector (feeds `cf_w_flag`), not the battery.

**Q: Are pivot zones overriding my demand/supply zones?**
No — pattern zones are created first and always win the dedup; pivot zones are the ones skipped on overlap. Uncheck "Draw Pivot (Structural) zones" to isolate.

---

*This is the authoritative user + logic manual for Section 4 Entry Trigger & Price Memory v3.9. It supersedes the earlier v3.4 guide. Pine ↔ Golden-Matcher parity is a design rule (zero drift on the PA battery); some Pine subsystems (zone-engine location) are intentionally richer than the Golden Matcher's OB/FVG/EMA proxy.*
