import re

PINE_PATH = "Weinstein and Swing Pro Dashboard v67.4.12.pine"

def fix_pine():
    with open(PINE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Fix finalT1 and finalT2 indentation
    # Currently it looks like:
    # finalTSL := 0.0
    #     finalT1 := 0.0
    #     finalT2 := 0.0
    # finalDate := 0
    # We want:
    # finalTSL := 0.0
    # finalT1 := 0.0
    # finalT2 := 0.0
    # finalDate := 0
    content = content.replace("finalTSL := 0.0\n    finalT1 := 0.0\n    finalT2 := 0.0\nfinalDate := 0", "finalTSL := 0.0\nfinalT1 := 0.0\nfinalT2 := 0.0\nfinalDate := 0")

    # 2. Remove dangling finalDate := pX_date for 21-30
    for i in range(21, 31):
        content = content.replace(f"    finalDate := p{i}_date\n", "")

    # 3. Remove get_sector lookups for 21-30
    for i in range(21, 31):
        pattern = re.compile(rf'^[ \t]*else if f_match\(p{i}_tick\)\n[ \t]*t := p{i}_sec\n[ \t]*n := str\.replace_all\(p{i}_sec, "NSE:", ""\)\n?', re.MULTILINE)
        content = pattern.sub('', content)

    # 4. Remove CSV export lines for 21-30
    for i in range(21, 31):
        content = content.replace(f"    csv_out := csv_out + f_row(p{i}_tick, p{i}_ent, p{i}_sl, p{i}_date, p{i}_sec)\n", "")

    with open(PINE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("✅ Pine Script formatting and p21-p30 references fixed.")

if __name__ == "__main__":
    fix_pine()
