import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fundamental_xray import fetch_fundamentals

print("Executing fetch_fundamentals('CUB')...")
data = fetch_fundamentals('CUB')
print(f"RevenueTTM: {data.get('RevenueTTM')}")
print(f"OpMargin: {data.get('OpMargin')}")
print(f"PriceToBook: {data.get('PriceToBook')}")
print(f"EpsTTM: {data.get('EpsTTM')}")
