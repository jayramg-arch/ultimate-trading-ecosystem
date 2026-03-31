import os
import subprocess

def kill_chrome():
    print("Force killing Chrome processes...")
    try:
        if os.name == 'nt': # Windows
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "chrome"], stderr=subprocess.DEVNULL)
        print("Chrome processes killed.")
    except Exception as e:
        print(f"Error killing chrome: {e}")

if __name__ == "__main__":
    kill_chrome()
