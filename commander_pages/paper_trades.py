# commander_pages/paper_trades.py - the PAPER TRADES page of Web Commander (13-Oct-2026).
#
# Every TAKE, taken on paper: entry, thesis SL, hard SL, T1, T2, tracked bar by bar.
# Engine: paper_trades.py (Streamlit-free, writes data/paper_trades.csv; rebuilt nightly by
# the auto-pilot and by the button here). Runs in the app's namespace via
# commander_pages.run('paper_trades', globals()). Edit the page HERE, then restart.
if True:
    import os as _os
    import datetime as _dt
    import pandas as _pd
    import paper_trades as _pt

    st.markdown('<div class="page-title">📄 Paper Trades · how the ecosystem is doing</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Every TAKE taken on paper: filled at the plan entry, then tracked bar by bar '
                'to the thesis SL, the hard SL, T1 and T2 // in R, never rupees // nothing is ordered</div>',
                unsafe_allow_html=True)

    _b1, _b2 = st.columns([1, 3])
    if _b1.button("🔄 Rebuild paper trades", help="Re-reads the Reviewer Log and walks every TAKE to today's bars (~30-60 s)"):
        with st.spinner("Walking every TAKE through its bars..."):
            try:
                _pt.build()
            except Exception as _e:
                st.error(f"Rebuild failed: {_e}")
    if not _os.path.exists(_pt.OUT):
        st.info("No paper trades yet - press Rebuild (the auto-pilot also builds them every evening).")
        st.stop()
    _built = _dt.datetime.fromtimestamp(_os.path.getmtime(_pt.OUT))
    _b2.caption(f"Built {_built:%d %b %Y %H:%M} IST · source: Reviewer Log ({_pt.LOG.split(_os.sep)[-1]}) · "
                "bars to the last close")

    _df = _pd.read_csv(_pt.OUT)
    _cohorts = [c for c in _pt.COHORTS if c in set(_df.get("cohort", _pd.Series(dtype=str)).astype(str))]
    _sel = st.radio("Cohort", _cohorts, horizontal=True, key="paper_cohort",
                    help="Reviewer TAKE = the AI's final ruling after every house gate. "
                         "S4 TAKE IT = S4's own panel verdict on the same read, which no gate rewrites - "
                         "since 6 Oct the exposure rule keeps the reviewer at WAIT, so this cohort keeps "
                         "measuring the system.") if _cohorts else None
    _d = _df[_df["cohort"] == _sel] if _sel else _df
    _s = _pt.summary(_d)
    if not _s:
        st.info("Nothing in this cohort yet."); st.stop()

    def _pct(x):
        return "—" if x is None else f"{100 * x:.0f}%"

    def _r(x):
        return "—" if x is None or x != x else f"{x:+.2f}R"

    _m = st.columns(6)
    _m[0].metric("TAKEs", _s["takes"], help="Every TAKE in the cohort, including repeats and unfilled ones")
    _m[1].metric("Paper trades", _s["traded"], f"{_s['open']} open", delta_color="off")
    _m[2].metric("T1 reached", _pct(_s.get("t1_rate")), help="Share of paper trades whose high reached T1")
    _m[3].metric("T2 reached", _pct(_s.get("t2_rate")))
    _m[4].metric("Mean R · two-tier", _r(_s.get("R_two_tier_mean")),
                 f"median {_r(_s.get('R_two_tier_median'))}", delta_color="off",
                 help="Exit on a CLOSE below the thesis or a touch of the hard SL; open trades marked to the last close")
    _m[5].metric("Mean R · hard SL only", _r(_s.get("R_hard_only_mean")),
                 f"median {_r(_s.get('R_hard_only_median'))}", delta_color="off",
                 help="The same trades with the thesis ignored - the difference is what the thesis rule is worth")
    st.caption(f"Exits so far: {_s.get('thesis_exits', 0)} on the thesis close · {_s.get('hard_exits', 0)} on the hard SL · "
               f"win {_pct(_s.get('win_two_tier'))} · median stop {_s.get('median_risk_atr_d') or '—'}× daily ATR · "
               f"skipped: {_s['repeat']} repeats (paper position already open), {_s['no_fill']} unfilled, "
               f"{_s['no_levels']} without usable levels")

    st.markdown("##### By era — before and after the 4× ATR(D) positional stop floor (3 Oct)")
    _g = _pt.by_group(_d, "era")
    if not _g.empty:
        st.dataframe(_g, hide_index=True, width="stretch")
        st.caption("Read the era split before the totals: reviews before 3 Oct carried stops near 1.4× daily ATR, "
                   "the band that stopped out 80% of the time. Small samples - a handful of trades proves nothing.")

    _cols_open = ["symbol", "review_ts", "plan_type", "clock", "fill_ts", "fill_px", "thesis", "stop",
                  "t1", "t2", "last_close", "R_two_tier", "t1_hit", "t2_hit", "risk_atr_d", "bars_held", "ruling"]
    _op = _d[_d["status"] == "open"].copy()
    st.markdown(f"##### Open paper positions ({len(_op)})")
    if len(_op):
        _op["to thesis %"] = ((_op["last_close"] - _op["thesis"]) / _op["last_close"] * 100).round(1)
        _op["to hard SL %"] = ((_op["last_close"] - _op["stop"]) / _op["last_close"] * 100).round(1)
        st.dataframe(_op[[c for c in _cols_open if c in _op] + ["to thesis %", "to hard SL %"]]
                     .sort_values("R_two_tier", ascending=False),
                     hide_index=True, width="stretch",
                     column_config={"R_two_tier": st.column_config.NumberColumn("R now", format="%+.2f"),
                                    "risk_atr_d": st.column_config.NumberColumn("stop × ATR(D)", format="%.2f")})
    else:
        st.caption("None open.")

    _cl = _d[_d["status"] == "closed"].copy()
    st.markdown(f"##### Closed paper trades ({len(_cl)})")
    if len(_cl):
        st.dataframe(_cl[["symbol", "review_ts", "plan_type", "clock", "fill_ts", "fill_px", "thesis", "stop", "t1", "t2",
                          "t1_hit", "t2_hit", "exit", "exit_ts", "exit_px", "R_two_tier", "exit_hard_only", "R_hard_only",
                          "risk_atr_d", "era"]].sort_values("exit_ts", ascending=False),
                     hide_index=True, width="stretch",
                     column_config={"R_two_tier": st.column_config.NumberColumn("R two-tier", format="%+.2f"),
                                    "R_hard_only": st.column_config.NumberColumn("R hard only", format="%+.2f"),
                                    "risk_atr_d": st.column_config.NumberColumn("stop × ATR(D)", format="%.2f")})

    _sk = _d[~_d["status"].isin(["open", "closed"])]
    with st.expander(f"Not paper-traded ({len(_sk)}) — repeats, unfilled orders, missing levels"):
        st.dataframe(_sk[["symbol", "review_ts", "review_tf", "status", "entry", "stop", "ruling"]],
                     hide_index=True, width="stretch")

    with st.expander("How a paper trade is scored"):
        st.markdown(
            "- **Levels** — Reviewer TAKE: the reviewer's own plan (R-CHECK). S4 TAKE IT: S4's panel plan. "
            "**Thesis** = S4's INVAL on the review's panel. Missing T1/T2 → the house canon off the plan's stop "
            "(positional 3R/5R, swing 2R/4R).\n"
            "- **Clock** — positional on Daily bars, swing on the review's 75m/125m bars (125m for a Daily review).\n"
            "- **Fill** — the plan entry within ~3 sessions: a buy-limit when the entry is at or below the last "
            "closed bar's close, else a buy-stop. Gaps fill at the open.\n"
            "- **Exits** — hard SL on a touch (gaps fill at the open); thesis on a CLOSE below it (only when the "
            "thesis sits above the stop). A bar that reaches both a stop and a target is scored stop-first.\n"
            "- **Partials** — house canon: positional 25% at T1 + 25% at T2, swing 33% + 33%; the rest exits on the "
            "stop/thesis or is marked to the last close.\n"
            "- **One position per symbol** — a TAKE while that name's paper trade is still open is a repeat.\n"
            "- Display only: nothing is ordered, the journal is not touched.")
