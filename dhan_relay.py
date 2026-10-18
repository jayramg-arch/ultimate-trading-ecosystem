#!/usr/bin/env python3
"""Route Dhan ORDER calls through a static-IP relay (18-Oct-2026, Doc 42 §9).

Dhan accepts order placement / modification only from the static public IP registered on the
account (SEBI rule; otherwise DH-905). JioFiber gives no static IP at home, so a small AWS
Lightsail server in Mumbai with a static IP runs a proxy that only the tailnet can reach, and
ONLY the order-changing calls go through it. Market data, holdings and the journal sync stay on
the home connection.

    .env:  DHAN_ORDER_PROXY=http://dhanrelay:8888     (the relay's Tailscale name + proxy port)

install() wraps the order methods of the dhanhq CLASS once per process (dhan_auth imports this,
so every client in the house is covered - about twenty places construct one). With
DHAN_ORDER_PROXY unset it is a no-op: behaviour is exactly as before.

    python dhan_relay.py --check         which public IP Dhan sees - directly and via the relay
    python dhan_relay.py --test-modify   re-submit one resting stop at its SAME values through
                                         the relay (asks first) - proves DH-905 is gone
"""
from __future__ import annotations

import argparse
import functools
import os
import sys

ORDER_METHODS = ("place_order", "modify_order", "cancel_order", "place_slice_order",
                 "place_forever", "modify_forever", "cancel_forever")


def proxy_url() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    except Exception:
        pass
    return (os.getenv("DHAN_ORDER_PROXY") or "").strip()


def _wrap(fn):
    @functools.wraps(fn)
    def w(self, *a, **k):
        px = proxy_url()
        sess = getattr(self, "session", None)
        if not px or sess is None:
            return fn(self, *a, **k)
        old = dict(sess.proxies)
        sess.proxies.update({"https": px, "http": px})
        try:
            return fn(self, *a, **k)
        finally:
            sess.proxies.clear()
            sess.proxies.update(old)
    w._dhan_relay = True
    return w


def install() -> bool:
    """Wrap the dhanhq class's order methods (idempotent). Returns True when installed."""
    try:
        from dhanhq import dhanhq as _cls
    except Exception:
        return False
    for m in ORDER_METHODS:
        f = getattr(_cls, m, None)
        if f is not None and not getattr(f, "_dhan_relay", False):
            setattr(_cls, m, _wrap(f))
    return True


def _public_ip(proxy: str | None = None) -> str:
    import requests
    pr = {"https": proxy, "http": proxy} if proxy else None
    return requests.get("https://api.ipify.org", proxies=pr, timeout=10).text.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--test-modify", action="store_true")
    a = ap.parse_args()
    px = proxy_url()
    if a.check or not a.test_modify:
        try:
            print("home public IP (data calls):     %s" % _public_ip())
        except Exception as e:
            print("home public IP: unavailable (%s)" % e)
        if not px:
            print("DHAN_ORDER_PROXY is not set - order calls go out on the home IP (DH-905 until a relay is set up)")
            return 1
        try:
            v4 = _public_ip(px)
            print("relay public IPv4 (order calls): %s   <- the IP registered with Dhan" % v4)
        except Exception as e:
            print("relay unreachable via %s: %s" % (px, e))
            return 2
        # 18-Oct-2026: Dhan's API is on CloudFront, which answers over IPv6 - a dual-stack relay then
        # leaves on its IPv6 address and Dhan replies DH-905 although the IPv4 above is registered.
        # api64 answers over whichever family the relay PREFERS, i.e. what Dhan would actually see.
        try:
            import requests
            seen = requests.get("https://api64.ipify.org", proxies={"https": px, "http": px}, timeout=10).text.strip()
        except Exception:
            seen = v4
        print("address Dhan would see:          %s%s" % (seen, "" if seen == v4 else
              "   <- IPv6! the relay must prefer IPv4 (Doc 42 §9: /etc/gai.conf precedence, or Lightsail IPv6 off)"))
        return 0 if seen == v4 else 3
    # --test-modify: one harmless modify at the same values
    if not px:
        print("set DHAN_ORDER_PROXY first", file=sys.stderr)
        return 2
    install()
    import gtt_auto_shield as g
    dhan = g.connect_dhan()
    legs = g._live_oco_sl_legs(dhan) or {}
    # one stop of EACH kind - an OCO stop leg and a SINGLE stop (the runner covers) - because the
    # trail modifies both and each must be accepted before it goes live
    picks = []
    for kind in ("OCO", "SINGLE"):
        p = next(((s, l) for s, ls in sorted(legs.items()) for l in ls if l.get("flag") == kind), None)
        if p:
            picks.append(p)
    if not picks:
        print("no resting stop order to test with")
        return 1
    results = []
    for s, leg in picks:
        lim = leg.get("sl_price") or round(leg["sl_trigger"] * 0.995, 2)
        ans = input("Re-submit %s %s stop %s at its SAME values (trigger %.2f, limit %.2f, qty %d) via the relay? (Y/N): "
                    % (leg.get("flag"), s, leg["order_id"], leg["sl_trigger"], lim, leg["sl_qty"])).strip().upper()
        if ans != "Y":
            print("not sent")
            continue
        r = dhan.modify_forever(order_id=leg["order_id"], order_flag=leg.get("flag", "OCO"), order_type=dhan.LIMIT,
                                leg_name=leg.get("leg_name") or "STOP_LOSS_LEG", quantity=leg["sl_qty"],
                                price=lim, trigger_price=leg["sl_trigger"], disclosed_quantity=0, validity="DAY")
        print(r)
        results.append((leg.get("flag"), isinstance(r, dict) and r.get("status") == "success"))
    for kind, ok in results:
        print("%-6s stop: %s" % (kind, "ACCEPTED" if ok else "not accepted - read the remarks above (DH-905 = IP not registered yet)"))
    ok = bool(results) and all(o for _k, o in results) and len(results) == len(picks)
    print("RELAY WORKS for every stop kind - switch the trail live" if ok else "do NOT switch the trail live yet")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
