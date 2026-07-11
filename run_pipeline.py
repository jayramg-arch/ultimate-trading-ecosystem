
import sys
import os
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Import application modules
try:
    import chartink_scanner_pro
    import screener_fetcher
    import screener_processor
    import brute_force_match_pro
    import watchlist_manager # Added for Auto-Pilot
    from pipeline_status import PipelineRun  # E9: per-phase status writer
    from kill_chrome import kill_automation_chrome
except ImportError as e:
    print(f"❌ Critical Import Error: {e}")
    input("Press Enter to exit...")
    sys.exit(1)

_DIR = os.path.dirname(os.path.abspath(__file__))


import logging

def setup_logging():
    logger = logging.getLogger("AutoPilot")
    logger.setLevel(logging.INFO)
    
    import datetime as _dt
    log_path = os.path.join(_DIR, f"auto_pilot_{_dt.datetime.now():%Y%m%d_%H%M%S}.log")
    
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    console_handler = logging.StreamHandler(sys.__stdout__)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, log_path


def _load_bull_universe(logger):
    """Load the broad bull-scan universe (catalyst-first). Returns a list of plain
    NSE symbols (no .NS suffix), or None to fall back to bull_screener's default
    FINAL_COMBINED_BULL_PICKS.csv matcher list.

    Why broad: a catalyst is a time-localized event. Scanning only the ~10
    fundamentally-pre-filtered matcher names almost never fires one (funnel: 10
    in -> ~1 out). The POS-BO edge was validated on Nifty 500, so we scan that.

    Source order: env BULL_SCAN_UNIVERSE (path to .json list or .csv) ->
    nifty500_symbols.json. A missing/unreadable file is non-fatal -> None
    (legacy matcher behaviour preserved).
    """
    import json
    src = os.getenv("BULL_SCAN_UNIVERSE", os.path.join(_DIR, "nifty500_symbols.json"))
    if not os.path.exists(src):
        logger.warning(f"⚠️  Bull universe file not found ({src}); falling back to "
                       f"Golden Matcher list (FINAL_COMBINED_BULL_PICKS).")
        return None
    try:
        if src.lower().endswith(".json"):
            with open(src, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            import pandas as pd
            _df = pd.read_csv(src)
            _col = next((c for c in _df.columns
                         if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                        _df.columns[0])
            raw = _df[_col].dropna().astype(str).tolist()
        syms = []
        for s in raw:
            s = str(s).strip().upper().replace("NSE:", "").replace("BSE:", "")
            for suf in (".NS", ".BO", ".NSE"):
                if s.endswith(suf):
                    s = s[:-len(suf)]
            if s and not s.isdigit():
                syms.append(s)
        syms = sorted(set(syms))
        logger.info(f"  Bull universe: {len(syms)} symbols from {os.path.basename(src)} "
                    f"(catalyst-first broad scan).")
        return syms or None
    except Exception as e:
        logger.warning(f"⚠️  Failed to load bull universe ({e}); falling back to "
                       f"Golden Matcher list.")
        return None


def main():
    logger, log_path = setup_logging()
    logger.info(f"[log] Auto-Pilot console log -> {log_path}")

    # Clear any stale automated Chrome processes before starting the pipeline
    try:
        kill_automation_chrome()
    except Exception as ce:
        logger.warning(f"Warning: Pre-run Chrome cleanup returned: {ce}")

    logger.info("="*60)
    logger.info("🚀 WEINSTEIN COMMANDER: FULL AUTO-PILOT")
    logger.info("="*60)
    logger.info("This will execute the entire workflow:")
    logger.info("1. Run ALL Technical Scanners (Chartink)")
    logger.info("2. Fetch Fundamental Data (Screener.in)")
    logger.info("3. Process Data")
    logger.info("4. Run Golden Matcher")
    logger.info("5. Run Recovery Screener")
    logger.info("6. Run Bull Screener")
    logger.info("7. Generate Local Watchlists")
    logger.info("8. Sync to Strike.Money")
    logger.info("-" * 60)

    # E9: pipeline status tracker — writes pipeline_status.json after every phase
    run = PipelineRun(label="Auto-Pilot Pipeline")

    # 0. PRE-FLIGHT CLEANUP — clear leftover Playwright browsers / profile locks
    # / temp files / duplicate pick_log rows from a prior hung run, so running
    # the auto-pilot multiple times in a short span starts clean each time.
    # Non-fatal: cleanup problems never block the run.
    logger.info("\n[PHASE 0] PRE-FLIGHT CLEANUP...")
    with run.phase("Phase 0 — Pre-flight Cleanup") as p:
        try:
            import pipeline_cleanup
            _cl = pipeline_cleanup.preflight_cleanup(verbose=True)
            p.message = (f"browsers={_cl['browsers_killed']} locks={_cl['locks_removed']} "
                         f"temp={_cl['temp_removed']} pick_log_dupes={_cl['pick_log_deduped']}")
        except Exception as e:
            logger.warning(f"⚠️  Pre-flight cleanup skipped: {e}")
            p.status = "SKIP"
            p.message = f"skipped: {e}"

    # 1. RUN ALL CHARTINK SCANS
    logger.info("\n[PHASE 1] RUNNING TECHNICAL SCANNERS...")
    with run.phase("Phase 1 — Chartink Scanners") as p:
        scan_keys = ['1', '2', '3', '4', '5', '6', '7']
        ok_count = 0
        for key in scan_keys:
            try:
                chartink_scanner_pro.run_scan(key)
                ok_count += 1
                time.sleep(1) # Polite delay
            except Exception as e:
                logger.error(f"❌ Error running scan {key}: {e}")
        p.records = ok_count
        p.message = f"{ok_count}/{len(scan_keys)} scans completed"

    # 2. FETCH FUNDAMENTALS
    logger.info("\n[PHASE 2] FETCHING FUNDAMENTAL DATA...")
    with run.phase("Phase 2 — Screener.in Fundamentals") as p:
        try:
            screener_fetcher.fetch_screener_data(interactive=False)
            p.message = "fetch complete"
        except Exception as e:
            logger.error(f"❌ Error fetching data: {e}")
            raise

    # 3. PROCESS HTML
    logger.info("\n[PHASE 3] PROCESSING DATA...")
    with run.phase("Phase 3 — Process HTML") as p:
        try:
            screener_processor.process_screener_pages()
            p.message = "HTML processed"
        except Exception as e:
            logger.error(f"❌ Error processing HTML: {e}")
            raise

    # 4. GOLDEN MATCHER
    logger.info("\n[PHASE 4] RUNNING GOLDEN MATCHER...")
    match_summary = ""
    with run.phase("Phase 4 — Golden Matcher") as p:
        try:
            results = brute_force_match_pro.perform_match(return_raw=True)
            total_matches = 0
            if results:
                for strategy, val in results.items():
                    if isinstance(val, tuple):
                        mode, df = val
                    else:
                        df = val
                    if not df.empty:
                        match_summary += f"✅ {strategy}: {len(df)} matches\n"
                        total_matches += len(df)
            p.records = total_matches
            p.message = match_summary.strip().replace("\n", " | ") or "no matches"

            if match_summary:
                logger.info(f"🌟 Matching Summary:\n{match_summary}")
                # Trigger Push Notification
                try:
                    import telegram_sentinel
                    import asyncio
                    push_msg = f"🌟 *GOLDEN MATCH DETECTED* 🌟\n\nPipeline found high-conviction setups:\n{match_summary}\nCheck your journal for tactical entry!"
                    asyncio.run(telegram_sentinel.send_push_notification(push_msg))
                except Exception as pe:
                    logger.warning(f"⚠️ Telegram Push Failed: {pe}")
        except Exception as e:
            logger.error(f"❌ Error in matching: {e}")
            raise

    # 4.5. RECOVERY SCREENER (Python edition — signal hold-window aware)
    logger.info("\n[PHASE 4.5] RUNNING RECOVERY SCREENER...")
    with run.phase("Phase 4.5 — Recovery Screener") as p:
        try:
            import recovery_screener
            recovery_screener.main()   # BUG-C2: no longer calls os.chdir() — CWD safe
            p.message = "recovery scan complete"
        except Exception as e:
            logger.error(f"❌ Error in recovery screener: {e}")
            raise

    # 4.6. BULL SCREENER (catalyst scoring on FINAL_COMBINED_BULL_PICKS.csv)
    # Unchanged matcher-first run: tags whichever of the curated Golden Matcher
    # names happen to be firing a catalyst today. Writes Bull_Screener_Results.csv
    # (the "Bull_Screener" TV watchlist). Note: a catalyst is a time-localized
    # event, so this curated-set run usually surfaces few/none — that is expected;
    # Phase 4.7 below is the catalyst-FIRST broad scan that actually surfaces them.
    logger.info("\n[PHASE 4.6] RUNNING BULL SCREENER...")
    with run.phase("Phase 4.6 — Bull Screener") as p:
        try:
            import bull_screener
            def _bull_progress(idx, total, sym):
                if idx == 1 or idx == total or idx % 10 == 0:
                    logger.info(f"  Bull Screener [{idx}/{total}]: {sym}")
            # strict=True: batch-pipeline writes Bull_Screener_Results.csv consumed
            # by downstream tools that expect catalyst-firing rows only.
            df_bull = bull_screener.run_bull_screener(progress_callback=_bull_progress, strict=True)
            if df_bull is not None and not df_bull.empty:
                logger.info(f"✅ Bull Screener: {len(df_bull)} catalyst signals found.")
                p.records = len(df_bull)
                p.message = f"{len(df_bull)} catalyst signals"
            else:
                logger.info("ℹ️  Bull Screener: no catalyst signals fired.")
                p.records = 0
                p.message = "no catalyst signals"
        except FileNotFoundError as e:
            logger.warning(f"⚠️  Bull Screener skipped — input missing: {e}")
            p.status  = "SKIP"
            p.message = f"input missing: {e}"
        except Exception as e:
            logger.error(f"❌ Error in Bull Screener: {e}")
            raise

    # 4.7. BULL CATALYST BROAD SCAN — CATALYST-FIRST (new 26 Jun 2026)
    # ----------------------------------------------------------------------
    # The matcher-first Phase 4.6 scans only ~10 pre-filtered names, so the
    # weinstein funnel collapses 10→~1 and catalysts rarely surface. The POS-BO
    # edge (+7.67%/PF 3.14) was VALIDATED on the broad Nifty 500 universe, so we
    # scan that catalyst-first here. Fundamental conviction is joined INSIDE
    # run_bull_screener (conviction_passthrough → Combined_Score), so names that
    # are BOTH firing a catalyst AND fundamentally sound rank to the top.
    #
    # Output is a SEPARATE new watchlist — FINAL_CATALYST_WATCHLIST.csv — so it
    # NEVER overwrites FINAL_WATCHLIST.csv (Golden Matcher) or Bull_Screener_
    # Results.csv. Universe overridable via env BULL_SCAN_UNIVERSE; falls back to
    # the legacy matcher list if the broad file is missing.
    CATALYST_WATCHLIST = "FINAL_CATALYST_WATCHLIST.csv"
    logger.info("\n[PHASE 4.7] RUNNING BULL CATALYST BROAD SCAN (catalyst-first)...")
    with run.phase("Phase 4.7 — Bull Catalyst Broad Scan") as p:
        try:
            import bull_screener
            bull_universe = _load_bull_universe(logger)   # None => legacy matcher CSV
            _uni_n = len(bull_universe) if bull_universe else "matcher-list"
            def _cat_progress(idx, total, sym):
                if idx == 1 or idx == total or idx % 25 == 0:
                    logger.info(f"  Catalyst Scan [{idx}/{total}]: {sym}")
            df_cat = bull_screener.run_bull_screener(
                progress_callback=_cat_progress, symbols=bull_universe,
                strict=True, out_file=CATALYST_WATCHLIST)
            if df_cat is not None and not df_cat.empty:
                # CURATE for decision-readiness: (1) drop Stage-4 swing breakouts
                # (buying a breakout in a confirmed downtrend — marginal/negative
                # edge per per-family validation), then (2) order the POS family
                # first (the proven +7.67%/PF-3.14 edge) and by Combined_Score
                # within each tier. POS-* are kept regardless of stage.
                n_dropped = 0
                try:
                    _drop = (df_cat["Catalyst"].isin(["SWG-BO", "SWG-GAP"]) &
                             (df_cat["Stage"] == 4))
                    n_dropped = int(_drop.sum())
                    df_cat = df_cat[~_drop].copy()
                    _tier = {"POS-BO": 0, "POS-ACCUM": 1, "SWG-GAP": 2,
                             "SWG-BO": 3, "SWG-PB": 4, "SWG-REV": 5}
                    _sort_col = "Combined_Score" if "Combined_Score" in df_cat.columns else "Score"
                    df_cat["_tier"] = df_cat["Catalyst"].map(lambda c: _tier.get(c, 9))
                    df_cat = (df_cat.sort_values(["_tier", _sort_col], ascending=[True, False])
                                    .drop(columns="_tier"))
                    df_cat.to_csv(os.path.join(_DIR, CATALYST_WATCHLIST), index=False)
                except Exception as _ce:
                    logger.warning(f"   Catalyst curation skipped ({_ce}); raw output kept.")
                # HARD FUNDAMENTAL GATE (Jay, 6 Jul 2026) — the bull catalyst
                # list had no fundamental floor (only a sparse Conviction rank).
                # Score each FIRING name with the recovery engine's RFF (zero-
                # drift via recovery_screener.get_rff) and DROP names below the
                # recovery floor (base ≥ 4/6 AND quality ≠ INSUFFICIENT). Only
                # the ~firing names are scored, so the live fundamental fetch is
                # cheap. Disable with env CATALYST_RFF_GATE=0.
                if os.environ.get("CATALYST_RFF_GATE", "1").strip().lower() not in ("0", "false", "off", "no"):
                    try:
                        import recovery_screener as _rs
                        _fmap  = _rs.load_fundamentals()
                        _floor = float(_rs.CONFIG.get("rff_min_score", 4))
                        _bases, _quals = [], []
                        for _sym in df_cat["Symbol"].astype(str):
                            _b, _bo, _t, _q, _src = _rs.get_rff(
                                _sym, _fmap.get(_sym.strip().upper()), allow_live=True)
                            _bases.append(_b); _quals.append(_q)
                        df_cat["RFF_Base"]    = _bases
                        df_cat["RFF_Quality"] = _quals
                        _n_before = len(df_cat)
                        _keep = (df_cat["RFF_Base"] >= _floor) & (df_cat["RFF_Quality"] != "INSUFFICIENT")
                        _n_gated = int((~_keep).sum())
                        df_cat = df_cat[_keep].copy()
                        df_cat.to_csv(os.path.join(_DIR, CATALYST_WATCHLIST), index=False)
                        logger.info(f"   RFF fundamental gate: kept {len(df_cat)}/{_n_before} "
                                    f"(dropped {_n_gated} with RFF<{_floor:.0f}/6 or INSUFFICIENT)")
                    except Exception as _ge:
                        logger.warning(f"   RFF fundamental gate skipped ({_ge}); ungated list kept.")
                logger.info(f"✅ Catalyst Scan: {len(df_cat)} catalyst signals from "
                            f"{_uni_n} symbols → {CATALYST_WATCHLIST}"
                            + (f" (dropped {n_dropped} Stage-4 swing BO)" if n_dropped else ""))
                try:
                    logger.info(f"   Catalysts: {df_cat['Catalyst'].value_counts().to_dict()}")
                except Exception:
                    pass
                p.records = len(df_cat)
                p.message = f"{len(df_cat)} catalysts / {_uni_n} scanned → {CATALYST_WATCHLIST}"
            else:
                logger.info("ℹ️  Catalyst Scan: no catalyst signals fired.")
                p.records = 0
                p.message = "no catalyst signals"
        except Exception as e:
            # Non-fatal: the new broad scan must never break the established pipeline.
            logger.error(f"❌ Error in Bull Catalyst Broad Scan: {e}")
            p.status  = "SKIP"
            p.message = f"error: {e}"

    # 4.75. RECOVERY CATALYST WATCHLIST — companion to Phase 4.7 (new 6 Jul 2026)
    # ----------------------------------------------------------------------
    # Phase 4.5 already ran the recovery screener (RFF≥4 hard-gated, regime- and
    # drawdown-gated) → Recovery_Screener_Results.csv. That file mixes watch
    # (Signal 1) with fired signals and isn't curated for TV import. Here we
    # distil the FIRING recovery catalysts (Signal ≥ 2: REV-CB/RS/EARLY + WYC-*)
    # into a curated companion watchlist that mirrors the bull catalyst file —
    # so the trader has ONE recovery list to scan. Fundamentals are already
    # enforced inside the recovery engine (RFF gate), so no extra gate here.
    REC_CATALYST_WATCHLIST = "FINAL_RECOVERY_CATALYST_WATCHLIST.csv"
    logger.info("\n[PHASE 4.75] BUILDING RECOVERY CATALYST WATCHLIST...")
    with run.phase("Phase 4.75 — Recovery Catalyst Watchlist") as p:
        try:
            import pandas as _pd
            _rec_src = os.path.join(_DIR, "Recovery_Screener_Results.csv")
            if not os.path.exists(_rec_src):
                logger.info("ℹ️  Recovery results not found — skipping recovery catalyst watchlist.")
                p.status = "SKIP"; p.message = "Recovery_Screener_Results.csv missing"
            else:
                _rdf = _pd.read_csv(_rec_src)
                _fired = _rdf[_rdf.get("Signal", 0) >= 2].copy() if "Signal" in _rdf.columns else _rdf.iloc[0:0].copy()
                if _fired.empty:
                    # Header-only file so the timestamp updates ("ran, found none").
                    _rdf.iloc[0:0].to_csv(os.path.join(_DIR, REC_CATALYST_WATCHLIST), index=False)
                    logger.info("ℹ️  No firing recovery catalysts (Signal ≥ 2) today.")
                    p.records = 0; p.message = f"0 recovery catalysts → {REC_CATALYST_WATCHLIST}"
                else:
                    # Priority: WYC/EARLY/RS/CB by Signal desc, then fundamental+
                    # technical rank (Combined_Score if present, else Score).
                    _sort_col = "Combined_Score" if "Combined_Score" in _fired.columns else "Score"
                    _fired = _fired.sort_values(["Signal", _sort_col], ascending=[False, False])
                    _fired.to_csv(os.path.join(_DIR, REC_CATALYST_WATCHLIST), index=False)
                    try:
                        logger.info(f"   Recovery catalysts: {_fired['Signal_Label'].value_counts().to_dict()}")
                    except Exception:
                        pass
                    logger.info(f"✅ Recovery Catalyst Watchlist: {len(_fired)} firing → {REC_CATALYST_WATCHLIST}")
                    p.records = len(_fired)
                    p.message = f"{len(_fired)} recovery catalysts → {REC_CATALYST_WATCHLIST}"
        except Exception as e:
            logger.error(f"❌ Error building Recovery Catalyst Watchlist: {e}")
            p.status  = "SKIP"
            p.message = f"error: {e}"

    # FEED HEALTH SUMMARY (G2) — surface which data source actually served the
    # screeners. data_provider tracks per-source fetch counts in-process; both
    # screeners have run above, so these counters reflect the whole scan. A run
    # that quietly fell to the FREE feed (expired token / DH-904 throttle / stale
    # scrip master) shows up here instead of looking healthy. Non-fatal.
    try:
        import data_provider as _dp_report
        _counts = _dp_report.get_source_counts()
        logger.info(f"[FEED] {_dp_report.feed_status_banner()}")
        if _counts:
            _total = sum(_counts.values()) or 1
            _summary = " · ".join(f"{k}={v} ({v / _total * 100:.0f}%)"
                                  for k, v in sorted(_counts.items(), key=lambda kv: -kv[1]))
            logger.info(f"[FEED] data sources this run: {_summary}")
            # Live fetches that bypassed the paid feed (cache hits excluded — a
            # yfinance-poisoned cache is a separate concern, G3).
            _free = (_counts.get("yfinance", 0) + _counts.get("nselib", 0)
                     + _counts.get("nsepython", 0))
            _live = _total - _counts.get("cache", 0)
            if _dp_report.DHAN_OK and _live and (_free / _live) > 0.20:
                logger.warning(
                    f"⚠️  [FEED] {_free}/{_live} live fetches "
                    f"({_free / _live * 100:.0f}%) used the FREE fallback despite "
                    f"Dhan being wired — check token (dhan_auth), DH-904 throttle "
                    f"(DHAN_MIN_INTERVAL_S), or scrip-master freshness.")
    except Exception as _fe:
        logger.debug(f"feed-health summary skipped: {_fe}")

    # 4.8. GOLDEN MATCHER BOARD — consolidate the 5 board watchlists (Golden
    # Matcher + Bull ALL + Recovery ALL + Bull/Recovery Catalyst) into ONE deduped
    # union CSV (FINAL_GOLDEN_MATCHER.csv). This is the exact universe the Trigger
    # Board evaluates; it is exported as the single "Golden_Matcher_Board" TV list
    # (Phase 5) and synced to Strike (auto-split at 49) + TradingView (Phase 6/7).
    logger.info("\n[PHASE 4.8] CONSOLIDATING GOLDEN MATCHER BOARD WATCHLIST...")
    with run.phase("Phase 4.8 — Golden Matcher Board (union)") as p:
        try:
            import gm_trigger_board as _gtb
            import pandas as _pd
            _uni = _gtb.load_watchlist_union()          # reads the 5 FINAL_*.csv, deduped
            _syms = sorted(_uni.keys())
            if _syms:
                _pd.DataFrame({"Symbol": _syms}).to_csv("FINAL_GOLDEN_MATCHER.csv", index=False)
                p.message = f"{len(_syms)} names → FINAL_GOLDEN_MATCHER.csv"
            else:
                p.status = "SKIP"; p.message = "no watchlist names to consolidate"
        except Exception as e:
            logger.error(f"⚠️  Golden Matcher Board consolidation failed: {e}")
            p.status = "SKIP"; p.message = f"skipped: {e}"

    # 5. GENERATE LOCAL WATCHLISTS (Pass 1 - Bull & Recovery)
    logger.info("\n[PHASE 5] GENERATING LOCAL WATCHLISTS (Pass 1)...")
    with run.phase("Phase 5 — Watchlists (Pass 1)") as p:
        try:
            watchlist_manager.generate_tradingview_files(silent=True)
            p.message = "watchlists generated"
        except Exception as e:
            logger.error(f"❌ Error creating watchlists: {e}")
            raise

    # 5.5. FUNDAMENTAL X-RAY SCREENER (Deprecated — integrated directly into Golden Matcher)
    # logger.info("\n[PHASE 5.5] RUNNING FUNDAMENTAL X-RAY SCREENER...")
    # with run.phase("Phase 5.5 — Fundamental X-Ray") as p:
    #     try:
    #         # Delete custom symbols if they exist so it sweeps the newly generated watchlists
    #         custom_xray = "xray_custom_symbols.txt"
    #         if os.path.exists(custom_xray):
    #             os.remove(custom_xray)
    # 
    #         import xray_screener_job
    #         xray_screener_job.main()
    #         p.message = "X-Ray complete"
    #     except Exception as e:
    #         logger.error(f"❌ Error in X-Ray screener: {e}")
    #         raise
    # 
    # # 5.6. GENERATE LOCAL WATCHLISTS (Pass 2 - Includes X-Ray) (Deprecated)
    # logger.info("\n[PHASE 5.6] GENERATING LOCAL WATCHLISTS (Pass 2)...")
    # with run.phase("Phase 5.6 — Watchlists (Pass 2)") as p:
    #     try:
    #         watchlist_manager.generate_tradingview_files(silent=True)
    #         p.message = "watchlists (pass 2) generated"
    #     except Exception as e:
    #         logger.error(f"❌ Error creating watchlists (Pass 2): {e}")
    #         raise

    # 5.7. STALE WATCHLISTS CLEANUP (NUCLEAR CLEANUP)
    logger.info("\n[PHASE 5.7] RUNNING STALE WATCHLISTS CLEANUP...")
    with run.phase("Phase 5.7 — Stale Watchlists Cleanup") as p:
        try:
            import nuclear_cleanup
            nuclear_cleanup.main()
            p.message = "Cleanup complete"
        except Exception as e:
            logger.error(f"❌ Error in Nuclear Cleanup: {e}")
            raise

    # 6. STRIKE.MONEY SYNC
    logger.info("\n[PHASE 6] SYNCING TO STRIKE.MONEY (WATCHLISTS)...")
    with run.phase("Phase 6 — Strike.Money Sync") as p:
        try:
            import strike_automation
            import asyncio
            asyncio.run(strike_automation.run_pipeline(mode_param="watchlist"))
            p.message = "Strike sync OK"
        except Exception as e:
            logger.error(f"❌ Error in Strike Sync: {e}")
            raise

    # 7. TRADINGVIEW SYNC
    logger.info("\n[PHASE 7] SYNCING TO TRADINGVIEW (WATCHLISTS)...")
    with run.phase("Phase 7 — TradingView Sync") as p:
        try:
            import tradingview_automation_v2
            import asyncio
            asyncio.run(tradingview_automation_v2.run_sync(pipeline_mode=True))
            p.message = "TV sync OK"
        except Exception as e:
            logger.error(f"❌ Error in TradingView Sync: {e}")
            raise

    # 8. POST-FLIGHT CLEANUP & BACKUP
    logger.info("\n[PHASE 8] POST-FLIGHT CLEANUP & DATABASE BACKUP...")
    with run.phase("Phase 8 — Backup") as p:
        try:
            import pipeline_cleanup
            _bk = pipeline_cleanup.postflight_backup(verbose=True)
            p.message = "DB backed up safely" if _bk else "no backup needed"
        except Exception as e:
            logger.warning(f"⚠️  Post-flight backup skipped: {e}")
            p.status = "SKIP"
            p.message = f"skipped: {e}"

    # 9. PORTFOLIO ROTATION GUARD
    logger.info("\n[PHASE 9] RUNNING PORTFOLIO ROTATION GUARD...")
    with run.phase("Phase 9 — Portfolio Rotation Guard") as p:
        try:
            import portfolio_rotation_guard
            portfolio_rotation_guard.run_portfolio_guard()
            p.message = "rotation report generated"
        except Exception as e:
            logger.error(f"❌ Error in Portfolio Guard: {e}")
            raise

    # 10. COPY RESULTS TO SCREENER CSVs
    logger.info("\n[PHASE 10] EXPORTING SCREENER CSVs...")
    with run.phase("Phase 10 — Export CSVs") as p:
        try:
            import shutil
            export_dir = r"C:\Users\jayra\Documents\GeminiVSCode\Screener CSVs"
            os.makedirs(export_dir, exist_ok=True)
            
            files_to_copy = [
                "Bull_Screener_Results.csv",
                "Recovery_Screener_Results.csv",
                "FINAL_WATCHLIST.csv"
            ]
            copied = 0
            for src in files_to_copy:
                if os.path.exists(src):
                    # We keep the same name except perhaps renaming FINAL_WATCHLIST for clarity,
                    # but keeping original names is fine, or we can use the same name.
                    dst_name = "Golden_Matcher_Results.csv" if src == "FINAL_WATCHLIST.csv" else src
                    shutil.copy2(src, os.path.join(export_dir, dst_name))
                    copied += 1
                else:
                    logger.warning(f"⚠️ Warning: {src} not found for export.")
            
            p.message = f"Exported {copied} CSV files"
            logger.info(f"✅ Exported {copied} files to {export_dir}")
        except Exception as e:
            logger.error(f"❌ Error exporting CSVs: {e}")
            raise

    # 11. SCORE AUTHENTICITY CHECK — prove every stored score is reproducible
    # from the visible metric columns (read-only, ~2s). Non-fatal: a FAIL is
    # surfaced loudly but does not abort the run.
    logger.info("\n[PHASE 11] VALIDATING SCORE AUTHENTICITY...")
    with run.phase("Phase 11 — Score Authenticity") as p:
        try:
            import score_authenticity_check
            _res = score_authenticity_check.run_authenticity_check(verbose=True)
            if _res["pass"]:
                p.message = "all scores reproducible from columns"
            else:
                p.status = "WARN"
                p.message = "score/column mismatch — see report in reports/"
                logger.warning("⚠️  SCORE AUTHENTICITY: mismatches found — review the report above.")
        except Exception as e:
            logger.warning(f"⚠️  Score authenticity check skipped: {e}")
            p.status = "SKIP"
            p.message = f"skipped: {e}"

    run.finalize()

    logger.info("\n" + "="*60)
    logger.info("🎉 AUTO-PILOT PIPELINE COMPLETED SUCCESSFULLY!")
    logger.info("="*60)
    logger.info(f"[log] Full console log saved -> {log_path}")


    if "--batch" not in sys.argv:
        input("Press Enter to close window...")

if __name__ == "__main__":
    main()
