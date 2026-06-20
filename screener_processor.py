import pandas as pd
import glob
import os
from bs4 import BeautifulSoup

# --- SYMBOL CORRECTIONS ---
# BUG-L2: expanded with common BSE-code → NSE-ticker mappings that appear
# frequently in Screener.in HTML export (numeric scrip codes not mapped by ISIN).
# Add new entries here when you see "UNKNOWN" symbols in the output.
SYMBOL_MAP = {
    '506854': 'TANFAC',
    '543619': 'CONCORD',
    '500002': 'ABB',
    '500008': 'AMARAJABAT',
    '500010': 'HDFC',
    '500034': 'BAJAJ-AUTO',
    '500103': 'BHEL',
    '500112': 'SBIN',
    '500180': 'HDFCBANK',
    '500209': 'INFY',
    '500247': 'KOTAKBANK',
    '500325': 'RELIANCE',
    '500696': 'HINDUNILVR',
    '532174': 'ICICIBANK',
    '532281': 'HCLTECH',
    '532454': 'BHARTIARTL',
    '532540': 'TCS',
    '532648': 'MARUTI',
    '532755': 'TECHM',
    '533155': 'TIINDIA',
    '540777': 'DMART',
    '542985': 'IRCTC',
    '543257': 'HLEGLAS',
}

# ==========================================
# ROUTING CONFIG
# ==========================================
# HTML files whose names start with 'Recovery_' are routed to their own
# separate CSVs instead of being merged into MASTER_scan_results.csv.
# This preserves the richer column set (Debt/Equity, Promoter Holding, ROCE)
# that the recovery conviction scorer in brute_force_match_pro.py needs.

RECOVERY_OUTPUT_MAP = {
    "Recovery_RS_Survivors":  "SCREENER_Recovery_RSLeaders.csv",
    "Recovery_Climax_Bounce": "SCREENER_Recovery_ClimaxBounce.csv",
    "Recovery_Early_Birds":   "SCREENER_Recovery_EarlyBirds.csv",
}

def _normalize_cols(df):
    """BUG-H3 / REC-3: Strip embedded newlines and excess spaces from Screener.in
    column headers so downstream readers use clean names like 'ROCE %' not
    'ROCE\\n                    %'."""
    df.columns = [" ".join(str(c).replace("\n", " ").split()) for c in df.columns]
    return df


def _extract_table_data(html_text):
    """Parse HTML and extract stock table rows. Returns list of row dicts."""
    soup = BeautifulSoup(html_text, 'html.parser')
    rows_out = []
    final_headers = []

    for t in soup.find_all('table'):
        headers = [th.text.strip() for th in t.find_all('th')]
        if 'Name' in headers:
            final_headers = headers
            for tr in t.find_all('tr')[1:]:
                cols = tr.find_all('td')
                if not cols:
                    continue
                row_data = [td.text.strip() for td in cols]

                extracted_symbol = "UNKNOWN"
                for col in cols:
                    anchor = col.find('a')
                    if anchor and 'href' in anchor.attrs and '/company/' in anchor['href']:
                        parts = anchor['href'].split('/')
                        try:
                            extracted_symbol = parts[parts.index('company') + 1].upper()
                        except:
                            pass

                if extracted_symbol in SYMBOL_MAP:
                    extracted_symbol = SYMBOL_MAP[extracted_symbol]

                row_dict = {}
                for i, header in enumerate(final_headers):
                    if i < len(row_data):
                        row_dict[header] = row_data[i]
                row_dict['Symbol'] = extracted_symbol
                rows_out.append(row_dict)
            break

    return rows_out


def process_screener_pages():
    print("\n🚀 Starting Screener Data Processor...")

    # Screener.in is now consumed via direct premium-CSV downloads (premium
    # subscription); the old HTML-page scrape/parse path was removed 20 Jun 2026.
    premium_csvs = glob.glob("*_premium.csv")

    if not premium_csvs:
        print("❌ No _premium.csv files found! Please run screener_fetcher.py first.")
        return False

    print(f"📂 Found {len(premium_csvs)} premium CSV files to process.")

    # Bucket by screen name prefix
    master_data    = []                          # Stage 2 screens → MASTER_scan_results.csv
    recovery_data  = {k: [] for k in RECOVERY_OUTPUT_MAP}  # Recovery screens → separate CSVs

    # 1. Process Premium CSVs
    for filename in sorted(premium_csvs):
        base = os.path.splitext(filename)[0]
        strategy_name = base[:-8] if base.endswith("_premium") else base

        screen_key = None
        for key in RECOVERY_OUTPUT_MAP:
            if strategy_name.startswith(key):
                screen_key = key
                break

        try:
            df_csv = pd.read_csv(filename)
            df_csv = _normalize_cols(df_csv)
            
            # Resolve Symbol from NSE Code, BSE Code, or Symbol column
            resolved_symbols = []
            for _, row in df_csv.iterrows():
                symbol = "UNKNOWN"
                nse = str(row.get('NSE Code', '')).strip()
                bse = str(row.get('BSE Code', '')).strip()
                sym = str(row.get('Symbol', '')).strip()
                
                if nse and nse.lower() != 'nan' and nse != '':
                    symbol = nse
                elif sym and sym.lower() != 'nan' and sym != '':
                    symbol = sym
                elif bse and bse.lower() != 'nan' and bse != '':
                    symbol = bse
                    
                if symbol in SYMBOL_MAP:
                    symbol = SYMBOL_MAP[symbol]
                resolved_symbols.append(symbol.upper())
                
            df_csv['Symbol'] = resolved_symbols

            rows = df_csv.to_dict(orient='records')
            if screen_key:
                recovery_data[screen_key].extend(rows)
                print(f"   🔄 Recovery Premium [{screen_key}] — {len(rows)} rows from {filename}")
            else:
                master_data.extend(rows)
                print(f"   📄 Stage 2 Premium — {len(rows)} rows from {filename}")
        except Exception as e:
            print(f"❌ Error reading premium CSV {filename}: {e}")

    # ── Save Stage 2 master file ──────────────────────────────────────────────
    if master_data:
        df = pd.DataFrame(master_data)
        df = _normalize_cols(df)                              # BUG-H3: clean headers
        if 'Symbol' in df.columns:
            df = df[['Symbol'] + [c for c in df.columns if c != 'Symbol']]
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        df.to_csv('MASTER_scan_results.csv', index=False)
        print(f"\n✅ Stage 2 Master: {len(df)} stocks → MASTER_scan_results.csv")
    else:
        print("\n⚠️  No Stage 2 premium-CSV data found (MASTER_scan_results.csv unchanged)")

    # ── Save Recovery CSVs (separate, preserve all columns) ──────────────────
    for screen_key, out_file in RECOVERY_OUTPUT_MAP.items():
        rows = recovery_data[screen_key]
        if not rows:
            print(f"⏭️  Skipping {screen_key} — no premium-CSV rows (run fetcher first)")
            continue
        df = pd.DataFrame(rows)
        df = _normalize_cols(df)                              # BUG-H3: clean headers
        if 'Symbol' in df.columns:
            df = df[['Symbol'] + [c for c in df.columns if c != 'Symbol']]
        df.drop_duplicates(subset=['Symbol'], inplace=True)
        df.to_csv(out_file, index=False)
        print(f"✅ Recovery [{screen_key}]: {len(df)} stocks → {out_file}")

    print("\n🏁 Processing complete.")
    return True


if __name__ == "__main__":
    import sys
    process_screener_pages()
    if "--batch" not in sys.argv:
        input("\nPress Enter to exit...")