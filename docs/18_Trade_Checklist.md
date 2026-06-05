# 18 — Swing & Positional Trade Checklist

> **Single source of truth:** `docs/Weinstein_Minervini_Trading_Bible.md` (**v6.0**, 22 May 2026).
> This checklist is the tick-box distillation of the Bible's **9-Step Confluence Sequence (§7D)**,
> the **Bull/Recovery edge exit tables (§8/§9)**, and **position sizing (§10)** — mapped to the
> modules you load and run.
>
> **Deployed versions this is written against** (all aligned with Bible v6.0):
> Dashboard **v67.4.12** (in-file title v67.4.13 = display-only icon/font tweak) ·
> Bull Screener **v3.2** (Py v1.11) · Recovery Screener **v2.0** (Py v1.6) ·
> Unified Ecosystem file **v3.4** / in-file title **v3.6** · Context Layers **v1.2** ·
> Zigzag **Strict v6.2** · Risk Allocator **v1.0** · Web Commander **v4.0** ·
> Scans `SCAN_PARAMS_VERSION = "v2_FINAL_20260510"`.
>
> **Three nuances to internalise (not bugs — read these once):**
> 1. **The Pine catalyst trigger is confirmation, not a gate.** The `*_trigger` booleans in the Unified
>    Ecosystem are deliberately strict — they encode the v1 FINAL + v2 LOCK *backtest* gates, so they stay
>    **silent most of the time even on a clean, tradeable setup**. A silent trigger is **not** a veto. If
>    Steps 1–7 pass and you can see the edge's documented entry conditions on the chart with your own eyes,
>    **you take the trade discretionarily** (Step 8, Path B). Gemini's independent review confirmed:
>    Minervini/VCP discretionary pattern trading is highly viable on Indian mid/small-caps, and rigid
>    algorithmic backtests can't validate a visual pattern. The trigger firing is a *bonus* confirmation, not
>    a prerequisite. **What discretion never overrides:** the macro/sector/score/structure HARD FLOORS
>    (Steps 1–7) and the sizing/SL discipline (Step 9). You may use judgement on *entry timing*; never on
>    regime, conviction, or risk.
> 2. **POS-ACCUM is ENABLED everywhere — and is now PURE PRICE ACTION (June 2026).** It fires identically across
>    `bull_screener.py`, the Pine Bull Screener v3.3, and the Unified Ecosystem. The anti-chase gate is no longer
>    an RSI cap: **`dailyRsi ≤ 50` was replaced by `pa_not_extended` = `close ≤ close[5] × 1.05`** (don't enter an
>    already-extended accumulation), and its VCP was loosened to `f_is_vcp(1.5)` so quiet accumulation isn't
>    starved. In the 24-month nifty500 validation POS-ACCUM is the **strongest catalyst (+3.20% matched alpha)**.
>    Any older note describing "POS-ACCUM gated `d_rsi ≤ 50`" is superseded — the gate is now price action.
> 3. **Exit-table doc lag.** Both Bible §8 and the Unified Ecosystem guide §3 *say* v3.6 widened trails
>    (POS-BO Chandelier 3.0×→4.5×, swing trail EMA20→SMA50, swing targets 5R/10R→3R/5R @33%), but their
>    detailed body tables still show the legacy 3.0×/2.5R/3.5R/EMA20 values. **Trust the input defaults in
>    your loaded v3.6 script** — exits are automated by the strategy, not entered by hand. The exit section
>    below shows the body-table (legacy) values with the v3.6 claim flagged inline.

---

## How to use

- **Two tracks, one funnel.** Swing (8–12 wk, 5–8%) and Positional (6–8 mo, 10–30%) run the **same 9 steps**.
  Track changes only the **catalyst** (Step 4/8), the **time-stop/exit row** (§ Exits), and **risk %** (Step 9).
- **Hard floors are hard.** A failed **HARD FLOOR** = no trade, no matter how strong everything downstream looks.
  The floors encode the v1 FINAL + v2 LOCK backtest verdicts — bypassing them is bypassing the system (DNA rule).
- **Funnel order is one-directional:** Macro → Sector → Watchlist → Stock. If Step 1 or 2 fails, stop — don't score the stock.

### Swing vs Positional — *when and how you decide*

You do **not** pick the track up front. The checklist decides it for you, in three stages:

1. **Lean (Step 2 / 3.5 — RRG tier):** **LEADING + RS-Ratio ≥ 100** → *positional lean*; **IMPROVING + RS-Ratio < 100** → *swing / early-entry lean*. Bias only, not a commitment.
2. **LOCK (Step 4 — the catalyst):** **this is the decision point.** The catalyst *is* the horizon — **POS-BO / POS-AC = Positional** (120/180-day window); **SWG-PB / SWG-BO / GAP-GO = Swing** (30-day); **REV-* = Recovery**. Whatever fires sets the track. *Make the firm call here.*
3. **Operationalize (Step 8 MTF category + Step 9 exit/risk):** **Positional →** Cat-2 (M/W HTF → Daily LTF), room ≥ **20% ROI**, POS exit row (Chandelier trail, 6-wk time-stop), risk 0.75%. **Swing →** Cat-1 (W/D HTF → 75/125 LTF), room ≥ **2R**, SWG exit row (EMA20 ratchet, 10-day time-stop), risk 0.75%.

> **Tie-breaker:** if a positional catalyst (e.g. POS-AC in a Fresh WCDZ) *and* a swing structure both appear,
> default to the **catalyst's horizon** — never cut a positional winner short with a swing-sized target.

---

## PRE-MARKET  (08:00–09:15 IST)

### STEP 1 — MACRO & BREADTH  *(Commander Web → Macro+ / Breadth / AI Brief)*

| Reading | HARD FLOOR | Full-conviction (confluence) |
|---|---|---|
| **CNX500 regime** | NOT BEAR (not Stage 4 / below SMA200 & falling) | BULL: price > SMA200 **and** SMA50 > SMA200 |
| **India VIX** | **< 22** | < 16 optimal · 16–22 tradeable but elevated · **> 22 → halve all sizing** |
| **McClellan (MSI)** | **> −50** | > 0 confirms · > +50 = breadth thrust |
| **FII/DII (5-day)** | not net selling > **₹10,000 Cr** | net buyers = tailwind; persistent FII selling → prefer POS-AC over POS-BO |
| **Sector breadth** | **≥ 4 / 12** sectors Stage 1/2 | ≥ 7 = broad bull · ≤ 3 = narrow, swing-only |

- [ ] All five floors pass.
> **Disqualifier:** CNX500 confirmed BEAR **+ VIX > 25** → **NO BULL TRADES**. Recovery-only mode, half size.

### STEP 2 — SECTOR  *(Commander Web Tab 5 · RRG · Mansfield)*

| Reading | HARD FLOOR | Full-conviction |
|---|---|---|
| Stock's sector — Weinstein Stage | **Stage 1 or 2** | Stage 2 + rising 30W slope |
| Sector RRG quadrant | **NOT LAGGING** | LEADING (full) · IMPROVING (smaller) · WEAKENING → avoid POS-BO. *(Pre-filtered over the weekend — see Step 3.5)* |
| Sector Mansfield RS vs CNX500 | **≥ 0** | ≥ +5 leading · ≥ +10 strong rotation-in |
| Weeks in sector stage | **≤ 26** | < 13 best · 13–26 mature-but-good · > 26 downgrade |

- [ ] Sector NOT Stage 3/4 (hard reject), NOT LAGGING.
> **Boost:** top-3 sectors all Stage 2 + LEADING + rising RS → bias the whole day's watchlist to them.

### STEP 3 — AUTO-PILOT WATCHLIST  *(Commander Web → 🤖 Run Full Auto-Pilot)*

- [ ] Stock is in `FINAL_WATCHLIST.csv` (Golden Matcher, conviction-ranked).
- [ ] **Matcher conviction ≥ 6.0** (already enforced by matcher).  **← HARD FLOOR**
> **Boost:** appears in BOTH `FINAL_Hunter_Picks.csv` AND `FINAL_Leader_Picks.csv` = dual-strategy confirmation → top priority.
> **Never** hand-add a ticker outside Auto-Pilot output — that's bypassing the system.

### STEP 3.5 — WEEKEND RRG PRE-FILTER  *(Strike.Money — run on the Auto-Pilot CSV candidates)*

> Run the Full Auto-Pilot CSV candidates through RRG on Strike.Money, keep only **LEADING / IMPROVING**
> quadrants, and bias the universe to **LEADING / IMPROVING sectors**. This is a *universe-narrowing pre-filter*
> done over the weekend — it front-loads Step 2 + the RS half of Steps 4–5. It does **not** pre-approve trades;
> survivors still run the full per-ticker validation on Monday.

**Setup (consistency with the ecosystem):**
- [ ] **Benchmark = Nifty 500** (`^CRSLDX` / NIFTY500), **not** Nifty 50 — matches the Dashboard's RS-vs-N500 row.
- [ ] **Timeframe = weekly RRG** for the positional universe (engine is weekly-anchored: 30W MA, 52W level, 26W slope). Use daily RRG only for swing-entry *timing*, never for the weekend cut.

**Stock filter — keep LEADING + IMPROVING, but tier them (don't lump):**

| Quadrant | RS-Ratio | Tier | How to treat |
|---|---|---|---|
| **LEADING** | ≥ 100 | Confirmed leader — passes the validated RS gate (Gate 2); STRONG BUY-eligible | Full-size eligible; preferred for **positional** |
| **IMPROVING** | < 100 (only momentum turned up) | Anticipatory — BUY tier, **not** STRONG BUY | Smaller size + tighter structure (clean HH-HL, Stage 2 *confirmed* not Stage 1); better for **swing / early-entry**. Many curl back to LAGGING — cut fast on failure |
| WEAKENING / LAGGING | — | Drop | LAGGING = hard reject (Step 2 floor) |

- [ ] **Read the tail/heading, not just the dot.** Sweet spot = IMPROVING→LEADING with a long north-east tail.
      A LEADING dot **rolling over toward WEAKENING** (RS-Momentum falling, south-east heading) is a distribution
      warning → drop it even though it's still in the Leading box.

**Sector filter (soft bias, not a hard gate):**
- [ ] Shortlist sectors in **LEADING / IMPROVING** and fish there preferentially.
- [ ] "To the extent possible" stays soft: a genuinely **LEADING stock** in a sector that's merely mid-pack is
      still tradeable. The only **hard** sector rejects are **Stage 3/4 or LAGGING** sectors (Step 2 disqualifier).
      Don't discard a strong leader just because its sector isn't top-3.

> **This pre-filter narrows the universe; it never replaces the downstream floors.** Survivors still pass
> Dashboard (≥ BUY, Grade A/A+), Context Layers (FINAL ≥ +3), and structure (HH-HL) before any entry.
> *(RRG interpretation only — the RRG calculation stays read-only per [[rrg-logic-do-not-touch]].)*

---

## PER-TICKER VALIDATION  (09:15–10:30 IST)

### STEP 4 — BULL SCREENER v3.2  *(per chart, daily)*

| Reading | HARD FLOOR | Full-conviction |
|---|---|---|
| **Active catalyst** | > 0 (some catalyst fires) | match to regime: bull→POS-BO · pullback→SWG-PB · gap→GAP-GO |
| **`alphaScore`** | **≥ 60** | ≥ 80 = STRONG BUY tier |
| **`pyScore`** (Python-aligned Score) | **≥ 60** | ≥ 80 full · 60–79 normal · 40–59 half max · < 40 pass |
| **9-Gate POS-BO panel** (POS-BO only) | **≥ 8/9** ✓ | 9/9 highest conviction · **7/9 = watch only, no entry** |
| ADX (numeric) + weekly RSI (POS-BO) | **ADX ≥ 25 · wRSI ≥ 60** | ADX 30+ / wRSI 65+ |
| OBV (POS-BO / POS-AC structure) | rising 2 bars **and** > OBV SMA20 | confirms institutional accumulation |
| Vol Shelf (VWMA20 > VWMA50) | required POS-BO / POS-AC | absent → halve size |
| VCP Tight (ATR < 1.0× ATR-SMA) | required SWG-BO · preferred POS-BO | tighter base = sharper break |

- [ ] `alphaScore ≥ 60` AND `pyScore ≥ 60` AND a catalyst is active.  **← HARD FLOOR**
> **Note:** POS-AC **does** show as a catalyst label here (re-enabled, in-file v3.3 / Py v1.10), gated `dailyRsi ≤ 50`. Ignore the stale "disabled" comment in the .pine file header.
> **Gold standard:** pyScore ≥ 80 + POS-BO + 9/9 + wRSI ≥ 65 + ADX ≥ 30 + Vol Shelf + OBV rising → full size.

### STEP 5 — DASHBOARD v67.4.12  *(final go/no-go, Decision Mode)*

| Row | HARD FLOOR | Full-conviction |
|---|---|---|
| **MACRO** | GREEN (Bull) or YELLOW (Recovery) — **never RED** | GREEN + sector Stage 2 |
| **SECTOR** | Stage 1 or 2 | Stage 2 + LEADING RRG |
| **STAGE** (weekly) | Stage 2 (or Stage 1 for early entry) | Stage 2.1, stage-weeks 4–13 |
| **30W SMA slope** | Rising ↑ | rising & price above |
| **RS vs N500** | LEADING (IMPROVING ok for BUY tier) | LEADING + Mansfield ≥ +10 |
| **ALPHA SCORE** | **≥ 60** | ≥ 80 full size |
| **GRADE** | **A or A+** | A+ = STRONG BUY tier |
| **CATALYST** | active & **matches Bull Screener** | same catalyst both = high conviction |
| **RECOMMENDATION** | **STRONG BUY or BUY** | STRONG BUY full · BUY normal · BUY* check fundamentals · PULLBACK re-entry only · WAIT pass |
| **RFF LITE** | 2/2 ✓ (1/2 caution · 0/2 skip unless Alpha ≥ 90) | — |

- [ ] Recommendation ≥ BUY · Macro not RED · Stage not 3/4 · Alpha ≥ 60 · Grade A/A+.  **← HARD FLOOR**
- [ ] **Gate-3 R:R preview** (LEVELS/ROOM row, v67.4.13): prospective `~R:R ≥ 2.0R` to nearest overhead, or "open ▲".

### STEP 6 — CONTEXT LAYERS v1.2  *(FINAL SCORE panel)*

| Reading | HARD FLOOR | Full-conviction |
|---|---|---|
| **CONTEXT (FINAL) SCORE** | **≥ +3 (BULL) for full size** · ≥ 0 (NEUTRAL) for half | ≥ +6 STRONG · ≥ +9 MAX |
| **SETUP BONUS** | **≥ 0** (negative = S7 Distribution / S8 Choppy = sit out) | +2 S2 Spring/LPS or S3 Sweep+CHoCH |
| **Wyckoff Bias** | ACCUMULATION or NEUTRAL | ACCUMULATION + SOS/LPS ≤ 20 bars |
| **VP price location** | at/above POC | above VAH strong · below VAL = skip |
| **Distance to POC** | within **2 ATR** | 0–5% above POC = ideal pullback zone |
| **SMC Trend** | BULLISH or NEUTRAL | BULLISH + bull OB within 1 ATR below |

- [ ] FINAL SCORE ≥ +3 (full) and SETUP BONUS ≥ 0.  **← HARD FLOOR**
> **Disqualifier:** FINAL SCORE ≤ −3 (BEAR) OR Wyckoff = DISTRIBUTION → skip regardless of Steps 4–5.
> *Panel labels (v1.2 bands): STRONG BULL ≥ 9 · BULL 4–8 · NEUTRAL −3..+3 · CAUTION −4..−6 · BEAR ≤ −7.*

### STEP 7 — ZIGZAG STRICT v6.2  *(structure)*

| Reading | HARD FLOOR | Full-conviction |
|---|---|---|
| Trend state | **HH-HL** | clean HH-HL over last 3 swings |
| MTF Trend | confluence with current TF | HH-HL on daily AND weekly |
| Pivots | **Left=2 / Right=2** (must match all modules) | — |

- [ ] HH-HL (LH-LL = structural downtrend = skip bull entries).  **← HARD FLOOR**

---

## EXECUTION  (signal-fire bar onward)

### STEP 8 — ENTRY: UNIFIED ECOSYSTEM v3.6 TRIGGER **or** DISCRETIONARY CONFIRMATION

**Bull master prerequisites (must hold on BOTH paths):**
- [ ] Bull Strategy toggle ON · Market Health: CNX500 close > SMA200 **AND** SMA50 > SMA200
- [ ] Weinstein Stage 2 (or early Stage 2 for POS edges) · Alpha ≥ 60 · RS LEADING/IMPROVING
- [ ] **Micro Edge:** Close > Daily CPR Pivot **AND** Close > Monthly VWAP

**Take the entry if EITHER path is satisfied — Path A is preferred, Path B is fully legitimate:**

**Path A — Automated trigger fires** (highest-confidence confirmation): the matched catalyst boolean = TRUE.
Enter on the signal bar **or within the 3-bar HOLD window** while conditions remain valid.

**Path B — Discretionary entry** (trigger silent, but you can see the edge on the chart): the strict gates
didn't all line up for the algo, yet the edge's *documented entry conditions* are visibly present. You verify
them by eye and enter manually. **This is the normal case, not an exception.** Discretion is on *timing only* —
Steps 1–7 hard floors and Step 9 sizing still bind.

| Edge | Path A built-in gate (don't override the algo) | Path B — verify by eye for a manual entry |
|---|---|---|
| `pos_bo_trigger` | breakout + 1.5× vol + vol_shelf + **wRSI ≥ 60 + ADX ≥ 25** | Close above 20-bar high; vol ≥ 1.5× 50-day; not ≥ 3% extended. Buy-stop 0.25% above the high; wait for **close** above level |
| `pos_ac_trigger` | accum + 1.2× vol + OBV rising & > MA + vol_shelf + **d_rsi ≤ 50** | Base + Close > EMA20 > SMA50, close top-30% of bar, OBV rising 2 bars & > SMA20, daily RSI ≤ 50. Limit 0.25% below close |
| `swing_pb_trg` | mkt_bull + pullback + vcp_tight + ma_stack + rsi_pocket + vol_dry | Low pierced EMA20, close back > EMA20 (within 1.5%) on dry volume, RSI 30–70. Enter first green close |
| `swing_bo_trg` | mkt_bull + vcp_tight + breakout + 1.5× vol | VCP tight (ATR < 1× avg), close > 20-bar high on ≥ 1.5× vol, bar range < 2× ATR. Buy-stop 0.5% above pivot |
| `gap_go_trg` | mkt_bull + gap ≥ 4% + intraday pos ≥ 60% + 3× vol | Gap ≥ 4%, holds past 11:30 IST (first 15-min didn't retrace > 50%), ≥ 3× vol. Enter above first-candle high |
| REV-CB / REV-RS / REV-EARLY | recovery gates + **RFF ≥ 3/6** + regime gate | All 4 CB pillars (or RS-survivor / early-bird structure) + RFF ≥ 3 + regime gate (CNX500 ≥ 7% off OR stock ≥ 10% off 52W high) |

- [ ] Path A trigger fired, **OR** Path B edge conditions confirmed by eye **with all Steps 1–7 floors intact**.

> **When the trigger is silent, ask *why* before going discretionary.** If it's just the algo's strict gate
> margin (e.g. ADX 23 not 25, vol 1.4× not 1.5×) on an otherwise clean setup → Path B is sound, size normally.
> If a *real* condition is missing (no breakout, RS LAGGING, macro RED, structure LH-LL) → that's a Step 1–7
> floor failure, not a trigger quirk → **do not** discretionarily override it. The trigger being quiet is fine;
> a failed hard floor is not.
> **Conviction tiering:** Path A (trigger + 9/9 gates) → full size · Path B clean discretionary (floors all pass,
> 1–2 algo gates marginal) → normal size · Path B with any soft floor (e.g. Context NEUTRAL, Grade B) → half size.

### EXECUTION TOOLKIT — D&S PRICE-ACTION ENTRIES  *(feeds Step 8 Path B)*

> A second, complementary system: pure price-action **Demand/Supply (D&S)** zones, key levels, and
> EMA20-as-dynamic-S/R, learned from a professional trainer. **The quant funnel (Steps 1–7) decides *which*
> stock; this toolkit decides *where/when* you enter, *where* the stop sits, and *whether there's room*.** These
> are named, selectable **Path B triggers** — when the Pine catalyst is silent but one of these patterns is
> visibly on the chart, you have a documented, repeatable manual entry. They never relax Steps 1–7 or Step 9.
>
> **Scope (per your operating profile):** swing & positional only — **no intraday, long-side only.** Setups that
> were originally short or intraday are de-scoped to *exit/trim* aids or dropped (flagged below).

**Shared vocabulary:**
- **Zone construction** — Legin → base (1–6 candles, sweet-spot 2–4) → Legout. **RBR/DBR** = bullish demand zones (Rally-Base-Rally / Drop-Base-Rally). Proximal = zone edge nearest price; distal = far edge (your SL anchor).
- **Controlling / WCDZ-WDZ** — a Weekly Controlling Demand Zone that produced the move creating the prevailing structure; highest-grade demand. **Fresh** = untested since formation; **Strong** = strong Legout + gap/multi-pivot break.
- **TL BO / Rectangle BO** — trendline / range breakout (long). **IC** = Inside Candle. **Engulf** = bullish engulfing. **FTF** = *Follow the Footsteps* (of institutional investors) — a complex swing entry, **to be detailed later**.
- **MTTWR / MTTWS** — *Multiple Times Tested Weak Resistance / Weak Support* (a level tested so often it's primed to break).
- **MTF pairing (swing) — your two categories:**
  - **Category-1:** HTF = **Monthly / Weekly / Daily** (zone + bias) · LTF = **125-min / 75-min** (entry trigger + SL). Finer-grained — tighter SL, more entries, faster swing-to-STI. *Here the Daily is an HTF.*
  - **Category-2:** HTF = **Monthly / Weekly** (zone + bias) · LTF = **Daily** (entry trigger + SL). Broader — wider SL, fewer/cleaner signals, better for **positional**. *Here the Daily is the LTF.*
  - Pick the category by how much room/horizon the trade needs: Cat-1 for a tactical swing off a Daily/Weekly zone, Cat-2 for a positional ride off a Weekly/Monthly zone.
- **Room rule** — only take the setup if the path to the nearest **opposing (supply) zone gives ≥ 20% ROI** for positional / clears **Gate-3 R:R ≥ 2.0R** for swing. No room = no trade, however clean the entry.

**The setups (long-only, swing-focused) — pick the one that matches the chart:**

| # | Pattern (what you must see) | Long entry trigger (LTF) | SL anchor | Catalyst it satisfies | MTF category |
|---|---|---|---|---|---|
| **1** | Healthy time-correction sitting *near* EMA20(D/W) → continuation | **TL BO** or **Rectangle BO** (close + retest hold) | below base / breakout candle low | `swing_pb` · `swing_bo` · `pos_bo` | Cat-1 (W/D HTF → 75) · Cat-2 (W HTF → D) |
| **2** | Price *too far below* EMA20(D/W), basing → revert-to-mean rally | **TL BO** off the basing structure | below the basing low | `swing_pb` (oversold-bounce) | Cat-1 · Cat-2 |
| **3** | *Exit/trim aid (not a long entry):* unhealthy HTF move, extended above HTF EMA → expect a sharp LTF pullback (**TL BD**) | — *(short de-scoped)* — use to **trim/tighten** an open long into the move | — | risk-management overlay | Cat-1 (faster read) |
| **4** | Price halting at **MTTWR** in HTF, about to clear it (or reclaiming EMA20-HTF) → powerful rally on the break | **HTF BO** confirmed by LTF: **TL BO / IC / FTF / Engulf at retest** | below retest / EMA20-HTF | `pos_bo` · `swing_bo` | Cat-1 (W/D → 75/125 confirm) · Cat-2 (W → D) |
| **5** | Price reacting up from a **Very Strong + Fresh Controlling demand zone** | first LTF bullish reaction (Engulf / IC) inside the zone | **distal of the controlling zone** | `pos_ac` (accumulation bounce) · `swing_pb` | Cat-1 · Cat-2 |
| **6** | Price reacting up from a **Strong + Fresh demand zone while extended below HTF EMA** → sharp mean-revert bounce | **Engulf / IC / TL BO / FTF** at the zone | distal of the zone | `swing_pb` · `pos_ac` | Cat-1 · Cat-2 |
| **7** | **Engulf inside a Fresh + Strong WCDZ**, *or* **TL BO** after a clean reaction off it — **room ≥ 20% ROI** | Engulf in zone, or TL BO post-reaction | distal of the WCDZ | `pos_ac` · `pos_bo` (premier positional) | Cat-2 (W zone → D) · Cat-1 (→ 75 for tighter entry) |
| **8** | Good **Weekly Rectangle BO, room ≥ 20%**; WEMA nearby or extended | swing entry on **TL BO / IC / Engulf** at the retest | below the rectangle top (now support) | `pos_bo` · `swing_bo` | Cat-2 (W BO → D retest) · Cat-1 (→ 75 retest) |
| **9** | ~~Intraday level break before 2nd-half~~ | **— EXCLUDED (intraday; you don't intraday-trade) —** | — | — | — |
| **10** | One-sided uptrend above **W EMA**; **fib 38.2%/50% confluence with W EMA**; 1st/2nd/3rd pullback into it | catch the turn via **Engulf · IC · TL BO · FTF** at the W-EMA | below the fib/W-EMA confluence low | `swing_pb` (premier pullback) | Cat-2 (W EMA → D) · Cat-1 (→ 75) |
| **T** | **Testing setup:** Legin + 1+ base candle(s) in HTF → mark the recent pivot **TL** in LTF → enter on the break to ride the Legout | **TL BO** of the LTF pivot in the Legout direction (long) | opposite side of base | `pos_bo` · `swing_bo` | Cat-1 (W/D → 75/125) · Cat-2 (W → D) |

**How it wires into the funnel:**
- [ ] **Zone-aware SL → Step 9.** Use the **distal** of the demand/controlling zone as the structural SL. Only fall back to catalyst-aware ATR (POS 4.0× / SWG 1.5×) if the distal sits *above* entry (invalid).
- [ ] **Room → Gate 3 (Step 5/8).** Measure clear air to the nearest overhead supply zone. ≥ 20% ROI (positional) / **R:R ≥ 2.0R** (swing) or **skip** — this *is* the Gate-3 R:R check, just measured zone-to-zone.
- [ ] **Zone quality → Context (Step 6).** Fresh + Strong + Controlling (WCDZ) = highest confidence; a tested or weak zone is a half-size signal at best. "Overall chart / confluence confidence is a must" (your trainer's rule) = the Trade-Quality Scorecard ≥ 7.
- [ ] **Long-only & no-intraday discipline.** Setup 3 and any "too-above-EMA → TL BD" branch are **exit/trim tools, not entries**. Setup 9 is out of scope entirely.

> **One funnel, two lenses:** the quant edges (Steps 4–8 Path A) and these D&S patterns (Step 8 Path B) point at
> the *same* trade from different angles. When a Pine catalyst **and** a D&S zone agree (e.g. `pos_ac_trigger` +
> Engulf in a Fresh WCDZ), that's your highest-conviction, full-size entry.

### STEP 9 — RISK ALLOCATOR v1.0  *(size before you order)*

| Field | HARD FLOOR / setting |
|---|---|
| **Risk per trade** | Bull **0.75%** · Recovery **0.50%** of capital. Reduce to 0.50%/0.25% if VIX > 22 or Context NEUTRAL |
| **Initial SL** | structural (below demand/pivot). If invalid (anchor > close), catalyst-aware ATR14 fallback: **POS 4.0× · WYC 3.5× · REV 2.5× · SWG 1.5×** |
| **Max allocation** | **₹25,000** per trade (or ~25% of capital, whichever lower) |
| **Position size** | `(Capital × Risk%) / (Entry − SL)`, round **DOWN** |
| **Kelly multiplier** | 1.25× if all 3 (Stage 2 + RS+ + Vol > SMA50) · 1.0× any 2 · 0.75× only 1 |
| **Vol discount** | `min(3.0 / ATR%, 1.0)`, floored at 0.75× — ATR% > 3% auto-trims ≥ 25% |
| **Regime discount** | bear/correction: `Risk% − 0.25%` (floor 0.25%) |
| **Sector concentration** | ≤ **25%** of capital per sector (hard cap) |
| **Max open positions** | **6** simultaneously |

- [ ] Computed size **> 0** (size = 0 means SL too wide vs risk budget → skip).  **← HARD FLOOR**

---

## TRADE-QUALITY SCORECARD  *(max 9, entry floor ≥ 7)*

Score each of the 9 steps: **+1** if at the *confluence-boost* level · **+0.5** if it *just clears* the hard floor · **0** if it *fails* (and the trade is dead).

- **Step 8 scoring:** Path A trigger fired = **+1** · Path B discretionary entry (edge confirmed by eye, floors intact) = **+0.5** · no edge visible = **0**. A silent trigger never scores 0 on its own — only an absent setup does.
- **9 / 9** → textbook STRONG BUY, full size · **7–8 / 9** → normal size · **5–6 / 9** → half size or skip · **< 5** → next candidate.

---

## EXIT RULES  *(automated by Unified Ecosystem v3.6 — verify against your loaded script's inputs)*

> **Breakeven lock on every edge:** once T1 hits, SL floor → entry price. The runner can't turn into a loss.
> **Doc-lag flag:** v3.6 "what's new" claims POS-BO Chandelier **4.5×** (vs 3.0× below) and swing **SMA50 trail / 3R-5R @33%** (vs EMA20 / 2.5R-3.5R @50% below). Body tables still show the legacy values shown here — trust your script's input panel if they differ.

### Bull track
| Edge | T1 | T1 exit | T2 | Trail | Time stop | Hard exit |
|---|---|---|---|---|---|---|
| **POS-BO** | +2.5R | 30% | none (CE runs) | CE-POS: HiClose[22] − ATR[22]×3.0 (×3.5 bear) | 6 wk (30d) if < 0.5R | **Stage 4 → close now** |
| **POS-AC** | +2.5R | 30% | none (CE runs) | CE-POS (same) | 6 wk if < 0.5R | Stage 4 → close |
| **SWG-PB** | +2.5R (bull) / +2.0R (bear) | 50% | +3.5R / +3.0R | EMA20 ratchet | 10d if < 0.5R | close < SMA50 → exit |
| **SWG-BO** | +2.5R | 50% | +3.5R | EMA20 ratchet | 10d | close < SMA50 |
| **GAP-GO** | +2.5R | 50% | +3.5R | EMA20 ratchet | 10d | close < SMA50; disqualify if first 15-min retraces > 50% of gap |
| **SWG-REV** | +2.0R | 50% | **none** | EMA20 ratchet | **5d** (by design) | close < SMA50 |

### Recovery track
| Edge | Initial SL | T1 | T1 exit | T2 | Trail post-T1 | Time stop |
|---|---|---|---|---|---|---|
| **REV-CB** | climax low − 0.5× ATR | EMA20 reclaim | 50% | SMA200 reclaim | EMA20 ratchet | 15d |
| **REV-RS** | higher low − pad | +2.5R | 50% | 52W high | CE-REC | 15d |
| **REV-EARLY** | NR7 low − pad | +2.5R | 50% | 52W high | CE-REC | 15d |

> **Recovery regime-change override (mandatory):** if CNX500 falls back through the regime gate into a full Bear, **exit ALL recovery positions immediately** — the regime *is* the thesis.

---

## DAILY RHYTHM

| When | Action |
|---|---|
| **Weekend** | Run Full Auto-Pilot → Hunter / EarlyBird (fresh Stage-2). **Step 3.5: RRG pre-filter on Strike.Money** — keep LEADING/IMPROVING stocks (tiered) + bias to LEADING/IMPROVING sectors (weekly RRG, N500 benchmark). Refresh sector + ETF rotation. |
| **Pre-open** | Step 1 (Macro/VIX/McClellan/flows) + AI Brief. RED → stand down. |
| **Session** | Pullback entries (SWG-PB) on existing setups → run Steps 2–9 per candidate. |
| **Post-close** | `master_portfolio_sync.py` → Dashboard slots. Trail SLs, check time-stops & Stage-4 exits, journal + snapshot archive. |

---

*Entry: every HARD FLOOR passes + Scorecard ≥ 7/9. Exit: follow the edge row mechanically — no discretionary
overrides (DNA rule). RRG and scoring math are read-only ([[rrg-logic-do-not-touch]]); this checklist only
consumes their outputs. POS-ACCUM is live across all surfaces (Bull Screener in-file v3.3, Py v1.10, Ecosystem
v3.6; gated RSI ≤ 50) — judge it on the full 180-day horizon, never a short window. The .pine header's
"disabled" comment is stale; trust the code ([[validation-window-mismatch-warning]]).*
