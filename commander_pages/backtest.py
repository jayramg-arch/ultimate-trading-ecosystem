# commander_pages/backtest.py - the BACKTEST page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('backtest', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📈 Signal Backtest Lab</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-desc">Forward-return analysis of Recovery Screener signals — '
        'measures actual price outcomes at 10/21/30/60-day horizons via yfinance</div>',
        unsafe_allow_html=True,
    )

    # ── Signal source ─────────────────────────────────────────────────────────
    _REC_CSV = os.path.join(_APP_DIR, "Recovery_Screener_Results.csv")
    section("Signal Source")
    src_mode = st.radio(
        "Source",
        ["Current Recovery_Screener_Results.csv", "Upload historical signals CSV"],
        horizontal=True, label_visibility="collapsed",
    )

    df_src = None
    if src_mode == "Current Recovery_Screener_Results.csv":
        if os.path.exists(_REC_CSV):
            try:
                df_src = pd.read_csv(_REC_CSV)
                st.caption(f"Loaded **{len(df_src)} rows** from Recovery_Screener_Results.csv")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
        else:
            st.warning(
                "⚠️  Recovery_Screener_Results.csv not found in the app directory.  "
                "Run the Recovery Screener at least once, or upload a historical CSV."
            )
    else:
        up_file = st.file_uploader(
            "Upload signal CSV (required columns: Symbol, Signal_Date — optionally Edge)",
            type="csv", key="bt_upload",
        )
        if up_file:
            try:
                df_src = pd.read_csv(up_file)
                st.caption(f"Uploaded: **{len(df_src)} rows**")
            except Exception as e:
                st.error(f"Error reading uploaded CSV: {e}")

    if df_src is not None and not df_src.empty:
        # ── Parse Signal_Date ─────────────────────────────────────────────────
        if "Signal_Date" in df_src.columns:
            df_src["Signal_Date"] = pd.to_datetime(df_src["Signal_Date"], errors="coerce")
        else:
            df_src["Signal_Date"] = pd.NaT

        df_valid = df_src.dropna(subset=["Signal_Date"]).copy()

        if df_valid.empty:
            st.info(
                "No rows with a valid Signal_Date found.  "
                "The CSV must have a Signal_Date column in YYYY-MM-DD format."
            )
        else:
            # ── Configuration ─────────────────────────────────────────────────
            section("Backtest Configuration")
            bc1, bc2, bc3 = st.columns(3, gap="small")
            hold_days = bc1.selectbox(
                "Holding Period (days)", [10, 21, 30, 45, 60], index=1,
                help="Calendar days from signal date to measure the exit return",
            )

            edge_choices = sorted(df_valid["Edge"].dropna().unique().tolist()) if "Edge" in df_valid.columns else []
            edge_filter = bc2.multiselect(
                "Edge Filter", edge_choices,
                default=[], placeholder="All edges",
            )

            earliest = (datetime.today() - timedelta(days=365)).date()
            min_date = bc3.date_input(
                "Earliest signal date",
                value=max(df_valid["Signal_Date"].min().date(), earliest),
                help="Exclude signals older than this date",
            )

            today = pd.Timestamp(datetime.today().date())
            cutoff = today - pd.Timedelta(days=hold_days)

            df_bt = df_valid[df_valid["Signal_Date"] >= pd.Timestamp(min_date)].copy()
            df_bt = df_bt[df_bt["Signal_Date"] <= cutoff].copy()
            if edge_filter:
                df_bt = df_bt[df_bt["Edge"].isin(edge_filter)]

            st.caption(
                f"**{len(df_bt)} signals** eligible for {hold_days}d backtest  "
                f"(signal date between {min_date} and "
                f"{cutoff.strftime('%Y-%m-%d')})"
            )

            if len(df_bt) == 0:
                st.warning(
                    "No eligible signals found.  "
                    "Try lowering 'Earliest signal date' or reducing the holding period."
                )
            else:
                if st.button("▶  Run Backtest", type="primary", key="run_bt"):
                    # Inline cache — 24h TTL since historical data does not change
                    @st.cache_data(ttl=86400, show_spinner=False)
                    def _fetch_bt_return(symbol: str, sig_date_str: str, hold_d: int) -> "float | None":
                        """Fetch entry price at signal date and exit price at hold_d calendar days later."""
                        try:
                            sig_dt  = pd.to_datetime(sig_date_str)
                            end_buf = min(
                                sig_dt + pd.Timedelta(days=hold_d + 20),
                                pd.Timestamp.today() + pd.Timedelta(days=1),
                            )
                            import data_provider as dp
                            df_px = dp.fetch_ohlcv(
                                symbol,
                                start_date=sig_dt.strftime("%Y-%m-%d"),
                                end_date=end_buf.strftime("%Y-%m-%d"),
                                interval="1d", auto_adjust=True, use_cache=True,
                            )
                            if df_px.empty or len(df_px) < 2:
                                return None
                            entry = float(df_px["Close"].iloc[0])
                            # Exit: closest trading session to (signal_date + hold_d calendar days)
                            exit_target = sig_dt + pd.Timedelta(days=hold_d)
                            exit_idx = df_px.index.searchsorted(exit_target)
                            exit_idx = min(exit_idx, len(df_px) - 1)
                            exit_p = float(df_px["Close"].iloc[exit_idx])
                            return round((exit_p - entry) / entry * 100, 2) if entry > 0 else None
                        except Exception:
                            return None

                    prog = st.progress(0, text="Fetching price data from yfinance ...")
                    returns = []
                    n = len(df_bt)
                    import time as _t
                    for i, (_, row) in enumerate(df_bt.iterrows()):
                        sym   = str(row.get("Symbol", "")).strip().upper()
                        sdate = row["Signal_Date"].strftime("%Y-%m-%d")
                        ret   = _fetch_bt_return(sym, sdate, hold_days)
                        returns.append(ret)
                        prog.progress((i + 1) / n, text=f"Fetching {sym}  [{i+1}/{n}]")
                        _t.sleep(0.15)
                    prog.empty()

                    df_bt_result = df_bt.copy()
                    df_bt_result["Return_%"] = returns
                    st.session_state["_bt_results"] = df_bt_result
                    st.session_state["_bt_hold"]    = hold_days
                    st.rerun()

                # ── Display results ───────────────────────────────────────────
                if (
                    "_bt_results" in st.session_state
                    and st.session_state.get("_bt_hold") == hold_days
                ):
                    df_res  = st.session_state["_bt_results"]
                    df_done = df_res.dropna(subset=["Return_%"]).copy()

                    if df_done.empty:
                        st.warning(
                            "No return data fetched.  "
                            "Check symbol names, signal dates, and internet connection."
                        )
                    else:
                        hold_used = st.session_state["_bt_hold"]
                        section(f"Results — {hold_used}-day Hold  ({len(df_done)} signals)")

                        rets = df_done["Return_%"]
                        r1, r2, r3, r4, r5 = st.columns(5, gap="small")
                        r1.metric("Win Rate",      f"{(rets > 0).mean() * 100:.0f}%")
                        r2.metric("Avg Return",    f"{rets.mean():.1f}%",
                                   delta="▲" if rets.mean() > 0 else "▼", delta_color="off")
                        r3.metric("Median Return", f"{rets.median():.1f}%")
                        r4.metric("Best Signal",   f"{rets.max():.1f}%")
                        r5.metric("Worst Signal",  f"{rets.min():.1f}%")

                        # ── By edge breakdown ─────────────────────────────────
                        if "Edge" in df_done.columns and df_done["Edge"].notna().any():
                            section("By Edge Type")
                            edge_grp = (
                                df_done.groupby("Edge")["Return_%"]
                                .agg(
                                    Count="count",
                                    Win_Rate=lambda x: f"{(x > 0).mean() * 100:.0f}%",
                                    Avg_Return=lambda x: f"{x.mean():.1f}%",
                                    Median=lambda x: f"{x.median():.1f}%",
                                    Best=lambda x: f"{x.max():.1f}%",
                                )
                                .reset_index()
                            )
                            st.dataframe(edge_grp, use_container_width=True, hide_index=True)

                        # ── Distribution histogram ────────────────────────────
                        section("Return Distribution")
                        fig_hist = px.histogram(
                            df_done, x="Return_%", nbins=30,
                            color_discrete_sequence=["#1D4ED8"],
                            labels={"Return_%": f"Return % at {hold_used}d"},
                        )
                        fig_hist.add_vline(x=0, line_dash="dash", line_color="#E9857C", line_width=1)
                        fig_hist.add_vline(
                            x=float(rets.mean()), line_dash="dot", line_color="#45BE92",
                            line_width=1,
                            annotation_text=f"Mean {rets.mean():.1f}%",
                            annotation_font_color="#45BE92",
                        )
                        fig_hist.update_layout(
                            height=260, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(title=f"Return % ({hold_used}d)", gridcolor="#E2E8F0"),
                            yaxis=dict(title="Signal Count", gridcolor="#E2E8F0"),
                            font=dict(color="#E3EBEC"),
                        )
                        st.plotly_chart(fig_hist, use_container_width=True)

                        # ── Scatter: return vs signal age ─────────────────────
                        if "Age_Days" in df_done.columns and df_done["Age_Days"].notna().any():
                            section("Return vs Signal Age at Entry")
                            fig_sc = px.scatter(
                                df_done, x="Age_Days", y="Return_%",
                                color="Edge" if "Edge" in df_done.columns else None,
                                hover_data=["Symbol"],
                                labels={"Age_Days": "Signal Age (days)",
                                        "Return_%": f"Return % at {hold_used}d"},
                                color_discrete_sequence=px.colors.qualitative.Set2,
                            )
                            fig_sc.add_hline(y=0, line_dash="dash", line_color="#E9857C", line_width=1)
                            fig_sc.update_layout(
                                height=260, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(gridcolor="#E2E8F0"),
                                yaxis=dict(gridcolor="#E2E8F0"),
                                font=dict(color="#E3EBEC"),
                            )
                            st.plotly_chart(fig_sc, use_container_width=True)

                        # ── Signal equity curve (sorted by signal date) ───────
                        section("Cumulative Average Return (by Signal Date)")
                        df_ec = df_done.sort_values("Signal_Date").copy()
                        df_ec["Cum_Avg"] = df_ec["Return_%"].expanding().mean()
                        fig_ec = px.line(
                            df_ec, x="Signal_Date", y="Cum_Avg",
                            labels={"Signal_Date": "Signal Date",
                                    "Cum_Avg": "Cumulative Avg Return %"},
                            color_discrete_sequence=["#15803D"],
                        )
                        fig_ec.add_hline(y=0, line_dash="dash", line_color="#E9857C", line_width=1)
                        fig_ec.update_layout(
                            height=240, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(gridcolor="#E2E8F0"),
                            yaxis=dict(gridcolor="#E2E8F0"),
                            font=dict(color="#E3EBEC"),
                        )
                        st.plotly_chart(fig_ec, use_container_width=True)

                        # ── Full trade log ────────────────────────────────────
                        section("Signal Backtest Log")
                        log_cols = ["Symbol", "Signal_Date", "Return_%"]
                        if "Edge" in df_done.columns:
                            log_cols.insert(1, "Edge")
                        if "Age_Days" in df_done.columns:
                            log_cols.append("Age_Days")
                        df_log = df_done[log_cols].copy()
                        df_log["Signal_Date"] = df_log["Signal_Date"].dt.strftime("%Y-%m-%d")
                        df_log["Result"] = df_log["Return_%"].apply(
                            lambda x: f"{'▲ WIN' if x >= 0 else '▼ LOSS'}  {abs(x):.1f}%"
                        )
                        st.dataframe(
                            df_log.sort_values("Return_%", ascending=False).drop(columns=["Return_%"]),
                            use_container_width=True, hide_index=True,
                        )

                        # Download
                        csv_out = df_done.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "⬇️  Download Backtest Results CSV",
                            data=csv_out,
                            file_name=f"Backtest_{hold_used}d_{datetime.today().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )
