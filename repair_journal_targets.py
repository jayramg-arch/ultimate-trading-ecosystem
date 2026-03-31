import sqlite3
import math

DB_FILE = "trade_journal_v6.db"

def repair_targets():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Find OPEN trades with SL but no Target
        c.execute("SELECT symbol, buy_price, stoploss FROM journal WHERE status = 'OPEN' AND stoploss > 0 AND (target IS NULL OR target = 0)")
        missing = c.fetchall()
        
        if not missing:
            print("✅ No missing targets found for active trades.")
            return

        print(f"🔧 Repairing {len(missing)} entries...")
        for sym, buy, sl in missing:
            if not buy or buy <= 0:
                print(f"⚠️ Skipping {sym}: Buy Price is 0. Please fix in Journal UI.")
                continue
                
            # Use absolute distance for reward unit in case of Trailed SL
            reward_unit = abs(buy - sl)
            if reward_unit == 0:
                print(f"⚠️ Skipping {sym}: SL is exactly at Buy Price.")
                continue
                
            # Default 1:2 RR from the Buy Price
            new_target = buy + (reward_unit * 2)
            
            # Ensure target is actually above SL
            if new_target <= sl:
                new_target = sl + (reward_unit * 2)

            c.execute("UPDATE journal SET target = ?, planned_rr = '1:2' WHERE symbol = ?", (new_target, sym))
            print(f"   ✅ {sym}: Target set to ₹{new_target:.2f} (1:2 R:R logic)")
            
        conn.commit()
        conn.close()
        print("\nDatabase Repair Complete.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    repair_targets()
