# Golden Matcher — The Comprehensive Manual

The exhaustive reference for the **Golden Matcher (GM)** — the Python decision engine that sits between your scanners and the trade. It qualifies *which* names to act on and *arms* them; the **S4 Entry Trigger** (Pine) then *times* the exact entry. This manual covers the philosophy, the six-step decision path, both trading paths (Bull & Recovery), the evaluation engine, the Trigger Board, the fundamental filters, the plan/sizing, and the full architecture.

> **Canonical surface.** The Golden Matcher you use is the **page inside `weinstein_commander_web_v4.0.py`** (Execution → 🎯 Golden Matcher), plus the **Trigger Board** (`gm_trigger_board.py`). The old standalone `golden_matcher_dashboard.py` is archived — do not use it. The shared evaluator is `gm_evaluate()`; the two workflows are `compute_workflow()` (Bull) and `compute_recovery_workflow()` (Recovery).

---

## Table of Contents
1. [Philosophy — qualify vs time](#1-philosophy)
2. [The two paths & the symmetry doctrine](#2-two-paths)
3. [The six-step decision path](#3-six-steps)
4. [`gm_evaluate` — the single source of truth](#4-gm-evaluate)
5. [The PA battery (Setup/Trigger signal)](#5-pa-battery)
6. [Location — support zones (proxy + IZE engine)](#6-location)
7. [Inherited Qualification — watchlists qualify, the board times](#7-inherited)
8. [The Trigger Board](#8-trigger-board)
9. [Fundamental filters — BFF & RFF](#9-fundamentals)
10. [The Plan — entry / SL / R:R / sizing](#10-plan)
11. [Guided Execution — journal, shortlist, TV export](#11-execution)
12. [Trigger-TF selector & last-closed-bar](#12-trigger-tf)
13. [Verdicts & categories reference](#13-verdicts)
14. [Zero-drift architecture](#14-architecture)
15. [Relationship to S4 (two-stage)](#15-s4-relationship)
16. [FAQ](#16-faq)

---

<a name="1-philosophy"></a>
## 1. Philosophy — Qualify vs Time

The system is a **funnel with two cadences**:

```
Scanners (Chartink + Screener.in watchlists)   →   GOLDEN MATCHER            →   S4 ENTRY TRIGGER   →   Execute (GTT)
     QUALIFY (heavy, daily/on-demand)               QUALIFY + ARM (the board)      TIME (the GO)          the order
```

- **The Golden Matcher answers "should I be ready to buy this name, and is it armed?"** — it runs a disciplined **6-gate** sequence and produces a **verdict** (BUY — TRIGGER LIVE / ARMED / WAIT / WATCHLIST / AVOID / INVALIDATED).
- **The S4 Entry Trigger answers "is this the exact bar to pull the trigger?"** — the strict `GO = PA · Location · Volume · Bar` gate on the chart.

**The GM fires *early* (arms) so you focus; S4's GO is the strict execution instant.** This two-stage split is deliberate — see §15.

**Hard rule:** a name should reach the GM only *after* a scanner (Chartink/Screener) has surfaced it. The GM times and confirms; it is not the first-pass screen.

---

<a name="2-two-paths"></a>
## 2. The Two Paths & the Symmetry Doctrine

Every name runs one (or both) of two paths, chosen by its source archetype / signal:

| | **Bull path** (`compute_workflow`) | **Recovery path** (`compute_recovery_workflow`) |
|---|---|---|
| For | Stage-2 leaders, breakouts, pullbacks, accumulation | Beaten-down names turning up (≥10% off 52WH) |
| CONTEXT | Stage 2 + weekly-up + RS (or an accumulation base) | Beaten down + open recovery regime |
| QUALITY | Technical **leadership** (Alpha + Minervini + RRG) | Fundamental **strength** (RFF ≥ 4/6) — *hard gate* |
| SETUP | Catalyst / VCP base (**soft**) | A recovery catalyst fired, Signal ≥ 2 (**hard-ish**) |
| LOCATION | At value: above EMA20, not extended, good R:R | Turn-confirmed, not chased above the recovery entry |
| Battery | 17 Bull PA patterns | 10 Recovery PA patterns |

**Path-symmetry doctrine (deliberate):** the two paths are **symmetric in FORM** (same 6-step skeleton, same TRIGGER-LIVE/ARMED language, PA chips at Steps 3 & 5) but **asymmetric in SUBSTANCE** — Bull = technical leadership with a *soft* setup gate; Recovery = fundamental strength (RFF) with a *hard* quality gate. Do not try to make them identical.

**Auto path selection** mirrors S4's Auto mode: a name **≥10% off its 52-week high and below/repairing the 30-WMA (and below the 200-DMA)** takes the Recovery path; otherwise Bull. The **200-DMA is the spine** — leaders live above it, recoveries below.

---

<a name="3-six-steps"></a>
## 3. The Six-Step Decision Path

`CONTEXT → QUALITY → SETUP → LOCATION → TRIGGER → EXECUTE`. Steps 1–2 are **hard gates** (a fail stops the funnel); Steps 3–4 are **soft** (a fired trigger overrides them — the *trigger-wins* rule); Steps 5–6 are the execution.

### 3.1 Bull path gates (`compute_workflow`)

| # | Step | Gate (`g`) | Passes when |
|---|---|---|---|
| 1 | **CONTEXT** (hard) | `g1` | Breakout: Stage 2 · weekly-up · RS>0, not Stage 3/4. **Accumulation** (POS-ACCUM): Stage 1/2 · above 200-DMA · RS>0. |
| 2 | **QUALITY** (hard) | `g2` | Breakout: Alpha ≥ 50 **and** Minervini ≥ 5/8. Accumulation: Alpha ≥ 40 **and** (RRG leading/improving **or** volume accumulation). |
| 3 | **SETUP** (soft) | `g3` | A live `bull_screener` catalyst is on (`cat_on`). |
| 4 | **LOCATION** (soft) | `g4` | Above CPR+VWAP value **and** R:R ≥ `RR_MIN_LOCATION` **and** above EMA20 but not extended (≤ `EMA20_EXT_ATR_MAX` ATR above it). |
| 5 | **TRIGGER** (manual) | — | A PA-battery pattern fired (Σ tier). This is where **BUY — TRIGGER LIVE** comes from. |
| 6 | **EXECUTE** | — | The plan: buy-STOP above the trigger bar, structural SL, size at 0.25%. |

> **POS-ACCUM branch:** the accumulation catalyst buys the *base before* the Stage-2 breakout, so Steps 1–2 switch to the *accumulation playbook* (Stage 1/2 + above-200-DMA + RS + volume accumulation) rather than demanding a completed Stage-2 breakout — otherwise a valid accumulation name would fail Step 1 wrongly.

### 3.2 Recovery path gates (`compute_recovery_workflow`)

| # | Step | Passes when |
|---|---|---|
| 1 | **CONTEXT** — beaten down | Correction ≥ `dd_floor` (10%) off 52WH **and** recovery regime open. |
| 2 | **QUALITY** — fundamentally strong (**hard**) | `RFF_Quality ≠ INSUFFICIENT` **and** `RFF_Base ≥ rff_min` (4/6). *This is the recovery thesis — only fundamentally strong beaten-down names.* |
| 3 | **SETUP** — recovery catalyst | `Signal ≥ 2` fired (REV-CB/RS/EARLY + WYC-*). |
| 4 | **LOCATION** — not chased | Price hasn't run far above the engine's recovery entry; turn confirmed. |
| 5 | **TRIGGER** — recovery PA (manual) | One of the 10 recovery patterns fired on a closed bar. |
| 6 | **EXECUTE** | The recovery engine's Entry/SL/T1/T2 plan. |

### 3.3 The *trigger-wins* rule (both paths)

A **fired Step-5 PA trigger is never vetoed by a missing catalyst (Step 3) or weak location (Step 4)** — because hard Context + Quality already passed (or the name is pre-qualified by its source watchlist). A live pattern is actionable on its own setup; the missing catalyst / weak location becomes a **caveat** appended to the verdict (`BUY — TRIGGER LIVE · thin R:R`), not a block. Hard gates (Context, Quality) still stop the funnel.

---

<a name="4-gm-evaluate"></a>
## 4. `gm_evaluate` — the Single Source of Truth

`gm_evaluate(symbol, trigger_tf="75m")` is the **one** evaluator both the Single-Symbol page and the Trigger Board call — which is what guarantees the two surfaces can never disagree. It returns a dict with:

- `rec` / `rec_r` — the bull / recovery screener rows (Stage, Alpha, RS, RRG, Catalyst, Entry/SL/T1…).
- `ctx` — the computed **context**: `sma150/sma200/ema20/atr`, `pa_patterns` / `recovery_pa_patterns` (the battery), `support` (zones), `bff`, `stage2_weeks`, `cpr_p/mvwap`, `dist52wh`, the intraday overlay fields (`relvol`, `bar_ok`, `adx`, `_trigger_tf`).
- `fun` — fundamentals.
- `wf_bull` / `wf_rec` — the two workflow results.
- `inherited_bull` / `inherited_rec` — source archetypes (see §7).
- `cmp_px`, `mansfield`, `intra_ok` / `intra_reason`.

**Context stays Daily/Weekly; the PA battery + momentum + live CMP come from the intraday overlay** (§12). This mirrors S4: zones and structure come from Daily+Weekly, the trigger fires on the intraday bar.

---

<a name="5-pa-battery"></a>
## 5. The PA Battery (Setup status / Trigger)

The **v67-mirror PA battery** — 17 Bull patterns (`pa_patterns.detect_bull_patterns`) and 10 Recovery patterns (`detect_recovery_patterns`) — is the same battery the S4 chart shows (**byte-identical formulas**, verified). Each pattern is `(name, fired, tier, note)`; the **Σ tier** = sum of fired weights. Patterns are **bonuses** (Jay's rule: 11/11 is not the benchmark).

- At **Step 3 (SETUP)** the Σ tier is a *status* chip (`+N`).
- At **Step 5 (TRIGGER)** a fired pattern is the actionable **BUY — TRIGGER LIVE** signal, named (`VCP-BO, Pocket…`).

Bull (17): HTF · Strong-Close · VCP-BO · Pocket · Engulf · Liq-Sweep · 3-Bar · Stage-2 Launch · Inside-3 · NR7 · IB-NR7 · Spring · Gap-BO · Undercut-50 · Hammer-50 · Hammer-200 · Breakout-Confirmed.
Recovery (10): Climax · Spring · Higher-Low/2B · Base-BO (SOS/JAC) · Engulf · Hammer-at-support · 3-Bar · Pocket · VDU · 30-WMA-reclaim.
(Full weights & formulas: see the S4 guide §4 — they are shared.)

**Important — HTF & Stage-2 Launch** are weekly/positional and are **suppressed on the intraday (`intraday=True`) battery**, so on a 75/125m trigger-TF they don't fire. Every other pattern is bar-based and computes on any TF.

---

<a name="6-location"></a>
## 6. Location — Support Zones

The GM's **location gate** (`ctx.support.at_support`, used by Step-4 and the board's S4-GO column) answers *"is price at a demand zone?"* Two engines:

1. **Proxy (`pa_patterns.detect_support_zones_dw`)** — the original, on Daily + confirmed-Weekly:
   - **Order Block** — the last red candle before a volume displacement up; FRESH → TESTED (entered-then-left) → VIOLATED (close below → deleted).
   - **FVG** — a 3-bar bullish gap; same lifecycle.
   - **Pivot low** — structural; never deleted, FLIPS to resistance when violated, cleared on reclaim.
   - `at_support` = price inside / within 1.5% of a FRESH OB / FVG / pivot.

2. **IZE zone engine (`zone_engine.py`, behind `GM_USE_IZE_ZONES`)** — the faithful port of the S4 Pine **leg-base-leg** engine (RBR/DBR/RBD/DBD, gap-bridged candles, per-TF leg-in, wick distals + narrow wick-to-wick, per-TF width band, FVG tag, travel/EMA/violation/ageing lifecycle). ON = an IZE demand zone at/near price also satisfies `at_support` (toward S4 `z_inDZ` parity). Default **OFF** pending A/B validation against S4.

> The proxy and the IZE engine fire on **different** names (different methodologies). The IZE port is the fix for the documented *"location-accuracy ceiling"* between the board (proxy) and S4 (IZE zones).

**Location is soft:** it never *blocks* a fired trigger — a weak location is a caveat. And when the catalyst plan gives no levels, **EMA20 becomes the dynamic support** so a location / R:R is always computed (for a long above EMA20: risk = CMP − EMA20; target = 52W high or a 2R default).

---

<a name="7-inherited"></a>
## 7. Inherited Qualification — Watchlists Qualify, the Board Times

**Doctrine (P1):** the rigorous Chartink + Screener.in watchlists already *qualified* a name — so the board must **not re-screen it**. Behind `INHERIT_QUALIFICATION = True`:

- When a name arrives with a **source archetype** (Breakout / Accumulation / Pullback / Leader / Catalyst-Scan for Bull; Recovery-RS / Climax / Early for Recovery), the hard Context+Quality gates are replaced by a lightweight **"still-valid" break-down guard**: invalidate *only* on positively-observed break-down (Stage 3/4 **or** price seen below the 30-WMA). A missing `sma150` never flips a name to INVALIDATED (honesty rule — no NaN→veto).
- **Quality becomes a ranking overlay** (never a block) → this is what unblocks Recovery names whose fast-mode RFF reads INSUFFICIENT.
- **The inherited archetype IS the setup** — no live catalyst required.
- Steps 1–3 relabel in the tree: *STILL VALID? · QUALITY (overlay) · SETUP (inherited archetype)*.

**Catalyst-Scan caveat:** a *catalyst-scan-only* name (its thesis was a time-localized event, not a persistent structure) must still have a **live catalyst OR a fired PA** to stay actionable — else `WATCHLIST · catalyst expired`.

---

<a name="8-trigger-board"></a>
## 8. The Trigger Board (`gm_trigger_board.py`)

A batch table that runs **all the watchlists** through `gm_evaluate` (zero-drift with the Single-Symbol page — same evaluator). Key columns/behaviours:

- **Overall / Category** — the timing state from `trigger_category(verdict, path)`: `Buy Trigger Live · Bull` / `Armed Wait` / `Wait for Pullback` / `No Catalyst` / `Watchlist` / `Invalidated` / `Avoid`.
- **Archetype** (show-all) — every inherited archetype the name carries (a name can be multi-archetype, e.g. Breakout+Catalyst). `★` badge = a top-25 `FINAL_WATCHLIST` conviction name.
- **S4-GO** (`s4go_status`) — a **gates-passed closeness score** `4/4 GO / 3/4 · no vol / 2/4 · no loc / n/a`, mirroring the S4 stage-2 gate (PA · location · volume · bar_ok) so the closest-to-GO float to the top. *A strong predictor, not identical — the S4 chart is final* (§15).
- **Loc** — the Step-4 caveat (extended / thin R:R) as an annotation, without fragmenting the Category filter.
- **Freshness** — bar-close auto-refresh (rebuilds once per NSE 75m/125m session bar) so a mid-session forming-bar signal doesn't linger; an AGE banner warns on a stale snapshot.
- **Observability** — build-failure counts, `n/a`-reason strip (auth/data/thin-history), unreadable-CSV surfacing, provenance (source mix).

**Maximized board** (`?view=gm_board_maximized`) = a table-only pop-out (default-sorted by S4-GO closeness) for a single-glance monitor.

---

<a name="9-fundamentals"></a>
## 9. Fundamental Filters — BFF & RFF

- **BFF (Bull Fundamental Filter)** — the Minervini growth leg, sourced from **screener.in**, shown at Bull **QUALITY** as `STRONG / OK / WEAK / INSUFFICIENT (n/5)`. **Display-only** — it *never* gates a technically-valid leader (structure fires; quality is status Jay eyeballs). Growth data lives in the "Compounded Growth" ranges-table TTM row.
- **RFF (Recovery Fundamental Filter)** — the recovery thesis, a **hard gate** at Recovery QUALITY: Tier-A (0-6) Pine-parity fundamental gate (NI>0, FCF>0, ICR>3.5, D/E<2, CR>1, ROA>5%) + Tier-B (0-4) recovery bonus (sales↑, profit↑, operating-leverage, deleverage). `RFF_Base ≥ 4` and quality ≠ INSUFFICIENT required. *Only fundamentally strong beaten-down names.*

The asymmetry is the point: **Bull leadership is technical** (BFF is decoration); **Recovery is fundamental** (RFF is the gate).

---

<a name="10-plan"></a>
## 10. The Plan — Entry / SL / R:R / Sizing

Computed in the workflow and shown at **EXECUTE**:

- **Entry** — the trigger/breakout level (default CMP). Always a **buy-STOP above the trigger bar** — confirmation before entry.
- **Stop-Loss** — **structural first** (`_plan_structural_sl`): the nearest FRESH demand-zone distal below entry, capped at **3× ATR** (a stop can never be absurdly far); else the EMA20 dynamic-support fallback; else screener SL. Recomputes `sl_pct` and R:R off the disciplined stop.
- **Targets / R:R** — T1 from the screener or the 52W-high overhead; `RR_MIN_LOCATION` is the Step-4 gate.
- **Position size** — the sizer (E2): Capital × Risk% (**0.25%** house rule) / (Entry − SL) → shares, persisted to `gm_settings.json`.

---

<a name="11-execution"></a>
## 11. Guided Execution — Journal, Shortlist, TV Export

- **E1 — Guided checklist → journal.** The step-through checklist logs an OPEN trade via `dhan_journal_v7.upsert_trade` (with an auto entry-signal snapshot: setup / entry_stage / entry_alpha / entry_rs / entry_conviction).
- **E2 — Position sizer** (above), persisted.
- **E3 — Session shortlist + TV-watchlist export** — collect the names you're arming and push them to a TradingView watchlist (then apply S4 + set the "S4 GO" alert on each).
- **E4 — Refresh** clears only the GM caches; a shared "Refresh Data (fresh · both surfaces)" button keeps the board and Single-Symbol on one data vintage.

---

<a name="12-trigger-tf"></a>
## 12. Trigger-TF Selector & Last-Closed-Bar

A **Trigger-TF selector** (75m default / 125m / Daily) recomputes the **Step-5 PA battery + momentum board** on the intraday TF via `gm_load_intraday` (Dhan 25m→75/125m session-anchored resample, **forming bar dropped** → last closed bar). Context/quality/setup/location (Stage/RS/Alpha/catalyst/zones) stay **Daily/Weekly**. The Step-5 wording names the actual TF (*"fired on the 75m"*). This matches S4's `use_chart_tf` (battery on 75m, structure on Daily/Weekly).

---

<a name="13-verdicts"></a>
## 13. Verdicts & Categories Reference

| Verdict | Meaning | Category |
|---|---|---|
| **BUY — TRIGGER LIVE** | A PA pattern fired; actionable now (caveat appended if location weak) | Buy Trigger Live |
| **ARMED · AWAIT TRIGGER** | All gates good, waiting for the Step-5 pattern | Armed Wait |
| **WAIT FOR PULLBACK** | Location weak (extended / thin R:R) — wait for EMA20 / a zone | Wait for Pullback |
| **BUY-WATCH · no catalyst** | Pre-qualified, no live catalyst — set an alert at the zone | No Catalyst |
| **WATCHLIST** | Quality not confirmed yet (or catalyst-scan expired) | Watchlist |
| **INVALIDATED · broke down** | Stage 3/4 or lost the 30-WMA since watchlisted — drop it | Invalidated |
| **AVOID / EXIT** | Stage 3/4 or RS negative | Avoid |

---

<a name="14-architecture"></a>
## 14. Zero-Drift Architecture

- **Python is canonical** for the signal logic (the PA battery, the workflows). **S4 Pine mirrors Python** — the 17 bull PA formulas are byte-identical (verified).
- **"Zero drift" means Python ↔ Python/Web**, not Python ↔ Pine. Pine platform limits (and the Dhan-vs-TradingView **feed-data** gap) prevent perfect Pine parity — that's expected, not a bug.
- `gm_evaluate` is the SSOT: the Single-Symbol page and the board can never disagree because they call the same evaluator on the same data vintage.
- **Data provenance:** fundamentals = screener.in (primary) + yfinance (fallback); technicals (OHLCV) = Dhan Data API (primary). The Web Commander runs from `C:\Users\jayra\TradingData\venv`.

---

<a name="15-s4-relationship"></a>
## 15. Relationship to S4 — the Two-Stage Design (do not collapse)

| | **Golden Matcher** | **S4 Entry Trigger** |
|---|---|---|
| Question | *Should I be ready, and is it armed?* | *Is this the exact bar?* |
| Signal | **TRIGGER LIVE** (early — a PA pattern appeared) | **GO** (strict — PA **at a location, with volume, on a clean bar**) |
| Location | OB/FVG/pivot proxy (or IZE port) | the full IZE zone engine (`z_inDZ`) |
| Role | qualify + arm | time + execute |

**This gap is intentional** ([[gm_early_s4_execute_twostage]]). The GM arms early so you *focus* on a name; you then wait for the S4 **GO**. Do **not** try to make the board's S4-GO column identical to S4 — the S4 chart is final. The board's S4-GO is a *closeness predictor* to tell you which names to open on S4 next.

**Why the board can show 4/4 GO while S4 shows no-GO:** (1) **mode/path mismatch** — the board sums the battery for its chosen path while S4 Auto resolves Bull/Recovery independently (set S4 Mode manually to match); (2) **feed data** (Dhan vs TradingView 75m bars, esp. volume on rv-gated patterns); (3) **snapshot staleness**. None is a battery bug — the formulas are identical.

---

<a name="16-faq"></a>
## 16. FAQ

**Q: The board says a name is BUY — TRIGGER LIVE but I don't see a catalyst.**
Trigger-wins: a fired PA pattern is actionable on the pre-qualified setup; "no catalyst" is a caveat, not a block (Context+Quality already passed).

**Q: A Recovery name reads WATCHLIST despite a fired pattern.**
Recovery QUALITY (RFF) is a **hard** gate — a fundamentally weak (RFF INSUFFICIENT) beaten-down name is not tradeable, no matter the pattern. Unless inherited (then RFF is a ranking overlay).

**Q: Why does the board's S4-GO disagree with my S4 chart?**
By design — see §15. Set S4's Mode manually to match the board path; expect feed/staleness differences; the S4 chart is final.

**Q: Bull vs Recovery — which runs?**
Auto by structure (≥10% off 52WH + below/repairing 30-WMA + below 200-DMA → Recovery, else Bull); a name on both watchlists is timed on **both** paths and the more-actionable wins.

**Q: What's the difference between the board and the Single-Symbol page?**
None in logic — both call `gm_evaluate`. The board is the batch monitor; the Single-Symbol page is the deep-dive on one name.

---

*Authoritative manual for the Golden Matcher (Web Commander page + Trigger Board), aligned to `weinstein_commander_web_v4.0.py`, `gm_trigger_board.py`, `pa_patterns.py`, `zone_engine.py`. Pair with the **S4 Entry Trigger Guide** (the timing layer) and the **Trading Guide** (the end-to-end workflow).*
