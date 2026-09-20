import sys
import json
import logging
from fastmcp import FastMCP
from dhan_auth import get_dhan_client
from dhan_symbols import get_nse_id_map

# Set up simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dhan_mcp")

# Initialize the FastMCP server
mcp = FastMCP("DhanHQ MCP Server")

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------
def serialize(obj):
    return json.dumps(obj, default=str, indent=2)

def _get_security_id(symbol: str) -> str:
    symbol = symbol.strip().upper()
    id_map = get_nse_id_map()
    security_id = id_map.get(symbol)
    if not security_id:
        raise ValueError(f"Could not find NSE security_id for symbol: {symbol}")
    return security_id

# ------------------------------------------------------------------------------
# NATIVE DHANHQ TOOLS
# ------------------------------------------------------------------------------
@mcp.tool()
def dhan_get_funds() -> str:
    """Fetch the available funds and margins in the Dhan account."""
    dhan = get_dhan_client()
    try:
        res = dhan.get_fund_limits()
        return serialize(res)
    except Exception as e:
        return f"Error fetching funds: {str(e)}"

@mcp.tool()
def dhan_get_holdings() -> str:
    """Fetch current portfolio holdings from Dhan."""
    dhan = get_dhan_client()
    try:
        res = dhan.get_holdings()
        return serialize(res)
    except Exception as e:
        return f"Error fetching holdings: {str(e)}"

@mcp.tool()
def dhan_get_positions() -> str:
    """Fetch current active daily positions from Dhan."""
    dhan = get_dhan_client()
    try:
        res = dhan.get_positions()
        return serialize(res)
    except Exception as e:
        return f"Error fetching positions: {str(e)}"

@mcp.tool()
def dhan_get_order_book() -> str:
    """Fetch today's order book from Dhan (includes pending, executed, cancelled)."""
    dhan = get_dhan_client()
    try:
        res = dhan.get_order_list()
        return serialize(res)
    except Exception as e:
        return f"Error fetching orders: {str(e)}"

@mcp.tool()
def dhan_place_order(
    symbol: str, 
    transaction_type: str, 
    quantity: int, 
    order_type: str, 
    product_type: str, 
    price: float = 0.0,
    trigger_price: float = 0.0,
    is_amo: bool = False,
    stop_loss: float = 0.0
) -> str:
    """
    Place an order on Dhan.
    Args:
        stop_loss: REQUIRED for a BUY (20-Sep-2026) — the planned stop, below entry.
                   The pre-trade gate blocks a BUY without one. Not sent to Dhan by
                   this call (place the GTT separately); it sizes the 1%-risk check.
        symbol: e.g. 'TCS', 'RELIANCE'
        transaction_type: 'BUY' or 'SELL'
        quantity: integer quantity
        order_type: 'MARKET', 'LIMIT', 'STOP_LOSS', 'STOP_LOSS_MARKET'
        product_type: 'CNC' (delivery), 'INTRADAY', 'MARGIN'
        price: Required for LIMIT/STOP_LOSS orders
        trigger_price: Required for STOP_LOSS/STOP_LOSS_MARKET orders
        is_amo: True for After Market Orders
    """
    try:
        dhan = get_dhan_client()
        security_id = _get_security_id(symbol)

        # ── PRE-TRADE RISK GATE (26-Jul-2026, audit P0) ────────────────────────
        # This tool is callable by an LLM and previously reached dhan.place_order
        # with no portfolio checks whatsoever. BUY orders now clear the shared
        # fail-closed gate (max open positions / sector cap / per-trade risk-%).
        # SELL/exit orders are deliberately NOT gated — never block an exit.
        # 20-Sep-2026 (AUD-PY-02): `stop_loss` added — the gate now REFUSES a BUY
        # without a stop below entry, so the per-trade risk-% cap is always evaluated.
        from pre_trade_gate import gate_order
        _entry_px = float(price or 0.0) or float(trigger_price or 0.0)
        if transaction_type.upper() == "BUY" and _entry_px <= 0:
            try:
                import data_provider as _dp
                _entry_px = float(_dp.get_ltp(symbol.upper()) or 0.0)
            except Exception as _e:
                return (f"BLOCKED by pre-trade risk gate: MARKET buy with no price and "
                        f"the LTP lookup failed ({_e}). Cannot size the sector-exposure "
                        f"check, so the order was not placed.")
            if _entry_px <= 0:
                return ("BLOCKED by pre-trade risk gate: could not establish an entry "
                        "price, so the sector-exposure check cannot be evaluated. "
                        "Order not placed.")
        _ok, _reason = gate_order(dhan, symbol.upper(), transaction_type,
                                  int(quantity), entry_price=_entry_px,
                                  sl_price=float(stop_loss or 0.0))
        if not _ok:
            return f"BLOCKED by pre-trade risk gate: {_reason}. No order was placed."

        # Resolve dhan constants based on strings
        t_type = getattr(dhan, transaction_type.upper(), transaction_type.upper())
        o_type = getattr(dhan, order_type.upper(), order_type.upper())
        p_type = getattr(dhan, product_type.upper(), product_type.upper())
        
        res = dhan.place_order(
            security_id=security_id, 
            exchange_segment=dhan.NSE,
            transaction_type=t_type,
            quantity=int(quantity),
            order_type=o_type,
            product_type=p_type,
            price=float(price),
            trigger_price=float(trigger_price),
            after_market_order=is_amo,
            trading_symbol=symbol.upper()
        )
        return serialize(res)
    except Exception as e:
        return f"Error placing order: {str(e)}"

@mcp.tool()
def dhan_cancel_order(order_id: str) -> str:
    """Cancel a pending order on Dhan by its order ID."""
    try:
        dhan = get_dhan_client()
        res = dhan.cancel_order(order_id)
        return serialize(res)
    except Exception as e:
        return f"Error cancelling order {order_id}: {str(e)}"


# ------------------------------------------------------------------------------
# WEINSTEIN COMMANDER EXTENDED TOOLS
# ------------------------------------------------------------------------------
@mcp.tool()
def commander_get_unprotected_holdings() -> str:
    """
    Get a list of holdings that do NOT have a pending stop-loss order (OCO or regular).
    This tool cross-references get_holdings() with get_order_book().
    """
    try:
        dhan = get_dhan_client()
        holdings_res = dhan.get_holdings()
        if holdings_res.get('status') != 'success':
            return "Failed to fetch holdings."
            
        orders_res = dhan.get_order_list()
        pending_orders = []
        if orders_res.get('status') == 'success' and isinstance(orders_res.get('data'), list):
            pending_orders = [o for o in orders_res['data'] if o.get('orderStatus') == 'PENDING']
            
        holdings = holdings_res.get('data', [])
        unprotected = []
        
        for h in holdings:
            sym = h.get('tradingSymbol', '')
            # Check if there is a pending SELL order for this symbol
            has_sl = any(o.get('tradingSymbol') == sym and o.get('transactionType') == 'SELL' for o in pending_orders)
            if not has_sl:
                unprotected.append(h)
                
        return serialize({"unprotected_holdings": unprotected})
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    logger.info("Starting DhanHQ FastMCP Server...")
    # Run the server via stdio by default
    mcp.run()
