import re

file_path = "e:/Gemini/VS Code/Weinstein & Swing Pro Dashboard v53.12Pine code.pine"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace input.float with input.price ONLY for _sl variables
# Patern: p1_sl = input.float(...)
# We want: p1_sl = input.price(...)
# We strictly match variables ending in _sl to avoid affecting others.

new_content = re.sub(r'(\w+_sl\s*=\s*)input\.float\(', r'\1input.price(', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Successfully updated input.float to input.price for SL variables.")
