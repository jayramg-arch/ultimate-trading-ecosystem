import os
import argparse
from dotenv import load_dotenv
from dhanhq import dhanhq
import math
import time
import sqlite3
from datetime import datetime, date
from dhan_symbols import get_nse_id_map
from ai_journaler_helper import generate_tactical_analysis

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
load_dotenv()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DB_FILE = "trade_journal_v6.db"

RISK_PER_TRADE_PERCENT = 0.01  # 1% Risk
MAX_CAPITAL_USAGE = 0.20       # Max 20% per stock

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')

def connect_dhan():
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_fund_limits()
        if resp['status'] == 'success':
            return dhan, resp['data']
        else:
            print("❌ API Connection Failed.")
            return None, None
    except Exception as e:
        print(f"❌ Error connecting to Dhan: {e}")
        return None, None

def log_trade_to_db(symbol, entry, stoploss, quantity, rationale):
    """Logs the trade to the SQLite journal database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Ensure table exists (safeguard)
        c.execute('''
            CREATE TABLE IF NOT EXISTS journal (
                symbol TEXT PRIMARY KEY,
                trade_type TEXT,
                stoploss REAL,
                target REAL,
                rationale TEXT,
                timeframe TEXT,
                entry_date TEXT,
                quantity REAL, 
                buy_price REAL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                status TEXT DEFAULT 'OPEN',
                sector TEXT,
                trade_quality TEXT,
                compromises TEXT,
                lessons TEXT,
                screenshot_path TEXT,
                planned_rr TEXT,
                ai_analysis TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Calculate logical target (2:1 reward/risk) for initial logging
        risk = entry - stoploss
        target = entry + (risk * 2)

        sql = '''
            INSERT INTO journal (symbol, trade_type, stoploss, target, rationale, timeframe, entry_date, quantity, buy_price, status, planned_rr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                stoploss=excluded.stoploss,
                target=excluded.target,
                rationale=excluded.rationale,
                entry_date=excluded.entry_date,
                quantity=excluded.quantity,
                buy_price=excluded.buy_price,
                status='OPEN',
                planned_rr=excluded.planned_rr
        '''
        
        c.execute(sql, (
            symbol, 
            "Positional", # Default to Positional as per scanner context
            stoploss, 
            target, 
            rationale, 
            "Daily", 
            str(date.today()), 
            quantity, 
            entry, 
            "OPEN",
            "1:2"
        ))
        
        conn.commit()
        conn.close()
        print(f"✅ Trade logged to Journal: {DB_FILE}")
        
    except Exception as e:
        print(f"⚠️ Failed to log trade to DB: {e}")

def log_ai_analysis_to_db(symbol, analysis):
    """Updates the AI analysis column in the journal."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE journal SET ai_analysis = ? WHERE symbol = ?", (analysis, symbol))
        conn.commit()
        conn.close()
        print(f"🤖 AI Tactical Analysis saved for {symbol}.")
    except Exception as e:
        print(f"⚠️ Failed to log AI analysis: {e}")

# ==========================================
# 2. RISK CALCULATOR
# ==========================================
def calculate_position_size(total_capital, entry, stoploss):
    if entry <= stoploss:
        print("❌ Error: Entry must be higher than Stoploss for a Long trade.")
        return None, None, None

    risk_per_share = entry - stoploss
    max_risk_rupees = total_capital * RISK_PER_TRADE_PERCENT
    
    if risk_per_share <= 0: return None, None, None
        
    quantity = math.floor(max_risk_rupees / risk_per_share)
    
    max_capital_allowed = total_capital * MAX_CAPITAL_USAGE
    cost_of_trade = quantity * entry
    
    if cost_of_trade > max_capital_allowed:
        print(f"⚠️ Quantity adjusted for Diversification (Max 20% Capital rule applied).")
        quantity = math.floor(max_capital_allowed / entry)

    if quantity < 1:
        print(f"❌ Error: Risk allows 0 quantity. (Capital: {total_capital}, Risk/Share: {risk_per_share})")
        return None, None, None

    return quantity, risk_per_share, max_risk_rupees

import yfinance as yf
# import pandas_ta as ta # Removed unused import to avoid dependency issues

def get_technical_analysis(symbol):
    """Fetches key technical indicators for display."""
    try:
        print(f"   • Fetching Technicals for {symbol}...")
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period="6mo")
        
        if df.empty: return None

        # Calculate Indicators (Simple Pandas)
        # EMA 20
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        # SMA 50, 150, 200
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_150'] = df['Close'].rolling(window=150).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        
        # RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        latest = df.iloc[-1]
        
        return {
            'close': latest['Close'],
            'ema_20': latest['EMA_20'],
            'sma_50': latest['SMA_50'],
            'sma_150': latest['SMA_150'],
            'sma_200': latest['SMA_200'],
            'rsi': latest['RSI']
        }
    except Exception as e:
        print(f"⚠️ Technical Fetch failed: {e}")
        return None

