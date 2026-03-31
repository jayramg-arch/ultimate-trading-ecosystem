from google import genai
import os
from dotenv import load_dotenv
from ai_cache_manager import get_cached_response, set_cached_response
from ai_provider_manager import ask_llm

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_tactical_analysis(symbol, sector, stage="Stage 2", rs_status="Leading", volume_status="Expanding", buy_price=0, ltp=0, sl=0, target=0, force_refresh=False):
    """Generates an institutional-grade tactical analysis focused on trend health and risk management."""
    if not GEMINI_API_KEY:
        return "Manual Entry: AI Key Missing."
    
    # Calculate P&L % for context (not for display repetition)
    pnl_pct = ((ltp - buy_price) / buy_price * 100) if buy_price > 0 else 0
    risk_dist = abs(ltp - sl) / ltp * 100 if ltp > 0 else 0

    # 1. Check Cache First (Include P&L bucket for sensitivity)
    pnl_bucket = round(pnl_pct / 2) * 2 # 2% sensitivity buckets
    cache_key = {
        "type": "institutional_analysis_v4",
        "symbol": symbol,
        "sector": sector,
        "stage": stage,
        "rs": rs_status,
        "vol": volume_status,
        "pnl_bucket": pnl_bucket
    }
    
    if not force_refresh:
        cached = get_cached_response(cache_key)
        if cached:
            return cached

    # 2. Call LLM via Bridge
    system_instruction = """
    You are a Senior Risk Desk Manager at a top-tier Hedge Fund. 
    Your tone is blunt, skeptical, and strictly analytical. 
    Talk like a trader to a trader. 
    NO fluff, NO 'it appears', NO 'confirmed', NO 'happy' language. 
    Focus on 'Price-Volume Hygiene'.
    """
    
    prompt = f"""
    Analyze active position: {symbol} ({sector}).
    
    DATA POINT:
    - P&L: {pnl_pct:.1f}% | Risk Dist: {risk_dist:.1f}% | Stage: {stage} | RS: {rs_status}.
    
    STRICT COMMANDS:
    1. NEVER repeat specific price numbers or RR ratios. They are already in the table.
    2. Zero corporate fillers or introductory phrases.
    3. Use technical judgment: Is the price action validating the Stage 2 breakout or is momentum exhausting? Is the distance to danger (risk dist) acceptable?
    4. Provide a blunt, data-driven "Risk Desk Verdict".
    5. Max 2 punchy, analytical sentences.
    
    Output assessment only.
    """
    
    fallback_text = f"Trend structure for {symbol} is structurally healthy. Momentum validates the entry with sufficient buffer from primary invalidation. Monitor for secondary VCP."
    
    result = ask_llm(prompt, system_instruction=system_instruction, fallback_text=fallback_text)
    
    # 3. Save to Cache
    if result and "Error" not in result:
        set_cached_response(cache_key, result)
        
    return result

if __name__ == "__main__":
    # Test call with new parameters to bypass old cache
    print(generate_tactical_analysis("HDFCBANK", "Banking", "Stage 1", "Lagging", "Rising", 1600, 1550, 1500, 1800))
