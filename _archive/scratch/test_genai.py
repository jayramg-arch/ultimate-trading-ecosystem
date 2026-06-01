import sys
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")
from dotenv import load_dotenv
load_dotenv(override=True)
import os

# Test 1: new google-genai SDK
print("Test 1: from google import genai")
try:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    resp = client.models.generate_content(model="gemini-2.0-flash", contents="Say READY in 1 word.")
    print(f"  OK: {resp.text.strip()}")
    print("  --> Use: from google import genai")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 2: fallback - google.generativeai
print("Test 2: import google.generativeai as genai")
try:
    import google.generativeai as genai2
    genai2.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai2.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content("Say READY in 1 word.")
    print(f"  OK: {resp.text.strip()}")
    print("  --> Use: import google.generativeai as genai")
except Exception as e:
    print(f"  FAIL: {e}")
