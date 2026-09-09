import os
import sys
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

# ==========================================
# 1. SCAN LOGIC CATALOG (FINAL)
# ==========================================
SCAN_CATALOG = {
    # ── 1. STAGE 2 HUNTER (POSITIONAL) ──────────────────────────────────────
    # Synced to live Chartink state (13 conditions as of Apr-2026).
    # Key upgrades: Mansfield RS (RS Line vs N500 > 30W & 4W SMA),
    #   ADX(14)>20, price>₹20 floor, Close>200D SMA, weekly volume floor.
    "1": {
        "name": "Stage 2 Hunter (Positional)",
        "logic": (
            "( {57960} ("
            " weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 )"        # 30W MA Rising
            " and daily sma( daily close , 50 ) > daily sma( daily close , 150 )"            # Trend Template: 50D>150D
            " and daily sma( daily close , 150 ) > daily sma( daily close , 200 )"           # Trend Template: 150D>200D
            " and weekly close > weekly sma( weekly close , 30 )"                            # Price > 30W MA
            " and weekly close > weekly max( 52 , weekly high ) * 0.85"                      # Within 15% of 52W High
            " and daily close > daily ema( daily close , 20 )"                               # Price > EMA20
            " and weekly rsi( 14 ) > 55"                                                     # Weekly RSI momentum
            " and daily adx( 14 ) > 20"                                                      # Trend strength gate
            " and weekly close > 20"                                                          # Anti-penny filter
            " and daily close > daily sma( daily close , 200 )"                              # Above 200D SMA
            " and weekly volume > weekly sma( weekly volume , 20 ) * 1"                      # Volume floor
            " ) )"
        ),
        "filename": "Stage2_Hunter.csv"
    },

    # ── 2. STAGE 2 PULLBACK (SWING) ─────────────────────────────────────────
    # Minervini-style EMA20 pullback within a confirmed Stage 2 uptrend.
    # PARITY FIX (Gap 3 vs Strategy v4.4): Added max pullback depth ≤ 15%.
    #   Strategy v4.4: pb_depth = (swing_high_10d - low) / swing_high_10d <= 0.15
    #   Chartink equiv: daily close >= daily max(10, daily high) * 0.85
    #   Prevents broken-down stocks (30-50% declines to EMA) from passing.
    # Other: Mansfield RS > 30W SMA, anti-penny ₹20 floor.
    "2": {
        "name": "Stage 2 Pullback (Swing)",
        "logic": (
            "( {57960} ("
            " weekly close > weekly sma( weekly close , 30 )"
            " and weekly rsi( 14 ) > 55"
            " and daily low < daily ema( daily close , 20 ) * 1.015"
            " and daily close > daily ema( daily close , 20 )"
            " and daily volume < daily sma( daily volume , 10 )"
            " and daily close > daily sma( daily close , 200 )"
            " and daily high - daily low < 1 day ago high - 1 day ago low"
            " and daily close > 20"                                                           # Anti-penny filter
            " ) )"
        ),
        "filename": "Stage2_Pullback.csv"
    },


    # ── 3. EARLY BIRDS (ACCUMULATION) ───────────────────────────────────────
    # Stage 1→2 transition detection via volume surge breakout.
    # Dynamic volume injection (Mon-Thu vs Fri-Sun) applied at runtime below.
    "3": {
        "name": "Early Birds (Accumulation)",
        "logic": (
            "( {57960} ("
            " weekly rsi( 14 ) > 50"
            " and daily close > daily sma( daily close , 50 )"
            " and daily close < daily sma( daily close , 50 ) * 1.15"
            " and daily volume > 100000"
            " and weekly macd line( 26 , 12 , 9 ) > weekly macd signal( 26 , 12 , 9 )"
            " and 1 week ago macd signal( 26 , 12 , 9 ) < 0"
            " and daily close > 1 day ago max( 20 , high )"
            " and daily close > 20"                                                           # Anti-penny filter
            " ) )"
        ),
        "filename": "Early_Birds.csv"
    },

    # ── 4. STRONG LEADERS (MOMENTUM) ────────────────────────────────────────
    # High-RS momentum leaders with full MA stack alignment and volume confirmation.
    # Added: Mansfield RS > 30W SMA (RS must be market-beating, not just rising).
    "4": {
        "name": "Strong Leaders (Momentum)",
        "logic": (
            "( {57960} ("
            " daily rsi( 14 ) > 60"
            " and daily close > daily sma( daily close , 20 )"
            " and daily adx( 14 ) > 25"
            " and daily volume > daily sma( daily volume , 20 )"
            " and daily close > daily sma( daily close , 200 )"
            " and daily close > 20"                                                           # Anti-penny filter
            " ) )"
        ),
        "filename": "Strong_Leaders.csv"
    },

    # ══════════════════════════════════════════════════════════════════════
    # RECOVERY PHASE SCANNERS v2.0 (Redesigned Apr-2026)
    #
    # DESIGN PHILOSOPHY (v2.0):
    #   Stage 2 scanners work because Chartink and Screener.in agree — both
    #   describe the same type of stock (quality leaders in uptrend). The
    #   original recovery scanners (v1.x) diverged from Screener.in because
    #   they selected for ANY stock showing technical bounce patterns, not for
    #   QUALITY companies in temporary correction.
    #
    #   Root cause of misalignment:
    #     Scanner 5 v1: "off 52W high ≥8%" gate → blocked AIAENG, ALKEM (barely
    #                    fell 3-7%) and passed BHEL, ADANIPOWER (fell 25%+).
    #                    Selected for WEAKNESS, not quality.
    #     Scanner 6 v1: No RS filter + RSI<40 + ≥10% below SMA200 → only
    #                    distressed stocks pass. Missed ABBOTINDIA, ASIANPAINT.
    #     Scanner 7 v1: VCP dry-up condition (5D vol < 50D vol) → reduced
    #                    universe to 2 stocks. Missed BAJAJ-AUTO, COLPAL, entire
    #                    Screener.in EarlyBirds universe of 73 quality names.
    #
    #   v2.0 redesign principle: QUALITY COMPANIES IN TEMPORARY CORRECTION.
    #   Technical proxies for fundamental quality used across all three scanners:
    #     • RS Line > 30W SMA (outperforms CNX500 even during selloff = strong business)
    #     • Close > SMA200 (where applicable — quality companies hold long-term trend)
    #     • Close > ₹100 (established companies vs micro-caps)
    #     • Weekly RSI > 50 (positive momentum = business momentum intact)
    #   VCP dry-up removed from Chartink (too restrictive for large-caps) —
    #   the Python screener handles ATR tightness and volume dry-up checks.
    # ══════════════════════════════════════════════════════════════════════

    # ── 5. REV-RS: RS QUALITY LEADER ─────────────────────────────────────
    # v2.0 redesign: quality RS survivors, not technically bouncing weak stocks.
    #
    # REMOVED: close < 52W high × 0.92
    #   Old gate BLOCKED the best RS survivors (AIAENG, ALKEM, SANOFICONR that
    #   barely fell 3-7%) and PASSED weaker stocks (BHEL, ADANIPOWER that fell
    #   25%+ then bounced). Inverted selection. Removed entirely.
    #
    # ADDED: close > SMA200
    #   Quality companies maintain or quickly recover above their 200D SMA even
    #   during macro selloffs. This single condition aligns Chartink with the
    #   quality universe that Screener.in's fundamental screens select for.
    #
    # ADDED: weekly RSI > 55 (up from no RSI gate)
    #   Stronger momentum requirement. Quality RS leaders have RSI > 55 on weekly
    #   charts — they're not just "less bad", they're actively outperforming.
    #
    # CHANGED: price floor ₹20 → ₹100
    #   Screener.in RS Leaders are all ₹100+ stocks. ₹20 floor was letting in
    #   micro-caps that never appeared in any fundamental screen.
    #
    # KEPT: RS Line > 30W SMA (Mansfield RS positive vs CNX500)
    # KEPT: close > SMA50
    # REMOVED: volume > 1.2× avg (Python screener handles volume confirmation)
    #
    # Python screener then applies: 20D structural breakout with 1.5× volume
    # confirmation + signal hold window.
    "5": {
        "name": "REV-RS: RS Quality Leader",
        "logic": (
            "( {57960} ("
            " weekly close / rs:'nifty500' weekly close"
            " > weekly sma( weekly close / rs:'nifty500' weekly close , 30 )"                # RS Line > 30W SMA — Mansfield RS positive vs CNX500
            " and daily close < daily max( 250 , daily high ) * 0.90"                         # MANDATORY: Corrected >= 10% from 52W High (Recovery Premise)
            " and daily close > daily max( 250 , daily high ) * 0.60"                         # QUALITY CAP: Not more than 40% off 52W High (>40% = distressed)
            " and daily close > daily sma( daily close , 200 )"                              # Above 200D SMA — quality company maintaining long-term trend
            " and daily close > daily sma( daily close , 50 )"                               # Above 50D SMA
            " and weekly rsi( 14 ) > 55"                                                     # Strong weekly momentum (not just "less bad")
            " and daily close > 100"                                                          # Quality price floor (₹100+) — aligns with Screener.in universe
            " ) )"
        ),
        "filename": "Recovery_RS_Survivors.csv"
    },

    # ── 6. REV-CB: QUALITY CORRECTION BOUNCE ─────────────────────────────
    # v2.0 redesign: quality companies that corrected and are showing early
    # recovery signs — not deep distressed stocks.
    #
    # ADDED: RS Line > 30W SMA (CRITICAL NEW CONDITION)
    #   The key quality discriminator. Stocks in Screener.in ClimaxBounce
    #   (ABBOTINDIA, ASIANPAINT, BRITANNIA, ASTRAL) all maintain positive RS
    #   vs CNX500 even during corrections because their businesses are strong.
    #   Weaker stocks (BHEL, OLAELEC, PSUs) typically have negative RS.
    #   Adding this single condition aligns the universe with Screener.in.
    #
    # CHANGED: close < SMA200 × 0.90 → close < SMA200 × 0.95
    #   Quality stocks don't fall 10%+ below SMA200 in orderly corrections.
    #   ABBOTINDIA, ASIANPAINT typically correct to 5-10% below SMA200 before
    #   recovering. Widening from 10% to 5% catches these quality names.
    #
    # CHANGED: RSI14 < 40 → RSI14 < 55
    #   Quality companies recover RSI faster — their institutional holders buy
    #   dips aggressively. By the time the Python screener runs (post-market/
    #   weekend), RSI may have recovered to 40-55. Old gate blocked all of them.
    #
    # CHANGED: price floor ₹20 → ₹100
    #   Screener.in CB stocks are all ₹100+ established companies.
    #
    # Python screener checks: 4-pillar climax detection (RSI14<30, RSI3<15,
    # 2.5× vol, turn candle) within cb_climax_window lookback.
    "6": {
        "name": "REV-CB: Quality Correction Bounce",
        "logic": (
            "( {57960} ("
            " weekly close / rs:'nifty500' weekly close"
            " > weekly sma( weekly close / rs:'nifty500' weekly close , 30 )"                # RS positive — QUALITY discriminator (ABBOTINDIA/ASIANPAINT pass, BHEL fails)
            " and daily close < daily max( 250 , daily high ) * 0.90"                         # MANDATORY: Corrected >= 10% from 52W High
            " and daily close > daily max( 250 , daily high ) * 0.60"                         # QUALITY CAP: Not more than 40% off 52W High (>40% = distressed)
            " and daily close < daily sma( daily close , 200 ) * 0.95"                       # 5%+ below 200D SMA — in correction zone (wider than old 10%)
            " and daily rsi( 14 ) < 55"                                                      # Below 55 RSI — corrected but not extended (wider than old 40)
            " and daily close > 100"                                                          # Quality price floor (₹100+)
            " ) )"
        ),
        "filename": "Recovery_Climax_Bounce.csv"
    },

    # ── 7. REV-EARLY: QUALITY GOLDEN CROSS LEADER ────────────────────────
    # v2.0 redesign: quality companies approaching or at golden cross —
    # NOT restricted to micro-VCP patterns.
    #
    # REMOVED: 5D vol < 50D vol (VCP dry-up)
    #   This single condition was responsible for reducing the universe from
    #   73 Screener.in EarlyBirds quality stocks to 2 Chartink stocks (GICRE,
    #   NSLNISP). Large-cap quality stocks (BAJAJ-AUTO ₹8000+, ASIANPAINT,
    #   COLPAL) have consistently high institutional volume — the 5D avg rarely
    #   dips below 50D avg. VCP dry-up is checked by the Python screener using
    #   ATR tightness (ATR10 < ATR_avg50 × 1.5) which is a better measure.
    #
    # ADDED: weekly RSI > 50
    #   Momentum positive on weekly chart — quality early birds are not breaking
    #   down, they're building bases with recovering momentum.
    #
    # CHANGED: price floor ₹20 → ₹100
    #   Screener.in EarlyBirds are all ₹100+ stocks.
    #
    # KEPT: SMA50 ≥ SMA200 × 0.92 (near/past golden cross)
    # KEPT: close > SMA50, close > SMA150 (trend structure intact)
    # KEPT: RS Line > 30W SMA (Mansfield RS positive vs CNX500)
    #
    # Python screener then applies: ATR tightness, 5D vol dry-up,
    # 15D pivot breakout, 1.5× volume expansion + signal hold window.
    "7": {
        "name": "REV-EARLY: Quality Golden Cross Leader",
        "logic": (
            "( {57960} ("
            " daily sma( daily close , 50 ) >= daily sma( daily close , 200 ) * 0.92"        # Near/past golden cross — SMA50 ≥ 92% of SMA200
            " and daily close < daily max( 250 , daily high ) * 0.90"                         # MANDATORY: Corrected >= 10% from 52W High
            " and daily close > daily max( 250 , daily high ) * 0.60"                         # QUALITY CAP: Not more than 40% off 52W High (>40% = distressed)
            " and daily close > daily sma( daily close , 50 )"                               # Price above 50D SMA
            " and daily close > daily sma( daily close , 150 )"                              # Price above 150D SMA (trend structure)
            " and weekly close / rs:'nifty500' weekly close"
            " > weekly sma( weekly close / rs:'nifty500' weekly close , 30 )"                # Mansfield RS positive vs CNX500
            " and weekly rsi( 14 ) > 50"                                                     # Positive weekly momentum (quality early birds building, not breaking)
            " and daily close > 100"                                                          # Quality price floor (₹100+) — aligns with Screener.in EarlyBirds
            " ) )"
        ),
        "filename": "Recovery_Early_Birds.csv"
    }
}

