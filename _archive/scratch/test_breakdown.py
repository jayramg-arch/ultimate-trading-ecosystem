import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

logic = "( {57960} ( daily close < daily sma( daily close , 50 ) * 1.10 and daily close > daily sma( daily close , 200 ) * 0.85 and weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 ) and daily rsi( 14 ) > 40 and daily volume > daily sma( daily volume , 20 ) * 1.5 and daily close > 5 days ago daily close and daily close > 20 ) )"

payload = {'scan_clause': logic, '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=payload)
data = rp.json()
print('Full Scanner 6:', len(data.get('data', [])))

# Let's break it down progressively to see where it drops to 0
def test_logic(clause):
    import time
    time.sleep(0.5)
    l = f"( {{57960}} ( {clause} ) )"
    p = {'scan_clause': l, '_token': csrf}
    r = session.post('https://chartink.com/screener/process', data=p)
    print(f"Count: {len(r.json().get('data',[])):<4} | Logic: {clause}")

test_logic("daily close > 20")
test_logic("daily close > 20 and daily close < daily sma( daily close , 50 ) * 1.10")
test_logic("daily close > 20 and daily close > daily sma( daily close , 200 ) * 0.85")
test_logic("daily close > 20 and weekly sma( weekly close , 30 ) > 4 weeks ago sma( weekly close , 30 )")
test_logic("daily close > 20 and daily rsi( 14 ) > 40")
test_logic("daily close > 20 and daily volume > daily sma( daily volume , 20 ) * 1.5")
test_logic("daily close > 20 and daily close > 5 days ago daily close")

