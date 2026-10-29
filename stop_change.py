"""stop_change.py - change a Disaster SL from Web Commander, only when every condition holds
(29-Oct-2026).

Jay: "Presently, I'm manually lowering the disaster SL levels. It should be routed through web
commander now and it should check whether all the conditions are met before placing the
modify SL order."

TWO STEPS, the same checks both times:
  plan(sym, new_stop)   reads Dhan FRESH (holdings, every resting stop leg, LTP), and returns
                        the checks - each BLOCK or WARN, pass or fail - plus the legs it would
                        modify. Nothing is sent.
  apply(sym, new_stop)  runs plan() again on fresh data and, only when no BLOCK check fails,
                        modifies EVERY stop leg of the holding to the one new trigger (limit
                        0.5% below, both on the exchange's half-rupee grid - stop_prices, the
                        trail's own call), reads the legs back, and then:
                          * journal stoploss and manual_sl_override = the new stop. The override
                            is the trail's FLOOR: left at the old, higher level, the 15:45 trail
                            would put a lowered stop straight back up;
                          * stop_guard baseline = the new legs, so the guard does not flag the
                            change it just approved;
                          * stop_history row (source 'web') + stop_guard event 'WEB';
                          * one Telegram.

BLOCKING CONDITIONS (all must pass):
  1  Dhan reachable and the token valid (get_fund_limits).
  2  The holding is in the live Dhan book with shares, and is not a v2 (POS-V2) holding - v2
     has no stop by design.
  3  It has resting stop legs.
  4  The new trigger sits below LTP by at least 0.5 x ATR(D) - a SELL stop at or near the price
     fires at once, which would be an exit placed by accident.
  5  LOWERING (the rule Jay set): the shares held fit the per-trade rule at the new stop, from
     cost (gap_risk.lower_stop_qty, the same 5% slack the guard uses). Sell the excess FIRST.
     A stop that stays at or above cost gives back profit, not capital: no cut needed.
  6  The stop legs cover no more shares than are held - after a sale the legs must be shrunk to
     the holding on Dhan (a leg for shares you no longer own is an order that cannot fill).
WARNINGS (shown, never blocking): shares with no stop at all; the stop below today's trail
level (the 15:45 trail raises a positional stop back up to it); the disaster below the thesis
by more than the house 1 x ATR(D); results within 7 days with a gap-sized holding below the
shares held; the worst 2-year gap opening below the new stop.

Raising a stop runs through the same path with conditions 1-4 and 6 only (a tighter stop needs
no cut). Nothing here ever sells, cancels or places a new order - it modifies resting stops.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_GAP_ATR = 0.5            # condition 4: the new trigger must be this far below LTP

log = logging.getLogger("stop_guard")      # same log file as the guard: one stop audit trail


def _chk(name, ok, detail, block=True):
    return {"name": name, "ok": bool(ok), "detail": detail, "block": block}


def plan(sym: str, new_stop: float, dhan=None, book=None, legs_by=None) -> dict:
    """Checks for moving sym's Disaster SL to new_stop. dhan/book/legs_by are injectable for
    tests; by default everything is read live."""
    import gap_risk as gr
    import house_policy as hp
    sym = str(sym).upper().strip()
    out = {"symbol": sym, "new_stop": float(new_stop), "checks": [], "legs": [], "ok": False,
           "direction": "", "dhan": dhan}
    C = out["checks"]
    try:
        import gtt_auto_shield as gas
    except Exception as e:
        C.append(_chk("Dhan", False, f"order module unavailable: {e}"))
        return out

    # 1 broker + token
    if dhan is None:
        dhan = gas.connect_dhan()
        out["dhan"] = dhan
        if dhan is None:
            C.append(_chk("Dhan reachable", False, "could not connect"))
            return out
        try:
            fl = dhan.get_fund_limits()
            okt = isinstance(fl, dict) and fl.get("status") == "success"
        except Exception as e:
            okt, fl = False, e
        C.append(_chk("Dhan reachable, token valid", okt, "ok" if okt else f"token/API check failed: {fl}"))
        if not okt:
            return out
    else:
        C.append(_chk("Dhan reachable, token valid", True, "ok"))

    # 2 the holding
    if book is None:
        import briefing_book as bb
        book, src = bb.load_book()
        if src != "dhan":
            C.append(_chk("Live holding", False, "Dhan holdings unavailable - refusing to act on journal quantities"))
            return out
    b = next((x for x in book if x["symbol"] == sym), None)
    if not b or not (b.get("qty") or 0) > 0:
        C.append(_chk("Live holding", False, f"{sym} is not in the live Dhan book"))
        return out
    if str(b.get("setup") or "").upper().startswith("POS-V2"):
        C.append(_chk("Live holding", False, "a v2 holding - v2 has no stop by design (Clenow exits)"))
        return out
    qty, avg, ltp = float(b["qty"]), float(b["avg"] or 0), float(b.get("broker_ltp") or 0)
    C.append(_chk("Live holding", qty > 0 and avg > 0 and ltp > 0,
                  f"{int(qty)} sh @ ₹{avg:,.2f}, LTP ₹{ltp:,.2f}"))
    out.update({"qty": qty, "avg": avg, "ltp": ltp})

    # 3 resting stop legs
    if legs_by is None:
        legs_by = gas._live_oco_sl_legs(dhan)
        if legs_by is None:
            C.append(_chk("Resting stop legs", False, "could not read the forever orders"))
            return out
    legs = legs_by.get(sym) or []
    covered = sum(int(l.get("sl_qty") or 0) for l in legs)
    cur = min((float(l["sl_trigger"]) for l in legs), default=None)
    C.append(_chk("Resting stop legs", bool(legs),
                  (f"{len(legs)} leg(s), {covered} sh covered, lowest trigger ₹{cur:,.2f}" if legs
                   else "none - place a stop on Dhan first")))
    if not legs:
        return out
    out.update({"legs": legs, "covered": covered, "current": cur})
    # the trigger that will actually be sent: on the exchange's half-rupee grid, limit 0.5% below
    # (the trail's own call). Every check below runs on THIS number, not the typed one.
    new_stop, limit = gas.stop_prices(sym, float(new_stop))
    out.update({"new_stop": new_stop, "trigger": new_stop, "limit": limit})
    out["direction"] = "lower" if new_stop < cur else ("raise" if new_stop > cur else "same")
    if out["direction"] == "same" and all(abs(float(l["sl_trigger"]) - new_stop) < 0.01 for l in legs):
        C.append(_chk("A change", False, "every leg is already at this trigger"))
        return out

    try:
        from ai_risk_manager import get_atr
        atr = float(get_atr(sym) or 0) or None
    except Exception:
        atr = None
    out["atr"] = atr

    # 4 not into the price
    gap_need = MIN_GAP_ATR * (atr or 0.0)
    C.append(_chk("Below the price", new_stop < ltp - gap_need,
                  f"₹{new_stop:,.2f} vs LTP ₹{ltp:,.2f}" + (f" (needs ≥ {MIN_GAP_ATR:g}×ATR = ₹{gap_need:,.2f} below)"
                                                           if atr else " (ATR unavailable: strict < LTP)")))

    # 5 the rule - only a lowering pays in shares
    cap, _ = hp.sizing_capital()
    budget = cap * hp.risk_pct_for(sym) / 100.0
    out["budget"] = budget
    import stop_guard as sg
    allowed, sell = gr.lower_stop_qty(qty, avg, new_stop, budget * sg.RULE_SLACK)
    out.update({"allowed": allowed, "sell_first": sell})
    if out["direction"] == "lower":
        if new_stop >= avg:
            C.append(_chk("Shares fit the rule at the new stop", True,
                          f"still above cost (₹{avg:,.2f}) - gives back profit, not capital"))
        else:
            C.append(_chk("Shares fit the rule at the new stop", allowed is not None and qty <= allowed,
                          f"loss at ₹{new_stop:,.2f} = ₹{qty * (avg - new_stop):,.0f} vs rule ₹{budget:,.0f}: "
                          f"{allowed} sh allowed, you hold {int(qty)}"
                          + (f" - SELL {sell} first" if sell else "")))

    # 6 legs no larger than the holding
    C.append(_chk("Stop legs ≤ holding", covered <= qty,
                  f"legs cover {covered} sh, you hold {int(qty)}"
                  + ("" if covered <= qty else f" - shrink the legs by {covered - int(qty)} sh on Dhan first")))

    # warnings
    if covered < qty:
        C.append(_chk("Every share covered", False, f"{int(qty) - covered} sh have no stop at all", block=False))
    try:
        import sl_board as slb
        df, _ = slb.build(symbols=[sym])
        r = df.iloc[0].to_dict() if len(df) else {}
    except Exception:
        r = {}
    out["row"] = r
    trail_lvl = None
    if r.get("chand") and atr:
        trail_lvl = min(float(r["chand"]), ltp - hp.DHAN_STOP_MIN_ATR * atr)
    if trail_lvl and new_stop < trail_lvl and "pos" in str(r.get("plan", "")).lower():
        C.append(_chk("Trail", False, f"below today's trail level ₹{trail_lvl:,.2f}: the 15:45 trail raises a "
                                      "positional stop back up to it", block=False))
    th = r.get("thesis")
    if th and atr and new_stop < th - hp.THESIS_TO_DISASTER_ATR * atr - 0.01:
        C.append(_chk("Two-tier", False, f"more than {hp.THESIS_TO_DISASTER_ATR:g}×ATR below the thesis ₹{th:,.2f}",
                      block=False))
    gw = r.get("gap_worst")
    if gw is not None:
        fill, loss, fit, through = gr.gap_numbers(qty, avg, ltp, new_stop, gw, budget)
        if through and loss is not None and loss > budget * sg.RULE_SLACK:
            C.append(_chk("Gap", False, f"its worst gap ({gw:.1f}%) opens at ₹{fill:,.2f}, below the new stop - "
                                        f"loss ₹{loss:,.0f}; {fit} sh fit even that", block=False))
    if r.get("earn_soon") and r.get("gap_fit_qty") is not None and r["gap_fit_qty"] < qty:
        C.append(_chk("Results", False, f"results on {r.get('earn_date')} - gap-sized holding "
                                        f"{int(r['gap_fit_qty'])} sh", block=False))

    out["ok"] = all(c["ok"] for c in C if c["block"])
    return out


def _journal_write(sym: str, new_stop: float) -> str:
    import journal_path as jp
    try:
        con = sqlite3.connect(jp.JOURNAL_DB)
        n = con.execute("UPDATE journal SET stoploss=?, manual_sl_override=? WHERE UPPER(symbol)=? "
                        "AND UPPER(status)='OPEN'", (new_stop, new_stop, sym)).rowcount
        con.commit()
        con.close()
        return f"journal: {n} row(s)"
    except Exception as e:
        log.warning("stop_change: journal write failed for %s: %s", sym, e)
        return f"journal write FAILED ({e})"


def apply(sym: str, new_stop: float, dhan=None, book=None, legs_by=None, reread=None) -> dict:
    """Re-check on fresh data; modify every leg only when every BLOCK check passes."""
    p = plan(sym, new_stop, dhan=dhan, book=book, legs_by=legs_by)
    res = {"plan": p, "done": [], "failed": [], "notes": [], "ok": False}
    if not p["ok"]:
        res["notes"].append("not sent: " + "; ".join(c["name"] for c in p["checks"] if c["block"] and not c["ok"]))
        return res
    import gtt_auto_shield as gas
    d = p["dhan"]
    sym = p["symbol"]
    trig, lim = p["trigger"], p["limit"]
    if trig >= p["ltp"]:
        res["notes"].append(f"not sent: on the tick the trigger {trig} is not below LTP")
        return res
    for leg in p["legs"]:
        try:
            resp = d.modify_forever(order_id=leg["order_id"], order_flag=leg.get("flag", "OCO"),
                                    order_type=d.LIMIT, leg_name=leg.get("leg_name") or "STOP_LOSS_LEG",
                                    quantity=leg["sl_qty"], price=lim, trigger_price=trig,
                                    disclosed_quantity=0, validity="DAY")
            ok = isinstance(resp, dict) and resp.get("status") == "success"
        except Exception as e:
            ok, resp = False, str(e)
        (res["done"] if ok else res["failed"]).append(
            {"order_id": leg["order_id"], "from": leg["sl_trigger"], "to": trig, "resp": "" if ok else str(resp)[:200]})
        log.info("stop_change %s %s: %s -> %s ok=%s %s", sym, leg["order_id"], leg["sl_trigger"], trig, ok,
                 "" if ok else resp)

    # read back what Dhan now holds - the baseline is the broker's truth, not our intent
    try:
        fresh = reread() if reread else gas._live_oco_sl_legs(d)
    except Exception:
        fresh = None
    legs_now = (fresh or {}).get(sym) or []
    res["readback"] = [(l["order_id"], l["sl_trigger"]) for l in legs_now]
    res["ok"] = bool(res["done"]) and not res["failed"]
    if res["done"]:
        res["notes"].append(_journal_write(sym, trig))
        try:
            import stop_guard as sg
            st = sg.load_state()
            base = sg.evaluate(sym, legs_now or p["legs"], p["qty"], p["avg"], p["ltp"], p.get("atr"),
                               p["budget"], None)["new_base"]
            st[sym] = base
            sg._save_state(st)
            sg._event({"ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "symbol": sym, "kind": "WEB",
                       "from": p["current"], "to": trig, "qty": p["qty"], "allowed": p.get("allowed"),
                       "action": f"modified {len(res['done'])} leg(s)" + (f", {len(res['failed'])} FAILED"
                                                                         if res["failed"] else ""),
                       "note": "changed from Web Commander after the checks passed"})
        except Exception as e:
            res["notes"].append(f"guard baseline NOT updated ({e}) - the guard may flag this change")
        try:
            import stop_history as sh
            sh._upsert([{"date": datetime.now().strftime("%Y-%m-%d"), "symbol": sym, "qty": p["qty"],
                         "avg": p["avg"], "ltp": p["ltp"], "atr": p.get("atr"), "initial": None,
                         "thesis": (p.get("row") or {}).get("thesis"), "disaster": trig, "chand": None,
                         "source": "web"}])
        except Exception as e:
            res["notes"].append(f"stop history not written ({e})")
        try:
            from digest_common import send
            send(f"🛠 STOP CHANGED · {sym}: ₹{p['current']:g} -> ₹{trig:g} on {len(res['done'])} leg(s) "
                 f"({p['direction']}), {int(p['qty'])} sh held" + (f" · {len(res['failed'])} leg(s) FAILED"
                                                                  if res["failed"] else ""))
        except Exception:
            pass
    return res
