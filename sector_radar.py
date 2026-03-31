
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import webbrowser
import os

# ==========================================
# 1. CONFIGURATION (ULTRA MODERN)
# ==========================================
SECTORS = {
    'Nifty Bank': '^NSEBANK',
    'Nifty Auto': '^CNXAUTO',
    'Nifty IT': '^CNXIT',
    'Nifty Pharma': '^CNXPHARMA',
    'Nifty FMCG': '^CNXFMCG',
    'Nifty Metal': '^CNXMETAL',
    'Nifty Realty': '^CNXREALTY',
    'Nifty Energy': '^CNXENERGY',
    'Nifty Infra': '^CNXINFRA',
    'Nifty PSU Bank': '^CNXPSUBANK'
}

BENCHMARKS = {
    'Nifty 50': '^NSEI',
    'Nifty 500': '^CRSLDX' 
}

PERIOD = "2y"       # Consistent history
SMOOTHING = 10      # JdK RS-Ratio Smoothing
TAIL_LENGTH = 6     # Weeks of history to show (Reduces Clutter)


# ==========================================
# 2. CALCULATION ENGINE
# ==========================================
def calculate_rrg_series(df_sector, df_benchmark):
    """Calculates RRG values for the entire series."""
    # align dates
    df = pd.DataFrame({'s': df_sector['Close'], 'b': df_benchmark['Close']}).dropna()
    
    # 1. Relative Strength (RS)
    df['rs'] = df['s'] / df['b']
    
    # 2. RS-Ratio (Trend)
    df['rs_ratio'] = 100 + ((df['rs'] - df['rs'].rolling(window=SMOOTHING).mean()) / df['rs'].rolling(window=SMOOTHING).mean()) * 100
    
    # 3. RS-Momentum (Rate of Change of Ratio)
    df['rs_momentum'] = 100 + ((df['rs_ratio'] - df['rs_ratio'].shift(1)) / df['rs_ratio'].shift(1)) * 100
    
    return df.dropna().tail(TAIL_LENGTH) # Return last N weeks

def fetch_and_process():
    print("="*60)
    print("📡 SECTOR RADAR PRO: FETCHING LIVE DATA & HISTORY...")
    print("="*60)
    
    # 1. Fetch Benchmarks
    bench_data = {}
    for name, ticker in BENCHMARKS.items():
        print(f"   Getting {name} ({ticker})...")
        try:
            bench_data[name] = yf.Ticker(ticker).history(period=PERIOD, interval="1wk")
        except:
            print(f"❌ Failed to fetch {name}")

    if not bench_data:
        print("❌ Critical: No Benchmark Data Found.")
        return None

    # 2. Process Sectors -> Returns Dict of Dicts
    # Structure: { 'Nifty 50': { 'SectorA': df_tail, ... }, ... }
    rrg_data = {b: {} for b in BENCHMARKS.keys()}
    
    for sec_name, sec_ticker in SECTORS.items():
        print(f"   Analyzing {sec_name}...", end="\r")
        try:
            sec_df = yf.Ticker(sec_ticker).history(period=PERIOD, interval="1wk")
            if sec_df.empty: continue
            
            for b_name, b_df in bench_data.items():
                if b_df.empty: continue
                rrg_df = calculate_rrg_series(sec_df, b_df)
                if not rrg_df.empty:
                    rrg_data[b_name][sec_name] = rrg_df
            
        except Exception as e:
            pass
            
    print("\n✅ Processing Complete.")
    return rrg_data
