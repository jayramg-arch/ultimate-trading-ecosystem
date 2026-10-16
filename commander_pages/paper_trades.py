# commander_pages/paper_trades.py - the PAPER TRADES page of Web Commander (13-Oct-2026).
#
# Every TAKE taken on paper the way Jay takes a trade: Risk Allocator quantity, OCO-1 at T1,
# OCO-2 at T2, a stop-only runner, the thesis close, the Disaster SL and the house trail - with a
# post-mortem per trade. Engine: paper_trades.py (Streamlit-free, writes
# data/paper_trades.csv; rebuilt nightly by auto-pilot Phase 12g and by the button here).
# Runs in the app's namespace via commander_pages.run('paper_trades', globals()).
if True:
    import os as _os
    import datetime as _dt
    import pandas as _pd
    import plotly.graph_objects as _go
    import paper_trades as _pt

    st.markdown('<div class="page-title">📄 Paper Trades · the ecosystem on paper</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Every TAKE, taken the way you take it: Risk Allocator quantity · OCO-1 at T1 · '
                'OCO-2 at T2 · a stop-only runner on the house trail · out on a close below the thesis or a touch '
                'of the Disaster SL // nothing is ordered</div>', unsafe_allow_html=True)

    _b1, _b2 = st.columns([1, 3])
    if _b1.button("🔄 Rebuild", help="Re-reads the Reviewer Log and walks every TAKE to the last close (~1 min)"):
        with st.spinner("Walking every TAKE through its bars..."):
            try:
                _pt.build()
            except Exception as _e:
                st.error(f"Rebuild failed: {_e}")
    if not _os.path.exists(_pt.OUT):
        st.info("No paper trades yet - press Rebuild (the auto-pilot also rebuilds them every evening).")
        st.stop()
    _built = _dt.datetime.fromtimestamp(_os.path.getmtime(_pt.OUT))
    _b2.caption(f"Built {_built:%d %b %Y %H:%M} IST · bars to the last close · "
                f"size = house risk (stock 0.5% / ETF 0.75%) capped per trade, half on 'TAKE · reduced size'")

    _df = _pd.read_csv(_pt.OUT)
    _cohorts = [c for c in _pt.COHORTS if c in set(_df.get("cohort", _pd.Series(dtype=str)).astype(str))]
    _sel = st.radio("Cohort", _cohorts, horizontal=True, key="paper_cohort",
                    help="Reviewer TAKE = the AI's final ruling after every house gate. "
                         "S4 TAKE IT = S4's own panel verdict on the same read, which no gate rewrites - "
                         "since 6 Oct the exposure rule keeps the reviewer at WAIT, so this cohort keeps "
                         "measuring the system.") if _cohorts else None
    _d = _df[_df["cohort"] == _sel] if _sel else _df
    _s = _pt.summary(_d)
    if not _s or not _s.get("traded"):
        st.info("Nothing traded in this cohort yet."); st.stop()
    _inr = _pt.inr

    def _pct(x):
        return "—" if x is None else f"{100 * x:.0f}%"

    # ── account strip ───────────────────────────────────────────────────────
    _a = st.columns(6)
    _a[0].metric("Net P&L", _inr(_s["pnl_total"]), f"{_s['traded']} trades · {_s['open']} open", delta_color="off")
    _a[1].metric("Realised", _inr(_s["pnl_realised"]))
    _a[2].metric("Open P&L", _inr(_s["pnl_open"]), f"deployed {_inr(_s['invested_open'])}", delta_color="off")
    _a[3].metric("Win rate (closed)", _pct(_s.get("win_rate")),
                 f"PF {_s['profit_factor']:.2f}" if _s.get("profit_factor") is not None else "PF —", delta_color="off")
    _a[4].metric("Avg win / loss", f"{_inr(_s.get('avg_win'))} / {_inr(_s.get('avg_loss'))}")
    _a[5].metric("Mean R", f"{_s['R_mean']:+.2f}R", f"hard-SL only {_s['R_hard_only_mean']:+.2f}R", delta_color="off",
                 help="Two-tier (thesis close or Disaster SL) vs the same trades with the thesis ignored")
    st.caption(f"T1 reached {_pct(_s.get('t1_rate'))} · T2 reached {_pct(_s.get('t2_rate'))} · exits: "
               f"{_s.get('hard_exits', 0)} Disaster SL · {_s.get('trail_exits', 0)} trail · {_s.get('thesis_exits', 0)} thesis close · "
               f"median stop {_s.get('median_risk_atr_d') or '—'}× daily ATR · "
               + " · ".join(f"{k} {v}" for k, v in (_s.get("verdicts") or {}).items())
               + f" · not traded: {_s['repeat']} repeats, {_s['no_fill']} unfilled, {_s['no_levels']} no levels")

    # ── equity curve ────────────────────────────────────────────────────────
    _cl = _d[_d["status"] == "closed"].copy()
    if len(_cl):
        _cl["_x"] = _pd.to_datetime(_cl["exit_ts"], errors="coerce")
        _eq = _cl.dropna(subset=["_x"]).sort_values("_x")
        _eq["cum"] = _eq["pnl_total"].cumsum()
        _fig = _go.Figure()
        _fig.add_trace(_go.Scatter(x=_eq["_x"], y=_eq["cum"], mode="lines+markers", name="realised",
                                   line=dict(width=2), hovertext=_eq["symbol"]))
        _fig.add_hline(y=0, line_dash="dot", opacity=0.5)
        if _s["pnl_open"]:
            _fig.add_trace(_go.Scatter(x=[_eq["_x"].max()], y=[_eq["cum"].iloc[-1] + _s["pnl_open"]],
                                       mode="markers", marker=dict(size=12, symbol="diamond"),
                                       name="+ open P&L"))
        _fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10), title="Equity curve (₹, realised)",
                           showlegend=True, legend=dict(orientation="h"))
        st.plotly_chart(_fig, use_container_width=True)

    # ── positions ───────────────────────────────────────────────────────────
    _op = _d[_d["status"] == "open"].copy()
    st.markdown(f"##### Open positions ({len(_op)})")
    if len(_op):
        _op["Qty (OCO-1/OCO-2/Run)"] = (_op["qty"].astype(int).astype(str) + " (" + _op["q_oco1"].astype(int).astype(str)
                                       + "/" + _op["q_oco2"].astype(int).astype(str) + "/" + _op["q_runner"].astype(int).astype(str) + ")")
        _op["P&L"] = _op["pnl_total"].map(_inr)
        _op["Invested"] = _op["invested"].map(_inr)
        st.dataframe(
            _op.sort_values("R_two_tier", ascending=False)[[
                "symbol", "verdict", "Qty (OCO-1/OCO-2/Run)", "fill_px", "last_close", "Invested", "P&L", "pnl_pct",
                "R_two_tier", "stop", "trail_stop", "thesis", "t1", "t2", "oco1", "oco2", "runner",
                "bars_held", "trend_now", "review_ts", "ruling"]],
            hide_index=True, width="stretch",
            column_config={"symbol": "Symbol", "verdict": "Status", "fill_px": "Avg", "last_close": "LTP",
                           "pnl_pct": st.column_config.NumberColumn("P&L %", format="%+.2f"),
                           "R_two_tier": st.column_config.NumberColumn("R", format="%+.2f"),
                           "stop": "Disaster SL", "trail_stop": "Trail SL", "thesis": "Thesis SL",
                           "oco1": "OCO-1", "oco2": "OCO-2", "runner": "Runner", "bars_held": "Bars",
                           "trend_now": "Trend now", "review_ts": "Taken", "ruling": "Ruling"})
    else:
        st.caption("No open paper positions.")

    # ── closed blotter ──────────────────────────────────────────────────────
    st.markdown(f"##### Closed trades ({len(_cl)})")
    if len(_cl):
        _cl["P&L"] = _cl["pnl_total"].map(_inr)
        _cl["Hard-SL only"] = _cl["pnl_hard_only"].map(_inr)
        st.dataframe(
            _cl.sort_values("exit_ts", ascending=False)[[
                "symbol", "verdict", "review_ts", "qty", "fill_px", "exit", "exit_ts", "exit_px", "P&L", "R_two_tier",
                "Hard-SL only", "mfe_R", "oco1", "oco2", "runner", "risk_atr_d", "went_wrong", "tweak"]],
            hide_index=True, width="stretch",
            column_config={"symbol": "Symbol", "verdict": "Verdict", "review_ts": "Taken", "qty": "Qty",
                           "fill_px": "Avg", "exit": "Exit", "exit_ts": "Exit at", "exit_px": "Exit px",
                           "R_two_tier": st.column_config.NumberColumn("R", format="%+.2f"),
                           "mfe_R": st.column_config.NumberColumn("Best R", format="%+.2f"),
                           "risk_atr_d": st.column_config.NumberColumn("Stop × ATR(D)", format="%.2f"),
                           "oco1": "OCO-1", "oco2": "OCO-2", "runner": "Runner",
                           "went_wrong": st.column_config.TextColumn("What went wrong", width="large"),
                           "tweak": st.column_config.TextColumn("Tweak", width="large")})

    # ── trade card ──────────────────────────────────────────────────────────
    _t = _d[_d["status"].isin(["open", "closed"])].copy()
    st.markdown("##### Trade review")
    _opts = (_t["symbol"] + " · " + _t["review_ts"] + " · " + _t["status"]).tolist()
    _pick = st.selectbox("Pick a trade", _opts, key="paper_pick")
    if _pick:
        _r = _t.iloc[_opts.index(_pick)]
        _c1, _c2 = st.columns([1, 1])
        with _c1:
            st.markdown(f"**{_r['symbol']}** · {_r['verdict']} · {_r['plan_type']} on {_r['clock']} · "
                        f"{int(_r['qty'])} sh ({int(_r['q_oco1'])} / {int(_r['q_oco2'])} / {int(_r['q_runner'])})"
                        + (" · **reduced size**" if bool(_r.get("reduced")) else ""))
            st.markdown(f"**Thesis / logic** — {_r.get('thesis_logic') or '—'}")
            st.markdown(f"**Ruling** — {_r.get('ruling') or '—'}")
            st.markdown(f"**Trend now** — {_r.get('trend_now') or '—'}")
            st.markdown(f"**Plan** — entry {_r['entry']} · filled {_r['fill_px']} ({_r['order']}, {_r['fill_ts']}) · "
                        f"Disaster SL {_r['stop']} · thesis {_r['thesis']} · T1 {_r['t1']} · T2 {_r['t2']} · "
                        f"stop {_r.get('risk_atr_d')}× ATR(D)")
        with _c2:
            st.markdown(f"**Result** — {_inr(_r['pnl_total'])} ({_r['R_two_tier']:+.2f}R) · exit: {_r['exit']} "
                        f"{_r.get('exit_ts') or ''} · best {_r['mfe_R']:+.2f}R / worst {_r['mae_R']:+.2f}R · "
                        f"hard-SL only: {_inr(_r['pnl_hard_only'])}"
                        + (f" · 4× ATR stop: {_inr(_r['pnl_4atr'])}" if _pd.notna(_r.get("pnl_4atr")) else ""))
            st.markdown(f"**Legs** — OCO-1 {_r['oco1']} · OCO-2 {_r['oco2']} · runner {_r['runner']} "
                        f"(trail at {_r.get('trail_stop')})")
            st.success(f"**What went well** — {_r.get('went_well')}")
            st.error(f"**What went wrong** — {_r.get('went_wrong')}")
            st.info(f"**Tweak** — {_r.get('tweak')}")

    # ── splits ──────────────────────────────────────────────────────────────
    st.markdown("##### Before and after the 4× ATR(D) positional stop floor (3 Oct)")
    _g = _pt.by_group(_d, "era")
    if not _g.empty:
        st.dataframe(_g, hide_index=True, width="stretch")
        st.caption("Read the era split before the totals: reviews before 3 Oct carried stops near 1.4× daily ATR, "
                   "the band that stopped out 80% of the time. A handful of trades proves nothing.")

    _sk = _d[~_d["status"].isin(["open", "closed"])]
    with st.expander(f"Not traded ({len(_sk)}) — repeats, unfilled orders, missing levels"):
        st.dataframe(_sk[["symbol", "review_ts", "review_tf", "status", "entry", "stop", "ruling"]],
                     hide_index=True, width="stretch")

    with st.expander("How a paper trade is run"):
        st.markdown(
            "- **Size** — house risk (stock 0.5%, ETF 0.75% of the sizing capital) capped at the per-trade rupee cap, "
            "as the Risk Allocator sizes it; **half** on a 'TAKE · reduced size' ruling.\n"
            "- **Orders** — the Allocator's default split: OCO-1 at T1 and OCO-2 at T2 (positional 25% each, swing 33%), "
            "each with the Disaster SL; the balance is a stop-only runner. Every target leg gets at least one share.\n"
            "- **Levels** — Reviewer TAKE: the reviewer's own plan. S4 TAKE IT: S4's panel plan. Thesis = S4's INVAL. "
            "Missing targets → the canon (positional 3R/5R, swing 2R/4R).\n"
            "- **Clock** — Daily bars for every trade: risk and trade management are Daily only (swing names "
            "time their entry on 75m/125m, but are managed on the Daily close).\n"
            "- **Fill** — the plan entry within ~3 sessions: a limit at/below the last close, else a buy-stop.\n"
            "- **Exits** — Disaster SL on a touch (gaps at the open; stop-first when one bar reaches both a stop and a "
            "target); the house Chandelier trail (positional 22 bars × 4.5 ATR, swing 14 × 1.5), tighten-only; a "
            "CLOSE below the thesis exits every remaining leg.\n"
            "- **Review** — thesis = the review's DECIDING FACTOR (S4: its verdict); trend now = today's weekly stage "
            "and trend; what went well/wrong and the tweak are measured on the trade's own bars (best/worst R, wick "
            "sweeps, recovery after the exit, a 4× ATR(D) stop at house size, the hard-SL-only result).\n"
            "- One paper position per symbol per cohort. Display only: nothing is ordered, the journal is untouched.")
