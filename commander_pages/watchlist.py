# commander_pages/watchlist.py - the WATCHLIST page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('watchlist', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📋 Watchlist Sync</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Synchronize your selected setups across all platforms.</div>', unsafe_allow_html=True)

    # ── Auto-Pilot Output Panel (G — 10 May 2026) ────────────────────────────
    # Per user feedback: the WATCHLIST page should surface what Run Full
    # Auto-Pilot just produced. Without this, the user clicked Auto-Pilot in
    # the sidebar, landed here, and had no visual confirmation of the FINAL_*.csv
    # files that had been written. This panel solves that.
    import datetime as _dt_wl

    if st.session_state.get("wf_run_trigger"):
        st.success(
            "🤖 **Auto-Pilot pipeline launched.** It runs in a separate console window — "
            "Layer 1 Chartink scans → Layer 2 Screener.in conviction filter → Layer 3 "
            "combined files → Layer 4 TradingView sync. Files below refresh automatically "
            "as each layer completes (typical run: 5–10 minutes)."
        )
        st.session_state["wf_run_trigger"] = False  # consume the flag

    section("🤖 Latest Auto-Pilot Output")

    _ap_root = os.path.dirname(os.path.abspath(__file__))
    # Layer 2 (conviction-filtered) FINAL_*_Picks.csv files
    _ap_final_files = [
        ("🐂 Hunter Picks",          "FINAL_Hunter_Picks.csv"),
        ("🔄 Pullback Picks",        "FINAL_Pullback_Picks.csv"),
        ("🌅 EarlyBird Picks",       "FINAL_EarlyBird_Picks.csv"),
        ("👑 Leader Picks",          "FINAL_Leader_Picks.csv"),
        ("🔻 Recovery Climax",       "FINAL_Recovery_ClimaxBounce.csv"),
        ("📈 Recovery EarlyBirds",   "FINAL_Recovery_EarlyBirds.csv"),
        ("⚡ Recovery RS Leaders",   "FINAL_Recovery_RSLeaders.csv"),
    ]
    # Layer 3 — combined + golden
    _ap_combined_files = [
        ("📦 Combined Bull Picks",      "FINAL_COMBINED_BULL_PICKS.csv"),
        ("📦 Combined Recovery Picks",  "FINAL_COMBINED_RECOVERY_PICKS.csv"),
        ("📦 Combined All Picks",       "FINAL_COMBINED_PICKS.csv"),
        ("🏆 Golden Matcher Watchlist", "FINAL_WATCHLIST.csv"),
    ]

    def _ap_file_meta(fname):
        """Return (rows, mtime_str, age_h) for a CSV in project root, or (None, '—', None)."""
        p = os.path.join(_ap_root, fname)
        if not os.path.exists(p):
            return None, "—", None
        try:
            df_t = pd.read_csv(p)
            mt = _dt_wl.datetime.fromtimestamp(os.path.getmtime(p))
            age_h = (_dt_wl.datetime.now() - mt).total_seconds() / 3600.0
            return len(df_t), mt.strftime("%d %b %H:%M"), age_h
        except Exception:
            return None, "—", None

    # Top status strip — quick health-check across all FINAL_*.csv files
    _ap_total_rows = 0
    _ap_freshest_age = None
    for _label, _fname in _ap_final_files + _ap_combined_files:
        rows, _ts, age_h = _ap_file_meta(_fname)
        if rows is not None:
            _ap_total_rows += rows
            if _ap_freshest_age is None or (age_h is not None and age_h < _ap_freshest_age):
                _ap_freshest_age = age_h

    _ap_c1, _ap_c2, _ap_c3 = st.columns(3)
    _ap_c1.metric("FINAL_*.csv files present",
                  sum(1 for _, f in (_ap_final_files + _ap_combined_files)
                      if os.path.exists(os.path.join(_ap_root, f))))
    _ap_c2.metric("Total rows across all picks", f"{_ap_total_rows:,}")
    _ap_c3.metric("Freshest file age",
                  f"{_ap_freshest_age:.1f}h" if _ap_freshest_age is not None else "—",
                  delta="stale (>28h)" if _ap_freshest_age and _ap_freshest_age > 28 else "fresh",
                  delta_color="inverse" if _ap_freshest_age and _ap_freshest_age > 28 else "normal")

    # Two-column file inventory: Layer 2 (per-strategy) on left, Layer 3 (combined) on right
    _ap_left, _ap_right = st.columns(2, gap="medium")

    with _ap_left:
        st.markdown("**Layer 2 — Per-Strategy Picks (Conviction-Filtered)**")
        for _label, _fname in _ap_final_files:
            rows, ts, age_h = _ap_file_meta(_fname)
            if rows is None:
                st.caption(f"{_label} · `{_fname}` · _not found_")
            else:
                _stale_tag = " ⚠️" if age_h and age_h > 28 else ""
                with st.expander(f"{_label} — **{rows}** picks  ·  {ts}{_stale_tag}", expanded=False):
                    try:
                        df_view = pd.read_csv(os.path.join(_ap_root, _fname))
                        st.dataframe(df_view, use_container_width=True, hide_index=True,
                                     height=min(40 + 35 * len(df_view), 400))
                    except Exception as _e:
                        st.error(f"Failed to load: {_e}")

    with _ap_right:
        st.markdown("**Layer 3 — Combined & Golden Matcher**")
        for _label, _fname in _ap_combined_files:
            rows, ts, age_h = _ap_file_meta(_fname)
            if rows is None:
                st.caption(f"{_label} · `{_fname}` · _not found_")
            else:
                _stale_tag = " ⚠️" if age_h and age_h > 28 else ""
                _expand = (_fname == "FINAL_WATCHLIST.csv")  # auto-expand the golden one
                with st.expander(f"{_label} — **{rows}** picks  ·  {ts}{_stale_tag}", expanded=_expand):
                    try:
                        df_view = pd.read_csv(os.path.join(_ap_root, _fname))
                        st.dataframe(df_view, use_container_width=True, hide_index=True,
                                     height=min(40 + 35 * len(df_view), 500))
                    except Exception as _e:
                        st.error(f"Failed to load: {_e}")

    st.caption(
        "Files generated by **🤖 Run Auto-Pilot** (sidebar button) or `python run_pipeline.py`. "
        "Per Bible §6E, the Golden Matcher Watchlist (`FINAL_WATCHLIST.csv`) is the single best "
        "file to load into TradingView for Phase 3 validation."
    )

    # ── Pipeline Health & Targeted Regeneration ─────────────────────────────
    # 10 May 2026 — answers two questions:
    #   1. Which CSVs were not generated (or are stale)?
    #   2. How do I regenerate ONE without re-running the whole 5–10 min Auto-Pilot?
    #
    # Each row shows status (✅ fresh / ⚠ stale / ❌ missing) + a "Re-run this only"
    # button that fires the specific script for that file. Saves time when only
    # one Chartink scan failed or only the Bull Screener needs a refresh.
    st.markdown("---")
    section("🩺 Pipeline Health & Targeted Regeneration")
    st.caption(
        "Status of every file in the discovery pipeline. Click **Re-run** on any "
        "row to regenerate that file specifically — no need to re-run the full "
        "Auto-Pilot for one missing CSV."
    )

    # 10 May 2026: launch_script() fires a subprocess in a SEPARATE console
    # window and returns immediately. Streamlit re-renders before the
    # subprocess writes the file, so the panel shows OLD mtimes. Streamlit
    # has no way to know when the subprocess finishes. Manual refresh button
    # below lets the user re-render the panel after the script's console
    # window closes (visible cue that the run completed).
    _ph_rfc1, _ph_rfc2 = st.columns([1, 5])
    with _ph_rfc1:
        if st.button("🔄 Refresh status", key="ph_refresh",
                     help="Re-read all CSV mtimes + row counts. Click this AFTER "
                          "a launched subprocess's console window closes."):
            st.rerun()
    with _ph_rfc2:
        st.caption(
            "ℹ️ **After clicking Re-run** on any row below: a separate console "
            "window opens and runs the script. **Wait until the console window "
            "closes** (typically 30-60s for a single Chartink scan, ~2 min for "
            "the matcher), then click **🔄 Refresh status** above to see the "
            "updated row counts and timestamps."
        )

    import datetime as _dt_ph
    _ph_root = os.path.dirname(os.path.abspath(__file__))

    # ── File registry — maps file → generator script + args ─────────────────
    # Layer 1 = raw Chartink scans (chartink_scanner_pro.py <id>)
    # Layer 2 = conviction-filtered FINAL_*_Picks.csv (brute_force_match_pro.py)
    # Layer 3 = combined files (also brute_force_match_pro.py)
    # Standalone screeners run independently from each tab's Run button
    _ph_layers = [
        ("🥇 Layer 1 — Raw Chartink Scans (chartink_scanner_pro.py)", [
            ("Stage2_Hunter.csv",            "chartink_scanner_pro.py", "1", "Bull · Hunter"),
            ("Stage2_Pullback.csv",          "chartink_scanner_pro.py", "2", "Bull · Pullback"),
            ("Early_Birds.csv",              "chartink_scanner_pro.py", "3", "Bull · EarlyBird"),
            ("Strong_Leaders.csv",           "chartink_scanner_pro.py", "4", "Bull · Leader"),
            ("Recovery_RS_Survivors.csv",    "chartink_scanner_pro.py", "5", "Recovery · RS"),
            ("Recovery_Climax_Bounce.csv",   "chartink_scanner_pro.py", "6", "Recovery · Climax"),
            ("Recovery_Early_Birds.csv",     "chartink_scanner_pro.py", "7", "Recovery · EarlyBird"),
        ]),
        ("🧬 Layer 2 — Conviction-Filtered FINAL_*_Picks (brute_force_match_pro.py)", [
            ("FINAL_Hunter_Picks.csv",          "brute_force_match_pro.py", None, "Bull · Hunter"),
            ("FINAL_Pullback_Picks.csv",        "brute_force_match_pro.py", None, "Bull · Pullback"),
            ("FINAL_EarlyBird_Picks.csv",       "brute_force_match_pro.py", None, "Bull · EarlyBird"),
            ("FINAL_Leader_Picks.csv",          "brute_force_match_pro.py", None, "Bull · Leader"),
            ("FINAL_Recovery_RSLeaders.csv",    "brute_force_match_pro.py", None, "Recovery · RS"),
            ("FINAL_Recovery_ClimaxBounce.csv", "brute_force_match_pro.py", None, "Recovery · Climax"),
            ("FINAL_Recovery_EarlyBirds.csv",   "brute_force_match_pro.py", None, "Recovery · EarlyBird"),
        ]),
        ("📦 Layer 3 — Combined & Golden (brute_force_match_pro.py)", [
            ("FINAL_COMBINED_BULL_PICKS.csv",     "brute_force_match_pro.py", None, "Combined Bull union"),
            ("FINAL_COMBINED_RECOVERY_PICKS.csv", "brute_force_match_pro.py", None, "Combined Recovery union"),
            ("FINAL_COMBINED_PICKS.csv",          "brute_force_match_pro.py", None, "Everything, deduped"),
            ("FINAL_WATCHLIST.csv",               "brute_force_match_pro.py", None, "Golden Matcher conviction-ranked"),
        ]),
        ("🐂 Standalone Live Screeners (run from HUNTER tabs)", [
            ("Bull_Screener_Results.csv",     "bull_screener.py",     None, "HUNTER → 🐂 Bull Screener"),
            ("Recovery_Screener_Results.csv", "recovery_screener.py", None, "HUNTER → 🔄 Recovery Screener"),
            ("FINAL_XRay_Picks.csv",     "xray_screener_job.py", None, "HUNTER → 🧬 X-Ray Screener"),
        ]),
    ]

    def _ph_status(file_path):
        """Return (badge, color, mtime_str, age_h) for a file.

        Row-count-aware (10 May 2026 update). Five distinct states:
            ❌ Missing         — file doesn't exist
            ⚪ 0 entries       — fresh + empty (ran today, no signals)
            ✅ N entries       — fresh + has data
            ⚠ Stale: N entries → ranges back to N rows from when last good
            ⚠ Stale: 0 entries → empty AND old
        """
        if not os.path.exists(file_path):
            return ("❌ Missing", "var(--bear)", "—", None)
        mtime = _dt_ph.datetime.fromtimestamp(os.path.getmtime(file_path))
        age_h = (_dt_ph.datetime.now() - mtime).total_seconds() / 3600
        ts = mtime.strftime("%d %b  %H:%M")
        # Count data rows
        try:
            _n_rows = len(pd.read_csv(file_path))
        except Exception:
            _n_rows = None
        _ent_str = (f"{_n_rows} entries" if _n_rows is not None else "?? entries")
        if age_h > 28:
            return (f"⚠ Stale: {_ent_str} ({age_h:.0f}h)", "var(--warn)", ts, age_h)
        if _n_rows == 0:
            return (f"⚪ 0 entries ({age_h:.1f}h ago)", "#7a92a6", ts, age_h)
        return (f"✅ {_ent_str} ({age_h:.1f}h)", "var(--bull)", ts, age_h)

    for layer_label, files in _ph_layers:
        st.markdown(f"**{layer_label}**")
        for fname, script, arg, note in files:
            fpath = os.path.join(_ph_root, fname)
            badge, color, ts, age_h = _ph_status(fpath)
            _r1, _r2, _r3, _r4 = st.columns([3, 2, 2, 2])
            _r1.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                f'color:var(--ink);">{fname}</div>'
                f'<div style="font-size:0.66rem;color:var(--ink);">{note}</div>',
                unsafe_allow_html=True
            )
            _r2.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                f'color:{color};font-weight:600;">{badge}</div>',
                unsafe_allow_html=True
            )
            _r3.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;'
                f'color:#9ba8b6;">{ts}</div>',
                unsafe_allow_html=True
            )
            with _r4:
                _btn_key = f"ph_regen_{fname.replace('.', '_')}"
                _btn_label = (f"▶ Re-run scan {arg}" if arg
                               else "▶ Re-run script")
                if st.button(_btn_label, key=_btn_key, use_container_width=True):
                    try:
                        if arg:
                            launch_script(script, arg)
                        else:
                            launch_script(script)
                        st.toast(
                            f"🚀 Launched {script} {arg or ''}. "
                            f"Wait for its console window to close, then click "
                            f"🔄 Refresh status above.".strip(),
                            icon="🚀",
                        )
                    except Exception as _e:
                        st.error(f"Launch failed: {_e}")
        st.markdown("")  # vertical breathing room between layer groups

    # Quick legend / regen guidance
    with st.expander("ℹ️ When to use which regeneration", expanded=False):
        st.markdown(
            "- **One Chartink scan failed** (e.g. Stage2_Hunter.csv missing): "
            "click the **▶ Re-run scan N** button on that row. ~10 seconds.\n"
            "- **Layer 2 / Layer 3 missing** (FINAL_*.csv files): the matcher "
            "needs Layer 1 to be present first. Check Layer 1 health, then "
            "click **▶ Re-run script** on any Layer 2/3 row — `brute_force_match_pro.py` "
            "regenerates ALL Layer 2 + Layer 3 outputs in one go (~2 min).\n"
            "- **Bull / Recovery / X-Ray Screener results stale**: these are "
            "INDEPENDENT of Auto-Pilot. They only refresh when you click their "
            "Run button on the respective HUNTER tab. The links in the right "
            "column are shortcuts.\n"
            "- **Everything missing or you want a clean refresh**: use the "
            "**🤖 Run Auto-Pilot** button in the sidebar (runs Layer 1 → Layer 2 → "
            "Layer 3 → Layer 4 sync in one shot, ~5–10 min)."
        )

    st.markdown("---")
    section("Sync & Tools")

    _wl1, _wl2, _wl3, _wl4, _wl5, _wl6, _wl7, _wl8 = st.tabs(
        ["🏗️ Generate", "☁️ Sync Cloud", "🏆 Smart Rank",
         "🏭 Sectors DB", "💾 Data Cache", "⚙️ Pipeline Status",
         "⏪ Replay", "📜 Track Record"]
    )

    with _wl1:
        left_col, right_col = st.columns(2, gap="medium")
        with left_col:
            section("1. Local Generation")
            if st.button("📁  Generate CSVs — Local\nGenerate clean CSVs for local analysis.\n→  Generate Now", key="wl_gen"):
                launch_script("watchlist_manager.py")
        with right_col:
            section("2. TV Pine Screener Generator")
            st.info("Upload a TradingView Watchlist (.txt) to automatically generate your Ultimate Screener indicator.")
            uploaded_wl = st.file_uploader("Upload Watchlist (.txt)", type=["txt"])
            if uploaded_wl is not None:
                raw_text = uploaded_wl.read().decode("utf-8")
                raw_syms = [s.strip() for s in raw_text.replace(',', '\n').split('\n') if s.strip()]
                # BUG-L6 / REC-9: Pine Screener hard cap is ~40 symbols per indicator
                _PINE_CAP = 40
                if len(raw_syms) > _PINE_CAP:
                    st.warning(
                        f"⚠️ **Pine Screener symbol cap:** TradingView Pine indicators support "
                        f"~{_PINE_CAP} symbols before hitting the execution time limit. "
                        f"You uploaded {len(raw_syms)} symbols — the generated script will include "
                        f"all of them but may show a 'Script execution timed out' error on TV. "
                        f"Consider splitting into two watchlists of ≤{_PINE_CAP} symbols each."
                    )
                pine_code = generate_pine_code(raw_syms)
                st.download_button(label="⬇️ Download Generated .pine", data=pine_code,
                                   file_name="Commander_Screener_Custom.pine", mime="text/plain")

    with _wl2:
        section("2. External Cloud Sync")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            # 13-Sep-2026: Strike.Money lapsed; RRG Studio (local) lists the same TXTs.
            if st.button("📈  Sync to RRG Studio\nRefresh the Commander lists in RRG Studio.\n→  Sync Now", use_container_width=True, key="wl_rrg_studio"):
                try:
                    import commander_watchlists as _cwl
                    _cws = _cwl.sync(verbose=False)
                    _msg = f"RRG Studio: {_cws['populated']}/{_cws['total']} lists written"
                    if _cws["stale"]:
                        _msg += f" · stale: {', '.join(_cws['stale'])}"
                    (st.warning if (_cws["empty"] or _cws["missing"]) else st.success)(_msg)
                except Exception as _e:
                    st.error(f"RRG Studio sync failed: {_e}")
        with c2:
            if st.button("📊  Sync to TradingView\nSync curated lists to TradingView.\n→  Sync Now", use_container_width=True, key="wl_tv"):
                launch_script("tradingview_automation_v2.py")
        with c3:
            if st.button("🔁  Master Sync — All\nPush to all connected platforms simultaneously.\n→  Sync All", type="primary", use_container_width=True, key="wl_master"):
                launch_script("master_portfolio_sync.py")
        section("3. Email Dispatches")
        c4, c5 = st.columns(2, gap="small")
        with c4:
            if st.button("📧  Send Test Email\nVerify SMTP Connection.\n→  Send Now", use_container_width=True, key="wl_em_test"):
                launch_script("gmail_dispatcher.py", "--mode test")
        with c5:
            if st.button("🏆  Email Golden Matches\nSend latest AI 5-Star picks to your inbox.\n→  Send Now", use_container_width=True, key="wl_em_match"):
                launch_script("gmail_dispatcher.py", "--mode matches")

    with _wl3:
        section("Smart Rank — Weinstein Setup Scorer")
        st.caption("Scores each stock 0–100 across Stage 2 status, RS vs CNX500, "
                   "52W position, volume surge and SMA200 slope. "
                   "Auto-loads symbols from watchlist CSVs in your project folder.")

        if not _RANKER_OK:
            st.error("❌ watchlist_ranker module not available.")
        else:
            # Symbol source
            _wr_auto = load_watchlist_symbols()
            _wr_src  = st.radio("Symbol source",
                                ["📂 Auto-load from watchlist CSVs",
                                 "✏️ Manual entry"],
                                horizontal=True, key="wr_src")

            if _wr_src == "📂 Auto-load from watchlist CSVs":
                if _wr_auto:
                    st.caption(f"Found **{len(_wr_auto)}** symbols in watchlist CSVs")
                    _wr_syms = _wr_auto
                else:
                    st.warning("No watchlist CSVs found. Run HUNTER scanners first, or switch to manual entry.")
                    _wr_syms = []
            else:
                _wr_raw = st.text_area("Enter symbols (one per line or comma-separated)",
                                       height=120, key="wr_manual",
                                       placeholder="RELIANCE\nINFY\nHDFCBANK\nTCS")
                _wr_syms = [s.strip() for s in
                            _wr_raw.replace(",", "\n").split("\n") if s.strip()]

            _wr_period = st.selectbox("Lookback period", ["3mo", "6mo", "1y"],
                                      index=1, key="wr_period")

            if _wr_syms and st.button("🏆 Rank Setups", key="wr_run",
                                       type="primary", use_container_width=True):
                with st.spinner(f"Scoring {len(_wr_syms)} stocks — fetching price data…"):
                    try:
                        _wr_df = rank_watchlist(_wr_syms, period=_wr_period)
                    except Exception as _wre:
                        _wr_df = pd.DataFrame()
                        st.error(f"Ranking failed: {_wre}")

                if not _wr_df.empty:
                    st.session_state["wr_last_df"] = _wr_df
                else:
                    st.warning("No results — check symbol names or network.")

            # Display cached result
            if st.session_state.get("wr_last_df") is not None:
                _wr_res = st.session_state["wr_last_df"]

                # Summary metrics
                _wr_s2  = int((_wr_res["Stage"].str.contains("Stage 2")).sum())
                _wr_top = int((_wr_res["Score"] >= 65).sum())
                _wr_c1, _wr_c2, _wr_c3, _wr_c4 = st.columns(4, gap="small")
                _wr_c1.metric("Stocks Ranked",  len(_wr_res))
                _wr_c2.metric("Stage 2",        _wr_s2)
                _wr_c3.metric("Grade A+ / A",   _wr_top)
                _wr_c4.metric("Top Score",
                              f"{_wr_res['Score'].iloc[0]:.1f}" if len(_wr_res) else "–")

                st.markdown("---")
                # Colour-coded table
                def _wr_colour(val):
                    if isinstance(val, str):
                        if "Stage 2" in val: return "color: var(--bull)"
                        if "Stage 4" in val: return "color: var(--bear)"
                        if "A+" in val:      return "color: var(--bull); font-weight:700"
                        if val == "⭐⭐ A":   return "color: var(--acc)"
                    return ""

                _wr_disp = _wr_res[["Symbol","Score","Grade","Stage","LTP",
                                     "RS_3M%","RS_Edge%","52W_Pos%","Vol_Surge"]].copy()
                # 10 May 2026: round numeric columns to 2 decimals so the table
                # reads cleanly (was showing values like 1.42857142857… for
                # Vol_Surge etc.).
                _wr_num_cols = ["Score", "LTP", "RS_3M%", "RS_Edge%",
                                 "52W_Pos%", "Vol_Surge"]
                _wr_styler = (_wr_disp.style
                              .applymap(_wr_colour, subset=["Grade","Stage"])
                              .format({c: "{:.2f}" for c in _wr_num_cols
                                        if c in _wr_disp.columns}))
                st.dataframe(
                    _wr_styler,
                    use_container_width=True, hide_index=True,
                )
                st.download_button(
                    "📥 Download Rankings (CSV)",
                    data=_wr_res.to_csv(index=False).encode("utf-8"),
                    file_name=f"WatchlistRank_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="wr_dl",
                )

    # ── TAB 4 — SECTORS DB (unified Pine ↔ Python sector mapping) ────────
    with _wl4:
        section("Unified Sector Database")
        st.caption(
            "Single source of truth for stock→sector mappings, shared between "
            "the Pine Dashboard family and the Python pipeline. "
            "Curated entries come from `Weinstein and Swing Pro Dashboard v67`."
        )
        try:
            import sector_lookup as _sl
            _sl.refresh_cache()
            _sl_stats = _sl.stats()
        except Exception as _sle:
            _sl_stats = {}
            st.error(f"sector_lookup unavailable: {_sle}")

        if not _sl_stats.get("db_exists"):
            st.warning(
                "**sectors.db not found.** Run `python sector_manager.py` once "
                "in the project folder to build it from the v67 Pine block + "
                "legacy `sector_db.json`."
            )
        else:
            _sd_c1, _sd_c2, _sd_c3, _sd_c4 = st.columns(4, gap="small")
            _sd_c1.metric("Symbols",  _sl_stats.get("total_symbols", 0))
            _sd_c2.metric("Sectors",  _sl_stats.get("total_sectors", 0))
            _sd_c3.metric("Aliases",  _sl_stats.get("total_aliases", 0))
            _sd_c4.metric(
                "Last Update",
                str(_sl_stats.get("last_update", "—"))[:16] if _sl_stats.get("last_update") else "—",
            )

            _by_src = _sl_stats.get("by_source", {})
            if _by_src:
                st.markdown("**By source**")
                _src_rows = [{"source": s, "count": c} for s, c in
                             sorted(_by_src.items(), key=lambda x: -x[1])]
                st.dataframe(pd.DataFrame(_src_rows), hide_index=True,
                             use_container_width=False)

            st.markdown("---")
            section("Sector Index Coverage")
            try:
                _sec_df = _sl.list_sectors()
                if not _sec_df.empty:
                    _disp = _sec_df[["sector_index", "display_name", "yf_ticker",
                                      "fallback", "stock_count", "is_broad"]].copy()
                    st.dataframe(_disp, hide_index=True, use_container_width=True)
            except Exception as _sde:
                st.error(f"Sector list error: {_sde}")

            st.markdown("---")
            section("Lookup")
            _lu_c1, _lu_c2 = st.columns([2, 3], gap="small")
            with _lu_c1:
                _lu_sym = st.text_input(
                    "Symbol", placeholder="e.g. RELIANCE, NSE:TCS-EQ, M_M",
                    key="sd_lookup_sym",
                )
            with _lu_c2:
                if _lu_sym:
                    _rec = _sl.get_sector(_lu_sym)
                    if _rec:
                        st.success(
                            f"**{_rec['symbol']}** → **{_rec['sector_index']}** "
                            f"({_rec.get('display_name') or _rec['sector_name']})  ·  "
                            f"yf=`{_sl.sector_to_yf(_rec['sector_index'])}`  ·  "
                            f"source=`{_rec['source']}`  ·  "
                            f"confidence=`{_rec['confidence']}`"
                        )
                    else:
                        st.warning(
                            f"`{_lu_sym}` not in DB. Run `python sector_manager.py "
                            f"refresh-yf --symbols {_lu_sym}` to fetch from yfinance."
                        )

            st.markdown("---")
            section("Maintenance")
            _mt_c1, _mt_c2, _mt_c3 = st.columns(3, gap="small")
            with _mt_c1:
                if st.button(
                    "🔄  Re-import v67 Pine\nIngest the curated block.\n→  Run",
                    key="sd_imp_pine", use_container_width=True,
                ):
                    launch_script(
                        "sector_manager.py",
                        'import-pine "Weinstein and Swing Pro Dashboard v67.3.pine"',
                    )
            with _mt_c2:
                if st.button(
                    "🌐  Refresh from yfinance\nUpdate auto-sourced rows only.\n→  Run",
                    key="sd_ref_yf", use_container_width=True,
                ):
                    launch_script("sector_manager.py", "refresh-yf")
            with _mt_c3:
                if st.button(
                    "📊  Re-run Audit\nPrint DB statistics.\n→  Run",
                    key="sd_audit", use_container_width=True,
                ):
                    launch_script("sector_manager.py", "audit")

            st.caption(
                "Two-way sync: edit `sectors.db` (or re-import a newer Pine "
                "version) → run `python sector_manager.py export-pine "
                "<dashboard.pine>` to write the updated `<DB_LOOKUP_START>` "
                "block back into your Pine file."
            )

    # ── TAB 5 — DATA CACHE (C1.13: parquet-cached OHLCV health) ──────────
    with _wl5:
        section("Unified OHLCV Cache")
        st.caption(
            "All screeners, the breadth engine, the rotation guard and the "
            "sniper pre-flight route through `data_provider`. Each symbol's "
            "OHLCV is stored once on disk (parquet when available) with a "
            "TTL by interval — daily=1h, weekly=24h, intraday=15min."
        )
        try:
            import data_provider as _dp_admin
            _cs = _dp_admin.stats()
        except Exception as _ce:
            _cs = {}
            st.error(f"data_provider unavailable: {_ce}")

        if _cs:
            _dc1, _dc2, _dc3, _dc4 = st.columns(4, gap="small")
            _dc1.metric("Cache Entries", _cs.get("entry_count", 0))
            _dc2.metric("Fresh", _cs.get("fresh", 0))
            _dc3.metric("Expired", _cs.get("expired", 0),
                         delta=None if _cs.get("expired", 0) == 0 else "evict",
                         delta_color="off")
            _dc4.metric("Disk Size", f"{_cs.get('total_size_mb', 0):.2f} MB")

            _dc5, _dc6, _dc7, _dc8, _dc9 = st.columns(5, gap="small")
            _dc5.metric("Format", _cs.get("format", "—"))
            _dc6.metric("Parquet OK", "yes" if _cs.get("parquet_available") else "no")
            _dc7.metric(
                "NSE Fallback (nselib)",
                "active" if _cs.get("nselib_available") else "—",
                help="nselib kicks in when yfinance returns empty for a daily "
                     "NSE-equity request. Primary working secondary provider.",
            )
            _dc8.metric(
                "NSE Fallback (nsepython)",
                "active" if _cs.get("nsepython_available") else "—",
                help="nsepython is the tertiary provider — currently fails to "
                     "parse NSE's response shape (KeyError 'data') as of v2.97. "
                     "Kept in case it gets fixed upstream.",
            )
            _oldest = _cs.get("oldest_age_hours")
            _dc9.metric(
                "Oldest Entry",
                f"{_oldest:.1f}h" if _oldest is not None else "—",
            )

            st.caption(f"📁 `{_cs.get('cache_dir')}`")

            st.markdown("---")
            section("Maintenance")
            _mc1, _mc2, _mc3 = st.columns(3, gap="small")
            with _mc1:
                if st.button(
                    "🧹  Clear Expired\nRemove only TTL-expired entries.\n→  Run",
                    key="dc_clear_expired", use_container_width=True,
                ):
                    try:
                        n = _dp_admin.clear_expired()
                        st.success(f"Removed {n} expired cache files.")
                    except Exception as _ee:
                        st.error(f"Clear-expired failed: {_ee}")
            with _mc2:
                if st.button(
                    "💣  Clear All\nWipe the entire OHLCV cache.\n→  Run",
                    key="dc_clear_all", use_container_width=True,
                ):
                    try:
                        n = _dp_admin.clear_cache()
                        st.warning(f"Removed all {n} cache files. Next fetch is cold.")
                    except Exception as _ce2:
                        st.error(f"Clear-all failed: {_ce2}")
            with _mc3:
                if st.button(
                    "🔄  Refresh Stats\nRecount on-disk entries.\n→  Run",
                    key="dc_refresh", use_container_width=True,
                ):
                    st.rerun()

            st.caption(
                "Set `USE_DATA_PROVIDER = False` at the top of any consumer "
                "module (bull_screener, recovery_screener, exit_signal_engine, "
                "rotation_guard, breadth_engine, watchlist_ranker, ai_risk_manager, "
                "market_regime, market_data_hub) to fall back to direct yfinance "
                "calls if the cache misbehaves."
            )

    # ── TAB 6 — PIPELINE STATUS (E9) ──────────────────────────────────────
    with _wl6:
        section("Auto-Pilot Pipeline Status")
        st.caption(
            "Per-phase status from the most recent `run_pipeline.py` run. "
            "`run_pipeline.py` writes `pipeline_status.json` after every phase "
            "boundary, so this tab reflects live progress while a pipeline is "
            "running and the final outcome afterwards."
        )
        try:
            import pipeline_status as _ps
            _ps_state = _ps.load_status()
        except Exception as _pse:
            _ps_state = {}
            st.error(f"pipeline_status unavailable: {_pse}")

        if not _ps_state:
            st.info(
                "📋 No `pipeline_status.json` yet. Trigger the **Complete "
                "Workflow** button on the Dashboard to run the pipeline — "
                "this tab will populate as each phase completes."
            )
        else:
            _phases = _ps_state.get("phases", []) or []
            _started = _ps_state.get("started_at", "—")
            _ended   = _ps_state.get("ended_at")
            _current = _ps_state.get("current")
            _total_s = _ps.total_duration(_ps_state)

            # Top metrics row
            _ok   = sum(1 for p in _phases if p.get("status") == "OK")
            _fail = sum(1 for p in _phases if p.get("status") == "FAIL")
            _skip = sum(1 for p in _phases if p.get("status") == "SKIP")
            _run  = sum(1 for p in _phases if p.get("status") == "RUNNING")

            _ms1, _ms2, _ms3, _ms4, _ms5 = st.columns(5, gap="small")
            _ms1.metric("Phases OK",     _ok)
            _ms2.metric("Failed",        _fail,
                          delta=None if _fail == 0 else f"-{_fail}",
                          delta_color="inverse" if _fail else "normal")
            _ms3.metric("Skipped",       _skip)
            _ms4.metric("Running",       _run)
            _ms5.metric("Total Time",    f"{_total_s:.1f}s")

            if _current and not _ended:
                st.warning(f"🔄 **In progress** — current phase: `{_current}`")
            elif _ended:
                st.success(f"✅ Run completed at `{_ended[:19]}` "
                            f"(started `{_started[:19]}`)")

            # Per-phase grid
            if _phases:
                _rows = []
                for p in _phases:
                    _stat = p.get("status", "?")
                    _icon = ("✅" if _stat == "OK"
                               else "❌" if _stat == "FAIL"
                               else "⏭" if _stat == "SKIP"
                               else "🔄")
                    _dur = p.get("duration_s")
                    _rec = p.get("records")
                    _rows.append({
                        "":         _icon,
                        "Phase":    p.get("name", "?"),
                        "Status":   _stat,
                        "Duration": f"{_dur:.1f}s" if _dur is not None else "—",
                        "Records":  _rec if _rec is not None else "—",
                        "Last Run": (p.get("ended_at", "—") or "—")[11:19],
                        "Message":  (p.get("message", "") or "")[:80],
                    })
                _df_ps = pd.DataFrame(_rows)
                st.dataframe(_df_ps, hide_index=True, use_container_width=True)

                # Surface failures prominently
                _fails = [p for p in _phases if p.get("status") == "FAIL"]
                for fp in _fails:
                    st.error(
                        f"❌ **{fp.get('name')}** failed after "
                        f"{fp.get('duration_s', 0):.1f}s — {fp.get('message', '')}"
                    )

            with st.expander("Raw status payload"):
                st.json(_ps_state)

    # ── TAB 7 — REPLAY (E10) ───────────────────────────────────────────────
    with _wl7:
        section("Screener Replay — As-of-Date Backtest")
        st.caption(
            "Re-run a screener as of any historical date and grade the picks "
            "against their actual N-day forward returns. data_provider pins "
            "every OHLCV slice to that date so SMAs / RSI / Mansfield / VCP "
            "see exactly what they would have seen on the day."
        )

        try:
            import replay as _replay
        except Exception as _re:
            st.error(f"replay module unavailable: {_re}")
            _replay = None

        if _replay is not None:
            from datetime import date as _date_t, timedelta as _td_t
            _r_c1, _r_c2, _r_c3, _r_c4 = st.columns([2, 2, 2, 2], gap="small")
            with _r_c1:
                _r_date = st.date_input(
                    "As-of date",
                    value=_date_t.today() - _td_t(days=90),
                    max_value=_date_t.today() - _td_t(days=1),
                    key="rp_date",
                )
            with _r_c2:
                _r_screener = st.selectbox(
                    "Screener",
                    ["Bull (custom basket)", "Bull (default watchlist)", "Recovery"],
                    key="rp_screener",
                )
            with _r_c3:
                _r_forward = st.number_input(
                    "Forward (trading days)", min_value=5, max_value=120,
                    value=30, step=5, key="rp_forward",
                )
            with _r_c4:
                st.write("")  # spacer
                _r_go = st.button("⏪  Run Replay", type="primary",
                                    use_container_width=True, key="rp_go")

            _r_syms = None
            if _r_screener == "Bull (custom basket)":
                _r_basket = st.text_area(
                    "Custom basket (comma or newline separated, NSE symbols)",
                    value="HDFCBANK, TCS, RELIANCE, INFY, ITC, BHARTIARTL, LT, SBIN",
                    height=80, key="rp_basket",
                )
                _r_syms = [s.strip() for s in _r_basket.replace(",", "\n").split("\n")
                            if s.strip()]

            if _r_go:
                _as_of = str(_r_date)
                with st.spinner(f"Running replay @ {_as_of} …"):
                    try:
                        if _r_screener == "Recovery":
                            _r_result = _replay.run_recovery_replay(_as_of, int(_r_forward))
                        elif _r_screener == "Bull (default watchlist)":
                            _r_result = _replay.run_bull_replay(_as_of, int(_r_forward))
                        else:
                            _r_result = _replay.run_bull_replay(
                                _as_of, int(_r_forward), symbols=_r_syms,
                            )
                        st.session_state["rp_last"] = _r_result
                    except Exception as _re2:
                        st.error(f"Replay failed: {_re2}")

            _r_last = st.session_state.get("rp_last")
            if _r_last:
                _summary = _r_last.get("summary", {}) or {}
                _bench   = _r_last.get("benchmark_pct")
                _picks_df = _r_last.get("picks", pd.DataFrame())
                _perf_df  = _r_last.get("performance", pd.DataFrame())

                st.markdown("---")
                section(f"Result: {_r_last['as_of']} → +{_r_last['forward_days']} trading days")

                _m1, _m2, _m3, _m4, _m5 = st.columns(5, gap="small")
                _m1.metric("Picks", len(_picks_df))
                _m2.metric("Win rate", f"{_summary.get('win_rate_pct', 0):.1f}%"
                              if _summary.get("n_complete") else "—")
                _m3.metric("Avg return",
                              f"{_summary.get('avg_return_pct', 0):+.2f}%"
                              if _summary.get("n_complete") else "—")
                _m4.metric("Benchmark", f"{_bench:+.2f}%" if _bench is not None else "—")
                _alpha = _summary.get("alpha_vs_bench")
                _m5.metric(
                    "Alpha vs bench",
                    f"{_alpha:+.2f}%" if _alpha is not None else "—",
                    delta=None if _alpha is None
                          else (f"{_alpha:+.2f}%" if _alpha != 0 else None),
                    delta_color="normal" if _alpha is None or _alpha >= 0 else "inverse",
                )

                if not _perf_df.empty:
                    section("Forward Performance")
                    # Merge picks + performance for single combined view
                    _show_cols = ["Symbol", "Entry_Close", "Forward_Close",
                                   "Return_pct", "Forward_Date", "Status"]
                    _disp = _perf_df[[c for c in _show_cols if c in _perf_df.columns]].copy()
                    if not _picks_df.empty and "Symbol" in _picks_df.columns:
                        _join_cols = [c for c in ["Catalyst", "Score",
                                                    "VCP_Valid", "VCP_Score",
                                                    "Pivot_Price"]
                                        if c in _picks_df.columns]
                        if _join_cols:
                            _disp = _disp.merge(
                                _picks_df[["Symbol"] + _join_cols],
                                on="Symbol", how="left",
                            )
                    _disp = _disp.sort_values(
                        "Return_pct", ascending=False, na_position="last",
                    ).reset_index(drop=True)
                    st.dataframe(_disp, hide_index=True, use_container_width=True)

                    st.download_button(
                        "📥 Download Replay CSV",
                        data=_disp.to_csv(index=False).encode("utf-8"),
                        file_name=f"replay_{_r_last['as_of']}.csv",
                        mime="text/csv",
                        key="rp_dl",
                    )
                    st.caption(f"Saved to `{_r_last['out_csv']}`")

                with st.expander("Raw summary payload"):
                    st.json({k: v for k, v in _summary.items()})

            # ── 12-month validation (multi-anchor backtest) ──────────────────
            st.markdown("---")
            section("12-Month Validation Backtest")
            st.caption(
                "Runs the bull screener at monthly anchors over the last "
                "N months on a fixed Nifty 100 universe. Set filters to "
                "measure the screener's *selection* edge vs the universe's "
                "drift. Each anchor takes ~45s on a cold cache; subsequent "
                "runs are cache hits."
            )
            try:
                import validation as _val
            except Exception as _ve:
                _val = None
                st.error(f"validation module unavailable: {_ve}")

            if _val is not None:
                _v_c1, _v_c2, _v_c3, _v_c4 = st.columns(4, gap="small")
                with _v_c1:
                    _v_months = st.number_input(
                        "Months back", min_value=3, max_value=24,
                        value=12, step=3, key="val_months",
                    )
                with _v_c2:
                    _v_forward = st.number_input(
                        "Forward (TD)", min_value=5, max_value=120,
                        value=30, step=5, key="val_forward",
                    )
                with _v_c3:
                    _v_topn = st.number_input(
                        "Top-N filter (0=all)",
                        min_value=0, max_value=50, value=10, step=5,
                        key="val_topn",
                        help="Keep only the top-N picks by Score per anchor. "
                             "0 = no filter (baseline universe).",
                    )
                with _v_c4:
                    _v_cat = st.checkbox(
                        "Require catalyst",
                        value=False, key="val_cat",
                        help="Only count picks where Catalyst != 'None'.",
                    )

                _v_go = st.button(
                    f"⏱  Run validation ({int(_v_months)} anchors × Nifty 100, "
                    f"~{int(_v_months)*45}s)",
                    type="primary", use_container_width=False, key="val_go",
                )

                if _v_go:
                    _topn_arg = int(_v_topn) if int(_v_topn) > 0 else None
                    with st.spinner(f"Running {int(_v_months)}-anchor validation … "
                                     "this can take several minutes on cold cache."):
                        try:
                            _v_res = _val.run_validation(
                                months_back=int(_v_months),
                                forward_days=int(_v_forward),
                                basket=None,
                                min_score=0,
                                require_catalyst=bool(_v_cat),
                                top_n=_topn_arg,
                            )
                            st.session_state["val_last"] = _v_res
                            st.success(f"Completed in {_v_res['aggregate'].get('duration_s',0):.0f}s")
                        except Exception as _ve2:
                            st.error(f"Validation failed: {_ve2}")

                # Show last result (live or loaded from disk)
                _v_last = st.session_state.get("val_last")
                if _v_last is None:
                    try:
                        _v_last = _val.load_last_validation()
                    except Exception:
                        _v_last = None

                if _v_last:
                    _v_agg = _v_last.get("aggregate", {}) or {}
                    _v_sum = _v_last.get("summary_df", pd.DataFrame())

                    st.markdown(
                        f"**Run `{_v_last.get('run_id','—')}`**  ·  "
                        f"{_v_agg.get('n_anchors','?')} anchors · "
                        f"{_v_agg.get('n_picks_total','?')} picks total · "
                        f"forward {_v_agg.get('forward_days','?')}d"
                    )

                    _va1, _va2, _va3, _va4, _va5 = st.columns(5, gap="small")
                    _va1.metric("Anchor Avg Alpha",
                                  f"{_v_agg.get('anchor_avg_alpha_pct', 0):+.2f}%"
                                  if _v_agg.get('anchor_avg_alpha_pct') is not None
                                  else "—")
                    _va2.metric("Median Alpha",
                                  f"{_v_agg.get('anchor_median_alpha_pct', 0):+.2f}%"
                                  if _v_agg.get('anchor_median_alpha_pct') is not None
                                  else "—")
                    _va3.metric("Alpha Hit Rate",
                                  f"{_v_agg.get('alpha_hit_rate_pct', 0):.1f}%"
                                  if _v_agg.get('alpha_hit_rate_pct') is not None
                                  else "—")
                    _va4.metric("Avg Win Rate",
                                  f"{_v_agg.get('anchor_avg_winrate_pct', 0):.1f}%"
                                  if _v_agg.get('anchor_avg_winrate_pct') is not None
                                  else "—")
                    _va5.metric("Best / Worst Anchor",
                                  f"{_v_agg.get('best_anchor_alpha',0):+.1f}% / "
                                  f"{_v_agg.get('worst_anchor_alpha',0):+.1f}%"
                                  if _v_agg.get('best_anchor_alpha') is not None
                                  else "—")

                    if not _v_sum.empty:
                        _show_v = _v_sum[[
                            "as_of", "picks_filtered", "picks_with_data",
                            "win_rate_pct", "avg_return_pct",
                            "benchmark_pct", "alpha_pct",
                        ]].copy()
                        st.dataframe(_show_v, hide_index=True,
                                       use_container_width=True)

                        # Alpha-over-time bar chart
                        try:
                            import plotly.express as _px
                            _chart_df = _v_sum.dropna(subset=["alpha_pct"]).copy()
                            if not _chart_df.empty:
                                _chart_df["color"] = _chart_df["alpha_pct"].apply(
                                    lambda x: "#22c55e" if x >= 0 else "var(--bear)"
                                )
                                _fig = _px.bar(
                                    _chart_df, x="as_of", y="alpha_pct",
                                    color="color", color_discrete_map="identity",
                                    title="Alpha vs Nifty 500 by anchor (positive = green)",
                                )
                                _fig.update_layout(showlegend=False, height=280,
                                                    paper_bgcolor="rgba(0,0,0,0)",
                                                    plot_bgcolor="rgba(0,0,0,0)",
                                                    font=dict(color="#E3EBEC"),
                                                    yaxis=dict(title="Alpha %",
                                                               gridcolor="#E2E8F0"),
                                                    xaxis=dict(gridcolor="#E2E8F0"))
                                _fig.add_hline(y=0, line_dash="dot",
                                                line_color="#B6C4C6")
                                st.plotly_chart(_fig, use_container_width=True)
                        except Exception:
                            pass

                        st.download_button(
                            "📥 Download Validation Summary (CSV)",
                            data=_v_sum.to_csv(index=False).encode("utf-8"),
                            file_name=f"validation_{_v_last['run_id']}.csv",
                            mime="text/csv", key="val_dl_sum",
                        )

                    with st.expander("Run config & aggregate (raw)"):
                        st.json(_v_agg)

    # ── TAB 8 — LIVE TRACK RECORD ──────────────────────────────────────────
    with _wl8:
        section("Live Pick Track Record")
        st.caption(
            "Every live screener run auto-logs its picks to `pick_log.db` "
            "(replay/validation runs are skipped). The evaluator computes "
            "the N-trading-day forward return for each pick once the window "
            "elapses — giving us a real-world track record that complements "
            "the 12-month replay backtest."
        )
        try:
            import pick_log as _pl_admin
            _pl_stats = _pl_admin.stats()
        except Exception as _ple:
            _pl_stats = {}
            st.error(f"pick_log unavailable: {_ple}")

        if not _pl_stats.get("db_exists") or _pl_stats.get("pick_count", 0) == 0:
            st.info(
                "📋 No live picks logged yet. As soon as you run the bull or "
                "recovery screener (HUNTER → Bull Screener tab, or via the "
                "auto-pilot pipeline), picks land here automatically."
            )
        else:
            _pl_c1, _pl_c2, _pl_c3, _pl_c4 = st.columns(4, gap="small")
            _pl_c1.metric("Total Picks Logged", _pl_stats.get("pick_count", 0))
            _pl_c2.metric("Evaluated",          _pl_stats.get("eval_count", 0))
            _pl_c3.metric("First Pick",         _pl_stats.get("first_pick") or "—")
            _pl_c4.metric("Last Pick",          _pl_stats.get("last_pick") or "—")

            _pl_btn_c1, _pl_btn_c2 = st.columns(2, gap="small")
            with _pl_btn_c1:
                _pl_fwd = st.number_input(
                    "Evaluation horizon (trading days)",
                    min_value=5, max_value=120, value=30, step=5,
                    key="pl_fwd",
                )
            with _pl_btn_c2:
                st.write("")
                if st.button(
                    "🔄  Evaluate pending picks "
                    "(fetch forward returns for picks ≥ horizon old)",
                    key="pl_eval", type="primary", use_container_width=True,
                ):
                    with st.spinner("Computing forward returns…"):
                        try:
                            _new = _pl_admin.evaluate_pending(int(_pl_fwd))
                            st.success(f"Wrote {_new} new evaluation(s).")
                            st.rerun()
                        except Exception as _eve:
                            st.error(f"Evaluation failed: {_eve}")

            st.markdown("---")
            section("Per-screener Summary")
            for _scr in (_pl_stats.get("screeners") or ["bull"]):
                try:
                    _sum = _pl_admin.summarize(_scr, forward_days=int(_pl_fwd))
                except Exception:
                    _sum = {"n": 0}
                if not _sum.get("n"):
                    st.caption(f"**{_scr}**: 0 evaluated picks at "
                                f"forward {int(_pl_fwd)}d (run evaluator above).")
                    continue
                _ss1, _ss2, _ss3, _ss4 = st.columns(4, gap="small")
                _ss1.metric(f"{_scr.title()} — Picks Evaluated", _sum["n"])
                _ss2.metric("Win Rate",      f"{_sum['win_rate_pct']:.1f}%")
                _ss3.metric("Avg Return",    f"{_sum['avg_return_pct']:+.2f}%")
                _ss4.metric("Median Return", f"{_sum['median_return_pct']:+.2f}%")
                st.caption(
                    f"  best: {_sum['best_pct']:+.2f}% ({_sum['best_symbol']})   "
                    f"worst: {_sum['worst_pct']:+.2f}% ({_sum['worst_symbol']})   "
                    f"window: {_sum['first_pick']} → {_sum['last_pick']}"
                )

            st.markdown("---")
            section("Recent Picks")
            try:
                _recent = _pl_admin.load_picks(limit=50)
            except Exception as _le:
                _recent = pd.DataFrame()
                st.error(f"load_picks failed: {_le}")
            if _recent.empty:
                st.caption("(no picks)")
            else:
                _show = _recent[["as_of_date", "screener", "symbol", "catalyst",
                                   "score", "entry_close", "forward_days",
                                   "forward_close", "return_pct"]].copy()
                _show.columns = ["Date", "Screener", "Symbol", "Catalyst",
                                  "Score", "Entry", "Fwd Days", "Fwd Close",
                                  "Return %"]
                st.dataframe(_show, hide_index=True, use_container_width=True)

                st.download_button(
                    "📥 Download Pick Log (CSV)",
                    data=_recent.to_csv(index=False).encode("utf-8"),
                    file_name="pick_log_export.csv",
                    mime="text/csv", key="pl_dl",
                )
