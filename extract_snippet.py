
import os

target_file = "e:/Gemini/VS Code/debug_tv_source.html"
keyword = "widgetbar-wrap"

try:
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    if keyword in content:
        idx = content.index(keyword)
        # Extract a generous chunk around it (start 1000 chars before, end 20000 chars after)
        start = max(0, idx - 1000)
        end = min(len(content), idx + 20000)
        snippet = content[start:end]
        
        with open("e:/Gemini/VS Code/debug_snippet.html", "w", encoding="utf-8") as out:
            out.write(snippet)
            
        print(f"✅ Extracted snippet of {len(snippet)} chars to debug_snippet.html")
    else:
        print(f"❌ '{keyword}' not found in file.")

except Exception as e:
    print(f"Error: {e}")
