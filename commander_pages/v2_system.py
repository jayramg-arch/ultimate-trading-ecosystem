# commander_pages/v2_system.py - the v2 SYSTEM page of Web Commander (17-Oct-2026, Doc 41).
#
# The v2 system runs beside the current (trigger) system and has its own paper-trading instance:
# the weekly ranked board, the books (P1E primary, P1ER routed through the reviewer, P1 / P1F
# research controls), this week's orders with the reviewer's verdicts, positions and the trade
# blotter. Engine: p1_paper.py (nightly, auto-pilot Phase 12i) + v2_core.py. Paper only.
# Runs in the app's namespace via commander_pages.run('v2_system', globals()).
if True:
    import os as _os
    import datetime as _dt
    import pandas as _pd
    import plotly.graph_objects as _go
    import p1_paper as _p1
    import v2_core as _v2
    import paper_trades as _ptx

    st.markdown('<div class="page-title">🧭 v2 System · paper trading</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">A weekly ranked portfolio — Clenow\'s <i>Stocks on the Move</i>, ensemble '
                'rank — chosen by a pre-registered, survivorship-corrected tournament. Orders are decided at the '
                'week\'s last close and filled on paper at the next open; the week\'s buys go to the reviewer for an '
                'execution check. Nothing is sent to Dhan. Design: Doc 41.</div>', unsafe_allow_html=True)

    _books = {n: _p1.load_state(n) for n in _p1.BOOKS}
    _bd = _v2.board()

    # ── status strip ───────────────────────────────────────────────────────
    _pend = _books.get(_v2.PRIMARY, {}).get("pending") or {}
    _reg = _pend.get("regime_up")
    _s = st.columns(4)
    _s[0].metric("Regime", "UP — buys allowed" if _reg else ("DOWN — no new buys" if _reg is False else "—"),
                 help="Nifty 500 vs its 200-day SMA at the last week-end close")
    _s[1].metric("Last decision", _pend.get("decided", "—"))
    _s[2].metric("Eligible names", _pend.get("eligible", (len(_bd) if len(_bd) else 0)))
    _s[3].metric("Board as of", str(_bd["as_of"].iloc[0]) if len(_bd) else "—")

    # ── the books ──────────────────────────────────────────────────────────
    st.markdown("#### Books")
    st.caption("Each paper book starts at the full house sizing capital (%s) - the research scale the tournament and "
               "backtests used - so their results compare in percent with the evidence. Your real v2 book is "
               "one-third of it (%s): v2 · BOOK and ⚖️ v1 vs v2." % (
                   _ptx.inr(next(iter(_books.values()))["start_capital"]), _ptx.inr(_p1.v2_capital())))
    _role = {"P1E": "v2 primary", "P1ER": "v2 + reviewer", "P1ES": "P1E + disaster stop",
             "V2H": "live v2 rules (Clenow exits, resize, Wed, ETFs)", "P1": "control · tournament winner",
             "P1F": "control · fundamental floor"}
    _order = [b for b in ("P1E", "P1ER", "P1ES", "V2H", "P1", "P1F") if b in _books]
    _cols = st.columns(len(_order))
    for _c, _nm in zip(_cols, _order):
        _st = _books[_nm]
        _h = _st["history"][-1] if _st["history"] else {}
        _eq = _h.get("equity", _st["cash"])
        _c.metric(f"{_nm} · {_role.get(_nm, '')}", _ptx.inr(_eq),
                  f"{(_eq / _st['start_capital'] - 1) * 100:+.2f}% since start",
                  help=f"cash {_ptx.inr(_st['cash'])} · {len(_st['pos'])} positions · last close {_st['last_date']}")
    _hist = {n: _pd.DataFrame(_books[n]["history"]) for n in _order if _books[n]["history"]}
    _base = _hist.get(_v2.PRIMARY)
    if _base is not None and len(_base) > 1:
        _fig = _go.Figure()
        for _nm, _hh in _hist.items():
            _fig.add_trace(_go.Scatter(x=_hh["date"], y=_hh["equity"] / _hh["equity"].iloc[0] * 100, name=_nm))
        _fig.add_trace(_go.Scatter(x=_base["date"], y=_base["nifty500"] / _base["nifty500"].iloc[0] * 100,
                                   name="Nifty 500", line=dict(dash="dot")))
        _fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="start = 100")
        st.plotly_chart(_fig, use_container_width=True)
    else:
        st.caption("The equity curve appears after the first few sessions of paper trading.")

    _t1, _t2, _t3, _t4 = st.tabs(["📋 Rank board", "🗓️ This week's orders + reviews", "📂 Positions", "🧾 Trades"])

    with _t1:
        if not len(_bd):
            st.info("No board yet — it is written nightly by the auto-pilot (Phase 12i).")
        else:
            _n = st.slider("Show the top", 10, int(min(200, max(10, len(_bd)))), int(min(50, len(_bd))), 10,
                           key="v2_board_n")
            _v = _bd.sort_values("rank", na_position="last").head(_n)[
                [c for c in ["rank", "symbol", "score", "close", "atr20", "in_cut", "held", "fno", "action"] if c in _bd.columns]]
            st.dataframe(_v, hide_index=True, use_container_width=True,
                         column_config={"score": st.column_config.NumberColumn("score", format="%.3f",
                                            help="Mean percentile rank of the 60/90/120-session trend-quality scores"),
                                        "in_cut": st.column_config.CheckboxColumn("in top 25 %"),
                                        "held": st.column_config.CheckboxColumn("held (P1E)"),
                                        "fno": st.column_config.CheckboxColumn("F&O", help="Has stock futures and options (display only)")})
            st.caption("Eligible = above its 100-DMA, no single-day move over 15 % in 90 sessions, median turnover "
                       "≥ ₹5 crore. The system holds names inside the top-25 % cut and buys from the top when the "
                       "regime is up and cash allows.")

    with _t2:
        _ord = sorted(f for f in _os.listdir(_p1.REPORT_DIR) if f.startswith("orders_") and f.endswith(".md")) \
            if _os.path.isdir(_p1.REPORT_DIR) else []
        if _ord:
            with open(_os.path.join(_p1.REPORT_DIR, _ord[-1]), encoding="utf-8") as _fh:
                st.markdown(_fh.read())
        _since = _pend.get("decided")
        if _since:
            _rv = _v2.latest_reviews(_since)
            _buys = [b[0] for b in _pend.get("buys", [])]
            if _buys:
                st.markdown("**Reviewer on this week's buys** (execution check — P1ER skips WAIT / PASS):")
                st.dataframe(_pd.DataFrame([{"symbol": s, "ruling": _rv.get(s, "not reviewed yet")} for s in _buys]),
                             hide_index=True, use_container_width=True)
            else:
                st.caption("No buys this week, so nothing went to the reviewer.")

    with _t3:
        for _nm in _order:
            _st = _books[_nm]
            st.markdown(f"**{_nm}** · {_role.get(_nm, '')} · {len(_st['pos'])} positions")
            if _st["pos"]:
                st.dataframe(_pd.DataFrame([{"symbol": k, "kind": v.get("kind", "stock"),
                                             "shares": round(v["sh"], 1), "entry": round(v["entry"], 2),
                                             "last": round(v["last"], 2), "stop": v.get("stop"),
                                             "P&L %": round((v["last"] / v["entry"] - 1) * 100, 1),
                                             "since": v.get("entry_date")} for k, v in _st["pos"].items()]),
                             hide_index=True, use_container_width=True)

    with _t4:
        _rows = []
        for _nm in _order:
            for _tr in _books[_nm].get("trades", []):
                _rows.append(dict(book=_nm, **_tr))
        if _rows:
            st.dataframe(_pd.DataFrame(_rows).sort_values("date", ascending=False), hide_index=True,
                         use_container_width=True)
        else:
            st.caption("No trades yet — the books are in cash while the regime is down.")

    with st.expander("How the v2 system works (rules)"):
        st.markdown(
            "- **Regime:** new buys only when the Nifty 500 closed the week above its 200-day SMA.\n"
            "- **Eligible:** above its 100-DMA; no single-day move over 15 % in 90 sessions; liquid.\n"
            "- **Rank:** trend quality = 90-day-style exponential-regression slope × R², averaged as percentile "
            "ranks over 60, 90 and 120 sessions (the ensemble — no single setting has to be right).\n"
            "- **Portfolio:** weekly; sell a holding outside the top 25 % or no longer eligible; buy from the top "
            "while cash lasts; each position = 0.10 % of equity per ATR(20) (equal risk).\n"
            "- **Reviewer:** each Friday's buys are reviewed for execution only; P1ER skips WAIT/PASS.\n"
            "- Evidence and plan: Docs 39, 40, 41 and the PREREG_* files.")
