from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI(title="TV Sidecar API")

# Allow CORS so the Chrome Extension can talk to it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all. Or restrict to "https://*.tradingview.com"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "data"
TICKER_FILE = os.path.join(DATA_DIR, "active_ticker.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize blank file if doesn't exist
if not os.path.exists(TICKER_FILE):
    with open(TICKER_FILE, 'w') as f:
        json.dump({"active_symbol": ""}, f)


@app.post("/set_ticker")
async def set_ticker(symbol: str):
    """Called by the Chrome Extension to update the active ticker."""
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    
    # Write directly to text file to serve as a fast cache for Streamlit
    try:
        with open(TICKER_FILE, 'w') as f:
            json.dump({"active_symbol": symbol}, f)
        print(f"✅ Sidecar API: Active ticker updated to {symbol}")
        return {"status": "success", "active_symbol": symbol}
    except Exception as e:
        print(f"Error writing to ticker file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save ticker state")

@app.get("/get_ticker")
async def get_ticker():
    """Called by Streamlit to quickly poll the active ticker."""
    try:
        if os.path.exists(TICKER_FILE):
            with open(TICKER_FILE, 'r') as f:
                data = json.load(f)
                return data
        return {"active_symbol": ""}
    except Exception as e:
        print(f"Error reading ticker file: {e}")
        return {"active_symbol": ""}

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting TradingView AI Sidecar API on port 8001...")
    uvicorn.run("tv_sidecar_api:app", host="localhost", port=8001, reload=True)
