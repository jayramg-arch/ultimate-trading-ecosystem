# commander_pages/v2_autopsy.py - 🔬 v2 · AUTOPSY (19-Oct-2026).
#
# Every closed REAL v2 slice (data/v2/real_book.json): P&L, hold, return and matched alpha against
# the Nifty 500 over the SAME holding period (entry close → exit close), grouped by why it left.
# v2 has no stop, so there is no R unit here - percent return and alpha are the measures. Empty
# until the first v2 exit. Read-only.
# Runs in the app's namespace via commander_pages.run('v2_autopsy', globals()).
if True:
    import pandas as _pd
    import v2_ui as _ui

    _ui.page_head("🔬 v2 · Autopsy",
                  "Closed v2 trades: what they made, how long they were held, and how they did against the Nifty 500 "
                  "over the same days. Grouped by the exit that took them out (rank, 100-DMA, 15 % move, index, "
                  "surveillance, resize trim).")
    _c = _ui.load()
    _ui.status_strip(_c)
    _inr, _cl = _c["inr"], _c["ledger"]["closed"]

    @st.cache_data(ttl=3600, show_spinner=False)
    def _v2a_bench():
        import data_provider as dp
        b = dp.fetch_ohlcv("^CRSLDX", period="5y", interval="1d", use_cache=True)
        c = b["Close"].dropna()
        c.index = _pd.to_datetime(c.index).normalize()
        return c

    if not _cl:
        st.info("No closed v2 trades yet. The first ones come when a holding is sold at a rebalance open - the "
                "comparison against the current system is on ANALYSIS › ⚖️ v1 vs v2.")
    else:
        try:
            _bc = _v2a_bench()
        except Exception:
            _bc = None

        def _bat(d):
            if _bc is None:
                return None
            s = _bc[_bc.index <= _pd.Timestamp(str(d)[:10])]
            return float(s.iloc[-1]) if len(s) else None
        _rows = []
        for r in _cl:
            ret = (r["exit"] / r["entry"] - 1) * 100 if r["entry"] else None
            b0, b1 = _bat(r["entry_date"]), _bat(r["exit_date"])
            bret = (b1 / b0 - 1) * 100 if (b0 and b1) else None
            _rows.append({"symbol": r["symbol"], "shares": r["sh"], "entry": round(r["entry"], 2), "entry date": r["entry_date"],
                          "exit": round(r["exit"], 2), "exit date": r["exit_date"],
                          "days": (_pd.Timestamp(str(r["exit_date"])[:10]) - _pd.Timestamp(str(r["entry_date"])[:10])).days,
                          "P&L": (r["exit"] - r["entry"]) * r["sh"], "return %": ret, "Nifty 500 %": bret,
                          "alpha %": (ret - bret) if (ret is not None and bret is not None) else None,
                          "why": r.get("why", "")})
        _T = _pd.DataFrame(_rows)
        _w = _T["P&L"] > 0
        _k = st.columns(6)
        _k[0].metric("Closed", len(_T))
        _k[1].metric("Realised", _inr(_T["P&L"].sum()))
        _k[2].metric("Win rate", "%.0f %%" % (_w.mean() * 100))
        _aw = _T.loc[_w, "return %"].mean() if _w.any() else 0.0
        _al = -_T.loc[~_w, "return %"].mean() if (~_w).any() else 0.0
        _k[3].metric("Payoff", "%.2f" % (_aw / _al) if _al else "—", help="mean winning return ÷ mean losing return")
        _k[4].metric("Median hold", "%d days" % _T["days"].median())
        _k[5].metric("Mean alpha", "%+.2f %%" % _T["alpha %"].mean() if _T["alpha %"].notna().any() else "—",
                     help="return minus the Nifty 500 over the same entry → exit closes")
        st.markdown("**By exit reason**")
        _g = _T.groupby("why").agg(n=("symbol", "size"), pnl=("P&L", "sum"), win=("P&L", lambda s: (s > 0).mean() * 100),
                                   ret=("return %", "mean"), alpha=("alpha %", "mean"), days=("days", "median")).reset_index()
        _g["pnl"] = _g["pnl"].map(_inr)
        st.dataframe(_g.round(2), hide_index=True, use_container_width=True)
        _show = _T.copy()
        _show["P&L"] = _show["P&L"].map(_inr)
        st.dataframe(_show.round(2), hide_index=True, use_container_width=True)
        if len(_T) < 25:
            st.caption("%d closed trades - too few to judge the system; the capital-move check needs ≥ 25 (Doc 42)." % len(_T))
