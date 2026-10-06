"""trade_class.py - swing vs positional: classify, convert, re-qualify (7-Oct-2026, Jay).

WHY: Jay's practical problem was the grey area between a swing and a positional trade.
Trades taken as swing were carried on as positional when the tape turned, stops were
widened without the quantity coming down, and the book's risk grew past what the Risk
Allocator had sized. This module writes the procedure down as code, so every surface
(Risk Shield tab, evening digest, tests) answers the same way.

THE RULES (docs 25 + 26 carry the full text):

1. CLASSIFY AT ENTRY - the STOCK decides, not the intention.
   Positional only if ALL hold on the entry day: daily ATR <= 4% of price, within 30%
   of the 52W high, above the 200-DMA (commander_core.plan_type - the one rule S4, the
   board split and Risk Shield already use), AND Stage 2 on the confirmed weekly close.
   A GO from GM_Positional (Daily alert) is positional; from GM_Swing (75/125m) swing.

2. CONVERT SWING -> POSITIONAL only when all four gates pass on a DAILY close:
   G1 working  - close >= the swing T1 (journal target1), or >= entry + 3 x ATR(D)
                 (2R on a 1.5 x ATR swing stop) when no T1 is recorded, or the new
                 positional stop would already sit at/above the entry.
   G2 rule     - plan_type(...) == "positional" today.
   G3 stage    - Stage 2 on the confirmed weekly close AND the weekly structure trend
                 is not down (the S4 first test).
   G4 sector   - the sector index is not Stage 4. SOFT: a conversion in a Stage-4
                 sector is allowed but must carry a written reason.
   New stop    = close - 4 x ATR(D) (house_policy.POS_STOP_FLOOR_ATR_D), moved down to
                 the 20-day swing low when that low sits within 5 x ATR(D) - the
                 nearest daily structure, never closer than the floor.
   Risk check  = if the new stop >= entry the profit is locked (0 capital at risk);
                 else (close - stop) x qty <= house risk % x sizing capital. Over it,
                 trim the quantity to fit.
   SALVAGE     = a LOSING swing (G1 fails) that passes G2 and G3 may convert only at
                 HALF the house risk. That is the line between a decision and a rescue.
   NEVER       = losing (outside salvage), below the 200-DMA, Stage 3/4, ATR > 4%.

3. RE-QUALIFY POSITIONAL HOLDINGS weekly: a positional holding that is no longer
   Stage 2 on a confirmed weekly close (Stage 3 or 4) goes to the exit/reduce review.
   It is NOT demoted to swing. Below the 200-DMA alone is a warning.

Advisory only. Nothing here places, modifies or cancels an order. record_conversion()
writes the journal Timeframe + a dated note and appends logs/trade_class_events.csv;
the stop itself stays on Dhan (journal_sync reads it back at 16:30).
"""
from __future__ import annotations

import csv
import datetime as dt
import math
import os
import sqlite3

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = os.path.join(HERE, "logs", "trade_class_events.csv")

SWING_T1_ATR = 3.0          # 2R on a 1.5 x ATR(D) swing stop, when no T1 is recorded
STRUCT_MAX_ATR = 5.0        # a 20-day swing low further than this is not "nearest structure"
SALVAGE_RISK_MULT = 0.5     # a losing swing converts only at half the house risk


# ---------------------------------------------------------------- facts ----------
def _atr_wilder(df: pd.DataFrame, n: int = 14) -> float:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return float(tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1])


def weekly_stage(daily: pd.DataFrame) -> tuple[int | None, float | None]:
    """(stage, weekly structure trend) on CONFIRMED weekly bars - the forming week is
    dropped (pa_patterns), the stage is bull_screener's stateless 2x2 (the definition
    S4 / v67 / GM share), the trend is strict_trend(structure=True) at the Zigzag's
    weekly pivot length 5 (S4's first-test input)."""
    try:
        import pa_patterns as pap
        import bull_screener as bs
        import strict_trend as st
        wk = pap._confirmed_weekly_ohlcv(daily)
        if wk is None or len(wk) < 35:
            return None, None
        stages, _ = bs.compute_weekly_stage_and_wks(wk)
        tr = st.compute_strict_trend(wk["High"], wk["Low"], piv_left=5, piv_right=5, structure=True)
        return int(stages.iloc[-1]), float(tr.iloc[-1])
    except Exception:
        return None, None


