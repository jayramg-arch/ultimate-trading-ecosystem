#!/usr/bin/env python3
"""v2 risk view - Risk Shield tab '🧭 v2 Holdings' (Jay, 19-Oct-2026).

v2 holdings carry no stop and no targets (Clenow's rules); this is how they are watched instead.
For each REAL v2 holding (v2_ledger) it reads, at the last close:
  - Clenow's exits: distance to the 100-day average, the largest one-day move in 90 days (15 %
    rule), rank against the buy cut (data/v2/board.csv), Nifty 500 membership, NSE surveillance
  - the twice-monthly resize: target shares now (0.10 % of v2 equity / ATR20, at most the
    per-trade cap) against shares held, flagged when outside the +/-10 % band
  - money: value, P&L, weight in v2 equity, days held and the tax-hold band (300-364 days)
plus a book summary: v2 capital, equity, cash, realised/unrealised P&L, sector weights vs the
25 % cap, the next decision and whether it is a resize day.

Read-only - nothing here touches the journal, the ledger or an order.

    python v2_risk.py        print the table
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _bars(sym: str):
    import data_provider as dp
    d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
    if d is None or len(d) < 30:
        return None
    d = d.copy()
    d.index = pd.to_datetime(d.index)
    if getattr(d.index, "tz", None) is not None:
        d.index = d.index.tz_localize(None)
    return d[~d.index.duplicated(keep="last")]


def _next_decision(today: dt.date | None = None) -> dt.date | None:
    """The next session whose close decides the week (the Wednesday rule)."""
    import nse_calendar as nc
    import v2_house as vh
    d = today or dt.date.today()
    days = []
    x = d
    while len(days) < 12:
        if nc.is_trading_day(x):
            days.append(x)
        x += dt.timedelta(days=1)
    for a, b in zip(days, days[1:]):
        if vh.is_wed_decision(pd.Timestamp(a), pd.Timestamp(b)):
            return a
    return None


def review() -> dict:
    """{"rows": DataFrame, "summary": dict}."""
    import house_policy as hp
    import p1_paper as pp
    import v2_house as vh
    import v2_ledger as vl
    book = vl.load()
    cap = pp.v2_capital()
    realised = vl.realised()
    try:
        import v2_core
        b = v2_core.board()
    except Exception:
        b = pd.DataFrame()
    rank = dict(zip(b["symbol"], b["rank"])) if len(b) else {}
    n_cut = int(b["in_cut"].astype(str).str.lower().eq("true").sum()) if len(b) else 0
    regime_up = bool(b["regime_up"].iloc[0]) if len(b) and "regime_up" in b else None
    try:
        uni = {x.replace(".NS", "").upper() for x in json.load(open(os.path.join(HERE, "nifty500_symbols.json")))}
    except Exception:
        uni = set()
    try:
        import nse_surveillance as ns
        surv, surv_note = ns.excluded()
    except Exception as e:
        surv, surv_note = None, "surveillance list unavailable (%s)" % e
    pool = set(vh.etf_pool())
    sect = {}
    rows = []
    for s, q in sorted(book["open"].items()):
        d = _bars(s)
        sh, entry = float(q["sh"]), float(q["entry"])
        if d is None:
            rows.append({"symbol": s, "shares": sh, "entry": entry, "note": "no price data"})
            continue
        C = d["Close"]
        last = float(C.iloc[-1])
        prev = C.shift()
        tr = np.maximum(d["High"] - d["Low"], np.maximum((d["High"] - prev).abs(), (d["Low"] - prev).abs()))
        atr20 = float(tr.ewm(alpha=1 / 20, adjust=False).mean().iloc[-1])
        sma100 = float(C.rolling(100).mean().iloc[-1]) if len(C) >= 100 else float("nan")
        gap90 = float(C.pct_change().abs().tail(90).max())
        held_days = (pd.Timestamp(dt.date.today()) - pd.Timestamp(q["entry_date"])).days
        rows.append({"symbol": s, "kind": "ETF" if s in pool else "stock", "shares": sh, "entry": entry,
                     "entry_date": q["entry_date"], "last": last, "as_of": str(C.index[-1].date()),
                     "value": sh * last, "pnl": (last - entry) * sh, "pnl_pct": (last / entry - 1) * 100,
                     "days": held_days, "sma100": sma100,
                     "vs_sma100_pct": (last / sma100 - 1) * 100 if sma100 == sma100 else float("nan"),
                     "max_move_90d_pct": gap90 * 100, "rank": rank.get(s), "atr20": atr20,
                     "in_n500": (s in uni) if (uni and s not in pool) else None,
                     "surveillance": (surv or {}).get(s, "")})
        try:
            import sector_lookup
            sec = (sector_lookup.get_sector(s) or {}).get("sector") or "?"
        except Exception:
            sec = "?"
        rows[-1]["sector"] = sec
    R = pd.DataFrame(rows)
    invested = float(R["value"].sum()) if len(R) and "value" in R else 0.0
    cost = float((R["shares"] * R["entry"]).sum()) if len(R) else 0.0
    equity = cap + realised + (invested - cost)
    if len(R) and "value" in R:
        tgt_cap = hp.MAX_ALLOC_DEFAULT / hp.CAPITAL_DEFAULT * equity
        R["weight_pct"] = R["value"] / equity * 100
        R["target_sh"] = [min(equity * vh.H["risk"] / a, tgt_cap / l) if (a == a and a > 0) else float("nan")
                          for a, l in zip(R["atr20"], R["last"])]
        band = vh.BOOK_FLAGS["V2H"].get("reb_band", vh.H["reb_band"])
        R["resize"] = [("trim %d" % math.floor(h - t)) if h > t * (1 + band) else
                       ("top up %d" % math.floor(t - h)) if h < t * (1 - band) else "within band"
                       if t == t else "" for h, t in zip(R["shares"], R["target_sh"])]
        R["tax_hold"] = [("in band (%dd)" % dd) if (vh.H["tax_from"] <= dd < vh.H["tax_to"] and p > 0) else
                         ("LTCG" if dd >= 365 else "") for dd, p in zip(R["days"], R["pnl"])]
        flags = []
        for _, r in R.iterrows():
            f = []
            if r["vs_sma100_pct"] == r["vs_sma100_pct"] and r["vs_sma100_pct"] < 0:
                f.append("below 100-DMA")
            if r["max_move_90d_pct"] > 15:
                f.append("15 % move in 90d")
            if r["kind"] == "stock" and n_cut:
                rk = r["rank"]
                if rk is None or rk != rk:
                    f.append("not ranked")
                elif rk > n_cut:
                    f.append("outside cut (%d > %d)" % (rk, n_cut))
            if r["in_n500"] is False:
                f.append("left Nifty 500")
            if r["surveillance"]:
                f.append("surveillance")
            flags.append(" · ".join(f) if f else "OK")
        R["exit_watch"] = flags
        for sec, v in R.groupby("sector")["value"].sum().items():
            sect[sec] = v / equity * 100
    import p1_paper as _pp
    try:
        st = _pp.load_state("V2H")
        n_next = int(st.get("n_dec") or 0) + 1
    except Exception:
        n_next = None
    nd = _next_decision()
    summary = {"capital": cap, "equity": equity, "cash": equity - invested, "invested": invested,
               "realised": realised, "unrealised": invested - cost, "holdings": int(len(R)),
               "sector_pct": dict(sorted(sect.items(), key=lambda kv: -kv[1])), "sector_cap": hp.SECTOR_CAP_PCT,
               "cut": n_cut, "regime_up": regime_up, "next_decision": nd,
               "next_is_reset": (n_next % 2 == 0) if n_next else None, "surv_note": surv_note,
               "closed": len(book["closed"])}
    return {"rows": R, "summary": summary}


def render_streamlit() -> None:
    import streamlit as st
    from p1_paper import _inr
    st.markdown('<div class="section-sub-lbl">🧭 v2 Holdings — Clenow exits, no stops</div>', unsafe_allow_html=True)
    st.caption("v2 holdings carry no stop and no targets. They leave at the rebalance open when the decision close (Tuesday; Monday if Tuesday is a holiday) "
               "shows: rank outside the buy cut, a close below the 100-day average, a one-day move beyond 15 % "
               "in 90 days, the name left the Nifty 500, or NSE surveillance. Every second decision resizes "
               "each holding to equal risk (0.10 % of v2 equity per ATR20, ±10 % band). Read-only — orders come "
               "from the Tuesday order sheet; fills are recorded with v2_take.py. Doc 42.")

    @st.cache_data(ttl=900, show_spinner="Reading the v2 book…")
    def _rv():
        return review()

    c1, _ = st.columns([1, 5])
    if c1.button("🔄 Re-check", key="v2risk_refresh"):
        _rv.clear()
    r = _rv()
    sm, R = r["summary"], r["rows"]
    m = st.columns(6)
    m[0].metric("v2 capital", _inr(sm["capital"]))
    m[1].metric("Equity", _inr(sm["equity"]), "%+.1f%%" % ((sm["equity"] / sm["capital"] - 1) * 100) if sm["capital"] else None)
    m[2].metric("Cash", _inr(sm["cash"]))
    m[3].metric("Holdings", sm["holdings"])
    m[4].metric("Realised P&L", _inr(sm["realised"]))
    m[5].metric("Unrealised P&L", _inr(sm["unrealised"]))
    reg = sm["regime_up"]
    st.markdown("**Next decision:** %s close%s · **regime:** %s · **buy cut:** top %s · %s" % (
        sm["next_decision"] or "?", " — a RESIZE day" if sm["next_is_reset"] else "",
        "Nifty 500 above its 200-day average (buys allowed)" if reg else
        "Nifty 500 below its 200-day average (no new buys; holdings stay)" if reg is False else "?",
        sm["cut"] or "?", sm["surv_note"]))
    if not len(R):
        st.info("No real v2 holdings yet. The first buys come on the first Wednesday after the Nifty 500 closes "
                "above its 200-day average.")
        return
    watch = R[R["exit_watch"] != "OK"] if "exit_watch" in R else R.iloc[0:0]
    if len(watch):
        st.warning("**Exit watch** — sold at the next rebalance open unless it recovers by the decision close:\n\n" +
                   "\n".join("- **%s**: %s" % (a, b) for a, b in zip(watch["symbol"], watch["exit_watch"])))
    else:
        st.success("Every v2 holding passes Clenow's exits at the last close.")
    show = R.copy()
    for c in ("value", "pnl"):
        if c in show:
            show[c] = show[c].map(lambda v: _inr(v) if v == v else "")
    cols = [c for c in ("symbol", "kind", "shares", "entry", "last", "as_of", "value", "pnl", "pnl_pct", "weight_pct",
                        "rank", "sma100", "vs_sma100_pct", "max_move_90d_pct", "exit_watch", "target_sh", "resize",
                        "days", "tax_hold", "sector", "surveillance") if c in show]
    st.dataframe(show[cols].round(2), hide_index=True, use_container_width=True)
    if sm["sector_pct"]:
        over = [s for s, v in sm["sector_pct"].items() if v > sm["sector_cap"]]
        st.markdown("**Sector weights (cap %d %% for new buys):** " % sm["sector_cap"] +
                    " · ".join("%s %.1f %%" % kv for kv in sm["sector_pct"].items()) +
                    (" — **over the cap: %s**" % ", ".join(over) if over else ""))


def main() -> int:
    r = review()
    sm = r["summary"]
    print({k: v for k, v in sm.items() if k != "sector_pct"})
    if len(r["rows"]):
        print(r["rows"].round(2).to_string(index=False))
    else:
        print("no real v2 holdings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
