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

# Test 1: Simple 200D SMA
logic1 = '( {57960} ( daily close > daily sma( daily close , 200 ) ) )'
payload = {'scan_clause': logic1, '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=payload)
print('Simple 200D:', len(rp.json().get('data', [])), rp.status_code)

# Test 2: Simple 200D + Mansfield RS
logic2 = '( {57960} ( daily close > daily sma( daily close , 200 ) and weekly close / {57960} weekly close > weekly sma( weekly close / {57960} weekly close , 30 ) ) )'
payload = {'scan_clause': logic2, '_token': csrf}
rp = session.post('https://chartink.com/screener/process', data=payload)
print('With Mansfield:', len(rp.json().get('data', [])), rp.status_code)
