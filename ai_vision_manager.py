from google import genai
import os
from dotenv import load_dotenv

# Load Env
load_dotenv(override=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def analyze_chart_screenshot(image_path, symbol):
    """
    Uses Gemini Vision to analyze a stock chart screenshot.
    """
    if not GEMINI_API_KEY:
        return "AI Vision: Key Missing."
        
    if not os.path.exists(image_path):
        return f"AI Vision: Image not found at {image_path}"

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Load image
        with open(image_path, "rb") as f:
            image_data = f.read()
            
        prompt = f"""
        Analyze this stock chart for {symbol}. 
        You are looking for technical hygiene based on Stan Weinstein's Stage 2 rules:
        1. Is it a clear Stage 2 breakout or an existing uptrend?
        2. Do you see a Volatility Contraction Pattern (VCP)? (Look for tightening price swings).
        3. Identify major Support or Resistance levels if visible.
        
        Provide a blunt, 2-sentence 'Vision Verdict'.
        Format:
        Verdict: [Blunt Assessment]
        Observation: [Technical Detail]
        """
        
        # Using types for explicit part definition
        from google.genai import types
        
        image_part = types.Part.from_bytes(
            data=image_data,
            mime_type="image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        )
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, image_part]
        )
        
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip()
            
    except Exception as e:
        return f"AI Vision Error: {str(e)}"
        
    return "AI Vision: No analysis generated."

if __name__ == "__main__":
    # Test script stub
    # print(analyze_chart_screenshot("path/to/test.png", "RELIANCE"))
    pass
