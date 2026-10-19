# commander_pages/v2_book.py - 📂 v2 · BOOK (19-Oct-2026).
#
# The real v2 book: every holding against Clenow's exits and the resize target (v2_risk.py -
# the same view as Risk Shield › 🧭 v2 Holdings), the tax lots, the ETF sleeve against its caps,
# and the ledger itself (open + closed slices). Read-only.
# Runs in the app's namespace via commander_pages.run('v2_book', globals()).
if True:
    import datetime as _dt
    import pandas as _pd
    import v2_house as _vh
    import v2_ledger as _vl
    import v2_risk as _vr
    import v2_ui as _ui

    _ui.page_head("📂 v2 · Book",
                  "What v2 holds with real money: Clenow's exits, the resize target, tax lots and the ETF sleeve. "
                  "No stops and no targets - a holding leaves at the open after a decision close that shows an exit. "
                  "Fills are recorded with v2_take.py; the 16:30 sync closes a holding Dhan shows sold.")
    _c = _ui.load()
    _ui.status_strip(_c)
    _inr, _held, _led = _c["inr"], _c["held"], _c["ledger"]

    _vr.render_streamlit(summary=False)      # the strip above already carries the summary

    _t = st.tabs(["🧾 Tax lots", "🪙 ETF sleeve", "📒 Ledger"])
    with _t[0]:
        if not _held:
            st.info("No open lots.")
        else:
            _today = _dt.date.today()
            _rows = []
            for s, q in sorted(_held.items()):
                d0 = _dt.date.fromisoformat(str(q["entry_date"])[:10])
                days = (_today - d0).days
                lp = _c["px"].get(s, q["entry"])
                g = (lp - q["entry"]) * q["sh"]
                _rows.append({"symbol": s, "shares": q["sh"], "entry": round(q["entry"], 2), "since": str(d0),
                              "days": days, "to LTCG (365d)": max(0, 365 - days),
                              "gain": _inr(g), "status": ("LTCG" if days >= 365 else
                                                          "tax-hold band (300-364d): a profitable holding may stay "
                                                          "in the top 50 %" if days >= _vh.H["tax_from"] and g > 0 else
                                                          "short-term")})
            st.dataframe(_pd.DataFrame(_rows), hide_index=True, use_container_width=True)
            st.caption("Short-term gains are taxed at 20 %, long-term (≥ 365 days) at 12.5 % above ₹1.25 lakh a year. "
                       "Converted holdings keep your real cost basis for tax; the ledger entry is v2's.")
    with _t[1]:
        _pool = _vh.etf_pool()
        _e = {s: q for s, q in _held.items() if s in _pool}
        _eq = _c["eq"] or 1.0
        if not _e:
            st.info("v2 holds no ETFs. The sleeve holds 2-5 ETFs, ≤ 10 % of v2 equity each, ≤ 30 % in all, "
                    "and drops any ETF more than 3 % from its NAV.")
        else:
            _rows = [{"ETF": s, "underlying": _pool[s].get("underlying"), "value": _inr(q["sh"] * _c["px"].get(s, q["entry"])),
                      "% of v2 equity": round(q["sh"] * _c["px"].get(s, q["entry"]) / _eq * 100, 1)} for s, q in _e.items()]
            _tot = sum(r["% of v2 equity"] for r in _rows)
            st.dataframe(_pd.DataFrame(_rows), hide_index=True, use_container_width=True)
            st.markdown("Sleeve total **%.1f %%** of v2 equity (cap 30 %%)%s" % (_tot, " — **OVER**" if _tot > 30 else ""))
    with _t[2]:
        st.markdown("**Open slices** (data/v2/real_book.json)")
        if _held:
            st.dataframe(_pd.DataFrame([dict(symbol=s, **q) for s, q in sorted(_held.items())]),
                         hide_index=True, use_container_width=True)
        else:
            st.caption("none")
        st.markdown("**Closed slices** · realised %s" % _inr(_vl.realised()))
        if _led["closed"]:
            st.dataframe(_pd.DataFrame(_led["closed"]), hide_index=True, use_container_width=True)
        else:
            st.caption("none yet")
