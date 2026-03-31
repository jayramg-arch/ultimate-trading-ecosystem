import os
import json
from ai_fundamental_engine import fetch_fundamental_data
from ai_provider_manager import ask_llm
import yfinance as yf
import pandas as pd
import numpy as np
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

def fetch_technical_data(ticker_symbol: str):
    """Fetches real technical momentum indicators via yfinance."""
    clean_ticker = ticker_symbol.upper().replace("NSE:", "").replace("BSE:", "")
    if not clean_ticker.endswith(".NS") and not clean_ticker.endswith(".BO"):
        clean_ticker += ".NS"
        
    try:
        ticker = yf.Ticker(clean_ticker)
        # Fetch 1 year of daily data to calculate 200 SMA and RSI
        hist = ticker.history(period="1y")
        if hist.empty:
            return {"Error": "No historical data found."}
            
        close = hist['Close']
        vol = hist['Volume']
        
        ltp = close.iloc[-1]
        
        # SMAs
        sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None
        sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else None
        
        # 52W High/Low
        high_52w = close.max()
        low_52w = close.min()
        pct_from_high = ((ltp - high_52w) / high_52w) * 100
        
        # 14-Day RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
        if loss == 0:
            rsi_14 = 100.0
        else:
            rs = gain / loss
            rsi_14 = 100.0 - (100.0 / (1.0 + rs))
        
        # Volume Surge (Current vs 20d Avg)
        vol_20d_avg = vol.rolling(window=20).mean().iloc[-1] if len(vol) >= 20 else None
        vol_surge = (vol.iloc[-1] / vol_20d_avg) if vol_20d_avg else None
        
        return {
            "LTP": round(ltp, 2),
            "SMA_50": round(sma_50, 2) if sma_50 else "N/A",
            "SMA_200": round(sma_200, 2) if sma_200 else "N/A",
            "Trend_Alignment": "🟢 Bullish (Price > 50 > 200)" if (sma_50 and sma_200 and ltp > sma_50 and sma_50 > sma_200) else "🔴 Bearish/Mixed",
            "Pct_From_52W_High": f"{round(pct_from_high, 2)}%",
            "RSI_14": round(rsi_14, 2) if pd.notna(rsi_14) else "N/A",
            "Volume_Surge_Ratio": round(vol_surge, 2) if vol_surge else "N/A"
        }
    except Exception as e:
        return {"Error": str(e)}

def fetch_catalyst_news(ticker_symbol: str):
    """Fetches highly targeted real-time news via Google News RSS for the specific Indian stock."""
    clean_ticker = ticker_symbol.upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "").replace(".BO", "")
    
    query = urllib.parse.quote(f"{clean_ticker} NSE India OR {clean_ticker} stock news")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            items = root.findall('./channel/item')
            if not items:
                return ["No targeted company catalysts found via RSS."]
            
            catalysts = []
            for item in items[:5]:
                title = item.find('title').text if item.find('title') is not None else "Unknown Title"
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                # Clean up title and extract publisher (Google News appends publisher after a dash)
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    clean_title = parts[0].strip()
                    publisher = parts[1].strip()
                else:
                    clean_title = title.strip()
                    publisher = "News Source"
                
                # Format date string to be shorter
                short_date = pubDate[:16] if len(pubDate) >= 16 else pubDate
                
                catalysts.append(f"[{short_date} | {publisher}] {clean_title}")
                
        return catalysts
    except Exception as e:
        return [f"Error fetching RSS catalysts: {e}"]

def generate_hedge_fund_brief(ticker_symbol: str) -> str:
    """
    Generates an advanced, institutional-grade analysis for the given ticker.
    Uses yfinance fundamental data and Gemini 2.0.
    """
    print(f"🕵️ Fetching data for {ticker_symbol}...")
    
    # 1. Gather Data
    fund_data = fetch_fundamental_data(ticker_symbol)
    tech_data = fetch_technical_data(ticker_symbol)
    news_data = fetch_catalyst_news(ticker_symbol)
    
    if "Error" in fund_data and "Error" in tech_data:
        return f"### Validation Error\nCould not retrieve data for **{ticker_symbol}**. It may be invalid or delisted."
        
    combined_data = {
        "Fundamental_Metrics": fund_data,
        "Technical_Momentum": tech_data,
        "Qualitative_Catalysts": news_data
    }

    # 2. System Instruction for Gemini 2.0
    system_instruction = """
    You are an elite Quantitative & Fundamental Hedge Fund Analyst at an institutional tier-1 desk.
    Your job is to provide devastatingly clear, objective, and high-conviction trade analysis.
    You evaluate quantitative metrics strictly. You look for acceleration, catalyst setups, and risk symmetry.
    Your tone is ultra-professional, deeply analytical, and precise. No fluff.
    """

    # 3. Prompt Construction
    prompt = f"""
    TARGET SYMBOL: {ticker_symbol}
    
    RAW DATA INJECT:
    {json.dumps(combined_data, indent=2)}
    
    REQUIREMENTS:
    Based strictly on the data above, provide an advanced 'Sidecar Briefing'.
    Integrate the Technical Momentum (SMAs, RSI, Volume) tightly with the Fundamental Metrics to paint a complete picture.
    Format the output elegantly using Markdown.
    
    Structure the response exactly as follows:
    
    ### 1. The Core Thesis
    (1-2 sentences summarizing the absolute truth: Is it a screaming buy, a value trap, a momentum leader, or a short target? Why?)
    
    ### 2. Technical & Momentum Structure
    (Analyze the price action using the provided SMAs, RSI, and Volume Surge. Are we extended? Breaking out? Accumulating? Mention specific calculated levels.)
    
    ### 3. Fundamental & Institutional Reality
    (A brutally honest breakdown of profitability, valuations, and likely institutional footprint. MUST include the current Industry Analyst Sentiment (Buy/Sell/etc.) and Price Targets if available.)
    
    ### 4. Catalyst & Narrative Assessment
    (Review the provided 'Qualitative_Catalysts' news headlines. Are there earnings beats, management changes, order wins, or sector tailwinds supporting the quantitative setup? Identify explicit company events. If the news is generic aggregator noise, strictly state "No specific fundamental catalysts evident in recent news flow.")
    
    ### 5. Trade Execution Stance
    (Deliver a definitive verdict:)
    - **Bias:** [Aggressive Long / Cautious Long / Neutral / Short / Avoid]
    - **Risk Factor:** [Low / Moderate / High / Extreme]
    - **Trigger Rationale:** Why is now the exact time to deploy or pull capital?
    """

    # 4. Execute LLM Call
    print(f"🧠 Asking AI Commander Engine for Hedge Fund Brief on {ticker_symbol}...")
    llm_response = ask_llm(prompt, system_instruction=system_instruction)
    
    return llm_response

if __name__ == "__main__":
    # Test
    print(generate_hedge_fund_brief("NSE:RELIANCE"))
