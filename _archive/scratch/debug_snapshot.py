import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\jayra\Documents\GeminiVSCode')

from market_data_hub import build_postmarket_snapshot

print("Fetching post-market snapshot...")
snap = build_postmarket_snapshot()

# Show what we got
print("\n=== SNAPSHOT KEYS ===")
for k, v in snap.items():
    if isinstance(v, (dict, list)):
        print(f"  {k}: {type(v).__name__} with {len(v)} items")
        if k == 'india_indices':
            for idx_name, idx_data in v.items():
                print(f"    {idx_name}: {idx_data}")
        elif k == 'fii_dii_last5':
            for row in v:
                print(f"    {row}")
        elif k == 'global' and isinstance(v, dict):
            for section, sdata in v.items():
                if isinstance(sdata, dict):
                    first_key = next(iter(sdata), None)
                    print(f"    {section}: {len(sdata)} items, first: {first_key}")
    else:
        print(f"  {k}: {v}")

# Show JSON size
context = json.dumps(snap, indent=2, default=str)
print(f"\n=== JSON SIZE: {len(context)} chars ===")
print("\nFirst 2000 chars of context:")
print(context[:2000])
