from fastapi import FastAPI, Request, HTTPException
import uvicorn
import logging
from broker_gateway import get_broker_gateway
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Weinstein Commander Webhook Daemon", version="1.0")
dhan_gateway = get_broker_gateway()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Commander Webhook Daemon is running."}

@app.post("/tv-alert")
async def receive_tv_alert(request: Request):
    """
    Endpoint to receive TradingView webhook alerts.
    Expected JSON payload format:
    {
        "symbol": "TCS",
        "action": "BUY",  # or "SELL"
        "price": 4000.50,
        "quantity": 10,
        "message": "Stage 2 Breakout Alert"
    }
    """
    try:
        data = await request.json()
        logger.info(f"Received TradingView Alert: {data}")

        symbol = data.get("symbol")
        action = data.get("action", "").upper()
        price = data.get("price")
        quantity = data.get("quantity")

        if not symbol or not action or not quantity:
            logger.error("Invalid payload missing required fields.")
            raise HTTPException(status_code=400, detail="Missing required fields (symbol, action, quantity)")

        if action not in ["BUY", "SELL"]:
            logger.error(f"Invalid action: {action}")
            raise HTTPException(status_code=400, detail="Action must be BUY or SELL")

        # Map to DhanHQ constants
        transaction_type = dhan_gateway.BUY if action == "BUY" else dhan_gateway.SELL

        # Place Order via Gateway
        # Note: Security ID resolution is required in real-world use. 
        # For simplicity in this daemon, we rely on the user sending the exact security_id or 
        # we would look it up from a master list. Assuming 'security_id' is passed in payload.
        security_id = data.get("security_id")
        
        if not security_id:
            logger.warning("No security_id provided in webhook, order execution skipped. Alert logged.")
            return {"status": "logged", "message": "Alert received but no security_id provided for execution."}

        order = dhan_gateway.place_order(
            security_id=security_id, 
            exchange_segment=dhan_gateway.NSE,
            transaction_type=transaction_type, 
            quantity=int(quantity),
            order_type=dhan_gateway.MARKET if not price else dhan_gateway.LIMIT, 
            product_type=dhan_gateway.CNC,
            price=float(price) if price else 0.0
        )

        logger.info(f"Order Execution Result: {order}")
        return {"status": "success", "order": order}

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting TradingView Webhook Listener on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
