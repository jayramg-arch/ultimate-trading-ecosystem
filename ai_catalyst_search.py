from google import genai
import os
from dotenv import load_dotenv
from ai_cache_manager import get_cached_response, set_cached_response

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from ai_provider_manager import ask_llm

def get_stock_catalyst(symbol):
    """Fetches recent news catalyst using Multi-LLM bridge with local caching."""
    if not GEMINI_API_KEY:
        return "Manual: API Key Missing."

    # 1. Check Cache First
    cache_key = {"type": "catalyst", "symbol": symbol}
    cached = get_cached_response(cache_key)
    if cached:
        return cached

    # 2. Call LLM via Bridge
    system_instruction = "You are a professional fundamental analyst specialized in the Indian stock market."
    prompt = f"""
    Find the most recent fundamental catalyst (earnings report results, management change, major new order, or sector tailwind) for the Indian stock: {symbol}.
    Focus on events from the last 3-6 months.
    Output a single sentence (max 25 words). No preamble.
    If no specific recent catalyst is found, state the primary long-term fundamental driver for this stock.
    """
    
    fallback_text = f"Bullish setup in {symbol} with constructive volume as per Weinstein Stage Analysis."
    
    result = ask_llm(prompt, system_instruction=system_instruction, fallback_text=fallback_text)
    
    # 3. Save to Cache
    if result and "Error" not in result:
        set_cached_response(cache_key, result)
        
    return result

if __name__ == "__main__":
    import sys
    test_sym = sys.argv[1] if len(sys.argv) > 1 else "COFORGE"
    print(f"Catalyst for {test_sym}: {get_stock_catalyst(test_sym)}")
