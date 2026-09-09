import re, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('weinstein_commander_web_v4.0.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("--- CSS BLOCK SEARCH ---")
for m in re.finditer(r'<style>', text):
    ln = text[:m.start()].count('\n') + 1
    print(f"L{ln}: <style> block starts")

print("\n--- RADIO CALLS ---")
for m in re.finditer(r'st\.radio\(', text):
    ln = text[:m.start()].count('\n') + 1
    print(f"L{ln}: {text[m.start():m.start()+90]}")
