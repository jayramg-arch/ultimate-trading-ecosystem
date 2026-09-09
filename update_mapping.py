with open('Stock to Sector mappings for pine script-1.txt', 'r', encoding='utf-8') as f:
    mapping_lines = f.readlines()

# Add indentation
mapping_content = ""
for line in mapping_lines:
    mapping_content += "        " + line.strip() + "\n"

with open('Weinstein_Unified_Ecosystem.pine', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# Regex to replace the block
# We will match from "    s := switch t" up to "        => """
pattern = r'(    s := switch t\n)(.*?)(        => "")'
match = re.search(pattern, text, flags=re.DOTALL)

if match:
    new_text = text[:match.start(2)] + mapping_content + text[match.end(2):]
    with open('Weinstein_Unified_Ecosystem.pine', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Mapping updated successfully!")
else:
    print("Could not find the mapping block in the file.")
