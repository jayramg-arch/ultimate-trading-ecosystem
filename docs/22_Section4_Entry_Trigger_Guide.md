# Section 4 — Entry Trigger & Price Memory v9.12 — User & Trading Guide

> **Module Role:** The **precision entry layer** you apply on a single name in TradingView **after** the Golden Matcher decision tree has filtered it to **Step 5 (TRIGGER)**. It does **not** re-screen (Stage / RS / RRG / VCP / catalyst all live upstream in the Golden Matcher and Dashboard v67). It does four things: (A) fires the price-action battery (**17 Bull / 10 Recovery**) on the **chart timeframe**; (B) draws the **price-memory anchored VWAPs** (Low / Breakout / Gap) and their "pinch"; (C) **auto-marks demand and supply zones on Chart + Daily + Weekly + Monthly** using the leg-base-leg engine ported from the Institutional Zone Engine, plus horizontal S/R levels and Volume-Profile VAL/POC — so you no longer hand-draw them; (D) gives the exact **intraday timing trigger** (rising 10-EMA reclaim + TTM squeeze) on 75/125-min. It then prints a ready-to-execute **entry + SL plan** and raises alerts so you never have to sit and watch.
>
> **File:** `Section4_Entry_Trigger_v7.2.pine` — **the filename is stale and does not track the version.** The authoritative version is the in-file title, currently `Section 4 Entry Trigger and Price Memory v9.12 (Sectioned Panel)` (`shorttitle "S4 Entry v9.12"`, line 853). · **Type:** Indicator (overlay) · **Pine:** v6 · **Library:** `import jayramg/S4Core/5` · **Market:** NSE · **Applies on:** the **75/125-min trading chart**.
>
> **Which timeframe the PA battery actually reads** — this is the single most-misread line in this guide. `use_chart_tf` **defaults to TRUE** (line 938), so on a 75m chart the battery runs on **75m bars**, not Daily. The panel header says so: `PA · BULL (auto·75)`. Only the two weekly-anchored patterns (Stage-2 Launch, 30-WMA Reclaim) and the HTF pattern are suppressed on intraday. Set `use_chart_tf` OFF and the battery reverts to confirmed Daily via `request.security`. `confirm_daily` (default ON) shifts **only the daily-security call** by one bar — after the v4.1 fix it does **not** shift the chart-TF call, which is what had the 75m battery reading a stale bar.
>
> **Design contract (zero-drift by intent):**
> - The PA conditions are the twin of the Web Commander Golden Matcher's — `detect_bull_patterns` / `detect_recovery_patterns` in the shared **`pa_patterns.py`** module (a port of **Dashboard v67.4.20**). ⚠ **Known drift, measured 10-Aug-2026:** S4 fires **17** bull chips, `detect_bull_patterns` returns **16** — Pine has `★ IB-NR7 Coil` (chip `IBN`) and Python does not. Σ can therefore differ by up to the IB-NR7 tier between board and chart, and because IB-NR7 is a **TENSION** role, a bar where it is the only tension pattern reads IGNITION-only in Python (`⚠role` tag) and correctly mixed in Pine. Recovery is 10 = 10 with no drift.
> - **Zones are NOT `detect_support_zones` (OB/FVG/pivot) any more.** That was v2.x. Since v3.0 the primary source is `S4Core.detectZone` — leg-base-leg RBR/DBR/RBD/DBD formations with per-TF width bands, a touch budget and calendar ageing — with `structZone` pivot shelves, FVGs and AVWAPs as secondary. The Python twin is **`zone_engine.py`**, not `pa_patterns.detect_support_zones`.
> - The **VCP-BO volume dry-up** uses `ta.vwma(VOLUME, 5) < sma(volume, 50)` — the **correct canonical** form (matches `pa_field_validator.py`). *(This is the same leg that had a `(c*v)` no-op bug in the dashboard `.py`, fixed 8-Jul-2026; Pine has always used the correct form.)*
> - Every daily PA pattern **and support zone** is computed on **confirmed daily bars** via `request.security(..., lookahead_off)` — **no repaint** (the confirmed-daily offset is timeframe-independent, so it holds on 75/125-min too). The two weekly-crossover patterns (Stage-2 Launch, 30-WMA Reclaim) read confirmed weeks. All alerts fire **once per bar close**.
> - **S4 no longer re-derives what another indicator already computes.** As of v8.2/v8.4 it
>   READS values from the Swing Zigzag and the v67 Dashboard via `input.source` — the same
>   computed series, not a second implementation. This is what finally closed the recurring
>   "v67 says Stage 1, S4 says Stage 2" class of disagreement: an imported field *cannot*
>   drift from its source. Anything not imported is either genuinely S4's own (zones, PA
>   battery, verdict) or explicitly documented as an approximation.
> - **Heavy engines live in the `S4Core` library** (published `jayramg/S4Core`, currently **v5**).
>   Library bodies compile separately, so they cost nothing against S4's compiled-token
>   ceiling. NOTE there are TWO ceilings: compiled tokens (~100,256) and MAIN-BODY
>   STATEMENTS (~1000). The library only helps the first.
> - The indicator is a **trigger/timing layer only.** It assumes Context / Quality / Setup already passed upstream. It automates **Location** (marking the demand zone) and owns the trigger; it never overrides the Stage / RS / regime discipline.

---

## Version history

