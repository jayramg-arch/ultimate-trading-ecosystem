import os
import sys
import subprocess
import time
from dotenv import load_dotenv
from dhanhq import dhanhq

# ==========================================
# 1. SETUP & HEALTH CHECK
# ==========================================
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_connection():
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        return "❌ .env Missing"
    
    try:
        dhan = dhanhq(client_id, access_token)
        # Fast "Ping" to check validity
        response = dhan.get_fund_limits()
        if response['status'] == 'success':
            return "✅ ONLINE"
        else:
            return "⚠️ EXPIRED TOKEN"
    except Exception as e:
        return f"❌ ERROR: {str(e)[:15]}..."

# ==========================================
# 2. THE DASHBOARD UI
# ==========================================
def main_menu():
    while True:
        clear_screen()
        status = check_connection()
        
        print("\n" + "="*45)
        print(f" 🦅 WEINSTEIN TRADE COMMANDER v2.0")
        print("="*45)
        print(f" 🔌 SYSTEM STATUS: {status}")
        print("-" * 45)
        
        # --- NEW LAYOUT ---
        print(" 1. 🔍 Run Scanner")
        print("    (Chartink + RRG Analysis)")
        
        print("\n 2. 🏥 Audit Portfolio")
        print("    (Health Check & P&L Report)")
        
        print("\n 3. 🎯 Sniper Entry")
        print("    (Calculate Risk + Place AMO Buy)")
        
        print("\n 4. 🛡️ Activate Sentinel")
        print("    (Attach OCO Stop Loss to Holdings)")
        
        print("-" * 45)
        print(" Q. Quit")
        print("="*45)
        
        choice = input("\n👉 AWAITING COMMAND: ").upper().strip()
        
        if choice == '1':
            # Ensure your scanner file is named this, or rename it here
            launch_tool("chartink_scanner_v5.py") 
            
        elif choice == '2':
            launch_tool("portfolio_audit.py")
            
        elif choice == '3':
            launch_tool("sniper_trigger.py")
            
        elif choice == '4':
            launch_tool("gtt_portfolio_v2.py")
            
        elif choice == 'Q':
            print("\n👋 Happy Trading. Closing System.")
            break
        else:
            input("❌ Invalid Option. Press Enter...")

# ==========================================
# 3. LAUNCHER ENGINE
# ==========================================
def launch_tool(script_name):
    if not os.path.exists(script_name):
        print(f"\n❌ Error: File '{script_name}' not found!")
        print(f"   Please make sure the file exists in this folder.")
        input("Press Enter to continue...")
        return

    print(f"\n🚀 Launching {script_name}...")
    time.sleep(1)
    
    try:
        subprocess.run([sys.executable, script_name])
    except Exception as e:
        print(f"❌ Crash: {e}")
    
    input("\n✅ Task Complete. Press Enter to return to Menu...")

if __name__ == "__main__":
    main_menu()