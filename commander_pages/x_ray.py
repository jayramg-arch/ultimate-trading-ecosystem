# commander_pages/x_ray.py - the X-RAY page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('x_ray', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🧬 Stock X-Ray</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Deep-dive fundamental analysis — valuation · financials · quarterly results · sector comparison · multi-stock screen <span style="color:var(--ink);font-size:0.7rem;">(absorbed Fundamentals 10 May 2026)</span></div>', unsafe_allow_html=True)

    def sync_tv_symbol_xray():
        import subprocess
        import csv
        import re
        from io import StringIO
        
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'], capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ["NIFTY 50", "NIFTY"]: sym = "^NSEI"
                                elif sym.upper() in ["NIFTY BANK", "BANKNIFTY"]: sym = "^NSEBANK"
                                elif sym.upper() == "NIFTY 500": sym = "^CRSLDX"
                                else:
                                    if not sym.endswith(".NS") and "^" not in sym and "=" not in sym: sym += ".NS"
                                st.session_state["xr_sym_input"] = sym
                                st.session_state["xr_symbol"] = sym
                                return
            except Exception:
                pass

    if not _FUND_OK:
        st.error("❌ fundamental_hub module not available.")
    else:
        _xr_col1, _ = st.columns([2, 4])
        with _xr_col1:
            st.button("🔄 Sync with TV", on_click=sync_tv_symbol_xray, help="Auto-read symbol from open TradingView", use_container_width=True, key="xr_sync_btn")
            
            if "xr_sym_input" not in st.session_state:
                st.session_state["xr_sym_input"] = st.session_state.get("xr_symbol", "RELIANCE.NS")
                
            _xr_sym = st.text_input(
                "NSE Symbol", 
                key="xr_sym_input", placeholder="e.g. INFY.NS, TCS.NS"
            ).strip().upper()
            if _xr_sym and not _xr_sym.endswith(".NS"):
                _xr_sym += ".NS"
            if _xr_sym:
                st.session_state["xr_symbol"] = _xr_sym

        # P2 follow-up D (10 May 2026): added "📰 News" tab so per-stock news is
        # available where the trader is doing the deep-dive — instead of having
        # to switch to the standalone NEWS page and manually filter.
        _xr_t1, _xr_t2, _xr_t3, _xr_t4, _xr_t5, _xr_t6 = st.tabs([
            "📊 Snapshot", "📋 Income Statement", "📆 Quarterly Results",
            "🎯 Scorecard", "🔍 Screen", "📰 News"
        ])

        # ── TAB 1 — SNAPSHOT ────────────────────────────────────────────────
        with _xr_t1:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Loading X-Ray for {_xr_sym}..."):
                    try:
                        _xr_fd = fetch_stock_fundamentals(_xr_sym)
                    except Exception as _xre:
                        _xr_fd = {}; st.error(f"Fetch failed: {_xre}")

                if _xr_fd:
                    st.markdown(
                        f'<div class="metric-card" style="padding:12px 16px;margin-bottom:14px">'
                        f'<div style="font-size:1.1rem;font-weight:700;color:var(--acc)">{_xr_fd.get("name","")}</div>'
                        f'<div style="font-size:0.78rem;color:var(--muted)">{_xr_fd.get("sector","")} › {_xr_fd.get("industry","")}</div>'
                        f'</div>', unsafe_allow_html=True
                    )
                    # Price
                    _xr_r1 = st.columns(4)
                    _xr_r1[0].metric("Price",       f"₹{_xr_fd.get('price',0):,.2f}")
                    _xr_r1[1].metric("Market Cap",  f"₹{_xr_fd.get('market_cap',0):,.0f}Cr" if _xr_fd.get('market_cap') else "N/A")
                    _xr_r1[2].metric("52W vs High", f"{_xr_fd.get('week52_vs_high',0):+.1f}%" if _xr_fd.get('week52_vs_high') is not None else "N/A")
                    _xr_r1[3].metric("Beta",        f"{_xr_fd.get('beta',0):.2f}" if _xr_fd.get('beta') else "N/A")
                    st.markdown("---")
                    # Valuation
                    section("Valuation")
                    _xr_r2 = st.columns(5)
                    _xr_r2[0].metric("P/E",      f"{_xr_fd.get('pe_ratio',0):.1f}x"   if _xr_fd.get('pe_ratio')   else "N/A")
                    _xr_r2[1].metric("Fwd P/E",  f"{_xr_fd.get('forward_pe',0):.1f}x" if _xr_fd.get('forward_pe') else "N/A")
                    _xr_r2[2].metric("P/B",      f"{_xr_fd.get('pb_ratio',0):.2f}x"   if _xr_fd.get('pb_ratio')   else "N/A")
                    _xr_r2[3].metric("EV/EBITDA",f"{_xr_fd.get('ev_ebitda',0):.1f}x"  if _xr_fd.get('ev_ebitda')  else "N/A")
                    _xr_r2[4].metric("P/S",      f"{_xr_fd.get('ps_ratio',0):.2f}x"   if _xr_fd.get('ps_ratio')   else "N/A")
                    # Profitability
                    section("Profitability")
                    _xr_r3 = st.columns(5)
                    _xr_r3[0].metric("Net Margin",  f"{_xr_fd.get('profit_margin',0):.1f}%"    if _xr_fd.get('profit_margin')    else "N/A")
                    _xr_r3[1].metric("Op Margin",   f"{_xr_fd.get('operating_margin',0):.1f}%" if _xr_fd.get('operating_margin') else "N/A")
                    _xr_r3[2].metric("ROE",         f"{_xr_fd.get('roe',0):.1f}%"             if _xr_fd.get('roe')              else "N/A")
                    _xr_r3[3].metric("ROA",         f"{_xr_fd.get('roa',0):.1f}%"             if _xr_fd.get('roa')              else "N/A")
                    _xr_r3[4].metric("Div Yield",   f"{_xr_fd.get('dividend_yield',0):.2f}%"  if _xr_fd.get('dividend_yield')   else "N/A")
                    # Balance sheet
                    section("Balance Sheet")
                    _xr_r4 = st.columns(4)
                    _xr_r4[0].metric("Revenue (TTM)",  f"₹{_xr_fd.get('revenue_ttm',0):,.0f}Cr"    if _xr_fd.get('revenue_ttm')    else "N/A")
                    _xr_r4[1].metric("Net Income",     f"₹{_xr_fd.get('net_income_ttm',0):,.0f}Cr" if _xr_fd.get('net_income_ttm') else "N/A")
                    _xr_r4[2].metric("Debt/Equity",    f"{_xr_fd.get('debt_equity',0):.2f}x"        if _xr_fd.get('debt_equity')    else "N/A")
                    _xr_r4[3].metric("Current Ratio",  f"{_xr_fd.get('current_ratio',0):.2f}"       if _xr_fd.get('current_ratio')  else "N/A")

        # ── TAB 2 — INCOME STATEMENT ────────────────────────────────────────
        with _xr_t2:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Loading financial statements..."):
                    try:
                        _xr_fs = fetch_financial_statements(_xr_sym)
                    except Exception as _xrfe:
                        _xr_fs = {}; st.error(f"Failed: {_xrfe}")

                if _xr_fs:
                    for _stmt_name, _stmt_df in _xr_fs.items():
                        section(_stmt_name)
                        if isinstance(_stmt_df, pd.DataFrame) and not _stmt_df.empty:
                            st.dataframe(_stmt_df, use_container_width=True)
                        else:
                            st.caption("No data available.")
                else:
                    st.info("Financial statement data unavailable for this symbol.")

        # ── TAB 3 — QUARTERLY RESULTS ────────────────────────────────────────
        with _xr_t3:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Loading quarterly results..."):
                    try:
                        _xr_qr = fetch_quarterly_results(_xr_sym)
                    except Exception as _xrqe:
                        _xr_qr = pd.DataFrame(); st.error(f"Failed: {_xrqe}")

                if isinstance(_xr_qr, pd.DataFrame) and not _xr_qr.empty:
                    section("Quarterly Results")
                    st.dataframe(_xr_qr, use_container_width=True, hide_index=True)

                    # Revenue trend chart
                    _rev_cols = [c for c in _xr_qr.columns if 'revenue' in c.lower() or 'sales' in c.lower() or 'total revenue' in c.lower()]
                    _prof_cols = [c for c in _xr_qr.columns if 'net income' in c.lower() or 'profit' in c.lower()]
                    if _rev_cols or _prof_cols:
                        section("Revenue & Profit Trend")
                        # FIX (10 May 2026 — chart "shaking continuously" reported, then
                        # "whole screen shaking" after first attempt):
                        #
                        # Root cause: _xr_qr.index.astype(str) on a DatetimeIndex emitted
                        # "2025-12-31 00:00:00" which Plotly auto-parsed as dates each
                        # render → animated re-fit on every Streamlit rerun.
                        #
                        # First attempt added `responsive: False` which conflicted with
                        # `use_container_width=True` and caused horizontal layout thrash
                        # (the "whole screen shaking, more towards the right"). Removed.
                        #
                        # Final fix:
                        #   1. Stable Q-string x-labels (Q4-25, Q3-25, …) — no date re-parse
                        #   2. xaxis type="category" with pinned categoryarray — order fixed
                        #   3. transition.duration=0 — no animated re-fits
                        #   4. Stable Streamlit `key` (sanitised: dots stripped from sym)
                        #   5. NO `responsive: False` config (let Streamlit/Plotly negotiate)
                        #   6. Wrap in fixed-height st.container — prevents the chart from
                        #      pushing the page layout when its bbox is computed
                        def _fmt_quarter(idx_val):
                            try:
                                ts = pd.to_datetime(idx_val)
                                return f"Q{((ts.month - 1) // 3) + 1}-{ts.strftime('%y')}"
                            except Exception:
                                return str(idx_val)
                        _x_labels = [_fmt_quarter(i) for i in _xr_qr.index]
                        _fig_qr = go.Figure()
                        for _rc in _rev_cols[:1]:
                            _fig_qr.add_trace(go.Bar(name="Revenue", x=_x_labels,
                                                      y=_xr_qr[_rc], marker_color="#56C2CC"))
                        for _pc in _prof_cols[:1]:
                            _fig_qr.add_trace(go.Bar(name="Net Profit", x=_x_labels,
                                                      y=_xr_qr[_pc], marker_color="#45BE92"))
                        _fig_qr.update_layout(
                            barmode="group", height=300, margin=dict(t=10,l=0,r=0,b=40),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(type="category", gridcolor="#E2E8F0", tickangle=-30,
                                       categoryorder="array", categoryarray=_x_labels),
                            yaxis=dict(gridcolor="#E2E8F0"),
                            legend=dict(font=dict(color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#E3EBEC"),
                            transition=dict(duration=0),
                        )
                        _xr_sym_key = "".join(c if c.isalnum() else "_" for c in (_xr_sym or "x"))
                        with st.container(height=350):
                            st.plotly_chart(
                                _fig_qr, use_container_width=True,
                                key=f"xr_qr_chart_{_xr_sym_key}",
                            )
                else:
                    st.info("Quarterly results unavailable for this symbol.")

        # ── TAB 4 — SCORECARD ────────────────────────────────────────────────
        with _xr_t4:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Building Weinstein X-Ray Scorecard (Bypassing TV limitations)..."):
                    try:
                        from weinstein_xray_screener import get_xray_scorecard
                        _xr_sc = get_xray_scorecard(_xr_sym)
                    except Exception as _xrsce:
                        _xr_sc = {}; st.error(f"Scorecard failed: {_xrsce}")
                
                if _xr_sc and "error" not in _xr_sc:
                    st.markdown(
                        f'<div class="metric-card" style="padding:20px;text-align:center;margin-bottom:16px">'
                        f'<div style="font-size:2.4rem;font-weight:800;color:var(--acc)">{_xr_sc.get("Overall_Grade", "N/A")}</div>'
                        f'<div style="font-size:1rem;color:var(--ink);margin-top:4px">Overall Rating: {_xr_sc.get("Overall_Rating", 0)} / 17</div>'
                        f'</div>', unsafe_allow_html=True
                    )
                    
                    _col1, _col2 = st.columns(2)
                    with _col1:
                        section(f"Minervini Score: {_xr_sc.get('Minervini_Score', 0)}/8")
                        for _k, _v in _xr_sc.get("Minervini_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid var(--rule);display:flex;gap:8px;align-items:center">'
                                f'<span>{"✅" if _v == 1 else "❌"}</span>'
                                f'<span style="flex:1;font-size:0.85rem;color:var(--ink)">{_k}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        section("Overall Breakdown")
                        for _k, _v in _xr_sc.get("Overall_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid var(--rule);display:flex;gap:8px;align-items:center">'
                                f'<span style="flex:1;font-size:0.85rem;color:var(--ink)">{_k}</span>'
                                f'<span style="color:var(--warn);font-weight:bold;">{_v}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                            
                    with _col2:
                        section(f"Piotroski F-Score: {_xr_sc.get('Piotroski_Score', 0)}/9")
                        for _k, _v in _xr_sc.get("Piotroski_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid var(--rule);display:flex;gap:8px;align-items:center">'
                                f'<span>{"✅" if _v == 1 else "❌"}</span>'
                                f'<span style="flex:1;font-size:0.85rem;color:var(--ink)">{_k}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                elif "error" in _xr_sc:
                    st.warning("Insufficient financial data from yfinance to calculate X-Ray.")

        # ── TAB 5 — SCREEN (absorbed from former Fundamentals page) ─────────
        with _xr_t5:
            section("Multi-Stock Fundamental Screener")
            st.caption("Filter NSE stocks by valuation, profitability, and growth criteria. "
                       "Same engine that powered the (now-merged) Fundamentals page.")
            _xsc_c1, _xsc_c2, _xsc_c3 = st.columns(3)
            with _xsc_c1:
                _xsc_max_pe   = st.number_input("Max P/E",      min_value=0.0, max_value=200.0, value=30.0, step=1.0, key="xsc_pe")
                _xsc_min_roe  = st.number_input("Min ROE (%)",  min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="xsc_roe")
            with _xsc_c2:
                _xsc_max_de   = st.number_input("Max Debt/Eq",  min_value=0.0, max_value=10.0,  value=1.0,  step=0.1, key="xsc_de")
                _xsc_min_marg = st.number_input("Min Net Margin (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="xsc_margin")
            with _xsc_c3:
                _xsc_universe = st.selectbox(
                    "Universe", ["Nifty 50", "Nifty 500", "Custom"], key="xsc_uni",
                    help="Nifty 500 = backtest-aligned full universe (validation.default_universe)"
                )
                _xsc_custom = st.text_area("Custom symbols (one per line, with .NS)",
                    height=68, key="xsc_custom",
                    placeholder="RELIANCE.NS\nINFY.NS\nHDFCBANK.NS")

            if st.button("🔍 Run Screen", key="xsc_run", type="primary"):
                if _xsc_universe == "Custom" and _xsc_custom.strip():
                    _xsc_syms = [s.strip().upper() for s in _xsc_custom.strip().splitlines() if s.strip()]
                elif _xsc_universe == "Nifty 500":
                    try:
                        import validation as _val_xsc
                        _xsc_syms = [
                            s if s.endswith(".NS") else (s + ".NS")
                            for s in _val_xsc.default_universe("nifty500")
                        ]
                    except Exception as _xsc500e:
                        st.error(f"Could not load Nifty 500: {_xsc500e}")
                        _xsc_syms = []
                else:
                    _xsc_syms = [
                        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
                        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
                        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
                        "BAJFINANCE.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS",
                        "NTPC.NS","ONGC.NS","JSWSTEEL.NS","TATAMOTORS.NS","ADANIPORTS.NS",
                        "CIPLA.NS","DRREDDY.NS","SUNPHARMA.NS","DIVISLAB.NS","TECHM.NS",
                    ]
                _xsc_criteria = {
                    "pe_ratio":      (0, _xsc_max_pe),
                    "roe":           (_xsc_min_roe, 9999),
                    "debt_equity":   (0, _xsc_max_de),
                    "profit_margin": (_xsc_min_marg, 9999),
                }
                with st.spinner(f"Screening {len(_xsc_syms)} stocks (may take 30–60s)..."):
                    try:
                        _xsc_df = screen_fundamentals(_xsc_syms, _xsc_criteria)
                    except Exception as _xsce:
                        _xsc_df = pd.DataFrame(); st.error(f"Screen failed: {_xsce}")

                if not _xsc_df.empty:
                    st.success(f"✅ {len(_xsc_df)} stocks passed all criteria")
                    _xsc_show_cols = [c for c in ["symbol","name","pe_ratio","roe","profit_margin",
                                                   "debt_equity","market_cap"] if c in _xsc_df.columns]
                    _xsc_show = _xsc_df[_xsc_show_cols].rename(columns={
                        "pe_ratio":"P/E","roe":"ROE%","profit_margin":"Net Margin%",
                        "debt_equity":"D/E","market_cap":"Mkt Cap (Cr)"
                    })
                    st.dataframe(_xsc_show, use_container_width=True, hide_index=True)
                else:
                    st.info("No stocks passed all criteria. Try relaxing the filters.")

        # ── TAB 6 — NEWS (per-stock filtered, NEW 10 May 2026) ──────────────
        # Per user feedback (D): a news headline about Reliance is most useful
        # when you're looking at Reliance, not at the start of the day. This
        # tab pulls from the same news_fetcher the standalone NEWS page uses,
        # then filters by ticker / company-name keywords for the symbol the
        # user is currently X-Raying.
        with _xr_t6:
            section(f"News — {_xr_sym or '(no symbol)'}")
            st.caption(
                "Articles + NSE announcements mentioning this ticker or its company name "
                "(headline + summary keyword match). Cached 30 min. "
                "Full market-wide feed is on **📰 NEWS**."
            )
            if not _xr_sym:
                st.info("Enter an NSE symbol above to filter news.")
            else:
                try:
                    from news_fetcher import get_news as _xr_get_news
                    _xr_news = _xr_get_news(hours_back=72)
                except Exception as _xrne:
                    _xr_news = {"articles": [], "announcements": []}
                    st.error(f"News fetch failed: {_xrne}")

                # Build search keywords: bare ticker + variations
                _xr_clean = (_xr_sym or "").upper().replace(".NS", "").replace(".BO", "")
                _xr_keywords = {_xr_clean}
                # Try common company-name variants for top tickers
                _xr_company_map = {
                    "RELIANCE": ["reliance industries", "ril"],
                    "TCS":      ["tata consultancy"],
                    "INFY":     ["infosys"],
                    "HDFCBANK": ["hdfc bank"],
                    "ICICIBANK":["icici bank"],
                    "SBIN":     ["state bank", "sbi"],
                    "BHARTIARTL":["bharti airtel", "airtel"],
                    "KOTAKBANK":["kotak mahindra", "kotak bank"],
                    "LT":       ["larsen", "l&t"],
                    "HCLTECH":  ["hcl technologies", "hcl tech"],
                    "WIPRO":    ["wipro"],
                    "AXISBANK": ["axis bank"],
                    "MARUTI":   ["maruti suzuki"],
                    "ASIANPAINT":["asian paints"],
                    "NESTLEIND":["nestle india"],
                    "HINDUNILVR":["hindustan unilever", "hul"],
                    "ITC":      ["itc"],
                    "ONGC":     ["oil and natural gas"],
                    "NTPC":     ["ntpc"],
                    "POWERGRID":["power grid"],
                }
                for kw in _xr_company_map.get(_xr_clean, []):
                    _xr_keywords.add(kw.upper())

                def _xr_news_match(item):
                    blob = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).upper()
                    return any(kw in blob for kw in _xr_keywords)

                _xr_articles = [a for a in _xr_news.get("articles", []) if _xr_news_match(a)]
                _xr_anns     = [a for a in _xr_news.get("announcements", []) if _xr_news_match(a)]

                _xr_n1, _xr_n2 = st.columns(2)
                _xr_n1.metric(f"Matching articles", len(_xr_articles))
                _xr_n2.metric(f"NSE announcements", len(_xr_anns))
                st.caption(f"Match keywords: `{', '.join(sorted(_xr_keywords))}` · "
                           f"news cache fetched {_xr_news.get('fetched_at', '—')}")

                if _xr_articles:
                    section("📰 Articles")
                    for _a in _xr_articles[:25]:
                        _t = _a.get("title", "(no title)")
                        _s = _a.get("source", "")
                        _p = _a.get("published", "")
                        _u = _a.get("link", "")
                        _sm = _a.get("summary", "")[:300]
                        st.markdown(
                            f"**[{_t}]({_u})**  ·  *{_s}*  ·  {_p}\n\n"
                            f"<div style='font-size:0.82rem;color:#9ba8b6;'>{_sm}…</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("---")

                if _xr_anns:
                    section("📢 NSE Corporate Announcements")
                    for _ann in _xr_anns[:15]:
                        _t = _ann.get("title", "(no title)")
                        _p = _ann.get("published", "")
                        _u = _ann.get("link", "")
                        _sm = _ann.get("summary", "")[:300]
                        st.markdown(
                            f"**[{_t}]({_u})**  ·  {_p}\n\n"
                            f"<div style='font-size:0.82rem;color:#9ba8b6;'>{_sm}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("---")

                if not _xr_articles and not _xr_anns:
                    st.info(f"No free RSS news in the last 72h mentioning **{_xr_clean}**. "
                            f"See the paid ET + MC section below.")

                # ── Paid sources: ET + Moneycontrol via analyst_sentiment ────
                # Stage 3b (10 May 2026): augments the free RSS feed with paid
                # ET + MC analyst recos and stock news. Cookies sourced from
                # data/paid_news_cookies/ (see setup_paid_news_cookies.py).
                st.markdown("---")
                section(f"📊 Analyst Sentiment + Paid News — {_xr_clean}")
                try:
                    import analyst_sentiment as _xr_ans
                    _xr_sent = _xr_ans.get_for_symbol(_xr_clean)

                    # Consensus badge + counts
                    _xr_cons = _xr_sent["consensus"]
                    _cons_color = {
                        "STRONG_BUY":  "#39ff14",  # bright neon green — louder than BUY
                        "BUY":         "var(--bull)",
                        "HOLD":        "var(--warn)",
                        "SELL":        "var(--bear)",
                        "STRONG_SELL": "#ff1744",  # bright red — louder than SELL
                        "MIXED":       "#a78bfa",
                        "NONE":        "var(--ink-2)",
                    }.get(_xr_cons, "var(--ink-2)")
                    # Display label: pretty-print the underscored ones
                    _cons_label_display = _xr_cons.replace("_", " ")

                    _xs1, _xs2, _xs3, _xs4, _xs5, _xs6 = st.columns(6)
                    _xs1.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-label">Consensus</div>'
                        f'<div class="metric-value" style="color:{_cons_color}">{_cons_label_display}</div>'
                        f'</div>', unsafe_allow_html=True)
                    _xs2.metric("⭐ STRONG BUY", _xr_sent.get("strong_buy", 0))
                    _xs3.metric("BUY",          _xr_sent["buy"])
                    _xs4.metric("HOLD",         _xr_sent["hold"])
                    _xs5.metric("SELL",         _xr_sent["sell"])
                    _xs6.metric("⚠ STRONG SELL", _xr_sent.get("strong_sell", 0))

                    _src_ok = _xr_sent.get("sources_ok", {})
                    st.caption(
                        f"ET session: {'✓' if _src_ok.get('et') else '✗'}  ·  "
                        f"MC session: {'✓' if _src_ok.get('mc') else '✗'}  ·  "
                        f"Fetched: {_xr_sent.get('fetched_at', '—')}  ·  "
                        f"6h cache (re-runs are instant)"
                    )

                    _xr_items = _xr_sent.get("items", [])
                    if _xr_items:
                        # Show actionable items first — STRONG_BUY at top, then BUY, etc.
                        _action_order = {
                            "STRONG_BUY":  0,
                            "BUY":         1,
                            "STRONG_SELL": 2,
                            "SELL":        3,
                            "HOLD":        4,
                            "OTHER":       5,
                        }
                        _xr_items_sorted = sorted(
                            _xr_items,
                            key=lambda x: _action_order.get(x.get("action", "OTHER"), 6)
                        )
                        for _it in _xr_items_sorted[:30]:
                            _act = _it.get("action") or "?"
                            _act_col = {
                                "STRONG_BUY":  "#39ff14",
                                "BUY":         "var(--bull)",
                                "HOLD":        "var(--warn)",
                                "SELL":        "var(--bear)",
                                "STRONG_SELL": "#ff1744",
                            }.get(_act, "var(--ink-2)")
                            # Pretty-print underscored buckets for the badge label
                            _act_label = _act.replace("_", " ")
                            _brk = _it.get("brokerage") or ""
                            _brk_str = f" · **{_brk}**" if _brk else ""
                            _origin = _it.get("_origin", "?").upper()
                            _origin_label = {"ET": "Economic Times", "MC": "Moneycontrol"}.get(_origin, _origin)
                            st.markdown(
                                f'<div style="margin:6px 0;padding:8px;background:var(--surface);border-left:3px solid {_act_col};border-radius:4px;">'
                                f'<span style="color:{_act_col};font-weight:600;font-family:JetBrains Mono,monospace;font-size:0.7rem;">{_act_label}</span>'
                                f'  ·  <span style="color:var(--ink);font-size:0.72rem;">{_origin_label}</span>'
                                f'  ·  <span style="color:#8b9eb0;font-size:0.72rem;">{_brk}</span>'
                                f'<div style="margin-top:4px;">'
                                f'<a href="{_it.get("url","#")}" target="_blank" style="color:var(--ink);font-size:0.86rem;text-decoration:none;">{_it.get("title","")}</a>'
                                f'</div></div>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.info(
                            f"No paid ET / MC headlines mentioning **{_xr_clean}** "
                            f"in current cache. Either no analyst coverage today or "
                            f"the symbol's name isn't matching headlines exactly. "
                            f"Try the bare ticker (e.g. RELIANCE not RIL)."
                        )
                except FileNotFoundError as _xr_se:
                    st.warning(
                        f"Paid news cookies not configured. Run "
                        f"`python setup_paid_news_cookies.py` to enable ET + MC scraping. "
                        f"Details: {_xr_se}"
                    )
                except Exception as _xr_se:
                    st.error(f"Sentiment fetch failed: {_xr_se}")
