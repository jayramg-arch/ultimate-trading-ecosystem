# commander_pages/tv_sidecar.py - the TV SIDECAR page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('tv_sidecar', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📺 TV Sidecar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Quick-look companion for your TradingView chart — real-time quote, technicals, key levels</div>', unsafe_allow_html=True)

    @st.fragment(run_every="2s")
    def auto_sync_tv_symbol():
        import subprocess
        import csv
        import re
        from io import StringIO
        
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'], capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ["NIFTY 50", "NIFTY"]: sym = "^NSEI"
                                elif sym.upper() in ["NIFTY BANK", "BANKNIFTY"]: sym = "^NSEBANK"
                                elif sym.upper() == "NIFTY 500": sym = "^CRSLDX"
                                else:
                                    if not sym.endswith(".NS") and "^" not in sym and "=" not in sym: sym += ".NS"
                                
                                current_sym = st.session_state.get("tv_sym_input", "")
                                if sym != current_sym:
                                    # DEBOUNCE (2026-07-03): same 2-poll stability rule as the
                                    # Golden Matcher pane — no fetch bursts while scrolling the
                                    # TV watchlist.
                                    if sym == st.session_state.get("tv_pend_sym"):
                                        st.session_state["tv_pend_count"] = st.session_state.get("tv_pend_count", 0) + 1
                                    else:
                                        st.session_state["tv_pend_sym"] = sym
                                        st.session_state["tv_pend_count"] = 1
                                    if st.session_state["tv_pend_count"] >= 2:
                                        st.session_state["tv_pend_sym"] = None
                                        st.session_state["tv_pend_count"] = 0
                                        st.session_state["tv_sym_input"] = sym
                                        st.session_state["tv_symbol"] = sym
                                        st.rerun()
                                else:
                                    st.session_state["tv_pend_sym"] = None
                                    st.session_state["tv_pend_count"] = 0
                                return
            except Exception:
                pass

    _tv_col1, _tv_col2 = st.columns([2, 4])
    with _tv_col1:
        auto_sync = st.toggle("🔄 Auto-Sync TV", value=True, key="tv_auto_sync", help="Automatically sync with active TradingView chart")
        if auto_sync:
            auto_sync_tv_symbol()
        
        if "tv_sym_input" not in st.session_state:
            st.session_state["tv_sym_input"] = st.session_state.get("tv_symbol", "RELIANCE.NS")
            
        _tv_sym = st.text_input(
            "Symbol", 
            key="tv_sym_input", placeholder="e.g. INFY.NS, NIFTY=F"
        ).strip().upper()
        if _tv_sym and not _tv_sym.endswith(".NS") and "=" not in _tv_sym and "^" not in _tv_sym:
            _tv_sym += ".NS"
        if _tv_sym:
            st.session_state["tv_symbol"] = _tv_sym
    with _tv_col2:
        _tv_tf = st.selectbox("Timeframe context", ["Daily", "Weekly", "15min", "60min"], key="tv_tf")

    if _tv_sym:
        with st.spinner(f"Fetching {_tv_sym}..."):
            try:
                import yfinance as _yf2
                _tv_ticker = _yf2.Ticker(_tv_sym)
                _tv_info   = _tv_ticker.info
                _tv_hist   = _tv_ticker.history(period="6mo", interval="1d", auto_adjust=True)
            except Exception as _tve:
                _tv_info, _tv_hist = {}, pd.DataFrame()
                st.error(f"Fetch failed: {_tve}")

        if _tv_info:
            # ── Quote strip ──────────────────────────────────────────────────
            _tv_price  = _tv_info.get("currentPrice") or _tv_info.get("regularMarketPrice") or 0
            _tv_prev   = _tv_info.get("previousClose") or 0
            _tv_chg    = ((_tv_price / _tv_prev) - 1) * 100 if _tv_prev > 0 else 0
            _tv_hi52   = _tv_info.get("fiftyTwoWeekHigh") or 0
            _tv_lo52   = _tv_info.get("fiftyTwoWeekLow") or 0
            _tv_vol    = _tv_info.get("volume") or 0
            _tv_avol   = _tv_info.get("averageVolume") or 1

            _tvc = st.columns(6)
            _tvc[0].metric("LTP",        f"₹{_tv_price:,.2f}", delta=f"{_tv_chg:+.2f}%",
                           delta_color="normal" if _tv_chg >= 0 else "inverse")
            _tvc[1].metric("Prev Close", f"₹{_tv_prev:,.2f}")
            _tvc[2].metric("52W High",   f"₹{_tv_hi52:,.2f}")
            _tvc[3].metric("52W Low",    f"₹{_tv_lo52:,.2f}")
            _tvc[4].metric("Volume",     f"{_tv_vol:,}")
            _tvc[5].metric("Vol/Avg",    f"{_tv_vol/_tv_avol:.2f}x" if _tv_avol > 0 else "N/A",
                           delta="above avg" if _tv_vol > _tv_avol else "below avg",
                           delta_color="normal" if _tv_vol > _tv_avol else "off")

        if not _tv_hist.empty:
            st.markdown("---")
            # ── Key technical levels ─────────────────────────────────────────
            section("Key Technical Levels")
            _tv_c = _tv_hist["Close"]
            _tv_sma20  = float(_tv_c.rolling(20).mean().iloc[-1])
            _tv_sma50  = float(_tv_c.rolling(50).mean().iloc[-1])
            _tv_sma200 = float(_tv_c.rolling(min(200, len(_tv_c))).mean().iloc[-1])
            _tv_hi10   = float(_tv_hist["High"].rolling(10).max().iloc[-1])
            _tv_lo10   = float(_tv_hist["Low"].rolling(10).min().iloc[-1])
            _tv_atr14  = float(
                pd.concat([
                    (_tv_hist["High"] - _tv_hist["Low"]),
                    (_tv_hist["High"] - _tv_hist["Close"].shift()).abs(),
                    (_tv_hist["Low"]  - _tv_hist["Close"].shift()).abs(),
                ], axis=1).max(axis=1).rolling(14).mean().iloc[-1]
            ) if len(_tv_hist) >= 14 else 0.0

            _lv_col1, _lv_col2 = st.columns(2)
            with _lv_col1:
                for _lbl, _val, _above in [
                    ("SMA 20",   _tv_sma20,  _tv_price > _tv_sma20),
                    ("SMA 50",   _tv_sma50,  _tv_price > _tv_sma50),
                    ("SMA 200",  _tv_sma200, _tv_price > _tv_sma200),
                ]:
                    _ic = "🟢" if _above else "🔴"
                    _di = f"{((_tv_price/_val)-1)*100:+.1f}%" if _val > 0 else ""
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid var(--rule);display:flex;gap:8px;font-size:0.82rem">'
                        f'<span>{_ic}</span>'
                        f'<span style="flex:1;color:var(--ink)">{_lbl}</span>'
                        f'<span style="color:var(--acc)">₹{_val:,.2f}</span>'
                        f'<span style="color:var(--muted);margin-left:8px">{_di}</span>'
                        f'</div>', unsafe_allow_html=True
                    )
            with _lv_col2:
                for _lbl, _val, _col in [
                    ("10D High", _tv_hi10, "var(--warn)"),
                    ("10D Low",  _tv_lo10, "var(--warn)"),
                    ("ATR(14)",  _tv_atr14, "var(--muted)"),
                ]:
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid var(--rule);display:flex;gap:8px;font-size:0.82rem">'
                        f'<span style="flex:1;color:var(--ink)">{_lbl}</span>'
                        f'<span style="color:{_col}">₹{_val:,.2f}</span>'
                        f'</div>', unsafe_allow_html=True
                    )

            # ── Multi-panel chart: Price + Volume + RSI + MACD ───────────────
            st.markdown("---")
            section("Technical Chart")
            from plotly.subplots import make_subplots as _make_subplots

            # ── Compute RSI(14) ──────────────────────────────────────────────
            def _calc_rsi(series, period=14):
                delta = series.diff()
                gain  = delta.clip(lower=0).rolling(period).mean()
                loss  = (-delta.clip(upper=0)).rolling(period).mean()
                rs    = gain / loss.replace(0, float("nan"))
                return 100 - (100 / (1 + rs))

            # ── Compute MACD(12,26,9) ────────────────────────────────────────
            def _calc_macd(series, fast=12, slow=26, sig=9):
                ema_fast = series.ewm(span=fast, adjust=False).mean()
                ema_slow = series.ewm(span=slow, adjust=False).mean()
                macd     = ema_fast - ema_slow
                signal   = macd.ewm(span=sig, adjust=False).mean()
                hist_val = macd - signal
                return macd, signal, hist_val

            _tv_rsi          = _calc_rsi(_tv_hist["Close"])
            _tv_macd, _tv_sig, _tv_hist_macd = _calc_macd(_tv_hist["Close"])

            _fig_mp = _make_subplots(
                rows=4, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.50, 0.15, 0.18, 0.17],
                subplot_titles=("", "Volume", "RSI(14)", "MACD(12,26,9)")
            )

            # Row 1: Candlestick + SMAs
            _fig_mp.add_trace(go.Candlestick(
                x=_tv_hist.index,
                open=_tv_hist["Open"], high=_tv_hist["High"],
                low=_tv_hist["Low"],   close=_tv_hist["Close"],
                name=_tv_sym,
                increasing_line_color="#45BE92", decreasing_line_color="#E9857C",
                increasing_fillcolor="#15803D",  decreasing_fillcolor="#DC2626",
            ), row=1, col=1)
            for _sl, _sv, _sc in [
                ("SMA20",  _tv_hist["Close"].rolling(20).mean(),  "var(--warn)"),
                ("SMA50",  _tv_hist["Close"].rolling(50).mean(),  "var(--acc)"),
                ("SMA200", _tv_hist["Close"].rolling(200).mean(), "#a78bfa"),
            ]:
                _fig_mp.add_trace(go.Scatter(
                    x=_tv_hist.index, y=_sv, name=_sl, mode="lines",
                    line=dict(width=1.2, color=_sc)
                ), row=1, col=1)

            # Row 2: Volume bars
            _vol_colors = [
                "var(--bull)" if c >= o else "var(--bear)"
                for c, o in zip(_tv_hist["Close"], _tv_hist["Open"])
            ]
            _fig_mp.add_trace(go.Bar(
                x=_tv_hist.index, y=_tv_hist["Volume"],
                name="Volume", marker_color=_vol_colors, showlegend=False
            ), row=2, col=1)

            # Row 3: RSI
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_rsi, name="RSI(14)", mode="lines",
                line=dict(width=1.4, color="#1D4ED8"), showlegend=False
            ), row=3, col=1)
            _fig_mp.add_hrect(y0=70, y1=100, row=3, col=1,
                              fillcolor="rgba(255,75,75,0.08)", line_width=0)
            _fig_mp.add_hrect(y0=0, y1=30, row=3, col=1,
                              fillcolor="rgba(0,242,96,0.08)", line_width=0)
            _fig_mp.add_hline(y=70, row=3, col=1, line_dash="dot",
                              line_color="#E9857C", line_width=1)
            _fig_mp.add_hline(y=30, row=3, col=1, line_dash="dot",
                              line_color="#45BE92", line_width=1)

            # Row 4: MACD
            _macd_bar_colors = [
                "var(--bull)" if v >= 0 else "var(--bear)" for v in _tv_hist_macd.fillna(0)
            ]
            _fig_mp.add_trace(go.Bar(
                x=_tv_hist.index, y=_tv_hist_macd,
                name="Histogram", marker_color=_macd_bar_colors, showlegend=False
            ), row=4, col=1)
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_macd, name="MACD", mode="lines",
                line=dict(width=1.2, color="#1D4ED8"), showlegend=False
            ), row=4, col=1)
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_sig, name="Signal", mode="lines",
                line=dict(width=1.2, color="#B45309"), showlegend=False
            ), row=4, col=1)

            _common_ax = dict(gridcolor="#E2E8F0", showgrid=True, zeroline=False)
            _fig_mp.update_layout(
                height=640, margin=dict(t=20, l=0, r=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis_rangeslider_visible=False,
                legend=dict(font=dict(size=9, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)",
                            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
                font=dict(color="#E3EBEC"),
            )
            for _ax_key in ["xaxis", "xaxis2", "xaxis3", "xaxis4",
                            "yaxis",  "yaxis2",  "yaxis3",  "yaxis4"]:
                _fig_mp.update_layout(**{_ax_key: _common_ax})
            _fig_mp.update_layout(yaxis3=dict(range=[0, 100], **_common_ax))

            # Annotation: current RSI value
            _rsi_now = float(_tv_rsi.dropna().iloc[-1]) if not _tv_rsi.dropna().empty else 0
            _rsi_col = "var(--bear)" if _rsi_now > 70 else "var(--bull)" if _rsi_now < 30 else "var(--warn)"
            _fig_mp.add_annotation(
                x=0.01, y=0.28, xref="paper", yref="paper",
                text=f"RSI {_rsi_now:.1f}", showarrow=False,
                font=dict(size=10, color=_rsi_col), bgcolor="rgba(0,0,0,0.5)"
            )

            st.plotly_chart(_fig_mp, use_container_width=True)

            # ── Weinstein Stage Quick-Score ───────────────────────────────────
            st.markdown("---")
            section("Weinstein Stage Quick Assessment")
            _ws_above200  = _tv_price > _tv_sma200
            _ws_above50   = _tv_price > _tv_sma50
            _ws_sma200slp = float(
                (_tv_c.rolling(200).mean().diff(10) / _tv_c.rolling(200).mean().shift(10) * 100).iloc[-1]
            ) if len(_tv_c) >= 210 else 0.0
            _ws_pos52     = ((_tv_price - _tv_lo52) / max(_tv_hi52 - _tv_lo52, 1)) * 100 if _tv_hi52 > _tv_lo52 else 50
            _ws_score = (
                (25 if _ws_above200 and _ws_sma200slp > 0 else 0) +
                (20 if _ws_above200 else 0) +
                (15 if _ws_sma200slp > 0 else 0) +
                (12 if _ws_pos52 >= 75 else 6 if _ws_pos52 >= 50 else 0) +
                (8  if _ws_above50  else 0)
            )
            _ws_stage = (
                "Stage 2 — Advancing 🟢" if _ws_score >= 60 and _ws_above200 else
                "Stage 1 — Basing 🟡"    if _ws_above200 and _ws_sma200slp >= -0.5 else
                "Stage 4 — Declining 🔴" if not _ws_above200 and _ws_sma200slp < 0 else
                "Stage 3 — Topping 🟠"
            )
            _ws_c1, _ws_c2, _ws_c3, _ws_c4 = st.columns(4)
            _ws_c1.metric("Stage",          _ws_stage.split("—")[0].strip())
            _ws_c2.metric("Weinstein Score", f"{_ws_score}/80")
            _ws_c3.metric("52W Position",    f"{_ws_pos52:.0f}%")
            _ws_c4.metric("SMA200 Slope",    f"{_ws_sma200slp:+.2f}%",
                          delta="Rising" if _ws_sma200slp > 0 else "Falling",
                          delta_color="normal" if _ws_sma200slp > 0 else "inverse")
