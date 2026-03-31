import yfinance as yf
import pandas as pd
from datetime import datetime

def format_percentage(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value * 100:.2f}%"

def format_ratio(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}"

def fetch_fundamental_data(ticker_symbol):
    """
    Fetches fundamental metrics for a given Indian ticker using yfinance.
    Normalizes symbols (e.g., RELIANCE -> RELIANCE.NS)
    """
    clean_ticker = ticker_symbol.upper().replace("NSE:", "").replace("BSE:", "")
    if not clean_ticker.endswith(".NS") and not clean_ticker.endswith(".BO"):
        clean_ticker += ".NS"

    try:
        ticker = yf.Ticker(clean_ticker)
        info = ticker.info
        
        # We need historical financials for Q-o-Q growth if info doesn't provide it cleanly
        # but info dict often has trailing metrics that are useful.
        
        # Quadrant A: Earnings & Revenue Momentum
        eps_growth = info.get('earningsQuarterlyGrowth', None)
        rev_growth = info.get('revenueQuarterlyGrowth', None)
        
        # To get Q-o-Q acceleration, we ideally need the last 2 quarters.
        # yfinance's quarterly_financials and quarterly_income_stmt
        q_income = ticker.quarterly_income_stmt
        acceleration = "N/A"
        if not q_income.empty and 'Net Income' in q_income.index:
            net_income = q_income.loc['Net Income'].dropna()
            if len(net_income) >= 3:
                # Calculate growth of Most Recent Q vs previous Q
                # And Previous Q vs the Q before that
                try:
                    growth_q1 = (net_income.iloc[0] - net_income.iloc[1]) / abs(net_income.iloc[1])
                    growth_q2 = (net_income.iloc[1] - net_income.iloc[2]) / abs(net_income.iloc[2])
                    acceleration = "🟢 YES" if growth_q1 > growth_q2 else "🔴 NO"
                except:
                    acceleration = "N/A"
        
        # Quadrant B: Profitability & Efficiency
        roe = info.get('returnOnEquity', None)
        op_margin = info.get('operatingMargins', None)
        debt_to_equity = info.get('debtToEquity', None) # Note: yf often returns this as a percentage (e.g., 40.5 for 0.40)
        
        if debt_to_equity is not None:
            debt_to_equity = debt_to_equity / 100.0 # Normalize to absolute ratio
            
        # Quadrant C: Valuation & Institutional
        pe_ratio = info.get('trailingPE', info.get('forwardPE', None))
        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')
        
        # yfinance doesn't natively expose Promoter Pledging or FII clean trends for Indian stocks easily in `info`.
        # We will expose Institutional Holders % if available.
        inst_hold = info.get('heldPercentInstitutions', None)
        promoter_hold = info.get('heldPercentInsiders', None)
        
        # Industry Analyst Sentiment & Targets
        analyst_sentiment = str(info.get('recommendationKey', 'N/A')).replace('_', ' ').title()
        target_mean = info.get('targetMeanPrice', 'N/A')
        num_analysts = info.get('numberOfAnalystOpinions', 'N/A')

        data = {
            "Symbol": ticker_symbol.replace("NSE:", ""),
            "Sector": sector,
            "Industry": industry,
            "EPS_Growth_QoQ": format_percentage(eps_growth),
            "Rev_Growth_QoQ": format_percentage(rev_growth),
            "Earnings_Acceleration": acceleration,
            "ROE": format_percentage(roe),
            "Op_Margin": format_percentage(op_margin),
            "Debt_to_Equity": format_ratio(debt_to_equity),
            "PE_Ratio": format_ratio(pe_ratio),
            "Inst_Holding": format_percentage(inst_hold),
            "Promoter_Holding": format_percentage(promoter_hold),
            "Market_Cap": info.get('marketCap', "N/A"),
            "Analyst_Sentiment": f"{analyst_sentiment} (based on {num_analysts} analysts)" if num_analysts != 'N/A' else analyst_sentiment,
            "Target_Mean_Price": target_mean
        }
        
        return data

    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return {
            "Symbol": ticker_symbol.replace("NSE:", ""),
            "Error": str(e)
        }

if __name__ == "__main__":
    # Quick Test
    test_symbols = ["RELIANCE", "TCS", "HDFCBANK"]
    results = []
    for sym in test_symbols:
        print(f"Fetching {sym}...")
        results.append(fetch_fundamental_data(sym))
    
    df = pd.DataFrame(results)
    print("\n--- Test Results ---")
    print(df.to_string())
