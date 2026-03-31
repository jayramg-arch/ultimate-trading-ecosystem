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
print("🧪 GTT BUY TESTER (VERIFIED)")
print("="*50)

symbol = input("1. Enter Symbol (e.g., MCX): ").upper().strip()
if symbol not in id_map:
    print(f"❌ Error: Symbol '{symbol}' not found.")
    exit()

security_id = id_map[symbol]
print(f"✅ Found ID: {security_id}")

# 3. USE YOUR REAL VALUES (For Testing)
# Since we are BUYING, we set a trigger BELOW current price (Dip Buy)
# or ABOVE current price (Breakout Buy).
# Let's try a SAFE Dip Buy test.

try:
    print(f"   (CMP is approx {2261})")
    qty = int(input("2. Quantity: "))
    entry_price = float(input("3. Buy Trigger Price (Try 2000 for test): "))
except:
    print("❌ Invalid Input")
    exit()

print("\n🚀 PLACING BUY GTT...")

try:
    # NOTE: For BUY GTT, we usually use a 'Single' leg, not OCO.
    # We are buying, so we just need one trigger.
    
    response = dhan.place_forever(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.BUY,  # <--- BUY SIDE (No Holdings Check)
        quantity=qty,
        price=entry_price,
        trigger_Price=entry_price   # Capital P
    )

    if response['status'] == 'success':
        print(f"\n✅ SUCCESS! Order ID: {response['data']['orderId']}")
        print("👉 Go to Dhan App -> Forever Orders.")
        print("   You should finally see an 'ACTIVE' order there!")
    else:
        print(f"\n❌ REJECTED: {response}")

except Exception as e:
    print(f"\n❌ Error: {e}")