# commander_pages/ai_lab.py - the AI LAB page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('ai_lab', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🧠 AI Laboratory</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Advanced Generative AI workflows and automation.</div>', unsafe_allow_html=True)
    _ai1, _ai2, _ai3, _ai4 = st.tabs(["🛫 Pre-Flight", "🤖 Generative", "⚙️ Workflows", "📆 Weekly Report"])

    with _ai1:
        section("AI-Trade Proposer — Pre-flight Check")
        p1, p2, p3 = st.columns([2,1,1], gap="small")
        with p1: prop_sym   = st.text_input("Ticker Symbol", key="prop_sym", placeholder="e.g. RELIANCE").upper()
        with p2: prop_entry = st.number_input("Entry Price", min_value=0.0, step=0.1, key="prop_entry")
        # House risk in rupees (25-Sep-2026) - was a flat ₹5,000 (~0.17% of ₹30L), a fifth
        # sizing rule. Now declared capital x house_policy.risk_pct_for(symbol).
        _pp_cap = _HP.sizing_capital()[0]
        prop_risk = (_pp_cap * _HP.risk_pct_for(prop_sym or "") / 100.0) if _pp_cap == _pp_cap else 0.0
        with p3: st.metric("Risk ₹", format_inr_int(prop_risk) if prop_risk else "capital unset",
                           help=f"House rule {_HP.risk_label()} of the declared capital (GM settings).")

        if st.button("🛫  Run Analysis\nScore and size a new trade before execution.\n→  Analyse Now", type="primary", use_container_width=True, key="btn_analysis"):
            if not prop_sym:
                st.error("Enter ticker.")
            else:
                with st.spinner(f"Analyzing {prop_sym}..."):
                    try:
                        ticker_yf = yf_symbol(prop_sym)   # BUG-15: centralised mapper
                        hist = yf.Ticker(ticker_yf).history(period="1mo")
                        ltp_val = float(hist['Close'].iloc[-1]) if not hist.empty else prop_entry

                        prop_sector  = get_sector(prop_sym)   # BUG-15: top-level import
                        rating_res   = get_weinstein_score(symbol=prop_sym, sector=prop_sector,
                                                           ltp=ltp_val, buy_price=prop_entry)
                        # The GM/S4 stop ladder (AUD-INT-12), not an ADR multiple, and no
                        # invented 5% fallback: no stop means no size.
                        suggested_sl, _sl_src = _house_initial_stop(prop_sym, prop_entry) if prop_entry > 0 else (None, "enter a price")
                        if not suggested_sl:
                            st.error(f"No stop: {_sl_src}. Sizing needs a stop below entry.")
                            suggested_sl = 0.0
                        else:
                            st.caption(f"Stop basis: {_sl_src}")

                        risk_per_share = (prop_entry - suggested_sl) if suggested_sl else 0.0
                        # FORM-03 FIX: risk % is of total_cap, not just available cash
                        qty = int(prop_risk / risk_per_share) if risk_per_share > 0 else 0
                        if prop_entry > 0:
                            qty = min(qty, int(_HP.max_alloc() // prop_entry))   # per-trade ₹ cap

                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Weinstein Grade", rating_res.get('rating', 'N/A'))
                        r2.metric("Quant Score",     f"{rating_res.get('quant_score', 0)}/100")
                        r3.metric("Suggested SL",    f"₹{format_inr(suggested_sl)}")
                        r4.metric("Rec. Quantity",   f"{qty} shares")
                        st.info(f"AI Rationale: {rating_res.get('reason','N/A')}")

                        breakdown = rating_res.get('breakdown', {})
                        if breakdown:
                            with st.expander("📊 Quant Scorecard Breakdown", expanded=True):
                                for factor, detail in breakdown.items():
                                    st.caption(f"**{factor}:** {detail}")

                        # MISS-8: store pre-flight results in session for atomic GTT workflow
                        st.session_state["preflight_sym"]  = prop_sym
                        st.session_state["preflight_entry"] = prop_entry
                        st.session_state["preflight_sl"]    = round(suggested_sl, 2)
                        st.session_state["preflight_qty"]   = qty
                    except Exception as e:
                        st.error(f"Analysis error: {e}")

        # MISS-8: Atomic Entry + GTT-SL workflow ─────────────────────────────
        if st.session_state.get("preflight_sym"):
            st.markdown("---")
            section("MISS-8 · Atomic Entry + GTT Stop-Loss")
            st.caption(
                "Once you are satisfied with the Pre-Flight analysis, use the buttons below "
                "to place the entry order AND set up the GTT stop-loss in one workflow. "
                "**Review all values before submitting.**"
            )
            _pf_sym   = st.session_state.get("preflight_sym", "")
            _pf_entry = st.session_state.get("preflight_entry", 0.0)
            _pf_sl    = st.session_state.get("preflight_sl", 0.0)
            _pf_qty   = st.session_state.get("preflight_qty", 0)

            _af1, _af2, _af3, _af4 = st.columns(4, gap="small")
            _af1.metric("Symbol",  _pf_sym)
            _af2.metric("Entry",   f"₹{format_inr(_pf_entry)}")
            _af3.metric("SL",      f"₹{format_inr(_pf_sl)}")
            _af4.metric("Qty",     str(_pf_qty))

            _at1, _at2 = st.columns(2, gap="small")
            with _at1:
                if st.button(
                    f"🎯  Place Entry Order — {_pf_sym}\n"
                    f"Buy {_pf_qty} shares at ₹{_pf_entry:.2f}\n→  Confirm & Place",
                    use_container_width=True, key="preflight_entry_btn", type="primary"
                ):
                    # Route to the SNIPER tab in the web interface
                    st.info(
                        f"ℹ️ Navigate to **AI LAB → Sniper Entry** tab to place order for "
                        f"{_pf_sym}. Values pre-populated: Entry={_pf_entry}, "
                        f"Qty={_pf_qty}, SL={_pf_sl}"
                    )
            with _at2:
                if st.button(
                    f"🛡️  Set GTT Stop-Loss — {_pf_sym}\n"
                    f"GTT trigger at ₹{_pf_sl:.2f}\n→  Launch GTT Shield",
                    use_container_width=True, key="preflight_gtt_btn"
                ):
                    launch_script("gtt_auto_shield.py",
                                  f"--symbol {_pf_sym} --sl {_pf_sl} --qty {_pf_qty}")

    with _ai2:
        _g1, _g2 = st.tabs(["📈 Stock Analysis", "🔬 Portfolio Review"])

        # ── Stock Analysis ────────────────────────────────────────────────────
        with _g1:
            section("Gemini AI Stock Analysis")
            _ga_c1, _ga_c2, _ga_c3 = st.columns([2, 1, 1], gap="small")
            with _ga_c1:
                _ga_sym = st.text_input("NSE Symbol", placeholder="e.g. RELIANCE, INFY",
                                        key="ga_sym").strip().upper()
            with _ga_c2:
                _ga_depth = st.selectbox("Report depth", ["Quick (100w)", "Full (250w)", "Trade Setup"],
                                         key="ga_depth")
            with _ga_c3:
                _ga_entry = st.number_input("Entry price (optional)", min_value=0.0, step=0.5,
                                            key="ga_entry", help="Leave 0 to skip trade setup calc")

            if st.button("🤖 Generate AI Analysis", key="ga_run", type="primary",
                         use_container_width=True):
                if not _ga_sym:
                    st.warning("Enter a symbol first.")
                elif not _GEMINI_OK:
                    st.error("❌ Gemini reporter module not available.")
                else:
                    with st.spinner(f"Collecting data for {_ga_sym} and generating analysis…"):
                        try:
                            _ga_yf_sym = _ga_sym if _ga_sym.endswith(".NS") else _ga_sym + ".NS"
                            _ga_tk = yf.Ticker(_ga_yf_sym)
                            _ga_hist = _ga_tk.history(period="6mo")
                            _ga_info = _ga_tk.info

                            # Technical levels
                            _ga_close = _ga_hist["Close"].dropna()
                            _ga_ltp   = float(_ga_close.iloc[-1]) if not _ga_close.empty else 0.0
                            _ga_data  = {
                                "symbol":     _ga_sym,
                                "ltp":        round(_ga_ltp, 2),
                                "entry_price": _ga_entry if _ga_entry > 0 else None,
                                "week_52_high": round(float(_ga_close.tail(252).max()), 2) if len(_ga_close) >= 20 else None,
                                "week_52_low":  round(float(_ga_close.tail(252).min()), 2) if len(_ga_close) >= 20 else None,
                                "sma_20":  round(float(_ga_close.rolling(20).mean().iloc[-1]), 2) if len(_ga_close) >= 20 else None,
                                "sma_50":  round(float(_ga_close.rolling(50).mean().iloc[-1]), 2) if len(_ga_close) >= 50 else None,
                                "sma_200": round(float(_ga_close.rolling(200).mean().iloc[-1]), 2) if len(_ga_close) >= 200 else None,
                                "above_sma50":  _ga_ltp > float(_ga_close.rolling(50).mean().iloc[-1]) if len(_ga_close) >= 50 else None,
                                "above_sma200": _ga_ltp > float(_ga_close.rolling(200).mean().iloc[-1]) if len(_ga_close) >= 200 else None,
                                # Fundamentals from yfinance
                                "sector":       _ga_info.get("sector", ""),
                                "industry":     _ga_info.get("industry", ""),
                                "market_cap_cr": round(_ga_info.get("marketCap", 0) / 1e7, 0) if _ga_info.get("marketCap") else None,
                                "pe_ratio":     _ga_info.get("trailingPE"),
                                "pb_ratio":     _ga_info.get("priceToBook"),
                                "roe_pct":      round(_ga_info.get("returnOnEquity", 0) * 100, 1) if _ga_info.get("returnOnEquity") else None,
                                "debt_equity":  _ga_info.get("debtToEquity"),
                                "revenue_growth": round(_ga_info.get("revenueGrowth", 0) * 100, 1) if _ga_info.get("revenueGrowth") else None,
                                "earnings_growth": round(_ga_info.get("earningsGrowth", 0) * 100, 1) if _ga_info.get("earningsGrowth") else None,
                                "analyst_target": _ga_info.get("targetMeanPrice"),
                                "recommendation": _ga_info.get("recommendationKey", ""),
                                # Market context
                                "breadth_regime": st.session_state.get("cached_breadth_regime", "unknown"),
                            }

                            # Recent news headlines (top 3)
                            if _NEWS_OK:
                                try:
                                    _ga_news_df = fetch_all_news(max_per_feed=5, hours_back=48)
                                    _ga_news_df = add_sentiment(_ga_news_df)
                                    _ga_sym_news = filter_by_symbol(_ga_news_df, _ga_sym)
                                    if not _ga_sym_news.empty:
                                        _ga_data["recent_news"] = _ga_sym_news[["title","sentiment"]].head(3).to_dict(orient="records")
                                except Exception:
                                    pass

                            # Adjust prompt depth
                            _depth_map = {
                                "Quick (100w)": 100, "Full (250w)": 250, "Trade Setup": 250
                            }
                            _word_limit = _depth_map.get(_ga_depth, 250)
                            if _ga_depth == "Trade Setup" and _ga_entry > 0:
                                _ga_data["analysis_focus"] = "trade_setup"
                                _ga_data["risk_reward_required"] = True

                            # Not in the top-level gemini_reporter import list — import
                            # locally, same as the Fundamentals card at ~:11565.
                            from gemini_reporter import generate_stock_analysis
                            _ga_report = generate_stock_analysis(_ga_sym, _ga_data)
                            st.session_state["ga_last_report"] = _ga_report
                            st.session_state["ga_last_sym"]    = _ga_sym
                        except Exception as _ga_e:
                            st.error(f"Analysis failed: {_ga_e}")

            # ── Display last report ──────────────────────────────────────────
            if st.session_state.get("ga_last_report"):
                _ga_disp_sym = st.session_state.get("ga_last_sym", "")
                st.markdown("---")
                _ltp_disp = ""
                try:
                    # C1 sweep: cached latest_close
                    try:
                        import data_provider as _dp_ga
                        _ltp_v = _dp_ga.latest_close(_ga_disp_sym)
                    except Exception:
                        _ltp_v = float(yf.Ticker(_ga_disp_sym+'.NS' if not _ga_disp_sym.endswith('.NS') else _ga_disp_sym).fast_info.get('lastPrice', 0))
                    _ltp_disp = f" — ₹{_ltp_v:,.2f}"
                except Exception:
                    pass
                section(f"AI Analysis: {_ga_disp_sym}{_ltp_disp}")
                _render_ai_report(st.session_state["ga_last_report"], header_color="var(--acc)")

                # Download button
                st.download_button(
                    "📥 Download Report (.txt)",
                    data=st.session_state["ga_last_report"],
                    file_name=f"AI_Analysis_{_ga_disp_sym}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain", key="ga_dl",
                )

        # ── Portfolio Review ──────────────────────────────────────────────────
        with _g2:
            section("AI Portfolio Review — Closed Trades")
            if not _GEMINI_OK:
                st.error("❌ Gemini module unavailable.")
            else:
                _pr_df = load_closed_trades_db()
                if _pr_df is None or _pr_df.empty:
                    st.info("No closed trades found. Complete trades via the Journal to unlock AI review.")
                else:
                    for _c in ["ExitPrice","BuyPrice","Quantity"]:
                        _pr_df[_c] = pd.to_numeric(_pr_df.get(_c,0), errors="coerce").fillna(0)
                    _pr_df["PnL"] = (_pr_df["ExitPrice"] - _pr_df["BuyPrice"]) * _pr_df["Quantity"]
                    _pr_analytics = compute_portfolio_analytics(_pr_df, app_state.total_cap)
                    st.caption(f"{len(_pr_df)} closed trades loaded  |  "
                               f"Win rate {_pr_analytics.get('win_rate',0)}%  |  "
                               f"Profit Factor {_pr_analytics.get('profit_factor',0)}")
                    if st.button("🔬 Generate AI Portfolio Review", key="pr_run", type="primary",
                                 use_container_width=True):
                        with st.spinner("Generating Gemini portfolio review…"):
                            try:
                                _pr_report = generate_portfolio_review(_pr_df, _pr_analytics)
                                st.session_state["pr_last_report"] = _pr_report
                            except Exception as _pre:
                                st.error(f"Review failed: {_pre}")

                    if st.session_state.get("pr_last_report"):
                        st.markdown("---")
                        _render_ai_report(st.session_state["pr_last_report"], header_color="var(--warn)")
                        st.download_button(
                            "📥 Download Review (.txt)",
                            data=st.session_state["pr_last_report"],
                            file_name=f"Portfolio_Review_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain", key="pr_dl",
                        )

        # ── Cache management ─────────────────────────────────────────────────
        st.markdown("---")
        _cache_col1, _cache_col2 = st.columns(2, gap="small")
        with _cache_col1:
            if st.button("🗑️ Clear AI Cache", use_container_width=True, key="ai_cache"):
                _ai_cache_path = os.path.join(_APP_DIR, "ai_cache.json")
                if os.path.exists(_ai_cache_path):
                    os.remove(_ai_cache_path); st.success("AI Cache Cleared!")
                else:
                    st.info("Cache already empty.")
        with _cache_col2:
            if st.button("🗑️ Clear News Cache", use_container_width=True, key="ai_news_cache"):
                _nc = os.path.join(_APP_DIR, "reports", "news_cache.json")
                if os.path.exists(_nc):
                    os.remove(_nc); st.success("News Cache Cleared!")
                else:
                    st.info("News cache already empty.")

    with _ai3:
        section("Workflow Automation — Inline Pipeline")
        if st.button("🤖  Run Full Auto-Pilot\nExecute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync.\n→  Initiate", type="primary", use_container_width=True, key="wf_run"):
            import time as _time
            import subprocess as _sp
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            phases = [
                ("Phase 1/8: Technical Scanners — Stage 2 + Recovery (Chartink)", "chartink_scanner_pro", "run_scan"),
                ("Phase 2/8: Fetching Fundamental Data",      "screener_fetcher",     "fetch_screener_data"),
                ("Phase 3/8: Processing HTML to CSV",         "screener_processor",   "process_screener_pages"),
                ("Phase 4/8: Golden Matcher",                  "brute_force_match_pro","perform_match"),
                ("Phase 5/8: Recovery Screener (Python)",      "recovery_screener",    "main"),
                ("Phase 6/8: Generating Watchlists",           "watchlist_manager",    "generate_tradingview_files"),
                ("Phase 7/8: Syncing to RRG Studio",           "commander_watchlists", "sync"),
                ("Phase 8/8: Syncing to TradingView",          "_subprocess",          "tradingview_automation_v2.py --pipeline"),
            ]
            progress_bar = st.progress(0, text="Initializing Auto-Pilot...")
            results_log  = []
            for i, (label, module_name, func_name) in enumerate(phases):
                progress_bar.progress(i / len(phases), text=f"⏳ {label}")
                try:
                    if module_name == "_subprocess":
                        # Run platform-sync scripts the same way run_pipeline.py does
                        parts = func_name.split()
                        _sp.run([_PYTHON_EXE, parts[0]] + parts[1:],
                                check=True, cwd=_script_dir, timeout=180)
                    else:
                        # BUG-M4: importlib.reload() can silently execute stale byte-code.
                        # Use sys.modules eviction so re-import always reads .py from disk.
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                        importlib.invalidate_caches()
                        mod = importlib.import_module(module_name)
                        fn = getattr(mod, func_name)
                        if module_name == "chartink_scanner_pro":
                            for scan_key in ['1','2','3','4','5','6','7']:
                                fn(scan_key); _time.sleep(0.5)
                        elif module_name == "screener_fetcher":  fn(interactive=False)
                        elif module_name == "brute_force_match_pro": fn(return_raw=True)
                        elif module_name == "watchlist_manager": fn(silent=True)
                        elif module_name == "recovery_screener":
                            fn()   # BUG-C2: recovery_screener.main() no longer calls os.chdir()
                        else: fn()
                    results_log.append(f"✅ {label}")
                except Exception as e:
                    results_log.append(f"❌ {label}: {e}")
                progress_bar.progress((i+1) / len(phases), text=f"✅ {label}")
            progress_bar.progress(1.0, text="✅ Pipeline Complete!")
            st.success("🏁 Full Auto-Pilot Complete!")
            # REC-6: wrap verbose phase logs in expander so the page stays clean
            with st.expander("📋 Phase-by-Phase Log", expanded=False):
                for log in results_log:
                    st.caption(log)

        st.markdown("---")
        section("Sniper Entry — Web Interface")
        sub_label("🎯  Advanced Position Size Calculator & Order Entry")

        if "prev_sniper_sym" not in st.session_state:
            st.session_state.prev_sniper_sym = ""

        s1, s2 = st.columns([2, 2], gap="small")
        with s1:
            sniper_sym_input = st.text_input("Stock Symbol", placeholder="e.g. CHOLAFIN").upper().strip()

        if sniper_sym_input != st.session_state.prev_sniper_sym and sniper_sym_input:
            st.session_state.prev_sniper_sym = sniper_sym_input
            try:
                atr_val = get_atr(sniper_sym_input)
                # C1 sweep: cached latest_close (5-day window)
                try:
                    import data_provider as _dp_sn
                    ltp = _dp_sn.latest_close(sniper_sym_input)
                except Exception:
                    info    = yf.Ticker(yf_symbol(sniper_sym_input)).fast_info
                    ltp     = info.get("lastPrice", 0.0)
                if ltp > 0:
                    st.session_state.sniper_entry = round(ltp, 2)
                    # Default stop = the GM/S4 ladder (AUD-INT-12), was ltp - 2xATR.
                    _sn_sl, _sn_src = _house_initial_stop(sniper_sym_input, ltp)
                    st.session_state.sniper_sl    = round(_sn_sl, 2) if _sn_sl else 0.0
                    st.session_state.sniper_sl_src = _sn_src
                else:
                    st.session_state.sniper_entry = 0.0
                    st.session_state.sniper_sl    = 0.0
            except Exception: pass

        c1, c2, c3 = st.columns([1,1,1], gap="small")
        with c1: sniper_entry = st.number_input("Entry Price ₹", min_value=0.0, step=0.1, key="sniper_entry")
        with c2: sniper_sl    = st.number_input("Stop Loss ₹",   min_value=0.0, step=0.1, key="sniper_sl",
                                                help="Pre-filled from the GM/S4 stop ladder: "
                                                     + str(st.session_state.get("sniper_sl_src", "—")))
        # House risk, not a slider (25-Sep-2026): this defaulted to 1% on the TOTAL-equity
        # base with a 20% cap, while every other sizer used 0.5% / 0.75% on the declared
        # capital with the ₹ cap. One rule now, from house_policy.
        risk_pct = _HP.risk_pct_for(sniper_sym_input or "")
        _sn_cap, _sn_src = _HP.sizing_capital()
        with c3: st.metric("House risk", f"{risk_pct:g}%",
                           help=f"house_policy.py — {_HP.risk_label()}. Capital: "
                                f"{('₹' + format_inr_int(_sn_cap)) if _sn_cap == _sn_cap else 'NOT SET'} ({_sn_src}).")

        if sniper_sym_input and sniper_entry > 0 and sniper_sl > 0 and sniper_entry > sniper_sl:
            risk_per_share = sniper_entry - sniper_sl
            risk_pct_of_entry = (risk_per_share / sniper_entry) * 100
            # Sizing base = the declared capital (house_policy.sizing_capital); the cap is the
            # per-trade ₹ cap. No capital declared → no quantity, never an invented base.
            _sn_base = _sn_cap if _sn_cap == _sn_cap else 0.0
            if not _sn_base:
                st.error("Set Capital in the Golden Matcher settings — sizing refuses to invent a capital base.")
            max_risk_rupees  = _sn_base * (risk_pct / 100.0)
            sniper_qty       = math.floor(max_risk_rupees / risk_per_share) if risk_per_share > 0 else 0

            max_cap_allowed = _HP.max_alloc()
            capped_reason   = ""
            if sniper_qty * sniper_entry > max_cap_allowed:
                sniper_qty    = math.floor(max_cap_allowed / sniper_entry)
                capped_reason = f"Capped at the per-trade limit ₹{format_inr_int(max_cap_allowed)}"

            trade_value = sniper_qty * sniper_entry
            target_2r   = sniper_entry + (risk_per_share * 2)
            target_3r   = sniper_entry + (risk_per_share * 3)

            if capped_reason: st.info(f"💡 **Position Adjusted**: {capped_reason}")

            q1,q2,q3,q4 = st.columns(4)
            q1.metric("Quantity",    f"{sniper_qty} shares")
            q2.metric("Trade Value", f"₹{format_inr_int(trade_value)}")
            q3.metric("Risk/Trade",  f"₹{format_inr_int(max_risk_rupees)}")
            q4.metric("Risk %",      f"{risk_pct_of_entry:.1f}%")
            t1,t2 = st.columns(2)
            t1.metric("Target 2R", f"₹{format_inr(target_2r)}")
            t2.metric("Target 3R", f"₹{format_inr(target_3r)}")

            if st.button("🚀  Execute CNC Order via Dhan", type="primary", use_container_width=True, key="sniper_exec"):
                try:
                    from dhan_symbols import get_nse_id_map
                    id_map = get_nse_id_map()
                    sec_id = id_map.get(sniper_sym_input)
                    if not sec_id:
                        st.error(f"❌ Symbol '{sniper_sym_input}' not found in NSE master.")
                    else:
                        dhan_exec, _ = get_dhanhq_client()
                        if not dhan_exec:
                            st.error("❌ Dhan Auth Failed")
                            st.stop()
                        now        = datetime.now()
                        mkt_open   = now.replace(hour=9,  minute=15, second=0, microsecond=0)
                        mkt_close  = now.replace(hour=15, minute=30, second=0, microsecond=0)
                        # REC-7: Indian market holiday awareness
                        # NSE public holidays 2026 (update annually or fetch from API)
                        _NSE_HOLIDAYS_2026 = {
                            (2026, 1, 26),  # Republic Day
                            (2026, 3, 25),  # Holi
                            (2026, 4, 14),  # Dr. Ambedkar Jayanti / Ram Navami
                            (2026, 4, 17),  # Good Friday
                            (2026, 5, 1),   # Maharashtra Day
                            (2026, 8, 15),  # Independence Day
                            (2026, 10, 2),  # Gandhi Jayanti
                            (2026, 11, 14), # Diwali Laxmi Pujan (check BSE circular)
                            (2026, 12, 25), # Christmas
                        }
                        _today_tuple = (now.year, now.month, now.day)
                        _is_holiday  = _today_tuple in _NSE_HOLIDAYS_2026
                        is_amo = not (mkt_open <= now <= mkt_close and now.weekday() < 5 and not _is_holiday)
                        if _is_holiday:
                            st.info(f"ℹ️ Today is an NSE market holiday — order will be placed as AMO.")
                        # PRE-TRADE RISK GATE (26-Jul-2026, audit P0). This button
                        # placed live orders with none of the checks sniper_trigger.py
                        # enforces. Both entry and SL are known here, so all three caps
                        # apply (max open positions / sector / per-trade risk-%).
                        # Fail-closed: an unevaluable gate blocks the order.
                        from pre_trade_gate import gate_order
                        _gok, _greason = gate_order(
                            dhan_exec, sniper_sym_input, "BUY", sniper_qty,
                            entry_price=sniper_entry, sl_price=sniper_sl)
                        if not _gok:
                            st.error(f"🛡️ BLOCKED by pre-trade risk gate — {_greason}")
                            st.caption("No order was placed. Adjust size/stop, or resolve "
                                       "the portfolio breach, then retry.")
                            st.stop()
                        st.caption(f"🛡️ Risk gate passed — {_greason}")
                        order = dhan_exec.place_order(
                            security_id=sec_id, exchange_segment=dhan_exec.NSE,
                            transaction_type=dhan_exec.BUY, quantity=sniper_qty,
                            order_type=dhan_exec.LIMIT, product_type=dhan_exec.CNC,
                            price=sniper_entry, after_market_order=is_amo,
                            trading_symbol=sniper_sym_input
                        )
                        if order.get('status') == 'success':
                            st.success(f"✅ Order Placed! ID: {order['data']['orderId']}")
                            st.toast(f"🎯 {sniper_sym_input} order placed successfully!")
                        else:
                            st.error(f"❌ Order Failed: {order.get('remarks','Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Execution Error: {e}")
        elif sniper_sym_input and sniper_entry > 0 and sniper_sl > 0:
            st.warning("⚠️ Entry Price must be higher than Stop Loss for a new Long trade.")

    with _ai4:
        # ── WEEKLY REPORT ─────────────────────────────────────────────────────
        section("📆 Weekly Market Report")
        st.caption(
            "Comprehensive Sunday evening market letter — 500-600 words covering "
            "index moves, breadth, sector rotation, FII/DII flows, and setups for next week. "
            "The scheduler auto-generates and Telegrams this report every Sunday at 7:00 PM IST. "
            "Use the button below to generate on demand at any time."
        )

        # ── Generate on demand ────────────────────────────────────────────────
        _wr_gen_col1, _wr_gen_col2 = st.columns([2, 1])
        with _wr_gen_col1:
            st.markdown(
                "**Generate a fresh report** using live data — fetches market snapshot, "
                "breadth metrics, FII/DII flows, and sector data, then calls Gemini AI."
            )
        with _wr_gen_col2:
            _wr_generate = st.button(
                "🤖 Generate Weekly Report", type="primary",
                key="gen_weekly_report", use_container_width=True
            )

        st.markdown("---")

        # ── Show cached report if available ──────────────────────────────────
        _wr_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        _wr_file = os.path.join(_wr_dir, "weekly_report.txt")
        _wr_json = os.path.join(_wr_dir, "weekly_report.json")

        _wr_cached_text = None
        _wr_cached_meta = {}
        if os.path.exists(_wr_file):
            try:
                _wr_cached_text = open(_wr_file, encoding="utf-8").read()
            except Exception:
                pass
        if os.path.exists(_wr_json):
            try:
                _wr_cached_meta = json.loads(open(_wr_json, encoding="utf-8").read())
            except Exception:
                pass

        if _wr_cached_text:
            _wr_age = ""
            _wr_ts  = _wr_cached_meta.get("generated_at", "")
            if _wr_ts:
                _wr_age = f" · Generated {_wr_ts}"
            st.info(f"📄 Cached report available{_wr_age}")
            with st.expander("📖 View Cached Report", expanded=True):
                st.text(_wr_cached_text)
            st.download_button(
                "⬇️ Download Cached Report (.txt)",
                data=_wr_cached_text,
                file_name=f"weekly_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                key="dl_weekly_cached"
            )
            st.markdown("---")

        if _wr_generate or st.session_state.get("_wr_just_generated"):
            st.session_state["_wr_just_generated"] = False
            with st.spinner("Generating weekly report… (10–30 seconds)"):
                try:
                    from gemini_reporter import generate_weekly_market_report as _gen_weekly
                    _wr_snapshot = {}
                    if _HUB_OK:
                        try:
                            from market_data_hub import build_postmarket_snapshot as _bps
                            _wr_snapshot = _bps()
                        except Exception as _hube:
                            st.warning(f"Could not fetch live snapshot: {_hube}. Using cached breadth.")

                    # Supplement with breadth cache if available
                    _bl = os.path.join(_wr_dir, "latest_breadth.json")
                    if os.path.exists(_bl):
                        try:
                            _bdata = json.loads(open(_bl, encoding="utf-8").read())
                            _wr_snapshot["breadth"] = _bdata.get("breadth", {})
                        except Exception:
                            pass

                    _wr_snapshot["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _fresh_report = _gen_weekly(_wr_snapshot)

                    # Save to disk
                    os.makedirs(_wr_dir, exist_ok=True)
                    open(_wr_file, "w", encoding="utf-8").write(_fresh_report)
                    open(_wr_json, "w", encoding="utf-8").write(
                        json.dumps({"generated_at": _wr_snapshot["generated_at"],
                                    "word_count": len(_fresh_report.split())}, indent=2)
                    )

                    st.success(f"✅ Report generated ({len(_fresh_report.split())} words)")
                    with st.expander("📖 Weekly Report", expanded=True):
                        st.text(_fresh_report)
                    st.download_button(
                        "⬇️ Download Report (.txt)",
                        data=_fresh_report,
                        file_name=f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        key="dl_weekly_fresh"
                    )
                except Exception as _wre:
                    st.error(f"Weekly report generation failed: {_wre}")
