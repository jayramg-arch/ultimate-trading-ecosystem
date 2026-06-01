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

logic = chartink_scanner_pro.SCAN_CATALOG['1']['logic']
payload = {'scan_clause': logic, '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=payload)
data = rp.json()
print('Stage 2 Hunter count:', len(data.get('data', [])))

logic = chartink_scanner_pro.SCAN_CATALOG['5']['logic']
payload = {'scan_clause': logic, '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=payload)
data = rp.json()
print('RS Survivors count:', len(data.get('data', [])))
