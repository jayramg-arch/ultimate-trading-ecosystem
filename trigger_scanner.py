import os
import re
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ==============================================================================
# TECHNICAL INDICATORS CALCULATION HELPERS
# ==============================================================================
def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    h, l, c = df['High'], df['Low'], df['Close']
    c_prev = c.shift(1)
    
    tr1 = h - l
    tr2 = (h - c_prev).abs()
    tr3 = (l - c_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def compute_vcp_state(df: pd.DataFrame) -> pd.Series:
    """Check if ATR(10) is contracted relative to ATR(40) (VCP base state)."""
    atr10 = compute_atr(df, 10)
    atr40 = compute_atr(df, 40)
    
    # Simple proxy: atr10 is less than 75% of atr40 (volatility compression)
    return atr10 < (atr40 * 0.75)

# ==============================================================================
# TRIGGER DETECTORS
# ==============================================================================
def scan_triggers(df: pd.DataFrame) -> dict:
    """
    Evaluates the last row of the DataFrame for the daily entry triggers.
    Returns a dict containing True/False for each pattern.
    """
    results = {}
    if len(df) < 50:
        return {k: False for k in ["50sma_undercut", "hammer_50", "hammer_200", "3bar_rev", "spring", "ib_nr7", "pocket", "vcp_bo", "gap_up_bo"]}

    # Extract series
    c = df['Close']
    h = df['High']
    l = df['Low']
    o = df['Open']
    v = df['Volume']
    
    # Calculate indicators
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    vol_ma = v.rolling(50).mean()
    atr10 = compute_atr(df, 10)
    
    # Retrieve current bar values
    c_now, o_now, h_now, l_now, v_now = c.iloc[-1], o.iloc[-1], h.iloc[-1], l.iloc[-1], v.iloc[-1]
    sma50_now = sma50.iloc[-1]
    sma200_now = sma200.iloc[-1]
    vol_ma_now = vol_ma.iloc[-1]
    
    # Candle shapes
    rng = h_now - l_now
    body = abs(c_now - o_now)
    body_hi = max(c_now, o_now)
    body_lo = min(c_now, o_now)
    lower_wick = body_lo - l_now
    upper_wick = h_now - body_hi
    
    # Is Hammer Shape
    is_hammer = (rng > 0) and (lower_wick > body * 2.0) and (upper_wick < body) and (body_hi >= l_now + rng * 0.66)
    
    # Relative Volume
    rel_vol = v_now / vol_ma_now if vol_ma_now > 0 else 0.0

    # 1. 50SMA Undercut & Reclaim
    results["50sma_undercut"] = (
        not pd.isna(sma50_now) and
        l_now < sma50_now and
        c_now > sma50_now and
        c_now > o_now and
        rel_vol > 1.25
    )

    # 2. Hammer at 50 SMA / 200 SMA
    results["hammer_50"] = (
        is_hammer and
        not pd.isna(sma50_now) and
        abs(l_now - sma50_now) / sma50_now <= 0.015 and
        c_now > sma50_now and
        rel_vol > 1.0
    )
    
    results["hammer_200"] = (
        is_hammer and
        not pd.isna(sma200_now) and
        abs(l_now - sma200_now) / sma200_now <= 0.02 and
        c_now > sma200_now and
        rel_vol > 1.0
    )

    # 3. Three-Bar Reversal
    if len(df) >= 4:
        prev_lows_declining = l.iloc[-2] < l.iloc[-3] and l.iloc[-3] < l.iloc[-4]
        reclaimed_highs = c_now > max(h.iloc[-2], h.iloc[-3], h.iloc[-4])
        results["3bar_rev"] = prev_lows_declining and reclaimed_highs
    else:
        results["3bar_rev"] = False

    # 4. Wyckoff Spring
    if len(df) >= 51:
        lowest_50_prev = l.iloc[-51:-1].min()
        results["spring"] = (
            l_now < lowest_50_prev and
            c_now > lowest_50_prev and
            c_now > o_now and
            v_now < vol_ma_now
        )
    else:
        results["spring"] = False

    # 5. Inside Bar NR7 Coil
    is_inside = h_now < h.iloc[-2] and l_now > l.iloc[-2]
    # Check if range is narrowest of last 7
    ranges = h - l
    is_nr7 = ranges.iloc[-1] == ranges.iloc[-7:].min()
    results["ib_nr7"] = is_inside and is_nr7

    # 6. Pocket Pivot
    if len(df) >= 11:
        is_up_day = c_now > c.iloc[-2] and c_now > o_now
        # Get maximum volume of any down days in last 10 days
        down_vols = []
        for i in range(2, 12):
            idx = -i
            is_down = c.iloc[idx] < c.iloc[idx-1] or (c.iloc[idx] == c.iloc[idx-1] and c.iloc[idx] < o.iloc[idx])
            if is_down:
                down_vols.append(v.iloc[idx])
        max_down_vol = max(down_vols) if down_vols else 0.0
        results["pocket"] = is_up_day and c_now > sma50_now and v_now > max_down_vol
    else:
        results["pocket"] = False

    # 7. VCP Breakout
    if len(df) >= 12:
        vcp_state = compute_vcp_state(df)
        vcp_tight_prev = bool(vcp_state.iloc[-6:-1].any()) # Contraction in previous 5 bars
        high10_prev = h.iloc[-11:-1].max()
        results["vcp_bo"] = (
            vcp_tight_prev and
            c_now > high10_prev and
            rel_vol > 1.2 and
            (c_now - l_now) > (rng * 0.60)
        )
    else:
        results["vcp_bo"] = False

    # 8. Gap-Up Breakout
    if len(df) >= 21:
        lockH_prev = c.iloc[-21:-1].max() # Highest close of prior 20 bars
        results["gap_up_bo"] = (
            o_now > h.iloc[-2] and
            c_now > lockH_prev and
            c_now > o_now and
            rel_vol > 1.5
        )
    else:
        results["gap_up_bo"] = False

    return results

# ==============================================================================
# MAIN SCANNER WORKFLOW
# ==============================================================================
def main():
    # Example symbols (you can replace this with symbols read from nifty500_symbols.json)
    watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "LTIM", "TVSMOTOR", "LT"]
    
    print("\n" + "="*70)
    print(f"   WEINSTEIN & SWING PRO SIGNAL SCANNER (Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("="*70)
    
    trigger_hits = []
    
    for sym in watchlist:
        ticker = f"{sym}.NS"
        print(f"Scanning {sym}...")
        try:
            # Download daily data (need ~250 days for SMAs and historical ranges)
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if data.empty or len(data) < 50:
                print(f"  ⚠️ Insufficient data for {sym}")
                continue
                
            # Flatten multi-index if present (yfinance v3 compatibility)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
                
            triggers = scan_triggers(data)
            
            # Record hits
            hits = [name.upper() for name, hit in triggers.items() if hit]
            if hits:
                trigger_hits.append({
                    "Symbol": sym,
                    "Close": f"Rs. {data['Close'].iloc[-1]:.2f}",
                    "Triggers Fired": ", ".join(hits)
                })
        except Exception as e:
            print(f"  ❌ Error downloading/processing {sym}: {e}")
            
    print("\n" + "="*70)
    print("   SCAN COMPLETED: DAILY TRIGGER REPORT")
    print("="*70)
    
    if trigger_hits:
        df_report = pd.DataFrame(trigger_hits)
        print(df_report.to_string(index=False))
    else:
        print("No triggers fired today on the scanned watchlist.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
