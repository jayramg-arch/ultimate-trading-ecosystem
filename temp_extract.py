
import asyncio
from playwright.async_api import async_playwright
async def run():
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context('dhan_session', headless=True)
    page = ctx.pages[0]
    await page.goto('https://login.dhan.co/?location=DH_WEB', timeout=60000)
    await page.wait_for_timeout(5000)
    print('URL:', page.url)
    token = await page.evaluate('localStorage.getItem(\'accessToken\')')
    print('TOKEN_LEN:', len(str(token)))
    if str(token) != 'None' and str(token) != 'null':
        print('TOKEN_START:', str(token)[:15])
    await ctx.close()
    await p.stop()
asyncio.run(run())

