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
print("🛡️ UNIVERSAL GTT MANAGER (AUTO-FIX MODE)")
print("="*50)

symbol = input("1. Enter Symbol (e.g., MCX): ").upper().strip()
if symbol not in id_map:
    print(f"❌ Error: Symbol '{symbol}' not found.")
    exit()

security_id = id_map[symbol]
print(f"✅ Found ID: {security_id}")

try:
    qty = int(input("2. Quantity: "))
    stop_trigger = float(input("3. Stop Loss Trigger: "))
    target_trigger = float(input("4. Target Profit Trigger: "))
    
    # Validation
    if stop_trigger >= target_trigger:
        print("❌ Logic Error: Stop Loss must be LOWER than Target.")
        exit()
        
    # Set Limits (Slippage Protection)
    stop_limit = stop_trigger * 0.99
    target_limit = target_trigger 
    
except:
    print("❌ Invalid input.")
    exit()

# 3. THE UNIVERSAL EXECUTION ENGINE
print("\n🚀 ACTIVATING SENTINEL...")

try:
    # ATTEMPT 1: The "Modern" Syntax (sl_trigger_price)
    print("👉 Attempting Method A (Standard)...")
    response = dhan.place_gtt_order(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        price=target_limit,
        trigger_price=target_trigger,
        # OCO Params
        sl_trigger_price=stop_trigger,
        sl_price=stop_limit
    )

    if response['status'] == 'success':
        print(f"✅ SUCCESS (Method A)! Order ID: {response['data']['orderId']}")
        exit()
    else:
        # If API returns failure, print why
        print(f"⚠️ Method A Refused: {response.get('remarks', 'Unknown Error')}")

except Exception as e:
    print(f"⚠️ Method A Failed: {e}")


try:
    # ATTEMPT 2: The "Legacy/Alternative" Syntax (trigger_price1)
    print("\n👉 Attempting Method B (Alternative)...")
    response = dhan.place_gtt_order(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        price=target_limit,
        trigger_price=target_trigger,
        # OCO Params Alternative
        order_flag="OCO",     # Explicit Flag
        price1=stop_limit,    # Leg 2 Price
        trigger_price1=stop_trigger # Leg 2 Trigger
    )

    if response['status'] == 'success':
        print(f"✅ SUCCESS (Method B)! Order ID: {response['data']['orderId']}")
    else:
        print(f"❌ Method B Also Refused: {response}")
        print("\n💡 POSSIBLE CAUSE: Price Logic.")
        print("   Make sure Target > Current Price AND Stop Loss < Current Price.")

except Exception as e:
    print(f"\n❌ CRITICAL FAILURE: {e}")