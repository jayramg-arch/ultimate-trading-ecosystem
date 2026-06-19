# Trading Ecosystem — End-to-End Data & Ranking Audit

**Date:** 19 June 2026
**Branch:** `phase0-1-attribution-journal-snapshot`
**Trigger:** CSV watchlists were missing required metrics, corrupting final rankings, after the migration from free yfinance to paid **Dhan Data API + Screener.in premium**.

---

## TL;DR — two systemic problems, both fixed

1. **🟢 (was 🔴) The Dhan paid feed was completely dead — every fetch silently fell back to free yfinance. Now fixed and live.**
   The loud-logging instrumentation immediately exposed it. Three stacked root causes, all in the data path (`dhan_ohlcv.py`):
   - **Expired token (`DH-901`):** the data path read the raw `DHAN_ACCESS_TOKEN` from env (which expires daily) while the *journal* path auto-refreshed via `dhan_auth`. → **Fixed:** `_get_client()` now calls `dhan_auth.get_valid_token()` (TOTP auto-refresh — your `DHAN_PIN`/`DHAN_TOTP_KEY` are already in `.env`, so this works with no manual step).
   - **Missing `client-id` header (`DH-905`):** the Dhan v2 `/charts/historical` endpoint requires **both** `access-token` *and* `client-id` headers; the `dhanhq` SDK sends only `access-token`, so *every* historical call failed. → **Fixed:** inject `client-id` into the client header.
   - **No Dhan rate-limiting (`DH-904`):** under a 500-symbol screen the data path hammered Dhan and got rate-limited, losing those symbols to yfinance. → **Fixed:** added a Dhan throttle (~4 req/s) + one backoff retry on `DH-904`.
   - **Verified:** RELIANCE/TCS/SBIN/HDFCBANK/COALINDIA/GESHIP/INFY/ITC/LT all now return **`dhan`** as source (1238 daily bars each, deeper than yfinance's ~250), 0 fallbacks.

2. **🟢 (was 🔴) The ranking bug (your actual symptom): individual watchlists were saved before enrichment. Fixed.**
   `brute_force_match_pro.py` wrote each `FINAL_*.csv` (Hunter/EarlyBird/Leader/Pullback) **before** technical enrichment ran, leaving `Combined_Score, Tech_Score, Stage, Mansfield_RS, Daily_RSI, Daily_ADX, EMA_Stack, Above_200DMA, Dist_52WH_pct, Vol_RelAvg` **blank**. Only the combined file got enriched. Any ranking off those blank `Tech_Score` values used `(Conviction×10×0.5)+(0×0.5)` → misleading. **Fixed:** enrich each per-edge frame before saving, reuse for the combined files.

These compound: with the feed now live, the enriched metrics are computed on **deep Dhan data** (5y) rather than yfinance's truncated ~2y — directly improving the ranking quality you were worried about.

---

## Fixes applied (all syntax-verified; enrichment + loud-feed paths runtime-verified)

### P0 — Ranking bug — `brute_force_match_pro.py`
- Each per-edge `merged` frame is now enriched via `technical_enrichment.enrich_dataframe` **before** `save_with_golden_schema`, and sorted by `Combined_Score` desc.
- The enriched frame is stored in `results_dict` and **reused** when building the combined files (`_enrich_and_rank` now detects already-enriched frames via `_is_enriched` and only re-sorts — no double fetch).
- Removed the duplicate enrichment-helper block that previously only ran for combined files.
- **Verified:** `enrich_dataframe` populates all 10 metric columns + `Tech_Score`/`Combined_Score` (non-null) on a live 2-symbol test.

### P0 — Dhan paid feed brought back to life — `dhan_ohlcv.py`
- **Auto-refresh token in the data path:** `_get_client()` now uses `dhan_auth.get_valid_token()` (validates JWT expiry, TOTP-refreshes if stale) instead of the raw env token — fixes `DH-901`.
- **`client-id` header injected** into the dhanhq client so the v2 `/charts/historical` endpoint accepts requests — fixes `DH-905`.
- **Dhan throttle + retry:** `_throttle_dhan()` (~4 req/s, env-tunable `DHAN_MIN_INTERVAL_S`) before each call, plus one backoff retry on `DH-904` rate-limit — keeps the paid feed under screening load.
- **Silent failure made loud:** `_note_dhan_failure()` surfaces the real reason once (ASCII banner, no cp1252 crash), detects expired auth and fast-fails the rest of the run instead of issuing one doomed call per symbol.
- Scrip-master staleness guard: if the weekly refresh download fails, warn loudly and use the stale cache (or hard-fail if no cache) instead of silently using old symbol mappings.
- **Verified:** 10/10 large-caps now resolve to `dhan` with deep history; auth-failure banner fires once and fast-fails without crashing.

### P1 — Feed visibility — `data_provider.py`
- Startup banner (once): `Dhan=ON/OFF | nselib | nsepython | cache=parquet`; hard warning when Dhan is OFF.
- Per-fetch source tagging: `get_last_source(symbol)`, `get_source_counts()`, `feed_status_banner()`.
- Every Dhan→fallback transition now logs at INFO (was debug); the "no data from any provider" case logs a WARNING (no silent empty).
- **Verified:** banner prints the live feed; `get_last_source` correctly reports `dhan`/`cache`/`yfinance`/`none`.

### P1 — yfinance bypass routing (the metric/ranking-critical engines)
- `bull_screener.py`, `technical_enrichment.py`, `etf_screener.py`, `etf_rotation.py`, and `brute_force_match_pro.py`'s weekly stage-gate all route OHLCV through `data_provider` (Dhan-first) with yfinance as a **loud** fallback. The one true direct call (`etf_rotation.py` liquidity volume) was rerouted through `data_provider.fetch_batch_ohlcv` (which carries Volume), yfinance loud-fallback retained.
- `bull_screener` now prints a warning if `data_provider` itself fails to import (whole-module yfinance bypass).

### P1 — Recovery RFF transparency — `recovery_screener.py`
- Added `Fund_Source` column (Screener.in / yfinance / unavailable) to output rows.
- After each run: prints fundamental-source coverage (% Screener.in vs yfinance vs unavailable) and RFF-quality counts, and **flags actionable signals (Signal≥2) not backed by Screener.in premium**.
- `load_fundamentals` warns loudly when a Screener.in CSV is older than 35 days (stale fundamentals were scored as "FULL").

### P2 — Backtest point-in-time integrity — `validation.py`
- `main()` prints the active data feed at run start and warns hard if Dhan is OFF (replays on yfinance mix corporate-action adjustment & holiday calendars → biased point-in-time results).

---

## Residual risks / deferred (not changed this pass)

- **Throttle tuning:** the Dhan throttle defaults to ~4 req/s. If you still see occasional `DH-904` on a full 500-symbol run, raise `DHAN_MIN_INTERVAL_S` (e.g. `0.35`). Symbols that hit a transient limit fall back to yfinance loudly (not silently).
- **dhanhq SDK (2.0.2)** omits the `client-id` header for `/charts/historical`; we patch it at the client. If you upgrade the SDK, re-verify the header patch is still needed.
- **Secondary modules — audited 19 Jun 2026 (mostly already routed).** On inspection, `ai_risk_manager.py`, `portfolio_analytics.py`, `ai_grading_engine.py`, `python_backtester.py`, `pullback_scanner.py`, `breadth_engine.py`, `quant_analyst.py` were **already** `data_provider`-first with yfinance only as a fallback (the earlier flag was on the `import yfinance` line, not the calls). Genuine bypasses fixed this pass:
  - `deep_analysis.py` — `get_technical_context` + `check_market_health` were raw `yf.download`; now `data_provider`-first (benchmark switched to canonical `^CRSLDX`). Verified COALINDIA → `dhan`.
  - `market_data_hub.py` — the Nifty-50 "Key Movers" fetch was raw `yf.download`; now `data_provider.fetch_batch_ohlcv` with loud yfinance fallback. (Its `^`-index fetches intentionally stay on yfinance — Dhan doesn't serve `^` indices.)
  - `ai_fundamental_engine.py` — `fetch_fundamental_data` pulled Indian fundamentals from yfinance `.info`; now overlays **Screener.in premium** (via `fundamental_hub`) on the accuracy-critical fields (P/E, ROE, D/E, promoter, growth, market cap), unit-matched, with a `Data_Source` stamp. Verified RELIANCE → `Screener.in+yfinance`.
- **Remaining minor (display/narrative only, low impact):** `portfolio_analytics.get_sector` and `quant_analyst` line ~537 use `yf.Ticker().info` for sector/misc lookups; `^INDIAVIX` and other `^`-indices come from yfinance by design. None affect watchlist rankings or trade decisions.
- **Cache mixing:** within one run, cached bars may be from a different source than a later live fetch. Low impact in live mode; matters most for pinned/replay — now at least the feed is announced.
- **Stale worktrees** under `.claude/worktrees/*` contain old copies and were intentionally out of scope.

---

## What to do next (you)
1. **Re-run the matcher pipeline** (Golden Matcher / `brute_force_match_pro.py`). Confirm each `FINAL_*.csv` now has populated metrics and is ranked by `Combined_Score`. The paid feed is already live — no manual token step needed (auto-refresh handles it).
2. **Clear stale yfinance-sourced cache** so the deeper Dhan history takes over: the parquet cache in `data/market_cache/` may hold yfinance bars from before this fix. Either delete it or let TTLs expire; fetches with `use_cache=False` already confirmed `dhan` sourcing.
3. Re-run the recovery screener; confirm the coverage line shows a high Screener.in % and watch for the `Fund_Source`/`RFF_Quality` columns.
4. Spot-check the startup banner shows `Dhan=ON` and that `source counts` are dominated by `dhan` (not `yfinance`) on a real run.