def daily_facts(symbol: str, daily: pd.DataFrame | None = None) -> dict | None:
    """Everything the rules read, from cached DAILY bars. None when history is short."""
    try:
        if daily is None:
            import data_provider as dp
            daily = dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True, auto_adjust=True)
            # 7-Oct-2026: the cached frame was one session behind (5 Oct read at 00:40 on the 7th),
            # so the conversion gates judged yesterday's close. A cache older than the last
            # COMPLETED session is busted once and re-fetched.
            try:
                import nse_calendar as nc
                want = nc.last_completed_session(dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).replace(tzinfo=None))
                if daily is not None and len(daily) and pd.Timestamp(daily.index[-1]).date() < want:
                    dp.invalidate_symbol(symbol)
                    fresh = dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True, auto_adjust=True)
                    if fresh is not None and len(fresh) >= 60:
                        daily = fresh
            except Exception:
                pass
        if daily is None or len(daily) < 60:
            return None
        if isinstance(daily.columns, pd.MultiIndex):
            daily = daily.copy()
            daily.columns = daily.columns.get_level_values(0)
        c = daily["Close"]
        px = float(c.iloc[-1])
        atr = _atr_wilder(daily)
        hi52 = float(daily["High"].iloc[-252:].max())
        s200 = float(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None
        stage, wtrend = weekly_stage(daily)
        return {
            "close": px, "atr": atr, "atr_pct": atr / px * 100.0 if px else 0.0,
            "off52": (1.0 - px / hi52) * 100.0 if hi52 else 0.0,
            "sma200": s200, "below200": bool(s200 and px < s200),
            "swing_lo20": float(daily["Low"].iloc[-20:].min()),
            "stage": stage, "w_trend": wtrend,
            "asof": str(pd.Timestamp(daily.index[-1]).date()),
        }
    except Exception:
        return None


def plan_type_of(f: dict) -> str:
    """The house rule (commander_core.plan_type) on daily_facts output."""
    import commander_core as cc
    return cc.plan_type(f["atr_pct"], f["off52"], f["below200"])


def sector_stage(symbol: str) -> tuple[str | None, int | None]:
    """(sector name, stage of its sector index) - best effort, (name, None) if unknown."""
    try:
        import sector_lookup as sl
        rec = sl.get_sector(symbol) or {}
        name = rec.get("sector_name") or rec.get("display_name")
        yf = rec.get("yf_ticker")
        if not yf:
            return name, None
        import data_provider as dp
        d = dp.fetch_ohlcv(yf, period="2y", interval="1d", use_cache=True, auto_adjust=True)
        if d is None or len(d) < 200:
            return name, None
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        return name, weekly_stage(d)[0]
    except Exception:
        return None, None


def positional_stop(f: dict) -> float:
    """Nearest daily structure, never closer than close - 4 x ATR(D)."""
    from house_policy import POS_STOP_FLOOR_ATR_D
    floor = f["close"] - POS_STOP_FLOOR_ATR_D * f["atr"]
    stop = floor
    lo = f.get("swing_lo20")
    if lo is not None and lo < floor and lo >= f["close"] - STRUCT_MAX_ATR * f["atr"]:
        stop = lo
    return round(math.floor(stop * 20) / 20.0, 2)           # 0.05 tick, rounded down


def _budget(symbol: str, mult: float = 1.0) -> float:
    import house_policy as hp
    cap = hp.sizing_capital()[0] or 0.0
    return cap * hp.risk_pct_for(symbol) / 100.0 * mult


# ---------------------------------------------------------------- checks ---------
def conversion_check(symbol: str, qty: float, entry: float, target1: float | None = None,
                     facts: dict | None = None, sector: tuple | None = None) -> dict:
    """The four gates + new stop + the quantity the house risk allows.

    verdict: CONVERT / CONVERT · TRIM / SALVAGE · TRIM / SALVAGE / NOT ELIGIBLE / NO DATA."""
    f = facts if facts is not None else daily_facts(symbol)
    out = {"symbol": symbol, "verdict": "NO DATA", "gates": {}, "reasons": []}
    if not f or not entry or not qty:
        out["reasons"].append("no daily history" if not f else "no entry/qty in the journal")
        return out
    px, atr = f["close"], f["atr"]
    new_stop = positional_stop(f)
    pt = plan_type_of(f)
    sec_name, sec_stage = sector if sector is not None else sector_stage(symbol)

    t1 = target1 if (target1 and target1 > entry) else entry + SWING_T1_ATR * atr
    g1 = px >= t1 or new_stop >= entry
    g2 = pt == "positional"
    g3 = f["stage"] == 2 and (f["w_trend"] is None or f["w_trend"] > -0.5)
    g4 = sec_stage != 4                     # unknown sector stage passes (soft gate)
    out["gates"] = {"G1 working": g1, "G2 rule positional": g2,
                    "G3 Stage 2 weekly": g3, "G4 sector not Stage 4": g4}
    if not g1:
        out["reasons"].append("not working: close %.2f below T1 %.2f and the new stop %.2f is under entry %.2f"
                              % (px, t1, new_stop, entry))
    if not g2:
        why = []
        if f["atr_pct"] > 4.0:
            why.append("ATR(D) %.2f%% > 4%%" % f["atr_pct"])
        if f["off52"] > 30.0:
            why.append("%.1f%% off the 52W high > 30%%" % f["off52"])
        if f["below200"]:
            why.append("below the 200-DMA")
        out["reasons"].append("rule says swing: " + ", ".join(why))
    if not g3:
        out["reasons"].append("weekly: Stage %s, structure trend %s" % (f["stage"], {1.0: "up", -1.0: "DOWN", 0.0: "sideways"}.get(f["w_trend"], f["w_trend"])))
    if not g4:
        out["reasons"].append("sector %s is Stage 4 - convert only with a written reason" % (sec_name or "?"))

    salvage = (not g1) and g2 and g3
    mult = SALVAGE_RISK_MULT if salvage else 1.0
    budget = _budget(symbol, mult)
    per_share = max(px - new_stop, 0.0)
    locked = new_stop >= entry
    risk_now = 0.0 if locked else per_share * qty
    max_qty = int(qty) if locked else (int(budget // per_share) if per_share > 0 else int(qty))
    trim = max(0, int(qty) - max_qty)

    if g1 and g2 and g3:
        out["verdict"] = "CONVERT · TRIM" if trim else "CONVERT"
    elif salvage:
        out["verdict"] = "SALVAGE · TRIM" if trim else "SALVAGE"
    else:
        out["verdict"] = "NOT ELIGIBLE"
    out.update({
        "close": round(px, 2), "atr": round(atr, 2), "atr_pct": round(f["atr_pct"], 2),
        "off52": round(f["off52"], 1), "below200": f["below200"], "stage": f["stage"],
        "w_trend": f["w_trend"], "plan_type": pt, "sector": sec_name, "sector_stage": sec_stage,
        "t1_used": round(t1, 2), "new_stop": new_stop, "locked": locked,
        "risk_now": round(risk_now, 0), "budget": round(budget, 0), "max_qty": max_qty,
        "trim": trim, "soft_note_needed": not g4, "asof": f["asof"],
        "t1_pos": round(px + 3.0 * per_share, 2) if per_share else None,
        "t2_pos": round(px + 5.0 * per_share, 2) if per_share else None,
    })
    return out


def requalify(symbol: str, facts: dict | None = None) -> dict:
    """A POSITIONAL holding's weekly re-qualification.
    status: OK / EXIT REVIEW (Stage 3/4 on the confirmed weekly close) / WARN / NO DATA."""
    f = facts if facts is not None else daily_facts(symbol)
    if not f:
        return {"symbol": symbol, "status": "NO DATA", "reasons": ["no daily history"]}
    r = []
    status = "OK"
    if f["stage"] in (3, 4):
        status = "EXIT REVIEW"
        r.append("Stage %d on the confirmed weekly close - no Stage 3/4 holds" % f["stage"])
    if f["below200"]:
        r.append("below the 200-DMA")
        status = "WARN" if status == "OK" else status
    if f["w_trend"] is not None and f["w_trend"] < -0.5:
        r.append("weekly structure trend DOWN")
        status = "WARN" if status == "OK" else status
    return {"symbol": symbol, "status": status, "stage": f["stage"], "plan_type": plan_type_of(f),
            "close": round(f["close"], 2), "reasons": r, "asof": f["asof"]}


# ---------------------------------------------------------------- book -----------
def _journal():
    from journal_path import JOURNAL_DB
    return JOURNAL_DB


def open_positions() -> pd.DataFrame:
    with sqlite3.connect(_journal()) as c:
        d = pd.read_sql("SELECT id, symbol, timeframe, setup, quantity, buy_price, stoploss, "
                        "target1, entry_date FROM journal WHERE UPPER(status)='OPEN'", c)
    return d


def _is_swing(tf) -> bool:
    return str(tf or "").strip().lower().startswith("swing")


def review_book() -> pd.DataFrame:
    """One row per OPEN position: its journal type, what the rule says today, and either
    the conversion check (swing) or the weekly re-qualification (positional)."""
    rows = []
    for _, p in open_positions().iterrows():
        sym = str(p["symbol"]).strip().upper()
        f = daily_facts(sym)
        jt = "Swing" if _is_swing(p["timeframe"]) else ("Positional" if str(p["timeframe"] or "").strip() else "—")
        base = {"id": int(p["id"]), "symbol": sym, "journal": jt, "qty": p["quantity"],
                "entry": p["buy_price"], "stop": p["stoploss"]}
        if not f:
            rows.append({**base, "rule_now": "—", "action": "NO DATA", "detail": "no daily history"})
            continue
        pt = plan_type_of(f)
        pnl = (f["close"] / p["buy_price"] - 1) * 100 if p["buy_price"] else None
        base.update({"close": round(f["close"], 2), "pnl_pct": round(pnl, 1) if pnl is not None else None,
                     "rule_now": pt, "stage": f["stage"], "atr_pct": round(f["atr_pct"], 2)})
        if jt == "Swing":
            ck = conversion_check(sym, float(p["quantity"] or 0), float(p["buy_price"] or 0),
                                  float(p["target1"]) if p["target1"] else None, facts=f)
            det = "; ".join(ck["reasons"]) or ("new stop %.2f · max qty %d" % (ck.get("new_stop", 0), ck.get("max_qty", 0)))
            if ck["verdict"] != "NOT ELIGIBLE" and ck.get("trim"):
                det += " · trim %d" % ck["trim"]
            rows.append({**base, "action": ck["verdict"], "new_stop": ck.get("new_stop"),
                         "max_qty": ck.get("max_qty"), "detail": det})
        else:
            rq = requalify(sym, facts=f)
            act = {"OK": "HOLD (qualifies)", "WARN": "WATCH", "EXIT REVIEW": "EXIT REVIEW"}.get(rq["status"], rq["status"])
            if pt == "swing" and rq["status"] == "OK":
                act = "WATCH"
                rq["reasons"].append("the rule now reads swing (ATR/off-high)")
            rows.append({**base, "action": act, "detail": "; ".join(rq["reasons"]) or "Stage 2, above the 200-DMA"})
    return pd.DataFrame(rows)


def record_conversion(symbol: str, new_stop: float, verdict: str, note: str = "",
                      trim: int = 0) -> bool:
    """Journal: Timeframe -> Positional, a dated line appended to the rationale; the event
    goes to logs/trade_class_events.csv. Does NOT touch the stop or the quantity - those
    change on Dhan (journal_sync reads them back at 16:30)."""
    sym = symbol.strip().upper()
    today = dt.date.today().isoformat()
    line = "[%s] swing -> positional (%s): new stop %.2f%s%s" % (
        today, verdict, new_stop, (" · trim %d" % trim) if trim else "", (" · " + note) if note else "")
    with sqlite3.connect(_journal()) as c:
        cur = c.execute("UPDATE journal SET timeframe='Positional', "
                        "rationale = COALESCE(rationale,'') || ? WHERE UPPER(status)='OPEN' AND UPPER(symbol)=?",
                        ("\n" + line, sym))
        n = cur.rowcount
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    new = not os.path.exists(EVENTS)
    with open(EVENTS, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "symbol", "event", "verdict", "new_stop", "trim", "note", "rows"])
        w.writerow([today, sym, "swing->positional", verdict, new_stop, trim, note, n])
    return n > 0


def digest_lines() -> list[str]:
    """Evening digest: positional holdings that failed Stage 2 on the weekly close, and
    swing holdings that now pass the conversion gates."""
    b = review_book()
    if b.empty:
        return ["TRADE CLASS: no open positions"]
    ex = b[b["action"] == "EXIT REVIEW"]
    wa = b[b["action"] == "WATCH"]
    cv = b[b["action"].astype(str).str.startswith("CONVERT")]
    sv = b[b["action"].astype(str).str.startswith("SALVAGE")]
    out = ["TRADE CLASS: %d positional · %d swing" % ((b["journal"] != "Swing").sum(), (b["journal"] == "Swing").sum())]
    if len(ex):
        out.append("  EXIT REVIEW (positional, Stage 3/4 weekly): " + ", ".join(ex["symbol"]))
    if len(wa):
        out.append("  watch (positional, below 200-DMA / rule now swing): " + ", ".join(wa["symbol"]))
    if len(cv):
        out.append("  swing -> positional eligible: " + ", ".join("%s%s" % (r.symbol, " (trim)" if "TRIM" in r.action else "") for r in cv.itertuples()))
    if len(sv):
        out.append("  salvage only (losing, half risk): " + ", ".join(sv["symbol"]))
    return out


def render_streamlit() -> None:
    """Risk Shield tab '🔁 Swing ↔ Positional'. Advisory: it records a conversion in the
    journal, it never touches an order."""
    import streamlit as st

    st.markdown('<div class="section-sub-lbl">🔁 Swing ↔ Positional — classify, convert, re-qualify</div>',
                unsafe_allow_html=True)
    st.caption(
        "Positional only if daily ATR ≤ 4%, within 30% of the 52W high, above the 200-DMA and Stage 2 "
        "on the weekly close. A swing converts only when it is WORKING, the rule reads positional today, "
        "it is Stage 2 weekly and the sector is not Stage 4 (soft). New stop = nearest daily structure, "
        "never closer than 4×ATR(D); risk from the close must fit the house risk, else trim. A losing "
        "swing that qualifies may convert only at HALF risk (salvage). Positional holdings that read "
        "Stage 3/4 on the weekly close go to EXIT REVIEW. Doc 25 Part 7b · Doc 26.")

    @st.cache_data(ttl=900, show_spinner="Reading the open book…")
    def _book():
        return review_book()

    c1, _ = st.columns([1, 5])
    if c1.button("🔄 Re-check", key="tc_refresh"):
        _book.clear()
    b = _book()
    if b.empty:
        st.info("No open positions in the journal.")
        return

    order = {"EXIT REVIEW": 0, "WATCH": 1, "CONVERT": 2, "CONVERT · TRIM": 2, "SALVAGE": 3,
             "SALVAGE · TRIM": 3, "NOT ELIGIBLE": 4, "HOLD (qualifies)": 5, "NO DATA": 6}
    b = b.assign(_o=b["action"].map(order).fillna(9)).sort_values(["_o", "symbol"]).drop(columns="_o")
    n_ex = int((b["action"] == "EXIT REVIEW").sum())
    n_cv = int(b["action"].astype(str).str.startswith("CONVERT").sum())
    n_ne = int((b["action"] == "NOT ELIGIBLE").sum())
    m = st.columns(4)
    m[0].metric("Positional", int((b["journal"] != "Swing").sum()))
    m[1].metric("Swing", int((b["journal"] == "Swing").sum()))
    m[2].metric("Exit review", n_ex)
    m[3].metric("Convertible", n_cv)
    if n_ex:
        st.error("Positional holdings that are no longer Stage 2 on the weekly close: "
                 + ", ".join(b.loc[b["action"] == "EXIT REVIEW", "symbol"])
                 + " — no Stage 3/4 holds. Review for exit or reduce; do not relabel them swing.")
    if n_ne:
        st.warning("Swing trades NOT eligible to convert: " + ", ".join(b.loc[b["action"] == "NOT ELIGIBLE", "symbol"])
                   + ". Manage them as swing trades — their swing stop and trail apply. Calling a losing "
                   "swing positional is the rescue that builds large drawdowns.")
    cols = [c for c in ("symbol", "journal", "rule_now", "stage", "action", "pnl_pct", "close", "entry",
                        "stop", "new_stop", "qty", "max_qty", "atr_pct", "detail") if c in b.columns]
    st.dataframe(b[cols], width="stretch", hide_index=True)

    swings = b.loc[b["journal"] == "Swing", "symbol"].tolist()
    if not swings:
        return
    st.markdown("**Conversion check**")
    sym = st.selectbox("Swing holding", swings, key="tc_sym")
    p = open_positions()
    p = p[p["symbol"].str.upper() == sym].iloc[0]
    ck = conversion_check(sym, float(p["quantity"] or 0), float(p["buy_price"] or 0),
                          float(p["target1"]) if p["target1"] else None)
    g = st.columns(4)
    for i, (k, v) in enumerate(ck.get("gates", {}).items()):
        g[i].markdown(("🟢 " if v else "🔴 ") + k)
    if ck["verdict"] == "NO DATA":
        st.info("; ".join(ck["reasons"]))
        return
    st.markdown(
        f"**{ck['verdict']}** — close ₹{ck['close']:,.2f} · ATR(D) {ck['atr_pct']}% · Stage {ck['stage']} · "
        f"sector {ck.get('sector') or '?'} (Stage {ck.get('sector_stage') or '?'})  \n"
        f"New positional stop **₹{ck['new_stop']:,.2f}**"
        + (" — at/above entry, profit locked" if ck["locked"] else f" — risk from the close ₹{ck['risk_now']:,.0f} vs budget ₹{ck['budget']:,.0f}")
        + f" · max qty **{ck['max_qty']}**" + (f" → **trim {ck['trim']}**" if ck["trim"] else "")
        + (f"  \nPositional targets from the close: T1 3R ₹{ck['t1_pos']:,.2f} · T2 5R ₹{ck['t2_pos']:,.2f}" if ck.get("t1_pos") else ""))
    if ck["reasons"]:
        st.caption("Why: " + "; ".join(ck["reasons"]))
    if ck["verdict"] == "NOT ELIGIBLE":
        return
    note = st.text_input("Reason (required when the sector is Stage 4; recorded in the journal)", key="tc_note")
    blocked = ck["soft_note_needed"] and not note.strip()
    if st.button(f"Record conversion of {sym} in the journal", key="tc_go", disabled=blocked):
        if record_conversion(sym, ck["new_stop"], ck["verdict"], note.strip(), ck["trim"]):
            _book.clear()
            st.success(f"{sym} is now Positional in the journal. Next, on Dhan: "
                       + (f"sell {ck['trim']} share(s), " if ck["trim"] else "")
                       + f"set ONE stop at ₹{ck['new_stop']:,.2f} covering the full quantity (limit below the trigger), "
                       "then press Sync to TV so the v67 trail moves to the positional 22-bar 4.5×ATR.")
        else:
            st.error("No OPEN journal row matched — nothing recorded.")


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 90)
    print(review_book().to_string(index=False))
    print()
    print("\n".join(digest_lines()))
