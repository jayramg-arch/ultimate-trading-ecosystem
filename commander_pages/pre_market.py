# commander_pages/pre_market.py - the PRE-MARKET page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('pre_market', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🌅 Pre-Market Intelligence Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Global Overnight Pulse // FII/DII // VIX // Calendar // AI Brief — 8:30 AM IST</div>', unsafe_allow_html=True)

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

    # GIFT Nifty pill — canonical overnight indicator for cash Nifty.
    # Sourced from investing.com (yfinance has no working GIFT/SGX symbol).
    try:
        from market_data_hub import fetch_gift_nifty as _fgn_pm
        _gn = _fgn_pm() or {}
        if _gn:
            _gn_chg = _gn.get("change_pct", 0)
            _gn_col = "var(--bull)" if _gn_chg >= 0 else "var(--bear)"
            _gn_arrow = "▲" if _gn_chg >= 0 else "▼"
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center;margin:6px 0 10px 0;'
                f'padding:8px 14px;background:rgba(20,30,48,0.6);border-left:3px solid {_gn_col};'
                f'border-radius:6px;font-family:JetBrains Mono,monospace">'
                f'<span style="color:var(--ink);font-size:0.7rem;letter-spacing:1px">GIFT NIFTY</span>'
                f'<span style="color:var(--ink);font-size:1.05rem;font-weight:700">{_gn.get("close",0):,.2f}</span>'
                f'<span style="color:{_gn_col};font-size:0.85rem">{_gn_arrow} {_gn_chg:+.2f}%</span>'
                f'<span style="color:var(--ink);font-size:0.65rem">O {_gn.get("open",0):,.0f} · H {_gn.get("high",0):,.0f} · L {_gn.get("low",0):,.0f}</span>'
                f'<span style="color:var(--ink);font-size:0.62rem;margin-left:auto">as of {_gn.get("date","")}</span>'
                f'</div>', unsafe_allow_html=True
            )
    except Exception as _gn_e:
        st.caption(f"GIFT Nifty unavailable: {_gn_e}")

    # Direct links to external pre-market analysis on ET Prime + MC Pro.
    # The paid news grid is in the ET + MC Pro tab below; these are
    # one-click shortcuts to the publisher's curated pre-market sections
    # for cases when the user wants the full editorial article.
    st.markdown(
        '<div style="display:flex;gap:10px;align-items:center;margin:0 0 10px 0;'
        'padding:6px 12px;background:rgba(20,30,48,0.3);border-radius:6px;'
        'font-family:JetBrains Mono,monospace;font-size:0.7rem">'
        '<span style="color:var(--ink);letter-spacing:1px">EXTERNAL ANALYSIS</span>'
        '<a href="https://economictimes.indiatimes.com/markets/pre-open-market" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET · Pre-Open Market →</a>'
        '<a href="https://economictimes.indiatimes.com/prime/markets" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET Prime · Markets →</a>'
        '<a href="https://www.moneycontrol.com/markets/indian-indices/" target="_blank" '
        'style="color:var(--acc);text-decoration:none;font-weight:600">MC · Indices →</a>'
        '<a href="https://www.moneycontrol.com/news/business/markets/" target="_blank" '
        'style="color:var(--acc);text-decoration:none;font-weight:600">MC Pro · Markets →</a>'
        '</div>', unsafe_allow_html=True
    )

    st.markdown("---")
    _pm1, _pm2, _pm3, _pm4, _pm5 = st.tabs([
        "📋 Brief", "🌍 Global", "📅 Calendar", "📐 Options", "💎 ET + MC Pro"
    ])

    with _pm1:
        section("AI Pre-Market Brief — Full Report")
        st.caption(
            "Canonical location for the daily AI briefing (single source of truth). "
            "Generated 8:30 AM IST automatically by the scheduler, or click **Refresh Now** to force. "
            "A 300-word snippet of this report is mirrored on **📊 DASHBOARD** for quick context "
            "the moment you land there."
        )
        _brief_text = _latest_pm.get("text")
        if _brief_text:
            _render_ai_report(_brief_text, header_color="var(--acc)")
        else:
            st.info("No pre-market report yet. Click **Refresh Now** to generate one.")
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Now", key="pm_gen_now", type="primary"):
                    with st.spinner("Generating AI pre-market brief..."):
                        try:
                            snap = build_premarket_snapshot()
                            brief = generate_premarket_brief(snap)
                            _render_ai_report(brief, header_color="var(--acc)")
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    with _pm2:
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
                            _col  = "var(--bull)" if _chg >= 0 else "var(--bear)"
                            _arrow= "▲" if _chg >= 0 else "▼"
                            st.markdown(f"""
                            <div style="display:flex;justify-content:space-between;align-items:center;
                                        padding:5px 0;border-bottom:1px solid var(--rule);">
                              <span style="font-family:'Inter',sans-serif;font-size:0.82rem;color:var(--ink);">{_name}</span>
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
                        _col = "var(--bull)" if _chg >= 0 else "var(--bear)"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--rule);">
                          <span style="font-size:0.82rem;color:var(--ink);">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.2f} ({'+' if _chg>=0 else ''}{_chg:.1f}%)</span>
                        </div>""", unsafe_allow_html=True)

                with _cc2:
                    section("Currencies & Bonds")
                    for _name, _dat in {**_currs, **_bonds}.items():
                        if not _dat: continue
                        _chg = _dat.get("change_pct", 0) or 0
                        _ltp = _dat.get("ltp", 0) or 0
                        _col = "var(--bull)" if _chg >= 0 else "var(--bear)"
                        if _name == "USD/INR": _col = "var(--bear)" if _chg > 0 else "var(--bull)"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--rule);">
                          <span style="font-size:0.82rem;color:var(--ink);">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.4f} ({'+' if _chg>=0 else ''}{_chg:.2f}%)</span>
                        </div>""", unsafe_allow_html=True)

    with _pm3:
        section("Economic & Events Calendar")
        if _HUB_OK:
            # Inline "Fetch Live" button — calls investing.com (country=India,
            # timezone=IST) and rewrites economic_calendar.json with current
            # events + Previous/Forecast/Actual where available. The page-level
            # "Refresh Now" button now also runs this fetcher.
            _cal_btn_col, _cal_meta_col = st.columns([1, 5])
            with _cal_btn_col:
                if st.button("🔄 Fetch Live", key="cal_fetch_live", type="primary"):
                    try:
                        from market_data_hub import refresh_calendar_from_investing
                        with st.spinner("Pulling India events from investing.com…"):
                            _r = refresh_calendar_from_investing(days_ahead=14)
                        if _r.get("error"):
                            st.error(f"Fetch failed: {_r['error']}")
                        else:
                            st.toast(f"✅ Calendar refreshed — {_r['count']} events written",
                                     icon="📅")
                            st.rerun()
                    except Exception as _ce:
                        st.error(f"Refresh error: {_ce}")
            with _cal_meta_col:
                st.caption("Source: investing.com/economic-calendar · country=India · timezone=IST")

            try:
                # B13: surface staleness so users know the file is user-maintained
                try:
                    from market_data_hub import get_economic_calendar_status
                    _cal_status = get_economic_calendar_status()
                except Exception:
                    _cal_status = {"exists": False, "stale": True}
                if not _cal_status.get("exists"):
                    st.warning(
                        "📅 No `economic_calendar.json` found — the calendar is now "
                        "user-maintained (B13). Run "
                        "`python -c \"import market_data_hub; market_data_hub.seed_economic_calendar()\"` "
                        "to create a starter file, then edit the events list."
                    )
                elif _cal_status.get("stale"):
                    _age = _cal_status.get("age_days")
                    st.warning(
                        f"📅 Calendar last updated **{_cal_status.get('last_updated')}** "
                        f"({_age}d ago). Dates older than 30 days may be inaccurate — "
                        f"refresh `economic_calendar.json` and bump `last_updated`."
                    )
                else:
                    st.caption(
                        f"📅 Updated {_cal_status.get('last_updated')} · "
                        f"{_cal_status.get('future_count', 0)} upcoming · "
                        f"{_cal_status.get('event_count', 0)} total events"
                    )
                _cal = fetch_economic_calendar()
                if _cal:
                    _df_cal = pd.DataFrame(_cal)
                    _df_cal["date"] = pd.to_datetime(_df_cal["date"])
                    _df_cal = _df_cal.sort_values("date")

                    def _imp_color(imp):
                        return "var(--bear)" if imp=="HIGH" else "var(--warn)" if imp=="MEDIUM" else "var(--ink-2)"

                    _cal_cols = st.columns([1,3,1,1,1,1], gap="small")
                    for _h, _c in zip(["Date","Event","Importance","Previous","Forecast","Actual"], _cal_cols):
                        _c.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:var(--ink);letter-spacing:2px;text-transform:uppercase;">{_h}</div>', unsafe_allow_html=True)
                    st.markdown('<div style="border-bottom:1px solid var(--rule);margin:4px 0 8px 0;"></div>', unsafe_allow_html=True)

                    for _, _row in _df_cal.iterrows():
                        _c1,_c2,_c3,_c4,_c5,_c6 = st.columns([1,3,1,1,1,1], gap="small")
                        _c1.markdown(f'<div style="font-size:0.78rem;color:var(--muted);">{_row["date"].strftime("%d %b")}</div>', unsafe_allow_html=True)
                        _c2.markdown(f'<div style="font-size:0.82rem;color:var(--ink);">{_row.get("event","")}</div>', unsafe_allow_html=True)
                        _imp = _row.get("importance","")
                        _c3.markdown(f'<div style="font-size:0.78rem;font-weight:600;color:{_imp_color(_imp)};">{_imp}</div>', unsafe_allow_html=True)
                        _c4.markdown(f'<div style="font-size:0.78rem;color:var(--muted);">{_row.get("previous","–")}</div>', unsafe_allow_html=True)
                        _c5.markdown(f'<div style="font-size:0.78rem;color:var(--muted);">{_row.get("forecast","–")}</div>', unsafe_allow_html=True)
                        _act = _row.get("actual","")
                        _act_col = "var(--ink-2)" if _act else "var(--faint)"
                        _c6.markdown(f'<div style="font-size:0.78rem;color:{_act_col};font-weight:{'700' if _act else '500'};">{_act if _act else "Pending"}</div>', unsafe_allow_html=True)
                else:
                    st.info("No calendar events available.")
            except Exception as _e:
                st.error(f"Calendar fetch error: {_e}")
        else:
            st.warning("market_data_hub not available.")

    with _pm4:
        section("Pre-Market Options Snapshot — Nifty")
        if _HUB_OK:
            try:
                _opts = fetch_nse_options_summary("NIFTY")

                # ── Determine display state ─────────────────────────────────
                _is_closed = _opts.get("_market_closed", False)
                _src       = _opts.get("_source", "live")
                _has_data  = bool(_opts.get("spot_price"))
                _msg       = _opts.get("_message", "")

                # ── Off-hours / fallback banner ─────────────────────────────
                if _is_closed and _has_data:
                    _cached_at = _opts.get("_cached_at_utc", "")
                    try:
                        _ca = datetime.fromisoformat(_cached_at.replace("Z", "+00:00"))
                        _ca_ist = _ca + timedelta(hours=5, minutes=30)
                        _ca_str = _ca_ist.strftime("%a %d %b %H:%M IST")
                    except Exception:
                        _ca_str = "earlier session"
                    st.info(
                        f"📁 **Showing last cached snapshot from {_ca_str}.** "
                        f"NSE markets are closed (weekend / outside 09:15–15:30 IST). "
                        f"Live data resumes next trading session."
                    )
                elif _is_closed and not _has_data:
                    st.warning(
                        "🕒 **NSE markets are closed and no cached snapshot exists yet.** "
                        "Open this tab during the next trading session (09:15–15:30 IST Mon–Fri) "
                        "to fetch and cache the first snapshot. After that, off-hours visits will "
                        "show the last good snapshot here."
                    )
                elif not _has_data and _msg:
                    st.warning(f"⚠️ {_msg}")
                elif "disk-cache (live error" in _src:
                    st.warning(
                        f"📁 Live fetch failed; showing last good cached snapshot. "
                        f"({_src})"
                    )

                if _has_data:
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
                    if _pcr > 1.2:   _pcr_sig, _pcr_col = "🟢 BULLISH — heavy Put writing (market supported)", "var(--bull)"
                    elif _pcr < 0.7: _pcr_sig, _pcr_col = "🔴 BEARISH — heavy Call writing (market capped)", "var(--bear)"
                    else:            _pcr_sig, _pcr_col = "🟡 NEUTRAL — balanced positioning", "var(--warn)"
                    st.markdown(f'<div class="metric-card" style="margin-top:12px;">'
                                f'<div class="metric-label">PCR Signal</div>'
                                f'<div class="metric-value" style="color:{_pcr_col};font-size:0.88rem;">{_pcr_sig}</div>'
                                f'<div style="font-size:0.55rem;color:var(--ink);margin-top:4px;">Source: {_src} · As of: {_opts.get("fetched_at","–")}</div>'
                                f'</div>', unsafe_allow_html=True)
            except Exception as _e:
                st.warning(f"Options data unavailable: {_e}")
        else:
            st.warning("market_data_hub not available.")

    with _pm5:
        section("Pre-Market — ET Prime + Moneycontrol Pro")
        # Filter to pre-market / opening / overnight / GIFT Nifty themed items.
        # Loose, case-insensitive substring match — captures ET/MC pre-market
        # columns ("Stocks to watch", "Trade Setup", "Bulls Vs Bears", "GIFT Nifty
        # signals", "Opening Bell", etc.).
        _PM_KWS = [
            "pre-market", "premarket", "pre market",
            "stocks to watch", "stocks in focus", "trade setup", "trade idea",
            "opening bell", "gift nifty", "overnight", "morning brief",
            "f&o", "pre-open", "buy or sell", "stocks to buy",
            "bulls vs bears",
        ]
        _render_paid_news_grid(
            key_prefix="pm_paid",
            keyword_filter=_PM_KWS,
            default_limit=50,
            show_recos_only=False,
            caption=("Filtered to pre-market / opening / overnight headlines from your "
                     "ET Prime + MC Pro subscriptions. Use the **Source** dropdown to "
                     "isolate one outlet. Cards link out to the full article."),
        )
