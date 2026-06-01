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
test_logic(f"daily close > daily sma( daily close , 200 )")
test_logic(f"daily close > daily ema( daily close , 20 ) * 0.98")
test_logic(f"daily close < daily ema( daily close , 20 ) * 1.05")
test_logic(f"weekly rsi( 14 ) > 60")
test_logic(f"daily volume < daily sma( daily volume , 50 ) * 0.75")
test_logic(f"daily high - daily low < 1 day ago high - 1 day ago low")

