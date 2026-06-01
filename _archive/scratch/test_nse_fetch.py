import requests
import time

def fetch_nse_option_chain(nse_symbol: str):
    headers = {
        'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept':          'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection':      'keep-alive',
        'Referer':         'https://www.nseindia.com/option-chain',
        'X-Requested-With':'XMLHttpRequest',
        'sec-fetch-dest':  'empty', 'sec-fetch-mode': 'cors', 'sec-fetch-site': 'same-origin',
    }
    url = f'https://www.nseindia.com/api/option-chain-indices?symbol={nse_symbol}'
    for attempt in range(3):
        session = requests.Session()
        try:
            print(f"Attempt {attempt+1}")
            session.get('https://www.nseindia.com', headers=headers, timeout=12)
            time.sleep(1 + attempt * 0.5)
            session.get('https://www.nseindia.com/option-chain', headers=headers, timeout=12)
            time.sleep(1 + attempt * 0.3)
            resp = session.get(url, headers=headers, timeout=15)
            print("Status code:", resp.status_code)
            if resp.status_code == 200:
                print("Success length:", len(resp.text))
                return resp.json()
            else:
                print(resp.text[:200])
        except Exception as e:
            print("Error:", e)
    return None

fetch_nse_option_chain("NIFTY")
