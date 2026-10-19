# commander_pages/v2_live.py - 🗓️ v2 · THIS WEEK (18-Oct-2026; split into four pages 19-Oct-2026).
#
# The weekly cycle of the v2 system for real money: the checklist, your orders for Wednesday's
# open, the reviewer's rulings on the buys and the exit watch. The book, the rank board and the
# autopsy have their own pages (v2 · BOOK / RANK & UNIVERSE / AUTOPSY); the paper books stay on
# ANALYSIS › 🧭 PAPER · v2 SYSTEM. Reads what the nightly engine wrote (p1_paper.py, Phase 4.79)
# and the v2 ledger; nothing here places an order.
# Runs in the app's namespace via commander_pages.run('v2_live', globals()).
if True:
    import os as _os
    import pandas as _pd
    import p1_paper as _p1
    import v2_core as _v2
    import v2_ui as _ui

    _ui.page_head("🗓️ v2 · This Week",
                  "The v2 system (Clenow's <i>Stocks on the Move</i>, ensemble rank) for real money, beside the current "
                  "system. Decided at Tuesday's close (Monday's when Tuesday is a holiday), placed at the next open. "
                  "No stops, no targets: holdings leave on Clenow's exits, and every second decision resizes the book "
                  "to equal risk. Workflow: Doc 42 · design and evidence: Doc 41.")
    _c = _ui.load()
    _ui.status_strip(_c)
    _pend, _held, _inr = _c["pend"], _c["held"], _c["inr"]
    _dec = _pend.get("decided")
    _rv = _v2.latest_reviews(_dec) if _dec else {}
    _buys = [b[0] for b in _pend.get("buys", [])]
    _since = [q for q in _held.values() if _dec and str(q.get("entry_date")) >= str(_dec)]
    _wl_ok = _os.path.exists(_p1.V2_WATCHLIST)

    _l, _r = st.columns([3, 2])
    with _l:
        st.markdown("**The weekly cycle** (Doc 42 §2)")
        _steps = [
            ("Decision close 16:30 · auto-pilot Phase 4.79", bool(_dec), "decided %s" % _dec if _dec else "no V2H decision yet"),
            ("Watchlist V2_System pushed to TradingView + Add-ons M2 status", _wl_ok,
             "FINAL_V2_WATCHLIST.csv written" if _wl_ok else "not written"),
            ("Reviewer rulings on the buys (execution check)", (not _buys) or all(b in _rv for b in _buys),
             ("%d of %d reviewed" % (sum(1 for b in _buys if b in _rv), len(_buys))) if _buys else "no buys this week"),
            ("Evening: your review - this page + V2_System on a Daily chart", None, "you"),
            ("Next open 09:15 · limit at the decision close + 1 %, cancel by 10:00 · CONVERT: sell the excess, "
             "cancel the v1 stop", None, "you"),
            ("Record each fill: python v2_take.py SYM --price P --qty Q (or --convert / --sell)",
             (not _buys) or bool(_since),
             ("%d slice(s) recorded since the decision" % len(_since)) if _buys else "nothing to record"),
        ]
        for _t, _ok, _note in _steps:
            st.markdown("%s %s · <span style='color:var(--muted)'>%s</span>" % (
                "✅" if _ok else ("⏳" if _ok is False else "👤"), _t, _note), unsafe_allow_html=True)
    with _r:
        import v2_risk as _vr

        @st.cache_data(ttl=900, show_spinner="Reading the v2 book…")
        def _v2w_review():
            return _vr.review()
        try:
            _rw = _v2w_review()
            _sm, _R = _rw["summary"], _rw["rows"]
            st.markdown("**Next decision:** %s%s" % (_sm["next_decision"] or "?",
                                                    " — a **RESIZE** day (every holding back to equal risk)"
                                                    if _sm["next_is_reset"] else ""))
            _w = _R[_R["exit_watch"] != "OK"] if len(_R) and "exit_watch" in _R else _R.iloc[0:0]
            if not len(_R):
                st.info("No real v2 holdings yet - nothing on exit watch.")
            elif len(_w):
                st.warning("**Exit watch** (sold at the next open unless it recovers by the decision close):\n\n" +
                           "\n".join("- **%s**: %s" % (a, b) for a, b in zip(_w["symbol"], _w["exit_watch"])))
            else:
                st.success("Every v2 holding passes Clenow's exits at the last close.")
            st.caption(_sm.get("surv_note") or "")
        except Exception as _e:
            st.error("v2 book not readable: %s" % _e)

    st.markdown("---")
    _ord = sorted(f for f in _os.listdir(_p1.REPORT_DIR) if f.startswith("orders_") and f.endswith(".md")) \
        if _os.path.isdir(_p1.REPORT_DIR) else []
    _yours = ""
    if _ord:
        _txt = open(_os.path.join(_p1.REPORT_DIR, _ord[-1]), encoding="utf-8").read()
        _k = _txt.find("## YOUR v2 ORDERS")
        _yours = _txt[_k:] if _k >= 0 else ""
        st.caption("Order sheet: reports/p1_paper/%s" % _ord[-1])
    if _yours:
        st.markdown(_yours)
    else:
        st.info("No orders for your book yet - the next decision is %s's close."
                % (_c["nd"].strftime("%A %d-%b") if _c["nd"] else "the next Tuesday"))
    if _buys:
        st.markdown("**Reviewer on this week's buys** (execution only; WAIT / PASS = skip this week):")
        st.dataframe(_pd.DataFrame([{"symbol": s, "ruling": _rv.get(s, "not reviewed yet")} for s in _buys]),
                     hide_index=True, use_container_width=True)
