import sqlite3
import re
import sys
from datetime import datetime

# Force UTF-8 encoding for standard output to fix UnicodeEncodeError in Windows subprocesses
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

PINE_PATH = "Weinstein and Swing Pro Dashboard v67.4.12.pine"
DB_PATH = "trade_journal_v6.db"
DEFAULT_SECTOR = "NSE:CNX500"

def normalize_ticker(t):
    if not t: return ""
    # TradingView substitutes "_" for BOTH "-" and "&" in NSE symbols. Only "-" was
    # handled, so NAM-INDIA mapped correctly to NAM_INDIA while M&MFIN stayed
    # "M&MFIN" and could never match syminfo.tickerid ("NSE:M_MFIN") - that slot
    # sat on the chart matching nothing, with no error to show for it.
    return (str(t).strip().upper().replace("NSE:", "").replace("BSE:", "")
            .replace("-", "_").replace("&", "_"))

def main():
    print("\n" + "="*60)
    print("🔄 DB PORTFOLIO SYNC (SQLite -> Pine Script)")
    print("="*60)

    # 1. Fetch from DB
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal WHERE status='OPEN' ORDER BY id ASC")
        open_trades = cursor.fetchall()
        print(f"✅ Fetched {len(open_trades)} active trades from DB.")
    except Exception as e:
        print(f"❌ Error reading DB: {e}")
        return

    # 2. Read Pine Script to preserve existing dates and TSL if we want
    try:
        with open(PINE_PATH, "r", encoding="utf-8") as f:
            pine_content = f.read()
    except Exception as e:
        print(f"❌ Error reading {PINE_PATH}: {e}")
        return

    # Extract existing inputs to preserve TSL and Date if they aren't changing
    existing_tsl = {}
    existing_dates = {}
    
    # Try to extract existing values using regex
    for match in re.finditer(r'p\d+_tick\s*=\s*input\.string\("([^"]+)".*?p\d+_tsl\s*=\s*input\.(?:price|float)\(([^,]+).*?p\d+_date\s*=\s*input\.time\(([^,]+)', pine_content, re.DOTALL):
        t = normalize_ticker(match.group(1).strip())
        if t:
            existing_tsl[t] = match.group(2).strip()
            existing_dates[t] = match.group(3).strip()

    # 3. Generate Pine Code
    lines = []
    
    # 25 SLOTS, not 20 (2 Sep 2026). v67 grew to slots 21-25 - it carries 55 references
    # to p21..p25 - but this loop was never raised with it, so the generated block
    # declared only p1..p20 and pasting it left every p21+ use site undeclared. The
    # group logic below already handled 21-25 and 26-30; only the bound was stale.
    # Also: the live book is 22 positions, so at 20 slots two holdings could not reach
    # the chart at all. Raise this and v67's slot count TOGETHER.
    for i in range(1, 26):
        tick = ""
        entry = 0.0
        sl = 0.0
        t1 = 0.0
        t2 = 0.0
        sec = DEFAULT_SECTOR
        date_val = "0"
        tsl_val = "0.0"

        if i - 1 < len(open_trades):
            row = open_trades[i - 1]
            raw_sym = row['symbol']
            tick = f"NSE:{normalize_ticker(raw_sym)}" if raw_sym else ""
            entry = float(row['buy_price']) if row['buy_price'] else 0.0
            sl = float(row['stoploss']) if row['stoploss'] else 0.0
            t1 = float(row['target1']) if 'target1' in row.keys() and row['target1'] else 0.0
            t2 = float(row['target2']) if 'target2' in row.keys() and row['target2'] else 0.0
            sec = row['sector'] if row['sector'] else DEFAULT_SECTOR
            
            # Format Date for Pine Script timestamp()
            entry_date = row['entry_date']
            if entry_date:
                try:
                    dt_obj = datetime.strptime(entry_date, "%Y-%m-%d")
                    date_val = f'timestamp("{entry_date}")'
                except:
                    date_val = "0"
        
        # Preserve TSL if same ticker
        norm_t = normalize_ticker(tick)
        if norm_t in existing_tsl:
            tsl_val = existing_tsl[norm_t]
            
        # Preserve Date if DB has no date
        if date_val == "0" and norm_t in existing_dates:
            date_val = existing_dates[norm_t]
            
        # Group Logic
        grp_var = "grpP1_5"
        if i == 1: lines.append(f'grpP1_5 = "1. Portfolio Slots 1-5"')
        elif i == 6: 
            lines.append(f'\n// --- GROUP 2: SLOTS 6-10 ---')
            lines.append(f'grpP6_10 = "2. Portfolio Slots 6-10"')
        elif i == 11:
            lines.append(f'\n// --- GROUP 3: SLOTS 11-15 ---')
            lines.append(f'grpP11_15 = "3. Portfolio Slots 11-15"')
        elif i == 16:
            lines.append(f'\n// --- GROUP 4: SLOTS 16-20 ---')
            lines.append(f'grpP16_20 = "4. Portfolio Slots 16-20"')
        elif i == 21:
            lines.append(f'\n// --- GROUP 5: SLOTS 21-25 ---')
            lines.append(f'grpP21_25 = "5. Portfolio Slots 21-25"')
        elif i == 26:
            lines.append(f'\n// --- GROUP 6: SLOTS 26-30 ---')
            lines.append(f'grpP26_30 = "6. Portfolio Slots 26-30"')
            
        if i <= 5: grp_var = "grpP1_5"
        elif i <= 10: grp_var = "grpP6_10"
        elif i <= 15: grp_var = "grpP11_15"
        elif i <= 20: grp_var = "grpP16_20"
        elif i <= 25: grp_var = "grpP21_25"
        else: grp_var = "grpP26_30"

        # Create inline parameters for inputs
        lines.append(f'p{i}_tick = input.string("{tick}", title="Slot {i}", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_ent  = input.float({entry}, title="Entry", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_sl   = input.float({sl}, title="SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_tsl  = input.float({tsl_val}, title="Trail SL", group={grp_var}, inline="p{i}", display=display.data_window)')
        lines.append(f'p{i}_t1   = input.float({t1}, title="T1", group={grp_var}, inline="p{i}t", display=display.data_window)')
        lines.append(f'p{i}_t2   = input.float({t2}, title="T2", group={grp_var}, inline="p{i}t", display=display.data_window)')
        lines.append(f'p{i}_sec  = input.string("{sec}", title="Sector", group={grp_var}, inline="p{i}s", display=display.data_window)')
        lines.append(f'p{i}_date = input.time({date_val}, title="Date", group={grp_var}, inline="p{i}d", display=display.data_window)')
        lines.append("")

    new_code_block = "\n".join(lines)

    # 4. Inject
    try:
        start_marker = "// <PORTFOLIO_START>"
        end_marker = "// <PORTFOLIO_END>"
        
        s_idx = pine_content.find(start_marker)
        e_idx = pine_content.find(end_marker)
        
        if s_idx == -1 or e_idx == -1:
            print("❌ Error: Target markers not found in Pine Script.")
        else:
            new_content = pine_content[:s_idx + len(start_marker)] + "\n" + new_code_block + pine_content[e_idx:]
            
            with open(PINE_PATH, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("✅ Pine Script Inputs Updated Successfully.")
            
    except Exception as e:
        print(f"❌ Error editing Pine file: {e}")

if __name__ == "__main__":
    main()
