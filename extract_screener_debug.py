
import requests
import os

SCREENER_URLS = {
    "Stage2_Hunter": "https://www.screener.in/screens/3454433/stage2-hunter-final/"
}

COOKIE_STRING = "csrftoken=TTQwjRrn5mKrjemC7LKLDL7m3wJrwTQU; sessionid=x5or8z7s9n3y1w2v4u6t8r0q; expires=Sun, 24 Jan 2027 13:34:38 GMT;" # Simplified, but better to use the specific one from the file if possible. 
# actually, I'll just copy the one from screener_fetcher.py exactly.
COOKIE_STRING = "csrftoken=TTQwjRrn5mKrjemC7LKLDL7m3wJrwTQU; expires=Sun, 24 Jan 2027 13:34:38 GMT; Max-Age=31449600; Path=/; SameSite=Lax; Secure"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Cookie": COOKIE_STRING
}


def run():
    # Construct edit URL
    base_url = list(SCREENER_URLS.values())[0]
    if base_url.endswith("/"):
        edit_url = base_url + "edit/"
    else:
        edit_url = base_url + "/edit/"
        
    print(f"Fetching {edit_url}...")
    try:
        r = requests.get(edit_url, headers=headers)
        if r.status_code == 200:
            with open("screener_edit_debug.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("Successfully saved screener_edit_debug.html")
        else:
            print(f"Failed with status {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
