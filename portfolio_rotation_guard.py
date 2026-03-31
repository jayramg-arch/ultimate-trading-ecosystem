import sqlite3
import pandas as pd
import yfinance as yf
import glob
import os
import json
from dhanhq import dhanhq
from dotenv import load_dotenv
from ai_grading_engine import get_weinstein_score

DB_FILES = ['trade_journal_v7.db', 'trade_journal_v6.db']

def get_open_portfolio():
    # 1. Try Live Dhan First
    load_dotenv()
    CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
    ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
    try:
        if CLIENT_ID and ACCESS_TOKEN:
            dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
            resp = dhan.get_holdings()
            if isinstance(resp, dict) and resp.get('status') == 'success':
                symbols = set()
                for item in resp.get('data', []):
                    if float(item.get('totalQty', 0)) > 0:
                        sym = str(item.get('tradingSymbol', item.get('securityId', ''))).replace("NSE:", "").strip()
                        if sym:
                            if not sym.endswith(".NS"): sym += ".NS"
                            symbols.add(sym)
                if symbols:
                    print("✅ Successfully fetched LIVE Open Portfolio from Dhan.")
                    return list(symbols)
    except Exception as e:
        print(f"⚠️ Live Portfolio fetch failed: {e}. Falling back to Journal DB...")

    # 2. Fallback to DB
    db_file = next((f for f in DB_FILES if os.path.exists(f)), None)
    if not db_file:
        print("❌ Could not find Trade Journal DB.")
        return []
    
    conn = sqlite3.connect(db_file)
    df = pd.read_sql("SELECT symbol, buy_price FROM journal WHERE status = 'OPEN'", conn)
    conn.close()
    
    # Use a set to eliminate duplicate rows if you bought the same stock multiple times
    symbols = set()
    for sym in df['symbol'].tolist():
        sym = str(sym).replace("NSE:", "").strip()
        if not sym.endswith(".NS"):
            sym += ".NS"
        symbols.add(sym)
    return list(symbols)

def get_sector(ticker):
    try:
        t = str(ticker).replace(".NS", "").strip().upper()
        if not t.startswith("NSE:"): t = "NSE:" + t
        if os.path.exists("sector_db.json"):
            with open("sector_db.json", "r") as f:
                db = json.load(f)
            return db.get(t, "Other").replace("NSE:", "").replace("CNX", "").strip()
    except: pass
    return "Other"

def grade_stocks(symbols):
    """Assigns an Institutional Grade based on pure Minervini Structural Alignment."""
    if not symbols: return pd.DataFrame()
    
    try:
        data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, ignore_tz=True)
    except Exception as e:
        print(f"Error downloading data: {e}")
        return pd.DataFrame()
        
    results = []
    is_multi = len(symbols) > 1
    
    for symbol in symbols:
        try:
            df = data[symbol].copy() if is_multi else data.copy()
            if df.empty: continue
            
            # Ensure enough data points for 200 SMA
            if len(df) < 50:
                continue
                
            close = df['Close'].iloc[-1]
            sma50 = df['Close'].rolling(window=50).mean().iloc[-1]
            sma150 = df['Close'].rolling(window=150).mean().iloc[-1]
            sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
            
            # Pure Structural Grade (A to F)
            # A: Perfect Minervini (C > 50 > 150 > 200)
            # B: Pullback (C < 50, but 50 > 150 > 200) -- structural trend is still intact
            # C: Consolidation/Messy (C > 200, but 50 < 150)
            # D: Danger (C < 200, but 150 > 200)
            # F: Stage 4 (C < 50 < 150)
            if pd.isna(sma200): # Fallback if < 200 days of history
                sma200 = sma150 if not pd.isna(sma150) else 0
                
            if close > sma50 and sma50 > sma150 and sma150 > sma200:
                grade = "A"
                score = 5
            elif sma50 > sma150 and sma150 > sma200:
                grade = "B"
                score = 4
            elif close > sma200:
                grade = "C"
                score = 3
            elif close < sma200 and sma50 > sma200:
                grade = "D"
                score = 2
            else:
                grade = "F"
                score = 1
                
            # Get Sector
            sector = get_sector(symbol)
            clean_sym = symbol.replace('.NS', '')
            
            # Get Deep AI Ranking
            print(f"   ... Fetching AI Weinstein Grade for {clean_sym:<10} [{sector}]")
            ai_data = get_weinstein_score(
                symbol=clean_sym,
                sector=sector,
                ltp=close,
                buy_price=close,
                stage=f"Structural Grade {grade}"
            )
            
            # Boost score based on AI Stars (1 to 5 mapping onto structural 1 to 5)
            ai_rating = ai_data.get('rating', '3-Star')
            ai_reason = ai_data.get('reason', '')
            
            final_composite_score = score
            if "5-Star" in ai_rating: final_composite_score += 1.5
            elif "4-Star" in ai_rating: final_composite_score += 0.5
            elif "2-Star" in ai_rating: final_composite_score -= 1.0
            elif "1-Star" in ai_rating: final_composite_score -= 2.0
                
            results.append({
                'Symbol': clean_sym,
                'Sector': sector,
                'Current Price': round(close, 2),
                'Trend Grade': grade,
                'AI Rating': ai_rating,
                'AI Reason': ai_reason,
                'Score': final_composite_score
            })
        except Exception:
            pass
            
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by='Score', ascending=False)
    return res_df

