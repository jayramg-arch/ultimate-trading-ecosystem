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

logic = """
( {57960} (
    daily close > daily sma( daily close , 50 )
    and daily close < daily sma( daily close , 50 ) * 1.15
    and daily sma( daily close , 30 ) >= 5 days ago sma( daily close , 30 )
    and daily close > 1 day ago max( 20 , daily high )
    and weekly volume > weekly sma( weekly volume , 10 ) * 1.5
    and daily close > 20
) )
"""
p = {'scan_clause': logic.replace('\n', ' '), '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=p)
try:
    print('Scanner 7 (No VDU):', len(rp.json().get('data',[])))
except Exception as e:
    print(e)
