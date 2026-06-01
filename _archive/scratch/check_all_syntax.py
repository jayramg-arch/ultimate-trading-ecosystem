import ast, pathlib, sys

FILES = [
    'news_feed.py',
    'news_fetcher.py',
    'breadth_engine.py',
    'dhan_journal_v7.py',
]
BASE = pathlib.Path(r'C:\Users\jayra\Documents\GeminiVSCode')
ok = True
for f in FILES:
    try:
        ast.parse((BASE / f).read_text(encoding='utf-8'))
        print(f'OK  {f}')
    except SyntaxError as e:
        print(f'ERR {f}: {e}')
        ok = False
sys.exit(0 if ok else 1)