def run_portfolio_guard():
    print("\n" + "="*60)
    print("🛡️  CAPITAL ROTATION & PORTFOLIO GUARD")
    print("="*60)
    
    open_symbols = get_open_portfolio()
    if not open_symbols:
        print("✅ No open positions found in DB. You have maximum capacity for new set-ups.")
        return

    print(f"📡 Evaluating Structural Integrity of {len(open_symbols)} Open Portfolio Stocks...")
    open_df = grade_stocks(open_symbols)
    
    if open_df.empty:
        print("❌ Could not score open portfolio.")
        return
        
    # Summarize Portfolio Health
    grade_counts = open_df['Trend Grade'].value_counts().to_dict()
    print("\n[PORTFOLIO HEALTH CHECK]")
    for g in ['A', 'B', 'C', 'D', 'F']:
        count = grade_counts.get(g, 0)
        percentage = (count / len(open_df)) * 100
        print(f"  Grade {g}: {count} stocks ({percentage:.0f}%)")
    
    # Identify Golden Matches
    golden_files = glob.glob("FINAL_*_Picks.csv")
    new_golden_symbols = set()
    for f in golden_files:
        try:
            df = pd.read_csv(f)
            sym_col = next((c for c in df.columns if c.lower() in ['symbol', 'nsecode']), None)
            if sym_col:
                for s in df[sym_col].tolist():
                    clean_sym = str(s).replace("NSE:", "").strip()
                    if clean_sym:
                        new_golden_symbols.add(clean_sym + ".NS")
        except: pass
        
    # Remove stocks already in the portfolio from the new picks
    new_golden_symbols = [s for s in new_golden_symbols if s not in open_symbols]
    
    print(f"\n🌟 Golden Matcher produced {len(new_golden_symbols)} NEW potential targets.")
    
    if len(new_golden_symbols) > 0:
        print(f"\n📡 Evaluating Structural & AI Integrity of {len(new_golden_symbols)} NEW Golden Targets...")
        new_df = grade_stocks(new_golden_symbols)
        
        # We define a "Weak Link" as Score <= 3.0 (Grade C, D, or F, OR AI degraded)
        weakest_open = open_df[open_df['Score'] <= 3.0].copy()
        
        # We only want to swap into Elite Grade setups
        strongest_new = new_df[new_df['Score'] >= 4.5].copy() if not new_df.empty else pd.DataFrame()
        
        print("\n" + "="*60)
        print("📋 CAPITAL ROTATION REPORT & AI SWAP ANALYSIS")
        print("="*60)
        
        if not weakest_open.empty and not strongest_new.empty:
            print("🚨 ROTATION ALERT: UPGRADE OPPORTUNITY DETECTED")
            print("Your portfolio holds structurally weak capital while pristine Golden Targets are available.\n")
            
            open_sectors = open_df['Sector'].tolist()
            
            print("❌ SELL CANDIDATES (Dead Money / Broken Trends / Poor AI Outlook):")
            for i, r in weakest_open.iterrows():
                print(f"  - {r['Symbol']:<12} | Grade: {r['Trend Grade']} | AI: {r['AI Rating']:<7} | Reason: {r['AI Reason']}")
                if r['Sector'] in open_sectors:
                    open_sectors.remove(r['Sector']) # Removing the sell candidate's sector to free it up
                
            print("\n✅ BUY REPLACEMENTS (Elite Technical Alignment & Fundamental Catalyst):")
            swaps_proposed = 0
            max_swaps = len(weakest_open)
            
            for i, r in strongest_new.iterrows():
                if swaps_proposed >= max_swaps: break
                
                # Prevent over-concentration (skip if portfolio already has 2+ stocks in this sector)
                sector_count = open_sectors.count(r['Sector'])
                if sector_count >= 2 and r['Sector'] != "Other":
                    print(f"  - ⚠️ SKIPPED: {r['Symbol']} (Portfolio is over-concentrated in {r['Sector']} [{sector_count}])")
                    continue
                
                print(f"  - {r['Symbol']:<12} | Sector: {r['Sector']:<15} | AI: {r['AI Rating']:<7} | Reason: {r['AI Reason']}")
                open_sectors.append(r['Sector'])
                swaps_proposed += 1
                
            if swaps_proposed == 0:
                 print("  - No optimal replacements found that pass Sector-Concentration rules.")
                
        elif weakest_open.empty:
            print("✅ Your entire open portfolio is structurally sound and AI-approved (Grade A/B limits).")
            print("Hold tight! Only add these new Golden Targets if you explicitly have excess cash capacity:")
            for i, r in strongest_new.iterrows():
                print(f"  - {r['Symbol']:<12} | Sector: {r['Sector']:<15} | AI: {r['AI Rating']:<7}")
        else:
            print("⚠️ You have weak open holdings, but no new elite setups passed the strict AI filters today.")
            print("Consider trimming these weak links to raise cash for tomorrow:")
            for i, r in weakest_open.iterrows():
                print(f"  - {r['Symbol']:<12} | Grade: {r['Trend Grade']} | AI: {r['AI Rating']:<7} | Reason: {r['AI Reason']}")
    else:
        print("\n📭 No new Golden Targets found today. Focus on managing open positions.")

if __name__ == "__main__":
    run_portfolio_guard()
