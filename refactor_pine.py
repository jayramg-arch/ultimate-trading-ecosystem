import re

with open("Weinstein and Swing Pro Dashboard v67.0.pine", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Trail SL inputs
for i in range(1, 31):
    # Find the pX_sl input
    pattern = rf'(p{i}_sl\s*=\s*input\.price\([^,]+,\s*title="SL"[^\)]+\))'
    
    grp_start = ((i-1)//5)*5 + 1
    grp_end = grp_start + 4
    grp_name = f"grpP{grp_start}_{grp_end}"
    if i >= 6 and i <= 10:
        grp_name = "grpP6_10" # Fix standard naming just in case
    
    def replacer(match):
        return match.group(1) + f'\np{i}_tsl  = input.price(0.0, title="Trail SL", group={grp_name}, inline="p{i}", display=display.data_window)'
        
    content = re.sub(pattern, replacer, content)

# 2. Add var finalTSL
content = content.replace('var float finalSL = 0.0\n', 'var float finalSL = 0.0\nvar float finalTSL = 0.0\n')

# 3. Add finalTSL assignments
for i in range(1, 31):
    pattern = rf'(finalSL\s*:=\s*p{i}_sl)'
    def replacer2(match):
        return match.group(1) + f'\n    finalTSL := p{i}_tsl'
    content = re.sub(pattern, replacer2, content)

content = content.replace('finalSL := 0.0\n', 'finalSL := 0.0\n    finalTSL := 0.0\n')
content = content.replace('finalSL    := quick_sl\n', 'finalSL    := quick_sl\n    finalTSL   := 0.0\n')

with open("Weinstein and Swing Pro Dashboard v67.0_mod.pine", "w", encoding="utf-8") as f:
    f.write(content)
