import os
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
print("🛡️ FOREVER ORDER MANAGER (FINAL PATCH)")
print("="*50)

symbol = input("1. Enter Symbol (e.g., MCX): ").upper().strip()
if symbol not in id_map:
    print(f"❌ Error: Symbol '{symbol}' not found.")
    exit()

security_id = id_map[symbol]
print(f"✅ Found ID: {security_id}")

try:
    qty = int(input("2. Quantity: "))
    target_price = float(input("3. Target Price: "))
    stop_price = float(input("4. Stop Loss Price: "))
except:
    print("❌ Invalid Input")
    exit()

print("\n🚀 ACTIVATING FOREVER ORDER...")

try:
    # CORRECTION: Both triggers need Capital 'P'
    response = dhan.place_forever(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        
        # LEG 1: TARGET (Profit)
        price=target_price,
        trigger_Price=target_price,   # Capital P
        
        # LEG 2: STOP LOSS (OCO)
        order_flag="OCO",
        price1=stop_price * 0.99,     # Stop Limit
        trigger_Price1=stop_price     # Capital P <--- THE FINAL FIX
    )

    if response['status'] == 'success':
        print(f"\n✅ SUCCESS! Order ID: {response['data']['orderId']}")
        print("   Your OCO Sentinel is now active.")
    else:
        print(f"\n❌ REJECTED: {response}")

except Exception as e:
    print(f"\n❌ Error: {e}")