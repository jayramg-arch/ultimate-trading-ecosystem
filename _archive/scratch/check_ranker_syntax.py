import ast, pathlib
src = pathlib.Path(r'C:\Users\jayra\Documents\GeminiVSCode\watchlist_ranker.py').read_text(encoding='utf-8')
try:
    ast.parse(src)
    print('watchlist_ranker.py OK')
except SyntaxError as e:
    print(f'SyntaxError: {e}')
