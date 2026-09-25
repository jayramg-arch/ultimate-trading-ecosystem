# commander_pages/news.py - the NEWS page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('news', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📰 Financial News & Sentiment</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live RSS feeds from ET, Moneycontrol, Business Standard, LiveMint, NDTV Profit — keyword sentiment scoring</div>', unsafe_allow_html=True)

    if not _NEWS_OK:
        st.error("❌ news_feed module not available. Run: pip install feedparser")
    else:
        # ── Controls ─────────────────────────────────────────────────────────
        c1, c2, c3 = st.columns([1, 2, 3])
        with c1:
            _nw_refresh = st.button("🔄 Refresh", key="nw_refresh", type="primary")
        with c2:
            _nw_max = st.selectbox("Max per feed", [10, 15, 20], index=1, key="nw_max")
        with c3:
            _all_src_opts = ["Economic Times Markets","Economic Times Stocks",
                             "CNBCTV18 Markets","Business Standard",
                             "Business Standard Co.","LiveMint Markets",
                             "LiveMint Companies","NDTV Profit"]
            _nw_src = st.multiselect("Sources", _all_src_opts,
                default=["Economic Times Markets","CNBCTV18 Markets",
                         "Business Standard","LiveMint Markets"],
                key="nw_sources")

        if _nw_refresh:
            try:
                from news_feed import _cache as _nw_cache_store
                _nw_cache_store.clear()
            except Exception:
                pass

        _nw_df = pd.DataFrame()
        _nw_health = {}
        with st.spinner("Fetching live news feeds..."):
            try:
                _nw_df = fetch_all_news(max_per_feed=_nw_max)
                _nw_df = add_sentiment(_nw_df)
                if _nw_src and not _nw_df.empty:
                    _nw_df = _nw_df[_nw_df["source"].isin(_nw_src)]
                try:
                    from news_feed import get_last_feed_health as _glfh
                    _nw_health = _glfh() or {}
                except Exception:
                    _nw_health = {}
            except Exception as _ne:
                st.error(f"News fetch failed: {_ne}")

        # Per-feed status pill — replaces the old behaviour of injecting
        # "Feed unavailable" placeholder rows into the headline list.
        if _nw_health:
            _bad = {k: v for k, v in _nw_health.items() if v != "ok"}
            if _bad:
                _bad_lines = " · ".join(f"<b>{k}</b>: {v}" for k, v in _bad.items())
                st.markdown(
                    f"<div style='font-size:0.72rem;color:var(--warn);"
                    f"background:rgba(227,179,65,0.08);padding:6px 10px;"
                    f"border-left:3px solid var(--warn);border-radius:4px;margin-bottom:8px'>"
                    f"⚠ {len(_bad)}/{len(_nw_health)} feed(s) unavailable — "
                    f"others loaded normally. {_bad_lines}"
                    f"</div>", unsafe_allow_html=True)

        # ── Sentiment summary bar ─────────────────────────────────────────────
        if not _nw_df.empty and "sentiment" in _nw_df.columns:
            _bull = int((_nw_df["sentiment"].str.contains("Bullish", case=False, na=False)).sum())
            _bear = int((_nw_df["sentiment"].str.contains("Bearish", case=False, na=False)).sum())
            _neut = len(_nw_df) - _bull - _bear
            _score = round((_bull - _bear) / max(len(_nw_df), 1) * 100, 1)
            _score_lbl = "BULLISH" if _score > 10 else "BEARISH" if _score < -10 else "NEUTRAL"
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Headlines", len(_nw_df))
            m2.metric("🟢 Bullish", _bull)
            m3.metric("🔴 Bearish", _bear)
            m4.metric("⬜ Neutral", _neut)
            m5.metric("Sentiment", f"{_score:+.1f}%", delta=_score_lbl,
                      delta_color="off" if _score_lbl == "BEARISH" else "normal")

        st.markdown("---")

        # Source colour tags — matches the paid grid convention so both tabs
        # feel visually consistent.
        _RSS_SRC_COL = {
            "Economic Times Markets": "#ff7b72",
            "Economic Times Stocks":  "#ff7b72",
            "CNBCTV18 Markets":       "var(--acc)",
            "Business Standard":      "var(--warn)",
            "Business Standard Co.":  "var(--warn)",
            "LiveMint Markets":       "#a371f7",
            "LiveMint Companies":     "#a371f7",
            "NDTV Profit":            "#3fb950",
        }

        def _news_card_html(row) -> str:
            """Return one news card matching the paid-grid card style."""
            _sent    = str(row.get("sentiment", "🟡 Neutral"))
            _sent_c  = str(row.get("sentiment_color", "var(--warn)"))
            _src     = str(row.get("source", ""))
            _src_c   = _RSS_SRC_COL.get(_src, "var(--muted)")
            _ts      = str(row.get("published_ts", ""))[:16]
            _title   = str(row.get("title", "")).replace("<", "&lt;").replace(">", "&gt;")
            _link    = str(row.get("link", "#")) or "#"
            _summ    = str(row.get("summary", ""))[:160].replace("<", "&lt;").replace(">", "&gt;")
            if len(str(row.get("summary", ""))) > 160:
                _summ += "…"
            return (
                f'<div class="metric-card" style="padding:10px 12px;'
                f'margin-bottom:8px;min-height:150px;border-left:3px solid {_sent_c}">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;margin-bottom:5px">'
                f'<span style="color:{_sent_c};font-size:0.62rem;'
                f'font-weight:700;letter-spacing:0.5px">{_sent}</span>'
                f'<span style="color:{_src_c};font-size:0.6rem;'
                f'font-weight:600">{_src}</span></div>'
                f'<div style="font-size:0.78rem;color:var(--ink);line-height:1.3">'
                f'<a href="{_link}" target="_blank" '
                f'style="color:var(--ink);text-decoration:none">{_title}</a></div>'
                f'<div style="font-size:0.66rem;color:var(--muted);'
                f'margin-top:6px;line-height:1.35">{_summ}</div>'
                f'<div style="font-size:0.58rem;color:var(--ink);margin-top:6px">{_ts}</div>'
                f'</div>'
            )

        def _render_news_grid(df, n_cols: int = 4):
            """Render the news DataFrame as an n-column responsive card grid."""
            if df is None or df.empty:
                return
            _rows = list(df.to_dict("records"))
            for _i in range(0, len(_rows), n_cols):
                _chunk = _rows[_i:_i + n_cols]
                _cols = st.columns(n_cols, gap="small")
                for _col, _r in zip(_cols, _chunk):
                    with _col:
                        st.markdown(_news_card_html(_r), unsafe_allow_html=True)

        # Back-compat: keep single-row renderer in case other call sites use it.
        def _render_news_row(row):
            st.markdown(_news_card_html(row), unsafe_allow_html=True)

        # ── Inline tabs ───────────────────────────────────────────────────────
        _nw_tab1, _nw_tab3, _nw_tab2 = st.tabs([
            "📰 Market News (Free RSS)",
            "💎 ET Prime + MC Pro",
            "🔍 Stock Filter",
        ])

        with _nw_tab1:
            section("Market Headlines — Sorted by Recency")
            if _nw_df.empty:
                st.info("No news fetched. Check network or try refreshing.")
            else:
                _nw_ncols = st.select_slider(
                    "Columns", options=[1, 2, 3, 4, 5], value=4,
                    key="nw_free_cols",
                    help="Adjust grid density for the headline cards.")
                _render_news_grid(_nw_df, n_cols=int(_nw_ncols))

        with _nw_tab3:
            section("ET Prime + Moneycontrol Pro — Analyst Recos & News")
            _render_paid_news_grid(
                key_prefix="news_paid",
                keyword_filter=None,
                default_limit=40,
                show_recos_only=False,
                caption=("Live pull from your paid ET Prime + MC Pro sessions. "
                         "Cards are colour-coded by analyst action (Buy / Hold / Sell). "
                         "Cached 1h — click **Refresh** to force a re-fetch."),
            )

        with _nw_tab2:
            section("Stock-Specific News Filter")
            _sym_input = st.text_input(
                "Enter stock name or NSE symbol (e.g. RELIANCE, Infosys, HDFC)",
                key="nw_sym").strip()
            if _sym_input and not _nw_df.empty:
                try:
                    _stk_df = filter_by_symbol(_nw_df, _sym_input)
                except Exception as _fbe:
                    _stk_df = pd.DataFrame()
                    st.error(f"Filter error: {_fbe}")
                if not _stk_df.empty:
                    st.caption(f"**{len(_stk_df)}** headlines mentioning **{_sym_input}**")
                    _render_news_grid(_stk_df, n_cols=4)
                else:
                    st.info(f"No headlines found mentioning **{_sym_input}**.")
            elif not _sym_input:
                st.info("Enter a symbol or company name above to filter headlines.")
