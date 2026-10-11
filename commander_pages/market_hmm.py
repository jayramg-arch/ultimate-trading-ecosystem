# commander_pages/market_hmm.py - the REGIME (HMM) page of Web Commander (11-Oct-2026).
#
# Is the market calm or volatile? A Gaussian Hidden Markov Model on daily index returns.
# Engine: market_hmm.py (Streamlit-free). Runs in the app's namespace via
# commander_pages.run('market_hmm', globals()). Edit the page HERE, then restart.
if True:
    import numpy as _np
    import pandas as _pd
    import plotly.graph_objects as _go
    from plotly.subplots import make_subplots as _subplots
    import market_hmm as _hmm

    st.markdown('<div class="page-title">🎲 Market Regime · Hidden Markov Model</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Calm vs volatile, inferred from daily index returns // '
                'filtered probability = what was knowable at each close</div>', unsafe_allow_html=True)

    _c1, _c2, _c3 = st.columns([2, 1, 1])
    _idx_name = _c1.selectbox("Index", list(_hmm.INDEXES), index=0, key="hmm_idx")
    _K = _c2.selectbox("States", [2, 3], index=0, key="hmm_k",
                       help="2 = calm / volatile. 3 adds a middle 'normal' state. "
                            "BIC below says which fits this index better.")
    _per = _c3.selectbox("History", ["3y", "5y", "10y"], index=1, key="hmm_per")

    @st.cache_data(ttl=3600, show_spinner=False)
    def _hmm_run(sym, per, k):
        r = _hmm.analyse(sym, per, k)
        alt = _hmm.analyse(sym, per, 3 if k == 2 else 2)["model"]["bic"]
        return r, alt

    try:
        with st.spinner("Fitting the regime model..."):
            _r, _bic_alt = _hmm_run(_hmm.INDEXES[_idx_name], _per, _K)
    except Exception as _e:
        st.error(f"Regime model failed: {_e}")
        st.stop()

    _df, _labels, _today = _r["df"], _r["labels"], _r["today"]
    _COL = {"CALM": "#26A69A", "NORMAL": "#F2B705", "VOLATILE": "#EF5350"}
    _st_today = next(s for s in _r["states"] if s["state"] == _today["state"])

    # ── headline ─────────────────────────────────────────────────────────────
    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Regime today (filtered)", _today["state"],
               f"{_today['probs'][_today['state']]:.0%} probability")
    _m2.metric("Days in this regime", f"{_today['run_days']}",
               f"typical run ~{_st_today['exp_days']:.0f} days")
    _m3.metric("Regime volatility", f"{_st_today['ann_vol']:.1%} ann.",
               f"calm {_r['states'][0]['ann_vol']:.1%} · volatile {_r['states'][-1]['ann_vol']:.1%}",
               delta_color="off")
    _better = "this model" if _r["model"]["bic"] <= _bic_alt else f"the {3 if _K == 2 else 2}-state model"
    _m4.metric("Fit (BIC, lower = better)", f"{_r['model']['bic']:,.0f}",
               f"{3 if _K == 2 else 2}-state: {_bic_alt:,.0f} → {_better} fits better", delta_color="off")
    st.caption(f"{_idx_name} · last close {_today['date']} ₹{_today['close']:,.2f} · "
               + " · ".join(f"P({k}) {v:.0%}" for k, v in _today["probs"].items()))

    # ── chart: price shaded by regime · filtered probabilities · returns ───────
    _fig = _subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                     row_heights=[0.5, 0.25, 0.25],
                     subplot_titles=("Index close · shaded by regime (filtered)",
                                     "Regime probability (filtered — no look-ahead)",
                                     "Daily return · coloured by regime"))
    _fig.add_trace(_go.Scatter(x=_df.index, y=_df["Close"], name="Close",
                               line=dict(color="#90A4AE", width=1.4)), row=1, col=1)
    # shade contiguous runs of the filtered state
    _s = _df["state_filt"].values
    _start = 0
    for _i in range(1, len(_s) + 1):
        if _i == len(_s) or _s[_i] != _s[_start]:
            if _s[_start] != "CALM":
                _fig.add_vrect(x0=_df.index[_start], x1=_df.index[_i - 1],
                               fillcolor=_COL[_s[_start]], opacity=0.15, line_width=0,
                               row=1, col=1)
            _start = _i
    for _lab in _labels:
        _fig.add_trace(_go.Scatter(x=_df.index, y=_df[f"filt_{_lab}"], name=f"P({_lab})",
                                   stackgroup="p", line=dict(width=0.5, color=_COL[_lab])),
                       row=2, col=1)
    _fig.add_trace(_go.Bar(x=_df.index, y=_df["ret"] * 100, name="return %",
                           marker_color=[_COL[s] for s in _df["state_filt"]], showlegend=False),
                   row=3, col=1)
    _fig.update_yaxes(range=[0, 1], tickformat=".0%", row=2, col=1)
    _fig.update_yaxes(ticksuffix="%", row=3, col=1)
    _fig.update_layout(height=760, margin=dict(l=10, r=10, t=40, b=10),
                       legend=dict(orientation="h", y=1.04, x=0), hovermode="x unified",
                       template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(_fig, width="stretch")

    # ── state table + transition matrix ───────────────────────────────────────
    _t1, _t2 = st.columns([3, 2])
    with _t1:
        section("What each regime looks like")
        _tab = _pd.DataFrame(_r["states"])
        _tab = _tab.assign(
            ann_vol=_tab.ann_vol.map("{:.1%}".format), ann_drift=_tab.ann_drift.map("{:+.1%}".format),
            stay=_tab.stay.map("{:.1%}".format), exp_days=_tab.exp_days.map("{:.0f}".format),
            share=_tab.share.map("{:.0%}".format),
            fwd20_mean=_tab.fwd20_mean.map("{:+.2%}".format), fwd20_median=_tab.fwd20_median.map("{:+.2%}".format))
        _tab.columns = ["Regime", "Volatility (ann.)", "Drift (ann.)", "Stays next day", "Typical run (days)",
                        "Share of days", "Next 20d mean", "Next 20d median", "n"]
        st.dataframe(_tab, hide_index=True, width="stretch")
    with _t2:
        section("Transition matrix (row → next day)")
        _A = _pd.DataFrame(_r["model"]["A"], index=_labels, columns=_labels)
        st.dataframe(_A.style.format("{:.1%}"), width="stretch")

    with st.expander("How to read this page — and what it is NOT"):
        st.markdown(
            "- **Filtered vs smoothed.** Everything on this page uses the *filtered* probability: "
            "the regime given only the returns up to that close. A smoothed reading (using later "
            "data) looks cleaner on old dates but was never available live.\n"
            "- **The model's parameters are fitted on the whole window**, so even the filtered "
            "history carries some hindsight in its calibration. Treat it as a description of "
            "regimes, not as a backtested signal.\n"
            "- **It measures volatility, not direction.** The 'Next 20d' columns are in-sample "
            "description only — volatile spells have often been followed by rebounds, so do not "
            "read VOLATILE as 'sell'.\n"
            "- **How it fits the house rules.** The exposure rule (regime score, breaker) still "
            "decides size. This page answers a different question — how wide daily swings are — "
            "which is what stop distance and patience should respect.\n"
            "- **Engine:** Gaussian HMM, Baum-Welch with 8 random starts, states ordered by "
            "volatility (`market_hmm.py`). Recomputed at most hourly.")
