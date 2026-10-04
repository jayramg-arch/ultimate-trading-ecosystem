"""order_levels.py - a holding's stop-loss and targets read off its resting Dhan orders.

ONE definition (4-Oct-2026), used by the Journal page when it loads and by the 16:30
journal sync, so a stop you move on Dhan reaches the journal - and from there v67's
slots (tv_push_v67_trail.py) - whether or not the Journal page is opened that day.
Light on purpose: no Streamlit, no app imports.
"""
from __future__ import annotations


def clean_symbol(symbol):
    """Dhan symbol -> journal symbol: strip exchange prefix and series suffix."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s == "NIFTY":
        return "^NSEI"
    if s == "BANKNIFTY" or s == "NIFTYBANK":
        return "^NSEBANK"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s


def parse_orders(items) -> dict:
    """{symbol: [{'leg','otype','price','trigger'}]} for PENDING sell orders
    (regular order book and forever/OCO orders alike)."""
    out = {}
    for item in items or []:
        if item.get('transactionType') != 'SELL' or item.get('orderStatus') != 'PENDING':
            continue
        sym = item.get('tradingSymbol')
        if not sym:
            continue
        out.setdefault(clean_symbol(sym), []).append({
            'leg': item.get('legName'), 'otype': item.get('orderType', ''),
            'price': float(item.get('price') or 0.0), 'trigger': float(item.get('triggerPrice') or 0.0),
            # 4-Oct-2026: which stop is CURRENT needs the time and the quantity, not just the price
            'ts': str(item.get('updateTime') or item.get('createTime') or ''),
            'qty': int(float(item.get('quantity') or 0)), 'oid': str(item.get('orderId') or '')})
    return out


def _classify(orders, ref_price):
    """Split one symbol's resting orders into stop legs and target prices."""
    stops, targets = [], set()
    for o in orders or []:
        val = o['trigger'] if o['trigger'] > 0 else o['price']
        val_limit = o['price'] if o['price'] > 0 else o['trigger']
        if o['leg'] == 'TARGET_LEG':
            targets.add(val_limit)
        elif o['leg'] == 'STOP_LOSS_LEG' or o['otype'] in ['SL', 'SL-M', 'STOP_LOSS']:
            stops.append((val, o))
        elif val > ref_price:
            targets.add(val_limit)
        elif 0 < val < ref_price:
            stops.append((val, o))
    return stops, targets


def derive_sl_targets(orders, ref_price) -> tuple[float, float, float]:
    """(stop, target1, target2) from one symbol's resting orders; 0.0 = none.

    The stop is the MOST RECENTLY placed or modified stop leg (4-Oct-2026, Jay: VIJAYA had
    a new 1268.5 stop beside two August OCOs at 1275.5, and "highest wins" kept the old
    one). Ties on time -> the higher stop. When stops disagree, stop_report() says so.
    ref_price is the LTP (27-Aug-2026): against the buy price a stop trailed above entry
    was filed as a target. Unlabelled orders are classed by price against ref_price."""
    stops, targets = _classify(orders, ref_price)
    live_sl = max(stops, key=lambda v: (v[1].get('ts', ''), v[0]))[0] if stops else 0.0
    st = sorted(targets)
    return live_sl, (st[0] if st else 0.0), (st[1] if len(st) > 1 else 0.0)


def stop_report(orders, ref_price, holding_qty=None) -> str:
    """'' when the stops are consistent; otherwise a one-line warning: stop legs at
    different prices (the higher one fires FIRST, whatever the journal shows) and/or
    shares with no stop at all. OCO legs of one order share a quantity, so each
    order id is counted once."""
    stops, _ = _classify(orders, ref_price)
    if not stops:
        return ""
    by_price, seen = {}, set()
    for val, o in stops:
        key = o.get('oid') or id(o)
        if key in seen:
            continue
        seen.add(key)
        by_price[val] = by_price.get(val, 0) + int(o.get('qty') or 0)
    msgs = []
    if len(by_price) > 1:
        msgs.append("stops disagree: " + ", ".join(f"{q} sh @ {p:g}" for p, q in sorted(by_price.items(), reverse=True))
                    + f" - {max(by_price):g} fires first")
    covered = sum(by_price.values())
    if holding_qty and covered < holding_qty:
        msgs.append(f"{int(holding_qty) - covered} of {int(holding_qty)} shares have no stop")
    return "; ".join(msgs)


def fetch_live_orders(dhan) -> dict:
    """parse_orders over the order book and the forever orders of one Dhan client."""
    out = {}
    for call in ("get_order_list", "get_forever"):
        try:
            r = getattr(dhan, call)()
            if r.get('status') == 'success' and r.get('data'):
                for k, v in parse_orders(r['data']).items():
                    out.setdefault(k, []).extend(v)
        except Exception:
            pass
    return out
