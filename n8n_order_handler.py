import sys
import os
import argparse
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map

# 1. Setup Argument Parser
parser = argparse.ArgumentParser(description='Dhan Order Handler for n8n')
parser.add_argument('ticker', type=str, help='Stock Symbol (e.g. TCS, RELIANCE)')
parser.add_argument('action', type=str, help='BUY or SELL')
parser.add_argument('quantity', type=int, help='Quantity to trade')
parser.add_argument('--dry-run', action='store_true', help='Simulate order without executing')

def main():
    # Parse Args
    try:
        args = parser.parse_args()
    except:
        # If running from n8n simple exec, sys.argv might be messy if not handled, 
        # but argparse is standard.
        print("Usage: python n8n_order_handler.py [TICKER] [ACTION] [QTY]")
        sys.exit(1)

    ticker = args.ticker.upper()
    action = args.action.upper()
    qty = args.quantity
    
    print(f"🤖 Received Signal: {action} {qty} {ticker}")

    # 2. Load Environment
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token:
        print("❌ Error: Credentials not found in .env")
        sys.exit(1)

    # 3. Resolve Security ID
    # Note: caching this file locally or using a smaller map would be faster,
    # but reusing existing logic is safer for now.
    print("🔍 resolving Security ID...")
    symbol_map = get_nse_id_map()
    
    security_id = symbol_map.get(ticker)
    
    if not security_id:
        print(f"❌ Error: Symbol '{ticker}' not found in Dhan NSE Equity map.")
        # Try fuzzy match or removing -EQ? 
        # For now, strict match.
        sys.exit(1)
        
    print(f"✅ Found Security ID for {ticker}: {security_id}")

    # 4. Connect to Dhan
    dhan = dhanhq(client_id, access_token)
    
    # 5. Place Order
    if args.dry_run:
        print(f"🚧 DRY RUN: Would have placed {action} order for {qty} x {ticker} (ID: {security_id})")
        sys.exit(0)
        
    try:
        print(f"🚀 Executing Order...")
        transaction_type = dhan.BUY if action == 'BUY' else dhan.SELL
        
        # Placing MARKET Order for Equity Delivery (CNC) or Intraday? 
        # For automation, usually Intraday (MIS) or Carry (CNC). 
        # Defaulting to CNC (Delivery) for safety, user can change if needed.
        
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment=dhan.NSE,
            transaction_type=transaction_type,
            quantity=qty,
            order_type=dhan.MARKET,
            product_type=dhan.CNC, # Delivery
            validity=dhan.DAY
        )
        
        if response.get('status') == 'success':
            print(f"✅ Order Success! ID: {response.get('data', {}).get('orderId')}")
            print(f"📝 {response}")
        else:
            print(f"❌ Order Rejected: {response}")
            
    except Exception as e:
        print(f"❌ Exception during order placement: {e}")

if __name__ == "__main__":
    main()
