import yfinance as yf
import pandas as pd
import numpy as np
from ai_provider_manager import ask_llm

def _fetch_technicals(symbol):
    """Fetches 1-year daily data and computes key technicals for grading."""
    try:
        ticker_sym = symbol.replace("NSE:", "").replace("BSE:", "").strip()
        if not ticker_sym.startswith("^"):
            ticker_sym = f"{ticker_sym}.NS"
        
        data = yf.download(ticker_sym, period="1y", interval="1d", progress=False)
        if data.empty or len(data) < 50:
            return None
        
        # Handle MultiIndex columns from newer yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        close = float(data['Close'].iloc[-1])
        sma50 = float(data['Close'].rolling(50).mean().iloc[-1])
        sma150 = float(data['Close'].rolling(150).mean().iloc[-1]) if len(data) >= 150 else sma50
        sma200 = float(data['Close'].rolling(200).mean().iloc[-1]) if len(data) >= 200 else sma150
        sma200_10 = float(data['Close'].rolling(200).mean().shift(10).iloc[-1]) if len(data) >= 210 else sma200
        ema20 = float(data['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
        
        # New Catalyst Metrics (v4.0 Hybrid Engine)
        high_low = data['High'] - data['Low']
        high_close = (data['High'] - data['Close'].shift()).abs()
        low_close = (data['Low'] - data['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr10 = float(tr.rolling(10).mean().iloc[-1])
        atr40 = float(tr.rolling(40).mean().iloc[-1])
        vcp_tight = atr10 < (atr40 * 0.75)
        
        direction = np.sign(data['Close'].diff())
        obv = (direction * data['Volume']).cumsum()
        obv_latest = float(obv.iloc[-1])
        obv_h50_1 = float(obv.shift(1).rolling(50).max().iloc[-1])
        
        p_h50 = float(data['High'].rolling(50).max().iloc[-1])
        h10_1 = float(data['High'].shift(1).rolling(10).max().iloc[-1])
        
        def calc_rsi(series, lookback):
            delta = series.diff()
            gain = delta.where(delta > 0, 0.0).rolling(lookback).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(lookback).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

        rsi70 = float(calc_rsi(data['Close'], 70).iloc[-1])
        rsi3 = float(calc_rsi(data['Close'], 3).iloc[-1])
        
        o = float(data['Open'].iloc[-1])
        h1 = float(data['High'].iloc[-2]) if len(data) > 1 else o
        v_sma = float(data['Volume'].rolling(50).mean().iloc[-1])
        v = float(data['Volume'].iloc[-1])
        
        # RSI 14
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        
        # Volume profile
        vol_avg = v_sma
        vol_latest = v
        rel_vol = vol_latest / vol_avg if vol_avg > 0 else 1.0
        
        # 52-week high/low
        high_52w = float(data['High'].max())
        low_52w = float(data['Low'].min())
        pct_from_52w_high = ((close - high_52w) / high_52w) * 100
        
        # Dynamic Catalyst Tag
        cat = "NONE"
        is_stg2 = (close > sma150) and (sma150 > sma200) and (sma200 > sma200_10)
        is_stg1 = not is_stg2 and (close > sma200)
        
        d_flat = ((p_h50 - close) / close) > 0.08
        if (is_stg1 or is_stg2) and (obv_latest > obv_h50_1) and d_flat and vcp_tight:
            cat = "POS-ACCUM"
        elif is_stg2 and (close > high_52w * 0.95) and (v > v_sma * 1.5):
            cat = "POS-BO"
        elif is_stg2 and (o > h1 * 1.02) and (close > o):
            cat = "SWG-GAP"
        elif is_stg2 and vcp_tight and (close > h10_1) and (v > v_sma * 1.2):
            cat = "SWG-BO"
        elif is_stg2 and (close > ema20) and (((close - ema20) / ema20) < 0.05) and (v < v_sma) and (rsi > 40) and (rsi70 > 55):
            cat = "SWG-PB"
        elif is_stg2 and (rsi3 < 20) and (((ema20 - close) / ema20) > 0.05):
            cat = "SWG-REV"
        
        return {
            'close': close, 'sma50': sma50, 'sma150': sma150, 'sma200': sma200,
            'ema20': ema20, 'rsi': rsi, 'rel_vol': rel_vol,
            'high_52w': high_52w, 'low_52w': low_52w,
            'pct_from_52w_high': pct_from_52w_high,
            'catalyst': cat
        }
    except Exception as e:
        print(f"⚠️ Technical fetch failed for {symbol}: {e}")
        return None


def _quant_grade(techs):
    """
    Deterministic Quant Grading based on Minervini Structural Alignment.
    Returns (grade_letter, numeric_score, breakdown_dict).
    """
    if not techs:
        return "N/A", 0, {}
    
    c = techs['close']
    s50, s150, s200 = techs['sma50'], techs['sma150'], techs['sma200']
    ema20, rsi, rv = techs['ema20'], techs['rsi'], techs['rel_vol']
    
    score = 0
    breakdown = {}
    
    # 1. SMA Stack Alignment (0-30 pts)
    if c > s50 and s50 > s150 and s150 > s200:
        score += 30
        breakdown['SMA Stack'] = 'Perfect (C > 50 > 150 > 200)'
    elif s50 > s150 and s150 > s200:
        score += 20
        breakdown['SMA Stack'] = 'Pullback (50 > 150 > 200, but C < 50)'
    elif c > s200:
        score += 10
        breakdown['SMA Stack'] = 'Messy (C > 200, disordered MAs)'
    else:
        score += 0
        breakdown['SMA Stack'] = 'Broken (C < 200)'
    
    # 2. Proximity to 20 EMA (0-15 pts)
    dist_ema = abs((c - ema20) / ema20) * 100
    if dist_ema < 3:
        score += 15
        breakdown['EMA Proximity'] = f'Tight ({dist_ema:.1f}%)'
    elif dist_ema < 8:
        score += 10
        breakdown['EMA Proximity'] = f'Moderate ({dist_ema:.1f}%)'
    elif dist_ema < 15:
        score += 5
        breakdown['EMA Proximity'] = f'Extended ({dist_ema:.1f}%)'
    else:
        score += 0
        breakdown['EMA Proximity'] = f'Dangerously Extended ({dist_ema:.1f}%)'
    
    # 3. RSI Health (0-20 pts)
    if 55 <= rsi <= 75:
        score += 20
        breakdown['RSI'] = f'Optimal ({rsi:.0f})'
    elif 45 <= rsi < 55:
        score += 12
        breakdown['RSI'] = f'Neutral ({rsi:.0f})'
    elif rsi > 75:
        score += 5
        breakdown['RSI'] = f'Overbought ({rsi:.0f})'
    else:
        score += 0
        breakdown['RSI'] = f'Weak ({rsi:.0f})'
    
    # 4. Volume Confirmation (0-15 pts)
    if rv > 1.5:
        score += 15
        breakdown['Volume'] = f'Institutional Surge ({rv:.1f}x)'
    elif rv > 1.0:
        score += 10
        breakdown['Volume'] = f'Above Average ({rv:.1f}x)'
    else:
        score += 3
        breakdown['Volume'] = f'Dry ({rv:.1f}x)'
    
    # 5. Distance from 52-Week High (0-20 pts)
    pct_hi = techs['pct_from_52w_high']
    if pct_hi > -5:
        score += 20
        breakdown['52W High'] = f'Near High ({pct_hi:.1f}%)'
    elif pct_hi > -15:
        score += 12
        breakdown['52W High'] = f'Healthy ({pct_hi:.1f}%)'
    elif pct_hi > -30:
        score += 5
        breakdown['52W High'] = f'Correcting ({pct_hi:.1f}%)'
    else:
        score += 0
        breakdown['52W High'] = f'Deep Correction ({pct_hi:.1f}%)'
    
    # Map to Grade
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "F"
    
    return grade, score, breakdown


def get_weinstein_score(symbol, sector, ltp, buy_price, rs_status="Unknown", stage="Stage 2"):
    """
    Hybrid Quant + AI Grading Engine.
    1. Quant Layer: Deterministic structural scoring from real market data.
    2. AI Layer: LLM generates a human-readable justification grounded in the quant results.
    """
    from ai_cache_manager import get_cached_response, set_cached_response
    import json
    
    # --- EARLY CACHE CHECK (before any network calls) ---
    cache_key = {
        "type": "weinstein_grade_v2",
        "symbol": symbol
    }
    
    cached = get_cached_response(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except: pass
    
    # --- QUANT LAYER (only runs on cache miss) ---
    techs = _fetch_technicals(symbol)
    grade, quant_score, breakdown = _quant_grade(techs)
    
    # Map quant score to star rating
    if quant_score >= 80:
        star_rating = "5-Star"
    elif quant_score >= 60:
        star_rating = "4-Star"
    elif quant_score >= 40:
        star_rating = "3-Star"
    elif quant_score >= 20:
        star_rating = "2-Star"
    else:
        star_rating = "1-Star"
    
    # --- AI NARRATIVE LAYER ---
    breakdown_text = "\n".join([f"  - {k}: {v}" for k, v in breakdown.items()])
    
    system_instruction = """
    You are the WEINSTEIN GUARD, an expert in Stan Weinstein's 'Stage Analysis'.
    You are given a QUANT SCORECARD with real market data. Your ONLY job is to write
    a 15-word maximum institutional-grade summary explaining the rating.
    Tone: Blunt, technical, hedge fund. No pleasantries.
    """
    
    prompt = f"""
    Trade: {symbol} ({sector}) | LTP: {ltp}
    
    QUANT SCORECARD (Grade {grade}, Score {quant_score}/100):
{breakdown_text}
    
    The quant model assigned: {star_rating}.
    COMMAND: Write a single-line, 15-word-max institutional justification for this rating.
    FORMAT: Reason: [your justification]
    """
    
    try:
        response = ask_llm(prompt, system_instruction=system_instruction)
        reason = "Quant-graded structural assessment."
        if "Reason:" in response:
            reason = response.split("Reason:")[1].strip().split("\n")[0]
    except:
        reason = f"Grade {grade} ({quant_score}/100). {breakdown.get('SMA Stack', 'N/A')}."
    
    final_result = {
        "rating": star_rating,
        "reason": reason,
        "quant_grade": grade,
        "quant_score": quant_score,
        "breakdown": breakdown,
        "catalyst": techs.get("catalyst", "NONE") if techs else "NONE"
    }
    
    set_cached_response(cache_key, json.dumps(final_result))
    return final_result


if __name__ == "__main__":
    result = get_weinstein_score("RELIANCE", "Energy", 2550, 2500, "Leading", "Stage 2")
    print(f"Rating: {result['rating']}")
    print(f"Grade: {result['quant_grade']} ({result['quant_score']}/100)")
    print(f"Reason: {result['reason']}")
    for k, v in result['breakdown'].items():
        print(f"  {k}: {v}")
