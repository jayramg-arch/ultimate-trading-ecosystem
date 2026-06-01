import requests
import time
from bs4 import BeautifulSoup
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

def test_logic(clause):
    time.sleep(0.4)
    l = f"( {{57960}} ( {clause} ) )"
    p = {'scan_clause': l, '_token': csrf}
    rp = session.post('https://chartink.com/screener/process', data=p)
    try:
        print(f"{len(rp.json().get('data',[])):<4} | {clause}")
    except:
        print(f"ERR  | {clause}")

test_logic("1 week ago weekly macd signal( 26 , 12 , 9 ) < 0")
test_logic("1 week ago macd signal( 26 , 12 , 9 ) < 0")
test_logic("weekly macd line( 26 , 12 , 9 ) > weekly macd signal( 26 , 12 , 9 )")
