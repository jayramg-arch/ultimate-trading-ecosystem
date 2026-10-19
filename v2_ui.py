"""v2_ui.py - what the four v2 SYSTEM pages share (19-Oct-2026, Jay: "pages like v1's, for v2").

  🗓️ v2 · THIS WEEK        commander_pages/v2_live.py
  📂 v2 · BOOK             commander_pages/v2_book.py
  📋 v2 · RANK & UNIVERSE  commander_pages/v2_rank.py
  🔬 v2 · AUTOPSY          commander_pages/v2_autopsy.py

`load()` reads what the nightly engine wrote (p1_paper.py Phase 4.79, the v2 ledger, the rank
board) once per page; `status_strip(ctx)` prints the same six numbers at the top of every page.
Read-only: nothing here places an order or writes a file.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd


def _cache(fn=None, ttl=900):
    import streamlit as st
    return st.cache_data(ttl=ttl, show_spinner=False)(fn)


def _bench():
    import data_provider as dp
    b = dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d", use_cache=True)
    c = b["Close"].dropna()
    return float(c.iloc[-1]), float(c.rolling(200).mean().iloc[-1]), str(pd.Timestamp(c.index[-1]).date())


def _last(syms: tuple):
    import data_provider as dp
    out = {}
    for s in syms:
        try:
            d = dp.fetch_ohlcv(s, period="3mo", interval="1d", use_cache=True)
            out[s] = float(d["Close"].dropna().iloc[-1])
        except Exception:
            pass
    return out


def next_decision():
    """(decision date, fill date) of the next weekly cycle - holiday-aware (Tuesday's close,
    Monday's when Tuesday is a holiday; the fill is the next session)."""
    try:
        import nse_calendar as nc
        import v2_house as vh
        d = dt.date.today()
        if nc.last_completed_session() >= d:      # today's close has passed: its decision is made
            d = d + dt.timedelta(days=1)
        for _ in range(15):
            n = vh._next_session(d)
            if nc.is_trading_day(d) and vh.is_wed_decision(pd.Timestamp(d), pd.Timestamp(n)):
                return d, n
            d = d + dt.timedelta(days=1)
    except Exception:
        pass
    return None, None


def load() -> dict:
    import p1_paper as p1
    import v2_core as v2
    import v2_ledger as vl
    st_ = p1.load_state("V2H")
    led = vl.load()
    held = led["open"]
    cap = p1.v2_capital()
    px = _cache(_last)(tuple(sorted(held)))
    inv = sum(q["sh"] * px.get(s, q["entry"]) for s, q in held.items())
    cost = sum(q["sh"] * q["entry"] for q in held.values())
    eq = cap + vl.realised() + (inv - cost)
    try:
        b_last, b_200, b_date = _cache(_bench)()
    except Exception:
        b_last = b_200 = None
        b_date = "-"
    nd, nf = next_decision()
    return {"state": st_, "pend": st_.get("pending") or {}, "board": v2.board(), "ledger": led, "held": held,
            "cap": cap, "px": px, "inv": inv, "cost": cost, "eq": eq, "b_last": b_last, "b_200": b_200,
            "b_date": b_date, "nd": nd, "nf": nf, "inr": p1._inr}


def status_strip(c: dict) -> None:
    import streamlit as st
    inr = c["inr"]
    k = st.columns(6)
    if c["b_last"] and c["b_200"]:
        up = c["b_last"] > c["b_200"]
        k[0].metric("Regime", "UP · buys allowed" if up else "DOWN · no new buys",
                    "%+.1f%% vs 200-DMA" % ((c["b_last"] / c["b_200"] - 1) * 100),
                    help="Nifty 500 close %.0f vs its 200-day SMA %.0f (%s). v2 buys only when above; holdings "
                         "stay either way." % (c["b_last"], c["b_200"], c["b_date"]))
    else:
        k[0].metric("Regime", "—")
    k[1].metric("Next decision", c["nd"].strftime("%a %d-%b") if c["nd"] else "—",
                ("fill %s" % c["nf"].strftime("%a %d-%b")) if c["nf"] else None)
    k[2].metric("v2 capital", inr(c["cap"]), help="One-third of the house sizing capital (V2_CAPITAL in .env overrides).")
    k[3].metric("v2 equity", inr(c["eq"]), "%+.2f%%" % ((c["eq"] / c["cap"] - 1) * 100) if c["cap"] else None)
    k[4].metric("Cash", inr(c["eq"] - c["inv"]), help="Idle cash sits in the ICICI sweep-in FD (≥ 6.75 %).")
    k[5].metric("Holdings", "%d" % len(c["held"]))


def page_head(title: str, desc: str) -> None:
    import streamlit as st
    st.markdown('<div class="page-title">%s</div>' % title, unsafe_allow_html=True)
    st.markdown('<div class="page-desc">%s</div>' % desc, unsafe_allow_html=True)
