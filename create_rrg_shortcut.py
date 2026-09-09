"""
create_rrg_shortcut.py — Generates a Taskbar-pinnable Windows Shortcut (.lnk) for RRG Studio
Target points to cmd.exe with arguments so Windows permits "Pin to taskbar".
"""
import os
import sys

def create_shortcuts():
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except ImportError:
        # Fallback to pure powershell script
        os.system("powershell -ExecutionPolicy Bypass -File create_rrg_shortcut.ps1")
        return

    workspace = os.path.abspath(os.path.dirname(__file__))
    desktop = shell.SpecialFolders("Desktop")
    bat_path = os.path.join(workspace, "START_RRG_STUDIO.bat")
    icon_path = os.path.join(workspace, "commander_logo.ico")
    cmd_exe = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "cmd.exe")

    targets = [
        os.path.join(desktop, "RRG Studio.lnk"),
        os.path.join(workspace, "RRG Studio.lnk")
    ]

    for sc_path in targets:
        try:
            shortcut = shell.CreateShortcut(sc_path)
            shortcut.TargetPath = cmd_exe
            shortcut.Arguments = f'/c ""{bat_path}""'
            shortcut.WorkingDirectory = workspace
            shortcut.Description = "RRG Studio — Sector Rotation Cockpit"
            if os.path.exists(icon_path):
                shortcut.IconLocation = f"{icon_path},0"
            shortcut.Save()
            print(f"[SUCCESS] Created Taskbar-Pinnable Shortcut: {sc_path}")
        except Exception as exc:
            print(f"[ERROR] Failed creating {sc_path}: {exc}")

if __name__ == "__main__":
    create_shortcuts()
