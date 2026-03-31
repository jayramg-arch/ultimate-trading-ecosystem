import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import warnings

warnings.filterwarnings('ignore')

# 1. Configuration
# NSE F&O Basket (Representative sample to keep runtime reasonable, ~100 liquid names)
SYMBOLS = [
    'AARTIIND.NS', 'ABB.NS', 'ABBOTINDIA.NS', 'ABCAPITAL.NS', 'ABFRL.NS', 'ACC.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'ALKEM.NS', 'AMBUJACEM.NS',
    'APOLLOHOSP.NS', 'APOLLOTYRE.NS', 'ASHOKLEY.NS', 'ASIANPAINT.NS', 'ASTRAL.NS', 'ATUL.NS', 'AUBANK.NS', 'AUROPHARMA.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS',
    'BAJAJFINSV.NS', 'BAJFINANCE.NS', 'BALKRISIND.NS', 'BALRAMCHIN.NS', 'BANDHANBNK.NS', 'BANKBARODA.NS', 'BATAINDIA.NS', 'BEL.NS', 'BERGEPAINT.NS', 'BHARATFORG.NS',
    'BHARTIARTL.NS', 'BHEL.NS', 'BIOCON.NS', 'BOSCHLTD.NS', 'BPCL.NS', 'BRITANNIA.NS', 'BSOFT.NS', 'CANBK.NS', 'CANFINHOME.NS', 'CHAMBLFERT.NS',
    'CHOLAFIN.NS', 'CIPLA.NS', 'COALINDIA.NS', 'COFORGE.NS', 'COLPAL.NS', 'CONCOR.NS', 'COROMANDEL.NS', 'CROMPTON.NS', 'CUB.NS', 'CUMMINSIND.NS',
    'DABUR.NS', 'DALBHARAT.NS', 'DEEPAKNTR.NS', 'DIVISLAB.NS', 'DIXON.NS', 'DLF.NS', 'DRREDDY.NS', 'EICHERMOT.NS', 'ESCORTS.NS', 'EXIDEIND.NS',
    'FEDERALBNK.NS', 'GAIL.NS', 'GLENMARK.NS', 'GMRINFRA.NS', 'GNFC.NS', 'GODREJCP.NS', 'GODREJPROP.NS', 'GRASIM.NS', 'GUJGASLTD.NS', 'HAL.NS',
    'HAVELLS.NS', 'HCLTECH.NS', 'HDFCAMC.NS', 'HDFCBANK.NS', 'HDFCLIFE.NS', 'HEROMOTOCO.NS', 'HINDALCO.NS', 'HINDCOPPER.NS', 'HINDPETRO.NS', 'HINDUNILVR.NS',
    'ICICIBANK.NS', 'ICICIGI.NS', 'ICICIPRULI.NS', 'IDEA.NS', 'IDFCFIRSTB.NS', 'IEX.NS', 'IGL.NS', 'INDHOTEL.NS', 'INDIACEM.NS', 'INDIAMART.NS',
    'INDIGO.NS', 'INDUSINDBK.NS', 'INDUSTOWER.NS', 'INFY.NS', 'IOC.NS', 'IPCALAB.NS', 'IRCTC.NS', 'ITC.NS', 'JINDALSTEL.NS', 'JKCEMENT.NS',
    'JSWSTEEL.NS', 'JUBLFOOD.NS', 'KOTAKBANK.NS', 'LALPATHLAB.NS', 'LAURUSLABS.NS', 'LICHSGFIN.NS', 'LT.NS', 'LTIM.NS', 'LTTS.NS', 'LUPIN.NS',
    'M&M.NS', 'M&MFIN.NS', 'MANAPPURAM.NS', 'MARICO.NS', 'MARUTI.NS', 'MCX.NS', 'METROPOLIS.NS', 'MFSL.NS', 'MGL.NS', 'MOTHERSON.NS',
    'MPHASIS.NS', 'MRF.NS', 'MUTHOOTFIN.NS', 'NATIONALUM.NS', 'NAUKRI.NS', 'NAVINFLUOR.NS', 'NESTLEIND.NS', 'NMDC.NS', 'NTPC.NS', 'OBEROIRLTY.NS',
    'OFSS.NS', 'ONGC.NS', 'PAGEIND.NS', 'PEL.NS', 'PERSISTENT.NS', 'PETRONET.NS', 'PFC.NS', 'PIDILITIND.NS', 'PIIND.NS', 'PNB.NS',
    'POLYCAB.NS', 'POWERGRID.NS', 'PVRINOX.NS', 'RAMCOCEM.NS', 'RBLBANK.NS', 'RECCMTD.NS', 'RELIANCE.NS', 'SAIL.NS', 'SBICARD.NS', 'SBILIFE.NS',
    'SBIN.NS', 'SHREECEM.NS', 'SHRIRAMFIN.NS', 'SIEMENS.NS', 'SRF.NS', 'SUNPHARMA.NS', 'SUNTV.NS', 'SYNGENE.NS', 'TATACHEM.NS', 'TATACOMM.NS',
    'TATACONSUM.NS', 'TATAMOTORS.NS', 'TATAPOWER.NS', 'TATASTEEL.NS', 'TCS.NS', 'TECHM.NS', 'TITAN.NS', 'TORNTPHARM.NS', 'TRENT.NS', 'TVSMOTOR.NS',
    'UBL.NS', 'ULTRACEMCO.NS', 'UPL.NS', 'VEDL.NS', 'VOLTAS.NS', 'WIPRO.NS', 'ZEEL.NS', 'ZYDUSLIFE.NS'
]
BENCHMARK = '^CRSLDX' # Use ^CRSLDX as a proxy for NSE 500
START_DATE = '2019-01-01'
END_DATE = datetime.now().strftime('%Y-%m-%d')
INITIAL_CAPITAL = 100000

