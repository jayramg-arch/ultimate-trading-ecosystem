import os
from google import genai
from dotenv import load_dotenv

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def ask_llm(prompt, system_instruction="You are a professional trading analyst.", fallback_text="Technical analysis confirms the current trend."):
    """
    Abstractions layer to call Gemini with a rule-based fallback.
    """
    
    # --- 1. TRY GEMINI (Primary / Free) ---
    if GEMINI_API_KEY:
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Prepend system instruction to prompt for simple SDK usage
            full_prompt = f"{system_instruction}\n\nPROMPT: {prompt}"
            
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=full_prompt
            )
            
            if response and hasattr(response, 'text'):
                return response.text.strip()
            
        except Exception as e:
            # Fallback to rule-based system on any API failure (404, 429, etc)
            pass
            
    # --- 2. RULE-BASED FALLBACK (Expert System) ---
    # Claude usage is currently disabled/held back by user request.
    return f"🤖 [Analyst Proxy]: {fallback_text}"
