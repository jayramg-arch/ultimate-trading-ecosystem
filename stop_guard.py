"""stop_guard.py - no Disaster SL comes down until the quantity has (29-Oct-2026).

Jay: "the system should force me to reduce the quantity, before I lower any disaster SL for
any stock." The stop history showed why: 51 widenings on the open book added Rs 1,90,108 of
risk at the shares held (M&MFIN x7, -32% open). A wider stop with the same shares is a bigger
bet; the house risk rule (0.5% stock / 0.75% ETF of sizing capital, house_policy) only holds
if every widening is paid for in shares.

WHAT IT DOES. Each run reads the resting Dhan stop legs (gtt_auto_shield._live_oco_sl_legs:
every OCO and SINGLE sell stop, one entry per order) and the live holdings, and compares each
leg with its BASELINE in data/stop_guard.json:
  * a stop that went UP (the 15:45 trail, a hand tighten) -> the baseline follows it;
  * a stop that went DOWN, or a new stop below the old floor that adds no cover
    (cancel-and-replace lower) -> a LOWERING. It is ACCEPTED only when the shares now held
    fit the per-trade rule at the new stop, from cost (gap_risk.lower_stop_qty) - i.e. you
    sold first. Otherwise it is a VIOLATION: one Telegram per new level, naming the shares
    to sell, and - with STOP_GUARD_REVERT=1 - the lowered leg is modified back to its
    approved trigger (a tighten, the trailer's own direction and call).
  * a stop at or above cost locks a profit: lowering it costs no risk from cost, accepted.
  * a new stop over shares that had none (the cover pass, a fresh runner GTT) is cover, not
    a widening: accepted.

NEVER: sells, cancels, or moves a stop down. It never moves a stop UP to a level the market
is already at or below (LTP within 0.5 x ATR of the approved trigger): putting that stop back
would sell the position at once, so it alarms "the approved stop is already through - that
is an exit review" and leaves the order alone. POS-V2 holdings (no stop by design) and cash
parks are skipped.

How the quantity gets cut: by you, on Dhan (sell the excess, then shrink the stop legs to the
holding). The SL Dashboard's Edit tab ("Lower a Disaster SL") gives the numbers first. Once
the holding is at or below the allowed quantity the next run accepts the lower stop.

REVERT IS OFF BY DEFAULT (STOP_GUARD_REVERT=0): the guard alarms for a session first, so a
mis-detection costs a message, not a broker modify. Turn it on in .env once the alarms read
right. Runs from the in-app scheduler (scheduler_daemon job stop_guard) at 09:05, every 15
minutes in the session, 16:20 and 21:00 - stops are edited after hours too.

CLI: python stop_guard.py            one check (alarm/revert as configured)
     python stop_guard.py --dry-run  report only - no state write, no Telegram, no modify
     python stop_guard.py --init     set every baseline to the stops resting NOW
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "data", "stop_guard.json")
EVENTS = os.path.join(HERE, "logs", "stop_guard_events.csv")
TOL = 0.002                 # moves under 0.2% are rounding (same as stop_history.MOVE_TOL)
RULE_SLACK = 1.05           # the same 5% slack sl_board uses for "over the rule"
THROUGH_ATR = 0.5           # approved trigger this close to LTP = already through, never revert
EV_COLS = ["ts", "symbol", "kind", "order_id", "from", "to", "qty", "allowed", "sell_first", "action", "note"]

log = logging.getLogger("stop_guard")
if not log.handlers:
    os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
    _h = RotatingFileHandler(os.path.join(HERE, "logs", "stop_guard.log"), maxBytes=1_000_000, backupCount=3,
                             encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


def revert_enabled() -> bool:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass
    return os.getenv("STOP_GUARD_REVERT", "0").strip() == "1"


def load_state() -> dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _save_state(d: dict) -> None:
    from io_utils import atomic_write_text
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    atomic_write_text(STATE, json.dumps(d, indent=1, sort_keys=True))


def _event(row: dict) -> None:
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    new = not os.path.exists(EVENTS)
    with open(EVENTS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EV_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({**{c: "" for c in EV_COLS}, **row})


def load_events():
    import pandas as pd
    try:
        return pd.read_csv(EVENTS)
    except Exception:
        return pd.DataFrame(columns=EV_COLS)


# ── the decision, pure (tested without a broker) ─────────────────────────────────────────

def evaluate(sym: str, legs: list[dict], qty: float, avg: float, ltp: float, atr: float | None,
             budget: float, base: dict | None) -> dict:
    """One holding. legs: [{order_id, sl_trigger, sl_qty, ...}]. base: the stored baseline or
    None. Returns {'kind', 'new_base', 'lowered': [(leg, approved_trigger)], 'floor', 'allowed',
    'sell_first', 'through', 'msg'} - kind is NEW, OK, RAISED, ACCEPTED, VIOLATION."""
    from gap_risk import lower_stop_qty
    cur = {str(l["order_id"]): float(l["sl_trigger"]) for l in legs if l.get("sl_trigger")}
    covered = sum(int(l.get("sl_qty") or 0) for l in legs)
    floor = min(cur.values()) if cur else None
    snap = {"orders": cur, "floor": floor, "covered": covered, "qty": qty,
            "set": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if not base or not base.get("orders"):
        return {"kind": "NEW", "new_base": snap, "lowered": [], "floor": floor, "msg": ""}

    b_orders = {str(k): float(v) for k, v in base["orders"].items()}
    b_floor = float(base.get("floor") or min(b_orders.values()))
    b_cov = int(base.get("covered") or 0)
    lowered = []
    for l in legs:
        oid, trig = str(l["order_id"]), float(l["sl_trigger"])
        if oid in b_orders:
            if trig < b_orders[oid] * (1 - TOL):
                lowered.append((l, b_orders[oid]))
        elif trig < b_floor * (1 - TOL) and covered <= b_cov:
            lowered.append((l, b_floor))         # cancel-and-replace lower, no added cover
    if not lowered:
        kind = "RAISED" if (floor and floor > b_floor * (1 + TOL)) else "OK"
        return {"kind": kind, "new_base": snap, "lowered": [], "floor": floor, "msg": ""}

    new_floor = min(float(l["sl_trigger"]) for l, _ in lowered)
    allowed, sell = lower_stop_qty(qty, avg, new_floor, budget * RULE_SLACK)
    if allowed is not None and qty <= allowed:
        return {"kind": "ACCEPTED", "new_base": snap, "lowered": lowered, "floor": new_floor,
                "allowed": allowed, "sell_first": 0,
                "msg": (f"{sym}: stop lowered to {new_floor:g} - accepted, {int(qty)} sh fit the rule at that level"
                        if new_floor < avg else f"{sym}: stop lowered to {new_floor:g}, still above cost - accepted")}
    appr = max(a for _, a in lowered)
    through = bool(ltp and appr >= ltp - THROUGH_ATR * (atr or 0.0))
    return {"kind": "VIOLATION", "new_base": None, "lowered": lowered, "floor": new_floor,
            "allowed": allowed, "sell_first": sell, "through": through,
            "msg": (f"{sym}: Disaster SL lowered to {new_floor:g} with {int(qty)} sh. At that stop the rule "
                    f"(Rs {budget:,.0f}) allows {allowed} sh - sell {sell} first, or the stop goes back to "
                    f"{appr:g}." + (" The approved stop is already at/through the price (LTP "
                                     f"{ltp:g}) - that is an exit review, not a widening." if through else ""))}


# ── the run ──────────────────────────────────────────────────────────────────────────────

def _send(text: str) -> None:
    try:
        from digest_common import send
        send(text)
    except Exception as e:
        log.warning("telegram failed: %s", e)


def check(dry_run: bool = False, init: bool = False) -> dict:
    import briefing_book as bb
    import gtt_auto_shield as gas
    import house_policy as hp
    try:
        from ai_risk_manager import get_atr
    except Exception:
        get_atr = None

    book, src = bb.load_book()
    if src != "dhan":
        log.error("holdings not from Dhan (%s) - guard skipped", src)
        return {"ok": False, "why": "Dhan holdings unavailable"}
    dhan = gas.connect_dhan()
    legs_by = gas._live_oco_sl_legs(dhan) if dhan else None
    if legs_by is None:
        log.error("forever orders unreadable - guard skipped")
        return {"ok": False, "why": "Dhan forever orders unreadable"}

    state = {} if init else load_state()
    revert = revert_enabled() and not dry_run
    cap, _ = hp.sizing_capital()
    out = {"ok": True, "checked": 0, "violations": [], "accepted": [], "reverted": [], "new": 0}
    for b in book:
        sym = b["symbol"]
        if str(b.get("setup") or "").upper().startswith("POS-V2"):
            continue                                # v2: no stop by design (Clenow rules)
        legs = legs_by.get(sym) or []
        if not legs:
            continue
        out["checked"] += 1
        atr = None
        if get_atr:
            try:
                atr = float(get_atr(sym)) or None
            except Exception:
                atr = None
        budget = cap * hp.risk_pct_for(sym) / 100.0
        r = evaluate(sym, legs, float(b["qty"] or 0), float(b["avg"] or 0), float(b.get("broker_ltp") or 0),
                     atr, budget, state.get(sym))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        if r["kind"] == "NEW":
            out["new"] += 1
        if r["kind"] in ("NEW", "OK", "RAISED", "ACCEPTED"):
            if r["kind"] == "ACCEPTED":
                out["accepted"].append(r["msg"])
                if not dry_run:
                    _event({"ts": ts, "symbol": sym, "kind": "ACCEPTED", "to": r["floor"], "qty": b["qty"],
                            "allowed": r.get("allowed"), "action": "baseline moved down", "note": r["msg"]})
                    _send("🟢 STOP GUARD · " + r["msg"])
            state[sym] = r["new_base"]
            continue

        # VIOLATION
        prev = state.get(sym) or {}
        first = prev.get("alarmed_floor") != r["floor"]
        out["violations"].append(r["msg"])
        action = "alarm"
        if revert and not r.get("through"):
            done = []
            for leg, appr in r["lowered"]:
                trig, lim = gas.stop_prices(sym, appr)
                try:
                    resp = dhan.modify_forever(order_id=leg["order_id"], order_flag=leg.get("flag", "OCO"),
                                               order_type=dhan.LIMIT, leg_name=leg.get("leg_name") or "STOP_LOSS_LEG",
                                               quantity=leg["sl_qty"], price=lim, trigger_price=trig,
                                               disclosed_quantity=0, validity="DAY")
                    okm = isinstance(resp, dict) and resp.get("status") == "success"
                except Exception as e:
                    okm, resp = False, str(e)
                done.append(f"{leg['order_id']} {'->' if okm else 'FAILED ->'} {trig:g}")
                log.info("revert %s %s: %s -> %s ok=%s resp=%s", sym, leg["order_id"], leg["sl_trigger"], trig, okm,
                         resp if not okm else "")
            action = "reverted: " + "; ".join(done)
            out["reverted"].append(f"{sym}: {action}")
        log.warning("VIOLATION %s (%s)", r["msg"], action)
        if not dry_run:
            _event({"ts": ts, "symbol": sym, "kind": "VIOLATION",
                    "from": prev.get("floor"), "to": r["floor"], "qty": b["qty"], "allowed": r.get("allowed"),
                    "sell_first": r.get("sell_first"), "action": action, "note": r["msg"]})
            if first or action.startswith("reverted"):
                _send("🔴 STOP GUARD · " + r["msg"] + ("" if action == "alarm" else "\n" + action))
            prev["alarmed_floor"] = r["floor"]
            state[sym] = prev                       # baseline unchanged: the approved stop stands
    if not dry_run:
        _save_state(state)
    out["revert"] = revert
    return out


def status_lines() -> list[str]:
    """For the evening digest: today's guard events."""
    ev = load_events()
    if ev.empty:
        return ["STOP GUARD: no lowered stop on record" + ("" if revert_enabled() else " (alarm mode)")]
    today = datetime.now().strftime("%Y-%m-%d")
    t = ev[ev["ts"].astype(str).str.startswith(today)]
    v = t[t["kind"] == "VIOLATION"]
    a = t[t["kind"] == "ACCEPTED"]
    mode = "revert ON" if revert_enabled() else "alarm mode - STOP_GUARD_REVERT=0"
    L = [f"STOP GUARD ({mode}): {v['symbol'].nunique()} lowered without the cut, {len(a)} accepted today"]
    for s, g in v.groupby("symbol"):
        r = g.iloc[-1]
        L.append(f"  {s}: lowered to {r['to']} - allowed {r['allowed']} sh, sell {r['sell_first']} first ({r['action']})")
    return L


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Hold every Disaster SL until the quantity has been cut.")
    ap.add_argument("--dry-run", action="store_true", help="report only: no state write, Telegram or modify")
    ap.add_argument("--init", action="store_true", help="set every baseline to the stops resting now")
    a = ap.parse_args()
    r = check(dry_run=a.dry_run, init=a.init)
    if not r.get("ok"):
        print("STOP GUARD skipped:", r.get("why"))
        return 1
    print(f"STOP GUARD: {r['checked']} holdings checked, {r['new']} new baseline(s), "
          f"revert {'ON' if r['revert'] else 'off'}")
    for m in r["accepted"]:
        print("  ACCEPTED ", m)
    for m in r["violations"]:
        print("  VIOLATION", m)
    for m in r["reverted"]:
        print("  REVERTED ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
