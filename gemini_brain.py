import warnings
import os

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from google import genai
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

def generate_rationale(symbol):
    """
    Generates a trade rationale for the given symbol using Gemini.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    
    # INTERACTIVE FALLBACK
    if not api_key:
        print("\n⚠️ GEMINI_API_KEY not found in .env file.")
        print("   (You can get one from aistudio.google.com)")
        api_key = input("👉 Enter API Key now (to run once): ").strip()
        if not api_key:
            return "❌ Error: No API Key provided."

    print(f"   🤖 AI Analysis in progress for {symbol} (Model: gemini-2.0-flash)...")
    
    try:
        # 1. Fetch Basic Context (Price/News) to ground the AI
        ticker = yf.Ticker(f"{symbol}.NS")
        news = ticker.news
        headlines = []
        if news:
            for item in news[:3]: # Top 3 news
                headlines.append(f"- {item.get('title')}")
        
        hist = ticker.history(period="5d")
        trend = "Unknown"
        if not hist.empty:
            close = hist['Close'].iloc[-1]
            open_p = hist['Open'].iloc[0]
            change = ((close - open_p) / open_p) * 100
            trend = f"{'+' if change > 0 else ''}{change:.2f}% (5d)"

        context = f"Stock: {symbol}. Recent Trend: {trend}.\nRecent News:\n" + "\n".join(headlines)

        # 2. Call Gemini (Strictly gemini-2.0-flash)
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are a professional stock trader. 
        Context: {context}
        
        Task: Write a very concise, 2-sentence trade rationale for entering a LONG position on {symbol} now.
        Focus on technical strength or recent positive news catalysts. 
        Do not give financial advice, just the rationale.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip().replace("\n", " ")

    except Exception as e:
        return f"❌ AI Critical Error: {e}"

if __name__ == "__main__":
    # Test
    sym = input("Enter Symbol: ")
    print(generate_rationale(sym))
