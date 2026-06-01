import asyncio
import os
import sys
import pyotp
import tkinter as tk
from tkinter import simpledialog
from dotenv import load_dotenv, set_key
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv(override=True)

_HERE    = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(_HERE, ".env")

MOBILE   = "9840715503"
PIN      = "828582"
TOTP_KEY = os.getenv("DHAN_TOTP_KEY", "")

USER_DATA_DIR = os.path.join(_HERE, "dhan_session")


def ask_sms_otp() -> str:
    """Show a popup asking user for the SMS OTP."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    otp = simpledialog.askstring(
        "Dhan SMS OTP Required",
        "Enter the 6-digit OTP sent to your mobile 9840715503:",
        parent=root
    )
    root.destroy()
    return (otp or "").strip()


async def fill_otp_boxes(page, value: str):
    """Fill OTP/PIN boxes - tries tel, password, number, text inputs in order."""
    for input_type in ["tel", "password", "number", "text"]:
        boxes = page.locator(f"input[type='{input_type}']")
        count = await boxes.count()
        if count > 0:
            print(f"    Using {count} input[type='{input_type}'] boxes")
            if count >= len(value):
                for i, ch in enumerate(value):
                    await boxes.nth(i).click()
                    await boxes.nth(i).fill(ch)
                    await page.wait_for_timeout(80)
            else:
                await boxes.first.click()
                await page.keyboard.type(value, delay=80)
            return
    # Last resort: any visible input
    print("    Fallback: typing into first visible input")
    inp = page.locator("input").first
    await inp.click()
    await page.keyboard.type(value, delay=80)


async def auto_login():
    if not TOTP_KEY:
        print("ERROR: DHAN_TOTP_KEY not set in .env"); return False

    access_token = None

    async def intercept(response):
        nonlocal access_token
        if access_token:
            return  # already have it
        try:
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                data = await response.json()
                tok = None
                # Check top-level and nested 'data' key
                if isinstance(data, dict):
                    tok = (data.get("accessToken")
                           or data.get("access_token")
                           or (data.get("data") or {}).get("accessToken")
                           or (data.get("data") or {}).get("access_token"))
                if tok and len(str(tok)) > 20:
                    access_token = str(tok).strip('"')
                    print(f"[+] Token captured from {response.url} ({len(access_token)} chars)")
        except:
            pass

    async with async_playwright() as p:
        print("[*] Launching browser...")
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.on("response", intercept)

        sms_otp_done = False
        pin_done     = False
        totp_done    = False

        try:
            print("[*] Navigating to login.dhan.co ...")
            await page.goto("https://login.dhan.co/?location=DH_WEB", timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(3000)

            for step in range(20):
                if access_token:
                    break

                await page.screenshot(path=f"dhan_step_{step}.png")

                # ── QR screen → switch to Mobile ─────────────────────────────
                if await page.locator("text=Show login with Mobile").first.is_visible(timeout=500):
                    print(f"[{step}] QR → Mobile")
                    await page.locator("text=Show login with Mobile").first.click()
                    await page.wait_for_timeout(2000)
                    continue

                # ── Mobile input ─────────────────────────────────────────────
                mobile_inp = page.locator("input[placeholder='Enter Your Mobile Number Here']")
                if await mobile_inp.first.is_visible(timeout=500):
                    print(f"[{step}] Entering mobile")
                    await mobile_inp.first.fill(MOBILE)
                    await page.click("button:has-text('Proceed')")
                    await page.wait_for_timeout(3000)
                    continue

                # ── SMS OTP screen → ask user for the code ───────────────────
                sms_screen = (
                    await page.locator("text=Verify with OTP").first.is_visible(timeout=500)
                    or await page.locator("text=Enter OTP sent to").first.is_visible(timeout=500)
                )
                if sms_screen and not sms_otp_done:
                    print(f"[{step}] SMS OTP screen — asking user for code...")
                    sms_otp = ask_sms_otp()
                    if not sms_otp:
                        print("[-] No OTP entered — aborting")
                        await ctx.close(); return False
                    await fill_otp_boxes(page, sms_otp)
                    await page.wait_for_timeout(500)
                    try:
                        btn = page.locator("button:has-text('Verify OTP')")
                        if await btn.first.is_visible(timeout=500):
                            await btn.first.click()
                    except:
                        pass
                    sms_otp_done = True
                    await page.wait_for_timeout(3000)
                    continue

                # ── PIN screen ───────────────────────────────────────────────
                pin_screen = (
                    await page.locator("text=Enter Dhan Account PIN").first.is_visible(timeout=500)
                    or await page.locator("text=Dhan Account PIN").first.is_visible(timeout=500)
                )
                if pin_screen and not pin_done:
                    print(f"[{step}] PIN screen → entering PIN")
                    await fill_otp_boxes(page, PIN)
                    await page.wait_for_timeout(1000)
                    for txt in ["Login", "Proceed", "Submit", "Verify"]:
                        try:
                            btn = page.locator(f"button:has-text('{txt}')")
                            if await btn.first.is_visible(timeout=400):
                                await btn.first.click()
                                break
                        except:
                            pass
                    pin_done = True
                    await page.wait_for_timeout(3000)
                    continue

                # ── Authenticator TOTP screen ────────────────────────────────
                totp_screen = (
                    await page.locator("text=Authenticator").first.is_visible(timeout=500)
                    or await page.locator("text=Time-based OTP").first.is_visible(timeout=500)
                    or await page.locator("text=Enter OTP from").first.is_visible(timeout=500)
                )
                if totp_screen and not totp_done:
                    totp = pyotp.TOTP(TOTP_KEY.replace(" ", "")).now()
                    print(f"[{step}] TOTP screen → {totp}")
                    await fill_otp_boxes(page, totp)
                    await page.wait_for_timeout(1000)
                    for txt in ["Verify", "Submit", "Login"]:
                        try:
                            btn = page.locator(f"button:has-text('{txt}')")
                            if await btn.first.is_visible(timeout=400):
                                await btn.first.click()
                                break
                        except:
                            pass
                    totp_done = True
                    await page.wait_for_timeout(5000)
                    continue

                # ── localStorage / sessionStorage full scan ──────────────────
                # Dhan stores the token as 'policeToken' in localStorage
                all_keys = await page.evaluate("() => Object.keys(localStorage)")
                priority = ["policeToken", "accessToken", "access_token"]
                check_keys = priority + [k for k in all_keys if k not in priority]
                for k in check_keys:
                    val = await page.evaluate(f"() => localStorage.getItem('{k}')")
                    if val and len(str(val)) > 50 and any(x in k.lower() for x in ["police","token","access","auth","jwt","session","key"]):
                        access_token = str(val).strip('"')
                        print(f"[{step}] Token from localStorage['{k}'] ({len(access_token)} chars)")
                        break
                if access_token:
                    break

                print(f"[{step}] Waiting... (url={page.url})")
                await page.wait_for_timeout(2000)

            # Final localStorage check
            if not access_token:
                tok = await page.evaluate("() => localStorage.getItem('accessToken')")
                if tok and tok not in ("null", "undefined", ""):
                    access_token = tok.strip('"')

            if access_token:
                print(f"[+] SUCCESS — writing token to .env")
                set_key(ENV_FILE, "DHAN_ACCESS_TOKEN", access_token)
                
                # Also update the E: drive .env if it exists
                e_env = r"e:\Gemini\VS Code\.env"
                if os.path.exists(e_env):
                    print(f"[+] Syncing token to {e_env}")
                    set_key(e_env, "DHAN_ACCESS_TOKEN", access_token)
                
                await ctx.close()
                return True
            else:
                await page.screenshot(path="dhan_final_fail.png")
                print("[-] Failed — check dhan_final_fail.png")
                await ctx.close()
                return False

        except Exception as e:
            print(f"[-] Exception: {e}")
            try: await page.screenshot(path="dhan_error.png")
            except: pass
            await ctx.close()
            return False


if __name__ == "__main__":
    ok = asyncio.run(auto_login())
    print("LOGIN_SUCCESS" if ok else "LOGIN_FAILED")
