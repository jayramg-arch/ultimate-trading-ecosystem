import os
import subprocess

def kill_automation_chrome():
    print("Finding and killing orphaned automated Chrome processes...")
    if os.name != 'nt':
        keywords = ["strike_user_data", "tv_user_data_v2", "browser_data", "screener_session", "dhan_session"]
        for kw in keywords:
            try:
                subprocess.run(["pkill", "-f", kw], stderr=subprocess.DEVNULL)
            except:
                pass
        return

    keywords = ["strike_user_data", "tv_user_data_v2", "browser_data", "screener_session", "dhan_session"]
    conditions = " -or ".join([f'$_.CommandLine -like "*{kw}*"' for kw in keywords])
    cmd = f'Get-CimInstance Win32_Process -Filter "Name = \'chrome.exe\'" | Where-Object {{ {conditions} }} | Select-Object -ExpandProperty ProcessId'
    
    try:
        res = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, check=True)
        pids = [line.strip() for line in res.stdout.split('\n') if line.strip().isdigit()]
        if pids:
            print(f"   Killing {len(pids)} automated Chrome processes: {pids}")
            for pid in pids:
                subprocess.run(["taskkill", "/F", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("   Orphaned automated Chrome processes terminated.")
        else:
            print("   No orphaned automated Chrome processes found.")
    except Exception as e:
        print(f"   Error during targeted Chrome cleanup: {e}")

def kill_chrome():
    print("Force killing all Chrome and Chromedriver processes...")
    try:
        if os.name == 'nt': # Windows
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "chrome"], stderr=subprocess.DEVNULL)
        print("All Chrome processes killed.")
    except Exception as e:
        print(f"Error killing chrome: {e}")

if __name__ == "__main__":
    import sys
    if "--all" in sys.argv:
        kill_chrome()
    else:
        kill_automation_chrome()
