import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

print(f"DEBUG: API Key found? {'Yes' if api_key else 'No'}")
if api_key:
    print(f"DEBUG: Key length: {len(api_key)}")
    print(f"DEBUG: Key prefix: {api_key[:4]}...")

try:
    if not api_key:
        print("❌ ERROR: No API Key found in .env file.")
    else:
        genai.configure(api_key=api_key)
        
        # List available models to debug generic access
        print("\nChecking available models...")
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(f"- {m.name}")
        except Exception as e:
             print(f"⚠️ Error listing models: {e}")
             print(f"Error listing models: {e}")

    # 3. Test Text Generation
    print("\nAttempting generation with 'gemini-2.0-flash'...")
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Hello, can you hear me? Respond with 'CONNECTED' if you receive this.")
        print(f"\nSUCCESS: Gemini 2.0 replied: {response.text}")
    except Exception as e:
        print(f"\nCONNECTION FAILED: {e}")

except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
