# Trading Ecosystem — Deep Logic Audit Ledger

**Started:** 19 June 2026. Companion to `AUDIT_REPORT.md` (which covers the data-feed/migration fixes).
**Purpose:** an *auditable* record — every module that touches rankings gets an explicit **CLEAN** or **BUG** verdict with evidence, so anomalies are eliminated by coverage, not by assertion. Triggered by the user's (correct) observation that repeated prior "audits" kept missing silent ranking-corruptors.

**Method:** for each scoring/ranking/data module, check the recurring failure-mode classes that have actually burned this system:
(1) stale data served as fresh, (2) empty/NaN columns silently propagating into rankings, (3) silent fallbacks/`except: pass` masking failures, (4) type traps (`np.bool_ is True`), (5) miscalibrated normalization, (6) join key mismatches.

---

## ⚠️ CORRECTIONS TO MY OWN EARLIER CLAIMS (verified against real data 19 Jun)

Honesty over body-count. On deeper verification against the actual auto-pilot output, two of my four initial "bugs" did **not** have the production impact I claimed. Recording the retraction:

- **B1 (np.bool_ in Tech_Score) — RETRACTED as a production bug.** The trap only bites a *pure-bool* DataFrame. The real pipeline's enriched frame has many mixed-dtype columns, so `apply(axis=1)` yields an **object** row and the flag comes back as **python `bool`** → `is True` works. Proof: the pre-fix auto-pilot `FINAL_WATCHLIST.csv` shows NETWEB Tech=90, which *includes* the +20 from the flags (no-flag value would be 70). The `== True` change is harmless hardening, **not** a live fix. My "20 points silently dropped from every ranking" was wrong.
- **B2 (conviction abort-on-bad-cell) — DOWNGRADED to latent.** Real code defect, but not confirmed to have fired this run: the scored columns are mostly *absent* from `MASTER_scan_results.csv` (default 0, no raise) and the one present column has zero float-choking values. Valid defensive hardening; not a proven live corruption.
- **B3 (recovery /12 saturation) — real arithmetic bug, but its target file is currently produced by a path that skips it entirely (see B6),** so no live impact via the auto-pilot CLI; it would matter on the Web Commander path. Fix retained.

The genuinely real, impactful items remain: **P0 enrichment** (confirmed working — Hunter/Watchlist now enriched & sorted), **A1 stale watchlist** (confirmed from disk), and the new **B5/B6** below.

## BUGS FOUND & FIXED (this deep pass)

### A1 — Stale watchlists uploaded as fresh — `strike_automation.py` — FIXED ✅
When a day's scan yields 0 picks, the generator (`watchlist_manager.py`) correctly writes nothing. But the Strike sync then fell back to `LATEST_<name>.txt` **from a prior run** and uploaded those stale symbols under today's date.
- **Evidence:** auto-pilot 19 Jun log — `Rec_Climax_Bounce` scan = 0, yet sync uploaded "3 symbols"; on disk `LATEST_Rec_Climax_Bounce.txt` was dated **2026-06-12** (7 days stale). The TradingView sync (correctly) skipped — the two syncs were inconsistent.
- **Fix:** `strike_automation.py` now uses the `LATEST_` fallback only if it was modified **today** (`_is_file_from_today`); a stale fallback is skipped loudly (cleanup already purged the old list). `strike_automation.py` was the only consumer with this bug (grep-confirmed).
- **This is the exact failure the user reported** ("seeing a different version of the watchlist").

### B1 — Tech_Score silently drops the 200DMA + EMA-stack terms — `technical_enrichment.py` — FIXED ✅
`calc_tech_score` used `row.get("Above_200DMA") is True` / `EMA_Stack is True`. In the real pipeline `enrich_dataframe` builds these via `pd.DataFrame(...)`; when every row succeeds the column becomes **numpy bool dtype**, so `row.get()` returns `numpy.bool_`, and **`np.bool_(True) is True` → False**. Both +10 terms were silently dropped from every Tech_Score.
- **Evidence (tested):** `calc_tech_score({'Above_200DMA':np.bool_(True),'EMA_Stack':np.bool_(True)})` → **0**; with python `True` → **20**. Real enriched column dtype confirmed `bool`.
- **Impact:** every Tech_Score understated up to 20 pts; stocks that genuinely clear those gates got no credit over those that don't → skewed `Combined_Score`. Worst exactly when the watchlist is clean (all rows enrich).
- **Fix:** use `== True` (correct for python bool, numpy bool, and False for None/NaN/False). Verified the flags now register (NETWEB 85→90).

### B2 — Conviction scorers abort on first unparseable field — `brute_force_match_pro.py` — FIXED ✅
Both `calculate_conviction_score` and `calculate_recovery_conviction_score` wrapped their **entire** body in `try/except: pass`. A single `'N/A'`/`'-'`/`None` cell raised on the first field and skipped **all** remaining additions, silently collapsing conviction toward the 5.0 base.
- **Evidence (tested):** a strong stock with `'N/A'` in the first field scored **5.0** instead of **7.5**.
- **Impact:** conviction is 50% of `Combined_Score`; any stock with one bad fundamental cell was under-ranked.
- **Fix:** new `_safe_num()` parses each field independently (skips `'', nan, n/a, na, -, --, none`); one bad cell yields 0 for that field only. Missing-field default preserved (0.0, same as old `or 0`) → no scoring regression. Verified → 7.5.

### B3 — Recovery Combined_Score saturates above Score 12 — `conviction_passthrough.py` — FIXED ✅
`score_norm_factor = 100/12` assumed recovery `Score` ∈ [0,12]. But `recovery_screener.compute_score` maxes at **22** (rff 8 + rs 2 + corr 3 + regime 2 + stage 1 + signal 3 + vol 2 + chartink 1). Every recovery pick scoring ≥12 mapped to `tech_norm=100`.
- **Evidence:** auto-pilot actionable recovery picks scored 14–18 — all saturated to 100, so their ranking was driven by conviction alone; the recovery signal quality was washed out.
- **Fix:** factor → `100/22`. Verified Score 14 → 63.6 and 18 → 81.8 (were both 100).

---

## NEW FINDINGS — recovery ranking interconnectivity (19 Jun, NOT yet fixed)

### B6 — Recovery CLI path skips conviction/Combined_Score ranking — `recovery_screener.py` — FIXED ✅
Factored the passthrough + Combined_Score re-sort into a shared `_apply_combined_ranking()` called by BOTH `run_recovery_screener()` and `main()`. CLI (auto-pilot) and Web Commander now produce identical recovery rankings. **Note:** the on-disk `Recovery_Screener_Results.csv` still shows the old Signal+Score order until the next recovery run regenerates it.

### B5 — Recovery conviction degenerate (raw vs golden column names) — `conviction_passthrough.py` — FIXED ✅ (with documented coverage caveat)
Root cause was deeper than "wrong source": MASTER carries RAW Screener names (`Return on equity`), but the conviction scorers expect GOLDEN names (`ROE %`), so only `Debt to equity` matched and conviction collapsed to a degenerate base+D/E (~5.0/7.0). Fix: apply the matcher's rename map in `_load_master` (fixes BOTH bull and recovery passthrough). Verified — recovery conviction now varies `[6.0, 8.0, 9.5]` instead of `{5.0, 7.0}`.
- **Caveat (documented, not silently bodged):** the recovery Screener.in CSVs (`SCREENER_Recovery_*.csv`) only carry RFF fields (NI/OCF/ICR/D-E/CR/ROA), NOT the conviction fields (ROE/ROCE/promoter/div/mcap/growth). Those exist only in the Stage-2 MASTER, which covers ~16/78 recovery names. The rest get tech-only Combined_Score. Full coverage needs per-symbol `fundamental_hub` enrichment of the recovery set — flagged as optional follow-up, NOT done (changes recovery scoring weight + adds per-symbol network fetches).

