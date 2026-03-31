import dhanhq
import inspect

print("\n" + "="*40)
print("🔍 LIBRARY DIAGNOSTIC")
print("="*40)

# 1. Check Location (Where is it loading from?)
print(f"📂 File Path: {dhanhq.__file__}")

# 2. Check Available Methods
# We look for the exact function name for GTT/Forever orders
dhan_methods = dir(dhanhq.dhanhq)
forever_methods = [m for m in dhan_methods if 'forever' in m or 'gtt' in m]

if forever_methods:
    print(f"✅ SUCCESS! Found new methods: {forever_methods}")
    print("   You are now on Version 2.0 (The Modern Era).")
    print("   Please proceed to Step 3.")
else:
    print("❌ FAILURE: Still on Version 1.0 (The Stone Age).")
    print("   The upgrade command did not work.")
    print("   Try restarting VS Code and running the upgrade command again.")