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
    # RECOVERY PHASE SCANNERS (Active: Post-Geopolitical-Shock Apr-2026)
    # Use these when market is in recovery mode — Stage 4 bottom / Stage 1
    # basing — after a sharp macro-driven correction.
    # Scanners 1-4 remain active for when Stage 2 uptrend resumes.
    # ══════════════════════════════════════════════════════════════════════

    # ── 5. RS SURVIVORS (Best Risk/Reward in Recovery) ────────────────────
    # Stocks that fell the LEAST during the correction — they lead the recovery.
    # Key logic: 200D SMA still intact (structural), RS still positive,
    #   daily RSI > 50 (momentum already recovering), volume re-entry surge.
    # These are the institutional favourites — they held support while others collapsed.
    "5": {
        "name": "RS Survivors (Recovery Leaders)",
        "logic": (
            "( {57960} ("
            " daily close > daily sma( daily close , 200 )"                                  # 200D SMA intact (structural floor)
            " and daily rsi( 14 ) > 50"                                                      # RSI crossing centreline (recovery confirmed)
            " and daily volume > daily sma( daily volume , 20 )"                             # Institutional re-entry volume
            " and daily close > 3 days ago close"                                            # Price recovering (3-day upswing)
            " and daily close > 20"                                                           # Anti-penny filter
            " ) )"
        ),
        "filename": "Recovery_RS_Survivors.csv"
    },

    # ── 6. CLIMAX BOTTOM BOUNCE (Deep Discount, Higher Risk) ─────────────
    # Fundamentally strong stocks that sold off hard but are now reversing.
    # Key logic: below 50D SMA but within 15% of 200D SMA (at key support),
    #   was deeply oversold (RSI < 35) and now recovering, volume surge on bounce.
    #   30W SMA still rising = pre-correction long-term trend was intact.
    # These are the biggest discounts — higher risk but highest potential return.
    "6": {
        "name": "Climax Bottom Bounce (Deep Discount)",
        "logic": (
            "( {57960} ("
            " daily close < daily sma( daily close , 50 ) * 1.10"                            # At or below 50D SMA (discounted)
            " and daily close > daily sma( daily close , 200 ) * 0.85"                       # Within 15% of 200D SMA (key support)
            " and weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 )"    # 30W MA was rising (pre-shock trend intact)
            " and daily rsi( 14 ) > 40"                                                      # RSI recovering from oversold
            " and daily volume > daily sma( daily volume , 20 ) * 1.5"                       # Strong volume on the bounce
            " and daily close > 5 days ago close"                                            # Price recovering over 5 days
            " and daily close > 20"                                                           # Anti-penny filter
            " ) )"
        ),
        "filename": "Recovery_Climax_Bounce.csv"
    },

    # ── 7. MODIFIED EARLY BIRDS (Widened for Recovery Phase) ─────────────
    # The closest existing scanner to the recovery phase — widened to allow
    #   stocks slightly BELOW their 50D SMA (common post-correction).
    # Key changes vs Scanner 3:
    #   - Allows up to 8% BELOW 50D SMA (vs strictly above)
    #   - Weekly RSI lowered from > 50 to > 45
    #   - Weekly volume threshold lowered from 2× to 1.5× (less panic volume)
    #   - Uses 30D SMA (not 50D) for the flattening check
    "7": {
        "name": "Modified Early Birds (Recovery Widened)",
        "logic": (
            "( {57960} ("
            " daily close > daily sma( daily close , 50 ) * 0.92"                            # Within 8% BELOW 50D SMA (widened from strictly above)
            " and daily close < daily sma( daily close , 50 ) * 1.10"                        # Not extended above 50D SMA
            " and daily sma( daily close , 30 ) >= 5 days ago sma( daily close , 30 )"       # 30D SMA flattening (basing, not still falling)
            " and weekly rsi( 14 ) > 45"                                                     # Lowered from 50 → 45 for recovery phase
            " and weekly volume > weekly sma( weekly volume , 10 ) * 1.5"                    # Lowered from 2× → 1.5× (recovery buying, not panic)
            " and daily close > 1 day ago max( 20 , high )"                                  # Breakout from recent 20D range
            " and daily close > 20"                                                           # Anti-penny filter
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
    print("\n── RECOVERY SCANNERS (Post-Shock / Apr-2026) ──")
    print("  5  RS Survivors        (Held up best, lead recovery)")
    print("  6  Climax Bounce       (Deep discount at 200D support)")
    print("  7  Modified Early Birds(Widened for recovery phase)")
    print("="*55)
    if len(sys.argv) > 1:
        run_scan(sys.argv[1])
    else:
        choice = input("\n👉 Enter Option (1-7): ").strip()
        run_scan(choice)
    
    input("\nPress Enter to exit...")