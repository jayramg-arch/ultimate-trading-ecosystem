import math
import os
from dotenv import load_dotenv
from dhanhq import dhanhq

# ==========================================
# 1. CONFIGURATION (DEFAULTS)
# ==========================================
PORTFOLIO_CAPITAL = 4000000.0      # ₹40 Lakhs (Total Capital)
DEFAULT_MAX_ALLOC = 800000.0       # Default Max Cap (20% of Portfolio)

# Risk Percentages
RISK_PCT_STOCK = 1.00              # 1% for Stocks
RISK_PCT_ETF = 0.75                # 0.75% for ETFs

# ==========================================
# 2. CONNECT TO DHAN (AUTO-CHECK CASH)
# ==========================================
current_cash = 0.0
try:
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if client_id and access_token:
        dhan = dhanhq(client_id, access_token)
        funds = dhan.get_fund_limits()
        if 'data' in funds:
            current_cash = float(funds['data'].get('availabelBalance', 0))
    else:
        print("[INFO] No .env found. Assuming manual cash check.")
except:
    pass

print(f"\n" + "="*50)
print(f"💰 PORTFOLIO RISK ALLOCATOR (v6.2)")
print(f"   Capital Base:   ₹ {PORTFOLIO_CAPITAL:,.0f}")
print(f"   Available Cash: ₹ {current_cash:,.2f}")
print(f"="*50 + "\n")

# ==========================================
# 3. MANUAL INPUTS (JUST LIKE PINE SCRIPT)
# ==========================================
symbol = input("1. Enter Symbol (e.g., CRAFTSMAN): ").upper()

# Asset Type Input
asset_input = input("2. Asset Type? (Enter 'E' for ETF, 'S' for Stock) [Default: S]: ").upper()
asset_type = 'E' if asset_input == 'E' else 'S'

# Price Inputs
entry_price = float(input("3. Enter Entry Price: "))
stop_price = float(input("4. Enter Stop Price: "))

# Max Allocation Input (The New Field)
alloc_str = input(f"5. Max Allocation per Trade? [Default: ₹{DEFAULT_MAX_ALLOC:,.0f}]: ")
if alloc_str.strip():
    max_allocation = float(alloc_str)
else:
    max_allocation = DEFAULT_MAX_ALLOC  # Use default if user presses Enter

# ==========================================
# 4. THE CALCULATION ENGINE
# ==========================================
if entry_price <= 0 or stop_price <= 0:
    print("Error: Prices must be positive.")
    exit()

# A. Direction & Stop Distance
is_long = entry_price > stop_price
stop_distance = abs(entry_price - stop_price)
stop_pct = (stop_distance / entry_price) * 100

# B. Select Risk %
if asset_type == 'E':
    risk_pct = RISK_PCT_ETF
    type_label = "ETF"
else:
    risk_pct = RISK_PCT_STOCK
    type_label = "STOCK"

# C. Calculate Allowable Risk Amount (The "R")
risk_amount = PORTFOLIO_CAPITAL * (risk_pct / 100.0)

# D. Limit Price (Entry + 0.5% buffer)
limit_price = entry_price * 1.005

# E. Targets (1:2 and 1:3)
if is_long:
    target1 = entry_price + (stop_distance * 2)
    target2 = entry_price + (stop_distance * 3)
else:
    target1 = entry_price - (stop_distance * 2)
    target2 = entry_price - (stop_distance * 3)

# F. Quantity Logic (The "Min" Function)
# 1. Quantity based on RISK (How much can I lose?)
qty_by_risk = math.floor(risk_amount / stop_distance)

# 2. Quantity based on ALLOCATION (How much can I buy?)
qty_by_alloc = math.floor(max_allocation / entry_price)

# 3. Final Quantity (Whichever is smaller is Safer)
final_qty = min(qty_by_risk, qty_by_alloc)
is_capped = qty_by_alloc < qty_by_risk

# G. Realized Metrics
capital_used = final_qty * entry_price
actual_risk = final_qty * stop_distance

# ==========================================
# 5. THE BLUEPRINT
# ==========================================
print(f"\n" + "-"*40)
print(f"🤖 TRADE PLAN: {symbol} ({type_label})")
print(f"-"*40)
print(f"   🎯 FINAL QUANTITY :  {final_qty} shares")
print(f"-"*40)
print(f"   🛑 Stop Loss      :  {stop_price:.2f} ({stop_pct:.2f}%)")
print(f"   🔵 Limit Buy Order:  {limit_price:.2f}")
print(f"   🟢 Target 1 (1:2) :  {target1:.2f}")
print(f"   🟢 Target 2 (1:3) :  {target2:.2f}")
print(f"-"*40)
print(f"   💵 Capital Req    :  ₹ {capital_used:,.2f}")
print(f"   🔥 Risk Amount    :  ₹ {actual_risk:,.2f} ({risk_pct}%)")

if is_capped:
    print(f"\n   ⚠️ LIMIT HIT: Quantity reduced by Max Allocation rule.")
    print(f"      Risk allowed {qty_by_risk} shares, but Budget (₹{max_allocation:,.0f}) allows only {qty_by_alloc}.")

if capital_used > current_cash and current_cash > 0:
    print(f"\n   ❌ INSUFFICIENT FUNDS IN DHAN!")
    print(f"      Available: ₹ {current_cash:,.2f}")
    print(f"      Shortfall: ₹ {capital_used - current_cash:,.2f}")