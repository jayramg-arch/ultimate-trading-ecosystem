
import asyncio
from playwright.async_api import async_playwright
import os

SESSION_DIR = "dhan_session"

async def log_headers():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            channel="chrome"
        )
        page = context.pages[0]
        
        async def handle_request(request):
            if "dhan.co" in request.url:
                auth = request.headers.get("authorization") or request.headers.get("page_auth") or request.headers.get("x-api-token")
                if auth:
                    print(f"📡 FOUND AUTH HEADER: {request.url}")
                    print(f"Header: {auth[:30]}... (Length: {len(auth)})")
                    if "Bearer" in auth and len(auth) > 50:
                         with open("intercepted_token.txt", "w") as f:
                             f.write(auth.replace("Bearer ", "").strip())
                         print("✅ Token saved to intercepted_token.txt")

        page.on("request", handle_request)
        
        print("🌍 Navigating to Dhan Dashboard...")
        await page.goto("https://web.dhan.co/index/home", timeout=60000)
        await page.wait_for_timeout(10000)
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(log_headers())
