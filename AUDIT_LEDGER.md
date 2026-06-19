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
- **XRay (`weinstein_xray_screener`) — output CLEAN/fresh.** `FINAL_XRay_Picks.csv` regenerated today (25 syms from FINAL_WATCHLIST), Minervini/Piotroski/ROE/PE/DE populated. (Deeper logic check of the M:/P: checklist math still pending.)
- **Bull regime gate — CLEAN logic.** "NOT BULL" was correct: requires `close>SMA200 AND SMA50>SMA200`; SMA50<SMA200 currently → bull POS catalysts intentionally suppressed. Conservative-by-design, not inverted.
- **P0 enrichment — CONFIRMED in output.** `FINAL_Hunter_Picks.csv` etc. now fully enriched + sorted by Combined_Score; file counts consistent across the pipeline (Hunter 2 / Pullback 6 / EB 1 / Leader 5 / RS 9 / RecEB 18 / Combined 29 / Watchlist 25 / XRay 25).

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
