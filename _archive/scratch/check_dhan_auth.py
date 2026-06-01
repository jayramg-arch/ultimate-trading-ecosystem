import ast
with open(r'C:\Users\jayra\Documents\GeminiVSCode\dhan_auth.py', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print(f"Syntax OK — {len(src)} chars, {src.count(chr(10))+1} lines")
except SyntaxError as e:
    print(f"SYNTAX ERROR at line {e.lineno}: {e.msg}")
    print(f"  Text: {e.text}")