| Version | Added |
|---|---|
| **v9.12** | **SECTIONED PANEL.** The 32 fields are grouped under five banded header rows, each stating the question its block answers: **I MACRO & CONTEXT** (what is the regime?) · **II LOCATION & QUALITY** (where are we?) · **III EXECUTION & TIMING** (is it firing?) · **IV DECISION SYNTHESIS** (what is the ruling?) · **V PLAN & RISK** (how do we size it?). The sections are not interchangeable — a name can be perfect on regime and worthless on location — and 32 undifferentiated rows read under time pressure hid that. **Room for Trade moved into DECISION**, because room is what decides whether a setup is tradeable at all. Table capacity 34 → 40. |
| **v9.12** | **STRUCTURE BASIS is now a ladder, not a sentence:** `Stage 2 (13w leg/13w macro) · >30WMA ↗️ · >50DMA ↗️ · >200DMA · Trend 75 ⬆️ · D ➡️ · W ➡️`. Icons match the RRG row and the two arrow families MEAN different things — **diagonals are a moving-average slope, verticals are a trend state**. Previously both used the same glyphs so you had to remember which kind each was. `>50DMA` had to be built: S4's only 50-SMA was the INDEX's, and v67 exports the 50-DMA *slope* but not the *position*. One daily call now returns `[SMA50, ATH, SMA50 slope]`, the slope subtracted INSIDE the call because `d_sma50[5]` on a 75m chart is five CHART bars, not five days. |
| **v9.12** | **off52 + offATH** on the extension row (`Price vs EMA20`), which already answers *how stretched are we* against value and volatility. 52-week distance alone cannot separate a name printing fresh highs from one that reclaimed its 52W high but sits far under its all-time high; side by side they do. Both signs forced negative with a literal minus so the convention cannot drift with the source — v67 publishes off52 POSITIVE. |
| **v9.12** | **Two defects fixed, both mine.** The re-sequence remapped `table.cell()` but not `table.merge_cells()`, so TRIGGER/STATUS/VERDICT moved to rows 27-29 while their merges stayed on 23-25 — the dark block to the right of those rows. And the Daily trend term sat inside `_zzOkD ? … : ""`, so an unbound Zigzag source did not blank the field, it **deleted** it; it now prints `D —`. Same rule as *unknown must never read as clear*: an absent input has to be visible as absent. |
| **v9.11** | **50-DMA slope made NATIVE.** It read v67's `s4_slope50` while the position came from S4's own SMA, so every recompile left the position printed with no arrow beside it. Fewer bindings is the durable fix — import from v67 only what S4 genuinely cannot compute. |
| **v9.2** | **FIB is long-only and direction-aware.** It measured DOWN from the 120-bar high unconditionally, which is only right when the swing is an ADVANCE being retraced. ANANDRATHI 75m: high 2176.2 (10-Jul) came BEFORE the low 2002.1 (24-Jul), so the leg was a DECLINE and the panel called 2068.6 "61.8" when it was the 38.2% retracement of that fall. A first fix measured UP from the low — a counter-trend BOUNCE, a short-seller's frame. **v9.2 measures the ADVANCE**: swing low, then the highest high made AFTER it, retraced downward. With no advance to measure the row prints nothing rather than a level with no leg behind it. `fib_tag` also reports the NEAREST level, not the first in a fixed ternary. |
| **v9.0** | **HTF NESTING, TF-RANKED.** Was a flat +1 for `_dzTfN >= 2` — a COUNT, so a 75m zone sheltered by a MONTHLY zone scored the same as one sheltered by a Daily zone. Now awarded by the RANK of the highest timeframe above the chart (M 3× · W 2× · D 1×). A zone on the chart's own timeframe is native, not nesting. |
| **v9.x stage** | **The stage is the 2×2, and all three surfaces now agree.** CRISIL read Stage 1 on the Dashboard and the GM board, Stage 3 on S4. S4 was right. See §Stage parity below. |
| **v8.9** | **ROLE vs LOCATION — a tag, never a gate.** A pattern's ROLE says *what* it claims is happening; the location says *where*. IGNITION is expansion AWAY from value (a volume thrust, a gap, a strong close); price inside a demand zone is being ABSORBED at value. Both can be arithmetically true of one bar while describing opposite things — and the pair still prints a clean `GO`. Measured on the live 75m board: **3 of 7 armed names were IGNITION-only inside a zone** (TITAN, UNOMINDA, HINDALCO). n=7 is a story, not a rate, so this **tags and never gates** — it cannot remove a signal, and it earns a gate only after a Σ-matched measurement, the way the combos were tested (and the combos failed). The converse case (TENSION alone at a level) had **zero** live instances, so it is deliberately NOT flagged: tagging it would assert a rule nothing supports. Roles mirror `pa_combos.ROLE` exactly — one definition, both surfaces. Prints `⚠role` on the **TRIGGER** row. |
| **v8.8** | **SPENT DEMAND STAYS VISIBLE** (`keep_tested_demand`, default ON). *"If there is a strong demand zone, I'll wait for the price to come back to the zone and retrace — then only I should take the entry. We need to keep the tested zones on the chart, else I'll lose the edge to trade them."* The old rule deleted a demand zone the moment it was TESTED — but the **reaction is the entry** and the **travel is the trade working**, so the most-evidenced level on the chart was the one erased, right after it proved itself. Now a tested demand zone is **greyed and kept** on a **touch budget**: a normal zone is spent after **1** test, a Controlling zone or one scoring ≥ `demand_strong_score` (default 75) gets **2**. Beyond the budget it is deleted. **A VIOLATED zone is still deleted immediately** — that is not a test, it is a failure. Note the asymmetry, which is the point: a spent **supply** zone can still act as resistance, but a spent **demand** zone is no longer a location or a trigger. It stays on the chart so you can see the level; it does not arm a trade. |
| **v8.7** | **PA COMBINATIONS.** A combo is a *sequence* — a structural CONTEXT that formed over the last N bars, released by a TRIGGER on the current bar — which Σ cannot express, because Σ sums booleans on one bar. Context ages come from `ta.barssince` on the existing flags, so an age can never disagree with the flag it is an age of. New panel row 32. **DISPLAY ONLY:** measured against a Σ-matched control on 464 picks, both testable combos *underperformed* (Coiled Spring −2.00pp, Institutional Ignition −1.18pp), so no combo feeds the gate or the confluence score. `Bear Trap` fires 0.33% of bars — too rare to ever be testable. |
| **v8.6** | Statement-cap reclaim (`f_zoneMaintain`). **The panel CANNOT be wrapped in a function** — a Pine function may reference at most **254 external elements** (inputs + `request.*` results, ints/floats/bools counting double) and the panel touches **453**. |
| **v8.5** | **ZONE DECLUTTER.** `Draw at most N zones each side of price` (default 3). Same-direction zones across 125m/D/W/M are kept on purpose (that is confluence), but with `extend.right` each box runs to the screen edge forever — measured on USHAMART: 15 boxes, **six overlapping inside a 40-point band**, which is what "the zones are glued to the screen" was. Display only; every zone stays live and still satisfies `z_inDZ`. |
| **v8.4** | **DASHBOARD IMPORT.** 13 `input.source` fields from v67 (`v67.4.18` exports them as hidden numeric plots) + 2 from the Zigzag, rendered as panel rows 29-31 so both panels need not be open. Strings cannot cross a source input, so the sector NAME and macro label stay on v67; the sector STAGE crosses. Unbound inputs default to a PRICE series — every row range-checks, and row 29 says `not bound — Settings ▸ Dashboard import` rather than showing dashes. |
| **v8.3** | Statement-cap reclaim (`f_activePA`, `f_soSnap`, `f_palette`). NOTE the same trick is **illegal for input groups**: `input(group=)` needs a `const string` and a function return is `simple` — attempting it produced 317 errors. |
| **v8.2** | **CANONICAL TREND.** S4's "W ↑" was `stage_n == 2` — a Weinstein STAGE read wearing a trend arrow. USHAMART is genuinely Stage 2 *and* genuinely sideways in weekly swing structure, so S4 printed `W ↑` beside the Zigzag's `W →`. The Swing Zigzag (**v6.4**) now exports `mtfTrendState` / `mtfTrendState2`; S4 reads them. `ALIGNED` now means what v67 and the Zigzag mean. Unwired falls back to the old proxy and marks it `~↑`. |
| **v8.1** | **STAGE PARITY WITH v67.** S4 took both the 30WMA position and its slope from `sma150` on **daily** bars over **10 days**; v67 uses `sma(close,30)` on **weekly** over **4 weeks**, band `0.0012 × MA`. A slow average barely moves in ten days, so S4 read FLAT where v67 read FALLING. Measured across 55 board names before changing: 3 differ (TECHM, LTFOODS, CASTROLIND), all Stage 2 → 3. The `above + flat` cell now resolves **1-vs-3** as its own comment always said (a flat 30WMA is not an advance), **paired** with decoupling `auto_rec` from the bare digit via the 200-DMA discriminant — otherwise every healthy base routes to the Recovery battery. |
| **v8.0** | **KNIFE-EDGE + GATE BASIS.** (a) Patterns sitting on their threshold are tagged `N⚖` — NAM-INDIA read Σ6 on the GM and Σ2 here for the SAME bar because Dhan closed it at 1210.4 (76.4% up the range) and TV at 1210.0 (73.2%); proven by swapping the OHLCV, same code, Σ6 → Σ2. (b) The `Nearest AVWAP` / `S/R` distance readouts measured from LIVE close while their gates read `[_so]` — AUROPHARMA showed `AVWAP −2.5%` beside `AT LOCATION` because the gate had measured 1.15% from the closed bar. |
| **v7.9** | **STAGE VETO REACHES BOTH ARMS.** `stage_skip` was the first branch of the GO+plan arm only, so a Stage-3/4 name that had not triggered fell through and read **ARM** — inviting an alert on a declining stock. |
| **v7.8** | **TIGHT PIVOT SHELVES** (S4Core v4 `rejectOnly`). A pivot shelf spanned the whole bridged body; on POLYCAB's June bar that was 648pts of which **483 was body** — the part price traded UP THROUGH, not where supply sat. Now the rejection region only. Measured over 55 names: monthly median zone width **8.7% → 4.9%**, weekly 5.5% → 3.9%, zone count UP (narrow shelves survive the max-width ceiling), and **ZERO `at_support` flips**. Per-TF pad + body tolerance added (M 1/0.5, W 2/0.8) — the tolerance is a multiple of ATR and ATR scales with timeframe. |
| **v7.7** | **ZONE COHERENCE.** A band cannot be supply AND demand. POLYCAB had SZ 9106.5-10126 and DZ 8791-9961 overlapping **855 points with spot inside BOTH**. Newer zone wins the contested band; the older is trimmed to its edge. Same TF only — a Monthly zone on a Weekly one is confluence. Fully engulfed → greyed, never deleted. |
| **v7.6** | **CLOSED-CONFIRM PIVOTS.** With the canonical monthly length of 1, a pivot low needs only ONE bar to its right — on the monthly chart that bar was a three-day-old August, so the zone could simply un-happen while feeding the location gate. The confirming bar must now be closed. |
| **v7.5** | **CANONICAL PER-TF PIVOT LENGTHS** — Monthly 1 · Weekly 5 · Daily 2 · Intraday 2, matching the Swing Zigzag and the S/R Lab. One global 5/3 served every timeframe: too coarse for the daily shelves price turns at, far too long for monthly bars. |
| **v7.4** | **PLAYBOOK SPLIT.** A breakout must expand on heavy volume and close strong; a pullback enters on volume DRY-UP with a bar that only holds the zone. One gate cannot be neutral between them, and S4 has no archetype — so it inferred the setup from patterns, and the two surfaces graded the same candle against different standards. The GM now hands the answer over (`Auto: GM Pullback list`). The inference had a real hole: a reversal bar off a demand zone that CLOSES STRONG fires Strong-Close, which counts as *expansion*, so the textbook pullback entry disqualified itself. |
| **v7.1** | **THE PULLBACK RULING.** The verdict ladder had *three* named breakout rulings (BREAKOUT PIVOT ×2, CLEAR TO BREAK) and one for recovery, but **none for a pullback** — so the house A+ setup (buy the pullback into a Daily+ demand zone) came out as a generic "TAKE IT", or was captured by CLEAR TO BREAK and described as a level to break *through*. New `_atValue` branch (Stage-2 · standing IN a real demand zone · not extended · not in supply), placed **above** CLEAR TO BREAK, which now carries `not _atValue`. It fires whether or not the reward gates clear — the headline says which (`TAKE IT — PULLBACK TO VALUE` vs `ARM — PULLBACK TO VALUE, reward still thin`). Unlike blue-sky and recovery it does **not** override `entry_method`, so a pullback at value keeps the Retest default. |
| **v7.0.1** | **Token de-duplication (no functional change).** 117 repeated `color.new()` literals → 18 constants; 72 repeated `X[_so]` reads → 12 variables; `f_size(panel_size)` ×12 → one. Freed **~1,400 compiled tokens** and took headroom from ~0 to several hundred. `array.size(activeZones)` is deliberately **not** hoisted — that array is mutated during the bar, so caching its size is a correctness bug, not an optimisation. |
| **v7.0** | **THE RECOVERY GUARD (NYKAA).** The `is_rec_v` branch was **unconditional**, so a name forced to Manual = Recovery short-circuited the ladder and printed `TAKE IT — Recovery ★strong` while `_blueSky` / `_clearToBreak` were unreachable — the same bar read TAKE IT in Recovery and CLEAR TO BREAK in Bull, with only the mode differing. And it is the greedy branch: no reward gate, and `_qRoomBad` excludes `is_rec_v` so room is bypassed too. Now `else if is_rec_v and not _stage2ok`. The guard is **`_stage2ok`, not an ATH test** — `stage_skip` already vetoes Stage 3/4, so the one remaining contradiction is Manual = Recovery on a **repaired** name (Stage 2 above a *rising* 30WMA **and** above the 200-DMA). A genuine in-progress recovery that reclaimed the 30WMA but is still under the 200-DMA fails `_stage2ok` and **keeps** this branch — correct, that one really is a recovery. |
| **v6.9** | Verdict wrap fix. |
| **v6.6-v6.8** | **Panel presentation.** Soft pastel palette ported from the Weinstein & Swing Pro dashboard; column alignment + the panel-width fix; **per-token PA badges** — every one of the ~17 battery tokens gets its own cell rather than being aggregated away. |
| **v6.4-v6.5** | *(reverted)* A CONTEXT row (Stage · RRG · RS vs N500 · Weekly trend · 30WMA · RSI) — **failed to compile at 102,602 tokens** and was reverted. Documented here because the finding matters: 4 of the 6 fields were already free (`stage_n`, the 30WMA state, `rsRatio`/`rsSlope`, and `rsi14` inside `f_daily_pa`) and two of them were **already on the panel** in the Structure basis row. Only RRG quadrant + Weekly Trend were genuinely new/expensive. |
| **v6.1-v6.3** | **VERDICT = DIRECTION, not a restatement.** Three real defects on a live TITAN panel: (1) *"SWING only" printed under a "POSITIONAL" plan* — two independent swing/positional determinations coexisted (`tt_swing` = the trade TYPE from structure; `_swingOk`/`_posOk` = house gates on REWARD) and were reported as peers. Now the trade **type** decides which gate applies, each quotes its own number. ⚠️ *Structural tension this exposed:* a POSITIONAL plan targets 5R, so ROI-to-T1 = 5 × risk% — with a 2.3% stop that is 11.5% and the **20% positional rule can never be met whenever risk% < 4%**. The two positional rules contradict each other by construction; the verdict now explains it rather than hiding it. (2) *Three entry instructions on one panel* — the TAKE-IT branch was overriding `entry_method` unconditionally, silently reversing the retest default the 23-Jul A/B established. (3) The **metrics digest was deleted**, not hidden — every field it carried already had its own row, and a hidden string still costs tokens. **VERDICT is now exactly four lines: ruling · why · the one caveat · the action.** |
| **v6.0** | **TRIGGER-BAR LATCH (found on PFC).** `pl_entry` was recomputed on **every** bar the GO stayed true, so a multi-bar GO sequence re-based the "retest limit" upward bar after bar — *a retest limit that follows price is a market entry wearing a limit's clothes*. Worse, the staleness guard tested `close > pl_entry` (price vs the quoted bar) and never asked whether that bar was the trigger, so it printed "(true retest)" precisely when the anchor was most stale. Now `var trigBar/trigCls/trigHi` latch on the **GO edge** in global scope, with a `· trig Nb ago` tag and a **re-latch after N bars** input (12) so a limit far behind an advancing market re-anchors rather than quoting fiction. `_cl` changed from `close[_so]` to `pl_entry` — necessary, not cosmetic: capping the ATR stop from the current close with a latched entry below it would **inflate R**. |
| **v5.9** | **CLASSIFY BY WEINSTEIN STAGE, NOT BY DRAWDOWN — and the THIRD STATE.** Auto never resolved CRISIL / GLAXO / COLPAL. Three successive diagnoses: manual mode was never broken (the blocker was `auto_require_below_200`); v5.8's drawdown band is a *qualification*, not a classifier; the answer is the **2×2 on `d_bel30` × `d_s150dn`** — below 30WMA + falling = Stage 4, below + not falling = **Stage 1 → RECOVERY**, above + falling = Stage 3, above + not falling = **Stage 2 → BULL**. Stage 3/4 → **`stage_skip`, a NO-TRADE third state that outranks every verdict branch and applies under MANUAL mode too** (the stage is a fact, not a preference). Previously a Stage-3 name was forced into one of two tradeable paths and the verdict then reasoned faithfully inside a frame it should never have entered — exactly how COLPAL (30WMA falling) reached "TAKE IT — Recovery ★strong". Also: `_stage2ok` was a **second** definition of Stage 2 that never checked whether the anchor was RISING; confluence paid points for **sellers** (`of_absorb` at supply means sellers absorbing — new `of_bull` drives the long-side terms); and `ta.cross`/`math.sum` were inside `if barstate.islast`, so the chop count was **garbage**, not merely non-idiomatic. **Rule: compute in global scope, display in the panel block.** |
| **v5.3-v5.8** | Σ **parity** (`kLAU`/`kRECLAIM` had no intraday guard and, keying off a weekly crossover that stays true all week, added +3 on **every** 75m bar — ~26 bars; `pa_patterns.py` suppresses both under `intraday=True`); WCL wiring; drawdown-band classifier (superseded by v5.9); "retest" honesty (the limit sits *at* the trigger close, so on the trigger bar it fills at **market**); four entry-conflict fixes; EXTENDED warning below the veto; DOWNGRADE on ≥2 quality faults. |
| **v5.0-v5.2** | **Weinstein Context Layers integration + the review that had to undo most of it.** v5.0 never compiled (101,338 vs 100,256) and **three of the five features its header advertised were declared but never wired**. Fixed in v5.1/v5.2: a **5-bar "sticky" PA window was REVERTED** — it claimed to match `pa_patterns.py`, but that module evaluates the **last bar only**, so the window *created* drift (ΣPA summed patterns from **different bars** — a Σ describing no bar that ever existed) and printed GO while the V/L/B gate chips read fail beneath it; `cf_w_wcl` was in `cf_max` but never added to `cf` (the ceiling rose while the score could not reach it); `near_vp_val`/`near_vp_poc` were computed and referenced nowhere — **Volume Profile VAL/POC is the one WCL component that earns its place** and now joins `support_pass` behind `en_wcl_loc` (~18% of names). Wyckoff was tested and **rejected** both as a GO veto (backwards — the vetoed cohort returned +5.60% vs +0.52% kept) and as a score input (held-out ρ +0.013, p 0.74); 49% of qualified picks read DISTRIBUTION at signal time because Wyckoff events fire at high-volume pivot highs — structurally what a breakout looks like. |
| **v4.7** | **BLUE-SKY / BREAKOUT-PIVOT ruling (APOLLOHOSP).** A Stage-2 leader within `ath_prox_pct` (3%) of its 52W high sitting in a supply band is a **continuation pivot, not distribution** — the "supply" there IS the prior high, meant to break. Reframes "SKIP · no room" → *don't buy here, arm a buy-STOP above the band ceiling, blue sky above*. Stage-2 only; a Stage 3/4 lower high stays a real SKIP. |
| **v4.6** | ABBOTINDIA reconciliation: **ext-ATR unit bug** (daily-EMA20 distance ÷ 75m ATR inflated extension ~3×; now `atrD_tf`) + the **WEAK-LOCATION guard** — a GO resting only on the AVWAP/EMA with no zone or S/R reads "CAUTION — momentum/chase", not TAKE IT. This is why the GM read "No location" while S4 said "TAKE IT strong"; both are now consistent. |
| **v4.3-v4.5** | The "must clear" obstacle **drawn on chart**; **controlling zones were structurally dead** (D/W/M passed `ctrlAllowed=false` — trend-reversal never counted); over-extension → verdict; EMA20-far zone-quality malus; round numbers +1 confluence; same-base zone dedup; S/R wick-fit line placement; daily-battery-agreement +1 confluence (**not** a gate); **dynamic risk** (Kelly × vol × regime, ported from Risk Allocator §9); **TRADE-TYPE plan** — `is_swing` (ATR% > 4 / off52 > 30% / below-200 → SWING else POSITIONAL) sets the SL cap (2.5× / 4.0× ATR) and the R-targets (swing 3R/5R · positional 5R/10R · Recovery T2 = 52WH). |
| **v4.2** | **VERDICT now RULES** instead of naming the first failing gate: TAKE IT / SKIP / **NOT TRADEABLE** (blocked **and** in-supply — "clearing that gate alone will NOT make this a trade") / LOW QUALITY / ARM. Multi-line so one long sentence stops stretching the panel across the chart. |
| **v4.1** | **⚠️ CRITICAL BUGFIX — the PA battery was reading a STALE bar.** `f_daily_pa`'s `_o = confirm_daily ? 1 : 0` shift was applied to **both** the daily security call (correct) **and** the chart-TF `loc_*` call (wrong) — so with defaults ON the 75m battery evaluated the bar **before** the last closed one, compounding with `[_so]` to up to **2 bars stale**, silently eating triggers. Fixed via a `confirmShift` parameter. **Likely the true cause of the GM→S4 GO conversion collapse.** *Lesson: when two surfaces disagree, diff the EVALUATED BAR/offset, not just the formulas — I had diffed only the BULL battery while claiming parity generally, and the failing case was RECOVERY.* |
| **v4.0** | **ARRIVAL STYLE + ORDER-FLOW Δ.** Arrival = the velocity of the approach leg into the zone (ATR/bar) → FAST (sharp rejection likely) / GRIND (absorbing → bleed-through) / NORMAL. Order-flow Δ is a **bar-level PROXY, not true tick/aggressor delta** (no TV plan exposes that to Pine): intrabar up/down volume via `request.security_lower_tf`, summed over a window → ABSORBING Δ+ / BLEEDING Δ− / NEUTRAL. Both **GRADE, they do not GATE.** |
| **v3.5-v3.9** | The 14-item review sweep: trigger path-specificity (`⇄both` / `Bull-only` / `Rec-only` tags — four patterns are shared, so a GO can survive a Bull↔Recovery flip); load no longer forces a Trendline draw; zone fill transparency input; grey-tested toggle; narrow-zone wick-to-wick rescue; recency decay on the displayed score; **HTF over-removal fix** — the tested EMA/level cross referenced the **DAILY** EMA20 for W/M zones, so a *weekly* zone died on a *daily* EMA cross (CoalIndia: 3 of 37 weekly zones alive); per-TF leg-in split (`legin_ltf` 0.6 intraday+daily / `legin_htf` 1.0 weekly+monthly); S/R wick-pierce touches; D/W/M pattern funnel diagnostics. |
| **v3.2-v3.4** | Horizontal **S/R levels** absorbed from Commander Chart Markup (MTTWR grading, R↔S flip); a 25-fix comprehensive audit; **panel rebuild**. |
| **v3.0-v3.1** | **INSTITUTIONAL DEMAND/SUPPLY ZONES replace the built-in OB.** The Institutional Zone Engine v4.2 subsystem was ported wholesale: `f_detectZone` (RBR/DBR/RBD/DBD leg-base-leg patterns) + `f_structZone` (pivot structural) on **Chart + Daily + Weekly + Monthly**. **Order Blocks were REMOVED as a support source** — the zones replace them; FVG and pivots are kept. MTF propagation fixed (calendar ageing per-TF by FORMATION time; same-TF dedup only), per-TF width bands, the "tested" rule (reaction → travel/EMA/pivot cross → **deleted**), exclusive controlling zones, box-text labels, per-TF label colours. **GO logic redesigned (Option A):** `go = any_pa AND support_pass AND vol_ok AND bar_ok`; AVWAP/intraday become **optional timing (⏱)**. **`bar_ok`** (green OR close in the upper half) kills big-red distribution/upthrust GOs. |
| **v2.9** | On-candle "GO" matches the panel; format-string bug fix (`"#.1"`/`"#.2"` are broken in Pine — they round to int and print a literal decimal; use `"0.00"`). |
| **v2.8** | **`use_chart_tf` defaults ON. Current design.** The Pine PA battery now runs on the chart TF (75/125m) out of the box, matching the GM (Trigger TF also defaults to 75m). No-op on a Daily chart; Auto path / LAU / RECLAIM / zones stay Daily/Weekly regardless. |
| **v2.7** | **Chart-TF battery parity fixes (review of v2.5/v2.6).** The `use_chart_tf` battery now matches the GM Python exactly: **HTF suppressed** on chart-TF (positional "100% in 8 weeks" — was the one leaking pattern), and the **chart-TF engulf uses the DAILY EMA20/EMA10** (DNA anchor, via `f_daily_pa` refs) instead of an intraday EMA20. Auto-path, Stage-2 Launch, 30-WMA Reclaim and the OB/FVG/pivot zones already stayed Daily/Weekly. |
| **v2.6** | **`use_chart_tf` toggle** — when ON, the PA battery computes on the active chart TF (75/125m) instead of daily (mirrors the GM's Trigger-TF selector). Auto path + LAU/RECLAIM + support zones remain Daily/Weekly. |
| **v2.5** | **Responsive intraday triggers:** `require_squeeze` toggle (default ON; OFF lets a high-volume 10-EMA reclaim fire GO alone); **relaxed squeeze window** (`sqz_releasing` — fires while momentum rises out of the squeeze, not only the single fire bar); **TF-aware volume** — on an intraday chart the GO volume gate accepts the chart-TF relative volume (not just the incomplete daily bar), so morning breakouts aren't blocked. |
| **v2.4** | **Zones start at their FORMATION candle.** `f_zones()` captures the origin bar-time of each OB (down-candle), FVG (3-bar gap) and pivot (pivot-low bar); the boxes/lines are drawn from that time and extend right — so a zone begins at the candles that made it, not the fixed 180/540-day lookback of v2.1 (which started "from nowhere"). Flipped pivots keep their original origin. |
| **v2.3** | **Auto path ↔ Golden Matcher parity.** `Auto` now mirrors the GM's structural Bull-vs-Recovery split by adding the **200-DMA discriminant**: a name **above its 200-DMA resolves Bull** (matches GM's Bull-by-default / accumulation-above-200DMA), and only a genuinely beaten-down turn (**≥ floor off 52wk high AND 30-WMA not repaired AND below the 200-DMA**) flips to **Recovery**. This stops a shallow bull **pullback** (10–15% off highs, still above the 200-DMA) from mis-resolving Recovery while GM stays Bull. The **Auto basis** panel row now shows the 200-DMA state; manual `Mode` override unchanged. *Residual gap (documented):* Pine can't see RFF, so an early recovery that has already reclaimed the 200-DMA resolves Bull here vs Recovery on GM — use the manual override. *(Also: I **rejected** Gemini's "double-shift lag" fix — its `timeframe.isdaily` gate reintroduces the intraday repaint; the `[1]` offset is timeframe-independent and correct.)* |
| **v2.2** | **Tested-zone lifecycle.** An OB/FVG is auto-sensed as **tested** once price has **entered it and left** (a completed mitigation). Tested zones **grey out** and are **excluded from `require_support` / the GO trigger** — only **fresh** zones qualify (the first tap of a fresh zone is the setup; a retest is spent). The current first tap still reads fresh. **Pivot lines are never deleted** — tested → stay as support; **violated (close below) → flip to resistance** (maroon `Pivot S→R`, previous-support-now-resistance), cleared on reclaim. Panel Support Zone row marks a tested zone under price with a `t` suffix (`OBt`/`FVGt` = present but excluded). Mirrored 1:1 into the GM Python (`ob_tested` / `fvg_tested` / `pivot_res`). |
| **v2.1** | **Support zones on Daily *and* Weekly.** The OB/FVG/pivot trackers were extracted into `f_zones()` and are requested on **both `"D"` and `"W"`** — the trading TF stays 75/125-min, but demand zones now come from Daily *and* Weekly structure. **Weekly** zones draw **solid/thicker** (bigger structural demand), **Daily dashed/thin**. `require_support` passes on a **Daily OR Weekly OR AVWAP** zone; the Support Zone panel row reads `D:.. W:..` and the GO alert names the timeframe. New `show_zones` toggle. Also fixed the **weekly Stage-2-Launch offset** (a `timeframe.isweekly` gate had made 75/125-min charts repaint the weekly crossover — now TF-independent). Mirrored 1:1 into the GM Python (`pa_patterns.detect_support_zones_dw`). |
| **v2.0** | **Automated support zones — Steps 1-2 of the Guided Execution are now drawn for you.** Three stateful daily trackers: **Order Block** (last down-candle before a volume displacement up), **Fair-Value-Gap** (3-bar bullish gap `high[2] < low`), and **Pivot Support** (`ta.pivotlow(5,5)`, confirmed 5 bars later). Each invalidates on a close below it, is drawn as a box/line near the last bar, and is summarised in a new **"Support Zone"** panel row. New input **`require_support`** (default ON) gates GO on price being inside/near a support level. **Two fixes over the initial cut:** (a) the confirmed-daily offset is timeframe-independent again — a `timeframe.isdaily` gate had made 75/125-min charts repaint the battery through the session; (b) an **AVWAP support also counts** toward `support_pass`, so an AVWAP bounce isn't suppressed for lacking an OB/FVG. The GO alert names the zone. **Mirrored 1:1 into the Golden Matcher Python** (`pa_patterns.detect_support_zones`). |
| **v1.0** | Three anchored VWAPs (Low / BO / Gap) with daily-derived anchor dates; pinch detection; AVWAP bounce / Red-to-Green trigger; intraday 10-EMA + TTM-squeeze trigger; entry panel + plan line; alerts. |
| **v1.1** | *(interim)* Added the first daily PA layer (the plan's 8 §4 triggers). Superseded. |
| **v1.2** | **PA layer re-based to the canonical 11 Golden-Matcher conditions** (Power Play HTF / Strong Close, VCP-BO, Pocket, gated Engulf, Liq Sweep, 3-Bar Rev, Stage-2 Launch, Inside-3, True NR7, IB-NR7) with **Σ tier** scoring; correct `ta.vwma(volume,5)` dry-up; na-safe float returns; ASCII panel; unique title. |
| **v1.9** | **GM-parity audit follow-up + alert upgrades.** (1) **Higher-Low/2B** gains a base-proximity ceiling (`recent low ≤ prior base low × 1.10`) — without it the +3 pattern fired on nearly every green day of an uptrend (same fix applied to `pa_patterns.py` the same day). (2) **Stage-2 Launch** now requires the **Stage-2 proxy** (close above a *rising* 30-WMA proxy) — mirrors Python's `"2" in stage` gate; previously LAU could fire on a Stage-4 dead-cat bounce that crossed the 30-WMA. (3) **`auto_dd_floor` input** (default 10) exposes the Auto-mode off-52WH threshold — keep in sync with GM recovery `CONFIG.min_stock_correction_pct`. (4) New **"Auto basis" panel row** (off52% + 30-WMA state) so Auto's Bull/Recovery resolution is explainable. (5) **Self-describing GO `alert()`** — names mode + which leg fired (AVWAP/intraday) + RV on the GO rising edge; plus a new **Σ-strengthening alert** when another pattern joins while one is already live (`pa_fire` only caught the first). |
| **v1.8** | **Auto rule fixed.** v1.7's `off52 ≥15% AND below SMA150` was self-defeating — recovery names at Step 5 have *confirmed the turn* and often reclaimed SMA150, so the best recoveries (e.g. CIPLA) resolved **Bull**. New rule: **Recovery when ≥10% off the 52-week high (the GM recovery CONTEXT gate) AND trend-not-repaired (below the 30-WMA proxy OR its 10-day slope falling)**. A fully repaired name (above a *rising* 30-WMA, <10% off highs) is genuinely Stage-2 → Bull. **Current design.** |
| **v1.7** | **Mode gains `Auto` (new default)** — infers the path from price structure: **≥15% off the 52-week high AND below the 30-WMA proxy (SMA150) → Recovery battery, else Bull** (mirrors the Golden Matcher's recovery CONTEXT gate). The panel header shows what Auto resolved to (`PA · RECOVERY (auto·EOD)` etc.); manual Bull/Recovery remain as overrides. Caveat: Auto is a price-structure approximation — Pine can't see RFF/fundamentals, so on a rare borderline name it can resolve differently than the Golden Matcher; the header keeps the choice visible. **Current design.** |
| **v1.6** | **Unified Bull/Recovery.** New **Mode** input swaps the PA battery: **Bull** = the 17 continuation/breakout conditions; **Recovery** = 10 capitulation-reversal + Wyckoff-accumulation conditions (Climax Reversal, Wyckoff Spring, Higher-Low/2B, Base-Breakout SOS/JAC, Bull Engulf, Hammer-at-support, 3-Bar Rev, Pocket, Volume-Dry-Up, 30-WMA reclaim) for beaten-down, fundamentally-strong bases. Shared plumbing (AVWAP price memory, RV, intraday trigger, TRIGGER gate) is identical; only the battery + panel grid + header (`PA · BULL` / `PA · RECOVERY`) change. Mirrors the Golden Matcher's Bull `compute_workflow` (17) and Recovery `compute_recovery_workflow` (10). RS-turning-up lives in the recovery **Quality gate**, not the battery. **Current design.** |
| **v1.5** | **TRIGGER row is now the COMBINED gate** — `Event (E) · Volume (V) · Intraday (I)`, each shown ✓/·, colour-coded. **GO = a trigger fired (E *or* I) AND volume (V)** — deliberately **not** all three at once (that would be a rarely-gettable "Holy Grail"; intraday is the *premium* confirmation, not mandatory). **Volume floor is a tunable input** (`rv_floor`, default RV 1.0). **RV is now its own colour-coded field** (green ≥1.25 / amber ≥1.0 / red <1.0). Plan prints only when TRIGGER = GO. **Current design.** |
| **v1.4** | **PA battery expanded 11 → 17** — added the strong v67-cascade triggers the curated 11 omitted: **Wyckoff Spring (+3), Gap-Up Breakout (+3), 50-SMA Undercut (+2), Hammer@50 (+2), Hammer@200 (+2), Breakout-Confirmed (+2)**. Panel now shows **all 17 as a compact grid** with per-condition **fired (✓) / quiet (·)** — nothing hidden. The Golden Matcher's `_detect_pa_patterns` was expanded to the same 17 for zero drift. **Current design.** |
| **v1.3** | Three changes: (1) **"Confirmed daily only" toggle (default ON)** — the daily PA battery reads the last CLOSED daily bar so patterns no longer repaint on the forming intraday bar (a 30-min-old day was flashing false NR7/IB-NR7); OFF = live developing bar; header shows `(EOD)` vs `(live*)`. (2) **New consolidated `TRIGGER` field** — clear GO / ARMED / COIL / NO-TRIGGER status; the **Plan now prints only on an actual actionable trigger** (AVWAP bounce/R2G or intraday GO), never on a daily PA/coil alone (fixes the old "coil implied a trade" ambiguity). (3) **Dark-theme panel** — solid dark bg + TV grid frame + higher-contrast label text. **Current design.** |

> **Note on the filename:** the file is `Section4_Entry_Trigger_v5.9.pine` (git-tracked since 29-Jul-2026) and the **in-file indicator title is v7.1**. Filename and title deliberately diverge — the title is bumped every revision so TradingView never reuses a stale study's persisted panel table. A pre-WCL reference copy of v4.7 remains at `Section4_Entry_Trigger_v3.0.pine`.
>
> ### ⛔ TWO OPERATIONAL RULES — read before editing or recompiling
>
> **1. The file lives at the compiled-token ceiling.** TradingView's limit is **100,256** tokens and S4 sits within a few hundred of it. **Every addition needs a paired removal.** Cost is per **operation** (concat / ternary / call / index), *not* per character — a string literal is **one token however long**, so trimming tooltips or comments saves nothing, and newlines inside strings are free. Measured ratios: **~2.12×** compiled-per-source for structural code, **~3.46×** for verdict/panel string code (concat-and-ternary chains are ~60% more expensive). Before adding, check what is already computed — in the one audit done, 4 of 6 requested fields were already free and 2 were already on screen. The scalable escape hatch is `input.source` bridging (~2 tokens per field, and zero-drift by construction) rather than recomputing what v67 already publishes.
>
> **2. A recompile DESTROYS your alerts — it does not stale them.** Alerts bind to the compiled `pine_id`. After every compile you must **delete and re-create every "S4 GO" alert**. This is not optional housekeeping: a silently-lost alert on an armed name is a trade you will never see. (This is what silenced the JBCHEPHARM alerts.)

---

# PART A — USER GUIDE

## 0b. Stage parity — the definition all three surfaces share (9 Aug 2026)

CRISIL printed **Stage 1** on the Dashboard and the GM board and **Stage 3** on S4, for the same chart. S4 was right, and closing the gap took three separate fixes on the Python/v67 side.

**The definition, everywhere:** price vs the weekly 30-SMA × that MA's slope, classified fresh each bar.

| price vs 30-WMA | MA slope | stage |
|---|---|---|
| above | rising | **2** |
| above | falling | **3** |
| above | flat | RS up → 1, else 3 |
| **below** | **rising** | **2 (PULLBACK)** |
| below | falling & RS not up | **4** |
| below | flat | **1** |

**What was wrong before.** GM and v67 both ran a *hysteresis state machine* that evolved the stage from its previous value, so promotion required a RISING 30-WMA and a name trading well above a DECLINING 30-week average never left "Stage 1". MPHASIS sat at Stage 1 with its 30-WMA falling 62.9 points and price 5.8% above it — distribution, not a base. Measured over 56 board names, **19 (34%) were mis-staged** and `stage_ok` moved 48 → 41.

Two further gaps were older and less visible: the slope was a **per-bar rate** (`(ma − ma[n]) / n`) against S4's raw N-bar change, and the lookback was **6** against S4's **4** — together making Python's flat band 6× wider. Both were hidden by hysteresis; with a stateless read they decide the digit.

The two `tDir` strict-trend overrides (4→1, 2→3) are **gone**. A stage a separate pivot engine can rewrite is a stage you cannot reason about, and it is what let the panels disagree.

**Two deliberate differences remain**, both documented in code: the **flat cell** (S4 breaks the tie with RS slope, v67 with `tDir`, because only `tDir` is in scope where v67 classifies), and **STAGE 2 (PULLBACK)** — v67 names that cell, S4 folds it into Stage 2. Same family, different label granularity.

## 1. What it does (in one breath)

For the single name on the chart it:
1. **Detects the daily PA battery** (17 Bull / 10 Recovery, mode-selected) and shows which fired + a **Σ tier** score (patterns are *bonuses*, not a fixed checklist).
2. **Draws three anchored VWAPs** — the institutional **price memory** — and flags when they **pinch** (converge) into a high-conviction zone.
3. **Auto-marks the demand zones (v2.0)** — a daily **Order Block**, **Fair-Value-Gap** and **pivot-low support** — as boxes/lines, and tells you whether price is sitting inside/near one (the **Support Zone** row). This is Steps 1-2 of the Guided Execution done for you.
4. Fires an **AVWAP trigger** (bounce off support, or a Red-to-Green reclaim above the breakout AVWAP).
5. On 75/125-min, fires the **intraday trigger** (reclaim of the rising 10-EMA + TTM squeeze firing up).
6. Prints a **plan line** (buy-stop above the bar high, SL below nearest support) and raises **alerts** so you can walk away.

The one question it answers: *"A leader is at its zone — is price actually in a demand zone, has a real trigger printed yet, and where exactly do I buy-stop and stop-loss?"*

## 2. Installation

1. **Prerequisite:** the name should already be a **Golden Matcher Step-5** candidate (Context + Quality + Setup + Location green). This indicator is the *last* layer, not a scanner.
2. **Pine Editor → paste `Section4_Entry_Trigger_v1.0.pine` → Save → Add to chart.** It is an **overlay** (draws on price).
3. **Timeframe:**
   - The **daily PA battery** and the **AVWAPs** work on any chart TF (anchor dates/patterns come from the Daily via `request.security`).
   - The **intraday trigger** row is meaningful only on **75-min or 125-min** — that's where the 10-EMA reclaim + squeeze fire.
   - Recommended: keep it on your execution TF (125-min), and read the daily PA rows from there.
4. Leave the defaults as-is for the first pass (they mirror the Golden Matcher). Tune only the pinch/tolerance and anchor lookbacks if a specific chart needs it.

## 3. Inputs — field by field

### 3.1 Anchored VWAPs
| Input | Default | Meaning |
|---|---|---|
| **AVWAP Stage-1 Low** | ✓ | Show the AVWAP anchored to the 52-week / Stage-1 **absolute-bottom low** — the institutional cost baseline. |
| **AVWAP Breakout** | ✓ | Show the AVWAP anchored to the most recent **N-bar-high breakout day**. |
| **AVWAP Gap-up** | ✓ | Show the AVWAP anchored to the last **high-volume gap-up day** (earnings/news). |
| **Low-anchor lookback (days)** | `252` | Window for the Stage-1 low anchor (52 weeks). |
| **Breakout-anchor lookback (days)** | `40` | The breakout is a cross above the prior `40`-bar high. |
| **Gap-up min %** | `3.0` | Minimum gap size (open vs prior close) to qualify a gap anchor. |
| **Gap-up vol x 50d avg** | `1.5` | The gap day must trade ≥ `1.5×` its 50-day average volume. |

### 3.2 Daily PA battery
| Input | Default | Meaning |
|---|---|---|
| **Mode** | `Auto` (v1.7; parity v2.3) | `Auto` / `Bull` / `Recovery`. **Auto** mirrors the Golden Matcher's structural split: it resolves **Recovery** only when **≥ `auto_dd_floor`% off the 52-week high AND the 30-WMA proxy not repaired (below it, or its 10-day slope falling) AND below the 200-DMA**; otherwise **Bull**. The 200-DMA leg (v2.3) keeps a shallow bull pullback (above the 200-DMA) resolving Bull, matching GM. Panel header + Auto-basis row show what it resolved to; `Bull`/`Recovery` force it. |
| **Detect the daily PA patterns** | ✓ | Master toggle for the whole PA battery + its panel rows + `pa_fire` alert. Turn off for a pure price-memory view. |
| **Confirmed daily only (no intraday repaint)** | ✓ (v1.3) | ON = the battery reads the **last CLOSED daily bar** — patterns don't flicker on the forming intraday bar, and it matches the Golden Matcher's EOD read (panel header shows `PA CONDITIONS (EOD)`). OFF = the live **developing** daily bar, which repaints intraday (header shows `(live*)`). Leave ON unless you deliberately want the same-day developing view. |
| **Volume floor (RV) for a valid trigger** | `1.0` (v1.5) | The TRIGGER only reads **GO** if relative volume ≥ this. 1.0 = average day; a real breakout usually has RV > 1.25. **Lower it (e.g. 0.8)** if you find it too strict; raise it to demand stronger participation. This is the knob that decides how "gettable" a GO is. |
| **Auto: min % off 52W high for Recovery** | `10.0` (v1.9) | The off-52WH threshold Auto uses to pick the Recovery battery. Mirrors the Golden Matcher recovery CONTEXT gate (`CONFIG.min_stock_correction_pct` = 10) — keep the two in sync. |
| **Use chart timeframe for PA patterns** | **ON (v2.8)** | ON = the PA battery computes on the **active chart TF** (75/125m) — **default**, to match the GM (Trigger TF also defaults to 75m). HTF is auto-suppressed and the engulf keeps its **daily** EMA20 anchor (v2.7). OFF = always **Daily** (EOD). On a Daily chart the toggle is a no-op. Stage-2 Launch, 30-WMA Reclaim, the Auto Bull/Recovery path, and the OB/FVG/pivot zones always stay Daily/Weekly regardless. |

### 3.3 Pinch & entry zone
| Input | Default | Meaning |
|---|---|---|
| **Pinch tolerance (% spread across AVWAPs)** | `2.5` | The three AVWAPs are "pinched" when their high-vs-low spread is ≤ this % of price. Tighter = stricter high-conviction zone. |
| **Support-touch tolerance (% around AVWAP)** | `1.0` | How close the bar's **low** must come to an AVWAP to count as a "touch/bounce", and the buffer used to place the SL below support. |
| **Require Price in Support Zone (OB/FVG/Pivot)** | ✓ (v2.0) | When ON, the **GO** trigger only fires if the close is **inside or within 1.5%** of an active Order Block, FVG, pivot support (**Daily OR Weekly**), **or AVWAP** — automating "is price at a real demand zone?" (Steps 1-2). Turn OFF to let a trigger fire on volume alone regardless of location. |
| **Draw OB / FVG / Pivot zones (Daily + Weekly)** | ✓ (v2.1) | Toggles the on-chart zone drawings (Daily dashed/thin, Weekly solid/thick). Turn off for a clean chart while keeping the `require_support` gate + panel row active. |

### 3.4 Intraday trigger (apply on 75/125-min)
| Input | Default | Meaning |
|---|---|---|
| **Show intraday 10-EMA + TTM-squeeze trigger** | ✓ | Master toggle for the intraday row + `GO` marker + intraday alert. |
| **Intraday EMA length** | `10` | The reclaim EMA (Shannon's rising-10-EMA reclaim). |
| **BB mult** | `2.0` | Bollinger-Band multiplier for the squeeze. |
| **KC mult** | `1.5` | Keltner-Channel multiplier for the squeeze. |
| **Squeeze length** | `20` | Lookback for BB/KC/momentum. TTM squeeze = BB inside KC; "fires up" when the squeeze releases with positive momentum. |
| **Require TTM Squeeze to fire** | ✓ (v2.5) | ON = the intraday trigger needs a squeeze release (relaxed to a *rising-momentum-out-of-squeeze* window, not just the single fire bar). OFF = a high-volume 10-EMA reclaim alone fires the intraday trigger — more responsive for morning breakouts. |

*Volume note (v2.5): on an intraday chart the **GO** volume gate accepts the **chart-TF** relative volume (or the daily), so a 75/125m breakout isn't blocked by the still-incomplete daily volume bar.*

### 3.5 Display
| Input | Default | Meaning |
|---|---|---|
| **Entry panel** | ✓ | Show the info table. |
| **Panel position** | `top_right` | `top_right / top_left / bottom_right / bottom_left`. |
| **Low / BO / Gap colours** | blue / purple / orange | Line colours for the three AVWAPs. |


### 3.6 Handoffs from the Golden Matcher (v7.4 / v7.3)

S4 cannot see which screen qualified a name — that lives in the GM's watchlists, on RFF
fundamentals and history no price rule can recover. So the GM hands the answer over.
Paste each list **once per watchlist refresh**; the answer is a property of the NAME, so
the same paste is correct on every timeframe.

| Input | What it does |
|---|---|
| `Auto: GM Recovery list` | Symbols here resolve **Recovery**. Anything else falls back to the stage/drawdown heuristic. |
| `Auto: GM Pullback list` | Symbols here take the **pullback playbook** — volume floor drops to `pb_rv_floor`, and the bar test becomes "closed back above the zone distal" instead of "closed strong". **The demand-zone requirement is NOT relaxed** — that is the discipline of the setup and the only thing keeping the lower floor honest. |

Get both from the Trigger Board header. Names on *both* lists are genuinely ambiguous and
are left to S4's own inference rather than an arbitrary preference here.

### 3.7 Zones — structural (v7.5 – v7.8)

| Input | Default | Notes |
|---|---|---|
| `Pivot length — Monthly / Weekly / Daily / Intraday` | 1 / 5 / 2 / 2 | Canonical, shared with the Swing Zigzag and the S/R Lab. Do **not** raise Daily to reduce noise — that breaks Zigzag alignment; filter with min-move or the width band instead. |
| `Pivot zones: confirming bar must be CLOSED` | ON | Kills the repaint. At monthly length 1 the confirming bar can be three days old. |
| `Resolve supply/demand overlap (newer wins)` | ON | A band cannot be supply and demand. Same TF only; cross-TF overlap is confluence. |
| `Pivot shelf = rejection region only` | ON | Supply = body-top→high, demand = low→body-bottom. OFF restores the old whole-body span. |
| `Monthly / Weekly: pad bars + body tolerance` | 1/0.5, 2/0.8 | How far a shelf reaches into neighbours' bodies. The tolerance is × ATR, and ATR scales with timeframe — which is why one global value could not serve all four. |
| `Draw at most N zones each side of price` | 3 | **Display only.** Never changes the gate, the counts or a verdict. |

### 3.8 Imported from the v67 Dashboard (v8.2 / v8.4)

Bind these to the hidden `s4_*` plots on **Weinstein & Swing Pro Dashboard [v67.4.18]**
and to the Swing Zigzag's `mtfTrendState` / `mtfTrendState2`. They carry **the value that
indicator computed** — not a re-implementation — so an imported field cannot drift.

Two constraints worth knowing: `input.source` carries **one float series**, so strings
(sector name, macro label) cannot cross and stay on v67; and inputs are matched by
**position**, so inserting a new input mid-list drops existing bindings — if the rows go
blank after an upgrade, re-bind rather than debug.

Unbound is safe: an unwired source defaults to a PRICE series, every row range-checks it,
and row 29 reads `not bound — Settings ▸ Dashboard import` rather than showing dashes.

## 4. Reading the panel (top to bottom)

Since **v9.12 the panel is SECTIONED** — 32 fields under five banded header rows, each
stating the question its block answers. The sections are not interchangeable: a name can
be perfect on regime and worthless on location. Read them in order and stop at the first
one that fails.

The map below is the live panel, verified against a running chart (SONACOMS 75m,
10-Aug-2026) via `data_get_pine_tables`. Row numbers are `f_row`/`f_sec` ids in the source.

### I · MACRO & CONTEXT — *what is the underlying regime and environment?*

| Row | Reads | How to use |
|---|---|---|
| **Structure basis** | A position/direction **ladder**: `Stage 2 (27w leg/27w macro) · >30WMA ↗️ · >50DMA ↗️ · >200DMA · Trend 75 ⬆️ · D ⬆️ · W ⬆️` | Two arrow families, and they mean different things — **diagonals (↗️↘️➡️) are a moving-average SLOPE, verticals (⬆️⬇️) are a TREND STATE**. The trend ladder runs chart-TF → next two higher (so a Daily chart ends at M). A field printing `—` means the source is **unbound**, not flat. |
| **WCL Context** | `BULL (+6)` / `BEAR` / `NEUTRAL` | Wyckoff-SMC composite. Grading only — measured and rejected as both a veto and a score input. |
| **Structure Health** | `CLEAN (0)` | CHoCH count. `CLEAN` on ~90% of names is **expected**, not a bug. |
| **RS · RRG (vs N500)** | `N500: Rising (Positive) ↗️ · Sec: Rising (Positive) ↗️` / `LEADING ↗️ +2 · LEADING (stable) · ✓ BUY OK (RS-Ratio 114.3)` | Wording is identical to v67 by design. The quadrant is derived from the same (RS-Ratio, RS-Momentum) pair v67 classifies with, so it **is** v67's quadrant. |
| **Sector · Futures OI** | `Sector Stage 3 · OI Short covering +2.5%` plus its plain-English reading | The OI state is only meaningful against price direction, so it is derived from both: **Long build-up** (price↑ OI↑) fresh money · **Short covering** (price↑ OI↓) the rally is shorts exiting, fades are common, do not chase · **Short build-up** (price↓ OI↑) supply into strength · **Long unwinding** (price↓ OI↓) weak, not a short signal. |
| **Signal · Quality · RSI** | v67's Action Signal (0-10), Asset Quality (0-100 + letter), daily RSI | `not bound` = the `input.source` bindings are missing, **not** that the data is absent. Re-bind after every recompile. |

### II · LOCATION & QUALITY — *where are we on the chart right now?*

| Row | Reads | How to use |
|---|---|---|
| **Zones (MTF)** | `between zones · 11 DZ / 0 SZ live` or `IN DEMAND · …` | Live zone inventory across Chart/D/W/M. |
| **Support Zone** | `D:- W:-` or the zone grade + TF | The leg-base-leg zone under price, per timeframe. |
| **S/R (nearest)** | `S 784.80 ·W (−4.3%) │ R —` | Nearest horizontal level each side, with its source TF. **MTTWR-graded levels are deliberately excluded from this picker** — repeated tests WEAKEN a level; one tested that often is a breakout candidate, not a ceiling. `R —` with nothing above is what produces `BLUE SKY`. |
| **Trendlines** | `off` / the auto or manual line | — |
| **Volume Profile** | `✓ ABOVE VAH (POC 723.00)` | VAL and POC join the location sources when `en_wcl_loc` is ON (default). The one WCL component that earned its place (~18% of names). |
| **Price vs EMA20 (D)** | `ABOVE +9.5% (Norm) · ATR(D) ₹23.7 (2.9%) · off52 −4.0% · offATH −0.5%` | The extension read. **off52 and offATH together** separate a name printing fresh highs from one that reclaimed its 52W high but sits far under its all-time high. Both signs forced negative — v67 publishes off52 positive. |
| **Location (L)** | `NOT AT LOCATION — Zone · D/W-lvl · AVWAP · EMA20 · S/R ·` | The **L gate**, with each source ticked or dotted. This is the gate the board mirrors. |

### III · EXECUTION & TIMING — *are the intraday triggers and PA patterns firing?*

| Row | Reads | How to use |
|---|---|---|
| **Intraday \<TF\>** | `GO 10EMA+sqz` / `10EMA ok, sqz wait` / `sqz ON, wait EMA` / `wait` / `off` | Momentum timing on the chart TF. **Optional** since v3.0 — it times, it does not qualify. |
| **Nearest AVWAP** | price + distance | The closest anchored VWAP at or below price. |
| **AVWAP L·BO·Gap** | the three anchors | Low (52wk/Stage-1 bottom) · Breakout · Gap. |
| **Pinch** | `YES x%` / `no x%` | Anchors converged = high-conviction zone. Lower % = tighter. |
| **AVWAP trigger** | `FIRED bounce` / `FIRED R2G>BO` / `waiting` | Optional timing leg (⏱ on the TRIGGER row). |
| **Pattern \| Shape** | `no flag │ —` | Flag / geometry classifier. ⚠ The 2-pivot classifier calls rectangles "symmetrical triangles" (APOLLOHOSP, GLAXO) — known, unfixed. |
| **PA · BULL/RECOVERY (auto·\<TF\>) Σ+N** + **grid** | Every condition of the active battery, `✓` fired / `·` quiet — nothing aggregated away | Bull codes: HTF, SC, VCP, LAU, GAP, BC, PP, U50, LIQ, SPR, ENG, 3BR, H50, H200, IN3, NR7, **IBN**. Recovery: CLIMAX, SPR, 2B, SOS, ENG, HSUP, 3BR, PP, VDU, 30WMA. **`IBN` has no Python twin** — see the drift note in the header. |
| **PA Combo** | `COILED SPRING · VCP 6b → coil now` | The **sequence** Σ cannot express. **Narrative only** — both testable combos underperformed a Σ-matched control on 464 picks. |
| **Bar (B)** | `OK — green candle (bullish close)` | The **B gate**. In a pullback context it becomes *held the zone* instead of *closed strong*. |
| **Arrival · Δ** | `FAST / GRIND / NORMAL` + `Δ+ absorbing / Δ− bleeding` | Approach velocity and an intrabar order-flow **proxy** (not true aggressor delta — no TV plan exposes that to Pine). Grades, never gates. |
| **RV (rel vol · \<TF\>)** | `1.30 strong` / `1.05 ok` / `0.20 thin` | The **V gate**. Floor is `rv_floor` (1.0), dropping to `pb_rv_floor` (0.5) in a pullback context. |

### IV · DECISION SYNTHESIS — *what is the final ruling of the engine?*

| Row | Reads | How to use |
|---|---|---|
| **Room for Trade** | `BLUE SKY 🚀` / `1.4R to <obstacle>` / `NO ROOM` | Distance to the **first obstacle overhead** across six sources. Pivot ceilings are named `Pv·` and ranked last. Room is what decides whether a setup is tradeable at all — which is why it sits in DECISION, not LOCATION. |
| **Confluence n/23** | the scoring terms that fired | Grades the setup. `★strong` at the threshold. |
| **TRIGGER** | `no location  P✓ L· V✓ B✓ ⏱  Bull-only  7/23` | The four gates as chips — **P**attern · **L**ocation · **V**olume · **B**ar — plus optional ⏱ timing, the path tag (`⇄both` / `Bull-only` / `Rec-only`), `·PB` for a pullback-relaxed gate, and **`⚠role`**. |
| **STATUS** | the same gates in words + `conf` + `RV x/floor` + `Σ` | — |
| **VERDICT** | Exactly **four lines**: ruling · why · the one caveat · the action | Rulings: **TAKE IT** · **SKIP** · **NOT TRADEABLE** (blocked *and* in supply — clearing the one gate will not make this a trade) · **LOW QUALITY** · **ARM** (names the single missing gate) · **BREAKOUT PIVOT** (Stage-2 within 3% of the 52W high in a supply band — don't buy here, arm a buy-stop above the band) · **NO TRADE** (Stage 3/4, outranks everything, applies under manual mode too). |

### V · PLAN & RISK — *how do we execute and size it?*

| Row | Reads | How to use |
|---|---|---|
| **Plan** | `wait for GO`, or the order | **Prints only on GO.** Follows `entry_method` — default **Retest (pullback limit)** at the latched trigger bar's close, not a buy-stop. Tagged `· trig Nb ago`; a stale anchor re-latches after N bars rather than quoting fiction. |
| **Entry · SL · T1 · T2** | the levels | SL is **structural** — zone distal → recent swing low → 2.5×ATR, capped by trade type (swing 2.5× / positional 4.0×). T1/T2 are R-multiples by trade type. |
| **Qty @ x% risk** | shares | Dynamic risk (Kelly × vol × regime), ported from the Risk Allocator. |

> **The one thing to carry away:** the panel is a ladder, and the gates it prints are
> `P L V B`. Everything above III grades; III fires; IV rules; V sizes.

## 5. The 17 PA patterns — what each requires

*(On the CHART timeframe by default — `use_chart_tf` is ON, so "bar" below means a 75m bar on a 75m chart, not a day. RV = this bar's volume ÷ its 50-bar average. The two weekly-anchored patterns and HTF are suppressed on intraday. Set `use_chart_tf` OFF for confirmed-daily behaviour.)*

| # | Pattern | Tier | Fires when |
|---|---|---:|---|
| 1 | **★★ Power Play (HTF)** | +4 | ≥ **100% move in 8 weeks** AND a tight **15-bar flag** (range < 20%) AND price > 50-SMA. The rarest, strongest. |
| 2 | **Power Play (Strong Close)** | +2 | Bullish bar closing in the top quartile (`close−low > 3×(high−close)`) on RV > 1.0. |
| 3 | **VCP Breakout** | +3 | **Prior bar contracted** (ATR10 < 1.5× its 50-SMA **and** volume dry-up: `vwma(vol,5) < sma(vol,50)`) → today **breaks the 10-day high**, RV > 1.2, close in top 40% of range. |
| 4 | **Pocket Pivot** | +2 | Up close, above 50-SMA, today's volume > the **largest down-day volume of the last 10** sessions. |
| 5 | **Bullish Engulfing (gated)** | +2 | A true engulf **in a downtrend** (`close < 10-EMA < 20-EMA`) on **RV > 2.0** with prior-bar RSI(14) < 40. Quality-gated — not a naked engulf. |
| 6 | **Liq Sweep Reclaim** | +2 | Price swept **below the 50-SMA** within the last 5 bars but **reclaimed** it, closing back above on ≥ 1.5× volume. |
| 7 | **3-Bar Bull Reversal** | +2 | Three consecutive lower lows, then a close **above the highest high** of those three bars — end of the pullback. |
| 8 | **Stage-2 Launch** | +3 | A **true weekly close crossover** of the 30-WMA (this week's weekly close > 30-WMA, last week's ≤ it) on RV > 1.25, **and** the Stage-2 proxy holds (close above a *rising* 30-WMA proxy). *(v1.9 added the Stage-2 gate — mirrors Python's `"2" in stage`; stops LAU firing on a Stage-4 dead-cat cross.)* Fresh Weinstein Stage 1→2. |
| 9 | **Inside-3 (Coil)** | +2 | Three **nested inside bars** — a tightening coil. |
| 10 | **True NR7** | +1 | Today's range is the **narrowest of the last 7** bars. |
| 11 | **★ IB-NR7 Coil** | +2 | An **inside bar that is also NR7** — the Crabel compression coil (best early-inception trigger). |
| 12 | **Wyckoff Spring** | +3 | Undercut the **prior 50-bar low**, then reclaim it closing green on **low** volume (supply vacuum). |
| 13 | **Gap-Up Breakout** | +3 | Opens **above the prior high**, closes above the **20-bar locked resistance**, green, RV > 1.25. |
| 14 | **50-SMA Undercut & Reclaim** | +2 | Low sweeps **below the 50-SMA**, closes back **above** it, green, RV > 1.25 (Minervini undercut-&-rally). |
| 15 | **Hammer at 50-SMA** | +2 | Hammer within **1.5%** of the 50-SMA, closes above it, RV > 1.0. |
| 16 | **Hammer at 200-SMA** | +2 | Hammer within **2%** of the 200-SMA, closes above it, RV > 1.0. |
| 17 | **Breakout Confirmed** | +2 | Anti-algo: close > **20-bar locked resistance**, **top-quartile** close, RV > 1.25. |

*(1–11 are the original curated Golden-Matcher battery; 12–17 were added in v1.4 — the strong §4 triggers the curated 11 had omitted.)*

**Recovery battery (Mode = Recovery / Auto-recovery):** the panel swaps to the **10 capitulation-reversal / accumulation** conditions — Climax Reversal (+3), Wyckoff Spring (+3), Higher-Low / 2B (+3), Base-Breakout SOS/JAC (+3), Bull Engulf (+2), Hammer-at-support (+2), 3-Bar Reversal (+2), Pocket Pivot (+2), Volume-Dry-Up (+1), 30-WMA Reclaim (+3). *(v1.9: **Higher-Low / 2B** now requires the recent low to sit within **10% above** the prior base low — it retests the base rather than firing on any green day of a rising trend.)* RS-turning-up lives in the recovery **Quality gate** (Golden Matcher), not this battery.

**Σ tier reading:** patterns are additive bonuses. A single Tier-3/4 (VCP-BO, Stage-2 Launch, HTF) or **Σ ≥ 4** is a strong trigger. Multiple coil/reversal patterns stacking is a coiled-spring about to release. Jay's rule: *you eyeball the tier; there is no fixed "N/N" benchmark.*

## 6. The three anchored VWAPs (price memory)

- **AVWAP-Low** — anchored to the 52-week / Stage-1 absolute bottom. The institutional cost basis; strongest long-term support.
- **AVWAP-BO** — anchored to the last 40-bar-high **breakout day**. The line breakout buyers defend; a **Red-to-Green reclaim above it** is a trigger.
- **AVWAP-Gap** — anchored to the last high-volume **gap-up**. Earnings/news cost basis.

Anchor **dates** are derived from **Daily** structure (via `request.security`), so the lines are stable regardless of chart TF; the VWAP itself accumulates on the chart TF from that date. A **pinch** (all three converging within the tolerance) marks a zone where every class of holder is at breakeven — the highest-conviction entry pocket.

## 6b. LOCATION — the Institutional zone engine, S/R levels and AVWAPs (v3.0+)

> **⚠️ This section replaced the old OB / FVG / Pivot description.** In **v3.0** the
> **Order Block was REMOVED as a support source** — the Institutional Zone Engine's
> leg-base-leg zones replace it. FVGs and pivots are kept as secondary shelves.
> If you are reading an older copy of this guide, that section is wrong.

Location is the gate that stops a PA pattern from being an entry on its own. S4 draws
it from **four** independent sources, and `support_pass` is their OR.

### 1. Demand / supply ZONES — `f_detectZone` (the primary source)

A wholesale port of the **Institutional Zone Engine v4.2**, run on **Chart + Daily +
Weekly + Monthly** through one universal function (single source of truth across TFs).

| Pattern | Shape | Distal drawn from |
|---|---|---|
| **DBR** Drop-Base-Rally | demand | full formation (incl. leg-in) |
| **RBR** Rally-Base-Rally | demand | base + leg-out only |
| **RBD** Rally-Base-Drop | supply | full formation (incl. leg-in) |
| **DBD** Drop-Base-Drop | supply | base + leg-out only |

- **Leg candle** = body ≥ 0.75 × range **and** TR > `ercMult` × ATR. An *average* leg
  (0.60-0.75) is rescued by strong follow-through.
- **Base** = 1-6 small candles; 2-4 scores highest.
- **Per-TF leg-in strictness** (v3.8): `legin_ltf` **0.6** for intraday+daily,
  `legin_htf` **1.0** for weekly+monthly. A single global value was either starving the
  daily/intraday zones or letting monthly noise through.
- **Per-TF width band** (× ATR14): M 0.5-4.0 · W 0.4-3.5 · D 0.3-3.0 · 125m 0.25-2.5 ·
  75m 0.2-2.0. **If intraday zones vanish, this is the first knob to check.**
- **Structural (pivot) zones** — weaker dashed shelves from a bare swing high/low with no
  leg-base-leg. Toggle `useStructural` OFF to isolate pattern zones when debugging.
- **Controlling zones** — a new ATH/ATL print, a 50-SMA trend shift, or breaking an
  opposing controlling zone. Get 2 touches instead of 1, a thicker border, and a
  `Controlling …` label prefix. **Exclusive** — only the DZ nearest the ATH holds it.

**Lifecycle — and note it differs from an S/R level on purpose:**

| State | Trigger | Result |
|---|---|---|
| **FRESH** | formed, untouched | tradeable |
| **TESTED** | a reaction (wick pierced / closed inside, then moved out) **followed by** travel ≥ 2 × width, *or* a daily-EMA20 / level cross | **supply → kept**, still resists · **demand → greyed, kept, NOT tradeable** (v8.8 touch budget: normal 1 test, Controlling / score ≥ 75 gets 2; spent past that → deleted) |
| **VIOLATED** | close beyond the distal | deleted, faint mark |
| **AGED OUT** | calendar age by TF (M 4y · W 2y · D 6mo · 125m 4w · 75m 3w), measured from **formation** | deleted |

> **The v3.8 fix worth knowing:** the EMA/level "tested" test used the **DAILY** EMA20 for
> *every* TF, so a **weekly** zone died on a **daily** EMA cross — CoalIndia had 3 of 37
> weekly zones alive. EMA/level now applies to **daily zones only**; W/M are judged by
> travel in their **own** TF's ATR, and by violation. **Judge a zone on its own timeframe.**

### 2. Horizontal S/R LEVELS (v3.2)

Absorbed from Commander Chart Markup. Graded by touch count and **MTTWR** (multi-touch,
tested, weakening) — and the asymmetry with zones is deliberate:

> **A ZONE is fuel; an S/R LEVEL is price memory.** A zone that has been tested is
> **spent** — since v8.8 it is greyed and kept on a touch budget rather than deleted, so
> you can still *see* the level, but a spent **demand** zone no longer arms a trade
> (a spent **supply** zone does still resist). A LEVEL behaves differently: tested →
> *weaker*, violated → **flips** R↔S and stays on the chart forever.** Tests **weaken** a level,
> never strengthen it. A level tested that often is a **breakout candidate, not a
> ceiling** — which is why MTTWR levels (`sr_mttwr_n`, default **6**) are excluded from
> the S/R picker. Do not "fix" this.

### 3. Anchored VWAPs — Low / Breakout / Gap (see §6)

### 4. Volume Profile VAL / POC (v5.1, behind `en_wcl_loc`)

The **only** component of the Weinstein Context Layers integration that earned its place
(~18% of names). Wyckoff was tested and rejected as both a veto and a score input.

### How location feeds the verdict

`support_pass` = zone **OR** FVG/pivot **OR** S/R **OR** AVWAP **OR** VP. But a GO resting
**only** on the AVWAP/EMA — no zone, no S/R — is downgraded to **CAUTION — momentum/chase**
(v4.6, `_qLocWeak`). That is a momentum entry, not a pullback to support, and it is exactly
why the GM can read "No location" while S4 shows a trigger. **The Python twin
(`zone_engine.py`) deliberately excludes `near_ema`** — it fires most of the time and would
make the board over-predict 4/4.

## 6c. The VERDICT ladder — what S4 actually decides

Evaluated **in order**; the first match wins. This is the output that matters.

| # | Ruling | Fires when | What it means |
|---|---|---|---|
| 1 | **NO TRADE — Stage 3/4** | `stage_skip` | A valid TRIGGER inside an invalid CONTEXT. Applies under **manual** mode too — the stage is a fact, not a preference. |
| 2 | **TAKE IT — Recovery** | recovery path **and not** `_stage2ok` | A recovery climbs *through* overhead; thin room is expected and does not deny the trade. Buy-STOP (confirms the turn) — **overrides** `entry_method`. |
| 3 | **BREAKOUT PIVOT** | in supply **and** near ATH **and** Stage 2 | The "supply" IS the prior high. Don't buy here — arm above the band ceiling; blue sky above. **Overrides** `entry_method`. |
| 4 | **PULLBACK TO VALUE** | Stage 2 · in a demand zone · not extended · not in supply | **The house A+ location.** Follows `entry_method` (keeps the Retest default). `TAKE IT` if a reward gate clears, else `ARM — reward still thin`. |
| 5 | **CLEAR TO BREAK** | Stage 2 · a level overhead · neither reward gate clears · **not** at value | The overhead is a level to *break*, not the target. Can only ever reframe a would-be SKIP. |
| 6 | **SKIP — no room** | in supply / < 1R of room (non-recovery) | Buying into overhead supply is not a trade. |
| 7 | **TAKE IT** / **CAUTION** | a reward gate clears | CAUTION when location is weak or price is extended. |
| 8 | **SKIP — payoff too thin** | neither gate | Entry clean, reward doesn't justify the risk. |

Below a GO the ladder continues with **BREAKOUT PIVOT (arming)** · **NOT TRADEABLE**
(blocked **and** in-supply — clearing the one gate will not make this a trade) ·
**LOW QUALITY** · **ARM**.

**Which reward gate applies is decided by the TRADE TYPE, not by whichever passes**
(v6.1): `tt_swing` (ATR% > 4 / off52 > 30% / below the 200-DMA) → the **2R** bar;
positional → the **20% ROI** bar. Per the DNA these are not peers — swing is 5-8% over
8-12 weeks, positional 10-30% over 6-8 months.

> **Known structural tension, stated rather than hidden:** a positional plan targets
> `tt_t1r_pos` (5R), so ROI-to-T1 = 5 × risk%. With a 2.3% stop that is 11.5% — so the
> **20% positional rule is unreachable whenever risk% < 4%**. The two positional rules
> contradict each other by construction. Either the 5R target or the 20% gate should
> move; until then the verdict explains the conflict instead of pretending it away.

## 7. Triggers & alerts

**Two on-chart triggers:**
- **AVWAP trigger** (`S4` triangle below bar): the bar's low touches an AVWAP (within tolerance) and closes green above it (**bounce**), **or** price crosses up through AVWAP-BO (**R2G>BO**).
- **Intraday trigger** (`GO` label): on 75/125-min, price reclaims the **rising 10-EMA** *and* the **TTM squeeze fires up**.
- **Daily PA trigger** (`PA` diamond above bar): any battery pattern turned on this bar.

**Alerts (set once per Step-5 name):**
| Alert | Fires when |
|---|---|
| `S4 GO (Event+Vol+Intraday)` | a trigger fired (AVWAP or intraday) **with** volume ≥ floor |
| `S4 AVWAP trigger` | bounce / R2G>BO |
| `S4 Intraday trigger` | 10-EMA reclaim + squeeze up |
| `S4 AVWAP pinch` | anchors pinched (zone forming) |
| `S4 ANY daily PA pattern` | any battery pattern fired |
| **Dynamic `alert()`** (use "Any alert() function call") | the richest path — three self-describing runtime messages: (1) **PA fired**, naming which patterns + Σ, e.g. `S4 PA on CAPLIPOINT (Sum+5): VCP-BO, Pocket`; (2) **GO**, naming mode + leg + **zone** + RV, e.g. `S4 GO on RADICO (Bull) via AVWAP bounce @ at OB · RV 1.42 · Sum+5. Confirm the closed 75/125m bar → buy-STOP above its high.`; (3) **Σ-strengthening**, when another pattern joins while one is already live, e.g. `S4 PA strengthened on X (Sum+2 → +5): …` |

All fire **once per bar close** — this is deliberate: the closed bar *is* your confirmation. For the single most useful alert, add **"Any alert() function call"** on the script — it carries all three dynamic messages above.

---

# PART B — THE COMPLETE GM + S4 TRADING WORKFLOW

> S4 is **one layer of five**. This section is the end-to-end system, so the indicator is
> read in the place it actually occupies. The companion is
> `docs/23_Golden_Matcher_Guide.md`, which owns the upstream layers in detail.

## The two-stage doctrine — read this first

**The GM ARMS. S4 EXECUTES.** They deliberately disagree, and aligning them would be a
regression:

| | Golden Matcher | S4 |
|---|---|---|
| Says | `TRIGGER LIVE` — a PA pattern fired | `GO` — PA **and** location **and** volume **and** a strong bar |
| Fires | **early**, so you can focus | **late**, at the executable instant |
| Answers | *which names deserve attention today* | *is this the bar, and where exactly do I buy and stop* |
| Final word | no | **yes** — the chart is the last authority |

GM's job is to hand you a shortlist small enough to actually watch. S4's job is to stop
you entering on the touch. Do not collapse them.

---

## Layer 0 — QUALIFY (automatic, ~16:30 IST)

The auto-pilot runs Chartink x Screener.in through the matcher and writes the nine
`FINAL_*.csv` watchlists, each stamped with an **archetype** (Hunter -> Breakout,
EarlyBird -> Accumulation, Pullback -> Pullback, Leader -> Leader, plus the Nifty-500
catalyst scan and the three Recovery lists). `pyramid_logic` adds
`FINAL_Portfolio_Picks.csv` — ADD candidates on names you already hold.

**You do nothing here.** But know the leak: every list is intersected with
`MASTER_scan_results.csv`, a ~149-name screener.in fundamental universe. The Pullback
list loses roughly **76%** of its names to that join and EarlyBird can fall to **zero**.
If pullback supply feels thin, that is why — it is not a signal problem.

## Layer 0b — LOCATE (`pullback_finder.py`, on demand)

A trigger is, by construction, a wide-range up-bar near the recent high — so a
trigger-based board can only ever hand you **extension**. Measured on a live board:
actionable rows sat a median **1.74 ATR** above the EMA20, every one within 0.2-2.9% of
its own 20-day high, while the names filed under "Wait for Pullback" sat at **0.23 ATR**.
The board was telling you to wait on the names that were ready.

`pullback_finder.py` answers the other question — **where is value right now** — ranking
Stage-2 names on extension from the EMA20, pullback depth, volume dry-up, range
contraction and real support below price. No trigger required, no fundamental join.
Run it from Control Center -> Command, or:

```bash
python pullback_finder.py --universe nifty500 --max-ext 1.0 --top 40
```

Use it when the board is all breakouts and you want names that have actually pulled back.

## Layer 1 — TIME (the GM Trigger Board)

Every watchlist name runs through the **same** `gm_evaluate()` the single-symbol view
uses, so the board and the name page agree by construction. Two columns matter:

- **Category** — the stage-1 ARM state (`Buy Trigger Live` / `Armed Wait` /
  `Wait for Pullback` / `Invalidated`).
- **S4-GO** — the stage-2 preview: how many of S4's four gates pass *right now*
  (`4/4 GO` · `3/4 · no vol` · `2/4 · no loc` ...). **Sort by this.**

**PA recency.** An NSE session is five 75-min bars, so a pattern that fires at 10:30 is
invisible to a last-bar read by 11:45 — and this board is where you filter. The PA gate
now also accepts a pattern from the **last 3 closed bars**, always labelled:
`4/4 · PA 2b` never reads as `4/4 GO`. **Only the PA gate** may be satisfied by history —
a pattern is a *structural event*, while volume, location and bar-strength are *current
state* and stay strictly on the live bar. (The naive version — a rolling "sticky" window —
was built and reverted in v5.2 for summing Sigma across different bars.)

**Arm what you intend to watch.** Tick the **bell** column (or use Single Symbol) at the
same moment you create the TradingView alert. The board is rebuilt nightly from
watchlists that churn, so without the **Armed Register** an alert firing three days later
lands on a name with no row, no levels and no thesis. Arming snapshots the plan and keeps
the name on the board through the churn, re-evaluated live on every rebuild.

## Layer 2 — EXECUTE (this indicator)

Open the armed name on your 75m or 125m chart and read the panel **top to bottom**:

1. **Structure basis** — Stage · % off 52WH · 30WMA · 200DMA. If this reads Stage 3 or 4,
   stop: the verdict will say **NO TRADE**, and it is right.
2. **Support Zone** — which of the four location sources sits under price, and its grade.
   `DZ` / `S-R` beats `AVWAP` / `EMA20` alone.
3. **Room for Trade** — the nearest overhead. Thin room is a real objection for a bull
   continuation and **not** an objection for a recovery.
4. **Arrival · Delta** — FAST/GRIND plus the order-flow proxy. These **grade**, never gate.
5. **PA grid** — which of the 17 (Bull) / 10 (Recovery) fired, and Sigma.
6. **TRIGGER** — `P·L·V·B` (+ optional timing). All four = GO.
7. **Plan** — entry / SL / T1 / T2, latched to **the bar that fired** (v6.0), with the
   trade type and its R-targets.
8. **VERDICT** — four lines: ruling · why · the one caveat · the action. **This is the
   output.** Full ladder in section 6c.

## Layer 3 — ENTER

**The one rule: never buy the touch.** Confirmation is the mechanical fix for the single
most expensive habit — entering at the zone because it *looks* right.

1. The alert pings on a **closed** bar.
2. Read the VERDICT. If it says NO TRADE / SKIP / NOT TRADEABLE, you are done.
3. Enter per the **Plan row**, which follows your `entry_method`:
   - **Retest (default)** — buy-LIMIT at the trigger bar's close; you fill only on a
     pullback to value. Backtested better than buy-stop across every family
     (-0.02% -> +0.38% matched alpha). Caveat: the sim cannot model the false-breakout
     whipsaw a buy-stop avoids, so treat that edge as optimistic.
   - **Buy-stop** — above the trigger bar's **high**. House doctrine; avoids the false
     breakout, at a higher entry.
   - Two rulings **deliberately override** this and say so on the panel: **Recovery**
     (you confirm the turn, never buy the touch of a falling name) and **Blue-sky**
     (a limit would fill you inside resistance). **Pullback-to-value does not** — it
     keeps your retest default, which is the entire point of it.
4. Size at **0.25% risk** (new entries) off the plan's SL. Place the **GTT** for the stop
   *after* the fill — never a resting order at the level.

## Layer 4 — MANAGE (Risk Shield / Pyramid)

Once you are filled, S4's job is over.

- **TSL** = the catalyst-aware Chandelier from `risk_common.py` (POS 4.5 · WYC 3.5 ·
  REV 2.5 · SWG 1.5, +0.5 in a bear regime; swing runs a 14-bar clock, positional 22).
  It only ever tightens. `gtt_auto_shield --trail` pushes it to Dhan at 15:45.
- **Rec SL** on the Risk Shield tile is *not* a trail — it is `LTP - ATR x mult`, a sizing
  suggestion that moves **down** with price. When TSL > Rec SL the trail has taken over.
- **Pyramid/Trim** rates each holding ADD / HOLD / REDUCE / TRIM / EXIT; ADDs re-enter the
  board as their own archetype and are timed exactly like a new name.
- `exit_scan` 16:00 and `journal_sync` 16:30 close the loop.

---

## The daily cadence, condensed

| When | Do |
|---|---|
| **Weekend** | Run the pullback finder. Review the board's Wait-for-Pullback names. Build the watch shortlist and arm it. |
| **Pre-open** | Rebuild the board. Read overnight invalidations. |
| **10:30 · 11:20 · 11:45 · 13:00 · 13:25 · 14:15** | The board auto-rebuilds on 75m/125m closes. Glance at S4-GO; act on **alerts**, not on the touch. |
| **On an alert** | Open S4 -> read the VERDICT -> enter per the Plan row -> GTT the stop. |
| **15:45 / 16:00 / 16:30** | `gtt_trail` · `exit_scan` · `journal_sync` run themselves. |
| **After any S4 recompile** | **Delete and re-create every GO alert.** Non-negotiable. |


## Quality ladder (what to prioritise when several names ping)

| Grade | Looks like |
|---|---|
| **A+** | Verdict **TAKE IT — PULLBACK TO VALUE**, a fresh **demand zone** under price, Sigma >= 4, RV >= 1.25, arrival not GRIND. The house setup. |
| **A** | Verdict **TAKE IT** with `DZ` or `S-R` location, both reward gates comfortable, clean bar. |
| **A-** | **BREAKOUT PIVOT** on a Stage-2 leader at its high — but you buy **above the band**, never inside it. |
| **B** | **CLEAR TO BREAK** — clean trigger, nearby overhead, Stage 2. Real target is the R-objective, not the level. |
| **B-** | GO but location is **AVWAP/EMA only** -> panel says CAUTION — momentum/chase. Size down or wait for a zone. |
| **Wait** | `ARM` / `3/4` — one gate short. Coils (NR7 / Inside-3) are **compression, not a trigger**. |
| **Skip** | **SKIP — no room** · **SKIP — payoff too thin** · **LOW QUALITY** (GRIND + Delta-negative). |
| **Never** | **NO TRADE — Stage 3/4** and **NOT TRADEABLE**. The second one means clearing the blocking gate alone still would not make it a trade. |

## Relationship to the rest of the ecosystem (zero-drift map)

| Surface | Role | Shares with S4 |
|---|---|---|
| **Golden Matcher** (Web Commander page) | Upstream decision tree + Trigger Board. **Arms**; S4 executes. | `pa_patterns.py` batteries (byte-identical formulas), `s4go_status` gate mirror |
| **`pa_patterns.py`** | Canonical Python battery — Bull 17 / Recovery 10 | The formulas. A port of Dashboard v67.4.12 |
| **`zone_engine.py`** | Python port of this file's zone engine + S/R + AVWAP | Location, behind `GM_USE_IZE_ZONES` (still **False** — A/B it before flipping) |
| **`gm_armed.py`** | The Armed Register — survives watchlist churn | Nothing computational; it holds the plan S4 produced |
| **Dashboard v67.4.12** | Canonical source of the PA formulas + the trade dashboard | The 17 patterns |
| **`risk_common.py`** | Chandelier trail after entry | Takes over once filled |

> **Pine <-> Python parity caveat, stated precisely:** the 17 bull PA formulas are
> **byte-identical** between `f_daily_pa` and `pa_patterns.detect_bull_patterns`. When the
> two surfaces disagree it is (a) **mode/path** — S4's Auto vs the GM's resolved path,
> (b) **feed** — TV vs Dhan volume on a marginal RV test, or (c) **staleness** — the board
> snapshot vs the live chart. It is *not* a battery drift. Diff the **evaluated bar** before
> diffing formulas: the one real parity bug (v4.1) was an offset, and it was in the
> **Recovery** battery, which had never been diffed.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **"Compiled code contains too many tokens"** | You are at the ceiling. Every addition needs a paired removal — see the two operational rules at the top. Cost is per **operation**, not per character. |
| **A GO alert never fired even though the panel showed GO** | The alert was **destroyed by a recompile** — they bind to the `pine_id`. Delete and re-create every GO alert after every compile. |
| `GO` never appears on strong triggers | Location: price is not at a zone/level. Check the **Support Zone** row. If intraday zones are missing entirely, the per-TF **width band** (75m 0.2-2.0 x ATR) is the first knob. |
| **Intraday zones vanish / too few daily zones** | Per-TF **leg-in** strictness — `legin_ltf` (0.6) for intraday+daily, `legin_htf` (1.0) for W/M. A single global value starves one end. |
| **A weekly zone disappeared for no reason** | Pre-v3.8 behaviour: the tested EMA/level cross used the **daily** EMA20 for every TF. Judge a zone on **its own** timeframe. Fixed in v3.8. |
| **A heavily-tested level is not offered as support** | Working as designed. MTTWR levels are excluded — tests **weaken** a level; one tested that often is a **breakout candidate, not a ceiling**. |
| **Verdict says NO TRADE but the chart looks fine** | Stage 3 or 4. `stage_skip` outranks everything and applies under manual mode too. Trust it, or accept it is a counter-trend trade at half size. |
| **Recovery mode gives "TAKE IT" on a name that looks like a bull pullback** | Fixed in **v7.0** — a repaired Stage-2 name now falls through to the bull-frame rulings, and the panel says the mode is contradicted. If you are on an older build, set Mode manually. |
| **Panel gives two different entry prices** | Fixed across v5.2/v6.1/v6.3. Only **Recovery** and **Blue-sky** override `entry_method`, and they say so explicitly. |
| **"Retest" filled at market** | Correct and now stated: on the trigger bar itself the limit *is* that bar's close. The panel distinguishes a true retest from a market fill, and names where a real pullback sits. |
| **Board says `4/4 GO` but S4 shows nothing** | Check (1) **mode/path** — set S4's Mode to match the board's Path; (2) **PA age** — `4/4 · PA 2b` means the pattern fired two bars ago, so the live bar is legitimately quiet; (3) board **snapshot staleness**. |
| PA rows all `-` on a fresh add | Give `request.security` a moment; confirm the master detect toggle is on. |
| Panel stops after a row | A stale persisted table from an older build — reload the current file into a **fresh** chart. |
| Numbers print like `1.2` when the true value is `0.94` | Pine format strings `"#.1"` / `"#.2"` are **broken** (they round to int and print a literal decimal). Use `"0.00"`. Fixed in v2.9.1; grep for `"#.` if you see it elsewhere. |

---

*Guide rewritten 31 July 2026 from `Section4_Entry_Trigger_v5.9.pine` (in-file title
**v7.1 — Pullback Ruling**). S4 is the execution layer of the GM + S4 system; the upstream
layers are documented in `docs/23_Golden_Matcher_Guide.md`, and PART B above is the
end-to-end workflow across both.*
