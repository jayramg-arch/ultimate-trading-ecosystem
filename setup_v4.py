"""
setup_v4.py — One-time setup for Commander Web v4.0
Run this once after upgrading to v4.0:
    python setup_v4.py
"""
import sys, os
BASE = r"C:\Users\jayra\Documents\GeminiVSCode"
sys.path.insert(0, BASE)
os.chdir(BASE)

print("=" * 60)
print("  Weinstein Commander Web v4.0 — Setup")
print("=" * 60)

# ── 1. Check packages ────────────────────────────────────────
print("\n[1/4] Checking required packages...")
missing = []
for pkg, import_name in [
    ("google-generativeai", "google.generativeai"),
    ("apscheduler",         "apscheduler"),
    ("pytz",                "pytz"),
    ("streamlit",           "streamlit"),
    ("yfinance",            "yfinance"),
    ("pandas",              "pandas"),
    ("plotly",              "plotly"),
    ("requests",            "requests"),
]:
    try:
        __import__(import_name)
        print(f"  OK  {pkg}")
    except ImportError:
        print(f"  MISSING  {pkg}")
        missing.append(pkg)

if missing:
    print(f"\n  Installing missing: {', '.join(missing)}")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])
    print("  Done.")

# ── 2. Test Gemini API key ───────────────────────────────────
print("\n[2/4] Testing Gemini API key...")
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"), override=True)
    import google.generativeai as genai
    key = os.getenv("GEMINI_API_KEY")
    if key:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-3.5-flash-lite")
        resp = model.generate_content("Say: COMMANDER ONLINE in exactly 2 words.")
        print(f"  Gemini OK — Response: {resp.text.strip()}")
    else:
        print("  WARNING: GEMINI_API_KEY not found in .env")
except Exception as e:
    print(f"  WARNING: Gemini test failed: {e}")

# ── 3. Generate nifty500_symbols.json ───────────────────────
print("\n[3/4] Generating Nifty 500 symbols file...")
try:
    from market_data_hub import generate_nifty500_symbols_file
    syms = generate_nifty500_symbols_file()
    print(f"  OK — {len(syms)} symbols saved to nifty500_symbols.json")
except Exception as e:
    print(f"  WARNING: Could not generate symbols file: {e}")
    print("  Falling back to Nifty 50 hardcoded list in breadth_engine.py")

# ── 4. Create reports/ and logs/ dirs ───────────────────────
print("\n[4/4] Creating required directories...")
for d in ["reports", "logs", "screenshots"]:
    path = os.path.join(BASE, d)
    os.makedirs(path, exist_ok=True)
    print(f"  OK  {d}/")

print("\n" + "=" * 60)
print("  Setup complete! Start the app with:")
print("  streamlit run weinstein_commander_web_v4.0.py")
print("=" * 60)
