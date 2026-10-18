# commander_pages/v2_live.py - the v2 SYSTEM page (18-Oct-2026, Doc 42 §8 D5).
#
# The live, real-money view of the v2 system. Its paper books stay on 🧭 PAPER · v2 SYSTEM.
# Status strip · this week (checklist, your orders, reviewer rulings) · your v2 book · rank board
# · ETF pool · risk · trailing · rules. Reads what the nightly engine wrote (p1_paper.py, Phase
# 4.79) and the v2 ledger; nothing here places an order.
# Runs in the app's namespace via commander_pages.run('v2_live', globals()).
if True:
    import os as _os
    import json as _json
    import datetime as _dt
    import pandas as _pd
    import p1_paper as _p1
    import v2_core as _v2
    import v2_house as _vh
    import v2_ledger as _vl

    _inr = _p1._inr
    st.markdown('<div class="page-title">🧭 v2 System</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">A weekly ranked portfolio (Clenow\'s <i>Stocks on the Move</i>, ensemble rank, '
                'house rules) for real money, beside the current system. Decided at Tuesday\'s close, placed at '
                'Wednesday\'s open. Workflow: Doc 42 · design and evidence: Doc 41. Paper books: '
                'ANALYSIS › 🧭 PAPER · v2 SYSTEM.</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=900, show_spinner=False)
    def _v2_bench():
        import data_provider as _dp
        b = _dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d", use_cache=True)
        c = b["Close"].dropna()
        return float(c.iloc[-1]), float(c.rolling(200).mean().iloc[-1]), str(_pd.Timestamp(c.index[-1]).date())

    @st.cache_data(ttl=900, show_spinner=False)
    def _v2_last(syms: tuple):
        import data_provider as _dp
        out = {}
        for s in syms:
            try:
                d = _dp.fetch_ohlcv(s, period="3mo", interval="1d", use_cache=True)
                out[s] = float(d["Close"].dropna().iloc[-1])
            except Exception:
                pass
        return out

    def _next_decision():
        try:
            import nse_calendar as _nc
            d = _dt.date.today()
            for _ in range(15):
                n = _vh._next_session(d)
                if _nc.is_trading_day(d) and _vh.is_wed_decision(_pd.Timestamp(d), _pd.Timestamp(n)):
                    return d, n
                d = d + _dt.timedelta(days=1)
        except Exception:
            pass
        return None, None

    _st = _p1.load_state("V2H")
    _pend = _st.get("pending") or {}
    _bd = _v2.board()
    _led = _vl.load()
    _held = _led["open"]
    _cap = _p1.v2_capital()
    _px = _v2_last(tuple(sorted(_held)))
    _inv = sum(q["sh"] * _px.get(s, q["entry"]) for s, q in _held.items())
    _cost = sum(q["sh"] * q["entry"] for q in _held.values())
    _eq = _cap + _vl.realised() + (_inv - _cost)
    try:
        _b_last, _b_200, _b_date = _v2_bench()
    except Exception:
        _b_last = _b_200 = None
        _b_date = "-"
    _nd, _nf = _next_decision()

    # ── status strip ───────────────────────────────────────────────────────
    _c = st.columns(6)
    if _b_last and _b_200:
        _up = _b_last > _b_200
        _c[0].metric("Regime", "UP · buys allowed" if _up else "DOWN · no new buys",
                     "%+.1f%% vs 200-DMA" % ((_b_last / _b_200 - 1) * 100),
                     help="Nifty 500 close %.0f vs its 200-day SMA %.0f (%s). v2 buys only when above." % (_b_last, _b_200, _b_date))
    else:
        _c[0].metric("Regime", "—")
    _c[1].metric("Next decision", _nd.strftime("%a %d-%b") if _nd else "—",
                 ("fill %s" % _nf.strftime("%a %d-%b")) if _nf else None)
    _c[2].metric("v2 capital", _inr(_cap), help="One-third of the house sizing capital (V2_CAPITAL in .env overrides).")
    _c[3].metric("v2 equity", _inr(_eq), "%+.2f%%" % ((_eq / _cap - 1) * 100) if _cap else None)
    _c[4].metric("Cash", _inr(_eq - _inv))
    _c[5].metric("Holdings", "%d" % len(_held), "%d shared with the current system" % sum(1 for q in _held.values() if q.get("shared")))

    _tabs = st.tabs(["🗓️ This week", "📂 Your v2 book", "📋 Rank board", "🪙 ETF pool", "🛡️ Risk", "📈 Trailing", "📘 Rules"])

    # ── this week ──────────────────────────────────────────────────────────
    with _tabs[0]:
        _dec = _pend.get("decided")
        _wl_ok = _os.path.exists(_p1.V2_WATCHLIST)
        _rv = _v2.latest_reviews(_dec) if _dec else {}
        _buys = [b[0] for b in _pend.get("buys", [])]
        _since = [q for q in _held.values() if _dec and str(q.get("entry_date")) >= str(_dec)]
        st.markdown("**The weekly cycle** (Doc 42 §2)")
        _steps = [
            ("Tue 16:30 · decision at the close (auto-pilot Phase 4.79)", bool(_dec), "decided %s" % _dec if _dec else "no V2H decision yet"),
            ("Tue · watchlist V2_System pushed to TradingView", _wl_ok, "FINAL_V2_WATCHLIST.csv written" if _wl_ok else "not written"),
            ("Tue · reviewer rulings on the buys", (not _buys) or all(b in _rv for b in _buys),
             ("%d of %d reviewed" % (sum(1 for b in _buys if b in _rv), len(_buys))) if _buys else "no buys this week"),
            ("Tue evening · your review: this page + V2_System on a Daily chart (S4, S5, Add-ons)", None, "you"),
            ("Wed 09:15 · orders at the open (limit at Tuesday's close + 1 %, cancel by 10:00) + one Dhan stop per buy", None, "you"),
            ("Wed · record each fill: python v2_take.py SYM --price P --qty Q", (not _buys) or bool(_since),
             ("%d slice(s) recorded since the decision" % len(_since)) if _buys else "nothing to record"),
        ]
        for _t, _ok, _note in _steps:
            st.markdown("%s %s · <span style='color:var(--muted)'>%s</span>" % (
                "✅" if _ok else ("⏳" if _ok is False else "👤"), _t, _note), unsafe_allow_html=True)
        st.markdown("---")
        _ord = sorted(f for f in _os.listdir(_p1.REPORT_DIR) if f.startswith("orders_") and f.endswith(".md")) \
            if _os.path.isdir(_p1.REPORT_DIR) else []
        _yours = ""
        if _ord:
            _txt = open(_os.path.join(_p1.REPORT_DIR, _ord[-1]), encoding="utf-8").read()
            _k = _txt.find("## YOUR v2 ORDERS")
            _yours = _txt[_k:] if _k >= 0 else ""
        if _yours:
            st.markdown(_yours)
        else:
            st.info("No orders for your book yet - the first V2H decision is %s's close." % (_nd.strftime("%A %d-%b") if _nd else "the next Tuesday"))
        if _buys:
            st.markdown("**Reviewer on this week's buys** (execution check; WAIT / PASS = skip this week):")
            st.dataframe(_pd.DataFrame([{"symbol": s, "ruling": _rv.get(s, "not reviewed yet")} for s in _buys]),
                         hide_index=True, use_container_width=True)

    # ── your v2 book ───────────────────────────────────────────────────────
    with _tabs[1]:
        if not _held:
            st.info("You hold no v2 shares yet. Fills are recorded with `python v2_take.py SYMBOL --price P --qty Q` "
                    "(a pyramid onto a current-system holding is recorded the same way; the journal row stays).")
        else:
            _rank = _bd.set_index("symbol") if len(_bd) else _pd.DataFrame()
            _n = int(_bd["eligible"].iloc[0]) if len(_bd) else 0
            _rows = []
            for s, q in sorted(_held.items()):
                lp = _px.get(s, q["entry"])
                rk = _rank["rank"].get(s) if len(_rank) else None
                inc = bool(_rank["in_cut"].get(s)) if len(_rank) and s in _rank.index else False
                _rows.append({"symbol": s, "shares": q["sh"], "entry": round(q["entry"], 2), "last": round(lp, 2),
                              "P&L %": round((lp / q["entry"] - 1) * 100, 1), "value": _inr(q["sh"] * lp),
                              "stop": q.get("stop"), "rank": ("%d / %d" % (rk, _n)) if rk == rk and rk is not None else "out",
                              "next Tuesday": "HOLD (in the top 25 %)" if inc else "SELL unless it re-enters the cut",
                              "since": q["entry_date"], "shared": "with the current system" if q.get("shared") else ""})
            st.dataframe(_pd.DataFrame(_rows), hide_index=True, use_container_width=True)
            st.caption("Stop = the slice's disaster stop when bought; the resting Dhan stop (one per holding) is "
                       "raised by the trail - see 📈 Trailing.")
        if _led["closed"]:
            with st.expander("Closed v2 slices (%d) · realised %s" % (len(_led["closed"]), _inr(_vl.realised()))):
                st.dataframe(_pd.DataFrame(_led["closed"]), hide_index=True, use_container_width=True)

    # ── rank board ─────────────────────────────────────────────────────────
    with _tabs[2]:
        if not len(_bd):
            st.info("No board yet - written nightly by the auto-pilot (Phase 4.79).")
        else:
            @st.cache_data(ttl=3600, show_spinner=False)
            def _v2_sectors(syms: tuple):
                return _vh.sector_map(list(syms))
            _sec = _v2_sectors(tuple(_bd["symbol"]))
            _b = _bd.copy()
            _b["sector"] = _b["symbol"].map(_sec).fillna("—")
            _f = st.columns(4)
            _only_cut = _f[0].checkbox("Top 25 % only", value=True, key="v2l_cut")
            _only_fno = _f[1].checkbox("F&O only", value=False, key="v2l_fno")
            _secs = _f[2].multiselect("Sector", sorted(_b["sector"].unique()), key="v2l_sec")
            _q = _f[3].text_input("Symbol", key="v2l_q").strip().upper()
            if _only_cut:
                _b = _b[_b["in_cut"]]
            if _only_fno and "fno" in _b.columns:
                _b = _b[_b["fno"]]
            if _secs:
                _b = _b[_b["sector"].isin(_secs)]
            if _q:
                _b = _b[_b["symbol"].str.contains(_q)]
            _b["held"] = _b["symbol"].map(lambda s: "v2" if s in _held else "")
            st.dataframe(_b[[c for c in ["rank", "symbol", "sector", "score", "close", "atr20", "in_cut", "fno", "held", "action"]
                              if c in _b.columns]], hide_index=True, use_container_width=True,
                         column_config={"score": st.column_config.NumberColumn("score", format="%.3f"),
                                        "in_cut": st.column_config.CheckboxColumn("top 25 %"),
                                        "fno": st.column_config.CheckboxColumn("F&O")})
            st.caption("As of %s · %d eligible (above the 100-DMA, no 15 %% day in 90 sessions, ≥ ₹5 crore turnover). "
                       "Rank = mean percentile of the 60/90/120-session trend-quality scores." % (
                           _bd["as_of"].iloc[0], int(_bd["eligible"].iloc[0])))

    # ── ETF pool ───────────────────────────────────────────────────────────
    with _tabs[3]:
        @st.cache_data(ttl=3600, show_spinner=False)
        def _v2_prem():
            try:
                import etf_inav
                return etf_inav.premium_map()
            except Exception:
                return {}
        _pm = _v2_prem()
        _pool = _vh.etf_pool()
        _ew = {x[0]: x[1] for x in (_pend.get("etf_watch") or [])}
        _po = _pend.get("etf_premium_out") or {}
        st.dataframe(_pd.DataFrame([{"ETF": s, "class": m.get("asset_class"), "underlying": m.get("underlying"),
                                     "premium vs NAV %": _pm.get(s), "rank score": _ew.get(s),
                                     "status": ("OUT - premium" if s in _po else ("ranked" if s in _ew else "not eligible"))}
                                    for s, m in sorted(_pool.items())]), hide_index=True, use_container_width=True)
        st.caption("ETFs are ranked only against each other, one per underlying, ≥ ₹2 crore turnover; Indian-equity ETFs "
                   "follow the stock regime, gold / silver / international their own 200-DMA; out of the pool when the "
                   "price is more than 3 % from NAV (T-1). Holds the top 25 % (2 to 5), ≤ 10 % each, ≤ 30 % in all.")

    # ── risk ───────────────────────────────────────────────────────────────
    with _tabs[4]:
        import house_policy as _hp
        if not _held:
            st.info("No v2 holdings - nothing at risk.")
        else:
            _sec = _vh.sector_map(list(_held))
            _cap_pos = _hp.MAX_ALLOC_DEFAULT / _hp.CAPITAL_DEFAULT * _eq
            _r = []
            _by = {}
            for s, q in _held.items():
                v = q["sh"] * _px.get(s, q["entry"])
                _by[_sec.get(s, "unknown")] = _by.get(_sec.get(s, "unknown"), 0.0) + v
                _r.append({"symbol": s, "value": _inr(v), "% of v2 equity": round(v / _eq * 100, 1) if _eq else None,
                           "over the per-name cap": "YES" if v > _cap_pos * 1.05 else "",
                           "risk to stop": _inr(max(0.0, (_px.get(s, q["entry"]) - float(q.get("stop") or 0)) * q["sh"]))})
            st.dataframe(_pd.DataFrame(_r), hide_index=True, use_container_width=True)
            st.dataframe(_pd.DataFrame([{"sector": k, "% of v2 equity": round(v / _eq * 100, 1),
                                         "cap": "%g %%" % _hp.SECTOR_CAP_PCT,
                                         "status": "OVER" if v / _eq * 100 > _hp.SECTOR_CAP_PCT else "ok"}
                                        for k, v in sorted(_by.items(), key=lambda kv: -kv[1])]),
                         hide_index=True, use_container_width=True)
            st.caption("v2 is held to its own limits: per-name cap %.2f %% of equity at entry, sector cap %g %%. The "
                       "house open-risk budget and the 25-position limit apply to the current system only (Doc 42 D1)."
                       % (_hp.MAX_ALLOC_DEFAULT / _hp.CAPITAL_DEFAULT * 100, _hp.SECTOR_CAP_PCT))

    # ── trailing ───────────────────────────────────────────────────────────
    with _tabs[5]:
        st.markdown("The trail raises the resting Dhan stop of every **positional** holding (v2 and the current "
                    "system; swing trades are not trailed) to the house Chandelier, never closer than 3 × ATR14 to the "
                    "close, raise-only, once a day at 15:45. **Dry run**: the evening Telegram lists the moves; nothing "
                    "changes at Dhan until it is switched live (needs the static IP registered with Dhan).")
        if st.button("Compute today's trail proposals (reads Dhan)", key="v2l_trail"):
            try:
                import gtt_auto_shield as _gas
                _pr, _br, _er = _gas.build_trail_proposals()
                if _er:
                    st.error(_er)
                else:
                    st.dataframe(_pd.DataFrame([{"symbol": s, "order": l["order_id"], "stop now": o, "would rise to": n,
                                                 "v2": "v2" if s in _held else "", "source": nt}
                                                for s, l, o, n, _m, _s, nt in _pr]), hide_index=True, use_container_width=True)
                    if _br:
                        st.warning("Exit review (trail at/above the close): " + ", ".join(sorted({b[0] for b in _br})))
                    _sk = {}
                    for s, why in _gas.LAST_SKIPPED:
                        _sk.setdefault(why, set()).add(s)
                    for why, ss in _sk.items():
                        st.caption("Not trailed - %s: %s" % (why, ", ".join(sorted(ss))))
            except Exception as e:
                st.error("trail proposals failed: %s" % e)

    # ── rules ──────────────────────────────────────────────────────────────
    with _tabs[6]:
        st.markdown(
            "| Layer | Rule |\n|---|---|\n"
            "| Regime | new buys only when the Nifty 500 closes above its 200-day SMA |\n"
            "| Eligible | above the 100-DMA · no single-day move over 15 % in 90 sessions · ≥ ₹5 crore median turnover |\n"
            "| Rank | trend quality (exp. regression slope × R²), percentile-averaged over 60/90/120 sessions |\n"
            "| Hold / sell | weekly: hold inside the top 25 %; sell outside it (a profitable 300–364-day holding may stay in the top 50 %) |\n"
            "| Size | 0.10 % of equity per ATR20 · per-name cap 3.33 % · sector cap 25 % · correlation block 0.90 |\n"
            "| Stops | disaster stop entry − 4 × ATR14 · house Chandelier trail (capped at close − 3 × ATR14) |\n"
            "| Partials / pyramid | monthly trim when risk > 1.5 × target · top-up when risk < 0.5 × target |\n"
            "| ETFs | own pool, NAV premium ≤ 3 %, 2–5 held, ≤ 10 % each / 30 % in all |\n"
            "| Guards | results within 7 days → wait a week · reviewer WAIT/PASS → skip a week · stale data never sells |\n"
            "| Shared holdings | v2 may pyramid onto a current-system holding: one journal row, one stop for all shares |\n")
        st.caption("Evidence (survivorship-corrected backtest 2018–2026, costs in): CAGR ~17 %, max drawdown ~20 %, "
                   "return ÷ drawdown 0.74 / 1.12 in the two halves; after tax ~15.5 %. Docs 41 and 42, "
                   "PREREG_v2_house_rules, PREREG_v2_borrowed_rules.")
