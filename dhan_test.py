import os
from dotenv import load_dotenv
from dhanhq import dhanhq

# 1. Load the Secret Vault
load_dotenv()

# 2. Get Credentials safely
client_id = os.getenv("DHAN_CLIENT_ID")
access_token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not access_token:
    print("[ERROR] Credentials not found! Check your .env file.")
    exit()

# 3. Connect
try:
    print("Connecting to Dhan...")
    dhan = dhanhq(client_id, access_token)
    
    # Get Funds
    funds = dhan.get_fund_limits()
    cash = 0
    if 'data' in funds:
        # Note: 'availabelBalance' is a known typo in Dhan's API
        cash = funds['data'].get('availabelBalance', 0) 
    
    print(f"\n[SUCCESS] Connection Established!")
    print(f"--------------------------------")
    print(f"💰 Available Cash: ₹ {cash}")
    
    # Get Holdings
    holdings = dhan.get_holdings()
    if 'data' in holdings and holdings['data']:
        count = len(holdings['data'])
        print(f"📦 You have {count} stocks in your portfolio.")
    else:
        print("📦 Portfolio is empty.")

except Exception as e:
    print(f"\n[ERROR] Connection Failed.")
    print(f"Reason: {e}")