import json
import re
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
import os

from dhan_auth import ensure_valid_token
from dhanhq import dhanhq

INPUT_FILE = "portfolio_data.json"
OUTPUT_FILE = "market_intel.json"

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

def get_dhan_balance():
    try:
        if not CLIENT_ID or not ACCESS_TOKEN: return 0.0
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_fund_limits()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', {})
            return float(data.get('availabelBalance', data.get('availableBalance', 0.0)))
        return 0.0
    except:
        return 0.0

def get_live_holdings():
    try:
        if not CLIENT_ID or not ACCESS_TOKEN: return {}
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_holdings()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', [])
            holding_map = {}
            for item in data:
                sym = item.get('tradingSymbol', '').split('-')[0]
                qty = float(item.get('totalQty', 0))
                avg = float(item.get('avgCostPrice', 0))
                if qty > 0 and sym:
                    holding_map[sym] = {'Qty': qty, 'Avg': avg}
            return holding_map
        return {}
    except:
        return {}

# --- CONFIGURATION ---
STAGE_MA_LENGTH = 30       # Weekly SMA for Stage Analysis
RS_LENGTH = 52             # Mansfield RS Length

def get_ticker(symbol):
    cleaned = clean_symbol(symbol)
    if cleaned.startswith("^"): return cleaned
    return f"{cleaned}.NS"

def get_fundamentals(stock_obj):
    try:
        info = stock_obj.info
        return {
            "Sector": info.get('sector', 'ETF / Index'),
            "Industry": info.get('industry', 'Exchange Traded Fund'),
            "MarketCapCr": round(info.get('marketCap', 0) / 10000000, 2) if info.get('marketCap') else 0,
            "PE": info.get('trailingPE'),
            "PEG": info.get('pegRatio'),
            "PB": info.get('priceToBook'),
            "ROE": info.get('returnOnEquity'),
            "RevGrowth": info.get('revenueGrowth'),
            "ProfitGrowth": info.get('earningsGrowth'),
            "DebtToEq": info.get('debtToEquity'),
            "Beta": info.get('beta'),
            # Enhanced Metrics
            "BookValue": info.get('bookValue'),
            "OperatingMargins": info.get('operatingMargins'),
            "FreeCashflow": info.get('freeCashflow')
        }
    except:
        return {}

def calculate_technical_structure(df):
    # 1. Stage Analysis (Weekly)
    df_weekly = df.resample('W').agg({'Close': 'last', 'Volume': 'sum'})
    df_weekly['SMA30'] = ta.sma(df_weekly['Close'], length=STAGE_MA_LENGTH)
    
    stage = "TRANSITION"
    sma_wk = 0
    if len(df_weekly) > 32:
        curr = df_weekly.iloc[-1]
        prev = df_weekly.iloc[-2]
        sma_wk = curr['SMA30']
        is_rising = curr['SMA30'] > prev['SMA30']
        is_above = curr['Close'] > curr['SMA30']
        
        if is_rising and is_above: stage = "STAGE 2 (UP)"
        elif not is_rising and not is_above: stage = "STAGE 4 (DOWN)"
        elif not is_rising and is_above: stage = "STAGE 4 (TRAP)"
        elif is_rising and not is_above: stage = "STAGE 2 (PULLBACK)"
        else: stage = "STAGE 1 (BASE)"

    # 2. Volatility Squeeze (Daily)
    bands = ta.bbands(df['Close'], length=20)
    is_squeeze = False
    if bands is not None:
         cols = [c for c in bands.columns if "BBB" in c]
         if cols:
             bw = bands[cols[0]]
             if bw.iloc[-1] < bw.tail(126).min() * 1.15: is_squeeze = True

    # 3. Accumulation/Distribution
    df['Vol_SMA'] = df['Volume'].rolling(50).mean()
    df['Ret'] = df['Close'].pct_change()
    recent = df.tail(50)
    acc_days = len(recent[(recent['Ret'] > 0) & (recent['Volume'] > recent['Vol_SMA'])])
    dist_days = len(recent[(recent['Ret'] < 0) & (recent['Volume'] > recent['Vol_SMA'])])
    vol_net = acc_days - dist_days
    
    vol_status = "Neutral"
    if vol_net > 2: vol_status = "Accumulation"
    elif vol_net < -2: vol_status = "Distribution"
    
    return stage, sma_wk, is_squeeze, vol_status

