# commander_pages/command.py - the COMMAND page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('command', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">⚡ Command Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Active trade management and execution protocols.</div>', unsafe_allow_html=True)
    # 15-Oct-2026 DUPLICATE RETIREMENT (Jay: "retain the most relevant, retire the rest"):
    # Exit Signal Engine -> Dashboard; E-02 Trailing Stop + GTT Live View -> Risk Shield;
    # Ledger tab + its Sync to TV -> Journal (which pushes to the charts); Webhook Gateway
    # launcher -> START_ALERT_REVIEWER / Fix Webhook (a second receiver clashes on :8000);
    # console Sniper -> AI Lab's Sniper Entry (through the pre-trade gate).
    _cm1, _cm3 = st.tabs(["⚡ Active Ops", "🔔 Price Alerts"])

    with _cm1:
        section("Active Operations")
        c2, c3, c4 = st.columns(3, gap="small")
        with c2:
            if st.button("🛡️  GTT Auto-Shield\nAuto-protect holdings using Journal levels.\n→  Launch", use_container_width=True, key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  Telegram Sentinel\nActive market monitoring via Mobile.\n→  Launch", use_container_width=True, key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        with c4:
            if st.button("🤖  Market Monitor Agent\nLive intraday scans and Telegram alerts.\n→  Launch", use_container_width=True, key="cmd_monitor"):
                launch_script("market_monitor_agent.py")
        # ── PULLBACK FINDER ─────────────────────────────────────────────────
        # The Trigger Board answers WHEN (and a trigger bar is a wide-range up-bar
        # near the recent high, so it is breakout-biased BY CONSTRUCTION — measured
        # 31-Jul: actionable rows ran a median 1.74 ATR above the EMA20, all within
        # 0.2-2.9% of their own 20-day high). This answers WHERE: Stage-2 names
        # sitting AT value right now, ranked by location quality, regardless of
        # whether anything has fired. Separate surface on purpose — see
        # pullback_finder.py's header.
        st.markdown("---")
        section("Pullback Finder · Stage-2 names AT VALUE")
        st.caption(
            "Ranks by LOCATION, not by trigger: extension from the EMA20 (in ATR), "
            "depth off the 20-day high, volume dry-up, range contraction and the "
            "nearest real support below price. Scans the full Nifty 500 — it does "
            "NOT apply the screener.in fundamental join that thins the Chartink "
            "pullback list. Take a name from here to S4 for the trigger."
        )
        _pb_csv = os.path.join(_APP_DIR, "Pullback_Candidates.csv")
        _pb1, _pb2 = st.columns([1, 3], gap="small")
        with _pb1:
            if st.button("🎯  Find Pullbacks\nStage-2 names at value (Nifty 500).\n→  Scan Now",
                         use_container_width=True, key="cmd_pullback_scan", type="primary"):
                launch_script("pullback_finder.py", "--universe nifty500")
                st.info("Scan running in the console window (~3-5 min). "
                        "Click ↻ Reload results when it finishes.")
            if st.button("↻  Reload results", use_container_width=True, key="cmd_pb_reload"):
                st.rerun()
        with _pb2:
            if os.path.exists(_pb_csv):
                try:
                    _df_pb = pd.read_csv(_pb_csv)
                    _pb_at = datetime.fromtimestamp(os.path.getmtime(_pb_csv))
                    _at_value = int((_df_pb["Ext_ATR"] <= 0).sum()) if "Ext_ATR" in _df_pb.columns else 0
                    st.success(f"🎯 **{len(_df_pb)} names at value** — {_at_value} sitting at or "
                               f"BELOW the EMA20 · last scan: {_pb_at.strftime('%d %b %H:%M')}")
                    _pb_show = [c for c in ["Symbol", "Value_Score", "CMP", "Ext_ATR", "Depth_%",
                                            "RS", "RRG", "Vol_vs_50", "Tight", "Support",
                                            "Sup_Src", "Trigger>", "SL", "Risk_%", "T1_2R"]
                                if c in _df_pb.columns]
                    st.dataframe(_df_pb[_pb_show], use_container_width=True, hide_index=True,
                                 height=340)
                    st.caption("Trigger> = wait for a CLOSED bar above it, then buy-STOP above "
                               "THAT bar. Never rest an order at the level.")
                except Exception as _pe:
                    st.info(f"Run the Pullback Finder to generate results. ({_pe})")
            else:
                st.info("No scan yet — press **Find Pullbacks**.")

        st.markdown("---")
        # ── MISS-2: PORTFOLIO ROTATION GUARD UI ─────────────────────────────
        section("Portfolio Rotation Guard")
        st.caption("Grade all open positions on Weinstein structural alignment. "
                   "Surfaces deteriorating Stage 2 holdings before they become losers.")
        _rot_csv = os.path.join(_APP_DIR, "portfolio_rotation_output.csv")
        _pg1, _pg2 = st.columns([1, 3], gap="small")
        with _pg1:
            if st.button("🔄  Run Rotation Guard\nGrade all open positions.\n→  Scan Now",
                         use_container_width=True, key="cmd_rot_guard"):
                launch_script("portfolio_rotation_guard.py")
        with _pg2:
            if os.path.exists(_rot_csv):
                try:
                    _df_rot = pd.read_csv(_rot_csv)
                    if not _df_rot.empty:
                        _rot_show = [c for c in ["Symbol","Grade","Stage","Reason","Conviction"] if c in _df_rot.columns]
                        if not _rot_show:
                            _rot_show = list(_df_rot.columns[:6])
                        st.dataframe(_df_rot[_rot_show], use_container_width=True, hide_index=True)
                    else:
                        st.info("No rotation data. Run the guard first.")
                except Exception:
                    st.info("Run Rotation Guard to view portfolio grading.")

        st.markdown("---")
        section("External Apps")
        if st.button("📓  Open Full Journal\nActive trades, closed history, performance lab.\n→  Open", use_container_width=True, key="cmd_journal"):
            # 23-Sep: navigates instead of spawning a second Streamlit process.
            _goto_page("JOURNAL")
            st.rerun()

    with _cm3:
        # ── PRICE ALERTS ─────────────────────────────────────────────────────
        section("🔔 Price Alert Manager")
        st.caption(
            "Set threshold alerts for any ticker. "
            "The scheduler checks every 15 min during market hours (9:00–15:45 IST) "
            "and sends a Telegram notification when the condition fires."
        )
        try:
            from alert_engine import add_alert, remove_alert, toggle_alert, list_alerts, get_current_price
            _ae_ok = True
        except ImportError:
            _ae_ok = False
            st.error("alert_engine.py not found. Ensure it is in the same folder as this app.")

        if _ae_ok:
            # ── Add new alert ──────────────────────────────────────────────────
            with st.expander("➕ Add New Alert", expanded=True):
                _al_c1, _al_c2, _al_c3 = st.columns([2, 2, 2])
                with _al_c1:
                    _al_sym = st.text_input(
                        "Symbol", placeholder="INFY.NS / RELIANCE.NS / NIFTY=F",
                        key="alert_sym"
                    ).strip().upper()
                    if _al_sym and not any(c in _al_sym for c in [".", "=", "^"]):
                        _al_sym += ".NS"
                with _al_c2:
                    _al_cond = st.selectbox(
                        "Condition", ["above", "below", "crossing"], key="alert_cond"
                    )
                with _al_c3:
                    _al_price = st.number_input(
                        "Trigger Price ₹", min_value=0.01, step=1.0, format="%.2f",
                        key="alert_price"
                    )
                _al_note = st.text_input(
                    "Note (optional)", placeholder="e.g. Breakout level / SL hit",
                    key="alert_note"
                )
                _al_add_btn = st.button("✅ Add Alert", type="primary", key="add_alert_btn")
                if _al_add_btn:
                    if not _al_sym or _al_price <= 0:
                        st.warning("Enter a valid symbol and price.")
                    else:
                        _new_alert = add_alert(_al_sym, _al_cond, _al_price, _al_note)
                        st.success(
                            f"🔔 Alert added: **{_al_sym}** {_al_cond} ₹{format_inr(_al_price)}"
                        )
                        st.rerun()

            st.markdown("---")

            # ── List existing alerts ──────────────────────────────────────────
            _all_alerts = list_alerts()
            _active_alerts = [a for a in _all_alerts if a.get("active")]
            _fired_alerts  = [a for a in _all_alerts if not a.get("active")]

            section(f"Active Alerts ({len(_active_alerts)})")
            if not _active_alerts:
                st.info("No active alerts. Add one above.")
            else:
                # Quick-check prices inline
                if st.button("⚡ Check Prices Now", key="check_alerts_btn"):
                    _cur_prices = {}
                    _prog = st.progress(0, text="Fetching prices…")
                    for _i, _al in enumerate(_active_alerts):
                        _cur_prices[_al["symbol"]] = get_current_price(_al["symbol"])
                        _prog.progress((_i + 1) / len(_active_alerts))
                    _prog.empty()
                    st.session_state["alert_prices"] = _cur_prices

                _cached_prices = st.session_state.get("alert_prices", {})

                for _al in _active_alerts:
                    _al_col1, _al_col2, _al_col3, _al_col4 = st.columns([3, 2, 2, 2])
                    _cur_p = _cached_prices.get(_al["symbol"])
                    _dist  = (
                        f"({((_cur_p / _al['price']) - 1) * 100:+.1f}% away)"
                        if _cur_p else ""
                    )
                    with _al_col1:
                        st.markdown(
                            f"**{_al['symbol']}** — {_al['condition']} ₹{format_inr(_al['price'])}  "
                            f"<span style='color:var(--muted);font-size:0.8rem'>{_dist}</span>"
                            + (f"  *{_al['note']}*" if _al.get("note") else ""),
                            unsafe_allow_html=True
                        )
                        st.caption(f"Added {_al.get('created_at','')}")
                    with _al_col2:
                        if _cur_p:
                            _trig_color = "var(--bull)" if (
                                (_al["condition"] == "above"    and _cur_p >= _al["price"]) or
                                (_al["condition"] == "below"    and _cur_p <= _al["price"]) or
                                (_al["condition"] == "crossing" and abs(_cur_p - _al["price"]) / max(_al["price"], 1) < 0.003)
                            ) else "var(--muted)"
                            st.markdown(
                                f'<div style="color:{_trig_color};font-size:0.9rem">₹{format_inr(_cur_p)}</div>',
                                unsafe_allow_html=True
                            )
                    with _al_col3:
                        if st.button("🔕 Pause", key=f"pause_{_al['id'][:8]}"):
                            toggle_alert(_al["id"])
                            st.rerun()
                    with _al_col4:
                        if st.button("🗑️ Remove", key=f"del_{_al['id'][:8]}"):
                            remove_alert(_al["id"])
                            st.rerun()
                    st.markdown('<hr style="margin:4px 0;border-color:var(--rule)">', unsafe_allow_html=True)

            # ── Fired history ─────────────────────────────────────────────────
            if _fired_alerts:
                st.markdown("---")
                section(f"Fired History ({len(_fired_alerts)})")
                _fh_rows = []
                for _al in reversed(_fired_alerts):
                    _fh_rows.append({
                        "Symbol":    _al["symbol"],
                        "Condition": f"{_al['condition']} ₹{format_inr(_al['price'])}",
                        "Note":      _al.get("note", ""),
                        "Fired At":  _al.get("fired_at", ""),
                        "Added":     _al.get("created_at", ""),
                    })
                st.dataframe(pd.DataFrame(_fh_rows), use_container_width=True, hide_index=True)
                if st.button("🧹 Clear Fired History", key="clear_fired"):
                    from alert_engine import _load as _ae_load, _save as _ae_save
                    _ae_save([a for a in _ae_load() if a.get("active")])
                    st.rerun()
