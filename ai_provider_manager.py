import os
import requests
import logging
from google import genai
from dotenv import load_dotenv

# Suppress excessive INFO logging from the GenAI SDK
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Reusable client instance (avoid recreating per call)
_gemini_client = None
def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'timeout': 30_000})
    return _gemini_client

def ask_llm(prompt, system_instruction="You are a professional trading analyst.", fallback_text="Technical analysis confirms the current trend."):
    """
    Abstractions layer to call LLMs with cascading providers:
    1. Gemini (Primary / Free)
    2. Perplexity Pro (Secondary / Fallback)
    3. Rule-based fallback
    """
    # --- 1. TRY GEMINI (Primary / Paid Tier) ---
    client = _get_gemini_client()
    if client:
        import time
        for attempt in range(3):
            try:
                # Prepend system instruction to prompt for simple SDK usage
                full_prompt = f"{system_instruction}\n\nPROMPT: {prompt}"
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=full_prompt
                )
                
                if response and hasattr(response, 'text'):
                    return response.text.strip()
                
            except Exception as e:
                if attempt < 2:
                    logging.warning(f"[ask_llm] Gemini call failed (attempt {attempt+1}/3): {e} - Retrying...")
                    time.sleep(1.5 * (attempt + 1))
                else:
                    logging.error(f"[ask_llm] Gemini call failed on final attempt (3/3): {e}", exc_info=True)
                    pass
    
    # --- 2. TRY PERPLEXITY PRO (Secondary / Paid) ---
    if PERPLEXITY_API_KEY:
        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar-pro",
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2048,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            # Fallback to rule-based system on any Perplexity failure
            pass
            
    # --- 3. RULE-BASED FALLBACK (no prefix) ---
    return fallback_text


def ask_llm_fast(prompt, system_instruction="Give direct trading actions. No preamble, no disclaimers. 1 sentence max.", fallback_text="Monitor position."):
    """
    Lightweight, fast LLM call for batch short reviews.
    Uses gemini-2.0-flash-lite for speed. Single attempt, no retries.
    Falls back silently on any error.
    """
    client = _get_gemini_client()
    if client:
        try:
            full_prompt = f"{system_instruction}\n\n{prompt}"
            response = client.models.generate_content(
                model='gemini-2.0-flash-lite',
                contents=full_prompt
            )
            if response and hasattr(response, 'text'):
                text = response.text.strip()
                # Remove any AI role-play prefixes
                for prefix in ["[Analyst Proxy]:", "🤖 [Analyst Proxy]:", "**Action:**", "Action:"]:
                    if text.startswith(prefix):
                        text = text[len(prefix):].strip()
                return text
        except Exception as e:
            logging.warning(f"[ask_llm_fast] Failed for prompt: {e}")
    
    return fallback_text
