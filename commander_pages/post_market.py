# commander_pages/post_market.py - the POST-MARKET page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('post_market', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🌙 Post-Market Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">EOD Market Summary // Breadth Recap // FII/DII Provisional // Top Movers — 4:30 PM IST</div>', unsafe_allow_html=True)

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

    # GIFT Nifty pill (same as Pre-Market) — useful post-close too because it
    # ticks through overnight US/Asian sessions and frames the next open.
    try:
        from market_data_hub import fetch_gift_nifty as _fgn_po
        _gn2 = _fgn_po() or {}
        if _gn2:
            _c2 = _gn2.get("change_pct", 0)
            _col2 = "var(--bull)" if _c2 >= 0 else "var(--bear)"
            _ar2 = "▲" if _c2 >= 0 else "▼"
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center;margin:6px 0 10px 0;'
                f'padding:8px 14px;background:rgba(20,30,48,0.6);border-left:3px solid {_col2};'
                f'border-radius:6px;font-family:JetBrains Mono,monospace">'
                f'<span style="color:var(--ink);font-size:0.7rem;letter-spacing:1px">GIFT NIFTY</span>'
                f'<span style="color:var(--ink);font-size:1.05rem;font-weight:700">{_gn2.get("close",0):,.2f}</span>'
                f'<span style="color:{_col2};font-size:0.85rem">{_ar2} {_c2:+.2f}%</span>'
                f'<span style="color:var(--ink);font-size:0.65rem">O {_gn2.get("open",0):,.0f} · H {_gn2.get("high",0):,.0f} · L {_gn2.get("low",0):,.0f}</span>'
                f'<span style="color:var(--ink);font-size:0.62rem;margin-left:auto">as of {_gn2.get("date","")}</span>'
                f'</div>', unsafe_allow_html=True
            )
    except Exception as _gn_e2:
        st.caption(f"GIFT Nifty unavailable: {_gn_e2}")

    # External post-market analysis shortcuts (canonical EOD wrap pages)
    st.markdown(
        '<div style="display:flex;gap:10px;align-items:center;margin:0 0 10px 0;'
        'padding:6px 12px;background:rgba(20,30,48,0.3);border-radius:6px;'
        'font-family:JetBrains Mono,monospace;font-size:0.7rem">'
        '<span style="color:var(--ink);letter-spacing:1px">EXTERNAL ANALYSIS</span>'
        '<a href="https://economictimes.indiatimes.com/markets/stocks/news" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET · Closing Bell →</a>'
        '<a href="https://economictimes.indiatimes.com/prime/markets" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET Prime · Markets →</a>'
        '<a href="https://www.moneycontrol.com/markets/" target="_blank" '
        'style="color:var(--acc);text-decoration:none;font-weight:600">MC · Market Wrap →</a>'
        '<a href="https://www.moneycontrol.com/news/business/markets/" target="_blank" '
        'style="color:var(--acc);text-decoration:none;font-weight:600">MC Pro · Markets →</a>'
        '</div>', unsafe_allow_html=True
    )

    st.markdown("---")
    # Breadth tab removed on 19 May 2026: it ran a breadth-only regime classifier
    # ("BULL HEALTHY" when >55% of stocks > SMA50) that contradicted the composite
    # Market Regime ("Bear / Cash") in the top bar — same indicator name, two
    # incompatible definitions. The composite regime + the dedicated BREADTH page
    # already cover this surface; keeping a third panel here only confused things.
    _po1, _po3, _po4, _po5 = st.tabs([
        "📝 Summary", "💰 FII/DII", "📈 Movers", "💎 ET + MC Pro"
    ])

    with _po1:
        section("AI Post-Market Summary")
        _po_text = _latest_po.get("text")
        if _po_text:
            _render_ai_report(_po_text, header_color="var(--warn)")
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
                            _render_ai_report(summary, header_color="var(--warn)")
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    with _po3:
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
                _f1.metric("FII Net (latest)", f"₹{_fn:,.0f}Cr", delta_color="normal")
                _f2.metric("DII Net (latest)", f"₹{_dn:,.0f}Cr")
                _f3.metric("FII 5D Sum",
                           f"₹{_fii_df2['fii_net'].tail(5).sum():,.0f}Cr" if "fii_net" in _fii_df2 else "–")
                _f4.metric("DII 5D Sum",
                           f"₹{_fii_df2['dii_net'].tail(5).sum():,.0f}Cr" if "dii_net" in _fii_df2 else "–")

                try:
                    _fig_fii = go.Figure()
                    if "fii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["fii_net"],
                                         name="FII Net (₹Cr)",
                                         marker_color=["#15803D" if v>=0 else "#DC2626" for v in _fii_df2["fii_net"]])
                    if "dii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["dii_net"],
                                         name="DII Net (₹Cr)",
                                         marker_color=["#1D4ED8" if v>=0 else "#B45309" for v in _fii_df2["dii_net"]])
                    _fig_fii.update_layout(
                        height=280, barmode="group",
                        margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        legend=dict(font=dict(size=10, color="#E3EBEC"),bgcolor="rgba(0,0,0,0)"),
                        xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0",title="₹ Cr"),
                        font=dict(color="#E3EBEC")
                    )
                    st.plotly_chart(_fig_fii, use_container_width=True)
                except Exception: pass

                st.dataframe(_fii_df2.tail(30), use_container_width=True, hide_index=True)
            else:
                st.info("FII/DII data not available. NSE API may be down or data not yet released.")
        else:
            st.warning("market_data_hub not available.")

    with _po4:
        section("Today's Notable Movers")
        _mov_src = st.radio("Universe", ["📂 My Holdings", "📊 Nifty 50", "🔀 Both"],
                            horizontal=True, key="mov_src")

        # Build symbol list
        _mov_holding_syms = ([yf_symbol(s) for s in app_state.df_live_holdings["CleanSymbol"].tolist() if s]
                             if not app_state.df_live_holdings.empty else [])
        # Note: Infosys ticker is INFY.NS on Yahoo Finance, not INFOSYS.NS
        # (the latter returns 404 — was a typo that silently dropped Infy
        # from the universe and made non-N50 holdings look like leakage).
        _N50 = [
            "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
            "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","LT.NS",
            "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
            "TITAN.NS","SUNPHARMA.NS","ULTRACEMCO.NS","WIPRO.NS","ONGC.NS",
            "NESTLEIND.NS","POWERGRID.NS","NTPC.NS","HCLTECH.NS","TECHM.NS",
            "TATASTEEL.NS","JSWSTEEL.NS","TATAMOTORS.NS","M&M.NS","ADANIENT.NS",
            "ADANIPORTS.NS","COALINDIA.NS","BAJAJFINSV.NS","INDUSINDBK.NS","DRREDDY.NS",
            "CIPLA.NS","DIVISLAB.NS","EICHERMOT.NS","HEROMOTOCO.NS","APOLLOHOSP.NS",
            "BRITANNIA.NS","BPCL.NS","HINDALCO.NS","SHREECEM.NS","TATACONSUM.NS",
            "GRASIM.NS","SBILIFE.NS","HDFCLIFE.NS","PIDILITIND.NS","BAJAJ-AUTO.NS",
        ]

        if _mov_src == "📂 My Holdings":
            _mov_syms = _mov_holding_syms
        elif _mov_src == "📊 Nifty 50":
            _mov_syms = _N50
        else:
            _mov_syms = list(dict.fromkeys(_mov_holding_syms + _N50))  # deduplicated

        if _mov_syms:
            with st.spinner(f"Fetching price data for {len(_mov_syms)} symbols…"):
                try:
                    # C1 sweep: cached batch via data_provider
                    _mov_close = None
                    try:
                        import data_provider as _dp_mov
                        _bd_mov = _dp_mov.fetch_batch_ohlcv(_mov_syms, period="5d", interval="1d")
                        if _bd_mov:
                            _mov_close = pd.DataFrame({
                                (k if k.startswith("^") else f"{k}.NS"): df["Close"]
                                for k, df in _bd_mov.items() if "Close" in df.columns
                            })
                    except Exception as e:
                        logger.warning(f"Movers fetch: {e}")
                        _mov_close = None

                    _N50_set = set(_N50)
                    _hold_set = set(_mov_holding_syms)
                    _mov_rows = []
                    for _sym_yf in _mov_syms:
                        try:
                            _cl = (_mov_close[_sym_yf] if _sym_yf in _mov_close.columns
                                   else None)
                            if _cl is not None and len(_cl.dropna()) >= 2:
                                _today_c = float(_cl.dropna().iloc[-1])
                                _prev_c  = float(_cl.dropna().iloc[-2])
                                _chg     = (_today_c - _prev_c) / _prev_c * 100 if _prev_c else 0
                                _in_port = _sym_yf in _hold_set
                                _in_n50  = _sym_yf in _N50_set
                                # Source label makes Universe=Both transparent:
                                # the user can see whether a row is N50, a
                                # personal holding, or both at a glance.
                                if _in_port and _in_n50:
                                    _source = "N50 + Portfolio"
                                elif _in_n50:
                                    _source = "Nifty 50"
                                else:
                                    _source = "Portfolio"
                                _mov_rows.append({
                                    "Symbol":      _sym_yf.replace(".NS",""),
                                    "Close":       round(_today_c, 2),
                                    "Chg%":        round(_chg, 2),
                                    "Source":      _source,
                                    "In Portfolio": "✅" if _in_port else "",
                                })
                        except Exception:
                            pass

                    if _mov_rows:
                        _df_mov = pd.DataFrame(_mov_rows).sort_values("Chg%", ascending=False).reset_index(drop=True)
                        _df_mov["Signal"] = _df_mov["Chg%"].apply(
                            lambda x: "🚀 Strong" if x > 3 else "📈 Up" if x > 0 else "📉 Down" if x > -3 else "🔻 Weak")

                        _TOP_N = 10
                        _COLS  = ["Symbol","Close","Chg%","Signal","Source","In Portfolio"]

                        # Split on sign so a stock can't appear in BOTH lists.
                        # If the universe is small (e.g. 3 holdings) a simple
                        # head/tail split would overlap — filter by Chg% instead.
                        _df_gainers = (_df_mov[_df_mov["Chg%"] >= 0]
                                       .head(_TOP_N)[_COLS]
                                       .reset_index(drop=True))
                        _df_losers  = (_df_mov[_df_mov["Chg%"] < 0]
                                       .iloc[::-1]          # worst-first
                                       .head(_TOP_N)[_COLS]
                                       .reset_index(drop=True))

                        _mv_col1, _mv_col2 = st.columns(2, gap="medium")
                        with _mv_col1:
                            sub_label(f"🏆 Top Gainers ({len(_df_gainers)})")
                            if _df_gainers.empty:
                                st.info("No gainers today.")
                            else:
                                st.dataframe(_df_gainers, use_container_width=True, hide_index=True)
                        with _mv_col2:
                            sub_label(f"📉 Top Losers ({len(_df_losers)})")
                            if _df_losers.empty:
                                st.info("No losers today.")
                            else:
                                st.dataframe(_df_losers, use_container_width=True, hide_index=True)
                except Exception as _e:
                    st.error(f"Mover data error: {_e}")
        else:
            st.info("No symbols to scan. Load holdings via Dhan or select Nifty 50.")

    with _po5:
        section("Post-Market — ET Prime + Moneycontrol Pro")
        # Filter to EOD / closing / market-wrap / after-hours items.
        _PO_KWS = [
            "post-market", "postmarket", "post market",
            "closing bell", "market wrap", "market close", "closing",
            "eod", "end of day", "today's market", "todays market",
            "sensex closes", "nifty closes", "settles", "settled",
            "after market", "after-hours", "session ends", "wraps up",
            "today's top", "top gainers", "top losers", "movers",
        ]
        _render_paid_news_grid(
            key_prefix="po_paid",
            keyword_filter=_PO_KWS,
            default_limit=50,
            show_recos_only=False,
            caption=("Filtered to EOD / closing-bell / market-wrap headlines from your "
                     "ET Prime + MC Pro subscriptions. Cards are colour-coded by analyst "
                     "action (Buy / Hold / Sell). Cached 1h."),
        )
