import requests
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
from bs4 import BeautifulSoup
csrf = BeautifulSoup(r.text, 'html.parser').select_one('meta[name="csrf-token"]')['content']

def test(logic):
    p = {'scan_clause': f'( {{57960}} ( {logic} ) )', '_token': csrf}
    rp = session.post('https://chartink.com/screener/process', data=p)
    try: print(f"{len(rp.json().get('data',[])):<4} | {logic}")
    except: print(f"ERR  | {logic}")

test('daily close / [0] Nifty 50 close > 0')
test('daily close / [0] Nifty 500 close > 0')
test('daily close / [0] 57960 close > 0')

test('weekly close / [0] Nifty 50 close > 0')
test('weekly close / [0] Nifty 500 close > 0')
