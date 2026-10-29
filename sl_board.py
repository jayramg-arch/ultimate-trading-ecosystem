"""sl_board.py - every stop and target of every holding, in one frame (28-Oct-2026).

Jay: "To have all the SL activity in one place." Each morning he opened the Portfolio
watchlist on TradingView, read the thesis and disaster levels off v67 symbol by symbol and
fine-tuned some of them. This module puts the same levels for the whole book in one table,
for the SL DASHBOARD page (commander_pages/sl_dashboard.py). No Streamlit here.

Every level comes from the code that already owns it, so the page cannot drift from v67,
Risk Shield or the Dhan order book:
  LTP, qty, avg        Dhan holdings (briefing_book.load_book); journal when Dhan is down
  Disaster SL, T1, T2  the RESTING Dhan orders (order_levels) - what would actually fire.
                       Journal stoploss/target1/target2 (synced 16:30) when the order book
                       cannot be read
  Initial SL           journal initial_sl; the policy R-unit stop when none was recorded
  Thesis SL            journal thesis_sl (close-basis exit, never an order)
  Chandelier           tv_push_v67_trail.compute_book() = risk_common.holding_chandelier,
                       the exact number v67 draws and Risk Shield shows
  Rec SL (3xATR)       house_policy.rec_dhan_stop with the Noise Watchdog ATR, as on v67
  Rec T1/T2            canon off the R unit: swing 2R/4R, positional 3R/5R
  EMA20 (Daily)        EMA(20) of the daily closes

Chandelier and Rec SL are DIFFERENT questions. The Chandelier is the TRAIL: the highest
close since entry (14 or 22 bars) minus a multiple of ATR - it only ever rises, and a close
below it says the trend has given back too much. The Rec SL is a FLOOR on distance: a resting
order closer than 3xATR to LTP sits inside ordinary noise and gets swept, so it recommends
LTP - 3xATR with the share count that keeps today's rupee risk. It appears only when the Dhan
stop is closer than that, and it never tightens.

RISK (the reason the page exists). The house rule is a fixed rupee loss per trade -
house_policy.risk_pct_for (stock 0.5%, ETF 0.75%, add 1% of sizing capital). Widening a stop
without cutting shares breaks it. For each holding the frame carries the loss if the Dhan stop
fills (from cost, and from LTP) and the share count that brings that loss back inside the
rule at the CURRENT stop: a wider stop has to come with a smaller position.
"""
from __future__ import annotations

import math
import os
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

# Every level the chart draws, in drawing order: (key, label, colour, marker symbol, size).
LEVELS = [
    # targets: one arrow, one size, told apart by colour
    ("rec_t2",    "Rec T2",            "#60A5FA", "arrow-up",         14),
    ("rec_t1",    "Rec T1",            "#2DD4BF", "arrow-up",         14),
    ("t2",        "T2 (Dhan)",         "#A3E635", "arrow-up",         14),
    ("t1",        "T1 (Dhan)",         "#22C55E", "arrow-up",         14),
    ("ema20",     "EMA20 (D)",         "#F59E0B", "line-ns",          20),
    # stops: one dot, one size, told apart by colour
    ("initial",   "Initial SL",        "#9CA3AF", "circle",           12),
    ("chand",     "Chandelier",        "#22D3EE", "circle",           12),
    ("rec_sl",    "Rec SL 3×ATR",      "#D946EF", "circle",           12),
    # where this stock's WORST overnight gap of the last 2 years would open from LTP - gap_risk.py
    ("gapw",      "Worst-gap open (2y)", "#FB7185", "triangle-down",  12),
    ("disaster",  "Disaster SL (Dhan)", "#EF4444", "circle",          12),
    ("thesis",    "Thesis SL",         "#F97316", "circle",           12),
    ("avg",       "Avg entry",         "#FACC15", "square",           11),
    ("ltp",       "LTP",               "#F8FAFC", "diamond-wide",     15),
]


def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError):
        return None


