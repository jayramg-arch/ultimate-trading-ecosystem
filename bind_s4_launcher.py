"""Pinnable launcher for the S4 source binder.

Exists because a shortcut whose target is cmd.exe is awkward to pin on Windows 11
(the option hides under "Show more options" and is sometimes refused outright), while
a shortcut to python.exe pins like any application. Same output and same exit codes as
BIND_S4_SOURCES.bat, which stays as the terminal entry point.

Run it after EVERY S4 compile: TradingView drops every input.source binding on every
recompile, and an unbound source silently reads `close` rather than erroring.
"""
import os
import subprocess
import sys

PROJ = r"C:\Users\jayra\Documents\GeminiVSCode"
PY = r"C:\Users\jayra\TradingData\venv\Scripts\python.exe"
BAR = "=" * 62


def hold(code=1):
    print()
    try:
        input("Press Enter to close...")
    except EOFError:
        pass
    sys.exit(code)


def main():
    print(BAR)
    print("  BIND S4 SOURCES")
    print(BAR)
    if not os.path.isdir(PROJ):
        print(f"[X] Project folder not found: {PROJ}")
        hold()
    os.chdir(PROJ)
    if not os.path.exists("tv_bind_s4.py"):
        print(f"[X] tv_bind_s4.py not found in {PROJ}")
        hold()
    if not os.path.exists(PY):
        print(f"[X] Python not found at {PY}")
        hold()

    print("\n---- BEFORE ----")
    subprocess.run([PY, "tv_bind_s4.py", "--check"])
    print("\n---- BINDING ----")
    rc = subprocess.run([PY, "tv_bind_s4.py"]).returncode
    print()
    if rc == 0:
        print("  [OK] All sources bound.")
    elif rc == 2:
        print("  [X] Could not reach TradingView.")
        print("      Start it with LAUNCH_TRADINGVIEW_CDP.bat, open a chart, then re-run.")
    else:
        print("  [!] Finished with problems - read the report above.")
        print('      "MISSING PLOT" means the v67 Dashboard or the Swing Zigzag is not on')
        print("      this chart, or a plot was renamed. Both must be loaded: S4 reads THEIR")
        print("      plots, so it cannot bind to something that is not there.")
    hold(rc)


if __name__ == "__main__":
    main()
