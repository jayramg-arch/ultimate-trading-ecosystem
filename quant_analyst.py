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

import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
# Silence nselib's noisy ERROR-level logs ("Resource not available for Price Volume Data")
# that fire whenever NSE returns empty. The data is recovered via yfinance fallback
# (see _safe_history below); these errors are cosmetic noise, not real failures.
# Defensive duplicate of data_provider.py's silencing in case import order varies.
logging.getLogger("nselib").setLevel(logging.CRITICAL)
logging.getLogger("nselib.capital_market").setLevel(logging.CRITICAL)
logging.getLogger("nselib.capital_market.get_func").setLevel(logging.CRITICAL)

def _safe_history(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Robust OHLCV fetch via data_provider."""
    def _flatten(df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    try:
        import data_provider as _dp
        df = _dp.fetch_ohlcv(symbol, period=period, interval=interval, use_cache=True, auto_adjust=True)
        if df is not None and not df.empty:
            return _flatten(df)
    except Exception:
        pass

    return pd.DataFrame()

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

def get_dhan_balance():
    # 15-Oct-2026: the raw .env token expires daily, so this failed silently and the
    # briefing reported Rs 0 cash. ensure_valid_token() refreshes it (as journal_sync does).
    # CLIENT_ID is read at import, BEFORE this module's load_dotenv() further down, so it
    # was None unless the caller had loaded .env first - another silent Rs 0.
    try:
        from dotenv import load_dotenv as _ld
        _ld(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
        cid = CLIENT_ID or os.getenv("DHAN_CLIENT_ID")
        if not cid: return 0.0
        dhan = dhanhq(cid, ensure_valid_token())
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
        
        # Canonical Weinstein 4-stage classification (was mislabelled: Stage 3
        # called "Stage 4 Trap", Stage 1 called "Stage 2 Pullback").
        if is_rising and is_above:         stage = "STAGE 2 (UP)"
        elif not is_rising and not is_above: stage = "STAGE 4 (DOWN)"
        elif not is_rising and is_above:    stage = "STAGE 3 (TOP)"
        elif is_rising and not is_above:    stage = "STAGE 1 (BASE)"
        else:                                stage = "STAGE 1 (BASE)"

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
            # 1. Price Data — use _safe_history to avoid NoneType crash on Yahoo API failures
            hist = _safe_history(ticker, period="5d")
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
            # `t` was the yfinance Ticker built here before the _safe_history
            # refactor removed it; the NameError landed in the bare except
            # below, so this block has been contributing ZERO news items while
            # looking like it worked. yfinance is the only source for .news —
            # data_provider serves OHLCV, not headlines.
            try:
                import yfinance as _yf
                t = _yf.Ticker(ticker)
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
    # 0. THE BOOK (15-Oct-2026): live Dhan holdings joined to the journal's plan fields
    # (briefing_book). This replaced portfolio.csv + portfolio_data.json, which only ever
    # ADDED names - sold positions (RELIANCE) stayed in the report and the Gemini prompt
    # with stale quantities, and inflated "Invested Value".
    import briefing_book
    book, book_src = briefing_book.load_book()
    print(f"[-] Book: {len(book)} positions from {book_src}")
    if not book:
        print("[!] No open positions found - the briefing will carry macro only.")

    # Benchmark — _safe_history handles Yahoo chart API returning null
    print("[-] Fetching Nifty 50 Data...")
    nifty_hist = _safe_history("^NSEI", period="2y")
    if nifty_hist.empty:
        nifty_hist = _safe_history("^CRSLDX", period="2y")   # Nifty 500 fallback
    if nifty_hist.empty:
        print("[!] WARNING: Could not fetch Nifty benchmark — RS ratings will be skipped.")
    have_bench = not nifty_hist.empty
    
    # Get Macro Data
    macro_intel = get_macro_intel()
    geo_text, macro_text = generate_macro_narrative(macro_intel)
    
    # Enrich Macro Intel with Narratives
    macro_intel["Analysis"] = {
        "Geopolitics": geo_text,
        "Macro": macro_text
    }
    
    intel_dossier = []
    
    for pos in book:
        symbol = pos["symbol"]
        print(f"[>] Analyzing: {symbol}...")
        
        try:
            ticker = get_ticker(symbol)
            stock = yf.Ticker(ticker)

            # 1. Price Data - Dhan first (data_provider, the house feed), Yahoo as fallback
            df = pd.DataFrame()
            try:
                import data_provider as _dp
                df = _dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True)
                df = df if df is not None else pd.DataFrame()
            except Exception:
                df = pd.DataFrame()
            if df.empty:
                df = _safe_history(ticker, period="2y")
            if df.empty: continue
            
            # 2. Fundamentals
            fund = get_fundamentals(stock)
            
            # Sector from the board's own map (sector_lookup) - yfinance returned '.' for some
            fund['Sector'] = pos["sector"]

            # 3. Technical Structure
            stage, sma_wk, squeeze, vol_status = calculate_technical_structure(df)
            # CANONICAL stage (15-Oct-2026): the shared 2x2 on confirmed weeks (trade_class),
            # not this module's one-week slope on the forming week - the briefing had shown
            # 12/0/1 while the exit scan and Risk Shield disagreed with it and each other.
            try:
                import trade_class as _tc
                _cs = _tc.weekly_stage(df)[0]
                if _cs in (1, 2, 3, 4):
                    stage = {1: "STAGE 1 (BASE)", 2: "STAGE 2 (UP)", 3: "STAGE 3 (TOP)",
                             4: "STAGE 4 (DOWN)"}[_cs]
                else:
                    print(f"[!] {symbol}: canonical stage unavailable - local read kept")
            except Exception as _se:
                print(f"[!] {symbol}: canonical stage failed ({_se}) - local read kept")
            
            # 4. Relative Strength (skipped if benchmark unavailable)
            rs_rating = 0.0
            if have_bench:
                try:
                    common = df.index.intersection(nifty_hist.index)
                    s_c = df['Close'].loc[common]
                    n_c = nifty_hist['Close'].loc[common]
                    ratio = s_c / n_c
                    d_sma = ratio.rolling(52).mean()
                    mansfield = ((ratio / d_sma) - 1) * 10
                    rs_rating = round(float(mansfield.iloc[-1]), 2)
                except Exception:
                    rs_rating = 0.0
            
            # HOUSE RS (15-Oct-2026): JdK RS-Ratio - 100 vs Nifty 500 on confirmed weeks
            # (gm_trigger_board.rrg_live) - the RS every other surface reads. The local
            # Mansfield above (vs Nifty 50, x10 scale) stays only as the fallback.
            try:
                import gm_trigger_board as _gtb
                _rl = _gtb.rrg_live(df)
                if _rl.get("rs") is not None:
                    rs_rating = round(float(_rl["rs"]), 2)
            except Exception:
                pass

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
            
            # 8. Position (15-Oct-2026): from the book - quantity and average from Dhan, plan
            # fields from the journal. Invested = cost; CurrentValue = market value.
            qty = float(pos["qty"] or 0)
            entry_price = float(pos["avg"] or 0)
            invested = round(qty * entry_price, 2)
            position_value = round(qty * float(cmp), 2)
            pnl = round(position_value - invested, 2)
            pnl_pct = round(pnl / invested * 100, 2) if invested else 0.0
            r_mult = None
            try:
                import risk_common as _rc
                _atr = float(ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1])
                _rs, _pol = _rc.r_unit_stop({"buy_price": entry_price, "initial_sl": pos["initial_sl"],
                                             "timeframe": pos["plan"]}, _atr)
                if _rs and _rs < entry_price:
                    r_mult = round((float(cmp) - entry_price) / (entry_price - _rs), 2)
            except Exception:
                pass

            intel_dossier.append({
                "Symbol": symbol,
                "CMP": round(cmp, 2),
                "Position": {
                     "Qty": qty,
                     "AvgPrice": round(entry_price, 2),
                     "Invested": invested,
                     "CurrentValue": position_value,
                     "PnL": pnl,
                     "PnL_pct": pnl_pct,
                     "R": r_mult,
                     "Plan": pos["plan"],
                     "Setup": pos["setup"],
                     "EntryDate": pos["entry_date"],
                     "DhanSL": pos["dhan_sl"],
                     "ThesisSL": pos["thesis_sl"],
                     "InitialSL": pos["initial_sl"],
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
            time.sleep(1)   # yfinance fundamentals/news only now
            
        except Exception as e:
            print(f"[X] Error {symbol}: {e}")
            import traceback
            traceback.print_exc()
            
    # Load Account Info via Live API
    live_cash = get_dhan_balance()
    acc_info = {"AvailableCash": live_cash, "BookSource": book_src}
    try:
        import market_context as _mc
        acc_info["Context"] = _mc.for_review()
    except Exception:
        acc_info["Context"] = ""

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

def _inr(v, dec=0):
    """Indian grouping: 12,34,567 (house rule). '-' for missing."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    neg = v < 0
    v = abs(v)
    s = f"{v:.{dec}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return ("-" if neg else "") + whole + (("." + frac) if frac else "")


def generate_gemini_prompt_file(macro, portfolio, account):
    """The prompt for the Strategic Daily Briefing (rewritten 15-Oct-2026).

    Built for HOW THE BOOK IS RUN, not a generic hedge-fund note: every position carries its
    plan type, Weinstein stage, R from the frozen R unit, and the three stops (Dhan disaster,
    thesis close-exit, initial plan) plus cost vs value. The exposure rule is stated as
    BINDING, so the model cannot recommend entries or adds the house rule forbids.
    """
    import datetime as _dt
    ist = _dt.datetime.utcnow() + _dt.timedelta(hours=5, minutes=30)
    stamp = ist.strftime("%a %d %b %Y, %H:%M IST")

    cash = float(account.get("AvailableCash") or 0)
    invested = sum(float(i["Position"].get("Invested") or 0) for i in portfolio)
    value = sum(float(i["Position"].get("CurrentValue") or 0) for i in portfolio)
    pnl = value - invested
    pnl_pct = (pnl / invested * 100) if invested else 0.0

    nifty = macro.get("Nifty 50", {}) or {}
    vix = macro.get("India VIX", {}) or {}
    usd = macro.get("USD/INR", {}) or {}
    news = "".join(f"\n  - {n.get('Title')} ({n.get('Source')})" for n in (macro.get("Top_News") or [])[:4])

    # sector weights by market value
    sec = {}
    for i in portfolio:
        k = i["Fundamental"].get("Sector") or "Unassigned"
        sec[k] = sec.get(k, 0.0) + float(i["Position"].get("CurrentValue") or 0)
    sec_lines = "\n".join(f"  - {k}: Rs {_inr(v)} ({v / value * 100:.1f}%)" for k, v in
                          sorted(sec.items(), key=lambda x: -x[1])) if value else "  - none"

    rows = []
    for i in sorted(portfolio, key=lambda x: -float(x["Position"].get("CurrentValue") or 0)):
        t, f, ps, se = i["Technical"], i["Fundamental"], i["Position"], i.get("Sentiment", {})
        is_etf = "BEES" in i["Symbol"] or "ETF" in str(f.get("Sector", "")).upper()
        r = ps.get("R")
        fund = ""
        if not is_etf:
            pe = f.get("PE")
            g = f.get("ProfitGrowth")
            roe = f.get("ROE")
            de = f.get("DebtToEq")
            fund = (f"\n  Fundamentals: P/E {round(pe, 1) if isinstance(pe, (int, float)) else 'n/a'} | profit growth "
                    f"{(str(round(g * 100, 1)) + '%') if isinstance(g, (int, float)) else 'n/a'} | ROE "
                    f"{(str(round(roe * 100, 1)) + '%') if isinstance(roe, (int, float)) else 'n/a'} | D/E "
                    f"{round(de, 2) if isinstance(de, (int, float)) else 'n/a'}")
        rows.append(
            f"### {i['Symbol']} - {f.get('Sector', 'Unassigned')}{' (ETF)' if is_etf else ''}\n"
            f"  Plan: {ps.get('Plan')}{(' · setup ' + ps['Setup']) if str(ps.get('Setup') or '').upper() not in ('', 'NONE') else ''}"
            f"{(' · entered ' + str(ps['EntryDate'])[:10]) if ps.get('EntryDate') else ''}\n"
            f"  Position: {_inr(ps.get('Qty'))} sh @ Rs {_inr(ps.get('AvgPrice'), 2)} | invested Rs {_inr(ps.get('Invested'))}"
            f" | value Rs {_inr(ps.get('CurrentValue'))} | P&L {ps.get('PnL_pct', 0):+.1f}%"
            f" | R {('%+.2f' % r) if r is not None else 'n/a'}\n"
            f"  Price: CMP Rs {_inr(i['CMP'], 2)} | {t.get('Stage')} | 30-week SMA Rs {_inr(t.get('Support_SMA30'), 2)}"
            f" | {t.get('Dist_High')}% below the 52-week high | RS-Ratio {t.get('RS_Rating')} (JdK vs Nifty 500, >0 = outperforming)"
            f" | volume {t.get('Vol_Status')}{' | squeeze' if t.get('Squeeze') else ''}\n"
            f"  Stops: Dhan (disaster) Rs {_inr(ps.get('DhanSL'), 2)} | thesis (exit on a Daily close below)"
            f" Rs {_inr(ps.get('ThesisSL'), 2)} | initial plan Rs {_inr(ps.get('InitialSL'), 2)}"
            f"{fund}\n  News tone: {se.get('Rating', 'n/a')}")
    book = "\n\n".join(rows) if rows else "(no open positions)"

    prompt = f"""# ROLE
You are the risk-first portfolio reviewer for an independent NSE trader who runs a
systematic Weinstein Stage 2 / relative-strength book with ATR-based stops. Write the
Strategic Daily Briefing he reads before the open. Be specific, numerical and brief. His
system's rules are final - you explain and apply them, you do not override them.

# AS OF
{stamp} · book source: {account.get('BookSource', 'dhan')}

# ACCOUNT
- Invested (cost): Rs {_inr(invested)} | market value: Rs {_inr(value)} | unrealised P&L: Rs {_inr(pnl)} ({pnl_pct:+.1f}%)
- Cash available: Rs {_inr(cash)} | positions: {len(portfolio)}

# MARKET
- Nifty 50: {nifty.get('Trend')} ({nifty.get('Change')}%) | India VIX {vix.get('Current')} | USD/INR {usd.get('Current')} ({usd.get('Trend')})
- Global risk read: {macro.get('GeoPolitical_Risk')}
- News:{news or ' none'}
{account.get('Context') or ''}

# HOUSE RULES (apply them; never contradict them)
1. The EXPOSURE RULE above is binding. If it says no new entries or no adds, recommend none
   - say what would have to change for that to lift.
2. Stage: hold Stage 2; Stage 3 = review or trim; Stage 4 = exit review. Never "buy the dip"
   on a Stage 3 or 4 name.
3. Two-tier stop: the THESIS is exited on a Daily CLOSE below it; the Dhan stop is the
   disaster stop for gaps. Keep the Dhan stop at least 3x ATR below price; never suggest
   widening it beyond the initial plan without saying the risk grows.
4. Targets are R-multiples off the initial risk: swing 2R / 4R, positional 3R / 5R. Never
   propose a target under 2R.
5. Sector cap 25% of the book. Risk per new trade 0.5% of capital (ETF 0.75%, add 1%).
6. Plain text and Markdown only - no LaTeX, no $ signs. Rupees as Rs with Indian grouping.

# SECTOR WEIGHTS (by market value)
{sec_lines}

# THE BOOK
{book}

# OUTPUT (Markdown, these sections, in this order)
## 1. Verdict for today
Three sentences: the tape and the exposure rule; the book's health (how many in Stage 2 / 3 / 4,
unrealised P&L); the single most important action today.

## 2. Risk first
Every position that is: below or within 1% of its thesis, under 3x ATR from its Dhan stop,
in Stage 3 or 4, or at a loss beyond -1R. One line each: what is wrong and the level that decides it.

## 3. Action matrix
| Asset | Plan | Stage / RS | R now | Stops (Dhan / thesis) | Verdict | The level or trigger |
Verdict is one of HOLD, TRAIL, TRIM, EXIT REVIEW, ADD (only if the exposure rule allows).

## 4. Concentration
Sectors over or near the 25% cap, and whether the book is one trade in disguise.

## 5. Capital
What to do with cash today under the exposure rule (usually: nothing new until it lifts),
and the order to free capital if trims are due.

## 6. What would change the view
Two or three specific market or price events.
"""
    with open("Gemini_Analysis_Prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    print("[OK] Gemini Prompt File Generated: 'Gemini_Analysis_Prompt.txt'")


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