### (historical) B6 original write-up — Recovery CLI path skips ranking — superseded by FIXED above
`run_recovery_screener()` (programmatic / Web Commander) calls `conviction_passthrough` and re-sorts by `Combined_Score`. But `main()` (the CLI path the **auto-pilot uses**) saves at line 2076 sorted by **Signal+Score only** and never calls the passthrough.
- **Evidence:** today's `Recovery_Screener_Results.csv` (auto-pilot output) has **no `Conviction`/`Combined_Score` columns** and is ordered Signal→Score. Running the passthrough on it manually succeeds and adds both columns — so it simply wasn't invoked.
- **Impact:** the 78-symbol `Rec_Screener` watchlist is ordered differently than the Web Commander would show for the same data. Same file, two rankings depending on entry point.
- **Proposed fix:** have `main()` apply the same `conviction_passthrough` + Combined_Score re-sort as `run_recovery_screener()` (or factor the save+rank into one shared helper both call). *Deferred for your sign-off — it changes the recovery list ordering.*

### B5 — Recovery conviction sourced from the Stage-2 master — `conviction_passthrough.py` — OPEN
`conviction_passthrough._load_master()` always reads `MASTER_scan_results.csv` (the **Stage-2** universe). For recovery, conviction should come from the recovery Screener.in CSVs (`SCREENER_Recovery_*.csv`). So on the programmatic path, recovery conviction resolves for only the ~16/78 names that happen to also be in the Stage-2 master; the other ~60 get `Conviction=NaN` and rank on tech alone.
- **Evidence:** ran passthrough on the recovery file → `Conviction` non-null for **16 of 78**; matches the log's "Screener.in overlap 18 of 78."
- **Proposed fix:** point recovery-mode conviction lookup at the recovery fundamentals source. *Deferred — entangled with B6 and changes recovery scoring.*

## H/G FINDINGS (screeners + output files)

- **`FINAL_*_RRG.csv` are 5 months stale (2026-01-30) — orphaned, LOW severity.** Written by `strike_automation.run_rrg_scan()` (a separate Strike RRG mode), which the auto-pilot does NOT invoke. Grep confirms **nothing reads them downstream** → no live data leak, but misleading clutter. Recommend: delete the stale files, or wire `run_rrg_scan` into the flow if RRG_Quadrant is wanted. (Not a ranking bug.)
- **XRay (`weinstein_xray_screener`) — CLEAN (logic verified).** Minervini (0-8), Piotroski (0-9), Overall (0-17) math is sound. The suspicious `roa_ttm > (roa_ly*100)` / `gross_margin > (gm_ly*100)` in Piotroski F3/F8 are CORRECT unit reconciliation — current-year ratios are percent (×100 at lines 179/181), prior-year are fractions (lines 172/175), so the ×100 aligns them. F5/F6/F9 use consistent fraction-vs-fraction. Data-source note: XRay uses yfinance `.info`+financials for fundamentals (not Screener.in) — works, but could be Screener-overlaid later (enhancement, not a bug).
- **Bull regime gate — CLEAN logic.** "NOT BULL" was correct: requires `close>SMA200 AND SMA50>SMA200`; SMA50<SMA200 currently → bull POS catalysts intentionally suppressed. Conservative-by-design, not inverted.
- **P0 enrichment — CONFIRMED in output.** `FINAL_Hunter_Picks.csv` etc. now fully enriched + sorted by Combined_Score; file counts consistent across the pipeline (Hunter 2 / Pullback 6 / EB 1 / Leader 5 / RS 9 / RecEB 18 / Combined 29 / Watchlist 25 / XRay 25).

## I — WEB COMMANDER INTERCONNECTIVITY — CLEAN (structural)