def get_news_sentiment(stock_obj):
    # ... (Same as before, abbreviated for brevity in replacement) ...
    try:
        news = stock_obj.news
        if not news: return "Neutral", []
        headlines = []
        score = 0
        for n in news[:3]:
            title = n.get('title', '')
            headlines.append(title)
            t_low = title.lower()
            if any(x in t_low for x in ['profit', 'jump', 'surge', 'buy', 'record', 'growth']): score += 1
            if any(x in t_low for x in ['loss', 'fall', 'plunge', 'sell', 'fraud', 'weak']): score -= 1
        if score > 0: return "Positive", headlines
        if score < 0: return "Negative", headlines
        return "Neutral", headlines
    except: return "Neutral", []

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping suffixes and mapping indices."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY" or "NIFTYBANK" in s: return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

def indian_format(num):
    """Formats a number into the Indian numbering system (e.g., 1,23,456.78)."""
    try:
        if num is None or (isinstance(num, str) and num.upper() == "N/A"): return "N/A"
        f_num = float(num)
        is_neg = f_num < 0
        f_num = abs(f_num)
        
        s = f"{f_num:.2f}"
        parts = s.split('.')
        main = parts[0]
        
        if len(main) <= 3:
            res = main
        else:
            last_three = main[-3:]
            remaining = main[:-3]
            rev_rem = remaining[::-1]
            groups = [rev_rem[i:i+2] for i in range(0, len(rev_rem), 2)]
            res = ",".join(groups)[::-1] + "," + last_three
        
        final = f"{res}.{parts[1]}"
        return f"-{final}" if is_neg else final
    except:
        return str(num)

import warnings
warnings.filterwarnings("ignore") # Silence Deprecation Warnings
from google import genai
from dotenv import load_dotenv

# Load Env
load_dotenv()

