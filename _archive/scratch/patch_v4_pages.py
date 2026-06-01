

# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — PRE-MARKET INTELLIGENCE HUB
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'PRE-MARKET':
    st.markdown('<div class="page-title">🌅 Pre-Market Intelligence Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Global Overnight Pulse // FII/DII // VIX // Calendar // AI Brief — 8:30 AM IST</div>', unsafe_allow_html=True)

    pm_tab = st.session_state.premarkettab

    # ── Shared: latest report meta ──────────────────────────────────────────
    _latest_pm = {}
    if _SCHED_OK:
        try: _latest_pm = load_latest_report("premarket")
        except Exception: pass

    _last_upd = _latest_pm.get("generated_at", "Not yet generated")
    c_refresh, c_meta = st.columns([1, 5])
    with c_refresh:
        if st.button("🔄 Refresh Now", key="pm_refresh", type="primary"):
            with st.spinner("Fetching data and generating report..."):
                try:
                    if _SCHED_OK:
                        trigger_manual_report("premarket")
                        st.toast("✅ Pre-market report refreshed!", icon="🌅")
                        st.rerun()
                    else:
                        st.error("Scheduler module not available")
                except Exception as _e:
                    st.error(f"Refresh failed: {_e}")
    with c_meta:
        st.caption(f"🕐 Last updated: {_last_upd}  |  Scheduler auto-runs at 8:30 AM IST Mon–Fri")

    st.markdown("---")

    if pm_tab == 'BRIEF':
        section("AI Pre-Market Brief")
        _brief_text = _latest_pm.get("text")
        if _brief_text:
            _sections = [s.strip() for s in _brief_text.split("===") if s.strip()]
            if len(_sections) >= 2:
                for _sec in _sections:
                    _lines = _sec.strip().split("\n", 1)
                    _title = _lines[0].strip() if _lines else ""
                    _body  = _lines[1].strip() if len(_lines) > 1 else _sec
                    if _title:
                        st.markdown(f"""
                        <div class="metric-card" style="text-align:left;margin-bottom:10px;">
                          <div style="font-family:'Rajdhani',sans-serif;font-size:1.05rem;font-weight:700;
                                      color:#58a6ff;letter-spacing:1px;margin-bottom:6px;">{_title}</div>
                          <div style="font-family:'Inter',sans-serif;font-size:0.85rem;color:#c9d1d9;
                                      line-height:1.6;">{_body}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.6;">{_body}</div>',
                                    unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;">{_brief_text}</div>',
                            unsafe_allow_html=True)
        else:
            st.info("No pre-market report yet. Click **Refresh Now** to generate one.")
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Now", key="pm_gen_now", type="primary"):
                    with st.spinner("Generating AI pre-market brief..."):
                        try:
                            snap = build_premarket_snapshot()
                            brief = generate_premarket_brief(snap)
                            st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;">{brief}</div>',
                                        unsafe_allow_html=True)
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    elif pm_tab == 'GLOBAL':
        section("Global Overnight Pulse")
        if not _HUB_OK:
            st.warning("⚠️ market_data_hub module not available. Please check installation.")
        else:
            with st.spinner("Fetching global market data..."):
                try:
                    _global = fetch_global_overview()
                except Exception as _e:
                    st.error(f"Data fetch error: {_e}"); _global = {}

            if _global:
                _indices  = _global.get("indices", {})
                _comms    = _global.get("commodities", {})
                _currs    = _global.get("currencies", {})
                _bonds    = _global.get("bonds", {})
                _fetched  = _global.get("fetched_at", "")

                st.caption(f"Data fetched at: {_fetched} IST")

                section("Equity Indices")
                _americas = {k:v for k,v in _indices.items() if k in ["S&P 500","NASDAQ 100","Dow Jones","US VIX"]}
                _europe   = {k:v for k,v in _indices.items() if k in ["DAX","FTSE 100"]}
                _asia     = {k:v for k,v in _indices.items() if k in ["Nifty 50","India VIX","GIFT Nifty","Nikkei 225","Hang Seng"]}

                _reg_cols = st.columns(3, gap="medium")
                for _reg_col, _reg_name, _reg_data in zip(
                    _reg_cols, ["🌎 Americas","🌍 Europe","🌏 Asia-Pacific"],
                    [_americas, _europe, _asia]
                ):
                    with _reg_col:
                        st.markdown(f'<div class="section-sub-lbl">{_reg_name}</div>', unsafe_allow_html=True)
                        for _name, _dat in _reg_data.items():
                            if not _dat: continue
                            _chg  = _dat.get("change_pct", 0) or 0
                            _ltp  = _dat.get("ltp", 0) or 0
                            _col  = "#00f260" if _chg >= 0 else "#ff4b4b"
                            _arrow= "▲" if _chg >= 0 else "▼"
                            st.markdown(f"""
                            <div style="display:flex;justify-content:space-between;align-items:center;
                                        padding:5px 0;border-bottom:1px solid #1e3a5f;">
                              <span style="font-family:'Inter',sans-serif;font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                              <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                                {_arrow} {abs(_chg):.2f}%</span>
                            </div>""", unsafe_allow_html=True)

                st.markdown("---")
                _cc1, _cc2 = st.columns(2, gap="medium")

                with _cc1:
                    section("Commodities")
                    for _name, _dat in _comms.items():
                        if not _dat: continue
                        _chg = _dat.get("change_pct", 0) or 0
                        _ltp = _dat.get("ltp", 0) or 0
                        _col = "#00f260" if _chg >= 0 else "#ff4b4b"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a5f;">
                          <span style="font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.2f} ({'+' if _chg>=0 else ''}{_chg:.1f}%)</span>
                        </div>""", unsafe_allow_html=True)

                with _cc2:
                    section("Currencies & Bonds")
                    for _name, _dat in {**_currs, **_bonds}.items():
                        if not _dat: continue
                        _chg = _dat.get("change_pct", 0) or 0
                        _ltp = _dat.get("ltp", 0) or 0
                        _col = "#00f260" if _chg >= 0 else "#ff4b4b"
                        if _name == "USD/INR": _col = "#ff4b4b" if _chg > 0 else "#00f260"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a5f;">
                          <span style="font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.4f} ({'+' if _chg>=0 else ''}{_chg:.2f}%)</span>
                        </div>""", unsafe_allow_html=True)

    elif pm_tab == 'CALENDAR':
        section("Economic & Events Calendar")
        if _HUB_OK:
            try:
                _cal = fetch_economic_calendar()
                if _cal:
                    _df_cal = pd.DataFrame(_cal)
                    _df_cal["date"] = pd.to_datetime(_df_cal["date"])
                    _df_cal = _df_cal.sort_values("date")

                    def _imp_color(imp):
                        return "#ff4b4b" if imp=="HIGH" else "#e3b341" if imp=="MEDIUM" else "#5a8a9f"

                    _cal_cols = st.columns([1,3,1,1,1,1], gap="small")
                    for _h, _c in zip(["Date","Event","Importance","Previous","Forecast","Actual"], _cal_cols):
                        _c.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#5a8a9f;letter-spacing:2px;text-transform:uppercase;">{_h}</div>', unsafe_allow_html=True)
                    st.markdown('<div style="border-bottom:1px solid #1e3a5f;margin:4px 0 8px 0;"></div>', unsafe_allow_html=True)

                    for _, _row in _df_cal.iterrows():
                        _c1,_c2,_c3,_c4,_c5,_c6 = st.columns([1,3,1,1,1,1], gap="small")
                        _c1.markdown(f'<div style="font-size:0.78rem;color:#8b949e;">{_row["date"].strftime("%d %b")}</div>', unsafe_allow_html=True)
                        _c2.markdown(f'<div style="font-size:0.82rem;color:#e6edf3;">{_row.get("event","")}</div>', unsafe_allow_html=True)
                        _imp = _row.get("importance","")
                        _c3.markdown(f'<div style="font-size:0.78rem;font-weight:600;color:{_imp_color(_imp)};">{_imp}</div>', unsafe_allow_html=True)
                        _c4.markdown(f'<div style="font-size:0.78rem;color:#8b949e;">{_row.get("previous","–")}</div>', unsafe_allow_html=True)
                        _c5.markdown(f'<div style="font-size:0.78rem;color:#adbac7;">{_row.get("forecast","–")}</div>', unsafe_allow_html=True)
                        _act = _row.get("actual","")
                        _act_col = "#e6edf3" if _act else "#3d5a6e"
                        _c6.markdown(f'<div style="font-size:0.78rem;color:{_act_col};">{_act if _act else "Pending"}</div>', unsafe_allow_html=True)
                else:
                    st.info("No calendar events available.")
            except Exception as _e:
                st.error(f"Calendar fetch error: {_e}")
        else:
            st.warning("market_data_hub not available.")

    elif pm_tab == 'OPTIONS':
        section("Pre-Market Options Snapshot — Nifty")
        if _HUB_OK:
            try:
                _opts = fetch_nse_options_summary("NIFTY")
                if _opts:
                    _o1,_o2,_o3,_o4 = st.columns(4, gap="small")
                    _o1.metric("PCR (OI)", f'{_opts.get("pcr_oi",0):.2f}',
                                help=">1.2 Bullish | <0.7 Bearish")
                    _o2.metric("PCR (Vol)", f'{_opts.get("pcr_vol",0):.2f}')
                    _o3.metric("Max Pain", f'{_opts.get("max_pain_strike","–")}')
                    _o4.metric("ATM IV", f'{_opts.get("atm_iv","–")}%' if _opts.get("atm_iv") else "–")

                    _o5,_o6,_o7,_o8 = st.columns(4, gap="small")
                    _o5.metric("Total Call OI", f'{_opts.get("total_call_oi",0):,.0f}')
                    _o6.metric("Total Put OI",  f'{_opts.get("total_put_oi",0):,.0f}')
                    _o7.metric("Call Wall",     f'{_opts.get("strongest_call_strike","–")}')
                    _o8.metric("Put Wall",      f'{_opts.get("strongest_put_strike","–")}')

                    _pcr = _opts.get("pcr_oi", 1.0)
                    if _pcr > 1.2:   _pcr_sig, _pcr_col = "🟢 BULLISH — heavy Put writing (market supported)", "#00f260"
                    elif _pcr < 0.7: _pcr_sig, _pcr_col = "🔴 BEARISH — heavy Call writing (market capped)", "#ff4b4b"
                    else:            _pcr_sig, _pcr_col = "🟡 NEUTRAL — balanced positioning", "#e3b341"
                    st.markdown(f'<div class="metric-card" style="margin-top:12px;">'
                                f'<div class="metric-label">PCR Signal</div>'
                                f'<div class="metric-value" style="color:{_pcr_col};font-size:0.88rem;">{_pcr_sig}</div>'
                                f'</div>', unsafe_allow_html=True)
                else:
                    st.info("Options data unavailable. NSE API may require market hours.")
            except Exception as _e:
                st.error(f"Options fetch error: {_e}")
        else:
            st.warning("market_data_hub not available.")


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — POST-MARKET ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'POST-MARKET':
    st.markdown('<div class="page-title">🌙 Post-Market Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">EOD Market Summary // Breadth Recap // FII/DII Provisional // Top Movers — 4:30 PM IST</div>', unsafe_allow_html=True)

    po_tab = st.session_state.postmarkettab

    _latest_po = {}
    if _SCHED_OK:
        try: _latest_po = load_latest_report("postmarket")
        except Exception: pass

    _last_upd_po = _latest_po.get("generated_at", "Not yet generated")
    c_ref2, c_meta2 = st.columns([1, 5])
    with c_ref2:
        if st.button("🔄 Refresh Now", key="po_refresh", type="primary"):
            with st.spinner("Fetching EOD data and generating summary..."):
                try:
                    if _SCHED_OK:
                        trigger_manual_report("postmarket")
                        st.toast("✅ Post-market report refreshed!", icon="🌙")
                        st.rerun()
                    else:
                        st.error("Scheduler module not available")
                except Exception as _e:
                    st.error(f"Refresh failed: {_e}")
    with c_meta2:
        st.caption(f"🕐 Last updated: {_last_upd_po}  |  Scheduler auto-runs at 4:30 PM IST Mon–Fri")

    st.markdown("---")

    if po_tab == 'SUMMARY':
        section("AI Post-Market Summary")
        _po_text = _latest_po.get("text")
        if _po_text:
            _po_secs = [s.strip() for s in _po_text.split("===") if s.strip()]
            if len(_po_secs) >= 2:
                for _sec in _po_secs:
                    _lns = _sec.strip().split("\n", 1)
                    _ttl = _lns[0].strip() if _lns else ""
                    _bdy = _lns[1].strip() if len(_lns) > 1 else _sec
                    if _ttl:
                        st.markdown(f"""
                        <div class="metric-card" style="text-align:left;margin-bottom:10px;">
                          <div style="font-family:'Rajdhani',sans-serif;font-size:1.05rem;font-weight:700;
                                      color:#e3b341;letter-spacing:1px;margin-bottom:6px;">{_ttl}</div>
                          <div style="font-size:0.85rem;color:#c9d1d9;line-height:1.6;">{_bdy}</div>
                        </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;">{_po_text}</div>',
                            unsafe_allow_html=True)
        else:
            st.info("No post-market report yet. Click **Refresh Now** or wait for 4:30 PM auto-run.")
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Now", key="po_gen_now", type="primary"):
                    with st.spinner("Generating AI post-market summary..."):
                        try:
                            snap = build_postmarket_snapshot()
                            if _BREADTH_OK:
                                snap["breadth"] = calculate_breadth_metrics()
                                snap["breadth_regime"] = build_breadth_regime(snap["breadth"])
                            summary = generate_postmarket_summary(snap)
                            st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.7;white-space:pre-wrap;">{summary}</div>',
                                        unsafe_allow_html=True)
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    elif po_tab == 'BREADTH':
        section("End-of-Day Breadth Snapshot")
        if _BREADTH_OK:
            with st.spinner("Calculating breadth metrics..."):
                try:
                    _br = calculate_breadth_metrics()
                except Exception as _e:
                    _br = {}; st.error(f"Breadth error: {_e}")

            if _br:
                _regime_str = build_breadth_regime(_br)
                _reg_c = "#00f260" if "BULL" in _regime_str else "#ff4b4b" if "BEAR" in _regime_str else "#e3b341"
                st.markdown(f"""
                <div class="metric-card" style="margin-bottom:16px;">
                  <div class="metric-label">Breadth Regime</div>
                  <div class="metric-value" style="color:{_reg_c};font-size:1.2rem;">{_regime_str}</div>
                  <div style="font-size:0.65rem;color:#5a8a9f;margin-top:4px;">
                    Based on {_br.get("symbols_analyzed",0)} stocks | {_br.get("calculated_at","")}
                  </div>
                </div>""", unsafe_allow_html=True)

                _b1,_b2,_b3,_b4 = st.columns(4, gap="small")
                _b1.metric("Above SMA50",  f"{_br.get('above_sma50_pct',0):.1f}%")
                _b2.metric("Above SMA150", f"{_br.get('above_sma150_pct',0):.1f}%")
                _b3.metric("Above SMA200", f"{_br.get('above_sma200_pct',0):.1f}%")
                _b4.metric("Stage 2",      f"{_br.get('stage2_pct',0):.1f}%")

                _b5,_b6,_b7,_b8 = st.columns(4, gap="small")
                _b5.metric("52W Highs",    str(_br.get("new_52w_high_count",0)))
                _b6.metric("52W Lows",     str(_br.get("new_52w_low_count",0)))
                _b7.metric("A/D Ratio",    f"{_br.get('ad_ratio',0):.2f}")
                _b8.metric("H/L Ratio",    f"{_br.get('high_low_ratio',0):.2f}")
        else:
            st.warning("breadth_engine module not available.")

    elif po_tab == 'FII/DII':
        section("FII/DII Provisional Data")
        if _HUB_OK:
            with st.spinner("Fetching FII/DII data..."):
                try: _fii_df2 = fetch_fii_dii_data()
                except Exception as _e: _fii_df2 = pd.DataFrame(); st.error(str(_e))

            if not _fii_df2.empty:
                _latest_fii = _fii_df2.iloc[-1]
                _f1,_f2,_f3,_f4 = st.columns(4, gap="small")
                _fn = float(_latest_fii.get("fii_net",0))
                _dn = float(_latest_fii.get("dii_net",0))
                _f1.metric("FII Net (latest)", f"₹{_fn/1e7:.2f}Cr", delta_color="normal")
                _f2.metric("DII Net (latest)", f"₹{_dn/1e7:.2f}Cr")
                _f3.metric("FII 5D Sum",
                           f"₹{_fii_df2['fii_net'].tail(5).sum()/1e7:.1f}Cr" if "fii_net" in _fii_df2 else "–")
                _f4.metric("DII 5D Sum",
                           f"₹{_fii_df2['dii_net'].tail(5).sum()/1e7:.1f}Cr" if "dii_net" in _fii_df2 else "–")

                try:
                    _fig_fii = go.Figure()
                    if "fii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["fii_net"]/1e7,
                                         name="FII Net (₹Cr)",
                                         marker_color=["#00f260" if v>=0 else "#ff4b4b" for v in _fii_df2["fii_net"]])
                    if "dii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["dii_net"]/1e7,
                                         name="DII Net (₹Cr)",
                                         marker_color=["#58a6ff" if v>=0 else "#e3b341" for v in _fii_df2["dii_net"]])
                    _fig_fii.update_layout(
                        height=280, barmode="group",
                        margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        legend=dict(font=dict(size=10,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                        xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f",title="₹ Cr"),
                        font=dict(color="#c9d1d9")
                    )
                    st.plotly_chart(_fig_fii, use_container_width=True)
                except Exception: pass

                st.dataframe(_fii_df2.tail(30), use_container_width=True, hide_index=True)
            else:
                st.info("FII/DII data not available. NSE API may be down or data not yet released.")
        else:
            st.warning("market_data_hub not available.")

    elif po_tab == 'MOVERS':
        section("Today's Notable Movers")
        st.caption("Uses live holdings and watchlist data. For full screener, use HUNTER page.")
        if not df_live_holdings.empty:
            _mov_syms = [yf_symbol(s) for s in df_live_holdings["CleanSymbol"].tolist() if s]
            if _mov_syms:
                try:
                    _mov_data = yf.download(_mov_syms, period="2d", interval="1d",
                                            auto_adjust=True, progress=False)
                    if isinstance(_mov_data.columns, pd.MultiIndex):
                        _mov_close = _mov_data["Close"]
                    else:
                        _mov_close = _mov_data[["Close"]]

                    _mov_rows = []
                    for _sym_yf in _mov_syms:
                        try:
                            _cl = _mov_close[_sym_yf] if _sym_yf in _mov_close.columns else None
                            if _cl is not None and len(_cl.dropna()) >= 2:
                                _today_c = float(_cl.dropna().iloc[-1])
                                _prev_c  = float(_cl.dropna().iloc[-2])
                                _chg     = (_today_c - _prev_c) / _prev_c * 100 if _prev_c else 0
                                _mov_rows.append({"Symbol": _sym_yf.replace(".NS",""),
                                                  "Today Close": _today_c, "Chg%": round(_chg,2)})
                        except Exception: pass

                    if _mov_rows:
                        _df_mov = pd.DataFrame(_mov_rows).sort_values("Chg%", ascending=False)
                        _df_mov["Signal"] = _df_mov["Chg%"].apply(
                            lambda x: "🚀 Strong" if x>3 else "📈 Up" if x>0 else "📉 Down" if x>-3 else "🔻 Weak")
                        st.dataframe(_df_mov, use_container_width=True, hide_index=True)
                except Exception as _e:
                    st.error(f"Mover data error: {_e}")
        else:
            st.info("No live positions found. Add holdings via Dhan broker to see movers.")

# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — MARKET BREADTH ENGINE
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'BREADTH':
    st.markdown('<div class="page-title">📈 Market Breadth Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Nifty 500 Internals // A/D Ratio // McClellan // Stage Distribution // Sector Breadth</div>', unsafe_allow_html=True)

    br_tab = st.session_state.breadthtab

    if not _BREADTH_OK:
        st.error("❌ breadth_engine module not available. Please check installation.")
    else:
        if br_tab == 'OVERVIEW':
            section("Breadth Overview — Nifty 500 Universe")
            with st.spinner("Calculating breadth metrics (may take 30–60s first run)..."):
                try:
                    _bm = calculate_breadth_metrics()
                except Exception as _be:
                    _bm = {}; st.error(f"Breadth calculation error: {_be}")

            if _bm:
                _regime_s = build_breadth_regime(_bm)
                _r_col = "#00f260" if "BULL" in _regime_s else "#ff4b4b" if "BEAR" in _regime_s else "#e3b341"
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border:1px solid {_r_col};border-radius:8px;
                            padding:16px 24px;margin-bottom:20px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#5a8a9f;letter-spacing:3px;text-transform:uppercase;">Breadth Regime</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:2rem;font-weight:700;color:{_r_col};margin:4px 0;">{_regime_s}</div>
                  <div style="font-size:0.68rem;color:#5a8a9f;">{_bm.get("symbols_analyzed",0)} stocks analyzed | Updated: {_bm.get("calculated_at","")}</div>
                </div>""", unsafe_allow_html=True)

                _g1,_g2,_g3,_g4 = st.columns(4, gap="small")
                _g1.metric("Above SMA 50",  f"{_bm.get('above_sma50_pct',0):.1f}%",
                           help="% of Nifty 500 stocks above their 50-day moving average")
                _g2.metric("Above SMA 150", f"{_bm.get('above_sma150_pct',0):.1f}%",
                           help="% above 150-day MA — intermediate trend health")
                _g3.metric("Above SMA 200", f"{_bm.get('above_sma200_pct',0):.1f}%",
                           help="% above 200-day MA — long-term breadth")
                _g4.metric("Stage 2",       f"{_bm.get('stage2_pct',0):.1f}%",
                           help="% in confirmed Stage 2 (price > SMA200, SMA200 sloping up)")

                _g5,_g6,_g7,_g8 = st.columns(4, gap="small")
                _g5.metric("New 52W Highs", str(_bm.get("new_52w_high_count",0)))
                _g6.metric("New 52W Lows",  str(_bm.get("new_52w_low_count",0)))
                _g7.metric("A/D Ratio",     f"{_bm.get('ad_ratio',0):.2f}",
                           help=">2.0 = Bullish thrust | <0.5 = Bearish pressure")
                _g8.metric("High/Low Ratio",f"{_bm.get('high_low_ratio',0):.2f}",
                           help=">0.7 = Healthy | <0.3 = Weak")

                _sma_data = {
                    "SMA 50":  _bm.get("above_sma50_pct",0),
                    "SMA 150": _bm.get("above_sma150_pct",0),
                    "SMA 200": _bm.get("above_sma200_pct",0),
                    "Stage 2": _bm.get("stage2_pct",0),
                }
                _fig_bar = go.Figure(go.Bar(
                    x=list(_sma_data.keys()), y=list(_sma_data.values()),
                    marker_color=["#00f260" if v>50 else "#e3b341" if v>30 else "#ff4b4b"
                                  for v in _sma_data.values()],
                    text=[f"{v:.1f}%" for v in _sma_data.values()], textposition="auto"
                ))
                _fig_bar.add_hline(y=50, line_dash="dot", line_color="#5a8a9f", line_width=1,
                                   annotation_text="50% neutral line")
                _fig_bar.update_layout(
                    height=260, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                    xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f",range=[0,100]),
                    font=dict(color="#c9d1d9"), title_text="% Stocks Above Key Moving Averages"
                )
                st.plotly_chart(_fig_bar, use_container_width=True)

        elif br_tab == 'SECTORS':
            section("Sector Breadth")
            with st.spinner("Fetching sector data..."):
                try:
                    _sec_df = get_sector_breadth()
                except Exception as _e:
                    _sec_df = pd.DataFrame(); st.error(str(_e))

            if not _sec_df.empty:
                def _stage_icon(s):
                    return "🟢" if "Stage 2" in str(s) else "🔴" if "Stage 4" in str(s) else "🟡"

                _sec_disp = _sec_df.copy()
                if "Stage" in _sec_disp.columns:
                    _sec_disp[""] = _sec_disp["Stage"].apply(_stage_icon)

                st.dataframe(_sec_disp, use_container_width=True, hide_index=True)

                if "Monthly%" in _sec_disp.columns and "Sector" in _sec_disp.columns:
                    _fig_sec = go.Figure(go.Bar(
                        x=_sec_disp["Sector"].str.replace("Nifty ",""),
                        y=_sec_disp["Monthly%"],
                        marker_color=["#00f260" if v>=0 else "#ff4b4b" for v in _sec_disp["Monthly%"]],
                        text=[f"{v:+.1f}%" for v in _sec_disp["Monthly%"]], textposition="auto"
                    ))
                    _fig_sec.update_layout(
                        height=260, margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f",tickangle=-30), yaxis=dict(gridcolor="#1e3a5f"),
                        font=dict(color="#c9d1d9"), title_text="Monthly % Change by Sector"
                    )
                    st.plotly_chart(_fig_sec, use_container_width=True)
            else:
                st.info("Sector breadth data unavailable.")

        elif br_tab == 'MCCLELLAN':
            section("McClellan Oscillator")
            st.info("McClellan calculation requires historical daily A/D data. "
                    "Populate `reports/latest_breadth.json` by running the daily breadth job "
                    "for at least 40 trading days. The oscillator will appear automatically.")

        elif br_tab == 'STAGE MAP':
            section("Stage Distribution — Nifty 500")
            with st.spinner("Loading stage data..."):
                try:
                    _bm2 = calculate_breadth_metrics()
                except Exception:
                    _bm2 = {}

            if _bm2:
                _total = _bm2.get("symbols_analyzed", 1)
                _s2_pct = _bm2.get("stage2_pct", 0)
                _above200 = _bm2.get("above_sma200_pct", 0)
                _below200 = 100 - _above200

                _stage_data = {
                    "Stage 2 (Advance)": _s2_pct,
                    "Stage 1/3 (Base/Top)": max(0, _above200 - _s2_pct),
                    "Stage 4 (Decline)": _below200,
                }
                _fig_pie = go.Figure(go.Pie(
                    labels=list(_stage_data.keys()),
                    values=list(_stage_data.values()),
                    hole=0.5,
                    marker_colors=["#00f260","#e3b341","#ff4b4b"],
                    textfont=dict(size=12, color="#e6edf3")
                ))
                _fig_pie.update_layout(
                    height=320, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(font=dict(size=11,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                    annotations=[dict(text=f"S2: {_s2_pct:.0f}%",
                                      x=0.5, y=0.5, font_size=20,
                                      font_color="#00f260", showarrow=False)]
                )
                st.plotly_chart(_fig_pie, use_container_width=True)
                st.caption("Stage 2 > 35% = Confirmed Bull Market. Stage 2 < 20% = Bear Market.")

# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — MACRO: GLOBAL INDICES TAB + FII/DII FLOWS TAB (appended to existing MACRO)
# ══════════════════════════════════════════════════════════════════════════════
# NOTE: The MACRO page elif block above handles 'OVERVIEW' and 'SECTOR RRG' tabs.
# The new tabs 'GLOBAL INDICES' and 'FII/DII FLOWS' need to be inserted into
# that block. Since we patched mac_opts to include them, they will fall through
# to this catch-all handler below which is checked ONLY when page=='MACRO' and
# the tab is one of the new ones.
# We use a session-state trick: after the existing MACRO block runs its tabs,
# Python falls through — so we re-check here.

if page == 'MACRO' and st.session_state.get("macrotab") == 'GLOBAL INDICES':
    section("Global Indices — Full Board")
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
                    _rows.append({
                        "Name": _n, "LTP": _d.get("ltp",0),
                        "Chg%": _d.get("change_pct",0),
                        "52W High": _d.get("week52_high",0),
                        "52W Low":  _d.get("week52_low",0),
                        "vs 52W H": f"{_d.get('pct_vs_52h',0):.1f}%",
                    })
            if _rows:
                _df_glo = pd.DataFrame(_rows)
                st.dataframe(_df_glo, use_container_width=True, hide_index=True)
    else:
        st.warning("market_data_hub not available.")

elif page == 'MACRO' and st.session_state.get("macrotab") == 'FII/DII FLOWS':
    section("FII/DII Cumulative Flows")
    if _HUB_OK:
        with st.spinner("Fetching FII/DII flow history..."):
            try: _fii3 = fetch_fii_dii_data()
            except Exception as _e: _fii3 = pd.DataFrame(); st.error(str(_e))

        if not _fii3.empty and "fii_net" in _fii3.columns:
            _fii3["fii_cumulative"] = _fii3["fii_net"].cumsum() / 1e7
            _fii3["dii_cumulative"] = _fii3["dii_net"].cumsum() / 1e7

            _fig_cum = go.Figure()
            _x = _fii3["date"] if "date" in _fii3.columns else _fii3.index
            _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["fii_cumulative"],
                                          name="FII Cumulative (₹Cr)", line=dict(color="#00f260",width=2)))
            _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["dii_cumulative"],
                                          name="DII Cumulative (₹Cr)", line=dict(color="#58a6ff",width=2)))
            _fig_cum.add_hline(y=0, line_dash="dot", line_color="#3d5a6e", line_width=1)
            _fig_cum.update_layout(
                height=340, margin=dict(t=10,l=0,r=0,b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                legend=dict(font=dict(size=10,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f",title="₹ Crore"),
                font=dict(color="#c9d1d9")
            )
            st.plotly_chart(_fig_cum, use_container_width=True)
            st.dataframe(_fii3[["date","fii_net","dii_net","fii_buy","fii_sell"]].tail(30)
                         if "fii_buy" in _fii3.columns else _fii3.tail(30),
                         use_container_width=True, hide_index=True)
        else:
            st.info("FII/DII flow data unavailable.")
    else:
        st.warning("market_data_hub not available.")
