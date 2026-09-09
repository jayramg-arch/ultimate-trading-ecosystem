import re

PINE_PATH = "Weinstein and Swing Pro Dashboard v67.4.12.pine"
SYNC_PATH = "db_portfolio_sync.py"

def remove_pine_slots():
    with open(PINE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # We want to remove any "else if f_match(pX_tick)" blocks for X from 21 to 30.
    # The regex matches the 'else if' line up to the next 'else if' or whatever comes after.
    # But string replacement is safer if we just match exactly.
    for i in range(21, 31):
        # We find "else if f_match(pX_tick)"
        # and the lines inside it.
        pattern = re.compile(rf'^[ \t]*else if f_match\(p{i}_tick\)\n[ \t]*finalEntry := p{i}_ent\n[ \t]*finalSL := p{i}_sl\n[ \t]*finalTSL := p{i}_tsl\n[ \t]*finalT1 := p{i}_t1\n[ \t]*finalT2 := p{i}_t2\n?', re.MULTILINE)
        content = pattern.sub('', content)

    with open(PINE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"✅ Removed slots 21-30 f_match logic from {PINE_PATH}")

def update_sync_script():
    with open(SYNC_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Change loop range from range(1, 31) to range(1, 21)
    content = content.replace("for i in range(1, 31):", "for i in range(1, 21):")
    
    with open(SYNC_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"✅ Updated loop range in {SYNC_PATH}")

if __name__ == "__main__":
    remove_pine_slots()
    update_sync_script()
