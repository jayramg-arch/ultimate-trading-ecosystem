import os
from bs4 import BeautifulSoup
import re

def search_all_html():
    results = []
    for root, dirs, files in os.walk("e:/Gemini/VS Code"):
        if ".venv" in root or ".git" in root or ".vscode" in root:
            continue
            
        for file in files:
            if file.lower().endswith((".html", ".htm", ".mhtml")):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if "Oct" in content or "October" in content:
                        print(f"FOUND 'Oct' in {path}")
                        # Extract some context
                        soup = BeautifulSoup(content, 'html.parser')
                        rows = soup.find_all('tr')
                        for row in rows:
                            text = row.get_text(separator=" ", strip=True)
                            if "Oct" in text or "October" in text:
                                if "2025" in text:
                                    print(f"MATCH: {text}")
                                    results.append(text)
                except Exception as e:
                    pass
    
    print(f"\nTotal October 2025 matches found: {len(results)}")

if __name__ == "__main__":
    search_all_html()
