import ast
for f in [
    r'C:\Users\jayra\Documents\GeminiVSCode\weinstein_commander_web_v4.0.py',
    r'C:\Users\jayra\Documents\GeminiVSCode\gemini_reporter.py',
]:
    with open(f, encoding='utf-8') as fh:
        src = fh.read()
    try:
        ast.parse(src)
        print(f"OK  {f.split(chr(92))[-1]}  ({len(src)} chars)")
    except SyntaxError as e:
        print(f"ERR {f.split(chr(92))[-1]}  line {e.lineno}: {e.msg}")