# ==========================================
# 3. EXECUTION ENGINE
# ==========================================
def run_sniper():
    parser = argparse.ArgumentParser(description="Sniper Execution Engine")
    parser.add_argument("symbol", nargs="?", default="", help="Stock Symbol")
    parser.add_argument("entry", nargs="?", type=float, default=0.0, help="Entry Price")
    parser.add_argument("sl", nargs="?", type=float, default=0.0, help="Stop Loss Price")
    parser.add_argument("--auto", action="store_true", help="Auto-pick from Golden Matches")
    args, unknown = parser.parse_known_args()

    cls()
    print("="*60)
    print("🎯 WEINSTEIN SNIPER: PRE-FLIGHT CHECK")
    print("="*60)

    # 0. LOAD SYMBOLS
    print("⏳ Loading Symbol Map...")
    id_map = get_nse_id_map()
    if not id_map:
        print("❌ CRITICAL: Could not load Security IDs.")
        return

    # 1. CONNECT & FETCH FUNDS
    print("⏳ Connecting to Dhan...")
    dhan, funds = connect_dhan()
    if not dhan: return

    # --- SMART CAPITAL FETCH ---
    avail_cash = 0.0
    try:
        if isinstance(funds, dict):
            avail_cash = float(funds.get('availabelBalance', 0) or 
                             funds.get('availableBalance', 0) or 
                             funds.get('availLimit', 0) or 
                             funds.get('sodLimit', 0))
    except: pass

    if avail_cash <= 0:
        print(f"\n⚠️ Could not read balance automatically.") 
        try:
            avail_cash = float(input("👉 Please Enter Available Capital Manually: "))
        except:
            print("❌ Invalid Number.")
            return

    print(f"\n💰 AVAILABLE CAPITAL: ₹ {avail_cash:,.2f}")
    print("-" * 60)

    # 2. INPUTS & ARGUMENTS
    symbol = args.symbol.upper()
    entry_price = args.entry
    sl_price = args.sl

    if args.auto and not symbol:
        import pandas as pd
        import glob
        golden_files = glob.glob("FINAL_*_Picks.csv")
        candidates = []
        for f in golden_files:
            try:
                df = pd.read_csv(f)
                sym_col = next((c for c in df.columns if 'symbol' in c.lower() or 'nsecode' in c.lower() or 'ticker' in c.lower()), None)
                if not sym_col: sym_col = df.columns[0] # Fallback
                for _, row in df.head(3).iterrows():
                    sym = str(row[sym_col]).replace("NSE:","").strip()
                    if sym: candidates.append((sym, f.replace("FINAL_","").replace("_Picks.csv","")))
            except: pass
        if candidates:
            print("\n🌟 GOLDEN MATCH CANDIDATES (Auto-Mode)")
            for i, (sym, src) in enumerate(candidates):
                print(f"  [{i+1}] {sym:<12} | {src}")
            print("  [0] CANCEL")
            try:
                idx = int(input("\n👉 Select candidate number: ")) - 1
                if 0 <= idx < len(candidates):
                    symbol = candidates[idx][0]
                else: return
            except: return
        else:
            print("⚠️ No Golden Matches found in CSVs.")

    while not symbol:
        symbol = input("👉 Enter Stock Symbol (e.g. CUB): ").strip().upper()
        if not symbol:
            print("⚠️ Symbol cannot be empty.")
            
    # VALIDATE SYMBOL
    security_id = id_map.get(symbol)
    if not security_id:
        print(f"❌ ERROR: Symbol '{symbol}' not found in NSE Equity Master.")
        input("\nPress Enter to exit...")
        return
        
    # --- TECHNICAL PREVIEW & LIVE LTP ---
    techs = get_technical_analysis(symbol)
    live_ltp = 0.0
    if techs:
        live_ltp = techs['close']
        print(f"\n📊 TECHNICAL SNAPSHOT ({symbol})")
        print(f"   • CMP (Live) : ₹ {live_ltp:.2f}")
        print(f"   • RSI (14)   : {techs['rsi']:.1f}")
        print(f"   • EMA 20     : {techs['ema_20']:.2f} (Trend: {'UP' if live_ltp>techs['ema_20'] else 'DOWN'})")
        print(f"   • SMA 50     : {techs['sma_50']:.2f}")
        print(f"   • SMA 200    : {techs['sma_200']:.2f}")
        
    if entry_price <= 0:
        try:
            print("")
            entry_price = float(input(f"👉 Enter ENTRY Price (Limit) [LTP: {live_ltp:.2f}]: "))
        except ValueError:
            print("❌ Invalid numbers.")
            return

    if sl_price <= 0:
        try:
            sl_price = float(input("👉 Enter STOPLOSS Price: "))
        except ValueError:
            print("❌ Invalid numbers.")
            return

    # 3. CALCULATE
    qty, risk_share, total_risk = calculate_position_size(avail_cash, entry_price, sl_price)
    
    if not qty:
        input("\nPress Enter to restart...")
        return

    trade_value = qty * entry_price
    
    # 4. DASHBOARD
    print("\n" + "="*50)
    print(f"📋 TRADE PLAN: {symbol}")
    print("="*50)
    print(f"   • Entry Price :  ₹ {entry_price}")
    print(f"   • Stop Loss   :  ₹ {sl_price} ({(sl_price-entry_price)/entry_price:.2%})")
    print(f"   • Quantity    :  {qty} shares")
    print("-" * 50)
    print(f"   • Total Value :  ₹ {trade_value:,.2f} (Margin Req)")
    print(f"   • TOTAL RISK  :  ₹ {total_risk:,.2f} ({RISK_PER_TRADE_PERCENT*100}% of Capital)")
    if techs:
        print(f"   • RSI Check   : {'✅ Bullish' if techs['rsi']>50 else '⚠️ Weak'}")
        print(f"   • Trend Check : {'✅ Above EMA20' if techs['close']>techs['ema_20'] else '⚠️ Below EMA20'}")
    print("="*50)

    # 5. EXECUTE
    now = datetime.now()
    mkt_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    mkt_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_market_open = (mkt_open <= now <= mkt_close) and (now.weekday() < 5)
    is_amo = not is_market_open
    
    order_type_str = "MARKET-HOURS (LIMIT)" if is_market_open else "AMO (LIMIT)"
    confirm = input(f"\n🚀 EXECUTE {order_type_str} ORDER? (Y/N): ").strip().upper()
    
    if confirm == 'Y':
        # GET RATIONALE (Required by Logic)
        print("\n📝 JOURNAL ENTRY")
        rationale = input("👉 Enter Trade Rationale (or type 'AI' for auto-gen): ")
        
        if rationale.strip().upper() == "AI":
            print("   ...Contacting AI Analyst (Institutional Flash)...")
            # Calculate logical target for AI context
            t_risk = entry_price - sl_price
            t_target = entry_price + (t_risk * 2)
            
            # Use the high-intelligence helper
            ai_report = generate_tactical_analysis(
                symbol=symbol,
                sector="General Market", # Sector detection could be added later
                buy_price=entry_price,
                ltp=live_ltp if live_ltp > 0 else entry_price, 
                sl=sl_price,
                target=t_target,
                force_refresh=True
            )
            
            print(f"\n   🤖 INSTITUTIONAL VERDICT:\n   {ai_report}\n")
            confirm_ai = input("   Confirm entries and execute? (Y/N): ").upper()
            if confirm_ai != 'Y':
                print("🚫 Order Cancelled by User.")
                return
            
            # In our new structure, 'rationale' is manual. We leave it blank or user can add.
            rationale = "AI Validated Order"
            auto_ai_analysis = ai_report
        else:
            auto_ai_analysis = ""
        
        if not rationale: rationale = " Technically Validated Setup"

        print("\n⏳ Placing Order...")
        try:
            # Using the Correct Security ID now
            order = dhan.place_order(
                security_id=security_id, 
                exchange_segment=dhan.NSE,
                transaction_type=dhan.BUY,
                quantity=qty,
                order_type=dhan.LIMIT,
                product_type=dhan.CNC,
                price=entry_price,
                after_market_order=is_amo,
                trading_symbol=symbol
            )
            
            if order['status'] == 'success':
                print(f"✅ SUCCESS! Order ID: {order['data']['orderId']}")
                
                # AUTO-LOG TO JOURNAL
                log_trade_to_db(symbol, entry_price, sl_price, qty, rationale)
                if auto_ai_analysis:
                    log_ai_analysis_to_db(symbol, auto_ai_analysis)

            else:
                print(f"❌ ORDER FAILED: {order['remarks']}")
                
        except Exception as e:
            print(f"❌ Execution Error: {e}")

    else:
        print("\n🚫 SIMULATION ENDED. No order placed.")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    run_sniper()