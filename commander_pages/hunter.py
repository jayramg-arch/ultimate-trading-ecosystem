# commander_pages/hunter.py - the HUNTER page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('hunter', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🎯 Hunter</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Stock Discovery Engine — unified Bull · Recovery · Chartink scanners + Fundamentals enrichment + Matcher selection</div>', unsafe_allow_html=True)
    # P1.6 + P2 follow-up (10 May 2026 — user feedback #13): split the former
    # "Matcher + Recovery" mega-tab into discrete tabs so each discovery tool
    # has its own real estate. Tab order reflects the workflow:
    #   Chartink Scans (Layer 1) → Fundamentals (Layer 2) → Golden Matcher
    #   (Layer 3 conviction-filter combine) → Bull Screener (Pine-aligned live)
    #   → Recovery Screener (REV signals) → X-Ray Screener (deep fundamentals).
    # Note: X-Ray here is the BATCH screener; the single-ticker X-Ray deep-dive
    # remains its own top-level page in DISCOVERY.
    _ht1, _ht2, _ht3, _ht4, _ht5, _ht6 = st.tabs([
        "🔍 Chartink Scans",
        "🧬 Fundamentals",
        "🥇 Golden Matcher",
        "🐂 Bull Screener",
        "🔄 Recovery Screener",
        "🧬 X-Ray Screener",
    ])

    with _ht1:
        section("Chartink Scanners")
        left, right = st.columns(2, gap="medium")
        with left:
            sub_label("📌  Positional Strategies")
            if st.button("Stage 2 Hunter\nLong-horizon stage-based breakout entries.\n→  Run Scanner", use_container_width=True, key="h_s2"):
                launch_script("chartink_scanner_pro.py", "1")
            if st.button("Early Birds Accumulation\nEarly-stage accumulation zone detection.\n→  Run Scanner", use_container_width=True, key="h_eb"):
                launch_script("chartink_scanner_pro.py", "3")
        with right:
            sub_label("📈  Swing Strategies")
            if st.button("Stage 2 Pullback\nShort-term pullback within an uptrend.\n→  Run Scanner", use_container_width=True, key="h_pb"):
                launch_script("chartink_scanner_pro.py", "2")
            if st.button("Strong Leaders\nMomentum leaders with relative strength.\n→  Run Scanner", use_container_width=True, key="h_sl"):
                launch_script("chartink_scanner_pro.py", "4")

        st.markdown("---")
        section("Recovery Phase Scanners  (Post-Shock Mode)")
        st.caption("Use when market has corrected ≥7% from 52W high or is in recovery. Complements Stage 2 scanners.")
        rc1, rc2, rc3 = st.columns(3, gap="medium")
        with rc1:
            if st.button("REV-RS: RS Survivor Breakout\nStocks beating CNX500 now breaking 20D high.\n→  Run Scanner", use_container_width=True, key="h_rev_rs"):
                launch_script("chartink_scanner_pro.py", "5")
        with rc2:
            if st.button("REV-CB: Climax Bottom Bounce\nDeeply stretched stocks with panic-volume signature.\n→  Run Scanner", use_container_width=True, key="h_rev_cb"):
                launch_script("chartink_scanner_pro.py", "6")
        with rc3:
            if st.button("REV-EARLY: Early Bird VCP\nNear golden cross — VCP base compressing.\n→  Run Scanner", use_container_width=True, key="h_rev_early"):
                launch_script("chartink_scanner_pro.py", "7")

    with _ht2:
        section("Fundamental Data")
        left, right = st.columns(2, gap="medium")
        with left:
            if st.button("🌐  Fetch Screener.in Data\nPull raw fundamental HTML from Screener.in.\n→  Fetch Now", use_container_width=True, key="e_fetch"):
                launch_script("screener_fetcher.py")
        with right:
            if st.button("⚙️  Process HTML to CSV\nConvert raw HTML into structured CSV for analysis.\n→  Process Now", use_container_width=True, key="e_proc"):
                launch_script("screener_processor.py")

    with _ht3:
        section("Golden Matcher Engine")
        st.caption("Combines technical scans (Chartink Layer 1) with fundamental filters "
                   "(Screener.in conviction) to find 5-Star setups. Output: FINAL_*.csv files "
                   "+ Ultimate Golden Meta-Ranking (below).")

        # Show last-generated timestamp across all 4 FINAL_*_Picks.csv files
        # so the user knows whether their watchlist is fresh.
        _gm_files = ["FINAL_Hunter_Picks.csv", "FINAL_Pullback_Picks.csv",
                      "FINAL_EarlyBird_Picks.csv", "FINAL_Leader_Picks.csv"]
        _gm_root = os.path.dirname(os.path.abspath(__file__))
        import datetime as _dt_gm
        _gm_mtimes = []
        for _f in _gm_files:
            _p = os.path.join(_gm_root, _f)
            if os.path.exists(_p):
                _gm_mtimes.append((os.path.getmtime(_p), _f))
        if _gm_mtimes:
            _newest_t, _newest_f = max(_gm_mtimes)
            _newest_str = _dt_gm.datetime.fromtimestamp(_newest_t).strftime("%d %b %Y  %H:%M")
            _age_h = (_dt_gm.datetime.now().timestamp() - _newest_t) / 3600
            if _age_h > 28:
                st.warning(f"⚠ Latest FINAL_*.csv from **{_newest_str}** "
                           f"({_age_h:.0f}h old) — re-run **🤖 Run Auto-Pilot** "
                           f"or click below to refresh.")
            else:
                st.caption(f"✓ Last generated: **{_newest_str}** "
                           f"({_age_h:.1f}h ago, freshest: `{_newest_f}`)")
        else:
            st.info("No FINAL_*.csv files found yet. Click **🤖 Run Auto-Pilot** "
                    "in the sidebar OR run the Golden Matcher button below.")

        if st.button("🏆  Run Golden Matcher\nCombines Technical Scans with Fundamental Filters to find 5-Star setups.\n→  Initiate Matching", type="primary", use_container_width=True, key="sel_run"):
            launch_script("brute_force_match_pro.py")

        st.markdown("---")
        section("Ultimate Golden Meta-Ranking")
        _gm_pmap = {"Stage 2 Hunter":"FINAL_Hunter_Picks.csv",
                    "Stage 2 Pullback":"FINAL_Pullback_Picks.csv",
                    "Early Birds":"FINAL_EarlyBird_Picks.csv",
                    "Strong Leaders":"FINAL_Leader_Picks.csv"}
        _gm_master_dfs = []
        for _gm_strat_name, _gm_fname in _gm_pmap.items():
            if os.path.exists(_gm_fname):
                try:
                    _gm_df_t = pd.read_csv(_gm_fname); _gm_df_t.insert(0, 'Strategy', _gm_strat_name)
                    _gm_master_dfs.append(_gm_df_t)
                except Exception as _gm_e:
                    logger.warning(f"Loading {_gm_fname}: {_gm_e}")

        if _gm_master_dfs:
            _gm_master_df = pd.concat(_gm_master_dfs, ignore_index=True)
            _gm_conv_map  = {'High': 3, 'Medium': 2, 'Low': 1, 'N/A': 0}
            if 'Conviction' in _gm_master_df.columns:
                _gm_master_df['Conv_Score'] = _gm_master_df['Conviction'].map(_gm_conv_map).fillna(0)
            else:
                _gm_master_df['Conv_Score'] = 0
            _gm_sort_cols, _gm_asc_opts = ['Conv_Score'], [False]
            if '%Chg' in _gm_master_df.columns:
                _gm_sort_cols.append('%Chg'); _gm_asc_opts.append(False)
            _gm_master_df = _gm_master_df.sort_values(by=_gm_sort_cols, ascending=_gm_asc_opts)
            _gm_show_cols = ['Strategy','Symbol']
            for _c in ['Conviction','AI Catalyst','AI_Catalyst','%Chg','Volume']:
                if _c in _gm_master_df.columns: _gm_show_cols.append(_c)

            # Strategy filter — "All" shows the full combined ranking; specific
            # strategy narrows the table to that bucket. Per user feedback
            # (10 May 2026), the drill-down dropdown belongs HERE next to the
            # Meta-Ranking, not on the Bull Screener tab.
            _gm_strategies_avail = ["All"] + sorted(_gm_master_df["Strategy"].unique().tolist())
            _gm_pick_strat = st.selectbox(
                "Filter by Strategy",
                _gm_strategies_avail,
                key="gm_strat_filter",
                help="Narrows the Meta-Ranking to a single strategy bucket.",
            )
            if _gm_pick_strat != "All":
                _gm_view = _gm_master_df[_gm_master_df["Strategy"] == _gm_pick_strat]
                st.caption(f"Showing top picks for **{_gm_pick_strat}** ({len(_gm_view)} candidates).")
            else:
                _gm_view = _gm_master_df
                st.caption(f"Showing top 25 across all strategies ({len(_gm_view)} total candidates).")

            st.dataframe(
                _gm_view[_gm_show_cols].head(25 if _gm_pick_strat == "All" else len(_gm_view)),
                use_container_width=True, hide_index=True,
            )

            # ── Analyst Sentiment for Golden Matcher picks ────────────────────
            # Pulls sentiment for the top-N picks of the currently-filtered
            # strategy. Uses FINAL_Hunter_Picks.csv if "Stage 2 Hunter" filter
            # is active, etc. — single source per click.
            st.markdown("---")
            _gm_sentiment_csv = (_gm_pmap.get(_gm_pick_strat)
                                  if _gm_pick_strat != "All"
                                  else "FINAL_Hunter_Picks.csv")  # default to Hunter
            _gm_sentiment_path = os.path.join(_gm_root, _gm_sentiment_csv) \
                                  if _gm_sentiment_csv else ""
            _render_analyst_sentiment_panel(
                csv_path=_gm_sentiment_path,
                symbol_col="Symbol",
                key_prefix="gm",
                label=f"Golden Matcher — {_gm_pick_strat}",
                extra_caption=(f"Source: `{_gm_sentiment_csv}` "
                               f"(filter currently set to **{_gm_pick_strat}**)"),
            )
        else:
            st.info("No Final Golden Pick CSVs found. Run the Golden Matcher first.")

    with _ht5:
        section("Recovery Screener  (Python Edition)")
        st.caption("Signal hold-window aware — safe to run post-market or over the weekend. Uses Chartink CSVs 5-7 + yfinance data.")

        # ── Input source selector ──────────────────────────────────────────────
        # P1.6 + #14 (10 May 2026): added Nifty 500 source for backtest-aligned runs.
        _rec_src = st.radio(
            "Symbol Source",
            [
                "📂 Default  (Chartink Recovery CSVs 5-7)",
                "🌐 Nifty 500  (full universe — backtest-aligned)",
                "⚡ F&O Basket  (NSE derivatives universe ~210 stocks)",
                "⬆️ Upload CSV Watchlist",
            ],
            horizontal=True, key="rec_src_radio",
        )

        _rec_custom_syms = None
        _rec_out_file    = "Recovery_Screener_Results.csv"

        if _rec_src.startswith("🌐"):
            try:
                import validation as _val
                _rec_custom_syms = list(_val.default_universe("nifty500"))
                _rec_out_file = "Recovery_Screener_N500_Results.csv"
                st.success(f"✅ {len(_rec_custom_syms)} Nifty 500 symbols loaded.")
                st.caption("Results → **Recovery_Screener_N500_Results.csv**")
            except Exception as _n500re:
                st.error(f"Could not load Nifty 500: {_n500re}")
                _rec_custom_syms = None

        if _rec_src.startswith("⚡"):
            try:
                import validation as _val
                _rec_custom_syms = list(_val.default_universe("fno"))
                _rec_out_file = "Recovery_Screener_FNO_Results.csv"
                st.success(f"✅ {len(_rec_custom_syms)} F&O symbols loaded.")
                st.caption(
                    "Results → **Recovery_Screener_FNO_Results.csv**. "
                    "Refresh `fno_symbols.json` periodically per NSE F&O circulars."
                )
            except Exception as _fnore:
                st.error(f"Could not load F&O basket: {_fnore}")
                _rec_custom_syms = None

        if _rec_src.startswith("⬆️"):
            _rec_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="rec_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _rec_upload is not None:
                try:
                    if _rec_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _rec_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _rec_custom_syms = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _rec_custom_syms.append(s)
                        _rec_custom_syms = list(dict.fromkeys(_rec_custom_syms))
                        _rec_out_file = "Recovery_Screener_Custom_Results.csv"
                        st.success(f"✅ {len(_rec_custom_syms)} symbols loaded from **{_rec_upload.name}**")
                        st.caption("Results → **Recovery_Screener_Custom_Results.csv** (default run not overwritten)")
                    else:
                        _df_rec_up = pd.read_csv(_rec_upload)
                        _rec_col   = next(
                            (c for c in _df_rec_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _rec_col is None:
                            st.warning(f"No Symbol column found. Columns: {list(_df_rec_up.columns)}")
                        else:
                            _rec_custom_syms = (
                                _df_rec_up[_rec_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _rec_custom_syms = [s for s in _rec_custom_syms if s and not s.isdigit()]
                            _rec_out_file    = "Recovery_Screener_Custom_Results.csv"
                            st.success(f"✅ {len(_rec_custom_syms)} symbols loaded from **{_rec_upload.name}**")
                            st.caption("Results → **Recovery_Screener_Custom_Results.csv** (default run not overwritten)")
                except Exception as _rue:
                    st.error(f"Could not parse upload: {_rue}")

        _rec_run_label = (
            f"Run Recovery Screener — Custom Watchlist\n{len(_rec_custom_syms)} symbols\n→  Screen Now"
            if _rec_custom_syms is not None
            else "Run Recovery Screener\nScores REV-CB / REV-RS / REV-EARLY across all watchlist symbols.\n→  Run Now"
        )
        if st.button(_rec_run_label, type="primary", use_container_width=True, key="sel_rec"):
            try:
                import recovery_screener as _rs
                _rec_prog  = st.progress(0)
                _rec_stat  = st.empty()

                def _on_rec_progress(idx, total, sym):
                    _rec_prog.progress(int(idx / total * 100))
                    _rec_stat.text(f"Scanning [{idx}/{total}]: {sym}")

                # strict=True for Nifty 500 / F&O — drop Signal=0 rows so the CSV
                # only contains actionable candidates. Upload-CSV keeps all rows.
                _rec_strict = _rec_src.startswith("🌐") or _rec_src.startswith("⚡")
                _df_rec_res = _rs.run_recovery_screener(
                    progress_callback=_on_rec_progress,
                    symbols=_rec_custom_syms,
                    out_file=_rec_out_file,
                    strict=_rec_strict,
                )
                _rec_prog.empty(); _rec_stat.empty()
                if not _df_rec_res.empty:
                    st.success(f"✅ Done — {len(_df_rec_res)} stocks screened, {(_df_rec_res['Signal'] >= 2).sum()} actionable.")
                else:
                    st.info("No candidates found. Check Chartink CSVs or uploaded symbols.")
            except Exception as _re:
                st.error(f"Recovery Screener error: {_re}")

        import datetime as _dt
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        rec_csv = os.path.join(_script_dir, _rec_out_file)
        if not os.path.exists(rec_csv):
            rec_csv = _rec_out_file   # fallback: CWD
        if os.path.exists(rec_csv):
            try:
                df_rec = pd.read_csv(rec_csv)

                # ── Last-run timestamp & staleness warning ────────────────────
                _mtime = _dt.datetime.fromtimestamp(os.path.getmtime(rec_csv))
                _age_h = (_dt.datetime.now() - _mtime).total_seconds() / 3600
                _ts_str = _mtime.strftime("%d %b %Y  %H:%M")
                if _age_h > 28:
                    st.warning(f"Results last updated {_ts_str} — more than 1 trading day old. Re-run for fresh signals.")
                else:
                    st.caption(f"Results from {_ts_str}")

                # ── Signal age column (trading days since signal fired) ───────
                if "Signal_Date" in df_rec.columns:
                    _today = _dt.date.today()
                    def _td_age(d):
                        try:
                            sd = _dt.datetime.strptime(str(d).strip(), "%d %m %y").date() if len(str(d)) == 8 else _dt.datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
                            delta = (_today - sd).days
                            weeks, rem = divmod(delta, 7)
                            return weeks * 5 + min(rem, 5)
                        except Exception:
                            return None
                    df_rec.insert(df_rec.columns.get_loc("Signal_Date") + 1,
                                  "Age_Days", df_rec["Signal_Date"].apply(_td_age))

                st.markdown("**Latest Recovery Screener Results**")

                # ── Filters ──────────────────────────────────────────────────
                fc1, fc2, fc3 = st.columns([2, 2, 2], gap="small")
                with fc1:
                    sig_filter = st.selectbox("Signal", ["All (Actionable)", "Signal=4 (REV-EARLY)", "Signal=3 (REV-RS)", "Signal=2 (REV-CB)", "Signal=1 (CB-Watch)", "Show All"], key="rec_sig_filter")
                with fc2:
                    rs_min = st.number_input("Min Mansfield RS", min_value=0.0, max_value=10.0, value=0.0, step=0.5, key="rec_rs_min")
                with fc3:
                    max_age = st.number_input("Max Signal Age (trading days)", min_value=1, max_value=20, value=5, key="rec_age_max")

                sig_map = {"Signal=4 (REV-EARLY)": 4, "Signal=3 (REV-RS)": 3, "Signal=2 (REV-CB)": 2, "Signal=1 (CB-Watch)": 1}
                if sig_filter == "All (Actionable)":
                    df_rec = df_rec[df_rec["Signal"] >= 2]
                elif sig_filter in sig_map and "Signal" in df_rec.columns:
                    df_rec = df_rec[df_rec["Signal"] == sig_map[sig_filter]]

                if rs_min > 0 and "Mansfield_RS" in df_rec.columns:
                    df_rec = df_rec[pd.to_numeric(df_rec["Mansfield_RS"], errors="coerce") >= rs_min]

                if "Age_Days" in df_rec.columns:
                    _age_num = pd.to_numeric(df_rec["Age_Days"], errors="coerce")
                    df_rec = df_rec[_age_num.isna() | (_age_num <= max_age)]

                show_rec_cols = [c for c in [
                    "Symbol", "Signal_Label", "Signal_Date", "Age_Days", "Score", "RFF_Score",
                    "Weinstein_Stage", "Mansfield_RS", "RSI14", "Rel_Vol",
                    "Entry", "SL", "T1", "RR_T1", "SL_pct", "T1_pct", "Details"
                ] if c in df_rec.columns]
                st.dataframe(df_rec[show_rec_cols].head(50), use_container_width=True, hide_index=True)
                st.caption(f"{len(df_rec)} stocks shown after filters.")

                # ── Export buttons ────────────────────────────────────────────
                if not df_rec.empty and "Symbol" in df_rec.columns:
                    _rec_syms = df_rec["Symbol"].dropna().astype(str).str.strip().tolist()
                    _pine_export = (
                        f'// Commander Recovery Screener — Pine Symbol Array\n'
                        f'// Generated {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}\n\n'
                        f'recovery_syms = array.from(\n    '
                        + ",\n    ".join(f'"NSE:{s}"' for s in _rec_syms)
                        + '\n)'
                    )
                    _rec_col1, _rec_col2, _rec_col3 = st.columns([2, 1, 1])
                    with _rec_col1:
                        st.text_area(
                            "📋 Pine Symbol List",
                            value=", ".join(f'"NSE:{s}"' for s in _rec_syms),
                            height=80, key="rec_pine_syms"
                        )
                    with _rec_col2:
                        st.download_button(
                            label="⬇️ Export CSV",
                            data=df_rec[show_rec_cols].to_csv(index=False).encode("utf-8"),
                            file_name="Recovery_Screener_Export.csv",
                            mime="text/csv",
                            key="rec_csv_dl",
                        )
                    with _rec_col3:
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_export,
                            file_name="Recovery_Pine_Symbols.pine",
                            mime="text/plain",
                            key="rec_pine_dl",
                            help="Download as a .pine snippet ready to paste into your indicator"
                        )
            except Exception as e:
                st.error(f"Error loading Recovery Screener results: {e}")
        else:
            st.info("No Recovery Screener results yet. Run the screener above (default or upload a custom watchlist).")

        # ── Analyst Sentiment for Recovery picks ─────────────────────────────
        st.markdown("---")
        _rec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  _rec_out_file)
        _render_analyst_sentiment_panel(
            csv_path=_rec_path,
            symbol_col="Symbol",
            key_prefix="rec",
            label="Recovery Screener Picks",
            extra_caption=f"Reading from `{_rec_out_file}`",
        )

    with _ht6:
        # ── Quick Look — per-symbol analyst sentiment + paid news, inline ───
        # 10 May 2026: per user feedback, the bulk X-Ray Screener input was here
        # but the per-symbol News result was on the separate X-RAY page.
        # This Quick Look panel keeps both on the same screen — type a symbol,
        # see its sentiment + paid headlines without leaving the tab.
        section("🔍 Quick Look — Single-Symbol Analyst Sentiment + Paid News")
        st.caption("Type any NSE symbol below to see its consensus + ET/MC headlines "
                   "right here. For deep fundamentals (Income Statement, Quarterly "
                   "Results, Scorecard), open **🧬 X-RAY** in the sidebar.")

        _ql_c1, _ql_c2 = st.columns([2, 4])
        with _ql_c1:
            _ql_sym = st.text_input(
                "NSE Symbol", value="",
                placeholder="e.g. RELIANCE, INFY, DIXON",
                key="ht_xray_quicklook_sym"
            ).strip().upper().replace(".NS", "").replace(".BO", "")
        with _ql_c2:
            _ql_force = st.checkbox(
                "Force refresh (bypass 6h cache)",
                value=False, key="ht_xray_quicklook_force"
            )

        if _ql_sym:
            try:
                import analyst_sentiment as _ql_ans
                with st.spinner(f"Fetching ET + MC analyst sentiment for {_ql_sym}…"):
                    _ql_sent = _ql_ans.get_for_symbol(_ql_sym, force=_ql_force)

                _ql_cons = _ql_sent["consensus"]
                _ql_cons_color = {
                    "STRONG_BUY":  "#39ff14",
                    "BUY":         "var(--bull)",
                    "HOLD":        "var(--warn)",
                    "SELL":        "var(--bear)",
                    "STRONG_SELL": "#ff1744",
                    "MIXED":       "#a78bfa",
                    "NONE":        "var(--ink-2)",
                }.get(_ql_cons, "var(--ink-2)")
                _ql_cons_label = _ql_cons.replace("_", " ")

                _q1, _q2, _q3, _q4, _q5, _q6 = st.columns(6)
                _q1.markdown(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">Consensus</div>'
                    f'<div class="metric-value" style="color:{_ql_cons_color}">{_ql_cons_label}</div>'
                    f'</div>', unsafe_allow_html=True)
                _q2.metric("⭐ STRONG BUY",  _ql_sent.get("strong_buy", 0))
                _q3.metric("BUY",            _ql_sent["buy"])
                _q4.metric("HOLD",           _ql_sent["hold"])
                _q5.metric("SELL",           _ql_sent["sell"])
                _q6.metric("⚠ STRONG SELL", _ql_sent.get("strong_sell", 0))

                _src_ok = _ql_sent.get("sources_ok", {})
                st.caption(
                    f"ET: {'✓' if _src_ok.get('et') else '✗'}  ·  "
                    f"MC: {'✓' if _src_ok.get('mc') else '✗'}  ·  "
                    f"Fetched: {_ql_sent.get('fetched_at', '—')}  ·  6h cache"
                )

                _ql_items = _ql_sent.get("items", [])
                if _ql_items:
                    # Action-priority ordering: STRONG_BUY → BUY → STRONG_SELL → SELL → HOLD → OTHER
                    _ql_order = {"STRONG_BUY": 0, "BUY": 1, "STRONG_SELL": 2,
                                  "SELL": 3, "HOLD": 4, "OTHER": 5}
                    _ql_sorted = sorted(
                        _ql_items,
                        key=lambda x: _ql_order.get(x.get("action", "OTHER"), 6)
                    )
                    with st.expander(f"📰 {len(_ql_items)} headlines (sorted by action)",
                                     expanded=True):
                        for _it in _ql_sorted[:30]:
                            _a = _it.get("action") or "?"
                            _ac = {
                                "STRONG_BUY":  "#39ff14",
                                "BUY":         "var(--bull)",
                                "HOLD":        "var(--warn)",
                                "SELL":        "var(--bear)",
                                "STRONG_SELL": "#ff1744",
                            }.get(_a, "var(--ink-2)")
                            _origin = _it.get("_origin", "?").upper()
                            _origin_label = {"ET": "Economic Times",
                                              "MC": "Moneycontrol"}.get(_origin, _origin)
                            _brk = _it.get("brokerage") or ""
                            _brk_str = f"  ·  {_brk}" if _brk else ""
                            st.markdown(
                                f'<div style="margin:6px 0;padding:8px;background:var(--surface);'
                                f'border-left:3px solid {_ac};border-radius:4px;">'
                                f'<span style="color:{_ac};font-weight:600;'
                                f'font-family:JetBrains Mono,monospace;font-size:0.7rem;">'
                                f'{_a.replace("_"," ")}</span>'
                                f'  ·  <span style="color:var(--ink);font-size:0.72rem;">{_origin_label}</span>'
                                f'<span style="color:#8b9eb0;font-size:0.72rem;">{_brk_str}</span>'
                                f'<div style="margin-top:4px;">'
                                f'<a href="{_it.get("url","#")}" target="_blank" '
                                f'style="color:var(--ink);font-size:0.86rem;text-decoration:none;">'
                                f'{_it.get("title","")}</a></div></div>',
                                unsafe_allow_html=True
                            )
                else:
                    st.info(
                        f"No paid ET/MC headlines mentioning **{_ql_sym}** in current cache. "
                        f"Try a different ticker or expand the company-name keyword map."
                    )
            except FileNotFoundError as _ql_e:
                st.warning(
                    "Paid news cookies not configured. Run "
                    "`python setup_paid_news_cookies.py` to enable ET + MC scraping."
                )
            except Exception as _ql_e:
                st.error(f"Quick Look fetch failed: {_ql_e}")

        st.markdown("---")
        section("📊 Bulk X-Ray Fundamental Screener (Python Edition)")
        st.caption("Scans watchlists OR custom symbols using the deep Weinstein Fundamental X-Ray v2.2 logic.")

        # ── Input source selector ──────────────────────────────────────────────
        _xray_src = st.radio(
            "Symbol Source",
            ["📂 Default  (Generated Watchlists)", "⬆️ Upload CSV Watchlist"],
            horizontal=True, key="xray_src_radio",
        )

        _xray_custom_syms = None
        _xray_out_file    = "FINAL_XRay_Picks.csv"

        if _xray_src.startswith("⬆️"):
            _xray_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="xray_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _xray_upload is not None:
                try:
                    if _xray_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _xray_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _xray_custom_syms = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _xray_custom_syms.append(s)
                        _xray_custom_syms = list(dict.fromkeys(_xray_custom_syms))
                        _xray_out_file = "XRay_Screener_Custom_Results.csv"
                        st.success(f"✅ {len(_xray_custom_syms)} symbols loaded from **{_xray_upload.name}**")
                        st.caption("Results → **XRay_Screener_Custom_Results.csv** (default run not overwritten)")
                    else:
                        _df_xr_up = pd.read_csv(_xray_upload)
                        _xr_col   = next(
                            (c for c in _df_xr_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _xr_col is None:
                            st.warning(f"No Symbol column found. Columns: {list(_df_xr_up.columns)}")
                        else:
                            _xray_custom_syms = (
                                _df_xr_up[_xr_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _xray_custom_syms = [s for s in _xray_custom_syms if s and not s.isdigit()]
                            _xray_out_file    = "XRay_Screener_Custom_Results.csv"
                            st.success(f"✅ {len(_xray_custom_syms)} symbols loaded from **{_xray_upload.name}**")
                            st.caption("Results → **XRay_Screener_Custom_Results.csv** (default run not overwritten)")
                except Exception as _xue:
                    st.error(f"Could not parse upload: {_xue}")
        else:
            # Legacy text-area passthrough for backward compat
            _xray_text = st.text_area(
                "Custom Symbols (Optional — overrides watchlists when filled)",
                help="TradingView format (NSE:RELIANCE) or plain codes, comma/newline separated.",
                key="xray_custom_input", height=80,
                placeholder="NSE:WELCORP,NSE:APARINDS\nOr leave blank to scan all watchlists automatically."
            )
            if _xray_text.strip():
                _xray_custom_syms = [
                    s.strip().replace("NSE:", "").replace("BSE:", "").upper()
                    for s in _xray_text.replace(",", "\n").splitlines() if s.strip()
                ]

        _xray_run_label = (
            f"Run X-Ray Screener — Custom Watchlist\n{len(_xray_custom_syms)} symbols\n→  Screen Now"
            if _xray_custom_syms is not None
            else "Run X-Ray Screener\nEvaluates Minervini & Piotroski logic bypassing TV limits.\n→  Run Now"
        )
        if st.button(_xray_run_label, type="primary", use_container_width=True, key="sel_xray"):
            try:
                import xray_screener_job as _xj
                _xray_prog = st.progress(0)
                _xray_stat = st.empty()

                def _on_xray_progress(idx, total, sym):
                    _xray_prog.progress(int(idx / total * 100))
                    _xray_stat.text(f"Scanning [{idx}/{total}]: {sym}")

                _df_xray_res = _xj.run_xray_screener(
                    progress_callback=_on_xray_progress,
                    symbols=_xray_custom_syms,
                    out_file=_xray_out_file,
                )
                _xray_prog.empty(); _xray_stat.empty()
                if not _df_xray_res.empty:
                    st.success(f"✅ Done — {len(_df_xray_res)} stocks scored.")
                else:
                    st.info("No results. Check watchlists or uploaded symbols.")
            except Exception as _xe:
                st.error(f"X-Ray Screener error: {_xe}")

        import datetime as _dt
        xray_csv = os.path.join(_script_dir, _xray_out_file)
        if os.path.exists(xray_csv):
            try:
                df_xray = pd.read_csv(xray_csv)

                _xmtime  = _dt.datetime.fromtimestamp(os.path.getmtime(xray_csv))
                _xage_h  = (_dt.datetime.now() - _xmtime).total_seconds() / 3600
                _xts_str = _xmtime.strftime("%d %b %Y  %H:%M")
                if _xage_h > 28:
                    st.warning(f"Results last updated {_xts_str} — consider re-running.")
                else:
                    st.caption(f"Results from **{_xts_str}**")

                st.markdown("**Latest X-Ray Screener Results**")

                xc1, xc2 = st.columns([1, 1], gap="small")
                with xc1:
                    min_rating = st.number_input("Min Overall Rating", min_value=0, max_value=17, value=0, step=1, key="xray_rating")
                with xc2:
                    min_piotroski = st.number_input("Min Piotroski Score", min_value=0, max_value=7, value=0, step=1, key="xray_pio")

                df_xray_disp = df_xray[
                    (pd.to_numeric(df_xray["Overall_Rating"], errors="coerce").fillna(0) >= min_rating) &
                    (pd.to_numeric(df_xray["Piotroski_Score"], errors="coerce").fillna(0) >= min_piotroski)
                ]
                st.dataframe(df_xray_disp, use_container_width=True, hide_index=True)
                st.caption(f"{len(df_xray_disp)} stocks shown after filters.")

                if not df_xray_disp.empty:
                    _xray_syms = df_xray_disp["Symbol"].dropna().astype(str).unique().tolist()
                    _pine_xray = (
                        "// Commander X-Ray Screener — Pine Symbol Array\n"
                        f"// Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        "var string[] xray_symbols = array.from(\n    "
                        + ", ".join(f'"{s.replace(".NS", "")}"' for s in _xray_syms)
                        + "\n)"
                    )
                    _xdl1, _xdl2 = st.columns([3, 1])
                    with _xdl1:
                        st.download_button(
                            label="⬇️ Export Filtered to CSV",
                            data=df_xray_disp.to_csv(index=False).encode("utf-8"),
                            file_name="XRay_Screener_Export.csv",
                            mime="text/csv",
                            key="xray_csv_dl",
                        )
                    with _xdl2:
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_xray,
                            file_name="XRay_Pine_Symbols.pine",
                            mime="text/plain",
                            key="xray_pine_dl",
                            help="Download as a .pine snippet ready to paste into your indicator"
                        )
            except Exception as e:
                st.error(f"Error loading X-Ray Screener results: {e}")
        # (Old in-tab Ultimate Golden Meta-Ranking removed — it now lives at the
        # top of the 🥇 Golden Matcher tab next to the Run Matcher button.)

        # ── Analyst Sentiment for X-Ray Screener picks (bulk run) ────────────
        st.markdown("---")
        _xray_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   _xray_out_file)
        _render_analyst_sentiment_panel(
            csv_path=_xray_path,
            symbol_col="Symbol",
            key_prefix="xray",
            label="X-Ray Screener Picks",
            extra_caption=f"Reading from `{_xray_out_file}` "
                          "(use the Quick Look box at the top of this tab for single-symbol drill-down)",
        )

    with _ht4:
        section("Bull Market Screener")
        st.caption("Implements 6 catalysts from Commander Screener Beta Edition v2.9 (Pine).")

        # ── Input source selector ──────────────────────────────────────────────
        # P1.6 + #14 (10 May 2026): added "Nifty 500 (full universe)" as a third
        # source option so the python screener can run on the same universe used
        # by the validation backtest (validation.default_universe('nifty500')).
        # Per Bible §14A this is the canonical universe for cross-platform
        # consistency between backtest and live screening.
        _bull_src = st.radio(
            "Symbol Source",
            [
                "📂 Default  (FINAL_COMBINED_BULL_PICKS.csv)",
                "🌐 Nifty 500  (full universe — backtest-aligned)",
                "⚡ F&O Basket  (NSE derivatives universe ~210 stocks)",
                "⬆️ Upload CSV Watchlist",
            ],
            horizontal=True, key="bull_src_radio",
        )

        _bull_custom_symbols = None   # None → screener reads default file
        _bull_out_file       = "Bull_Screener_Results.csv"

        if _bull_src.startswith("🌐"):
            # Nifty 500 — load via validation.default_universe('nifty500')
            try:
                import validation as _val
                _bull_custom_symbols = list(_val.default_universe("nifty500"))
                _bull_out_file = "Bull_Screener_N500_Results.csv"
                st.success(
                    f"✅ {len(_bull_custom_symbols)} Nifty 500 symbols loaded "
                    "(via validation.default_universe('nifty500'))."
                )
                st.caption(
                    "Results will be saved to **Bull_Screener_N500_Results.csv** "
                    "(separate from the default-watchlist run)."
                )
            except Exception as _n500e:
                st.error(f"Could not load Nifty 500: {_n500e}")
                _bull_custom_symbols = None

        if _bull_src.startswith("⚡"):
            # F&O Basket — load via validation.default_universe('fno')
            try:
                import validation as _val
                _bull_custom_symbols = list(_val.default_universe("fno"))
                _bull_out_file = "Bull_Screener_FNO_Results.csv"
                st.success(
                    f"✅ {len(_bull_custom_symbols)} F&O symbols loaded "
                    "(via validation.default_universe('fno') → fno_symbols.json)."
                )
                st.caption(
                    "Results will be saved to **Bull_Screener_FNO_Results.csv** "
                    "(separate from default / Nifty 500 runs). "
                    "Refresh `fno_symbols.json` periodically per NSE F&O circulars."
                )
            except Exception as _fnoe:
                st.error(f"Could not load F&O basket: {_fnoe}")
                _bull_custom_symbols = None

        if _bull_src.startswith("⬆️"):
            _bull_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="bull_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _bull_upload is not None:
                try:
                    if _bull_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _bull_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _bull_custom_symbols = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _bull_custom_symbols.append(s)
                        _bull_custom_symbols = list(dict.fromkeys(_bull_custom_symbols))
                        _bull_out_file = "Bull_Screener_Custom_Results.csv"
                        st.success(
                            f"✅ {len(_bull_custom_symbols)} symbols loaded from "
                            f"**{_bull_upload.name}**"
                        )
                        st.caption(
                            "Results will be saved to **Bull_Screener_Custom_Results.csv** "
                            "and will not overwrite your default run."
                        )
                    else:
                        _df_up = pd.read_csv(_bull_upload)
                        _col   = next(
                            (c for c in _df_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _col is None:
                            st.warning(
                                f"No Symbol column found. Columns in file: {list(_df_up.columns)}"
                            )
                        else:
                            _bull_custom_symbols = (
                                _df_up[_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _bull_custom_symbols = [
                                s for s in _bull_custom_symbols if s and not s.isdigit()
                            ]
                            _bull_out_file = "Bull_Screener_Custom_Results.csv"
                            st.success(
                                f"✅ {len(_bull_custom_symbols)} symbols loaded from "
                                f"**{_bull_upload.name}**"
                            )
                            st.caption(
                                "Results will be saved to **Bull_Screener_Custom_Results.csv** "
                                "and will not overwrite your default run."
                            )
                except Exception as _ue:
                    st.error(f"Could not parse upload: {_ue}")

        # ── Run button ─────────────────────────────────────────────────────────
        _run_label = (
            "Run Bull Screener — Custom Watchlist\n"
            f"{len(_bull_custom_symbols)} symbols loaded\n→  Screen Now"
            if _bull_custom_symbols is not None
            else "Run Bull Screener — Default Watchlist\n"
                 "Reads FINAL_COMBINED_BULL_PICKS.csv\n→  Screen Now"
        )
        if st.button(_run_label, type="primary", use_container_width=True, key="sel_bull"):
            try:
                import bull_screener as _bs
                _prog_bar  = st.progress(0)
                _stat_text = st.empty()

                def _on_bull_progress(idx, total, sym):
                    _prog_bar.progress(int(idx / total * 100))
                    _stat_text.text(f"Scanning [{idx}/{total}]: {sym}")

                # strict=True for Nifty 500 / F&O — apply full catalyst gate (no tracker mode).
                # Upload-CSV path keeps tracker mode so users see every monitored stock.
                _bull_strict = _bull_src.startswith("🌐") or _bull_src.startswith("⚡")
                _df_result = _bs.run_bull_screener(
                    progress_callback=_on_bull_progress,
                    symbols=_bull_custom_symbols,   # None → uses default file
                    out_file=_bull_out_file,
                    strict=_bull_strict,
                )
                _prog_bar.empty(); _stat_text.empty()
                if not _df_result.empty:
                    st.success(f"✅ Done — {len(_df_result)} signals found.")
                else:
                    st.info("No catalyst signals fired for this watchlist.")
            except Exception as _be:
                st.error(f"Bull Screener error: {_be}")

        # ── Results display ────────────────────────────────────────────────────
        import datetime as _dt
        _script_dir_bs = os.path.dirname(os.path.abspath(__file__))
        _bull_csv_path = os.path.join(_script_dir_bs, _bull_out_file)
        _bull_input_path = os.path.join(_script_dir_bs, "FINAL_COMBINED_BULL_PICKS.csv")

        # Show INPUT file freshness alongside OUTPUT — if input is newer than
        # output, the user ran Auto-Pilot but hasn't re-run the Bull Screener.
        # 10 May 2026 fix: prevents "stale 5 May date" confusion when the
        # underlying watchlist was actually refreshed today.
        _bf_in_col, _bf_out_col = st.columns(2)
        with _bf_in_col:
            st.markdown("**📥 Input watchlist** (`FINAL_COMBINED_BULL_PICKS.csv`)")
            _csv_freshness_caption(_bull_input_path, label="Watchlist")
        with _bf_out_col:
            st.markdown(f"**📤 Last screen run** (`{_bull_out_file}`)")
            _csv_freshness_caption(_bull_csv_path, label="Last run")

        # Stale-input warning: if input is newer than output, alert user
        if os.path.exists(_bull_input_path) and os.path.exists(_bull_csv_path):
            _input_mt  = os.path.getmtime(_bull_input_path)
            _output_mt = os.path.getmtime(_bull_csv_path)
            if _input_mt > _output_mt + 60:  # 60-sec grace to avoid false-positives
                st.info(
                    "🆕 The input watchlist is **newer** than your last Bull Screener "
                    "run. Click **Run Bull Screener** above to refresh against the "
                    "current watchlist."
                )

        if os.path.exists(_bull_csv_path):
            try:
                _df_bull = pd.read_csv(_bull_csv_path)

                st.markdown("**Latest Bull Screener Results**")

                _fc1, _fc2 = st.columns([2, 2], gap="small")
                with _fc1:
                    _cat_choices = ["All"] + sorted(
                        _df_bull["Catalyst"].dropna().unique().tolist()
                    ) if "Catalyst" in _df_bull.columns else ["All"]
                    _cat_filt = st.selectbox(
                        "Catalyst Filter", _cat_choices, key="bull_cat_filter"
                    )
                with _fc2:
                    # v1.0 sync: bull_screener now uses 0-100 score scale (was 0-20).
                    # Default kept at 0 (no filter) so existing user behaviour preserved.
                    _min_scr = st.number_input(
                        "Min Score", min_value=0, max_value=100,
                        value=0, key="bull_score_filter"
                    )

                _df_view = _df_bull.copy()
                if _cat_filt != "All" and "Catalyst" in _df_view.columns:
                    _df_view = _df_view[_df_view["Catalyst"] == _cat_filt]
                if "Score" in _df_view.columns:
                    _df_view = _df_view[
                        pd.to_numeric(_df_view["Score"], errors="coerce").fillna(0) >= _min_scr
                    ]

                st.dataframe(_df_view, use_container_width=True, hide_index=True)
                st.caption(f"{len(_df_view)} stocks shown after filters.")

                if not _df_view.empty:
                    _dl1, _dl2 = st.columns([3, 1])
                    with _dl1:
                        st.download_button(
                            label="⬇️ Export Filtered to CSV",
                            data=_df_view.to_csv(index=False).encode("utf-8"),
                            file_name="Bull_Screener_Export.csv",
                            mime="text/csv",
                            key="bull_csv_dl",
                        )
                    with _dl2:
                        _pine_bull = (
                            "// Commander Bull Screener — Pine Symbol Array\n"
                            f"// Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                            "var string[] bull_syms = array.from(\n    "
                            + ",\n    ".join(
                                f'"NSE:{s}"'
                                for s in _df_view["Symbol"].dropna().astype(str).tolist()
                            )
                            + "\n)"
                        )
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_bull,
                            file_name="Bull_Pine_Symbols.pine",
                            mime="text/plain",
                            key="bull_pine_dl",
                        )
            except Exception as _be2:
                st.error(f"Error loading Bull Screener results: {_be2}")
        else:
            st.info(
                "No Bull Screener results yet. "
                "Run the screener above (default or upload a custom watchlist)."
            )

        # ── Catalyst Drill-Down ───────────────────────────────────────────
        # Note: the Strategy → fundamentals drill-down (FINAL_*_Picks.csv) was
        # moved to the Golden Matcher tab. This drill-down is purpose-built for
        # the Bull Screener: pick a catalyst (POS-AC / POS-BO / SWG-PB / SWG-BO
        # / SWG-REV / GAP-GO) and see ONLY that catalyst's signals with full
        # column detail. Useful when you want to focus on one playbook at a time.
        if os.path.exists(_bull_csv_path):
            try:
                _drill_df = pd.read_csv(_bull_csv_path)
                if not _drill_df.empty and "Catalyst" in _drill_df.columns:
                    section("Catalyst Drill-Down")
                    _cat_options = sorted(_drill_df["Catalyst"].dropna().unique().tolist())
                    if _cat_options:
                        _drill_pick = st.selectbox(
                            "Select Catalyst to drill down:",
                            _cat_options,
                            key="bull_drill_catalyst",
                            help="Filters the table to signals fired by ONE specific catalyst, "
                                 "with all columns visible.",
                        )
                        _drill_view = _drill_df[_drill_df["Catalyst"] == _drill_pick]
                        st.caption(
                            f"**{_drill_pick}** — {len(_drill_view)} signal(s). "
                            f"Refer to the Beta Screener v2.9 catalyst playbooks for entry/exit logic."
                        )
                        st.dataframe(_drill_view, use_container_width=True, hide_index=True)
                    else:
                        st.info("No catalysts to drill into. Run the Bull Screener first.")
            except Exception as _drill_e:
                st.error(f"Catalyst drill-down failed: {_drill_e}")

        # ── DEPRECATED inline Analyst Sentiment panel ──────────────────────
        # Removed 10 May 2026 — duplicated the helper-based panel at the top
        # of this tab (line ~2406, _render_analyst_sentiment_panel(...)). The
        # inline duplicate had a brittle r["consensus"] dict access that raised
        # KeyError('Consensus') when a cached result was missing keys. The
        # canonical panel uses .get() throughout. This block neutralised so
        # only one Analyst Sentiment section renders per tab.
        if False:  # original block kept inert below; never executes
            section("📊 Analyst Sentiment — ET + Moneycontrol (paid)")
        try:
            import analyst_sentiment as _ans
            _ans_health = _ans.health_check()
            _et_ok = _ans_health.get("et", {}).get("ok", False)
            _mc_ok = _ans_health.get("mc", {}).get("ok", False)
            _ans_h1, _ans_h2 = st.columns(2)
            _ans_h1.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
                f'ET session: <b style="color:{"var(--bull)" if _et_ok else "var(--bear)"}">'
                f'{"✓ live" if _et_ok else "✗ down — re-run setup_paid_news_cookies.py"}</b>'
                f'</div>', unsafe_allow_html=True)
            _ans_h2.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
                f'MC session: <b style="color:{"var(--bull)" if _mc_ok else "var(--bear)"}">'
                f'{"✓ live" if _mc_ok else "✗ down — re-run setup_paid_news_cookies.py"}</b>'
                f'</div>', unsafe_allow_html=True)

            if (_et_ok or _mc_ok) and os.path.exists(_bull_csv_path):
                st.caption("Pulls Buy/Hold/Sell consensus + recent analyst headlines for "
                           "each Bull Screener pick. Cached 6h per symbol — first run can "
                           "take ~20–40s for 10 symbols.")
                _ans_top_n = st.slider("Symbols to pull sentiment for (top N by Score)",
                                       min_value=5, max_value=30, value=10,
                                       key="bull_ans_topn")
                _ans_force = st.checkbox("Force refresh (bypass 6h cache)",
                                         value=False, key="bull_ans_force")
                if st.button("📊 Pull Analyst Sentiment", key="bull_ans_btn",
                             type="secondary"):
                    try:
                        _ans_df_full = pd.read_csv(_bull_csv_path)
                        _sym_col = next((c for c in ["Symbol","NSECode","Ticker"]
                                         if c in _ans_df_full.columns), None)
                        if _sym_col is None:
                            st.warning("No Symbol column in Bull Screener results.")
                        else:
                            # Sort by Score descending, take top N
                            if "Score" in _ans_df_full.columns:
                                _ans_df_full = _ans_df_full.sort_values(
                                    "Score", ascending=False
                                )
                            _ans_syms = (_ans_df_full[_sym_col].dropna().astype(str)
                                         .head(int(_ans_top_n)).tolist())
                            _ans_results = []
                            _prog = st.progress(0)
                            for i, sym in enumerate(_ans_syms, 1):
                                r = _ans.get_for_symbol(sym, force=_ans_force)
                                _ans_results.append({
                                    "Symbol":        sym,
                                    "Consensus":     r["consensus"],
                                    "★ STRONG BUY":  r.get("strong_buy", 0),
                                    "BUY":           r["buy"],
                                    "HOLD":          r["hold"],
                                    "SELL":          r["sell"],
                                    "★ STRONG SELL": r.get("strong_sell", 0),
                                    "Items":         len(r["items"]),
                                    "ET":            "✓" if r["sources_ok"]["et"] else "✗",
                                    "MC":            "✓" if r["sources_ok"]["mc"] else "✗",
                                })
                                _prog.progress(int(i / len(_ans_syms) * 100))
                            _prog.empty()
                            _ans_df = pd.DataFrame(_ans_results)
                            # Sort: STRONG_BUY → BUY → MIXED → HOLD → NONE → SELL → STRONG_SELL
                            _consensus_rank = {
                                "STRONG_BUY":  0, "BUY":  1, "MIXED": 2,
                                "HOLD":        3, "NONE": 4, "SELL":  5,
                                "STRONG_SELL": 6,
                            }
                            _ans_df["_rank"] = _ans_df["Consensus"].map(_consensus_rank).fillna(7)
                            _ans_df = (_ans_df.sort_values(
                                ["_rank", "★ STRONG BUY", "BUY"],
                                ascending=[True, False, False])
                                       .drop(columns=["_rank"]))
                            st.dataframe(_ans_df, use_container_width=True,
                                         hide_index=True)

                            # ── Strong Buy spotlight ──────────────────────────
                            _strong_only = _ans_df[
                                (_ans_df["Consensus"] == "STRONG_BUY") |
                                (_ans_df["★ STRONG BUY"] > 0)
                            ]
                            if not _strong_only.empty:
                                st.success(
                                    f"⭐ **{len(_strong_only)} Strong Buy candidate(s)** — "
                                    f"{', '.join(_strong_only['Symbol'].astype(str).tolist())}"
                                )
                            else:
                                st.caption(
                                    "_No Strong Buy candidates in this batch. "
                                    "Strong Buy requires at least one analyst headline with "
                                    "'strong buy' / 'top pick' / 'best idea' / 'high-conviction buy' "
                                    "AND no opposing actionable Sells._"
                                )

                            st.caption(f"Pulled at {pd.Timestamp.now().strftime('%H:%M IST')}. "
                                       "Drill into a single symbol on **🧬 X-RAY → 📰 News** "
                                       "for full headlines + brokerage details.")
                    except Exception as _ans_e:
                        st.error(f"Sentiment pull failed: {_ans_e}")
            elif not (_et_ok or _mc_ok):
                st.warning(
                    "Both ET and MC sessions are down. Re-run "
                    "`python setup_paid_news_cookies.py` to refresh cookies."
                )
            else:
                st.info("Run the Bull Screener above first — sentiment pulls from those picks.")
        except ImportError:
            st.info("Analyst sentiment module not installed. See `analyst_sentiment.py`.")
