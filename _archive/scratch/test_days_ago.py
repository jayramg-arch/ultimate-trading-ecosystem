import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'X-Requested-With': 'XMLHttpRequest'
})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

def test(logic):
    p = {'scan_clause': f'( {{57960}} ( {logic} ) )', '_token': csrf}
    rp = session.post('https://chartink.com/screener/process', data=p)
    try:
        print(f"{len(rp.json().get('data',[])):<4} | {logic}")
    except:
        print(f"ERR  | {logic}")

test('daily close > 3 days ago close')
test('daily close > 3 days ago daily close')
test('daily close > 1 days ago close')
test('daily close > 1 days ago daily close')
test('daily close > 5 days ago daily close')
