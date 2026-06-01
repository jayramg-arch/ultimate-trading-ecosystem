"""Test new quantitative Gemini prompts and parser."""
import sys, re, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\jayra\Documents\GeminiVSCode')

from market_data_hub import build_postmarket_snapshot
from gemini_reporter import generate_postmarket_summary

print("Fetching market snapshot...")
snap = build_postmarket_snapshot()

print("Generating post-market summary with new prompt...")
text = generate_postmarket_summary(snap)

print("\n" + "="*60)
print("RAW OUTPUT:")
print("="*60)
print(text)
print("="*60)

# Test the parser
print("\nPARSED SECTIONS:")
parts = re.split(r'===\s*(.+?)\s*===', text)
i = 1
while i < len(parts) - 1:
    title = parts[i].strip()
    body  = parts[i+1].strip()
    print(f"\n[SECTION] {title}")
    print(f"  Body ({len(body)} chars): {body[:120]}...")
    i += 2

print(f"\nTotal sections found: {(len(parts)-1)//2}")