def generate_analyst_commentary(tech, fund, dist_high):
    """
    Generates 'Deep Research' style commentary using Gemini API (if available) or Expert System fallback.
    """
    # 1. Prepare Data Context
    symbol = fund.get('Symbol', 'Unknown')
    sector = fund.get('Sector', 'Unknown')
    stage = tech['Stage']
    rs = tech['RS_Rating']
    
    # 2. Check for API Key (Support both names)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    # --- API DISABLED FOR MANUAL PROMPT GENERATION ---
    # if api_key:
    #     try:
            # ... API Logic Commented Out ...
    #         pass 
            
    # --- RULE BASED FALLBACK (Original & Enhanced) ---
            
    # --- RULE BASED FALLBACK (Original & Enhanced) ---
    # 1. TECHNICAL THESIS
    thesis = f"The asset is currently in a {stage} structure. "
    if "STAGE 2" in stage:
        thesis += "Price action confirms a constructive uptrend, supported by accumulation volume. "
        if tech['Vol_Status'] == "Accumulation":
            thesis += "Institutional footprints are visible (Buying on Dips). "
    elif "STAGE 4" in stage:
        thesis += "Technical structure is weak, characterized by lower highs and distribution. "
    else:
        thesis += "Price is consolidating (Stage 1 or 3), building a base for the next potential move. "
        
    if tech['Squeeze']:
        thesis += "CRITICAL: A Volatility Contraction Pattern (VCP) is detected, often preceding an explosive move. "
    
    if rs > 0:
        thesis += f"It exhibits positive Relative Strength (RS: {rs}), outperforming the Nifty 50 benchmark."
    else:
        thesis += f"Relative Strength is lagging ({rs}), indicating potential rotation into other sectors."

    # 2. FUNDAMENTAL / MACRO CONTEXT
    pe = fund.get('PE', 0)
    mk_cap = fund.get('MarketCap', 0)
    symbol_name = fund.get('Symbol', '')
    
    context = ""
    # Special ETF Handling
    is_etf = "MCX" in str(sector) or "ETF" in str(sector) or "BEES" in str(symbol_name) or "Index" in str(sector)
    
    if is_etf:
        context = f"This is a passive tracking instrument for the {sector} theme. "
        if "GOLD" in str(sector) or "SILV" in str(sector):
            context += "It acts as a strategic hedge against currency depreciation and global inflation. Historically uncorrelated to equities."
        elif "NIFTY" in str(sector) or "SENSEX" in str(sector) or "BANK" in str(sector):
            context += "It provides broad market exposure, suitable for core portfolio allocation and long-term compounding."
        elif "AUTO" in str(sector) or "IT" in str(sector) or "PHARMA" in str(sector):
            context += f"Provides concentrated exposure to the {sector} cyclical theme."
    else:
        # Stock Analysis
        if pe and pe > 0:
            val_status = "premium" if pe > 60 else "moderate" if pe > 25 else "undervalued"
            if pe > 80:
                context += f"Valuations are stretched (P/E: {pe:.1f}), pricing in high growth expectations. Risk of mean reversion exists if earnings miss. "
            else:
                context += f"Valuations appear {val_status} relative to growth (P/E: {pe:.1f}). "
        
        # Market Cap Logic
        if mk_cap > 100000:
            context += "As a Large Cap entity, it offers stability but typically lower beta. "
        elif mk_cap > 0:
            context += "Mid/Small Cap nature implies higher growth potential, albeit with elevated volatility. "
            
        pro_growth = fund.get('ProfitGrowth', 0)
        if pro_growth and pro_growth > 0.2:
            context += f"Strong Earnings Momentum ({round(pro_growth*100)}% Growth) supports the bullish thesis. "
            
        # Enhanced Checks
        roe = fund.get('ROE', 0)
        if roe and roe > 0.15:
            context += f"Quality compounding machine with High ROE ({round(roe*100)}%). "
            
        d2e = fund.get('DebtToEq', 0)
        if d2e and d2e > 1.5:
            context += f"CAUTION: High Debt levels (D/E: {d2e:.2f}) warrants monitoring. "

    # 3. STRATEGIC VERDICT & SENTIMENT RATING
    verdict = "HOLD"
    verdict_desc = ""
    
    # Map to Strong Buy / Buy / Hold / Sell / Strong Sell
    rating = "Hold"
    
    if "STAGE 2" in stage and rs > 0:
        verdict = "BUY / ACCUMULATE"
        rating = "Strong Buy" if tech['Vol_Status'] == "Accumulation" or tech['Squeeze'] else "Buy"
        verdict_desc = "Strong Uptrend + Relative Strength. Any pullback to the 30-week SMA (" + str(tech['Support_SMA30']) + ") is a low-risk entry opportunity."
    elif "STAGE 4" in stage:
        verdict = "SELL / AVOID"
        rating = "Strong Sell" if rs < -5 else "Sell"
        verdict_desc = "Downtrend dominant. Capital preservation is priority; avoid catching a falling knife until a Stage 1 base forms."
    elif tech['Squeeze']:
        verdict = "BUY STOP"
        rating = "Buy"
        verdict_desc = "Volatility Squeeze imminent. Set a Buy Stop above the recent consolidation high to capture the breakout momentum."
    else:
        verdict = "HOLD"
        rating = "Hold"
        verdict_desc = f"Consolidation Phase. Maintain exposure but keep stops loose below {tech['Support_SMA30']}. Wait for a renewed breakout to add."
        
    return thesis, context, verdict, verdict_desc, rating

def get_macro_intel():
    """
    Fetches Macro-Economic indicators and determines Market Regime.
    Also fetches top Global/India news.
    """
    print("[-] Fetching Macro-Economic Data & News...")
    tickers = {
        "Nifty 50": "^NSEI",
        "India VIX": "^INDIAVIX",
        "USD/INR": "INR=X",
        "Crude Oil": "CL=F",
        "Gold": "GC=F",
        "US 10Y Bond": "^TNX"
    }
    
    macro_data = {}
    collected_news = []
    seen_titles = set()
    
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            
            # 1. Price Data
            hist = t.history(period="5d")
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                chg = ((current - prev) / prev) * 100
                macro_data[name] = {
                    "Current": round(current, 2),
                    "Change": round(chg, 2),
                    "Trend": "UP" if current > prev else "DOWN"
                }
            else:
                macro_data[name] = {"Current": 0, "Change": 0, "Trend": "FLAT"}
            
            # 2. News Data
            try:
                news = t.news
                if news:
                    for n in news[:2]: # Top 2 per asset
                        title = n.get('title', '')
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            collected_news.append({
                                "Source": name,
                                "Title": title,
                                "Link": n.get('link', '')
                            })
            except: pass
            
        except:
            macro_data[name] = {"Current": 0, "Change": 0, "Trend": "FLAT"}
            
    # Geo-Political Proxy (High Oil + High Gold + High VIX)
    geo_risk = "LOW"
    oil = macro_data["Crude Oil"]["Current"]
    gold = macro_data["Gold"]["Current"]
    vix = macro_data["India VIX"]["Current"]
    
    if oil > 90 or gold > 2500 or vix > 20: geo_risk = "HIGH"
    elif oil > 80 or gold > 2400 or vix > 15: geo_risk = "MODERATE"
    
    macro_data["GeoPolitical_Risk"] = geo_risk
    macro_data["Top_News"] = collected_news[:8] # Limit to top 8 unique stories
    
    return macro_data

