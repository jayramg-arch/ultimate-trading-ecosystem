# commander_pages/macro.py - the MACRO page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('macro', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🌐 Macro Radar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Global Risk Environment // VIX // Currencies // Commodities</div>', unsafe_allow_html=True)
    _mc1, _mc2, _mc3, _mc4 = st.tabs(["🌍 Overview", "📊 Global Indices", "💰 FII/DII Flows", "🔄 Sector RRG"])

    with _mc1:
        with st.spinner("Loading macro data (cached 5min)..."):
            macro = fetch_macro_data_cached()

        if not macro:
            st.error("Could not fetch macro data. Check your internet connection.")
        else:
            # ── Row 1: Key metrics ──
            section("Global Macro Snapshot")
            cols = st.columns(len(macro), gap="small")
            color_map = {
                'India VIX': lambda v: "var(--bear)" if v > 20 else "var(--warn)" if v > 15 else "var(--bull)",
                'Nifty 50':  lambda v: "var(--bull)",
            }
            for col, (name, dat) in zip(cols, macro.items()):
                ltp_v = dat['LTP']
                chg   = dat['1M%']
                color = "var(--bull)" if chg >= 0 else "var(--bear)"
                if name == 'India VIX':
                    color = "var(--bear)" if ltp_v > 20 else "var(--warn)" if ltp_v > 15 else "var(--bull)"
                pctile_str = f"Pctile: {dat['Pctile']:.0f}%"
                col.metric(name, f"{ltp_v:,.2f}", delta=f"{chg:+.1f}% (1M)",
                           help=f"1Y Range Percentile: {pctile_str} | Stage: {dat['Stage']}")

            st.markdown("---")
            # ── Regime Indicators ──
            section("Regime Indicators")
            r1, r2, r3 = st.columns(3, gap="small")

            vix_data = macro.get('India VIX', {})
            vix_val  = vix_data.get('LTP', 0)
            if vix_val > 25:     vix_regime, vix_col = "🔴 STRESSED  (>25)", "var(--bear)"
            elif vix_val > 18:   vix_regime, vix_col = "🟡 ELEVATED (18–25)", "var(--warn)"
            else:                vix_regime, vix_col = "🟢 CALM     (<18)",   "var(--bull)"

            with r1:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">India VIX Regime</div>
                  <div class="metric-value" style="color:{vix_col};">{vix_regime}</div>
                  <div style="font-size:0.7rem;color:var(--ink);margin-top:4px;">1Y Pctile: {vix_data.get('Pctile',0):.0f}%</div>
                </div>""", unsafe_allow_html=True)

            inr_data = macro.get('USD/INR', {})
            inr_ltp  = inr_data.get('LTP', 0)
            inr_sma200 = inr_data.get('SMA200', inr_ltp)
            inr_signal = "🔴 Weak INR (above 200MA)" if inr_ltp > inr_sma200 else "🟢 Strong INR (below 200MA)"
            with r2:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">USD/INR Signal</div>
                  <div class="metric-value" style="font-size:0.9rem;">{inr_signal}</div>
                  <div style="font-size:0.7rem;color:var(--ink);margin-top:4px;">LTP: {inr_ltp:.2f} | 200MA: {inr_sma200:.2f}</div>
                </div>""", unsafe_allow_html=True)

            crude_data  = macro.get('Brent Crude', {})
            crude_chg1m = crude_data.get('1M%', 0)
            crude_sig   = "🔴 Rising Crude (inflationary)" if crude_chg1m > 5 else "🟢 Stable / Falling Crude"
            with r3:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">Crude Oil Signal</div>
                  <div class="metric-value" style="font-size:0.9rem;">{crude_sig}</div>
                  <div style="font-size:0.7rem;color:var(--ink);margin-top:4px;">1M Change: {crude_chg1m:+.1f}%</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            # ── Multi-line chart ──
            section("12-Month Trend — Normalised to 100")
            # P2.1 (#5) — added Nifty 500 alongside Nifty 50 so divergence between
            # large-cap and broad market is visible on the same chart.
            chart_names = ['Nifty 50','Nifty 500','India VIX','Gold','Brent Crude']
            fig_macro = go.Figure()
            for name in chart_names:
                if name in macro and macro[name].get('series') is not None:
                    series = macro[name]['series'].dropna()
                    norm   = (series / series.iloc[0]) * 100
                    fig_macro.add_trace(go.Scatter(
                        x=norm.index, y=norm.values, name=name, mode='lines',
                        line=dict(width=1.5)
                    ))
            fig_macro.update_layout(
                height=300, margin=dict(t=10,l=0,r=0,b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(size=10, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"),
                font=dict(color="#E3EBEC")
            )
            st.plotly_chart(fig_macro, use_container_width=True)

    with _mc2:
        section("Global Indices — Full Board")
        st.caption("Sorted by absolute |Chg%|: biggest movers float to top. ▲ green = up, ▼ red = down.")
        if _HUB_OK:
            with st.spinner("Fetching global indices..."):
                try: _glo2 = fetch_global_overview()
                except Exception as _e: _glo2 = {}; st.error(str(_e))

            if _glo2:
                _all_items = {**_glo2.get("indices",{}), **_glo2.get("commodities",{}),
                              **_glo2.get("currencies",{}), **_glo2.get("bonds",{})}
                _rows = []
                for _n, _d in _all_items.items():
                    if _d:
                        _chg_v = float(_d.get("change_pct", 0) or 0)
                        # P2.1 (#6) — direction marker as Unicode arrow with explicit text
                        _arrow = "▲" if _chg_v >= 0 else "▼"
                        _rows.append({
                            "Name": _n,
                            "LTP": _d.get("ltp", 0),
                            "Chg%": f"{_arrow} {_chg_v:+.2f}%",
                            "_chg_sort": abs(_chg_v),   # used for sort, dropped before display
                            "52W High": _d.get("week52_high", 0),
                            "52W Low":  _d.get("week52_low", 0),
                            "vs 52W H": f"{_d.get('pct_vs_52h', 0):.1f}%",
                        })
                if _rows:
                    _df_glo = pd.DataFrame(_rows)
                    _df_glo = _df_glo.sort_values("_chg_sort", ascending=False).drop(columns=["_chg_sort"])

                    # Style with red/green colour on the Chg% column based on sign
                    def _color_chg(val):
                        if isinstance(val, str) and val.startswith("▲"):
                            return "color: var(--bull); font-weight: 600;"
                        if isinstance(val, str) and val.startswith("▼"):
                            return "color: var(--bear); font-weight: 600;"
                        return ""
                    # 10 May 2026: round numeric columns to 2 decimals (user
                    # feedback: LTP, 52W High/Low were showing 6+ decimals).
                    _glo_num_cols = {c: "{:,.2f}" for c in
                                      ["LTP", "52W High", "52W Low"]
                                      if c in _df_glo.columns}
                    try:
                        _styled = _df_glo.style.format(_glo_num_cols)
                        _styled = (_styled.set_properties(**{'text-align': 'right', 'background-color': 'var(--surface)', 'color': 'var(--ink-2)', 'border-bottom': '1px solid var(--surface-3)', 'padding': '8px', 'font-weight': '600'})
                                   .set_properties(subset=['Name'], **{'text-align': 'left', 'font-weight': '700'}))
                        _styled = (_styled.map(_color_chg, subset=["Chg%"]) if hasattr(_styled, "map") else _styled.applymap(_color_chg, subset=["Chg%"]))
                        _styled = (_styled.set_table_styles([
                                       {'selector': 'th', 'props': [('text-align', 'right'), ('background-color', 'var(--surface-2)'), ('color', 'var(--surface)'), ('font-weight', '800'), ('letter-spacing', '0.8px'), ('font-size', '0.72rem'), ('text-transform', 'uppercase'), ('border-bottom', '2px solid var(--acc)'), ('padding', '9px 8px')]},
                                       {'selector': 'th.col_heading.level0.col0', 'props': [('text-align', 'left')]},
                                       {'selector': 'tbody tr:nth-child(even) td', 'props': [('background-color', 'var(--surface-2)')]},
                                       {'selector': 'table', 'props': [('width', '100%'), ('border-collapse', 'collapse')]}
                                   ])
                                   .hide(axis="index"))
                        st.markdown(f'<div style="max-height: 700px; overflow-y: auto;">{_styled.to_html(escape=False)}</div>', unsafe_allow_html=True)
                    except Exception:
                        # Pandas fallback
                        for c in ["LTP", "52W High", "52W Low"]:
                            if c in _df_glo.columns:
                                _df_glo[c] = pd.to_numeric(_df_glo[c], errors="coerce").round(2)
                        st.dataframe(_df_glo, use_container_width=True, height=min(40 + 35 * len(_df_glo), 700))
        else:
            st.warning("market_data_hub not available.")

    with _mc3:
        section("FII/DII Cumulative Flows")
        if _HUB_OK:
            with st.spinner("Fetching FII/DII flow history..."):
                try: _fii3 = fetch_fii_dii_data()
                except Exception as _e: _fii3 = pd.DataFrame(); st.error(str(_e))

            if not _fii3.empty and "fii_net" in _fii3.columns:
                _fii3["fii_cumulative"] = _fii3["fii_net"].cumsum()
                _fii3["dii_cumulative"] = _fii3["dii_net"].cumsum()

                _fig_cum = go.Figure()
                _x = _fii3["date"] if "date" in _fii3.columns else _fii3.index
                _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["fii_cumulative"],
                                              name="FII Cumulative (₹Cr)", line=dict(color="#15803D",width=2)))
                _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["dii_cumulative"],
                                              name="DII Cumulative (₹Cr)", line=dict(color="#1D4ED8",width=2)))
                _fig_cum.add_hline(y=0, line_dash="dot", line_color="#5C6B6E", line_width=1)
                _fig_cum.update_layout(
                    height=340, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(font=dict(size=10, color="#E3EBEC"),bgcolor="rgba(0,0,0,0)"),
                    xaxis=dict(gridcolor="#E2E8F0", type="date",
                               tickformat="%d %b", dtick="D1"),
                    yaxis=dict(gridcolor="#E2E8F0", title="₹ Crore"),
                    font=dict(color="#E3EBEC")
                )
                st.plotly_chart(_fig_cum, use_container_width=True)
                _df_to_show = _fii3[["date","fii_net","dii_net","fii_buy","fii_sell"]].tail(30) if "fii_buy" in _fii3.columns else _fii3.tail(30)
                _fii_num_cols = {c: "{:,.2f}" for c in _df_to_show.columns if c != "date"}
                try:
                    _styled_fii = (_df_to_show.style
                                   .format(_fii_num_cols)
                                   .set_properties(**{'text-align': 'right', 'background-color': 'var(--surface-2)', 'color': 'var(--ink-2)', 'border-bottom': '1px solid var(--surface-3)', 'padding': '8px'})
                                   .set_properties(subset=['date'], **{'text-align': 'left'})
                                   .set_table_styles([
                                       {'selector': 'th', 'props': [('text-align', 'right'), ('background-color', 'var(--surface-2)'), ('color', 'var(--surface)'), ('border-bottom', '2px solid var(--acc)'), ('padding', '8px')]},
                                       {'selector': 'th.col_heading.level0.col0', 'props': [('text-align', 'left')]},
                                       {'selector': 'table', 'props': [('width', '100%'), ('border-collapse', 'collapse')]}
                                   ])
                                   .hide(axis="index"))
                    st.markdown(f'<div style="max-height: 500px; overflow-y: auto;">{_styled_fii.to_html(escape=False)}</div>', unsafe_allow_html=True)
                except Exception:
                    st.dataframe(_df_to_show, use_container_width=True)
            else:
                st.info("FII/DII flow data unavailable.")
        else:
            st.warning("market_data_hub not available.")

    with _mc4:
        # NOTE (10 May 2026): Stock-level Recovery Signals block was previously
        # rendered here. Removed per user feedback (#7): RRG is sector-rotation
        # analytics; stock-level recovery signals belong in HUNTER → Recovery
        # Screener where you actually act on them. See HUNTER cockpit.

        section("Relative Rotation Graphs (RRG) — Rotation Quadrant")
        st.caption("Canonical JdK 4-Quadrant Sector & Stock Rotation Engine (Pine v67.4 Standard). Select universe, timeframe, and tail length below.")
        
        # ── Interactive Control Panel for RRG ─────────────────────────────
        c_rrg1, c_rrg2, c_rrg3, c_rrg4 = st.columns([3, 2, 2, 2])
        with c_rrg1:
            rrg_mode = st.selectbox(
                "Rotation Universe:",
                options=[
                    "🌍 All Sectors (rotation universe)",
                    "🛡️ Capital Goods & Defense Stocks",
                    "🧪 Specialty Chemicals & Commodities",
                    "🏆 Nifty 50 Heavyweights",
                    "🔍 Intra-Sector Breakdown",
                    "💼 Custom Watchlist"
                ],
                key="tab_rrg_mode"
            )
        with c_rrg2:
            rrg_tf = st.selectbox(
                "Timeframe:",
                options=["Weekly (Positional)", "Daily (Swing)"],
                index=0,
                key="tab_rrg_tf"
            )
        with c_rrg3:
            rrg_tail_len = st.slider("Tail Length (Bars):", min_value=1, max_value=15, value=6, key="tab_rrg_tail")
        with c_rrg4:
            rrg_tradeable_only = st.checkbox("BUY OK Only (✓)", value=False, key="tab_rrg_tr_only")

        # Secondary Selectors for Intra-Sector and Custom Watchlist
        rrg_sec_drill = None
        rrg_custom_raw = None
        if rrg_mode == "🔍 Intra-Sector Breakdown":
            # rotation_universe(), not SECTOR_INDICES: the sectoral table alone
            # left 44% of mapped stocks (298/684) pointing at an index the chart
            # never plotted, so Infrastructure - 151 stocks - could not be drilled.
            rrg_sec_drill = st.selectbox("Select Sector to Drill Down:",
                                         options=list(rotation_universe().keys()),
                                         key="tab_rrg_drill")
        elif rrg_mode == "💼 Custom Watchlist":
            rrg_custom_raw = st.text_input("Enter Tickers (comma separated):", value="DATAPATTNS, HAL, BEL, DEEPAKNTR, DIXON", key="tab_rrg_custom")

        # Resolve Symbols & Data
        interval = "1wk" if "Weekly" in rrg_tf else "1d"
        period = "2y" if "Weekly" in rrg_tf else "6mo"
        bench_symbol = "^CRSLDX"
        symbols_to_fetch = []
        disp_title = ""

        if rrg_mode == "🌍 All Sectors (rotation universe)":
            # Derived from sectors.db so every sector a stock can map to is plotted.
            _rot_uni = rotation_universe()
            symbols_to_fetch = list(_rot_uni.values()) + [bench_symbol, "^NSEI"]
            disp_title = f"{len(_rot_uni)} Sector Indices Rotation vs Nifty 500 ({rrg_tf})"
        elif rrg_mode == "🛡️ Capital Goods & Defense Stocks":
            DEFENSE_STOCKS = ['DATAPATTNS.NS', 'HAL.NS', 'BEL.NS', 'BDL.NS', 'COCHINSHIP.NS', 'MAZDOCK.NS', 'GRSE.NS', 'SOLARINDS.NS', 'ZENTEC.NS', 'MTARTECH.NS', 'BEML.NS', 'PARAS.NS']
            symbols_to_fetch = DEFENSE_STOCKS + [bench_symbol, "^CNXINFRA"]
            disp_title = f"Capital Goods & Defense Stocks Rotation ({rrg_tf})"
        elif rrg_mode == "🧪 Specialty Chemicals & Commodities":
            CHEMICAL_STOCKS = ['DEEPAKNTR.NS', 'AARTIIND.NS', 'NAVINFLUOR.NS', 'ATUL.NS', 'SRF.NS', 'CLEAN.NS', 'FINEORG.NS', 'CHAMBLFERT.NS', 'COROMANDEL.NS', 'UPL.NS', 'PIIND.NS']
            symbols_to_fetch = CHEMICAL_STOCKS + [bench_symbol, "^CNXCMDT"]
            disp_title = f"Specialty Chemicals & Commodities Rotation ({rrg_tf})"
        elif rrg_mode == "🏆 Nifty 50 Heavyweights":
            NIFTY_50_STOCKS = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'INFY.NS', 'BHARTIARTL.NS', 'ITC.NS', 'SBIN.NS', 'LT.NS', 'HINDUNILVR.NS', 'AXISBANK.NS', 'M&M.NS', 'TATAMOTORS.NS', 'SUNPHARMA.NS', 'NTPC.NS']
            symbols_to_fetch = NIFTY_50_STOCKS + [bench_symbol, "^NSEI"]
            disp_title = f"Nifty 50 Stock Rotation vs Nifty 500 ({rrg_tf})"
        elif rrg_mode == "🔍 Intra-Sector Breakdown" and rrg_sec_drill:
            sec_ticker = rotation_universe()[rrg_sec_drill]
            bench_symbol = sec_ticker
            db_path = os.path.join(os.path.dirname(__file__), "sectors.db")
            sec_stocks = []
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    rows = cur.execute("SELECT symbol FROM stock_sector WHERE sector_index = ?", (sec_ticker,)).fetchall()
                    sec_stocks = [r[0] + ".NS" for r in rows]
            if not sec_stocks:
                sec_stocks = ['DATAPATTNS.NS', 'HAL.NS', 'BEL.NS', 'BDL.NS']
            symbols_to_fetch = sec_stocks + [sec_ticker, "^NSEI"]
            disp_title = f"{rrg_sec_drill} Constituent Stocks vs {rrg_sec_drill} ({rrg_tf})"
        elif rrg_mode == "💼 Custom Watchlist" and rrg_custom_raw:
            raw_list = [s.strip().upper().replace('.NS', '') for s in rrg_custom_raw.split(',') if s.strip()]
            symbols_to_fetch = [s + ".NS" for s in raw_list] + [bench_symbol, "^NSEI"]
            disp_title = f"Custom Watchlist Rotation ({rrg_tf})"

        with st.spinner("Computing JdK RRG 4-Quadrant Rotation..."):
            data_map = load_universe_data(tuple(symbols_to_fetch), period=period, interval=interval)
            summary_df, tails_dict = compute_universe_rrg(
                data_map, 
                benchmark_symbol=bench_symbol.replace('.NS', '').replace('^', ''), 
                jdk_length=12, 
                tail_length=rrg_tail_len,
                # 18-Aug-2026: Strike.Money parity. RRG Studio is where this logic is
                # developed and Web Commander must match it - the whole point of the
                # split was to bring the result BACK here. Without this argument the
                # call fell through to compute_universe_rrg's "percentage" default and
                # the calibrated branch, though present in rrg_engine, never ran.
                # jdk_length above is IGNORED in this mode (strike_cal carries its own
                # 25/10/7 lookbacks); left in place so reverting the mode still works.
                mode="strike_cal"
            )

        if not summary_df.empty:
            # Filter tradeable if selected
            plot_df = summary_df.copy()
            if rrg_tradeable_only:
                plot_df = plot_df[plot_df['Is_Tradeable'] == True]

            rrg_label_mode = "Show All Tickers"
            fig_rrg = render_rrg_plotly(plot_df, tails_dict, title=disp_title, tail_length=rrg_tail_len, label_mode=rrg_label_mode)
            fig_rrg.update_layout(height=680)
            
            # Center the plot inside a container to maintain crisp square proportions
            col_chart_left, col_chart_center, col_chart_right = st.columns([1, 10, 1])
            with col_chart_center:
                st.plotly_chart(fig_rrg, use_container_width=True)
            
            st.markdown("#### 📊 RRG Rotation & Tradeable Gate Cockpit")
            _df_rrg_show = summary_df[[
                'Symbol', 'Quadrant_Badge', 'Arrow', 'Trajectory', 'Tradeable Gate', 
                'RRG Score', 'RS-Ratio', 'RS-Momentum', '4W %', 'Distance', 'Last_Price'
            ]].rename(columns={'Quadrant_Badge': 'Quadrant', 'Distance': 'Dist from Center'})
            
            if rrg_tradeable_only:
                _df_rrg_show = _df_rrg_show[_df_rrg_show['Tradeable Gate'] == '✓ BUY OK']
                
            st.dataframe(_df_rrg_show, use_container_width=True, hide_index=True)

            # ================================================================
            #  ROTATION DESK (21-Aug-2026)
            #  The chart + cockpit above say WHERE each sector sits. They never
            #  said what to DO about it, which is what Jay actually asks of this
            #  page: which sectors are working, which of my names sit in them,
            #  and is my book aligned. Those three, in that order.
            #  Logic lives in sector_rotation_view.py (pure, testable, no network).
            #  Sector standing RANKS and WARNS - it never filters. The RRG
            #  transition gate was measured at +0.12pp/4w and disabled in S4
            #  (rrg_cell_remeasure.py); this must not smuggle it back as a veto.
            # ================================================================
            if rrg_mode == "🌍 All Sectors (rotation universe)":
                try:
                    import sector_rotation_view as _srv

                    st.markdown("---")
                    st.markdown("### 🔄 Rotation Desk — what to do about it")

                    _lb = _srv.sector_leaderboard(summary_df)
                    if not _lb.empty:
                        st.info(_srv.rotation_summary_line(_lb))

                    _rt1, _rt2, _rt3 = st.tabs([
                        "🏆 Sector Leaderboard",
                        "🎯 Candidates in the Right Sectors",
                        "💼 My Book vs Rotation",
                    ])

                    # ---- 1. which sectors are working -------------------------
                    with _rt1:
                        if _lb.empty:
                            st.info("No sector rows to rank.")
                        else:
                            st.caption(
                                "Ranked by quadrant (Leading → Lagging), then distance from "
                                "centre — further out is a stronger statement of the same "
                                "quadrant. Benchmark rows are excluded.")
                            st.dataframe(_lb, use_container_width=True, hide_index=True)

                    # ---- 2. my shortlist, ordered by sector standing ----------
                    with _rt2:
                        _bpath = None
                        for _cand in ("gm_board_cache.csv", "FINAL_GOLDEN_MATCHER.csv"):
                            if os.path.exists(_cand):
                                _bpath = _cand
                                break
                        if _bpath is None:
                            st.info("No board cache yet — build the Trigger Board first.")
                        else:
                            _bdf = pd.read_csv(_bpath)
                            _cand_df = _srv.candidates_by_sector(_bdf, summary_df)
                            if _cand_df.empty:
                                st.info("No candidates to map.")
                            else:
                                _unm = int((_cand_df["Sector Standing"].astype(str)
                                            .str.contains("Unknown")).sum())
                                st.caption(
                                    f"From `{_bpath}` · {len(_cand_df)} names · "
                                    f"sector resolved for {len(_cand_df) - _unm}, "
                                    f"unmapped {_unm}. Sorted by sector standing FIRST, then "
                                    "Overall — so a strong name in a dead sector sinks. "
                                    "Nothing is removed; this ranks, it does not gate.")
                                st.dataframe(_cand_df, use_container_width=True, hide_index=True)

                    # ---- 3. is the book aligned ------------------------------
                    with _rt3:
                        # load_open_positions() is a LOCAL journal read. Deliberately
                        # NOT get_precomputed_classifications(): that fetches per-symbol
                        # over the network for every position and takes minutes, which
                        # would hang this tab on every visit. Sector mapping needs only
                        # symbol + qty + price, all of which are local.
                        _hold = None
                        try:
                            import pyramid_logic as _pl
                            _raw = _pl.load_open_positions()
                            if _raw is not None and not _raw.empty:
                                _hold = _raw.rename(columns={
                                    "symbol": "Symbol", "quantity": "Qty",
                                    "buy_price": "Avg", "setup": "Setup",
                                    "timeframe": "TF"})
                        except Exception as _he:
                            _gm_logger.warning(f"rotation desk: holdings load failed: {_he}")
                        if _hold is None or getattr(_hold, "empty", True):
                            st.info("No open positions available to map.")
                        else:
                            _per, _conc = _srv.holdings_by_sector(_hold, summary_df)
                            if _per.empty:
                                st.info("No holdings could be mapped.")
                            else:
                                st.markdown("**Concentration by sector**")
                                st.caption(
                                    "Cap imported from `pre_trade_gate.SECTOR_CAP_PCT`, the same "
                                    "number the order gate enforces — so this page and your "
                                    "entries cannot disagree.")
                                st.dataframe(_conc, use_container_width=True, hide_index=True)
                                st.markdown("**Positions — weakest sector standing first**")
                                st.caption(
                                    "This table exists to surface decay, so it is deliberately "
                                    "sorted worst-first. A holding in a Lagging sector is fighting "
                                    "the name and the tape at once.")
                                st.dataframe(_per, use_container_width=True, hide_index=True)
                except Exception as _re:
                    _gm_logger.warning(f"rotation desk failed: {_re}")
                    st.warning(f"Rotation Desk unavailable: {_re}")
        else:
            st.info("Sector RRG data unavailable for selected universe. Check network or symbols.")