- **All 21 `launch_script()` targets exist** (chartink_scanner_pro, screener_fetcher/processor, brute_force_match_pro, bull/recovery_screener, xray_screener_job, watchlist_manager, strike_automation, tradingview_automation_v2, master_portfolio_sync, gmail_dispatcher, sector_manager, run_pipeline, dhan_journal_v7, pages/*). No dangling references.
- **All 38 local-module imports resolve** (ai_grading_engine … xray_screener_job). The only "unresolved" token was `concurrent` = `concurrent.futures` (stdlib). No wrong refs.
- **Compiles clean** — web commander + all 4 `pages/*.py` + xray_screener_job.
- **`run_pipeline.py` (auto-pilot) orchestration correct & consistent:** Phase 4 `perform_match` (P0/B2 fixes), Phase 4.5 `recovery_screener.main()` (**B6 fix lands here** → auto-pilot now Combined_Score-ranked), Phase 4.6 `run_bull_screener`, two-pass watchlist gen (5 then 5.6 so X-Ray picks are included), Phase 6 `strike_automation --mode=watchlist` (**A1 fix**), Phase 7 `tradingview_automation_v2 --pipeline`.
- **Caveat:** this is structural (imports/refs/orchestration + compile). The ~7,500-line per-page handler logic was NOT line-by-line audited; no evidence of dead refs, but a full UI-logic review is a separate effort if you want it.

## B7 — XRay Piotroski F9 column always 0 (copy-paste bug) — `xray_screener_job.py` — FIXED ✅
Line 112 read `p_details.get("Piotroski_Details", {}).get("F9 Asset Turnover Increasing", 0)` — but `p_details` IS already the Piotroski_Details dict, so the inner lookup returned `{}` and the **"P: F9 Asset Turnover Increasing" column was hard-wired to 0** regardless of the real check. The stored `Piotroski_Score` (correct) was therefore +1 vs the sum of the displayed P: flags whenever F9 actually passed.
- **Caught by `score_authenticity_check.py` on its first run** (Piotroski_Score == sum(P:) failed 6/25; all 6 were exactly +1).
- **Fix:** `p_details.get("F9 Asset Turnover Increasing", 0)`. The on-disk `FINAL_XRay_Picks.csv` still shows the bug until the next XRay run regenerates it (validator will then PASS).

## NEW TOOL — `score_authenticity_check.py` (confidence guarantee)
Read-only validator (~2s; wired as auto-pilot Phase 11, non-fatal). For each output CSV it RE-COMPUTES the stored score from the row's own visible columns using the canonical pipeline functions (zero drift) and confirms they match, plus per-column fill rates (distinguishing real gaps from semantic blanks). First-run results: FINAL_WATCHLIST 25/25, FINAL_COMBINED 29/29, Bull blend 3/3, **Recovery Score 78/78 reproducible**, XRay Minervini 25/25 — and it caught B7. This turns "do I trust this CSV?" into a per-run PASS/FAIL stamp.

## J / C / D / E — RESULTS (19 Jun 2026)

### J — Strike/TV porting — CLEAN (post A1 fix)
- `create_strike_csv_from_txt`: reads all symbols, strips NSE:/BSE:, chunks at 49 (correct ceil-division), one Symbol-headed CSV per chunk, no dropping. (No dedup, but source txt is from already-deduped FINAL CSVs.)
- TradingView sync (`tradingview_automation_v2`): dated files only, skips missing (line 391) + empty (395), deletes same-name lists before re-upload (dup-safe). No stale fallback (correct — the contrast to the Strike A1 bug, now fixed).
- Both syncs consume the same `Generated_Watchlists` source → consistent symbol sets.

### C — Joins/merges & column integrity — 1 LATENT BUG FIXED
- **C1 FIXED — `technical_enrichment.enrich_dataframe` index misalignment.** It dropped NaN symbols (`syms = ...dropna()`) but assigned enriched rows to `out.index[:n]` (first n labels). A blank symbol anywhere but the tail misaligned EVERY metric to the wrong stock (proven with a 3-row repro: BBB's value landed on the blank row). Doesn't trigger in today's Golden Matcher path (symbols are the non-null merge key) but is a silent-misalignment landmine. Fixed to align on the real non-null index (`_sym_index`).
- All other merges CLEAN: the `pd.merge(..., left_index/right_index, how="inner")` in bull/recovery and `concat(join="inner")` in enrichment are **date-index RS/Mansfield alignments** (correct — RS only computable on common dates); the matcher `MATCH_KEY` join is an intentional intersection with consistent `upper().strip()` keys; combined dedup keeps first occurrence (metrics identical per symbol).

### D — Silent-fallback / NaN→0 / empty-as-success — RANKING PIPELINE CLEAN
- The dangerous patterns were already remediated this audit: conviction abort (B2), Dhan silent→yfinance (now loud), recovery passthrough swallow (B6).
- Remaining `except` blocks are benign: indicator guards (return None → **visible blank**, the honest behavior you want), temp-file cleanup, optional-feature imports.
- `fillna(0)` audit: the matcher's only fillna(0) is a throwaway `_Sort_Num` sort key (blank scores sink to bottom; real Combined_Score untouched). No STORED ranking score is faked via fillna(0) anywhere.
- **Cross-domain caveat (NOT watchlist):** journal P&L display uses `BuyPrice.fillna(0)` (pages/1_home.py, dhan_journal_v7) — a missing buy price would inflate displayed P&L. Separate domain (journal, already reconciled earlier); flagged for awareness.

### FOLLOW-UP FIXES (user Q&A, 19 Jun 2026)
- **Q2 → B8 FIXED — watchlist Stage now uses the canonical WEEKLY 30-WMA (zero drift).** `technical_enrichment.enrich_symbol` now calls `bull_screener.compute_weekly_stage_and_wks` (lazy import) for Stage, with the daily proxy only as a fallback. Verified enrichment == bull_screener for NETWEB/RELIANCE/COALINDIA/TCS. **COALINDIA was Stage 3 (daily proxy) vs Stage 2 (canonical weekly)** — a +20 Tech_Score correction. The daily SMA200/50 stage was drift, not a requirement: bull_screener (and Pine's weekly-anchored stage) use the 30-WMA. Re-run the pipeline to propagate.
- **Q4 → FIXED — recovery conviction no longer rewards MISSING Debt/Equity.** `_safe_num(..., default=None)`; the +2.0 "strong balance sheet" bonus (and -1.0 penalty) now require D/E to be present. Verified: missing D/E 10.0→8.5; present D/E still scores.
- **Q1 → FIXED — recovery conviction now covers the FULL set (78/78, was 16/78).** Root cause: value-style columns (ROE/ROCE/mcap/promoter/growth) exist only in the Stage-2 MASTER; the recovery Screener.in source carries RFF fields instead. Fix: `conviction_passthrough._extend_recovery_conviction` fetches the missing names per-symbol via `fundamental_hub` (Screener.in primary), maps the units to the golden column names, and computes the same recovery conviction. Verified 16→78/78; conviction now varies 5.5–10.0 and ranks correctly (ELECON Score17+conv10 → top). Cached by fundamental_hub; failures degrade to tech-only (no regression). **Tradeoff:** adds ~1–2 min to the recovery phase on a cold cache (≈62 fetches), fast thereafter — accepted by Jay.
- **Q3 (stale FINAL_*_RRG.csv):** user will handle — left as-is.
- **Q5 (journal BuyPrice.fillna(0)):** flagged as MUST-FIX whenever the journal P&L module (pages/1_home.py, dhan_journal_v7.py) is next touched — a missing buy price currently inflates displayed P&L.

### E — Structural indicator math — CLEAN, weekly-stage drift FIXED (B8 above)
- RSI (Wilder ewm), ADX (Wilder DI/DX), Mansfield RS ((ratio/SMA−1)×100), EMA-stack (50>150>200), Above_200DMA, Dist_52WH, ATR, Vol_RelAvg — all mathematically correct. No Stage 1↔3 swap (that prior bug was in watchlist_ranker, a different module).
- **SPEC DEVIATION (flagged, not changed):** `technical_enrichment._calc_stage` classifies Weinstein stage from **daily SMA200/SMA50** ("Simplified" per its docstring), but the DNA spec anchors Stage on the **weekly 30-WMA** (and `bull_screener` uses a weekly stage). So the `Stage` column in the watchlist (→ ±15 in Tech_Score) is a daily proxy that can disagree with the canonical weekly stage. Changing it alters scoring semantics → deferred for your decision.

## MODULES AUDITED — VERDICTS

| Module / function | Role | Verdict |
|---|---|---|
| `strike_automation.py` (watchlist upload) | Strike sync | **BUG (A1) → fixed** |
| `watchlist_manager.py` (generation) | writes dated + LATEST txt | **CLEAN** — correctly writes nothing on empty scan (doesn't fabricate) |
| TradingView sync (Phase 7) | TV upload | **CLEAN** — skips missing dated file (no stale fallback) |
| `technical_enrichment.calc_tech_score` | tech half of Combined_Score | **BUG (B1) → fixed** |
| `technical_enrichment.calc_combined_score` | 50/50 blend | **CLEAN** (handles None/''/'N/A') — note: duplicated in conviction_passthrough |
| `technical_enrichment.enrich_symbol/_calc_*` | Stage/RS/EMA/200DMA/52WH/vol | **CLEAN** — Python `bool()` wraps, `pd.isna` guards present |
| `brute_force_match_pro.calculate_conviction_score` | bull conviction (50% of rank) | **BUG (B2) → fixed** |
| `brute_force_match_pro.calculate_recovery_conviction_score` | recovery conviction | **BUG (B2) → fixed**; LOGIC NOTE below |
| `conviction_passthrough.add_conviction_and_combined_score` | recovery/bull Combined_Score | **BUG (B3) → fixed**; key-symmetry NOTE below |
| `bull_screener.compute_score` (pyScore, 0-100) | bull catalyst quality | **CLEAN** — safe `.get` defaults, capped, no NaN/abort traps |
| `recovery_screener.compute_score` (0-22) | recovery quality | **CLEAN** (range now correctly consumed) |

### Logic notes (flagged, NOT silently changed — your call)
- **Recovery conviction rewards MISSING Debt/Equity:** `_safe_num` returns 0.0 when D/E is absent, and `if de < 0.5: score += 2.0` then awards the "strong balance sheet" bonus to stocks with *no* D/E data. This matches the pre-existing `or 0` behavior (not a regression introduced now), but it is a real logic smell — missing data is rewarded. Recommend: require D/E present for the +2.0. Deferred pending your decision (changes scoring semantics).
- **Duplicate blend logic:** `_calc_combined_score` exists in both `technical_enrichment.py` and `conviction_passthrough.py`. They currently agree; drift risk. Recommend consolidating to one.
- **Symbol-key symmetry:** `conviction_passthrough` strips `NSE:/.NS` from the screener side but the MASTER map keys are not stripped. Works while MASTER symbols are clean (current case); fragile if MASTER ever carries prefixes.

---

## REMAINING SCOPE (not yet audited — in progress)

- **C. Joins/merges & column integrity** — every `pd.merge`/`concat` in the pipeline for key mismatches that drop rows/null columns; the Screener.in→golden-schema renames; empty-column propagation.
- **D. Silent-fallback / NaN→0 / empty-as-success sweep** — ecosystem-wide `except: pass`, `fillna(0)`, empty-df-as-success, stale-cache-as-fresh.
- **E. Structural indicator correctness** — Stage/30WMA, Mansfield, EMA/SMA, ATR, 52WH math vs documented specs (RRG read-only per do-not-touch rule).

**Status:** A and B (watchlist freshness + ranking formulae — the core of "wrong lists from wrong calculations") are complete: 4 ranking-affecting bugs found and fixed. C/D/E pending.

---

# 20 September 2026 — End-to-end system, logic and parity audit (Phases 1–5)

Scope: Web Commander + engines + pipelines + honesty layer (Python), the 9 live Pine files,
Python↔Pine parity, RRG Studio, Strike sync (dormant, kept). Against `main` @ `e643d97f`.
Every finding carries a file:line read on the day. Severity: P0 blocker · P1 logic/parity
drift · P2 latent defect · P3 debt/doc lag. Phase-2/3/4 reports live in the session
transcript of 20 Sep; this is the ledger.

## Health: 71 / 100 — stable, tradeable tomorrow, drifting at the seams

| Finding | Sev | Location | One line |
|---|---|---|---|
| AUD-PAR-01 | P1 | pa_patterns.py:344 vs S4Core.dailyPA p_eng / v67:3287 | Bull Engulf is two different patterns since 10 Aug (uptrend-reclaim vs validated B6 oversold form) |
| AUD-PAR-02 | P1 | pa_patterns.py:383 vs S4:3028 | Stage-2 Launch: weekly-volume gate (Py) vs daily RV (S4) |
| AUD-PAR-03 | P1 | S4:3165 · v67:2500 · bull_screener.py:530 | Stage 2×2 tie-break: RS slope (S4) vs strict trend (v67, Py); Python lacks the below-rising → 2 PULLBACK branch |
| AUD-PY-01 | P1 | rrg_studio/rrg_engine.py:245–330 | RRG Studio computes on the forming week (every other surface drops it) |
| AUD-PY-02 | P1 | pre_trade_gate.py:96 | Risk-% check is skipped when SL is missing / zero / ≥ entry → BUY passes |
| AUD-PY-03 | P1 | exit_signal_engine.py:151–156 | Third stop engine (22-high − 3×ATR) still live; Telegrams 16:00 ACTIONs from a formula no other surface uses |
| AUD-PINE-01 | P1 | S4:4293–4308 + 5553–5586 | Trigger latch fixes the ENTRY only; SL (and so T1/T2) recompute from current-bar structure |
| AUD-PY-04 | P2 | data_provider.py:309 | Daily frames with 2y+ period get the 24 h weekly TTL |
| AUD-PY-05 | P2 | data_provider.py:796 | Expired last-resort cache recorded as "cache" |
| AUD-PY-06 | P2 | scheduler_daemon.py:559–692 | token_check / exit_scan are in-app only, no catch-up (auto_pilot moved to Task Scheduler 20 Sep) |
| AUD-PY-07 | P2 | gm_trigger_board.py:1344 | ⚠unval tag now false — recovery IS measured (no edge) |
| AUD-PY-08 | P2 | recovery_screener.py:1575 + replay | CB-Watch (Signal=1, a pre-signal) is 30% of the recovery replay set |
| AUD-PY-09 | P2 | _archive/strike_money/strike_automation.py | Dormant; mtime-only freshness, DOM-selector fragility, Phase 6b/nuclear hooks removed — re-enable needs three edits |
| AUD-PINE-02 | P2 | S5:99 vs f_geoClean:1083 | close[_off] up to 3,999 under max_bars_back=300 — will error on Daily |
| AUD-PINE-03 | P2 | S4 input.source ×2 | Footprint sources can never bind (S5 lives on another chart) |
| AUD-PINE-04 | P2 | Context Layers:414–420, 1055 | S8 / BROKEN need 3 alternating CHoCH in 20 bars — reachable but effectively never |
| AUD-PAR-04 | P2 | S4:973 / :5016 | No bundle-length / tag-count check; tooltip's "4,096 cap" unverified against a 7,555-char paste |
| AUD-PY-10 | P3 | rrg_studio/rrg_engine.py:690 | Second copy of STRIKE_CAL |
| AUD-PY-11 | P3 | conviction_passthrough.py:148, 249 | Strip-only symbol key (the _canon_key class) |
| AUD-PY-12 | P3 | weinstein_commander_web_v4.0.py | 333 blanket excepts, 51 `pass` |
| AUD-PINE-05 | P3 | S4:6378 | Alerts survive only by the nightly ritual (constraint, not defect) |
| AUD-PINE-06 | P3 | S4:1924–2046 | activeZones has no hard cap (20 s-limit exposure) |
| AUD-PAR-05 | P3 | gm_trigger_board.py:2630 | ACC bundle section written, never read |

Fixed during the audit: in-app auto-pilot had no catch-up → Task Scheduler (bfc4f83d);
pop-out views were not hiding the sidebar (e9cb855c); Phase-1 read died on volume-less
index bars (acd7ac65); superseded Pine copies archived (e643d97f).

## Verified clean (do not re-audit): lock lifecycle · dhan_auth refresh/rate-limit ·
scheduler singleton · cache no-retimestamp · pop-out TF isolation · R-canon on 5 surfaces ·
RRG calibration on 6 · 15/17 bull + 10/10 recovery formulas · weekly evaluated-bar ·
S4-GO gate mirror · bundle tags · v67 plot budget 38/64 · Zigzag bootstrap · latch edge in
global scope · Risk Allocator v2.2 targets/partials.

---

# 23 September 2026 — RRG trajectory: counter-clockwise call inside the dead band

Found by Jay reading a live ANANDRATHI 75m S4 panel (v10.6 / panel v11.5 / core 55):
the sector half of the RRG row printed `LEADING → IMPROVING`, which he flagged as an
impossible rotation. Verified against the live panel over CDP and against the compiled
source (repo copy is byte-clean vs the chart build).

The row as it read:

```
RRG (N500 / Financial Services) | LEADING ↙️  +2  │  LEADING → WEAKENING  │  🔴 WAIT  (RS-Ratio 111.4)
                                 │   vs sector: LEADING ↙️  +2  │  LEADING → IMPROVING  │  🟢 BUY OK  (RS-Ratio 113.1)
```

| Finding | Sev | Location | One line |
|---|---|---|---|
| AUD-PINE-07 | P2 | S4Core.pine:1060 (`rrgInfo`, LEADING branch) | A quadrant CHANGE is called off a momentum delta inside the ±0.3 dead band, so the arrow and the trajectory contradict each other on the same line |
| AUD-PAR-06 | P1 | S4:1279 tooltip vs S4:4164 + S4Core.pine:1071 (`tr`) | `cf_w_rrg` documents the 2-cell measured whitelist; the code awards on the OLD 5-cell `_rrgTr`, including a cell the 18-Aug study measured reliably negative |

**AUD-PINE-07 — not "impossible", but not earned either.** Every quadrant in `rrgInfo`
has a clockwise primary and a counter-clockwise secondary (LEADING→IMPROVING,
WEAKENING→LEADING, LAGGING→WEAKENING, IMPROVING→LAGGING). That is deliberate: the
function answers "which quadrant is this point drifting into", and a point in the
top-right CAN move left into the top-left. Counter-clockwise rotation is a known RRG
caveat rather than an impossibility, and the strike calibration's decoupled windows
(25/10/7) leave the two axes only loosely coupled, so it is more reachable here than on
a textbook JdK RRG.

The defect is the THRESHOLD, not the branch. Back out the numbers from the arrow:
`↙️` requires `dv < -0.3` with `dm` not rising, and reaching the IMPROVING clause at all
requires `dm >= -0.3`. So on that bar the sector momentum delta sat **between −0.3 and
+0.3 — flat, below the very threshold the function uses elsewhere to call a direction** —
and a real leftward x-move plus nothing on y was resolved into a confident "→ IMPROVING".
Hence the contradiction Jay spotted: `↙️` is down-and-left, `IMPROVING` is up-and-left,
printed on one line. Honest output is `LEADING (drifting ↙)` — stable with a qualifier.

Aggravating context on that same panel: the SUMMARY block read "the rotation has rolled
over: relative strength is being GIVEN BACK, not built", directly beside a `🟢 BUY OK`.

**Blast radius today: display only.** The sector half's `tr` is computed inside
`rrgSecTxt` and only printed. Only the N500 pair drives the `Q` chip and the confluence
point (S4:1519, S4:4164), and that half read `LEADING → WEAKENING → 🔴 WAIT` — `⚪Q` in
TRIGGER, `⚪RRG` in Confluence 3/23. Nothing scored off it.

**AUD-PAR-06 is the consequential one.** `tr` = L→L, **L→I**, **I→L**, **Lag→I**, W→L
(5 cells). The `cf_w_rrg` tooltip says the point is awarded "when the RRG TRAJECTORY is
on the measured whitelist - LEADING->LEADING or WEAKENING->LEADING". The 18-Aug
re-measurement (473 symbols / 93,745 weekly observations, IS/OOS, bootstrapped by
symbol) found only those two positive at both horizons in both windows, and found
`IMPROVING→LEADING` reliably NEGATIVE (−0.33 / −0.87, CI excludes 0). The code still
awards the confluence point on all five, and `en_rrg_gate` would enforce all five if
ever switched on. Doc and code disagree; the doc matches the measurement.

**Proposed fix (HELD — clubbed with the next Pine batch, Jay's call).**
1. `rrgInfo`: require the counter-clockwise secondary to carry a real y-component
   instead of firing on a flat `dm`, so a left-drift out of LEADING prints as
   `LEADING (drifting ↙)`. Fixes the arrow/label contradiction at source, both halves.
2. Narrow `tr` to the two measured cells so `BUY OK`, `Q` and `cf_w_rrg` agree with the
   tooltip and the study.

(2) is a SIGNAL change — it flips `Q` on some names and shifts Confluence totals, so it
needs a board rebuild and a look before it is trusted. Both need a library republish, an
S4 recompile, `BIND_S4_SOURCES.bat`, and the two GO alerts recreated.

---

# 23 September 2026 — Reviewer audit: today's 35 alerts vs their panels and Log rows

Every claim below is checked against the **PANEL READ embedded in the same `.md`**, never a
live re-read — the panel moves on, so a live diff measures the clock, not the reviewer.

| Finding | Sev | Location | One line |
|---|---|---|---|
| AUD-REV-01 | **P1** | s4_review.py:1005 (`r_check`, entry branch) | The entry branch is skipped whenever the PLAN line also contains "stop:", so a ONE-LINE plan never parses — R-CHECK silently did not run on **16 of 34** reviews today |
| AUD-REV-02 | P1 | (consequence of REV-01) | 3 of those 16 unchecked plans carry real R mis-statements, one of them 2× |
| AUD-REV-03 | P2 | s4_alert_review.py:176 | A failed review logs `review rc 1` and nothing else — no stderr, no `.md`, no Log row |
| AUD-REV-04 | P2 | s4_review prompt · §6 "STRUCTURE (S5)" | The prompt asks for an S5 structure read while S5 §I GEOMETRY / §II LEVELS / §VI READ are withheld; one review filled the gap by asserting "the geometry is clean" |
| AUD-REV-05 | P2 | 15:30 batch | Cross-sectional inputs (RS / RRG) were still settling at read time; ANANDRATHI crossed a quadrant boundary between 15:31 and 15:50 with its own price fields unchanged |

## Coverage
35 queued · 34 reviewed · **1 failed**: `BAJAJ_AUTO 125`, queued 13:25:11, `review rc 1` at
13:31:42 after ~55 s. No `.md`, so no Reviewer Log row, and no captured stderr — the failure
is undiagnosable after the fact (AUD-REV-03).

## AUD-REV-01 — reproduced against the real function, not inferred
`r_check` iterates the PLAN line by line and guards the entry branch with
`re.search(r"entry|buy-?limit|buy-?stop|limit order", low) and "stop:" not in low`. The guard
exists so the stop line is not read as the entry; it also means **any plan that puts entry and
stop on one line yields `entry = None`** → "could not parse". Secondary: plain `Buy 2190.0` is
not in the entry vocabulary.

Five fixtures run through the imported `r_check`:

| plan form | result |
|---|---|
| `Entry: Limit order at 52.45 · Stop: 51.59 · T1 …` (MOCAPITAL) | could not parse |
| `Entry: Market Fill (27.69). Stop: 27.02 …` (PVTBANIETF) | could not parse |
| `Buy 2190.0 (Stop 2103.4) · T1 …` (ANANDRATHI) | could not parse |
| one line, stop written first | could not parse |
| entry/stop on SEPARATE lines (GLAND form) | **runs correctly** |

Where it ran, it worked: it caught CPPLUS 75 `T2 4685.40 → 11.74R (model said 3.5R)`,
TVSMOTOR 75 `T2 → 3.33R (model said 5.0R)`, and PIDILITIND's mis-stated pair. The tool is
sound; its input parser is not.

## AUD-REV-02 — what went out unchecked
| review | claimed | actual | entry / stop |
|---|---|---|---|
| MOCAPITAL 75 | T1 3R · T2 5R | **7.37R · 11.56R** | 52.45 / 51.59 (risk 0.86; true 3R = 55.03) |
| PVTBANIETF 125 | T1 0.7R · T2 4R | **0.30R · 2.01R** | 27.69 / 27.02 |
| ANANDRATHI 75 | T1 2R | **1.00R** | 2190.0 / 2103.4 |

MOCAPITAL reads as targets written backwards from "positional canon is 3R/5R" rather than
computed from the risk — the exact failure R-CHECK was built for.

## Behaviour, not a bug: T1 under the canon floor
R-CHECK's `⚠ T1 … under the …R floor` fired on **11 of the 18** plans it could check. The
reviewer keeps writing sub-canon T1s; the check is catching them. No code change proposed.

## Faithfulness spot-check — clean
ANANDRATHI 75 read line by line against its embedded panel: "RRG Weakening → Lagging", "RS vs
N500 flat", "not leading" — all three exactly match the panel it was handed
(`WEAKENING ↙️ 0 │ WEAKENING → LAGGING`, `N500: Flat (Positive) ➡️`, `LEADERSHIP: Not leading.`).
An earlier suspicion that the reviewer had misread the RRG was **wrong** and is retracted here.

## AUD-REV-05 — the 15:30 batch reads settling cross-sectional inputs
Between the 15:31 read and a 15:50 live read of the same last-closed bar, ANANDRATHI's own
price fields were IDENTICAL (E 2173.0, TRIGGER GO, Confluence 3/23, RSI 47.1) while the
RRG/RS block moved: `WEAKENING ↙️ 0 · WEAKENING → LAGGING · RS-Ratio 110.9` →
`LEADING ↙️ +2 · LEADING → WEAKENING · RS-Ratio 111.4`, and RS vs N500 `Flat` → `Rising`.
Price fixed + ratio moving points at the **benchmark leg settling after the close**, not a bar
shift. Mechanism NOT proven. It matters because the move crossed the LEADING/WEAKENING
boundary — the difference between `Q` passing and failing. Affected today: ANANDRATHI ×2,
HONASA ×2, CRISIL. To settle it: re-read one 15:30-batch name at 15:31 and again at 15:50 on
a day when v67's weekly bindings can be sampled directly.

## Proposed fixes (HELD)
1. **REV-01** — parse entry and stop independently of line layout: drop the `"stop:" not in low`
   guard in favour of taking the number that follows the *entry* token on that line, and add
   bare `buy` to the entry vocabulary. Python only: no compile, no re-bind, no alert recreation.
   Add the five fixtures above as a regression test.
2. **REV-03** — capture the child's stderr tail into `s4_alert_review.log` on a non-zero rc.
3. **REV-04** — have the prompt name which S5 sections are withheld, so §6 reports "withheld"
   instead of inventing a geometry read.

### AUD-REV-01 — FIXED (23 Sep, same session)

`s4_review.py`, three hunks, Python only — no compile, no re-bind, no alert recreation.

1. **Entry/stop by TOKEN POSITION, not line position.** New `_TOK` scanner: each token owns
   the text from itself to the next token, so layout and order stop mattering. `buy-stop` is
   consumed as an entry token and can never also register as a stop, which is what the old
   `"buy-stop" not in low` string test was for. A second entry token is tried when the first
   owns no number (`Entry:` followed by `Limit order at 52.45`).
2. **`market fill / market order / market entry` added to the entry vocabulary.** Bare
   `market` deliberately is NOT a token — it appears in prose, where it would own the wrong
   number.
3. **`_ruling_line` strips asterisks THROUGHOUT.** It was returning `RULING:** TAKE` for the
   `**RULING:**` form the model actually writes.

**Isolated against the committed baseline over all 222 recorded reviews** (both versions run
on the same inputs, so intervening fixes cannot be mistaken for this one):

| | |
|---|---:|
| identical | 174 |
| now parses (was the bug) | 19 |
| now correctly silent on a PASS / NO TRADE | 4 |
| **lost parsing** | **0** |
| **entry/stop changed on an already-parsing plan** | **0** |

Today's coverage: **33 of 34**, up from 18. The one that still declines is a `WAIT` whose
plan is prose with no entry/stop pair — declining loudly is the required behaviour there.

**A third dormant check came back with it.** `r_check:1078` escalates a sub-canon T1 when the
ruling is a TAKE — `"ruling is TAKE — the reward bar is NOT met on these numbers; use the
canon T1"`. It tests `ruling.startswith("RULING: TAKE")`, so against `RULING:** TAKE` it had
**never once fired**. It now appears on 25 historical reviews, including today's TVSMOTOR 75
(T1 1.29R under the 2R swing floor, ruled TAKE) and SAILIFE 125.

Regression test: `tests/test_r_check_plan_forms.py` — 7 real plan layouts taken verbatim from
the failing reviews, plus the recompute assertion, the loud-decline case and the PASS case.
10 pass; full suite 199 pass.

**STANDING: the receiver must be restarted** — alert-driven reviews run the `s4_review` module
loaded when the receiver started. `REVIEW.bat` and the CLI pick it up immediately.

### AUD-REV-03 and AUD-REV-04 — FIXED (23 Sep, same session)

**REV-03 — a failed review now says why.** The reason always existed: `review_one`
prints it to stderr (`"S4 is not on this chart (tables found: …)"`), but stderr goes to
the receiver's console window, which nobody watches and which does not persist — so
BAJAJ_AUTO 125 left `review rc 1` and no other trace anywhere. `s4_alert_review._run`
now wraps the review call in `contextlib.redirect_stderr` and, on a non-zero rc OR an
exception, puts the last three non-empty stderr lines into `logs/s4_alert_review.log`
AND into the Telegram failure message. On success the buffer is dropped. `_log` writes
to stdout, so the running commentary is untouched.

**REV-04 — the withheld S5 sections are now named to the model.** `SYSTEM` already said
"sections marked [withheld] are not available - do not guess them", and CPPLUS 125 still
wrote *"S5 confirms … the geometry is clean"*. A standing rule that names nothing is easy
to read past, so `build_prompt` now detects the withheld headings from the read itself and
puts them in the PRE-READ — the "computed by the script, not negotiable" block — as a fact
about THIS read, with the loophole closed explicitly ("not even to call them clean, quiet
or neutral"). §6 of SYSTEM points at that list and names the failure by example.

**Verified on the offending name.** Re-running CPPLUS 125 through the live model:

> **6. STRUCTURE (S5)** — Sections I, II, and VI are withheld. Based on the available
> data, there is no range-edge or Wyckoff accumulation event currently in play. The
> diagnostic section highlights the 200-DMA at 2501.4 as the floor …

The fabricated geometry claim is gone and the paragraph is built from the sections that
were actually present.

`tests/test_review_failure_visibility.py` — 7 tests: the stderr tail (content, bounding,
silence when empty), the rc-branch driven end to end through `_run` with a faked review
that fails the way the real one did, and the prompt (names every withheld section,
carries the "not even to call them clean" clause, claims nothing when nothing is
withheld). Full suite 206.

Caught while writing them: `_run`'s `finally` rebuilds the REAL Reviewer Log page, so the
first run of that test rewrote `docs/portal/31_reviewer_log_v2.html` — the side-effect
class `tests/conftest.py` exists to prevent. The rebuild is monkeypatched out and the
file's mtime is asserted unchanged.

**STANDING: restart the receiver again** — both files changed after the 17:00 restart.

### AUD-PAR-06 — FIXED (23 Sep)

The RRG "BUY OK" whitelist is now **two cells everywhere**: `LEADING → LEADING` and
`WEAKENING → LEADING`, the pair that survived the 18-Aug re-measurement (473 symbols,
93,745 weekly observations, matched-horizon alpha, chronological IS/OOS, bootstrapped by
SYMBOL). `IMPROVING → LEADING` — measured reliably NEGATIVE at −0.33 / −0.87 with the CI
excluding zero — is gone, along with `LEADING → IMPROVING` and `LAGGING → IMPROVING`,
which do not survive the split.

**What the bug actually was.** Both GATES were switched off on that 18-Aug evidence and
the DEFINITION was never narrowed with them. So `cf_w_rrg` went on awarding its +1
confluence point on all five cells — including the negative one — while its own tooltip
told the reader the point was for the measured two. Doc and code disagreed for five weeks,
and the doc was the one that matched the measurement.

**THREE copies, not one.** The predicate lives in `bull_screener._rrg_tradeable` (Python,
canonical → `RRG_Tradeable`, and the board's Gate 5), `S4Core.rrgInfo` (→ S4's Q chip, the
confluence point, `en_rrg_gate`) and v67's `f_rrg_info` (display only). Nothing mechanical
kept them equal, which is why the drift survived a re-measurement that was explicitly
about these cells.

**Blast radius, measured on the 515-trade validation set:** tradeable 220 → 156, so **64
names (12.4%) lose the chip and the point**. Every one is a dropped cell —
`LAGGING → IMPROVING` 49, `IMPROVING → LEADING` 15. Both gates remain OFF
(`RRG_GATE=False`, `en_rrg_gate=false`), so nothing is vetoed; what changes is the
confluence total and the BUY OK / Q display.

**NEW `tests/test_rrg_whitelist_parity.py`** is the mechanism that was missing. It pins the
Python predicate cell by cell, and reads the two Pine files' SOURCE for their `bool tr`
assignment — stripping comments first, since all three now describe the dropped cells in
prose directly above the code and a naive scan would match the history and always pass.
Mutation-checked: fed the five-cell form it reports drift. Suite 228.

**Pending on Jay, in this order** — the Pine half is not live until all of it is done:
1. Publish `S4Core.pine` → report the new version number.
2. I bump S4's `import jayramg/S4Core/55` to that number (never before it exists).
3. Recompile S4 and v67, run `BIND_S4_SOURCES.bat`, recreate both GO alerts.

`AUD-PINE-07` (the dead-band trajectory call, display-only) is still open and sits in the
same function — worth carrying on the same compile rather than paying a second cycle.

### AUD-PINE-07 — FIXED (23 Sep), and the original diagnosis was wrong

Carried on the same compile as AUD-PAR-06. Re-deriving it before writing the fix showed
the entry above had it backwards, so the correction is recorded rather than quietly
shipped.

**What the ledger said on 23-Sep morning:** that a quadrant CHANGE was being called off a
momentum delta inside the ±0.3 dead band, and that the fix was to require the
counter-clockwise secondary branch to carry a real y-component.

**That fix would have broken correct behaviour.** `LEADING → IMPROVING` is a crossing of
the line `v = 0` moving LEFT. It needs `dv` and needs no `dm` at all — demanding a y
component would have suppressed a legitimate transition. Checked all four branches: each
primary and each secondary requires the delta on the axis actually being crossed. The
trajectory logic is right, in all three surfaces, and always was.

**The real defect was the ARROW, and it was a parity drift.** S4Core's expression had no
branch for `dv < -0.3` with flat momentum, so a purely LEFT move fell through to `↙️` and
printed down-left beside an up-left label. It also printed `➡️` for a stationary point.
**v67's `f_rrg_info` and `bull_screener._rrg_trajectory` both already had `⬅️`/`←` and
`•`** — S4Core alone lagged. So the row Jay read as self-contradictory was exactly that:
a correct label next to a stale arrow.

Fixed by bringing S4Core into line; no threshold moved, no trajectory changed, and the
`tr` whitelist is untouched by this (AUD-PAR-06 handled that separately). Display-only, so
nothing scores differently.

`tests/test_rrg_whitelist_parity.py` extended to pin the arrow as well as the cells:
S4Core's glyph set must equal v67's, must contain a left-with-flat-momentum case, and must
print `•` rather than a direction when the point is not moving. Mutation-checked — fed the
old two-case form it reports 7 glyphs instead of 9 and fails. Suite 230.

**A latent inconsistency defused in passing:** `_rrg_trajectory` computes
`rs_ratio_centered = v_now - 100.0` on a value its own docstring calls "already centered",
and passes it to `_rrg_tradeable`. After AUD-PAR-06 that parameter is unused, so it can no
longer affect anything; a test pins that no value of it resurrects a dropped cell.


---

# 24 September 2026 — Full read: 27 Library pages + CLAUDE.md, against the code

Method: every Library page read in full (docs/portal, converted to text), plus
`AUDIT_LEDGER.md`, the two new F&O cheat sheets and CLAUDE.md; each claim checked at
file:line or re-measured. Market-hours rule waived by Jay for the day. **Nothing was changed
except this ledger** — an accidental baseline write by `docs_audit/code_truth.py` was reverted
with `git checkout` (the report-only checker is `truth_watch.py`). Fixes are PROPOSED and held.

## Five themes

1. **Evidence built on look-ahead.** The recovery backtest scores every historical anchor with
   TODAY's fundamentals; the growth-gate test uses quarters not yet published.
2. **Rules left live after their own test failed.** Derivative level rules (P3 failed 4/4),
   Wyckoff, round numbers and the old RRG whitelist still score or steer.
3. **The simulator does not trade the way the book does.** Time stops, OCO partials, the swing
   trail and the intraday PA battery all differ between live and backtest.
4. **No single owner for shared concepts.** Five stage definitions, three volume profiles,
   four time stops, two order gates, three sizing rules.
5. **Doctrine pages contradict each other and the code.** Doc 18 most of all.

## Findings

| ID | Sev | Location | One line |
|---|---|---|---|
| AUD-EVD-01 | **P0** | replay.run_recovery_replay → recovery_screener._fundamental_row :1342 | Recovery replay pins OHLCV only; RFF reads the LIVE screener.in pool/page + yfinance `.info`. Every recovery backtest — and the "best-evidenced gate in the repo" (RFF≥5, +2.40pp, Doc 09 §14 / Doc 25* §07) — is look-ahead biased |
| AUD-EVD-02 | P1 | fundamental_replay._latest_quarter_on_or_before :209 | Takes any quarter ENDED ≤ anchor with no reporting lag (NSE: up to 45d, 60d for Q4). Mid-month anchors in Jan/Apr/Jul/Oct use unpublished quarters — the growth-gate (+1.31pp) evidence is partially look-ahead |
| AUD-REV-06 | **P0** | s4_review.py prompt :663-670, level_check :1003-1018; Doc 32 §08b | P3 (22 Sep 19:54) FAILED all four derivative hypotheses; H1 and H4 INVERTED (T1 beyond the call wall reached MORE often — SWG-PB +13.3pp, CI excludes 0). The reviewer (last commit 23 Sep, after P3) still instructs capping T1 before the call wall and flags put-wall stops and max-pain paths |
| AUD-DOC-01 | P1 | docs/portal/fo_cheat_sheet_*.html (untracked) | Teach the P3-rejected rules as an execution protocol; "close before THURSDAY expiry" — NSE monthly expiry is TUESDAY (fno_history: 12 of the 16 recent expiries); recovery targets 2R/4R vs canon 3R/5R; "long build-up → full aggression, else pullbacks only" is a gate despite "never gate" |
| AUD-OPS-01 | **P0** | pre_trade_gate.py:41 | MAX_OPEN_POSITIONS default 15, no .env override; journal OPEN = 22 → every gated NEW buy (Streamlit CNC, MCP, n8n) is refused. Adds pass (existing symbol) |
| AUD-OPS-02 | P1 | gm_settings.json risk_pct 1.0 vs S4 size_risk 0.25 (:1248) | GM guided-execution sizes a new entry at 1%, S4's Qty row at 0.25% — 4× the quantity for the same trade. Docs disagree too: CLAUDE.md DNA 1% · Doc 25 0.25% new / 1% adds · Doc 26 "1%" · Doc 18 0.75% · Doc 13 0.5–1.25% |
| AUD-PAR-07 | P1 | Weinstein_Unified_Ecosystem_v3.4.pine:784-786, :1805 | AUD-PAR-06 (23 Sep) narrowed the RRG whitelist in Python/S4Core/v67 but not in Unified (still 5 cells). Unified's entry gate `rs_ok` admits LEADING **or IMPROVING** while its own note (:1914) measures RS-Ratio<100 at −0.64% |
| AUD-PAR-08 | P1 | Commander_Chart_Markup_v2.0.pine:439-440; Unified stage | Stage has five definitions. Markup: no flat band, 6-week slope, flat counts as rising, below-rising → 1. Unified: below-rising → 1 where S4/Python/v67 give 2. Doc 20 claims "zero drift by intent"; Doc 25's appendix says "all four surfaces" agree |
| AUD-PAR-09 | P1 | zone_engine.vp_support :1301-1330 vs S4 vp_lookback :3501 | Board VP location = 120 bars, typical-price single-bin (the method Doc 03 §02 calls wrong); S4 = 100 bars, overlap-weighted. Board and chart can disagree on "at VAL/POC". volume_profile.py is a third (120d / 50 bins) |
| AUD-PAR-10 | P2 | weinstein_commander_web_v4.0.py:3495-3518; Docs 23/04 | Board location and stop still admit order blocks (S4 removed them 16 Jul); the board SL resets to 2.5×ATR past 3×ATR while S4 caps by trade type (swing 2.5 / pos 4.0). The board's Step-4 "R:R ≥ 2.0" is computed on a different stop |
| AUD-PAR-11 | P2 | sniper_trigger.py:297-299 vs pre_trade_gate.py:41-43 | Two order gates: sniper sector cap 35%, no position cap, 20% capital per stock; pre_trade_gate 25% / 15 positions / 1.5% risk. Bible §3 says the gate's cap is imported by every order surface — sniper does not |
| AUD-SIM-01 | P1 | replay NO_TIME_STOP (5 Aug); pyramid_logic:255-257; v67:991-992; Unified:340,377 | Four time stops: backtest none · pyramid 180/60d · v67 36wk/60d (tooltips still say 6W/10D) · Unified 6wk/10d/15d. The live EXIT rung's time stop is untested |
| AUD-SIM-02 | P1 | Risk Allocator v2.2 split default 50/50; replay partial_qty_for 25/25 | Live OCOs cover 100% of the position (no runner); the backtest's edge lives in the 50% runner (88% of POS exits on the trail). The book does not run the tested structure |
| AUD-SIM-03 | P1 | replay._simulate_one_trade trail_atr_mult=4.5 for every family | Swing trades trail at 4.5× in every validation run; live trails swing at 1.5× on a 14-bar window (recorded in PREREG_exit_policy Amendment 1) |
| AUD-SIM-04 | P1 | S4 use_chart_tf ON; GM intraday battery; Doc 08 §01 | Doc 08: pattern alphas "validated on DAILY only … do not transfer to intraday; do not trust the tier output intraday". The P gate of every GO runs the battery on 75/125m |
| AUD-CF-01 | P2 | S4 :1277-1280, :4063-4165; S4Core :1995, :2263/2299/2326 | Confluence still pays WCL +2, round +1, RRG +1 (all measured failed), prints "TAKE IT ★strong", and the SUMMARY calls its terms "independent facts" (the panel-row audit found the context rows correlated ≥0.6 and no row carrying IC) |
| AUD-EVD-03 | P2 | Doc 25 Part 10b "Where to enter, relative to the EMA20" | The table is a family split, not an extension effect: the <1 ATR bins are 321/337 SWG-PB, the ≥1 ATR bins 175/175 POS. "Don't wait back to the EMA20 — under 1 ATR stop-outs run 70–75%" is SWG-PB's stop rate |
| AUD-PY-13 | P2 | docs_audit code_truth: rev_screener_t1_r 2.5 vs rev_canon_t1_r 3.0 | The recovery screener emits T1 at 2.5R against the 3R canon |
| AUD-PINE-08 | P3 | v67:5850-5851 | v67 still computes and plots `s4_mlWinProb`; S4 dropped the binding 21 Sep. Dead export, one plot slot |
| AUD-DOC-02 | P1 | docs/portal/18_trade_funnel.html (listed as Doctrine) | Contradicts ≥8 measured or current rules: Wyckoff DISTRIBUTION disqualifier (measured backwards), IMPROVING→LEADING "sweet spot" (measured negative), ADX/wRSI gates (removed in the PA conversion), Strike.Money (retired), risk 0.75% / max 6 positions / ₹25k cap, the legacy exit table, scorecard sizing, buy-stop entries |
| AUD-DOC-03 | P2 | Docs 16, 25, 27 | Describe exits at the catalyst horizon ("time expiry", "never test outside these", the forward_days_used check) — removed 5 Aug; the windows no longer set any exit |
| AUD-DOC-04 | P2 | Docs 00, 01, 02, 03, 07, 13, 22, 23, 32 + CLAUDE.md | Stale or wrong claims — detail list below |
| AUD-OPS-03 | P3 | DOCS_TRUTH_CHECK.bat; docs_audit/code_truth.json (baseline 9 Sep) | Doc 26 lists it as a daily post-close job; it is in no scheduler. Baseline not re-accepted since 9 Sep; 5 pages flagged today. It watches ~47 constants, so none of the findings above could have been caught by it |

## AUD-DOC-04 — stale claims, page by page

- **00 Bible** — GO is four gates (five since 1 Sep); S4-GO "n/4"; phase 6·7 "sync to Strike"; 15:45 trail "currently disarmed" (live since 9 Sep); "nothing here has been superseded" while mistake #22 (a breakout needs a squeeze) is the June POS-blackout bug.
- **01 Structure** — "no longer feeds the stage read" (it is the stage tie-break on S4 :3189 and in bull_screener, where the variable is misnamed `rs_up`); equal threshold "0.5% / 0.3%" vs code 0.2% (Zigzag :148, strict_trend :68).
- **02 Wyckoff** — "does not rank" (it scores +2 in confluence, whose documented job is ranking); recovery Wyckoff catalysts "validated … the priority recovery edge" (WYC-SOS −2.06% / −0.40% in the two re-baselines).
- **03 Volume profile** — "survived measurement" was a fire rate (~18%), never an outcome test; the panel-row audit found no IC.
- **07 Mission Control** — the journal "opens in its own window" (ported in-app 23 Sep); the swing workflow says "buy-stop, never a limit" against the retest default; RRG ranking "improving beats weakening".
- **13 Unified** — "Python does not map below-rising to Stage 2 either" (it has since 20 Sep).
- **22 / 25 / 13** — the stage tie-break is labelled "RS"; the code reads the Zigzag strict trend and falls back to the RS slope only when unbound.
- **23 Golden Matcher** — ⚠noedge cites run 20260810 (now 20260920); the re-baseline table's "Neither correction 400 / −0.88 / −2.38 / 33.8" row IS the recovery run mislabelled as bull (also in CLAUDE.md, 19 Aug block); "the one rule: buy-stop above a closed bar" and guided-exec step 4 against the measured retest default; Step 2 still lists "ML probability".
- **32 Reviewer** — doctrine "RRG LEADING / IMPROVING"; "S4 pairs OI with the last chart-TF bar" (fixed 12 Sep per Doc 22).
- **09 / 10 / 11 / 18 / 23** — "leading or improving" accepted as a rotation floor in five places; only L→L and W→L measured positive.
- **15 / 18 / 20** — setup-, scorecard- and conviction-based size multipliers (1.25× / full / half) — none outcome-tested.
- **CLAUDE.md DNA** — web app `weinstein_commander_web_v2.5.py` (it is v4.0); RS "Mansfield, 52-wk primary" (the engine is JdK strike_cal; the `mansfield` fields hold JdK−100); "risk per trade 1%" (house rule 0.25% new entries).

## Observation, not a finding

`FINAL_Portfolio_Picks.csv` (23 Sep): of 22 holdings the ladder rates **5 EXIT, 7 REDUCE,
3 TRIM, 5 HOLD, 2 ADD**.

## Proposed order of work (HELD — Jay's call)

1. **Ops, small:** set MAX_OPEN_POSITIONS to the book's real policy; make GM's new-entry risk
   read the same 0.25% as S4, from one source.
2. **Stop enforcing rejected rules:** remove the call-wall / put-wall / max-pain directives from
   the reviewer prompt and level_check (keep them as displayed facts); retire or correct the
   F&O cheat sheets (Tuesday expiry). Zero the WCL / round / RRG confluence weights; drop ★strong.
3. **Redo the evidence:** a point-in-time RFF (as-of fundamentals with a reporting lag) before
   the RFF=5 gate is cited again; add the lag to fundamental_replay.
4. **One owner per concept:** stage (retire Markup's and Unified's variants), VP, time stop, OCO
   structure — then make the backtest trade what the book trades, or the reverse.
5. **Docs:** move Doc 18 out of Doctrine; fix 16/25/27 on time stops and the page list above;
   schedule and re-baseline DOCS_TRUTH_CHECK.
