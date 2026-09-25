# commander_pages/command.py - the COMMAND page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('command', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">⚡ Command Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Active trade management and execution protocols.</div>', unsafe_allow_html=True)
    _cm1, _cm2, _cm3 = st.tabs(["⚡ Active Ops", "📒 Ledger", "🔔 Price Alerts"])

    with _cm1:
        section("Active Operations")
        c1, c2, c3, c4, c5 = st.columns(5, gap="small")
        with c1:
            if st.button("🎯  Sniper Entry AI v2\nOrder execution with Institutional AI analysis.\n→  Launch", use_container_width=True, key="cmd_sniper"):
                launch_script("sniper_trigger.py")
        with c2:
            if st.button("🛡️  GTT Auto-Shield\nAuto-protect holdings using Journal levels.\n→  Launch", use_container_width=True, key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  Telegram Sentinel\nActive market monitoring via Mobile.\n→  Launch", use_container_width=True, key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        with c4:
            if st.button("🤖  Market Monitor Agent\nLive intraday scans and Telegram alerts.\n→  Launch", use_container_width=True, key="cmd_monitor"):
                launch_script("market_monitor_agent.py")
        with c5:
            if st.button("🔌  Dhan Webhook Gateway\nExpose port 8000 via ngrok for TV alerts.\n→  Launch", use_container_width=True, key="cmd_webhook"):
                launch_script("dhan_tv_webhook.py")

        # ── MISS-1: EXIT SIGNAL ENGINE ───────────────────────────────────────
        st.markdown("---")
        section("MISS-1 · Exit Signal Engine")
        st.caption(
            "Watchdog scanner for open positions. Flags SL-breach, target hit, "
            "stage decay (Stage 2 → 3/4), and RS fade (positive → negative) alerts."
        )
        _exit_csv = os.path.join(_APP_DIR, "Exit_Signals.csv")
        _ec1, _ec2 = st.columns([1, 3], gap="small")
        with _ec1:
            # NOTE (31-Jul-2026): this used to launch with `--silent`. The engine
            # honours that flag by redirecting ALL stdout to a sink, so the console
            # window that `launch_script` opens printed NOTHING and sat there blank —
            # the scan ran fine and wrote Exit_Signals.csv, but it looked dead. The
            # silent contract exists for the in-process import path (line ~4557),
            # NOT for a user-launched console. Run it loud so the scan is visible;
            # the engine's own input("Press Enter") then holds the window open.
            if st.button("🚨  Scan Exit Signals\nCheck all open positions for exit triggers.\n→  Scan Now",
                         use_container_width=True, key="cmd_exit_scan", type="primary"):
                launch_script("exit_signal_engine.py")
                st.info("Scan running in the console window. When it finishes, "
                        "click ↻ Reload results below.")
            if st.button("↻  Reload results", use_container_width=True, key="cmd_exit_reload"):
                st.rerun()
        with _ec2:
            if os.path.exists(_exit_csv):
                try:
                    _df_exit = pd.read_csv(_exit_csv)
                    _action  = _df_exit[_df_exit.get("Exit_Flag", pd.Series()) == "ACTION"] if "Exit_Flag" in _df_exit.columns else pd.DataFrame()
                    if not _action.empty:
                        # pd.Timestamp(mtime, unit='s') is UTC — it rendered every
                        # scan 5h30m in the past (an 08:42 IST run read "03:12"),
                        # which made a scan that HAD just run look like it never did.
                        # datetime.fromtimestamp() is local (IST) time.
                        _scan_at = datetime.fromtimestamp(os.path.getmtime(_exit_csv))
                        st.warning(f"⚠️ **{len(_action)} position(s) need attention** — last scan: "
                                   f"{_scan_at.strftime('%d %b %H:%M')}")
                        _exit_show = [c for c in ["Symbol","LTP","Weinstein_Stage","Mansfield_RS","StopLoss","Target","Exit_Reasons"] if c in _action.columns]
                        st.dataframe(_action[_exit_show], use_container_width=True, hide_index=True)
                    else:
                        st.success("✅ All positions clear — no exit signals.")
                except Exception:
                    st.info("Run Exit Scan to generate results.")

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

        # ── E-02: TRAILING STOP ENGINE ──────────────────────────────────────
        st.markdown("---")
        section("E-02 · Trailing Stop Engine")
        st.caption("The SAME Chandelier the Risk Shield, the pyramid ladder and the GTT trailer use "
                   "(risk_common: swing 14-bar / positional 22-bar highest CLOSE − Wilder ATR × the "
                   "catalyst multiplier, +0.5 in a bear regime). SL > Entry = Locked Profit state.")
        # 25-Sep-2026: this was a fifth stop engine - highest HIGH since entry minus an
        # ADR-bucket multiplier - so one position showed two different suggested stops.
        df_active_cmd = df_active_global
        if not df_active_cmd.empty:
            trail_rows = []
            syms_cmd   = tuple(df_active_cmd['Symbol'].unique().tolist())
            live_prices_cmd = get_batch_ltps(syms_cmd)
            _bear_cmd = bool(_HP.regime().get("bear"))
            import data_provider as dp
            for _, row in df_active_cmd.iterrows():
                sym       = row['Symbol']
                bp        = float(row.get('BuyPrice', 0) or 0)
                qty       = float(row.get('Quantity', 0) or 0)
                curr_sl   = float(row.get('StopLoss', 0) or 0)
                ltp       = live_prices_cmd.get(sym) or live_prices_cmd.get(clean_symbol(sym)) or bp
                atr_val   = 0.0
                atr_trail_sl, _mult_cmd, _src_cmd = None, None, None
                try:
                    hist = dp.fetch_ohlcv(sym, period="2y", interval="1d", auto_adjust=True, use_cache=True)
                    if hist is not None and len(hist) > 30:
                        _swing_cmd = _rc.resolve_trade_type(
                            timeframe=row.get('Timeframe') or None, setup=row.get('Setup') or None,
                            entry=bp or None, stop=curr_sl or None)[0]
                        _a200 = (len(hist) < 200) or float(hist['Close'].iloc[-1]) > float(hist['Close'].rolling(200).mean().iloc[-1])
                        _cm = row.get('Custom CE Mult')
                        _cm = float(_cm) if (_cm is not None and str(_cm).strip() not in ("", "nan", "None")) else None
                        atr_trail_sl, _mult_cmd, _src_cmd = _rc.chandelier_exit(
                            hist['High'], hist['Low'], hist['Close'], setup=str(row.get('Setup') or ""),
                            bear=_bear_cmd, custom_mult=_cm, above200=_a200, swing=_swing_cmd)
                        _tr = pd.concat([hist['High'] - hist['Low'], (hist['High'] - hist['Close'].shift()).abs(),
                                         (hist['Low'] - hist['Close'].shift()).abs()], axis=1).max(axis=1)
                        atr_val = float(_tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
                        _msl = row.get('Manual SL Override')
                        if _msl is not None and str(_msl).strip() not in ("", "nan", "None") and float(_msl) > 0 \
                                and atr_trail_sl is not None:
                            atr_trail_sl = max(atr_trail_sl, float(_msl))    # Floor semantics, as the trailer
                except Exception as e:
                    logger.warning(f"E-02 Chandelier {sym}: {e}")
                if atr_trail_sl is None:
                    atr_trail_sl = curr_sl
                suggested_sl = max(atr_trail_sl, curr_sl)   # never trail backwards

                # Status — breach is always against Current SL (actual active stop),
                # NOT against suggested_sl (which is a recommendation only).
                if ltp < curr_sl:
                    status = "⚠️ SL BREACHED"
                elif suggested_sl > ltp:
                    # Price has fallen through where the ATR trail would have stopped you,
                    # but the actual SL was never moved up — warn user to update or exit.
                    status = f"📉 TRAIL LAPSED — update SL or exit"
                elif curr_sl > bp:
                    status = f"🔒 LOCKED (+₹{format_inr_int((curr_sl-bp)*qty)})"
                elif suggested_sl > curr_sl:
                    status = f"📈 TRAIL → ₹{format_inr(suggested_sl)}"
                else:
                    status = "✅ AT ENTRY SL"

                trail_rows.append({
                    'Symbol':       sym,
                    'Entry':        round(bp, 2),
                    'LTP':          round(ltp, 2),
                    'Current SL':   round(curr_sl, 2),
                    'Chandelier':   round(atr_trail_sl, 2),
                    'Mult':         (f"{_mult_cmd:g}× {_src_cmd}" if _mult_cmd else "—"),
                    'Suggested SL': round(suggested_sl, 2),
                    'ATR':          round(atr_val, 2),
                    'Status':       status
                })

            if trail_rows:
                df_trail = pd.DataFrame(trail_rows)
                st.dataframe(df_trail, use_container_width=True, hide_index=True, height=340)
                st.info("💡 Update 'Current SL' values in your Journal then re-run GTT Auto-Shield to push updated levels to Dhan.")
        else:
            st.info("No open positions found in journal.")

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
        section("GTT Orders — Live View")
        _gtt_c1, _gtt_c2 = st.columns([1, 5])
        with _gtt_c1:
            _gtt_refresh = st.button("🔄 Fetch GTTs", key="gtt_refresh", type="primary")
        with _gtt_c2:
            st.caption("Pulls active GTT orders from Dhan. Refreshes on click.")

        if _gtt_refresh or st.session_state.get("gtt_loaded"):
            with st.spinner("Fetching GTT orders from Dhan…"):
                try:
                    from dhan_auth import get_dhan_client as _gdc
                    _dhan_gtt  = _gdc()
                    # 10 May 2026 fix: Dhan SDK exposes GTTs under
                    # `get_forever()` (Dhan terminology = "Forever Orders").
                    # Previously called the non-existent `get_gtt_list()` →
                    # AttributeError → empty fallback → "No GTTs found"
                    # message even when many were pending.
                    _gtt_resp  = _dhan_gtt.get_forever()
                    if isinstance(_gtt_resp, dict) and _gtt_resp.get("status") == "success":
                        _gtt_data = _gtt_resp.get("data") or []
                    else:
                        _gtt_data = []
                        if isinstance(_gtt_resp, dict):
                            st.warning(f"Dhan returned non-success: "
                                        f"{_gtt_resp.get('remarks', _gtt_resp)}")
                    st.session_state["gtt_loaded"] = True
                    st.session_state["gtt_data"]   = _gtt_data
                except Exception as _gtte:
                    st.error(f"GTT fetch failed: {_gtte}")
                    _gtt_data = []

            _gtt_data = st.session_state.get("gtt_data", [])
            if _gtt_data:
                # Each row in `data` is a single leg of a Forever Order
                # (e.g. an OCO order produces 2 legs: STOP_LOSS_LEG + TARGET_LEG).
                _gtt_rows = []
                for _gtt_r in _gtt_data:   # was `_g` - it shadowed the shared _g() helper
                    _ot = _gtt_r.get("orderType", "")  # SINGLE or OCO
                    _leg = _gtt_r.get("legName", "")   # STOP_LOSS_LEG / TARGET_LEG / ENTRY_LEG
                    _txn = _gtt_r.get("transactionType", "")  # BUY/SELL
                    # Type column: combine action + leg context for clarity
                    _type_label = f"{_txn} · {_ot}"
                    if _leg and _leg != "ENTRY_LEG":
                        _type_label += f" · {_leg.replace('_LEG','').replace('_',' ').title()}"
                    _gtt_rows.append({
                        "Symbol":     _gtt_r.get("tradingSymbol", ""),
                        "Type":       _type_label,
                        "Trigger ₹":  _gtt_r.get("triggerPrice", ""),
                        "Price ₹":    _gtt_r.get("price", ""),
                        "Qty":        _gtt_r.get("quantity", ""),
                        "Status":     _gtt_r.get("orderStatus", ""),
                        "Created":    str(_gtt_r.get("createTime", ""))[:10],
                        "Order ID":   _gtt_r.get("orderId", ""),
                    })
                _df_gtt = pd.DataFrame(_gtt_rows)
                # Sort: PENDING first, then by Symbol
                if "Status" in _df_gtt.columns:
                    _df_gtt["_sp"] = (_df_gtt["Status"] == "PENDING").map(
                        {True: 0, False: 1}
                    )
                    _df_gtt = _df_gtt.sort_values(["_sp", "Symbol"]).drop(columns=["_sp"])
                st.dataframe(_df_gtt, use_container_width=True, hide_index=True)
                _n_pending = int((_df_gtt["Status"] == "PENDING").sum()) \
                              if "Status" in _df_gtt.columns else len(_df_gtt)
                st.caption(f"{_n_pending} pending GTT(s) of {len(_df_gtt)} total | "
                           "To cancel, use the Dhan app or Journal GTT Shield.")
            else:
                st.info("No GTT orders returned by Dhan API. "
                        "If you have active GTTs in the Dhan app, check that "
                        "your access token isn't expired (sidebar → 🔑 Token detail).")

        st.markdown("---")
        section("External Apps")
        if st.button("📓  Open Full Journal\nActive trades, closed history, performance lab.\n→  Open", use_container_width=True, key="cmd_journal"):
            # 23-Sep: navigates instead of spawning a second Streamlit process.
            _goto_page("JOURNAL")
            st.rerun()

    with _cm2:
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            section("Live Trade Ledger")
        with col2:
            st.write("") # Spacer
            if st.button("🔄 Sync to TV", help="Sync Active Ledger to Pine Script Dashboard", use_container_width=True):
                with st.spinner("Syncing..."):
                    try:
                        import subprocess
                        subprocess.run([_PYTHON_EXE, "db_portfolio_sync.py"], capture_output=True, text=True, check=True)
                        st.success("✅ Synced! Copy code from `Weinstein and Swing Pro Dashboard v67.4.12.pine`")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {e}")
                        
        df_j = load_journal_db()
        if not df_j.empty:
            show = [c for c in ["Symbol","Type","BuyPrice","Quantity","Status",
                                 "Sector","StopLoss","Target","PlannedRR","Timeframe"] if c in df_j.columns]
            st.dataframe(df_j[show], use_container_width=True, height=500, hide_index=True)
        else:
            st.info("No open trades found in the system.")

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
                            f"🔔 Alert added: **{_al_sym}** {_al_cond} ₹{_al_price:,.2f}"
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
                            f"**{_al['symbol']}** — {_al['condition']} ₹{_al['price']:,.2f}  "
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
                                f'<div style="color:{_trig_color};font-size:0.9rem">₹{_cur_p:,.2f}</div>',
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
                        "Condition": f"{_al['condition']} ₹{_al['price']:,.2f}",
                        "Note":      _al.get("note", ""),
                        "Fired At":  _al.get("fired_at", ""),
                        "Added":     _al.get("created_at", ""),
                    })
                st.dataframe(pd.DataFrame(_fh_rows), use_container_width=True, hide_index=True)
                if st.button("🧹 Clear Fired History", key="clear_fired"):
                    from alert_engine import _load as _ae_load, _save as _ae_save
                    _ae_save([a for a in _ae_load() if a.get("active")])
                    st.rerun()
