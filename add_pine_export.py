
# This python script will read the pine file and inject the export logic at the end.
# It effectively replaces the manual coding step to ensure consistency.

file_path = "e:/Gemini/VS Code/Weinstein & Swing Pro Dashboard v53.12Pine code.pine"

# The Pine Script block to append
export_logic = """
// ==========================================
// 11. EXPORT PORTFOLIO TO CSV (User Request)
// ==========================================
show_csv = input.bool(false, title="Export Portfolio to CSV Log", group="Data Tools", tooltip="Enable this, then check 'Pine Logs' tab to copy your portfolio data (Ticker, Entry, SL, Sector) in CSV format.")

if show_csv and barstate.islast and time_ok
    string csv_out = "Ticker,Entry,SL,Sector\\n"
    
    // Helper to format row
    f_row(t, e, s, sec) =>
        if t != ""
            t + "," + str.tostring(e) + "," + str.tostring(s) + "," + str.tostring(sec) + "\\n"
        else
            ""

    csv_out := csv_out + f_row(p1_tick, p1_ent, p1_sl, p1_sec)
    csv_out := csv_out + f_row(p2_tick, p2_ent, p2_sl, p2_sec)
    csv_out := csv_out + f_row(p3_tick, p3_ent, p3_sl, p3_sec)
    csv_out := csv_out + f_row(p4_tick, p4_ent, p4_sl, p4_sec)
    csv_out := csv_out + f_row(p5_tick, p5_ent, p5_sl, p5_sec)
    csv_out := csv_out + f_row(p6_tick, p6_ent, p6_sl, p6_sec)
    csv_out := csv_out + f_row(p7_tick, p7_ent, p7_sl, p7_sec)
    csv_out := csv_out + f_row(p8_tick, p8_ent, p8_sl, p8_sec)
    csv_out := csv_out + f_row(p9_tick, p9_ent, p9_sl, p9_sec)
    csv_out := csv_out + f_row(p10_tick, p10_ent, p10_sl, p10_sec)
    csv_out := csv_out + f_row(p11_tick, p11_ent, p11_sl, p11_sec)
    csv_out := csv_out + f_row(p12_tick, p12_ent, p12_sl, p12_sec)
    csv_out := csv_out + f_row(p13_tick, p13_ent, p13_sl, p13_sec)
    csv_out := csv_out + f_row(p14_tick, p14_ent, p14_sl, p14_sec)
    csv_out := csv_out + f_row(p15_tick, p15_ent, p15_sl, p15_sec)
    csv_out := csv_out + f_row(p16_tick, p16_ent, p16_sl, p16_sec)
    csv_out := csv_out + f_row(p17_tick, p17_ent, p17_sl, p17_sec)
    csv_out := csv_out + f_row(p18_tick, p18_ent, p18_sl, p18_sec)
    csv_out := csv_out + f_row(p19_tick, p19_ent, p19_sl, p19_sec)
    csv_out := csv_out + f_row(p20_tick, p20_ent, p20_sl, p20_sec)
    csv_out := csv_out + f_row(p21_tick, p21_ent, p21_sl, p21_sec)
    csv_out := csv_out + f_row(p22_tick, p22_ent, p22_sl, p22_sec)
    csv_out := csv_out + f_row(p23_tick, p23_ent, p23_sl, p23_sec)
    csv_out := csv_out + f_row(p24_tick, p24_ent, p24_sl, p24_sec)
    csv_out := csv_out + f_row(p25_tick, p25_ent, p25_sl, p25_sec)

    log.info("\\n⬇️ COPY PORTFOLIO CSV BELOW ⬇️\\n\\n" + csv_out + "\\n⬆️ COPY PORTFOLIO CSV ABOVE ⬆️")
    alert("Portfolio CSV Data Generated. Check Pine Logs.", alert.freq_once_per_bar_close)
"""

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Only append if not already present
if "EXPORT PORTFOLIO TO CSV" not in content:
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n" + export_logic)
    print("Export logic appended successfully.")
else:
    print("Export logic already exists.")
