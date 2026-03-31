import os
import sys
import subprocess
from PIL import Image

def create_icon(source_png, target_ico):
    """Converts PNG to ICO with multiple sizes."""
    if not os.path.exists(source_png):
        print(f"❌ Source image not found: {source_png}")
        return False
    
    try:
        img = Image.open(source_png)
        # Ensure it's square for a professional icon
        w, h = img.size
        size = min(w, h)
        left = (w - size)/2
        top = (h - size)/2
        img = img.crop((left, top, left + size, top + size))
        
        icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(target_ico, sizes=icon_sizes)
        print(f"✅ Icon created: {target_ico}")
        return True
    except Exception as e:
        print(f"❌ Icon creation failed: {e}")
        return False

def create_shortcut(target_path, shortcut_path, icon_path):
    """Creates a Windows shortcut using PowerShell."""
    try:
        ps_command = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target_path}"
        $Shortcut.WorkingDirectory = "{os.path.dirname(target_path)}"
        $Shortcut.IconLocation = "{icon_path}"
        $Shortcut.Description = "Weinstein Commander - Institutional Trading Terminal"
        $Shortcut.Save()
        """
        subprocess.run(["powershell", "-Command", ps_command], check=True)
        print(f"✅ Shortcut created: {shortcut_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to create shortcut: {e}")
        return False

def get_desktop_path():
    """Finds the correct Desktop path, handling OneDrive or system redirections."""
    try:
        ps_command = "[Environment]::GetFolderPath('Desktop')"
        result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, check=True)
        path = result.stdout.strip()
        if path: return path
    except:
        pass
    # Fallback to standard path
    return os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')

if __name__ == "__main__":
    # 1. Setup Paths
    root_dir = os.path.dirname(os.path.abspath(__file__))
    source_img = os.path.join(root_dir, "commander_lion.png")
    target_ico = os.path.join(root_dir, "commander_final_v1.ico")
    launcher_bat = os.path.join(root_dir, "LAUNCH_COMMANDER.bat")
    
    desktop = get_desktop_path()
    shortcut_path = os.path.join(desktop, "Weinstein Commander.lnk")
    
    # 2. Process Icon
    if os.path.exists(source_img):
        create_icon(source_img, target_ico)
    else:
        print("⚠️  Warning: Logo source not found. Using default icon.")
        target_ico = "" # Windows will use default .bat icon
        
    # 3. Create Shortcut
    create_shortcut(launcher_bat, shortcut_path, target_ico)
    
    print("\n🏁 COMMANDER SETUP COMPLETE!")
    print(f"👉 Look for 'Weinstein Commander' on your Desktop.")
