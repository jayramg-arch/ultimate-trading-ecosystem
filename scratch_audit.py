import re
import collections

with open(r'c:\Users\jayra\Documents\GeminiVSCode\Section4_Entry_Trigger_v5.9.pine', encoding='utf-8') as f:
    pine_code = f.read()

# Extract bull patterns from python
bull_pats_py = []
recovery_pats_py = []
try:
    with open(r'c:\Users\jayra\Documents\GeminiVSCode\pa_patterns.py', encoding='utf-8') as f:
        py_code = f.read()
        bull_section = py_code.split('def detect_bull_patterns')[1].split('def detect_recovery_patterns')[0]
        bull_pats_py = re.findall(r'pats\.append\(\("(.*?)",', bull_section)
        
        recovery_section = py_code.split('def detect_recovery_patterns')[1]
        recovery_pats_py = re.findall(r'pats\.append\(\("(.*?)",', recovery_section)
except Exception as e:
    pass

# Output to file
with open(r'c:\Users\jayra\Documents\GeminiVSCode\scratch_audit_out.txt', 'w', encoding='utf-8') as out:
    out.write("--- PYTHON BULL PATTERNS ---\n")
    out.write(str(bull_pats_py) + "\n\n")
    out.write("--- PYTHON RECOVERY PATTERNS ---\n")
    out.write(str(recovery_pats_py) + "\n\n")

    out.write("--- PINE SCRIPT OVERVIEW ---\n")
    out.write(f"Total lines: {len(pine_code.splitlines())}\n")
    zones = re.findall(r'f_detectZone.*?\{', pine_code, flags=re.DOTALL)
    out.write(f"\nFound f_detectZone: {len(zones)} times\n")
