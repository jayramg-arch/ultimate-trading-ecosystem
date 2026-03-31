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

print("\n" + "="*50)
print("🛡️ INTELLIGENT PORTFOLIO MANAGER")
print("="*50)

# 2. FETCH & DIAGNOSE
print("⏳ Contacting Dhan Server to fetch holdings...")

try:
    response = dhan.get_holdings()
except Exception as e:
    print(f"❌ CRITICAL CONNECTION ERROR: {e}")
    exit()

# Debug: Check if API returned success
if response.get('status') != 'success':
    print("\n❌ API REJECTED REQUEST.")
    print(f"   Reason: {response}")
    exit()

data = response.get('data', [])

if not data:
    print("\n⚠️ API Success, but Portfolio is EMPTY.")
    print("   (Do you have holdings in this specific account?)")
    exit()

# 3. DISPLAY INTERACTIVE MENU
print(f"\n✅ Found {len(data)} Holding(s).\n")
print(f"{'#':<4} {'SYMBOL':<15} {'QTY':<8} {'CMP (Approx)':<12}")
print("-" * 45)

# Filter only useful items & create a selection list
selectable_stocks = []
index = 1

for item in data:
    # Handle API inconsistencies (some keys might differ)
    sym = item.get('tradingSymbol') or item.get('tradingsymbol') or "Unknown"
    qty = item.get('totalQty') or item.get('quantity') or 0
    # Try different price keys that Dhan might use
    ltp = item.get('lastTradedPrice') or item.get('ltp') or item.get('close') or 0.0
    
    if qty > 0:
        print(f"{index:<4} {sym:<15} {qty:<8} ₹{ltp:<12}")
        # Store full object for later use
        selectable_stocks.append({
            'symbol': sym,
            'qty': qty,
            'ltp': ltp,
            'exchange': item.get('exchangeSegment', 'NSE_EQ')
        })
        index += 1

if not selectable_stocks:
    print("❌ No active holdings found (Qty > 0).")
    exit()

# 4. USER SELECTION
try:
    choice = int(input("\n👉 Select Stock # to Protect (e.g. 1): "))
    if choice < 1 or choice > len(selectable_stocks):
        print("❌ Invalid Selection.")
        exit()
        
    stock = selectable_stocks[choice - 1]
    symbol = stock['symbol']
    qty = stock['qty']
    ltp = float(stock['ltp'])
    
    # Get Security ID
    security_id = id_map.get(symbol)
    if not security_id:
        print(f"❌ Error: Could not find Security ID for {symbol} in your master list.")
        exit()
        
    print(f"\n🛡️ SELECTED: {symbol} (Qty: {qty})")
    print(f"   Reference Price: ₹{ltp}")

    # 5. SET TRIGGERS
    print("\n--- DEFINE OCO LEVELS ---")
    target = float(input(f"   🟢 Target Price (Must be > {ltp}): "))
    stop_loss = float(input(f"   🔻 Stop Loss  (Must be < {ltp}): "))
    
    # Logic Guard
    if target <= ltp:
        print("❌ Error: Target must be higher than current price.")
        exit()
    if stop_loss >= ltp:
        print("❌ Error: Stop Loss must be lower than current price.")
        exit()

except ValueError:
    print("❌ Invalid input format.")
    exit()

# 6. PLACE ORDER
print("\n🚀 ACTIVATING SENTINEL...")
try:
    resp = dhan.place_forever(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        
        # Target Leg
        price=target,
        trigger_Price=target,
        
        # Stop Leg (OCO)
        order_flag="OCO",
        quantity1=qty,
        price1=stop_loss * 0.99,
        trigger_Price1=stop_loss
    )

    if resp['status'] == 'success':
        print(f"\n✅ SUCCESS! Order ID: {resp['data']['orderId']}")
        print(f"   {symbol} is now protected.")
    else:
        print(f"\n❌ FAILED: {resp}")

except Exception as e:
    print(f"\n❌ CODE ERROR: {e}")

input("\nPress Enter to exit...")