"""
alert_engine.py  –  Price Alert Manager for Weinstein Commander
─────────────────────────────────────────────────────────────────
Stores alerts in reports/price_alerts.json.

Each alert record:
    {
        "id":         str  (uuid4),
        "symbol":     str  (e.g. "INFY.NS"),
        "condition":  "above" | "below" | "crossing",
        "price":      float,
        "note":       str,
        "active":     bool,
        "fired_at":   str | null,
        "created_at": str
    }

Public API
----------
add_alert(symbol, condition, price, note)  → dict
remove_alert(alert_id)                     → bool
toggle_alert(alert_id)                     → bool  (new active state)
list_alerts()                              → list[dict]
check_alerts(notify_fn=None)               → list[dict]  (fired alerts)
get_current_price(symbol)                  → float | None
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DIR   = Path(os.path.dirname(os.path.abspath(__file__)))
_STORE = _DIR / "reports" / "price_alerts.json"

# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load() -> list:
    try:
        if _STORE.exists():
            data = json.loads(_STORE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as exc:
        logger.warning("alert_engine: could not load store: %s", exc)
    return []


def _save(alerts: list) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(alerts, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Price fetch
# ---------------------------------------------------------------------------

def get_current_price(symbol: str) -> float | None:
    """Return the current price for a symbol.

    T3.6 (20 Jun 2026): uses data_provider.get_ltp — a LIVE Dhan last-traded-price
    during NSE market hours, falling back to the EOD close after close. Alerts now
    trigger on the live price during the session instead of yesterday's close.
    Falls back to yfinance fast_info if data_provider is unavailable.
    """
    try:
        import data_provider as _dp
        price = _dp.get_ltp(symbol)
        if price and price > 0:
            return float(price)
    except Exception:
        pass
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).fast_info
        price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
        if price and float(price) > 0:
            return float(price)
    except Exception as exc:
        logger.warning("get_current_price(%s) failed: %s", symbol, exc)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_alert(symbol: str, condition: str, price: float, note: str = "") -> dict:
    """
    Add a new price alert.

    Parameters
    ----------
    symbol    : ticker string, e.g. "INFY.NS" or "NIFTY=F"
    condition : "above" | "below" | "crossing"
    price     : trigger price level
    note      : optional freeform annotation

    Returns the created alert dict.
    """
    alerts = _load()
    alert = {
        "id":         str(uuid.uuid4()),
        "symbol":     symbol.upper().strip(),
        "condition":  condition,
        "price":      float(price),
        "note":       note.strip(),
        "active":     True,
        "fired_at":   None,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    alerts.append(alert)
    _save(alerts)
    logger.info("Alert added: %s %s %.2f", alert["symbol"], condition, price)
    return alert


def remove_alert(alert_id: str) -> bool:
    """Remove alert by ID. Returns True if found and removed."""
    alerts = _load()
    before = len(alerts)
    alerts = [a for a in alerts if a.get("id") != alert_id]
    if len(alerts) < before:
        _save(alerts)
        logger.info("Alert removed: %s", alert_id)
        return True
    return False


def toggle_alert(alert_id: str) -> bool:
    """Toggle active / paused state. Returns new active state (True/False)."""
    alerts = _load()
    for alert in alerts:
        if alert.get("id") == alert_id:
            alert["active"] = not alert.get("active", True)
            _save(alerts)
            return bool(alert["active"])
    return False


def list_alerts() -> list:
    """Return all alerts (active + fired)."""
    return _load()


def check_alerts(notify_fn=None) -> list:
    """
    Fetch current prices and evaluate all active alerts.

    Parameters
    ----------
    notify_fn : optional callable(alert_dict, current_price)
                Called for every triggered alert before it is marked inactive.

    Returns
    -------
    list of alert dicts that fired during this check (augmented with
    key "current_price").
    """
    alerts = _load()
    active = [a for a in alerts if a.get("active")]
    if not active:
        return []

    # Batch-fetch unique symbols
    symbols = list({a["symbol"] for a in active})
    prices: dict[str, float] = {}
    for sym in symbols:
        p = get_current_price(sym)
        if p is not None:
            prices[sym] = p

    fired = []
    for alert in alerts:
        if not alert.get("active"):
            continue
        sym   = alert["symbol"]
        cond  = alert["condition"]
        level = float(alert["price"])
        cur   = prices.get(sym)
        if cur is None:
            continue

        triggered = False
        if   cond == "above"    and cur >= level:
            triggered = True
        elif cond == "below"    and cur <= level:
            triggered = True
        elif cond == "crossing":
            # Treat as triggered if within 0.3 % of the level
            triggered = abs(cur - level) / max(level, 1e-9) < 0.003

        if triggered:
            alert["active"]   = False
            alert["fired_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fired_entry = {**alert, "current_price": cur}
            fired.append(fired_entry)
            logger.info("Alert fired: %s %s %.2f (cur=%.2f)", sym, cond, level, cur)
            if notify_fn:
                try:
                    notify_fn(alert, cur)
                except Exception as ne:
                    logger.warning("notify_fn raised: %s", ne)

    _save(alerts)
    return fired


# ---------------------------------------------------------------------------
# Telegram notification helper (used by scheduler)
# ---------------------------------------------------------------------------

def build_telegram_message(alert: dict, current_price: float) -> str:
    sym   = alert.get("symbol", "?")
    cond  = alert.get("condition", "?")
    level = alert.get("price", 0)
    note  = alert.get("note", "")
    emoji = "🟢" if cond == "above" else "🔴" if cond == "below" else "🔔"
    lines = [
        f"{emoji} <b>PRICE ALERT FIRED</b>",
        f"Symbol:    <b>{sym}</b>",
        f"Condition: {cond} {level:,.2f}",
        f"Current:   <b>{current_price:,.2f}</b>",
    ]
    if note:
        lines.append(f"Note:      {note}")
    lines.append(f"Time:      {alert.get('fired_at', '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point (quick test)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        alerts = list_alerts()
        if not alerts:
            print("No alerts configured.")
        for a in alerts:
            status = "✅ active" if a["active"] else f"🔕 fired {a.get('fired_at','')}"
            print(f"[{a['id'][:8]}] {a['symbol']:12s} {a['condition']:10s} {a['price']:>10.2f}  {status}  {a['note']}")
    elif cmd == "check":
        fired = check_alerts()
        print(f"Checked alerts. {len(fired)} fired.")
        for f in fired:
            print(f"  FIRED: {f['symbol']} {f['condition']} {f['price']:.2f} (cur={f['current_price']:.2f})")
    else:
        print("Usage: python alert_engine.py [list|check]")
