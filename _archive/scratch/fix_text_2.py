with open('Weinstein_Unified_Ecosystem.pine', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = 0

for i, line in enumerate(lines):
    if skip > 0:
        skip -= 1
        continue

    # Fix emojis
    if 'ðŸ ‚' in line:
        line = line.replace('ðŸ ‚', '🐂')
    if 'â— ' in line:
        line = line.replace('â— ', '●')

    # Detect start of CB Pillars block
    if '// --- CB Pillars (individual rows, not compressed into one string) ---' in line:
        # We want to replace this and the next 22 lines with our compressed block
        new_block = """    // --- CB Pillars ---
    color p1_col = is_stretched ? c_sig_on : c_sig_off
    color p2_col = is_oversold  ? c_sig_on : c_sig_off
    color p3_col = climax_bar   ? c_sig_on : c_sig_off
    color p4_col = is_turn      ? c_sig_on : c_sig_off
    int   n_pillars = (is_stretched ? 1 : 0) + (is_oversold ? 1 : 0) + (climax_bar ? 1 : 0) + (is_turn ? 1 : 0)
    color pillars_col = n_pillars >= 3 ? c_sig_on : n_pillars >= 2 ? c_sig_warn : c_sig_off
    string p1_dot = is_stretched ? "●" : "○"
    string p2_dot = is_oversold  ? "●" : "○"
    string p3_dot = climax_bar   ? "●" : "○"
    string p4_dot = is_turn      ? "●" : "○"
    string pillars_grid = "P1 " + p1_dot + "  P2 " + p2_dot + "  P3 " + p3_dot + "  P4 " + p4_dot + " (" + str.tostring(n_pillars) + "/4)"

    f_row(dash, r, "CB Pillars", pillars_grid, pillars_col, c_lbl, c_val, c_lbl_txt)
    r += 1
"""
        new_lines.append(new_block)
        skip = 22 # skip the 22 lines of the old CB Pillars block
    else:
        new_lines.append(line)

with open('Weinstein_Unified_Ecosystem.pine', 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)
print('Done!')
