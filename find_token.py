
import asyncio
from playwright.async_api import async_playwright
import os

SESSION_DIR = "dhan_session"

async def find_token():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = context.pages[0]
        await page.goto("https://web.dhan.co/index/home", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Comprehensive search script
        token = await page.evaluate("""() => {
            function isToken(v) {
                return typeof v === 'string' && v.length > 50 && (v.split('.').length === 3 || v.startsWith('ey'));
            }

            // 1. Search localStorage
            for (let i = 0; i < localStorage.length; i++) {
                let v = localStorage.getItem(localStorage.key(i));
                if (isToken(v)) return v;
            }

            // 2. Search sessionStorage
            for (let i = 0; i < sessionStorage.length; i++) {
                let v = sessionStorage.getItem(sessionStorage.key(i));
                if (isToken(v)) return v;
            }

            // 3. Search window object (shallow)
            for (let k in window) {
                try {
                    let v = window[k];
                    if (isToken(v)) return v;
                    if (typeof v === 'object' && v !== null) {
                         for (let sk in v) {
                             if (isToken(v[sk])) return v[sk];
                         }
                    }
                } catch(e) {}
            }
            return null;
        }""")
        
        if token:
            print(f"✅ FOUND TOKEN! (Length: {len(token)})")
            # Mask and print for verification
            print(f"Token start: {token[:20]}...")
            
            # Save to .env
            from dotenv import set_key
            ENV_PATH = os.path.join(os.getcwd(), ".env")
            set_key(ENV_PATH, "DHAN_ACCESS_TOKEN", token)
            print("💾 Token saved to .env")
        else:
            print("❌ Token not found in storage or window object.")
            
        await context.close()

if __name__ == "__main__":
    asyncio.run(find_token())
