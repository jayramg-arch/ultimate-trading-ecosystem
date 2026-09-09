import os
import datetime
import zipfile
import io
import requests
import pandas as pd
import logging

logger = logging.getLogger("NSEFetcher")
if not logger.handlers:
    # Basic console logging fallback
    logging.basicConfig(level=logging.INFO)

def get_latest_trading_date_and_data():
    """
    Attempts to download the latest available Delivery file and F&O Bhavcopy from NSE archives,
    backtracking up to 7 days if the current day's files are not yet published.
    Returns:
        tuple: (date_obj, delivery_df, fo_df)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    current_date = datetime.date.today()
    
    # We walk back up to 7 days
    for i in range(7):
        target_date = current_date - datetime.timedelta(days=i)
        # Skip weekends
        if target_date.weekday() in (5, 6):
            continue
            
        date_str_del = target_date.strftime("%d%m%Y")
        date_str_fo = target_date.strftime("%Y%m%d")
        
        del_url = f"https://archives.nseindia.com/archives/equities/mto/MTO_{date_str_del}.DAT"
        fo_url = f"https://archives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str_fo}_F_0000.csv.zip"
        
        logger.info(f"Checking NSE archives for date: {target_date.strftime('%Y-%m-%d')}")
        
        try:
            # 1. Fetch Delivery file
            r_del = requests.get(del_url, headers=headers, timeout=10)
            if r_del.status_code != 200:
                logger.debug(f"Delivery file not available for {target_date} (Status: {r_del.status_code})")
                continue
                
            # 2. Fetch F&O Bhavcopy
            r_fo = requests.get(fo_url, headers=headers, timeout=10)
            if r_fo.status_code != 200:
                logger.debug(f"F&O Bhavcopy not available for {target_date} (Status: {r_fo.status_code})")
                continue
                
            # Parse delivery file
            del_lines = r_del.text.split("\n")
            del_data = []
            for line in del_lines:
                line = line.strip()
                if line.startswith("20,"):
                    parts = line.split(",")
                    if len(parts) >= 7:
                        symbol = parts[2].strip()
                        sec_type = parts[3].strip()
                        # Capture standard equity series (EQ, BE, SM)
                        if sec_type in ('EQ', 'BE', 'SM'):
                            try:
                                del_pct = float(parts[6].strip())
                                del_data.append({"Symbol": symbol, "Delivery_Pct": del_pct})
                            except ValueError:
                                pass
            
            del_df = pd.DataFrame(del_data)
            
            # Parse F&O file
            z = zipfile.ZipFile(io.BytesIO(r_fo.content))
            fo_df = pd.read_csv(z.open(z.namelist()[0]))
            # Clean columns of whitespace
            fo_df.columns = [c.strip() for c in fo_df.columns]
            
            logger.info(f"Successfully loaded NSE data for {target_date.strftime('%Y-%m-%d')}")
            return target_date, del_df, fo_df
            
        except Exception as e:
            logger.warning(f"Error checking date {target_date}: {e}")
            continue
            
    return None, None, None

def get_nse_metrics() -> dict[str, dict]:
    """
    Returns a dictionary of symbol -> {'Delivery_Pct': float, 'Futures_OI_Chg_Pct': float}
    """
    date_obj, del_df, fo_df = get_latest_trading_date_and_data()
    if date_obj is None or del_df is None or fo_df is None:
        logger.error("Failed to retrieve latest NSE data from archives.")
        return {}
        
    metrics = {}
    
    # 1. Process Delivery
    for _, row in del_df.iterrows():
        symbol = row['Symbol']
        metrics[symbol] = {
            'Delivery_Pct': row['Delivery_Pct'],
            'Futures_OI_Chg_Pct': None # default
        }
        
    # 2. Process Futures Open Interest
    # Filter for Stock Futures (FinInstrmTp == 'STF')
    stf_df = fo_df[fo_df['FinInstrmTp'] == 'STF']
    
    # Group by TckrSymb and sum OpnIntrst and ChngInOpnIntrst
    grouped = stf_df.groupby('TckrSymb')[['OpnIntrst', 'ChngInOpnIntrst']].sum()
    
    for symbol, row in grouped.iterrows():
        oi = row['OpnIntrst']
        oi_chg = row['ChngInOpnIntrst']
        prev_oi = oi - oi_chg
        
        if prev_oi > 0:
            oi_chg_pct = round((oi_chg / prev_oi) * 100.0, 2)
        else:
            oi_chg_pct = 0.0
            
        if symbol in metrics:
            metrics[symbol]['Futures_OI_Chg_Pct'] = oi_chg_pct
        else:
            metrics[symbol] = {
                'Delivery_Pct': None,
                'Futures_OI_Chg_Pct': oi_chg_pct
            }
            
    return metrics

if __name__ == "__main__":
    # Test execution
    res = get_nse_metrics()
    print(f"Total symbols parsed: {len(res)}")
    # Print a few examples
    for sym in ['RELIANCE', 'TCS', 'ADANIENSOL', 'GODFRYPHLP', 'INDHOTEL']:
        if sym in res:
            print(f"{sym}: {res[sym]}")
