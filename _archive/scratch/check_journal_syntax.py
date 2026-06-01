import ast, pathlib
src = pathlib.Path(r'C:\Users\jayra\Documents\GeminiVSCode\dhan_journal_v7.py').read_text(encoding='utf-8')
try:
    ast.parse(src)
    print('dhan_journal_v7.py OK')
except SyntaxError as e:
    print(f'SyntaxError: {e}')
