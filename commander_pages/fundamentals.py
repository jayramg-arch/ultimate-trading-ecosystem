# commander_pages/fundamentals.py - the FUNDAMENTALS page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('fundamentals', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📊 Fundamentals Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Valuation multiples, earnings quality, balance sheet health, screening — powered by yfinance</div>', unsafe_allow_html=True)

    if not _FUND_OK:
        st.error("❌ fundamental_hub module not available.")
    else:
        # ── Symbol input (shared across all tabs) ────────────────────────────
        _fd_col1, _fd_col2 = st.columns([2, 4])
        with _fd_col1:
            _fd_sym = st.text_input(
                "NSE Symbol", value=st.session_state.get("fd_symbol","RELIANCE.NS"),
                key="fd_sym_input", placeholder="e.g. INFY.NS, TCS.NS"
            ).strip().upper()
            if _fd_sym and not _fd_sym.endswith(".NS"):
                _fd_sym += ".NS"
            if _fd_sym:
                st.session_state["fd_symbol"] = _fd_sym

        _fd_tab1, _fd_tab2, _fd_tab3 = st.tabs(["📈 Snapshot", "🎯 Scorecard", "🔍 Screen"])

        with _fd_tab1:
            section(f"Fundamental Snapshot — {_fd_sym}")
            if not _fd_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Fetching fundamentals for {_fd_sym}..."):
                    try:
                        _fd = fetch_stock_fundamentals(_fd_sym)
                    except Exception as _fe:
                        _fd = {}; st.error(f"Fetch failed: {_fe}")

                if not _fd:
                    st.warning(f"No fundamental data returned for {_fd_sym}. Check the symbol.")
                else:
                    # Identity row
                    st.markdown(
                        f'<div class="metric-card" style="padding:12px 16px;margin-bottom:12px">'
                        f'<div style="font-size:1.05rem;font-weight:700;color:var(--acc)">{_fd.get("name","")}</div>'
                        f'<div style="font-size:0.78rem;color:var(--muted)">{_fd.get("sector","")} › {_fd.get("industry","")}</div>'
                        f'</div>', unsafe_allow_html=True
                    )

                    # Price + market cap
                    r1 = st.columns(4)
                    r1[0].metric("Price", f"₹{_fd.get('price',0):,.2f}")
                    r1[1].metric("Market Cap", f"₹{_fd.get('market_cap',0):,.0f}Cr" if _fd.get('market_cap') else "N/A")
                    r1[2].metric("52W vs High", f"{_fd.get('week52_vs_high',0):+.1f}%" if _fd.get('week52_vs_high') is not None else "N/A")
                    r1[3].metric("Beta", f"{_fd.get('beta',0):.2f}" if _fd.get('beta') else "N/A")

                    st.markdown("---")
                    # Valuation
                    section("Valuation Multiples")
                    r2 = st.columns(5)
                    r2[0].metric("P/E (TTM)",     f"{_fd.get('pe_ratio',0):.1f}x"    if _fd.get('pe_ratio')    else "N/A")
                    r2[1].metric("Fwd P/E",        f"{_fd.get('forward_pe',0):.1f}x"  if _fd.get('forward_pe')  else "N/A")
                    r2[2].metric("P/B",             f"{_fd.get('pb_ratio',0):.2f}x"   if _fd.get('pb_ratio')    else "N/A")
                    r2[3].metric("EV/EBITDA",       f"{_fd.get('ev_ebitda',0):.1f}x"  if _fd.get('ev_ebitda')   else "N/A")
                    r2[4].metric("P/S",             f"{_fd.get('ps_ratio',0):.2f}x"   if _fd.get('ps_ratio')    else "N/A")

                    # Profitability
                    section("Profitability & Returns")
                    r3 = st.columns(5)
                    r3[0].metric("Net Margin",     f"{_fd.get('profit_margin',0):.1f}%"    if _fd.get('profit_margin')    else "N/A")
                    r3[1].metric("Op Margin",      f"{_fd.get('operating_margin',0):.1f}%" if _fd.get('operating_margin') else "N/A")
                    r3[2].metric("ROE",             f"{_fd.get('roe',0):.1f}%"             if _fd.get('roe')              else "N/A")
                    r3[3].metric("ROA",             f"{_fd.get('roa',0):.1f}%"             if _fd.get('roa')              else "N/A")
                    r3[4].metric("Div Yield",       f"{_fd.get('dividend_yield',0):.2f}%"  if _fd.get('dividend_yield')   else "N/A")

                    # Financials
                    section("Financials (TTM)")
                    r4 = st.columns(4)
                    r4[0].metric("Revenue",    f"₹{_fd.get('revenue_ttm',0):,.0f}Cr"    if _fd.get('revenue_ttm')    else "N/A")
                    r4[1].metric("Net Income", f"₹{_fd.get('net_income_ttm',0):,.0f}Cr" if _fd.get('net_income_ttm') else "N/A")
                    r4[2].metric("EPS (TTM)",  f"₹{_fd.get('eps_ttm',0):.2f}"           if _fd.get('eps_ttm')        else "N/A")
                    r4[3].metric("Fwd EPS",    f"₹{_fd.get('eps_forward',0):.2f}"       if _fd.get('eps_forward')    else "N/A")

                    # Balance sheet
                    section("Balance Sheet Health")
                    r5 = st.columns(3)
                    r5[0].metric("Debt/Equity",    f"{_fd.get('debt_equity',0):.2f}x"  if _fd.get('debt_equity')    else "N/A")
                    r5[1].metric("Current Ratio",  f"{_fd.get('current_ratio',0):.2f}" if _fd.get('current_ratio')  else "N/A")
                    r5[2].metric("Float Shares",   f"{_fd.get('float_shares',0):,.1f}Cr" if _fd.get('float_shares') else "N/A")

                    # AI analysis
                    if _GEMINI_OK:
                        st.markdown("---")
                        if st.button("🤖 Generate AI Analysis", key="fd_ai_btn", type="primary"):
                            with st.spinner("Generating Gemini analysis..."):
                                try:
                                    from gemini_reporter import generate_stock_analysis
                                    _ai_text = generate_stock_analysis(_fd_sym, _fd)
                                    _render_ai_report(_ai_text)
                                except Exception as _ae:
                                    st.error(f"AI analysis failed: {_ae}")

        with _fd_tab2:
            section(f"Valuation Scorecard — {_fd_sym}")
            if not _fd_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Building scorecard for {_fd_sym}..."):
                    try:
                        _fd_raw = fetch_stock_fundamentals(_fd_sym)
                        _sc = get_valuation_scorecard(_fd_raw) if _fd_raw else {}
                    except Exception as _se:
                        _sc = {}; st.error(f"Scorecard failed: {_se}")

                if not _sc:
                    st.warning("Scorecard unavailable — no fundamental data returned.")
                else:
                    _score   = _sc.get("score", 0)
                    _rating  = _sc.get("rating", "N/A")
                    _bdown   = _sc.get("breakdown", {})
                    _r_color = "var(--bull)" if "BUY" in str(_rating).upper() else "var(--bear)" if "SELL" in str(_rating).upper() else "var(--warn)"

                    st.markdown(
                        f'<div class="metric-card" style="padding:16px;text-align:center;margin-bottom:16px">'
                        f'<div style="font-size:2.5rem;font-weight:800;color:{_r_color}">{_rating}</div>'
                        f'<div style="font-size:1rem;color:var(--ink)">Score: {_score} / {sum(_bdown.values()) if _bdown else "?"}</div>'
                        f'</div>', unsafe_allow_html=True
                    )

                    if _bdown:
                        section("Score Breakdown")
                        for _metric, _pts in _bdown.items():
                            _icon = "✅" if _pts > 0 else "❌"
                            _lbl  = _metric.replace("_"," ").title()
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid var(--rule);display:flex;align-items:baseline;gap:8px">'
                                f'<span style="font-size:0.95rem">{_icon}</span>'
                                f'<span style="font-size:0.82rem;color:var(--ink);flex:1">{_lbl}</span>'
                                f'<span style="font-size:0.78rem;color:var(--warn);margin-left:8px">{_pts:+d} pts</span>'
                                f'</div>', unsafe_allow_html=True
                            )

        with _fd_tab3:
            section("Fundamental Screener")
            st.caption("Filter NSE stocks by valuation, profitability, and growth criteria")
            _sc_c1, _sc_c2, _sc_c3 = st.columns(3)
            with _sc_c1:
                _max_pe    = st.number_input("Max P/E",      min_value=0.0, max_value=200.0, value=30.0, step=1.0, key="sc_pe")
                _min_roe   = st.number_input("Min ROE (%)",  min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="sc_roe")
            with _sc_c2:
                _max_de    = st.number_input("Max Debt/Eq",  min_value=0.0, max_value=10.0,  value=1.0,  step=0.1, key="sc_de")
                _min_margin= st.number_input("Min Net Margin (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="sc_margin")
            with _sc_c3:
                _screen_universe = st.selectbox(
                    "Universe", ["Nifty 50", "Custom"], key="sc_uni"
                )
                _custom_syms = st.text_area("Custom symbols (one per line, with .NS)",
                    height=68, key="sc_custom",
                    placeholder="RELIANCE.NS\nINFY.NS\nHDFCBANK.NS")

            if st.button("🔍 Run Screen", key="sc_run", type="primary"):
                # Build symbol list
                if _screen_universe == "Custom" and _custom_syms.strip():
                    _syms_to_screen = [s.strip().upper() for s in _custom_syms.strip().splitlines() if s.strip()]
                else:
                    # Use a small fixed Nifty 50 subset for speed
                    _syms_to_screen = [
                        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
                        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
                        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
                        "BAJFINANCE.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS",
                        "NTPC.NS","ONGC.NS","JSWSTEEL.NS","TATAMOTORS.NS","ADANIPORTS.NS",
                        "CIPLA.NS","DRREDDY.NS","SUNPHARMA.NS","DIVISLAB.NS","TECHM.NS",
                    ]
                # screen_fundamentals expects criteria as {metric: (min_val, max_val)}
                criteria = {
                    "pe_ratio":        (0, _max_pe),
                    "roe":             (_min_roe, 9999),
                    "debt_equity":     (0, _max_de),
                    "profit_margin":   (_min_margin, 9999),
                }
                with st.spinner(f"Screening {len(_syms_to_screen)} stocks (may take 30–60s)..."):
                    try:
                        _df_sc = screen_fundamentals(_syms_to_screen, criteria)
                    except Exception as _scre:
                        _df_sc = pd.DataFrame(); st.error(f"Screen failed: {_scre}")

                if not _df_sc.empty:
                    st.success(f"✅ {len(_df_sc)} stocks passed all criteria")
                    _show_cols = [c for c in ["symbol","name","pe_ratio","roe","profit_margin",
                                               "debt_equity","market_cap"] if c in _df_sc.columns]
                    _df_show = _df_sc[_show_cols].rename(columns={
                        "pe_ratio":"P/E","roe":"ROE%","profit_margin":"Net Margin%",
                        "debt_equity":"D/E","market_cap":"Mkt Cap (Cr)"
                    })
                    st.dataframe(_df_show, use_container_width=True, hide_index=True)
                else:
                    st.info("No stocks passed all criteria. Try relaxing the filters.")
