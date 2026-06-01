import chartink_scanner_pro
import requests, json
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest'
})
r = session.get('https://chartink.com/screener/time-pass')
soup = BeautifulSoup(r.text, 'html.parser')
csrf = soup.select_one('meta[name="csrf-token"]')['content']

for k,v in chartink_scanner_pro.SCAN_CATALOG.items():
    logic = v['logic']
    if k == '3':
        logic = logic.replace('weekly volume > weekly sma( weekly volume , 10 ) * 2.0', '1 week ago weekly volume > 1 week ago weekly sma( weekly volume , 10 ) * 2.0')
    payload = {'scan_clause': logic, '_token': csrf}
    rp = session.post('https://chartink.com/screener/process', data=payload)
    data = rp.json()
    print(k, v['name'], 'count:', len(data.get('data', [])))
