
import sys
import os
import time

# Import application modules
try:
    import chartink_scanner_pro
    import screener_fetcher
    import screener_processor
    import brute_force_match_pro
    import watchlist_manager # Added for Auto-Pilot
except ImportError as e:
    print(f"❌ Critical Import Error: {e}")
    input("Press Enter to exit...")
    sys.exit(1)

def main():
    print("="*60)
    print("🚀 WEINSTEIN COMMANDER: FULL AUTO-PILOT")
    print("="*60)
    print("This will execute the entire workflow:")
    print("1. Run ALL Technical Scanners (Chartink)")
    print("2. Fetch Fundamental Data (Screener.in)")
    print("3. Process Data")
    print("4. Run Golden Matcher")
    print("5. Generate Local Watchlists")
    print("6. Sync to Strike.Money")
    print("-" * 60)
    
    # 1. RUN ALL CHARTINK SCANS
    print("\n[PHASE 1] RUNNING TECHNICAL SCANNERS...")
    scan_keys = ['1', '2', '3', '4']
    for key in scan_keys:
        try:
            chartink_scanner_pro.run_scan(key)
            time.sleep(1) # Polite delay
        except Exception as e:
            print(f"❌ Error running scan {key}: {e}")

    # 2. FETCH FUNDAMENTALS
    print("\n[PHASE 2] FETCHING FUNDAMENTAL DATA...")
    try:
        screener_fetcher.fetch_screener_data(interactive=False)
    except Exception as e:
        print(f"❌ Error fetching data: {e}")

    # 3. PROCESS HTML
    print("\n[PHASE 3] PROCESSING DATA...")
    try:
        screener_processor.process_screener_pages()
    except Exception as e:
        print(f"❌ Error processing HTML: {e}")

    # 4. GOLDEN MATCHER
    print("\n[PHASE 4] RUNNING GOLDEN MATCHER...")
    match_summary = ""
    try:
        results = brute_force_match_pro.perform_match(return_raw=True)
        if results:
            for strategy, df in results.items():
                if not df.empty:
                    match_summary += f"✅ {strategy}: {len(df)} matches\n"
        
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

    # 5. GENERATE LOCAL WATCHLISTS
    print("\n[PHASE 5] GENERATING LOCAL WATCHLISTS...")
    try:
        watchlist_manager.generate_tradingview_files(silent=True)
    except Exception as e:
        print(f"❌ Error creating watchlists: {e}")

    # 6. STRIKE.MONEY SYNC
    print("\n[PHASE 6] SYNCING TO STRIKE.MONEY (WATCHLISTS)...")
    try:
        # Use subprocess for cleaner execution, waiting for it to finish
        # We use sys.executable to ensure we use the same python runner
        import subprocess
        subprocess.run([sys.executable, "strike_automation.py", "--mode=watchlist"], check=True)
    except Exception as e:
        print(f"❌ Error in Strike Sync: {e}")

    # 7. TRADINGVIEW SYNC
    print("\n[PHASE 7] SYNCING TO TRADINGVIEW (WATCHLISTS)...")
    try:
        subprocess.run([sys.executable, "tradingview_automation_v2.py", "--pipeline"], check=True)
    except Exception as e:
        print(f"❌ Error in TradingView Sync: {e}")

    # 8. EMAIL DISPATCH
    print("\n[PHASE 8] DISPATCHING REPORTS VIA GMAIL...")
    try:
        import gmail_dispatcher
        gmail_dispatcher.dispatch_golden_matches()
    except Exception as e:
        print(f"❌ Error dispatching email: {e}")

    # 9. PORTFOLIO ROTATION GUARD
    print("\n[PHASE 9] RUNNING PORTFOLIO ROTATION GUARD...")
    try:
        import portfolio_rotation_guard
        portfolio_rotation_guard.run_portfolio_guard()
    except Exception as e:
        print(f"❌ Error in Portfolio Guard: {e}")

    print("\n" + "="*60)
    print("✅ WORKFLOW COMPLETE")
    print("="*60)
    
    input("Press Enter to close window...")

if __name__ == "__main__":
    main()
