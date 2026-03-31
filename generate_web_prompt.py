import json
import pandas as pd
import os

def create_mega_prompt():
    # 1. Load Market Intelligence (Technicals + Fundamentals)
    # Use existing market_intel.json to get the enriched data
    data = {}
    if os.path.exists("market_intel.json"):
        with open("market_intel.json", "r") as f:
            data = json.load(f)
            
    portfolio = data.get("Portfolio", [])
    
    # 2. Construct the Prompt
    prompt = """
You are a Senior Quantitative Analyst at a top-tier Hedge Fund. 
I am providing you with a JSON dataset of my current portfolio, including Technical Indicators (Stage Analysis, Relative Strength) and Fundamental Metrics.

YOUR TASK:
Perform a "Deep Research" analysis on this portfolio. 
For EACH asset, provide a concise but high-depth assessment.

DATASET:
"""
    prompt += json.dumps(portfolio, indent=2)
    
    prompt += """

REQUIRED OUTPUT FORMAT (Markdown):

## Executive Summary
(Brief Assessment of overall portfolio health, sector exposure, and risk).

## Asset Analysis
### [Symbol] - [Sector]
**Thesis:** (2 sentences on technical structure and trend conviction)
**Context:** (Valuations, Sector Tailwinds, or Macro factors. Identify ETFs correctly).
**Verdict:** [BUY / ACCUMULATE / HOLD / SELL]
**Action:** (Specific actionable advice based on the data provided).

---
(Repeat for all assets)
"""

    with open("GEMINI_PRO_PROMPT.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    
    print("✅ Master Prompt generated: GEMINI_PRO_PROMPT.txt")

if __name__ == "__main__":
    create_mega_prompt()
