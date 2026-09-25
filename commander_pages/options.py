# commander_pages/options.py - the OPTIONS page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('options', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📐 Options Desk</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live NSE option chain — PCR · Max Pain · OI buildup</div>', unsafe_allow_html=True)

    try:
        from nse_options import get_option_chain as _get_oc
        _OC_OK = True
    except ImportError:
        _OC_OK = False

    _opt1, _opt2, _opt3 = st.tabs(["📡 Live Chain", "🔗 External Tools", "📚 Quick Reference"])

    # ════════════════════════════════════════════════════════════════════════
    with _opt1:
        # ── Controls ──────────────────────────────────────────────────────
        _oc_c1, _oc_c2, _oc_c3, _oc_c4 = st.columns([2, 2, 2, 2])
        with _oc_c1:
            _oc_sym = st.selectbox(
                "Index / Symbol",
                ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
                key="oc_symbol"
            )
        with _oc_c2:
            _oc_custom = st.text_input(
                "Custom symbol (equity)", placeholder="e.g. RELIANCE",
                key="oc_custom"
            ).strip().upper()
            if _oc_custom:
                _oc_sym = _oc_custom
        with _oc_c3:
            _oc_expiry_idx = st.selectbox(
                "Expiry", [0, 1, 2, 3],
                format_func=lambda i: ["Current", "Next", "+2", "+3"][i],
                key="oc_expiry_idx"
            )
        with _oc_c4:
            _oc_fetch = st.button(
                "🔄 Fetch Chain", type="primary",
                key="oc_fetch_btn", use_container_width=True
            )
            _oc_auto = st.checkbox("Auto-load on open", value=True, key="oc_auto")

        if not _OC_OK:
            st.error(
                "nse_options.py not found in the project folder. "
                "Ensure the file exists and restart the app."
            )
        elif _oc_fetch or (_oc_auto and "oc_data_" + _oc_sym not in st.session_state):
            with st.spinner(f"Warming NSE session then fetching {_oc_sym} option chain… (takes ~3 seconds)"):
                if _oc_fetch:
                    # Force-clear cached session so 3-step warmup always runs fresh
                    try:
                        import nse_options as _nse_mod
                        _nse_mod._session_obj   = None
                        _nse_mod._session_built = 0.0
                    except Exception:
                        pass
                _oc_result = _get_oc(_oc_sym, int(_oc_expiry_idx))
                st.session_state["oc_data_" + _oc_sym] = _oc_result

        _oc_data = st.session_state.get("oc_data_" + _oc_sym)

        if _oc_data:
            if _oc_data.get("error"):
                if _oc_data.get("_market_closed"):
                    st.warning(
                        "**NSE markets are closed** (weekends / outside 09:15–15:30 IST). "
                        "Option chain data is only published during live trading sessions.\n\n"
                        "Fetch the chain on a weekday during market hours — results are "
                        "cached and will show here on subsequent visits."
                    )
                else:
                    st.error(f"Could not fetch option chain: {_oc_data['error']}")
                    st.info(
                        "**NSE uses Akamai bot-protection.** If you see session errors:\n\n"
                        "```\npip install curl_cffi\n```\n"
                        "`curl_cffi` impersonates Chrome's TLS fingerprint and bypasses "
                        "Akamai reliably. After installing, click **Fetch Chain** again.\n\n"
                        "Alternative: `pip install nsepython`"
                    )
            else:
                _oc_df   = _oc_data["chain_df"]
                _oc_spot = _oc_data["spot"]
                _oc_pcr  = _oc_data["pcr"]
                _oc_mp   = _oc_data["max_pain"]
                _oc_exp  = _oc_data["expiry"]
                _oc_src  = _oc_data.get("source", "")
                _oc_ts   = _oc_data.get("timestamp", "")

                # nse_options now returns None (not 0) when the chain did not arrive,
                # because these figures are drawn as chart levels and a max pain of 0 is
                # a price line that looks exactly like a real one. Everything below has
                # to tolerate None rather than format it.
                def _ocn(v, fmt="{:,.2f}"):
                    try:
                        return fmt.format(v) if v is not None else "—"
                    except (TypeError, ValueError):
                        return "—"

                if _oc_pcr is None or _oc_mp is None:
                    st.warning(
                        "The option chain did not return usable data — PCR, max pain and "
                        "OI totals are shown as “—”. They are NOT zero; NSE simply did "
                        "not answer. Click Fetch Chain again to rebuild the session."
                    )

                st.caption(
                    f"Expiry: **{_oc_exp}** · Spot: **{_ocn(_oc_spot)}** · "
                    f"Source: {_oc_src} · As of: {_oc_ts}"
                )

                # ── Key metrics row ────────────────────────────────────────
                section("Live Snapshot")
                _km1, _km2, _km3, _km4, _km5 = st.columns(5)

                # PCR colour — gated on the value EXISTING, not on its size. A missing
                # PCR falling through to the bottom band would label an absent chain
                # "Complacency Risk", which is a reading, not an absence.
                _pcr_col = (
                    "var(--muted)" if _oc_pcr is None else
                    "var(--bull)"  if _oc_pcr > 1.3 else
                    "var(--warn)"  if _oc_pcr > 0.7 else
                    "var(--bear)"
                )
                _pcr_label = (
                    "no data"            if _oc_pcr is None else
                    "Contrarian Bullish" if _oc_pcr > 1.3 else
                    "Mildly Bearish"     if _oc_pcr > 1.0 else
                    "Balanced"           if _oc_pcr > 0.7 else
                    "Complacency Risk"
                )
                _km1.metric("Spot", _ocn(_oc_spot))
                _km2.metric(
                    "PCR", _ocn(_oc_pcr, "{:.3f}"),
                    delta=_pcr_label,
                    delta_color="off" if _oc_pcr is None else
                                ("normal" if _oc_pcr > 0.7 else "inverse")
                )
                _km3.metric(
                    "Max Pain", _ocn(_oc_mp, "{:,.0f}"),
                    delta=(f"{((_oc_mp - _oc_spot) / _oc_spot)*100:+.2f}% from spot"
                           if (_oc_mp is not None and _oc_spot) else "—"),
                    delta_color=("off" if (_oc_mp is None or not _oc_spot)
                                 else ("normal" if _oc_mp >= _oc_spot else "inverse")))
                _km4.metric("Total CE OI", _ocn(_oc_data["total_ce_oi"], "{:,}"))
                _km5.metric("Total PE OI", _ocn(_oc_data["total_pe_oi"], "{:,}"))

                # PCR gauge bar
                st.markdown(
                    f"""<div style="margin:8px 0 4px;font-size:0.78rem;color:var(--muted)">
                    PCR gauge — 0 (bearish) → 0.7 → 1.0 → 1.3 → 2 (bullish hedge)
                    </div>""",
                    unsafe_allow_html=True
                )
                _pcr_pct = min(_oc_pcr / 2.0, 1.0) * 100
                st.progress(int(_pcr_pct), text=f"PCR {_oc_pcr:.3f} — {_pcr_label}")

                st.markdown("---")

                if not _oc_df.empty:
                    # ── Filter to ATM ± N strikes ──────────────────────────
                    _oc_n = st.slider(
                        "Strikes around ATM to display",
                        min_value=5, max_value=30, value=15, step=5,
                        key="oc_atm_range"
                    )
                    _atm_idx = (_oc_df["strike"] - _oc_spot).abs().idxmin()
                    _lo_idx  = max(0, _atm_idx - _oc_n)
                    _hi_idx  = min(len(_oc_df) - 1, _atm_idx + _oc_n)
                    _oc_view = _oc_df.iloc[_lo_idx:_hi_idx + 1].copy()

                    # ── OI bar chart (CE vs PE) ────────────────────────────
                    section("Open Interest by Strike")
                    _fig_oi = go.Figure()
                    _fig_oi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["CE_OI"],
                        name="Call OI", marker_color="#E9857C",
                        opacity=0.85
                    ))
                    _fig_oi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["PE_OI"],
                        name="Put OI", marker_color="#45BE92",
                        opacity=0.85
                    ))
                    # Vertical lines for spot and max pain
                    _fig_oi.add_vline(
                        x=_oc_spot, line_dash="dash", line_color="#56C2CC",
                        annotation_text=f"Spot {_oc_spot:,.0f}",
                        annotation_font_color="#56C2CC", line_width=1.5
                    )
                    _fig_oi.add_vline(
                        x=_oc_mp, line_dash="dot", line_color="#DCA84E",
                        annotation_text=f"Max Pain {_oc_mp:,.0f}",
                        annotation_font_color="#DCA84E", line_width=1.5
                    )
                    _fig_oi.update_layout(
                        barmode="group", height=340,
                        margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#E2E8F0", title="Strike"),
                        yaxis=dict(gridcolor="#E2E8F0", title="Open Interest (contracts)"),
                        legend=dict(font=dict(size=10, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                        font=dict(color="#E3EBEC"),
                    )
                    st.plotly_chart(_fig_oi, use_container_width=True)

                    # ── Change-in-OI (buildup) ─────────────────────────────
                    st.markdown("---")
                    section("Change in OI — Buildup Analysis")
                    _fig_doi = go.Figure()
                    _ce_doi_colors = [
                        "var(--bear)" if v >= 0 else "var(--bear-rule)"
                        for v in _oc_view["CE_chgOI"]
                    ]
                    _pe_doi_colors = [
                        "var(--bull)" if v >= 0 else "var(--bull-bg)"
                        for v in _oc_view["PE_chgOI"]
                    ]
                    _fig_doi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["CE_chgOI"],
                        name="Call ΔOI", marker_color=_ce_doi_colors, opacity=0.85
                    ))
                    _fig_doi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["PE_chgOI"],
                        name="Put ΔOI", marker_color=_pe_doi_colors, opacity=0.85
                    ))
                    _fig_doi.add_vline(x=_oc_spot, line_dash="dash",
                                       line_color="#56C2CC", line_width=1.5)
                    _fig_doi.add_hline(y=0, line_color="#5C6B6E", line_width=1)
                    _fig_doi.update_layout(
                        barmode="group", height=280,
                        margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(gridcolor="#E2E8F0", title="Strike"),
                        yaxis=dict(gridcolor="#E2E8F0", title="Change in OI"),
                        legend=dict(font=dict(size=10, color="#E3EBEC"), bgcolor="rgba(0,0,0,0)"),
                        font=dict(color="#E3EBEC"),
                    )
                    st.plotly_chart(_fig_doi, use_container_width=True)

                    # ── Buildup interpretation ─────────────────────────────
                    _oc_ce_chg_tot = int(_oc_view["CE_chgOI"].sum())
                    _oc_pe_chg_tot = int(_oc_view["PE_chgOI"].sum())
                    _oc_buildup = (
                        "Bears building (Call OI rising + Put OI rising)"
                        if _oc_ce_chg_tot > 0 and _oc_pe_chg_tot > 0 else
                        "Bulls building (Call OI falling + Put OI rising — put unwinding)"
                        if _oc_ce_chg_tot <= 0 and _oc_pe_chg_tot > 0 else
                        "Bearish (Call OI rising + Put OI falling — call writing)"
                        if _oc_ce_chg_tot > 0 and _oc_pe_chg_tot <= 0 else
                        "Bulls in control (both OIs declining)"
                    )
                    _oc_bu_col = (
                        "var(--bull)" if "Bull" in _oc_buildup else
                        "var(--bear)" if "Bear" in _oc_buildup else "var(--warn)"
                    )
                    st.markdown(
                        f'<div class="metric-card" style="border-left:3px solid {_oc_bu_col}">'
                        f'<div class="metric-label">ΔOI Interpretation</div>'
                        f'<div class="metric-value" style="color:{_oc_bu_col};font-size:0.9rem">'
                        f'{_oc_buildup}</div>'
                        f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px">'
                        f'CE ΔOI net: {_oc_ce_chg_tot:+,}  |  PE ΔOI net: {_oc_pe_chg_tot:+,}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    # ── IV Skew ────────────────────────────────────────────
                    st.markdown("---")
                    section("IV Skew — Implied Volatility by Strike")
                    _iv_view = _oc_view[
                        (_oc_view["CE_IV"] > 0) | (_oc_view["PE_IV"] > 0)
                    ]
                    if not _iv_view.empty:
                        _fig_iv = go.Figure()
                        _fig_iv.add_trace(go.Scatter(
                            x=_iv_view["strike"], y=_iv_view["CE_IV"],
                            name="Call IV", mode="lines+markers",
                            line=dict(color="#DC2626", width=1.5),
                            marker=dict(size=5)
                        ))
                        _fig_iv.add_trace(go.Scatter(
                            x=_iv_view["strike"], y=_iv_view["PE_IV"],
                            name="Put IV", mode="lines+markers",
                            line=dict(color="#15803D", width=1.5),
                            marker=dict(size=5)
                        ))
                        _fig_iv.add_vline(x=_oc_spot, line_dash="dash",
                                          line_color="#56C2CC", line_width=1.5)
                        _fig_iv.update_layout(
                            height=240, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(gridcolor="#E2E8F0", title="Strike"),
                            yaxis=dict(gridcolor="#E2E8F0", title="IV %"),
                            legend=dict(font=dict(size=10, color="#E3EBEC"),
                                        bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#E3EBEC"),
                        )
                        st.plotly_chart(_fig_iv, use_container_width=True)

                    # ── Data table ─────────────────────────────────────────
                    st.markdown("---")
                    section("Option Chain — Near ATM Strikes")
                    _tbl_cols = ["strike",
                                 "CE_OI", "CE_chgOI", "CE_LTP", "CE_IV",
                                 "PE_OI", "PE_chgOI", "PE_LTP", "PE_IV"]
                    _tbl_cols = [c for c in _tbl_cols if c in _oc_view.columns]
                    st.dataframe(
                        _oc_view[_tbl_cols].rename(columns={
                            "strike":   "Strike",
                            "CE_OI":    "CE OI", "CE_chgOI": "CE ΔOI",
                            "CE_LTP":   "CE LTP", "CE_IV":   "CE IV%",
                            "PE_OI":    "PE OI", "PE_chgOI": "PE ΔOI",
                            "PE_LTP":   "PE LTP", "PE_IV":   "PE IV%",
                        }),
                        use_container_width=True, hide_index=True
                    )

                    # Download
                    st.download_button(
                        "⬇️ Download chain CSV",
                        data=_oc_df.to_csv(index=False),
                        file_name=f"option_chain_{_oc_sym}_{_oc_exp.replace('-','')}.csv",
                        mime="text/csv",
                        key="dl_oc_csv"
                    )

    # ════════════════════════════════════════════════════════════════════════
    with _opt2:
        section("NSE Options — Direct Links")
        _ol1, _ol2, _ol3 = st.columns(3)
        with _ol1:
            st.link_button("📊 NSE Option Chain (NIFTY)",
                           "https://www.nseindia.com/option-chain",
                           use_container_width=True)
            st.link_button("📊 NSE Option Chain (BANKNIFTY)",
                           "https://www.nseindia.com/option-chain?optionType=CE&instrumentType=OPTIDX&symbol=BANKNIFTY",
                           use_container_width=True)
            st.link_button("📊 NSE Option Chain (FINNIFTY)",
                           "https://www.nseindia.com/option-chain?optionType=CE&instrumentType=OPTIDX&symbol=FINNIFTY",
                           use_container_width=True)
        with _ol2:
            st.link_button("🧠 Sensibull — Options Analysis",
                           "https://sensibull.com/nifty-option-chain",
                           use_container_width=True)
            st.link_button("📉 Sensibull Max Pain",
                           "https://sensibull.com/max-pain",
                           use_container_width=True)
            st.link_button("📈 Sensibull PCR",
                           "https://sensibull.com/pcr",
                           use_container_width=True)
        with _ol3:
            st.link_button("🔬 Opstra — Option Chain + Greeks",
                           "https://opstra.definedge.com/",
                           use_container_width=True)
            st.link_button("📋 Opstra OI Analysis",
                           "https://opstra.definedge.com/oi-analysis",
                           use_container_width=True)
            st.link_button("🎯 Opstra Strategy Builder",
                           "https://opstra.definedge.com/strategy-builder",
                           use_container_width=True)

        st.markdown("---")
        st.info(
            "If the Live Chain tab fails with a network error, these direct links "
            "open the full NSE / Sensibull / Opstra option chain in your browser.\n\n"
            "To enable the live data tab, run: `pip install nsepython` for an "
            "alternate session handler."
        )

    # ════════════════════════════════════════════════════════════════════════
    with _opt3:
        section("Key Concepts Quick Reference")
        _qr1, _qr2, _qr3 = st.columns(3, gap="large")
        with _qr1:
            st.markdown("""
**Max Pain**
Strike price where option writers (sellers) lose the *least* money at expiry.
Price gravitates toward max pain as expiry approaches.

🟢 Spot *below* max pain → drift upward expected
🔴 Spot *above* max pain → drift downward expected
""")
        with _qr2:
            st.markdown("""
**PCR (Put-Call Ratio)**
Total Put OI ÷ Total Call OI.

| PCR | Reading |
|-----|---------|
| > 1.3 | Heavy hedging — contrarian bullish |
| 1.0–1.3 | Mildly bearish |
| 0.7–1.0 | Balanced / neutral |
| < 0.7 | Complacency — reversal risk |
""")
        with _qr3:
            st.markdown("""
**Change in OI (ΔOI)**

| Call ΔOI | Put ΔOI | Interpretation |
|----------|---------|----------------|
| ↑ | ↑ | Bears in control |
| ↑ | ↓ | Put unwinding — bullish |
| ↓ | ↑ | Call writing — bearish |
| ↓ | ↓ | Bulls in control |

Short buildup = OI↑ + price↓
Long buildup  = OI↑ + price↑
""")
