import io
import sys

filepath = r'C:\Users\jayra\Documents\GeminiVSCode\Weinstein_Unified_Ecosystem.pine'

with io.open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "SECTION A:" in line and "BULL MARKET" in line:
        lines[i] = '    //  SECTION A: 🐂 BULL MARKET\n'
    elif "BULL MARKET STRATEGY" in line and "f_hdr" in line:
        lines[i] = '    f_hdr(dash, r, "🐂  BULL MARKET STRATEGY", c_head_bull)\n'
    elif "SECTION B:" in line and "RECOVERY MARKET" in line:
        lines[i] = '    //  SECTION B: 🔄 RECOVERY MARKET\n'
    elif "RECOVERY MARKET STRATEGY" in line and "f_hdr" in line:
        lines[i] = '    f_hdr(dash, r, "🔄  RECOVERY MARKET STRATEGY", c_head_rec)\n'
    elif "Icon helper for signal hold-window display:" in line:
        lines[i] = '// Icon helper for signal hold-window display: 🟢 FIRE | 🟡 HOLD | ⚫ WAIT\n'
    elif "bars_ago == 0 ?" in line and "bars_ago <=" in line:
        lines[i] = '    bars_ago == 0 ? "🟢" : (bars_ago <= hold_days ? "🟡" : "⚫")\n'
    elif "string p1_dot =" in line and "is_stretched" in line:
        lines[i] = '    string p1_dot = is_stretched ? "●" : "○"\n'
    elif "string p2_dot =" in line and "is_oversold" in line:
        lines[i] = '    string p2_dot = is_oversold  ? "●" : "○"\n'
    elif "string p3_dot =" in line and "climax_bar" in line:
        lines[i] = '    string p3_dot = climax_bar   ? "●" : "○"\n'
    elif "string p4_dot =" in line and "is_turn" in line:
        lines[i] = '    string p4_dot = is_turn      ? "●" : "○"\n'

with io.open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)
