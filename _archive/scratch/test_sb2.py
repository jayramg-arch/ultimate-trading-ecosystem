import requests
from bs4 import BeautifulSoup
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

logic = """
( {57960} (
    weekly close > weekly sma( weekly close , 30 )
    and weekly rsi( 14 ) > 55
    and daily low < daily ema( daily close , 20 ) * 1.015
    and daily close > daily ema( daily close , 20 )
    and daily volume < daily sma( daily volume , 10 )
    and daily close > daily sma( daily close , 200 )
    and daily high - daily low < 1 day ago high - 1 day ago low
    and daily close > 20
) )
"""

p = {'scan_clause': logic.replace('\n', ' '), '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=p)
try:
    print('Stage 2 Pullback new logic:', len(rp.json().get('data',[])))
except Exception as e:
    print('ERR:', e)
