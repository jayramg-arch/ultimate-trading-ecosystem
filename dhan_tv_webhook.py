from fastapi import FastAPI, Request
import os
import uvicorn
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map
from dhan_auth import get_dhan_client
from dhan_helpers import check_margin
from gmail_dispatcher import send_email

app = FastAPI()
load_dotenv()
id_map = get_nse_id_map()

# ─────────────────────────────────────────────────────────────────────────────
# HARDENING (23-Jul-2026, audit remediation 1B) — this is a MANUAL, on-demand
# gateway (a Streamlit button spawns it), so the safe posture is: SIMULATE unless
# explicitly told to go live, block on any unresolved risk/margin question, and
# never place the same alert twice. Thresholds are env-overridable.
# ─────────────────────────────────────────────────────────────────────────────
MAX_OPEN_POSITIONS = int(os.getenv("WEBHOOK_MAX_OPEN_POSITIONS", "15"))
SECTOR_CAP_PCT     = float(os.getenv("WEBHOOK_SECTOR_CAP_PCT", "25"))
MAX_RISK_PCT       = float(os.getenv("WEBHOOK_MAX_RISK_PCT", "1.5"))   # of portfolio equity
DEDUP_WINDOW_S     = int(os.getenv("WEBHOOK_DEDUP_WINDOW_S", "120"))

_RECENT_ALERTS: dict = {}   # (ticker, round(entry,2)) -> epoch seconds — in-memory dedup


def _is_duplicate(ticker: str, entry_price: float) -> bool:
    """A double-fired TradingView alert (same ticker+entry within DEDUP_WINDOW_S)
    must not place two orders. In-memory is sufficient for this single-process
    manual tool. Purges stale keys on each call."""
    import time
    key = (str(ticker).upper(), round(float(entry_price), 2))
    now = time.time()
    for k in [k for k, ts in _RECENT_ALERTS.items() if now - ts > DEDUP_WINDOW_S]:
        _RECENT_ALERTS.pop(k, None)
    if key in _RECENT_ALERTS:
        return True
    _RECENT_ALERTS[key] = now
    return False


def pre_trade_risk_check(dhan, ticker: str, qty: int, entry_price: float, sl_price: float):
    """Hard pre-trade portfolio risk gate. Returns (ok: bool, reason: str).

    Enforces three caps against the LIVE Dhan book: max open positions, single-
    sector exposure, and per-trade risk as a % of equity (reuses
    ai_risk_manager.analyze_sector_concentration + sector_lookup, same logic the
    Risk Shield surfaces). A breach → (False, reason) → the order is rejected.

    Degrades OPEN (True) with a note only when a sub-check genuinely cannot be
    computed (e.g. holdings fetch fails) — the margin check and DRY_RUN default
    remain as backstops. Never raises."""
    try:
        resp = dhan.get_holdings()
        holdings = resp.get('data', []) if isinstance(resp, dict) else []
    except Exception as e:
        return True, f"risk-gate skipped (holdings fetch failed: {e})"

    tk = str(ticker).upper()
    live = []
    for h in holdings or []:
        sym = str(h.get('tradingSymbol') or h.get('tradingsymbol') or '').upper()
        q = float(h.get('totalQty') or h.get('quantity') or 0)
        avg = float(h.get('avgCostPrice') or h.get('averagePrice') or 0)
        if q > 0:
            live.append({'Symbol': sym, 'Quantity': q, 'BuyPrice': avg})

    # 1) Max open positions (only blocks a BRAND-NEW name, not a top-up).
    open_syms = {p['Symbol'] for p in live}
    if tk not in open_syms and len(open_syms) >= MAX_OPEN_POSITIONS:
        return False, f"max open positions reached ({len(open_syms)}/{MAX_OPEN_POSITIONS})"

    # 2) Single-sector exposure cap — include the incoming order, test its sector.
    try:
        import pandas as _pd
        import ai_risk_manager as _rm
        import sector_lookup as _sl
        rows = list(live) + [{'Symbol': tk, 'Quantity': float(qty), 'BuyPrice': float(entry_price)}]
        breakdown = (_rm.analyze_sector_concentration(_pd.DataFrame(rows)) or {}).get('breakdown', {})
        rec = _sl.get_sector(tk)
        new_sector = (rec.get('display_name') or rec.get('sector_name')) if rec else None
        if new_sector and float(breakdown.get(new_sector, 0)) > SECTOR_CAP_PCT:
            return False, (f"sector cap breached: {new_sector} would be "
                           f"{breakdown[new_sector]:.1f}% (> {SECTOR_CAP_PCT:.0f}%)")
    except Exception:
        pass  # sector check inconclusive — do not block on it

    # 3) Per-trade risk as % of equity (needs a valid SL below entry).
    try:
        if sl_price and float(sl_price) > 0 and float(entry_price) > float(sl_price):
            risk_amt = float(qty) * (float(entry_price) - float(sl_price))
            funds = dhan.get_fund_limits()
            avail = float((funds.get('data') or {}).get('availabelBalance', 0)) if isinstance(funds, dict) else 0.0
            deployed = sum(p['Quantity'] * p['BuyPrice'] for p in live)
            equity = deployed + avail
            if equity > 0 and (risk_amt / equity * 100.0) > MAX_RISK_PCT:
                return False, (f"trade risk {risk_amt / equity * 100:.2f}% exceeds "
                               f"{MAX_RISK_PCT:.1f}% of equity (₹{equity:,.0f})")
    except Exception:
        pass

    return True, "risk-gate passed"

