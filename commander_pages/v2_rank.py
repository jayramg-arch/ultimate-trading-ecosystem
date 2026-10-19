# commander_pages/v2_rank.py - 📋 v2 · RANK & UNIVERSE (19-Oct-2026).
#
# The weekly ranked list and why a name is in or out of it, the ETF pool, the Nifty 500
# joiners/leavers, and the rules with their evidence. Reads data/v2/board.csv (+ its daily
# copies in data/v2/board_history), logs/universe_changes.csv and the price cache. Read-only.
# Runs in the app's namespace via commander_pages.run('v2_rank', globals()).
if True:
    import json as _json
    import os as _os
    import sqlite3 as _sq
    import numpy as _np
    import pandas as _pd
    import journal_path as _jp
    import v2_house as _vh
    import v2_ui as _ui

    _ui.page_head("📋 v2 · Rank & Universe",
                  "Every eligible Nifty 500 stock ranked by trend quality (exponential-regression slope × R², averaged "
                  "over 60/90/120 sessions). v2 holds the top 25 %; a name leaves when it drops out, closes below its "
                  "100-day average, makes a one-day move beyond 15 % in 90 sessions, leaves the index, or goes under "
                  "NSE surveillance.")
    _c = _ui.load()
    _ui.status_strip(_c)
    _bd, _held, _pend = _c["board"], _c["held"], _c["pend"]

    def _v1_open():
        try:
            con = _sq.connect(_jp.JOURNAL_DB)
            r = con.execute("SELECT UPPER(symbol), COALESCE(setup,'') FROM journal WHERE UPPER(status)='OPEN'").fetchall()
            con.close()
            return {s for s, su in r if not su.upper().startswith("POS-V2")}
        except Exception:
            return set()
    _v1 = _v1_open()

    _t = st.tabs(["📋 Rank board", "🔎 Why in / why out", "🪙 ETF pool", "🌐 Universe", "📘 Rules & evidence"])

    # ── rank board ────────────────────────────────────────────────────────
    with _t[0]:
        if not len(_bd):
            st.info("No board yet - written nightly by the auto-pilot (Phase 4.79).")
        else:
            @st.cache_data(ttl=3600, show_spinner=False)
            def _v2r_sectors(syms: tuple):
                return _vh.sector_map(list(syms))
            _b = _bd.copy()
            _b["sector"] = _b["symbol"].map(_v2r_sectors(tuple(_b["symbol"]))).fillna("—")
            _f = st.columns(4)
            _only_cut = _f[0].checkbox("Top 25 % only", value=True, key="v2r_cut")
            _only_fno = _f[1].checkbox("F&O only", value=False, key="v2r_fno")
            _secs = _f[2].multiselect("Sector", sorted(_b["sector"].unique()), key="v2r_sec")
            _q = _f[3].text_input("Symbol", key="v2r_q").strip().upper()
            if _only_cut:
                _b = _b[_b["in_cut"].astype(str).str.lower() == "true"]
            if _only_fno and "fno" in _b.columns:
                _b = _b[_b["fno"].astype(str).str.lower() == "true"]
            if _secs:
                _b = _b[_b["sector"].isin(_secs)]
            if _q:
                _b = _b[_b["symbol"].str.contains(_q)]
            _b["holder"] = _b["symbol"].map(lambda s: "v2" if s in _held else ("v1 (a v2 buy = CONVERT)" if s in _v1 else ""))
            st.dataframe(_b[[c for c in ["rank", "symbol", "sector", "score", "close", "atr20", "in_cut", "fno", "holder", "action"]
                             if c in _b.columns]], hide_index=True, use_container_width=True,
                         column_config={"score": st.column_config.NumberColumn("score", format="%.3f"),
                                        "in_cut": st.column_config.CheckboxColumn("top 25 %"),
                                        "fno": st.column_config.CheckboxColumn("F&O")})
            st.caption("As of %s · %d eligible (above the 100-DMA, no 15 %% day in 90 sessions, ≥ ₹5 crore median "
                       "turnover, not under surveillance). F&O is a display tag only." % (
                           _bd["as_of"].iloc[0], int(_bd["eligible"].iloc[0])))

    # ── why in / why out ──────────────────────────────────────────────────
    with _t[1]:
        _hd = _os.path.join(_os.path.dirname(_os.path.abspath(_vh.__file__)), "data", "v2", "board_history")
        _hist = sorted(f for f in _os.listdir(_hd) if f.startswith("board_")) if _os.path.isdir(_hd) else []
        if len(_hist) >= 2:
            _a = _pd.read_csv(_os.path.join(_hd, _hist[-2]))
            _z = _pd.read_csv(_os.path.join(_hd, _hist[-1]))
            _ca = set(_a.loc[_a["in_cut"].astype(str).str.lower() == "true", "symbol"])
            _cz = set(_z.loc[_z["in_cut"].astype(str).str.lower() == "true", "symbol"])
            st.markdown("**Top 25 %% since the previous board** (%s → %s): entered **%d**, left **%d**" % (
                _hist[-2][6:16], _hist[-1][6:16], len(_cz - _ca), len(_ca - _cz)))
            _x = st.columns(2)
            _x[0].markdown("Entered: " + (", ".join(sorted(_cz - _ca)) or "—"))
            _x[1].markdown("Left: " + (", ".join(sorted(_ca - _cz)) or "—"))
        else:
            st.caption("Board-to-board changes appear once two nightly boards are on file (data/v2/board_history).")
        st.markdown("---")
        _sym = st.text_input("Check a symbol against every v2 rule", key="v2r_why").strip().upper().replace("NSE:", "")

        @st.cache_data(ttl=1800, show_spinner="Reading the rules for the symbol…")
        def _v2r_explain(sym: str):
            import data_provider as dp
            import v2_backtest as vb
            d = dp.fetch_ohlcv(sym, period="1y", interval="1d", use_cache=True)
            if d is None or len(d) < 100:
                return None
            C, V = d["Close"].dropna(), d["Volume"]
            sma = float(C.rolling(100).mean().iloc[-1])
            mv = float(C.pct_change().abs().tail(90).max() * 100)
            to = float((C * V).rolling(50).median().iloc[-1])
            return {"close": float(C.iloc[-1]), "sma100": sma, "max_move": mv, "turnover": to,
                    "liq_min": float(vb.TURNOVER_MIN), "as_of": str(C.index[-1])[:10]}
        if _sym:
            try:
                _uni = {x.replace(".NS", "").upper() for x in _json.load(open(_os.path.join(
                    _os.path.dirname(_os.path.abspath(_vh.__file__)), "nifty500_symbols.json")))}
            except Exception:
                _uni = set()
            try:
                import nse_surveillance as _ns
                _sv, _svn = _ns.excluded()
            except Exception as _e:
                _sv, _svn = None, "surveillance list unavailable (%s)" % _e
            _ex = _v2r_explain(_sym)
            _row = _bd[_bd["symbol"] == _sym] if len(_bd) else _pd.DataFrame()
            _n_cut = int(_bd["in_cut"].astype(str).str.lower().eq("true").sum()) if len(_bd) else 0
            _chk = [("In the Nifty 500 (refreshed nightly)", _sym in _uni if _uni else None, "")]
            if _ex:
                _chk += [("Close above its 100-day average", _ex["close"] > _ex["sma100"],
                          "close %.2f vs 100-DMA %.2f (%+.1f %%)" % (_ex["close"], _ex["sma100"], (_ex["close"] / _ex["sma100"] - 1) * 100)),
                         ("No one-day move beyond 15 % in 90 sessions", _ex["max_move"] <= 15, "largest %.1f %%" % _ex["max_move"]),
                         ("Median turnover ≥ ₹5 crore (50 sessions)", _ex["turnover"] >= _ex["liq_min"],
                          "₹%.1f crore" % (_ex["turnover"] / 1e7))]
            _chk.append(("Not under NSE surveillance", (_sym not in _sv) if _sv is not None else None,
                         (_sv or {}).get(_sym, "") or _svn))
            if len(_row):
                _rk = _row["rank"].iloc[0]
                _chk.append(("Inside the top 25 %% (rank ≤ %d)" % _n_cut, bool(_rk == _rk and _rk <= _n_cut),
                             "rank %s of %d" % (int(_rk) if _rk == _rk else "—", int(_bd["eligible"].iloc[0]))))
            else:
                _chk.append(("Ranked on the latest board", False, "not eligible at the last close"))
            for _lbl, _ok, _nt in _chk:
                st.markdown("%s %s · <span style='color:var(--muted)'>%s</span>" % (
                    "✅" if _ok else ("❔" if _ok is None else "❌"), _lbl, _nt), unsafe_allow_html=True)
            st.caption(("Holder: v2" if _sym in _held else "Holder: v1 - a v2 buy would CONVERT it" if _sym in _v1 else "Not held")
                       + (" · prices as of %s" % _ex["as_of"] if _ex else " · no price history"))

    # ── ETF pool ──────────────────────────────────────────────────────────
    with _t[2]:
        @st.cache_data(ttl=3600, show_spinner=False)
        def _v2r_prem():
            try:
                import etf_inav
                return etf_inav.premium_map()
            except Exception:
                return {}
        _pm = _v2r_prem()
        _pool = _vh.etf_pool()
        _ew = {x[0]: x[1] for x in (_pend.get("etf_watch") or [])}
        _po = _pend.get("etf_premium_out") or {}
        st.dataframe(_pd.DataFrame([{"ETF": s, "class": m.get("asset_class"), "underlying": m.get("underlying"),
                                     "premium vs NAV %": _pm.get(s), "rank score": _ew.get(s),
                                     "held": "v2" if s in _held else "",
                                     "status": ("OUT - premium" if s in _po else ("ranked" if s in _ew else "not eligible"))}
                                    for s, m in sorted(_pool.items())]), hide_index=True, use_container_width=True)
        st.caption("ETFs are ranked only against each other, one per underlying, ≥ ₹2 crore turnover; Indian-equity ETFs "
                   "follow the stock regime, gold / silver / international their own 200-DMA; out of the pool when the "
                   "price is more than 3 % from NAV (T-1). Holds the top 25 % (2 to 5), ≤ 10 % each, ≤ 30 % in all.")

    # ── universe ──────────────────────────────────────────────────────────
    with _t[3]:
        _uc = _os.path.join(_os.path.dirname(_os.path.abspath(_vh.__file__)), "logs", "universe_changes.csv")
        if _os.path.exists(_uc):
            _U = _pd.read_csv(_uc).sort_values(["date", "change", "symbol"], ascending=[False, True, True])
            _lh = sorted(set(_U.loc[_U["change"] == "left", "symbol"]) & set(_held))
            if _lh:
                st.error("v2 holds names that LEFT the Nifty 500 (an exit at the next open): " + ", ".join(_lh))
            for _d, _g in list(_U.groupby("date", sort=False))[:6]:
                st.markdown("**%s** · joined %d: %s<br>left %d: %s" % (
                    _d, (_g["change"] == "joined").sum(), ", ".join(_g.loc[_g["change"] == "joined", "symbol"]) or "—",
                    (_g["change"] == "left").sum(), ", ".join(_g.loc[_g["change"] == "left", "symbol"]) or "—"),
                    unsafe_allow_html=True)
        else:
            st.info("No universe changes recorded yet (logs/universe_changes.csv, written by the nightly refresh).")
        st.caption("The universe is NSE's official Nifty 500 list, refreshed every evening (auto-pilot Phase 0.6); REITs/InvITs "
                   "and non-EQ series are left out.")

    # ── rules & evidence ──────────────────────────────────────────────────
    with _t[4]:
        st.markdown(
            "| Layer | Rule |\n|---|---|\n"
            "| Regime | new buys only when the Nifty 500 closes above its 200-day SMA; holdings stay either way |\n"
            "| Eligible | Nifty 500 member · above the 100-DMA · no one-day move over 15 % in 90 sessions · ≥ ₹5 crore median turnover · not under NSE surveillance |\n"
            "| Rank | trend quality (exp. regression slope × R²), percentile-averaged over 60/90/120 sessions |\n"
            "| Exits | at the decision close: out of the top 25 % (a profitable 300–364-day holding may stay in the top 50 %), below the 100-DMA, a 15 % day, left the index, surveillance — sold at the next open |\n"
            "| Stops / targets | none (Clenow) |\n"
            "| Size | 0.10 % of v2 equity per ATR20 · per-trade cap 3.33 % · sector cap 25 % · correlation block 0.90 |\n"
            "| Resize | every second decision, every holding back to equal risk, only when > ±10 % off target |\n"
            "| v1 holdings | a v2 buy of a v1 holding CONVERTS it: v2's size at the open, the v1 stop cancelled |\n"
            "| ETFs | own pool, NAV premium ≤ 3 %, 2–5 held, ≤ 10 % each / 30 % in all |\n"
            "| Guards | results within 7 days → wait a week · reviewer WAIT/PASS → skip a week · stale data never sells |\n")
        st.caption("Evidence: P1 (Clenow) won the pre-registered tournament and survived the survivorship-corrected "
                   "re-run (CAGR 19.3 %, max drawdown −22.4 %, MAR 0.86); Clenow's own exits + resize over the house "
                   "stop/trail: CAGR 17.3 → 20.5 %, MAR 0.86 → 1.00 (descriptive); convert over two slices +2.33 % "
                   "CI [+0.95, +3.71]. Docs 41, 42 §10.")
