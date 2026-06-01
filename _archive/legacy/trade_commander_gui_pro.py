import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import webbrowser
import subprocess
from dotenv import load_dotenv
from dhanhq import dhanhq
import watchlist_manager # New Module

# ==========================================
# 1. CONFIGURATION & THEME
# ==========================================
COLORS = {
    "bg": "#1e1e2e",        # Main Background (Dark Blue-Grey)
    "panel": "#252535",      # Lighter Panel Background
    "primary": "#00e676",    # Bright Green (Accent)
    "primary_hover": "#00c853",
    "text": "#ffffff",       # White Text
    "text_dim": "#a0a0b0",   # Dimmed Text
    "btn_default": "#3a3a4b",
    "btn_hover": "#4a4a5b",
    "danger": "#ff5252"
}

FONTS = {
    "h1": ("Segoe UI", 22, "bold"),
    "h2": ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 10),
    "small": ("Segoe UI", 9)
}

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_script_path(filename):
    base_folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_folder, filename)

def get_base_folder():
    return os.path.dirname(os.path.abspath(__file__))

def check_connection(lbl_target):
    load_dotenv(get_script_path(".env"), override=True)
    try:
        client_id = str(os.getenv("DHAN_CLIENT_ID"))
        access_token = str(os.getenv("DHAN_ACCESS_TOKEN"))
        
        print(f"DEBUG: Connecting with ID: {client_id}...")
        
        dhan = dhanhq(client_id, access_token)
        resp = dhan.get_fund_limits()
        
        print(f"DEBUG: Dhan Response: {resp}")
        
        if resp['status'] == 'success':
            lbl_target.config(text="● SYSTEM ONLINE", fg=COLORS["primary"])
            # Save Balance for Strategic Briefing
            try:
                avail_cash = resp['data'].get('availabelBalance', resp['data'].get('withdrawableBalance', 0))
                with open("account_info.json", "w") as f:
                    import json
                    json.dump({"AvailableCash": avail_cash}, f)
                print(f"DEBUG: Saved Available Cash: {avail_cash}")
            except Exception as e:
                print(f"DEBUG: Failed to save account info: {e}")
        else:
            lbl_target.config(text="● TOKEN EXPIRED", fg=COLORS["danger"])
    except Exception as e:
        print(f"DEBUG: Connection Exception: {e}")
        lbl_target.config(text="● CONNECTION FAILED", fg=COLORS["danger"])

def launch_script(script_name, arg=None, is_streamlit=False):
    full_path = get_script_path(script_name)
    base_folder = get_base_folder()

    if not os.path.exists(full_path):
        messagebox.showerror("Error", f"File not found:\n{full_path}")
        return

    try:
        if is_streamlit:
            # Run using python -m streamlit run to ensure venv usage
            cmd_str = f'"{sys.executable}" -m streamlit run "{script_name}"'
            # Streamlit needs args passed differently if needed, but usually none for this app
            if arg:
                cmd_str += f" -- {arg}"
        else:
            cmd_str = f'"{sys.executable}" "{script_name}"'
            if arg:
                cmd_str += f" {arg}"

        # /k for streamlit (Keep open), /c for others (Close after completion if input() exists)
        # Actually /c is fine for streamlit too because the server keeps running? 
        # No, streamlit run blocks. But if we use /c, closing the browser/server might happen?
        # Let's use /k for streamlit so the user sees the server URL/logs.
        
        # /k for streamlit (Keep open), /c for others (Close after completion if input() exists)
        # For troubleshooting Strike Automation, we keep it open too
        keep_open_scripts = ["strike_automation.py"]
        
        mode = "/k" if is_streamlit or script_name in keep_open_scripts else "/c"
        
        cmd = f'start cmd {mode} "cd /d "{base_folder}" && {cmd_str}"'
        os.system(cmd)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch: {e}")