def extract_trade_details(notes_list):
    """
    Parses user notes to extract Qty and Entry price for Portfolio Analysis.
    Expects format: '... Qty#1= 50 ... Entry#1=1240 ...'
    """
    if not notes_list: return 0, 0
    latest_note = notes_list[0] # Assuming first note is latest based on example
    
    qty = 0
    entry = 0
    
    # Simple RegEx for Qty#1 and Entry#1
    import re
    qty_match = re.search(r"Qty#1=\s*(\d+)", latest_note)
    entry_match = re.search(r"Entry#1=\s*([\d\.]+)", latest_note)
    
    if qty_match: qty = int(qty_match.group(1))
    if entry_match: entry = float(entry_match.group(1))
    
    return qty, entry

def generate_macro_narrative(macro_data):
    """
    Generates text-based analysis of the macro environment.
    """
    # 1. Geopolitical Analysis
    geo_risk = macro_data.get("GeoPolitical_Risk", "LOW")
    gold = macro_data["Gold"]["Current"]
    oil = macro_data["Crude Oil"]["Current"]
    vix = macro_data["India VIX"]["Current"]
    
    geo_text = f"Current Geopolitical Risk is rated {geo_risk}."
    if geo_risk == "HIGH":
        geo_text += f" This is driven by elevated Crude Oil (${oil}) and Gold (${gold}), indicating safe-haven demand amidst global tensions."
    elif geo_risk == "MODERATE":
        geo_text += " While Oil and Gold are stabilizing, underlying volatility (VIX) suggests market caution."
    else:
        geo_text += " Key fear gauges (Gold, VIX) are dormant, suggesting a stable geopolitical backdrop for equities."
        
    # 2. Macro-Economic Context
    us10y = macro_data["US 10Y Bond"]
    usdinr = macro_data["USD/INR"]
    
    macro_text = ""
    # Interest Rate / Curbency Logic
    if us10y["Trend"] == "UP" and usdinr["Trend"] == "UP":
        macro_text = "Capital Outflow Risk: Rising US Bond Yields and a strengthening USD are creating headwinds for Emerging Markets like India. FII flows may remain negative."
    elif us10y["Trend"] == "DOWN":
        macro_text = "Liquidity Boost: Cooling US Bond Yields are increasing risk appetite for equities. This environment favors growth stocks and high-beta sectors."
    else:
        macro_text = "Neutral Macro Setup: Currency and Yields are range-bound. Domestic triggers (Earnings, Budget) will drive market direction."
        
    if vix > 15:
        macro_text += f" High Volatility (VIX {vix}) warrants tighter Stop Losses."
        
    return geo_text, macro_text

