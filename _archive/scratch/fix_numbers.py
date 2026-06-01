import re
import os

path = r"E:\Gemini\VS Code\Weinstein and Swing Pro Dashboard v63.3.pine"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "drawRow" in line and '"' in line:
        line = re.sub(r'((?:drawRowL|drawRowR)\(panel,\s*row[LR],\s*")\d+\.\s+', r'\1', line)
    new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Updated v63.3 dashboard field names successfully.")
