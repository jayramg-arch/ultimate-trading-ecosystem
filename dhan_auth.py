
import os
import pyotp
import asyncio
import time
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv, set_key
from dhanhq import dhanhq
from playwright.async_api import async_playwright

load_dotenv(override=True)
ENV_PATH = ".env"
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_PIN = os.getenv("DHAN_PIN")
TOTP_KEY = os.getenv("DHAN_TOTP_KEY")
SESSION_DIR = "dhan_session"
AUTH_CACHE_FILE = os.path.join(SESSION_DIR, ".last_auth")

def get_totp():
    if not TOTP_KEY: return None
    return pyotp.TOTP(TOTP_KEY.replace(" ", "")).now()

async def refresh_token_headless():
    print("🚀 Launching Aggressive Refresh...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False, # Visible to allow user interaction/login
            channel="chrome",
            no_viewport=True,
        )
        page = browser.pages[0]
        extracted_token = None
        
        try:
            print("🌍 Navigating to Profile...")
            try:
                await page.goto("https://web.dhan.co/index/profile", timeout=60000)
            except:
                print("⚠️ Page load timeout (Profile), but proceeding...")

            await page.wait_for_timeout(5000)

            # Check if we need to enter PIN inside persistent session
            if "login" in page.url or await page.locator("input[type='password']").count() > 0:
                print("🔑 Login required. Entering PIN...")
                try:
                    if await page.locator("input[type='password']").count() > 0:
                        await page.fill("input[type='password']", DHAN_PIN)
                        await page.click("button:has-text('Proceed')", timeout=3000)
                    else:
                        await page.keyboard.type(DHAN_PIN)
                except Exception as e:
                    print("Error entering PIN:", e)
                await page.wait_for_timeout(5000)

            print("🖱️ Navigating to DhanHQ Trading APIs tab...")
            try:
                await page.evaluate("""() => {
                    let apiTab = document.evaluate("//span[contains(text(), 'DhanHQ Trading APIs')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (apiTab) apiTab.click();
                }""")
            except Exception as e:
                print("Error clicking API tab:", e)
                
            await page.wait_for_timeout(4000)
            
            print("⚙️ Automating token generation 'VS Code'...")
            try:
                # Click Generate Button if present
                await page.evaluate("""() => {
                    let genBtn = document.querySelector('.generate-btn');
                    if (genBtn) genBtn.click();
                    else {
                        let textSpan = document.evaluate("//span[contains(text(), 'Generate new Access Token')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (textSpan) textSpan.click();
                    }
                }""")
                await page.wait_for_timeout(2000)
                
                # Check for input field
                if await page.locator("input[placeholder*='Application']").count() > 0:
                    print("⌨️ Typing 'VS Code' application name...")
                    # Type without wiping everything if multiple inputs, but Playwright fill is safe
                    await page.fill("input[placeholder*='Application']", "VS Code", timeout=3000)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Token generation UI interaction error: {e}")

            print("💎 Analyzing Page for Token...")
            print("⏳ Scanning for token (will retry for 60 seconds)...")

            extracted_token = None
            
            # Loop to find token (giving user time to click Generate/Show)
            for attempt in range(30): # 30 * 2s = 60s

                # Check for token in body, inputs, and clipboard buttons
                # UPDATED REGEX: Added dot (.) to capture full JWT
                found_tokens = await page.evaluate(r"""() => {
                    const text = document.body.innerText;
                    const matches = text.match(/ey[a-zA-Z0-9._-]+/g) || [];
                    
                    // Check Inputs/Textareas
                    const inputs = Array.from(document.querySelectorAll('input, textarea'));
                    inputs.forEach(input => {
                        const val = input.value || '';
                        const valMatches = val.match(/ey[a-zA-Z0-9._-]+/g);
                        if (valMatches) matches.push(...valMatches);
                    });
                    
                    // Check Clipboard Buttons
                    const buttons = Array.from(document.querySelectorAll('[data-clipboard-text]'));
                    buttons.forEach(btn => {
                         const val = btn.getAttribute('data-clipboard-text') || '';
                         const m = val.match(/ey[a-zA-Z0-9._-]+/g);
                         if (m) matches.push(...m);
                    });

                    // Check specific Dhan UI classes
                    const tokenDivs = Array.from(document.querySelectorAll('.tokencolumn, .textoverflow'));
                    tokenDivs.forEach(div => {
                        const txt = div.innerText || '';
                        const m = txt.match(/ey[a-zA-Z0-9._-]+/g);
                        if (m) matches.push(...m);
                    });

                    return [...new Set(matches)].filter(t => t.length > 200 && t.split('.').length >= 3);
                }""")

                
                if found_tokens:
                    print(f"✨ Detected {len(found_tokens)} potential token(s)... Verifying...")
                    for candidate in found_tokens:
                        if await verify_candidate(candidate):
                            extracted_token = candidate
                            break
                
                if extracted_token:
                    break
                
                if attempt % 5 == 0:
                    print(f"   ... scanning ({attempt*2}s) ...")
                await page.wait_for_timeout(2000)
            
            # If still not found after 60s
            if not extracted_token:
                print("❌ No token found after 60 seconds.")
                # Dump HTML for debugging
                content = await page.content()
                with open("debug_auth_page.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("📝 Dumped page HTML to 'debug_auth_page.html' for analysis.")

                # Get ALL potential JWT candidates (length > 200, starts with ey)
                potential_tokens = await page.evaluate(r"""() => {
                    const text = document.body.innerText;
                    const matches = text.match(/ey[a-zA-Z0-9._-]+/g) || [];
                    
                    const inputs = Array.from(document.querySelectorAll('input, textarea'));
                    inputs.forEach(input => {
                        const val = input.value || '';
                        const valMatches = val.match(/ey[a-zA-Z0-9._-]+/g);
                        if (valMatches) matches.push(...valMatches);
                    });

                    return [...new Set(matches)].filter(t => t.length > 200 && t.split('.').length >= 3);
                }""")
                
                if potential_tokens:
                    print(f"🧐 Found {len(potential_tokens)} candidate tokens. Verifying...")
                    for idx, candidate in enumerate(potential_tokens):
                        if await verify_candidate(candidate):
                            extracted_token = candidate
                            break
                            
                if not extracted_token:
                    print("❌ No JWT-like tokens found in text areas. Checking Clipboard buttons...")
                    clipboard_tokens = await page.evaluate(r"""() => {
                        const buttons = Array.from(document.querySelectorAll('[data-clipboard-text]'));
                        const matches = [];
                        buttons.forEach(btn => {
                             const val = btn.getAttribute('data-clipboard-text') || '';
                             const m = val.match(/ey[a-zA-Z0-9._-]+/g);
                             if (m) matches.push(...m);
                        });
                        return [...new Set(matches)].filter(t => t.length > 200 && t.split('.').length >= 3);
                    }""")
                    
                    if clipboard_tokens:
                         print(f"🧐 Found {len(clipboard_tokens)} tokens in COPY BUTTONS! Verifying...")
                         for idx, candidate in enumerate(clipboard_tokens):
                            if await verify_candidate(candidate):
                                extracted_token = candidate
                                break

            if extracted_token:
                # 5. Success!
                return extracted_token
            
            print("❌ Extraction failed. Manual update recommended.")
            print(f"⚠️ EXPECTED CLIENT ID: {CLIENT_ID} (Make sure you are logged into THIS account)")
            await page.screenshot(path="debug_refresh_fail.png")

        except Exception as e:
            print(f"❌ Error during refresh: {e}")
            await page.screenshot(path="debug_error.png")
        finally:
            await browser.close()
    return None

async def verify_candidate(token):
    try:
        test_dhan = dhanhq(CLIENT_ID, token)
        res = test_dhan.get_fund_limits()
        if res.get('status') == 'success':
            set_key(ENV_PATH, "DHAN_ACCESS_TOKEN", token)
            os.environ["DHAN_ACCESS_TOKEN"] = token
            print(f"✅ Token Verified and Saved! (...{token[-10:]})")
            return True
        else:
            print(f"❌ Verification failed for candidate. Response: {res}")
            return False
    except Exception as e:
        print(f"❌ Verification logic error: {e}")
        return False

def is_token_valid():
    cid = os.getenv("DHAN_CLIENT_ID")
    tok = os.getenv("DHAN_ACCESS_TOKEN")
    if not cid or not tok: return False

    # Hard Check via API (Throttling removed for accuracy)
    try:
        res = dhanhq(cid, tok).get_fund_limits()
        is_success = res.get('status') == 'success'
        
        if is_success:
            # Create/Update Cache File
            if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)
            with open(AUTH_CACHE_FILE, "w") as f: f.write(str(time.time()))
            
        return is_success
    except: return False

def ensure_valid_token():
    # Force reload environment variables to pick up changes from other processes (e.g. manual run)
    load_dotenv(override=True)
    
    if is_token_valid():
        tok = os.getenv("DHAN_ACCESS_TOKEN")
        print(f"✅ Dhan Token is valid: {tok[:20]}...")
        return tok

    print("🔄 Token invalid. Attempting headless refresh...")
    new_tok = asyncio.run(refresh_token_headless())
    
    if new_tok:
        # Update current process environment immediately
        os.environ["DHAN_ACCESS_TOKEN"] = new_tok
        return new_tok
        
    print("\n" + "!"*40 + "\n⚠️ AUTO-REFRESH FAILED\nManual update needed: https://web.dhan.co/profile/api\n" + "!"*40)
    return None

if __name__ == "__main__":
    ensure_valid_token()
