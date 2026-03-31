import os
import quopri
from email import message_from_file
from bs4 import BeautifulSoup
import re
import pandas as pd

def get_html_from_mhtml(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding='utf-8', errors='ignore') as f:
        msg = message_from_file(f)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload()
            if part.get("Content-Transfer-Encoding") == "quoted-printable":
                return quopri.decodestring(payload).decode('utf-8', errors='ignore')
            else:
                return payload
    return ""

def deep_extract_mhtml(mhtml):
    print(f"\n--- Deep Extract: {mhtml} ---")
    content = get_html_from_mhtml(mhtml)
    if not content: return
    
    # Looking for dates like "26 Oct 2025"
    matches = re.finditer(r'(\d{1,2}\s+[A-Za-z]{3}\s+2025)', content)
    unique_dates = set()
    for m in matches:
        date_str = m.group(1)
        unique_dates.add(date_str)
        if "Oct" in date_str or "Dec" in date_str:
            # Print context
            start = max(0, m.start() - 100)
            end = min(len(content), m.end() + 200)
            print(f"TRADES DATA Context: {content[start:end]}\n")
            
    print(f"Unique 2025 dates found in {mhtml}: {sorted(list(unique_dates))}")

def check_pnl_report():
    print(f"\n--- Checking pnl-report.xls ---")
    path = "pnl-report.xls"
    if not os.path.exists(path):
        print(f"File {path} not found.")
        return
        
    try:
        # P&L reports from brokers are often HTML tables saved as .xls
        try:
            df = pd.read_excel(path)
            print("Successfully read as Excel.")
        except:
            print("Failed to read as Excel, trying to read as HTML table...")
            dfs = pd.read_html(path)
            df = dfs[0]
            print("Successfully read as HTML table.")
            
        print(f"Columns: {df.columns.tolist()}")
        # Check for Oct/Dec 2025
        # Need to verify if 'Sell Date' or 'Exit Date' column exists
        for col in df.columns:
            if any(k in str(col).lower() for k in ["date", "time"]):
                print(f"Date column found: {col}")
                # Filter for 2025
                matches = df[df[col].astype(str).str.contains("2025", na=False)]
                print(f"Found {len(matches)} rows with '2025' in column {col}")
                
    except Exception as e:
        print(f"Error reading P&L report: {e}")

if __name__ == "__main__":
    deep_extract_mhtml("Dhan Trade Journal-2025-26.mhtml")
    deep_extract_mhtml("Dhan Trade Journal-2024-25.mhtml")
    check_pnl_report()
