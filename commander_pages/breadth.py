# commander_pages/breadth.py - the BREADTH page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('breadth', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📈 Market Breadth Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Nifty 500 Internals // A/D Ratio // McClellan // Stage Distribution // Sector Breadth</div>', unsafe_allow_html=True)

    _br0, _br1, _br2, _br3, _br4, _br5 = st.tabs(
        ["🎯 Regime", "🌊 Overview", "📈 Broad Market", "🏭 Sectors", "〰️ McClellan", "🗺️ Stage Map"]
    )

    if not _BREADTH_OK:
        st.error("❌ breadth_engine module not available. Please check installation.")
    else:
        # ── TAB 0 — MARKET REGIME (B3 + B4 + B8 + composite score) ─────────
        with _br0:
            section("Market Regime — Composite Score")
            st.caption(
                "Combines benchmark trend, breadth, distribution-day count, "
                "follow-through, and Zweig breadth thrust. "
                "Use as a top-level filter: at score ≥ 6 swing entries are "
                "supported; ≤ 3 favors defensive posture."
            )
            try:
                import market_regime as _mr
                # Reuse the breadth metrics from elsewhere on the page if available
                with st.spinner("Computing regime (downloads benchmark + breadth)..."):
                    _bm_for_regime = None
                    _ad_for_regime = None
                    try:
                        _bm_for_regime = calculate_breadth_metrics()
                    except Exception:
                        pass
                    try:
                        from breadth_engine import load_or_bootstrap_ad_history as _load_ad
                        _ad_for_regime = _load_ad(min_rows=40)
                    except Exception:
                        _ad_for_regime = None
                    _reg = _mr.compute_regime(_bm_for_regime, _ad_for_regime)

                _verdict_color = (
                    "var(--bull)" if _reg["score"] >= 6 else
                    "var(--warn)" if _reg["score"] >= 4 else
                    "var(--bear)"
                )
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border:1px solid {_verdict_color};
                            border-radius:8px;padding:18px 24px;margin-bottom:20px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;
                              color:var(--ink);letter-spacing:3px;text-transform:uppercase;">Regime Score</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:2.6rem;font-weight:700;
                              color:{_verdict_color};margin:4px 0;">{_reg['score']}/10</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:1.2rem;color:{_verdict_color};">{_reg['verdict']}</div>
                  <div style="font-size:0.68rem;color:var(--ink);margin-top:6px;">
                      {_reg['benchmark']} @ {_reg['close']}  ·  SMA200 {_reg.get('sma200','—')}
                      ({'rising' if _reg.get('sma200_rising') else 'flat/falling'})
                      ·  computed {_reg['computed_at'][:16]}
                  </div>
                </div>""", unsafe_allow_html=True)

                _rcols = st.columns(3, gap="small")
                _dd = _reg["distribution"]
                _ft = _reg["follow_through"]
                _bt = _reg["breadth_thrust"]
                _rcols[0].metric(
                    "Distribution Days (25d)",
                    f"{_dd['count']}",
                    delta="STRESS" if _dd.get("stress") else "ok",
                    delta_color="inverse" if _dd.get("stress") else "normal",
                    help="≥5 in 25 sessions = institutional selling; cap new entries.",
                )
                _rcols[1].metric(
                    "Follow-Through",
                    "ACTIVE" if _ft.get("active") else "—",
                    delta=_ft.get("ft_date", "no signal") if _ft.get("active") else "no signal",
                    help="Bar 4–25 of a rally attempt closing up ≥1.7% on higher volume — O'Neil canonical re-entry signal.",
                )
                _rcols[2].metric(
                    "Breadth Thrust (Zweig)",
                    "ACTIVE" if _bt.get("active") else "—",
                    delta=f"EMA10={_bt.get('current_ema10','—')}",
                    help="EMA10 of A/(A+D) crossed ≤0.40→≥0.615 within 10 bars. Rare; very bullish.",
                )

                with st.expander("📋 Component Breakdown — what each gate measures"):
                    # Per user feedback (10 May 2026): the raw key/✓ table was
                    # cryptic. This version explains each component, the current
                    # reading vs threshold, and the role each plays in the regime
                    # composite score.
                    _comp = _reg.get("components", {})
                    _bm_local = _bm_for_regime if _bm_for_regime else {}
                    _above200_pct = _bm_local.get("above_sma200_pct", 0) if isinstance(_bm_local, dict) else 0
                    _above50_pct  = _bm_local.get("above_sma50_pct",  0) if isinstance(_bm_local, dict) else 0
                    _comp_meta = {
                        "above_sma200_rising": {
                            "label":   "% above SMA200 — Rising",
                            "desc":    "Pct of Nifty 500 trading above their 200-day SMA, AND that pct is improving. Confirms broad participation in any uptrend.",
                            "value":   f"{_above200_pct:.1f}%",
                            "thresh":  "≥ 50% & rising",
                            "weight":  "🟢 Bullish gate",
                        },
                        "breadth_above_50": {
                            "label":   "% above SMA50 — Strong",
                            "desc":    "Pct of Nifty 500 trading above their 50-day SMA. Short-term breadth — confirms recent uptrend strength.",
                            "value":   f"{_above50_pct:.1f}%",
                            "thresh":  "≥ 50%",
                            "weight":  "🟢 Bullish gate",
                        },
                        "dd_low": {
                            "label":   "Distribution Days — Low",
                            "desc":    "Distribution days = down ≥0.2% on higher volume. >5 in last 25 sessions = institutional selling pressure.",
                            "value":   f"{_dd.get('count', 0)} in last {_dd.get('window', 25)} days",
                            "thresh":  "≤ 5 days",
                            "weight":  "🛑 Risk filter (low = good)",
                        },
                        "no_death_cross": {
                            "label":   "No Death Cross",
                            "desc":    "Death cross = SMA50 crossing BELOW SMA200 on the index. Long-term bear signal. We require its absence.",
                            "value":   "Active" if not _comp.get("no_death_cross", True) else "Clear",
                            "thresh":  "Must be clear",
                            "weight":  "🛑 Hard regime gate",
                        },
                        "follow_through": {
                            "label":   "Follow-Through Day",
                            "desc":    "O'Neil canonical re-entry signal: bar 4–25 of a rally attempt closing up ≥1.7% on higher volume than the day before.",
                            "value":   _ft.get("ft_date", "no signal") if _ft.get("active") else "no signal",
                            "thresh":  "Within last 10 days",
                            "weight":  "🟢 Bull confirmation",
                        },
                        "breadth_thrust": {
                            "label":   "Breadth Thrust (Zweig)",
                            "desc":    "EMA10 of A/(A+D) ratio crosses from ≤0.40 to ≥0.615 within 10 bars. Very rare; historically the strongest broad-market reversal signal.",
                            "value":   f"EMA10 = {_bt.get('current_ema10', '—')}",
                            "thresh":  "Triggered ≤ 10 days ago",
                            "weight":  "🟢 Strong bull confirmation",
                        },
                    }
                    _comp_rows = []
                    for k, active in _comp.items():
                        meta = _comp_meta.get(k, {})
                        _comp_rows.append({
                            "Status":      "✅ Active" if active else "❌ Not Met",
                            "Component":   meta.get("label", k),
                            "Current":     meta.get("value", "—"),
                            "Required":    meta.get("thresh", "—"),
                            "Role":        meta.get("weight", "—"),
                            "Description": meta.get("desc", ""),
                        })
                    st.dataframe(
                        pd.DataFrame(_comp_rows),
                        hide_index=True, use_container_width=True,
                        column_config={
                            "Description": st.column_config.TextColumn(width="large"),
                        },
                    )
                    st.caption(f"**Distribution Day details:** {_dd.get('details','')}")
                    st.caption(f"**Follow-Through details:** {_ft.get('details','')}")
                    st.caption(f"**Breadth Thrust details:** {_bt.get('details','')}")

                if _dd.get("stress"):
                    st.warning(
                        f"⚠️ **Distribution stress detected** — {_dd['count']} distribution "
                        f"day(s) in last {_dd['window']} sessions "
                        f"(dates: {', '.join(_dd['dates'][-5:])}). "
                        "Consider pausing new positional entries until count drops."
                    )
                if _ft.get("active"):
                    st.success(
                        f"✅ **Follow-through day on {_ft['ft_date']}** "
                        f"(+{_ft['ft_gain_pct']}%, {_ft['days_since_ft']}d ago). "
                        "Re-entry green light per IBD methodology."
                    )
            except Exception as _mre:
                st.error(f"market_regime unavailable: {_mre}")

        with _br1:
            section("Breadth Overview — Nifty 500 Universe")
            with st.spinner("Calculating breadth metrics (may take 30–60s first run)..."):
                try:
                    _bm = calculate_breadth_metrics()
                except Exception as _be:
                    _bm = {}; st.error(f"Breadth calculation error: {_be}")

            if _bm:
                _regime_s = build_breadth_regime(_bm)
                _r_col = "var(--bull)" if "BULL" in _regime_s else "var(--bear)" if "BEAR" in _regime_s else "var(--warn)"
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border:1px solid {_r_col};border-radius:8px;
                            padding:16px 24px;margin-bottom:20px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:var(--ink);letter-spacing:3px;text-transform:uppercase;">Breadth Regime</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:2rem;font-weight:700;color:{_r_col};margin:4px 0;">{_regime_s}</div>
                  <div style="font-size:0.68rem;color:var(--ink);">{_bm.get("symbols_analyzed",0)} stocks analyzed | Updated: {_bm.get("calculated_at","")}</div>
                </div>""", unsafe_allow_html=True)

                _g1,_g2,_g3,_g4 = st.columns(4, gap="small")
                _g1.metric("Above SMA 50",  f"{_bm.get('above_sma50_pct',0):.1f}%",
                           help="% of Nifty 500 stocks above their 50-day moving average")
                _g2.metric("Above SMA 150", f"{_bm.get('above_sma150_pct',0):.1f}%",
                           help="% above 150-day MA — intermediate trend health")
                _g3.metric("Above SMA 200", f"{_bm.get('above_sma200_pct',0):.1f}%",
                           help="% above 200-day MA — long-term breadth")
                _g4.metric("Stage 2",       f"{_bm.get('stage2_pct',0):.1f}%",
                           help="% in confirmed Stage 2 (price > SMA150, SMA150 sloping up [30-Week MA])")

                _g5,_g6,_g7,_g8 = st.columns(4, gap="small")
                _g5.metric("New 52W Highs", str(_bm.get("new_52w_high_count",0)))
                _g6.metric("New 52W Lows",  str(_bm.get("new_52w_low_count",0)))
                _g7.metric("A/D Ratio",     f"{_bm.get('ad_ratio',0):.2f}",
                           help=">2.0 = Bullish thrust | <0.5 = Bearish pressure")
                _g8.metric("High/Low Ratio",f"{_bm.get('high_low_ratio',0):.2f}",
                           help=">0.7 = Healthy | <0.3 = Weak")

                _sma_data = {
                    "SMA 50":  _bm.get("above_sma50_pct",0),
                    "SMA 150": _bm.get("above_sma150_pct",0),
                    "SMA 200": _bm.get("above_sma200_pct",0),
                    "Stage 2": _bm.get("stage2_pct",0),
                }
                _fig_bar = go.Figure(go.Bar(
                    x=list(_sma_data.keys()), y=list(_sma_data.values()),
                    marker_color=["#15803D" if v>50 else "#B45309" if v>30 else "#DC2626"
                                  for v in _sma_data.values()],
                    text=[f"{v:.1f}%" for v in _sma_data.values()], textposition="auto"
                ))
                _fig_bar.add_hline(y=50, line_dash="dot", line_color="#B6C4C6", line_width=1,
                                   annotation_text="50% neutral line")
                _fig_bar.update_layout(
                    height=260, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0",range=[0,100]),
                    font=dict(color="#E3EBEC"), title_text="% Stocks Above Key Moving Averages"
                )
                st.plotly_chart(_fig_bar, use_container_width=True)
        with _br2:
            with st.spinner("Fetching broad market data..."):
                try:
                    _bm_df = get_broad_market_breadth()
                except Exception as _e:
                    _bm_df = pd.DataFrame(); st.error(str(_e))

            if not _bm_df.empty:
                def _stage_icon(s):
                    return "🟢" if "Stage 2" in str(s) else "🔴" if "Stage 4" in str(s) else "🟡"

                _bm_disp = _bm_df.copy()
                if "Stage" in _bm_disp.columns:
                    _bm_disp[""] = _bm_disp["Stage"].apply(_stage_icon)

                _total_n  = len(_bm_disp)
                section(f"Broad Market Indices — {_total_n} indices")

                # Reorder columns: Stage icon first, then key numbers including Daily%
                _col_order = ["", "Sector", "LTP", "Daily%", "Weekly%", "Monthly%",
                               "Stage", "SMA150D_slope"]
                _col_order = [c for c in _col_order if c in _bm_disp.columns]
                st.dataframe(_bm_disp[_col_order], use_container_width=True, hide_index=True,
                             height=min(40 + 35 * _total_n, 600))

                # ── Timeframe selector ────────────────────────────────────────
                _avail_periods = [c for c in ["Daily%","Weekly%","Monthly%"]
                                  if c in _bm_disp.columns]
                _bm_c1, _bm_c2 = st.columns([1, 5])
                with _bm_c1:
                    _bm_period = st.selectbox(
                        "Chart period", _avail_periods,
                        index=len(_avail_periods) - 1,   # default Monthly%
                        key="br_bm_period",
                    )
                _y_vals = _bm_disp[_bm_period] if _bm_period in _bm_disp.columns else []
                _x_vals = (_bm_disp["Sector"] if "Sector" in _bm_disp.columns else [])
                if len(_y_vals):
                    _fig_bm = go.Figure(go.Bar(
                        x=_x_vals, y=_y_vals,
                        marker_color=["#15803D" if v >= 0 else "#DC2626" for v in _y_vals],
                        text=[f"{v:+.1f}%" for v in _y_vals], textposition="auto"
                    ))
                    _fig_bm.update_layout(
                        height=280, margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#E2E8F0", tickangle=-30),
                        yaxis=dict(gridcolor="#E2E8F0"),
                    )
                    st.plotly_chart(_fig_bm, use_container_width=True)

        with _br3:
            with st.spinner("Fetching sector data..."):
                try:
                    _sec_df = get_sector_breadth()
                except Exception as _e:
                    _sec_df = pd.DataFrame(); st.error(str(_e))

            if not _sec_df.empty:
                def _stage_icon(s):
                    return "🟢" if "Stage 2" in str(s) else "🔴" if "Stage 4" in str(s) else "🟡"

                _sec_disp = _sec_df.copy()
                if "Stage" in _sec_disp.columns:
                    _sec_disp[""] = _sec_disp["Stage"].apply(_stage_icon)

                # P1.3 (10 May 2026): sort by Stage priority (2 → 1 → 4 → 3) so Stage 2
                # sectors — your hunting grounds — float to the top. Within same stage,
                # tiebreak by Monthly% descending. Per user feedback (#8): "Expand
                # Sector count and sort them with Stage 2 on top".
                if "Stage" in _sec_disp.columns:
                    def _stage_priority(s):
                        s_str = str(s)
                        if "Stage 2" in s_str: return 0
                        if "Stage 1" in s_str: return 1
                        if "Stage 4" in s_str: return 2
                        if "Stage 3" in s_str: return 3
                        return 4
                    _sec_disp["_sp"] = _sec_disp["Stage"].apply(_stage_priority)
                    _sort_cols = ["_sp"]
                    if "Monthly%" in _sec_disp.columns:
                        _sort_cols.append("Monthly%")
                    _sec_disp = _sec_disp.sort_values(_sort_cols, ascending=[True] + [False]*(len(_sort_cols)-1)).drop(columns=["_sp"])

                # Section header with counts so trader sees at a glance how many
                # sectors are in each stage — drives macro-state read in 1 second.
                _stage2_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 2")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage1_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 1")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage4_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 4")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage3_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 3")).sum()) if "Stage" in _sec_disp.columns else 0
                _total_n  = len(_sec_disp)
                section(f"Sector Breadth — {_total_n} sectors  ·  🟢 Stage 2: {_stage2_n}  ·  🟡 Stage 1: {_stage1_n}  ·  🔴 Stage 4: {_stage4_n}  ·  🟡 Stage 3: {_stage3_n}")

                # Reorder columns: Stage icon first, then key numbers including Daily%
                _col_order = ["", "Sector", "LTP", "Daily%", "Weekly%", "Monthly%",
                               "Stage", "SMA150D_slope"]
                _col_order = [c for c in _col_order if c in _sec_disp.columns]
                st.dataframe(_sec_disp[_col_order], use_container_width=True, hide_index=True,
                             height=min(40 + 35 * _total_n, 600))

                # ── Timeframe selector ────────────────────────────────────────
                _avail_periods = [c for c in ["Daily%","Weekly%","Monthly%"]
                                  if c in _sec_disp.columns]
                _br_c1, _br_c2 = st.columns([1, 5])
                with _br_c1:
                    _sec_period = st.selectbox(
                        "Chart period", _avail_periods,
                        index=len(_avail_periods) - 1,   # default Monthly%
                        key="br_sec_period",
                    )
                _y_vals = _sec_disp[_sec_period] if _sec_period in _sec_disp.columns else []
                _x_vals = (_sec_disp["Sector"].str.replace("Nifty ", "")
                           if "Sector" in _sec_disp.columns else [])
                if len(_y_vals):
                    _fig_sec = go.Figure(go.Bar(
                        x=_x_vals, y=_y_vals,
                        marker_color=["#15803D" if v >= 0 else "#DC2626" for v in _y_vals],
                        text=[f"{v:+.1f}%" for v in _y_vals], textposition="auto"
                    ))
                    _fig_sec.update_layout(
                        height=280, margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#E2E8F0", tickangle=-30),
                        yaxis=dict(gridcolor="#E2E8F0"),
                        font=dict(color="#E3EBEC"),
                        title_text=f"{_sec_period} Change by Sector",
                    )
                    st.plotly_chart(_fig_sec, use_container_width=True)
            else:
                st.info("Sector breadth data unavailable.")

        with _br4:
            section("McClellan Oscillator")
            st.caption("Bootstraps 60 days of A/D history from yfinance on first run (~60–90s). "
                       "Subsequent runs load from cache. History grows daily via the scheduler.")

            # 10 May 2026: surface the last-persisted date so the user knows
            # whether the displayed Summation Index is fresh or weeks old.
            # Previously the metric showed +3078 with no date — that value was
            # from April 17 but looked current.
            try:
                import json as _json_mc
                if os.path.exists("mcclellan_state.json"):
                    with open("mcclellan_state.json") as _mcfh:
                        _mc_state = _json_mc.load(_mcfh)
                    _last_d = _mc_state.get("last_date", "?")
                    _last_msi = _mc_state.get("msi", 0)
                    import datetime as _dt_mc
                    try:
                        _last_dt = _dt_mc.datetime.strptime(_last_d, "%Y-%m-%d")
                        _age_days = (_dt_mc.datetime.now() - _last_dt).days
                        if _age_days > 7:
                            st.warning(f"⚠ Last calculated **{_last_d}** "
                                       f"({_age_days}d ago, MSI={_last_msi:+.0f}). "
                                       f"Click below to refresh — Summation Index "
                                       f"is currently a stale snapshot.")
                        else:
                            st.caption(f"Last calculated: **{_last_d}** "
                                       f"({_age_days}d ago, MSI={_last_msi:+.0f})")
                    except Exception:
                        st.caption(f"Last persisted state: {_last_d}, MSI={_last_msi:+.0f}")
            except Exception:
                pass

            if st.button("📊 Compute McClellan Oscillator", key="br_mcl_btn", type="primary"):
                with st.spinner("Loading A/D history — first run downloads 60 days of data for Nifty 500…"):
                    try:
                        from breadth_engine import (
                            load_or_bootstrap_ad_history, calculate_mcclellan,
                            calculate_breadth_thrust,
                        )
                        # force=True bypasses the on-disk cache so a manual
                        # click always refetches today's A/D. Without this the
                        # MSI state file's last_date never advances and the
                        # "Last calculated" banner stays frozen.
                        _ad_df = load_or_bootstrap_ad_history(min_rows=40, force=True)
                    except Exception as _mcl_e:
                        _ad_df = pd.DataFrame()
                        st.error(f"A/D history load failed: {_mcl_e}")

                if _ad_df.empty or len(_ad_df) < 10:
                    st.warning("Insufficient A/D history. Need at least 10 days — "
                               "run the breadth job daily to accumulate data.")
                else:
                    _mcl  = calculate_mcclellan(_ad_df)
                    _thr  = calculate_breadth_thrust(_ad_df)
                    _osc  = _mcl.get("oscillator", 0)
                    _sum  = _mcl.get("summation", 0)
                    _sig  = _mcl.get("signal", "UNAVAILABLE")
                    _tval = _thr.get("current_value", 0)
                    _rows = len(_ad_df)

                    # Signal colours
                    _osc_col = "var(--bull)" if _osc > 0 else "var(--bear)"
                    _sig_col = "var(--bull)" if "OVERSOLD" in _sig else "var(--bear)" if "OVERBOUGHT" in _sig else "var(--warn)"

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("McClellan Oscillator", f"{_osc:+.1f}",
                               help="EMA19 − EMA39 of daily net advances. >0 = breadth expanding")
                    mc2.metric("Summation Index",     f"{_sum:+.0f}",
                               help="Cumulative McClellan. >0 = long-term breadth bullish")
                    mc3.metric("Signal",              _sig,
                               help=">100 overbought | <-100 oversold")
                    mc4.metric("Breadth Thrust EMA10",f"{_tval:.3f}",
                               delta="ACTIVE" if _thr.get("thrust_active") else "No thrust",
                               delta_color="normal" if _thr.get("thrust_active") else "off",
                               help="Zweig Thrust — reading >0.615 within 10 days = rare bullish signal")

                    st.markdown("---")
                    # Oscillator history chart
                    if "net_advances" not in _ad_df.columns:
                        _ad_df = _ad_df.copy()
                        _ad_df["net_advances"] = _ad_df["advance_count"] - _ad_df["decline_count"]
                    _ad_df["ema19"] = _ad_df["net_advances"].ewm(span=19, adjust=False).mean()
                    _ad_df["ema39"] = _ad_df["net_advances"].ewm(span=39, adjust=False).mean()
                    _ad_df["mco"]   = _ad_df["ema19"] - _ad_df["ema39"]

                    _fig_mcl = go.Figure()
                    _fig_mcl.add_bar(
                        x=_ad_df["date"], y=_ad_df["mco"],
                        marker_color=[("#15803D" if v >= 0 else "#DC2626") for v in _ad_df["mco"]],
                        name="McClellan Oscillator",
                    )
                    _fig_mcl.add_hline(y=100,  line_dash="dot", line_color="#E9857C", line_width=1,
                                       annotation_text="Overbought +100")
                    _fig_mcl.add_hline(y=-100, line_dash="dot", line_color="#45BE92", line_width=1,
                                       annotation_text="Oversold -100")
                    _fig_mcl.add_hline(y=0,    line_dash="solid", line_color="#B6C4C6", line_width=1)
                    _fig_mcl.update_layout(
                        height=300, margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"),
                        font=dict(color="#E3EBEC"),
                        title_text=f"McClellan Oscillator — {_rows} days of A/D history",
                    )
                    st.plotly_chart(_fig_mcl, use_container_width=True)
                    st.caption(f"A/D history: {_rows} trading days | "
                               f"Data stored at reports/ad_history.json")

        with _br5:
            section("Stage Distribution — Nifty 500")
            with st.spinner("Loading stage data..."):
                try:
                    _bm2 = calculate_breadth_metrics()
                except Exception:
                    _bm2 = {}

            if _bm2:
                _total = _bm2.get("symbols_analyzed", 1)
                _s2_pct = _bm2.get("stage2_pct", 0)
                _above200 = _bm2.get("above_sma200_pct", 0)
                _below200 = 100 - _above200

                _stage_data = {
                    "Stage 2 (Advance)": _s2_pct,
                    "Stage 1/3 (Base/Top)": max(0, _above200 - _s2_pct),
                    "Stage 4 (Decline)": _below200,
                }
                # Stage Map donut — % labels in dark text for readability against
                # the bright green/yellow/red wedges (user feedback 10 May 2026:
                # white text was hard to read on the light wedge fills).
                _fig_pie = go.Figure(go.Pie(
                    labels=list(_stage_data.keys()),
                    values=list(_stage_data.values()),
                    hole=0.5,
                    marker_colors=["#15803D","#B45309","#DC2626"],
                    textfont=dict(size=14, color="#0a0e14"),  # dark text on wedge
                    textposition="inside",
                    insidetextorientation="horizontal",
                    texttemplate="<b>%{percent}</b>",
                ))
                _fig_pie.update_layout(
                    height=320, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(font=dict(size=11,color="#E3EBEC"),bgcolor="rgba(0,0,0,0)"),
                    annotations=[dict(text=f"S2: {_s2_pct:.0f}%",
                                      x=0.5, y=0.5, font_size=20,
                                      font_color="#45BE92", showarrow=False)]
                )
                st.plotly_chart(_fig_pie, use_container_width=True)
                st.caption("Stage 2 > 35% = Confirmed Bull Market. Stage 2 < 20% = Bear Market.")
