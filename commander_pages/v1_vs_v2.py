# commander_pages/v1_vs_v2.py - ⚖️ v1 vs v2 (19-Oct-2026, Jay: "compare the performances of v1 vs v2").
#
# Real money: the nightly equity snapshot per system (system_equity.py, Phase 12j) - TWR, drawdown,
# excess over the Nifty 500, beta, trade stats. Paper: the current system's "S4 TAKE IT · house rules"
# cohort against v2's paper books. Capital decision: the pre-registered move rule
# (docs/PREREG_capital_move.md) and the origin of every journal row (who chose the trade).
# Read-only except the origin editor, which writes one column through trade_origin.set_origin().
# Runs in the app's namespace via commander_pages.run('v1_vs_v2', globals()).
if True:
    import json as _json
    import os as _os
    import sqlite3 as _sq
    import pandas as _pd
    import journal_path as _jp
    import p1_paper as _p1
    import system_equity as _se
    import trade_origin as _to
    import v2_ledger as _vl

    _inr = _p1._inr
    st.markdown('<div class="page-title">⚖️ v1 vs v2</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">The current system (v1: Golden Matcher + S4) against the v2 system (Clenow) - '
                'real money first, then paper. Each system is measured on its own capital, time-weighted, with idle '
                'cash earning 6.75 %. Legacy holdings (chosen by neither system) are shown apart. The capital-move '
                'rule was fixed before the first result (docs/PREREG_capital_move.md).</div>', unsafe_allow_html=True)

    def _pct(v, d=1):
        return ("%+.*f %%" % (d, v * 100)) if v is not None and v == v else "—"

    _t = st.tabs(["💰 Real money", "📄 Paper", "⚖️ Capital decision & trade origin"])

    # ── real money ────────────────────────────────────────────────────────
    with _t[0]:
        _S = _se.series()
        if not len(_S):
            st.info("No equity snapshot yet - the first row is written by tonight's auto-pilot (Phase 12j, after 16:30). "
                    "From then on every session adds one row per system.")
        else:
            _M = _se.metrics(_S)
            _lab = {"v1": "v1 · current system", "v2": "v2 · Clenow", "legacy": "legacy"}
            _cols = st.columns(3)
            for _i, _s in enumerate(("v1", "v2", "legacy")):
                _m = _M.get(_s)
                if not _m:
                    continue
                with _cols[_i]:
                    st.markdown("**%s**" % _lab[_s])
                    st.metric("Equity", _inr(_m["equity"]), _pct(_m["twr"], 2) + " since %s" % _m["start"])
                    st.caption("Nifty 500 same days %s · max drawdown %s · %d holdings" % (
                        _pct(_m["bench"], 2), _pct(_m["max_dd"]), _m["n"]))
            _S2 = _S.copy()
            _S2["date"] = _pd.to_datetime(_S2["date"])
            _nav = _S2.pivot_table(index="date", columns="system", values="nav")
            _b = _S2.groupby("date")["bench"].first()
            if _b.notna().any():
                _nav["Nifty 500"] = _b / _b.dropna().iloc[0]
            st.line_chart(_nav.rename(columns=_lab), height=300)
            _rows = []
            for _s in ("v1", "v2", "legacy"):
                _m = _M.get(_s)
                if _m:
                    _rows.append({"system": _lab[_s], "days": _m["days"], "TWR": _pct(_m["twr"], 2),
                                  "annualised": _pct(_m["cagr"]) if _m["cagr"] is not None else "too early (< %d d)" % _se.MIN_DAYS_ANNUAL,
                                  "Nifty 500": _pct(_m["bench"], 2), "excess": _pct(_m["excess"], 2),
                                  "max DD": _pct(_m["max_dd"]), "vol (ann.)": _pct(_m["vol"]),
                                  "beta": round(_m["beta"], 2) if _m["beta"] is not None else "—",
                                  "MAR": round(_m["mar"], 2) if _m["mar"] is not None else "—",
                                  "worst month": _pct(_m["worst_month"]), "time invested": _pct(_m["invested"], 0)})
            st.dataframe(_pd.DataFrame(_rows), hide_index=True, use_container_width=True)
            _un = int(_S[_S["system"] == "v1"]["unclassified"].iloc[-1]) if (_S["system"] == "v1").any() else 0
            if _un:
                st.warning("%d open journal row(s) have no origin - counted as v1 until you mark them below." % _un)

        # trade stats since the comparison began
        _start = str(_S["date"].min()) if len(_S) else "2026-10-19"
        try:
            _con = _sq.connect(_jp.JOURNAL_DB)
            _J = _pd.read_sql("SELECT id, symbol, status, quantity, buy_price, exit_price, entry_date, exit_date, "
                              "exit_reason, setup, origin FROM journal", _con)
            _con.close()
        except Exception as _e:
            _J = _pd.DataFrame()
            st.error("journal not readable: %s" % _e)
        _ts = []
        if len(_J):
            _c1 = _J[(_J["status"].str.upper() == "CLOSED") & (_J["origin"] == "v1") &
                     (_J["exit_date"].astype(str) >= _start) & (_J["exit_reason"].astype(str) != "Converted to v2")].copy()
            _c1["ret"] = _c1["exit_price"] / _c1["buy_price"] - 1
            _c1["days"] = (_pd.to_datetime(_c1["exit_date"]) - _pd.to_datetime(_c1["entry_date"])).dt.days
            _ts.append(("v1 · current system", _c1["ret"], _c1["days"], (_c1["exit_price"] - _c1["buy_price"]) * _c1["quantity"]))
        _cl = _pd.DataFrame(_vl.load()["closed"])
        if len(_cl):
            _cl = _cl[_cl["exit_date"].astype(str) >= _start]
            _ts.append(("v2 · Clenow", _cl["exit"] / _cl["entry"] - 1,
                        (_pd.to_datetime(_cl["exit_date"]) - _pd.to_datetime(_cl["entry_date"])).dt.days,
                        (_cl["exit"] - _cl["entry"]) * _cl["sh"]))
        st.markdown("**Closed trades since %s**" % _start)
        _tr = []
        for _n, _r, _d, _p in _ts:
            if not len(_r):
                _tr.append({"system": _n, "closed": 0})
                continue
            _w = _r > 0
            _tr.append({"system": _n, "closed": len(_r), "win %": round(_w.mean() * 100, 0),
                        "payoff": round(_r[_w].mean() / -_r[~_w].mean(), 2) if _w.any() and (~_w).any() else "—",
                        "mean return": _pct(_r.mean()), "median hold (d)": int(_d.median()) if _d.notna().any() else "—",
                        "realised": _inr(float(_p.sum()))})
        if _tr:
            st.dataframe(_pd.DataFrame(_tr), hide_index=True, use_container_width=True)
        else:
            st.caption("No closed trades in either system since the comparison began.")
        st.caption("Returns are before tax and include brokerage only as recorded in the fills. A v1 holding CONVERTED "
                   "to v2 ends its v1 trade at the conversion price; it is not counted as a v1 exit here.")

    # ── paper ─────────────────────────────────────────────────────────────
    with _t[1]:
        st.markdown("Paper results need no capital decision and start earlier than real money. v1's paper cohort is "
                    "every **S4 TAKE IT** walked with the house rules (4 × ATR(D) stop, 3R/5R partials, Chandelier); "
                    "v2's paper books are the live forward runs of the rules (V2H = Clenow with house execution, "
                    "P1E = the tournament book).")
        _pt = _os.path.join(_os.path.dirname(_os.path.abspath(_p1.__file__)), "data", "paper_trades.csv")
        _a, _b2 = st.columns(2)
        with _a:
            st.markdown("**v1 · S4 TAKE IT · house rules**")
            if _os.path.exists(_pt):
                _P = _pd.read_csv(_pt)
                _P = _P[_P["cohort"] == "S4 TAKE IT · house rules"]
                _fill = _P[_P["fill_px"].notna()]
                _done = _fill[_fill["status"].astype(str).str.upper().isin(["CLOSED", "EXITED", "DONE"]) | _fill["exit_px"].notna()]
                st.metric("Net P&L (paper)", _inr(float(_fill["pnl_total"].sum())), "%d filled · %d closed" % (len(_fill), len(_done)))
                if len(_done):
                    _w = _done["pnl_total"] > 0
                    st.caption("win %.0f %% · median %s · mean R %.2f" % (
                        _w.mean() * 100, _pct(_done["pnl_pct"].median() / 100), _done["R_two_tier"].mean()))
                _eqv = _fill.assign(d=_pd.to_datetime(_fill["exit_ts"].fillna(_fill["fill_ts"]), errors="coerce")) \
                    .sort_values("d").set_index("d")["pnl_total"].cumsum()
                if len(_eqv):
                    st.line_chart(_eqv, height=220)
            else:
                st.info("data/paper_trades.csv not written yet (auto-pilot Phase 12g).")
        with _b2:
            st.markdown("**v2 · paper books**")
            _H = []
            for _bk in ("V2H", "P1E"):
                try:
                    _hs = _p1.load_state(_bk).get("history") or []
                    for _h in _hs:
                        _H.append({"date": _h["date"], "book": _bk, "equity": _h["equity"], "nifty500": _h.get("nifty500")})
                except Exception:
                    pass
            if _H:
                _HH = _pd.DataFrame(_H)
                _HH["date"] = _pd.to_datetime(_HH["date"])
                _pv = _HH.pivot_table(index="date", columns="book", values="equity")
                _first = _pv.iloc[0]
                _nb = _HH.groupby("date")["nifty500"].first()
                _chart = _pv / _first
                if _nb.notna().any():
                    _chart["Nifty 500"] = _nb / _nb.dropna().iloc[0]
                for _bk in _pv.columns:
                    st.metric(_bk, _inr(float(_pv[_bk].iloc[-1])), _pct(float(_pv[_bk].iloc[-1] / _first[_bk] - 1), 2))
                if len(_chart) > 1:
                    st.line_chart(_chart, height=220)
                else:
                    st.caption("One point so far (%s) - the curves grow nightly." % _pv.index[0].date())
            else:
                st.info("No v2 paper history yet.")
        st.caption("Paper and real money are never mixed: paper shows whether the rules work, the real-money tab whether "
                   "you can run them.")

    # ── capital decision & origin ─────────────────────────────────────────
    with _t[2]:
        _cr = _se.capital_rule()
        st.markdown("**The capital-move rule** (pre-registered 19-Oct-2026)")
        for _lbl, _ok, _nt in _cr["checks"]:
            st.markdown("%s %s · <span style='color:var(--muted)'>%s</span>" % (
                "✅" if _ok else ("⏳" if _ok is None else "❌"), _lbl, _nt), unsafe_allow_html=True)
        (st.success if _cr["verdict"].startswith("MOVE") else st.info)("**%s**" % _cr["verdict"])
        st.caption("A capital move or a Dhan top-up is recorded in data/system_transfers.csv (date, system, amount, note) "
                   "so it is excluded from return. One-third of v1's capital = %s at today's sizing." % _inr(
                       (_p1.v2_capital() * 2) * _se.MOVE_FRACTION))
        st.markdown("---")
        st.markdown("**Trade origin** — who chose each trade. v1 = the current system (GM + S4), legacy = chosen by neither "
                    "(before 1-Apr-2026, cash parks, the tax-harvest batch), v2 = Clenow. Change a row if the default is wrong.")
        try:
            _con = _sq.connect(_jp.JOURNAL_DB)
            _O = _pd.read_sql("SELECT id, symbol, status, entry_date, exit_date, quantity, buy_price, exit_price, "
                              "setup, origin FROM journal ORDER BY (UPPER(status)='OPEN') DESC, COALESCE(exit_date, entry_date) DESC", _con)
            _con.close()
        except Exception as _e:
            _O = _pd.DataFrame()
            st.error("journal not readable: %s" % _e)
        if len(_O):
            _O["check"] = ""
            _O.loc[_O["symbol"].isin(["GESHIP", "NAM-INDIA"]) & (_O["entry_date"].astype(str).str[:10] == "2026-06-02"),
                   "check"] = "entry date is the first sync, not the real buy - confirm"
            _O.loc[_O["origin"].isna(), "check"] = "no origin"
            _f = st.radio("Show", ["open", "all", "needs a check"], horizontal=True, key="vs_ofilter")
            _V = _O if _f == "all" else (_O[_O["status"].str.upper() == "OPEN"] if _f == "open" else _O[_O["check"] != ""])
            _ed = st.data_editor(_V[["id", "symbol", "status", "entry_date", "exit_date", "setup", "origin", "check"]],
                                 hide_index=True, use_container_width=True, disabled=["id", "symbol", "status", "entry_date",
                                                                                       "exit_date", "setup", "check"],
                                 column_config={"origin": st.column_config.SelectboxColumn("origin", options=["v1", "legacy"])},
                                 key="vs_origin_ed")
            _chg = [(int(r["id"]), r["origin"]) for (_, r), (_, o) in zip(_ed.iterrows(), _V.iterrows())
                    if r["origin"] != o["origin"] and r["origin"] in ("v1", "legacy") and not str(o["setup"] or "").upper().startswith("POS-V2")]
            if _chg and st.button("Save %d origin change(s)" % len(_chg), key="vs_origin_save"):
                for _rid, _o in _chg:
                    _to.set_origin(_rid, _o)
                st.success("Saved. The equity snapshot treats a re-classified open holding as a transfer between "
                           "systems (value moves, return does not).")
            st.caption("v2 rows (setup POS-V2) are set by v2_take.py and cannot be changed here.")
