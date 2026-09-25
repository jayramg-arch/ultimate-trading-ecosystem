# commander_pages/etf.py - the ETF page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('etf', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🪙 ETF Trading System</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Sector Rotation // Asset-Class Regime // '
                'RRG Quadrants // Liquidity-Aware Picks — NSE ETFs only</div>',
                unsafe_allow_html=True)
    st.caption(
        "**Structure is read from the INDEX; the ETF is the vehicle you trade.** "
        "Stage, trend, RS and RRG come from the sector/asset-class index where one "
        "exists (42 of 51 names) — a clean, stock-like series without the tracking "
        "error, NAV premium and thin-book wicks that distort an ETF chart. Liquidity, "
        "turnover, LTP and anything an order touches always come from the ETF. "
        "**Volume is never borrowed between them**: volume confirmation asserts that "
        "*this* volume accompanied *this* price move, and ETF volume did not move the "
        "index — so volume-derived work belongs on the ETF chart, in stage 2. "
        "Every row records which series produced it.")

    if not _ETF_OK:
        st.error("❌ ETF modules (etf_universe / etf_screener / etf_rotation) "
                  "not available. Run `pip install -r requirements.txt` and ensure "
                  "the three modules are present in the project root.")
    else:
        import os as _os_etf

        # ── File status strip ───────────────────────────────────────────────
        _ETF_FILES = {
            "Screener":  "ETF_Screener_Results.csv",
            "Sectors":   "ETF_Sector_Rotation.csv",
            "Regime":    "ETF_AssetClass_Regime.csv",
            "RRG":       "ETF_RRG_Coordinates.csv",
            "Picks":     "ETF_Top_Picks.csv",
        }
        _file_meta = {}
        for label, fname in _ETF_FILES.items():
            p = _os_etf.path.join(_os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                                   fname)
            if _os_etf.path.exists(p):
                try:
                    _df_tmp = pd.read_csv(p)
                    _mtime = datetime.fromtimestamp(_os_etf.path.getmtime(p))
                    _age_h = (datetime.now() - _mtime).total_seconds() / 3600
                    _file_meta[label] = {
                        "rows":  len(_df_tmp),
                        "mtime": _mtime.strftime("%d %b %H:%M"),
                        "age_h": _age_h,
                        "exists": True,
                    }
                except Exception:
                    _file_meta[label] = {"exists": False}
            else:
                _file_meta[label] = {"exists": False}

        # Render the strip + Run-All button
        _hdr_l, _hdr_r = st.columns([5, 1])
        with _hdr_l:
            _strip_html = '<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px">'
            for label, meta in _file_meta.items():
                if meta.get("exists"):
                    _age = meta["age_h"]
                    _color = ("var(--bull)" if _age < 24
                              else "var(--warn)" if _age < 72
                              else "var(--bear)")
                    _icon = ("🟢" if _age < 24 else "🟡" if _age < 72 else "🔴")
                    _txt = f"{label}: {meta['rows']} rows · {meta['mtime']}"
                else:
                    _color = "var(--bear)"
                    _icon  = "🔴"
                    _txt   = f"{label}: not generated"
                _strip_html += (
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;'
                    f'color:{_color}">{_icon} {_txt}</div>'
                )
            _strip_html += "</div>"
            st.markdown(_strip_html, unsafe_allow_html=True)
        with _hdr_r:
            if st.button("🔄 Run All", key="etf_run_all", type="primary",
                          use_container_width=True):
                with st.spinner("Running ETF screener + rotation engine "
                                "(~30-60s)..."):
                    try:
                        _df_etf = _etf_s.rank_universe()
                        if not _df_etf.empty:
                            _df_etf.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Screener"]), index=False)

                        _sec = _etf_r.sector_rotation_table()
                        if not _sec.empty:
                            _sec.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Sectors"]), index=False)

                        _reg = _etf_r.asset_class_regime()
                        if _reg.get("rows"):
                            _df_reg = pd.DataFrame(_reg["rows"])
                            _df_reg["regime_label"] = _reg["regime_label"]
                            _df_reg["fetched_at"]   = _reg["fetched_at"]
                            _df_reg.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Regime"]), index=False)

                        _rrg = _etf_r.rrg_coordinates()
                        if not _rrg.empty:
                            _rrg.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["RRG"]), index=False)

                        _picks = _etf_r.top_picks_by_regime(_sec, _reg)
                        if not _picks.empty:
                            _picks.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Picks"]), index=False)

                        st.success("✅ ETF system refreshed!")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Run failed: {_e}")

        # ── Tabs ────────────────────────────────────────────────────────────
        _et1, _et2, _et3, _et4, _et5 = st.tabs([
            "🎯 Top Picks", "🔄 Sector Rotation",
            "📊 Asset-Class Regime", "💧 Liquidity & Universe",
            "🧭 Vehicle & Chart",
        ])

        # ─── TAB 1 — Top Picks ─────────────────────────────────────────────
        with _et1:
            section("Regime-Aware ETF Picks")
            _picks_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Picks"])
            _scr_path   = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Screener"])

            if not _file_meta["Picks"].get("exists") or _file_meta["Picks"]["rows"] == 0:
                st.info("No picks file yet. Click **🔄 Run All** above to generate.")
            else:
                _df_picks = pd.read_csv(_picks_path)
                _regime_lbl = (_df_picks["Regime"].iloc[0]
                                if "Regime" in _df_picks.columns and not _df_picks.empty
                                else "—")
                _reg_color = ("var(--bull)" if _regime_lbl == "RISK_ON" else
                              "var(--warn)" if _regime_lbl in ("MIXED","INTL_LED") else
                              "var(--acc)" if _regime_lbl == "GOLD_LED" else
                              "var(--bear)" if _regime_lbl == "RISK_OFF" else "var(--muted)")
                st.markdown(
                    f'<div class="metric-card" style="padding:12px 16px;margin-bottom:14px">'
                    f'<div class="metric-label">Active Regime</div>'
                    f'<div class="metric-value" style="color:{_reg_color};font-size:1.2rem">'
                    f'{_regime_lbl}</div>'
                    f'<div style="font-size:0.62rem;color:var(--ink);margin-top:3px">'
                    f'{len(_df_picks)} picks · suggested weights sum to '
                    f'{_df_picks["Suggested_Weight_pct"].sum() if "Suggested_Weight_pct" in _df_picks.columns else 0}%</div>'
                    f'</div>', unsafe_allow_html=True
                )

                # Picks table with highlighted weight column
                _disp = _df_picks.copy()
                if "Suggested_Weight_pct" in _disp.columns:
                    _disp = _disp.sort_values("Suggested_Weight_pct", ascending=False)

                # Enrich with screener LTP / Stage / Signal where available
                if _file_meta["Screener"].get("exists"):
                    try:
                        _df_scr = pd.read_csv(_scr_path)
                        _enrich_cols = ["Symbol", "LTP", "Stage", "RRG_Quadrant",
                                        "Total_Score", "Signal"]
                        _enrich_cols = [c for c in _enrich_cols
                                        if c in _df_scr.columns]
                        _disp = _disp.merge(_df_scr[_enrich_cols], on="Symbol", how="left")
                    except Exception:
                        pass

                st.dataframe(_disp, use_container_width=True, hide_index=True)

                # Send-to-TV / copy-to-clipboard helper
                _sym_str = ",".join(f"NSE:{s}" for s in _df_picks["Symbol"].tolist())
                with st.expander("📋 Copy symbols (for TradingView watchlist)"):
                    st.code(_sym_str, language="text")
                    st.caption("Paste into TradingView → Watchlist → Add Symbols")

        # ─── TAB 2 — Sector Rotation ────────────────────────────────────────
        with _et2:
            st.caption(
                "**Rotation is measured on the INDEX, not the ETF.** Rotation asks which "
                "SECTOR is leading; the ETF is only the vehicle. Measuring the vehicle adds "
                "tracking error, NAV premium (ITIETF has run +2.95% — enough to invent or "
                "erase a signal) and thin-book noise, none of which is about the sector. "
                "The `Measured_On` column records the series used per row.")
            section("Sector Rotation Table — composite RS (60% 12W + 40% 4W)")
            _sec_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Sectors"])
            if not _file_meta["Sectors"].get("exists") or _file_meta["Sectors"]["rows"] == 0:
                st.info("No sector rotation file. Click **🔄 Run All** above.")
            else:
                _df_sec = pd.read_csv(_sec_path)

                # Tier counts strip
                _q_counts = _df_sec["Quartile"].value_counts() if "Quartile" in _df_sec.columns else {}
                _qc1, _qc2, _qc3, _qc4 = st.columns(4)
                _qc1.metric("🟢 OVERWEIGHT", int(_q_counts.get("TOP", 0)))
                _qc2.metric("🟡 NEUTRAL+",   int(_q_counts.get("2",   0)))
                _qc3.metric("🟠 NEUTRAL−",   int(_q_counts.get("3",   0)))
                _qc4.metric("🔴 UNDERWEIGHT",int(_q_counts.get("BOTTOM", 0)))

                st.markdown("---")
                _sty_cols = [c for c in ["Excess_4W_pct", "Excess_12W_pct",
                                          "Composite_Score"]
                             if c in _df_sec.columns]
                _sty = _df_sec.style.format({c: "{:+.2f}" for c in _sty_cols})
                st.dataframe(_sty, use_container_width=True, hide_index=True)

                with st.expander("ℹ️ How the composite is built"):
                    st.markdown("""
- **Excess return** = sector return − Nifty 500 return (so we measure
  *true rotation*, not absolute beta exposure)
- **Composite Score** = `0.6 × rank(12W excess) + 0.4 × rank(4W excess)`
- The 60/40 split favours the established trend (12W) but lets the 4W catch
  the early turn — so a sector flipping from LAGGING → IMPROVING shows up
  before the 12W catches up.
- **Quartile**: TOP = OVERWEIGHT, BOTTOM = UNDERWEIGHT.
                    """)

        # ─── TAB 3 — Asset-Class Regime ─────────────────────────────────────
        with _et3:
            st.caption(
                "**The tilt % is a RANK template, not a score or a forecast.** A class "
                "qualifies only if its flagship is ABOVE its 200-DMA *and* has a positive "
                "12-week excess return; qualifiers then receive 40 / 25 / 20 / 15 % by rank, "
                "and debt absorbs the remainder. So 'gold 40%' means gold ranked FIRST among "
                "those that qualified — the count of qualifiers is the real signal. "
                "The cash park is **LIQUID1**, not LIQUIDBEES: LIQUIDBEES is the dividend "
                "variant with NAV pinned at ₹1,000, so its price return is +0.00% over a year "
                "across six distinct closes — it would have scored the debt leg at a permanent "
                "zero. LIQUID1 is the growth variant (+12.04% over the same year).")

            # WHICH METAL. The regime allocates by asset class - it says "gold 40%" but
            # not whether that sleeve belongs in gold or silver, and the two diverge
            # hard: silver leads risk-on metal phases and lags badly in fear phases.
            # From the file the pipeline wrote - NOT a live call. asset_class_regime()
            # batch-fetches every flagship, and this tab body re-runs on every
            # interaction; computing here would make the tab feel broken and look like
            # a network fault. Live call only as a first-run fallback.
            _ms = {}
            try:
                import json as _json_ui
                import etf_rotation as _er_ui
                _mp_ui = _os_etf.path.join(
                    _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                    getattr(_er_ui, "METALS_JSON", "ETF_Metals_Split.json"))
                if _os_etf.path.exists(_mp_ui):
                    with open(_mp_ui, encoding="utf-8") as _fh_ui:
                        _ms = _json_ui.load(_fh_ui) or {}
                else:
                    _ms = (_er_ui.asset_class_regime() or {}).get("metals_split") or {}
            except Exception:
                _ms = {}
            if _ms:
                _lead = _ms.get("lead", "—")
                _lc = ("var(--acc)" if _lead == "GOLD-LED"
                       else "var(--bull)" if _lead == "SILVER-LED" else "var(--muted)")
                _m1, _m2, _m3 = st.columns(3)
                _m1.markdown(
                    f'<div class="metric-card" style="padding:10px 14px">'
                    f'<div class="metric-label">Metals lead</div>'
                    f'<div style="color:{_lc};font-weight:700">{_lead}</div></div>',
                    unsafe_allow_html=True)
                _m2.metric("Gold − Silver · 12w",
                           "—" if _ms.get("gap_12w_pct") is None else f"{_ms['gap_12w_pct']:+.2f} pp")
                _m3.metric("Gold − Silver · 4w",
                           "—" if _ms.get("gap_4w_pct") is None else f"{_ms['gap_4w_pct']:+.2f} pp")
                _pc = _ms.get("ratio_pctile_1y")
                st.caption(
                    "**Which metal, once the regime has said metals.** Figures are the "
                    "gold-minus-silver return gap in percentage points — scale-free, so "
                    "they mean the same thing whatever the two ETFs cost per unit. "
                    + (f"The gold/silver ratio sits at the **{_pc:.0f}th percentile** of its "
                       "trailing year. " if _pc is not None else
                       "Percentile needs a full year of both series and is withheld until then. ")
                    + "**The ratio's LEVEL is deliberately not shown**: the classic ~80 reading "
                      "is spot-per-ounce, and computed from ETF unit prices the same number is "
                      "arbitrary — it would look precise and mean nothing. Silver leads in "
                      "risk-on metal phases; gold leads in fear phases.")
            section("Asset-Class Regime Detector")
            _reg_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Regime"])
            if not _file_meta["Regime"].get("exists") or _file_meta["Regime"]["rows"] == 0:
                st.info("No regime file. Click **🔄 Run All** above.")
            else:
                _df_reg = pd.read_csv(_reg_path)
                _label  = _df_reg["regime_label"].iloc[0] if "regime_label" in _df_reg.columns else "—"
                _fetched= _df_reg["fetched_at"].iloc[0]   if "fetched_at"   in _df_reg.columns else "—"

                _reg_color = ("var(--bull)" if _label == "RISK_ON" else
                              "var(--warn)" if _label in ("MIXED","INTL_LED") else
                              "var(--acc)" if _label == "GOLD_LED" else
                              "var(--bear)" if _label == "RISK_OFF" else "var(--muted)")

                _r_a, _r_b = st.columns([3, 1])
                with _r_a:
                    st.markdown(
                        f'<div class="metric-card" style="padding:14px 18px">'
                        f'<div class="metric-label">REGIME</div>'
                        f'<div class="metric-value" style="color:{_reg_color};'
                        f'font-size:1.5rem">{_label}</div>'
                        f'<div style="font-size:0.62rem;color:var(--ink)">'
                        f'Detected at {_fetched}</div></div>',
                        unsafe_allow_html=True)
                with _r_b:
                    _eligible = int((_df_reg["status"] == "RISK_ON").sum()
                                     if "status" in _df_reg.columns else 0)
                    st.metric("Risk-On Asset Classes", _eligible)

                st.markdown("---")

                # Allocation pie + table
                _pie_l, _pie_r = st.columns([2, 3])
                with _pie_l:
                    if "suggested_tilt_pct" in _df_reg.columns:
                        _pie_df = _df_reg[_df_reg["suggested_tilt_pct"] > 0].copy()
                        if not _pie_df.empty:
                            import plotly.express as _px
                            _fig_pie = _px.pie(
                                _pie_df, names="asset_class",
                                values="suggested_tilt_pct",
                                hole=0.5,
                                color_discrete_sequence=_px.colors.sequential.Teal_r,
                            )
                            _fig_pie.update_layout(
                                height=320, margin=dict(t=10,b=10,l=10,r=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#E3EBEC", size=11),
                                showlegend=True,
                            )
                            st.plotly_chart(_fig_pie, use_container_width=True)
                        else:
                            st.info("No allocation suggested in current regime.")
                with _pie_r:
                    _disp_reg = _df_reg.drop(columns=["regime_label","fetched_at"],
                                              errors="ignore")
                    if "score" in _disp_reg.columns:
                        _disp_reg = _disp_reg.sort_values("score", ascending=False)
                    _fmt_cols = {c: "{:+.2f}" for c in
                                 ["ret_4w_pct","ret_12w_pct","excess_12w_pct","score"]
                                 if c in _disp_reg.columns}
                    st.dataframe(_disp_reg.style.format(_fmt_cols),
                                  use_container_width=True, hide_index=True)

                with st.expander("ℹ️ Regime rules"):
                    st.markdown("""
| Regime | Trigger |
|---|---|
| **RISK_ON**  | ≥2 equity flagships above 200DMA + outperforming gold |
| **GOLD_LED** | Gold flagship score > best equity flagship score |
| **INTL_LED** | Indian equity off, US/Intl on |
| **RISK_OFF** | All equities below 200DMA, gold not leading |
| **MIXED**    | None of the above |

Allocation tilt template: top scorer 40% → 25% → 20% → 15% → 0%.
Gold floor 10% in RISK_OFF. Debt absorbs residual to 100%.
                    """)

        # ─── TAB 4 — Liquidity & Universe ──────────────────────────────────
        with _et4:
            section("ETF Universe — Liquidity & Per-ETF Scoring")
            _scr_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Screener"])
            if not _file_meta["Screener"].get("exists") or _file_meta["Screener"]["rows"] == 0:
                st.info("No screener file. Click **🔄 Run All** above.")
            else:
                _df_scr = pd.read_csv(_scr_path)

                # Filter row
                _f1, _f2, _f3 = st.columns([2, 2, 3])
                _ac_opts = ["(all)"] + sorted(_df_scr["Asset_Class"].dropna().unique().tolist()
                                               if "Asset_Class" in _df_scr.columns else [])
                _ac_pick = _f1.selectbox("Asset Class", _ac_opts, key="etf_ac_filt")
                _liq_pick = _f2.selectbox("Liquidity Tier",
                                          ["(all)", "A only", "A + B", "A + B + C"],
                                          index=2, key="etf_liq_filt")
                _grade_pick = _f3.multiselect(
                    "Grade", ["⭐⭐⭐ A+","⭐⭐ A","⭐ B","C","D"],
                    default=["⭐⭐⭐ A+","⭐⭐ A","⭐ B"], key="etf_grade_filt")

                _disp = _df_scr.copy()
                if _ac_pick != "(all)" and "Asset_Class" in _disp.columns:
                    _disp = _disp[_disp["Asset_Class"] == _ac_pick]
                if _liq_pick != "(all)" and "Liquidity_Tier" in _disp.columns:
                    _allowed = {"A only": ["A"], "A + B": ["A","B"],
                                "A + B + C": ["A","B","C"]}.get(_liq_pick, ["A","B","C"])
                    _disp = _disp[_disp["Liquidity_Tier"].isin(_allowed)]
                if _grade_pick and "Grade" in _disp.columns:
                    _disp = _disp[_disp["Grade"].isin(_grade_pick)]

                st.caption(f"Showing **{len(_disp)}** of {len(_df_scr)} ETFs")

                # Top metrics
                _m_a, _m_b, _m_c, _m_d = st.columns(4)
                _m_a.metric("Universe", len(_df_scr))
                _m_b.metric("Stage 2",
                            int((_df_scr.get("Stage", pd.Series(dtype=int)) == 2).sum()))
                _m_c.metric("LEADING",
                            int((_df_scr.get("RRG_Quadrant", pd.Series(dtype=str)) == "LEADING").sum()))
                _m_d.metric("Liquid (≥₹2Cr/d)",
                            int((_df_scr.get("Liquidity_Score", pd.Series(dtype=int)) >= 6).sum()))

                st.markdown("---")

                # Best display columns
                # Structure_Source is FIRST after the identity columns on purpose: it
                # says whether Stage/RS/RRG on that row describe the index or the ETF,
                # and every other number is read differently depending on the answer.
                _show_cols = [c for c in [
                    "Symbol", "Name", "Asset_Class", "Sub_Category",
                    "Structure_Source",
                    "Total_Score", "Grade", "Stage", "RRG_Quadrant",
                    "Liquidity_Score", "Trend_Score", "RS_Score", "Rotation_Score",
                    "LTP", "Mansfield_RS", "RS_Momentum_4W",
                    "Turnover_60D_Cr", "Dist_52WH_pct", "Signal",
                ] if c in _disp.columns]

                _fmt = {c: "{:+.2f}" for c in
                        ["Mansfield_RS","RS_Momentum_4W","Dist_52WH_pct"]
                        if c in _disp.columns}
                _fmt.update({c: "{:.2f}" for c in
                             ["LTP","Turnover_60D_Cr"] if c in _disp.columns})
                st.dataframe(_disp[_show_cols].style.format(_fmt),
                              use_container_width=True, hide_index=True,
                              height=560)
                _n_idx = int(_disp["Structure_Source"].astype(str)
                             .str.startswith("index").sum()) if "Structure_Source" in _disp.columns else 0
                st.caption(
                    f"**Structure_Source** — `index:NAME` means Stage / Trend / RS / RRG "
                    f"were measured on that INDEX ({_n_idx} of {len(_disp)} rows); `etf` "
                    "means no NSE index exists for the exposure (gold, silver, Nasdaq, "
                    "FANG, S&P Top 50, Hang Seng, the cash park), so the ETF is the "
                    "correct series rather than a fallback. "
                    "**Turnover_60D_Cr** is the 60-day MEDIAN daily traded value — median, "
                    "not average, so one block deal cannot lift a thin ETF over the floor; "
                    "and rupees, not shares, because 20,000 units is ₹2 L on one fund and "
                    "₹321 L on another. It is the number your position size is judged "
                    "against, not AUM: Bharat Bond 2032 holds ₹10,408 Cr and trades "
                    "₹0.36 Cr/day. **ETFs have no BFF / RFF / Piotroski** — an ETF has no "
                    "P&L or balance sheet, so those are not applicable rather than missing.")

        # ─── TAB 5 — Vehicle & Chart ───────────────────────────────────────
        # WHY THIS TAB EXISTS: the universe now picks ONE vehicle per exposure, and it
        # does not always pick the one Jay has traded before - gold moved GOLDBEES ->
        # GOLDIETF and silver SILVERBEES -> SILVERIETF on expense ratio. A vehicle
        # change that is only visible as a different ticker in a results file is the
        # kind of thing you discover mid-trade. This shows the choice AND its reason.
        with _et5:
            section("Which vehicle, and which chart")
            st.caption(
                "**One tracker per exposure.** Candidates come from your AUM-curated "
                "workbook (Stage 1, human, occasional). Among those clearing the ₹0.5 Cr/day "
                "floor, the one with **ample liquidity (≥ ₹5 Cr/day) and the lowest expense "
                "ratio** wins; AUM breaks ties. Past the point where liquidity is sufficient "
                "for your size, extra turnover buys nothing while the fee is charged every "
                "year — GOLDIETF at ₹80 Cr/day and 0.42% beats GOLDBEES at ₹328 Cr/day and "
                "0.69%, because you cannot use the difference in liquidity but you do pay "
                "the difference in fee. "
                "**Chart column**: where to run PHASE-1 analysis. `index` = chart the index "
                "(clean series); `etf_only` = no NSE index exists, so chart the ETF.")
            try:
                import etf_index_map as _eim_ui
                _map_p = _eim_ui.MAP_CSV
                if not _os_etf.path.exists(_map_p):
                    _eim_ui.build()
                _mp = pd.read_csv(_map_p)
                try:
                    _prop = pd.read_csv(_os_etf.path.join(
                        _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                        "ETF_Universe_Proposed.csv"))
                    _mp = _mp.merge(_prop[[c for c in ("Symbol", "ter_pct", "turnover_cr",
                                                       "aum_cr", "selected_from", "reason")
                                           if c in _prop.columns]],
                                    left_on="trade_symbol", right_on="Symbol", how="left")
                except Exception:
                    pass
                _c1, _c2, _c3 = st.columns(3)
                _c1.metric("Exposures", len(_mp))
                _c2.metric("Chart the index", int((_mp["chart_mode"] == "index").sum()))
                _c3.metric("Chart the ETF", int((_mp["chart_mode"] != "index").sum()))
                _cols = [c for c in ("exposure", "trade_symbol", "liquidity_tier",
                                     "turnover_cr", "ter_pct", "aum_cr", "selected_from",
                                     "chart_mode", "tv_index", "dhan_index",
                                     "index_status", "reason") if c in _mp.columns]
                st.dataframe(_mp[_cols].sort_values("exposure"),
                             use_container_width=True, hide_index=True, height=520)
                st.caption(
                    "`tv_index` is the TradingView symbol for PHASE-1 analysis; "
                    "`dhan_index` is what GM computes structure from. **They differ and "
                    "neither derives from the other** — Dhan's `NIFTYNXT50` is TradingView's "
                    "`NIFTYJR`, Dhan's `NIFTYCPSE` is `CPSE` — which is why this is a table "
                    "read back from both feeds rather than a naming rule. "
                    "`selected_from` is how many trackers competed for that exposure; "
                    "`reason` records whether the winner was *cheapest of the amply liquid* "
                    "or *most liquid (none ample)*. "
                    "**`index_status = no NSE index`** (gold, silver, Nasdaq, FANG, S&P Top 50, "
                    "Hang Seng, cash park) is not a gap — there is no Indian index to chart.")
            except Exception as _e_map:
                st.warning(f"Index map unavailable: {_e_map}")
