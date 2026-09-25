# commander_pages/autopsy.py - the AUTOPSY page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('autopsy', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🔬 Trade Autopsy</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Post-Trade Performance Intelligence — Closed Trade Analytics</div>', unsafe_allow_html=True)
    _ap1, _ap2, _ap3, _ap4, _ap5 = st.tabs(["📊 Overview", "📅 Calendar", "🏭 Sectors", "🎯 Trade Quality", "📐 Attribution"])

    df_closed = load_closed_trades_db()
    if df_closed is None or df_closed.empty:
        st.info("No closed trades found. Complete some trades to unlock the Autopsy Engine.")
    else:
        for col in ['ExitPrice','BuyPrice','Quantity']:
            df_closed[col] = pd.to_numeric(df_closed.get(col, 0), errors='coerce').fillna(0)
        df_closed['PnL']     = (df_closed['ExitPrice'] - df_closed['BuyPrice']) * df_closed['Quantity']
        df_closed['PnL_pct'] = np.where(df_closed['BuyPrice'] > 0,
                                         (df_closed['ExitPrice'] - df_closed['BuyPrice']) / df_closed['BuyPrice'] * 100, 0)
        df_closed['ExitDate']  = pd.to_datetime(df_closed['ExitDate'],  errors='coerce')
        df_closed['EntryDate'] = pd.to_datetime(df_closed.get('EntryDate', pd.NaT), errors='coerce')
        df_closed['DaysHeld']  = (df_closed['ExitDate'] - df_closed['EntryDate']).dt.days
        df_closed = df_closed.dropna(subset=['ExitDate'])

        with _ap1:
            analytics = compute_portfolio_analytics(df_closed, total_cap)
            if analytics:
                section("Closed Trade Summary")
                o1,o2,o3 = st.columns(3, gap="small")
                o1.metric("Total Trades",    str(analytics['total_trades']))
                o2.metric("Win Rate",        f"{analytics['win_rate']}%")
                o3.metric("Total Realized",  f"₹{format_inr_int(analytics['total_realized'])}")
                o4,o5,o6 = st.columns(3, gap="small")
                o4.metric("Sharpe Ratio",    str(analytics['sharpe']))
                o5.metric("Profit Factor",   str(analytics['profit_factor']))
                o6.metric("Expectancy/Trade",f"₹{format_inr_int(analytics['expectancy'])}")
                o7,o8,o9 = st.columns(3, gap="small")
                o7.metric("Max Drawdown",    f"₹{format_inr_int(abs(analytics['max_dd']))} ({analytics['max_dd_pct']}%)")
                o8.metric("Avg Win ₹",       f"₹{format_inr_int(analytics['avg_win_rs'])}")
                o9.metric("Avg Loss ₹",      f"₹{format_inr_int(abs(analytics['avg_loss_rs']))}")

            section("Holding Period Analysis")
            if 'DaysHeld' in df_closed.columns and df_closed['DaysHeld'].notna().any():
                winners = df_closed[df_closed['PnL'] > 0]['DaysHeld'].dropna()
                losers  = df_closed[df_closed['PnL'] <= 0]['DaysHeld'].dropna()
                h1,h2,h3 = st.columns(3, gap="small")
                h1.metric("Avg Days Held (All)",     f"{df_closed['DaysHeld'].mean():.0f} days")
                h2.metric("Avg Days Held (Winners)", f"{winners.mean():.0f} days" if len(winners) else "N/A")
                h3.metric("Avg Days Held (Losers)",  f"{losers.mean():.0f} days"  if len(losers)  else "N/A")

            section("Equity Curve")
            ec = df_closed.sort_values('ExitDate').copy()
            ec['Cum PnL'] = ec['PnL'].cumsum()
            fig_ec = px.area(ec, x='ExitDate', y='Cum PnL',
                             labels={'Cum PnL':'Cumulative P&L (₹)','ExitDate':'Date'})
            fig_ec.update_traces(line_color='#15803D', fillcolor='rgba(0,242,96,0.08)')
            fig_ec.update_layout(height=280, margin=dict(t=10,l=0,r=0,b=0),
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"),
                                  font=dict(color="#E3EBEC"))
            st.plotly_chart(fig_ec, use_container_width=True)

        with _ap2:
            section("Monthly P&L Calendar")
            cal = df_closed.copy()
            cal['YM'] = cal['ExitDate'].dt.to_period('M').astype(str)
            monthly   = cal.groupby('YM')['PnL'].sum().reset_index()
            monthly['Year']  = monthly['YM'].str[:4]
            monthly['Month'] = monthly['YM'].str[5:].astype(int)

            if not monthly.empty:
                pivot = monthly.pivot(index='Year', columns='Month', values='PnL').fillna(0)
                month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                pivot.columns = [month_names[m-1] for m in pivot.columns]
                fig_cal = px.imshow(pivot, color_continuous_scale='RdYlGn',
                                     color_continuous_midpoint=0, aspect='auto',
                                     labels=dict(color='P&L ₹'))
                fig_cal.update_layout(height=max(200, len(pivot)*60+80),
                                       margin=dict(t=10,l=0,r=0,b=0),
                                       paper_bgcolor="rgba(0,0,0,0)",
                                       font=dict(color="#E3EBEC"))
                st.plotly_chart(fig_cal, use_container_width=True)

            section("Monthly P&L Table")
            monthly['P&L ₹'] = monthly['PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
            monthly['Signal'] = monthly['PnL'].apply(lambda x: '✅ Profit' if x > 0 else '❌ Loss')
            st.dataframe(monthly[['YM','P&L ₹','Signal']].rename(columns={'YM':'Month'}),
                         use_container_width=True, hide_index=True)

        with _ap3:
            section("Sector P&L Breakdown")
            if 'Sector' in df_closed.columns:
                sec_pnl = df_closed.groupby('Sector').agg(
                    Trades   = ('PnL','count'),
                    Total_PnL= ('PnL','sum'),
                    Win_Rate = ('PnL', lambda x: (x > 0).sum() / len(x) * 100),
                    Avg_PnL  = ('PnL','mean')
                ).reset_index().sort_values('Total_PnL', ascending=False)
                sec_pnl['Total ₹']  = sec_pnl['Total_PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
                sec_pnl['Avg ₹']    = sec_pnl['Avg_PnL'].apply(lambda x:  f"₹{format_inr_int(x)}")
                sec_pnl['Win Rate'] = sec_pnl['Win_Rate'].apply(lambda x:  f"{x:.0f}%")
                st.dataframe(sec_pnl[['Sector','Trades','Total ₹','Avg ₹','Win Rate']],
                             use_container_width=True, hide_index=True)
                fig_sec = px.bar(sec_pnl, x='Sector', y='Total_PnL',
                                  color='Total_PnL', color_continuous_scale='RdYlGn',
                                  color_continuous_midpoint=0,
                                  labels={'Total_PnL':'Total P&L (₹)'})
                fig_sec.update_layout(height=280, margin=dict(t=10,l=0,r=0,b=0),
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"),
                                       font=dict(color="#E3EBEC"))
                st.plotly_chart(fig_sec, use_container_width=True)

                # ── Sector COVERAGE view (10 May 2026) ──────────────────
                # The table above only shows sectors where you have CLOSED
                # trades. User feedback: "only 12 sectors". Add a coverage
                # view showing ALL NSE sectors + which ones you've traded
                # vs not — useful for spotting concentration / blind spots.
                try:
                    from breadth_engine import NSE_SECTORS_YF as _all_nse_secs
                    _traded_secs = set(df_closed['Sector'].dropna().astype(str)
                                       .str.lower().str.strip())
                    _all_sec_names = sorted(_all_nse_secs.keys())

                    def _norm(s):
                        return str(s).lower().replace("nifty ", "").strip()
                    _traded_norm = {_norm(s) for s in _traded_secs}

                    _coverage_rows = []
                    for sec in _all_sec_names:
                        norm = _norm(sec)
                        traded = norm in _traded_norm
                        # find matching row in sec_pnl (best-effort name match)
                        match = sec_pnl[sec_pnl['Sector'].astype(str)
                                          .str.lower().str.contains(norm, na=False)]
                        if not match.empty:
                            n_t   = int(match.iloc[0]['Trades'])
                            tot   = float(match.iloc[0]['Total_PnL'])
                        else:
                            n_t, tot = 0, 0.0
                        _coverage_rows.append({
                            'Sector':  sec,
                            'Status':  '✅ Traded' if traded else '⚪ Untraded',
                            'Trades':  n_t,
                            'Total ₹': f"₹{format_inr_int(tot)}" if n_t > 0 else "—",
                        })
                    _df_cov = pd.DataFrame(_coverage_rows)
                    _df_cov['_sort'] = _df_cov['Trades']
                    _df_cov = _df_cov.sort_values('_sort', ascending=False).drop(columns=['_sort'])

                    _n_traded = (_df_cov['Status'] == '✅ Traded').sum()
                    _n_untraded = len(_df_cov) - _n_traded
                    section(f"Sector Coverage — Traded {_n_traded} of "
                            f"{len(_df_cov)} NSE sectors ({_n_untraded} untraded)")
                    st.dataframe(_df_cov, use_container_width=True, hide_index=True,
                                 height=min(40 + 35*len(_df_cov), 600))
                    if _n_untraded > 0:
                        _untraded = _df_cov[_df_cov['Status'] == '⚪ Untraded']['Sector'].tolist()
                        st.caption(f"Untraded sectors: {', '.join(_untraded)}. "
                                   "Worth exploring if your strategy is sector-agnostic.")
                except Exception as _ce:
                    st.caption(f"_Coverage view unavailable ({_ce})_")
            else:
                st.info("No Sector column found in closed trades.")

        with _ap4:
            section("Trade Quality Distribution")
            if 'Quality' in df_closed.columns:
                q_grp = df_closed.groupby('Quality').agg(
                    Count    = ('PnL','count'),
                    Total_PnL= ('PnL','sum'),
                    Avg_PnL  = ('PnL','mean'),
                    Win_Rate = ('PnL', lambda x: (x > 0).sum() / len(x) * 100)
                ).reset_index().sort_values('Avg_PnL', ascending=False)
                q_grp['Total ₹']  = q_grp['Total_PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
                q_grp['Avg ₹']    = q_grp['Avg_PnL'].apply(lambda x:   f"₹{format_inr_int(x)}")
                q_grp['Win Rate'] = q_grp['Win_Rate'].apply(lambda x:   f"{x:.0f}%")
                st.dataframe(q_grp[['Quality','Count','Total ₹','Avg ₹','Win Rate']],
                             use_container_width=True, hide_index=True)
                fig_q = px.bar(q_grp, x='Quality', y='Avg_PnL', color='Avg_PnL',
                                color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
                                labels={'Avg_PnL':'Average P&L per Trade (₹)'})
                fig_q.update_layout(height=260, margin=dict(t=10,l=0,r=0,b=0),
                                     paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                     xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"),
                                     font=dict(color="#E3EBEC"))
                st.plotly_chart(fig_q, use_container_width=True)
            else:
                st.info("No Quality column found. Grade your trades in the Journal to unlock this view.")

            section("Win/Loss Streak Analysis")
            pnls_chron = df_closed.sort_values('ExitDate')['PnL'].values
            if len(pnls_chron) > 0:
                max_win_streak = max_loss_streak = curr_w = curr_l = 0
                for p in pnls_chron:
                    if p > 0:
                        curr_w += 1; curr_l = 0
                        max_win_streak = max(max_win_streak, curr_w)
                    else:
                        curr_l += 1; curr_w = 0
                        max_loss_streak = max(max_loss_streak, curr_l)
                s1, s2 = st.columns(2, gap="small")
                s1.metric("Max Win Streak",  f"{max_win_streak} trades")
                s2.metric("Max Loss Streak", f"{max_loss_streak} trades",
                           delta=f"{'⚠️ Review setups' if max_loss_streak >= 3 else 'Manageable'}",
                           delta_color="off" if max_loss_streak >= 3 else "normal")

        # ── Attribution tab (Phase 0 engine) ───────────────────────────────────
        with _ap5:
            section("Performance Attribution — Realized P&L Decomposition")
            try:
                import performance_attribution as _pa
                _res = _pa.run_attribution()
                _q = _res.get("quality", {})

                # Data-quality / honesty line
                _dq = []
                _dq.append(f"{_q.get('attributable', 0)} attributable / {_q.get('total_closed', 0)} closed")
                if _q.get("cash_excluded"):
                    _dq.append(f"{_q['cash_excluded']} cash-park excluded ({', '.join(_q.get('cash_excluded_symbols', []))})")
                _dropped = {k: v for k, v in _q.get("dropped", {}).items() if v}
                if _dropped:
                    _dq.append("quarantined: " + ", ".join(f"{v} {k.replace('_',' ')}" for k, v in _dropped.items()))
                if _q.get("signal_snapshot_coverage"):
                    _dq.append(_q["signal_snapshot_coverage"])
                if _q.get("provenance_note"):
                    _dq.append(f"{_q.get('system_trades', 0)} SYSTEM / {_q.get('discretionary_trades', 0)} discretionary")
                st.caption("🧪 Data quality — " + "  •  ".join(_dq))

                if not _res.get("ok"):
                    st.info(_res.get("message", "No attributable closed trades yet."))
                else:
                    def _hl_metrics(_h):
                        _pf = "∞" if _h["profit_factor"] == float("inf") else f"{_h['profit_factor']:.2f}"
                        a1, a2, a3 = st.columns(3, gap="small")
                        a1.metric("Trades", str(_h["n_trades"]))
                        a2.metric("Win Rate", f"{_h['win_rate_pct']}%")
                        a3.metric("Total Realized", f"₹{format_inr_int(_h['total_realized'])}")
                        a4, a5, a6 = st.columns(3, gap="small")
                        a4.metric("Expectancy/Trade", f"₹{format_inr_int(_h['expectancy'])}")
                        a5.metric("Profit Factor", _pf)
                        a6.metric("Avg ROI/Trade", f"{_h['avg_roi_pct']}%")

                    # SYSTEM-only = the honest live record (Catalyst/GM+S4-entered). Foreground it.
                    _hs = _res.get("headline_system") or {}
                    section("🎯 System-only (Catalyst/GM+S4-entered — the honest live record)")
                    if _hs.get("n_trades", 0) == 0:
                        st.info("No system-entered trades have CLOSED yet. The live system record "
                                "starts accruing as GM guided-exec entries (recompute snapshot) close. "
                                "The numbers below are discretionary/random/legacy picks — NOT a measure of the system.")
                    else:
                        _hl_metrics(_hs)
                    # ALL + discretionary shown for context, clearly labelled as NOT the system.
                    with st.expander("All attributable (system + discretionary — NOT a system measure)", expanded=(_hs.get("n_trades", 0) == 0)):
                        _hl_metrics(_res["headline"])

                    # Per-dimension tables — lead with provenance, then the entry-signal drivers.
                    _labels = dict(_pa.DIMENSIONS)
                    _order = ["provenance", "setup", "stage_label", "alpha_band", "rs_band", "conv_band",
                              "sector", "trade_type", "hold_bucket", "exit_reason", "trade_quality", "system"]
                    for _col in _order:
                        _t = _res["tables"].get(_col)
                        if _t is None or _t.empty:
                            continue
                        section(f"By {_labels.get(_col, _col)}")
                        _disp = _t[["bucket", "n_trades", "win_rate_pct", "total_pnl",
                                    "expectancy", "profit_factor", "contribution_pct"]].copy()
                        _disp.columns = ["Bucket", "n", "Win %", "Total ₹", "Exp ₹", "PF", "Contrib %"]
                        _disp["Total ₹"] = _disp["Total ₹"].map(lambda v: format_inr_int(v))
                        _disp["Exp ₹"]   = _disp["Exp ₹"].map(lambda v: format_inr_int(v))
                        st.dataframe(_disp, use_container_width=True, hide_index=True)
            except Exception as _ae:
                st.error(f"Attribution failed: {_ae}")

        # ── Export ─────────────────────────────────────────────────────────────
        st.markdown("---")
        section("Export")
        _ex1, _ex2 = st.columns(2, gap="small")
        with _ex1:
            _csv_data = df_closed.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Trade Log (CSV)",
                data=_csv_data,
                file_name=f"Trade_Log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv", use_container_width=True, key="ap_dl_csv",
            )
        with _ex2:
            if _GEMINI_OK:
                if st.button("🤖 Generate + Download AI Review", use_container_width=True, key="ap_ai_dl"):
                    with st.spinner("Generating AI portfolio review…"):
                        try:
                            _ap_analytics = compute_portfolio_analytics(df_closed, total_cap)
                            _ap_review    = generate_portfolio_review(df_closed, _ap_analytics)
                            st.session_state["ap_ai_review"] = _ap_review
                        except Exception as _are:
                            st.error(f"AI review failed: {_are}")
                if st.session_state.get("ap_ai_review"):
                    st.download_button(
                        "📥 Save AI Review (.txt)",
                        data=st.session_state["ap_ai_review"],
                        file_name=f"AI_Trade_Review_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain", use_container_width=True, key="ap_ai_dl2",
                    )
