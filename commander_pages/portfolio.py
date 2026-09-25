# commander_pages/portfolio.py - the PORTFOLIO page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('portfolio', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🗂️ Portfolio Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Factor exposure · VaR/CVaR · Stress testing · Walk-forward backtest</div>', unsafe_allow_html=True)

    if not _PORT_OK:
        st.error("❌ portfolio_analytics module not available. Ensure portfolio_analytics.py is in the same folder.")
    else:
        # ── Holdings source ───────────────────────────────────────────────────
        _src_mode = st.radio(
            "Holdings source", ["🔄 Auto-load from Dhan", "✏️ Manual entry"],
            horizontal=True, key="port_src_mode",
            label_visibility="collapsed",
        )

        if _src_mode == "🔄 Auto-load from Dhan":
            # Build raw string from df_live_holdings (already fetched at app start)
            if app_state.df_live_holdings is not None and not app_state.df_live_holdings.empty:
                _dhan_lines = []
                for _, _dh_row in app_state.df_live_holdings.iterrows():
                    _dh_sym = str(_dh_row.get("Symbol", "")).strip()
                    if not _dh_sym:
                        continue
                    if not _dh_sym.endswith(".NS"):
                        _dh_sym += ".NS"
                    _dh_qty  = float(_dh_row.get("Quantity", 0) or 0)
                    _dh_cost = float(_dh_row.get("BuyPrice", 0) or 0)
                    if _dh_qty > 0:
                        _dhan_lines.append(f"{_dh_sym}, {_dh_qty:.0f}, {_dh_cost:.2f}")
                _holdings_raw = "\n".join(_dhan_lines)
                st.session_state.port_holdings_raw = _holdings_raw
                _n_pos = len(_dhan_lines)
                st.success(f"✅ Loaded {_n_pos} position{'s' if _n_pos != 1 else ''} from Dhan holdings")
                with st.expander("📋 View loaded holdings"):
                    st.code(_holdings_raw, language="text")
            else:
                _holdings_raw = st.session_state.port_holdings_raw
                st.warning("⚠️ Dhan holdings unavailable (check connection or token). Using last saved holdings below.")
                with st.expander("📋 Saved holdings"):
                    st.code(_holdings_raw or "(empty)", language="text")
        else:
            # Manual entry mode
            with st.expander("📋 Enter Holdings (symbol, quantity, avg_cost — one per line)", expanded=st.session_state.port_holdings_raw == ''):
                _ph_raw = st.text_area(
                    "Holdings",
                    value=st.session_state.port_holdings_raw,
                    height=140,
                    key="port_holdings_input",
                    label_visibility="collapsed",
                    placeholder="RELIANCE.NS, 100, 2500\nINFY, 50, 1800\nTCS, 20, 3600",
                )
                _pv_col1, _ = st.columns([2, 4])
                with _pv_col1:
                    _port_val_input = st.number_input(
                        "Portfolio Value Override (₹, 0 = auto)",
                        min_value=0.0, value=st.session_state.port_value,
                        step=100000.0, key="port_val_input",
                    )
                if st.button("💾 Save Holdings", key="port_save", type="primary"):
                    st.session_state.port_holdings_raw = _ph_raw
                    st.session_state.port_value = _port_val_input
                    st.success("Holdings saved.")
            _holdings_raw = st.session_state.port_holdings_raw

        _port_val = st.session_state.port_value or None

        if not _holdings_raw.strip():
            st.info("No holdings loaded. Switch to **Auto-load from Dhan** or enter positions manually.")
        else:
            _port_tab1, _port_tab2, _port_tab3, _port_tab4 = st.tabs([
                "📊 Overview", "📉 Risk & VaR", "🔥 Stress Test", "🔄 Walk-Forward"
            ])

            # ── TAB 1 — OVERVIEW ────────────────────────────────────────────
            with _port_tab1:
                section("Portfolio Overview")
                with st.spinner("Fetching current prices & sector data..."):
                    try:
                        _ov = portfolio_overview(_holdings_raw, _port_val)
                    except Exception as _ove:
                        _ov = {}; st.error(f"Overview failed: {_ove}")

                if not _ov:
                    st.warning("Could not build overview — check symbol format (e.g. RELIANCE.NS).")
                else:
                    # ── Live-price health check (10 May 2026) ────────────────
                    # Surface the case where data_provider + yfinance both
                    # failed to fetch live prices. Previously the page
                    # silently fell back to avg_cost → P&L mechanically
                    # showed 0.0% with no explanation.
                    _failed_syms = _ov.get("live_price_failures", [])
                    _ok_count    = _ov.get("live_price_ok_count", 0)
                    _total_pos   = _ov.get("num_positions", 0)
                    if _failed_syms:
                        st.warning(
                            f"⚠ **Live prices unavailable for {len(_failed_syms)}/"
                            f"{_total_pos} positions** — "
                            f"P&L on those positions reads 0% because the "
                            f"current_price fell back to avg_cost. "
                            f"Symbols: `{', '.join(_failed_syms[:8])}`"
                            + (f" + {len(_failed_syms)-8} more" if len(_failed_syms) > 8 else "")
                            + ". Likely yfinance/data_provider transient failure — try refresh "
                              "in 1-2 min, or check internet/cache."
                        )

                    # Summary metrics row
                    _ov_c = st.columns(4)
                    _ov_c[0].metric("Positions",     _ov.get("num_positions", 0))
                    _ov_c[1].metric("Portfolio Value", f"₹{_ov.get('total_value',0):,.0f}")
                    _ov_c[2].metric("Total Cost",     f"₹{_ov.get('total_cost',0):,.0f}")
                    _pnl = _ov.get("total_pnl_pct", 0)
                    # If ALL live prices failed, the P&L is mechanically 0% —
                    # show as "—" instead of misleading "+0.00%".
                    if _failed_syms and len(_failed_syms) == _total_pos:
                        _ov_c[3].metric("Unrealised P&L", "— (no live data)",
                                        help="All positions fell back to avg_cost. "
                                             "Wait for live price feed to recover.")
                    else:
                        _ov_c[3].metric("Unrealised P&L", f"{_pnl:+.2f}%",
                                        delta=f"{_pnl:+.2f}%",
                                        delta_color="normal" if _pnl >= 0 else "inverse")

                    st.markdown("---")
                    _ov_left, _ov_right = st.columns(2, gap="large")

                    with _ov_left:
                        # Holdings table
                        section("All Holdings")
                        _h_rows = []
                        for _h in _ov.get("holdings", []):
                            _h_rows.append({
                                "Symbol":    _h["symbol"].replace(".NS",""),
                                "Qty":       int(_h["quantity"]),
                                "Avg Cost":  f"₹{_h.get('avg_cost',0):,.0f}",
                                "LTP":       f"₹{_h.get('current_price',0):,.2f}",
                                "Mkt Value": f"₹{_h.get('market_value',0):,.0f}",
                                "Weight%":   f"{_h.get('weight',0)*100:.1f}%",
                                "P&L%":      f"{_h.get('pnl_pct',0):+.1f}%",
                                "Sector":    _h.get("sector","—"),
                            })
                        if _h_rows:
                            st.dataframe(pd.DataFrame(_h_rows), use_container_width=True, hide_index=True)

                        # HHI
                        _hhi = _ov.get("hhi", 0)
                        _hhi_label = "Low Concentration" if _hhi < 1000 else "Moderate" if _hhi < 2500 else "Highly Concentrated"
                        _hhi_color = "var(--bull)" if _hhi < 1000 else "var(--warn)" if _hhi < 2500 else "var(--bear)"
                        st.markdown(
                            f'<div class="metric-card" style="padding:10px 14px;margin-top:10px">'
                            f'<span style="color:var(--muted);font-size:0.78rem">HHI Concentration Index: </span>'
                            f'<span style="color:{_hhi_color};font-weight:700">{_hhi:.0f} — {_hhi_label}</span>'
                            f'</div>', unsafe_allow_html=True
                        )

                    with _ov_right:
                        # Top 5
                        section("Top 5 Holdings")
                        for _t5 in _ov.get("top5", []):
                            _w = _t5["weight_pct"]
                            st.markdown(
                                f'<div style="margin-bottom:6px">'
                                f'<div style="display:flex;justify-content:space-between;font-size:0.82rem;color:var(--ink)">'
                                f'<span>{_t5["symbol"]}</span><span style="color:var(--acc)">{_w:.1f}%</span></div>'
                                f'<div style="background:var(--rule);border-radius:4px;height:6px;margin-top:3px">'
                                f'<div style="background:var(--acc);width:{min(_w,100):.0f}%;height:100%;border-radius:4px"></div>'
                                f'</div></div>', unsafe_allow_html=True
                            )

                        # Sector pie chart — same dark-text fix as Stage Map donut
                        # (10 May 2026 user feedback: % labels were unreadable
                        # white-on-bright wedges).
                        section("Sector Allocation")
                        _sw = _ov.get("sector_weights", {})
                        if _sw:
                            _fig_sec = go.Figure(go.Pie(
                                labels=list(_sw.keys()),
                                values=list(_sw.values()),
                                hole=0.45,
                                textinfo="label+percent",
                                textfont=dict(size=12, color="#0a0e14"),  # dark text on wedge
                                textposition="inside",
                                insidetextorientation="horizontal",
                                marker=dict(colors=[
                                    "var(--acc)","var(--bull)","var(--warn)","var(--bear)","#a78bfa",
                                    "#f97316","#06b6d4","#ec4899","#84cc16","#14b8a6","#f43f5e"
                                ])
                            ))
                            _fig_sec.update_layout(
                                height=300, margin=dict(t=0,l=0,r=0,b=0),
                                paper_bgcolor="rgba(0,0,0,0)",
                                showlegend=False, font=dict(color="#E3EBEC")
                            )
                            st.plotly_chart(_fig_sec, use_container_width=True)

            # ── TAB 2 — RISK & VaR ──────────────────────────────────────────
            with _port_tab2:
                section("Risk Metrics & Factor Exposure")
                _r_c1, _r_c2 = st.columns(2)
                with _r_c1:
                    _var_conf  = st.selectbox("VaR Confidence", [0.90, 0.95, 0.99], index=1, key="var_conf",
                                               format_func=lambda x: f"{x*100:.0f}%")
                    _var_look  = st.selectbox("Lookback (days)", [126, 252, 504], index=1, key="var_look")
                with _r_c2:
                    _factor_period = st.selectbox("Factor Period", ["6mo","1y","2y"], index=1, key="factor_period")

                _r_run = st.button("⚙️ Compute Risk Metrics", key="risk_run", type="primary")
                if _r_run:
                    with st.spinner("Running risk calculations (may take ~30s)..."):
                        try:
                            _var_res = compute_var(_holdings_raw, _var_conf, _var_look, _port_val)
                        except Exception as _ve:
                            _var_res = {}; st.error(f"VaR failed: {_ve}")
                        try:
                            _fac_res = compute_factor_exposure(_holdings_raw, _factor_period)
                        except Exception as _fe:
                            _fac_res = {}; st.error(f"Factor exposure failed: {_fe}")

                    if _var_res:
                        st.markdown("---")
                        section("Value at Risk (Historical)")
                        _v1, _v2, _v3, _v4 = st.columns(4)
                        _v1.metric("1-Day VaR",       f"{_var_res['var_1d_pct']:.2f}%",    help="Historical simulation at chosen confidence")
                        _v2.metric("1-Day VaR (₹)",   f"₹{_var_res['var_1d_inr']:,.0f}")
                        _v3.metric("CVaR (ES)",        f"{_var_res['cvar_1d_pct']:.2f}%",   help="Expected loss beyond VaR threshold")
                        _v4.metric("10-Day VaR",       f"{_var_res['var_10d_pct']:.2f}%",   help="Scaled via sqrt-of-time rule")

                        _v5, _v6, _v7, _v8 = st.columns(4)
                        _v5.metric("Parametric VaR",  f"{_var_res['var_parametric_pct']:.2f}%", help="Normal distribution assumption")
                        _v6.metric("Annual Vol",       f"{_var_res['volatility_annual_pct']:.1f}%")
                        _v7.metric("Annual Return",    f"{_var_res['annualized_return_pct']:+.1f}%")
                        _v8.metric("Max Drawdown",     f"{_var_res['max_drawdown_pct']:.1f}%")

                    if _fac_res:
                        st.markdown("---")
                        section("Factor Exposure vs Nifty50")
                        _f1, _f2, _f3, _f4 = st.columns(4)
                        _beta = _fac_res.get("portfolio_beta", 0)
                        _beta_color = "var(--bear)" if _beta > 1.3 else "var(--warn)" if _beta > 1.0 else "var(--bull)"
                        _f1.metric("Portfolio Beta",   f"{_beta:.2f}",      help=">1 = more volatile than Nifty")
                        _f2.metric("Nifty Correlation",f"{_fac_res.get('benchmark_corr',0):.2f}")
                        _f3.metric("Tracking Error",   f"{_fac_res.get('tracking_error_annual',0):.1f}%", help="Annual active risk vs benchmark")
                        _f4.metric("Alpha (Annual)",   f"{_fac_res.get('alpha_annual',0):+.1f}%",         help="Jensen's alpha annualised")

                        _f5, _f6 = st.columns(2)
                        _f5.metric("Sharpe Ratio",     f"{_fac_res.get('sharpe',0):.2f}", help="Risk-free rate = 6.5%")
                        _f6.metric("Sortino Ratio",    f"{_fac_res.get('sortino',0):.2f}")

                        # Per-symbol beta bar chart
                        _sym_betas = _fac_res.get("symbol_betas", {})
                        if _sym_betas:
                            section("Per-Symbol Beta")
                            _sb_df = pd.DataFrame(
                                [{"Symbol": s, "Beta": b} for s, b in _sym_betas.items()]
                            ).sort_values("Beta", ascending=False)
                            _fig_beta = go.Figure(go.Bar(
                                x=_sb_df["Symbol"], y=_sb_df["Beta"],
                                marker_color=["#DC2626" if b > 1.2 else "#B45309" if b > 1.0 else "#1D4ED8"
                                              for b in _sb_df["Beta"]],
                                text=[f"{b:.2f}" for b in _sb_df["Beta"]], textposition="outside",
                            ))
                            _fig_beta.add_hline(y=1.0, line_dash="dash", line_color="#5C6B6E", line_width=1)
                            _fig_beta.update_layout(
                                height=280, margin=dict(t=20,l=0,r=0,b=40),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(tickfont=dict(size=9,color="#E3EBEC"), gridcolor="#E2E8F0"),
                                yaxis=dict(gridcolor="#E2E8F0", title="Beta"),
                                font=dict(color="#E3EBEC"),
                            )
                            st.plotly_chart(_fig_beta, use_container_width=True)

            # ── TAB 3 — STRESS TEST ─────────────────────────────────────────
            with _port_tab3:
                section("Historical Stress Scenarios")
                st.caption("Simulates how your current portfolio would have performed during past market events (using current weights applied to historical returns).")

                _st_run = st.button("🔥 Run Stress Test", key="stress_run", type="primary")
                if _st_run:
                    with st.spinner("Downloading historical data for all scenarios..."):
                        try:
                            _st_results = run_stress_test(_holdings_raw, _port_val)
                        except Exception as _ste:
                            _st_results = []; st.error(f"Stress test failed: {_ste}")

                    if _st_results:
                        # Summary table
                        _st_rows = []
                        for _s in _st_results:
                            _port_r = _s["portfolio_return"]
                            _bench_r= _s["benchmark_return"]
                            _exc    = _s["excess_return"]
                            _st_rows.append({
                                "Scenario":       _s["scenario"],
                                "Period":         f"{_s['start']} → {_s['end']}",
                                "Portfolio %":    f"{_port_r:+.1f}%",
                                "Nifty %":        f"{_bench_r:+.1f}%",
                                "Alpha":          f"{_exc:+.1f}%",
                                "P&L (₹)":        f"₹{_s['pnl_inr']:+,.0f}" if _s.get("pnl_inr") else "—",
                            })
                        st.dataframe(pd.DataFrame(_st_rows), use_container_width=True, hide_index=True)

                        # Bar chart — portfolio vs benchmark per scenario
                        _sc_labels = [_s["scenario"][:30] for _s in _st_results]
                        _sc_port   = [_s["portfolio_return"] for _s in _st_results]
                        _sc_bench  = [_s["benchmark_return"]  for _s in _st_results]

                        _fig_st = go.Figure()
                        _fig_st.add_trace(go.Bar(
                            name="Portfolio", x=_sc_labels, y=_sc_port,
                            marker_color=["#15803D" if v >= 0 else "#DC2626" for v in _sc_port],
                            text=[f"{v:+.1f}%" for v in _sc_port], textposition="outside",
                        ))
                        _fig_st.add_trace(go.Bar(
                            name="Nifty50", x=_sc_labels, y=_sc_bench,
                            marker_color="rgba(88,166,255,0.5)",
                            text=[f"{v:+.1f}%" for v in _sc_bench], textposition="outside",
                        ))
                        _fig_st.update_layout(
                            barmode="group", height=360,
                            margin=dict(t=20,l=0,r=0,b=100),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(tickangle=-30, tickfont=dict(size=9,color="#E3EBEC"), gridcolor="#E2E8F0"),
                            yaxis=dict(gridcolor="#E2E8F0", title="Return (%)"),
                            legend=dict(font=dict(size=10, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#E3EBEC"),
                        )
                        st.plotly_chart(_fig_st, use_container_width=True)
                    elif _st_run:
                        st.info("No scenario data returned — check holdings format or internet connection.")
                else:
                    st.info("Click **Run Stress Test** to simulate your portfolio across 6 historical market events.")

            # ── TAB 4 — WALK-FORWARD BACKTEST ───────────────────────────────
            with _port_tab4:
                section("Walk-Forward Weinstein Stage 2 Backtest")
                st.caption("Enters stocks when price > SMA50 & SMA200. Equal-weight. Rebalances on schedule.")

                _wf_c1, _wf_c2, _wf_c3 = st.columns(3)
                with _wf_c1:
                    _wf_start = st.date_input("Start Date", value=pd.Timestamp("2022-01-01"), key="wf_start")
                with _wf_c2:
                    _wf_rebal = st.selectbox("Rebalance", ["Weekly (1w)","Bi-Weekly (2w)","Monthly (4w)"],
                                              index=2, key="wf_rebal")
                    _wf_rebal_weeks = {"Weekly (1w)": 1, "Bi-Weekly (2w)": 2, "Monthly (4w)": 4}[_wf_rebal]
                with _wf_c3:
                    _wf_univ_choice = st.selectbox("Universe", ["Use my holdings","Nifty 50 subset","Custom"], key="wf_univ")

                if _wf_univ_choice == "Custom":
                    _wf_custom = st.text_area("Custom universe (one symbol per line)",
                                               height=80, key="wf_custom_syms",
                                               placeholder="RELIANCE\nINFY\nTCS")
                    _wf_universe_raw = _wf_custom
                elif _wf_univ_choice == "Use my holdings":
                    _parsed_h = parse_holdings(_holdings_raw)
                    _wf_universe_raw = "\n".join(h["symbol"] for h in _parsed_h)
                else:
                    _wf_universe_raw = "\n".join([
                        "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY",
                        "HINDUNILVR","ITC","SBIN","BHARTIARTL","KOTAKBANK",
                        "LT","AXISBANK","ASIANPAINT","MARUTI","TITAN",
                        "BAJFINANCE","WIPRO","ULTRACEMCO","POWERGRID","NTPC",
                    ])

                _wf_run = st.button("🔄 Run Backtest", key="wf_run", type="primary")

                if _wf_run:
                    with st.spinner("Running walk-forward backtest (may take 60–120s for large universes)..."):
                        try:
                            _wf_res = run_walkforward_backtest(
                                _wf_universe_raw,
                                start=str(_wf_start),
                                rebalance_weeks=_wf_rebal_weeks,
                            )
                        except Exception as _wfe:
                            _wf_res = {}; st.error(f"Backtest failed: {_wfe}")

                    if _wf_res:
                        # Stats header
                        _wf_cols = st.columns(5)
                        _wf_cols[0].metric("Strategy CAGR",  f"{_wf_res['cagr_pct']:+.1f}%")
                        _wf_cols[1].metric("Benchmark CAGR", f"{_wf_res['benchmark_cagr_pct']:+.1f}%",
                                           delta=f"{_wf_res['cagr_pct']-_wf_res['benchmark_cagr_pct']:+.1f}% vs Nifty")
                        _wf_cols[2].metric("Sharpe",         f"{_wf_res['sharpe']:.2f}")
                        _wf_cols[3].metric("Max Drawdown",   f"{_wf_res['max_drawdown_pct']:.1f}%")
                        _wf_cols[4].metric("Avg Positions",  f"{_wf_res['avg_positions']:.0f}")

                        st.markdown("---")
                        # Equity curve chart
                        _eq = pd.DataFrame(_wf_res["equity_curve"])
                        _fig_eq = go.Figure()
                        _fig_eq.add_trace(go.Scatter(
                            x=_eq["date"], y=_eq["portfolio_value"],
                            name="Strategy", line=dict(color="#15803D", width=2),
                        ))
                        _fig_eq.add_trace(go.Scatter(
                            x=_eq["date"], y=_eq["benchmark_value"],
                            name="Nifty50 (buy & hold)", line=dict(color="#1D4ED8", width=1.5, dash="dot"),
                        ))
                        _fig_eq.add_hline(y=100, line_dash="dot", line_color="#5C6B6E", line_width=1)
                        _fig_eq.update_layout(
                            height=380, margin=dict(t=10,l=0,r=0,b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(gridcolor="#E2E8F0"),
                            yaxis=dict(gridcolor="#E2E8F0", title="Indexed (Base 100)"),
                            legend=dict(font=dict(size=10, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#E3EBEC"),
                        )
                        st.plotly_chart(_fig_eq, use_container_width=True)
                        st.caption(f"Total return: Strategy {_wf_res['total_return_pct']:+.1f}% | Nifty {_wf_res['benchmark_total_return_pct']:+.1f}% | Rebalances: {_wf_res['num_rebalances']}")
                    elif _wf_run:
                        st.info("No backtest results — check universe symbols or widen the date range.")
                else:
                    st.info("Configure the parameters above and click **Run Backtest** to begin.")

        # ── Portfolio Export ─────────────────────────────────────────────────
        st.markdown("---")
        section("Export")
        _px1, _px2 = st.columns(2, gap="small")
        with _px1:
            if app_state.df_live_holdings is not None and not app_state.df_live_holdings.empty:
                st.download_button(
                    "📥 Download Holdings (CSV)",
                    data=app_state.df_live_holdings.to_csv(index=False).encode("utf-8"),
                    file_name=f"Holdings_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", use_container_width=True, key="port_dl_csv",
                )
            else:
                st.caption("Holdings not loaded — use Auto-load from Dhan above.")
        with _px2:
            if st.session_state.get("port_holdings_raw") and _GEMINI_OK:
                if st.button("🤖 AI Portfolio Analysis Report", use_container_width=True,
                             key="port_ai_dl"):
                    with st.spinner("Generating AI analysis…"):
                        try:
                            _px_analytics = {}
                            if _PORT_OK:
                                _px_ov = portfolio_overview(
                                    st.session_state["port_holdings_raw"], _port_val)
                                _px_analytics = _px_ov if isinstance(_px_ov, dict) else {}
                            _px_report = generate_portfolio_review(
                                app_state.df_live_holdings if app_state.df_live_holdings is not None else pd.DataFrame(),
                                _px_analytics)
                            st.session_state["port_ai_report"] = _px_report
                        except Exception as _pxe:
                            st.error(f"AI report failed: {_pxe}")
                if st.session_state.get("port_ai_report"):
                    st.download_button(
                        "📥 Save AI Report (.txt)",
                        data=st.session_state["port_ai_report"],
                        file_name=f"Portfolio_AI_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain", use_container_width=True, key="port_ai_dl2",
                    )
