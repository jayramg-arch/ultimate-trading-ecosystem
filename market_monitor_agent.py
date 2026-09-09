#!/usr/bin/env python3
"""
market_monitor_agent.py — Background Market Monitor Agent
Runs technical scanners, Bull and Recovery screeners during Indian market hours,
and pushes newly triggered setups (like POS-BO, REV-RS) to Telegram.
"""

import os
import sys
import time
import json
import logging
import asyncio
import argparse
import subprocess
from datetime import datetime, time as dt_time
import pandas as pd
from dotenv import load_dotenv

# Set encoding to UTF-8 for Windows console
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure working directory is correct
_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)
load_dotenv(os.path.join(_DIR, ".env"), override=True)

# ── LOGGING SETUP ────────────────────────────────────────────────────────────
os.makedirs(os.path.join(_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(_DIR, "reports"), exist_ok=True)

logger = logging.getLogger("market_monitor_agent")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# File handler
fh = logging.FileHandler(os.path.join(_DIR, "logs", "market_monitor.log"), encoding="utf-8")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

STATE_FILE = os.path.join(_DIR, "reports", "sent_alerts_state.json")

# ── TIMEZONE & MARKET HOURS CONSTANTS ─────────────────────────────────────────
import pytz
IST = pytz.timezone("Asia/Kolkata")

MARKET_START = dt_time(9, 15)
MARKET_END = dt_time(15, 30)

# ── STATE MANAGEMENT ─────────────────────────────────────────────────────────
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                if isinstance(state, dict):
                    return state
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
    return {}

def save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")

def prune_old_state(state: dict) -> dict:
    """Removes state entries older than 5 days to keep the file small."""
    pruned = {}
    today = datetime.now(IST).date()
    for key, timestamp_str in state.items():
        try:
            # key format: symbol_strategy_YYYY-MM-DD
            parts = key.split("_")
            if len(parts) >= 3:
                date_str = parts[-1]
                alert_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (today - alert_date).days <= 5:
                    pruned[key] = timestamp_str
            else:
                pruned[key] = timestamp_str  # Keep if format doesn't match
        except Exception:
            pruned[key] = timestamp_str  # Keep on error
    return pruned

# ── DUAL ALERTS (TELEGRAM & EMAIL) ───────────────────────────────────────────
def send_agent_alert(message: str) -> bool:
    """Sends setup alerts to both Telegram (via proxy) and Gmail (as fallback/dual delivery)."""
    telegram_ok = False
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    # 1. Telegram
    if token and chat_id:
        try:
            import telegram_sentinel
            asyncio.run(telegram_sentinel.send_push_notification(message))
            telegram_ok = True
        except Exception as e:
            logger.error(f"Telegram push failed: {e}")
    else:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env)")

    # 2. Email fallback / dual delivery
    email_ok = False
    gmail_sender = os.getenv("GMAIL_SENDER_EMAIL")
    gmail_pwd = os.getenv("GMAIL_APP_PASSWORD")
    if gmail_sender and gmail_pwd:
        try:
            import gmail_dispatcher
            
            # Format subject: Try to extract Symbol and Strategy
            subject = "🤖 Weinstein Commander Alert"
            symbol_tag = ""
            strategy_tag = ""
            for line in message.split("\n"):
                if line.startswith("Symbol:"):
                    symbol_tag = line.replace("Symbol:", "").replace("*", "").strip()
                elif line.startswith("Strategy:"):
                    strategy_tag = line.replace("Strategy:", "").replace("*", "").strip()
            if symbol_tag and strategy_tag:
                subject = f"🔔 ALERT: {symbol_tag} - {strategy_tag}"
            elif "Online" in message:
                subject = "🤖 Weinstein Commander: Monitor Agent Online"
            elif "Offline" in message:
                subject = "🛑 Weinstein Commander: Monitor Agent Offline"
                
            # Clean body (remove markdown asterisks)
            body_text = message.replace("*", "")
            
            email_ok = gmail_dispatcher.send_email(subject=subject, body_text=body_text)
        except Exception as e:
            logger.error(f"Email push failed: {e}")
    else:
        logger.warning("Gmail not configured (GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD missing in .env)")

    return telegram_ok or email_ok

