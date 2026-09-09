"""set_commander_icon.py — Switch or re-apply the Web Commander icon.

Usage:
    python set_commander_icon.py [1|2|3|4]

Options:
    1: Concept 1 — Full App Badge with Subtitle (Badge Edition)
    2: Concept 2 — Pure Cybernetic Lion Profile (Recommended / Default)
    3: Concept 3 — Symmetrical Front-Facing Crest (Shield Edition)
    4: Concept 4 — Geometric Low-Poly Tech Lion (Facet Edition)
"""

import sys
import os
import shutil
import subprocess

CONCEPTS = {
    "1": ("commander_concept_1_badge", "Concept 1 — Full App Badge with Subtitle"),
    "2": ("commander_concept_2_profile", "Concept 2 — Pure Cybernetic Lion Profile (Recommended)"),
    "3": ("commander_concept_3_front_crest", "Concept 3 — Symmetrical Front-Facing Crest"),
    "4": ("commander_concept_4_geometric", "Concept 4 — Geometric Low-Poly Tech Lion"),
}

def set_icon(choice="2"):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(root_dir, "assets", "icons")

    if choice not in CONCEPTS:
        print(f"Unknown choice '{choice}'. Valid choices: 1, 2, 3, 4")
        return False

    stem, desc = CONCEPTS[choice]
    src_png = os.path.join(icons_dir, f"{stem}.png")
    src_ico = os.path.join(icons_dir, f"{stem}.ico")

    if not os.path.exists(src_png) or not os.path.exists(src_ico):
        print(f"Source icon files missing for {desc}")
        return False

    dst_png = os.path.join(root_dir, "commander_web_icon.png")
    dst_ico = os.path.join(root_dir, "commander_web_icon.ico")

    shutil.copy2(src_png, dst_png)
    shutil.copy2(src_ico, dst_ico)
    print(f"Active icon updated to: {desc}")
    print(f"  -> {dst_png}")
    print(f"  -> {dst_ico}")

    # Update Desktop shortcuts
    ps_cmd = f"""
    $sh = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $ico = "{dst_ico}"
    Get-ChildItem -Path $desktop -Filter *Commander*.lnk -ErrorAction SilentlyContinue | ForEach-Object {{
        if ($_.Name -notmatch "Stop") {{
            $lnk = $sh.CreateShortcut($_.FullName)
            $lnk.IconLocation = "$ico,0"
            $lnk.Save()
            Write-Host "  Updated shortcut: $($_.Name)"
        }}
    }}
    """
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    except Exception as e:
        print(f"Notice: Could not refresh desktop shortcuts: {e}")

    print("\nIcon setup complete! Restart Web Commander to see the refreshed tab favicon.")
    return True

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else "2"
    set_icon(choice)
