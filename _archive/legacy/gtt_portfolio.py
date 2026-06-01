import os
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map

# 1. SETUP & CONNECT
load_dotenv()
try:
    dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
except:
    print("❌ Error: Check .env file")
    exit()

# Load NSE IDs for safe lookup
id_map = get_nse_id_map()

print("\n" + "="*60)
print("🛡️ PORTFOLIO SENTINEL (PROTECT YOUR HOLDINGS)")
print("="*60)

# 2. FETCH LIVE HOLDINGS
print("⏳ Fetching your portfolio...")
response = dhan.get_holdings()

if response['status'] != 'success' or 'data' not in response:
    print("❌ Failed to fetch holdings.")
    exit()

holdings = response['data']
if not holdings:
    print("❌ Portfolio is empty!")
    exit()

# 3. DISPLAY HOLDINGS
print(f"\n{'#':<4} {'SYMBOL':<15} {'QTY':<8} {'LTP':<10}")
print("-" * 45)

valid_holdings = []
for i, stock in enumerate(holdings):
    # Filter for NSE Equity to be safe
    # (Dhan holdings might show BSE or others, we prioritize NSE matching)
    sym = stock.get('tradingSymbol')
    qty = stock.get('totalQty')
    ltp = stock.get('lastTradedPrice')
    
    print(f"{i+1:<4} {sym:<15} {qty:<8} ₹{ltp:<10}")
    valid_holdings.append(stock)

# 4. SELECT STOCK
try:
    choice = int(input("\n👉 Select Stock Number to Protect (e.g. 1): "))
    if choice < 1 or choice > len(valid_holdings):
        print("❌ Invalid Number.")
        exit()
        
    selected = valid_holdings[choice - 1]
    symbol = selected['tradingSymbol']
    qty = selected['totalQty']
    ltp = selected['lastTradedPrice']
    
    # Get Security ID from our safe map (Ensure NSE Equity)
    # Holdings API has 'securityId' but mapping ensures we target NSE EQ specifically
    security_id = id_map.get(symbol)
    if not security_id:
        print(f"❌ Could not find NSE ID for {symbol}. Skipped.")
        exit()
        
    print(f"\n🛡️ PROTECTING: {symbol}")
    print(f"   Held Qty: {qty}")
    print(f"   Current Price: ₹{ltp}")

except ValueError:
    print("❌ Invalid Input.")
    exit()

# 5. ENTER EXIT LEVELS
try:
    print("\n--- ENTER YOUR LEVELS ---")
    target_price = float(input(f"   🟢 Target Price (Must be > {ltp}): "))
    stop_price = float(input(f"   🔻 Stop Loss  (Must be < {ltp}): "))
    
    # 6. LOGIC CHECK
    errors = []
    if target_price <= ltp:
        errors.append(f"❌ TARGET ERROR: Target {target_price} is below current price {ltp}.")
    if stop_price >= ltp:
        errors.append(f"❌ STOP ERROR: Stop {stop_price} is above current price {ltp}.")
        
    if errors:
        print("\n🚫 LOGIC BLOCKED:")
        for e in errors: print(e)
        exit()
        
except ValueError:
    print("❌ Invalid numbers.")
    exit()

# 7. PLACE FOREVER ORDER (OCO)
print("\n🚀 ACTIVATING SENTINEL...")

try:
    response = dhan.place_forever(
        security_id=str(security_id),
        exchange_segment=dhan.NSE,
        product_type=dhan.CNC,
        order_type=dhan.LIMIT,
        transaction_type=dhan.SELL,
        quantity=qty,
        
        # LEG 1: TARGET
        price=target_price,
        trigger_Price=target_price,   # Capital P fix
        
        # LEG 2: STOP LOSS
        order_flag="OCO",
        quantity1=qty,                # Qty fix
        price1=stop_price * 0.99,     # Stop Limit
        trigger_Price1=stop_price     # Capital P fix
    )

    if response['status'] == 'success':
        print(f"\n✅ SUCCESS! Order ID: {response['data']['orderId']}")
        print(f"   {symbol} is now protected by OCO Order.")
    else:
        print(f"\n❌ REJECTED: {response}")

except Exception as e:
    print(f"\n❌ Error: {e}")