# ==========================================
# 3. CUSTOM WIDGETS
# ==========================================
class ModernButton(tk.Button):
    def __init__(self, master, text, command, style="default"):
        self.style_type = style
        self.is_active = False
        
        # Colors
        self.col_default = COLORS["btn_default"]
        self.col_hover = COLORS["btn_hover"]
        self.col_active = COLORS["primary"]
        self.text_default = COLORS["text"]
        self.text_active = "#000000" # Black text on active
        
        # Initial State
        bg = self.col_default
        fg = self.text_default
        
        if style == "primary":
            bg = self.col_active
            fg = self.text_active

        super().__init__(master, text=text, command=self.on_click if style == "nav" else command,
                         font=FONTS["body"], bg=bg, fg=fg,
                         activebackground=self.col_hover, activeforeground=fg,
                         relief="flat", bd=0, cursor="hand2",
                         highlightthickness=0,
                         pady=12)

        self.user_command = command
        
        # Hover Effects
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    def on_enter(self, e):
        if not self.is_active:
            self['background'] = self.col_hover

    def on_leave(self, e):
        if not self.is_active:
            if self.style_type == "primary":
                self['background'] = self.col_active
            else:
                self['background'] = self.col_default

    def on_click(self):
        if self.user_command:
            self.user_command()

    def set_active(self, active=True):
        self.is_active = active
        if active:
            self.configure(bg=self.col_active, fg=self.text_active)
        else:
            self.configure(bg=self.col_default, fg=self.text_default)

# ==========================================
# 4. MAIN GUI
# ==========================================
root = tk.Tk()
root.title("Weinstein Commander PRO")
root.geometry("520x900")
root.configure(bg=COLORS["bg"])
root.resizable(True, True)

# --- HEADER ---
header_frame = tk.Frame(root, bg=COLORS["bg"])
header_frame.pack(pady=20, fill="x")

lbl_title = tk.Label(header_frame, text="WEINSTEIN COMMANDER", font=FONTS["h1"], bg=COLORS["bg"], fg=COLORS["text"])
lbl_title.pack()

lbl_status = tk.Label(header_frame, text="● INITIALIZING...", font=FONTS["small"], bg=COLORS["bg"], fg=COLORS["text_dim"])
lbl_status.pack(pady=5)

# --- NAVIGATION CONTROLLER ---
current_page = None
nav_buttons = []

def show_page(page_frame, btn_ref):
    global current_page
    
    # Hide old page
    if current_page:
        current_page.pack_forget()
    
    # Show new page
    page_frame.pack(fill="both", expand=True, padx=25, pady=10)
    current_page = page_frame
    
    # Update Buttons
    for btn in nav_buttons:
        btn.set_active(False)
    btn_ref.set_active(True)

# --- NAV BAR ---
nav_frame = tk.Frame(root, bg=COLORS["bg"])
nav_frame.pack(fill="x", padx=25, pady=10)

# Grid layout for Nav Buttons to ensure sticky size
nav_frame.columnconfigure(0, weight=1)
nav_frame.columnconfigure(1, weight=1)
nav_frame.columnconfigure(2, weight=1)
nav_frame.columnconfigure(3, weight=1)

# --- CONTENT FRAMES ---
# --- CONTENT FRAMES ---
content_container = tk.Frame(root, bg=COLORS["bg"])
content_container.pack(fill="both", expand=True)

# ==========================================
# TAB 1: DASHBOARD (Overview & High-Level Checks)
# ==========================================
frame_dashboard = tk.Frame(content_container, bg=COLORS["panel"])

# Section: Market Pulse
tk.Label(frame_dashboard, text="MARKET PULSE", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 10))

ModernButton(frame_dashboard, "�  Strategic Briefing (Daily Report)", 
             lambda: launch_script("workflow_strategic_briefing.py"), style="primary").pack(fill="x", padx=40, pady=8)

ModernButton(frame_dashboard, "�  Sector Radar (RRG Analysis)", 
             lambda: launch_script("sector_radar.py")).pack(fill="x", padx=40, pady=8)

# Section: System Health
tk.Label(frame_dashboard, text="SYSTEM STATUS", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 10))

ModernButton(frame_dashboard, "🏥  Portfolio Health Check", 
             lambda: launch_script("portfolio_audit.py")).pack(fill="x", padx=40, pady=8)

