from watchlist_manager import generate_tradingview_files
import os

print("Running Watchlist Generation...")
generate_tradingview_files()

print("\nVerifying Files:")
WATCHLIST_DIR = os.path.join(os.getcwd(), "Generated_Watchlists")
expected_files = [
    "FINAL_Hunter_Picks.txt",
    "FINAL_Pullback_Picks.txt",
    "FINAL_EarlyBird_Picks.txt",
    "FINAL_Leader_Picks.txt"
]

all_exist = True
for f in expected_files:
    path = os.path.join(WATCHLIST_DIR, f)
    exists = os.path.exists(path)
    print(f"[{'✅' if exists else '❌'}] {f}")
    if not exists:
        all_exist = False

if all_exist:
    print("\n✅ Verification SUCCESS: All static files created.")
else:
    print("\n❌ Verification FAILED: Missing files.")
