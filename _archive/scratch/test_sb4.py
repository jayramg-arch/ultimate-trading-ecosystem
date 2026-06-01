import requests
import json
from bs4 import BeautifulSoup
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0', 'X-Requested-With': 'XMLHttpRequest'})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

logic = """
( {57960} (
    daily rsi( 14 ) > 60
    and daily close > daily sma( daily close , 20 )
    and daily adx( 14 ) > 25
    and daily volume > daily sma( daily volume , 20 )
    and daily close > daily sma( daily close , 200 )
    and daily close > 20
) )
"""

p = {'scan_clause': logic.replace('\n', ' '), '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=p)
try:
    print('Strong Leaders new logic:', len(rp.json().get('data',[])))
except Exception as e:
    print('ERR:', e, rp.text[:200])
