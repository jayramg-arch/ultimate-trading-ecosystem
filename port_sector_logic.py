import re
import sys

cap_path = 'Commander_Capitulation_Screener_v1.3.pine'
beta_path = 'Commander_Screener_Beta_Edition_v2.5.pine'

with open(beta_path, 'r', encoding='utf-8') as f:
    beta_content = f.read()

# Extract Sector Mapping Logic from Beta Screener
# from f_get_sector_ticker() => to the end of f_get_hybrid_sector() => ... t\n
sector_pattern = r'(f_get_sector_ticker\(\) =>\n.*?f_get_hybrid_sector\(\) =>\n.*?    t\n)'
match = re.search(sector_pattern, beta_content, flags=re.DOTALL)
if not match:
    print("Could not find sector logic in Beta Screener")
    sys.exit(1)

sector_logic = match.group(1) + "\n"

with open(cap_path, 'r', encoding='utf-8') as f:
    cap_content = f.read()

# Insert before SECTION 2
insert_target = '// ─────────────────────────────────────────────────────────────────────────────\n// SECTION 2:'
if insert_target in cap_content and 'f_get_sector_ticker' not in cap_content:
    cap_content = cap_content.replace(insert_target, sector_logic + "\n" + insert_target)
    print("Injected sector logic before SECTION 2.")
elif 'f_get_sector_ticker' in cap_content:
    print("Sector logic already injected.")
else:
    print("Could not find SECTION 2 to inject.")

with open(cap_path, 'w', encoding='utf-8') as f:
    f.write(cap_content)

print("Saved Capitulation Screener.")