# ==========================================
# 3. VISUALIZATION (ENHANCED & REFINED)
# ==========================================
def plot_radar(rrg_data):
    if not rrg_data:
        print("❌ No Data to Plot.")
        return

    # Count active benchmarks
    benchmarks_found = [b for b in BENCHMARKS.keys() if rrg_data.get(b)]
    if not benchmarks_found:
        print("❌ No valid RRG data generated.")
        return

    fig = make_subplots(
        rows=1, cols=len(benchmarks_found),
        subplot_titles=[f"RELATIVE TO: {b.upper()}" for b in benchmarks_found],
        horizontal_spacing=0.08
    )

    for i, bench in enumerate(benchmarks_found):
        col_idx = i + 1
        sector_map = rrg_data[bench]
        
        # --- BACKGROUND QUADRANTS (Subtle Coloring) ---
        # Green (Leading): >100, >100
        fig.add_shape(type="rect", x0=100, y0=100, x1=110, y1=110, 
                      fillcolor="rgba(0, 230, 118, 0.05)", line=dict(width=0), layer="below", row=1, col=col_idx)
        # Yellow (Weakening): >100, <100
        fig.add_shape(type="rect", x0=100, y0=90, x1=110, y1=100, 
                      fillcolor="rgba(255, 214, 0, 0.05)", line=dict(width=0), layer="below", row=1, col=col_idx)
        # Red (Lagging): <100, <100
        fig.add_shape(type="rect", x0=90, y0=90, x1=100, y1=100, 
                      fillcolor="rgba(255, 82, 82, 0.05)", line=dict(width=0), layer="below", row=1, col=col_idx)
        # Blue (Improving): <100, >100
        fig.add_shape(type="rect", x0=90, y0=100, x1=100, y1=110, 
                      fillcolor="rgba(41, 121, 255, 0.05)", line=dict(width=0), layer="below", row=1, col=col_idx)

        # --- CROSSHAIRS (Thinner & Crisp) ---
        fig.add_hline(y=100, row=1, col=col_idx, line=dict(color="rgba(255,255,255,0.9)", width=1.5), layer="below")
        fig.add_vline(x=100, row=1, col=col_idx, line=dict(color="rgba(255,255,255,0.9)", width=1.5), layer="below")
        
        # --- PLOT SECTORS (Smooth Curves) ---
        for sec_name, df in sector_map.items():
            if df.empty: continue
            
            # Determine Color based on LATEST point
            last_x = df['rs_ratio'].iloc[-1]
            last_y = df['rs_momentum'].iloc[-1]
            
            if last_x > 100 and last_y > 100: color = '#00e676' # Green
            elif last_x > 100 and last_y < 100: color = '#ffd600' # Yellow
            elif last_x < 100 and last_y < 100: color = '#ff5252' # Red
            else: color = '#2979ff' # Blue (Improving)
            
            # 1. Plot the "Tail" (Curved Spline)
            fig.add_trace(
                go.Scatter(
                    x=df['rs_ratio'], 
                    y=df['rs_momentum'],
                    mode='lines',
                    line=dict(color=color, width=2, shape='spline', smoothing=1.3), # Smooth Curve
                    opacity=0.5, # Slightly more transparent to reduce clutter
                    hoverinfo='skip',
                    showlegend=False
                ),
                row=1, col=col_idx
            )
            
            # 2. Plot the "Head" (Marker + Text) - Only last point
            fig.add_trace(
                go.Scatter(
                    x=[last_x], 
                    y=[last_y],
                    mode='markers+text',
                    text=[sec_name],
                    textposition="top center",
                    textfont=dict(size=11, color="white"),
                    marker=dict(size=14, color=color, line=dict(width=2, color='white')),
                    name=sec_name,
                    showlegend=False,
                    hovertemplate=f"<b>{sec_name}</b><br>Ratio: %{{x:.2f}}<br>Mom: %{{y:.2f}}<extra></extra>"
                ),
                row=1, col=col_idx
            )

        # Axis Labels & Zoom
        fig.update_xaxes(title_text="Relative Trend (Ratio)", row=1, col=col_idx, gridcolor='rgba(255,255,255,0.1)')
        fig.update_yaxes(title_text="Relative Momentum", row=1, col=col_idx, gridcolor='rgba(255,255,255,0.1)')

        # Quadrant Labels (Pinned to Corners)
        def add_quad_label(x, y, text, color, align):
            fig.add_annotation(
                x=x, y=y, text=text, showarrow=False,
                font=dict(color=color, size=14, weight="bold", family="Rajdhani"),
                xref=f"x{col_idx if col_idx > 1 else ''} domain", 
                yref=f"y{col_idx if col_idx > 1 else ''} domain",
                xanchor=align[0], yanchor=align[1]
            )

        add_quad_label(0.98, 0.98, "LEADING", "#00e676", ("right", "top"))
        add_quad_label(0.98, 0.02, "WEAKENING", "#ffd600", ("right", "bottom"))
        add_quad_label(0.02, 0.02, "LAGGING", "#ff5252", ("left", "bottom"))
        add_quad_label(0.02, 0.98, "IMPROVING", "#2979ff", ("left", "top"))

    fig.update_layout(
        title={
            'text': "<b>SECTOR ROTATION RADAR PRO</b> <span style='font-size: 12px; color: #888'>(Last 8 Weeks Trail)</span>",
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        template="plotly_dark",
        height=700,
        margin=dict(l=40, r=40, t=80, b=40),
        plot_bgcolor='rgba(10, 14, 23, 1.0)',
        paper_bgcolor='rgba(5, 10, 15, 1.0)',
        font=dict(family="Rajdhani, sans-serif")
    )
    
    output_file = "sector_radar_pro.html"
    fig.write_html(output_file)
    print(f"\n✨ Chart Saved: {output_file}")
    
    # Auto Open
    webbrowser.open('file://' + os.path.realpath(output_file))

if __name__ == "__main__":
    try:
        data = fetch_and_process()
        if data is not None:
            plot_radar(data)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to exit...")
