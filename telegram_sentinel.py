import os
import asyncio
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import yfinance as yf
from dhanhq import dhanhq
import subprocess
import time

# Load environment variables
load_dotenv()

def set_chat_id(chat_id):
    """Saves the User's Chat ID to .env for proactive notifications."""
    env_path = ".env"
    with open(env_path, "r") as f:
         lines = f.readlines()
    
    # Check if exists
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("TELEGRAM_CHAT_ID="):
            new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
        
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    
    # Reload environment
    load_dotenv(override=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    set_chat_id(chat_id)
    
    await update.message.reply_text(
        "🤖 *Commander Jay Sentinel Online*\n\n"
        "Your Chat ID has been secured. I can now push alerts to you.\n\n"
        "*MISSION COMMANDS:*\n"
        "/initiate - 🚀 Full Auto-Pilot Protocol\n"
        "/report - 📝 Generate Strategic Briefing\n"
        "/briefing - 📋 Pilot's Morning Brief (P&L + Match)\n"
        "/portfolio - 💼 Live P&L and Holdings\n\n"
        "*PILOT TOOLS:*\n"
        "/status - Market Health Check\n"
        "/sync - Remote Master Sync (TV/Journal)\n"
        "/scan - Trigger Stage 2 Scanner\n"
        "/match - Run Golden Matcher\n"
        "/ping - Test Connection",
        parse_mode='Markdown'
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Keeping an eye on the markets... Fetching Status...")
    
    try:
        # Fetch Nifty 50 Data
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d")
        
        if hist.empty:
            await update.message.reply_text("❌ Failed to fetch Nifty data.")
            return

        last_close = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = ((last_close - prev_close) / prev_close) * 100
        
        # Determine Trend (Simple 5-day check)
        start_close = hist['Close'].iloc[0]
        trend_5d = ((last_close - start_close) / start_close) * 100
        trend_emoji = "🟢 Bullish" if trend_5d > 0 else "🔴 Bearish"

        msg = (
            f"📊 *MARKET STATUS REPORT*\n\n"
            f"🇮🇳 *Nifty 50*: {last_close:,.2f} ({change:+.2f}%)\n"
            f"📈 *5-Day Trend*: {trend_emoji} ({trend_5d:+.2f}%)\n\n"
            f"System Status: *OPERATIONAL* ✅"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Syncing with Dhan for live portfolio stats...")
    
    try:
        dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
        h_resp = dhan.get_holdings()
        f_resp = dhan.get_fund_limits()
        
        if h_resp['status'] != 'success':
            await update.message.reply_text("❌ Failed to fetch holdings from Dhan.")
            return

        holdings = h_resp['data']
        # Dhan Typo Handler
        cash = f_resp['data'].get('availabelBalance', f_resp['data'].get('availableBalance', 0)) if f_resp['status'] == 'success' else 0
        
        total_value = sum(float(h.get('lastTradedPrice', 0)) * int(h.get('totalQty', 0)) for h in holdings)
        
        # Calculate P&L manually as Dhan holdings don't always include it
        total_pnl = 0
        for h in holdings:
            ltp = float(h.get('lastTradedPrice', 0))
            avg = float(h.get('avgCostPrice', 0))
            qty = int(h.get('totalQty', 0))
            total_pnl += (ltp - avg) * qty

        pnl_pct = (total_pnl / (total_value - total_pnl) * 100) if (total_value - total_pnl) != 0 else 0
        
        emoji = "📈" if total_pnl >= 0 else "📉"
        
        msg = (
            f"💼 *PILOT PORTFOLIO SUMMARY*\n\n"
            f"💰 *Available Cash*: ₹{cash:,.2f}\n"
            f"📊 *Current Value*: ₹{total_value:,.2f}\n"
            f"{emoji} *Unrealized P&L*: ₹{total_pnl:,.2f} ({pnl_pct:+.2f}%)\n\n"
            f"*Top Positions:*"
        )
        
        # Add all holdings sorted by value
        sorted_h = sorted(holdings, key=lambda x: float(x.get('lastTradedPrice', 0)) * int(x.get('totalQty', 0)), reverse=True)
        for h in sorted_h:
            sym = h.get('tradingSymbol')
            ltp = float(h.get('lastTradedPrice', 0))
            avg = float(h.get('avgCostPrice', 0))
            qty = int(h.get('totalQty', 0))
            pos_pnl = (ltp - avg) * qty
            msg += f"\n• {sym}: {('🟢' if pos_pnl >= 0 else '🔴')} ₹{pos_pnl:,.0f}"
            
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Portfolio Fetch Failed: {e}")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    scan_id = "1" # Default to Stage 2 Hunter
    if args:
        scan_id = args[0]
        
    scan_names = {
        "1": "🚀 Stage 2 Hunter",
        "2": "📉 Swing Pullback",
        "3": "🐣 Early Birds",
        "4": "⚡ Strong Leaders"
    }
    
    scan_title = scan_names.get(scan_id, f"Scan {scan_id}")

    await update.message.reply_text(f"🚀 Running: {scan_title}...\n(This might take 5-10 seconds)")
    
    try:
        # Import dynamically to avoid circular deps or startup issues
        import chartink_scanner_pro
        import pandas as pd
        
        # Run Scanner
        df = chartink_scanner_pro.run_scan(scan_id, return_raw=True)
        
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
             await update.message.reply_text(f"⚠️ No stocks found for {scan_title}.")
             return

        # Format Results
        top_stocks = df.head(10)
        msg = f"🔎 *{scan_title.upper()} RESULTS*\n"
        
        for index, row in top_stocks.iterrows():
            sym = row['Symbol']
            price = row['Price']
            chg = row['%Chg']
            # Escape chars for MarkdownV2 if needed, but 'Markdown' mode is simpler
            msg += f"• *{sym}* : ₹{price} ({chg}%)\n"
            
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Scan Failed: {e}")

async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ Running Golden Matcher (Tech + Fundamental)...")
    
    try:
        import brute_force_match_pro
        import pandas as pd
        
        # Run Matcher
        results = brute_force_match_pro.perform_match(return_raw=True)
        
        if not results:
             await update.message.reply_text("⚠️ No Golden Matches found for ANY scan.\n(Master List might be empty or no overlap)")
             return

        # Expected Keys
        expected_scans = ["Stage 2 Hunter", "Stage 2 Pullback", "Early Birds", "Strong Leaders"]
        
        msg = "🌟 *GOLDEN MATCH REPORT* 🌟\n\n"
        has_content = False

        for strategy in expected_scans:
            # Check if we have results
            df = results.get(strategy)
            
            if df is None or df.empty:
                 msg += f"❌ *{strategy}*: 0 Matches\n"
                 continue
            
            has_content = True
            msg += f"✅ *{strategy.upper()}* ({len(df)})\n"
            
            # Show Top 5
            top_stocks = df.head(5) 
            for index, row in top_stocks.iterrows():
                # Flexible Column Access
                sym = row.get('Symbol', row.get('NSECode', 'Unknown'))
                price = row.get('Price', row.get('Current Price', 'N/A'))
                conv = row.get('Conviction', 'N/A')
                catalyst = row.get('AI_Catalyst', '')
                
                # Format line: Symbol (Score) - Catalyst
                msg += f"   • *{sym}* (₹{price}) | ⭐ *{conv}*\n"
                if catalyst and "Use AI Lab" not in catalyst:
                    msg += f"     ┗ 📑 _{catalyst}_\n"
            msg += "\n"
            
        await update.message.reply_text(msg, parse_mode='Markdown')
            
    except Exception as e:
        await update.message.reply_text(f"❌ Matcher Failed: {e}")

async def sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛰️ *Remote Sync Sequence Initiated*...\nRefreshing TradingView and Database files.")
    
    try:
        # Run master sync in background
        subprocess.Popen(["python", "master_portfolio_sync.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        await asyncio.sleep(2) # Give it a head start
        await update.message.reply_text("✅ *Master Sync Protocol Started*.\nTradingView script and local Journal are being updated in the background.")
    except Exception as e:
        await update.message.reply_text(f"❌ Sync Failed: {e}")

async def briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 *Preparing Pilot Briefing...*")
    
    # Combined report calls
    await portfolio(update, context)
    await match(update, context)
    
    await update.message.reply_text("🏁 Briefing Complete. Good luck, Commander.")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 *Initiating Strategic Briefing Workflow*...\nLaunching AI Analysis on Command Center.")
    try:
        subprocess.Popen(["python", "workflow_strategic_briefing.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        await update.message.reply_text("✅ *Strategic Briefing Started*.\nGenerating report in a new terminal window.")
    except Exception as e:
        await update.message.reply_text(f"❌ Report Generation Failed: {e}")

async def initiate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *INITIATING FULL AUTO-PILOT PROTOCOL*...\nExecuting: Scanners -> Fundamentals -> Matching -> Sync")
    try:
        subprocess.Popen(["python", "run_pipeline.py"], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        await update.message.reply_text("🔥 *Protocol Engaged*.\nFull pipeline is running in a visual console on your terminal.")
    except Exception as e:
        await update.message.reply_text(f"❌ Protocol Failed: {e}")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong! 🏓 Sentinel is listening.")

async def send_push_notification(message):
    """Utility to push a message manually if CHAT_ID is available."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Cannot send push notification.")
        return
    
    from telegram import Bot
    bot = Bot(token=token)
    try:
        # Use asyncio to run the bot command
        await bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ Push Alert Failed: {e}")

def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("\n⚠️ TELEGRAM_BOT_TOKEN not found in .env file.")
        print("   (You can get one from @BotFather on Telegram)")
        token = input("👉 Enter Bot Token now: ").strip()
        if not token:
            print("❌ No Token provided. Exiting.")
            sys.exit(1)

    print(f"🤖 Starting Commander Jay Sentinel...")
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("portfolio", portfolio))
    app.add_handler(CommandHandler("sync", sync))
    app.add_handler(CommandHandler("briefing", briefing))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("initiate", initiate))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CommandHandler("ping", ping))
    
    print("✅ Bot is Polling... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == '__main__':
    run_bot()
