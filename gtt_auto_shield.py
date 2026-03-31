import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map
import time

# --- 1. SETUP ---
load_dotenv()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DB_FILE = "trade_journal_v6.db"

def connect_dhan():
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        return dhan
    except Exception as e:
        print(f"❌ Error connecting to Dhan: {e}")
        return None

def load_journal_data():
    """Returns a dict mapping symbol to SL and Target."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT symbol, stoploss, target FROM journal WHERE status = 'OPEN'", conn)
        conn.close()
        # Normalize keys (Symbol -> data)
        data = {}
        for _, r in df.iterrows():
            sym = str(r['symbol']).strip().upper().replace("NSE:", "").replace("BSE:", "")
            data[sym] = {'SL': r['stoploss'], 'Target': r['target']}
        return data
    except:
        return {}

def run_auto_shield():
    print("="*60)
    print("🛡️ GTT AUTO-SHIELD: COCKPIT MODE")
    print("="*60)

    dhan = connect_dhan()
    if not dhan: return
    
    id_map = get_nse_id_map()
    journal_data = load_journal_data()
    
    print("⏳ Fetching Holdings...")
    resp = dhan.get_holdings()
    if resp.get('status') != 'success':
        print(f"❌ API Error: {resp}")
        return
    
    holdings = resp.get('data', [])
    if not holdings:
        print("⚠️ Portfolio is empty.")
        return

    # Check for GTT orders already active
    print("⏳ Fetching Active GTT Orders...")
    gtt_resp = dhan.get_forever()
    active_gtt_syms = []
    if gtt_resp.get('status') == 'success':
        for o in gtt_resp.get('data', []):
            if o.get('orderStatus') == 'ACTIVE':
                active_gtt_syms.append(o.get('tradingSymbol', '').upper())

    shieldable_list = []
    print(f"\n✅ Found {len(holdings)} holdings. Comparing with Journal...")
    print("-" * 60)
    print(f"{'SYMBOL':<15} {'QTY':<8} {'STATUS':<20}")
    print("-" * 60)

    for h in holdings:
        sym = (h.get('tradingSymbol') or h.get('tradingsymbol')).upper()
        qty = h.get('totalQty') or h.get('quantity') or 0
        if qty <= 0: continue
        
        status_msg = ""
        if sym in active_gtt_syms:
            status_msg = "🟢 PROTECTED (GTT)"
        elif sym in journal_data:
            sl = journal_data[sym]['SL']
            tgt = journal_data[sym]['Target']
            
            # Robust check for NaN or 0
            import math
            has_sl = sl > 0 and not (isinstance(sl, float) and math.isnan(sl))
            has_tgt = tgt > 0 and not (isinstance(tgt, float) and math.isnan(tgt))
            
            if has_sl and has_tgt:
                status_msg = "🟡 READY TO SHIELD"
                shieldable_list.append({
                    'symbol': sym,
                    'qty': qty,
                    'sl': sl,
                    'target': tgt,
                    'exchange': h.get('exchangeSegment', 'NSE_EQ')
                })
            else:
                missing = []
                if not has_sl: missing.append("SL")
                if not has_tgt: missing.append("TGT")
                status_msg = f"🔴 MISSING {(' & '.join(missing)) if missing else 'LEVELS'}"
        else:
            status_msg = "⚪ NOT IN JOURNAL"
            
        print(f"{sym:<15} {qty:<8} {status_msg}")

    if not shieldable_list:
        print("\n✅ All journalled trades are already protected or missing data.")
        input("\nPress Enter to exit...")
        return

    print("-" * 60)
    confirm = input(f"\n🚀 SHIELD ALL {len(shieldable_list)} READY TRADES? (Y/N): ").upper()
    
    if confirm == 'Y':
        for item in shieldable_list:
            sym = item['symbol']
            sec_id = id_map.get(sym)
            if not sec_id:
                print(f"⚠️ Skipping {sym}: Security ID not found.")
                continue
            
            print(f"📡 Activating OCO for {sym} (Tgt: {item['target']}, SL: {item['sl']})...")
            try:
                # OCO Order Logic
                res = dhan.place_forever(
                    security_id=str(sec_id),
                    exchange_segment=dhan.NSE,
                    product_type=dhan.CNC,
                    order_type=dhan.LIMIT,
                    transaction_type=dhan.SELL,
                    quantity=item['qty'],
                    # Target Leg
                    price=item['target'],
                    trigger_Price=item['target'],
                    # Stop Leg (OCO)
                    order_flag="OCO",
                    quantity1=item['qty'],
                    price1=item['sl'] * 0.995, # Slight buffer for SL limit
                    trigger_Price1=item['sl']
                )
                if res['status'] == 'success':
                    print(f"   ✅ SHIELD ACTIVE (ID: {res['data']['orderId']})")
                else:
                    print(f"   ❌ FAILED: {res.get('remarks')}")
                time.sleep(0.5) # Anti-throttle
            except Exception as e:
                print(f"   ❌ ERROR: {e}")

    print("\nMission Accomplished.")
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    run_auto_shield()
