# commander_pages/dashboard.py - the DASHBOARD page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('dashboard', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📊 Mission Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Real-Time Market Intelligence // Sector Radar // Risk Audit</div>', unsafe_allow_html=True)

    df_active = app_state.df_active_global

    # BUG-12 FIX: batch yfinance fetch instead of per-symbol loop
    live_map = {}
    if not df_active.empty:
        syms = tuple(df_active['Symbol'].unique().tolist())
        live_map = get_batch_ltps(syms)

    # ── AI Quick Brief ────────────────────────────────────────────────────────
    _db_brief_text = None
    if _SCHED_OK:
        try:
            _db_cached = load_latest_report("premarket")
            _db_brief_text = _db_cached.get("text") if _db_cached else None
            _db_brief_age  = _db_cached.get("generated_at", "") if _db_cached else ""
        except Exception:
            _db_brief_text = None; _db_brief_age = ""

    # Dashboard's AI Brief is INTENTIONALLY a quick snippet (first ~300 words)
    # of the latest pre-market briefing. It exists so the trader gets context
    # the moment they land on the dashboard. The full briefing — with global
    # indices, FII/DII, calendar, options snapshot — lives on PRE-MARKET → Brief.
    # Per user feedback (B, 10 May 2026): the role distinction is now explicit
    # in the expander label and caption.
    with st.expander("📰 AI Brief — Quick Preview" + (f"  ·  {_db_brief_age}" if _db_brief_text and _db_brief_age else "  ·  click to generate") + "  ·  full briefing in PRE-MARKET → Brief", expanded=False):
        if _db_brief_text:
            st.caption(
                "Snippet from the latest pre-market briefing (~300 words). "
                "For the full report + global indices + FII/DII + calendar + options, "
                "open **🌅 PRE-MARKET → 📋 Brief**."
            )
            _db_words  = _db_brief_text.split()
            _db_snippet = " ".join(_db_words[:300]) + ("…" if len(_db_words) > 300 else "")
            st.markdown(f'<div style="font-size:0.85rem;line-height:1.65;color:var(--ink);">{_db_snippet}</div>',
                        unsafe_allow_html=True)
            if st.button("📖 Open Full Brief in PRE-MARKET", key="db_full_brief"):
                _goto_page("PRE-MARKET"); st.rerun()
        else:
            st.caption(
                "No cached report yet. Generate one here for the snippet, OR open "
                "**🌅 PRE-MARKET → 📋 Brief** to generate the full briefing in its proper home."
            )
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Quick Brief (~30s)", key="db_gen_brief", type="primary"):
                    with st.spinner("Building market snapshot and generating AI brief…"):
                        try:
                            _db_snap  = build_premarket_snapshot()
                            _db_brief = generate_premarket_brief(_db_snap)
                            st.session_state["db_quick_brief"] = _db_brief
                        except Exception as _dbe:
                            st.error(f"Generation failed: {_dbe}")
                if st.session_state.get("db_quick_brief"):
                    _render_ai_report(st.session_state["db_quick_brief"], header_color="var(--acc)")

    st.markdown("---")
    section("Quick Launch")
    # Dashboard reorg (10 May 2026 — user feedback A + F + later):
    #   • Sector Radar moved to MACRO → Sector RRG
    #   • Complete Workflow / Auto-Pilot lives in sidebar + WATCHLIST tab (one script)
    #   • Sector Momentum Heatmap removed (lives in MACRO and BREADTH)
    #   • Export PDF removed — Market Briefing already produces a PDF (no separate btn needed)
    # Dashboard now hosts only the daily portfolio-decision action: Market Briefing.
    if st.button("📝  Market Briefing\nDaily strategic analysis and sector rotation — produces PDF.\n→  Generate Report", key="db_brief", use_container_width=True, type="primary"):
        launch_script("workflow_strategic_briefing.py")

    st.markdown("---")

    # ── OPEN PORTFOLIO HEALTH VITALS ──
    if not app_state.df_live_holdings.empty:
        section("Open Portfolio Health Vitals")

        pos_pnls, pos_pnl_pcts, pos_names = [], [], []
        total_unrealized = 0.0
        deployed_cost    = 0.0   # BUG-06: renamed from total_deployed to avoid shadowing

        for _, row in app_state.df_live_holdings.iterrows():
            sym = row.get('CleanSymbol', clean_symbol(row.get('Symbol', '')))
            bp  = float(row.get('BuyPrice', 0) or 0)
            qty = float(row.get('Quantity', 0) or 0)
            # Priority: broker LTP (most reliable for Indian stocks) → yfinance batch → BuyPrice
            broker_ltp = float(row.get('LTP', 0) or 0)
            ltp = broker_ltp if broker_ltp > 0 else (live_map.get(sym) or bp)
            if bp > 0 and qty > 0:
                pnl_rs  = (ltp - bp) * qty
                pnl_pct = ((ltp - bp) / bp) * 100
                pos_pnls.append(pnl_rs); pos_pnl_pcts.append(pnl_pct); pos_names.append(sym)
                total_unrealized += pnl_rs
                deployed_cost    += bp * qty

        n_eval    = len(pos_pnl_pcts)
        win_pcts  = [p for p in pos_pnl_pcts if p > 0]
        loss_pcts = [p for p in pos_pnl_pcts if p <= 0]
        winning, losing = len(win_pcts), len(loss_pcts)
        win_rate    = (winning / n_eval * 100) if n_eval > 0 else 0
        avg_gain_pct = sum(win_pcts)  / winning if winning > 0 else 0
        avg_loss_pct = sum(loss_pcts) / losing  if losing  > 0 else 0

        # BUG-03 FIX: show ∞ when no losing positions
        if avg_loss_pct != 0:
            risk_reward_str = f"{abs(avg_gain_pct / avg_loss_pct):.2f}"
        else:
            risk_reward_str = "∞" if winning > 0 else "N/A"

        # BUG-05 FIX: Open Return uses deployed capital, not total capital
        open_return_pct     = (total_unrealized / deployed_cost * 100) if deployed_cost > 0 else 0
        portfolio_return_pct = (total_unrealized / app_state.total_cap * 100)    if app_state.total_cap > 0 else 0

        v1, v2, v3, v4 = st.columns(4, gap="small")
        v1.metric("Unrealized P&L",    f"₹{format_inr_int(total_unrealized)}", help="Total unrealized P&L across all open positions.")
        v2.metric("Return on Deployed", f"{open_return_pct:.1f}%",             help="Unrealized P&L / Total deployed cost.")
        v3.metric("Portfolio Return",  f"{portfolio_return_pct:.1f}%",          help="Unrealized P&L / Total portfolio capital.")
        v4.metric("Current Value",     f"₹{format_inr_int(deployed_cost + total_unrealized)}", help="Current market value of all open positions.")

        ev1, ev2, ev3, ev4 = st.columns(4, gap="small")
        ev1.metric("Win Rate",    f"{win_rate:.1f}%  ({winning}W / {losing}L)")
        ev2.metric("Avg Gain %",  f"{avg_gain_pct:.1f}%")
        ev3.metric("Avg Loss %",  f"{avg_loss_pct:.1f}%")
        ev4.metric("Risk/Reward", risk_reward_str, help="Avg Gain% / |Avg Loss%|. ∞ = all positions in profit.")

        # ── E-6 (v2.3): Exit Signal Engine — Auto-Scan ───────────────────
        # Pipe exit_signal_engine alerts directly into the dashboard so the
        # trader sees which open positions need attention *alongside* the
        # portfolio vitals — no separate CLI run required.
        with st.expander("🔴 Exit Signal Scan — Check Positions for Exit Alerts", expanded=False):
            st.caption(
                "Runs the Exit Signal Engine on all open positions: checks stop-loss proximity, "
                "R-multiple targets, Weinstein stage decay, and RS fading. Regime-aware (v2.3)."
            )
            if st.button("⚡ Run Exit Scan", key="e6_exit_scan", type="primary"):
                with st.spinner("Scanning open positions for exit signals..."):
                    try:
                        from exit_signal_engine import run_exit_scan
                        _exit_df = run_exit_scan(silent=True)
                        st.session_state["e6_exit_results"] = _exit_df
                    except Exception as _e6e:
                        st.error(f"Exit scan failed: {_e6e}")
                        st.session_state["e6_exit_results"] = None

            _exit_cached = st.session_state.get("e6_exit_results")
            if _exit_cached is not None and not _exit_cached.empty:
                _action_df = _exit_cached[_exit_cached["Exit_Flag"] == "ACTION"]
                _hold_df   = _exit_cached[_exit_cached["Exit_Flag"] != "ACTION"]

                if not _action_df.empty:
                    st.markdown(
                        f'<div style="background:rgba(255,75,75,0.1);border-left:3px solid var(--bear);'
                        f'padding:8px 12px;border-radius:4px;margin-bottom:8px;">'
                        f'<strong style="color:var(--bear);">⚠ {len(_action_df)} position(s) need attention</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    # Display the ACTION rows in a clean table
                    _display_cols = ["Symbol", "LTP", "R_Multiple", "Weinstein_Stage",
                                     "Mansfield_RS", "Exit_Reasons"]
                    _show_cols = [c for c in _display_cols if c in _action_df.columns]
                    _show_df = _action_df[_show_cols].copy()
                    if "R_Multiple" in _show_df.columns:
                        _show_df["R_Multiple"] = _show_df["R_Multiple"].apply(
                            lambda x: f"{x:+.1f}R" if pd.notna(x) else "—"
                        )
                    if "Mansfield_RS" in _show_df.columns:
                        _show_df["Mansfield_RS"] = _show_df["Mansfield_RS"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
                        )
                    if "LTP" in _show_df.columns:
                        _show_df["LTP"] = _show_df["LTP"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
                        )
                    st.dataframe(_show_df, use_container_width=True, hide_index=True)

                    # Show recommendations if available
                    if "Recommendations_Str" in _action_df.columns:
                        for _, _ar in _action_df.iterrows():
                            _rec_str = _ar.get("Recommendations_Str", "")
                            if _rec_str:
                                st.markdown(
                                    f'<div style="font-size:0.8rem;color:var(--ink);padding:2px 0;">'
                                    f'<strong>{_ar["Symbol"]}</strong>: {_rec_str}</div>',
                                    unsafe_allow_html=True,
                                )
                else:
                    st.success(f"✅ All {len(_hold_df)} positions healthy — no exit signals triggered.")
            elif _exit_cached is not None:
                st.info("No open positions to scan.")

        st.markdown("---")

    # ── E-01: CLOSED TRADE ANALYTICS ──
    df_closed = load_closed_trades_db()
    if df_closed is not None and not df_closed.empty:
        section("Portfolio Analytics — Closed Trade Performance")
        analytics = compute_portfolio_analytics(df_closed, app_state.total_cap)
        if analytics:
            a1,a2,a3,a4,a5,a6 = st.columns(6, gap="small")
            a1.metric("Sharpe Ratio",    str(analytics.get('sharpe','—')),   help="Annualised Sharpe. >1.0 = good, >2.0 = excellent.")
            a2.metric("Sortino Ratio",   str(analytics.get('sortino','—')),  help="Downside-adjusted Sharpe. Penalises losing days only.")
            a3.metric("Max Drawdown",   f"₹{format_inr_int(abs(analytics.get('max_dd',0)))} ({analytics.get('max_dd_pct',0):.1f}%)", help="Largest peak-to-trough equity drop.")
            a4.metric("Profit Factor",  str(analytics.get('profit_factor','—')), help="Gross Profit / Gross Loss. >1.5 = solid, >2.0 = excellent.")
            a5.metric("Expectancy",     f"₹{format_inr_int(analytics.get('expectancy',0))}", help="Average ₹ expected per trade.")
            a6.metric("Total Realized", f"₹{format_inr_int(analytics.get('total_realized',0))}", help="Cumulative realized P&L from all closed trades.")
        st.markdown("---")

    if not df_active.empty:
        left_col, right_col = st.columns([3, 2], gap="medium")
        with left_col:
            section("Portfolio Heatmap — Capital Allocation")
            hmap = df_active.copy()
            # Phase-2A: enrich blank Sector cells from sectors.db before falling
            # back to "Unassigned". The treemap groups by Sector — accurate cells
            # mean meaningful clusters instead of one giant grey "Unassigned" tile.
            try:
                import sector_lookup as _hm_sl
                def _hm_sec(row):
                    cur = str(row.get('Sector', '') or '').strip()
                    if cur and cur.lower() not in ('', 'nan', 'unassigned', 'other', 'unknown'):
                        return cur
                    rec = _hm_sl.get_sector(row.get('Symbol', ''))
                    return (rec.get('display_name') or rec.get('sector_name')) if rec else 'Unassigned'
                hmap['Sector'] = hmap.apply(_hm_sec, axis=1)
            except Exception:
                hmap['Sector'] = hmap['Sector'].fillna("Unassigned").replace("", "Unassigned")
            hmap['Deployment'] = hmap['Quantity'] * hmap['BuyPrice']
            # Use clean_symbol so "NSE:RELIANCE" etc. resolve against live_map keys.
            # Fallback via `or p` ensures a 0-LTP key in the dict never corrupts the calc.
            hmap['PnLPct']     = [((live_map.get(clean_symbol(s)) or p) - p) / p * 100 if p > 0 else 0
                                   for s, p in zip(hmap['Symbol'], hmap['BuyPrice'])]
            # Format PnLPct for display
            hmap['PnL_Str'] = hmap['PnLPct'].apply(lambda x: f"{x:+.2f}%")
            fig = px.treemap(hmap, path=[px.Constant("Portfolio"), "Sector", "Symbol"],
                             values="Deployment", color="PnLPct",
                             color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                             custom_data=["PnL_Str", "Quantity", "BuyPrice"])
            fig.update_traces(
                textfont=dict(color="#E3EBEC", size=13, family="Inter"),
                hovertemplate="<b>%{label}</b><br>Capital Deployed: ₹%{value:,.0f}<br>Unrealized PnL: %{customdata[0]}<br>Qty: %{customdata[1]} | Buy Price: ₹%{customdata[2]:,.2f}"
            )
            fig.update_layout(margin=dict(t=10,l=0,r=0,b=0), height=320,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#E3EBEC", family="Inter", size=11))
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            section("Alpha Benchmarking vs Nifty 500")
            if df_closed is not None and not df_closed.empty:
                try:
                    # BUG-02 FIX: load_closed_trades_db() already renames — no second rename
                    dfc = df_closed.copy()
                    for col in ['ExitPrice','BuyPrice','Quantity']:
                        dfc[col] = pd.to_numeric(dfc.get(col, 0), errors='coerce').fillna(0)
                    dfc['ExitDate'] = pd.to_datetime(dfc['ExitDate'], errors='coerce')
                    dfc = dfc.dropna(subset=['ExitDate']).sort_values('ExitDate')
                    dfc['PnL'] = (dfc['ExitPrice'] - dfc['BuyPrice']) * dfc['Quantity']
                    pc = dfc.groupby('ExitDate').agg({'PnL': 'sum'}).reset_index()
                    pc['CumulativePnL'] = pc['PnL'].cumsum()

                    # FORM-02 FIX: normalise to starting equity, not current capital
                    starting_equity = app_state.total_cap - pc['CumulativePnL'].iloc[-1]
                    if starting_equity <= 0: starting_equity = app_state.total_cap
                    pc['Portfolio_%'] = (pc['CumulativePnL'] / starting_equity) * 100
                    pc = pc.rename(columns={'ExitDate': 'Date'})

                    import data_provider as _dp_bench
                    nifty_raw = _dp_bench.fetch_ohlcv("^NSEI", period="max", interval="1d")
                    nifty = nifty_raw.loc[pc['Date'].min() - pd.Timedelta(days=7) : pc['Date'].max() + pd.Timedelta(days=1)]
                    if not nifty.empty:
                        nifty = nifty['Close'].reset_index()
                        nifty.columns = ['Date', 'NiftyClose']
                        nifty['Date'] = pd.to_datetime(nifty['Date']).dt.tz_localize(None)
                        if isinstance(nifty['NiftyClose'], pd.DataFrame):
                            nifty['NiftyClose'] = nifty['NiftyClose'].iloc[:, 0]
                        nifty['Benchmark_%'] = ((nifty['NiftyClose'] - nifty['NiftyClose'].iloc[0]) / nifty['NiftyClose'].iloc[0]) * 100
                        merged = pd.merge_asof(pc, nifty[['Date', 'Benchmark_%']], on='Date')
                        fig2 = px.line(merged, x='Date', y=['Portfolio_%', 'Benchmark_%'],
                                       labels={'value': 'Return (%)', 'variable': 'Metric'})
                        fig2.update_layout(height=300, margin=dict(t=10,l=0,r=0,b=0),
                                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           font=dict(color="#E3EBEC", family="Inter", size=11),
                                           xaxis=dict(tickfont=dict(color="#E3EBEC", size=11), title_font=dict(color="#E3EBEC", size=12), gridcolor="#CBD5E1"),
                                           yaxis=dict(tickfont=dict(color="#E3EBEC", size=11), title_font=dict(color="#E3EBEC", size=12), gridcolor="#CBD5E1"),
                                           legend=dict(font=dict(color="#E3EBEC", size=11, weight="bold"), bgcolor="rgba(255,255,255,0.85)", bordercolor="#CBD5E1", borderwidth=1),
                                           yaxis_title="% Return (from starting equity)")
                        st.plotly_chart(fig2, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}")
            else:
                st.info("No closed trades to benchmark yet.")

        # ── ACTIVE POSITIONS P&L TABLE ──
        section("Active Positions — Live P&L")
        pnl_rows = []
        for _, row in df_active.iterrows():
            sym  = row['Symbol']
            bp   = float(row.get('BuyPrice', 0) or 0)
            qty  = float(row.get('Quantity', 0) or 0)
            # `or bp` guards against 0-valued keys that bypass the dict default
            ltp  = live_map.get(sym) or live_map.get(clean_symbol(sym)) or bp
            sl   = float(row.get('StopLoss', 0) or 0)
            tgt  = float(row.get('Target', 0) or 0)
            pnl_rs  = (ltp - bp) * qty
            pnl_pct = ((ltp - bp) / bp * 100) if bp > 0 else 0
            dist_sl  = ((ltp - sl) / ltp * 100) if sl > 0 and ltp > 0 else None
            dist_tgt = ((tgt - ltp) / ltp * 100) if tgt > 0 and ltp > 0 else 0

            atr_val = get_atr(sym)
            sl_atr  = round((ltp - sl) / atr_val, 1) if atr_val > 0 and sl > 0 else None

            entry_dt  = row.get('EntryDate', '')
            try: days_held = (pd.Timestamp.now() - pd.to_datetime(entry_dt)).days if entry_dt else 0
            except (ValueError, TypeError): days_held = 0

            # BUG-10 FIX: Trailing SL awareness (SL > entry is valid for locked-profit trailing)
            if sl > 0 and ltp > 0:
                if sl > bp:
                    sl_status = f"🔒 LOCKED +₹{format_inr_int((sl-bp)*qty)}"
                elif dist_sl is not None and dist_sl < 0:
                    sl_status = f"⚠️ BREACHED {dist_sl:.1f}%"
                else:
                    sl_status = f"{dist_sl:.1f}%" if dist_sl is not None else "—"
            else:
                sl_status = "—"

            pnl_rows.append({
                'Symbol': sym, 'Entry': round(bp,2), 'LTP': round(ltp,2),
                'P&L ₹': round(pnl_rs, 0), 'P&L %': round(pnl_pct,1),
                'SL Status': sl_status, 'Dist Tgt %': round(dist_tgt,1),
                'SL (ATR×)': sl_atr, 'Days': days_held
            })

        if pnl_rows:
            df_pnl = pd.DataFrame(pnl_rows)
            st.dataframe(df_pnl, use_container_width=True, hide_index=True, height=300)

        # ── CORRELATION RISK MATRIX ──
        section("Portfolio Correlation Risk")
        with st.expander("🔍 View Correlation Matrix & Shadow Concentration", expanded=False):
            syms_for_corr = df_active['Symbol'].unique().tolist()
            if len(syms_for_corr) >= 2:
                try:
                    with st.spinner("Computing correlation matrix..."):
                        corr_df, shadows, div_score = get_portfolio_correlation_matrix(syms_for_corr)
                    dc1, dc2 = st.columns([1, 1])
                    with dc1: st.metric("Diversification Score", f"{div_score}/10")
                    with dc2:
                        if shadows:
                            st.warning(f"⚠️ {len(shadows)} Shadow Concentration pair(s) detected!")
                            for sp in shadows:
                                st.caption(f"  {sp['Pair']} → r={sp['Correlation']} ({sp['Risk']})")
                        else:
                            st.success("✅ No shadow concentration detected.")
                    if not corr_df.empty:
                        fig_corr = ff.create_annotated_heatmap(
                            z=corr_df.values.round(2).tolist(),
                            x=corr_df.columns.tolist(), y=corr_df.index.tolist(),
                            colorscale='RdYlGn', showscale=True
                        )
                        fig_corr.update_layout(height=350, margin=dict(t=30,l=0,r=0,b=0),
                                               paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_corr, use_container_width=True)
                except Exception as e:
                    st.error(f"Correlation Error: {e}")
            else:
                st.info("Need at least 2 open positions for correlation analysis.")
    else:
        st.info("No open positions found. Launch a scanner to populate your portfolio.")
