import requests
from bs4 import BeautifulSoup
import re

url = "https://www.screener.in/company/CUB/consolidated/"
res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
if res.status_code == 404:
    url = "https://www.screener.in/company/CUB/"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    
soup = BeautifulSoup(res.text, 'html.parser')

def raw_t(sec_id):
    sec = soup.find('section', id=sec_id)
    if not sec: return
    table = sec.find('table', class_='data-table')
    if not table: return
    
    for tr in table.find('tbody').find_all('tr'):
        tds = tr.find_all('td')
        if not tds: continue
        
        row_name_btn = tds[0].find('button', class_='button-plain')
        if row_name_btn:
            row_name = re.sub(r'\s+', ' ', row_name_btn.text).strip().replace('+', '').strip()
        else:
            row_name = re.sub(r'\s+', ' ', tds[0].text).strip().replace('+', '').strip()
            
        vals = []
        for td in tds[1:]:
            val = td.text.replace(',','').strip()
            vals.append(val)
        
        print(row_name, "==>", vals)

print("==== QUARTERS ====")
raw_t('quarters')
print("----------------")
print("==== PROFIT LOSS ====")
raw_t('profit-loss')
