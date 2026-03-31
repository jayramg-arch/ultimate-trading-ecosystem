import dhanhq
from dotenv import load_dotenv
import os
from dhanhq import dhanhq

load_dotenv()
try:
    dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
    print("\n✅ Connection Object Created.")
    
    # Check what functions exist inside 'dhan'
    all_methods = dir(dhan)
    
    print("\n🔍 SEARCHING FOR GTT/FOREVER METHODS...")
    found = [m for m in all_methods if 'forever' in m or 'gtt' in m]
    
    if found:
        print(f"🎉 FOUND THEM! You should use these names: {found}")
    else:
        print("❌ STILL MISSING. Did you run the 'pip install --upgrade' command?")
        print("   Current installed version might still be old.")

except Exception as e:
    print(e)