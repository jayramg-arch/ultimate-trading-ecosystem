import requests
from bs4 import BeautifulSoup
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

def test_logic(clause):
    import time
    time.sleep(0.4)
    l = f"( {{57960}} ( {clause} ) )"
    p = {'scan_clause': l, '_token': csrf}
    r = session.post('https://chartink.com/screener/process', data=p)
    try:
        print(f"{len(r.json().get('data',[])):<4} | {clause}")
    except:
        print(f"ERR  | {clause}")

base = "daily close > 20"
test_logic(base)
test_logic(f"{base} and daily close > daily sma( daily close , 50 )")
test_logic(f"{base} and daily close < daily sma( daily close , 50 ) * 1.15")
test_logic(f"{base} and daily sma( daily close , 30 ) >= 5 days ago sma( daily close , 30 )")
test_logic(f"{base} and daily volume < daily sma( daily volume , 50 ) * 0.8")
test_logic(f"{base} and daily close > 1 day ago max( 20 , high )")
test_logic(f"{base} and weekly volume > weekly sma( weekly volume , 10 ) * 1.5")
