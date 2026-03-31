import requests
import re
from bs4 import BeautifulSoup

def get_sector_median(symbol):
    url = f'https://www.screener.in/company/{symbol}/consolidated/'
    res = requests.get(url)
    match = re.search(r'data-company-id="(\d+)"', res.text)
    if not match: return None
    cid = match.group(1)
    
    peer_url = f'https://www.screener.in/api/company/{cid}/peers/'
    peer_res = requests.get(peer_url)
    soup = BeautifulSoup(peer_res.text, 'html.parser')
    
    headers = [th.text.strip() for th in soup.select('th')]
    
    for tr in soup.select('tr'):
        if 'Median' in tr.text:
            cells = [td.text.strip() for td in tr.select('td')]
            return dict(zip(headers[1:], cells[1:]))
            
print(get_sector_median('RELIANCE'))
print(get_sector_median('FEDERALBNK'))
