import os
import json
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map

# 1. SETUP
load_dotenv()
try:
    dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
except:
    print("❌ Error: Check .env file")
    exit()

id_map = get_nse_id_map()

# 2. INPUTS
print("\n" + "="*50)
print("🐞 GTT DEBUGGER")
print("="*50)

symbol = input("Enter Symbol (e.g., MCX): ").upper().strip()

if symbol not in id_map:
    print(f"❌ Error: Symbol '{symbol}' not found.")
    exit()

security_id = id_map[symbol]
print(f"✅ Found ID: {security_id}")

# Hardcoded test values or ask user? Let's ask to be safe.
try:
    qty = int(input("Quantity: "))
    stop_trigger = float(input("Stop Loss Trigger: "))
    target_trigger = float(input("Target Profit Trigger: "))
    
    # Logic: 
    # Stop Limit = slightly below trigger to ensure fill
    stop_limit = stop_trigger * 0.99 
    # Target Limit = same as trigger
    target_limit = target_trigger 
    
except:
    print("Invalid input")
    exit()

# 3. EXECUTION WITH DEBUG PRINT
print("\n🚀 SENDING GTT REQUEST...")

try:
    response = dhan.place_gtt_order(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        price=target_limit,         # Target Limit
        trigger_price=target_trigger, # Target Trigger
        sl_trigger_price=stop_trigger, # Stop Trigger
        sl_price=stop_limit            # Stop Limit
    )
    
    # === THE DEBUGGER ===
    print("\n" + "*"*40)
    print("📥 RAW RESPONSE FROM DHAN:")
    print(json.dumps(response, indent=4)) # Pretty print the error
    print("*"*40 + "\n")
    
    # Safe Check
    if isinstance(response, dict) and response.get('status') == 'success':
        print("✅ SUCCESS! GTT Placed.")
    else:
        print("❌ FAILED. Read the error message above.")
        
except Exception as e:
    print(f"\n❌ CRASHED: {e}")MCX