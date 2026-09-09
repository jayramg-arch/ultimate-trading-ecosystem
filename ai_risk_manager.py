import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

def clean_symbol(symbol):
    """Clean Dhan symbols by stripping prefixes/suffixes and map common indices.
    Idempotent: passing 'RELIANCE.NS' returns 'RELIANCE' (was 'RELIANCE.NS' →
    callers double-appended .NS, breaking yfinance lookups)."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY": return "^NSEI"
    if s == "BANKNIFTY": return "^NSEBANK"
    if s == "FINNIFTY": return "NIFTY_FIN_SERVICE.NS" # Fallback

    # D3: strip .NS / .BO so callers re-appending .NS don't produce '.NS.NS'
    if s.endswith(".NS") or s.endswith(".BO"):
        s = s[:-3]
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

# E13: Streamlit cache layering note —
#   Streamlit cache TTL gates how often the dashboard re-runs this function.
#   data_provider underneath has its own 1h disk cache. With Streamlit at 30min
#   we get a within-session refresh after ATR data is replenished mid-hour.
@st.cache_data(ttl=1800)
def get_atr(symbol, period=14):
    """Fetches the 14-day ATR for a given symbol (C1: parquet-cached)."""
    try:
        import data_provider as _dp
        data = _dp.fetch_ohlcv(symbol, period="1mo", interval="1d", use_cache=True, auto_adjust=True)
        if data is None or data.empty: return 0.0
        
        if 'High' not in data.columns or 'Low' not in data.columns or 'Close' not in data.columns:
            return 0.0

        # Calculate ATR
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift())
        low_close = abs(data['Low'] - data['Close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr_series = true_range.rolling(period).mean()
        atr = atr_series.iloc[-1]
        
        return float(atr)
    except Exception as e:
        print(f"ATR Error for {symbol}: {e}")
        return 0.0

# E13: market health is a daily-bar check (close vs SMA200 + slope). 1h TTL
# is fine — Streamlit cache aligned with data_provider's daily TTL.
@st.cache_data(ttl=3600)
def get_market_health(benchmark="^NSEI"):
    """
    Checks if the benchmark index is above its 200-day SMA.
    Returns: (bool, ltp, sma200)
    """
    try:
        # BUG-M3: ^CNX500 was incorrectly mapped to ^NSEI (Nifty 50).
        # ^CRSLDX is the correct Yahoo Finance ticker for Nifty 500.
        ticker_map = {
            "^CNX500":   "^CRSLDX",   # Nifty 500 → correct YF ticker
            "^CRSLDX":   "^CRSLDX",
            "NSE:NIFTY": "^NSEI",
            "NSE:CNX500":"^CRSLDX",
        }
        yf_sym = ticker_map.get(benchmark, benchmark)

        # C1: parquet-cached benchmark fetch
        import data_provider as _dp
        data = _dp.fetch_ohlcv(yf_sym, period="1y", interval="1d", use_cache=True, auto_adjust=True)

        # Fallback: if Nifty 500 unavailable, fall back to Nifty 50
        if (data is None or data.empty) and yf_sym != "^NSEI":
            data = _dp.fetch_ohlcv("^NSEI", period="1y", interval="1d", use_cache=True, auto_adjust=True)

        if data.empty: return False, 0.0, 0.0
        
        sma200 = data['Close'].rolling(200).mean().iloc[-1]
        ltp = data['Close'].iloc[-1]
        
        return bool(ltp > sma200), float(ltp), float(sma200)
    except:
        return False, 0.0, 0.0

@st.cache_data(ttl=3600)
def get_nifty_correlation(symbol, period="60d"):
    """Fetches rolling Pearson correlation between the stock and Nifty 500.

    B10 fix: was correlating against ^NSEI (Nifty 50). Rest of the system
    uses ^CRSLDX (Nifty 500). For mid/small-cap-heavy portfolios, Nifty 50
    correlation overstated diversification.
    """
    BENCHMARK = "^CRSLDX"
    try:
        clean = clean_symbol(symbol)
        ticker = clean if clean.startswith("^") else f"{clean}.NS"

        # C1: prefer cached individual fetches (parquet) so two correlation
        # checks in the same session don't re-download the benchmark twice.
        import data_provider as _dp
        stock_df = _dp.fetch_ohlcv(symbol, period=period, interval="1d", use_cache=True, auto_adjust=True)
        bench_df = _dp.fetch_ohlcv(BENCHMARK, period=period, interval="1d", use_cache=True, auto_adjust=True)
        if stock_df is None or bench_df is None or stock_df.empty or bench_df.empty: return "N/A"
        closes = pd.DataFrame({ticker: stock_df["Close"], BENCHMARK: bench_df["Close"]})

        returns = closes.pct_change(fill_method=None).dropna()
        if len(returns) < 10: return "N/A"

        corr = returns[ticker].corr(returns[BENCHMARK])
        return round(corr, 2)
    except Exception as e:
        print(f"Correlation Error for {symbol}: {e}")
        return "N/A"

def get_noise_risk_stats(df):
    """
    Calculates the number of active trades with Noise Risk.
    """
    risk_count = 0
    at_risk_symbols = []
    
    if df.empty: return 0, []
    
    for _, row in df.iterrows():
        symbol = row['Symbol']
        # Try different column names
        buy_p = float(row.get('BuyPrice', row.get('Buy Price', 0)) or 0)
        ltp = float(row.get('LTP', buy_p) or buy_p)
        sl = float(row.get('StopLoss', row.get('Stop Loss', 0)) or 0)
        
        if sl <= 0: continue
        
        atr = get_atr(symbol)
        if atr <= 0: continue
        
        dist = abs(ltp - sl)
        # Aligned with validate_risk_hygiene threshold — both use 2.0×ATR.
        if dist < (2.0 * atr):
            risk_count += 1
            at_risk_symbols.append(symbol)
            
    return risk_count, at_risk_symbols

def validate_risk_hygiene(df):
    """
    Compares the distance to Stop Loss against 2x ATR.
    Returns a list of alerts for trades with 'Noise Risk' (SL too tight).
    """
    alerts = []
    if df.empty: return alerts
    
    for _, row in df.iterrows():
        symbol = row['Symbol']
        buy_price = float(row.get('Buy Price', row.get('BuyPrice', 0)) or 0)
        ltp = float(row.get('LTP', 0) or 0)
        sl = float(row.get('Stop Loss', row.get('StopLoss', 0)) or 0)
        
        if sl <= 0 or ltp <= 0: continue
        
        atr = get_atr(symbol)
        if atr <= 0: continue
        
        dist_to_sl = abs(ltp - sl)
        # If distance to SL is less than 2x ATR, it's considered "Tight/Noise Risk"
        # (D2: threshold + suggested-buffer aligned. D1: typo "prematurey" fixed.)
        if dist_to_sl < (2.0 * atr):
            alerts.append({
                'Symbol': symbol,
                'Issue': 'Noise Risk',
                'Detail': f"SL is only {dist_to_sl/atr:.1f}x ATR away. Market noise might trigger it prematurely. 2x ATR suggested."
            })
            
    return alerts

def analyze_sector_concentration(df):
    """
    Calculates sector exposure and flags over-concentration (>25%).
    Phase-2A: enriches a missing/blank Sector column from sectors.db so
    rotation analysis no longer falls back on "Unassigned" buckets.
    """
    if df.empty: return {}

    # Calculate Capital Deployed per trade
    qty_col = 'Quantity' if 'Quantity' in df.columns else 'Qty'
    buy_col = 'BuyPrice' if 'BuyPrice' in df.columns else 'Buy Price'

    df['Deployment'] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0) * \
                        pd.to_numeric(df[buy_col], errors='coerce').fillna(0)

    total_deployed = df['Deployment'].sum()
    if total_deployed <= 0: return {}

    # Enrich blank/Unassigned Sector cells via the unified sector DB.
    if 'Sector' not in df.columns:
        df['Sector'] = ''
    try:
        import sector_lookup as _sl
        def _enrich(row):
            cur = str(row.get('Sector', '') or '').strip()
            if cur and cur.lower() not in ('', 'nan', 'unassigned', 'other', 'unknown'):
                return cur
            sym = row.get('Symbol', '')
            rec = _sl.get_sector(sym) if sym else None
            return (rec.get('display_name') or rec.get('sector_name')) if rec else (cur or 'Unassigned')
        df['Sector'] = df.apply(_enrich, axis=1)
    except Exception:
        df['Sector'] = df['Sector'].fillna('Unassigned').replace('', 'Unassigned')

    sector_grouped = df.groupby('Sector')['Deployment'].sum()
    sector_pct = (sector_grouped / total_deployed * 100)
    
    alerts = []
    for sector, pct in sector_pct.items():
        if pct > 25:
            alerts.append({
                'Sector': sector,
                'Exposure': f"{pct:.1f}%",
                'Issue': 'High Concentration',
                'Detail': "Exposure exceeds 25%. Consider diversifying into other sectors."
            })
            
    return {
        'breakdown': sector_pct.to_dict(),
        'alerts': alerts
    }

def generate_post_mortem_summary(closed_df):
    """
    Generates a strategic summary of closed trades behavior.
    """
    if closed_df.empty: return "No closed trades to analyze yet."
    
    total_closed = len(closed_df)
    
    # Calculate P&L for each closed trade
    exit_col = 'ExitPrice' if 'ExitPrice' in closed_df.columns else 'Exit Price'
    buy_col = 'BuyPrice' if 'BuyPrice' in closed_df.columns else 'Buy Price'
    qty_col = 'Quantity' if 'Quantity' in closed_df.columns else 'Qty'
    
    # Only calculate stats for RECONCILED trades (ExitPrice > 0)
    reconciled = closed_df[pd.to_numeric(closed_df[exit_col], errors='coerce').fillna(0) > 0].copy()
    
    if reconciled.empty:
        return "Closed trades detected, but awaiting exit price reconciliation for strategic analysis."

    reconciled['PnL'] = (pd.to_numeric(reconciled[exit_col], errors='coerce').fillna(0) - \
                        pd.to_numeric(reconciled[buy_col], errors='coerce').fillna(0)) * \
                        pd.to_numeric(reconciled[qty_col], errors='coerce').fillna(0)
    
    wins = reconciled[reconciled['PnL'] > 0]
    total_reconciled = len(reconciled)
    win_rate = (len(wins) / total_reconciled * 100) if total_reconciled > 0 else 0
    
    # Analyze Exit Reasons
    reason_col = 'ExitReason' if 'ExitReason' in reconciled.columns else 'Exit Reason'
    reasons = reconciled[reason_col].value_counts().to_dict()
    
    summary = f"Summary of {total_reconciled} reconciled trades: Win Rate {win_rate:.1f}%. "
    if 'Target Met' in reasons:
        summary += f"Captured {reasons['Target Met']} targets. "
    if 'SL Hit' in reasons:
        summary += f"Stopped out {reasons['SL Hit']} times. "
        
    return summary

def get_portfolio_correlation_matrix(symbols):
    """
    Computes pairwise Pearson correlation of daily returns for portfolio positions.
    Returns: correlation_df, shadow_pairs (r > 0.85), diversification_score (1-10)
    """
    if not symbols or len(symbols) < 2:
        return pd.DataFrame(), [], 10.0
    
    clean_syms = []
    for s in symbols:
        s = str(s).replace("NSE:", "").replace("BSE:", "").strip()
        for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
            if s.endswith(suffix):
                s = s[:-len(suffix)]
        if not s.endswith(".NS") and not s.startswith("^"):
            s = s + ".NS"
        clean_syms.append(s)
    
    try:
        # C1: use cached batch fetch when available (each symbol is cached
        # independently so a portfolio of 20 stocks reuses single-symbol caches
        # populated elsewhere by ATR / correlation checks).
        import data_provider as _dp
        bd = _dp.fetch_batch_ohlcv(clean_syms, period="6mo", interval="1d", use_cache=True, auto_adjust=True)
        if not bd:
            return pd.DataFrame(), [], 10.0
        closes = pd.DataFrame({
            (k if k.startswith("^") else f"{k}.NS"): df["Close"]
            for k, df in bd.items() if "Close" in df.columns
        })

        # BUG-M7: if only 1 ticker succeeded, closes may be a Series (no shape[1])
        if isinstance(closes, pd.Series):
            return pd.DataFrame(), [], 10.0
        if closes.shape[1] < 2:
            return pd.DataFrame(), [], 10.0
        
        # Compute daily returns and correlation
        returns = closes.pct_change().dropna()
        corr_matrix = returns.corr()
        
        # Clean column names for display
        clean_names = {col: str(col).replace(".NS", "") for col in corr_matrix.columns}
        corr_matrix = corr_matrix.rename(columns=clean_names, index=clean_names)
        
        # Find shadow concentration pairs (r > 0.85)
        shadow_pairs = []
        cols = corr_matrix.columns.tolist()
        for i in range(len(cols)):
            for j in range(i+1, len(cols)):
                r = corr_matrix.iloc[i, j]
                if abs(r) > 0.85:
                    shadow_pairs.append({
                        'Pair': f"{cols[i]} ↔ {cols[j]}",
                        'Correlation': round(r, 3),
                        'Risk': 'HIGH' if r > 0.92 else 'MODERATE'
                    })
        
        # Effective Diversification Score (1-10)
        # Average of upper-triangle correlations. Lower avg = better diversification.
        import numpy as np
        upper_tri = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]
        avg_corr = float(np.mean(np.abs(upper_tri))) if len(upper_tri) > 0 else 0.0
        # Map: avg_corr 0.0 -> score 10, avg_corr 1.0 -> score 1
        div_score = round(max(1.0, 10.0 - (avg_corr * 9.0)), 1)
        
        return corr_matrix, shadow_pairs, div_score
        
    except Exception as e:
        print(f"⚠️ Correlation Matrix Error: {e}")
        return pd.DataFrame(), [], 10.0


def get_adaptive_atr_multiplier(symbol):
    """
    Returns an adaptive ATR multiplier based on the stock's ADR%.
    Small-caps with high ADR% need wider buffers than large-caps.
    """
    try:
        # C1: parquet-cached fetch
        import data_provider as _dp
        data = _dp.fetch_ohlcv(symbol, period="1mo", interval="1d", use_cache=True, auto_adjust=True)
        if data is None or data.empty:
            return 1.5  # Default fallback

        # Compute ADR%
        adr_pct = ((data['High'] - data['Low']) / data['Close'] * 100).mean()
        
        # Adaptive multiplier: high ADR = wider SL buffer needed
        if adr_pct > 5.0:
            return 2.5  # Very volatile (small-cap / mid-cap)
        elif adr_pct > 3.0:
            return 2.0  # Moderately volatile
        else:
            return 1.5  # Standard large-cap
            
    except:
        return 1.5


def calculate_portfolio_vitals(closed_df, total_capital, open_positions_df=None, live_map=None):
    """
    Computes institutional portfolio vitals including BOTH realized (closed) and
    unrealized (open) P&L for accurate drawdown and return calculations.
    
    Metrics:
      - Sharpe Ratio: Risk-adjusted return. (Annualized Mean Return - Risk Free) / Annualized Volatility
      - Max Drawdown %: Largest peak-to-trough decline including current unrealized equity.
      - Calmar Ratio: Annualized Return / |Max Drawdown|. Higher = better risk-adjusted performance.
      - Expectancy ₹: Average ₹ you expect to make per trade. (WinRate × AvgWin) - (LossRate × AvgLoss).
      - Win Rate, Avg Win, Avg Loss: Based on closed trades with exit prices.
      - Total Return %: (Total Realized P&L + Unrealized P&L) / Total Capital.
    """
    result = {
        'sharpe_ratio': 0.0,
        'max_drawdown_pct': 0.0,
        'calmar_ratio': 0.0,
        'expectancy': 0.0,
        'win_rate': 0.0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'total_return_pct': 0.0,
        'unrealized_pnl': 0.0
    }
    
    if total_capital <= 0:
        return result
    
    try:
        # ── STEP 1: Process Closed Trades ──
        realized_pnl = 0.0
        trade_pnls = []  # Individual trade P&L amounts for Sharpe
        trade_pnl_pcts = []  # Individual trade P&L% for Sharpe
        
        if closed_df is not None and not closed_df.empty:
            exit_col = 'ExitPrice' if 'ExitPrice' in closed_df.columns else 'Exit Price'
            buy_col = 'BuyPrice' if 'BuyPrice' in closed_df.columns else 'Buy Price'
            qty_col = 'Quantity' if 'Quantity' in closed_df.columns else 'Qty'
            date_col = 'ExitDate' if 'ExitDate' in closed_df.columns else 'Exit Date'
            
            df = closed_df.copy()
            df[exit_col] = pd.to_numeric(df[exit_col], errors='coerce').fillna(0)
            df[buy_col] = pd.to_numeric(df[buy_col], errors='coerce').fillna(0)
            df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
            
            # Filter to fully reconciled trades only (exit price > 0)
            df = df[df[exit_col] > 0].copy()
            
            if not df.empty:
                df['PnL'] = (df[exit_col] - df[buy_col]) * df[qty_col]
                df['PnL_Pct'] = ((df[exit_col] - df[buy_col]) / df[buy_col]) * 100
                
                trade_pnls = df['PnL'].tolist()
                trade_pnl_pcts = df['PnL_Pct'].tolist()
                realized_pnl = df['PnL'].sum()
        
        # ── STEP 2: Compute Unrealized P&L from Open Positions ──
        unrealized_pnl = 0.0
        if open_positions_df is not None and not open_positions_df.empty and live_map:
            for _, row in open_positions_df.iterrows():
                sym = row.get('Symbol', '')
                bp = float(row.get('BuyPrice', 0) or 0)
                qty = float(row.get('Quantity', 0) or 0)
                # BUG-H2: get_batch_ltps() returns {sym: float}, not {sym: {'LTP': float}}
                ltp_val = live_map.get(sym)
                ltp = float(ltp_val) if ltp_val is not None else bp
                unrealized_pnl += (ltp - bp) * qty
        
        # ── STEP 3: Win/Loss Statistics (Closed trades only) ──
        wins = [p for p in trade_pnls if p > 0]
        losses = [p for p in trade_pnls if p <= 0]
        total_trades = len(trade_pnls)
        
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 1  # Avoid div/0
        
        # Expectancy = (Win% × Avg Win) - (Loss% × Avg Loss) → ₹ per trade
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
        
        # ── STEP 4: Equity Curve & Max Drawdown (INCLUDING unrealized) ──
        max_dd = 0.0
        if trade_pnls:
            import numpy as np
            pnl_series = pd.Series(trade_pnls)
            cumulative_pnl = pnl_series.cumsum()
            
            # Add current unrealized P&L as the "latest point" in the equity curve
            equity_points = list(total_capital + cumulative_pnl)
            if unrealized_pnl != 0:
                equity_points.append(equity_points[-1] + unrealized_pnl)
            
            equity_curve = pd.Series(equity_points)
            running_max = equity_curve.cummax()
            drawdowns = (equity_curve - running_max) / running_max * 100
            max_dd = float(drawdowns.min())
        elif unrealized_pnl < 0:
            # No closed trades yet, but open positions are losing
            max_dd = (unrealized_pnl / total_capital) * 100
        
        # ── STEP 5: Total Return (Realized + Unrealized) ──
        total_pnl = realized_pnl + unrealized_pnl
        total_return_pct = (total_pnl / total_capital) * 100
        
        # ── STEP 6: Sharpe Ratio (Annualized) ──
        sharpe = 0.0
        if len(trade_pnl_pcts) > 1:
            import numpy as np
            returns_arr = np.array(trade_pnl_pcts)
            returns_mean = float(np.mean(returns_arr))
            returns_std = float(np.std(returns_arr, ddof=1))  # Sample std
            
            # Annualization factor: estimate trades per year
            if closed_df is not None and not closed_df.empty:
                try:
                    dates = pd.to_datetime(closed_df[date_col], errors='coerce').dropna()
                    if len(dates) >= 2:
                        date_range_days = (dates.max() - dates.min()).days
                        if date_range_days > 0:
                            trades_per_year = total_trades / (date_range_days / 365.25)
                        else:
                            trades_per_year = 52  # Default: ~1 trade/week
                    else:
                        trades_per_year = 52
                except:
                    trades_per_year = 52
            else:
                trades_per_year = 52
            
            # Risk-free per trade = 6.5% annual / trades_per_year
            risk_free_per_trade = 6.5 / trades_per_year
            
            # Sharpe = (Mean Return - Risk Free Per Trade) / Std * sqrt(trades_per_year)
            if returns_std > 0:
                sharpe = ((returns_mean - risk_free_per_trade) / returns_std) * (trades_per_year ** 0.5)
        
        # ── STEP 7: Calmar Ratio (annualized) ──
        # = Annualized Total Return / |Max Drawdown|.
        # Bug fix (A5): previously used cumulative total_return_pct directly,
        # which inflated Calmar for multi-year histories and deflated for
        # sub-year. Now annualize via elapsed years from closed-trade dates.
        years_elapsed = 1.0
        if closed_df is not None and not closed_df.empty:
            try:
                _dates = pd.to_datetime(closed_df[date_col], errors='coerce').dropna()
                if len(_dates) >= 2:
                    _days = (_dates.max() - _dates.min()).days
                    if _days > 0:
                        years_elapsed = max(_days / 365.25, 1.0/12)  # floor at 1 month
            except Exception:
                years_elapsed = 1.0
        annualized_return_pct = total_return_pct / years_elapsed
        calmar = abs(annualized_return_pct / max_dd) if max_dd != 0 else 0
        
        result = {
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'calmar_ratio': round(calmar, 2),
            'expectancy': round(expectancy, 2),
            'win_rate': round(win_rate, 1),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'total_return_pct': round(total_return_pct, 2),
            'unrealized_pnl': round(unrealized_pnl, 2)
        }
    except Exception as e:
        print(f"⚠️ Portfolio Vitals Error: {e}")
    
    return result


if __name__ == "__main__":
    # Test Data
    test_df = pd.DataFrame([
        {'Symbol': 'RELIANCE', 'Sector': 'Energy', 'Qty': 10, 'Buy Price': 2500, 'LTP': 2550, 'Stop Loss': 2480},
        {'Symbol': 'TCS', 'Sector': 'IT', 'Qty': 5, 'Buy Price': 3800, 'LTP': 3750, 'Stop Loss': 3700}
    ])
    print("Risk Hygiene:", validate_risk_hygiene(test_df))
    print("Sector Analysis:", analyze_sector_concentration(test_df))
    
    # Test Correlation
    corr, shadows, div = get_portfolio_correlation_matrix(["RELIANCE", "TCS", "INFY"])
    print(f"\nCorrelation Matrix:\n{corr}")
    print(f"Shadow Pairs: {shadows}")
    print(f"Diversification Score: {div}/10")

