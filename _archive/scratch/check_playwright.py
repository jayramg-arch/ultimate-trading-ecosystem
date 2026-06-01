import sys
sys.path.insert(0, r"C:\Users\jayra\Documents\GeminiVSCode")

# Check playwright
try:
    from playwright.sync_api import sync_playwright
    print("Playwright Python package: OK")
    # Check if Chromium browser is installed
    import subprocess, json as _json
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
        capture_output=True, text=True
    )
    print(f"Chromium status: {result.stdout.strip() or result.stderr.strip()}")
except ImportError:
    print("Playwright NOT installed — installing now...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "--quiet"])
    print("Installing Chromium browser...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    print("Done.")
