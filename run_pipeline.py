
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

def main():
    # Clear any stale automated Chrome processes before starting the pipeline
    try:
        kill_automation_chrome()
    except Exception as ce:
        print(f"⚠️ Warning: Pre-run Chrome cleanup returned: {ce}")

    print("="*60)
    print("🚀 WEINSTEIN COMMANDER: FULL AUTO-PILOT")
    print("="*60)
    print("This will execute the entire workflow:")
    print("1. Run ALL Technical Scanners (Chartink)")
    print("2. Fetch Fundamental Data (Screener.in)")
    print("3. Process Data")
    print("4. Run Golden Matcher")
    print("5. Run Recovery Screener")
    print("6. Run Bull Screener")
    print("7. Generate Local Watchlists")
    print("8. Sync to Strike.Money")
    print("-" * 60)

    # E9: pipeline status tracker — writes pipeline_status.json after every phase
    run = PipelineRun(label="Auto-Pilot Pipeline")

    # 1. RUN ALL CHARTINK SCANS
    print("\n[PHASE 1] RUNNING TECHNICAL SCANNERS...")
    with run.phase("Phase 1 — Chartink Scanners") as p:
        scan_keys = ['1', '2', '3', '4', '5', '6', '7']
        ok_count = 0
        for key in scan_keys:
            try:
                chartink_scanner_pro.run_scan(key)
                ok_count += 1
                time.sleep(1) # Polite delay
            except Exception as e:
                print(f"❌ Error running scan {key}: {e}")
        p.records = ok_count
        p.message = f"{ok_count}/{len(scan_keys)} scans completed"

    # 2. FETCH FUNDAMENTALS
    print("\n[PHASE 2] FETCHING FUNDAMENTAL DATA...")
    with run.phase("Phase 2 — Screener.in Fundamentals") as p:
        try:
            screener_fetcher.fetch_screener_data(interactive=False)
            p.message = "fetch complete"
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            raise

    # 3. PROCESS HTML
    print("\n[PHASE 3] PROCESSING DATA...")
    with run.phase("Phase 3 — Process HTML") as p:
        try:
            screener_processor.process_screener_pages()
            p.message = "HTML processed"
        except Exception as e:
            print(f"❌ Error processing HTML: {e}")
            raise

    # 4. GOLDEN MATCHER
    print("\n[PHASE 4] RUNNING GOLDEN MATCHER...")
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
                print(f"🌟 Matching Summary:\n{match_summary}")
                # Trigger Push Notification
                try:
                    import telegram_sentinel
                    import asyncio
                    push_msg = f"🌟 *GOLDEN MATCH DETECTED* 🌟\n\nPipeline found high-conviction setups:\n{match_summary}\nCheck your journal for tactical entry!"
                    asyncio.run(telegram_sentinel.send_push_notification(push_msg))
                except Exception as pe:
                    print(f"⚠️ Telegram Push Failed: {pe}")
        except Exception as e:
            print(f"❌ Error in matching: {e}")
            raise

    # 4.5. RECOVERY SCREENER (Python edition — signal hold-window aware)
    print("\n[PHASE 4.5] RUNNING RECOVERY SCREENER...")
    with run.phase("Phase 4.5 — Recovery Screener") as p:
        try:
            import recovery_screener
            recovery_screener.main()   # BUG-C2: no longer calls os.chdir() — CWD safe
            p.message = "recovery scan complete"
        except Exception as e:
            print(f"❌ Error in recovery screener: {e}")
            raise

    # 4.6. BULL SCREENER (catalyst scoring on FINAL_COMBINED_BULL_PICKS.csv)
    print("\n[PHASE 4.6] RUNNING BULL SCREENER...")
    with run.phase("Phase 4.6 — Bull Screener") as p:
        try:
            import bull_screener
            def _bull_progress(idx, total, sym):
                if idx == 1 or idx == total or idx % 10 == 0:
                    print(f"  Bull Screener [{idx}/{total}]: {sym}")
            # strict=True: batch-pipeline writes Bull_Screener_Results.csv consumed
            # by downstream tools that expect catalyst-firing rows only.
            # Tracker mode (default since 2026-05-18) is for the dashboard UX.
            df_bull = bull_screener.run_bull_screener(progress_callback=_bull_progress, strict=True)
            if df_bull is not None and not df_bull.empty:
                print(f"✅ Bull Screener: {len(df_bull)} catalyst signals found.")
                p.records = len(df_bull)
                p.message = f"{len(df_bull)} catalyst signals"
            else:
                print("ℹ️  Bull Screener: no catalyst signals fired.")
                p.records = 0
                p.message = "no catalyst signals"
        except FileNotFoundError as e:
            print(f"⚠️  Bull Screener skipped — input missing: {e}")
            p.status  = "SKIP"
            p.message = f"input missing: {e}"
        except Exception as e:
            print(f"❌ Error in Bull Screener: {e}")
            raise

    # 5. GENERATE LOCAL WATCHLISTS (Pass 1 - Bull & Recovery)
    print("\n[PHASE 5] GENERATING LOCAL WATCHLISTS (Pass 1)...")
    with run.phase("Phase 5 — Watchlists (Pass 1)") as p:
        try:
            watchlist_manager.generate_tradingview_files(silent=True)
            p.message = "watchlists generated"
        except Exception as e:
            print(f"❌ Error creating watchlists: {e}")
            raise

    # 5.5. FUNDAMENTAL X-RAY SCREENER
    print("\n[PHASE 5.5] RUNNING FUNDAMENTAL X-RAY SCREENER...")
    with run.phase("Phase 5.5 — Fundamental X-Ray") as p:
        try:
            # Delete custom symbols if they exist so it sweeps the newly generated watchlists
            custom_xray = "xray_custom_symbols.txt"
            if os.path.exists(custom_xray):
                os.remove(custom_xray)

            import xray_screener_job
            xray_screener_job.main()
            p.message = "X-Ray complete"
        except Exception as e:
            print(f"❌ Error in X-Ray screener: {e}")
            raise

    # 5.6. GENERATE LOCAL WATCHLISTS (Pass 2 - Includes X-Ray)
    print("\n[PHASE 5.6] GENERATING LOCAL WATCHLISTS (Pass 2)...")
    with run.phase("Phase 5.6 — Watchlists (Pass 2)") as p:
        try:
            watchlist_manager.generate_tradingview_files(silent=True)
            p.message = "watchlists regenerated incl. X-Ray"
        except Exception as e:
            print(f"❌ Error creating watchlists: {e}")
            raise

    # 5.7. STALE WATCHLISTS CLEANUP (NUCLEAR CLEANUP)
    print("\n[PHASE 5.7] RUNNING STALE WATCHLISTS CLEANUP...")
    with run.phase("Phase 5.7 — Stale Watchlists Cleanup") as p:
        try:
            import subprocess
            subprocess.run([sys.executable, "nuclear_cleanup.py"], check=True)
            p.message = "Cleanup complete"
        except Exception as e:
            print(f"❌ Error in Nuclear Cleanup: {e}")
            raise

    # 6. STRIKE.MONEY SYNC
    print("\n[PHASE 6] SYNCING TO STRIKE.MONEY (WATCHLISTS)...")
    with run.phase("Phase 6 — Strike.Money Sync") as p:
        try:
            # Use subprocess for cleaner execution, waiting for it to finish
            # We use sys.executable to ensure we use the same python runner
            import subprocess
            subprocess.run([sys.executable, "strike_automation.py", "--mode=watchlist"], check=True)
            p.message = "Strike sync OK"
        except Exception as e:
            print(f"❌ Error in Strike Sync: {e}")
            raise

    # 7. TRADINGVIEW SYNC
    print("\n[PHASE 7] SYNCING TO TRADINGVIEW (WATCHLISTS)...")
    with run.phase("Phase 7 — TradingView Sync") as p:
        try:
            import subprocess
            subprocess.run([sys.executable, "tradingview_automation_v2.py", "--pipeline"], check=True)
            p.message = "TV sync OK"
        except Exception as e:
            print(f"❌ Error in TradingView Sync: {e}")
            raise

    # 8. EMAIL DISPATCH
    print("\n[PHASE 8] DISPATCHING REPORTS VIA GMAIL...")
    with run.phase("Phase 8 — Gmail Dispatch") as p:
        try:
            import gmail_dispatcher
            gmail_dispatcher.dispatch_golden_matches()
            p.message = "email sent"
        except Exception as e:
            print(f"❌ Error dispatching email: {e}")
            raise

    # 9. PORTFOLIO ROTATION GUARD
    print("\n[PHASE 9] RUNNING PORTFOLIO ROTATION GUARD...")
    with run.phase("Phase 9 — Portfolio Rotation Guard") as p:
        try:
            import portfolio_rotation_guard
            portfolio_rotation_guard.run_portfolio_guard()
            p.message = "rotation report generated"
        except Exception as e:
            print(f"❌ Error in Portfolio Guard: {e}")
            raise

    # 10. COPY RESULTS TO SCREENER CSVs
    print("\n[PHASE 10] EXPORTING SCREENER CSVs...")
    with run.phase("Phase 10 — Export CSVs") as p:
        try:
            import shutil
            export_dir = r"C:\Users\jayra\Documents\GeminiVSCode\Screener CSVs"
            os.makedirs(export_dir, exist_ok=True)
            
            files_to_copy = [
                "Bull_Screener_Results.csv",
                "Recovery_Screener_Results.csv",
                "FINAL_WATCHLIST.csv",
                "FINAL_XRay_Picks.csv"
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
                    print(f"⚠️ Warning: {src} not found for export.")
            
            p.message = f"Exported {copied} CSV files"
            print(f"✅ Exported {copied} files to {export_dir}")
        except Exception as e:
            print(f"❌ Error exporting CSVs: {e}")
            raise

    # 11. SCORE AUTHENTICITY CHECK — prove every stored score is reproducible
    # from the visible metric columns (read-only, ~2s). Non-fatal: a FAIL is
    # surfaced loudly but does not abort the run.
    print("\n[PHASE 11] VALIDATING SCORE AUTHENTICITY...")
    with run.phase("Phase 11 — Score Authenticity") as p:
        try:
            import score_authenticity_check
            _res = score_authenticity_check.run_authenticity_check(verbose=True)
            if _res["pass"]:
                p.message = "all scores reproducible from columns"
            else:
                p.status = "WARN"
                p.message = "score/column mismatch — see report in reports/"
                print("⚠️  SCORE AUTHENTICITY: mismatches found — review the report above.")
        except Exception as e:
            print(f"⚠️  Score authenticity check skipped: {e}")
            p.status = "SKIP"
            p.message = f"skipped: {e}"

    run.finalize()

    print("\n" + "="*60)
    print("✅ WORKFLOW COMPLETE")
    print("="*60)

    if "--batch" not in sys.argv:
        input("Press Enter to close window...")

if __name__ == "__main__":
    main()