# ── CORE MONITOR CYCLE ────────────────────────────────────────────────────────
def run_scan_and_screen() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Runs Chartink Scanners and both Bull and Recovery Screeners."""
    logger.info("📡 Starting scan cycle...")
    
    # 1. Technical scanners (Chartink)
    import chartink_scanner_pro
    scan_keys = ["1", "2", "3", "4", "5", "6", "7"]
    logger.info(f"Running Chartink scans {scan_keys}...")
    for key in scan_keys:
        try:
            chartink_scanner_pro.run_scan(key)
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Chartink scan {key} failed: {e}")

    # 2. Bull Screener (run strict mode to output triggered signals only)
    logger.info("Running Bull Screener...")
    df_bull = pd.DataFrame()
    try:
        import bull_screener
        # strict=True filters for triggered catalysts only
        df_bull = bull_screener.run_bull_screener(strict=True)
    except Exception as e:
        logger.error(f"Bull Screener failed: {e}")

    # 3. Recovery Screener (run strict mode to output triggered signals only)
    logger.info("Running Recovery Screener...")
    df_rec = pd.DataFrame()
    try:
        import recovery_screener
        df_rec = recovery_screener.run_recovery_screener(strict=True)
    except Exception as e:
        logger.error(f"Recovery Screener failed: {e}")

    return df_bull, df_rec

def process_and_alert(df_bull: pd.DataFrame, df_rec: pd.DataFrame, force_alert: bool = False):
    """Checks results for new signals and sends Telegram alerts."""
    state = load_state()
    state = prune_old_state(state)
    
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    now_ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    
    new_alerts_count = 0

    # ── 1. Process Bull Screener Results ─────────────────────────────────────
    if df_bull is not None and not df_bull.empty:
        logger.info(f"Checking {len(df_bull)} Bull Screener rows...")
        for _, row in df_bull.iterrows():
            symbol = row.get("Symbol")
            strategy = row.get("Signal_Label")
            
            if not symbol or not strategy or strategy in ("None", ""):
                continue
                
            state_key = f"{symbol}_{strategy}_{today_str}"
            
            if state_key not in state or force_alert:
                score = row.get("Score", 0)
                price = row.get("Price", 0.0)
                stage = row.get("Weinstein_Stage", 0)
                rs_ratio = row.get("Mansfield_RS_x100", 0.0)
                details = row.get("Details", "")
                
                # Format message
                emoji = "🚀" if "BO" in strategy else "🔥" if "ACCUM" in strategy else "📈"
                msg = (
                    f"{emoji} *BULL SETUP DETECTED* {emoji}\n\n"
                    f"Symbol: *{symbol}*\n"
                    f"Strategy: *{strategy}*\n"
                    f"Price: *₹{price:,.2f}*\n"
                    f"Stage: *Stage {stage}*\n"
                    f"RRG RS-Ratio: *{rs_ratio:+.2f}*\n"
                    f"Score: *{score}/100*\n"
                    f"Details: _{details}_\n\n"
                    f"🕒 Time: {now_ts}"
                )
                
                logger.info(f"🔔 ALERT: Bull setup on {symbol} - {strategy}")
                if send_agent_alert(msg):
                    state[state_key] = now_ts
                    new_alerts_count += 1
                time.sleep(1)  # Rate limiting

    # ── 2. Process Recovery Screener Results ─────────────────────────────────
    if df_rec is not None and not df_rec.empty:
        logger.info(f"Checking {len(df_rec)} Recovery Screener rows...")
        # In recovery_screener, Signal >= 2 means actionable trigger (REV-RS, REV-CB, etc.)
        actionable_rec = df_rec[df_rec.get("Signal", 0) >= 2]
        for _, row in actionable_rec.iterrows():
            symbol = row.get("Symbol")
            strategy = row.get("Signal_Label")
            
            if not symbol or not strategy or strategy in ("None", ""):
                continue
                
            state_key = f"{symbol}_{strategy}_{today_str}"
            
            if state_key not in state or force_alert:
                score = row.get("Score", 0)
                entry = row.get("Entry", 0.0)
                sl = row.get("SL", 0.0)
                t1 = row.get("T1", 0.0)
                sl_pct = row.get("SL_pct", 0.0)
                rr = row.get("RR_T1", 0.0)
                details = row.get("Details", "")
                
                # Format message
                msg = (
                    f"⚡ *RECOVERY SETUP DETECTED* ⚡\n\n"
                    f"Symbol: *{symbol}*\n"
                    f"Strategy: *{strategy}*\n"
                    f"Entry: *₹{entry:,.2f}*\n"
                    f"Stop Loss: *₹{sl:,.2f}* ({sl_pct:.1f}%)\n"
                    f"Target 1: *₹{t1:,.2f}* (R:R {rr:.1f}x)\n"
                    f"Score: *{score}/22*\n"
                    f"Details: _{details}_\n\n"
                    f"🕒 Time: {now_ts}"
                )
                
                logger.info(f"🔔 ALERT: Recovery setup on {symbol} - {strategy}")
                if send_agent_alert(msg):
                    state[state_key] = now_ts
                    new_alerts_count += 1
                time.sleep(1)  # Rate limiting

    save_state(state)
    logger.info(f"Cycle completed. Sent {new_alerts_count} new alerts.")

# ── SCHEDULING & TIME CHECKS ──────────────────────────────────────────────────
def is_market_hours(force_override: bool = False) -> bool:
    if force_override:
        return True
        
    now = datetime.now(IST)
    # Weekday check: Monday=0, Friday=4, Saturday=5, Sunday=6
    if now.weekday() >= 5:
        return False
        
    now_time = now.time()
    return MARKET_START <= now_time <= MARKET_END

def sleep_until_market_open():
    """Calculates sleep time until next market open (Mon-Fri 9:15 AM IST)."""
    now = datetime.now(IST)
    
    # Target date
    target = now.replace(hour=9, minute=15, second=0, microsecond=0)
    
    # If it's already past 9:15 AM today, target tomorrow
    if now.time() >= MARKET_START:
        target += timedelta(days=1)
        
    # Skip weekends: if target is Saturday, add 2 days. If Sunday, add 1 day.
    while target.weekday() >= 5:
        target += timedelta(days=1)
        
    sleep_seconds = (target - now).total_seconds()
    logger.info(f"💤 Outside market hours. Sleeping for {sleep_seconds/3600:.2f} hours (until {target.strftime('%Y-%m-%d %H:%M:%S IST')})")
    
    # Sleep in chunks to allow keyboard interrupt
    chunk_size = 300
    while sleep_seconds > 0:
        time.sleep(min(sleep_seconds, chunk_size))
        sleep_seconds -= chunk_size

# ── ENTRY POINT ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Weinstein & Swing Pro Intraday Market Monitor Agent")
    parser.add_argument("--force", action="store_true", help="Force-run scanners immediately regardless of market hours.")
    parser.add_argument("--interval", type=int, default=1800, help="Scan interval in seconds (default: 1800s / 30m).")
    parser.add_argument("--force-alerts", action="store_true", help="Resend all active alerts even if previously notified today.")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🤖 WEINSTEIN COMMANDER: LIVE MARKET MONITOR AGENT ONLINE")
    logger.info(f"  Target timezone: {IST}")
    logger.info(f"  Scan interval  : {args.interval}s ({args.interval/60:.1f}m)")
    logger.info(f"  Market hours   : 09:15 AM - 03:30 PM IST (Mon-Fri)")
    logger.info("=" * 60)

    # Simple connection check
    send_agent_alert("🤖 *Market Monitor Agent Online* and actively listening.")

    try:
        while True:
            if is_market_hours(args.force):
                start_time = time.time()
                
                try:
                    df_bull, df_rec = run_scan_and_screen()
                    process_and_alert(df_bull, df_rec, force_alert=args.force_alerts)
                except Exception as cycle_err:
                    logger.error(f"Error in monitor cycle: {cycle_err}")
                    traceback.print_exc()
                
                # If forced run, exit immediately
                if args.force:
                    logger.info("Forced run finished. Exiting.")
                    break
                    
                # Calculate sleep time based on interval and elapsed cycle execution time
                elapsed = time.time() - start_time
                sleep_sec = max(10, args.interval - elapsed)
                logger.info(f"⏳ Sleeping for {sleep_sec/60:.1f} minutes until next scan cycle...")
                
                # Sleep in small steps to remain responsive to termination commands
                step = 10
                for _ in range(0, int(sleep_sec), step):
                    time.sleep(step)
            else:
                sleep_until_market_open()
                
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Monitor agent stopped by user.")
        send_agent_alert("🛑 *Market Monitor Agent Offline*.")

if __name__ == "__main__":
    from datetime import timedelta
    main()