def _journal_rows() -> dict:
    import journal_path as jp
    con = sqlite3.connect(jp.JOURNAL_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT * FROM journal WHERE UPPER(status)='OPEN'").fetchall()
    finally:
        con.close()
    return {str(r["symbol"]).strip().upper(): dict(r) for r in rows}


def _dhan_orders() -> dict | None:
    """{SYMBOL: [legs]} of resting SELL orders, or None when the book can't be read."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
        import order_levels as ol
        from dhan_auth import ensure_valid_token
        from dhanhq import dhanhq
        return ol.fetch_live_orders(dhanhq(client_id=os.getenv("DHAN_CLIENT_ID"),
                                           access_token=ensure_valid_token()))
    except Exception:
        return None


def thesis_state(close, thesis, atr) -> str:
    """'BROKEN' when the last Daily close is below the thesis, 'NEAR' within 0.5xATR,
    'ok' above, '' with no thesis. The thesis is a CLOSE rule, so the close decides."""
    if not thesis or not close:
        return ""
    if close < thesis:
        return "BROKEN"
    if atr and (close - thesis) <= 0.5 * atr:
        return "NEAR"
    return "ok"


def risk_numbers(qty, entry, ltp, stop, budget):
    """(loss if the stop fills from cost, open risk from LTP, shares that fit the budget at
    this stop). Loss from cost <= 0 = the stop has locked a profit; fit = None then."""
    if not (qty and entry and ltp and stop):
        return None, None, None
    loss = qty * (entry - stop)
    open_risk = qty * max(ltp - stop, 0.0)
    fit = None
    if stop < entry and budget:
        fit = int(budget // (entry - stop))
    return loss, open_risk, fit


def build(symbols: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """(one row per holding, meta). meta: source, orders_ok, capital, budget per trade %,
    heat budget, exposure tier, v2 count skipped, failures."""
    import briefing_book as bb
    import data_provider as dp
    import house_policy as hp
    import order_levels as ol
    import risk_common as rc
    import tv_push_v67_trail as v67
    from ai_risk_manager import get_atr

    book, source = bb.load_book()
    jr = _journal_rows()
    v2 = {s for s, r in jr.items() if str(r.get("setup") or "").upper().startswith("POS-V2")}
    book = [b for b in book if b["symbol"] not in v2]
    if symbols:
        want = {s.upper() for s in symbols}
        book = [b for b in book if b["symbol"] in want]

    orders = _dhan_orders()
    try:
        chand = {c["symbol"]: c for c in v67.compute_book()}
    except Exception as e:
        chand, chand_err = {}, str(e)
    else:
        chand_err = ""
    cap, cap_src = hp.sizing_capital()
    try:
        import open_risk
        heat = open_risk.budget()
    except Exception:
        heat = {}

    syms = [b["symbol"] for b in book]
    # 2y: the gap tail (gap_risk) needs ~500 sessions; EMA20 and the close are unaffected
    daily = dp.fetch_batch_ohlcv(syms, period="2y", interval="1d", use_cache=True, auto_adjust=True) if syms else {}
    plans = load_plans()
    import gap_risk as gr

    # The thesis is judged on the last CLOSE. Outside the session the broker LTP IS that
    # close (the cached daily bar can lag a day - SAILIFE read 26-Oct on the 28th); in the
    # session the cached daily bar is used only when it is the last completed session.
    try:
        import nse_calendar as nc
        sess_open = nc.is_session_open()
        last_sess = nc.last_completed_session()
    except Exception:
        sess_open, last_sess = False, None

    rows, fails = [], []
    for b in book:
        s = b["symbol"]
        j = jr.get(s, {})
        d = daily.get(s)
        close = ema20 = None
        if d is not None and not d.empty and "Close" in d.columns:
            c = d["Close"].dropna()
            if len(c):
                close = float(c.iloc[-1])
                ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
        ltp = _f(b.get("broker_ltp")) or close
        close_src = "daily bar"
        if not sess_open and _f(b.get("broker_ltp")):
            close, close_src = ltp, "Dhan LTP (market closed)"
        elif (d is not None and close is not None and last_sess is not None
              and pd.Timestamp(d.index[-1]).date() < last_sess):
            close_src = "STALE daily bar " + str(pd.Timestamp(d.index[-1]).date())
        qty = _f(b.get("qty")) or _f(j.get("quantity"))
        avg = _f(b.get("avg")) or _f(j.get("buy_price"))
        if not (ltp and qty and avg):
            fails.append(s)
            continue
        try:
            atr = float(get_atr(s)) or None
        except Exception:
            atr = None

        # what would actually fire: the resting Dhan legs; journal (16:30 sync) as fallback
        warn = ""
        if orders is not None and s in orders:
            stop, t1, t2 = ol.derive_sl_targets(orders[s], ltp)
            warn = ol.stop_report(orders[s], ltp, qty)
            lv_src = "dhan"
        elif orders is not None:
            stop, t1, t2 = 0.0, 0.0, 0.0
            warn = "no resting stop at Dhan"
            lv_src = "dhan"
        else:
            stop, t1, t2 = (_f(j.get("stoploss")) or 0.0, _f(j.get("target1")) or 0.0,
                            _f(j.get("target2")) or 0.0)
            lv_src = "journal"
        stop, t1, t2 = _f(stop), _f(t1), _f(t2)

        jrow = dict(j)
        jrow.setdefault("buy_price", avg)
        r_stop, r_pol = rc.r_unit_stop(jrow, atr)
        ini = _f(j.get("initial_sl"))
        ini_pol = False
        if not (ini and ini < avg) and r_stop:
            ini, ini_pol = round(r_stop, 2), True
        rt1, rt2 = (v67.canon_targets(jrow, atr) if atr else (None, None))

        rec = hp.rec_dhan_stop(ltp, stop, atr, qty) if atr else None
        ch = chand.get(s, {})
        swing = "swing" in str(j.get("timeframe") or "").lower()
        budget = cap * hp.risk_pct_for(s) / 100.0
        loss, open_r, fit = risk_numbers(qty, avg, ltp, stop, budget)
        thesis = _f(j.get("thesis_sl"))
        r_unit = (avg - r_stop) if (r_stop and r_stop < avg) else None
        dist = (ltp - stop) / atr if (stop and atr) else None

        # gap risk: this stock's own overnight gaps. The STRESS case is its worst gap of the last
        # two years repeated from today's price - on the live book the 1-in-100 gap (-1.6..-3.8%)
        # sits inside every stop, while the news days that took stops out (AUBANK -8%) are the
        # tail, so a p99 basis would read "no gap risk" on every name.
        gs = gr.gap_stats(d) if d is not None else {}
        g_fill, g_loss, g_fit, g_through = gr.gap_numbers(qty, avg, ltp, stop, gs.get("gap_worst"), budget)
        # planned quantity (a plan, never an order): risk recomputed as if the trim were done
        # results inside the hold: the one binary event a price chart cannot see. Read-only cache
        # (earnings_calendar refreshes it nightly, Phase 8a); unknown = None, never "no results".
        try:
            import earnings_calendar as ec
            e_days, e_date = ec.days_to_earnings(s), ec.next_earnings(s)
        except Exception:
            e_days = e_date = None
        pl = plans.get(s) or {}
        pq = _f(pl.get("plan_qty"))
        pq = pq if (pq and pq < qty) else None
        p_loss = (pq * (avg - stop)) if (pq and stop) else None

        rows.append({
            "symbol": s, "plan": "Swing" if swing else "Positional",
            "plan_src": (ch.get("tt_label") or "") if ch else "",
            "qty": qty, "avg": avg, "ltp": ltp, "close": close,
            "pnl_pct": (ltp / avg - 1) * 100,
            "r_now": ((ltp - avg) / r_unit) if r_unit else None,
            "atr": atr, "atr_pct": (atr / ltp * 100) if atr else None,
            "ema20": ema20,
            "initial": ini, "initial_policy": ini_pol,
            "thesis": thesis, "thesis_state": thesis_state(close, thesis, atr), "close_src": close_src,
            "thesis_vs_dhan": ("above Dhan stop" if (thesis and stop and thesis > stop)
                               else "BELOW Dhan stop (superseded)" if (thesis and stop) else ""),
            "disaster": stop, "dist_atr": dist, "noise": hp.noise_band(dist),
            "rec_sl": rec[0] if rec else None, "rec_qty": rec[1] if rec else None,
            "chand": _f(ch.get("level")), "chand_mult": ch.get("mult"),
            "chand_breach": bool(_f(ch.get("level")) and _f(ch.get("level")) >= ltp),
            "t1": t1, "t2": t2, "rec_t1": rt1, "rec_t2": rt2,
            "budget": budget, "loss_if_stopped": loss, "open_risk": open_r, "fit_qty": fit,
            "over_budget": bool(loss and loss > budget * 1.05),
            "widened_pct": (((avg - stop) / (avg - ini) - 1) * 100
                            if (stop and ini and ini < avg and stop < avg) else None),
            "levels_src": lv_src, "order_warn": warn,
            "gap_p95": gs.get("gap_p95"), "gap_p99": gs.get("gap_p99"), "gap_worst": gs.get("gap_worst"),
            "gap_worst_date": gs.get("gap_worst_date"), "gaps_3pct": gs.get("gaps_3pct"),
            "gap99": (ltp * (1 + gs["gap_p99"] / 100.0)) if gs.get("gap_p99") is not None else None,
            "gapw": (ltp * (1 + gs["gap_worst"] / 100.0)) if gs.get("gap_worst") is not None else None,
            "gap_fill": g_fill, "gap_loss": g_loss, "gap_fit_qty": g_fit, "gap_through": g_through,
            "gap_over": bool(g_loss and g_loss > budget * 1.05),
            "plan_qty": pq, "plan_note": pl.get("note") or "", "plan_set": pl.get("set") or "",
            "plan_loss": p_loss,
            "earn_days": e_days, "earn_date": e_date,
            "earn_soon": bool(e_days is not None and 0 <= e_days <= EARNINGS_WARN_DAYS),
        })
    meta = {"source": source, "orders_ok": orders is not None, "capital": cap, "cap_src": cap_src,
            "heat": heat, "v2_skipped": len(v2), "failed": fails, "chand_err": chand_err,
            "risk_pct_stock": hp.RISK_NEW_STOCK_PCT, "risk_pct_etf": hp.RISK_NEW_ETF_PCT}
    return pd.DataFrame(rows), meta


def to_axis(row, price, unit: str):
    """A price on the chart's x axis: distance from LTP in ATR(D) ('atr') or in % ('pct')."""
    if price is None or not row.get("ltp"):
        return None
    if unit == "atr":
        return (price - row["ltp"]) / row["atr"] if row.get("atr") else None
    return (price / row["ltp"] - 1) * 100


def triage(row) -> tuple[int, str]:
    """(rank, reason): what needs looking at first. Lower rank = more urgent."""
    if row.get("thesis_state") == "BROKEN":
        return 0, "thesis broken on the close"
    if row.get("chand_breach"):
        return 1, "Chandelier at/above LTP"
    if row.get("order_warn"):
        return 2, row["order_warn"]
    if row.get("over_budget"):
        if row.get("plan_qty"):
            return 3, f"loss at the Dhan stop over the risk rule - planned trim to {int(row['plan_qty'])} sh not done yet"
        return 3, "loss at the Dhan stop over the risk rule"
    if row.get("noise") == "red":
        return 4, "Dhan stop inside the noise (<1.5×ATR)"
    if row.get("thesis_state") == "NEAR":
        return 5, "close within 0.5×ATR of the thesis"
    if row.get("earn_soon") and row.get("gap_fit_qty") is not None and row.get("qty")             and row["gap_fit_qty"] < row["qty"]:
        return 6, (f"results in {int(row['earn_days'])}d - a repeat of its worst gap costs more than the rule; "
                   f"gap-sized holding {int(row['gap_fit_qty'])} sh")
    if row.get("gap_over") and row.get("gap_through"):
        return 7, "its worst 2-year gap, repeated today, opens below the Dhan stop and costs more than the rule"
    return 9, ""


# ── EDITS (28-Oct-2026): thesis levels and planned quantities, saved from the page ─────────
# A planned quantity is a PLAN, never an order: the trim itself is placed on Dhan by hand. It
# lives in data/sl_plan.json (not the journal, whose quantity must stay = Dhan's) and drops off
# the board on its own once the holding is at or below it.
PLAN_PATH = os.path.join(HERE, "data", "sl_plan.json")
EARNINGS_WARN_DAYS = 7      # morning digest + triage: results this close change SIZE, not direction


def load_plans() -> dict:
    import json
    try:
        with open(PLAN_PATH, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def save_edits(edits: list[dict]) -> dict:
    """edits: [{symbol, thesis, plan_qty, note, qty, avg, disaster}] - only CHANGED fields are
    passed in. Writes thesis_sl to the journal (backup first), plan_qty/note to sl_plan.json,
    and logs every thesis change to the stop history. Returns {'thesis': n, 'plan': n,
    'backup': path, 'errors': [...]}. Never touches stoploss, quantity or any order."""
    import json
    import shutil
    from datetime import datetime
    import journal_path as jp
    import stop_history as sh
    from io_utils import atomic_write_text

    out = {"thesis": 0, "plan": 0, "backup": "", "errors": []}
    th = [e for e in edits if "thesis" in e]
    if th:
        bk = jp.JOURNAL_DB.replace(".db", f".backup_{datetime.now():%Y%m%d_%H%M}_sldash.db")
        try:
            shutil.copy2(jp.JOURNAL_DB, bk)
            out["backup"] = bk
        except OSError as e:
            out["errors"].append(f"backup failed, nothing written: {e}")
            return out
        con = sqlite3.connect(jp.JOURNAL_DB)
        try:
            for e in th:
                v = _f(e["thesis"])
                n = con.execute("UPDATE journal SET thesis_sl=? WHERE UPPER(symbol)=? AND UPPER(status)='OPEN'",
                                (v, str(e["symbol"]).upper())).rowcount
                if n:
                    out["thesis"] += 1
                    try:
                        sh.record_page_edit(e["symbol"], e.get("qty"), e.get("avg"), v, e.get("disaster"))
                    except Exception as ex:
                        out["errors"].append(f"{e['symbol']}: history not logged ({ex})")
                else:
                    out["errors"].append(f"{e['symbol']}: no OPEN journal row")
            con.commit()
        finally:
            con.close()
    pl = [e for e in edits if "plan_qty" in e or "note" in e]
    if pl:
        plans = load_plans()
        today = datetime.now().strftime("%Y-%m-%d")
        for e in pl:
            s = str(e["symbol"]).upper()
            cur = dict(plans.get(s) or {})
            if "plan_qty" in e:
                q = _f(e["plan_qty"])
                if q:
                    cur["plan_qty"], cur["set"] = int(q), today
                else:
                    cur.pop("plan_qty", None)
            if "note" in e:
                cur["note"] = str(e["note"] or "").strip()
            if cur.get("plan_qty") or cur.get("note"):
                plans[s] = cur
            else:
                plans.pop(s, None)
            out["plan"] += 1
        os.makedirs(os.path.dirname(PLAN_PATH), exist_ok=True)
        atomic_write_text(PLAN_PATH, json.dumps(plans, indent=1, sort_keys=True))
    return out


def push_to_tradingview(alerts: bool = True, timeout: int = 600) -> list[tuple[str, int, str]]:
    """Re-push the v67 slots + stop book (tv_push_v67_trail) and, if asked, rebuild the
    GM-THESIS alerts (tv_thesis_alerts) - the same two scripts the 16:30 auto-pilot runs.
    Needs TradingView open with CDP. Returns [(script, returncode, last lines of output)]."""
    import subprocess
    import sys
    out = []
    for script in ["tv_push_v67_trail.py"] + (["tv_thesis_alerts.py"] if alerts else []):
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE,
                               capture_output=True, text=True, timeout=timeout)
            tail = "\n".join([l for l in (r.stdout or "").splitlines() if l.strip()][-6:] +
                             [l for l in (r.stderr or "").splitlines() if l.strip()][-3:])
            out.append((script, r.returncode, tail))
        except Exception as e:
            out.append((script, -1, str(e)))
    return out


def rec_disaster_for(thesis, atr):
    """The Disaster SL the two-tier rule pairs with a thesis on a HELD position:
    thesis - THESIS_TO_DISASTER_ATR x ATR(D). (house_policy.disaster_stop adds an entry-based
    floor, which is for a NEW trade.)"""
    import house_policy as hp
    t, a = _f(thesis), _f(atr)
    return (t - hp.THESIS_TO_DISASTER_ATR * a) if (t and a) else None