# 2. Indicator Math
def rma(x, n):
    """Running moving average used in RSI."""
    a = np.full_like(x, np.nan)
    if len(x) > n:
        a[n] = x[1:n+1].mean()
        for i in range(n+1, len(x)):
            a[i] = (a[i-1] * (n - 1) + x[i]) / n
    return a

def calc_technicals(df):
    if len(df) < 200:
        return df
        
    # Fix for newer yfinance returning MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_150'] = df['Close'].rolling(150).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Volume averages
    df['VOL_SMA_50'] = df['Volume'].rolling(50).mean()
    df['VOL_SMA_20'] = df['Volume'].rolling(20).mean()
    
    # 52 Week High/Low (250 days)
    df['HIGH_52W'] = df['High'].rolling(250).max()
    df['LOW_52W'] = df['Low'].rolling(250).min()
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = rma(gain.to_numpy(), 14)
    avg_loss = rma(loss.to_numpy(), 14)
    rs = avg_gain / np.where(avg_loss == 0, 1e-9, avg_loss)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR (14)
    df['TR'] = np.maximum(df['High'] - df['Low'], 
               np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                          abs(df['Low'] - df['Close'].shift(1))))
    df['ATR_14'] = rma(df['TR'].to_numpy(), 14)
    
    # Chandelier Exit (22, 3)
    highest_22 = df['High'].rolling(22).max()
    df['CE_RAW'] = highest_22 - (df['ATR_14'] * 3.0)
    # Ratchet handles during loop
    
    # BB Squeeze (20 length)
    basis = df['Close'].rolling(20).mean()
    dev = 2.0 * df['Close'].rolling(20).std()
    bbw = ((basis + dev) - (basis - dev)) / np.where(basis==0, 1, basis)
    df['BBW'] = bbw
    df['BBW_AVG_100'] = df['BBW'].rolling(100).mean()
    df['BB_SQZ'] = df['BBW'] < df['BBW_AVG_100']
    
    # MA Tension (Squeeze)
    ma_dist = abs(df['EMA_20'] - df['SMA_50']) / np.where(df['SMA_50']==0, 1, df['SMA_50'])
    df['MA_SQZ'] = ma_dist <= 0.06
    
    # ---------------- ADVANCED FILTERS ---------------- #
    # 1. Daily CPR (TC)
    df['Pivot'] = (df['High'].shift(1) + df['Low'].shift(1) + df['Close'].shift(1)) / 3
    df['BC'] = (df['High'].shift(1) + df['Low'].shift(1)) / 2
    df['TC'] = (df['Pivot'] - df['BC']) + df['Pivot']
    
    # 2. Monthly VWAP (Proxy using 20-day rolling VWAP)
    df['Typ_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_M'] = (df['Typ_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    
    # 3. Volume Shelf (VWMA > SMA)
    df['VWMA_20'] = (df['Close'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    df['VOL_SHELF'] = df['VWMA_20'] > df['SMA_20'] if 'SMA_20' in df else df['VWMA_20'] > df['Close'].rolling(20).mean()
    
    # 4. Volume Accumulation Setup
    # Require 2 days of above average volume on up days in last 10
    up_vol = np.where(df['Close'] > df['Open'], df['Volume'], 0)
    high_up_vol = np.where(up_vol > df['VOL_SMA_50'], 1, 0)
    df['VOL_ACCUM'] = pd.Series(high_up_vol).rolling(10).sum() >= 2
    
    # 5. VCP Tightness (Price Range Contraction)
    # Check if last 5 days range is 50% tighter than previous 15 days
    range_5 = (df['High'] - df['Low']).rolling(5).max()
    range_15 = (df['High'] - df['Low']).shift(5).rolling(15).max()
    df['VCP_TIGHT'] = range_5 < (range_15 * 0.6)
    
    # 6. Max Pullback Depth (15%)
    # Current close is no more than 15% below the 52W high
    df['PULLBACK_DEPTH'] = (df['HIGH_52W'] - df['Close']) / df['HIGH_52W']
    df['MILD_PB'] = df['PULLBACK_DEPTH'] <= 0.15
    
    # 7. Volume Dry Up (30% below avg)
    df['VOL_DRY'] = df['Volume'] < (df['VOL_SMA_50'] * 0.70)
    
    return df

# 3. Simulation Engine
def backtest_strategy(ticker, df, bench_df, mode="Breakout", config_params=None):
    if config_params is None:
        config_params = {}
        
    # Merge benchmark for Market Health and Relative Strength
    df = df.join(bench_df[['Close', 'SMA_50', 'SMA_200']], rsuffix='_BM')
    
    # 8. Market Health Filter
    df['MKT_HEALTH'] = (df['Close_BM'] > df['SMA_200_BM']) & (df['SMA_50_BM'] > df['SMA_200_BM'])
    
    # 9. Mansfield Relative Strength
    # (Stock_Close / Bench_Close) / SMA52 of (Stock_Close / Bench_Close) - 1
    ratio = df['Close'] / df['Close_BM']
    ratio_sma250 = ratio.rolling(250).mean() # 52 weeks = ~250 days
    df['MANSFIELD_RS'] = ((ratio / ratio_sma250) - 1) * 100
    df['RS_OK'] = df['MANSFIELD_RS'] > 0
    
    # 10. Alpha Score Approximation (Max 100)
    alpha = pd.Series(0, index=df.index)
    alpha += np.where(df['Close'] > df['SMA_200'], 10, 0)
    alpha += np.where(df['SMA_50'] > df['SMA_200'], 15, 0)
    alpha += np.where(df['Close'] > df['HIGH_52W'] * 0.75, 15, 0)
    alpha += np.where(df['RS_OK'], 20, 0)
    alpha += np.where(df['VOL_ACCUM'], 20, 0)
    alpha += np.where(df['MA_SQZ'], 10, 0)
    alpha += np.where(df['MKT_HEALTH'], 10, 0)
    df['ALPHA_SCORE'] = alpha
    
    trades = []
    in_trade = False
    entry_price = 0
    trade_type = ""
    stop_loss = 0
    target_1 = 0
    trade_start_idx = 0
    qty = 0
    capital = INITIAL_CAPITAL
    
    ce_trail = np.nan
    breakeven = False
    
    for i in range(250, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        # Trend Template (Stage 2)
        stage2 = (row['Close'] > row['SMA_50']) and (row['SMA_50'] > row['SMA_150']) and \
                 (row['SMA_150'] > row['SMA_200']) and (row['Close'] > row['LOW_52W'] * 1.30) and \
                 (row['Close'] >= row['HIGH_52W'] * 0.75)
                 
        if not in_trade:
            # Config Param Extraction (Default False)
            use_cpr = config_params.get('cpr', False)
            use_vwap = config_params.get('vwap_m', False)
            use_vshelf = config_params.get('vol_shelf', False)
            use_vaccum = config_params.get('vol_accum', False)
            use_vcp = config_params.get('vcp', False)
            use_masqz = config_params.get('ma_sqz', False)
            use_bbsqz = config_params.get('bb_sqz', False)
            use_mkt = config_params.get('mkt_health', False)
            use_alpha = config_params.get('alpha', False)
            use_rs = config_params.get('rs_ok', False)
            use_mpb = config_params.get('mild_pb', False)
            use_vdry = config_params.get('vol_dry', False)

            # Master Switch Toggles
            cpr_ok = row['Close'] > row['TC'] if use_cpr else True
            vwap_ok = row['Close'] > row['VWAP_M'] if use_vwap else True
            vshelf_ok = row['VOL_SHELF'] if use_vshelf else True
            vaccum_ok = row['VOL_ACCUM'] if use_vaccum else True
            vcp_ok = row['VCP_TIGHT'] if use_vcp else True
            sqz_ok = (row['MA_SQZ'] and row['BB_SQZ']) if (use_masqz and use_bbsqz) else (row['MA_SQZ'] if use_masqz else (row['BB_SQZ'] if use_bbsqz else True))
            mkt_ok = row['MKT_HEALTH'] if use_mkt else True
            alpha_ok = row['ALPHA_SCORE'] >= 70 if use_alpha else True
            rs_ok = row['RS_OK'] if use_rs else True
            mpb_ok = row['MILD_PB'] if use_mpb else True
            vdry_ok = row['VOL_DRY'] if use_vdry else True

            # Macro Validation Block
            all_filters_passed = cpr_ok and vwap_ok and vshelf_ok and vaccum_ok and vcp_ok and sqz_ok and mkt_ok and alpha_ok and rs_ok and mpb_ok and vdry_ok

            # Positional Breakout Logic
            if mode in ["Breakout", "Hybrid"]:
                # Breakout logic: 20-day high cross
                bo_level = df['High'].iloc[i-20:i].max()
                is_bo = row['Close'] > bo_level
                vol_expansion = row['Volume'] > (row['VOL_SMA_50'] * 1.5)
                
                if stage2 and is_bo and vol_expansion and all_filters_passed:
                    in_trade = True
                    trade_type = "Positional"
                    entry_price = row['Close']
                    trade_start_idx = i
                    stop_loss = df['Low'].iloc[i-10:i+1].min() - (row['ATR_14'] * 0.2)
                    if stop_loss >= entry_price:
                        stop_loss = entry_price - (row['ATR_14'] * 1.5)
                    ce_trail = row['CE_RAW']
                    qty = (capital * 0.10) / entry_price
                    continue
            
            # Swing Pullback Logic
            if mode in ["Swing", "Hybrid"] and not in_trade:
                # RSI Pocket
                rsi_in_pocket = (40 <= row['RSI'] <= 60)
                # Engulfing or Hammer (Simplified reversal check)
                is_reversal = row['Close'] > row['Open'] and prev_row['Close'] < prev_row['Open'] and row['Close'] > prev_row['Open']
                
                if stage2 and rsi_in_pocket and is_reversal and all_filters_passed:
                    in_trade = True
                    trade_type = "Swing"
                    entry_price = row['Close']
                    trade_start_idx = i
                    stop_loss = df['Low'].iloc[i-5:i+1].min() * (1 - 0.002)
                    if stop_loss >= entry_price:
                        stop_loss = entry_price * 0.99
                    
                    target_1 = entry_price + ((entry_price - stop_loss) * 2.0)
                    breakeven = False
                    qty = (capital * 0.10) / entry_price
                    continue
                    
        else:
            # Manage Open Trade
            bars_held = i - trade_start_idx
            
            if trade_type == "Positional":
                # Chandelier Ratchet
                if np.isnan(ce_trail):
                    ce_trail = row['CE_RAW']
                elif prev_row['Close'] > ce_trail:
                    ce_trail = max(row['CE_RAW'], ce_trail)
                else:
                    ce_trail = row['CE_RAW']
                
                active_sl = max(stop_loss, ce_trail)
                
                if row['Close'] < active_sl or (bars_held > 10 and row['Close'] <= entry_price):
                    exit_price = row['Close']
                    pnl_pct = (exit_price - entry_price) / entry_price
                    trades.append({'Ticker': ticker, 'Mode': mode, 'Type': trade_type, 'Entry': entry_price, 'Exit': exit_price, 'PnL_Pct': pnl_pct, 'Bars': bars_held})
                    in_trade = False
            
            elif trade_type == "Swing":
                # EMA 20 Trail
                trail_level = row['EMA_20'] * (1 - 0.01)
                active_sl = max(stop_loss, trail_level)
                if breakeven:
                    active_sl = max(active_sl, entry_price)
                
                # Check Targets
                if not breakeven and row['High'] >= target_1:
                    breakeven = True
                    
                # Exit
                if row['Close'] < active_sl or row['Close'] < row['SMA_50'] or (bars_held > 10 and row['Close'] <= entry_price):
                    exit_price = row['Close']
                    # Simplified accounting since target hit
                    pnl_pct = (exit_price - entry_price) / entry_price
                    if breakeven: # Estimate half hit T1, half stopped
                        pnl_pct = ((target_1 - entry_price) / entry_price) * 0.5 + ((active_sl - entry_price)/entry_price) * 0.5
                    
                    trades.append({'Ticker': ticker, 'Mode': mode, 'Type': trade_type, 'Entry': entry_price, 'Exit': exit_price, 'PnL_Pct': pnl_pct, 'Bars': bars_held})
                    in_trade = False

    return trades

# 4. Main Runner
def run_all():
    print("Downloading Benchmark...")
    try:
        bench_df = yf.download(BENCHMARK, start=START_DATE, end=END_DATE, progress=False)
        bench_df = calc_technicals(bench_df)
    except Exception as e:
        print(f"Error fetching benchmark: {e}")
        return
    
    all_trades = []
    configs = [
        # POSITIONAL COMBINATIONS
        {"name": "P1. Breakout Base (Stage 2 Only)", "mode": "Breakout", "params": {}},
        {"name": "P2. Breakout Price Lvls (CPR+VWAP)", "mode": "Breakout", "params": {"cpr": True, "vwap_m": True}},
        {"name": "P3. Breakout Vol Bias (Shelf+Accum)", "mode": "Breakout", "params": {"vol_shelf": True, "vol_accum": True}},
        {"name": "P4. Breakout Strength (RS+Alpha)", "mode": "Breakout", "params": {"rs_ok": True, "alpha": True}},
        {"name": "P5. Breakout Squeeze (BB+MA+VCP)", "mode": "Breakout", "params": {"bb_sqz": True, "ma_sqz": True, "vcp": True}},
        {"name": "P6. Breakout Market Health Only", "mode": "Breakout", "params": {"mkt_health": True}},
        {"name": "P7. Breakout UltraStrict (ALL ON)", "mode": "Breakout", "params": {
            "cpr": True, "vwap_m": True, "vol_shelf": True, "vol_accum": True, "vcp": True, 
            "ma_sqz": True, "bb_sqz": True, "mkt_health": True, "alpha": True, "rs_ok": True, "mild_pb": True}},
            
        # SWING COMBINATIONS
        {"name": "S1. Swing Base (Stage 2 + Engulf)", "mode": "Swing", "params": {}},
        {"name": "S2. Swing Price Lvls (CPR+VWAP)", "mode": "Swing", "params": {"cpr": True, "vwap_m": True}},
        {"name": "S3. Swing Vol Dry+Accum", "mode": "Swing", "params": {"vol_dry": True, "vol_accum": True}},
        {"name": "S4. Swing Strength (RS+Alpha)", "mode": "Swing", "params": {"rs_ok": True, "alpha": True}},
        {"name": "S5. Swing Squeeze (BB+MA+VCP)", "mode": "Swing", "params": {"bb_sqz": True, "ma_sqz": True, "vcp": True}},
        {"name": "S6. Swing Shallow (Max PB 15%)", "mode": "Swing", "params": {"mild_pb": True}},
        {"name": "S7. Swing UltraStrict (ALL ON)", "mode": "Swing", "params": {
            "cpr": True, "vwap_m": True, "vol_shelf": True, "vol_accum": True, "vcp": True, 
            "ma_sqz": True, "bb_sqz": True, "mkt_health": True, "alpha": True, "rs_ok": True, "mild_pb": True, "vol_dry": True}},
    ]
    
    for ticker in SYMBOLS:
        print(f"Processing {ticker}...")
        try:
            df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False)
            if df.empty:
                continue
            df = calc_technicals(df)
            
            for config in configs:
                res = backtest_strategy(ticker, df.copy(), bench_df, mode=config['mode'], config_params=config['params'])
                for t in res:
                    t['Config'] = config['name']
                all_trades.extend(res)
                
        except Exception as e:
            print(f"Error on {ticker}: {e}")
            
    trade_df = pd.DataFrame(all_trades)
    
    if trade_df.empty:
        print("No trades generated.")
        return
        
    print("\nGeneration Report...")
    metrics = []
    for conf in trade_df['Config'].unique():
        sub = trade_df[trade_df['Config'] == conf]
        win_rate = (sub['PnL_Pct'] > 0).mean() * 100
        avg_win = sub[sub['PnL_Pct'] > 0]['PnL_Pct'].mean() * 100
        avg_loss = sub[sub['PnL_Pct'] < 0]['PnL_Pct'].mean() * 100
        profit_factor = abs((avg_win * (win_rate/100)) / (avg_loss * (1 - win_rate/100))) if avg_loss != 0 else np.inf
        total_pnl = sub['PnL_Pct'].sum() * 100
        
        avg_win_bars = sub[sub['PnL_Pct'] > 0]['Bars'].mean()
        avg_loss_bars = sub[sub['PnL_Pct'] <= 0]['Bars'].mean()
        
        metrics.append({
            'Config': conf[:22], # Shorthand for PDF fit
            'Trades': len(sub),
            'Win %': round(win_rate, 1),
            'Avg Win': f"{round(avg_win, 1)}%",
            'Avg Loss': f"{round(avg_loss, 1)}%",
            'Profit Fac': round(profit_factor, 2),
            'Net Ret': f"{round(total_pnl, 1)}%",
            'Win Hold': round(avg_win_bars, 1) if pd.notna(avg_win_bars) else 0,
            'Loss Hold': round(avg_loss_bars, 1) if pd.notna(avg_loss_bars) else 0
        })
        
    res_df = pd.DataFrame(metrics)
    print(res_df.to_string(index=False))
    
    # Generate PDF Report
    doc = SimpleDocTemplate("Backtest_Report.pdf", pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("Weinstein/Minervini System: Historical Backtest Analysis", styles['Title']))
    elements.append(Spacer(1, 12))
    
    desc = f"Universe: {len(SYMBOLS)} NSE Large Caps<br/>Period: {START_DATE} to {END_DATE}<br/><br/>Evaluating the structural difference between Base settings and Strict Volatility Squeeze settings. Note the drastic difference in holding periods between Winners and Losers."
    elements.append(Paragraph(desc, styles['Normal']))
    elements.append(Spacer(1, 12))
    
    data = [res_df.columns.values.tolist()] + res_df.values.tolist()
    t = Table(data, colWidths=[120, 50, 50, 60, 60, 60, 60, 60, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ECF0F1")),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))
    
    elements.append(t)
    doc.build(elements)
    print("\nSaved report to Backtest_Report.pdf")

if __name__ == "__main__":
    run_all()
