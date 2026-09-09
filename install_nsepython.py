import subprocess, sys
r = subprocess.run([sys.executable, "-m", "pip", "install", "nsepython", "--quiet"],
                   capture_output=True, text=True)
print(r.stdout or r.stderr or "Done")
try:
    import nsepython
    print("nsepython import OK")
except Exception as e:
    print(f"Import failed: {e}")