def analyze_market():
    # 0. Sync Data & Get CSV Metadata
    csv_metadata = sync_portfolio_json() # sync_portfolio now returns metadata
    
    # 0.5 Fetch live portfolio and cash to guarantee 100% accuracy in reporting
    print("[-] Fetching live holdings from broker...")
    live_portfolio = get_live_holdings()

    print("[*] Launching Hybrid Intelligence Scanner...")
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    # Benchmark
    print("[-] Fetching Nifty 50 Data...")
    nifty = yf.Ticker("^NSEI")
    nifty_hist = nifty.history(period="2y")
    
    # Get Macro Data
    macro_intel = get_macro_intel()
    geo_text, macro_text = generate_macro_narrative(macro_intel)
    
    # Enrich Macro Intel with Narratives
    macro_intel["Analysis"] = {
        "Geopolitics": geo_text,
        "Macro": macro_text
    }
    
    intel_dossier = []
    
    for symbol, lines in raw_data.items():
        print(f"[>] Analyzing: {symbol}...")
        
        try:
            ticker = get_ticker(symbol)
            stock = yf.Ticker(ticker)
            
            # 1. Price Data
            df = stock.history(period="2y")
            if df.empty: continue
            
            # 2. Fundamentals
            fund = get_fundamentals(stock)
            
            # OVERRIDE SECTOR FROM CSV
            if symbol in csv_metadata:
                csv_sector = csv_metadata[symbol].get('Sector')
                if csv_sector and "NSE:" in str(csv_sector):
                    # Clean up "NSE:CNXAUTO" -> "Auto"
                    clean_sec = str(csv_sector).replace("NSE:", "").replace("CNX", "")
                    fund['Sector'] = clean_sec
                elif csv_sector:
                     fund['Sector'] = str(csv_sector)
            
            # 3. Technical Structure
            stage, sma_wk, squeeze, vol_status = calculate_technical_structure(df)
            
            # 4. Relative Strength
            common = df.index.intersection(nifty_hist.index)
            s_c = df['Close'].loc[common]
            n_c = nifty_hist['Close'].loc[common]
            ratio = s_c / n_c
            d_sma = ratio.rolling(52).mean()
            mansfield = ((ratio / d_sma) - 1) * 10
            rs_rating = round(mansfield.iloc[-1], 2)
            
            # 5. Sentiment
            sent, headlines = get_news_sentiment(stock)
            
            # 6. Distances
            cmp = df['Close'].iloc[-1]
            high52 = df['Close'].tail(252).max()
            dist_high = round(((high52 - cmp) / high52) * 100, 1)
            
            tech_dict = {
                "Stage": stage,
                "Support_SMA30": round(sma_wk, 2),
                "RS_Rating": rs_rating,
                "Vol_Status": vol_status,
                "Squeeze": squeeze,
                "Dist_High": dist_high
            }
            
            # 7. EXPERT SYSTEM GENERATION
            thesis, context, verdict, verdict_desc, rating = generate_analyst_commentary(tech_dict, fund, dist_high)
            
            # 8. Portfolio Details Extraction (Live API Priority > CSV Fallback)
            qty = 0
            entry_price = 0
            
            # Prefer absolute live reality
            if symbol in live_portfolio:
                qty = int(live_portfolio[symbol]['Qty'])
                entry_price = float(live_portfolio[symbol]['Avg'])
            elif symbol in csv_metadata:
                qty = int(csv_metadata[symbol].get('Qty', 0))
                entry_price = float(csv_metadata[symbol].get('Entry', 0))
            
            position_value = round(qty * cmp, 2)
            
            intel_dossier.append({
                "Symbol": symbol,
                "CMP": round(cmp, 2),
                "Position": {
                     "Qty": qty,
                     "AvgPrice": entry_price,
                     "CurrentValue": position_value
                },
                "Technical": tech_dict,
                "Fundamental": fund,
                "Sentiment": {
                    "Mood": sent,
                    "Headlines": headlines,
                    "Rating": rating
                },
                "Analysis": {
                    "Thesis": thesis,
                    "Context": context,
                    "Verdict": verdict,
                    "Verdict_Desc": verdict_desc
                }
            })
            
            # Rate Limit Safety
            time.sleep(4) 
            
        except Exception as e:
            print(f"[X] Error {symbol}: {e}")
            import traceback
            traceback.print_exc()
            
    # Load Account Info via Live API
    live_cash = get_dhan_balance()
    acc_info = {"AvailableCash": live_cash}

    final_output = {
        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "Account": acc_info,
        "Macro": macro_intel,
        "Portfolio": intel_dossier
    }
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4)
        
    # Generate Gemini Prompt File
    generate_gemini_prompt_file(macro_intel, intel_dossier, acc_info)
        
    print(f"[OK] Market Intelligence Gathered. Saved to {OUTPUT_FILE}")

