
import os

target_file = "e:/Gemini/VS Code/debug_tv_source.html"

search_terms = ["widgetbar-wrap", "layout__area--right"]

try:
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"File size: {len(content)} characters")
    
    for term in search_terms:
        if term in content:
            print(f"✅ Found '{term}' at index {content.index(term)}")
            start = max(0, content.index(term) - 100)
            end = min(len(content), content.index(term) + 300)
            print(f"   Context: ...{content[start:end]}...")
            print("-" * 50)
        else:
            print(f"❌ '{term}' NOT found.")

except Exception as e:
    print(f"Error reading file: {e}")