ModernButton(frame_dashboard, "�  Check System Connections", 
             lambda: check_connection(lbl_status), style="secondary").pack(fill="x", padx=40, pady=8)


# ==========================================
# TAB 2: HUNTER (Scanning & Discovery)
# ==========================================
frame_hunter = tk.Frame(content_container, bg=COLORS["panel"])

# Section: Chartink Scanners
tk.Label(frame_hunter, text="1. SCANNING (Chartink)", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 10))

ModernButton(frame_hunter, "🚀  Stage 2 Hunter (Positional)", 
             lambda: launch_script("chartink_scanner_pro.py", "1")).pack(fill="x", padx=40, pady=5)

ModernButton(frame_hunter, "📉  Stage 2 Pullback (Swing)", 
             lambda: launch_script("chartink_scanner_pro.py", "2")).pack(fill="x", padx=40, pady=5)

ModernButton(frame_hunter, "🐣  Early Birds (Accumulation)", 
             lambda: launch_script("chartink_scanner_pro.py", "3")).pack(fill="x", padx=40, pady=5)

ModernButton(frame_hunter, "⚡  Strong Leaders (Momentum)", 
             lambda: launch_script("chartink_scanner_pro.py", "4")).pack(fill="x", padx=40, pady=5)

# Section: Fundamental Data
tk.Label(frame_hunter, text="2. DATA ENRICHMENT", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(20, 10))

ModernButton(frame_hunter, "⬇️  Fetch Fundamentals (Screener.in)", 
             lambda: launch_script("screener_fetcher.py")).pack(fill="x", padx=40, pady=5)

ModernButton(frame_hunter, "⚙️  Process HTML to CSV", 
             lambda: launch_script("screener_processor.py")).pack(fill="x", padx=40, pady=5)

# Section: Matching
tk.Label(frame_hunter, text="⬇", font=("Arial", 14), bg=COLORS["panel"], fg=COLORS["text_dim"]).pack(pady=5)

ModernButton(frame_hunter, "✨  RUN GOLDEN MATCHER  ✨", 
             lambda: launch_script("brute_force_match_pro.py"), style="primary").pack(fill="x", padx=40, pady=8)


# ==========================================
# TAB 3: WATCHLIST (Sync & Distribution)
# ==========================================
frame_watchlist = tk.Frame(content_container, bg=COLORS["panel"])
tk.Label(frame_watchlist, text="CROSS-PLATFORM SYNC", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 15))

# Step 1: Local Generation
ModernButton(frame_watchlist, "1. GENERATE WATCHLISTS (Local CSVs)", 
             lambda: watchlist_manager.generate_tradingview_files(), style="secondary").pack(fill="x", padx=40, pady=10)

# Step 2: External Sync
tk.Label(frame_watchlist, text="EXTERNAL PLATFORMS", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(20, 10))

ModernButton(frame_watchlist, "2. SYNC TO STRIKE.MONEY", 
             lambda: launch_script("strike_automation.py", "--mode=watchlist"), style="secondary").pack(fill="x", padx=40, pady=8)

ModernButton(frame_watchlist, "3. SYNC TO TRADINGVIEW", 
             lambda: launch_script("tradingview_automation_v2.py"), style="primary").pack(fill="x", padx=40, pady=8)

ModernButton(frame_watchlist, "4. MASTER SYNC (All-in-One)", 
             lambda: launch_script("master_portfolio_sync.py"), style="primary").pack(fill="x", padx=40, pady=8)


# ==========================================
# TAB 4: COMMAND (Execution & Ops)
# ==========================================
frame_command = tk.Frame(content_container, bg=COLORS["panel"])

# Section: Active Trading
tk.Label(frame_command, text="ACTIVE EXECUTION", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 10))

ModernButton(frame_command, "🎯  Sniper Entry (Automated)", 
             lambda: launch_script("sniper_trigger.py"), style="primary").pack(fill="x", padx=40, pady=8)

