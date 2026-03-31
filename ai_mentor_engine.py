import sqlite3
import pandas as pd
from google import genai
import os
from dotenv import load_dotenv
from ai_cache_manager import get_cached_response, set_cached_response

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_FILE = "trade_journal_v6.db"

from ai_provider_manager import ask_llm

def get_mentor_report(force_refresh=False):
    """Generates a deep behavioral audit of closed trades with Multi-LLM bridge and local caching."""
    if not GEMINI_API_KEY:
        return "❌ Error: GEMINI_API_KEY not found in environment."

    # 1. Check Cache First
    try:
        conn = sqlite3.connect(DB_FILE)
        last_trade = pd.read_sql_query("SELECT MAX(exit_date) as last_date FROM journal WHERE status = 'CLOSED'", conn)
        conn.close()
        last_date = last_trade.iloc[0]['last_date'] or "empty"
        cache_key = {"type": "mentor_report", "last_closed_date": last_date}
        
        if not force_refresh:
            cached = get_cached_response(cache_key)
            if cached:
                return cached
    except:
        pass

    # 2. Fetch Data
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM journal WHERE status = 'CLOSED'", conn)
        conn.close()

        if df.empty:
            return "ℹ️ Not enough data yet. Complete some trades to generate an AI Mentor report!"

        # Basic Stats for context
        df['buy_price'] = pd.to_numeric(df['buy_price'], errors='coerce').fillna(0)
        df = df[df['buy_price'] > 0].copy()
        
        if df.empty:
            return "⚠️ Found trades but all have 0 buy price. Please check your journal entries."

        df['realized_pnl'] = (df['exit_price'] - df['buy_price']) * df['quantity']
        df['roi'] = (df['exit_price'] - df['buy_price']) / df['buy_price'] * 100

        trade_summary = df[['symbol', 'entry_date', 'exit_date', 'realized_pnl', 'roi', 'sector', 'exit_reason', 'lessons']].to_string()

        system_instruction = """
        You are 'Commander Mentor', a high-stakes trading coach specializing in Stan Weinstein's Stage Analysis and Mark Minervini's VCP patterns. 
        Your mission is to perform a surgical 'Post-Trade Autopsy'. You are direct, data-driven, and you focus on behavioral mastery.
        """
        prompt = f"""
        ### 📊 COMMANDER'S DATA LOG:
        {trade_summary}

        ### 🎯 MISSION OBJECTIVES:
        1. **Deep Behavioral Audit**: Analyze the 'exit_reason' and 'lessons' to identify deep-seated psychological patterns (e.g., Revenge trading, Fear of Missing Out, or Lack of trailing stops). Explain the *cost* of these biases in ROI terms.
        2. **Technical Pattern Match**: Based on the symbols and ROI, identify which technical setups (Stage 2 breakouts vs pullbacks) are yielding the best results for this specific trader.
        3. **Tactical Blueprint (Step-by-Step)**: Provide a 3-step 'Tactical Drill' for the upcoming week based on the biggest identified weakness. 
           - Step 1: What to look for on the charts.
           - Step 2: The specific rule to apply (e.g., "Set SL at 30-week SMA minus 2%").
           - Step 3: The mental trigger to hit or avoid.
        4. **Commander's Orders**: Provide 3 high-conviction, non-negotiable rules for the next 5 trading sessions.

        ### 🛠️ OUTPUT FORMAT:
        Use sharp markdown. Use Cyberpunk/Military terminology where appropriate to maintain character status.
        """
        
        fallback_text = """
### ⚠️ AI Quota Exceeded & Claude Offline
Commander, the **AI Co-Pilot** is currently in dry-dock. 
- **Status**: Mission continue with manual chart audits.
- **Note**: The cache will refresh once the API availability is restored.
        """
        
        result = ask_llm(prompt, system_instruction=system_instruction, fallback_text=fallback_text)
        
        # 3. Save to Cache
        if result and "Error" not in result:
            set_cached_response(cache_key, result)
            
        return result
        
    except Exception as e:
        return f"❌ AI Mentor Error: {str(e)}"

if __name__ == "__main__":
    print(get_mentor_report())
