import sys
import os
import argparse
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map

# 1. Setup Argument Parser
parser = argparse.ArgumentParser(description='Dhan Order Handler for n8n')
parser.add_argument('ticker', type=str, help='Stock Symbol (e.g. TCS, RELIANCE)')
parser.add_argument('action', type=str, help='BUY or SELL')
parser.add_argument('quantity', type=int, help='Quantity to trade')
parser.add_argument('--dry-run', action='store_true', help='Simulate order without executing')
# 26-Jul-2026 (audit P0): this handler reached dhan.place_order with ZERO portfolio
# checks. BUY orders now go through the shared fail-closed gate in pre_trade_gate.py
# (max open positions / sector cap / per-trade risk-%). SELLs are never gated.
parser.add_argument('--entry', type=float, default=0.0,
                    help='Entry price estimate for the risk gate (BUY only). '
                         'Omitted → the live LTP is fetched; if that fails the BUY is blocked.')
parser.add_argument('--sl', type=float, default=0.0,
                    help='Planned stop-loss (BUY only). Without it the per-trade '
                         'risk-%% cap cannot be evaluated and is skipped.')

def main():
    # Parse Args
    try:
        args = parser.parse_args()
    except:
        # If running from n8n simple exec, sys.argv might be messy if not handled, 
        # but argparse is standard.
        print("Usage: python n8n_order_handler.py [TICKER] [ACTION] [QTY]")
        sys.exit(1)

    ticker = args.ticker.upper()
    action = args.action.upper()
    qty = args.quantity
    
    print(f"🤖 Received Signal: {action} {qty} {ticker}")

    # 2. Load Environment
    load_dotenv()
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token:
        print("❌ Error: Credentials not found in .env")
        sys.exit(1)

    # 3. Resolve Security ID
    # Note: caching this file locally or using a smaller map would be faster,
    # but reusing existing logic is safer for now.
    print("🔍 resolving Security ID...")
    symbol_map = get_nse_id_map()
    
    security_id = symbol_map.get(ticker)
    
    if not security_id:
        print(f"❌ Error: Symbol '{ticker}' not found in Dhan NSE Equity map.")
        # Try fuzzy match or removing -EQ? 
        # For now, strict match.
        sys.exit(1)
        
    print(f"✅ Found Security ID for {ticker}: {security_id}")

    # 4. Connect to Dhan
    dhan = dhanhq(client_id, access_token)

    # 4b. PRE-TRADE RISK GATE (BUY only — exits are never blocked).
    # Fail-closed: if the gate can't be evaluated, the BUY does not go through.
    from pre_trade_gate import gate_order
    entry_px = float(args.entry or 0.0)
    if action == 'BUY' and entry_px <= 0:
        # The sector cap needs a notional; a ₹0 entry would silently neuter it.
        try:
            import data_provider as _dp
            entry_px = float(_dp.get_ltp(ticker) or 0.0)
            print(f"💹 Entry price for risk gate (live LTP): ₹{entry_px:,.2f}")
        except Exception as e:
            print(f"❌ BLOCKED: no --entry given and LTP fetch failed ({e}). "
                  f"Re-run with --entry <price>.")
            sys.exit(1)
        if entry_px <= 0:
            print("❌ BLOCKED: could not establish an entry price for the risk gate. "
                  "Re-run with --entry <price>.")
            sys.exit(1)

    gate_ok, gate_reason = gate_order(dhan, ticker, action, qty,
                                      entry_price=entry_px, sl_price=float(args.sl or 0.0))
    print(f"🛡️  Risk gate: {'PASS' if gate_ok else 'BLOCK'} — {gate_reason}")
    if not gate_ok:
        print("❌ Order rejected by the pre-trade risk gate. No order was placed.")
        sys.exit(1)

    # 5. Place Order
    if args.dry_run:
        print(f"🚧 DRY RUN: Would have placed {action} order for {qty} x {ticker} (ID: {security_id})")
        sys.exit(0)

    try:
        print(f"🚀 Executing Order...")
        transaction_type = dhan.BUY if action == 'BUY' else dhan.SELL
        
        # Placing MARKET Order for Equity Delivery (CNC) or Intraday? 
        # For automation, usually Intraday (MIS) or Carry (CNC). 
        # Defaulting to CNC (Delivery) for safety, user can change if needed.
        
        response = dhan.place_order(
            security_id=security_id,
            exchange_segment=dhan.NSE,
            transaction_type=transaction_type,
            quantity=qty,
            order_type=dhan.MARKET,
            product_type=dhan.CNC, # Delivery
            validity=dhan.DAY
        )
        
        if response.get('status') == 'success':
            print(f"✅ Order Success! ID: {response.get('data', {}).get('orderId')}")
            print(f"📝 {response}")
        else:
            print(f"❌ Order Rejected: {response}")
            
    except Exception as e:
        print(f"❌ Exception during order placement: {e}")

if __name__ == "__main__":
    main()
