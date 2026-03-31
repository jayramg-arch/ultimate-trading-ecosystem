import os
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map

# ==========================================
# 1. SETUP
# ==========================================
load_dotenv()
try:
    dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
except:
    print("❌ Error: Check .env file")
    exit()

id_map = get_nse_id_map()

# ==========================================
# 2. INPUTS
# ==========================================
print("\n" + "="*50)
print("🛡️ GTT SENTINEL (STOP LOSS & TARGET)")
print("="*50)

symbol = input("1. Enter Symbol (e.g., MCX): ").upper().strip()

if symbol not in id_map:
    print(f"❌ Error: Symbol '{symbol}' not found.")
    exit()

security_id = id_map[symbol]
print(f"✅ Found ID: {security_id}")

try:
    qty = int(input("2. Quantity to Protect: "))
    stop_trigger = float(input("3. Stop Loss Trigger Price: "))
    target_trigger = float(input("4. Target Profit Trigger Price: "))
    
    # CALCULATE LIMIT PRICES (SLIPPAGE PROTECTION)
    # Stop Loss: Trigger at 100, Sell Limit at 99 (ensure exit)
    stop_limit = stop_trigger * 0.99
    
    # Target: Trigger at 200, Sell Limit at 200 (limit fill)
    target_limit = target_trigger 
    
except:
    print("❌ Invalid input.")
    exit()

print("\n" + "-"*40)
print(f"🛡️ GTT PREVIEW: {symbol} (OCO MODE)")
print(f"-"*40)
print(f"   Quantity       : {qty}")
print(f"   🔻 STOP LOSS   : Trigger {stop_trigger} / Sell {stop_limit:.2f}")
print(f"   🟢 TARGET      : Trigger {target_trigger} / Sell {target_limit:.2f}")
print("-"*40)

# ==========================================
# 3. EXECUTION
# ==========================================
confirm = input("\n🚀 ACTIVATE SENTINEL? (Y/N): ").upper()

if confirm == "Y":
    try:
        # NOTE: This uses the OCO (One Cancels Other) logic
        # We place a SINGLE GTT with two legs.
        
        response = dhan.place_gtt_order(
            security_id=str(security_id),
            exchange_segment=dhan.NSE,
            product_type=dhan.CNC,
            order_type=dhan.LIMIT,
            transaction_type=dhan.SELL,
            quantity=qty,
            price=target_limit,        # Main Price (Target)
            trigger_price=target_trigger, # Main Trigger (Target)
            
            # OCO PARAMS (The Stop Loss Leg)
            sl_trigger_price=stop_trigger,
            sl_price=stop_limit
        )
        
        if response['status'] == 'success':
            print(f"\n✅ SENTINEL ACTIVE! Order ID: {response['data']['orderId']}")
            print("👉 This order will sleep until price hits your levels.")
        else:
            print(f"\n❌ REJECTED: {response}")
            
    except Exception as e:
        print(f"\n❌ API Error: {e}")
        print("Tip: If this failed, check if 'place_gtt_order' is valid for your library version.")

else:
    print("\n🚫 Cancelled.")