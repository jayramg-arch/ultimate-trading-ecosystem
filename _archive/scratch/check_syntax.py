import ast
files = [
    'portfolio_analytics.py',
    'broker_options.py',
    'dhan_auth.py',
    'weinstein_commander_web_v4.0.py',
]
for f in files:
    path = rf'C:\Users\jayra\Documents\GeminiVSCode\{f}'
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    try:
        ast.parse(src)
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'ERR {f}  line {e.lineno}: {e.msg}  → {(e.text or "").strip()}')