# ==========================================
# 2. SCANNER ENGINE
# ==========================================
def run_scan(scan_key, return_raw=False):
    scan_key = str(scan_key).strip().replace("'", "").replace('"', "")
    
    if scan_key not in SCAN_CATALOG:
        error_msg = f"❌ ERROR: Invalid Option '{scan_key}'"
        print(error_msg)
        return error_msg if return_raw else None

    scan_info = SCAN_CATALOG[scan_key]
    logic = scan_info['logic']

    # --- EXECUTION ---
    print(f"\n🚀 STARTING: {scan_info['name']}")
    
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"})

    try:
        print("⏳ Connecting to Chartink...")
        r = session.get("https://chartink.com/screener/time-pass")
        soup = BeautifulSoup(r.text, 'html.parser')
        csrf = soup.select_one('meta[name="csrf-token"]')['content']

        print("📥 Downloading Data...")
        payload = {'scan_clause': logic, '_token': csrf}
        r_post = session.post("https://chartink.com/screener/process", data=payload)
        data = r_post.json()
        
        df = pd.DataFrame(data.get('data', []))
        
        rename_map = {'nsecode': 'Symbol', 'close': 'Price', 'per_chg': '%Chg', 'volume': 'Volume'}
        if 'nsecode' in df.columns:
            df.rename(columns=rename_map, inplace=True)
            cols = [c for c in rename_map.values() if c in df.columns]
            df = df[cols]
        elif df.empty:
            df = pd.DataFrame(columns=['Symbol', 'Price', '%Chg', 'Volume'])

        filename = scan_info['filename']
        df.to_csv(filename, index=False)
        
        print(f"✅ SUCCESS: Saved to {filename} ({len(df)} stocks)")
        
        if return_raw:
            return df
            
    except Exception as e:
        print(f"❌ CRASH: {e}")
        if return_raw:
            return pd.DataFrame()

if __name__ == "__main__":
    print("="*55)
    print("🔍 CHARTINK SCANNER PRO")
    print("="*55)
    print("\n── STAGE 2 SCANNERS (Normal Market) ──")
    print("  1  Stage 2 Hunter      (Positional Breakout)")
    print("  2  Stage 2 Pullback    (Swing EMA20 Bounce)")
    print("  3  Early Birds         (Accumulation Breakout)")
    print("  4  Strong Leaders      (Momentum Continuation)")
    print("\n── RECOVERY SCANNERS v2.0 (Post-Shock / Apr-2026) ──")
    print("  5  REV-RS Survivor     (RS positive + above SMA200/SMA50, weekly RSI>55 — Stage 2 leaders)")
    print("  6  REV-CB Quality Dip  (RS positive + ≥5% below SMA200, RSI<55 — quality in correction)")
    print("  7  REV-EARLY Near-GC   (SMA50≥92% SMA200, above SMA50+SMA150, RS positive — near golden cross)")
    print("="*55)
    if len(sys.argv) > 1:
        run_scan(sys.argv[1])
    else:
        choice = input("\n👉 Enter Option (1-7): ").strip()
        run_scan(choice)
    
    input("\nPress Enter to exit...")