# Golden Matcher — Single-Stock Command Center — User & Trading Guide

> **Module Role:** A **read-only** single-symbol decision funnel that renders the entire Golden Matcher checklist for **one stock at a time**. It answers one question — *"Is this name a buy right now, and if not, exactly what am I waiting for?"* — by ordering every signal into a **6-step gated decision path** (CONTEXT → QUALITY → SETUP → LOCATION → TRIGGER → EXECUTE), for **both a Bull path and a Recovery path**, ending in a **tick-as-you-go execution checklist**.
>
> **Location:** the **🎯 Golden Matcher** page inside **`weinstein_commander_web_v4.0.py`** (Web Commander → **Execution → Golden Matcher**), with **Auto-Sync TV**. · **Companion Pine:** [Section 4 — Entry Trigger](./22_Section4_Entry_Trigger_Guide.md) (the TradingView trigger twin, unified Bull/Recovery mode).
>
> *(The older standalone `golden_matcher_dashboard.py` / `LAUNCH_GOLDEN_DASHBOARD.bat` (port 8510) was **archived to `_archive/legacy/` on 8-Jul-2026** — this Web Commander page supersedes it and is the sole Golden Matcher surface.)*
>
> **Design contract (zero-drift by intent):**
> - It is a **presentation layer only** — no new strategy logic. Every number comes from validated modules:
>   - `bull_screener.screen_one()` → Stage, RS, Alpha, Catalyst, Entry/SL/T1/T2, ML prob, VCP (**Bull path**)
>   - `recovery_screener` via `gm_load_recovery()` → REV catalysts, RFF, drawdown, Wyckoff (**Recovery path**)
>   - `data_provider.fetch_ohlcv()` → OHLCV / CMP (Dhan-routed) · `fundamental_hub` → fundamentals
> - **Bull path** uses the **17-PA battery**; **Recovery path** uses the **10-PA reversal battery** + RS-turning-up in its Quality gate. Both live in the shared **`pa_patterns.py`** module (`detect_bull_patterns` / `detect_recovery_patterns`, imported by the page as `_detect_pa_patterns` / `_detect_recovery_pa_patterns`) — the single source of truth also read by `pa_field_validator.py`. Both mirror the unified **Section 4 Pine** (Bull/Recovery mode) — same conditions fire on both surfaces.
> - **Auto support zones** — `pa_patterns.detect_support_zones_dw()` marks the **Order Block / FVG / pivot-low support on both Daily and Weekly** (twin of the Section 4 Pine v2.3), and tracks **fresh vs tested** (a mitigated OB/FVG is excluded), so the LOCATION step and the guided checklist reference the *same fresh* demand zones the chart draws. Automates Guided-Execution Steps 1-2.
> - **Bull/Recovery path parity** — the GM resolves the path from the engines (bull catalyst vs recovery signal + RFF). The **Section 4 Pine v2.3** now mirrors this structurally in its `Auto` mode (Bull above the 200-DMA; Recovery = beaten-down below it), so the two surfaces agree on which playbook applies (the residual gap is an early recovery that already reclaimed the 200-DMA — Pine can't see RFF; use the Pine `Mode` override).
> - The Golden Matcher **identifies and sequences**; it **never triggers**. The trigger is always a **closed 75/125-min bar on TradingView**.

---

## Version history

| Milestone | Change |
|---|---|
| **30 Jun 2026** | Initial single-symbol second-screen page — 6-step decision path, 3-gate banner, Pine-panel mirror cards, guided execution checklist. |
| **3 Jul 2026** | Full-metrics expander re-ordered around a **one-glance score strip** (`SECTION_SCORES`) — read the strip, open a card only when a score surprises you. |
| **8 Jul 2026** | **Step 5 (TRIGGER) wired to the PA conditions** — surfaces which fired + Σ tier; verdict split into `BUY — TRIGGER LIVE` vs `ARMED · AWAIT TRIGGER`. **3-gate banner aligned** to the same language (`STRONG BUY · TRIGGER LIVE` / `READY · AWAIT TRIGGER`). **VCP-BO dry-up bug fixed** (vwma of volume, not price). |
| **9 Jul 2026 — audit pass** | Full unbiased audit + fixes. **Correctness:** batch-CSV recovery rows no longer break the Stage chip / show "nan" (float→digit normalization); the two weekly-crossover PA patterns (Stage-2 Launch, 30-WMA Reclaim) now read **confirmed weeks only** (no mid-week repaint); **Higher-Low/2B** gains a base-proximity ceiling (was firing on every green day of an uptrend); one `_cat_on()` normalizes "catalyst firing?" everywhere (header could disagree with the path). **Data integrity:** header now shows the **last bar date + a STALE badge**; batch recovery rows show their **file age**; the 10% beaten-down floor + RFF≥4 gate are read from `recovery_screener.CONFIG` (no hardcoding). **Display:** `compute_decision`'s displayed checks now match the thresholds it enforces; dead `render_decision`/`render_pine_mirror` removed. |
| **9 Jul 2026 — enhancements** | **E1** Guided checklist now **logs the trade to the journal** (`dhan_journal_v7.upsert_trade`, auto-captures the entry signal snapshot). **E2** On-page **position sizer** (Capital + Risk% inputs, persisted to `gm_settings.json`) → shares + position value on Step 5/6. **E3** **Session shortlist** — actionable names collect into a table with a TV-watchlist download as you scroll. **E4** Refresh now clears only GM's caches (not the whole app). **E5** Both PA batteries extracted to a shared **`pa_patterns.py`** (single source of truth). |
| **9 Jul 2026 — stale-data fix** | Fixed "Refresh does nothing / data stuck a day behind": a `2y/1d` request carried the **24h weekly cache TTL**, so a daily frame survived all day even after a new session closed, and Refresh only cleared Streamlit's layer. New **`data_provider.invalidate_symbol()`** busts a single symbol's on-disk cache; **Refresh** now calls it (real re-fetch), and GM **auto-heals** a stale frame once per session on load. |
| **9 Jul 2026 — symbol canonicalization** | TradingView reports NSE names with underscores (`BAJAJ_AUTO`, `NAM_INDIA`) that Dhan/yfinance don't recognise (they use `-`/`&`). New `_canon_sym()` resolves any separator variant to the canonical ticker via the Dhan scrip master (`dhan_ohlcv.canonical_nse_symbol`, separator-insensitive — `M_M`→`M&M`, not a naive `_`→`-`). Applied at both the TV-sync commit and the manual box. |
| **9 Jul 2026 — Gemini review + parity + VCP fix** | Reviewed an independent Gemini audit. **Rejected** its "double-shift lag" fix (the `timeframe.isdaily` gate reintroduces the intraday repaint). **S4 Pine → v2.3:** `Auto` path now mirrors the GM Bull/Recovery split via the 200-DMA discriminant (see the note above). **Fixed `bull_screener.py` VCP dry-up** (`(v*c)`→`(v*v)` volume-VWMA; the dry leg was a near-no-op → VCP-BO fired without real contraction — re-baseline recommended). **Flagged** (not changed) `technical_enrichment._calc_mansfield_rs` computing a 52-**day** SMA on daily closes while its docstring claims weekly — RS/RRG-sensitive, shifts matcher rankings; Jay's separate call. |
| **10 Jul 2026 — intraday trigger TF + Dhan freshness** | **Step-5 PA battery + momentum board can now recompute natively on 75/125-min** (your trading TFs) via a **Trigger TF** selector (default 75m). Dhan 25-min bars (90d) → session-anchored resample (`pa_patterns.resample_intraday`) → the batteries run with `intraday=True` (the 3 weekly-anchored patterns — HTF, Stage-2 Launch, 30-WMA Reclaim — are suppressed), and RSI/ADX/RelVol/Vol-dry on the Technical Board switch to that TF. **EMA20 stays a DAILY anchor** (DNA: "EMA20(Daily) overlaid on 75/125m") — the engulfing trend-context uses the *daily* EMA20/EMA10 passed into the battery, not a fresh intraday EMA (also keeps parity with the S4 Pine, whose battery is daily-computed). **Context/Quality/Setup/Location (Stage · RS · Alpha · catalyst · demand-zones) stay Daily/Weekly** — positional, not intraday. A banner states which TF the trigger is on. Also fixed Dhan feed bugs: **`fetch_intraday` used the wrong response key** (`start_Time`→`timestamp`) so intraday was silently empty; and **`fetch_daily` now back-fills the just-closed session from intraday** (Dhan's daily endpoint publishes a session next-day), with a session-aware freshness banner/auto-heal so the GM is no longer "one day behind" after close. |
| **9 Jul 2026 — auto support zones (v2.0 / v2.1 / v2.2 parity)** | **Steps 1-2 of the Guided Execution are now automated.** `pa_patterns.detect_support_zones_dw()` marks an **Order Block**, **FVG** and **pivot-low support** on **both Daily and Weekly** (twin of the [Section 4 Pine v2.3](./22_Section4_Entry_Trigger_Guide.md)), surfaced as a **"Support (auto)"** chip (`D:.. · W:..`) in the LOCATION step (Bull + Recovery), **Daily + Weekly level rows** in the **LEVELS card**, and — when a **fresh** zone is under price — **auto-filled checklist Steps 1-2** (the tightest fresh zone's span + proximal, Daily preferred then Weekly). **v2.2:** full lifecycle FRESH → TESTED → VIOLATED. A **tested** OB/FVG (price entered then left) is flagged `ob_tested`/`fvg_tested`, shown greyed with a `TESTED` tag in the LEVELS card, and **excluded** from `at_support` / the auto-fill — only fresh zones qualify. A **violated** OB/FVG (a close below its distal) is **deleted** (a wick-below that closes back inside is a spring, not a violation). **Pivot lines** differ — never deleted: a violated pivot **flips to resistance** (`pivot_res`, shown `Pivot S→R (resist)` in the LEVELS card), cleared on reclaim. |

---

# PART A — USER GUIDE

## 1. What it is (in one breath)

Type one NSE symbol → get the whole Golden Matcher verdict for it: a colour-coded **6-step path** telling you which gate you're at, a **PA-trigger** read, a **guided checklist** for execution, and — one click away — **10 detail panels** mirroring your Pine cards. It's the "should I buy this, and what's my next physical action" screen.

## 2. Launch & setup

1. **Open the Web Commander** (`weinstein_commander_web_v4.0.py`) and go to **Execution → 🎯 Golden Matcher**. Type an NSE symbol; the page renders the Bull + Recovery paths for it. **Auto-Sync TV** keeps it on the symbol of your active TradingView chart.
2. **Prerequisite:** the ecosystem modules must import cleanly (Dhan token valid for live CMP; Screener.in cookie for fundamentals). Missing pieces degrade gracefully — a "Partial-data notes" expander, never fabricated numbers.
3. Put the Web Commander on your **second monitor**; keep TradingView on the primary for the trigger.
4. **After any code change to the Golden Matcher, restart the Web Commander** so the page reloads.

## 3. Top controls

| Control | Behaviour |
|---|---|
| **🔄 Auto-Sync TV** | On by default. Polls the active TradingView window title (~2 s, debounced 2 stable polls ≈ 4 s so mid-scroll names never trigger a fetch burst) and follows its symbol. |
| **NSE symbol** | Text box (default `NETWEB`). Type the bare NSE ticker, Enter. |
| **🔄 Refresh Data** | **Force a fresh fetch for THIS symbol** — busts its on-disk data cache via `data_provider.invalidate_symbol()` (beats the 24h daily TTL), then reloads. Other pages' caches stay warm. |
| **Capital (₹)** / **Risk %** | Feed the Step-5/6 **position sizer**. Persisted to `gm_settings.json`, so they survive restarts. Risk% default 0.25. |
| **Trigger TF** (`75m` / `125m` / `Daily`) | The timeframe the **Step-5 PA battery** and the **Technical-Board momentum gauges** (RSI/ADX/RelVol/Vol-dry) compute on. Default **75m**. Context/Quality/Setup/Location (Stage · RS · Alpha · catalyst · demand-zones) always stay **Daily/Weekly** — they're positional. Intraday = Dhan 25-min → session-anchored resample; the 3 weekly-anchored patterns (HTF, Stage-2 Launch, 30-WMA Reclaim) are suppressed on 75/125m. A banner shows which TF the trigger is on (and falls back to Daily if intraday is unavailable). Persisted to `gm_settings.json`. |

Data is cached **120 s** in Streamlit — re-typing the same symbol is instant. Refresh forces a live pull; the page also **auto-heals** a stale served frame once per session (see §4.1).

## 4. Page anatomy (top to bottom)

### 4.1 Header strip
- **Symbol — Company name**, with sector · industry beneath.
- **CMP** with the day's **% change**.
- **Freshness line** (under CMP): 🟢 `bar 08-Jul` when the last daily bar is current, or **⚠️ STALE — bar 07-Jul (last trading day 08-Jul)** when it lags a completed session. If the engine's `As_Of` differs from the chart bar, both are shown. On load, a stale frame **auto-heals once per (symbol, session)**: GM busts the cache and reloads to pull the fresh bar; if the provider genuinely hasn't published it yet, the STALE badge stays and manual Refresh remains.
- **CATALYST** (large, colour-coded): green if a POS-* catalyst, amber if any other live catalyst, grey if none. This is the screener's setup label (from `screen_one`), *not* the PA trigger.

### 4.2 DECISION PATH — the primary view (this is the decision)
A vertical, gated **6-step sequence** with a big **verdict** header and colour-coded steps. Each step shows metric **chips** (green ✓ / red ✗ / grey ·), an **imperative guidance line** (what to do), a **status pill** (DONE / STOP / WAIT / YOUR MOVE / LOCKED / PLAN), and a **"← NOW"** badge on the step that needs you.

The two **hard gates** (Steps 1–2) can stop the path: a hard fail greys out ("LOCKED") every step below it — the sequence literally won't let you skip to a trigger on a name that failed context or quality.

**The 6 steps:**

| # | Step | Hard? | Passes when | Chips shown |
|---|---|---|---|---|
| 1 | **CONTEXT** | ✅ | Stage 2 + weekly trend up + RS positive + not Stage 3/4 | Stage · Weekly Trend · RS vs N500 · Regime |
| 2 | **QUALITY** | ✅ | Alpha ≥ 50 **and** Minervini ≥ 5/8 | Asset Qual · Minervini · RRG · ML Prob |
| 3 | **SETUP** | soft | a catalyst is live | Catalyst · Freshness · VCP/Base · **PA Patterns Σ** |
| 4 | **LOCATION** | soft | above CPR+VWAP value **and** not extended | vs CPR+VWAP · VP position · Room to 52WH · **Support (auto)** |
| 5 | **TRIGGER** | your move | *(see §4.3)* | **PA trigger** (which fired) · **Σ tier** · Confirm on 75/125m |
| 6 | **EXECUTE** | plan | — | the SL/T1/R plan + size + GTT |

**Verdict labels** (workflow):
- `BUY — TRIGGER LIVE` — all gates pass **and** a daily PA pattern fired today.
- `ARMED · AWAIT TRIGGER` — all gates pass, no PA trigger printed yet (set the alert, wait).
- `WAIT FOR PULLBACK` — extended / below value (Location fail).
- `BUY-WATCH · no catalyst` — context+quality good, no live catalyst.
- `WATCHLIST` — quality incomplete.
- `AVOID / EXIT` — Stage 3/4 or RS negative (fails the no-Stage-3-holds rule).

### 4.3 Step 5 (TRIGGER) — the PA-driven trigger
This is the layer that maps to **§4 of the trading plan** and to the **Pine Section 4** indicator. It reads the daily PA battery (**17 conditions** Bull / **10** Recovery):
- **PA trigger** chip → the strongest patterns that fired (e.g. `VCP Breakout, Pocket Pivot`), green when any fired.
- **Σ tier** chip → the weighted sum of fired-pattern tiers (green at ≥ 2). Patterns are *bonuses*, not a checklist — you eyeball the tier.
- Guidance:
  - *Fired* → `TRIGGER LIVE — <names> (Σ+N) fired on the daily. Confirm on a CLOSED 75/125m bar → buy-STOP above its high. Never buy the touch.`
  - *Not fired* → `No daily PA trigger yet. Wait for a closed-bar pattern (VCP-BO / Pocket / 3-Bar / Undercut / IB-NR7 …) at the zone.`

### 4.4 PA banner
When strong patterns are live, a **high-visibility banner** appears above the steps so you can't miss a fired trigger at a glance.

### 4.5 The single next action + guided execution checklist
Below the path, one line tells you the **→ NOW** action for the current step. When you reach **Step 5**:

- **Position sizer** (if Capital > 0): `Risk ₹X ÷ (entry − SL) = N shares · position ₹Y (Z% of capital)`, using the plan's entry/SL. Counter-trend names are auto-halved. If capital is 0 it prompts you to set it.
- **Auto demand-zone (v2.0 / v2.1):** if an Order Block / FVG / pivot support (Daily **or** Weekly, or AVWAP) sits under price, a green caption states the tightest one (**Daily preferred, then Weekly**) plus the full `D:.. · W:..` summary — `🟩 Auto demand-zone: Daily OB near at ₹1,201–1,240 · alert proximal ₹1,240 · D:OB near · W:FVG inside` — and **checklist Steps 1-2 are auto-filled** with that zone + proximal (you *verify* rather than hand-draw). No zone on either TF → a grey caption and the manual "hand-draw" wording (below).
- A **6-item tick-as-you-go checklist** with a progress bar (Steps 1-2 shown here in their no-auto-zone fallback form):
  1. Mark the FRESH demand zone on Daily+ (hand-drawn, untested) — *or, auto:* "Auto zone confirmed: `<OB/FVG/Pivot>` at `₹lo–hi` (verify it's fresh/untested)"
  2. Set a TradingView alert at the zone proximal — *auto:* "…at the zone proximal `₹<level>`"
  3. Wait for a 75/125m bar to CLOSE in your direction at the zone
  4. Place a buy-STOP above that trigger bar's high (never buy the touch)
  5. Set SL below the zone distal · size at 0.25% risk
  6. Place the order + GTT the same evening · log the trade

When all 6 are ticked, a **📓 Log to journal** form appears, pre-filled from the active plan (buy price = entry, qty from the sizer, SL/T1, rationale = `GM <verdict> · <path> · <catalyst> · Σ+N`, timeframe inferred from the catalyst family). One click calls `dhan_journal_v7.upsert_trade` — which **auto-captures the true-entry signal snapshot** (the Phase-0 hook), so the trade lands in the journal *and* the attribution pipeline with its setup label. Fully guarded — a journal failure never breaks the page.

### 4.5b Session shortlist
A collapsed **📋 Session shortlist (n)** expander accumulates every **actionable** name (BUY / ARMED / WAIT verdict) you land on as you scroll TV — `Symbol · Verdict · Path · Σ tier · Signal · Seen`, sorted by Σ tier. A name that later degrades to AVOID/WATCHLIST drops off. Buttons: **⬇ TV watchlist (.txt)** (`###GM_SHORTLIST` + `NSE:SYM` lines, importable to TradingView) and **🗑 Clear**. Turns a scroll session into a ranked artifact.

### 4.6 Full-metrics expander (optional depth)
One expander holds a **score strip** + **10 detail cards** in three columns. The strip summarises each section's score so you **only open a card when its score surprises you**:

| Column | Cards |
|---|---|
| **1** | **Technical Board** (RSI/ADX/etc. gauges) · **PA Patterns** (the battery, Σ tier) · **Context** |
| **2** | **Structure** (the 3-gate decision) · **Bull Gates** · **Edges** · **Recovery** |
| **3** | **Trade** (entry/SL/targets) · **Levels** (room + **auto Daily & Weekly Order Block / FVG / pivot support levels** + "price at support D/W") · **Sector** (rotation) · **Fundamentals** (Screener.in) |

### 4.7 Footer
Data source + fetch time + cache note + the standing reminder: **"identification only — the trigger is yours on TradingView."** A "Partial-data notes" expander lists any module that degraded.

## 5. The two decision engines (why there are two verdicts)

| Engine | Where | Structure | Verdicts |
|---|---|---|---|
| **`compute_workflow`** | the **DECISION PATH** (primary) | 6 sequential steps, hard gates can lock the rest | `BUY — TRIGGER LIVE` / `ARMED · AWAIT TRIGGER` / `WAIT FOR PULLBACK` / `BUY-WATCH` / `WATCHLIST` / `AVOID` |
| **`compute_decision`** | the **Structure** card (in the expander) | 3-gate funnel (CONTEXT / STRENGTH / TIMING) | `STRONG BUY · TRIGGER LIVE` / `READY · AWAIT TRIGGER` / `BUY ON TRIGGER` / `WATCHLIST` / `NOT YET` / `AVOID` |

As of 8 Jul 2026 **both speak the same "trigger" language** — "trigger" means *a PA pattern fired*, in both. The DECISION PATH is your working view; the 3-gate banner is the compact cross-check inside the expander. (9 Jul 2026: `compute_decision`'s displayed sub-checks were aligned to the thresholds it actually enforces — Alpha ≥ 50, Minervini ≥ 5/8 — with non-gating rows marked "(info)", so a gate never shows ✓ over red criteria.)

---

## 6. Bull-path parameters & gates (reference)

Every gate and threshold the **Bull** `compute_workflow` enforces, per step. **Hard**
gates (Steps 1–2) can lock the rest of the path; **soft** gates (Steps 3–4) annotate but
don't block a fired trigger. Values are the live defaults in `weinstein_commander_web_v4.0.py`.

| Step | Type | Gate expression (must all pass) | Thresholds | Shown as status (does NOT gate) |
|---|---|---|---|---|
| **1 CONTEXT** | hard | `Stage-2` **and** `RS vs N500 > 0` **and** not Stage-3/4 | RS (Mansfield) > 0 | Weekly Trend (price > rising 30W-MA proxy), Regime = BULL |
| **1 CONTEXT** *(POS-ACCUM variant)* | hard | `Stage-1/2` **and** `RS > 0` **and** `price > 200-DMA` | — | Regime |
| **2 QUALITY** | hard | `Alpha ≥ 70` **and** `Minervini ≥ 6/8` | Alpha 70, Minervini 6 of 8 | RRG (LEADING/IMPROVING), BFF (funda, display-only), ML Prob ≥ 60% |
| **2 QUALITY** *(POS-ACCUM variant)* | hard | `Alpha ≥ 40` **and** `(RRG LEADING/IMPROVING **or** volume-accumulation)` | Alpha 40, Accum ≥ 60 | Accum days, BFF, ML Prob |
| **3 SETUP** | soft | `catalyst live` | catalyst ∈ POS-*/SWG-*/REV-* | Freshness ≤ 26w, VCP valid, PA-tier ≥ 2 |
| **4 LOCATION** | soft | `above value` **and** `R:R ≥ 2.0` **and** `EMA20-ok` | `RR_MIN_LOCATION = 2.0`; `EMA20-ok` = above EMA20 **and** distance ≤ `EMA20_EXT_ATR_MAX = 3.5 × ATR` (not chasing); *above value* = price > CPR pivot **and** > MVWAP | the on-screen "vs EMA20 +N ATR" is the **current** distance, not the cap |
| **5 TRIGGER** | your move | a PA pattern fired **and** a **closed** trigger bar confirms | PA battery = 17-pattern v67 mirror; trigger TF 75m/125m/Daily | Σ-tier chip (bonus, not x/N) |
| **6 EXECUTE** | — | disciplined plan: structural SL (nearest fresh zone distal D/W, 1% buffer, capped 3×ATR) → EMA20 → 2.5×ATR; size at 0.25% risk | 3×ATR SL cap; 0.25% risk | R:R off the disciplined stop |

**Inherited qualification** (a name from a rigorous Chartink+Screener watchlist, `INHERIT_QUALIFICATION=True`):
Steps 1–2 collapse to a lightweight **still-valid** guard (invalidate only on *observed* Stage-3/4
or price below the 30W-MA proxy — a missing 30W-MA never flips it); QUALITY becomes a ranking
overlay (never a veto); the inherited **archetype** is the setup (Step 3 needs no live catalyst).

**Other constants:** `EMA20_RECLAIM_BAND_PCT = 8.0` (recovery reclaim band — how far above
EMA20 a recovery bounce may be and still count as "turn confirmed, not chased").

**RS metric note:** the Bull path shows **JdK RS-Ratio − 100** (RRG convention, ~±small); the
Recovery path shows **Mansfield RS ×100** — different measures, so the two paths legitimately
show different RS numbers for the same stock.

---

# PART B — TRADING GUIDE (step-by-step)

The Golden Matcher runs the **entire pre-trade funnel** except the physical trigger. Work it top-down; the path won't let you cheat a gate.

### Step 0 — Load the name
Type the ticker (usually pulled from your Golden Picks / FINAL_WATCHLIST). Read the **header verdict** first — if it says `AVOID / EXIT`, stop and go to the next name.

### Step 1 — CONTEXT (hard gate)
Confirm **Stage 2 + weekly trend up + positive RS + not Stage 3/4**. If this fails, the name is not a leader — **SKIP**. No amount of a pretty daily setup rescues a Stage-3/4 or RS-negative name (this is the no-Stage-3-holds rule made mechanical).

### Step 2 — QUALITY (hard gate)
Confirm **Alpha ≥ 50 and Minervini ≥ 5/8**, with RRG LEADING/IMPROVING and a healthy ML prob as supporting chips. Fail → **WATCHLIST**; revisit when RS/Alpha firm up.

### Step 3 — SETUP (soft)
Is a **catalyst live** (POS-BO/ACCUM/SWG-*), is the Stage-2 base **fresh** (≤ ~26 weeks), is **VCP/base** valid, and what's the **PA Σ**? No live catalyst → `BUY-WATCH`: add to watchlist, set a price alert at the zone, wait.

### Step 4 — LOCATION (soft)
Is price **at value** (above CPR + monthly VWAP) and **not extended** (room to 52-week high)? Extended/below value → `WAIT FOR PULLBACK`. Do **not** chase — wait for a pullback into a fresh demand zone. The **Support (auto)** chip tells you whether price is *already at* an auto-detected Order Block / FVG / pivot support (green) or `outside` any zone — this is the informational read of "am I at a real demand zone?" *(It's a status chip, not a hard gate — the verdict still turns on value + not-extended; but a green Support chip is the confluence you want before Step 5.)*

### Step 5 — TRIGGER (your move — the PA layer)
Now the daily PA battery decides the state:
- **`BUY — TRIGGER LIVE`** (a pattern fired) → move to execution. Note *which* pattern and the **Σ tier** — a Tier-3/4 (VCP-BO, Stage-2 Launch, HTF) or Σ ≥ 4 is a strong trigger; a lone Tier-1 coil (True NR7) means *wait for the release*.
- **`ARMED · AWAIT TRIGGER`** (gates pass, no PA yet) → set the TradingView alert at the zone and **walk away**. The ping is your cue.

Then switch to TradingView with the **[Section 4 indicator](./22_Section4_Entry_Trigger_Guide.md)** on the name: confirm the trigger at an **auto support zone** (Order Block / FVG / pivot / AVWAP — the same zones GM's Support chip reads) or a **pinch**, drop to **75/125-min**, and wait for the **intraday `GO`** (rising 10-EMA reclaim + TTM squeeze). With Section 4's `require_support` ON, a `GO` only fires *at* a zone — so the "trigger must be at a demand zone" rule is enforced, not eyeballed.

### Step 6 — EXECUTE (the guided checklist)
Work the 6-item checklist on-screen. **Steps 1-2 are auto-filled** when an OB/FVG/pivot zone is under price — verify the auto-zone is fresh/untested and set the alert at the given proximal, rather than hand-drawing. Then → **wait for the CLOSED 75/125m trigger bar** → **buy-STOP above its high** → **SL below the zone distal, size at 0.25% risk** (the position sizer gives the share count) → **place order + GTT the same evening + log it** (the 📓 journal form). Read the plan card's **R:R** before committing; skip anything under ~2R.

### The one rule
**The Golden Matcher identifies. You trigger.** Never buy because price *arrived* at the zone — buy the **buy-stop above a closed trigger bar**. The whole page is built to keep you from buying the touch.

---

## Reading the verdict at a glance

| Header / path verdict | What to physically do |
|---|---|
| `AVOID / EXIT` | No long. If held, plan the exit (Sell-to-Buy matrix). |
| `WATCHLIST` | Track only — strength incomplete. |
| `BUY-WATCH · no catalyst` | Alert at the zone; wait for a catalyst. |
| `WAIT FOR PULLBACK` | Extended — wait for a fresh-zone pullback. |
| `ARMED · AWAIT TRIGGER` | All gates green; set the alert, walk away, act on the ping. |
| `BUY — TRIGGER LIVE` | Confirm intraday `GO` → buy-STOP + SL + 0.25% + GTT. |

## Relationship to the ecosystem (zero-drift map)

- **Upstream:** `bull_screener.screen_one` supplies Stage/RS/Alpha/Catalyst/levels; `data_provider` the OHLCV/CMP; `fundamental_hub` the Screener.in fundamentals. The Golden Matcher **re-computes nothing strategic** — it arranges.
- **Sideways:** the **PA battery** *and* the **auto support zones** (OB/FVG/pivot) live in shared **`pa_patterns.py`** (Dashboard v67.4.12 mirror); the **Section 4 Pine v2.0** shows the identical patterns *and* draws the identical zones on TradingView. Step 5 + the LOCATION support chip here, and the Pine panel + zone boxes there, are twins.
- **Downstream:** the **guided checklist** hands to the **📓 Log to journal** form → `dhan_journal_v7.upsert_trade` (auto entry-signal snapshot) → attribution pipeline; the 0.25% risk + same-evening GTT are your execution discipline.
- **Pine↔Python caveat:** a marginal RV-based PA pattern can differ between TV feed and Dhan feed — the *formulas* are identical; trade the confluence, not one borderline pattern.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Could not load \<SYM\>" | `screen_one` and OHLCV both failed — check the ticker and the Dhan token. |
| CMP or fundamentals blank | Dhan token / Screener.in cookie stale — see the "Partial-data notes" expander; refresh the relevant session. |
| Catalyst shows `NONE` but you expect a setup | The screener isn't triggering today — this is the SETUP gate doing its job; don't force it. |
| PA Σ = 0 on a name you think is breaking out | No canonical pattern fired on the confirmed daily bar (or a marginal RV test just missed) — wait for the closed-bar confirmation. |
| Page not reflecting a code change | Restart the Web Commander — Streamlit caches the module until reload. |
| **STALE badge / data a day behind, Refresh seemed to do nothing** | Fixed 9 Jul 2026. A `2y/1d` request carried the 24h weekly cache TTL, so the daily frame survived a full day and Refresh only cleared Streamlit's layer. Refresh now force-busts the on-disk cache (`invalidate_symbol`) and GM auto-heals once per session. If it *stays* stale after Refresh, the provider genuinely hasn't published the new session's bar yet — wait, don't force. |
| ₹ / emoji render as boxes | Launch via the .bat (it sets `PYTHONUTF8=1`); don't run bare `streamlit run` without it. |

---

*Guide written July 2026 from `weinstein_commander_web_v4.0.py` (Execution → Golden Matcher). The Golden Matcher is the single-symbol decision funnel; its Step-5 trigger and the [Section 4 Pine indicator](./22_Section4_Entry_Trigger_Guide.md) are the two faces of the same PA entry battery (17 Bull / 10 Recovery, shared via `pa_patterns.py`). It identifies and sequences — it never pulls the trigger.*
