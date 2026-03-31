import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from dotenv import load_dotenv
from dhanhq import dhanhq

# ==========================================
# 1. CONFIGURATION
# ==========================================
BG_COLOR = "#1e1e2e"       # Dark Blue-Grey
BTN_COLOR = "#4a4a6a"      # Lighter Grey
TEXT_COLOR = "#ffffff"     # White
ACCENT_COLOR = "#00e676"   # Green
TAB_BG = "#2e2e3e"         # Tab Background

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_script_path(filename):
    base_folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_folder, filename)

def get_base_folder():
    return os.path.dirname(os.path.abspath(__file__))

def check_connection():
    load_dotenv(get_script_path(".env"))
    try:
        dhan = dhanhq(os.getenv("DHAN_CLIENT_ID"), os.getenv("DHAN_ACCESS_TOKEN"))
        resp = dhan.get_fund_limits()
        if resp['status'] == 'success':
            lbl_status.config(text="● SYSTEM ONLINE", fg=ACCENT_COLOR)
        else:
            lbl_status.config(text="● TOKEN EXPIRED", fg="red")
    except:
        lbl_status.config(text="● CONNECTION FAILED", fg="red")

def launch_script(script_name, arg=None):
    """
    Launches script with optional argument.
    arg: '1', '2', etc.
    """
    full_path = get_script_path(script_name)
    base_folder = get_base_folder()

    if not os.path.exists(full_path):
        messagebox.showerror("Error", f"File not found:\n{full_path}")
        return

    try:
        # Construct command: "python script.py [arg]"
        cmd_str = f'"{sys.executable}" "{script_name}"'
        if arg:
            cmd_str += f" {arg}"

        # /k = Keep open so you can see the result (Success/Fail)
        # We use /k intentionally now so you can verify the CSV save message
        cmd = f'start cmd /k "cd /d "{base_folder}" && {cmd_str}"'
        
        os.system(cmd)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch: {e}")

# ==========================================
# 3. GUI LAYOUT
# ==========================================
root = tk.Tk()
root.title("Weinstein Commander v8.0")
root.geometry("500x650")
root.configure(bg=BG_COLOR)
root.resizable(False, False)

# Header
lbl_title = tk.Label(root, text="WEINSTEIN\nCOMMANDER", font=("Segoe UI", 20, "bold"), bg=BG_COLOR, fg=TEXT_COLOR)
lbl_title.pack(pady=15)

lbl_status = tk.Label(root, text="● CHECKING...", font=("Segoe UI", 10), bg=BG_COLOR, fg="yellow")
lbl_status.pack(pady=5)

# Tabs
style = ttk.Style()
style.theme_use('clam')
style.configure("TNotebook", background=BG_COLOR, borderwidth=0)
style.configure("TNotebook.Tab", background=BTN_COLOR, foreground="white", padding=[10, 8], font=("Segoe UI", 9))
style.map("TNotebook.Tab", background=[("selected", ACCENT_COLOR)], foreground=[("selected", "black")])

notebook = ttk.Notebook(root)
notebook.pack(pady=10, padx=20, fill="both", expand=True)

# ------------------------------------
# TAB 1: SCANNERS
# ------------------------------------
tab_scan = tk.Frame(notebook, bg=TAB_BG)

notebook.add(tab_scan, text="  1. Scanners  ")

tk.Label(tab_scan, text="Technical Analysis (Chartink)", bg=TAB_BG, fg="#aaaaaa").pack(pady=10)

# Pass "1" to the script automatically
btn_hunter = tk.Button(tab_scan, text="Option 1: Stage 2 Hunter\n(Positional Breakout)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=40,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("chartink_scanner_v16.py", "1"))
btn_hunter.pack(pady=5)

# Pass "2"
btn_pull = tk.Button(tab_scan, text="Option 2: Stage 2 Pullback\n(Swing Entry)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=40,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("chartink_scanner_v14.py", "2"))
btn_pull.pack(pady=5)

# Pass "3"
btn_early = tk.Button(tab_scan, text="Option 3: Early Birds\n(Accumulation)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=40,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("chartink_scanner_v14.py", "3"))
btn_early.pack(pady=5)

# Pass "4"
btn_lead = tk.Button(tab_scan, text="Option 4: Strong Leaders\n(Momentum)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=40,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("chartink_scanner_v14.py", "4"))
btn_lead.pack(pady=5)

# ------------------------------------
# TAB 2: MATCHER
# ------------------------------------
tab_match = tk.Frame(notebook, bg=TAB_BG)
notebook.add(tab_match, text="  2. Matcher  ")

tk.Label(tab_match, text="Fundamental Filter", bg=TAB_BG, fg="#aaaaaa").pack(pady=10)

btn_proc = tk.Button(tab_match, text="A. Process Screener HTMLs\n(Converts to CSV)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=40,
                activebackground="#00b359",
                command=lambda: launch_script("screener_processor.py"))
btn_proc.pack(pady=10)

btn_match = tk.Button(tab_match, text="B. ✨ Run Golden Matcher ✨\n(Finds Intersections)", font=("Segoe UI", 10, "bold"),
                bg=ACCENT_COLOR, fg="black", relief="flat", height=3, width=40,
                activebackground="#00994d",
                command=lambda: launch_script("brute_force_match.py"))
btn_match.pack(pady=10)

# ------------------------------------
# TAB 3: EXECUTION
# ------------------------------------
tab_exec = tk.Frame(notebook, bg=TAB_BG)
notebook.add(tab_exec, text="  3. Trade  ")

tk.Label(tab_exec, text="Execute & Protect", bg=TAB_BG, fg="#aaaaaa").pack(pady=10)

btn_sniper = tk.Button(tab_exec, text="🎯 Sniper Entry\n(Place AMOs)", font=("Segoe UI", 12, "bold"),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=35,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("sniper_trigger.py"))
btn_sniper.pack(pady=10)

btn_audit = tk.Button(tab_exec, text="🏥 Portfolio Health", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=35,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("portfolio_audit.py"))
btn_audit.pack(pady=5)

btn_sentinel = tk.Button(tab_exec, text="🛡️ Activate Sentinel (GTT)", font=("Segoe UI", 10),
                bg=BTN_COLOR, fg=TEXT_COLOR, relief="flat", height=2, width=35,
                activebackground=ACCENT_COLOR,
                command=lambda: launch_script("gtt_portfolio_v2.py"))
btn_sentinel.pack(pady=5)

# Footer
lbl_footer = tk.Label(root, text="v8.0 | Auto-Argument Integration", font=("Segoe UI", 8), bg=BG_COLOR, fg="#666666")
lbl_footer.pack(side="bottom", pady=10)

root.after(100, check_connection)
root.mainloop()