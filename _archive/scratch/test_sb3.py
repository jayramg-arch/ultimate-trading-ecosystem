import requests
from bs4 import BeautifulSoup
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

logic = """
( {57960} (
    weekly rsi( 14 ) > 50
    and daily close > daily sma( daily close , 50 )
    and daily close < daily sma( daily close , 50 ) * 1.15
    and daily volume > 100000
    and weekly macd line( 26 , 12 , 9 ) > weekly macd signal( 26 , 12 , 9 )
    and 1 week ago macd signal( 26 , 12 , 9 ) < 0
    and daily close > 1 day ago max( 20 , high )
    and daily close > 20
) )
"""

p = {'scan_clause': logic.replace('\n', ' '), '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=p)
try:
    print('Stage 3 Early Birds:', len(rp.json().get('data',[])))
except Exception as e:
    print('ERR:', e, rp.text[:200])