def generate_gemini_prompt_file(macro, portfolio, account):
    """
    Creates a detailed prompt file for manual Gemini Pro analysis.
    User-defined 'Deep Research' structure.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Prepare Macro Data Block
    macro_block = f"""
    - Global Risk Sentiment: {macro.get('GeoPolitical_Risk')}
    - Indian Market Trend (Nifty 50): {macro['Nifty 50']['Trend']} ({macro['Nifty 50']['Change']}%)
    - Volatility Index (India VIX): {macro['India VIX']['Current']}
    - Currency (USD/INR): {macro['USD/INR']['Current']} ({macro['USD/INR']['Trend']})
    - Key News Flow:
    """
    for n in macro.get('Top_News', [])[:4]:
        macro_block += f"      * {n['Title']} ({n['Source']})\n"

    # 1.1 Account Context
    cash = account.get('AvailableCash', 0)
    acc_block = f"Available Capital for Deployment: INR {cash:,.2f}"

    # 2. Prepare Portfolio Data Block
    portfolio_block = ""
    for item in portfolio:
        sym = item['Symbol']
        tech = item['Technical']
        fund = item['Fundamental']
        pos = item['Position']
        sent = item.get('Sentiment', {})
        
        # Calculate/Format Data Points
        pe_ratio = fund.get('PE')
        if pe_ratio is None: pe_ratio = "N/A"
        
        profit_growth = fund.get('ProfitGrowth')
        if profit_growth is None: profit_growth = "N/A"
        else: profit_growth = f"{round(profit_growth * 100, 1)}%"

        # New Metrics
        roe = fund.get('ROE', 'N/A')
        roestr = f"{round(roe*100, 1)}%" if isinstance(roe, (int, float)) else "N/A"
        
        de = fund.get('DebtToEq', 'N/A')
        destr = f"{round(de, 2)}" if isinstance(de, (int, float)) else "N/A"
        
        is_etf = "MCX" in str(fund.get('Sector')) or "ETF" in str(fund.get('Sector')) or "BEES" in str(sym) or "Index" in str(fund.get('Sector'))

        if is_etf:
            portfolio_block += f"""
    ### CONSTITUENT (ETF/INDEX): {sym}
    - **Type**: Exchange Traded Fund / Index Tracker
    - **Price Structure**: {tech['Stage']} | CMP: {indian_format(item['CMP'])}
    - **Trend Support**: 30-W SMA: {indian_format(tech['Support_SMA30'])} | Dist. from 52W High: -{tech['Dist_High']}%
    - **Relative Strength**: {tech['RS_Rating']} (vs Nifty Benchmark)
    - **Tracking Goal**: {fund.get('Sector', 'Market Index')}
    - **Analyst Sentiment Rating**: {sent.get('Rating', 'Hold')}
    - **Current Exposure**: Qty: {indian_format(pos['Qty'])} | Avg Price: {indian_format(pos['AvgPrice'])}
    - **ETP SPECIAL INSTRUCTIONS**: Analyze this as an Index/Sector proxy. Evaluate the underlying sector rotation, macroeconomic sensitivity (USD, Rates, Commodities), and tracking efficiency. Ignore traditional P/E or growth ratios for this instrument.
    --------------------------------------------------
    """
        else:
            portfolio_block += f"""
    ### CONSTITUENT (STOCK): {sym}
    - **Sector**: {fund.get('Sector', 'Unknown')}
    - **Price Structure**: {tech['Stage']} | CMP: {indian_format(item['CMP'])}
    - **Trend Support**: 30-W SMA: {indian_format(tech['Support_SMA30'])} | Dist. from 52W High: -{tech['Dist_High']}%
    - **Relative Strength**: {tech['RS_Rating']}
    - **Volume & Momentum**: {tech['Vol_Status']} | Squeeze: {'ACTIVE' if tech['Squeeze'] else 'None'}
    - **Fundamental Health**: P/E: {pe_ratio} | Growth (NP): {profit_growth} | ROE: {roestr} | D/E: {destr}
    - **Analyst Sentiment Rating**: {sent.get('Rating', 'Hold')}
    - **Current Exposure**: Qty: {indian_format(pos['Qty'])} | Avg Price: {indian_format(pos['AvgPrice'])}
    --------------------------------------------------
    """

    # 3. Construct the Full Prompt
    prompt = f"""
# SYSTEM ROLE
You are a **Senior Quantitative Analyst** at a top-tier Hedge Fund. Your mandate is to produce a "Strategic Daily Briefing" for the Chief Investment Officer (CIO). Your analysis must be data-driven, institutional in tone, and highly specific.

# INPUT DATA
## [TIMESTAMP]
{timestamp}

## [ACCOUNT_INFO]
{acc_block}

## [MACRO_DATA]
{macro_block}

## [PORTFOLIO_LIST]
{portfolio_block}

# ANALYTICAL FRAMEWORKS
You must apply the following frameworks to the provided data:

