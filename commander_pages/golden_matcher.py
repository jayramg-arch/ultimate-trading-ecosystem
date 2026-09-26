# commander_pages/golden_matcher.py - the GOLDEN MATCHER page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('golden_matcher', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    is_max_board = (st.query_params.get("view") == "gm_board_maximized")
    if is_max_board:
        st.markdown('<div class="page-title">📋 Golden Matcher — Trigger Board (Maximized)</div>', unsafe_allow_html=True)
        st.markdown('<div class="page-desc">Maximized batch Trigger Board view</div>', unsafe_allow_html=True)
    else:
        _gm_titlecol, _gm_popcol = st.columns([4, 1.3])
        with _gm_titlecol:
            st.markdown('<div class="page-title">🪙 Golden Matcher</div>', unsafe_allow_html=True)
            st.markdown('<div class="page-desc">Single-symbol checklist presentation layer</div>', unsafe_allow_html=True)
        with _gm_popcol:
            # Pop the WHOLE Golden Matcher (Single Symbol ↔ Board switch works) into a
            # new window so it stays open while the main window is used for other
            # pages. Auto-refresh runs in the pop-out (fresh session → bar-close mode).
            if not is_gm_window:
                st.markdown(
                    '''<div style="display:flex;justify-content:flex-end;margin-top:6px;">
                    <a href="/?view=gm_window" target="_blank" style="text-decoration:none;">
                        <span style="display:inline-block;padding:6px 12px;border:1px solid var(--rule);
                        background:var(--acc-bg);color:var(--acc);border:1px solid var(--acc-rule);border-radius:4px;font-size:12px;
                        font-family:'JetBrains Mono',monospace;font-weight:600;">
                        ↗️ OPEN IN NEW WINDOW</span></a></div>''',
                    unsafe_allow_html=True)

    def _gm_reload_market_data():
        """ONE refresh for BOTH surfaces (Jay). Re-fetches fresh market data for the
        WHOLE board universe so the Trigger Board snapshot and the Single Symbol view
        read IDENTICAL data — no more board-vs-single drift from a per-symbol refresh.
        Busts the on-disk cache + clears the Streamlit loaders + flags the board to
        rebuild. Same call is wired to the button on BOTH views."""
        try:
            import gm_trigger_board as _gtb0, data_provider as _dp0
            for _s in list(_gtb0.load_watchlist_union().keys()):
                try:
                    _dp0.invalidate_symbol(_s)
                except Exception as e:
                    _gm_logger.warning(f"refresh: invalidate {_s} failed (stays cached): {e}")
        except Exception as e:
            _gm_logger.warning(f"refresh: universe invalidation failed — data may stay stale: {e}")
        for _c in (gm_load_symbol, gm_load_recovery, gm_load_intraday):
            try:
                _c.clear()
            except Exception as e:
                _gm_logger.warning(f"refresh: loader cache clear failed: {e}")
        st.session_state["gm_force_rebuild"] = True


    @st.fragment(run_every='2s')
    def auto_sync_tv_symbol_gm():
        """Auto-sync the Golden Matcher symbol input with the active TradingView chart."""
        import subprocess, csv, re
        from io import StringIO
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'],
                                     capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and
                                title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ['NIFTY 50', 'NIFTY']:     sym = '^NSEI'
                                elif sym.upper() in ['NIFTY BANK', 'BANKNIFTY']: sym = '^NSEBANK'
                                elif sym.upper() == 'NIFTY 500':              sym = '^CRSLDX'
                                else:
                                    if not sym.endswith('.NS') and '^' not in sym and '=' not in sym:
                                        sym += '.NS'
                                current_sym = st.session_state.get('gm_sym_input', '')
                                if sym != current_sym:
                                    if sym == st.session_state.get('gm_pend_sym'):
                                        st.session_state['gm_pend_count'] = st.session_state.get('gm_pend_count', 0) + 1
                                    else:
                                        st.session_state['gm_pend_sym'] = sym
                                        st.session_state['gm_pend_count'] = 1
                                    if st.session_state['gm_pend_count'] >= 2:
                                        st.session_state['gm_pend_sym'] = None
                                        st.session_state['gm_pend_count'] = 0
                                        st.session_state['gm_sym_input'] = sym
                                        st.session_state['gm_symbol'] = sym
                                        st.rerun()
                                else:
                                    st.session_state['gm_pend_sym'] = None
                                    st.session_state['gm_pend_count'] = 0
                                return
            except Exception:
                pass

    # ── View switch: single-symbol checklist  vs  batch Trigger Board ──────────
    if is_max_board:
        _gm_view = "📋 Trigger Board"
    else:
        _gm_view = st.radio("View", ["🎯 Single Symbol", "📋 Trigger Board"],
                            horizontal=True, key="gm_view", label_visibility="collapsed")

    if _gm_view == "📋 Trigger Board":
        # Batch board — every watchlist name run through the SAME GM engine
        # (compute_workflow / compute_recovery_workflow) → zero-drift categories.
        import gm_trigger_board as _gtb
        import datetime as _gtb_dt, time as _gtb_time
        if not is_max_board:
            # 13-Sep-2026 (Jay): the TF in the title, as a colour chip - the selector sits
            # below the fold and three windows on three TFs were indistinguishable at a
            # glance. Colours match the 75m green / 125m amber window buttons.
            _hdr_tf = TF_LOCK or st.session_state.get("gm_trig_tf") or str(_gm_settings().get("trigger_tf", "75m"))
            _hdr_col = {"75m": "#22C55E", "125m": "#F59E0B", "Daily": "#60A5FA"}.get(_hdr_tf, "#94A3B8")
            st.markdown(
                "#### 📋 Trigger Board — watchlists × the Golden Matcher engine &nbsp;"
                f"<span style='display:inline-block;padding:2px 12px;border-radius:999px;"
                f"background:{_hdr_col};color:#0B1220;font-size:0.72em;font-weight:800;"
                f"letter-spacing:.06em;vertical-align:middle'>⏱ {_hdr_tf}</span>",
                unsafe_allow_html=True)
        _uni = _gtb.load_watchlist_union()
        # P1: an unreadable/empty source CSV silently shrank the universe — say so.
        _uissues = list(getattr(_gtb, "LAST_UNION_ISSUES", []) or [])
        if _uissues:
            st.warning("⚠️ Watchlist source issues: " + " · ".join(_uissues))
        # Instant-on: if this browser session has no board yet, load the last
        # persisted build from disk (survives Web Commander restarts / reloads) so
        # it doesn't force a full rebuild every time.
        # 13-Sep-2026: ALSO on a Trigger-TF switch. The session held only the last
        # TF built, so changing the selector after an Evening run (which writes all
        # three per-TF caches) showed the same rows plus the "stale snapshot" warning.
        # If a cache exists for the newly selected TF, swap to it; the warning below
        # now fires only when there is nothing on disk for that TF.
        _want_tf = TF_LOCK or st.session_state.get("gm_trig_tf")
        _have_tf = st.session_state.get("gm_board_built_tf")
        if st.session_state.get("gm_board_df") is None or (_want_tf and _have_tf and _have_tf != _want_tf):
            _cdf, _cmeta = _gtb.load_board_cache(tf=_want_tf)
            if _cdf is not None and (_cmeta or {}).get("built_tf", _want_tf) == _want_tf:
                st.session_state["gm_board_df"] = _cdf
                st.session_state["gm_board_stamp"] = (_cmeta or {}).get("stamp") or "from cache"
                st.session_state["gm_board_tech_stamp"] = (_cmeta or {}).get("tech_stamp")
                # P0 fix: restore the snapshot's TF so the staleness guard survives
                # a restart (a 75m snapshot shown against a Daily selector must warn).
                st.session_state["gm_board_built_tf"] = (_cmeta or {}).get("built_tf") or _want_tf
                if (_cmeta or {}).get("saved"):
                    st.session_state["gm_board_saved_iso"] = _cmeta["saved"]
                # the failure list / issue strip belong to the build that produced the
                # frame in memory, not to this cached one
                st.session_state["gm_board_failed"] = []
                st.session_state["gm_board_intra_issues"] = []

        # ── AGE staleness guard (14-Jul-2026) — the recurring "board says BUY,
        # single says WATCHLIST" class: a MID-SESSION snapshot holds PA fired on a
        # then-FORMING 75m bar; by close the pattern fades and the live Single
        # Symbol page correctly disagrees (proven on ANANDRATHI: ΣPA=1 at the 13:51
        # build → 0 on the closed bars). The TF guard can't catch this — warn on AGE:
        # a snapshot built BEFORE the last session close is intraday state, not the
        # final read. Shown here (header) so BOTH render paths get it.
        _saved_iso = st.session_state.get("gm_board_saved_iso")
        if _saved_iso and st.session_state.get("gm_board_df") is not None:
            try:
                _saved_dt = datetime.fromisoformat(_saved_iso)
                _now_dt = datetime.now()
                _sess_d = _expected_last_session()          # last COMPLETED session (date)
                _sess_close = datetime(_sess_d.year, _sess_d.month, _sess_d.day, 15, 30)
                _mkt_open = (_now_dt.weekday() < 5 and
                             _now_dt.replace(hour=9, minute=15) <= _now_dt
                             <= _now_dt.replace(hour=15, minute=30))
                _age_min = int((_now_dt - _saved_dt).total_seconds() // 60)
                if _mkt_open and _age_min >= 15:
                    # During the session, PA fires on the FORMING 75/125m bar and can
                    # fade within minutes — any non-fresh snapshot may legitimately
                    # disagree with the live Single Symbol page.
                    st.warning(f"⚠️ **Live market · snapshot is {_age_min} min old** (built "
                               f"{_saved_dt.strftime('%H:%M')}). The board reads the last CLOSED "
                               f"trigger bar (the forming bar is excluded), but a newer bar may have "
                               f"closed and the price moved since this build — the live Single Symbol "
                               f"page may legitimately disagree on trigger-edge names. **Rebuild** (or "
                               f"use Live refresh) before acting on a category.")
                elif (not _mkt_open) and _saved_dt < _sess_close:
                    st.warning(f"⚠️ **Mid-session snapshot** — this board was built "
                               f"**{_saved_dt.strftime('%d-%b %H:%M')}**, before the "
                               f"{_sess_d.strftime('%d-%b')} 15:30 close. PA triggers that fired on "
                               f"forming bars may have FADED on the closed bars — the live Single "
                               f"Symbol page will disagree on those names. Click **Build / Refresh** "
                               f"for the final read.")
            except Exception as e:
                _gm_logger.warning(f"board age-guard failed: {e}")

        if not is_max_board:
            _bc1, _bc2, _bc3 = st.columns([1.2, 1.0, 2.2])
            with _bc1:
                # 29-Jul: the two buttons both read "🔄 … Refresh" and neither showed its
                # COST, so it was not obvious that one is cheap and the other is minutes.
                # Build reuses cached data (_board_build(force_technical=False) clears no
                # cache) — it is the right button for a Trigger-TF or X-Ray change.
                _build = st.button(f"🔨 Rebuild board  ·  {len(_uni)} names",
                                   type="primary", use_container_width=True, key="gm_board_build",
                                   help="Re-runs the GM engine over the watchlist using data ALREADY CACHED. "
                                        "Fast. Use after changing the Trigger TF or the X-Ray toggle, or when "
                                        "the watchlist CSVs changed. Does NOT fetch new prices — for that use "
                                        "Fetch fresh data below.")
                _use_xray = st.checkbox("🔬 X-Ray (Piotroski · grade · P/E)", key="gm_board_xray",
                                        value=True,
                                        help="Adds the X-Ray fundamental screener fields and folds Piotroski "
                                             "into the Overall score. Heavier (statements per name), cached 24h. "
                                             "On by default; uncheck for a faster fundamentals-light build.")
                _refresh_all = st.button(f"🔄 Fetch fresh data + rebuild  ·  ~{len(_uni)} fetches",
                                         use_container_width=True, key="gm_board_refresh_all",
                                         help="Invalidates the on-disk cache for the WHOLE universe, then REBUILDS "
                                              "automatically — you do NOT need to press Rebuild afterwards. Slow "
                                              "(~50 fetches, minutes). Use it when prices may be stale: first build "
                                              "of the day, after the close, or when the freshness banner warns. The "
                                              "same button is on the Single Symbol page so both surfaces read "
                                              "identical data (this is what fixed board-vs-single drift).")
                # ── EVENING RUN (13-Sep-2026, Jay) ─────────────────────────────────
                # The post-auto-pilot ritual was: Fetch fresh here, open three more
                # windows (75m / 125m / Daily), Fetch fresh in each, then Build options
                # bundle, then copy two strings. Four windows, four full re-downloads of
                # the same universe, six clicks. This is ONE click in ONE window: the
                # universe is invalidated ONCE, the three boards are built in sequence
                # in this process (each writes its own per-TF cache, which is all the
                # union bundle and the options bundle read), the options chains are
                # pulled, and the two bundles render below. This window's own TF is
                # built LAST so the table on screen matches the TF selector.
                # It is the manual form of what Phase 6 of run_pipeline will do headless
                # once the decision core is importable without Streamlit.
                _evening = st.button("🌙 Evening run  ·  fetch once → Daily · 125m · 75m boards → options bundle",
                                     use_container_width=True, key="gm_evening_run",
                                     help="One click for the whole post-close routine. Invalidates the universe "
                                          "cache once, rebuilds all three boards in this window (writing the three "
                                          "per-TF caches the bundles read), builds the options bundle, and shows the "
                                          "ONE-PASTE bundle (all timeframes) and Bundle 2 below. Copy those two into "
                                          "S4. Takes as long as one Fetch fresh plus two cached rebuilds. Also the "
                                          "manual re-run after a recompile or a failed auto-pilot.")
                _ev_stamp = st.session_state.get("gm_evening_stamp")
                if _ev_stamp:
                    st.caption(f"🌙 last evening run: {_ev_stamp}")
            with _bc2:
                # Trigger TF — UNIFIED with the Single Symbol page. Both widgets use the
                # session key "gm_trig_tf" (the two views never render in the same run —
                # the view switch is mutually exclusive) and persist to gm_settings, so
                # changing the TF on either surface carries to the other and survives a
                # restart. Seed from the persisted setting on first load only.
                _tf_opts_b = ["75m", "125m", "Daily"]
                if "gm_trig_tf" not in st.session_state:
                    _tf0 = str(_gm_settings().get("trigger_tf", "75m"))
                    st.session_state["gm_trig_tf"] = _tf0 if _tf0 in _tf_opts_b else "75m"
                if TF_LOCK:
                    # Locked by ?tf= — render a caption, not a widget. A selectbox here
                    # would let the user change it and then be re-forced on the next run,
                    # which reads as the control fighting back.
                    _trig_tf = TF_LOCK
                    st.caption(f"⏱ Trigger TF **{TF_LOCK}** · locked by URL (dedicated window)")
                else:
                    _trig_tf = st.selectbox(
                        "⏱ Trigger TF", _tf_opts_b, key="gm_trig_tf",
                        help="Shared with the Single Symbol page (one setting). The board's "
                             "technical + PA columns (Category/Step/trigger/CMP) compute on THIS "
                             "timeframe. 75/125m use INTRADAY bars (move through the session); "
                             "Daily uses the closed daily bar.")
                if _trig_tf != _gm_settings().get("trigger_tf"):
                    _gm_settings_save(trigger_tf=_trig_tf)
                # Pivot (structural) zones — Jay's switch. Changing what a zone IS
                # invalidates every cached evaluation, so this clears the loaders and
                # forces a rebuild; without that the toggle reads as doing nothing.
                _piv_now = st.checkbox(
                    "Use pivot (structural) zones", value=_gm_use_pivot_zones(),
                    key="gm_use_pivot_zones",
                    help="ON (default): a pivot shelf can satisfy LOCATION, but only with a "
                         "confirming S/R or AVWAP (rule A2). OFF: pattern (leg-base-leg) zones "
                         "only — pivots are neither drawn nor counted. Measured 26-Aug: no alpha "
                         "difference between the two, but pattern-only fires on ~4x fewer names. "
                         "Mirror it on the S4 chart with 'Draw Pivot (Structural) zones'.")
                if _piv_now != _gm_use_pivot_zones():
                    _gm_settings_save(use_pivot_zones=bool(_piv_now))
                    for _c in (gm_load_symbol, gm_load_recovery, gm_load_intraday):
                        try:
                            _c.clear()
                        except Exception as e:
                            _gm_logger.warning(f"pivot toggle: cache clear failed: {e}")
                    st.session_state["gm_force_rebuild"] = True
                    st.rerun()
                _gm_sync_pivot_setting()
                # Entry method — shared, GLOBAL setting (see _render_entry_method_selector).
                _render_entry_method_selector("gm_entry_method_sel")
                # 75m/125m "bar-close" modes rebuild the board ONCE per session bar
                # (aligned to NSE bar closes + ~75s settle) so the snapshot always reads
                # a CLOSED bar — the definitive fix for the forming-bar fade that made
                # board vs Single Symbol disagree (Jay trades the 75m TF). Default to
                # the bar-close mode matching the selected Trigger-TF.
                _live_opts = ["Off", "Check-in schedule", "75m bar-close", "125m bar-close",
                              "75m+125m bar-close",
                              "1 min", "2 min", "3 min", "5 min", "10 min", "15 min"]
                # PERSISTED (30-Jul, Jay: "set Live refresh to 75m+125m"). This lived in
                # session_state only, so every reconnect/restart reset it to the Trigger-TF
                # default — and on plain "75m" the board never rebuilds at 11:20 or 13:25,
                # which silently made a 13:30 check-in read a 13:00 board. Now it survives
                # like capital / risk% / trigger_tf, and defaults to the UNION so all seven
                # session closes refresh out of the box.
                if "gm_board_live" not in st.session_state:
                    _lv0 = str(_gm_settings().get("board_live", "75m+125m bar-close"))
                    st.session_state["gm_board_live"] = _lv0 if _lv0 in _live_opts else "75m+125m bar-close"
                _live = st.selectbox("🟢 Live refresh", _live_opts,
                                     key="gm_board_live",
                                     help="Rebuilds the technical + PA columns while the board is open. "
                                          "**Check-in schedule** = your desk clock — 75m tab at 10:35·11:50·"
                                          "13:30·14:20·15:35, 125m tab at 11:50·13:30·15:35, Daily once at 15:35. "
                                          "**75m/125m bar-close** = rebuild ONCE per session bar (10:30·11:45·"
                                          "13:00·14:15·15:30 for 75m) so the board reads CLOSED bars and matches "
                                          "the live Single Symbol page. The "
                                          "N-min options are fixed-interval. Fundamentals stay cached (change "
                                          "daily/quarterly). Full Build refreshes everything.")
                _score_mode = st.selectbox("⚖️ Score mode", ["Balanced", "Hunting", "Watchlist"],
                                           key="gm_score_mode",
                                           help="Overall-score weighting (4-dimension model). Balanced = all-round. "
                                                "Hunting = skew to Setup/Trigger + Risk (find live entries). "
                                                "Watchlist = skew to Leadership + Fundamentals (rank by quality). "
                                                "Rebuild to apply.")
            with _bc3:
                _stamp = st.session_state.get("gm_board_stamp")
                _tstamp = st.session_state.get("gm_board_tech_stamp")
                # P1 provenance: built TF + which feeds served this process's fetches —
                # staleness/source-splits become visible even where not yet fixed.
                _btf = st.session_state.get("gm_board_built_tf")
                _srcmix = ""
                try:
                    import data_provider as _dpsrc2
                    _cnt = _dpsrc2.get_source_counts() or {}
                    if _cnt:
                        _srcmix = " · src " + "/".join(f"{k}:{v}" for k, v in
                                                       sorted(_cnt.items(), key=lambda x: -x[1]))
                except Exception:
                    pass
                st.caption((f"Full build **{_stamp}**" + (f" · live tech **{_tstamp}**" if _tstamp else "")
                            + (f" · TF **{_btf}**" if _btf else "") + _srcmix
                            + " · RRG persists") if _stamp
                           else "Not built yet — click **Build / Refresh** (full run ~2–5 min).")
                # ── THE ONE-PASTE BUNDLE (25-Aug-2026) ──────────────────────────
                # Five separate pastes was a CORRECTNESS problem, not a convenience
                # one: a missed paste does not blank the field in S4, it leaves the
                # PREVIOUS list in place, so the chart goes on applying last week's
                # answer to this week's board and nothing announces it. Five chances
                # to forget, each silent. This is one.
                # The five individual blocks below are KEPT: they are how you override
                # a single list by hand, and a hand-typed S4 input wins over the bundle
                # for its own field.
                try:
                    _s4bundle = _gtb.s4_bundle(_uni, tf=_trig_tf)
                except Exception as e:
                    _s4bundle = ""
                    _gm_logger.warning(f"s4_bundle failed: {e}")

                # ── ALL-TIMEFRAMES BUNDLE (29-Aug-2026) ─────────────────────────
                # For a single chart layout, which has ONE S4 bundle field. The
                # per-TF line above is still correct; this removes the daily "which
                # board has the most names today?" judgement, which flips with
                # breadth. Safe to merge because every section is symbol-keyed and
                # carries a property of the NAME, not the chart -- see
                # gm_trigger_board.s4_bundle_union for the field-by-field reasoning.
                try:
                    _s4union = _gtb.s4_bundle_union()
                except Exception as e:
                    _s4union = ""
                    _gm_logger.warning(f"s4_bundle_union failed: {e}")
                # Rendered even when it MATCHES the per-TF line: all three boards share
                # one watchlist union, so on a day every window was rebuilt they are
                # identical and the union adds nothing. Suppressing it then would hide
                # the field on exactly the days nothing is wrong, and you would go looking
                # for it. The caption says which case you are in instead.
                if _s4union:
                    st.caption("📋 **ONE-PASTE bundle (all timeframes)** — the Daily / "
                               "125m / 75m boards merged and deduped by symbol. Use this "
                               "one if you run a single chart layout: it covers every name "
                               "on any board, so you never have to pick the widest. "
                               "⚠️ A timeframe only contributes the BFFC/RFFC/PIOC "
                               "bitstrings once its board has been REBUILT at least once — "
                               "rebuild all three windows before copying."
                               + ("  ✅ Identical to the per-TF line above — all three boards "
                                  "were rebuilt from the same watchlist, so either works today."
                                  if _s4union == _s4bundle else
                                  "  ⚠️ DIFFERS from the per-TF line (folded below) — at least one board "
                                  "is stale or was not rebuilt. Prefer this one."))
                    st.code(_s4union, language=None)

                # ── SECOND PASTE — options OI (1-Sep-2026) ────────────────────
                # A SEPARATE S4 input ("GM: bundle 2 — options OI"), because
                # input.string caps around 4,096 chars and the bundle above is already
                # ~9,200. Pasting this into the first field would wipe every list in it,
                # so it gets its own block with the destination named.
                #
                # Behind a button: one NSE option-chain call per F&O name, and this
                # block re-renders on every interaction. Building it inline would fire
                # dozens of network calls per filter change and look like a hang.
                if st.button("🧮 Build options bundle (F&O names only)",
                             key="gm_opt_build",
                             help="One NSE option-chain call per F&O name on the board. "
                                  "Cash-only names are skipped entirely. Held in session "
                                  "state afterwards, so reruns do not re-fetch."):
                    with st.spinner("Fetching option chains…"):
                        try:
                            st.session_state["_gm_opt_bundle"] = _gtb.s4_bundle_options()
                            try:
                                import gm_evening_headless as _geh
                                _geh.write_bundles(st.session_state["_gm_opt_bundle"],
                                                   "options rebuilt · " + _gtb_dt.datetime.now().strftime("%d %b %H:%M"))
                            except Exception as e:
                                _gm_logger.warning(f"bundle file write failed: {e}")
                        except Exception as e:
                            st.session_state["_gm_opt_bundle"] = ""
                            _gm_logger.warning(f"s4_bundle_options failed: {e}")

                _s4opt = st.session_state.get("_gm_opt_bundle")
                _s4opt_src = ""
                if not _s4opt:
                    # 13-Sep-2026: session memory dies with a restart and Bundle 2 vanished
                    # after one. gm_bundles/latest.txt is written by the Evening run (both
                    # forms) and by the button above; read it back with its stamp.
                    try:
                        _gbf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gm_bundles", "latest.txt")
                        if os.path.exists(_gbf):
                            with open(_gbf, encoding="utf-8") as _fh:
                                _gbl = _fh.read().splitlines()
                            _gb_opt = [ln for ln in _gbl if ln.startswith("OPT=")]
                            if _gb_opt:
                                _s4opt = _gb_opt[0]
                                _s4opt_src = (_gbl[0].split("—", 1)[-1].strip() if _gbl and _gbl[0].startswith("#") else "file")
                    except Exception as e:
                        _gm_logger.warning(f"gm_bundles/latest.txt read failed: {e}")
                if _s4opt is not None:
                    _optn = len([x for x in _s4opt.split("=", 1)[-1].split(",") if x.strip()])
                    if _optn:
                        st.caption(
                            f"🧮 **Bundle 2 — options OI** · {_optn} F&O names · "
                            + (f"from the last run ({_s4opt_src}) · " if _s4opt_src else "") +
                            f"{len(_s4opt)} chars. Paste into S4's **“GM: bundle 2 — options "
                            "OI”** field, NOT the one above. Carries PCR, max pain, total CE/PE "
                            "OI, the ATM OI shift and the two strikes with the most written "
                            "OI — max pain and those two strikes are DRAWN on the chart as "
                            "levels. A field NSE did not return is emitted empty, never zero: "
                            "a max pain of 0 would render as a price line below every stop.")
                        st.code(_s4opt, language=None)
                    else:
                        # Empty and failed are different facts; only one is worth retrying.
                        st.caption(
                            "🧮 **Bundle 2 — options OI** — nothing returned. Either no F&O "
                            "names on this board, or NSE refused the chain request (its "
                            "endpoint rejects sessions frequently). Click again to rebuild "
                            "the session; the levels are simply not drawn until it succeeds.")

                # ── EVERYTHING ELSE, FOLDED (13-Sep-2026, Jay: 'remove the extra lists to
                # reduce the clutter'). The all-TF bundle + Bundle 2 above are the two
                # pastes that matter; these are per-TF / per-list overrides and read-only
                # views, kept for the day one list needs forcing by hand.
                with st.expander("🧰 Individual lists — hand overrides (per-TF bundle · Recovery · Pullback · BFF/RFF/rank)", expanded=False):
                    if _s4bundle:
                        st.caption("📋 **ONE-PASTE bundle** — paste this single line into S4's "
                                   "*GM: ONE-PASTE bundle* input and every list below is fed from "
                                   "it. Every section is emitted even when empty, which is what "
                                   "CLEARS a stale list in S4 — the individual blocks below are "
                                   "still there for overriding one list by hand.")
                        st.code(_s4bundle, language=None)
                    # ── S4 "Auto: GM Recovery list" (2-Aug-2026) — S4 cannot infer the GM's
                    # Bull-vs-Recovery answer (it is inherited from the qualifying screen on
                    # RFF fundamentals, which price structure does not contain), so the GM
                    # hands it over. Paste ONCE per watchlist refresh: the path is a property
                    # of the NAME, so the same string is correct on every timeframe.
                    try:
                        _s4rec = _gtb.s4_recovery_list(_uni)
                    except Exception as e:
                        _s4rec = ""
                        _gm_logger.warning(f"s4_recovery_list failed: {e}")
                    _s4n = len([s for s in _s4rec.split(",") if s.strip()]) if _s4rec else 0
                    # Shown OPEN, not behind an expander (Jay, 4-Aug): the paste is a
                    # once-per-watchlist-refresh action, so anything that needs a click to
                    # reveal is an action that gets forgotten — which leaves S4 on a stale
                    # list, silently forcing the wrong path on names that have since requalified.
                    if _s4rec:
                        st.caption(f"🩺 **S4 Recovery list · {_s4n} names** — paste into S4's "
                                   f"*Auto: GM Recovery list* (Mode stays **Auto**). Recovery "
                                   f"archetype and NO bull archetype; names in both are left to "
                                   f"S4's stage+drawdown tie-break. Re-paste after a refresh.")
                        st.code(_s4rec, language=None)
                    else:
                        st.caption("🩺 **S4 Recovery list · 0 names** — no Recovery-only names in "
                                   "the current union. Clear S4's list input so nothing stale "
                                   "forces a Recovery path.")
                    # ── S4 "Auto: GM Pullback list" (5-Aug-2026) — the PLAYBOOK SPLIT.
                    # A breakout must expand on heavy volume and close strong; a pullback
                    # enters on volume DRY-UP with a bar that only holds the zone. One gate
                    # cannot be neutral between them, and S4 has no archetype to tell them
                    # apart — so it inferred the setup from patterns and the two surfaces
                    # graded the same candle against different standards. The GM knows which
                    # screen qualified the name; it hands the answer over.
                    try:
                        _s4pb = _gtb.s4_pullback_list(_uni)
                    except Exception as e:
                        _s4pb = ""
                        _gm_logger.warning(f"s4_pullback_list failed: {e}")
                    _pbn = len([s for s in _s4pb.split(",") if s.strip()]) if _s4pb else 0
                    if _s4pb:
                        st.caption(f"↩️ **S4 Pullback list · {_pbn} names** — paste into S4's "
                                   f"*Auto: GM Pullback list*. These get the PULLBACK playbook "
                                   f"(volume dry-up OK, bar only has to hold the zone); everything "
                                   f"else keeps the breakout gates. Still must be AT a demand zone.")
                        st.code(_s4pb, language=None)
                    else:
                        st.caption("↩️ **S4 Pullback list · 0 names** — no pullback-only names in "
                                   "the current union. Clear S4's input; S4 falls back to inferring "
                                   "the setup from the pattern mix.")
                    # (Manual Strike-RRG paste block deleted 25-Sep-2026 - RRG is computed.)

                    # ── S4 BFF / RFF SCORE lists (25-Aug-2026) — the FOURTH handoff, and the
                    # one S4 cannot approximate at all. RFF needs six fundamental fields plus
                    # Tier-B growth against a five-call request.financial ceiling the
                    # Capitulation Screener already spends; BFF reads screener.in's growth
                    # table, which no Pine surface can reach. Unlike the path and the setup,
                    # there is no price-based fallback — without this the S4 fields stay blank.
                    # SYM:n pairs, not bare symbols: here the NUMBER is the message.
                    # Sourced from the BUILT BOARD so the chart cannot disagree with the row
                    # you clicked through from, and so this costs no screener.in fetches.
                    try:
                        _s4fund = _gtb.s4_fund_lists(tf=_trig_tf) or {}
                    except Exception as e:
                        _s4fund = {}
                        _gm_logger.warning(f"s4_fund_lists failed: {e}")
                    _bffs = _s4fund.get("BFF", "")
                    _rffs = _s4fund.get("RFF", "")
                    _rnks = _s4fund.get("RANK", "")
                    _bn = len([x for x in _bffs.split(",") if x])
                    _rn = len([x for x in _rffs.split(",") if x])
                    _kn = len([x for x in _rnks.split(",") if x])
                    if _bn or _rn or _kn:
                        st.caption(f"🧪 **S4 scores · BFF {_bn} · RFF {_rn} · rank {_kn}** — paste "
                                   f"into S4's *GM: BFF scores* and *GM: RFF scores*. A name ABSENT "
                                   f"from a list renders as an em-dash on the panel, not a zero: "
                                   f"unscored and scored-badly are different facts. Re-paste after a "
                                   f"board rebuild.")
                        if _bffs:
                            st.caption(f"*GM: BFF scores* · {_bn}")
                            st.code(_bffs, language=None)
                        if _rffs:
                            st.caption(f"*GM: RFF scores* · {_rn} — RFF only exists for names a "
                                       f"recovery screen has scored, so a bull-heavy board shows few.")
                            st.code(_rffs, language=None)
                        if _rnks:
                            # #10 - the board's Overall. S4 grades ONE chart and cannot know
                            # where that chart sits among the other forty; this is the only
                            # way the panel can say "clean setup, 38th best name on the list".
                            st.caption(f"*GM: board rank* · {_kn} — the board's Overall composite. "
                                       f"Display-only on S4: it never gates and never scores, because "
                                       f"the rank already contains most of what that panel measures.")
                            st.code(_rnks, language=None)
                    else:
                        st.caption("🧪 **S4 fundamental scores · 0** — build the board first; "
                                   "these are read from the built board, not recomputed.")

        else:
            # MAXIMIZED table-only pop-out (Jay): no heavy controls — a slim Rebuild
            # button + auto-refresh only. TF / Live / Score / X-Ray come from the
            # persisted settings so the table matches the main window.
            _gmset_mx = _gm_settings()
            # TF_LOCK FIRST (30-Jul bug): this branch skips the controls block entirely, so
            # it never saw the ?tf= override and BOTH pop-outs read trigger_tf from
            # gm_settings — the "125m Board" button opened a 75m board. The lock has to be
            # honoured here, not only where the selectbox lives.
            _trig_tf = TF_LOCK or str(_gmset_mx.get("trigger_tf", "75m"))
            if _trig_tf not in ("75m", "125m", "Daily"):
                _trig_tf = "75m"
            # Persisted board_live first; the old TF-derived fallback overrode the saved
            # "75m+125m bar-close" and displayed plain "75m bar-close".
            _live = st.session_state.get("gm_board_live") or str(
                _gmset_mx.get("board_live",
                              "125m bar-close" if _trig_tf == "125m" else "75m bar-close"))
            st.session_state["gm_board_live"] = _live
            # A DEDICATED WINDOW MUST SAY WHICH TF IT IS (Jay: "I'm not sure whether the
            # 125m Board is 75m or 125m"). Colour-matched to the launch buttons.
            _tfcol = {"75m": ("var(--bull)", "#0d1b12"), "125m": ("var(--warn)", "#1a1408"), "Daily": ("var(--acc)", "#0b1220")}.get(
                _trig_tf, ("var(--acc)", "var(--acc-bg)"))
            st.markdown(
                f'<div style="background:{_tfcol[1]};border-left:4px solid {_tfcol[0]};'
                f'padding:6px 14px;margin-bottom:6px;font-family:monospace;'
                f'font-size:20px;font-weight:700;color:{_tfcol[0]};letter-spacing:1px;">'
                f'{_trig_tf} TRIGGER BOARD'
                f'<span style="font-size:12px;font-weight:400;opacity:.75;margin-left:12px;">'
                f'PA + momentum computed on {_trig_tf}</span></div>',
                unsafe_allow_html=True)
            _use_xray = True
            _score_mode = "Balanced"
            # FRESH FETCH BELONGS HERE TOO (7-Aug, Jay: "these 3 timeframe windows have
            # only Rebuild"). _refresh_all was hardcoded False, so a pop-out could only
            # ever re-run the engine over CACHED frames. That matters because each TF
            # keeps its OWN cache file: a fresh rebuild on the main window updates only
            # the TF it is showing, leaving the other two pop-outs on older data with no
            # way to fix it from inside the window. It also cannot self-heal the case
            # that produced zero GOs — stub-corrupted intraday frames survive a plain
            # Rebuild because Rebuild never re-fetches.
            _mxc1, _mxc2, _mxc3 = st.columns([1, 1.4, 4])
            _build = _mxc1.button("🔨 Rebuild", use_container_width=True, key="gm_board_build_mx",
                                  help="Re-runs the engine over data ALREADY CACHED. Fast.")
            _refresh_all = _mxc2.button("🔄 Fresh + rebuild", use_container_width=True,
                                        key="gm_board_refresh_mx",
                                        help="Invalidates the on-disk cache for the whole universe, then "
                                             "rebuilds automatically. Slow (~50 fetches). Use it when prices "
                                             "may be stale — first build of the day, or after the close.")
            _mxc3.caption(f"Maximized table · TF {_trig_tf} · {_live} · auto-refresh on bar close · src {st.session_state.get('gm_board_built_tf','—')}")

        # --- build (full = fundamentals+technical; force_technical = technical/PA only;
        #     quiet = no progress bar, used on live ticks so the layout never jumps) ---
        def _board_build(force_technical=False, quiet=False, tf_override=None):
            # READ THE TF AT CALL TIME, NOT FROM THE CLOSURE (5-Aug-2026, Jay: "I set the
            # TF to Daily and ran the rebuild, it still showed 75m; rebuilt again and it
            # was Daily"). This function is also called from the live-refresh FRAGMENT
            # (run_every 3s), and a fragment rerun does NOT re-execute the enclosing
            # script — so it closes over whatever _trig_tf held at the last full rerun.
            # A bar-close tick landing between a TF change and the rebuild therefore
            # rebuilt at the OLD TF and re-stamped gm_board_built_tf with it, which also
            # silenced the stale-snapshot warning that exists to catch exactly this.
            # session_state is the single live value (the selectbox writes it directly),
            # with TF_LOCK still winning for the ?tf= pop-out windows.
            # tf_override: the Evening run builds all three TFs from ONE window, so it
            # names the TF per call instead of reading the window's own setting.
            _tf_now = tf_override or TF_LOCK or st.session_state.get("gm_trig_tf") or _trig_tf
            if force_technical:
                # Live refresh: recompute ONLY technicals + PA. Clear the technical
                # caches; the fundamental caches (BFF/RFF/X-Ray, 24h TTL) stay warm,
                # so fundamentals are REUSED, not re-fetched. Delivery% is an EOD
                # bhavcopy value → reuse the cached NSE metrics too.
                try:
                    gm_load_symbol.clear(); gm_load_intraday.clear()
                except Exception as e:
                    _gm_logger.warning(f"live tick: technical cache clear failed (stale tick): {e}")
                _nse_metrics = st.session_state.get("gm_board_nse") or {}
            else:
                _nse_metrics = {}
                try:
                    import nse_archive_fetcher as _naf
                    _nse_metrics = _naf.get_nse_metrics() or {}
                except Exception as e:
                    _nse_metrics = {}
                    _gm_logger.warning(f"board build: NSE delivery bulk fetch failed "
                                       f"(Deliv% falls to volume): {e}")
                st.session_state["gm_board_nse"] = _nse_metrics
            _xray_fn = None
            try:
                from weinstein_xray_screener import get_xray_scorecard as _xray_fn
            except Exception as e:
                _xray_fn = None
                _gm_logger.warning(f"board build: X-Ray import failed: {e}")
            _loaders = dict(evaluate=gm_evaluate,          # SINGLE source of truth (shared with Single Symbol)
                            load_symbol=gm_load_symbol, load_recovery=gm_load_recovery,
                            bull_wf=compute_workflow, rec_wf=compute_recovery_workflow,
                            minervini=minervini_checks, nse_metrics=_nse_metrics,
                            xray=_xray_fn, use_xray=True,
                            load_intraday=gm_load_intraday,
                            trigger_tf=_tf_now,           # "75m"/"125m"/"Daily" — gm_evaluate honours Daily
                            overall_weights=_gtb.OVERALL_PRESETS.get(_score_mode))
            _rows = []
            _failed = []                 # P1: a failed name must be VISIBLE, never vanish
            _items = list(_uni.items())
            # Per-build record of intraday (trigger-TF) load failures — the cause
            # behind an all-"n/a" S4-GO column. Reset HERE so counts describe THIS
            # build only; build_row appends via note_intra_issue.
            try:
                _gtb.reset_intra_issues()
            except Exception as e:
                _gm_logger.warning(f"board build: reset_intra_issues failed "
                                   f"(S4-GO cause counts may include a stale build): {e}")
            _prog = None if quiet else st.progress(0.0, "Building board…")
            for _i, (_sym, _info) in enumerate(_items):
                try:
                    _r = _gtb.build_row(_sym, _info, _loaders, _g)
                    if _r:
                        _rows.append(_r)
                    else:
                        _failed.append(_sym)
                        _gm_logger.warning(f"board build: {_sym}: build_row returned None (no data/candidates)")
                except Exception as _be:
                    _failed.append(_sym)
                    _gm_logger.warning(f"board build: {_sym}: {type(_be).__name__}: {_be}")
                if _prog is not None:
                    _prog.progress((_i + 1) / max(1, len(_items)), f"{_sym}  ({_i + 1}/{len(_items)})")
            if _prog is not None:
                _prog.empty()
            _bdf_new = pd.DataFrame(_rows)
            if not _bdf_new.empty and "Overall" in _bdf_new.columns:
                _bdf_new = _bdf_new.sort_values("Overall", ascending=False, na_position="last").reset_index(drop=True)
            st.session_state["gm_board_df"] = _bdf_new
            st.session_state["gm_board_built_tf"] = _tf_now        # TF this snapshot was computed at
            # Stamp the current session bar so bar-close auto-refresh doesn't
            # redundantly rebuild right after a manual/interval build.
            _bnd0 = _gm_last_passed_boundary(_tf_now if _tf_now in ("75m", "125m") else "75m")
            st.session_state["gm_board_last_boundary"] = _bnd0.isoformat() if _bnd0 else None
            st.session_state["gm_board_failed"] = _failed           # P1: visible failure list
            # Snapshot the S4-GO "n/a" causes for the header strip. Held in
            # session_state (not the DataFrame) so it survives reruns without
            # leaking a build-health column into the grid / CSV export.
            try:
                st.session_state["gm_board_intra_issues"] = _gtb.intra_issue_summary()
            except Exception as e:
                st.session_state["gm_board_intra_issues"] = []
                _gm_logger.warning(f"board build: intra_issue_summary failed "
                                   f"(S4-GO cause strip hidden): {e}")
            _now_s = _gtb_dt.datetime.now().strftime("%d %b %H:%M")
            st.session_state["gm_board_tech_stamp"] = _now_s
            st.session_state["gm_board_tech_ts"] = _gtb_time.time()
            if not force_technical:
                st.session_state["gm_board_stamp"] = _now_s
            st.session_state["gm_board_saved_iso"] = _gtb_dt.datetime.now().isoformat()
            # Persist to disk so the board survives a restart / reload (instant-on).
            _gtb.save_board_cache(_bdf_new, tf=_tf_now, stamp=st.session_state.get("gm_board_stamp"),
                                  tech_stamp=_now_s, built_tf=_tf_now)
            # FORWARD RECORD (5-Aug-2026). Append every state CHANGE to the append-only
            # signal log — written before the outcome is knowable, never edited after.
            # This is the live track record; it is not derived from any backtest and
            # cannot be re-specified by one. Dedup is per (date, tf, symbol, n/4 bucket),
            # so bar-close rebuilds every 75 min do not inflate the sample.
            # Guarded hard: a logging failure must never break a board build.
            try:
                import gm_signal_log as _gsl
                _nlog = _gsl.append_board(_bdf_new, tf=_tf_now)
                if _nlog:
                    _gm_logger.info(f"signal log: +{_nlog} rows ({_tf_now})")
            except Exception as e:
                _gm_logger.warning(f"signal log append failed (board unaffected): {e}")

        # --- render (RRG overlay + filters + editable table); keyed widgets so
        #     filter/edit state survives the live-refresh fragment reruns ---
        def _board_render():
            _bdf = st.session_state.get("gm_board_df")
            if _bdf is None or _bdf.empty:
                st.info("Click **Build / Refresh** to populate the board (fundamentals + technical).")
                return
            # (Failure counts, staleness guard, filters + CSV download now render in
            # the SHARED header above — visible in every mode. This path only draws
            # the editable table for the filtered view.)

            _view = _board_apply_filters(_bdf)      # SHARED filter (see header block)
            _edited = st.data_editor(
                # use_container_width=False (3-Aug): with it TRUE, Streamlit stretches or
                # SHRINKS every column to fill the container and the configured widths are
                # overridden — which is why a rebuild collapsed the table and the manual
                # re-widening never survived. False makes the configured pixel widths
                # authoritative and the table scrolls horizontally instead.
                _view, use_container_width=False, hide_index=True, key="gm_board_editor",
                column_config={
                    "Symbol": st.column_config.TextColumn(
                        "Symbol", width=105),
                    "Arm": st.column_config.CheckboxColumn(
                        "🔔", width=60,
                        help="Arm this name — records the plan on THIS row (entry / SL / T1 / "
                             "verdict) into the Armed Register. It then stays on the board even "
                             "after every watchlist drops it, so the alert you set today still "
                             "has its plan when it fires next week. Untick to disarm."),
                    "★": st.column_config.TextColumn(
                        "★", width=50,
                        help="Top-Conviction badge — the name is in FINAL_WATCHLIST.csv, i.e. the "
                             "top-25 by Combined_Score across all bull+recovery picks (the Golden "
                             "Matcher shortlist). A quality flag layered on top of the archetype."),
                    "RRG": st.column_config.TextColumn(
                        "RRG", width=110,
                        help="COMPUTED quadrant — JdK RS-Ratio/Momentum (strike_cal, the RRG Studio "
                             "maths) on confirmed weekly bars vs Nifty 500. The hand-typed RRG flag "
                             "was retired 25-Sep-2026: it had gone 39 days stale and contradicted "
                             "this on half the flagged names."),
                    "Overall": st.column_config.ProgressColumn(
                        "Overall", min_value=0, max_value=100, format="%.0f", width=105,
                        help="0-100 opportunity score — Leadership(Alpha+Minervini)/Fundamentals(Conviction/"
                             "BFF-or-RFF/Piotroski)/Setup(ΣPA+catalyst+VCP)/Risk(R:R), reweighted for missing "
                             "inputs. Independent of category & path."),
                    "Category": st.column_config.TextColumn(
                        "Category", width=215),
                    "S4-GO": st.column_config.TextColumn(
                        "S4-GO", width=175),
                    "Archetype": st.column_config.TextColumn(
                        "Archetype", width=250),
                    "Loc": st.column_config.TextColumn(
                        "Loc", width=230),
                    "Path": st.column_config.TextColumn(
                        "Path", width=85),
                    "WCL Context": st.column_config.TextColumn(
                        "WCL Context", width=200,
                        help="Weinstein Context Layer macro score band (STRONG BULL / BULL / NEUTRAL / CAUTION / BEAR) and active tactical setup (S1-S8)."),
                    "Struct Health": st.column_config.TextColumn(
                        "Struct Health", width=120,
                        help="SMC Structure Health: CLEAN (0-1 CHoCHs), CHOPPY (2-3 CHoCHs, caps Kelly size at 0.5x), BROKEN (4+ CHoCHs)."),
                    "VP Position": st.column_config.TextColumn(
                        "VP Position", width=135,
                        help="Volume Profile Position: ✓ ABOVE VAH, ✓ IN VA (upper), ✗ IN VA (lower), ✗ BELOW VAL."),
                },
                disabled=[c for c in _view.columns if c != "Arm"],
            )
            _changed = False
            # Arm ticks — SAME shared write-back the streaming grid uses.
            if _gm_apply_arm_edits(_edited):
                _changed = True
            if _changed:
                st.rerun()

        # ── ARM EDITS FROM THE GRID ──────────────────────────────────────────
        # ONE write-back used by BOTH render paths (data_editor and the streaming
        # AG-Grid). Two copies of this is exactly the drift that has bitten this
        # codebase repeatedly, and here it would be worse than cosmetic: the two
        # paths would snapshot different plans for the same click.
        #
        # The snapshot is built FROM THE ROW, which is better than the Single Symbol
        # route — the row is literally what you were looking at when you decided to
        # arm, so the recorded plan and the plan you read are the same object.
        def _gm_apply_arm_edits(edited) -> bool:
            try:
                import gm_armed as _ar
            except Exception as e:
                _gm_logger.warning(f"board: gm_armed unavailable, Arm column inert: {e}")
                return False
            if edited is None or "Arm" not in getattr(edited, "columns", []):
                return False
            _reg = _ar.load()
            _changed = False
            for _, r in edited.iterrows():
                _sym = str(r.get("Symbol") or "").strip()
                if not _sym:
                    continue
                _want = bool(r.get("Arm"))
                _key = _ar.canon(_sym)
                _now = (_reg.get(_key, {}) or {}).get("status") == _ar.STATUS_ARMED
                if _want == _now:
                    continue
                try:
                    if _want:
                        _pth = "recovery" if str(r.get("Path", "")).lower().startswith("rec") else "bull"
                        _arch = [a.strip() for a in str(r.get("Archetype") or "").split(",")
                                 if a.strip() and a.strip() != _gtb.ARMED_ARCHETYPE]
                        _ar.arm(_sym, path=_pth, archetypes=_arch,
                                verdict=str(r.get("Category") or ""),
                                category=str(r.get("Category") or ""),
                                trigger=r.get("Entry"), entry=r.get("Entry"),
                                sl=r.get("SL"), t1=r.get("T1"), rr=r.get("R:R"),
                                sigma_pa=r.get("ΣPA"), s4go=str(r.get("S4-GO") or ""),
                                cmp_px=r.get("CMP"),
                                tf=str(st.session_state.get("gm_trig_tf") or ""),
                                note="armed from the board grid")
                    else:
                        _ar.disarm(_sym, note="unticked on the board grid")
                    _changed = True
                except Exception as e:
                    _gm_logger.warning(f"board: arm edit failed for {_sym}: {e}")
            if _changed:
                # The cached board frame still carries the PRE-edit Arm/Armed values,
                # so without this the tick visibly reverts on the rerun and the change
                # reads as "it didn't take" — the register would be right and the grid
                # would be lying. Patch the two affected cells in place rather than
                # forcing a full rebuild (which costs a fetch sweep).
                try:
                    import gm_armed as _ar2
                    _bdf_s = st.session_state.get("gm_board_df")
                    if _bdf_s is not None and "Symbol" in _bdf_s.columns:
                        _reg2 = _ar2.load()
                        _armed_now, _armed_txt = [], []
                        for _sy in _bdf_s["Symbol"].astype(str):
                            _rc = _reg2.get(_ar2.canon(_sy)) or {}
                            _on = _rc.get("status") == _ar2.STATUS_ARMED
                            _armed_now.append(_on)
                            _armed_txt.append(_ar2.summary_line(_rc) if _on else "")
                        _bdf_s["Arm"] = _armed_now
                        if "Armed" in _bdf_s.columns:
                            _bdf_s["Armed"] = _armed_txt
                        st.session_state["gm_board_df"] = _bdf_s
                except Exception as e:
                    _gm_logger.warning(f"board: Arm cell refresh failed "
                                       f"(tick may revert until rebuild): {e}")
            return _changed

        # --- LIVE header: pulsing dot + last technical refresh time ---
        def _gm_live_header(live_label):
            _ts = st.session_state.get("gm_board_tech_stamp", "—")
            st.markdown(
                f'''<div style="display:flex;align-items:center;gap:8px;margin:2px 0;">
                <span style="display:inline-block;width:9px;height:9px;border-radius:50%;
                background:#26a69a;animation:gmpulse 1.4s infinite;"></span>
                <span style="color:#26a69a;font-weight:700;font-size:13px;letter-spacing:.5px;">LIVE</span>
                <span style="color:#787b86;font-size:12px;">· technicals refresh every {live_label}
                · last {_ts}</span></div>
                <style>@keyframes gmpulse{{0%{{opacity:1;}}50%{{opacity:.25;}}100%{{opacity:1;}}}}</style>''',
                unsafe_allow_html=True)

        # --- Flashing 'Changed this tick' strip (green=improved / red=worse). The
        #     data-tick attr varies each REBUILD so the CSS animation replays on a
        #     real refresh but not on mere filter interactions. ---
        def _gm_change_strip(changes):
            if not changes:
                st.caption("· no changes on the last refresh")
                return
            _tok = st.session_state.get("gm_board_tech_ts", 0)
            _chips = []
            for _c in changes[:24]:
                _sym = _c.get("symbol", "")
                if "cat_to" in _c:
                    _up = _c.get("cat_dir", 1) > 0
                    _lbl = f"{_sym}: {str(_c['cat_from']).split(' · ')[0]}→{str(_c['cat_to']).split(' · ')[0]}"
                elif "overall_to" in _c:
                    _up = _c.get("overall_dir", 1) > 0
                    _lbl = f"{_sym}: Overall {_c['overall_from']:.0f}→{_c['overall_to']:.0f}"
                elif "cmp_to" in _c:
                    _up = _c.get("cmp_dir", 1) > 0
                    _lbl = f"{_sym} {'▲' if _up else '▼'} {_c['cmp_to']:.1f}"
                else:
                    continue
                _chips.append(f'<span class="gmchip {"gmup" if _up else "gmdn"}">{_lbl}</span>')
            st.markdown(
                f'''<div class="gmstrip" data-tick="{_tok}">{"".join(_chips)}</div>
                <style>
                .gmstrip{{margin:2px 0 8px;white-space:nowrap;overflow-x:auto;padding-bottom:4px;}}
                .gmchip{{display:inline-block;padding:3px 9px;margin:2px;border-radius:4px;
                  font-size:12px;color:var(--ink);border:1px solid #2a2e39;}}
                .gmup{{animation:gmflashup 2.6s ease-out;}}
                .gmdn{{animation:gmflashdn 2.6s ease-out;}}
                @keyframes gmflashup{{0%{{background:#1f7a6d;}}12%{{background:#26a69a;}}100%{{background:rgba(38,166,154,.10);}}}}
                @keyframes gmflashdn{{0%{{background:#a13732;}}12%{{background:#ef5350;}}100%{{background:rgba(239,83,80,.10);}}}}
                </style>''',
                unsafe_allow_html=True)

        if _refresh_all:
            _gm_reload_market_data()                      # bust disk cache + clear loaders (sets the flag)
        if _evening:
            # Sequence, not a loop of buttons: fetch once, then every TF, this window's
            # own TF last so the on-screen table is the one the selector names.
            _ev_t0 = _gtb_time.time()
            _gm_reload_market_data()
            st.session_state.pop("gm_force_rebuild", None)       # consumed here, not by the block below
            _ev_own = TF_LOCK or st.session_state.get("gm_trig_tf") or _trig_tf
            _ev_order = [t for t in ("Daily", "125m", "75m") if t != _ev_own] + [_ev_own]
            _ev_done, _ev_fail = [], []
            _ev_box = st.status("🌙 Evening run…", expanded=True)
            for _ev_tf in _ev_order:
                try:
                    _ev_box.write(f"building **{_ev_tf}** board…")
                    _board_build(force_technical=False, quiet=True, tf_override=_ev_tf)
                    _bdf_ev = st.session_state.get("gm_board_df")
                    _bn = 0 if _bdf_ev is None else len(_bdf_ev)
                    _bf = len(st.session_state.get("gm_board_failed") or [])
                    _ev_done.append(_ev_tf)
                    _ev_box.write(f"✅ {_ev_tf}: {_bn} rows" + (f" · {_bf} failed" if _bf else ""))
                except Exception as _eve:
                    _ev_fail.append(_ev_tf)
                    _gm_logger.warning(f"evening run: {_ev_tf} board failed: {_eve}")
                    _ev_box.write(f"❌ {_ev_tf}: {type(_eve).__name__}: {_eve}")
            try:
                _ev_box.write("pulling option chains (F&O names)…")
                st.session_state["_gm_opt_bundle"] = _gtb.s4_bundle_options()
                _ev_optn = len([x for x in st.session_state["_gm_opt_bundle"].split("=", 1)[-1].split(",") if x.strip()])
                _ev_box.write(f"✅ options bundle: {_ev_optn} F&O names")
            except Exception as _eve:
                st.session_state["_gm_opt_bundle"] = ""
                _ev_optn = 0
                _gm_logger.warning(f"evening run: s4_bundle_options failed: {_eve}")
                _ev_box.write(f"❌ options bundle: {_eve}")
            _ev_secs = int(_gtb_time.time() - _ev_t0)
            st.session_state["gm_evening_stamp"] = (
                f"{_gtb_dt.datetime.now().strftime('%d %b %H:%M')} · boards {len(_ev_done)}/3"
                + (f" (failed: {', '.join(_ev_fail)})" if _ev_fail else "")
                + f" · options {_ev_optn} names · {_ev_secs // 60}m{_ev_secs % 60:02d}s")
            try:
                import gm_evening_headless as _geh
                _geh.write_bundles(st.session_state.get("_gm_opt_bundle") or None, st.session_state["gm_evening_stamp"])
            except Exception as _eve:
                _gm_logger.warning(f"evening run: bundle file write failed: {_eve}")
            _ev_box.update(label=f"🌙 Evening run done — {st.session_state['gm_evening_stamp']}",
                           state="error" if _ev_fail else "complete", expanded=False)
            # The bundle blocks render ABOVE this point in the script, from the caches
            # just written: rerun so they show this run's output, not last night's.
            st.rerun()
        # Build on: the Build button, the shared Refresh, OR a refresh flagged from the
        # Single Symbol view (so both surfaces re-sync to the same fresh data).
        if _build or st.session_state.pop("gm_force_rebuild", False):
            _board_build(force_technical=False)          # full: fundamentals + technical

        # Render a Maximize button above the table area (only when the board has data)
        _bdf_check = st.session_state.get("gm_board_df")
        if _bdf_check is not None and not _bdf_check.empty:
            is_max_board = (st.query_params.get("view") == "gm_board_maximized")
            if not is_max_board:
                st.markdown(
                    '''<div style="display: flex; justify-content: flex-end; margin-bottom: 8px; gap: 6px;">
                    <a href="/?view=gm_board_maximized" target="gm_board_main" style="text-decoration: none;">
                        <span style="display: inline-block; padding: 6px 14px; border: 1.5px solid var(--acc-rule);
                        background: var(--acc-bg); color: var(--acc); border-radius: 6px; font-size: 12px;
                        font-family: 'JetBrains Mono', monospace; font-weight: 700; cursor: pointer;
                        transition: all 0.2s ease; box-shadow: 0 2px 6px rgba(37,99,235,0.15);">
                            ↗️ MAXIMIZE BOARD
                        </span>
                    </a>
                    <a href="/?view=gm_board_maximized&tf=75m" target="gm_board_75m" style="text-decoration:none;">
                        <span style="display:inline-block;padding:6px 12px;border:1.5px solid var(--bull-rule);
                        background:var(--bull-bg);color:var(--bull);border-radius:6px;font-size:12px;
                        font-family:'JetBrains Mono',monospace;font-weight:700;cursor:pointer;
                        box-shadow:0 2px 6px rgba(21,128,61,0.15);">
                            ↗️ 75m BOARD
                        </span>
                    </a>
                    <a href="/?view=gm_board_maximized&tf=Daily" target="gm_board_Daily" style="text-decoration:none;">
                        <span style="display:inline-block;padding:6px 12px;border:1.5px solid var(--acc-rule);
                        background:var(--acc-bg);color:var(--acc);border-radius:6px;font-size:12px;
                        font-family:'JetBrains Mono',monospace;font-weight:700;cursor:pointer;
                        box-shadow:0 2px 6px rgba(29,78,216,0.15);">
                            ↗️ DAILY BOARD
                        </span>
                    </a>
                    <a href="/?view=gm_board_maximized&tf=125m" target="gm_board_125m" style="text-decoration:none;">
                        <span style="display:inline-block;padding:6px 12px;border:1.5px solid var(--warn-rule);
                        background:var(--warn-bg);color:var(--warn);border-radius:6px;font-size:12px;
                        font-family:'JetBrains Mono',monospace;font-weight:700;cursor:pointer;
                        box-shadow:0 2px 6px rgba(180,83,9,0.15);">
                            ↗️ 125m BOARD
                        </span>
                    </a>
                    <!-- OPEN ALL 3, IN THE ORDER THAT LANDS THEM 75m | 125m | Daily.
                         Chrome inserts a target=_blank tab immediately AFTER the opener,
                         so three separate presses land in REVERSE of the press order —
                         which is what Jay was seeing. Tab position is not settable from
                         JS at all, so the only lever is creation order: open Daily first,
                         then 125m, then 75m, and each one pushes the previous right.
                         Named targets mean a re-press REUSES that board tab instead of
                         opening a duplicate. -->
                    </div>''',
                    unsafe_allow_html=True
                )
                # ALL 3 BOARDS — rendered as a COMPONENT, not markdown (10-Aug-2026).
                # It was a <span onclick=...> inside st.markdown(unsafe_allow_html=True),
                # and Streamlit's markdown sanitiser STRIPS inline on* handlers, so the
                # click was silently doing nothing. The three single-TF buttons beside it
                # kept working because they are <a href> anchors, which the sanitiser keeps
                # — same block, same styling, and only the JS one was dead. Anything that
                # needs to RUN script has to go through components.html, which renders in
                # an iframe where scripts execute.
                _a3l, _a3r = st.columns([5, 1])
                with _a3r:
                    st_components.html(
                        """<button id="all3" style="width:100%;padding:6px 12px;
                            border:1.5px solid var(--acc-rule);background:var(--surface-2);color:var(--acc);
                            border-radius:6px;font-size:12px;font-family:'JetBrains Mono',monospace;
                            font-weight:700;cursor:pointer;box-shadow:0 2px 6px rgba(109,40,217,0.15);">
                            &#8599;&#65039; ALL 3 BOARDS</button>
                        <script>
                        document.getElementById('all3').onclick = function () {
                          // Creation order is the ONLY lever on tab position: Chrome inserts a
                          // new tab immediately after the opener, so opening Daily -> 125m ->
                          // 75m lands them left-to-right as 75m | 125m | Daily. Named targets
                          // mean a re-press REUSES each board tab instead of duplicating it.
                          var w = window.parent || window;   // break out of the component iframe
                          var blocked = [];
                          [['Daily','gm_board_Daily'],['125m','gm_board_125m'],['75m','gm_board_75m']]
                            .forEach(function (t) {
                              // window.open returns NULL when the popup blocker refuses it.
                              // Browsers allow ONE popup per user gesture, so without
                              // "Allow pop-ups" for this origin only the FIRST call lands —
                              // which is exactly the "only the Daily board opens" symptom,
                              // Daily being the one opened first. Report it rather than
                              // silently delivering one board out of three.
                              var h = w.open('/?view=gm_board_maximized&tf=' + t[0], t[1]);
                              if (!h) { blocked.push(t[0]); }
                            });
                          document.getElementById('all3msg').innerHTML = blocked.length
                            ? '&#9888; blocked: ' + blocked.join(', ') + ' — allow pop-ups for '
                              + w.location.host + ', or use the single-TF buttons'
                            : '';
                        };
                        </script>
                        <div id="all3msg" style="font-family:'JetBrains Mono',monospace;
                            font-size:10px;color:var(--warn);margin-top:4px;line-height:1.25;"></div>""",
                        height=68)

        # ── SHARED header — warnings + filters + CSV download rendered ONCE for
        #    BOTH render paths (static editor AND streaming grid) so filters are
        #    user-adjustable in every mode and the download can't regress. ──
        def _board_apply_filters(bdf):
            """RRG overlay + the 4 session_state filters + sort — the ONE filter
            definition the static editor, the streaming grid AND the CSV download
            all share, so they can never disagree."""
            v = bdf.copy()
            # RRG = the COMPUTED quadrant (25-Sep-2026). A cache built before then
            # carries it as "RRGeng" beside a stale manual "RRG"; fold it across.
            if "RRGeng" in v.columns:
                v["RRG"] = v["RRGeng"].fillna("—")
                v = v.drop(columns=["RRGeng"])
            for _key, _col in (("gm_bf_cat", "Category"), ("gm_bf_rrg", "RRG"),
                               ("gm_bf_tier", "Tier"), ("gm_bf_path", "Path")):
                _sel = st.session_state.get(_key) or []
                if _sel and _col in v.columns:
                    v = v[v[_col].isin(_sel)]
            # GO-ONLY (19-Aug-2026, Jay's default). Keep only rows whose S4-GO contains
            # "GO" - i.e. a LIVE GO on the current bar.
            #
            # READ THIS BEFORE WIDENING IT: s4go_status emits "4/4 GO" only when the PA
            # fired on the live bar; when it fired earlier it emits "4/4 · PA 3b", with
            # no "GO" in the string. So this filter also hides names where all four
            # gates pass but the pattern is a few bars old - CHOLAFIN was exactly that
            # ("4/4 · PA 3b · PB · ↑W") on 18-Aug and was worth a look. Measured on the
            # live 75m cache: 4 of 49 rows kept, and the recency 4/4s are among the 45
            # dropped. Match on "4/4" instead of "GO" if you want those back.
            # Default ON, cleared from the board header, and it lives HERE so the grid,
            # the static editor and the CSV download can never disagree about what you
            # are looking at.
            if st.session_state.get("gm_bf_go_only", True) and "S4-GO" in v.columns:
            # ALL-GATES-PASS filter (19-Aug-2026, Jay's default). Matches "4/4", NOT "GO".
            #
            # s4go_status emits "4/4 GO" only when the PA fired on the LIVE bar; a few
            # bars old it emits "4/4 · PA 3b" with no "GO" in the string. Matching "GO"
            # therefore hid names where all four gates pass but the pattern is not fresh
            # - CHOLAFIN was exactly that on 18-Aug ("4/4 · PA 3b · PB · ↑W"). Jay's call:
            # show the recency 4/4s.
            #
            # Anchored to the START of the string on purpose: the upstream vetoes render
            # as "⛔ Stage 3 · gates 4/4" / "⛔ RRG WAIT · gates 4/4", which CONTAIN "4/4".
            # startswith keeps them out; a plain `contains` would let a Stage-4 name back
            # onto a board that exists to show tradeable names.
                v = v[v["S4-GO"].astype(str).str.strip().str.startswith("5/5")]
            if not v.empty:
                # SORT: Overall descending (Jay's default) - was sort_values("Symbol"),
                # an alphabetical re-sort that silently discarded the Overall ranking the
                # board had already applied upstream, so the grid opened in name order.
                # Symbol breaks ties so the order is stable between rebuilds.
                if "Overall" in v.columns:
                    v = v.sort_values(["Overall", "Symbol"], ascending=[False, True],
                                      na_position="last")
                else:
                    v = v.sort_values("Symbol")
                v = v.reset_index(drop=True)
            return v

        _bdf_hdr = st.session_state.get("gm_board_df")
        if _bdf_hdr is not None and not _bdf_hdr.empty:
            # P1 failure counts + TF-staleness guard — now visible in EVERY mode.
            _bfail = st.session_state.get("gm_board_failed") or []
            if _bfail:
                st.warning(f"⚠️ Built {len(_bdf_hdr)}/{len(_bdf_hdr) + len(_bfail)} — "
                           f"**{len(_bfail)} failed:** {', '.join(_bfail[:10])}"
                           + (" …" if len(_bfail) > 10 else "") + "  ·  `logs/gm_errors.log`")
            # S4-GO "n/a" CAUSE strip — an all-n/a column is a data/feed problem,
            # not a scoring one, and used to say nothing. Counts are bucketed by
            # gm_load_intraday's stable code; the sample names let you spot-check.
            _intra_iss = st.session_state.get("gm_board_intra_issues") or []
            if _intra_iss:
                _na_tot = sum(_i["count"] for _i in _intra_iss)
                _lines = []
                for _i in _intra_iss:
                    _s = ", ".join(_i["symbols"][:6])
                    if _i["count"] > len(_i["symbols"][:6]):
                        _s += " …"
                    _lines.append(f"- **{_i['count']}× {_i['reason']}**  ·  {_s}")
                _auth_hit = any(_i["code"] == "auth" for _i in _intra_iss)
                _hdr = (f"⚠️ **S4-GO `n/a` for {_na_tot}/{len(_bdf_hdr)}** — no intraday "
                        f"trigger-TF read (a DATA/FEED gap, not a scoring result):")
                _tail = ("\n\n🔑 **Dhan auth expired** — the feed self-heals on a retry "
                         "(re-validated token, ~5 min); **Refresh Data** to force it now. "
                         "A restart is no longer required."
                         if _auth_hit else
                         "\n\nS4-GO needs a 75m/125m read; these names fall back to Daily PA.")
                st.warning(_hdr + "\n\n" + "\n".join(_lines) + _tail + "\n\n`logs/gm_errors.log`")
            _built_tf = st.session_state.get("gm_board_built_tf")
            if _built_tf and _built_tf != _trig_tf:
                st.warning(f"⚠️ Board built at **{_built_tf}** but Trigger-TF is now **{_trig_tf}** — "
                           f"stale snapshot; **Build / Refresh** to recompute at {_trig_tf}.")

            # ── SECTOR MIX (13-Aug-2026) ─────────────────────────────────────
            # Jay: "why am I mostly seeing pharma trades almost everyday?"
            # Measured: pharma was 20.4% of qualifiers against 9.8% of the Nifty
            # 500 (2.08x). About half of that is legitimate - pharma is a big
            # sector AND has the best uptrend breadth (76% above the 200-DMA vs
            # IT 31%) - and a sector cap INSIDE the screener was already tested
            # and rejected for cutting alpha. So the tilt is not a bug to fix in
            # the filters; it is something you should SEE while picking.
            #
            # The threshold is pre_trade_gate.SECTOR_CAP_PCT, imported rather than
            # duplicated: that is the cap the ORDER path actually enforces, so the
            # board warns with the same number that will later refuse the entry.
            # GO-only switch for the filter above. Shows how many rows it is hiding so
            # an empty-looking board is never mistaken for a failed build.
            _go_tot = (int(_bdf_hdr["S4-GO"].astype(str).str.strip().str.startswith("5/5").sum())
                       if "S4-GO" in _bdf_hdr.columns else 0)
            st.checkbox(f"All gates (5/5) only  ·  {_go_tot} of {len(_bdf_hdr)} rows",
                        value=True, key="gm_bf_go_only",
                        help="Default ON: only names where all five gates pass - both a live "
                             "'5/5 GO' and a recent '5/5 · PA 3b'. The fifth is fundamentals, "
                             "the same floor S4 shows as its F chip. Sorted by Overall "
                             "descending. Untick to see the near-misses (4/5, 3/5) and the "
                             "upstream vetoes (Stage, RRG, funda). Applies to the grid AND the CSV.")
            try:
                import sector_lookup as _sl
                _mix_src = _board_apply_filters(_bdf_hdr)
                if not _mix_src.empty:
                    def _sec1(_s):
                        try:
                            _r = _sl.get_sector(str(_s).upper()) or {}
                            return _r.get("display_name") or _r.get("sector_name") or "?"
                        except Exception:
                            return "?"
                    _secs = [_sec1(x) for x in _mix_src["Symbol"]]
                    _tot = len([x for x in _secs if x != "?"])
                    if _tot >= 5:
                        from collections import Counter
                        try:
                            from pre_trade_gate import SECTOR_CAP_PCT as _CAP
                        except Exception:
                            _CAP = 25.0
                        _cnt = Counter(x for x in _secs if x != "?")
                        _parts, _hot = [], []
                        for _k, _v in _cnt.most_common(6):
                            _p = _v / _tot * 100.0
                            _parts.append(f"**{_k} {_p:.0f}%** ({_v})" if _p >= _CAP
                                          else f"{_k} {_p:.0f}% ({_v})")
                            if _p >= _CAP:
                                _hot.append(f"{_k} {_p:.0f}%")
                        st.caption("Sector mix of the rows shown:  " + "  ·  ".join(_parts))
                        if _hot:
                            _hot_txt = ", ".join(_hot)
                            st.caption(f"⚠️ {_hot_txt} is at or over the "
                                       f"{_CAP:.0f}% sector cap the order gate enforces — "
                                       f"further entries there may be refused at placement.")
            except Exception as _e_mix:
                _gm_logger.debug(f"sector mix strip skipped: {_e_mix}")

        # CAPITAL QUEUE (25-Sep-2026) — the same engine the Risk Shield renders
        # (capital_queue.py): today's ADD-rated holdings and live names on ONE scale,
        # funded by EXITs. Built on demand so the board's bar-close refresh stays fast.
        with st.expander("💰 Capital Queue — where the next rupee goes (adds vs new names)", expanded=False):
            try:
                import capital_queue as _cq
                _cq_exit_toggle("cq_exits_board")
                if st.button("Build / rebuild the queue", key="cq_rebuild_board"):
                    st.session_state["cq_res"] = _cq_build_now()
                if "cq_res" in st.session_state:
                    _cq.render(st, st.session_state["cq_res"])
                else:
                    st.caption("Press the button to rank today's live names and ADD-rated holdings "
                               "against your available cash. Same queue as Risk Shield → 💰 Capital Queue.")
            except Exception as _cqe:
                st.error(f"Capital queue failed: {type(_cqe).__name__}: {_cqe}")

        _gm_col1, _gm_col2, _gm_col3 = st.columns([2.5, 3.5, 3.0], gap="small")
        # THE place to look when an alert fires days later: the plan you armed with,
        # beside what the board says about the name today. Rendered here (above the
        # grid) rather than as a separate page because the alert-fires moment IS a
        # board moment — you want the live row and the armed plan in one view.
        try:
            import gm_armed as _armreg
            _areg = _armreg.active()
            with st.expander(f"🔔 Armed Register — {len(_areg)} name(s) being watched",
                             expanded=False):
                if not _areg:
                    st.caption("Nothing armed. Open a name in Single Symbol, set the "
                               "TradingView alert, then press **Arm + record plan** — the "
                               "register keeps it on this board after the watchlists drop "
                               "it, and holds the levels for when the alert fires.")
                else:
                    st.caption("**Armed plan** = the levels as of the day you armed it. The "
                               "board row above is **live**. Compare the two before acting — "
                               "a wide gap means the setup moved on without you.")
                    _on_board = set(_bdf_hdr["Symbol"].astype(str).str.upper()) \
                        if "Symbol" in _bdf_hdr.columns else set()
                    for _asym, _arec in sorted(
                            _areg.items(), key=lambda kv: kv[1].get("first_armed") or ""):
                        _d = _armreg.days_armed(_arec)
                        _live_row = _bdf_hdr[_bdf_hdr["Symbol"].astype(str).str.upper() == _asym] \
                            if "Symbol" in _bdf_hdr.columns else None
                        _cat_now = (str(_live_row.iloc[0].get("Category", "—"))
                                    if _live_row is not None and not _live_row.empty else "—")
                        _s4_now = (str(_live_row.iloc[0].get("S4-GO", "—"))
                                   if _live_row is not None and not _live_row.empty else "—")
                        _r1, _r2 = st.columns([5, 1], gap="small")
                        with _r1:
                            st.markdown(
                                f"**{_asym}** · armed **{_d}d** ago ({_arec.get('armed_on')}) · "
                                f"{', '.join(_arec.get('archetypes') or []) or 'no archetype'} · "
                                f"{_arec.get('path', 'bull').title()}  \n"
                                f"　armed plan: trigger **₹{_arec.get('trigger') or '—'}** · "
                                f"SL ₹{_arec.get('sl') or '—'} · T1 ₹{_arec.get('t1') or '—'} · "
                                f"“{_arec.get('verdict') or '—'}” ({_arec.get('s4go') or '—'})  \n"
                                f"　now: **{_cat_now}** · S4-GO **{_s4_now}**"
                                + ("" if _asym in _on_board else
                                   "  \n　⚠️ no longer on any watchlist — the register is the "
                                   "only reason this name is still here")
                                + f"  \n　expires {_arec.get('expires_on')}")
                        with _r2:
                            if st.button("Filled", key=f"armfill_{_asym}",
                                         use_container_width=True,
                                         help="Mark TRIGGERED — you took the trade."):
                                _armreg.triggered(_asym); st.rerun()
                            if st.button("Drop", key=f"armdrop_{_asym}",
                                         use_container_width=True,
                                         help="Stop watching. Kept as CANCELLED, not deleted."):
                                _armreg.disarm(_asym, note="dropped from register panel")
                                st.rerun()
                        st.markdown("<hr style='margin:4px 0;border-color:var(--rule)'>",
                                    unsafe_allow_html=True)
        except Exception as _are:
            _gm_logger.warning(f"armed register panel failed: {_are}")

        if _live == "Off":
            _board_render()
        else:
            # ── Streaming AG-Grid (Option B): live PRICE via Dhan MarketFeed +
            #    AG-Grid native cell-flash; heavy DECISIONS recompute on cadence. ──
            _bar_mode = _live.endswith("bar-close") or _live.startswith("Check-in")
            # Order matters: test the UNION label before the "125" prefix test, or
            # "75m+125m" would fall through to plain 75m and silently drop 11:20/13:25.
            if _live.startswith("Check-in"):
                # Jay's desk schedule. The TIMES differ per tab, so this follows the
                # board's own Trigger-TF rather than a label — a Daily tab has nothing
                # to rebuild intraday and gets the single post-close pass.
                _ctf = str(st.session_state.get("gm_trig_tf") or _gm_settings().get("trigger_tf") or "75m")
                _bar_tf = ("checkin-125m" if _ctf.startswith("125")
                           else "checkin-Daily" if _ctf.lower().startswith("d")
                           else "checkin-75m")
            else:
                _bar_tf = ("75m+125m" if _live.startswith("75m+125m")
                           else "125m" if _live.startswith("125") else "75m")
            _iv_sec = {"1 min": 60, "2 min": 120, "3 min": 180, "5 min": 300,
                       "10 min": 600, "15 min": 900}.get(_live, 0)
            _stream_ok = True
            try:
                from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
                import dhan_marketfeed as _dmf
                _dmf.subscribe_symbols(list(_uni.keys()))          # start/extend the live feed
            except Exception as _age:
                _stream_ok = False
                st.warning(f"Streaming grid unavailable ({_age}) — falling back to the static grid.")
                _board_render()

            if _stream_ok:
                @st.fragment(run_every="3s")
                def _gm_stream():
                    # (1) HEAVY decision refresh (category/scores) + toasts. Two
                    # cadences: BAR-CLOSE (rebuild once per 75/125m session bar so
                    # the board reads CLOSED bars) or fixed N-min interval.
                    _now = _gtb_time.time()
                    _last = st.session_state.get("gm_board_tech_ts", 0)
                    if _bar_mode:
                        _bnd = _gm_last_passed_boundary(_bar_tf)
                        _need = (_bnd is not None and
                                 st.session_state.get("gm_board_last_boundary") != _bnd.isoformat())
                    else:
                        _need = (_iv_sec > 0) and ((_now - _last) >= _iv_sec)
                    if st.session_state.get("gm_board_df") is not None and _need:
                        _prev = st.session_state.get("gm_board_df")
                        _prev = _prev.copy() if _prev is not None else None
                        _board_build(force_technical=True, quiet=True)
                        if _bar_mode and _bnd is not None:
                            st.session_state["gm_board_last_boundary"] = _bnd.isoformat()
                        _chg = _gtb.diff_boards(_prev, st.session_state.get("gm_board_df"))
                        st.session_state["gm_board_changes"] = _chg
                        for _c in _chg:
                            if _c.get("to_go"):
                                st.toast(f"🟢 **{_c['symbol']}** → Buy Trigger Live", icon="🟢")
                    # Header label: for bar-close mode show the NEXT session close.
                    _hdr_lbl = _live
                    if _bar_mode:
                        _closes = _gm_bar_close_times(_bar_tf)
                        _nowdt = datetime.now()
                        _nxt = next((f"{h:02d}:{m:02d}" for h, m in _closes
                                     if _nowdt.replace(hour=h, minute=m, second=0, microsecond=0) > _nowdt), None)
                        _hdr_lbl = (f"{_bar_tf} bar-close · next {_nxt}" if _nxt
                                    else f"{_bar_tf} bar-close · session done")
                    _gm_live_header(_hdr_lbl)
                    _gm_change_strip(st.session_state.get("gm_board_changes"))
                    _bdf = st.session_state.get("gm_board_df")
                    if _bdf is None or _bdf.empty:
                        st.info("Click **Build / Refresh** to populate the board.")
                        return
                    # SHARED filter — identical to the static editor + CSV download,
                    # and now user-adjustable via the header multiselects in this mode.
                    _v = _board_apply_filters(_bdf)
                    # (2) FAST live-price overlay every 3s from the streaming feed
                    def _ltp(s):
                        p = _dmf.get_live_price(s)
                        return p if (p and p > 0) else None
                    _v["CMP"] = _v["Symbol"].map(_ltp).fillna(_v["CMP"])
                    if "PrevClose" in _v.columns:
                        _pc = pd.to_numeric(_v["PrevClose"], errors="coerce")
                        _cm = pd.to_numeric(_v["CMP"], errors="coerce")
                        _v["Chg%"] = (((_cm - _pc) / _pc) * 100).where(_pc > 0).round(2)
                    # Coerce the decision numbers to numeric dtype so AG-Grid sorts them
                    # numerically (not lexicographically) and the number filter works —
                    # a CSV round-trip (disk cache reload) can leave them as object.
                    for _nc in ("Overall", "Alpha", "RS", "Conviction", "Combined", "ΣPA",
                                "R:R", "CMP", "Chg%", "52WH%", "SL%", "MLProb%",
                                "Entry", "SL", "T1", "P/E"):
                        if _nc in _v.columns:
                            _v[_nc] = pd.to_numeric(_v[_nc], errors="coerce")
                    # Column order (item 14): decision columns first, then group the
                    # context metrics (RS · Stage · Catalyst · ΣPA · BFF · RFF) right
                    # after RRG, then everything else.
                    # "Pos" sits beside Archetype: on a Pyramid row it says what is already
                    # held and what the add would be, and is blank on every other row.
                    _front = ["Symbol", "★", "Overall", "Category", "S4-GO", "Archetype",
                              "Pos", "Loc", "Path", "RRG", "RS", "Stage", "Catalyst", "ΣPA",
                              "BFF", "RFF"]
                    _ordered = ([c for c in _front if c in _v.columns]
                                + [c for c in _v.columns if c not in _front])
                    _v = _v[_ordered]
                    # (3) AG-Grid with native cell-change flash on the live columns.
                    # Per-column SORT (click header) + FILTER with an always-visible
                    # FLOATING FILTER row so it's discoverable, not a hover menu (Jay).
                    _gb = GridOptionsBuilder.from_dataframe(_v)
                    # minWidth (3-Aug): a FLOOR no column can contract below, whatever
                    # AG-Grid decides on re-render. Explicit widths alone were not holding
                    # on rebuild — this makes narrowing structurally impossible rather than
                    # relying on the width hint being honoured.
                    _gb.configure_default_column(sortable=True, filter=True, resizable=True,
                                                 floatingFilter=True, minWidth=120,
                                                 suppressSizeToFit=True)
                    # Numeric columns get a NUMBER filter (>, <, range) + numeric sort;
                    # AG-Grid otherwise treats them as text (lexicographic) when the
                    # pandas dtype is object. Explicit for the key decision numbers.
                    for _nc in ("Overall", "Alpha", "RS", "Conviction", "Combined", "ΣPA",
                                "R:R", "CMP", "Chg%", "52WH%", "SL%", "MLProb%"):
                        if _nc in _v.columns:
                            # sortingOrder desc-FIRST (21-Aug): AG-Grid's default cycle is
                            # asc -> desc -> none, so on a ranked number the first click
                            # gives you the WORST rows. For a decision board the useful
                            # end is always the top, so descending is the first click.
                            _gb.configure_column(_nc, type=["numericColumn"],
                                                 filter="agNumberColumnFilter",
                                                 sortingOrder=["desc", "asc", None])
                    # Pin the decision columns to the left so they are ALWAYS visible
                    # (the grid has ~39 cols). Item 12: Path + RRG join the pinned set so
                    # the full decision row (Symbol · Overall · Category · S4-GO ·
                    # Archetype · Loc · Path · RRG) stays on-screen without scrolling.
                    # Widths sized from the WIDEST value actually in the board cache, not
                    # guessed (3-Aug): Category 28 chars, S4-GO 22, Archetype 46, Pos 72,
                    # Loc 36. The old numbers truncated every one of those, and because
                    # AG-Grid discards a hand-dragged width on each rerun, a rebuild threw
                    # the manual re-widening away every single time.
                    for _pc, _pw in (("Symbol", 105), ("★", 46), ("Overall", 95),
                                     ("Category", 215), ("S4-GO", 175), ("Archetype", 250),
                                     ("Pos", 330), ("Loc", 230), ("Path", 90), ("RRG", 120)):
                        if _pc in _v.columns:
                            # minWidth == width: AG-Grid may re-flow on re-render, but it
                            # cannot go below minWidth, so the decision columns keep their
                            # size through a rebuild without any manual re-widening.
                            _gb.configure_column(_pc, pinned=(None if MOBILE_VIEW else "left"),
                                                 width=_pw, minWidth=_pw, suppressSizeToFit=True)
                    # Grid-level sort indicator, matching the dataframe order applied in
                    # _board_apply_filters, so the header arrow agrees with what is on
                    # screen. The maximized board keeps S4-GO primary (it is a GO monitor);
                    # Overall is primary everywhere else.
                    if "Overall" in _v.columns:
                        _gb.configure_column("Overall", sort="desc",
                                             sortIndex=(1 if is_max_board else 0))
                    if "S4-GO" in _v.columns:
                        _gb.configure_column("S4-GO",
                            **({"sort": "desc", "sortIndex": 0} if is_max_board else {}),
                            cellStyle=JsCode(
                            "function(p){var v=String(p.value||'');"
                            "if(v.indexOf('5/5')>=0)return{'color':'#26a69a','fontWeight':'700'};"
                            "if(v.indexOf('3/4')>=0)return{'color':'var(--warn)','fontWeight':'600'};"
                            "if(v.indexOf('2/4')>=0)return{'color':'#ff9800'};"
                            "return{'color':'#787b86'};}"))
                    if "Arm" in _v.columns:
                        # Boolean + editable renders AG-Grid's native checkbox, and the
                        # VALUE_CHANGED update mode already round-trips edits, so no extra
                        # plumbing is needed.
                        _gb.configure_column("Arm", editable=True, pinned="left", width=52,
                                             cellRenderer="agCheckboxCellRenderer",
                                             cellEditor="agCheckboxCellEditor")
                    if "PrevClose" in _v.columns:
                        _gb.configure_column("PrevClose", hide=True)
                    for _cc in ("CMP", "Chg%", "Overall", "R:R"):
                        if _cc in _v.columns:
                            _gb.configure_column(_cc, enableCellChangeFlash=True)
                    if "Category" in _v.columns:
                        _gb.configure_column("Category", cellStyle=JsCode(
                            "function(p){var v=String(p.value||'');"
                            "if(v.indexOf('Buy Trigger Live')>=0)return{'color':'#26a69a','fontWeight':'700'};"
                            "if(v.indexOf('Armed')>=0)return{'color':'#ff9800'};"
                            "if(v.indexOf('Wait for Pullback')>=0)return{'color':'var(--warn)'};"
                            "return{};}"))
                    # 21-Aug: apply the default sort STATE explicitly. A colDef `sort`
                    # is honoured only when the grid first mounts; with a stable component
                    # key the grid persists across reruns and comes back unsorted, which is
                    # why the board needed one manual click. onGridReady + onFirstDataRendered
                    # fire on mount and on each new data set -- NOT on user header clicks --
                    # so this seeds the default without fighting a sort Jay chooses later.
                    _sort_primary = "S4-GO" if is_max_board else "Overall"
                    _sort_second = "Overall" if is_max_board else "S4-GO"
                    _apply_sort_js = JsCode(
                        "function(p){try{p.api.applyColumnState({state:["
                        f"{{colId:'{_sort_primary}',sort:'desc',sortIndex:0}},"
                        f"{{colId:'{_sort_second}',sort:'desc',sortIndex:1}}"
                        "],defaultState:{sort:null}});}catch(e){}}")
                    _go = _gb.build()
                    _go["onGridReady"] = _apply_sort_js
                    _go["onFirstDataRendered"] = _apply_sort_js
                    _resp = AgGrid(_v, gridOptions=_go,
                                   height=(880 if is_max_board else 560), theme="streamlit",
                                   allow_unsafe_jscode=True, reload_data=False,
                                   update_mode=GridUpdateMode.VALUE_CHANGED, key="gm_aggrid")
                    # Arm ticks — SAME shared write-back the data_editor path uses.
                    try:
                        if _gm_apply_arm_edits(_resp["data"]):
                            st.rerun()
                    except Exception as e:
                        _gm_logger.warning(f"stream grid: arm edit persist failed: {e}")

                _gm_stream()
        st.stop()

    else:   # ── 🎯 SINGLE SYMBOL VIEW ─────────────────────────────────────────────

        _gm_col1, _gm_col2, _gm_col3 = st.columns([2.5, 3.5, 3.0], gap="small")
        with _gm_col1:
            auto_sync = st.toggle("🔄 Auto-Sync TV", value=True, key="gm_auto_sync", help="Automatically sync with active TradingView chart")
            if auto_sync:
                auto_sync_tv_symbol_gm()
        
            if "gm_sym_input" not in st.session_state:
                st.session_state["gm_sym_input"] = "NETWEB.NS"
            
            symbol = st.text_input("NSE symbol", key="gm_sym_input").strip().upper()
            symbol = _canon_sym(symbol)
            if symbol and symbol != st.session_state.get("gm_symbol"):
                st.session_state["gm_symbol"] = symbol
            
        with _gm_col2:
            st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Fetch fresh data (both surfaces)", use_container_width=True,
                         help="Re-fetch FRESH data for the whole Golden Matcher universe, then rebuild the board."):
                _gm_reload_market_data()
                st.rerun()

        with _gm_col3:
            _render_entry_method_selector("gm_entry_method_sel_single")

        # ---- Position-sizing & Trigger TF settings ----
        _gmset = _gm_settings()
        _szc1, _szc2, _szc3, _szc5, _szc4 = st.columns([2.0, 1.1, 1.1, 1.6, 2.7], gap="small")
        with _szc1:
            _gm_capital = st.number_input("Capital (₹)", min_value=0.0, step=50000.0,
                                          value=float(_gmset.get("capital", 0.0)),
                                          format="%.0f", key="gm_capital",
                                          help="Trading capital used for position sizing.")
        # Risk % is a HOUSE RULE, not a setting (house_policy.py, 25-Sep-2026) - shown, not
        # edited, so this panel can no longer drift from the queue, the sniper or Risk Shield.
        _gm_riskpct = _HP.RISK_NEW_STOCK_PCT
        _gm_pyrrisk = _HP.RISK_ADD_PCT
        with _szc2:
            st.metric("Risk %", f"{_gm_riskpct:g}", help=f"House rule: {_HP.risk_label()}. "
                      "An ETF sizes at 1.5x the stock base, the same factor S4 applies. Change it in house_policy.py.")
        with _szc3:
            st.metric("Add risk %", f"{_gm_pyrrisk:g}", help="House rule for a PYRAMID add (house_policy.py).")
        with _szc5:
            # MAX ALLOCATION (5-Aug-2026, Jay: "I'm limiting my amount per trade to 1 lakh").
            # Mirrors S4's size_max_alloc so the two surfaces cannot disagree about size —
            # without it the board sized this book at ~10x what S4 showed.
            # NOTE it usually BINDS: at a 3% stop, 1% of 30L wants ~10L of stock, so a 1L
            # cap decides the size and the risk% never gets a say. That is not a bug, but
            # it does mean the effective risk is cap x stop% (~0.1% here), NOT the risk%
            # above — the sizer says which rule bound so the number is never mysterious.
            _gm_maxalloc = st.number_input("Max ₹/trade", min_value=0.0, step=25000.0,
                                           value=float(_gmset.get("max_alloc", 0.0)),
                                           format="%.0f", key="gm_maxalloc",
                                           help="Hard rupee ceiling on one position: Qty = min(risk-based qty, "
                                                "this ÷ entry). 0 = the house default ₹1,00,000 (S4's), never "
                                                "uncapped. Set it to the same value as S4's "
                                                "'Max allocation per trade (₹)' or the two surfaces will size "
                                                "differently.")
        with _szc4:
            _tf_opts = ["75m", "125m", "Daily"]
            if "gm_trig_tf" not in st.session_state:
                _tf0 = str(_gmset.get("trigger_tf", "75m"))
                st.session_state["gm_trig_tf"] = _tf0 if _tf0 in _tf_opts else "75m"
            _gm_trig_tf = st.radio(
                "Trigger TF (Step-5 PA battery + momentum board)", _tf_opts, horizontal=True,
                key="gm_trig_tf",
                help="Shared with the Trigger Board.")
        _lv_now = st.session_state.get("gm_board_live")
        if (_gm_capital != _gmset.get("capital")) \
                or (_gm_trig_tf != _gmset.get("trigger_tf")) \
                or (_gm_maxalloc != _gmset.get("max_alloc")) \
                or (_lv_now and _lv_now != _gmset.get("board_live")):
            if TF_LOCK:
                _gm_settings_save(board_live=_lv_now, capital=_gm_capital,
                                  max_alloc=_gm_maxalloc)
            else:
                _gm_settings_save(board_live=_lv_now, capital=_gm_capital,
                                  trigger_tf=_gm_trig_tf, max_alloc=_gm_maxalloc)

        if not symbol:
            st.info("Enter an NSE symbol in the sidebar.")
            st.stop()
    
        data = gm_load_symbol(symbol)

        # ---- Auto-heal a stale served frame (9-Jul-2026) --------------------------
        # A 2y/1d request carries the 24h weekly TTL, so a daily frame written after
        # yesterday's close is re-served all of today even though a newer session has
        # closed. If the served last bar is older than the last completed trading
        # session, bust this symbol's on-disk cache ONCE and reload — the network
        # then supplies the fresh bar. Guarded per (symbol, target-session) so it can
        # never loop when the provider genuinely hasn't published the new bar yet
        # (then the STALE banner shows and manual Refresh remains available).
        try:
            _df_h = data.get("df")
            if _df_h is not None and len(_df_h):
                _lb = _df_h.index[-1].date()
                _target = _expected_last_session()   # session-aware: today after 15:30 IST close
                if _lb < _target:
                    _heal_key = f"{symbol}|{_target.isoformat()}"
                    if st.session_state.get("gm_autoheal") != _heal_key:
                        st.session_state["gm_autoheal"] = _heal_key
                        import data_provider as _dph
                        _dph.invalidate_symbol(symbol)
                        gm_load_symbol.clear()
                        gm_load_recovery.clear()
                        st.rerun()
        except Exception as e:
            # (st.rerun's RerunException inherits BaseException, not Exception — it
            # passes through this handler untouched; verified on streamlit 1.53.1.)
            _gm_logger.warning(f"{symbol}: stale-frame auto-heal failed (STALE banner remains): {e}")

        # ---- SINGLE SOURCE OF TRUTH ------------------------------------------------
        # Evaluate EXACTLY like the Trigger Board: gm_evaluate() is the one function
        # both surfaces call, so cmp_px / intraday overlay / inherited setup / the two
        # workflows are byte-identical here and on the board. No more duplicated
        # assembly = no more category disagreement.
        _deep_rec = bool(st.session_state.get(f"gm_deeprec_{symbol}", False))
        _trig_tf = st.session_state.get("gm_trig_tf", "75m")
        _ev = gm_evaluate(symbol, trigger_tf=_trig_tf, deep_rec=_deep_rec)
        data = _ev["data"]
        rec = _ev["rec"]; ctx = _ev["ctx"]; fun = _ev["fun"]
        rec_r = _ev["rec_r"]
        wf_bull = _ev["wf_bull"]; wf_rec = _ev["wf_rec"]
        _intra_ok = _ev["intra_ok"]; _intra_label = _ev["intra_label"]
        _ib_ss = _ev["inherited_bull"]; _ir_ss = _ev["inherited_rec"]
        _inh_bull_on = bool(wf_bull.get("inherited"))
        _inh_rec_on = bool(wf_rec.get("inherited")) if wf_rec else False
        # Trigger-Board-IDENTICAL category — same wfs (shared gm_evaluate) + the same
        # most-actionable selection the board uses. Shown as the headline so this page
        # and the board can be reconciled at a glance (they now agree by construction).
        _board_cat = None
        try:
            import gm_trigger_board as _gtbx
            _bside = bool(_ib_ss); _rside = bool(_ir_ss); _noside = not (_bside or _rside)
            _bc = []
            if _bside or _noside:
                _bc.append(_gtbx.trigger_category(wf_bull.get("verdict"), "bull"))
            if wf_rec is not None and (_rside or _noside):
                _bc.append(_gtbx.trigger_category(wf_rec.get("verdict"), "recovery"))
            if _bc:
                _board_cat = max(_bc, key=lambda c: _gtbx._cat_rank(c))
        except Exception:
            _board_cat = None
        # Recovery signal state (parallel to the bull catalyst above).
        rec_sig   = int(_g(rec_r, "Signal", default=0) or 0)
        rec_label = str(_g(rec_r, "Signal_Label", default="None"))
        rec_fired = rec_sig >= 2   # 2=REV-CB 3=REV-RS 4=REV-EARLY 5-8=WYC-*
        # SEMANTIC GUARD: the recovery engine's regime gate opens for ANY non-
        # distressed stock when the *market* is in recovery/reclaim — so REV-EARLY/
        # REV-RS can fire on a stock at its OWN highs (market-recovery play, not a
        # beaten-down recovery). On this single-symbol tool the "RECOVERY" label is
        # read literally, so only treat it as a genuine recovery when the STOCK
        # itself is meaningfully off its 52W high (engine's own min_stock_correction
        # floor, 10%). Otherwise it's a bull setup, not a recovery — don't mislabel.
        _rec_dd_floor, _ = _rec_cfg()
        _rec_corr = _g(rec_r, "Correction_52W_pct")
        rec_beaten_down = (_rec_corr is not None) and (_rec_corr >= _rec_dd_floor)
        rec_fired_real  = rec_fired and rec_beaten_down   # genuine beaten-down recovery
        rec_fired_mktpath = rec_fired and not rec_beaten_down  # market-path artifact at/near highs

        if not rec and not ctx:
            st.error(f"Could not load **{symbol}**.")
            for e in data.get("errors", []):
                st.caption(f"• {e}")
            st.stop()
    
        # ----------------------------------------------------------------------------------------
        # Header — name, CMP, change, verdict
        # ----------------------------------------------------------------------------------------
        name = _g(fun, "name", default=symbol)
        # cmp_px / mansfield already set by gm_evaluate (intraday-aware) — do NOT
        # recompute cmp_px from the daily ctx here (that was the board-vs-single drift).
        cmp_px = _ev["cmp_px"]; mansfield = _ev["mansfield"]
        prev = _g(ctx, "prev", default=cmp_px)
        chg_pct = ((cmp_px - prev) / prev * 100) if (cmp_px and prev) else 0.0
        catalyst = _g(rec, "Catalyst", default="NONE")
        stage = str(_g(rec, "Stage", default="—"))
        alpha = _g(rec, "Alpha", default=None)
        ml_prob = _g(rec, "ML_Prob")
    
        h1, h2, h3 = st.columns([3, 1.3, 1.6])
        with h1:
            st.markdown(f"### {symbol} — {name}")
            st.caption(f"{_g(fun,'sector',default='')}  ·  {_g(fun,'industry',default='')}")
        with h2:
            st.metric("CMP", inr(cmp_px), f"{chg_pct:+.2f}%")
            # Data freshness (G1, 9-Jul-2026): show the LAST BAR DATE, not just the
            # fetch time — a stale feed (cache-poisoning / Dhan date-shift class)
            # must be visible at a glance. The expected bar is SESSION-AWARE: after
            # today's 15:30 IST close it should be TODAY, otherwise the last completed
            # trading day (see _expected_last_session). A flat 'yesterday' target used
            # to sit green on the prior day all evening — one session behind.
            _lastbar = None
            try:
                _dfh = data.get("df")
                if _dfh is not None and len(_dfh):
                    _lastbar = _dfh.index[-1].date()
            except Exception:
                pass
            _asof = _g(rec, "As_Of") or (_lastbar.strftime("%Y-%m-%d") if _lastbar else None)
            if _lastbar or _asof:
                _exp_sess = _expected_last_session()
                _stale = bool(_lastbar and _lastbar < _exp_sess)
                _fresh_txt = f"bar {_lastbar.strftime('%d-%b') if _lastbar else _asof}"
                if _asof and _lastbar and _asof != _lastbar.strftime("%Y-%m-%d"):
                    _fresh_txt += f" · engine as-of {_asof}"
                # P1 provenance: WHICH feed served this frame (dhan / yfinance / cache…)
                # — the silent Dhan→yfinance defection class becomes visible at a glance.
                try:
                    import data_provider as _dpsrc
                    _src = _dpsrc.get_last_source(symbol)
                    if _src and _src not in ("none", "?"):
                        _fresh_txt += f" · src {_src}"
                except Exception:
                    pass
                if _stale:
                    st.caption(f"⚠️ **STALE — {_fresh_txt}** (last completed session "
                               f"{_exp_sess.strftime('%d-%b')}). Refresh; if it stays behind, the "
                               f"broker feed hasn't published today's EOD bar yet.")
                else:
                    st.caption(f"🟢 {_fresh_txt}")
        with h3:
            bull_active = _cat_on(catalyst)
            is_pos = str(catalyst).upper().startswith("POS")
            # Primary verdict = bull catalyst if one fires; otherwise the recovery
            # signal if it fires; otherwise NONE. Recovery is teal to stay visually
            # distinct from the bull green/amber.
            if bull_active:
                head_label, head_color, head_tag = catalyst, ("#26A69A" if is_pos else "var(--warn)"), "CATALYST"
            elif rec_fired_real:
                head_label, head_color, head_tag = rec_label, "#00838F", "RECOVERY"
            else:
                head_label, head_color, head_tag = "NONE", "#787B86", "CATALYST"
            st.markdown(f"<div style='text-align:right'><div style='font-size:12px;opacity:.7'>{head_tag}</div>"
                        f"<div class='verdict' style='color:{head_color}'>{head_label}</div></div>",
                        unsafe_allow_html=True)
            # If BOTH sides fire (and the recovery is a GENUINE beaten-down one),
            # note it under the bull verdict so neither is hidden.
            if bull_active and rec_fired_real:
                st.markdown(f"<div style='text-align:right;font-size:12px;color:#00838F'>"
                            f"＋ Recovery: {rec_label}</div>", unsafe_allow_html=True)
    
        # ----------------------------------------------------------------------------------------
        # DECISION WORKFLOWS — Bull (left) · Recovery (right), side by side.
        # Recovery names are Stage 1/4 by nature and fail the bull Stage-2 gate at
        # Step 1, so a single bull path mislabels them AVOID. Showing BOTH paths
        # lets the trader read the correct verdict for whichever engine applies.
        # ----------------------------------------------------------------------------------------
        decision = compute_decision(rec, ctx, cmp_px, mansfield)
        _bull_active = _cat_on(catalyst)
        # wf_bull / wf_rec / inheritance already computed by gm_evaluate() above — the
        # SAME call the Trigger Board uses, so the two surfaces can't disagree.

        # P1 — INHERITED banner: make it explicit when this name is timed off its SOURCE
        # WATCHLIST archetype (Context/Quality trusted, not re-screened live). Same model
        # the board uses (zero-drift). Absent = a name with no source → legacy re-qualify.
        if _inh_bull_on or _inh_rec_on:
            _arche_lbl = ", ".join(dict.fromkeys(
                (_ib_ss if _inh_bull_on else []) + (_ir_ss if _inh_rec_on else []))) or "watchlist"
            st.markdown(
                f"<div style='border-left:6px solid #6D28D9;background:linear-gradient(135deg, var(--acc-bg) 0%, var(--surface) 100%);border:1.5px solid var(--acc-rule);"
                f"border-radius:8px;padding:10px 14px;margin:6px 0;font-size:0.88rem;color:var(--ink);font-weight:700;box-shadow:0 2px 6px rgba(109,40,217,0.1);'>"
                f"🧬 <b style='color:#6D28D9;font-weight:800;'>Inherited setup — {_arche_lbl}</b> (qualified by its source watchlist). "
                f"Context &amp; Quality are trusted; this name is <b>timed</b> (still-valid guard → "
                f"Location → Trigger), not re-screened. A break-down (Stage 3/4 · lost 30WMA) shows "
                f"<b>INVALIDATED</b>.</div>", unsafe_allow_html=True)
        elif _ev.get("inherit_error"):
            st.warning(f"⚠️ Inherited-qualification unavailable (archetype resolver failed) — "
                       f"showing the LEGACY re-qualification verdict. {_ev['inherit_error']} "
                       f"· logs/gm_errors.log")

        # Trigger-TF banner: makes it explicit that Step-5's battery + momentum are on
        # the trading TF while Steps 1-4 remain Daily/Weekly positional context.
        if _intra_label:
            _il_col = "#0284C7" if _intra_ok else "var(--warn)"
            _il_bg  = "var(--acc-bg)" if _intra_ok else "var(--warn-bg)"
            _il_bdr = "var(--acc-rule)" if _intra_ok else "var(--warn-rule)"
            st.markdown(f"<div style='border-left:6px solid {_il_col};background:linear-gradient(135deg, {_il_bg} 0%, var(--surface) 100%);border:1.5px solid {_il_bdr};"
                        f"border-radius:8px;padding:10px 14px;margin:6px 0;font-size:0.88rem;color:var(--ink);font-weight:700;box-shadow:0 2px 6px rgba(2,132,199,0.1);'>"
                        f"<b style='color:{_il_col};font-weight:800;'>{_intra_label}</b> &nbsp;·&nbsp; Steps 1-4 (Stage · RS · Alpha · catalyst · zones) stay Daily/Weekly."
                        f"</div>", unsafe_allow_html=True)

        # Trigger-Board-identical category headline — the exact value you'd see in the
        # board's Category column for this symbol (same gm_evaluate, same selection).
        if _board_cat:
            _bc_actionable = _board_cat.split(" · ")[0] in ("Buy Trigger Live", "Armed Wait", "Wait for Pullback")
            _bc_col = "#047857" if _board_cat.startswith("Buy Trigger") else ("var(--warn)" if _bc_actionable else "var(--muted)")
            _bc_bg  = "var(--bull-bg)" if _board_cat.startswith("Buy Trigger") else ("var(--warn-bg)" if _bc_actionable else "var(--surface-2)")
            _bc_bdr = "var(--bull-rule)" if _board_cat.startswith("Buy Trigger") else ("var(--warn-rule)" if _bc_actionable else "var(--rule)")
            st.markdown(f"<div style='border-left:6px solid {_bc_col};background:linear-gradient(135deg, {_bc_bg} 0%, var(--surface) 100%);border:1.5px solid {_bc_bdr};"
                        f"border-radius:8px;padding:10px 14px;margin:6px 0;font-size:0.88rem;color:var(--ink);font-weight:700;box-shadow:0 2px 6px rgba(4,120,87,0.1);'>"
                        f"📋 <b style='color:var(--ink);'>Trigger-Board category:</b> <b style='color:{_bc_col};font-weight:800;'>{_board_cat}</b> "
                        f"&nbsp;·&nbsp; TF {_trig_tf} — this matches the board's Category column exactly."
                        f"</div>", unsafe_allow_html=True)

        # S4-GO stage-2 preview chip — the SAME shared s4go_status the board's S4-GO
        # column uses, so this page and the board agree on the stage-2 read too. Category
        # above = the stage-1 ARM (no bar_ok); this = PA · location · volume · bar_ok.
        _s4_path, _s4_sigma, _s4go = "bull", 0, ""
        try:
            import gm_trigger_board as _gtbx2
            _s4_path = "recovery" if (_board_cat and _board_cat.endswith("Recovery")) else "bull"
            _s4_bat = "recovery_pa_patterns" if _s4_path == "recovery" else "pa_patterns"
            _s4_pp = _g(ctx, _s4_bat, default=[]) or []
            _s4_sigma = sum(t for _n, _f, t, _x in _s4_pp if _f) if _s4_pp else 0
            # Pass the INHERITED archetypes so this chip takes the same playbook branch
            # the board does (pullback gates vs breakout gates). Without them the Single
            # Symbol page would re-infer the setup from patterns while the board read it
            # off the watchlist — the two would disagree on exactly the pullbacks the
            # split exists to surface.
            _s4go = _gtbx2.s4go_status(_s4_sigma, ctx, _ev.get("intra_ok"), _s4_path,
                                       archetypes=(_ev.get("inherited_bull") or []),
                                       stage=_g(rec, "Stage", default=""),
                                       rrg_tradeable=_g(rec, "RRG_Tradeable"))
            _s4_col = ("#047857" if _s4go.startswith("5/5") else "#D97706" if (_s4go.startswith("4/5") or _s4go.startswith("2/4")) else "#475569")
            _s4_bg  = ("#D1FAE5" if _s4go.startswith("5/5") else "#FEF3C7" if (_s4go.startswith("4/5") or _s4go.startswith("2/4")) else "#F1F5F9")
            _s4_bdr = ("#6EE7B7" if _s4go.startswith("5/5") else "#FDE68A" if (_s4go.startswith("4/5") or _s4go.startswith("2/4")) else "#CBD5E1")
            _s4_msg = ("all five gates align — the S4 chart should show GO" if _s4go.startswith("5/5")
                       else "no intraday trigger-TF read (can't preview)" if _s4go == "n/a"
                       else f"one/two gates from GO ({_s4go.split('· ')[-1]}) — a watch candidate")
            st.markdown(f"<div style='border-left:6px solid {_s4_col};background:linear-gradient(135deg, {_s4_bg} 0%, var(--surface) 100%);border:1.5px solid {_s4_bdr};"
                        f"border-radius:8px;padding:10px 14px;margin:6px 0;font-size:0.88rem;color:var(--ink);font-weight:700;box-shadow:0 2px 6px rgba(217,119,6,0.1);'>"
                        f"⚡ <b style='color:var(--ink);'>S4-GO (stage-2 closeness):</b> <b style='color:{_s4_col};font-weight:800;'>{_s4go}</b> "
                        f"&nbsp;·&nbsp; PA · location · volume · bar — {_s4_msg}. Confirm on the S4 chart (final word)."
                        f"</div>", unsafe_allow_html=True)
        except Exception as _s4e:
            _gm_logger.warning(f"{symbol}: S4-GO chip failed: {_s4e}")

        # ── ARM / DISARM ────────────────────────────────────────────────────
        # Set the TV alert, then arm here. The board is rebuilt from watchlists that
        # churn nightly, so without this the plan you just read exists nowhere by the
        # time the alert fires. Arming snapshots the LEVELS (which cannot be
        # reconstructed later — they came off today's bar) and keeps the name on the
        # board through the churn, re-evaluated live every rebuild.
        try:
            import gm_armed as _arm
            _a_rec = _arm.get(symbol)
            _a_on = (_a_rec.get("status") or "") == _arm.STATUS_ARMED
            _ac1, _ac2 = st.columns([1, 3], gap="small")
            with _ac1:
                if _a_on:
                    if st.button("🔕 Disarm", key=f"gm_disarm_{symbol}",
                                 use_container_width=True):
                        _arm.disarm(symbol, note="disarmed from Single Symbol")
                        st.rerun()
                else:
                    if st.button("🔔 Arm + record plan", key=f"gm_arm_{symbol}",
                                 use_container_width=True, type="primary"):
                        _wf_a = (wf_rec if _s4_path == "recovery" else wf_bull) or {}
                        # Archetypes come from the SAME inherited lists the board
                        # uses (_ib_ss / _ir_ss), so an armed name rejoins the board
                        # under its original thesis rather than a re-derived one.
                        _arch_a = list(_ir_ss if _s4_path == "recovery" else _ib_ss) or []
                        _entry_a = _wf_a.get("plan_entry") or cmp_px
                        _sl_a = _wf_a.get("plan_sl")
                        _t1_a = _wf_a.get("plan_t1")
                        _rr_a = None
                        try:
                            if _entry_a and _sl_a and _t1_a and _entry_a > _sl_a:
                                _rr_a = (_t1_a - _entry_a) / (_entry_a - _sl_a)
                        except Exception:
                            _rr_a = None
                        _arm.arm(
                            symbol, path=_s4_path, archetypes=_arch_a,
                            verdict=str(_wf_a.get("verdict") or ""),
                            category=str(_board_cat or ""),
                            # The confirmation level to wait for. compute_workflow has no
                            # separate 'trigger' — the plan entry IS that level, and S4
                            # remains the final word on the exact bar.
                            trigger=_entry_a,
                            entry=_entry_a, sl=_sl_a, t1=_t1_a, rr=_rr_a,
                            sigma_pa=_s4_sigma, s4go=_s4go, cmp_px=cmp_px,
                            tf=str(st.session_state.get("gm_trig_tf") or ""))
                        st.rerun()
            with _ac2:
                if _a_on:
                    _d = _arm.days_armed(_a_rec)
                    st.caption(
                        f"🔔 **Armed {_d}d ago** ({_a_rec.get('armed_on')}) · plan as armed: "
                        f"trigger ₹{_a_rec.get('trigger') or '—'} · SL ₹{_a_rec.get('sl') or '—'} · "
                        f"T1 ₹{_a_rec.get('t1') or '—'} · “{_a_rec.get('verdict') or '—'}” · "
                        f"expires {_a_rec.get('expires_on')}. Levels shown above are LIVE — "
                        f"compare them against these before acting on the alert.")
                else:
                    st.caption("Set the TradingView alert, then Arm — the register keeps this "
                               "name on the board after the watchlists drop it, and holds "
                               "today's levels for when the alert fires.")
        except Exception as _ae:
            _gm_logger.warning(f"{symbol}: arm/disarm control failed: {_ae}")

        _wcol1, _wcol2 = st.columns(2)
        with _wcol1:
            st.markdown("##### 🐂 Bull path  ·  Stage-2 leadership")
            st.markdown(render_workflow(wf_bull), unsafe_allow_html=True)
        with _wcol2:
            st.markdown("##### 🔄 Recovery path  ·  beaten-down + RFF")
            # Render the full recovery path ONLY for a GENUINE recovery (signal fired
            # AND stock beaten-down ≥10%). A market-path artifact (signal fired at/near
            # highs) or no signal both get a concise note — so two "no real recovery"
            # names never render differently (one full red path, one one-liner).
            if wf_rec is not None and (rec_fired_real or _inh_rec_on):
                st.markdown(render_workflow(wf_rec), unsafe_allow_html=True)
                # UNVALIDATED BOOK — see gm_trigger_board.RECOVERY_UNVALIDATED for the
                # evidence. The board tags these rows `⚠unval`; this is the same statement
                # in the one place a recovery verdict is read in full. Both are display
                # only — the path stays tradeable, it just stops looking measured.
                try:
                    import gm_trigger_board as _gtb_unval
                    if getattr(_gtb_unval, "RECOVERY_UNVALIDATED", False):
                        st.caption(
                            "⚠ **Recovery has no valid backtest.** The only run that completed "
                            "used 30-day forward windows on setups designed for 90-180 days, "
                            "which invalidates it; the one post-fix attempt did not finish. "
                            "Trade this path on your own read, not on a measured edge.")
                except Exception:
                    pass
            elif _ev.get("rec_error"):
                # P0 fix: an eval FAILURE is decision-different from "no recovery context"
                # — never render a confident verdict off an error dict.
                st.error(f"⚠️ Recovery evaluation FAILED — verdict unavailable (not 'no context'). "
                         f"{_ev['rec_error']}")
            elif rec_fired_mktpath:
                st.info(f"Recovery engine notes **{rec_label}** only via the market-recovery regime — "
                        f"but **{symbol}** is just {fnum(_rec_corr, 1, '%')} off its 52W high "
                        f"(< {_rec_dd_floor:.0f}% floor), so it is **not** a beaten-down recovery. "
                        f"Trade the bull path.")
            else:
                st.info("No recovery catalyst on this name — the recovery path does not apply.")

        # ---- Fresh Stage-transition note (reconciles a lagging chart background) ----
        # Stage is a STATEFUL weekly state machine; at a Stage 4→1 reclaim the exact
        # flip bar is knife-edge (30-WMA slope crossing the flat band), so Python
        # (Dhan feed) and a TradingView background (TV feed + its own weekly bars)
        # can differ by one stage for a week or two. When price has RECLAIMED the
        # 30-week MA but the stage still reads 1 (base), that's a fresh turn Python
        # catches first — flag it so a chart still painting Stage 4 isn't confusing.
        _ma30 = _g(ctx, "sma150")   # daily 150-SMA ≈ 30-week MA (the stage anchor)
        _stg = None
        for _sv in (str(_g(rec, "Stage", default="")), str(_g(rec_r, "Weinstein_Stage", default=""))):
            _hit = next((d for d in "1234" if d in _sv), None)
            if _hit:
                _stg = int(_hit); break
        if _ma30 and cmp_px and _stg == 1 and cmp_px > _ma30:
            _d30 = (cmp_px / _ma30 - 1) * 100
            st.caption(f"🟡 **Stage 1 · fresh reclaim** — price is **{_d30:+.1f}% above the 30-week MA** "
                       f"({inr(_ma30)}), i.e. the stock has reclaimed its Weinstein anchor. If a "
                       f"TradingView stage-background still shows **Stage 4**, it is *lagging this turn* "
                       f"on its own data feed (the 4→1 flip is a knife-edge slope crossing) — Python "
                       f"registered the reclaim first. Trust the price-vs-30WMA read: this is an early base, not a decline.")

        # The PRIMARY path drives the single next-action + guided execution below.
        # Some names fire BOTH a bull catalyst AND a genuine recovery signal — and
        # the two have DIFFERENT entries/stops/targets — so let the trader choose
        # which setup to execute rather than silently defaulting. Otherwise the one
        # applicable path leads automatically.
        # The recovery path is SHOWN whenever it's a genuine/inherited recovery (the bull
        # path always renders). Whenever BOTH are shown, offer the radio so the trader
        # picks which to EXECUTE — and DEFAULT to the MORE-ACTIONABLE path. (The bug: the
        # radio used to default to Bull, so DLF showed Bull·Avoid in Guided Execution even
        # though Recovery·Buy-Trigger-Live was the valid setup.)
        import gm_trigger_board as _gtbp
        _rec_shown = (wf_rec is not None) and (rec_fired_real or _inh_rec_on)
        if _rec_shown:
            _br = _gtbp._cat_rank(_gtbp.trigger_category(wf_bull.get("verdict"), "bull"))
            _rr = _gtbp._cat_rank(_gtbp.trigger_category(wf_rec.get("verdict"), "recovery"))
            _default_idx = 1 if _rr > _br else 0        # default to the more-actionable path
            _pick = st.radio(
                "⚡ This name is valid on BOTH paths — execute which? (defaulting to the more-actionable)",
                ["🐂 Bull", "🔄 Recovery"], horizontal=True, index=_default_idx,
                key=f"gm_path_{symbol}")
            wf = wf_rec if _pick.startswith("🔄") else wf_bull
        else:
            wf = wf_bull
        _pa_html = render_pa_banner(ctx, recovery=bool(wf.get("recovery")))
        if _pa_html:
            st.markdown(_pa_html, unsafe_allow_html=True)

        # ---- Session shortlist capture (E3, 9-Jul-2026) — a TV scroll session
        # leaves an artifact: every actionable name (BUY / ARMED / WAIT-class) is
        # recorded in session state; a name that degrades to AVOID/WATCHLIST on a
        # later look is removed. Rendered as a table further down.
        _slk = "recovery_pa_patterns" if wf.get("recovery") else "pa_patterns"
        _sl_tier = sum(t for _, f, t, _ in (_g(ctx, _slk, default=[]) or []) if f)
        _sl_store = st.session_state.setdefault("gm_shortlist", {})
        _sl_sym = symbol.replace(".NS", "").replace(".BO", "").upper()
        if wf["actionable"]:
            _sl_store[_sl_sym] = {"Symbol": _sl_sym, "Verdict": wf["verdict"],
                                  "Path": "Recovery" if wf.get("recovery") else "Bull",
                                  "Σ tier": _sl_tier, "Signal": str(head_label),
                                  "Seen": datetime.now().strftime("%H:%M")}
        else:
            _sl_store.pop(_sl_sym, None)

        # ---- The single next action + guided execution sequence ----
        cur_step = wf["steps"][wf["current"] - 1]
        if not wf["actionable"]:
            if "AVOID" in wf["verdict"]:
                st.error(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Go to the next name.")
            else:
                st.warning(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Track only; no action today.")
        elif wf["current"] < 5:
            st.warning(f"**→ NOW · Step {wf['current']} ({cur_step['title']}):**  {cur_step.get('do_fail','')}")
        else:
            st.success(f"**→ NOW · Step 5 (TRIGGER):**  {cur_step.get('do_now')}")

            # ---- Position sizer (E2, 9-Jul-2026) — risk% of capital made concrete ----
            _pe = wf.get("plan_entry"); _psl = wf.get("plan_sl"); _pt1 = wf.get("plan_t1")
            _qty_sized = 0
            if _pe and _psl and _pe > _psl:
                if _gm_capital > 0:
                    # S4's DYNAMIC RISK, mirrored (Jay, 24-Sep-2026): the base scaled by regime,
                    # volatility and conviction exactly as S4's Qty row does it, so both
                    # screens size the same trade the same way. s4_sizing names every term.
                    # This replaces the old counter-trend halving: S4 has no such step, and
                    # its regime and conviction terms are what shrink a counter-trend name.
                    # RISK BASE BY ASSET (Jay, 24-Sep-2026): stock 0.5%, ETF 0.75% — 1.5x the
                    # Risk % above, the same factor S4 applies (`_szb`), so the two cannot drift.
                    _is_etf = False
                    try:
                        import etf_universe as _etfu
                        _is_etf = _etfu.is_etf(symbol)
                    except Exception as _ez:
                        _gm_logger.warning(f"{symbol}: ETF lookup failed, sizing as a stock: {_ez}")
                    _base_pct = _HP.risk_pct_for(symbol)   # house rule, ETF x1.5 included
                    _dyn = None
                    try:
                        import s4_sizing as _s4z
                        _tfm = {"75m": 75, "125m": 125}.get(str(_trig_tf))
                        _tfr = (gm_load_intraday(symbol, _tfm) or {}).get("df") if _tfm else None
                        _dyn = _s4z.gm_dynamic_risk(symbol, _base_pct, _tfr, ctx.get("wcl"))
                    except Exception as _dz:
                        _gm_logger.warning(f"{symbol}: dynamic risk failed, sizing at base: {_dz}")
                    _act_pct = float(_dyn["active_pct"]) if _dyn else _base_pct
                    _risk_amt = _gm_capital * _act_pct / 100.0
                    _qty_sized = int(_risk_amt // (_pe - _psl))
                    _ct_half = False
                    # MAX-ALLOCATION CEILING (mirrors S4: Qty = min(risk qty, cap ÷ entry)).
                    # Applied AFTER the counter-trend halving so the two reductions compose
                    # rather than one masking the other.
                    _cap_qty, _cap_bound = None, False
                    if _gm_maxalloc and _gm_maxalloc > 0:
                        _cap_qty = int(_gm_maxalloc // _pe)
                        if _cap_qty < _qty_sized:
                            _qty_sized, _cap_bound = _cap_qty, True
                    _pos_val = _qty_sized * _pe
                    # When the cap binds, the risk% shown is NOT the risk taken — say so
                    # with the real number rather than leaving a misleading label on screen.
                    _eff_risk = _qty_sized * (_pe - _psl)
                    _eff_pct = (_eff_risk / _gm_capital * 100.0) if _gm_capital else 0.0
                    if _dyn:
                        st.caption("📐 Risk, as S4 computes it: " + _s4z.describe(_dyn))
                    else:
                        st.caption("⚠ Dynamic risk unavailable — sized at the flat base, which S4 would not use.")
                    st.markdown(
                        f"**📏 Size @ {_act_pct:.2f}% risk:** {inr(_risk_amt)} ÷ "
                        f"(entry {inr(_pe)} − SL {inr(_psl)}) = **{_qty_sized} shares** · "
                        f"position {inr(_pos_val)}"
                        + (f" ({_pos_val / _gm_capital * 100:.1f}% of capital)" if _gm_capital else "")
                        + (" · ⚠ counter-trend — size halved" if _ct_half else "")
                        + (f" · 🧢 **capped by Max ₹/trade {inr(_gm_maxalloc)}** — actual risk "
                           f"{inr(_eff_risk)} ({_eff_pct:.2f}% of capital), not {_act_pct:.2f}%"
                           if _cap_bound else ""))
                else:
                    st.caption("📏 Set your capital above to get an auto position size at the configured risk.")

            # ---- Guided execution — COLLAPSES when there's no location (Jay) ----------
            # Expand automatically when there IS a location (a demand zone under price OR
            # the Step-4 location gate passed); otherwise stay collapsed so it doesn't
            # clutter with generic "hand-draw" steps you can't action yet. The checklist
            # lives in the expander; the journal form stays OUTSIDE it (Streamlit forbids
            # nested expanders — the journal has its own).
            _supz = _g(ctx, "support", default={}) or {}

            def _pick_zone(_z, _tf):
                """(label, lo, hi, proximal) for the tightest FRESH active zone under
                price in one TF, or None. Keys off the exact tradeable zone labels —
                'OB/FVG tested' never match, so a mitigated zone is never auto-picked."""
                if not _z:
                    return None
                _lbl = str(_z.get("zone", "outside"))
                if _lbl in ("OB inside", "OB near"):
                    return (f"{_tf} {_lbl}", _z.get("ob_bot"), _z.get("ob_top"), _z.get("ob_top"))
                if _lbl in ("FVG inside", "FVG near"):
                    return (f"{_tf} {_lbl}", _z.get("fvg_bot"), _z.get("fvg_top"), _z.get("fvg_top"))
                if _lbl == "Pivot near":
                    return (f"{_tf} Pivot near", _z.get("pivot"), _z.get("pivot"), _z.get("pivot"))
                return None

            _pick = _pick_zone(_supz.get("daily"), "Daily") or _pick_zone(_supz.get("weekly"), "Weekly")
            # Expand when there's a location (zone under price OR Step-4 passed) OR a live
            # trigger fired (a BUY is immediately actionable regardless of location).
            _has_loc = bool(_pick) or bool(wf.get("location_ok")) or str(wf.get("verdict", "")).startswith("BUY")
            _done = 0; _next = None; _man = []
            # Step-4 fill instruction follows the entry-method toggle (buy-stop / retest).
            # Routed through _gm_entry_instruction so the fill wording has ONE definition —
            # this was a hardcoded second copy and had already drifted from the helper.
            _step4 = "4 · Place a " + _gm_entry_instruction()
            with st.expander("✅ Guided execution — tick as you go", expanded=_has_loc):
                if _pick:
                    _z_lbl, _z_lo, _z_hi, _z_prox = _pick
                    _span_txt = inr(_z_lo) if _z_lo == _z_hi else f"{inr(_z_lo)}–{inr(_z_hi)}"
                    _zsummary = str(_supz.get("zone", ""))
                    st.caption(f"🟩 **Auto demand-zone:** {_z_lbl} at **{_span_txt}** "
                               f"· alert proximal **{inr(_z_prox)}**  ·  _{_zsummary}_ — Steps 1-2 auto-marked; verify on the chart.")
                    _man = [
                        ("zone",  f"1 · Auto zone confirmed: {_z_lbl} at {_span_txt} (verify it's fresh/untested)"),
                        ("alert", f"2 · Set the TradingView alert at the zone proximal {inr(_z_prox)}"),
                        ("close", "3 · Wait for a 75/125m bar to CLOSE in your direction at the zone"),
                        ("stop",  _step4),
                        ("size",  f"5 · Set SL below the zone distal · size at {_HP.risk_label()} risk"),
                        ("gtt",   "6 · Place the order + GTT the same evening · log the trade"),
                    ]
                else:
                    st.caption("⬜ No auto demand-zone (OB/FVG/pivot on Daily or Weekly) under price yet — hand-draw the fresh zone.")
                    _man = [
                        ("zone",  "1 · Mark the FRESH demand zone on Daily/Weekly (hand-drawn, untested)"),
                        ("alert", "2 · Set a TradingView alert at the zone proximal"),
                        ("close", "3 · Wait for a 75/125m bar to CLOSE in your direction at the zone"),
                        ("stop",  _step4),
                        ("size",  f"5 · Set SL below the zone distal · size at {_HP.risk_label()} risk"),
                        ("gtt",   "6 · Place the order + GTT the same evening · log the trade"),
                    ]
                _key = f"chk_{symbol}"
                for _k, _label in _man:
                    if st.checkbox(_label, key=f"{_key}_{_k}"):
                        _done += 1
                    elif _next is None:
                        _next = _label
                st.progress(_done / len(_man), text=f"{_done}/{len(_man)} done")
            if _man and _done == len(_man):
                # ---- E1 (9-Jul-2026): actually log the trade. upsert_trade()
                # auto-captures the true-entry signal snapshot on new OPEN inserts
                # (the Phase-0 hook) — so a GM-executed trade lands in the journal
                # AND the attribution pipeline with its setup label.
                st.success("✅ All steps done — log the trade to the journal below.")
                _path_lbl = "Recovery" if wf.get("recovery") else "Bull"
                _pa_key = "recovery_pa_patterns" if wf.get("recovery") else "pa_patterns"
                _sig_tier = sum(t for _, f, t, _ in (_g(ctx, _pa_key, default=[]) or []) if f)
                _rat_default = f"GM {wf['verdict']} · {_path_lbl} · {head_label} · Σ+{_sig_tier}"
                with st.expander("📓 Log to journal", expanded=True):
                    with st.form(f"gm_journal_{symbol}"):
                        _jc1, _jc2, _jc3 = st.columns(3)
                        with _jc1:
                            _j_buy = st.number_input("Buy price", min_value=0.0, format="%.2f",
                                                     value=float(_pe or cmp_px or 0.0))
                            _j_qty = st.number_input("Quantity", min_value=0, step=1,
                                                     value=int(_qty_sized))
                        with _jc2:
                            _j_sl = st.number_input("Stop-loss", min_value=0.0, format="%.2f",
                                                    value=float(_psl or 0.0))
                            _j_t1 = st.number_input("Target 1", min_value=0.0, format="%.2f",
                                                    value=float(_pt1 or 0.0))
                        with _jc3:
                            _j_tf = st.selectbox("Timeframe", ["Positional", "Swing"],
                                                 index=0 if str(head_label).upper().startswith(("POS", "REV", "WYC")) else 1)
                            _j_rat = st.text_input("Rationale", value=_rat_default)
                        if st.form_submit_button("📓 Log OPEN trade", type="primary"):
                            try:
                                # journal_core, not dhan_journal_v7: this only wants
                                # upsert_trade, and importing the old module rendered the
                                # entire journal into this page plus a live Dhan sync.
                                import journal_core as _dj
                                _bare_j = symbol.replace(".NS", "").replace(".BO", "").upper()
                                _dj.upsert_trade({
                                    "Symbol": _bare_j, "Type": "LONG", "Status": "OPEN",
                                    "BuyPrice": float(_j_buy), "Quantity": float(_j_qty),
                                    "StopLoss": float(_j_sl) or None,
                                    "Target1": float(_j_t1) or None,
                                    "EntryDate": datetime.now().strftime("%Y-%m-%d"),
                                    "Timeframe": _j_tf, "Rationale": _j_rat,
                                    "Sector": str(_g(fun, "sector", default="") or ""),
                                })
                                st.success(f"📓 {_bare_j} logged OPEN — entry snapshot captured. On to the next name.")
                            except Exception as _je:
                                st.error(f"Journal write failed (trade NOT logged): {_je}")
            elif _next:
                st.caption(f"→ Next: {_next}")

        # ---- Recovery engine callout ------------------------------------------------
        # The decision workflow above is bull-oriented; a recovery setup would
        # otherwise be buried under a bull "no action" verdict. Surface it here so
        # a REV/WYC signal on a fundamentally-strong beaten-down name is never missed.
        if rec_fired_real:
            _rev_entry = _g(rec_r, "Entry"); _rev_sl = _g(rec_r, "SL"); _rev_t1 = _g(rec_r, "T1")
            _plan = ""
            if _rev_entry and _rev_sl:
                _plan = f"  ·  Entry {inr(_rev_entry)} · SL {inr(_rev_sl)}" + (f" · T1 {inr(_rev_t1)}" if _rev_t1 else "")
            st.success(f"**🔄 RECOVERY SIGNAL — {rec_label}** (RFF {_g(rec_r,'RFF_Base',default=0)}/6, "
                       f"{_g(rec_r,'RFF_Quality',default='—')} · {fnum(_rec_corr,1,'%')} off 52WH).{_plan}  "
                       f"Fundamentally-strong beaten-down setup — validate on the chart, then trade the recovery playbook.")
        elif rec_fired_mktpath:
            # The engine fired REV/WYC via the MARKET-recovery path, but the stock
            # itself is at/near its highs — not a beaten-down recovery. Say so
            # plainly rather than mislabelling it "recovery".
            st.caption(f"ℹ️ Recovery engine notes *{rec_label}* only via the market-recovery regime — "
                       f"but **{symbol}** is just {fnum(_rec_corr,1,'%')} off its 52W high "
                       f"(< {_rec_dd_floor:.0f}% floor), so this is **not** a beaten-down recovery. "
                       f"Trade the bull catalyst above, not a recovery playbook.")
        elif rec_sig == 1 and rec_beaten_down:
            st.info(f"**🔄 Recovery: CB-Watch** — climax detected on **{symbol}**, no turn yet. "
                    f"On watch; no recovery entry until the bounce confirms.")

        # On-demand LIVE fundamentals: the fast path skips the blocking Screener.in
        # scrape (so TV auto-sync stays responsive). If RFF read INSUFFICIENT only
        # because fundamentals weren't cached, let the trader pull them for THIS name.
        if not _deep_rec and str(_g(rec_r, "RFF_Quality", default="")) == "INSUFFICIENT":
            if st.button("🔬 Fetch live fundamentals for recovery RFF (this symbol)",
                         key=f"deeprec_btn_{symbol}",
                         help="Skipped during fast scrolling to keep TV auto-sync responsive. "
                              "Pulls Screener.in/yfinance fundamentals for this symbol only."):
                st.session_state[f"gm_deeprec_{symbol}"] = True
                st.rerun()

        st.divider()

        # ---- AI analysis (12-Aug-2026) -------------------------------------
        # BESIDE the decision path, never inside it. It reads what gm_evaluate
        # already produced - so it can never describe a different bar than the
        # panel above - then adds fundamentals, news and analyst calls and asks
        # for a reading. Deliberately NOT a verdict: the framing Jay agreed is
        # evidence + the disconfirming case, because a confident buy/sell here
        # would be false precision against an edge every backtest calls thin.
        #
        # Button-gated on purpose. It is the only slow, non-deterministic thing
        # on this page (LLM + news fetch), so it must never run on every rerun.
        with st.expander("🧠 AI analysis — evidence, gaps and the disconfirming case", expanded=False):
            _ai_key = f"gm_ai_{symbol}_{_trig_tf}"
            _c1, _c2 = st.columns([1, 3])
            _go_ai = _c1.button("Run analysis", key=f"{_ai_key}_btn", type="primary",
                                use_container_width=True)
            _c2.caption("Reads this page's own engine output, then pulls X-Ray fundamentals, "
                        "RSS + NSE announcements and ET/MC analyst calls. Slow (~10-20s) and "
                        "not reproducible word-for-word — it is a research aid, it does not "
                        "gate the GO.")
            if _go_ai:
                with st.spinner("Assembling evidence and generating…"):
                    try:
                        import gm_ai_analysis as _gai
                        # holding comes from the journal INSIDE the module -
                        # journal_overrides is not in scope on this page and
                        # guessing at it is how the last two silent faults started.
                        _txt, _pl = _gai.analyse(symbol, ctx=ctx, verdict=_ev)
                        st.session_state[_ai_key] = {"text": _txt, "payload": _pl}
                    except Exception as _e_ai:
                        st.session_state[_ai_key] = {"text": f"AI analysis failed: {_e_ai}", "payload": {}}
            _cached_ai = st.session_state.get(_ai_key)
            if _cached_ai:
                _pl = _cached_ai.get("payload") or {}
                _miss = _pl.get("_missing") or []
                if _miss:
                    st.warning("Gaps in the evidence: " + " · ".join(str(m) for m in _miss))
                st.markdown(_cached_ai.get("text", ""))
                with st.expander("What it was given (provenance)", expanded=False):
                    for _k, _v in (_pl.get("_provenance") or {}).items():
                        st.caption(f"**{_k}** — {_v}")
                    st.json(_pl, expanded=False)

        # ---- Session shortlist (E3) — the ranked artifact of this scroll session ----
        _sl_all = st.session_state.get("gm_shortlist", {})
        with st.expander(f"📋 Session shortlist ({len(_sl_all)})", expanded=False):
            if _sl_all:
                _sl_df = pd.DataFrame(list(_sl_all.values()))
                _sl_df = _sl_df.sort_values(["Σ tier", "Symbol"], ascending=[False, True])
                st.dataframe(_sl_df, use_container_width=True, hide_index=True)
                _slc1, _slc2 = st.columns(2)
                with _slc1:
                    st.download_button(
                        "⬇ TV watchlist (.txt)",
                        "###GM_SHORTLIST\n" + "\n".join(f"NSE:{s}" for s in _sl_df["Symbol"]),
                        file_name=f"GM_Shortlist-{datetime.now().strftime('%d%b%y').upper()}.txt",
                        use_container_width=True)
                with _slc2:
                    if st.button("🗑 Clear shortlist", use_container_width=True):
                        st.session_state["gm_shortlist"] = {}
                        st.rerun()
            else:
                st.caption("Empty — actionable names (BUY / ARMED / WAIT) collect here as you scroll TV.")

        # Full per-panel detail is one click away — but the workflow above is the decision.
        with st.expander("▸ Full metrics — all panels (optional depth)", expanded=False):
            # v2 (2026-07-03): pre-render every card so SECTION_SCORES fills, then show
            # the one-glance score strip ABOVE the panels — read the strip, open a card
            # only when its score surprises you.
            SECTION_SCORES.clear()
            # PANELS FOLLOW THE ACTIVE PATH (recovery-context-leak fix). When the
            # Recovery path is selected, the shared metrics reflect the RECOVERY
            # source (Mansfield RS, recovery PA-battery Σ) and the plan card shows the
            # disciplined recovery levels — a recovery stock no longer shows bull
            # Stage/RS/Σ. Stage is the ONE canonical shared weekly value (item 16).
            _rec_active = bool(wf.get("recovery"))
            _mansf_disp = (_g(rec_r, "Mansfield_RS_x100") if _rec_active else mansfield)
            _canon_stage = _stg_digit(_g(rec, "Stage", default="")) or "—"
            _h_momentum, _h_minervini, _h_pa_signals = render_technical_board(rec, ctx, cmp_px, mansfield)
            # section_pa_patterns returns ONE html string per call, selected by the
            # `recovery` flag; the two names render in DIFFERENT columns below (bull in
            # tc2, recovery in tc3), hence two calls. Until 18-Aug the function still
            # returned a TUPLE while this site assigned it whole, so the panel printed
            # the tuple's repr as literal HTML text. Fixed in the function, not here.
            _h_pa_bull = section_pa_patterns(ctx, recovery=False)
            _h_pa_rec = section_pa_patterns(ctx, recovery=True) if _rec_active else ""
            _h_ctx    = section_context(rec, ctx, cmp_px)
            _h_struct = section_structure(rec, ctx, cmp_px, _mansf_disp, decision)
            _h_gates  = section_bull_gates(rec, ctx, cmp_px, mansfield)
            _h_edges  = section_edges(rec, ctx, cmp_px)
            _h_trade  = (_recovery_plan_card(wf) if _rec_active else section_trade(rec, cmp_px))
            _h_levels = section_levels(rec, ctx, cmp_px)
            _h_sector = section_sector(rec, ctx, _mansf_disp)
            _h_funda  = section_fundamentals(fun, bff=ctx.get("bff"))
            _h_recov  = section_recovery(rec_r, cmp_px, canon_stage=_canon_stage)
            _mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
            if _rec_active:
                st.info("▸ Panels reflect the **Recovery** path (Mansfield RS, recovery PA Σ, "
                        "disciplined recovery plan). The bull-leadership cards below "
                        "(Structure · Bull Gates · Edges) are shown as reference.")
            st.markdown(render_score_strip(_mpass), unsafe_allow_html=True)
            
            # Top row: 3 columns (Momentum & Strength (left) · Minervini Trend Template (center) · Price-Action Signals (right))
            mc1, mc2, mc3 = st.columns(3, gap="small")
            with mc1:
                st.markdown(_h_momentum, unsafe_allow_html=True)
            with mc2:
                st.markdown(_h_minervini, unsafe_allow_html=True)
            with mc3:
                st.markdown(_h_pa_signals, unsafe_allow_html=True)

            # Section tiles: 4 horizontal columns for high density and tight field-value alignment
            tc1, tc2, tc3, tc4 = st.columns(4, gap="small")
            with tc1:
                st.markdown(_h_struct, unsafe_allow_html=True)
                st.markdown(_h_edges, unsafe_allow_html=True)
                st.markdown(_h_recov, unsafe_allow_html=True)
            with tc2:
                st.markdown(_h_levels, unsafe_allow_html=True)
                if _h_pa_bull:
                    st.markdown(_h_pa_bull, unsafe_allow_html=True)
            with tc3:
                st.markdown(_h_gates, unsafe_allow_html=True)
                st.markdown(_h_trade, unsafe_allow_html=True)
                if _h_pa_rec:
                    st.markdown(_h_pa_rec, unsafe_allow_html=True)
            with tc4:
                st.markdown(_h_ctx, unsafe_allow_html=True)
                st.markdown(_h_sector, unsafe_allow_html=True)
                st.markdown(_h_funda, unsafe_allow_html=True)
    
        st.divider()
        st.caption(f"Data: Dhan feed + Screener.in via your validated modules · "
                   f"fetched {data.get('fetched_at','—')} · cache 120s · "
                   f"⚠ identification only — the trigger is yours on TradingView.")
        if data.get("errors"):
            with st.expander("⚠ Partial-data notes"):
                for e in data["errors"]:
                    st.caption(f"• {e}")
