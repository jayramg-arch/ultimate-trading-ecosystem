import asyncio
import os
import sys
from dotenv import set_key
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_HERE    = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_HERE, ".env")
USER_DATA_DIR = os.path.join(_HERE, "dhan_session")

async def extract_token():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            args=["--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # The session is already logged in — go to dashboard
        await page.goto("https://web.dhan.co/dashboard", timeout=30000)
        await page.wait_for_timeout(5000)

        print(f"URL: {page.url}")

        # Dump all localStorage keys
        all_keys = await page.evaluate("() => Object.keys(localStorage)")
        print(f"localStorage keys: {all_keys}")

        token = None
        for key in all_keys:
            val = await page.evaluate(f"() => localStorage.getItem('{key}')")
            if val and len(val) > 50:
                print(f"  {key}: {val[:60]}...")
                if any(k in key.lower() for k in ["token", "access", "auth", "jwt", "session"]):
                    token = val.strip('"')

        # Try sessionStorage too
        ss_keys = await page.evaluate("() => Object.keys(sessionStorage)")
        print(f"sessionStorage keys: {ss_keys}")
        for key in ss_keys:
            val = await page.evaluate(f"() => sessionStorage.getItem('{key}')")
            if val and len(val) > 50:
                print(f"  SS {key}: {val[:60]}...")
                if any(k in key.lower() for k in ["token", "access", "auth", "jwt"]):
                    token = val.strip('"')

        # Try cookies
        cookies = await ctx.cookies()
        for c in cookies:
            if len(c.get("value","")) > 50:
                print(f"  Cookie {c['name']}: {c['value'][:60]}...")
                if any(k in c['name'].lower() for k in ["token", "access", "auth", "jwt"]):
                    token = c['value']

        if token:
            print(f"\n[+] Found token ({len(token)} chars) — saving to .env")
            set_key(ENV_FILE, "DHAN_ACCESS_TOKEN", token)
        else:
            print("\n[-] No token found in localStorage/sessionStorage/cookies")

        await ctx.close()

asyncio.run(extract_token())
