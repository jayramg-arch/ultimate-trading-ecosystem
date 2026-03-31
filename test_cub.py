import sys
sys.path.append('e:\\Gemini\\VS Code')
from fundamental_xray import fetch_fundamentals

print("Executing fetch_fundamentals('CUB')...")
data = fetch_fundamentals('CUB')
print(f"RevenueTTM: {data.get('RevenueTTM')}")
print(f"OpMargin: {data.get('OpMargin')}")
print(f"PriceToBook: {data.get('PriceToBook')}")
print(f"EpsTTM: {data.get('EpsTTM')}")
