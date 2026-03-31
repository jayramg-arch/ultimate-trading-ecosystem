
# Read first 50 lines line by line to see the structure
with open("List of trades-2025-26.html", "r", encoding='utf-8') as f:
    for _ in range(50):
        print(f.readline().strip())
        
# Also, search for "Buy" or "Sell" in the whole file
print("\n--- Search for 'Buy' or 'Sell' ---")
with open("List of trades-2025-26.html", "r", encoding='utf-8') as f:
    content = f.read()
    if "Buy" in content:
        print("Found 'Buy' keyword!")
        # Print context
        idx = content.find("Buy")
        print(content[idx-50:idx+50])
    
    if "Sell" in content:
        print("Found 'Sell' keyword!")
        idx = content.find("Sell")
        print(content[idx-50:idx+50])
