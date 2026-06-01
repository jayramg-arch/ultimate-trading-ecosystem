import re

with open('Weinstein_Unified_Ecosystem.pine', 'r', encoding='utf-8') as f:
    text = f.read()
    
# Fix Bull Market Emoji
text = text.replace('ðŸ ‚', '🐂')

# Fix CB Pillars
text = text.replace('â— ', '●')

# Combine CB Pillars
old_cb = '''    // --- CB Pillars (individual rows, not compressed into one string) ---
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
    string pillars_grid = p1_dot + p2_dot + p3_dot + p4_dot + " (" + str.tostring(n_pillars) + "/4)"

    f_row(dash, r, "CB Pillars",               pillars_grid, pillars_col, c_lbl, c_val, c_lbl_txt)
    r += 1
    f_row(dash, r, "  P1: Stretched Drawdown", is_stretched ? "✓" : "○", p1_col, c_lbl, c_val, c_lbl_txt)
    r += 1
    f_row(dash, r, "  P2: Washout / Oversold", is_oversold  ? "✓" : "○", p2_col, c_lbl, c_val, c_lbl_txt)
    r += 1
    f_row(dash, r, "  P3: Climax Wide Bar",    climax_bar   ? "✓" : "○", p3_col, c_lbl, c_val, c_lbl_txt)
    r += 1
    f_row(dash, r, "  P4: Turn Bar",           is_turn      ? "✓" : "○", p4_col, c_lbl, c_val, c_lbl_txt)
    r += 1'''

new_cb = '''    // --- CB Pillars ---
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
    r += 1'''

if old_cb in text:
    text = text.replace(old_cb, new_cb)
    print('CB Pillars combined.')
else:
    print('Could not find old CB pillars string.')

with open('Weinstein_Unified_Ecosystem.pine', 'w', encoding='utf-8') as f:
    f.write(text)
print('Done!')
