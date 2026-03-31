import os
import sqlite3
import datetime
import pandas as pd
from dhanhq import dhanhq
from dhan_auth import ensure_valid_token
from ai_reconcile_engine import (
    process_trade_history, 
    normalize_symbol, 
    parse_html_trades, 
    parse_global_transaction_report_excel
)

def fetch_api_in_chunks(start_year=2024):
    """Fetches trade history by month to avoid timeouts and missing data."""
    tok = ensure_valid_token()
    cid = os.getenv("DHAN_CLIENT_ID")
    if not tok or not cid: return pd.DataFrame()
    
    dhan = dhanhq(client_id=cid, access_token=tok)
    all_trades = []
    
    current_date = datetime.datetime.now()
    start_date = datetime.datetime(start_year, 1, 1)
    
    iter_date = start_date
    while iter_date < current_date:
        next_date = iter_date + pd.DateOffset(months=3) # 3 month chunks
        if next_date > current_date: next_date = current_date
        
        f_str = iter_date.strftime('%Y-%m-%d')
        t_str = next_date.strftime('%Y-%m-%d')
        print(f"  - Querying API: {f_str} to {t_str}...")
        
        for page in range(0, 10):
            try:
                resp = dhan.get_trade_history(from_date=f_str, to_date=t_str, page_number=page)
                if resp['status'] == 'success' and resp['data']:
                    page_data = resp['data']
                    # Standardize Symbol inside the loop to avoid KeyError later
                    for t in page_data:
                        t['Symbol'] = t.get('tradingSymbol', t.get('customSymbol', t.get('symbol', 'UNKNOWN')))
                    all_trades.extend(page_data)
                else:
                    break
            except Exception as e:
                print(f"    ! Page error: {e}")
                break
        
        iter_date = next_date
        if next_date == current_date: break

    if not all_trades: return pd.DataFrame()
    df = pd.DataFrame(all_trades)
    df['exchangeTime'] = pd.to_datetime(df['exchangeTime'])
    return df.sort_values('exchangeTime')

def generate_excel_ledger():
    print("🚀 Starting Master Trade Audit (All Sources)...")
    
    # 1. Fetch from API (Chunked)
    api_df = fetch_api_in_chunks()
    if not api_df.empty:
        print(f"✅ API: Found {len(api_df)} transactions.")
        api_df = api_df[['exchangeTime', 'Symbol', 'transactionType', 'tradedQuantity', 'tradedPrice']].copy()
    else:
        print("⚠️ API: No remote transactions found.")

    # 2. Fetch from MHTML files
    print("📂 Parsing Local MHTML Logs...")
    html_df = parse_html_trades()
    if not html_df.empty:
        print(f"✅ MHTML: Found {len(html_df)} transactions.")
    else:
        print("⚠️ MHTML: No transactions parsed from local files.")

    # 3. Fetch from External Excel (Global Transaction Report)
    print("📂 Parsing Global Transaction Reports...")
    xl_df = parse_global_transaction_report_excel()
    if not xl_df.empty:
        print(f"✅ Excel: Found {len(xl_df)} transactions.")
    else:
        print("⚠️ Excel: No transactions found in external excel.")

    # 4. Combine and Clean
    print("🛠️ Merging and Deduplicating Data...")
    full_source = pd.concat([api_df, html_df, xl_df])
    
    if full_source.empty:
        print("❌ CRITICAL: No transaction data found in ANY source.")
        return

    # Deduplicate by Date, Symbol, Type, and Qty
    full_source['match_date'] = pd.to_datetime(full_source['exchangeTime']).dt.date
    len_before = len(full_source)
    # Group and take first to avoid exact duplicates
    full_source = full_source.drop_duplicates(subset=['match_date', 'Symbol', 'transactionType', 'tradedQuantity', 'tradedPrice'], keep='first')
    print(f"✅ Total Master Log: {len(full_source)} transactions (Deduplicated {len_before - len(full_source)}).")

    # 5. Process FIFO Matching to create Discrete Trades
    print("⛓️ Running FIFO Matching Engine...")
    # This matches buys and sells into individual "Trade" rows
    df_matched = process_trade_history(full_source)
    
    if df_matched.empty:
        print("❌ No matched trades found. (Check if you have both corresponding BUY and SELL logs)")
        return

    # 6. Format and Audit Calculations
    df_matched = df_matched.sort_values(['Symbol', 'Exit Date'])
    df_matched['Profit/Loss (INR)'] = df_matched['Realized P&L']
    
    # Calculate % P&L based on Cost Basis
    df_matched['PnL %'] = (df_matched['Realized P&L'] / (df_matched['Qty'] * df_matched['Entry Price'])) * 100
    
    # Symbol-level consolidation for the user
    df_matched['Consolidated Symbol PnL'] = df_matched.groupby('Symbol')['Profit/Loss (INR)'].transform('sum')

    # Reorder columns for professional layout
    cols = [
        'Symbol', 'Qty', 'Entry Date', 'Entry Price', 
        'Exit Date', 'Exit Price', 'Profit/Loss (INR)', 'PnL %', 'Consolidated Symbol PnL'
    ]
    df_export = df_matched[cols].copy()
    df_export = df_export.rename(columns={'Symbol': 'Ticker Symbol'})

    # 7. Final Export
    filename = "DHAN_MASTER_AUDIT_LEDGER.xlsx"
    try:
        df_export.to_excel(filename, index=False, engine='openpyxl')
        print(f"🏆 MASTER AUDIT COMPLETE: {filename}")
        
    except Exception as e:
        csv_name = "DHAN_MASTER_AUDIT_LEDGER.csv"
        df_export.to_csv(csv_name, index=False)
        print(f"⚠️ Exported as CSV ({csv_name}) due to Excel error: {e}")

    # 8. Print Oct/Dec specific verification
    target_period = df_export[df_export['Exit Date'].astype(str).str.contains('2025-10|2025-12')]
    if not target_period.empty:
        print("\n--- AUDIT PREVIEW (MISSING TRADES REGION) ---")
        print(target_period)

if __name__ == "__main__":
    generate_excel_ledger()