def send_webhook_email_notification(status: str, ticker: str, qty: int, entry: float, sl: float, tp: float, details: str):
    subject = f"🦁 Webhook Alert: {status.upper()} - {ticker}"
    color_banner = "#0366d6" if status == "simulation" else "#238636" if status == "success" else "#cb2431" if status == "rejected" else "#d73a49"
    status_icon = "🧪" if status == "simulation" else "✅" if status == "success" else "❌" if status == "rejected" else "⚠️"
    
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 0; padding: 20px; }}
          .card {{ max-width: 600px; margin: 0 auto; border: 1px solid #e1e4e8; border-radius: 6px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
          .banner {{ background-color: {color_banner}; color: white; padding: 20px; text-align: center; font-size: 1.5em; font-weight: bold; }}
          .content {{ padding: 24px; background-color: #ffffff; }}
          .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
          .table th {{ text-align: left; padding: 8px; border-bottom: 2px solid #eaecef; color: #586069; }}
          .table td {{ padding: 8px; border-bottom: 1px solid #eaecef; font-size: 1.1em; }}
          .footer {{ background-color: #f6f8fa; padding: 15px; text-align: center; font-size: 0.85em; color: #586069; border-top: 1px solid #e1e4e8; }}
          .btn {{ display: inline-block; background-color: #0366d6; color: white !important; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; }}
        </style>
      </head>
      <body>
        <div class="card">
          <div class="banner">
            {status_icon} GTT Order {status.upper()}
          </div>
          <div class="content">
            <p>Weinstein Commander Webhook Listener processed the following request:</p>
            <table class="table">
              <tr><th>Parameter</th><th>Value</th></tr>
              <tr><td><b>Ticker</b></td><td>NSE:{ticker}</td></tr>
              <tr><td><b>Action</b></td><td>BUY</td></tr>
              <tr><td><b>Quantity</b></td><td>{qty}</td></tr>
              <tr><td><b>Entry/Trigger Price</b></td><td>₹{entry:.2f}</td></tr>
              <tr><td><b>Planned Stop Loss</b></td><td>₹{sl:.2f}</td></tr>
              <tr><td><b>Planned Target</b></td><td>₹{tp:.2f}</td></tr>
              <tr><td><b>Details</b></td><td>{details}</td></tr>
            </table>
            <div style="text-align: center;">
              <a href="https://tradingview.com/chart" class="btn">Open TradingView Chart</a>
            </div>
          </div>
          <div class="footer">
            Autogenerated by Weinstein Commander Webhook Gateway
          </div>
        </div>
      </body>
    </html>
    """
    send_email(subject=subject, body_text=f"GTT Order {status.upper()} for {ticker}. Details: {details}", html_content=html_content)

@app.post("/tv-webhook")
async def handle_tv_webhook(request: Request):
    ticker = "UNKNOWN"
    qty = 0
    entry_price = 0.0
    sl_price = 0.0
    tp_price = 0.0
    try:
        data = await request.json()
        print(f"\n=========================================")
        print(f"RECEIVED TRADINGVIEW WEBHOOK:")
        print(f"Payload: {data}")
        
        # Parse payload
        # Expected: {"ticker":"NSE:RELIANCE", "action":"BUY", "entry":2500, "sl":2400, "tp":2700, "qty":10}
        ticker = data.get("ticker", "").replace("NSE:", "").replace("BSE:", "").strip()
        qty = int(data.get("qty", 0))
        entry_price = float(data.get("entry", 0))
        sl_price = float(data.get("sl", 0))
        tp_price = float(data.get("tp", 0))
        
        if not ticker or qty <= 0 or entry_price <= 0:
            print("Error: Invalid payload (missing ticker, qty, or entry).")
            send_webhook_email_notification("error", ticker, qty, entry_price, sl_price, tp_price, "Invalid payload (missing ticker, qty, or entry).")
            return {"status": "error", "message": "Invalid payload"}
            
        if ticker not in id_map:
            print(f"Error: Symbol {ticker} not found in dhan_symbols map.")
            send_webhook_email_notification("error", ticker, qty, entry_price, sl_price, tp_price, f"Symbol {ticker} not found in dhan_symbols map.")
            return {"status": "error", "message": "Symbol not found"}
            
        security_id = id_map[ticker]
        
        # Check for Dry Run mode. HARDENING: default is now TRUE — live order
        # placement is EXPLICIT opt-in (set DRY_RUN=False in the environment).
        dry_run = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")
        
        if dry_run:
            print(f"\n🧪 DRY RUN MODE ENABLED — SIMULATION ONLY")
            print(f"Symbol: {ticker} ({security_id})")
            print(f"Quantity: {qty}")
            print(f"Trigger & Limit Price: ₹{entry_price}")
            print(f"--> Target Planned: ₹{tp_price}")
            print(f"--> Stop Loss Planned: ₹{sl_price}")
            print("Action: Skipping live order placement on Dhan.")
            send_webhook_email_notification(
                "simulation", 
                ticker, 
                qty, 
                entry_price, 
                sl_price, 
                tp_price, 
                "SIMULATION SUCCESS: Dry Run Mode is active. No actual trade was placed on Dhan."
            )
            return {"status": "simulated", "message": "Simulation processed successfully"}

        # HARDENING: idempotency — reject a duplicate (ticker, entry) fired inside
        # the dedup window so a double-sent alert can never place two orders.
        if _is_duplicate(ticker, entry_price):
            msg = f"Duplicate alert ignored (same {ticker} @ ₹{entry_price} within {DEDUP_WINDOW_S}s)."
            print(f"REJECTED (dedup): {msg}")
            send_webhook_email_notification("rejected", ticker, qty, entry_price, sl_price, tp_price, msg)
            return {"status": "rejected", "message": msg}

        print(f"\nPLACING FOREVER (GTT) BUY ORDER")
        print(f"Symbol: {ticker} ({security_id})")
        print(f"Quantity: {qty}")
        print(f"Trigger & Limit Price: ₹{entry_price}")
        print(f"--> Target Planned: ₹{tp_price}")
        print(f"--> Stop Loss Planned: ₹{sl_price}")

        # Place the Entry GTT via Dhan API
        dhan = get_dhan_client()

        # HARDENING: hard pre-trade portfolio risk gate (max positions / sector cap
        # / per-trade risk %). A breach REJECTS the order before it reaches Dhan.
        risk_ok, risk_reason = pre_trade_risk_check(dhan, ticker, qty, entry_price, sl_price)
        if not risk_ok:
            msg = f"Pre-trade risk gate REJECTED: {risk_reason}"
            print(f"REJECTED (risk): {msg}")
            send_webhook_email_notification("rejected", ticker, qty, entry_price, sl_price, tp_price, msg)
            return {"status": "rejected", "message": msg}
        print(f"Risk gate: {risk_reason}")

        # Mandatory Pre-Flight: Check Margin for GTT Buy. HARDENING: a margin check
        # that itself THROWS is now BLOCKING (was "continuing anyway" — an order
        # could be placed with the balance question unresolved).
        try:
            margin_info = check_margin(
                dhan,
                security_id=str(security_id),
                exchange_segment=dhan.NSE,
                transaction_type=dhan.BUY,
                quantity=qty,
                product_type=dhan.CNC,
                price=entry_price,
                trigger_price=entry_price
            )
            if not margin_info.get("sufficient", True):
                msg = f"Insufficient Margin! Required: ₹{margin_info.get('total_margin', 0):.2f}, Available: ₹{margin_info.get('available_balance', 0):.2f}. Shortfall: ₹{margin_info.get('shortfall', 0):.2f}"
                print(f"REJECTED: {msg}")
                send_webhook_email_notification("rejected", ticker, qty, entry_price, sl_price, tp_price, msg)
                return {"status": "rejected", "message": msg}
        except Exception as e:
            msg = f"Margin check failed — order BLOCKED (balance unverified): {e}"
            print(f"REJECTED: {msg}")
            send_webhook_email_notification("rejected", ticker, qty, entry_price, sl_price, tp_price, msg)
            return {"status": "rejected", "message": msg}

        response = dhan.place_forever(
            security_id=str(security_id),
            exchange_segment=dhan.NSE,
            product_type=dhan.CNC,  # Delivery / Swing
            order_type=dhan.LIMIT,
            transaction_type=dhan.BUY,
            quantity=qty,
            price=entry_price,
            trigger_Price=entry_price
        )
        
        if response.get('status') == 'success':
            order_id = response['data'].get('orderId', 'UNKNOWN')
            print(f"SUCCESS! Order ID: {order_id}")
            send_webhook_email_notification("success", ticker, qty, entry_price, sl_price, tp_price, f"Successfully placed GTT buy order via Dhan! Order ID: {order_id}")
        else:
            print(f"REJECTED by Dhan: {response}")
            remarks = response.get('remarks', 'Dhan API Rejected the Order')
            send_webhook_email_notification("rejected", ticker, qty, entry_price, sl_price, tp_price, f"Dhan API Order Placement Rejected: {remarks}")
            
        return {"status": "processed", "dhan_response": response}
        
    except Exception as e:
        print(f"Webhook processing error: {e}")
        send_webhook_email_notification("error", ticker, qty, entry_price, sl_price, tp_price, f"Unexpected error during webhook execution: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  COMMANDER TRADINGVIEW WEBHOOK LISTENER")
    print("="*50)
    print("Listening for webhooks on http://localhost:8000/tv-webhook")
    print("\nTo connect this to TradingView, you MUST expose it to the internet.")
    print("Run this command in a NEW terminal window:")
    print("   ngrok http 8000")
    print("\nThen paste the ngrok URL (e.g., https://<your-id>.ngrok.app/tv-webhook)")
    print("into the 'Webhook URL' box in your TradingView Alert.")
    print("="*50 + "\n")
    
    # Start server
    uvicorn.run(app, host="0.0.0.0", port=8000)
