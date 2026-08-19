# Golden Matcher — the GM + S4 Trading System — User & Trading Guide

> **Module Role:** The **upstream half of the GM + S4 system**. It has grown two
> surfaces that share one engine:
>
> | Surface | Answers | Use it |
> |---|---|---|
> | **Trigger Board** | *Which of my ~50 qualified names deserve attention right now?* | All day — it rebuilds on every 75m/125m bar close |
> | **Single Symbol** | *Is THIS name a buy, and if not, what exactly am I waiting for?* | When the board surfaces something |
>
> Both call the **same** `gm_evaluate()`, so they agree by construction. The board is the
> filter; the single view is the read; **S4 on TradingView is the trigger and the final
> word.** For the complete end-to-end workflow across both halves, see **PART B of
> `docs/22_Section4_Entry_Trigger_Guide.md`**.
>
> Historically (and still, for the single view) it is a **read-only** single-symbol decision funnel that renders the entire Golden Matcher checklist for **one stock at a time**. It answers one question — *"Is this name a buy right now, and if not, exactly what am I waiting for?"* — by ordering every signal into a **6-step gated decision path** (CONTEXT → QUALITY → SETUP → LOCATION → TRIGGER → EXECUTE), for **both a Bull path and a Recovery path**, ending in a **tick-as-you-go execution checklist**.
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
> - **Location** — `pa_patterns.detect_support_zones_dw()` (FVG / pivot, Daily+Weekly) with fresh/tested/violated lifecycle. **`zone_engine.py`** is the full Python port of S4's Institutional leg-base-leg zone engine + S/R levels + AVWAPs; it sits behind the flag **`GM_USE_IZE_ZONES` (default False)** — A/B it against S4 before flipping. `near_ema` is deliberately **excluded** from the Python side: it fires most of the time and would make the board over-predict `4/4 GO`. *(Order Blocks were removed as a support source in S4 v3.0 — zones replace them.)*
> - **Inherited qualification** — the watchlists QUALIFY; the board TIMES. A name carries the **archetype** of every list it appears in, and Context/Quality stop being re-screened. See §4b.
> - **fresh vs tested** (a mitigated OB/FVG is excluded), so the LOCATION step and the guided checklist reference the *same fresh* demand zones the chart draws. Automates Guided-Execution Steps 1-2.
> - **Archetype handoff (5 Aug 2026).** Where the GM knows something S4 cannot recover from
>   price — which screen qualified a name — it **hands the answer over** rather than letting
>   S4 guess. Two lists now cross that boundary: Recovery and Pullback. This is the same
>   pattern as reading v67's values via `input.source`: the surface that computed it owns it,
>   and everyone else reads. Guessing is what produced the drift class this guide keeps
>   documenting.
> - **Bull/Recovery path parity** — the GM resolves the path from the engines (bull catalyst vs recovery signal + RFF). The **Section 4 Pine v2.3** now mirrors this structurally in its `Auto` mode (Bull above the 200-DMA; Recovery = beaten-down below it), so the two surfaces agree on which playbook applies (the residual gap is an early recovery that already reclaimed the 200-DMA — Pine can't see RFF; use the Pine `Mode` override).
> - The Golden Matcher **identifies and sequences**; it **never triggers**. The trigger is always a **closed 75/125-min bar on TradingView**.

---

## Version history

| Milestone | Change |
|---|---|
| **31 Jul 2026 — Armed Register** | **The board gained memory.** `gm_armed.py` + `gm_armed.json`. The board is a snapshot rebuilt from watchlists that churn nightly, so an alert set Monday and firing Thursday landed on a name with **no row, no levels, no thesis**. Arming snapshots the plan (trigger/entry/SL/T1/verdict/Sigma/archetypes/path) and injects the name into the watchlist union as an **11th source**, carrying the archetypes it had *when armed* — so it keeps its original thesis and path plus an `Armed` badge, and is re-evaluated live on every rebuild. Arm from the **bell checkbox in the grid** (both render paths) or from Single Symbol. 45-day expiry, applied on every read. Disarm keeps a `CANCELLED` record — "I armed this and dropped it" is information. |
| **9 Aug 2026 — ROOM measured to the real obstacle** | The board advertised HINDALCO at `R:R 1.9, T1 1163.5` on the same bar S4 called **NO ROOM**. `R:R` measured to the PLAN's T1 — a 2R projection or the 52-week high — and never asked what stands between here and there, so a big number meant *the target is far*, not *the path is open*: ULTRACEMCO read 11.6 with a pivot high 1.1% overhead. LOCATION was ported to `zone_engine` in July; ROOM never was. `zone_engine.overhead_room()` now ports S4's own six-source scan — supply band, supply-zone proximal, nearest non-MTTWR S/R, daily and weekly flipped pivots, last pivot high — plus a SECOND obstacle only beyond `max(0.5 ATR, 0.2%)` so one shelf reported twice cannot pose as two targets. New **Room** column (`0.05R · SZ·D` / `clear`), and **R:R now measures to the first obstacle when one exists**. On the 13 live GOs: HINDALCO 1.9 → **0.05**, ULTRACEMCO 11.6 → **0.37**; only MPHASIS (1.39) and GLENMARK (1.01) cleared 1R, and three read `clear`. **"No obstacle found" and "could not compute" are separate** — a failure leaves the cell BLANK and never reads as a green light. |
| **9 Aug 2026 — stage aligned across all three surfaces** | CRISIL read Stage 1 here and on the Dashboard, Stage 3 on S4. S4 was right. GM ran a hysteresis state machine plus two `tDir` overrides, so a name trading well above a DECLINING 30-week average never left Stage 1 — MPHASIS sat there with its 30-WMA falling 62.9 points. Now the stateless 2×2, with the slope taken as a RAW 4-bar change (was a per-bar rate over 6, making the flat band 6× wider than S4's). **19 of 56 board names re-staged; `stage_ok` 48 → 41.** Full table in the S4 guide §0b. |
| **9 Aug 2026 — the stub bar that zeroed the intraday boards** | 75m and 125m returned **ZERO** S4-GOs while Daily returned 12. Not a gate problem: Dhan publishes a phantom bar stamped 15:30 after the close (`O=H=L=C`, volume 0), which resamples into a whole extra 75m/125m bar. Any rebuild after ~16:45 read it as the last CLOSED bar — RV 0 on every name, so the volume gate failed everywhere. The damage was never only volume: a zero-range doji also feeds the PA battery and the bar-strength test. `dhan_ohlcv` now drops TRAILING zero-volume stub bars; `no vol` blockers fell 24 → 5. |
| **9 Aug 2026 — "near a zone" scales with the zone** | `TOUCH_TOL` was a flat 1.5% of price on every timeframe, so a monthly zone could essentially never be near — the nearest unspent monthly demand zone sits a median **30.6%** below price (weekly 20.1%, daily 6.2%), and the HTF-nesting term degraded to "Daily or nothing". The settling measurement: median daily zone width is 2.9% and half of that is 1.45% — **the flat 1.5% constant already WAS a width-proportional rule, only ever calibrated for Daily.** Now `0.5 × the zone's own width`: Daily and Weekly provably unchanged, Monthly at-support 2 → 5. ATR-scaled alternatives rejected — 1.0× TF ATR nearly doubled the PRIMARY location gate. |
| **9 Aug 2026 — POS targets 2R/4R (was 5R/10R)** | At 5R, T1 was reached in **2%** of POS trades (5 of 203 over 24 months), so the partial, the move to breakeven and the trail-from-there NEVER engaged and every trade carried full initial risk for its whole life. Sweep over T1_R with the shipped 25/25 partials, 60/40 chronological OOS split: 1.5R best in-sample (+0.027R), **2.0R best out-of-sample (+0.036R)** — statistically indistinguishable, and 2.0R matches the discipline Jay already trades by. The MEDIAN is flat across the entire grid, so booking earlier does **not** shorten the right tail. Read the absolute numbers honestly: every cell is NEGATIVE in R. This fixes the exit mechanic; it does not make the book profitable. |
| **9 Aug 2026 — Active Exits: off-policy flags + leg ordering** | Changing the screener does not move an order already resting at Dhan, so a book placed under 5R/10R keeps unreachable targets forever. Each target now carries **⚠ vs 2.0R** when it sits >25% beyond policy, reading `POS_T1_R`/`POS_T2_R` live so the page cannot drift from the screener. Legs are also **sorted by target price** — `orders` came in whatever order Dhan returned while the T1/T2 labels and the policy flag both key off `o_idx`, so a reversed response would mislabel the nearer target AND compare it to the wrong policy R, two wrong readings agreeing with each other. |
| **6 Aug 2026 — role-vs-location tag** | The S4-GO cell now appends `· ⚠role` when price is **in a demand zone** and the only pattern behind it is an **IGNITION** one (a volume thrust, a gap, a strong close). Those two describe opposite things — expansion *away* from value versus absorption *at* value — yet the pair still counts 4/4. Measured on the live 75m board: **3 of 7 armed names** were IGNITION-only in a zone (TITAN, UNOMINDA, HINDALCO). It **never changes the gate count**: n=7 is a story, not a rate, and a check that can only REMOVE signals has to clear a Σ-matched bar first — the pure-pattern combos went the other way (built, then measured, then discarded). Roles come from `pa_combos.ROLE`, so the board and S4 read **one** definition. The in-zone test was also hoisted out of `_pullback_ctx` into `_in_demand_zone()` — a second private copy of that test is how the drift class starts. |
| **6 Aug 2026 — Pocket Pivot classification (checked, left alone)** | Pocket Pivot sits in `PB_CONTRACTION`, which relaxes the volume floor — and our detector never tests for a base, so it *can* fire extended. Measured: **5 of 6** live pocket pivots fired **below** the 20-bar high, and the one that did not co-fired an expansion pattern, which cancels pullback context anyway. Only 2 of 6 had it as the sole contraction. No leak, no change. If you ever want it to mean what Minervini means, the fix is a base-width condition **on the detector**, not a change to the PB set. |
| **5 Aug 2026 — playbook split (the breakout/pullback clash)** | *"All the triggers are breakout trades, which are extended."* A breakout must expand on heavy volume and close strong; a pullback enters on volume DRY-UP with a bar that only holds the zone. One gate cannot be neutral between them. The board and S4 both now branch on the **archetype the watchlist already assigned** rather than inferring it from the pattern mix — `s4_pullback_list()` feeds S4's `Auto: GM Pullback list`, and `_pullback_ctx()` takes the same branch on the board. The inference had a real hole: a reversal bar off a demand zone that CLOSES STRONG fires Strong-Close, which counts as *expansion*, so the textbook pullback entry disqualified itself and was then judged on a breakout's volume floor. Live result: **20 pullback GOs vs 21 breakout**, against 1 pullback the morning before. |
| **5 Aug 2026 — S4-GO stage veto** | The S4-GO column computed only the four mechanical gates and never looked at stage, while S4's chart vetoes Stage 3/4 outright. So the board previewed `4/4 GO` on names the chart calls NO TRADE — and because the column sorts on that number, they floated to the TOP. Stage-blocked rows now read `⛔ Stage 3 · gates 2/4`: the count still shows, but it sorts below every live one. First live rebuild caught **45 rows across 15 names**, four of them Stage 4 sitting at 3-of-4 gates. |
| **5 Aug 2026 — knife-edge (marginal) patterns** | NAM-INDIA read Σ6 on the GM and Σ2 on the S4 panel for the SAME 75m bar. Not a logic bug: Dhan closed it at 1210.4 (76.4% up the bar's range), TradingView at 1210.0 (73.2%), and three patterns sat exactly on their thresholds. Proven by swapping the OHLCV — same code, Σ6 → Σ2. `pa_patterns.marginal_patterns()` re-runs the whole battery with the last bar's close and volume nudged and reports which patterns change their mind; the board tags them `N⚖`. **The two surfaces read different feeds by design**, so the fix is not to chase agreement but to mark which points are a coin-flip. |
| **5 Aug 2026 — forward signal log** | `gm_signal_log.py` — append-only, written the moment a signal fires, never edited after. **Every board row, not just the GOs**, so the later read can ask whether the gate DISCRIMINATES; that comparison is impossible if only GOs are kept. Deduped per (date, TF, symbol, gate-bucket), so bar-close rebuilds record state CHANGES rather than rebuild frequency. Outcomes are scored in **R** (`mfe_r` / `mae_r` / `reached_2r`): `hit_first` resolves against each row's own T1, and 13 of the first 57 rows carried a T1 more than 25% away, so wide-T1 names were structurally incapable of logging a win — a bias that sorts with playbook. |
| **5 Aug 2026 — allocation cap** | The board had **no** max-allocation setting while S4 did, so it would size a position at ~10× what S4 showed. New `Max ₹/trade` (persisted as `max_alloc`), honoured by the Single-Symbol sizer and by pyramid ADDs, where it **outranks the 50%-of-held floor** — that floor is a convenience ("don't buy 2 shares"), the cap is money the trader has said will not go into one name. When the cap binds, the sizer prints the ACTUAL risk taken rather than leaving a misleading risk% label above it. |
| **5 Aug 2026 — zone engine parity** | `zone_engine.py` tracks S4 v7.5–v7.8: canonical per-TF pivot lengths (M 1 / W 5 / D 2 / intraday 2), closed-bar pivot confirmation, supply/demand overlap resolution, and the **rejection-region** pivot shelf. Measured over 55 board names: monthly median zone width **8.7% → 4.9%**, weekly 5.5% → 3.9%, and **ZERO `at_support` flips** — tighter geometry at no cost to the location gate. NOTE the closed-confirm rule is scoped to the raw daily/intraday frames; the W/M frames already arrive confirmed via `_confirmed_*_ohlcv`, so applying it there would delay every monthly zone by a month for no protection. |
| **5 Aug 2026 — Daily board window** | A third TF-locked pop-out (`?view=gm_board_maximized&tf=Daily`) beside 75m and 125m. `_gm_bar_close_times()` had no Daily case and fell through to the **75m** list, so a Daily board would have rebuilt five times a session for an identical answer — a Daily read takes the last CLOSED daily bar and that does not move intraday. Daily now returns `[(15,30)]`: one rebuild, after the close. |
| **31 Jul 2026 — PA recency** | An NSE session is five 75-min bars, so a pattern firing at 10:30 was invisible to the board by 11:45 — and the board is where you filter. The S4-GO **PA gate** now also accepts a pattern from the **last 3 closed bars**, always labelled (`4/4 · PA 2b` never reads as `4/4 GO`). **Only** the PA gate: volume, location and bar-strength stay strictly on the live bar. Implemented by re-running the *same* battery on `df.iloc[:-k]` — a snapshot of one real bar, **not** a rolling sticky window (that version was built and reverted in S4 v5.2 for summing Sigma across different bars). |
| **31 Jul 2026 — Pullback Finder** | `pullback_finder.py` — a sibling surface answering **where is value**, because a trigger-based board is breakout-biased *by construction*. Measured: actionable rows sat a median **1.74 ATR** above the EMA20 while "Wait for Pullback" names sat at **0.23 ATR**. Ranks Stage-2 names on extension / depth / volume dry-up / contraction / real support, over the **full Nifty 500 and without** the ~149-name screener.in fundamental join that costs the Chartink pullback list ~76% of its names. First run: **76 candidates vs 6** from the watchlists. |
| **30 Jul 2026 — Pyramid ADDs + cadence** | Holdings that `pyramid_logic` rates **ADD** enter the board as their own archetype (`FINAL_Portfolio_Picks.csv`), timed by the unchanged engine — the two-stage doctrine applied to adds, with a correlation gate surfaced (never hidden). **75m+125m bar-close auto-refresh** persisted to `gm_settings`; per-window `?tf=` override; page persistence via `?p=`. |
| **14 Jul 2026 — P0/P1 hardening** | ~20 silent-failure paths closed. Error-dict guard (a phantom "NOT A RECOVERY CONTEXT" off an `{"_error"}` dict), NaN-safe `_g()`, `EMA20_RECLAIM_BAND_PCT` wired to 8.0 (it was dead), `built_tf` persisted so the staleness guard survives restarts, `STRUCTURAL_*_ARCHETYPES` constants (rename-drift killed), **`dhan_marketfeed` rewritten — it had never worked**. NEW `gm_log.py` -> `logs/gm_errors.log`; board build failures **counted and rendered**; `LAST_UNION_ISSUES` surfaces unreadable/empty watchlist CSVs — which immediately caught a real one (header-only Hunter + Recovery-Climax files). Atomic writes for the board cache / RRG flags / settings. |
| **13 Jul 2026 — board-vs-single drift closed** | Three successive real causes, each measured: (1) `.NS` suffix not stripped in `resolve_archetypes` -> inheritance silently off on Single Symbol only; (2) a second `.NS` leak into `gm_load_intraday` -> daily PA vs the board's 75m PA; (3) a **data-vintage split** — per-symbol Refresh made Single fresher than the board snapshot. Fixes: one `_canon_key` on both union keys *and* lookups, canonicalization at the top of `gm_evaluate`, one shared Refresh, and **`gm_evaluate()` extracted as the SINGLE evaluator both surfaces call** — the categories now agree by construction, not by coincidence. |
| **12 Jul 2026 — P1 INHERITED QUALIFICATION** | **The structural fix.** The board was re-qualifying (hard Context+Quality via the screeners) what each source watchlist had already qualified — so only the Nifty-500 catalyst scan produced actionable output, while the *rigorous* Chartink+Screener lists dead-ended at "no catalyst" (bull) or "SKIP · weak fundamentals" (recovery, because fast-mode RFF reads INSUFFICIENT). Doctrine: **the watchlists QUALIFY; the board TIMES.** Sources became the per-strategy lists so every name inherits its **archetype**; `FINAL_WATCHLIST` demoted to a **star** top-conviction badge; fundamentals became a ranking overlay, never a block; Category became pure timing state. A **still-valid break-down guard** (Stage 3/4, or below the 30WMA) replaces the re-screen. |
| **12 Jul 2026 — Trigger Board** | `gm_trigger_board.py` — the batch surface. Runs every watchlist name through the same engine, one row each, with editable RRG flags persisted to `gm_rrg_flags.json`. |
| **16 Jul 2026 — S4-GO preview** | `s4go_status()` mirrors S4's stage-2 gate into a **gates-passed closeness score** (`4/4 GO` / `3/4 · no vol` / ...), shared by the board column *and* the Single Symbol chip so they cannot drift. Lets you rank near-triggers without opening each name on TradingView. |
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

## 4b. THE TRIGGER BOARD — the surface you live in

The Single Symbol view answers *is this one a buy*. The board answers *which of ~50 should
I even look at*, and it is where the day is actually spent.

### The doctrine — inherited qualification

**The watchlists QUALIFY. The board TIMES.** Before this (P1, 12-Jul), the board
re-screened Context and Quality with the live screeners — re-doing work the Chartink +
Screener.in funnel had already done overnight. The result was perverse: only the loose
Nifty-500 catalyst scan produced actionable rows, while the *rigorous* lists dead-ended at
"no catalyst" or "SKIP · weak fundamentals".

Now every name carries the **archetype** of each list it appears in, and:

| Source list | Archetype | Path |
|---|---|---|
| `FINAL_Hunter_Picks.csv` | Breakout | bull |
| `FINAL_EarlyBird_Picks.csv` | Accumulation | bull |
| `FINAL_Pullback_Picks.csv` | Pullback | bull |
| `FINAL_Leader_Picks.csv` | Leader | bull |
| `FINAL_CATALYST_WATCHLIST.csv` | Catalyst-Scan | bull |
| `FINAL_Recovery_RSLeaders.csv` | Recovery-RS | recovery |
| `FINAL_Recovery_ClimaxBounce.csv` | Recovery-Climax | recovery |
| `FINAL_Recovery_EarlyBirds.csv` | Recovery-Early | recovery |
| `FINAL_RECOVERY_CATALYST_WATCHLIST.csv` | Rec-Catalyst-Scan | recovery |
| `FINAL_Portfolio_Picks.csv` (pyramid ADDs) | Pyramid | bull |
| **the Armed Register** | **Armed** + its original archetypes | from the record |

`FINAL_WATCHLIST.csv` is **not** an archetype source — it is the top-25-by-Combined_Score
union, surfaced only as a **star** badge.

Consequences worth internalising:
- **Fundamentals are a ranking overlay, never a block.** This is what unblocked the
  Recovery path, whose fast-mode RFF reads INSUFFICIENT.
- **Setup = the inherited archetype.** No live catalyst is required. The exception:
  a **Catalyst-Scan-ONLY** name (no structural archetype) *does* need a live catalyst or a
  fired PA, else it reads `WATCHLIST · catalyst expired` — its thesis was a time-localized
  event, and events expire.
- **The break-down guard replaces the re-screen.** Stage 3/4, or price below the 30WMA
  (recovery: Stage 4 or >50% off-high) -> **INVALIDATED**. Missing data never invalidates —
  only an *observed* break-down does.

### The columns that decide

| Column | Read it as |
|---|---|
| **Category** | Stage-1 ARM state: `Buy Trigger Live` / `Armed Wait` / `Wait for Pullback` / `Invalidated` / `Watchlist`. Pure **timing**, no quality. |
| **S4-GO** | Stage-2 preview — how many of S4's four gates pass now. **Sort by this.** Full grammar below. |
| **Archetype** | The inherited thesis. Multi-archetype names show all. |
| **Overall** | 0-100 opportunity score. Independent of category and path. |
| **Room** | Distance to the **first obstacle overhead**, in R — `clear`, or `0.22R · S/R·D`, or blank. Blank means **unknown**, never clear. |
| **bell / Armed** | Armed checkbox, and the age + trigger level as armed. |
| **Pos** | For Pyramid rows: what you already hold and the add's plan. |
| **Loc / Entry / SL / T1 / R:R** | The live plan, recomputed this rebuild. |

#### S4-GO — the complete grammar (`gm_trigger_board.s4go_status`)

This column is the single most-read cell on the board and it carries **seven** kinds of
suffix. They are not interchangeable and two of them look superficially alike, so read
the glyph, not the letter.

**The stem** — the gate count, which is what the column sorts on (descending):

| Stem | Meaning |
|---|---|
| `4/4 GO` | All four gates align **on the live bar** |
| `4/4 · PA Nb` | The other three are true now; the pattern fired **N bars ago** (≤3). Still actionable — but the entry anchors to the **bar that fired**, which is what S4's v6.0 latch does |
| `3/4 · no vol` | Armed, at a location, clean bar — waiting on volume |
| `3/4 · no PA` | Location + volume + bar, no pattern |
| `2/4 · no loc` | Needs a pullback to a location |
| `1/4 · no PA` | — |
| `⛔ Stage N · gates n/4` | **Stage 3 or 4.** Sorts *below* every live count. The gates may well all be true — a topping chart can fire a pattern at a location on volume — but the stage is upstream of all four. Parity with S4's `stage_skip` |
| `n/a` | No usable read: neither `relvol` nor `bar_ok` present. "No data", not "not attempted" |

**The four gates** (`s4go_status`, lines ~1000-1018): `sigma_pa > 0` · `support.at_support`
· `relvol ≥ RV_FLOOR` · `bar_ok`. An **unknown** `bar_ok` counts as PASS — the board never
penalises a missing read.

**The suffixes** — every one of these is **display-only and never changes the gate count**:

| Tag | Name | Read it as |
|---|---|---|
| `· PB` | Pullback context | The **relaxed** gate applied: volume floor dropped to `PB_RV_FLOOR` (0.5) and the bar test became *held the zone* instead of *closed strong*. Fires only when a CONTRACTION pattern fired with no expansion pattern **and** price is inside a demand zone. This is the setup you are hunting; PB 4/4s sort above breakout 4/4s |
| `· ↑D` `· ↑W` `· ↑M` | **HTF nesting** — up-arrow | **POSITIVE.** Price is held by a demand zone on a timeframe **above** the tab you are looking at (D 1 · W 2 · M 3). Only appears when the location gate already passed, and only for TFs strictly higher than the board tab — so a Daily zone shows on the 75m and 125m tabs and disappears on the Daily tab, where it is native |
| `· ⧖D` | **Daily fallback** — hourglass | **A FAULT.** The intraday read failed and the PA behind this verdict came from the **daily** battery while the row still wears the intraday label. Ignore its PA verdict and rebuild. Distinct from `↑D` in every way except the letter |
| `· N⚖` | Knife-edge | N fired patterns sit **on their threshold**. They flip on a difference smaller than the routine Dhan-vs-TradingView gap (NAM-INDIA: Σ6 here, Σ2 on the chart, same bar). A marginal Σ is not conviction |
| `· ⚠role` | Role mismatch | The fired battery is **IGNITION-only** (expansion away from value) while price sits **inside a demand zone** (absorption at value). Both arithmetically true of one bar, describing opposite things. Measured 3 of 7 armed names on the live 75m board; n=7 is a story, not a rate, so it tags and never gates |
| `· ⚠unval` | **Unvalidated book** | On every **Recovery**-path row. The recovery side has no valid backtest: the only run that completed used a 30-day forward window on setups designed for 90-180 days, and the one post-fix attempt died partway. ~22% of the board. Tradeable on your own read — it is not a measured edge. Controlled by `gm_trigger_board.RECOVERY_UNVALIDATED`; **delete the tag when the re-baseline reports** |

> **`↑D` is not `⧖D`.** The up-arrow is a strength term; the hourglass is a data fault.
> To check a whole tab at once, count `⧖` in `gm_board_cache_<tf>.csv` — zero is the
> expected reading.

**Location here is the GM's twin of S4's, not S4's.** `at_support` merges the IZE zone
engine, the OB/FVG/pivot proxy, `near_sr` and `near_avwap`; S4 on the chart uses its own
zone engine and is the plan of record. Treat a board `4/4 GO` as *arming*, and expect the
occasional disagreement — when it happens the chart wins.

### Refresh cadence

Set **Live = `75m+125m bar-close`** (now the default, persisted). The board then rebuilds
once per NSE session bar — **10:30 · 11:20 · 11:45 · 13:00 · 13:25 · 14:15 · 15:30**
(+75s settle). This is the fix for the forming-bar fade: a board built mid-bar shows PA
that evaporates by the close, so it read `Buy Trigger Live` while the single view said
`catalyst expired`.

Two buttons, **press one**:
- **Rebuild board** — reuses cached data. Fast. The right button after changing the
  Trigger-TF or the X-Ray toggle.
- **Fetch fresh data + rebuild** — invalidates the universe **and rebuilds itself**.
  Pressing both just rebuilds twice on identical data.

## 4b-i. Board defaults, and what they hide (19 Aug 2026)

The Trigger Board now opens **filtered and sorted**, and both defaults live in
`_board_apply_filters()` — the one definition the streaming grid, the static editor **and
the CSV download** all share, so they cannot disagree about what you are looking at.

| Default | Behaviour | Turn it off |
|---|---|---|
| **Sort: Overall descending** | Was `sort_values("Symbol")` — an alphabetical re-sort that silently discarded the Overall ranking the board had already applied upstream, which is why the grid always opened in name order. Symbol now breaks ties so the order is stable between rebuilds. | click any other column header |
| **Filter: all gates (4/4) only** | Keeps only rows whose `S4-GO` **starts with** `4/4`. The header checkbox states how many rows it is hiding, so an empty-looking board is never mistaken for a failed build. | untick **"All gates (4/4) only"** |

**Why the filter matches `4/4` and not `GO`.** `s4go_status` writes `4/4 GO` only when the
PA fired on the **live** bar; a few bars old it writes `4/4 · PA 3b`, with no "GO" in the
string. A `GO` match therefore hid names where all four gates pass but the pattern is not
fresh — **CHOLAFIN was exactly that on 18-Aug** (`4/4 · PA 3b · PB · ↑W`) and was worth a
full review. Measured on the live 75m cache the `GO` match kept **4 of 49**; `4/4` keeps
**10**. The match is anchored to the START of the string on purpose: the upstream vetoes
render as `⛔ Stage 3 · gates 4/4`, which *contain* `4/4`, and `startswith` keeps them out.

---

## 4b-ii. The RRG column and the `· RRG·` tag (19 Aug 2026)

A row tagged **`· RRG·`** is one whose RRG trajectory is **not** on the tradeable
whitelist. **It is display only — it never vetoes, and it never changes the gate count.**

The board computes it itself rather than reading a CSV column, and that detail matters:
only `FINAL_CATALYST_WATCHLIST.csv` carries `RRG_Tradeable`. `FINAL_GOLDEN_MATCHER.csv` —
**49 of 51 board rows** — does not, so a CSV-only gate would have failed open on ~96% of
the board while looking shipped. `gm_trigger_board.rrg_tradeable_live()` derives it from
the daily frame the board already holds, using the same calibrated engine and the same
whitelist as v67 and S4.

> **A bug worth remembering from that build:** the first version returned `None` for every
> symbol. The stock's weekly bars came from `_confirmed_weekly_ohlcv` while the benchmark
> came from a native `1wk` fetch — the two anchor differently, so the inner join dropped
> every row and the gate failed open *silently*. Both legs now use the same resampler.
> **If you ever add a weekly comparison, resample both sides the same way or verify the
> join is non-empty.**

`RRG_GATE = False` in `gm_trigger_board.py` is what keeps it display-only; set it True to
restore the veto, and read §"Gate 5" in the S4 guide first — the whitelist it would apply
measured **+0.00pp at a 12-week horizon**.

---

## 4b-iii. Stage, RS and RRG all moved on 18–19 Aug — expect different numbers

Three corrections landed in the screener that feed every board column. None of them
changed *which names fire* (catalyst selection was unchanged on all 49 board rows), but
they changed the **context** those names are shown with.

**1 · RRG is now the RRG Studio calibration.** `bull_screener` was still running the old
12/5/12 pair, so the Python producer disagreed with every other surface. It now **imports**
`rrg_engine.STRIKE_CAL` (never copies it) — decoupled 25/10/7 plus an origin-preserving
affine — verified identical to the Studio engine to `0.000000000000` across 8 symbols ×
222 weekly bars. Web Commander, RRG Studio, v67, S4, Mansfield and the Risk Allocator now
run the same maths.

**2 · Weekly indicators no longer use the forming week.** Found on **SYRMA**, from two
panels on one screen disagreeing — the Recovery card read `RRG LEADING`, SECTOR/MACRO read
`WEAKENING`. Neither was stale and neither was drifted: one used confirmed weekly bars, the
other included the week in progress. On a Tuesday that "weekly" bar holds two sessions:

| | RS-Ratio | Momentum | verdict |
|---|---:|---:|---|
| confirmed weeks only | 127.83 | **100.38** | LEADING |
| including the forming week | 126.73 | **98.92** | WEAKENING |

`_drop_forming_week()` now removes the bar whose Friday has not arrived, from **both** the
stock and the benchmark leg, and it reads the **pinned** date when one is set so replay
drops the week that was forming *at that anchor*. Measured blast radius on the 49-name
board: Stage changed 5/49, RRG quadrant 5/49, RRG tradeable 3/49, **Catalyst 0/49**.

**3 · What this means when you read the board.** Stage and RS values shifted for about one
name in ten — `MAZDOCK` and `TBOTEK` moved 2 → 3 and are now stage-blocked, `GVT&D` moved
1 → 2 and is admitted. That is a correction, not a regression, but **do not compare today's
Overall against a screenshot from last week.**

**Validation, re-baselined with both changes** (`20260819_112959`, 24 months, nifty500,
catalyst-aware windows verified 60/120/180):

| run | trades | mean matched α | median | win% | anchor hit% |
|---|---:|---:|---:|---:|---:|
| neither correction | 400 | −0.88% | −2.38% | 33.8 | 31.6 |
| RRG calibration only | 510 | +0.07% | −2.04% | 29.4 | 52.6 |
| **both** | 515 | **+0.30%** | −1.93% | 30.7 | **55.0** |

Every column improved monotonically and cumulative alpha went −9.71% → −3.86%. **But
P(α>0) is 46.1%, CI95 [−2.62, +1.76] — still indistinguishable from zero.** These were
correctness fixes; they made the measurement honest, they did not create an edge.

---

## 4b-iv. Operational fixes you will notice (18–19 Aug 2026)

| Symptom | Cause | Now |
|---|---|---|
| **Rebuild hangs; console full of screener.in timeouts** | screener.in refuses a *burst* at the TCP connect, so every name paid a 15s timeout and `core_universe` paid 30s per page — with no memo, `CONCORDBIO` was fetched **four times in 34 seconds**. A single shell request answered in 0.3s from the same IP the whole time. | `screener_breaker.py`: max 2 concurrent dials ≥0.7s apart, a 15-min memo that **caches a miss**, and a breaker that stops dialling for 10 min after 3 straight failures. Measured: 15 names across 8 threads, 15/15 OK, breaker never opened. |
| **"I restarted and it's still wrong"** | `python -m streamlit run` forks a **child** that serves the port; Ctrl+C hits the launcher and the child keeps 8501, so the app kept serving the OLD code. | **`STOP_COMMANDER.bat`** — kills the port-8501 owner plus any `weinstein_commander` orphan, and leaves RRG Studio on 8502 alone. |
| **Full Metrics printed raw HTML** (`('<div style=...`) | `section_pa_patterns` is annotated `-> str` but returned a **tuple**; a 14-Aug fix removed the unpack at the *call site* instead of fixing the function, so `st.markdown` rendered the tuple's repr. The leading `('` is the tell — that is a Python tuple, not markup. | Returns one string chosen by the `recovery` flag. COMMON renders in the bull column only. |

---

## 4c. THE ARMED REGISTER — the board's memory

**The problem it solves:** you arm a name Monday and set the TradingView alert. Tuesday the
auto-pilot rebuilds the watchlists and the name drops out of all of them. Thursday the
alert fires — and there is no row, no entry, no stop, no thesis. Only a ping and a chart.

**The model** is the same inherited-qualification doctrine: *the register qualifies, the
board times.* An armed name is injected into the union carrying the archetypes it had
**when armed**, so it keeps its original path and thesis and is re-evaluated live on every
rebuild.

**What is stored is the plan AS OF ARMING** — trigger, entry, SL, T1, R:R, verdict, Sigma,
S4-GO, path, archetypes, TF. That is the part you cannot reconstruct later, because those
levels came off that day's bar. Live re-evaluation is what the board already does.

| Action | Where | Effect |
|---|---|---|
| **Arm** | bell checkbox in the grid, or Single Symbol | Records the plan from that row; the name stays on the board through churn |
| **Disarm** | untick, or `Drop` in the register panel | Kept as `CANCELLED`, not deleted |
| **Filled** | `Filled` in the register panel | Marked `TRIGGERED`, leaves the active set |
| **Expiry** | automatic, 45 days | Applied on every read — an expiry that only runs on a button press never runs |

The **Armed Register panel** sits above the grid. It shows, per name: the armed plan beside
the **live** Category and S4-GO, how long you have been waiting, and a **warning on exactly
the names the register is saving** ("no longer on any watchlist"). That comparison — armed
at X, now Y — is the thing to read when an alert fires.

> **Habit:** arm at the same moment you create the TV alert. They are a pair. An alert
> without a register entry is precisely the failure this was built for.
>
> `gm_armed.json` is git-ignored — operational state, like the journal DB.

## 4d. THE PULLBACK FINDER — the "where is value" sibling

A trigger is a wide-range up-bar near the recent high, so a trigger-based board is
**breakout-biased by construction**. That is not a bug in a gate; it is what a stopwatch
does. Measured on a live board:

| Timing state | n | median extension from EMA20 | at value (<= 1.0 ATR) |
|---|---:|---:|---:|
| Buy Trigger Live | 8 | **1.74 ATR** | 1 of 8 |
| Armed Wait | 9 | 1.35 ATR | 4 of 9 |
| Wait for Pullback | 17 | **0.23 ATR** | 14 of 17 |

Every actionable name sat within 0.2-2.9% of its own 20-day high — and the names actually
at value were the ones labelled "wait".

`pullback_finder.py` ranks by **location**, not by trigger: extension from the EMA20 (in
ATR), pullback depth off the 20-day high, volume dry-up, 5-vs-20-bar range contraction, and
the nearest real support below price. Hard gates: Stage 2, above a rising 200-DMA, Mansfield
RS > 0, no climax volume bar. It scans the **full Nifty 500** and skips the ~149-name
screener.in fundamental join — the two things that were starving pullback supply.

`Trigger>` in the output is the **confirmation level**, not an entry: wait for a closed bar
above it, then buy-STOP above *that* bar.


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

| Surface | Role | Shared with the GM |
|---|---|---|
| **Section 4 Pine (v7.1)** | The trigger and the **final word**. GM arms; S4 executes. | `pa_patterns.py` batteries (byte-identical), the `s4go_status` gate mirror |
| **`gm_trigger_board.py`** | Batch data layer — union, archetypes, rows, RRG flags | `gm_evaluate()`, the single evaluator both surfaces call |
| **`gm_armed.py`** | The Armed Register — memory across watchlist churn | Injected as an 11th union source |
| **`pullback_finder.py`** | The "where is value" sibling | `bull_screener` + `zone_engine`; ranks only |
| **`zone_engine.py`** | Python port of S4's zone engine + S/R + AVWAP | Location, behind `GM_USE_IZE_ZONES` (still False) |
| **`pyramid_logic.py`** | ADD/TRIM/EXIT on holdings | ADDs enter the board as the Pyramid archetype |
| **`risk_common.py`** | The catalyst-aware Chandelier trail | Takes over after the fill |
| **Dashboard v67.4.12** | Canonical source of the PA formulas | The 17 patterns |

> **When the board and S4 disagree**, it is one of three things, in order of likelihood:
> **(1) mode/path** — S4's Auto vs the GM's resolved path (set S4's Mode manually);
> **(2) feed** — TV vs Dhan volume on a marginal RV test; **(3) staleness** — the board
> snapshot vs the live chart. It is **not** battery drift: the 17 bull formulas are
> byte-identical. Diff the **evaluated bar** before diffing formulas — the one real parity
> bug was an offset, in the Recovery battery, which had never been diffed.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **Board and Single Symbol disagree on a name** | Almost always vintage or TF, not logic — they call the same evaluator. Use the shared **Refresh Data**, confirm the board's built-TF matches your Trigger-TF, then rebuild. |
| **The board is all breakouts / everything is extended** | Working as designed — a trigger board is breakout-biased by construction. Run the **Pullback Finder** (§4d) for names at value. |
| **A name I armed vanished** | If it expired (45 days) it is `EXPIRED` in the register, not lost. If you disarmed it, it is `CANCELLED`. Both are still in `gm_armed.json`. |
| **The armed checkbox reverts after I tick it** | Fixed — the cached board frame is patched in place. If it persists, rebuild; the columns come from `build_row` so a board built before the feature lacks them. |
| **`S4-GO` column is all `n/a`** | No intraday trigger-TF read. The header strip names the cause (auth / no data / thin history / not closed yet) — it is a **feed** problem, not a scoring one. |
| **A rigorous watchlist name reads "no catalyst"** | Pre-P1 behaviour. Inherited qualification means Setup = the archetype; only **Catalyst-Scan-ONLY** names need a live catalyst. |
| **Pullback / EarlyBird lists are nearly empty** | The ~149-name `MASTER_scan_results.csv` fundamental join — Pullback loses ~76% of its Chartink names to it, EarlyBird can hit zero. Not a signal failure. |
| **Board shows PA that is gone by the time I look** | Set Live = `75m+125m bar-close`, and note that **PA recency** now keeps a pattern visible for 3 bars, labelled `PA Nb`. |
| **Watchlist CSV silently missing from the board** | The header strip surfaces unreadable/empty sources (`LAST_UNION_ISSUES`) — it has already caught real header-only files. |
| **A GO alert never fired** | An S4 **recompile destroys alerts** (they bind to the `pine_id`). Delete and re-create every GO alert after every compile. |
| Stage / RS look wrong vs Dashboard v67 | The strict-trend port was stale until 29-Jul (`strict_trend.py` is now the one engine). Confirm you restarted the app after that change. |

---

*Guide rewritten 31 July 2026. The Golden Matcher is the **upstream half** of the GM + S4
system: the Trigger Board filters, the Single Symbol view reads, the Armed Register
remembers, and the Pullback Finder supplies what a trigger board structurally cannot. The
downstream half — the trigger, the plan and the verdict — is
`docs/22_Section4_Entry_Trigger_Guide.md`, whose **PART B is the complete end-to-end
workflow across both.***
