import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0',
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

# Test multiple index relative strength syntaxes
test('daily close > 20 and weekly close / [0] 57960 close > 0')
test('daily close > 20 and weekly close / [0] 57960 weekly close > 0')
test('daily close > 20 and weekly close / 57960 close > 0')
test('daily close > 20 and weekly close / 57960 weekly close > 0')

# Also check other "ago daily" syntax from the scanners
test('daily close > 1 day ago max( 20 , high )')
test('daily close > 1 day ago max( 20 , daily high )')
test('daily sma( daily close , 30 ) >= 5 days ago sma( daily close , 30 )')
test('daily sma( daily close , 50 ) >= 5 days ago sma( daily close , 50 )')
test('daily high - daily low < 1 day ago high - 1 day ago low')
test('daily high - daily low < 1 day ago daily high - 1 day ago daily low')