1.  **Technical Analysis (Weinstein & Momentum)**:
    -   Classify assets into **Stage 1 (Base)**, **Stage 2 (Uptrend)**, **Stage 3 (Top)**, or **Stage 4 (Downtrend)** based on the provided "Price Structure" and "30-Week SMA".
    -   Use **Relative Strength (RS)** to identify leaders vs. laggards.
    -   Flag "Squeeze Alerts" as high-potential breakout setups.

2.  **Fundamental & ETP Analysis**:
    -   For Stocks: Compare **P/E Ratios** against **Profit Growth** (PEG principle). Identify "Stretched", "Fair", or "Undervalued" valuations.
    -   For ETFs: Analyze the **Sectoral Theme** momentum and its weight in the portfolio relative to macroeconomic trends.

3.  **Sentiment Composite**:
    -   Incorporate the provided **Analyst Sentiment (Strong Buy/Buy/Hold/Sell/Strong Sell)** into the final verdict.
    -   Factor in Volume Status (Accumulation = Bullish, Distribution = Bearish).

# VISION ANALYSIS (MULTI-MODAL AUDIT)
If I have attached a chart screenshot:
1.  **Stage Confirmation**: Visually confirm if the price is above the 30-week SMA and if the SMA is rising (Stage 2).
2.  **Pattern Recognition**: Identify VCP (Volatility Contraction), Cup & Handle, or Breakout patterns.
3.  **Volume Verification**: Check for 'Institutional Footprints' (large green volume bars) during the recent rally.
4.  **Verdict**: Provide a 'Technical Audit' score (1-10) based on the visual chart quality matched with the provided fundamental data.

# OUTPUT STRUCTURE (Strict Markdown)

## 1. Executive Summary
*   **Market Narrative**: Synthesize the `[MACRO_DATA]` into a brief 3-sentence narrative on the current risk environment (Risk-On / Risk-Off).
*   **Portfolio Health**: A quick pulse check on the `[PORTFOLIO_LIST]` (e.g., "Portfolio is heavily weighted towards Stage 2 leaders...").

## 2. Sectoral Deep Dives
*   Group the assets by their Sector.
*   Provide a mini-analysis of the strongest vs. weakest sectors in the portfolio.

## 3. Asset Action Matrix
*   Create a TABLE with the following columns:
    | Asset | Grouping | Technical Verdict | Sentiment Score (0-100) | Key Levels | Fundamental Check | Actionable Advice |
    | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
    *   **Grouping**: Growth / Value / Momentum / defensive.
    *   **Technical Verdict**: BUY / ACCUMULATE / HOLD / TRIM / SELL.
    *   **Actionable Advice**: Specific instruction (e.g., "Add on dip to 1450", "Trailing Stop at 30W SMA").

## 4. Investment Strategy
*   **Allocation Shift**: Based on Macro and Techs, should we increase Cash, Aggressively Deploy, or Rotate Sectors?
*   **Top Pick**: Identify the single highest-conviction idea from the list.

# CONSTRAINTS
-   Do **NOT** provide generic advice like "do your own research". You are an analyst; give your professional opinion.
-   Be concise. Use bullet points.
-   Focus on **Risk Management** (Stop Losses) as much as Upside.
"""

    with open("Gemini_Analysis_Prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    print("📝 Gemini Prompt File Generated: 'Gemini_Analysis_Prompt.txt'")

def sync_portfolio_json():
    """
    Syncs portfolio_data.json to match symbols in portfolio.csv.
    Returns metadata dict for Sector/Qty/Entry overrides.
    """
    csv_path = "portfolio.csv"
    json_path = INPUT_FILE
    metadata = {}
    
    if not os.path.exists(csv_path): return {}

    try:
        df = pd.read_csv(csv_path)
        valid_tickers = []
        
        for _, row in df.iterrows():
            t_str = str(row['Ticker']).strip()
            if "NSE:" in t_str: t_str = t_str.replace("NSE:", "")
            
            if t_str:
                valid_tickers.append(t_str)
                metadata[t_str] = {
                    "Sector": row.get("Sector", ""),
                    "Qty": row.get("Qty", 0),
                    "Entry": row.get("Entry", 0)
                }
            
        # Sync JSON
        current_data = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        
        new_data = {}
        for tick in valid_tickers:
            if tick in current_data: new_data[tick] = current_data[tick]
            else: new_data[tick] = []
                
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)
            
        return metadata
        
    except Exception as e:
        print(f"❌ Sync Error: {e}")
        return {}

if __name__ == "__main__":
    analyze_market()