ModernButton(frame_command, "🖌️  Visual Trade Manager", 
             lambda: launch_script("visual_manager.py")).pack(fill="x", padx=40, pady=8)

# Section: Protection & Bots
tk.Label(frame_command, text="DEFENSE & BOTS", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(20, 10))

ModernButton(frame_command, "📱  Start Sentinel Bot (Telegram)", 
             lambda: launch_script("telegram_sentinel.py")).pack(fill="x", padx=40, pady=8)

ModernButton(frame_command, "🛡️  Sentinel (GTT Protect)", 
             lambda: launch_script("gtt_portfolio_v2.py")).pack(fill="x", padx=40, pady=8)

# Section: Records
tk.Label(frame_command, text="RECORDS", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(20, 10))

ModernButton(frame_command, "📔  Trade Journal (DB)", 
             lambda: launch_script("dhan_journal_v6.py", is_streamlit=True)).pack(fill="x", padx=40, pady=8)

ModernButton(frame_command, "⚡  Master Sync (Dhan + TV + Pine)", 
             lambda: launch_script("master_portfolio_sync.py"), style="secondary").pack(fill="x", padx=40, pady=8)


# ==========================================
# TAB 5: AI LAB (Advanced Automation)
# ==========================================
frame_ai = tk.Frame(content_container, bg=COLORS["panel"])

tk.Label(frame_ai, text="GENERATIVE AI TOOLS", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(25, 15))

ModernButton(frame_ai, "🤖  Generate Gemini Web Prompt", 
             lambda: launch_script("generate_prompt_standalone.py"), style="primary").pack(fill="x", padx=40, pady=8)

tk.Label(frame_ai, text="FULL WORKFLOW AUTOMATION", font=FONTS["h2"], bg=COLORS["panel"], fg=COLORS["text"]).pack(pady=(30, 15))

ModernButton(frame_ai, "⚡  RUN AUTO-PILOT (End-to-End)", 
             lambda: launch_script("run_pipeline.py"), style="danger").pack(fill="x", padx=40, pady=20)

tk.Label(frame_ai, text="Runs Scanners -> Matcher -> Sync -> Watchlists", font=FONTS["small"], bg=COLORS["panel"], fg=COLORS["text_dim"]).pack()


# --- INITIALIZE NAV BUTTONS ---
# Columns: 0, 1, 2, 3, 4
for i in range(5):
    nav_frame.columnconfigure(i, weight=1)

btn_nav_dash = ModernButton(nav_frame, "DASHBOARD", lambda: show_page(frame_dashboard, btn_nav_dash), style="nav")
btn_nav_dash.grid(row=0, column=0, sticky="ew", padx=2)

btn_nav_hunter = ModernButton(nav_frame, "HUNTER", lambda: show_page(frame_hunter, btn_nav_hunter), style="nav")
btn_nav_hunter.grid(row=0, column=1, sticky="ew", padx=2)

btn_nav_watch = ModernButton(nav_frame, "WATCHLIST", lambda: show_page(frame_watchlist, btn_nav_watch), style="nav")
btn_nav_watch.grid(row=0, column=2, sticky="ew", padx=2)

btn_nav_cmd = ModernButton(nav_frame, "COMMAND", lambda: show_page(frame_command, btn_nav_cmd), style="nav")
btn_nav_cmd.grid(row=0, column=3, sticky="ew", padx=2)

btn_nav_ai = ModernButton(nav_frame, "AI LAB", lambda: show_page(frame_ai, btn_nav_ai), style="nav")
btn_nav_ai.grid(row=0, column=4, sticky="ew", padx=2)

nav_buttons = [btn_nav_dash, btn_nav_hunter, btn_nav_watch, btn_nav_cmd, btn_nav_ai]

# Start on Tab 1
show_page(frame_dashboard, btn_nav_dash)

# --- FOOTER ---


# --- FOOTER ---
lbl_footer = tk.Label(root, text="v10.0 PRO | Powered by Gemini 3", font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["text_dim"])
lbl_footer.pack(side="bottom", pady=15)

root.after(100, lambda: check_connection(lbl_status))
root.mainloop()
