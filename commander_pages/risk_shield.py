# commander_pages/risk_shield.py - the RISK SHIELD page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('risk_shield', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🛡️ Risk Shield — Risk Management & Entries</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live monitoring of OCO exits, pullback entries, and unprotected holdings from Dhan GTT orders.</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    #  DECLARE STRIP (22-Aug-2026, Jay: "I have a very bad discipline of not
    #  logging the journal on placing trades... how do I cultivate the habit")
    #
    #  The diagnosis was that there is no habit to cultivate. The journal
    #  already writes itself: buy_price 19/19, stoploss 19/19, entry snapshot
    #  19/19 - the 4:30 sync and the upsert hook fill everything the broker
    #  knows. Exactly ONE field cannot be recovered from Dhan and was blank on
    #  every row: `timeframe`, which is rung 1 of the trade-type ladder. With
    #  it blank the ladder falls through to a chart-state guess that moves with
    #  the chart, and the trail multiplier is a heuristic rather than a
    #  declaration.
    #
    #  So this is not a journaling form. It is one question, asked where he is
    #  already looking, answerable in one click. Design rules it follows:
    #    * never ask for data the machine has (only this one field appears)
    #    * the debt is COUNTED, not implied - invisible debt is not paid
    #    * forward-only; no backfill prompt, no history nag
    #    * writing is idempotent and scoped to OPEN rows of that symbol
    # ══════════════════════════════════════════════════════════════════════
    def _rs_declare_strip():
        import sqlite3 as _sq_d
        try:
            _dbf = journal_db_path()
        except Exception as _e:
            return
        try:
            _cn = _sq_d.connect(_dbf)
            _cn.row_factory = _sq_d.Row
            _cols = {r[1] for r in _cn.execute("PRAGMA table_info(journal)")}
            if "timeframe" not in _cols:
                _cn.close()
                return
            _open = [dict(r) for r in _cn.execute(
                "SELECT id, symbol, timeframe, setup, buy_price, quantity "
                "FROM journal WHERE UPPER(status)='OPEN' ORDER BY symbol")]
            _cn.close()
        except Exception as _e:
            _gm_logger.warning("declare strip: journal read failed: %s", _e)
            return
        if not _open:
            return

        def _blank(v):
            return str(v or "").strip().lower() in ("", "none", "nan", "-")

        _todo = [r for r in _open if _blank(r.get("timeframe"))]
        _done = len(_open) - len(_todo)

        if not _todo:
            st.markdown(
                f"<div style='background:#052E20;border:1px solid var(--bull);border-left:4px solid var(--bull);"
                f"border-radius:8px;padding:10px 16px;margin-bottom:14px;font-size:0.85rem;color:var(--bull);'>"
                f"\u2713 <b>All {_done} open positions have a declared timeframe.</b> "
                f"The trade-type ladder is reading rung 1 on every one of them \u2014 nothing is guessing."
                f"</div>", unsafe_allow_html=True)
            return

        st.markdown(
            f"<div style='background:#2A1F05;border:1px solid var(--warn);border-left:4px solid var(--warn);"
            f"border-radius:8px;padding:10px 16px;margin-bottom:6px;font-size:0.9rem;color:var(--warn);'>"
            f"<b>\u270d\ufe0f Declare \u2014 {len(_todo)} of {len(_open)} positions have no timeframe.</b>"
            f"<div style='font-size:0.78rem;color:var(--warn);margin-top:3px;'>"
            f"This is the ONE field Dhan cannot tell us, and it is rung 1 of the trade-type ladder. "
            f"Until it is set, the type is inferred from today\u2019s chart (the <code>?</code> on the "
            f"tiles) and the trail multiplier is a heuristic. One click each.</div></div>",
            unsafe_allow_html=True)

        def _write_tf(_rid, _sym, _val, _rat=None):
            try:
                _rat = str(_rat or "").strip()
                _c2 = _sq_d.connect(_dbf)
                if _rat:
                    # One statement, so the two fields can never half-land.
                    _c2.execute("UPDATE journal SET timeframe=?, rationale=? WHERE id=?",
                                (_val, _rat, _rid))
                else:
                    _c2.execute("UPDATE journal SET timeframe=? WHERE id=?", (_val, _rid))
                _c2.commit(); _c2.close()
                try:
                    # LOCAL import, deliberately. At this point in the file the
                    # module-level name `datetime` is the CLASS (line 17,
                    # `from datetime import datetime`); the RISK SHIELD block
                    # rebinds it to the MODULE about 25 lines below this
                    # function's call site. So `datetime.datetime.now()` here
                    # raises AttributeError, and the audit line would vanish
                    # into the except while the journal write looked fine.
                    import datetime as _dtm
                    os.makedirs("logs", exist_ok=True)
                    with open(os.path.join("logs", "risk_shield_actions.log"), "a",
                              encoding="utf-8") as _lf:
                        _lf.write(f"{_dtm.datetime.now().isoformat(timespec='seconds')} "
                                  f"DECLARE_TIMEFRAME {_sym} -> {_val}"
                                  + (f" | {_rat}" if _rat else "") + "\n")
                except Exception as _le:
                    _gm_logger.warning("declare strip: audit log failed: %s", _le)
                return True
            except Exception as _e:
                _gm_logger.warning("declare strip: write failed for %s: %s", _sym, _e)
                st.error(f"Could not write {_sym}: {_e}")
                return False

        with st.container():
            for _r in _todo:
                _rid = _r.get("id"); _sym = str(_r.get("symbol") or "").upper()
                _bp = _r.get("buy_price"); _qt = _r.get("quantity")
                _c1, _c2c, _c3, _c4 = st.columns([2.4, 3.2, 1.1, 1.4])
                with _c1:
                    _sub = []
                    if _qt:
                        _sub.append(f"{int(float(_qt))} sh")
                    if _bp:
                        _sub.append(f"@ \u20b9{float(_bp):,.2f}")
                    _stp = str(_r.get("setup") or "").strip()
                    if _stp and _stp.upper() != "NONE":
                        _sub.append(_stp)
                    st.markdown(
                        f"<div style='padding-top:6px;'><b style='color:var(--ink);'>{_sym}</b>"
                        f"<span style='color:var(--muted);font-size:0.78rem;'> "
                        f"{' \u00b7 '.join(_sub)}</span></div>", unsafe_allow_html=True)
                with _c2c:
                    # RATIONALE (22-Aug-2026, Jay: "I'll save the chart snapshot on
                    # the Notes section at trade time"). A snapshot records what the
                    # chart LOOKED like; swing-vs-positional is an INTENT, and one
                    # sentence typed at the same moment captures what re-reading the
                    # picture later can only guess at. Deliberately OPTIONAL - the
                    # one-click path must never be blocked by a second field, which
                    # is how the original form-shaped journal died.
                    st.text_input(
                        "rationale", key=f"decl_rat_{_rid}", label_visibility="collapsed",
                        value=str(_r.get("rationale") or ""),
                        placeholder="why you took it — optional",
                        help="Free text, written with the timeframe. One line is plenty: "
                             "\"75m pullback off the 20, sector leading\".")
                with _c3:
                    if st.button("SWING", key=f"decl_sw_{_rid}", use_container_width=True,
                                 help="8-12 week hold. Sets the 14-bar trail clock and the 2R/4R "
                                      "target pair."):
                        if _write_tf(_rid, _sym, "Swing",
                                     st.session_state.get(f"decl_rat_{_rid}")):
                            st.rerun()
                with _c4:
                    if st.button("POSITIONAL", key=f"decl_po_{_rid}", use_container_width=True,
                                 help="6-8 month hold. Sets the 22-bar trail clock and the 3R/5R "
                                      "target pair."):
                        if _write_tf(_rid, _sym, "Positional",
                                     st.session_state.get(f"decl_rat_{_rid}")):
                            st.rerun()
        st.caption("Declared once at entry and never re-read from the chart \u2014 that is the point. "
                   "Change it only if the trade\u2019s intent genuinely changed.")
        st.markdown("---")

    try:
        _rs_declare_strip()
    except Exception as _e_ds:
        _gm_logger.warning("declare strip failed: %s", _e_ds)

    # --- Precompute Pyramid/Trim classifications ---
    import pyramid_logic as pl
    if "pyramid_classifications" not in st.session_state:
        with st.spinner("Precomputing Pyramid/Trim classifications..."):
            try:
                st.session_state.pyramid_classifications = pl.get_precomputed_classifications()
            except Exception as _pe:
                st.session_state.pyramid_classifications = pd.DataFrame()
                st.warning(f"Failed to precompute classifications: {_pe}")

    pyramid_df = st.session_state.pyramid_classifications
    pyramid_class_dict = {}
    if pyramid_df is not None and not pyramid_df.empty:
        for _, row in pyramid_df.iterrows():
            sym = row.get("symbol")
            if sym:
                pyramid_class_dict[sym] = {
                    "classification": row.get("classification", "HOLD"),
                    "trigger": row.get("trigger", "")
                }

    # --- Portfolio Equity Curve Protection ---
    import datetime, json, os
    PORTFOLIO_FILE = "portfolio_history.json"

    # A8 FIX (2026-07-04 audit): atomic JSON writes (temp + os.replace) so a
    # crash or a second session mid-write can never truncate the history files.
    def _rs_atomic_json_write(path, obj):
        try:
            _tmp = path + ".tmp"
            with open(_tmp, "w") as f:
                json.dump(obj, f)
            os.replace(_tmp, path)
        except Exception:
            pass

    _portfolio_history = {}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                _portfolio_history = json.load(f)
        except Exception:
            pass
    _today_str = datetime.date.today().isoformat()
    # Only a LIVE reading goes into the equity history; a Dhan outage used to write the
    # invented ₹50L fallback as that day's equity.
    if 'total_cap' in globals() and globals().get("TOTAL_CAP_IS_LIVE", False):
        _portfolio_history[_today_str] = app_state.total_cap
        _rs_atomic_json_write(PORTFOLIO_FILE, _portfolio_history)

    import risk_common as _rc
    _capital_protection_mode = False
    _cap_prot_msg = ""
    if len(_portfolio_history) >= 5:
        # Convert to pandas series to calculate EMA — SORTED by date key (a
        # json file with out-of-order keys would otherwise scramble the EMA).
        _s_port = pd.Series([v for _, v in sorted(_portfolio_history.items())])
        _port_ema20 = _s_port.ewm(span=20, adjust=False).mean().iloc[-1]
        _curr_port = _s_port.iloc[-1]
        if _curr_port < _port_ema20:
            _capital_protection_mode = True
            _cap_prot_msg = f"📉 CAPITAL PROTECTION MODE ACTIVE: Portfolio Equity (₹{_curr_port:,.0f}) is below 20-EMA (₹{_port_ema20:,.0f}). Mechanical stops will be tightened globally."

    # --- AI review helper (uses fast model for batch) ---
    # Prompts are framed for Jay's NSE swing/positional method: Weinstein Stage 2,
    # ATR-trailed stops, R-discipline, and "confirmation before entry" (a closed
    # trigger bar, never a blind buy-limit at the zone). Keep answers to 1 sentence.
    # TRUTHFULNESS (Jay, 31-Jul-2026): ask_llm returns `fallback_text` verbatim when
    # every provider fails, and the old fallbacks were plausible-sounding advice
    # ("Monitor position. SL and targets active.") rendered under the same 🤖 AI header
    # as a real read. A dead API was therefore indistinguishable from analysis. One
    # sentinel now marks the failure and the renderer styles it as NOT analysis.
    _AI_UNAVAILABLE = "⚠ AI UNAVAILABLE — the LLM call failed. No analysis was generated for this position."

    def _rs_type_badge(label, src=None):
        """Trade-type badge + WHERE THE ANSWER CAME FROM.

        The source was computed by resolve_trade_type and discarded, so a tile reading
        POSITIONAL gave no way to tell a declared answer from a classifier verdict from
        the bare default — and those are three completely different situations. Chasing
        one such tile cost three wrong theories; the provenance ends that in a glance.
          journal  = you declared it (Timeframe)   -> authoritative
          setup    = derived from the catalyst      -> intent at entry
          allocator/structural = Risk Allocator v2.2 classification
          default  = NOTHING was known. Not a classification.
        """
        _st = ("padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-left:8px;"
               "font-weight:800;vertical-align:middle;color: var(--ink);letter-spacing:0.5px;")
        if not label or label == "UNKNOWN":
            return (f'<span style="{_st}background: var(--surface-2);border:1px solid var(--muted);" title="Technicals unavailable '
                    f'— trade type not determined">TYPE UNKNOWN</span>')
        _sw = label.startswith("SWING")
        _inf = label.endswith("?")
        _bg = "linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%)" if _sw else "linear-gradient(135deg, #059669 0%, #047857 100%)"
        _border = "var(--acc-rule)" if _sw else "var(--bull-rule)"
        _srcs = str(src or "")
        _tip = {"journal": "You declared this on the trade (journal Timeframe)",
                "setup": "Derived from the entry catalyst — the intent at entry",
                "structural": "Commander Risk Allocator v2.2 classification",
                "stop": "What you actually RISKED at entry, in ATR units — the one criterion that cannot drift mid-trade",
                "default": "NOTHING was known — no Timeframe, no setup, no classification. "
                           "This is a fallback, not a verdict."}.get(_srcs, _srcs or "—")
        _tag = ("" if not _srcs else
                f'<span style="font-size:0.62rem;font-weight:700;opacity:0.75;margin-left:4px;">'
                f'{"⚠ " if _srcs == "default" else ""}{_srcs}</span>')
        return (f'<span style="{_st}background:{_bg};border:1px solid {_border};'
                f'{"opacity:0.85;" if _inf else ""}" title="{_tip}">{label}{_tag}</span>')

    def _rs_ai_card(ai_text):
        """Render the AI block truthfully with high contrast glass styling."""
        if not ai_text:
            return ""
        if ai_text.startswith("⚠ AI UNAVAILABLE") or ai_text == "AI review unavailable.":
            return ('<div style="background:linear-gradient(145deg, #451A1A 0%, #2D1517 100%);border-left:4px solid var(--bear);border:1px solid #7F1D1D;padding:12px 14px;'
                    'border-radius:8px;margin-top:12px;font-size:0.82rem;color:var(--bear);'
                    'line-height:1.45;font-weight:600;">⚠ <b>No AI analysis</b> — the LLM call failed this run. '
                    'The numbers above are unaffected.</div>')
        if ai_text.startswith("AI analysis pending"):
            return ('<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border-left:4px solid var(--muted);border:1px solid var(--ink-2);padding:12px 14px;'
                    'border-radius:8px;margin-top:12px;font-size:0.82rem;color:var(--faint);'
                    'line-height:1.45;">🤖 <b>AI:</b> not run yet — press “Run AI Analysis”.</div>')
        _txt = ai_text.replace("[Positional]", "").replace("[Swing]", "").replace("[]", "").strip()
        # The model emphasises its verdict in markdown ("I fundamentally **DISAGREE**"),
        # but this string is embedded in a raw HTML div where markdown is never parsed,
        # so it rendered as literal asterisks around the one word worth seeing first.
        # Convert rather than forbid: the prompt cannot reliably stop a model reaching
        # for bold, so the renderer is the durable place to handle it. Non-greedy and
        # single-line, so an unmatched pair is left alone instead of swallowing the
        # rest of the paragraph.
        import re as _re          # `re` is not imported at module scope in this file
        _txt = _re.sub(r"\*\*([^*\n]+?)\*\*", r"<b>\1</b>", _txt)
        _ts = st.session_state.get("ai_cache_ts")
        _age = f' <span style="color: var(--acc);font-size:0.7rem;">· generated {_ts}</span>' if _ts else ""
        return (f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border-left:4px solid #38BDF8;border:1px solid var(--ink-2);padding:12px 16px;'
                f'border-radius:8px;margin-top:12px;font-size:0.83rem;color:var(--ink);'
                f'line-height:1.55;">🤖 <b>AI:</b>{_age}<br><span style="color:var(--ink);">{_txt}</span></div>')


    def get_stock_context_and_ai_review(symbol, order_type, **kwargs):
        from ai_provider_manager import ask_llm
        _tech = kwargs.get("tech")
        _tech_str = ""
        if isinstance(_tech, dict):
            _ws_score = _tech.get('ws_score', 'N/A')
            _sma200 = _tech.get('sma200', 'N/A')
            _sma200_slope = _tech.get('sma200_slope', 0)
            _sma50 = _tech.get('sma50', 'N/A')
            _above200 = 'Yes' if _tech.get('above200') else 'No'
            _dist_from_200 = _tech.get('dist_from_200', 'N/A')
            _atr_pct = _tech.get('atr_pct', 'N/A')
            _vol_climax = 'Yes (Spike >300%)' if _tech.get('vol_climax') else 'No'
            _vol_breakout = 'Yes (Base Breakout)' if _tech.get('vol_breakout') else 'No'
            _days_er = _tech.get('days_to_earnings') if _tech.get('days_to_earnings') is not None else 'N/A'
            _chand = _tech.get('chandelier_exit', 'N/A')
            _tech_str = (f"\nLIVE TECHNICALS: "
                         f"Weinstein Score: {_ws_score}/80 | "
                         f"200-SMA: ₹{_sma200} ({'Rising' if isinstance(_sma200_slope, (int, float)) and _sma200_slope > 0 else 'Falling'}, {_sma200_slope}% slope) | "
                         f"50-SMA: ₹{_sma50} | "
                         f"Price > 200-SMA: {_above200} | "
                         f"Dist from 200-SMA: {_dist_from_200}% | "
                         f"ATR Volatility: {_atr_pct}% | "
                         f"Volume Climax: {_vol_climax} | "
                         f"Breakout Volume: {_vol_breakout} | "
                         f"Days to Earnings: {_days_er} | "
                         f"Chandelier Exit (22D): ₹{_chand}")

        # TRADE TYPE (Jay, 31-Jul-2026): the model no longer classifies. Risk Shield's
        # _rs_trade_type() owns that call and it is stated here as a GIVEN, so the badge
        # and the Rec SL/T1/T2 multipliers can never disagree with the narrative. The
        # model may still argue the classification looks wrong — that is analysis, and
        # useful — but it cannot change what the page renders.
        _tt_lbl = kwargs.get("trade_type") or "UNKNOWN"
        _tt_str = (
            f"\nTRADE TYPE (already determined by the risk engine — do NOT re-classify, "
            f"and do NOT prefix your reply with any tag): {_tt_lbl}. "
            + ("Manage it as a swing: tighter risk, faster exits, 5-8% objectives over 8-12 weeks. "
               if _tt_lbl == "SWING" else
               "Manage it as a positional trend-follow: wider trail, 10-30% objectives over 6-8 months. "
               if _tt_lbl == "POSITIONAL" else
               "The engine could NOT determine the type (technicals unavailable) — say so and stay generic on horizon. ")
            + "If the data makes you think that classification is wrong, say so explicitly and why."
        )
        _sys = (
            "You are an elite NSE technical analyst and risk manager evaluating an active trade. "
            "ANALYSIS RULES: Provide a sharp, insightful 2-3 sentence technical evaluation. "
            "If 'Volume Climax' is Yes, warn about potential trend exhaustion. If 'Breakout Volume' is Yes, highlight the strong accumulation base breakout. If 'Days to Earnings' is < 5, recommend tightening risk or trimming. "
            "Do NOT just regurgitate the numbers provided in the prompt. "
            "Analyze the price action relative to the moving averages, volatility, and trend strength. Offer actionable risk management advice."
        )
        if order_type == "OCO_EXIT_COMBINED":
            orders_list = kwargs.get("orders", [])
            ltp = kwargs.get("ltp", 0)
            r_mult = kwargs.get("r_mult", "N/A")
            risk = kwargs.get("risk", 0)
            orders_desc = []
            for o_idx, o in enumerate(orders_list):
                sl = o.get("sl_trigger"); target = o.get("target_trigger")
                sl_qty = o.get("sl_qty") or o.get("qty") or 0
                tgt_qty = o.get("target_qty") or o.get("qty") or 0
                sl_dist = ((ltp - sl) / ltp * 100) if ltp and sl is not None else 0.0
                tgt_dist = ((target - ltp) / ltp * 100) if ltp and target is not None else 0.0
                sl_str = f"SL ₹{sl:,.0f} ({sl_dist:+.1f}%)" if sl is not None else "No SL"
                tgt_str = f"Tgt ₹{target:,.0f} (+{tgt_dist:.1f}%)" if target is not None else "Trailing Runner (No Target)"
                orders_desc.append(f"  Leg {o_idx+1}: {sl_str} | {tgt_str}")
            _pyr_class = kwargs.get("pyr_class", ""); _pyr_reason = kwargs.get("pyr_reason", "")
            _chand = _tech.get("chandelier_exit") if isinstance(_tech, dict) else None
            _chand_str = f" The catalyst-aware Chandelier trailing stop is ₹{_chand}." if _chand not in (None, "N/A") else ""
            if _pyr_class:
                _reconcile = (f"\n\nThe RULES ENGINE classifies this position as **{_pyr_class}** ({_pyr_reason}).{_chand_str} "
                              f"RECONCILE with it: state whether you AGREE, and if you disagree, say WHY specifically. "
                              f"If the engine says ADD (pyramid), judge whether this is a valid add — a leader at a genuine pullback, NOT extended — and if so, confirm the position stop should be RAISED to the Chandelier level; if it's extended or the trend is decaying, say do NOT add. "
                              f"If the engine says TRIM/REDUCE/EXIT, confirm or dispute that.")
            else:
                _reconcile = "\nAdvise if I should hold, trail the SL up, add (pyramid), or exit."
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | open R: {r_mult} | open risk ₹{risk:,.0f}{_tech_str}{_tt_str}\n" + "\n".join(orders_desc) + _reconcile
            return ask_llm(prompt, fallback_text=_AI_UNAVAILABLE)
        elif order_type == "GTT_ENTRY":
            trigger = kwargs.get("trigger", 0); price = kwargs.get("price", 0)
            ltp = kwargs.get("ltp", 0); dist = kwargs.get("dist", 0)
            _style = "dip buy-limit (fills on touch, NO confirmation)" if trigger < ltp else "breakout buy-stop (confirms on a close into the trigger)"
            _tech = kwargs.get("tech")
            _setup_warn = ""
            if isinstance(_tech, dict):
                if _tech.get("ws_score", 100) < 50 or _tech.get("sma200_slope", 0) < 0:
                    _setup_warn = f"\nWARNING: Setup may be invalid. WS Score is {_tech.get('ws_score')}/80 and SMA200 slope is {_tech.get('sma200_slope'):+.2f}%. Highlight these risks."
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | buy trigger ₹{trigger:,.2f} ({dist:+.1f}% vs LTP) | limit ₹{price:,.2f} | type: {_style}{_tech_str}{_tt_str}{_setup_warn}\nProvide a brief technical analysis on whether this looks like a valid Stage-2 pullback entry setup."
            return ask_llm(prompt, fallback_text=_AI_UNAVAILABLE)
        elif order_type == "UNPROTECTED_HOLDING":
            buy_price = kwargs.get("buy_price", 0); ltp = kwargs.get("ltp", 0)
            pnl_pct = ((ltp - buy_price) / buy_price * 100) if buy_price else 0.0
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | cost ₹{buy_price:,.2f} | P&L {pnl_pct:+.1f}% | NO STOP LOSS{_tech_str}{_tt_str}\nProvide a technical view and suggest an optimal placement for a stop loss to protect this position."
            return ask_llm(prompt, fallback_text=_AI_UNAVAILABLE)
        elif order_type == "SINGLE_EXIT":
            trigger = kwargs.get("trigger", 0); ltp = kwargs.get("ltp", 0)
            dist = kwargs.get("dist", 0); label = kwargs.get("label", "Stop Loss")
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | {label}: ₹{trigger:,.2f} ({dist:+.1f}% away){_tech_str}{_tt_str}\nShould I hold, trail, or act on this {label.lower()}?"
            return ask_llm(prompt, fallback_text=_AI_UNAVAILABLE)
        return "N/A"

    # --- Persistent AI Cache Logic ---
    import json
    import os
    AI_CACHE_FILE = "ai_cache.json"
    
    if "ai_cache_loaded" not in st.session_state:
        st.session_state.ai_cache_loaded = True
        if os.path.exists(AI_CACHE_FILE):
            try:
                with open(AI_CACHE_FILE, "r") as f:
                    _saved = json.load(f)
                for k, v in _saved.items():
                    if k not in st.session_state:
                        st.session_state[k] = v
            except: pass

    # Controls row
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([8, 2, 2])
    with ctrl_col3:
        if st.button("🔄 Refresh", key="es_refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.session_state.pop("pyramid_classifications", None)
            st.rerun()
    with ctrl_col2:
        if st.button("🤖 Run AI Analysis", key="es_run_ai", type="secondary", use_container_width=True):
            st.session_state.force_run_ai = True
            st.session_state.pop("pyramid_classifications", None)
            for k in list(st.session_state.keys()):
                if any(p in k for p in ["ai_exit_review_", "ai_single_review_", "ai_entry_review_", "ai_unprotected_review_"]):
                    del st.session_state[k]
            if os.path.exists(AI_CACHE_FILE):
                os.remove(AI_CACHE_FILE)
            st.rerun()

    if not _BROKER_OK:
        st.error("❌ Dhan broker API module not available.")
    else:
        try:
            _ts = dhan_token_status()
            _tk_valid = _ts.get("valid", False)
        except Exception:
            _tk_valid = False

        if app_state.sys_status == "AUTH EXPIRED" or not _tk_valid:
            st.error("🔑 Dhan token expired. Paste a fresh access token in the sidebar.")
        else:
            with st.spinner("Fetching active orders from Dhan..."):
                try:
                    dhan, ctx = get_dhanhq_client()
                    if not dhan:
                        st.error("Dhan Auth missing")
                        st.stop()
                    resp = dhan.get_forever()
                except Exception as e:
                    resp = None
                    st.error(f"Failed to fetch orders: {e}")

            if resp and isinstance(resp, dict) and resp.get("status") == "success":
                data = resp.get("data", [])

                # --- Parse and group orders ---
                buy_gtts = []; sell_gtts = {}; single_sells = []; symbols_to_fetch = set()

                # Dhan forever-order shape (canonical — see scratch/test_parse_gtt.py
                # and dhan_journal_v7.py): an OCO carries orderType == "OCO" and emits
                # TWO rows that share the SAME orderId — one legName=STOP_LOSS_LEG, one
                # legName=TARGET_LEG. Anything else SELL is a standalone exit. Group OCO
                # legs by orderId; classify by legName, price only as a last resort.
                for g in data:
                    if g.get("orderStatus", "") != "PENDING": continue
                    symbol = clean_symbol(g.get("tradingSymbol", ""))
                    if not symbol: continue
                    symbols_to_fetch.add(symbol)
                    txn = (g.get("transactionType", "") or "").upper()
                    ot  = (g.get("orderType", "") or "").upper()
                    order_id = g.get("orderId", ""); qty = int(float(g.get("quantity", 0) or 0))
                    trigger = float(g.get("triggerPrice", 0) or 0); price = float(g.get("price", 0) or 0)
                    leg = (g.get("legName", "") or "").upper()

                    if txn == "BUY":
                        buy_gtts.append({"symbol": symbol, "qty": qty, "trigger": trigger, "price": price, "order_id": order_id})
                        continue
                    if txn != "SELL":
                        continue

                    # OCO if the broker says so OR the row is a recognised OCO leg.
                    is_oco = (ot == "OCO") or (leg in ("STOP_LOSS_LEG", "TARGET_LEG"))
                    if is_oco:
                        gid = order_id or g.get("correlationId", "")
                        if gid not in sell_gtts:
                            sell_gtts[gid] = {"symbol": symbol, "sl_trigger": None, "sl_qty": None,
                                              "target_trigger": None, "target_qty": None, "order_id": gid, "qty": qty,
                                              # ORDER TYPE, carried through (22-Aug-2026). Dhan tags a
                                              # STANDALONE stop as orderType SINGLE but still labels the
                                              # leg STOP_LOSS_LEG, so `is_oco` above sweeps it into this
                                              # group and the card called it "OCO-3". It is the single SL
                                              # that covers the uncapped tail - a different instrument
                                              # with a different purpose, and it must say so.
                                              "order_type": ot}
                        if leg == "STOP_LOSS_LEG":
                            is_sl = True
                        elif leg == "TARGET_LEG":
                            is_sl = False
                        else:
                            # No leg label: a SELL stop sits below the target, so the
                            # lower-trigger leg is the SL. Self-heal pass below corrects ties.
                            is_sl = trigger < price if (trigger and price) else True
                        if is_sl:
                            sell_gtts[gid]["sl_trigger"] = trigger
                            sell_gtts[gid]["sl_qty"] = qty
                        else:
                            sell_gtts[gid]["target_trigger"] = trigger
                            sell_gtts[gid]["target_qty"] = qty
                    else:
                        single_sells.append({"symbol": symbol, "qty": qty, "trigger": trigger, "price": price, "order_id": order_id})

                # Self-heal: in any OCO the SL trigger must be below the target trigger.
                # If a mislabelled leg flipped them, swap (price/qty together) so downstream
                # risk + R-multiple math is correct regardless of broker leg labelling.
                for oco in sell_gtts.values():
                    _sl, _tg = oco["sl_trigger"], oco["target_trigger"]
                    if _sl is not None and _tg is not None and _sl > _tg:
                        oco["sl_trigger"], oco["target_trigger"] = _tg, _sl
                        oco["sl_qty"], oco["target_qty"] = oco["target_qty"], oco["sl_qty"]

                # LTP is now FULLY Dhan-sourced on this page (zero yfinance dependency).
                # Populated in two Dhan passes below:
                #   1) holdings lastTradedPrice — real-time, already fetched, no extra call
                #   2) Dhan ohlc_data via dhan_ohlcv.fetch_ltp() for anything not held
                #      (covers a stale OCO resting on a stock you've since sold) —
                #      resolves securityId + exchange_segment from the Dhan scrip master.
                ltps = {}

                # Fetch overrides from global df (from SQLite)
                journal_overrides = {}
                if 'df_active_global' in globals() and not app_state.df_active_global.empty:
                    for _, r in app_state.df_active_global.iterrows():
                        sym = r.get("Symbol")
                        if pd.notna(sym):
                            journal_overrides[sym] = {
                                "manual_sl_override": float(r.get("Manual SL Override", 0)) if pd.notna(r.get("Manual SL Override")) and str(r.get("Manual SL Override")).strip() else None,
                                "custom_ce_mult": float(r.get("Custom CE Mult", 0)) if pd.notna(r.get("Custom CE Mult")) and str(r.get("Custom CE Mult")).strip() else None,
                                "pyramid_status": str(r.get("Pyramid Status", "")) if pd.notna(r.get("Pyramid Status")) else "",
                                # B1: the trade's catalyst (journal 'setup' snapshot) drives
                                # the validated trail multiplier set.
                                "setup": str(r.get("Setup", "")).strip().upper() if pd.notna(r.get("Setup")) else "",
                                # Trade-type-aware trail window (Jay, 14-Jul-2026):
                                # journal Timeframe (Positional/Swing) → 22/14-bar clock.
                                "timeframe": str(r.get("Timeframe", "")).strip() if pd.notna(r.get("Timeframe")) else "",
                                # ENTRY + STOP (10-Aug-2026) — rung 3 of the trade-type ladder
                                # (risk taken at entry, in ATR units). This dict carried only
                                # the five override fields, so classify_by_stop_distance was
                                # handed stop=None and abstained on EVERY position — which is
                                # why every tile fell through to "POSITIONAL · default".
                                # The ladder was correct and simply never had the inputs.
                                "buy_price": float(r.get("BuyPrice")) if pd.notna(r.get("BuyPrice")) else None,
                                "stoploss": float(r.get("StopLoss")) if pd.notna(r.get("StopLoss")) else None,
                            }

                # B2: market regime (0-10 scorer) — degrades to per-symbol SMA200 check on failure
                _rs_regime_bear = None
                _rs_regime_chip = ""
                try:
                    from market_regime import compute_regime as _rs_creg
                    _rs_reg = _rs_creg(persist=False)
                    _rs_score9 = _rs_reg.get("score")
                    if _rs_score9 is not None:
                        _rs_regime_bear = _HP.is_bear(_rs_score9)
                        _rs_regime_chip = f"{_rs_reg.get('verdict','?')} ({_rs_score9}/10)"
                except Exception:
                    pass

                # Catalyst-aware trail multipliers now live in risk_common.chandelier_exit
                # (shared single source of truth with the Pyramid/Trim page).

                # Fetch holdings for entry price & unprotected detection
                _, _, df_holdings = get_live_holdings_stats()
                holdings_map = {}
                if not df_holdings.empty:
                    for _, h in df_holdings.iterrows():
                        csym = clean_symbol(h.get("Symbol", h.get("tradingSymbol", "")))
                        if csym:
                            holdings_map[csym] = {
                                "buy_price": float(h.get("BuyPrice", h.get("avgCostPrice", 0))),
                                "qty": int(float(h.get("Quantity", h.get("totalQty", 0)))),
                                "ltp": float(h.get("LTP", h.get("lastTradedPrice", 0))),
                                "entry_date": h.get("EntryDate", "")
                            }

                # Pass 1 — Dhan holdings lastTradedPrice (real-time intraday, already
                # fetched above, no extra API call). Every OCO exit sits on a stock you
                # hold, so this covers the common case. Symbols not held fall through to
                # the Dhan ohlc_data pass below. No yfinance anywhere on this page.
                for _csym, _h in holdings_map.items():
                    if _h.get("ltp"):
                        ltps[_csym] = _h["ltp"]

                # Dhan ohlc_data fallback for any exit symbol not covered by holdings
                # (e.g. an OCO still resting on a stock you've already sold). Batched —
                # one Dhan call for all missing names. dhan_ohlcv.fetch_ltp() resolves
                # securityId + exchange_segment from the scrip master and never raises,
                # so a failure just leaves the LTP blank (levels still render from Dhan).
                _missing_ltp = [s for s in symbols_to_fetch if not ltps.get(s)]
                if _missing_ltp:
                    try:
                        import dhan_ohlcv
                        _dhan_ltps = dhan_ohlcv.fetch_ltp(_missing_ltp)
                        for _s, _px in (_dhan_ltps or {}).items():
                            _cs = clean_symbol(_s)
                            if _px and not ltps.get(_cs):
                                ltps[_cs] = float(_px)
                    except Exception as _e:
                        logger.warning(f"Entry Shield Dhan ohlc_data LTP fallback failed: {_e}")

                # Detect unprotected holdings
                # A1 SAFETY FIX (2026-07-04 audit): a single sell order is only proof of
                # SL protection when a REAL LTP exists to compare against. The old
                # fallback to the order's own price made a TARGET-only order classify
                # the position as protected. No LTP -> protection state UNKNOWN,
                # surfaced loudly, never silently protected.
                all_protected_syms = set()
                protection_unknown = set()
                for oid, oco in sell_gtts.items():
                    if oco["sl_trigger"] is not None:
                        all_protected_syms.add(oco["symbol"])
                for s in single_sells:
                    _ss_ltp = ltps.get(s["symbol"])
                    if _ss_ltp and _ss_ltp > 0:
                        if s["trigger"] < _ss_ltp:
                            all_protected_syms.add(s["symbol"])
                    elif s["symbol"] in holdings_map and s["symbol"] not in all_protected_syms:
                        protection_unknown.add(s["symbol"])

                unprotected_holdings = []
                for csym, h in holdings_map.items():
                    if csym in protection_unknown:
                        continue  # rendered as UNKNOWN below, not as protected/unprotected
                    if csym not in all_protected_syms and h["qty"] > 0:
                        unprotected_holdings.append({"symbol": csym, "buy_price": h["buy_price"], "qty": h["qty"], "ltp": h["ltp"], "entry_date": h.get("entry_date", "")})
                        symbols_to_fetch.add(csym)
                unprotected_holdings_syms = {u["symbol"] for u in unprotected_holdings}
                if protection_unknown:
                    st.warning(f"⚠️ LTP unavailable — protection state UNKNOWN for: "
                               f"{', '.join(sorted(protection_unknown))}. Verify their stop "
                               f"orders manually on Dhan before trusting this page.")

                # Group sell_gtts by symbol
                sell_gtts_by_symbol = {}
                for oid, oco in sell_gtts.items():
                    sym = oco["symbol"]
                    if sym not in sell_gtts_by_symbol:
                        sell_gtts_by_symbol[sym] = []
                    sell_gtts_by_symbol[sym].append(oco)
                for sym, orders in sell_gtts_by_symbol.items():
                    orders.sort(key=lambda x: x["target_trigger"] if x["target_trigger"] is not None else 9999999)

                # PARTIAL COVER (22-Aug-2026, Jay). `unprotected_holdings` above is
                # ALL-OR-NOTHING per symbol: one protecting order anywhere puts the
                # symbol in all_protected_syms and it never appears again. So a
                # position with 71 of 258 shares covered counted as protected, and
                # the headline metric read "All Protected" while 187 shares sat
                # naked. Coverage is a QUANTITY question and the page was answering
                # it as a boolean. Same defect the tile's "held N sh" line had.
                _partial_cover = []
                for _csym, _h in holdings_map.items():
                    _hq = int(_h.get("qty") or 0)
                    if _hq <= 0 or _csym in unprotected_holdings_syms:
                        continue
                    _cov = sum(int(o.get("sl_qty") or o.get("qty") or 0)
                               for o in sell_gtts_by_symbol.get(_csym, []))
                    _cov += sum(int(x.get("qty") or 0) for x in single_sells
                                if x.get("symbol") == _csym)
                    if 0 < _cov < _hq:
                        _partial_cover.append((_csym, _hq, _cov, _hq - _cov))
                if _partial_cover:
                    _partial_cover.sort(key=lambda t: -t[3])
                    _pc_txt = " · ".join(f"**{a}** {d} of {b}" for a, b, c, d in _partial_cover)
                    st.warning(
                        f"⚠️ **Partly covered — {sum(t[3] for t in _partial_cover):,} shares "
                        f"carry no stop.** These do NOT appear under Unprotected Holdings, because that "
                        f"list is per-symbol and each of these has *some* order resting: {_pc_txt}")



                # ─────────────────────────────────────────────────────────────

                # --- Metrics ---
                # A6 FIX (2026-07-04 audit): rows without a REAL LTP are excluded from
                # the risk sums and COUNTED — headline metrics must never be quietly
                # understated by missing prices.
                total_protected = 0.0; total_risk = 0.0
                _no_ltp_rows = set()
                active_exits_count = len(sell_gtts_by_symbol)
                pending_entries_count = len(buy_gtts)
                for sym, orders in sell_gtts_by_symbol.items():
                    ltp = ltps.get(sym) or 0
                    if not ltp:
                        _no_ltp_rows.add(sym)
                    for oco in orders:
                        sl = oco["sl_trigger"]; sl_qty = oco.get("sl_qty") or oco.get("qty") or 0
                        if sl: total_protected += sl_qty * sl
                        if ltp and sl:
                            risk = sl_qty * (ltp - sl)
                            if risk > 0: total_risk += risk
                for s in single_sells:
                    trigger = s["trigger"]; qty = s["qty"]; sym = s["symbol"]
                    ltp = ltps.get(sym) or 0
                    if not ltp:
                        _no_ltp_rows.add(sym)
                    if trigger:
                        total_protected += qty * trigger
                        if ltp and ltp > trigger: total_risk += qty * (ltp - trigger)

                unprotected_count = len(unprotected_holdings)
                unprotected_color = "var(--bear)" if unprotected_count > 0 else "var(--bull)"
                unprotected_label = f"{unprotected_count} Positions" if unprotected_count > 0 else "All Protected ✅"
                risk_deployed_pct = (total_risk / total_deployed_g) * 100 if total_deployed_g > 0 else 0.0

                metrics_html = (
                    f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:20px;">'
                    f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid var(--bull);border-radius:12px;padding:16px;box-shadow:0 4px 16px rgba(0,0,0,0.25);text-align:left;">'
                    f'<div style="font-size:0.72rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Capital Protected</div>'
                    f'<div style="color:var(--bull);font-size:1.65rem;font-weight:900;margin-top:4px;font-family:JetBrains Mono;">₹{format_inr_int(total_protected)}</div>'
                    f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">Active Stop Loss value</div></div>'
                    f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid var(--bear);border-radius:12px;padding:16px;box-shadow:0 4px 16px rgba(0,0,0,0.25);text-align:left;">'
                    f'<div style="font-size:0.72rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Capital at Risk</div>'
                    f'<div style="color:var(--bear);font-size:1.65rem;font-weight:900;margin-top:4px;font-family:JetBrains Mono;">₹{format_inr_int(total_risk)} <span style="font-size:0.95rem; opacity:0.85;">({risk_deployed_pct:.1f}%)</span></div>'
                    f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">Loss to SL</div></div>'
                    f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid #38BDF8;border-radius:12px;padding:16px;box-shadow:0 4px 16px rgba(0,0,0,0.25);text-align:left;">'
                    f'<div style="font-size:0.72rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Active Exits</div>'
                    f'<div style="color:#38BDF8;font-size:1.65rem;font-weight:900;margin-top:4px;font-family:JetBrains Mono;">{active_exits_count} Stocks</div>'
                    f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">{len(sell_gtts)} OCO · {len(single_sells)} Standalone</div></div>'
                    f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid var(--warn);border-radius:12px;padding:16px;box-shadow:0 4px 16px rgba(0,0,0,0.25);text-align:left;">'
                    f'<div style="font-size:0.72rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Pullback Entries</div>'
                    f'<div style="color:var(--warn);font-size:1.65rem;font-weight:900;margin-top:4px;font-family:JetBrains Mono;">{pending_entries_count} Orders</div>'
                    f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">Active GTT buy limits</div></div>'
                    f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid {unprotected_color};border-radius:12px;padding:16px;box-shadow:0 4px 16px rgba(0,0,0,0.25);text-align:left;">'
                    f'<div style="font-size:0.72rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Unprotected</div>'
                    f'<div style="color:{unprotected_color};font-size:1.5rem;font-weight:900;margin-top:4px;font-family:JetBrains Mono;">{unprotected_label}</div>'
                    f'<div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">Holdings with no SL</div></div>'
                    f'</div>'
                )
                st.markdown(metrics_html, unsafe_allow_html=True)
                if _no_ltp_rows:
                    st.caption(f"⚠️ {len(_no_ltp_rows)} position(s) excluded from Capital-at-Risk "
                               f"(no live LTP): {', '.join(sorted(_no_ltp_rows))}")

                # B3: PORTFOLIO HEAT vs the capital risk budget. Budget = the house risk each
                # open position was allowed to take (stock 0.5% · ETF 0.75%, house_policy) x the
                # SIZING capital - the same base the sizers use. It was a session-only 0.25%
                # ("execution freeze") x live equity until 25-Sep-2026, so the card measured
                # heat against a rule nothing else in the book followed.
                try:
                    _cap_base, _cap_src = _HP.sizing_capital()
                    _heat_syms = list(sell_gtts_by_symbol.keys()) + [u["symbol"] for u in unprotected_holdings]
                    _n_open_h = len(_heat_syms)
                    _rb_sum = sum(_HP.risk_pct_for(_x) for _x in _heat_syms)
                    _rb_pct = (_rb_sum / _n_open_h) if _n_open_h else _HP.RISK_NEW_STOCK_PCT
                    _heat_budget = (_cap_base * _rb_sum / 100.0) if _cap_base == _cap_base else 0.0
                    if _cap_base != _cap_base:
                        st.caption("🔥 Portfolio Heat: sizing capital is not set (GM settings → Capital), "
                                   "so there is no budget to measure against.")
                    elif _cap_base > 0:
                        _heat_ok = total_risk <= _heat_budget
                        _hcol = "var(--bull)" if _heat_ok else "var(--bear)"
                        _chip = (f" · 🌡️ Regime: <b>{_rs_regime_chip}</b>" if _rs_regime_chip else "")
                        st.markdown(
                            f"<div style='background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border:1.5px solid {_hcol};border-radius:10px;padding:12px 16px;"
                            f"margin:4px 0 16px;font-size:0.9rem;color: var(--ink-2);box-shadow:0 4px 16px rgba(0,0,0,0.2);'>"
                            f"🔥 <b>Portfolio Heat:</b> ₹{format_inr_int(total_risk)} open risk vs budget "
                            f"₹{format_inr_int(_heat_budget)} (house risk, avg {_rb_pct:.2f}% × {_n_open_h} positions × "
                            f"₹{format_inr_int(_cap_base)} capital) — "
                            f"<b style='color:{_hcol}'>{'WITHIN BUDGET ✅' if _heat_ok else 'OVER BUDGET 🚨'}</b>"
                            f"{_chip}</div>", unsafe_allow_html=True)
                except Exception as _e_heat:
                    # A missing heat card reads as "nothing to worry about"; say it failed.
                    st.warning(f"🔥 Portfolio Heat could not be computed: {type(_e_heat).__name__}: {_e_heat}")

                # --- Fetch technicals for AI review and Risk Profile ---
                hist_data = st.session_state.get("cached_hist_data_v4", {})
                if hist_data and any(isinstance(v, dict) and ("close_5d_ago" not in v or "vol_breakout" not in v) for v in hist_data.values()):
                    hist_data = {}
                # FRESHNESS PROBE — must test the NEWEST required field, not an old one.
                # It tested only "ema20": a cache written before a new field was added still
                # had ema20, so nothing was ever refetched and the new field stayed absent
                # forever. That is why every tile read POSITIONAL after the trade-type
                # classifier shipped — tt_label was never computed, so the resolver fell
                # through to its positional default on all 15 holdings.
                _REQUIRED_TECH = ("ema20", "tt_label")
                missing_syms = [s for s in symbols_to_fetch
                                if s not in hist_data
                                or any(k not in hist_data.get(s, {}) for k in _REQUIRED_TECH)]
                _tech_failed_syms = []   # A5 FIX: track symbols whose technicals could not be computed
                if missing_syms:
                    try:
                        import data_provider as dp
                        import pandas as pd
                        import numpy as np

                        _batch_data = dp.fetch_batch_ohlcv(missing_syms, period="2y", interval="1d", use_cache=True, auto_adjust=True)  # 2y: the v2.2 classifier needs >=260 daily bars (highest(high,250) + SMA200); 1y is ~250 and fails every symbol
                        _tech_failed_syms = [s for s in missing_syms
                                             if _batch_data.get(s) is None or getattr(_batch_data.get(s), "empty", True)]
                        # A9: capture the technicals' as-of date for the freshness strip.
                        # Stored BOTH in session_state and inside the hist cache itself, so
                        # cache-hit runs (no batch fetch) still show the real date, not "—".
                        try:
                            _asof_candidates = [df.index[-1] for df in _batch_data.values()
                                                if df is not None and not df.empty]
                            if _asof_candidates:
                                _asof_s = str(max(_asof_candidates).date())
                                st.session_state["rs_tech_asof"] = _asof_s
                                hist_data["_asof"] = _asof_s
                        except Exception:
                            pass

                        for _s in missing_syms:
                            df_sym = _batch_data.get(_s)
                            if df_sym is not None and not df_sym.empty and "Close" in df_sym.columns:
                                _c = df_sym["Close"].dropna()
                                _hi = df_sym["High"].dropna() if "High" in df_sym.columns else _c
                                _lo = df_sym["Low"].dropna() if "Low" in df_sym.columns else _c
                                
                                _ema20 = float(_c.ewm(span=20, adjust=False).mean().iloc[-1]) if len(_c) >= 20 else None
                                _close_5d_ago = float(_c.iloc[-6]) if len(_c) >= 6 else None
                                
                                _ltp = float(_c.iloc[-1])
                                _ws_score = 0
                                _ws_above200 = False
                                _sma200slp = 0.0
                                _sma200 = 0.0
                                _sma50 = 0.0
                                _atr_pct = 0.0
                                _dist_from_200 = 0.0
                                
                                if len(_c) >= 200:
                                    _sma50 = float(_c.rolling(50).mean().iloc[-1])
                                    _sma200 = float(_c.rolling(200).mean().iloc[-1])
                                    # RS-P0 (14-Jul-2026): compute above200 HERE, before the
                                    # Chandelier call below — it used to be assigned ~20 lines
                                    # AFTER the call, so chandelier_exit always received
                                    # above200=False (and bear=True whenever the regime scorer
                                    # was down), silently loosening every trail by 0.5×ATR.
                                    _ws_above200 = _ltp > _sma200
                                    _sma200_10d_ago = float(_c.rolling(200).mean().shift(10).iloc[-1])
                                    _sma200slp = ((_sma200 - _sma200_10d_ago) / _sma200_10d_ago) * 100 if _sma200_10d_ago else 0
                                    _hi52 = float(_c.max())
                                    _lo52 = float(_c.min())
                                    
                                    # ATR Calculation (14-day)
                                    _tr1 = _hi - _lo
                                    _tr2 = (_hi - _c.shift(1)).abs()
                                    _tr3 = (_lo - _c.shift(1)).abs()
                                    _tr = pd.concat([_tr1, _tr2, _tr3], axis=1).max(axis=1)
                                    _atr = float(_tr.rolling(14).mean().iloc[-1])
                                    _atr_pct = (_atr / _ltp) * 100 if _ltp else 0.0
                                    _dist_from_200 = ((_ltp - _sma200) / _sma200) * 100 if _sma200 else 0.0
                                    
                                    _vol_climax = False
                                    _vol_breakout = False
                                    if "Volume" in df_sym.columns:
                                        _vol = df_sym["Volume"].dropna()
                                        if len(_vol) >= 50 and len(_hi) >= 45:
                                            _vol_50d_avg = float(_vol.rolling(50).mean().iloc[-1])
                                            if _vol_50d_avg > 0:
                                                _has_spike = False
                                                _has_heavy_selling = False
                                                _spike_high = 0.0
                                                for i in range(-5, 0):
                                                    if float(_vol.iloc[i]) / _vol_50d_avg >= 3.0:
                                                        _has_spike = True
                                                        _c_i = float(_c.iloc[i])
                                                        _h_i = float(_hi.iloc[i])
                                                        _l_i = float(_lo.iloc[i])
                                                        _o_i = float(df_sym["Open"].iloc[i]) if "Open" in df_sym.columns else _c_i
                                                        
                                                        _spike_high = max(_spike_high, _h_i)
                                                        
                                                        _candle_range = _h_i - _l_i
                                                        _upper_wick = _h_i - max(_c_i, _o_i)
                                                        _wick_pct = (_upper_wick / _candle_range) if _candle_range > 0 else 0.0
                                                        
                                                        if _wick_pct >= 0.35 or ((_h_i - _ltp) / _h_i) > 0.04:
                                                            _has_heavy_selling = True

                                                if _has_spike:
                                                    _prev_40d_high = float(_hi.iloc[-45:-5].max())
                                                    _dist_from_50 = ((_ltp - _sma50) / _sma50) * 100 if _sma50 else 0.0
                                                    
                                                    if _spike_high > _prev_40d_high and _dist_from_50 < 30.0 and not _has_heavy_selling:
                                                        _vol_breakout = True
                                                    else:
                                                        _vol_climax = True                                                
                                    # Chandelier trail via the SHARED risk_common helper — single
                                    # source of truth, kept in sync with the Pyramid/Trim page.
                                    _chandelier_exit = None
                                    _ce_mult = None
                                    _ce_mult_src = None
                                    _custom_mult = journal_overrides.get(_s, {}).get("custom_ce_mult") if _s in journal_overrides else None
                                    # A4 FIX (2026-07-04 audit): 0/negative custom mult is INVALID,
                                    # not "silently use system default" — flag it on the row.
                                    _invalid_ce_override = (_custom_mult is not None
                                                            and not (isinstance(_custom_mult, (int, float)) and _custom_mult > 0))
                                    import risk_common as _rc
                                    _setup_s = journal_overrides.get(_s, {}).get("setup", "")
                                    # Trade-type-aware trail clock (Jay, 14-Jul-2026):
                                    # journal Timeframe → swing 14-bar / positional 22-bar.
                                    # ONE resolver, same as the tile and the R-policy check
                                    # (10-Aug-2026). This read the journal Timeframe ONLY, so a
                                    # holding the page labelled SWING? from structure still fed
                                    # swing=None here and trailed on the positional multiplier.
                                    # resolve_trade_type's precedence is journal -> setup prefix
                                    # -> structural -> positional, so a declared Timeframe still
                                    # wins; the structural read only speaks when nothing else can.
                                    # TRADE TYPE — Risk Allocator v2.2 classifier, computed HERE
                                    # because df_sym is in hand. RS quadrant comes from the MANUAL
                                    # Strike flags, which is the reading Jay trades.
                                    #
                                    # THIS USED TO READ `rs_trade_type`, WHICH IS BUILT ~120 LINES
                                    # BELOW THIS LOOP. The NameError was swallowed by the batch
                                    # except as "Technicals fetch failed this run", so NO symbol got
                                    # technicals: no chandelier (TSL marker gone), no atr_pct (ladder
                                    # rung 3 silent), no tt_label (rung 4 silent) — and every tile
                                    # read "POSITIONAL default". One forward reference, every symptom
                                    # reported today. A batch-level except that reports a data problem
                                    # will hide a code problem indefinitely.
                                    _tt_sw = _tt_lab = _tt_fam = _tt_why = None
                                    try:
                                        # RRG for rung 4 = the COMPUTED quadrant (25-Sep-2026); the
                                        # hand-typed flag it used to read had gone 39 days stale.
                                        _q_rrg = None
                                        try:
                                            import gm_trigger_board as _gtb_tt
                                            _q_rrg = _gtb_tt.rrg_live(df_sym).get("quadrant")
                                        except Exception as _e_rrg:
                                            _gm_logger.warning(f"{_s}: RRG compute failed (rung 4 runs without it): {_e_rrg}")
                                        _tt_sw, _tt_lab, _tt_why, _tt_fam = _rc.classify_trade_type_v22(
                                            df_sym, rrg=_q_rrg)
                                    except Exception as _e_tt:
                                        _gm_logger.warning(f"{_s}: trade-type classify failed: {_e_tt}")
                                    _struct_s = _tt_sw
                                    _jov_s = journal_overrides.get(_s, {}) if isinstance(journal_overrides, dict) else {}
                                    _swing_s, _ttlab_s, _ttsrc_s = _rc.resolve_trade_type(
                                        timeframe=_jov_s.get("timeframe"),
                                        setup=_jov_s.get("setup"),
                                        structural=_struct_s,
                                        entry=_jov_s.get("buy_price"),
                                        stop=_jov_s.get("stoploss"),
                                        atr_pct=_atr_pct)
                                    if len(_c) >= _rc.trail_window_for(_setup_s, _swing_s):
                                        # #16 (24-Aug-2026). `bear` is the MARKET regime -- it widens the
                                        # trail by 0.5 ATR to survive a choppy tape. The old fallback fed it
                                        # `not _ws_above200`, a per-STOCK test, so when market_regime failed
                                        # every stock under its own 200-DMA silently got a LOOSER trail. That
                                        # is both a category error and backwards: a stock below its 200-DMA is
                                        # weak, and weak is not an argument for more room. v67 uses its own
                                        # market state for the same flag, so this was also a live source of
                                        # the v67-vs-Risk-Shield gap Jay reported.
                                        # Unknown regime now means NO widening, and the badge says so, rather
                                        # than a guess dressed as a measurement.
                                        _bear_s = bool(_rs_regime_bear) if _rs_regime_bear is not None else False
                                        _bear_unknown = _rs_regime_bear is None
                                        _ce_win = _rc.trail_window_for(_setup_s, _swing_s)
                                        _chandelier_exit, _ce_mult, _ce_mult_src = _rc.chandelier_exit(
                                            _hi, _lo, _c, setup=_setup_s, bear=_bear_s,
                                            cap_protect=_capital_protection_mode,
                                            custom_mult=_custom_mult, above200=_ws_above200,
                                            swing=_swing_s)

                                        # Apply Manual SL Override if present.
                                        # A7 FIX: override MODE — 'Floor' (default, can only tighten)
                                        # or 'Exact' (use the manual value verbatim, both directions).
                                        _manual_sl = journal_overrides.get(_s, {}).get("manual_sl_override") if _s in journal_overrides else None
                                        if _manual_sl and _manual_sl > 0:
                                            if st.session_state.get("rs_sl_override_mode",
                                                                    _gm_settings().get("sl_override_mode", "Floor")) == "Exact":
                                                _chandelier_exit = _manual_sl
                                            else:
                                                _chandelier_exit = max(_chandelier_exit, _manual_sl)
                                        
                                    _days_to_earnings = None
                                    _edate = get_earnings_date_cached(_s)
                                    if _edate:
                                        from datetime import date
                                        _diff = (_edate - date.today()).days
                                        if 0 <= _diff <= 30:
                                            _days_to_earnings = _diff
                                    
                                    _ws_above200 = _ltp > _sma200
                                    _ws_above50 = _ltp > _sma50
                                    _ws_pos52 = ((_ltp - _lo52) / max(_hi52 - _lo52, 1)) * 100 if _hi52 > _lo52 else 50
                                    _ws_score = (
                                        (25 if _ws_above200 and _sma200slp > 0 else 0) +
                                        (20 if _ws_above200 else 0) +
                                        (15 if _sma200slp > 0 else 0) +
                                        (12 if _ws_pos52 >= 75 else 6 if _ws_pos52 >= 50 else 0) +
                                        (8  if _ws_above50  else 0)
                                    )
                                    
                                # (trade type is classified further up, before the trail block that
                                # consumes it — computing it twice would be two chances to drift)
                                hist_data[_s] = {
                                    "ltp": round(_ltp, 2),
                                    "tt_swing": _tt_sw,
                                    "tt_label": _tt_lab,
                                    "tt_family": _tt_fam,
                                    "tt_source": _tt_why,
                                    "ws_score": int(_ws_score),
                                    "sma200_slope": round(_sma200slp, 2),
                                    "sma200": round(_sma200, 2),
                                    "sma50": round(_sma50, 2),
                                    "ema20": round(_ema20, 2) if _ema20 else None,
                                    "above200": _ws_above200,
                                    "atr_pct": round(_atr_pct, 2),
                                    "dist_from_200": round(_dist_from_200, 2),
                                    "chandelier_exit": round(_chandelier_exit, 2) if _chandelier_exit else None,
                                    "close_5d_ago": round(_close_5d_ago, 2) if _close_5d_ago else None,
                                    "vol_breakout": _vol_breakout if '_vol_breakout' in locals() else False,
                                    "vol_climax": _vol_climax if '_vol_climax' in locals() else False,
                                    "days_to_earnings": _days_to_earnings if '_days_to_earnings' in locals() else None,
                                    "ce_mult": _ce_mult if '_ce_mult' in locals() else None,
                                    "ce_mult_src": _ce_mult_src if '_ce_mult_src' in locals() else None,
                                    "ce_win": _ce_win if '_ce_win' in locals() else None,
                                    "bear_unknown": _bear_unknown if '_bear_unknown' in locals() else False,
                                    "invalid_ce_override": _invalid_ce_override if '_invalid_ce_override' in locals() else False,
                                }
                    except Exception as _e:
                        # A5 FIX (2026-07-04 audit): a batch-level failure means NONE of
                        # the missing symbols got technicals — say so instead of silence.
                        _tech_failed_syms = list(missing_syms)
                        st.warning(f"⚠️ Technicals fetch failed this run ({_e}) — Chandelier/"
                                   f"flags not computed for {len(missing_syms)} symbol(s).")
                if _tech_failed_syms:
                    st.warning(f"⚠️ Technicals unavailable for: {', '.join(sorted(_tech_failed_syms))} "
                               f"— Chandelier exits, WS scores and volume flags for these are "
                               f"NOT current this run.")
                st.session_state["cached_hist_data_v4"] = hist_data

                # ── TRADE TYPE: ONE rule, owned by Risk Shield (Jay, 31-Jul-2026) ──────
                # It used to be decided TWICE per tile: Python computed `is_swing` (which
                # drives Rec SL / T1 / T2 multipliers) and the LLM was separately ordered to
                # emit a "[Positional]"/"[Swing]" prefix, which is what the BADGE was parsed
                # from. Same thresholds, two evaluators — so a model that drifted, or a
                # prompt missing a field, put a SWING badge over positional-multiplier
                # levels. Worse, the OCO path then fed the AI's own label back in as a
                # fallback for `is_swing` (circular). Risk Shield decides now; the AI is
                # TOLD the answer and analyses inside it. Defaults are the safe ones: a
                # missing score must not silently mean "swing" (the OCO copy used 0 → <60 →
                # swing, the Unprotected copy used 100 → positional; they disagreed).
                def _rs_trade_type(_t, _sym=None):
                    """(is_swing, label) — read back the Risk Allocator v2.2 verdict the
                    technicals loop computed. The old version was an ad-hoc guess (atr_pct>4
                    or dist_from_200>30 or ws_score<60) that shared no term with the Pine
                    which owns this decision."""
                    if not isinstance(_t, dict):
                        return None, "UNKNOWN"
                    return _t.get("tt_swing"), (_t.get("tt_label") or "UNKNOWN")

                rs_trade_type = {}
                for _tt_sym, _tt_tech in hist_data.items():
                    if isinstance(_tt_tech, dict):
                        rs_trade_type[_tt_sym] = _rs_trade_type(_tt_tech, _tt_sym)

                # A9: DATA FRESHNESS STRIP — where prices came from + technicals as-of.
                try:
                    import data_provider as _dp9
                    _src_counts = {}
                    for _fs in list(symbols_to_fetch)[:100]:
                        _sname = str(_dp9.get_last_source(_fs) or "holdings")
                        _src_counts[_sname] = _src_counts.get(_sname, 0) + 1
                    _src_str = " · ".join(f"{k}:{v}" for k, v in sorted(_src_counts.items()))
                    _asof9 = st.session_state.get("rs_tech_asof") or hist_data.get("_asof") or "—"
                    _nsyms9 = sum(1 for _v9 in hist_data.values() if isinstance(_v9, dict))
                    # Split holdings vs order-only symbols (pending GTT entries / stale
                    # OCOs on sold stocks) so the count never reads as a mismatch vs
                    # the portfolio size.
                    _order_only9 = sorted(set(symbols_to_fetch) - set(holdings_map.keys()))
                    _split9 = (f" ({len(holdings_map)} holdings + {len(_order_only9)} order-only: "
                               f"{', '.join(_order_only9)})" if _order_only9 else f" ({len(holdings_map)} holdings)")
                    st.caption(f"🩺 Data: LTP sources [{_src_str}] · technicals as-of {_asof9} "
                               f"· hist cache {_nsyms9} syms{_split9}")
                except Exception:
                    pass

                _ai_tasks = []
                for _sym, _orders in sell_gtts_by_symbol.items():
                    _ai_k = f"ai_exit_review_{_sym}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or 0
                            _tq = sum(o.get("sl_qty") or o.get("qty") or 0 for o in _orders)
                            _re = sum((o.get("sl_qty") or o.get("qty") or 0) * (_ltp - o["sl_trigger"]) for o in _orders if _ltp and o["sl_trigger"] is not None)
                            _h = holdings_map.get(_sym)
                            if _h:
                                _bp = _h["buy_price"]
                                _tri = sum((o.get("sl_qty") or o.get("qty") or 0) * (_bp - o["sl_trigger"]) for o in _orders if o["sl_trigger"] is not None)
                                _rm = f"{(_ltp - _bp) * _tq / _tri:+.2f}R" if _tri > 0 else "N/A"
                            else:
                                _rm = "N/A"
                            # Feed the RULES-ENGINE verdict to the AI so it RECONCILES
                            # instead of contradicting: the AI was prompted only for
                            # hold/trail/exit and never saw the module's ADD/TRIM/etc.
                            # classification (Jay: "AI contradicts the module").
                            _pcr = pyramid_class_dict.get(_sym, {})
                            _ai_tasks.append((_ai_k, _sym, "OCO_EXIT_COMBINED", {"orders": _orders, "ltp": _ltp, "r_mult": _rm, "risk": _re, "tech": hist_data.get(_sym), "pyr_class": _pcr.get("classification", ""), "pyr_reason": _pcr.get("trigger", ""), "trade_type": rs_trade_type.get(_sym, (None, "UNKNOWN"))[1]}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _b in buy_gtts:
                    _sym = _b["symbol"]; _ai_k = f"ai_entry_review_{_sym}_{_b['order_id']}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or 0
                            _dist = (_ltp - _b["trigger"]) / _ltp * 100 if _ltp else 0.0
                            _ai_tasks.append((_ai_k, _sym, "GTT_ENTRY", {"trigger": _b["trigger"], "price": _b["price"], "ltp": _ltp, "dist": _dist, "tech": hist_data.get(_sym), "trade_type": rs_trade_type.get(_sym, (None, "UNKNOWN"))[1]}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _h in unprotected_holdings:
                    _sym = _h["symbol"]; _ai_k = f"ai_unprotected_review_{_sym}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or _h["ltp"] or 0
                            _ai_tasks.append((_ai_k, _sym, "UNPROTECTED_HOLDING", {"buy_price": _h["buy_price"], "qty": _h["qty"], "ltp": _ltp, "tech": hist_data.get(_sym), "trade_type": rs_trade_type.get(_sym, (None, "UNKNOWN"))[1]}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _s in single_sells:
                    _sym = _s["symbol"]; _ai_k = f"ai_single_review_{_sym}_{_s['order_id']}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or _s["price"] or 0
                            _dist = (_ltp - _s["trigger"]) / _ltp * 100 if _ltp else 0.0
                            _label = "Stop Loss" if _s["trigger"] < _ltp else "Target Limit"
                            _ai_tasks.append((_ai_k, _sym, "SINGLE_EXIT", {"trigger": _s["trigger"], "ltp": _ltp, "dist": _dist, "label": _label, "tech": hist_data.get(_sym), "trade_type": rs_trade_type.get(_sym, (None, "UNKNOWN"))[1]}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."

                if _ai_tasks:
                    st.session_state.pop("cached_hist_data_v4", None)
                    st.session_state.pop("pyramid_classifications", None)
                    st.caption("Only 'Tighten SL' rows execute. Trim / Pyramid remain manual. "
                               "Every execution is appended to logs/risk_shield_actions.log.")
                    with st.spinner(f"⚡ Loading AI analysis for {len(_ai_tasks)} positions..."):
                        def _run_ai(task):
                            key, sym, otype, kw = task
                            try:
                                return key, get_stock_context_and_ai_review(sym, otype, **kw)
                            except Exception as _e_ai:
                                import logging
                                logging.getLogger(__name__).error(f"[Risk Shield AI] Error running AI for {sym}: {_e_ai}", exc_info=True)
                                return key, "AI review unavailable."
                        from concurrent.futures import ThreadPoolExecutor
                        # 6 concurrent workers with retry jitter to prevent API rate limit bursts
                        with ThreadPoolExecutor(max_workers=6) as executor:
                            for key, res in executor.map(_run_ai, _ai_tasks):
                                st.session_state[key] = res
                        
                        # Stamp WHEN this batch ran. ai_cache.json survives restarts and is
                        # only rebuilt when you press "Run AI Analysis", so without this the
                        # card could show week-old prose beside a live LTP with nothing to
                        # say which. _rs_ai_card() renders it on every AI block.
                        from datetime import datetime as _dt_now
                        st.session_state["ai_cache_ts"] = _dt_now.now().strftime("%d %b %H:%M")

                        # Save back to cache
                        _new_cache = {"ai_cache_ts": st.session_state["ai_cache_ts"]}
                        for k, v in st.session_state.items():
                            if any(p in k for p in ["ai_exit_review_", "ai_single_review_", "ai_entry_review_", "ai_unprotected_review_", "cached_hist_data_v4"]):
                                _new_cache[k] = v
                        try:
                            with open(AI_CACHE_FILE, "w") as f:
                                json.dump(_new_cache, f)
                        except: pass
                        st.session_state.force_run_ai = False

                # =====================================================================
                # NEW ENHANCEMENTS: Actionable Alerts, Heatmap, What-If Tester, Risk Hist
                # =====================================================================
                st.markdown("<br><hr style='border-color:var(--rule); margin: 10px 0;'>", unsafe_allow_html=True)
                
                portfolio_data = []
                total_portfolio_value = 0
                total_open_risk = 0
                alerts = []

                if "holdings_map" in locals() and holdings_map:
                    for sym, h in holdings_map.items():
                        qty = h.get("qty", 0)
                        bp = h.get("buy_price", 0)
                        ltp = ltps.get(sym) or h.get("ltp") or bp
                        pos_val = qty * ltp
                        total_portfolio_value += pos_val
                        
                        _tech = hist_data.get(sym, {})
                        
                        # Find closest SL
                        sl = None
                        if sym in sell_gtts_by_symbol:
                            sl_vals = [o["sl_trigger"] for o in sell_gtts_by_symbol[sym] if o.get("sl_trigger")]
                            if sl_vals:
                                sl = max(sl_vals)
                        elif sym in [s["symbol"] for s in single_sells]:
                            sl_vals = [o["trigger"] for o in single_sells if o["symbol"] == sym and o["trigger"] < ltp]
                            if sl_vals:
                                sl = max(sl_vals)
                                
                        dist_to_sl = ((ltp - sl) / ltp * 100) if sl and ltp else None
                        open_risk_rs = qty * (ltp - sl) if sl else qty * ltp
                        total_open_risk += open_risk_rs if open_risk_rs > 0 else 0
                        
                        portfolio_data.append({
                            "Symbol": sym,
                            "Sector": h.get("sector", ""),
                            "Value": pos_val,
                            "Risk %": dist_to_sl if dist_to_sl is not None else -100,
                            "LTP": ltp,
                            "SL": sl if sl else 0
                        })
                        
                        # Alerts
                        if sl is None:
                            alerts.append({"type": "NO_SL", "sym": sym, "msg": "Missing Stop Loss"})
                        if _tech.get("vol_climax"):
                            alerts.append({"type": "VOL", "sym": sym, "msg": "Volume Climax"})
                        days_to_er = _tech.get("days_to_earnings")
                        if days_to_er is not None and days_to_er <= 3:
                            alerts.append({"type": "EARNINGS", "sym": sym, "msg": f"Earnings in {days_to_er}d"})

                # B5: sector over-concentration + shadow-pair correlation alerts —
                # reuses ai_risk_manager (existing modules), refreshed at most every 15 min.
                try:
                    import time as _t5
                    _sc_cache = st.session_state.get("rs_sector_corr")
                    if not _sc_cache or (_t5.time() - _sc_cache.get("ts", 0)) > 900:
                        _sc_alerts = []
                        try:
                            from ai_risk_manager import analyze_sector_concentration as _asc
                            _scres = _asc(df_holdings) or {}
                            for _a in _scres.get("alerts", []):
                                _sc_alerts.append({"type": "SECTOR", "sym": str(_a.get("Sector", "?")),
                                                   "msg": f"Sector {_a.get('Exposure', '?')} of book (>25%)"})
                        except Exception:
                            pass
                        try:
                            from ai_risk_manager import get_portfolio_correlation_matrix as _gpc
                            _corr_df5, _shadow5, _div5 = _gpc(list(holdings_map.keys()))
                            for _pair in (_shadow5 or [])[:6]:
                                if isinstance(_pair, dict):
                                    _sc_alerts.append({"type": "CORR", "sym": str(_pair.get("Pair", "?")),
                                                       "msg": f"Shadow pair r={_pair.get('Correlation', '?')} "
                                                              f"({_pair.get('Risk', '')}) — effectively one position"})
                                else:
                                    _sc_alerts.append({"type": "CORR", "sym": "PAIR", "msg": str(_pair)[:90]})
                        except Exception as _e_corr:
                            _sc_alerts.append({"type": "CORR", "sym": "—",
                                               "msg": f"Correlation check FAILED ({type(_e_corr).__name__}) — "
                                                      f"no shadow pairs is UNKNOWN, not clear"})
                        _sc_cache = {"ts": _t5.time(), "alerts": _sc_alerts}
                        st.session_state["rs_sector_corr"] = _sc_cache
                    alerts.extend(_sc_cache.get("alerts", []))
                except Exception:
                    pass

                # 1. Alerts
                if alerts:
                    st.markdown('<div class="section-sub-lbl" style="color:var(--bear);margin-bottom:10px;">🚨 Requires Immediate Action</div>', unsafe_allow_html=True)
                    alert_cols = st.columns(3)
                    for i, al in enumerate(alerts):
                        with alert_cols[i % 3]:
                            bg = "var(--bear)" if al["type"] == "NO_SL" else ("var(--warn)" if al["type"] == "EARNINGS" else "#bf40bf")
                            txt_c = "#fff" if al["type"] != "EARNINGS" else "#000"
                            st.markdown(f'<div style="background:{bg};color:{txt_c};padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:0.85rem;font-weight:bold;">{al["sym"]}: {al["msg"]}</div>', unsafe_allow_html=True)

                if portfolio_data:
                    # 3. What-If Tester
                    st.markdown('<div class="section-sub-lbl">🔮 What-If Scenario Tester</div>', unsafe_allow_html=True)
                    sim_drop = st.slider("Simulated NIFTY Drop (%)", min_value=0.0, max_value=15.0, value=2.0, step=0.5, format="-%f%%")
                        
                    sim_losses = 0
                    hits = 0
                    if sim_drop > 0:
                        for row in portfolio_data:
                            sim_ltp = row["LTP"] * (1 - (sim_drop/100))
                            if row["SL"] > 0 and sim_ltp <= row["SL"]:
                                loss = row["Value"] - (row["Value"] * (row["SL"] / row["LTP"]))
                                sim_losses += loss
                                hits += 1
                            elif row["SL"] == 0:
                                loss = row["Value"] * (sim_drop/100)
                                sim_losses += loss
                    
                    dd_pct = (sim_losses / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                    st.markdown(f'''
                    <div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);padding:16px;border-radius:12px;margin-bottom:20px;box-shadow:0 4px 16px rgba(0,0,0,0.25);">
                        <div style="font-size:0.75rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Est. Portfolio Drawdown</div>
                        <div style="font-size:1.8rem;font-weight:900;color:var(--bear);margin-top:4px;font-family:JetBrains Mono;">-{dd_pct:.2f}%</div>
                        <div style="font-size:0.85rem;color:var(--muted);margin-top:6px;">Est. Loss: <b style="color:var(--bear);">₹{sim_losses:,.0f}</b> | SLs Fired: <b style="color:var(--bear);">{hits}</b></div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    # 4. Historical Risk
                    st.markdown('<div class="section-sub-lbl">📈 Historical Risk (30 Days)</div>', unsafe_allow_html=True)
                    import os
                    import json
                    from datetime import date
                    import plotly.graph_objects as go
                    
                    RISK_FILE = "risk_history.json"
                    today_str = date.today().isoformat()
                    
                    risk_history = {}
                    if os.path.exists(RISK_FILE):
                        try:
                            with open(RISK_FILE, "r") as f:
                                risk_history = json.load(f)
                        except: pass
                        
                    risk_history[today_str] = {
                        "portfolio_value": total_portfolio_value,
                        "open_risk": total_open_risk
                    }
                    
                    _rs_atomic_json_write(RISK_FILE, risk_history)  # A8: atomic
                    
                    dates = sorted(list(risk_history.keys()))[-30:]
                    risks = [risk_history[d]["open_risk"] for d in dates]
                    
                    if len(dates) > 0:
                        fig2 = go.Figure(go.Scatter(
                            x=dates, y=risks, mode='lines+markers+text',
                            text=[f"₹{r:,.0f}" for r in risks], textposition="top center", textfont=dict(color="#38BDF8", size=10, family="JetBrains Mono"),
                            line=dict(color='#38BDF8', width=3), marker=dict(size=7, color='#38BDF8', line=dict(color='#FFFFFF', width=1))
                        ))
                        fig2.update_layout(
                            margin=dict(t=22, l=5, r=5, b=5), height=130,
                            paper_bgcolor='#0F172A', plot_bgcolor='#1E293B',
                            xaxis=dict(type='category', showgrid=False, visible=True, tickfont=dict(size=9, color="#94A3B8")),
                            yaxis=dict(showgrid=False, visible=False)
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                st.markdown("<br>", unsafe_allow_html=True)
                # =====================================================================

                if _capital_protection_mode and _cap_prot_msg:
                    st.error(_cap_prot_msg)

                # --- TABS ---
                entry_tab0, entry_tab1, entry_tab2, entry_tab_cq, entry_tab3, entry_tab4, entry_tab5 = st.tabs([
                    "✅ Morning Approval Dashboard",
                    "🎯 Active Exits (OCO)",
                    "⚖️ Pyramid / Trim",
                    "💰 Capital Queue",
                    "🛒 Pullback Entries (GTT)",
                    "📊 Risk Profile & Analytics",
                    "⚙️ Settings & Overrides"
                ])
                
                with entry_tab0:
                    st.markdown('<div class="section-sub-lbl">✅ Review & Push (Morning Gate)</div>', unsafe_allow_html=True)
                    st.markdown('<div style="font-size:0.85rem; color:var(--muted); margin-bottom:12px;">Approve automatically generated Risk Management actions before pushing to Dhan.</div>', unsafe_allow_html=True)
                    
                    proposed_actions = []
                    for sym, orders in sell_gtts_by_symbol.items():
                        _tech = hist_data.get(sym, {})
                        _ltp = ltps.get(sym) or 0
                        _c5 = _tech.get("close_5d_ago")
                        
                        # SIZE ACTIONS COME FROM THE LADDER, NOT FROM TWO INDEPENDENT
                        # CONDITIONS (9-Sep-2026). This block used to compute cond_trim and
                        # cond_add separately, so both could be true at once and a symbol
                        # emitted a Trim row AND a Pyramid row in the same table — SAILIFE
                        # and LAURUSLABS did exactly that. Contradictory advice on one
                        # position is worse than no advice, because whichever the eye lands
                        # on first wins.
                        #
                        # pyramid_logic.classify() already resolves this, and has since
                        # July: EXIT > TRIM > REDUCE > ADD > HOLD, best-of-each, one verdict
                        # per position. The Pyramid page and Risk Shield read it; the
                        # Morning Gate was the surface that did not. Reading it here also
                        # means the gate can no longer disagree with the page it sits next
                        # to — the same one-brain-many-surfaces rule the trail rows now follow.
                        _pcls = (pyramid_class_dict.get(sym) or {})
                        _verdict = str(_pcls.get("classification") or "").upper()
                        _vreason = str(_pcls.get("trigger") or "").strip()
                        _ema20 = _tech.get("ema20")
                        cond_trim = (_verdict == "TRIM")
                        cond_add = (_verdict == "ADD")

                        tsl_target = _tech.get("chandelier_exit")
                        
                        # Nearest active stop
                        sl_vals = [o["sl_trigger"] for o in orders if o["sl_trigger"] is not None]
                        curr_sl = max(sl_vals) if sl_vals else None
                        
                        # 1. Tighten SL - NOT built here any more. This block computed its
                        # own target from hist_data[sym]["chandelier_exit"] and collapsed a
                        # symbol's OCO legs into ONE row via max(sl_trigger), then executed
                        # against _ocos[0]. On the 11 of 15 positions carrying two OCOs, half
                        # of every stop never moved. Trail rows now come from
                        # gtt_auto_shield.build_trail_proposals(), one row PER ORDER - the
                        # same engine the 15:45 scheduled job runs. See below.

                        # 2. TRIM — harvest / de-risk, winners only
                        if cond_trim:
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": "Trim Position",
                                "Trigger Price": round(_ltp, 2),
                                "Qty %": 20,
                                "Reason": _vreason or "Ladder: TRIM"
                            })

                        # 3. PYRAMID — leader AND good location. Reached only when the
                        # ladder did not already call EXIT, TRIM or REDUCE, so an add can
                        # no longer appear beside a trim on the same position.
                        pyramid_state = journal_overrides.get(sym, {}).get("pyramid_status", "")
                        if cond_add and pyramid_state != "Maxed":
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": "Pyramid (Add)",
                                "Trigger Price": round(_ema20, 2) if _ema20 else round(_ltp, 2),
                                "Qty %": 50,
                                "Reason": _vreason or "Ladder: ADD"
                            })

                        # 4. EXIT / REDUCE — the two rungs this page used to drop on the
                        # floor. They outrank both rows above, so hiding them meant the
                        # gate could show a position as merely "over-extended" while the
                        # ladder was calling it broken. Propose-only, like Trim and Pyramid.
                        if _verdict in ("EXIT", "REDUCE"):
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": ("Exit (full)" if _verdict == "EXIT" else "Reduce"),
                                "Trigger Price": round(_ltp, 2),
                                "Qty %": (100 if _verdict == "EXIT" else 33),
                                "Reason": _vreason or f"Ladder: {_verdict}"
                            })
                            
                    # --- TRAIL ROWS FROM THE SHARED ENGINE -----------------------
                    # One row per ORDER. A symbol can hold two OCOs at the SAME stop level,
                    # so two identical-looking rows are two REAL orders, not a duplicate -
                    # the Order ID column is what tells them apart.
                    if st.button("Load / refresh trail proposals", key="rs_load_trail"):
                        st.session_state.pop("rs_trail_cache", None)
                    if "rs_trail_cache" not in st.session_state:
                        try:
                            import gtt_auto_shield as _gas
                            _pr, _br, _er = _gas.build_trail_proposals()
                            st.session_state["rs_trail_cache"] = {
                                "rows": [{"Symbol": _sy, "Action": "Tighten SL",
                                          "Order ID": str(_lg.get("order_id")),
                                          "Qty": int(_lg.get("sl_qty") or _lg.get("qty") or 0),
                                          "Current SL": round(float(_old), 2),
                                          "Trigger Price": round(float(_new), 2),
                                          "Qty %": 100, "Reason": str(_note)}
                                         for _sy, _lg, _old, _new, _m, _src, _note in _pr],
                                "breached": list(_br), "err": _er,
                                "at": datetime.datetime.now().strftime("%H:%M:%S")}
                        except Exception as _te:
                            st.session_state["rs_trail_cache"] = {"rows": [], "breached": [],
                                                                  "err": str(_te), "at": "-"}
                    _tc = st.session_state.get("rs_trail_cache") or {}
                    if _tc.get("err"):
                        st.warning(f"Trail engine: {_tc['err']}")
                    else:
                        st.caption(f"Trail proposals from gtt_auto_shield - {len(_tc.get('rows', []))} "
                                   f"leg(s), read {_tc.get('at', '-')}. Same engine the 15:45 job runs.")
                    # BREACHED never becomes an approvable row: the Chandelier already sits
                    # at/above the LTP, so a SELL trigger there fires instantly. That is an
                    # exit review, and this page does not auto-sell.
                    for _bs, _bo, _bc, _bl in _tc.get("breached", []):
                        st.error(f"{_bs}: Chandelier {_bc} >= LTP {_bl} - EXIT REVIEW, not trailed "
                                 f"(stop stays {_bo})")
                    proposed_actions = list(_tc.get("rows", [])) + proposed_actions

                    if proposed_actions:
                        df_props = pd.DataFrame(proposed_actions)
                        for _c in ("Order ID", "Qty", "Current SL"):
                            if _c not in df_props.columns:
                                df_props[_c] = None
                        df_props = df_props[["Symbol", "Action", "Order ID", "Qty",
                                             "Current SL", "Trigger Price", "Qty %", "Reason"]]
                        # Order ID / Qty / Current SL are TRAIL-ONLY: only a Tighten SL row
                        # modifies an existing GTT, so Trim and Pyramid have no order behind
                        # them. Rendering that as the literal string "None" read like missing
                        # data; blank says "not applicable", which is what it is.
                        _is_trail = df_props["Action"].eq("Tighten SL")
                        df_props["Order ID"] = df_props["Order ID"].where(_is_trail, "—")
                        for _c in ("Qty", "Current SL"):
                            df_props[_c] = pd.to_numeric(df_props[_c], errors="coerce").where(_is_trail)
                        # APPROVE DEFAULTS TO FALSE ON ROWS THAT CANNOT EXECUTE. The button only
                        # ever pushes Tighten SL rows (position-size changes have a much bigger
                        # blast radius and stay propose-only), so pre-ticking Trim and Pyramid
                        # invited the reading that they had been sent when they had not.
                        df_props.insert(0, "Approve", _is_trail.values)
                        edited_df = st.data_editor(
                            df_props,
                            column_config={
                                "Approve": st.column_config.CheckboxColumn("Approve", default=True),
                                "Symbol": st.column_config.TextColumn("Symbol", disabled=True),
                                "Order ID": st.column_config.TextColumn("Order ID", disabled=True,
                                    help="The GTT this row modifies. Two rows on one symbol are two REAL orders."),
                                "Qty": st.column_config.NumberColumn("Qty", disabled=True),
                                "Current SL": st.column_config.NumberColumn("Current SL", format="%.2f", disabled=True),
                                "Action": st.column_config.TextColumn("Action", disabled=True),
                                "Reason": st.column_config.TextColumn("Reason", disabled=True),
                                "Trigger Price": st.column_config.NumberColumn("Trigger Price (₹)", format="%.2f", step=0.05),
                                "Qty %": st.column_config.NumberColumn("Qty (%)", min_value=1, max_value=100, step=1)
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        # B4 (2026-07-04, Jay: review -> modify -> execute): the old button was
                        # a MOCK ("Orders pushed successfully!") — approvals went NOWHERE.
                        # Now executes TIGHTEN-SL rows for real via dhan.modify_forever, gated
                        # by an explicit arm switch. Trim/Pyramid stay propose-only this pass
                        # (position-size changes have a bigger blast radius).
                        st.caption("Only **Tighten SL** rows are pushed by the button below — they "
                                   "modify the GTT named in Order ID. **Trim** and **Pyramid** rows are "
                                   "propose-only: size changes are placed by hand, so their Order ID / "
                                   "Qty / Current SL are blank because there is no resting order to move.")
                        _rs_arm = st.checkbox("⚠️ I confirm LIVE modification of GTT stop orders on Dhan",
                                              key="rs_arm_execute")
                        if st.button("🚀 Execute Approved SL Updates on Dhan", type="primary",
                                     disabled=not _rs_arm):
                            _exec_results = []
                            for _, _pr in edited_df.iterrows():
                                if not _pr.get("Approve") or _pr.get("Action") != "Tighten SL":
                                    continue
                                _psym = str(_pr["Symbol"]); _new_sl = float(_pr["Trigger Price"])
                                try:
                                    # ONE ROW = ONE ORDER. This used to resolve the symbol to
                                    # its OCO list and always take _ocos[0], so on a symbol
                                    # holding two OCOs the second leg was never modified and
                                    # half the position kept its old stop. The row now carries
                                    # the order id it was built from, so the leg it displays is
                                    # the leg it moves.
                                    _oid = str(_pr.get("Order ID") or "").strip()
                                    if not _oid or _oid.lower() in ("none", "nan"):
                                        _exec_results.append((_psym, False,
                                            "row has no Order ID - reload the trail proposals"))
                                        continue
                                    _oco0 = next((o for o in sell_gtts_by_symbol.get(_psym, [])
                                                  if str(o.get("order_id")) == _oid), None)
                                    if _oco0 is None:
                                        _exec_results.append((_psym, False,
                                            f"order {_oid} no longer live - reload the proposals"))
                                        continue
                                    _old_sl = _oco0["sl_trigger"]
                                    # TIGHTEN-ONLY, enforced at the point of execution and not
                                    # only at proposal time: the price cell is editable, so a
                                    # typo could otherwise LOOSEN a live stop.
                                    if _old_sl is not None and _new_sl <= float(_old_sl):
                                        _exec_results.append((_psym, False,
                                            f"refused: {_new_sl} would not tighten {_old_sl}"))
                                        continue
                                    _q = int(_pr.get("Qty") or _oco0.get("sl_qty") or _oco0.get("qty") or 0)
                                    _resp = dhan.modify_forever(
                                        order_id=_oid,
                                        order_flag="OCO",
                                        order_type=dhan.LIMIT,
                                        leg_name="STOP_LOSS_LEG",
                                        quantity=_q,
                                        price=round(_new_sl * 0.995, 2),   # limit buffer, same convention as gtt_auto_shield
                                        trigger_price=round(_new_sl, 2),
                                        disclosed_quantity=0,
                                        validity="DAY")
                                    _ok = isinstance(_resp, dict) and _resp.get("status") == "success"
                                    _exec_results.append((_psym, _ok, str(_resp.get("remarks") or _resp.get("data") or _resp)[:160]))
                                    if _ok:
                                        # persist to journal + audit trail
                                        try:
                                            import sqlite3 as _sq4
                                            _cn4 = _sq4.connect(journal_db_path())
                                            _cn4.execute("UPDATE journal SET manual_sl_override=? "
                                                         "WHERE symbol=? AND status='OPEN'", (_new_sl, _psym))
                                            _cn4.commit(); _cn4.close()
                                        except Exception:
                                            pass
                                        try:
                                            os.makedirs("logs", exist_ok=True)
                                            with open(os.path.join("logs", "risk_shield_actions.log"), "a", encoding="utf-8") as _alf:
                                                _alf.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} "
                                                           f"TIGHTEN_SL {_psym} {_old_sl} -> {_new_sl} "
                                                           f"order={_oco0['order_id']} resp={_resp}\n")
                                        except Exception:
                                            pass
                                except Exception as _pex:
                                    _exec_results.append((_psym, False, f"EXCEPTION: {_pex}"))
                            for _psym, _ok, _msg in _exec_results:
                                (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_psym}: {_msg}")
                            if not _exec_results:
                                st.info("No approved 'Tighten SL' rows to execute. "
                                        "(Trim / Pyramid actions are propose-only — execute those manually.)")
                            else:
                                st.session_state.pop("cached_hist_data_v4", None)
                        st.caption("Only 'Tighten SL' rows execute. Trim / Pyramid remain manual. "
                                   "Every execution is appended to logs/risk_shield_actions.log.")
                    else:
                        st.info("No actionable updates for today. Portfolio is optimized.")

                # ── Tab 1: Active Exits (OCO) ──
                with entry_tab1:
                    st.markdown('<div class="section-sub-lbl">🎯 Paired OCO Exits</div>', unsafe_allow_html=True)
                    if not sell_gtts_by_symbol:
                        st.info("No active OCO paired exits found.")
                    else:
                        oco_symbols = sorted(list(sell_gtts_by_symbol.keys()))
                        for idx in range(0, len(oco_symbols), 3):
                            row_items = oco_symbols[idx:idx+3]
                            cols = st.columns(3)
                            for col, sym in zip(cols, row_items):
                                with col:
                                    orders = sell_gtts_by_symbol[sym]
                                    # ORDER THE LEGS BY TARGET, not by whatever Dhan returned. The T1/T2 labels
                                    # and the policy flag below both key off o_idx, so a broker response in the
                                    # other order would silently mislabel the nearer target as T2 AND compare it
                                    # against the wrong policy R. Sorting makes the index mean what the label says.
                                    # Legs with no target sort last so they never claim the T1 slot.
                                    orders = sorted(orders, key=lambda _o: (_o.get('target_trigger') is None,
                                                                            _o.get('target_trigger') or 0))
                                    ltp = ltps.get(sym) or 0
                                    holding = holdings_map.get(sym)
                                    buy_price = holding["buy_price"] if holding else 0

                                    # Compute aggregates
                                    total_qty = sum(o.get("sl_qty") or o.get("qty") or 0 for o in orders)
                                    risk_exposure = sum((o.get("sl_qty") or o.get("qty") or 0) * (ltp - o["sl_trigger"]) for o in orders if ltp and o["sl_trigger"] is not None)

                                    # R-Multiple
                                    if holding and buy_price:
                                        total_risk_at_entry = sum((o.get("sl_qty") or o.get("qty") or 0) * (buy_price - o["sl_trigger"]) for o in orders if o["sl_trigger"] is not None)
                                        r_multiple = (ltp - buy_price) * total_qty / total_risk_at_entry if total_risk_at_entry > 0 else 0.0
                                        r_multiple_str = f"{r_multiple:+.2f}R"
                                    else:
                                        r_multiple = 0.0; r_multiple_str = "N/A"
                                    r_color = "var(--bull)" if r_multiple > 0 else "var(--bear)" if r_multiple < 0 else "var(--muted)"

                                    # SL/Target distances
                                    sl_vals = [o["sl_trigger"] for o in orders if o["sl_trigger"] is not None]
                                    tgt_vals = [o["target_trigger"] for o in orders if o["target_trigger"] is not None]
                                    # Nearest stop to LTP = the HIGHEST SL (all stops sit below price),
                                    # i.e. the one most likely to fire — that drives the danger warning.
                                    near_sl = max(sl_vals) if sl_vals else None
                                    min_sl_dist = ((ltp - near_sl) / ltp * 100) if ltp and near_sl else None

                                    # Single-line layout: Combined Entry and LTP percent context
                                    sl_parts = []; tgt_parts = []
                                    for o_idx, o in enumerate(orders):
                                        sl = o["sl_trigger"]; tgt = o["target_trigger"]
                                        if sl is not None:
                                            sl_str = f"SL <span style='color:var(--bear);font-weight:bold;'>₹{sl:,.0f}</span>"
                                            if buy_price and ltp:
                                                sl_d_e = (sl - buy_price) / buy_price * 100
                                                sl_d_l = (sl - ltp) / ltp * 100
                                                sl_str += f" (<span style='color:var(--muted)'>{sl_d_e:+.1f}%</span> / <span style='color:#38BDF8'>{sl_d_l:+.1f}%</span>)"
                                                # ATR MULTIPLE of the CURRENT stop (Jay, 11-Aug-2026).
                                                # Read from hist_data rather than atr_val, which is not
                                                # computed until ~40 lines below this block.
                                                #
                                                # TWO numbers because they answer different questions and
                                                # the tile already shows both percentages the same way:
                                                #   from ENTRY = the risk you TOOK  (this is the number the
                                                #                trade-type ladder's rung 3 classifies on,
                                                #                and the one that sets R)
                                                #   from LTP   = how much room the stop has NOW, i.e. how
                                                #                close it is to being hit
                                                # On a trailed stop these diverge sharply, and the second is
                                                # the one that decides whether today's noise takes you out.
                                                _atrp = (hist_data.get(sym) or {}).get("atr_pct")
                                                try:
                                                    _atr_abs = float(ltp) * float(_atrp) / 100.0
                                                except Exception:
                                                    _atr_abs = 0.0
                                                if _atr_abs > 0:
                                                    # ENTRY-RELATIVE ONLY (Jay, 11-Aug-2026:
                                                    # "calculate that with regard to entry price and not
                                                    # LTP"). The stop's ATR multiple is the risk you TOOK,
                                                    # measured from where you bought. The LTP-relative
                                                    # version answered a different question (how much room
                                                    # is left) and made the field two numbers when the one
                                                    # that matters is the first. Dropped.
                                                    #
                                                    # This is also the number the trade-type ladder's rung 3
                                                    # classifies on, so the tile now shows what drives the
                                                    # SWING/POSITIONAL verdict rather than hiding it.
                                                    _x_ent = (buy_price - sl) / _atr_abs
                                                    # A stop AT or ABOVE entry has no risk left to express as
                                                    # a multiple — it is locked profit. "-3.9×ATR entry"
                                                    # (LAURUSLABS, stop 1549.5 vs entry 1377.2) reads as a
                                                    # bug rather than the good news it is; 5 of 15 live
                                                    # positions are in that state.
                                                    _ent_txt = (f"{_x_ent:.1f}×ATR" if _x_ent > 0.05
                                                                else ("breakeven" if abs(_x_ent) <= 0.05
                                                                      else f"locked +{-_x_ent:.1f}×ATR"))
                                                    # Colour against the POLICY stops: 2.5x swing, 4.0x
                                                    # positional. Beyond 5x is wider than either policy
                                                    # allows and worth seeing (COALINDIA was entered at 7.2x).
                                                    _xc = ("var(--bear)" if _x_ent > 5.0 else
                                                           "var(--warn)" if _x_ent > 4.0 else "var(--faint)")
                                                    sl_str += (f" <span style='color:{_xc};font-size:0.78rem;' "
                                                               f"title='Stop distance from ENTRY in ATR — the risk "
                                                               f"you took, and what sets R. Policy: 2.5x swing / "
                                                               f"4.0x positional; above 5x is wider than either. "
                                                               f"ATR is current, so on a long-held position it is "
                                                               f"an approximation of the ATR at entry.'>"
                                                               f"[{_ent_txt}]</span>")
                                            sl_parts.append(sl_str)
                                        if tgt is not None:
                                            label = f"T{o_idx+1}"
                                            tgt_str = f"<span style='color:var(--bull);font-weight:bold;'>{label} ₹{tgt:,.0f}</span>"
                                            if buy_price and ltp:
                                                tgt_d_e = (tgt - buy_price) / buy_price * 100
                                                tgt_d_l = (tgt - ltp) / ltp * 100
                                                tgt_str += f" (<span style='color:var(--muted)'>{tgt_d_e:+.1f}%</span> / <span style='color:#38BDF8'>{tgt_d_l:+.1f}%</span>)"
                                                if sl is not None and (buy_price - sl) > 0:
                                                    r_val = (tgt - buy_price) / (buy_price - sl)
                                                    tgt_str += f" <span style='color:var(--warn);font-weight:bold;'>[{r_val:.1f}R]</span>"
                                                    # POLICY CHECK (9-Aug-2026). These are LIVE broker OCOs — changing the
                                                    # screener's targets does NOT move an order already resting at Dhan, so a
                                                    # book placed under the old 5R/10R policy keeps its unreachable targets
                                                    # forever. T1 was reached in 2% of POS trades at 5R; the partial and the
                                                    # move-to-breakeven never fired. Flagging the gap is the only way to see
                                                    # which orders still need re-placing.
                                                    # 10-Aug-2026, two fixes: the policy was read
                                                    # from the POSITIONAL constants for EVERY
                                                    # position (a swing order was judged against
                                                    # 4R and its tooltip said so), and only a
                                                    # target that was too FAR was flagged — a leg
                                                    # resting at 1R books the partial too early
                                                    # and was invisible. Now keyed on the setup
                                                    # via the screener's own target_r_for, and
                                                    # flagged in both directions.
                                                    try:
                                                        import bull_screener as _bs_pol
                                                        _setup_pol = (journal_overrides.get(sym, {}) or {}).get("setup") \
                                                            if isinstance(journal_overrides, dict) else None
                                                        _t1w, _t2w = _bs_pol.target_r_for(_setup_pol)
                                                        _want = _t1w if o_idx == 0 else _t2w
                                                        _far, _near = r_val > _want * 1.25, r_val < _want * 0.75
                                                        if _far or _near:
                                                            _why = ("too far - the partial and the move to "
                                                                    "breakeven may never fire" if _far else
                                                                    "too near - you book the partial before the "
                                                                    "trade has paid for its risk")
                                                            _basis = (f"setup {_setup_pol}" if _setup_pol
                                                                      else "no setup on the journal row, so the swing default")
                                                            tgt_str += (f" <span style='color:#F87171;font-weight:bold;' "
                                                                        f"title='Policy is {_want:.1f}R for this leg ({_basis}). "
                                                                        f"This order is {_why}. Re-place it.'>"
                                                                        f"&#9888; vs {_want:.1f}R</span>")
                                                    except Exception:
                                                        pass
                                            tgt_parts.append(tgt_str)

                                    header_entry = f"<b style='color:var(--faint);'>Entry ₹{buy_price:,.2f}</b>" if buy_price else "<b style='color:var(--faint);'>Entry: N/A</b>"
                                    header_ltp = f"<b style='color:#38BDF8;'>LTP ₹{ltp:,.2f}</b>" if ltp else "<b style='color:#38BDF8;'>LTP: N/A</b>"
                                    
                                    # Calculate ATR + is_swing first for Time Stop logic.
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    # ONE trade-type answer for the whole page (10-Aug-2026).
                                    # This tile used to read the structural classifier alone,
                                    # while the Chandelier a few hundred lines up read the
                                    # journal Timeframe — so a position could be labelled
                                    # SWING here and trailed on the 22-bar POSITIONAL clock.
                                    # risk_common.resolve_trade_type owns the precedence:
                                    # journal Timeframe -> setup prefix -> structural -> positional.
                                    _tt_struct = rs_trade_type.get(sym, (None, "UNKNOWN"))[0]
                                    _jov = journal_overrides.get(sym, {}) if isinstance(journal_overrides, dict) else {}
                                    is_swing, tt_label, _tt_src = _rc.resolve_trade_type(
                                        timeframe=_jov.get("timeframe"),
                                        setup=_jov.get("setup"),
                                        structural=_tt_struct,
                                        entry=buy_price, stop=_jov.get("stoploss"),
                                        atr_pct=(_tech or {}).get("atr_pct"))
                                    # DIAGNOSTIC (10-Aug-2026). "default" means every rung
                                    # abstained, and offline the same ladder answers for 8 of
                                    # 14 holdings — so an input is not arriving. Rather than a
                                    # fourth theory, record WHICH one is missing, once per
                                    # symbol per run. Delete once the tiles read correctly.
                                    if _tt_src == "default":
                                        _gm_logger.warning(
                                            "TT-DEFAULT %s | tf=%r setup=%r struct=%r "
                                            "entry=%r stop=%r atr=%r | jov_keys=%s",
                                            sym, _jov.get("timeframe"), _jov.get("setup"),
                                            _tt_struct, buy_price, _jov.get("stoploss"),
                                            (_tech or {}).get("atr_pct"),
                                            sorted(_jov.keys()) if _jov else "EMPTY")

                                    if _tech and _tech.get("atr_pct"):
                                        val = _tech.get("atr_pct")
                                        if isinstance(val, (int, float)) and val == val and val > 0:
                                            atr_val = (ltp * val) / 100

                                    if (not atr_val or atr_val != atr_val) and ltp:
                                        raw_atr = get_atr(sym)
                                        if raw_atr and raw_atr == raw_atr: atr_val = raw_atr

                                    if (not atr_val or atr_val != atr_val) and sl_vals and ltp:
                                        closest_sl = max(sl_vals)
                                        dist = ltp - closest_sl
                                        if dist > 0:
                                            # The SL distance is a last-resort ATR PROXY. It may
                                            # only speak to the trade type when nothing better
                                            # has: inferring "swing" from a tight stop would
                                            # otherwise overrule what you declared in the journal,
                                            # and the stop is the one number you move by hand.
                                            _sl_swing = (dist / ltp) < 0.08
                                            atr_val = dist / (1.5 if _sl_swing else 3.0)
                                            if _tt_src in ("structural", "default"):
                                                is_swing = _sl_swing
                                                tt_label = ("SWING" if is_swing else "POSITIONAL") + "?"

                                    # Compute Days Held & Time Stop Hit
                                    days_held = None
                                    if holding and holding.get("entry_date"):
                                        from datetime import date
                                        try:
                                            dt_parts = holding["entry_date"].split('-')
                                            entry_d = date(int(dt_parts[0]), int(dt_parts[1]), int(dt_parts[2]))
                                            days_held = (date.today() - entry_d).days
                                        except: pass

                                    # No time stop (Jay, 24-Sep-2026) — this tile ran its own 42/10-day clock,
                                    # a fifth definition. Exits are the stop, the trail and structure.
                                    time_stop_hit = False

                                    flags_html = ""
                                    cond_trim = False
                                    cond_add = False
                                    _pyr_reason = ""
                                    if _tech:
                                        _c5 = _tech.get("close_5d_ago")
                                        if _c5 and _c5 > 0 and ltp:
                                            _dist200 = _tech.get("dist_from_200", 0)
                                            _days_er = _tech.get("days_to_earnings")
                                            _sma200slp = _tech.get("sma200_slope", 0)
                                            _above200 = _tech.get("above200", False)
                                            _ema20 = _tech.get("ema20")
                                            
                                            _is_breakout = _tech.get("vol_breakout", False)
                                            if (_days_er is not None and _days_er <= 3):
                                                cond_trim = True
                                            elif not _is_breakout and (ltp > _c5 * 1.15 or _dist200 > 40.0):
                                                cond_trim = True
                                                
                                            if _above200 and _sma200slp > 0 and ltp <= _c5 * 1.10 and _ema20 and ltp > _ema20:
                                                cond_add = True

                                        _flags = []
                                        _pyr_rec = pyramid_class_dict.get(sym, {})
                                        _class = _pyr_rec.get("classification", "HOLD")
                                        _pyr_reason = _pyr_rec.get("trigger", "")
                                        
                                        if _class == "EXIT":
                                            _flags.append("<span style='background:#451A1A;color:var(--bear);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid #7F1D1D;'>⬇ EXIT</span>")
                                        elif _class == "TRIM":
                                            _flags.append("<span style='background:#451A1A;color:var(--warn);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid #78350F;'>✂️ TRIM</span>")
                                        elif _class == "REDUCE":
                                            _flags.append("<span style='background: var(--surface-3);color:#38BDF8;padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid #0284C7;'>◐ REDUCE</span>")
                                        elif _class == "ADD":
                                            _flags.append("<span style='background:var(--bull-bg);color:var(--bull);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid var(--bull);'>▲ ADD</span>")
                                        else:  # HOLD
                                            _flags.append("<span style='background: var(--surface-2);color:var(--muted);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid var(--muted);'>━ HOLD</span>")
                                        
                                        if time_stop_hit:
                                            _flags.append(f"<span style='background:var(--bear);color:var(--ground);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;'>⏰ TIME STOP HIT</span>")

                                        if _tech.get("vol_breakout"):
                                            _flags.append("<span style='background:var(--bull-bg);color:var(--bull);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid var(--bull);'>🚀 Breakout Vol</span>")
                                        elif _tech.get("vol_climax"):
                                            _flags.append("<span style='background:var(--bear);color:var(--ground);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;'>🚨 Vol Climax</span>")
                                        if _tech.get("days_to_earnings") is not None and _tech.get("days_to_earnings") <= 5:
                                            _flags.append(f"<span style='background:#78350F;color:var(--warn);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:700;'>⚠️ ER in {_tech.get('days_to_earnings')}d</span>")
                                        if _tech.get("chandelier_exit"):
                                            # #16: the WINDOW is shown because it is what actually diverges from
                                            # v67. v67 picks 14 vs 22 from the CATALYST PREFIX alone; Risk Shield
                                            # picks it from the trade-type ladder, whose first rung is the journal
                                            # Timeframe Jay declares. Those disagree whenever a declared SWING
                                            # carries a POS setup (or the reverse), and the levels then differ with
                                            # both surfaces correct by their own rule. Risk Shield is the
                                            # authoritative one -- v67 structurally cannot see the journal.
                                            # The old fallback string said "22D" even when the window was 14.
                                            _ce_lbl = (f"{_tech.get('ce_mult'):.1f}×/{_tech.get('ce_win') or 22}b·{_tech.get('ce_mult_src')}"
                                                       + ("·regime?" if _tech.get("bear_unknown") else "")) if _tech.get("ce_mult") else "no trail"
                                            # DISTANCE FROM LTP, in ATR (Jay, 11-Aug-2026: the initial SL
                                            # is measured from ENTRY, the TSL and Rec SL from LTP).
                                            # The multiplier in the badge (4.5×) is the Chandelier's own
                                            # setting, NOT how far the level actually sits from price — the
                                            # anchor is the 22-bar highest CLOSE, so the live gap drifts with
                                            # every new high and is usually nothing like 4.5×. That gap is
                                            # what decides whether today's range reaches it.
                                            _ce_gap = ""
                                            try:
                                                _a = float(ltp) * float(_tech.get("atr_pct")) / 100.0
                                                _ce_g = (float(ltp) - float(_tech.get("chandelier_exit"))) / _a   # not `_g`: that name is the shared dict-getter
                                                _ce_gap = f" · {_ce_g:.1f}×ATR below"
                                            except Exception:
                                                pass
                                            _flags.append(f"<span style='background: var(--surface-2);color:#C084FC;border:1.5px solid #7C3AED;padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:700;'>TSL({_ce_lbl}): ₹{_tech.get('chandelier_exit'):.0f}{_ce_gap}</span>")
                                        if _tech.get("invalid_ce_override"):
                                            _flags.append(f"<span style='background:#451A1A;color:var(--bear);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:700;'>⚠ invalid CE override ignored</span>")
                                        if _flags:
                                            flags_html = f"<div style='margin-bottom:8px;'>{''.join(_flags)}</div>"
                                            
                                    _oco_family = "SWG" if is_swing else "POS"
                                    # MIRROR THE BROKER, LEG BY LEG (22-Aug-2026, Jay: ANANDRATHI
                                    # showed "OCO-1 6 sh / OCO-2 7 sh" with only ONE OCO resting at
                                    # Dhan). This half is labelled "what is resting" and it was not
                                    # reading `orders` at all: it split total_qty 50/50 and paired
                                    # the halves with tgt_vals[0]/[1] and the single nearest stop.
                                    # With one leg that invents a second; with two unequal legs it
                                    # misreports both. Now one row per ACTUAL resting order, each
                                    # carrying its own quantity, target and stop.
                                    _mirror_rows = []
                                    _oco_n = 0
                                    for _oi, _o in enumerate(orders):
                                        _mq = int(_o.get("sl_qty") or _o.get("qty") or 0)
                                        _mt = _o.get("target_trigger")
                                        _ms = _o.get("sl_trigger")
                                        _mtxt = (f"T{_oi+1} ₹{_mt:,.2f}" if _mt is not None
                                                 else "<span style='color:var(--bear)'>no target leg</span>")
                                        _mstxt = (f"SL ₹{_ms:,.2f}" if _ms is not None
                                                  else "<span style='color:var(--bear)'>no SL leg</span>")
                                        # --bull, not --bull-rule: a RULE token is a border and
                                        # renders 1.63:1 on this card's ground. The ternary was also
                                        # dead -- both branches were identical.
                                        _mcol = "var(--bull)"
                                        _mwt = 700 if _oi == 0 else 600
                                        _msingle = str(_o.get("order_type") or "").upper() == "SINGLE"
                                        if _msingle:
                                            _mname = "SINGLE SL"
                                            _mcol = "var(--acc)"
                                        else:
                                            _mname = f"OCO-{_oco_n + 1}"
                                            _oco_n += 1
                                        _mirror_rows.append(
                                            f"<div style='color:{_mcol};font-weight:{_mwt};'>"
                                            f"• <b>{_mname} ({_mq} sh):</b> {_mtxt} | {_mstxt}</div>")
                                    if not _mirror_rows:
                                        _mirror_rows.append(
                                            "<div style='color:var(--bear);font-weight:600;'>"
                                            "nothing resting at Dhan for this symbol</div>")
                                    _mirror_html = "".join(_mirror_rows)
                                    # COVERAGE (22-Aug-2026, Jay). The card only ever described what
                                    # is RESTING, never whether it covers the position. On the live
                                    # book five symbols were short: ANANDRATHI 54 held / 13 covered,
                                    # CAPLIPOINT 98 / 27, SONACOMS 258 / 71. Nothing on this tile
                                    # said so, and the recommendation below was sized off the covered
                                    # subset - so it recommended protecting 13 of 54 shares.
                                    _held_qty = 0
                                    try:
                                        _held_qty = int((holding or {}).get("qty") or 0)
                                    except Exception:
                                        _held_qty = 0
                                    _naked = (_held_qty - total_qty) if _held_qty else 0
                                    if _held_qty and _naked > 0:
                                        _cover_html = (
                                            f"<div style='color:var(--bear);font-size:0.72rem;margin-top:4px;font-weight:700;'>"
                                            f"⚠ {_held_qty} sh held · {total_qty} covered · "
                                            f"<b>{_naked} UNPROTECTED</b></div>")
                                    elif _held_qty and _naked < 0:
                                        _cover_html = (
                                            f"<div style='color:var(--warn);font-size:0.72rem;margin-top:4px;font-weight:700;'>"
                                            f"⚠ {_held_qty} sh held but {total_qty} sh in exit orders — "
                                            f"over-covered by {-_naked}</div>")
                                    else:
                                        _cover_html = (
                                            f"<div style='color:var(--ink-2);font-size:0.72rem;margin-top:4px;'>"
                                            f"{len(orders)} order(s) resting · {total_qty} sh covered"
                                            + (" — fully protected" if _held_qty else "")
                                            + "</div>")
                                    # Kept for the blocks below that still read them. They are
                                    # AGGREGATES across the legs, not per-leg values.
                                    t1_price = tgt_vals[0] if len(tgt_vals) > 0 else (buy_price * 1.08 if buy_price else 0)
                                    t2_price = tgt_vals[1] if len(tgt_vals) > 1 else (tgt_vals[0] if len(tgt_vals) > 0 else (buy_price * 1.15 if buy_price else 0))
                                    sl_price = near_sl if near_sl else (buy_price * 0.94 if buy_price else 0)

                                    # ── RECOMMENDED half (10-Aug-2026, Jay) ─────────────────────
                                    # The existing card is a MIRROR of what is already at Dhan
                                    # (sl_price = near_sl, t1/t2 = the resting target legs) yet was
                                    # labelled "Plan", which reads as advice. Left half now says so
                                    # plainly; the right half is the actual recommendation, built
                                    # from POLICY rather than from the broker:
                                    #   SL   tighten-only max(resting SL, Chandelier) — the same rule
                                    #        gtt_auto_shield --trail applies. It never loosens.
                                    #   T1/2 bull_screener.target_r_for(setup) x R, anchored at ENTRY.
                                    #        R is FIXED AT ENTRY (entry - the original stop): using a
                                    #        trailing stop as the R unit would slide the targets down
                                    #        every time the stop moved up.
                                    #   qty  the family partial policy (replay.py:530) — POS/WYC/REV
                                    #        25/25 so half rides the trail uncapped, SWG 33/33,
                                    #        SWG-GAP/REV 50/50. The mirror hardcodes 50/50 for all.
                                    _r_sl = _r_t1 = _r_t2 = _ce_r = None
                                    _t1r = _t2r = 0.0
                                    _r_note = "—"
                                    try:
                                        import bull_screener as _bs_r
                                        _setup_r = str((_jov or {}).get("setup") or "")
                                        _t1r, _t2r = _bs_r.target_r_for(_setup_r, swing=is_swing)
                                        # R unit: prefer the journal's original stop; else the LOWEST
                                        # resting SL (least-trailed, closest to the original); else the
                                        # policy ATR stop. Whichever answers is named on the card.
                                        for _cand, _lbl in ((_jov.get("stoploss"), "journal SL"),
                                                            (min(sl_vals) if sl_vals else None, "oldest resting SL"),
                                                            ((buy_price - atr_val * (1.5 if is_swing else 4.0))
                                                             if (buy_price and atr_val) else None, "policy ATR stop")):
                                            try:
                                                _c = float(_cand)
                                            except Exception:
                                                continue
                                            if _c > 0 and buy_price and _c < buy_price:
                                                _runit = buy_price - _c
                                                _r_t1 = buy_price + _t1r * _runit
                                                _r_t2 = buy_price + _t2r * _runit
                                                _r_note = _lbl
                                                break
                                        _ce_r = _tech.get("chandelier_exit") if isinstance(_tech, dict) else None
                                        _cands = [float(x) for x in (near_sl, _ce_r) if x]
                                        _r_sl = max(_cands) if _cands else None
                                    except Exception as _e_r:
                                        _gm_logger.warning(f"{sym}: recommended OCO failed: {_e_r}")
                                    # ONE source for the split, paired with target_r_for's fallback.
                                    # A local ternary here fell back to POS (25/25) while
                                    # target_r_for fell back to SWG (3R/5R) — swing targets sized
                                    # like a positional trade on any blank setup.
                                    try:
                                        _p1, _p2 = _bs_r.partial_qty_for((_jov or {}).get("setup"), swing=is_swing)
                                    except Exception:
                                        _p1 = _p2 = 33
                                    # QUANTITIES (22-Aug-2026, Jay). Two defects, both live:
                                    #  (a) TRUNCATION. int(6 * 33 / 100) = int(1.98) = 1, so
                                    #      APOLLOHOSP read 1/1/4 where thirds of 6 are 2/2/2. The
                                    #      policy percentages are shorthand for fractions of the
                                    #      position, so allocate by largest remainder and let the
                                    #      buckets sum to the position exactly.
                                    #  (b) NO RE-BASE AFTER T1 FILLS. The split was always taken off
                                    #      the current holding as if all three legs were still to
                                    #      come. ANANDRATHI has 13 left with OCO-1 already executed
                                    #      and read 4 / 5 - four shares unaccounted for. Once T1 is
                                    #      banked the remaining policy is the T2 leg against the
                                    #      uncapped tail, re-normalised over what is actually left:
                                    #      33:34 of 13 = 6 and 7.
                                    # Ties go to the LAST bucket, so the uncapped tail absorbs the
                                    # odd share rather than the capped leg.
                                    def _alloc_qty(_total, _fracs):
                                        try:
                                            _total = int(_total or 0)
                                        except Exception:
                                            _total = 0
                                        if _total <= 0:
                                            return [0] * len(_fracs)
                                        _sum = float(sum(_fracs)) or 1.0
                                        _raw = [_total * float(_f) / _sum for _f in _fracs]
                                        _base = [int(_x) for _x in _raw]
                                        _rem = _total - sum(_base)
                                        _order = sorted(range(len(_fracs)),
                                                        key=lambda _i: (_raw[_i] - _base[_i], _i),
                                                        reverse=True)
                                        for _i in _order[:max(0, _rem)]:
                                            _base[_i] += 1
                                        return _base
                                    _fr = lambda v: f"₹{v:,.2f}" if v else "—"
                                    _slsrc = ("Chandelier" if (_r_sl and _ce_r and abs(_r_sl - float(_ce_r)) < 0.01)
                                              else "resting SL (already tighter)") if _r_sl else "—"
                                    # T1 ALREADY BANKED (17-Aug, Jay). The timeline block (~:17179) and
                                    # the unprotected-holdings block (~:17466) both suppress T1 once
                                    # `ltp >= rec_t1` — this card never did, so after OCO-1 filled it
                                    # kept recommending a target BELOW the live price while the timeline
                                    # beside it correctly showed only T2. Same defect class as the two
                                    # copies of the Rec block noted at :17462: one guard, three renderers.
                                    _t1_banked = bool(_r_t1) and bool(ltp) and ltp >= _r_t1
                                    _p_tail = max(0, 100 - _p1 - _p2)
                                    # SIZE OFF THE POSITION, NOT OFF WHAT HAPPENS TO BE RESTING
                                    # (22-Aug-2026, Jay). total_qty is the sum of the resting SL legs,
                                    # so on a partly-covered name the recommendation was a plan for
                                    # the covered fraction: ANANDRATHI (54 held, 13 covered) was sized
                                    # as if the position were 13. The recommendation answers "what
                                    # should be resting", so its base is the HOLDING. Falls back to
                                    # the covered quantity only when the holding is unknown, and the
                                    # card names which base it used.
                                    _rec_base = _held_qty if _held_qty else total_qty
                                    _base_note = ("" if _held_qty
                                                  else " \u00b7 holding unknown, sized off the resting legs")
                                    _rq1, _rq2, _rq_rest = _alloc_qty(_rec_base, [_p1, _p2, _p_tail])
                                    # WHETHER T1 IS ALREADY TAKEN IS NOT SOMETHING THIS CARD CAN KNOW.
                                    # It used to infer it from `ltp >= policy T1` and grey OCO-1 out -
                                    # which read as "already banked". On ANANDRATHI that was FALSE:
                                    # the trade history shows no sell in 60 days; the position is
                                    # simply well in profit with a trailed stop above entry, so the
                                    # policy T1 sits below price. Quantities no longer depend on the
                                    # guess. The conditional line below offers the re-based split and
                                    # says plainly that taking the partial is the precondition.
                                    _qty_basis = ""
                                    _row_t1 = (
                                        f"<div style='color:var(--warn);font-weight:700;'>• <b>OCO-1 ({_rq1} sh):</b> "
                                        f"T1 {_fr(_r_t1)} <span style='color:var(--muted)'>({_t1r:.1f}R)</span> | SL {_fr(_r_sl)} "
                                        f"<span style='color:var(--bear)'>— LTP is already above this target</span></div>"
                                    ) if _t1_banked else (
                                        f"<div style='color:var(--warn);font-weight:700;'>• <b>OCO-1 ({_rq1} sh):</b> "
                                        f"T1 {_fr(_r_t1)} <span style='color:var(--muted)'>({_t1r:.1f}R)</span> | SL {_fr(_r_sl)}</div>"
                                    )
                                    # NO RE-BASE LINE (22-Aug-2026, Jay: "for ANANDRATHI OCO-1 was
                                    # executed, but subsequently there was a pyramid"). That is the
                                    # case that kills the idea of adjusting the plan for history: the
                                    # position was reduced by a fill and then added to again, so
                                    # "what is left after OCO-1" is meaningless. The current holding
                                    # is the only correct base whatever route it took to get here,
                                    # and it always wants the full three orders. All the card owes
                                    # you is the fact that the policy T1 currently sits below price.
                                    _rebase_html = (
                                        f"<div style='color:var(--warn);font-size:0.72rem;margin-top:4px;"
                                        f"border-top:1px dashed var(--warn);padding-top:4px;'>"
                                        f"Note: LTP is above the policy T1, so that leg would fill on "
                                        f"placement. Quantities below are thirds of what you hold "
                                        f"NOW — they do not assume anything about earlier fills."
                                        f"</div>") if _t1_banked else ""
                                    _rec_rows = ((
                                        f"{_row_t1}"
                                        f"<div style='color:var(--warn);font-weight:600;'>• <b>OCO-2 ({_rq2} sh):</b> "
                                        f"T2 {_fr(_r_t2)} <span style='color:var(--muted)'>({_t2r:.1f}R)</span> | SL {_fr(_r_sl)}</div>"
                                        f"<div style='color:var(--muted);font-size:0.72rem;margin-top:4px;'>"
                                        f"{_rq_rest} sh on a SINGLE SL (the uncapped tail) · SL = {_slsrc} · R from {_r_note}{_base_note}</div>"
                                        f"{_rebase_html}"
                                    ) if (_r_t1 or _r_sl) else
                                        "<div style='color:var(--muted);'>no entry price or stop on record — cannot size R</div>")

                                    dhan_oco_card_html = f"""<div style='display:flex;gap:10px;margin-top:10px;font-size:0.8rem;'>
                                      <div style='flex:1;background:linear-gradient(145deg, #022C22 0%, #064E3B 100%);border:1.5px solid var(--bull);border-radius:8px;padding:10px 14px;'>
                                        <div style='color:var(--bull);font-weight:800;margin-bottom:4px;letter-spacing:0.5px;'>📌 AT DHAN NOW · what is resting ({_oco_family})</div>
                                        {_mirror_html}
                                        {_cover_html}
                                      </div>
                                      <div style='flex:1;background:linear-gradient(145deg, #2A1F05 0%, #4A3410 100%);border:1.5px solid var(--warn);border-radius:8px;padding:10px 14px;'>
                                        <div style='color:var(--warn);font-weight:800;margin-bottom:4px;letter-spacing:0.5px;'>🎯 RECOMMENDED · policy {_p1}/{_p2}/{_p_tail} ({_oco_family}) · on {_rec_base} sh</div>
                                        {_rec_rows}
                                      </div>
                                    </div>"""

                                    combined_line = f"{flags_html}<div style='margin-bottom:6px;'>{header_entry} / {header_ltp}</div><div>{', '.join(sl_parts) if sl_parts else '⚠️ No SL'} | {', '.join(tgt_parts) if tgt_parts else 'N/A'}</div>{dhan_oco_card_html}"

                                    qty_parts = []
                                    for o_idx, o in enumerate(orders):
                                        sl_q = o.get("sl_qty") or o.get("qty") or 0
                                        tgt_q = o.get("target_qty") or o.get("qty") or 0
                                        qty_parts.append(f"SL:{int(sl_q)} Tgt:{int(tgt_q)}")
                                    qty_str = " · ".join(qty_parts)
                                    # HOLDING QUANTITY (10-Aug-2026, Jay). The tile showed only the
                                    # ORDER-LEG quantities ("SL:19 Tgt:19"), never how many shares are
                                    # actually held — so a position only PARTLY covered by its OCOs
                                    # looked fully protected. That gap is the one that matters: it is
                                    # the uncovered shares that carry naked risk. Flagged in amber when
                                    # the legs do not add up to the holding.
                                    # THE NUMBER THAT SAID "held" WAS NOT THE HOLDING (22-Aug-2026, Jay:
                                    # "held 13 sh, whereas the actual quantity on Dhan is 54... I was
                                    # misled by the quantity 13 and created the orders earlier").
                                    # `total_qty` is the sum of the RESTING SL legs. This line printed it
                                    # as "held N sh" and then compared `_leg_sl_tot >= total_qty` - the
                                    # same quantity against itself - so the "only N covered" warning it
                                    # exists to raise could never fire, on any position, ever. A tile
                                    # covering 13 of 54 shares read "held 13 sh" in calm grey.
                                    # Six positions were affected: ANANDRATHI 13/54, SONACOMS 71/258,
                                    # CAPLIPOINT 27/98, APOLLOHOSP 6/11, COALINDIA 262/263, IKS 53/54.
                                    _leg_sl_tot = sum(int(o.get("sl_qty") or o.get("qty") or 0) for o in orders)
                                    if _held_qty:
                                        _short = _held_qty - _leg_sl_tot
                                        _cov_col = "var(--faint)" if _short <= 0 else "var(--warn)"
                                        _cov_txt = (f"held {_held_qty} sh"
                                                    + ("" if _short <= 0
                                                       else f" · ⚠ only {_leg_sl_tot} covered · "
                                                            f"{_short} UNPROTECTED"))
                                        qty_str = (f"<span style='color:{_cov_col};font-weight:700'>{_cov_txt}</span>"
                                                   + (f" · {qty_str}" if qty_str else ""))
                                    elif total_qty:
                                        # Holding unknown - say what this number IS rather than calling
                                        # it the holding.
                                        qty_str = (f"<span style='color:var(--faint);font-weight:700'>"
                                                   f"{int(total_qty)} sh in exit orders · holding unknown</span>"
                                                   + (f" · {qty_str}" if qty_str else ""))

                                    progress_bar_html = ""
                                    atr_sl = None
                                    rec_t1 = None
                                    rec_t2 = None
                                    rec_line = ""

                                    if ltp and atr_val and atr_val == atr_val and atr_val > 0:
                                        # ONE target policy (10-Aug-2026, Jay: "the Rec SL below the
                                        # level markers is different from the Recommended box").
                                        # It was: sl 4.5xATR from LTP, t1/t2 5x/10xATR from ENTRY.
                                        # Three faults in three lines —
                                        #   * 5x/10x is the OLD 5R/10R target policy, never updated
                                        #     when POS moved to 2R/4R;
                                        #   * 4.5 is the CHANDELIER TRAIL multiplier being used as an
                                        #     INITIAL stop, which is 4.0xATR;
                                        #   * the stop was measured from LTP while the targets were
                                        #     measured from ENTRY, so the printed R was neither.
                                        # Now: initial stop 4.0x (POS) / 1.5x (SWG) and targets from
                                        # target_r_for x R, both anchored at ENTRY — the same numbers
                                        # the RECOMMENDED half of the OCO card shows.
                                        sl_mult = 1.5 if is_swing else 4.0
                                        _anchor = buy_price if buy_price else ltp
                                        atr_sl = _anchor - (atr_val * sl_mult)
                                        _runit_r = _anchor - atr_sl
                                        try:
                                            import bull_screener as _bs_rl
                                            _t1r_l, _t2r_l = _bs_rl.target_r_for((_jov or {}).get("setup"), swing=is_swing)
                                        except Exception:
                                            # canon: swing 2R/4R, positional 3R/5R (was inverted)
                                            _t1r_l, _t2r_l = (2.0, 4.0) if is_swing else (3.0, 5.0)
                                        rec_t1 = _anchor + _t1r_l * _runit_r
                                        rec_t2 = _anchor + _t2r_l * _runit_r
                                        
                                        if len(orders) == 1 or len(tgt_vals) <= 1 or (rec_t1 and ltp >= rec_t1):
                                            rec_t1 = None
                                            
                                        # R is measured from the SAME anchor the levels are, so the
                                        # printed multiple is the trade's R and not "R from here".
                                        # Previously both were divided from LTP against a stop taken
                                        # from LTP, which is why GLAXO read 2.2R / 3.6R instead of
                                        # the policy's clean 2.0R / 4.0R.
                                        _rr_risk = _runit_r
                                        def _rr(t):
                                            if not t or not _rr_risk or _rr_risk <= 0:
                                                return ''
                                            return f' <span style="color:var(--faint)">({(t - _anchor) / _rr_risk:.1f}R)</span>'
                                        t1_str = f' | Rec T1: <span style="color:var(--warn);font-weight:bold;">₹{rec_t1:,.0f}</span>{_rr(rec_t1)}' if rec_t1 else ''
                                        t2_str = f' | Rec T2: <span style="color:var(--warn);font-weight:bold;">₹{rec_t2:,.0f}</span>{_rr(rec_t2)}' if rec_t2 else ''
                                        # Rec SL is LTP - sl_mult x ATR by construction, so naming the multiple makes
                                        # the basis explicit rather than leaving a bare number to compare
                                        # against the entry-relative hard SL beside it.
                                        rec_line = f'<div style="font-size:0.78rem;margin-top:8px;color:var(--ink-2);">Rec SL: <span style="color:#C084FC;font-weight:bold;">₹{atr_sl:,.0f}</span> <span style="color:var(--faint);font-size:0.72rem;">({sl_mult:.1f}×ATR from LTP)</span>{t1_str}{t2_str}</div>'
                                            
                                    if ltp:
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        time_stop_price = None   # no time stop (24-Sep-2026) — marker retired
                                        
                                        all_lows = []
                                        if sl_vals: all_lows.extend(sl_vals)
                                        if buy_price: all_lows.append(buy_price)
                                        if atr_sl: all_lows.append(atr_sl)
                                        if ema20: all_lows.append(ema20)
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier: all_lows.append(chandelier)
                                        if time_stop_price: all_lows.append(time_stop_price)
                                        if not all_lows: all_lows.append(ltp * 0.95)
                                        bar_min = min(all_lows) * 0.98
                                        
                                        all_highs = [ltp]
                                        if tgt_vals: all_highs.extend(tgt_vals)
                                        if rec_t2: all_highs.append(rec_t2)
                                        if ema20: all_highs.append(ema20)
                                        if chandelier: all_highs.append(chandelier)
                                        if time_stop_price: all_highs.append(time_stop_price)
                                        bar_max = max(all_highs) * 1.02
                                        
                                        bar_range = bar_max - bar_min
                                        if bar_range > 0:
                                            markers_html = ""
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                # TSL was a 3px sliver in the SAME purple (#C084FC) as the 12px Rec-SL
                                                # dot, so the dot painted over it whenever the two levels were
                                                # close and the trail simply looked absent (Jay: "the TSL bar
                                                # is missing from the stock tile timeline"). Own colour, wider,
                                                # taller, and drawn with a z-index so it can never be buried.
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-9px;width:5px;height:26px;background:var(--acc);border-radius:2px;transform:translateX(-50%);box-shadow:0 0 6px rgba(34,211,238,0.9);z-index:5;" title="TSL / Chandelier ₹{chandelier:,.2f}"></div>'
                                                # #18 (24-Aug-2026, Jay: "show the price on the TSL curve").
                                                # The level was only in the hover title, so the trail's actual
                                                # number needed a mouse to read - and the whole point of the
                                                # marker is that it is the price the position exits at. Sits
                                                # BELOW the bar (top:20px) so it cannot collide with the
                                                # marker glyphs above it, and rounds to whole rupees because
                                                # two decimals at 9px is unreadable and the paise never matter
                                                # for a stop level.
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:20px;transform:translateX(-50%);font-size:9px;font-weight:700;color:var(--acc);white-space:nowrap;letter-spacing:.02em;z-index:5;">&#8377;{chandelier:,.0f}</div>'
                                            if time_stop_price:
                                                ts_pos = (time_stop_price - bar_min) / bar_range * 100
                                                if time_stop_hit:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:4px;height:20px;background:var(--bear);border-radius:1px;transform:translateX(-50%);box-shadow:0 0 8px #EF4444;" title="Time Stop HIT! Held {days_held}d (0.5R = ₹{time_stop_price:,.2f})"></div>'
                                                else:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:3px;height:20px;background:var(--warn);border-radius:1px;transform:translateX(-50%);" title="Time Stop (0.5R) ₹{time_stop_price:,.2f}"></div>'
                                            if atr_sl:
                                                atr_pos = (atr_sl - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{atr_pos:.1f}%;top:-2px;width:12px;height:12px;background:#C084FC;border-radius:50%;transform:translateX(-50%);" title="AI Rec SL ₹{atr_sl:,.0f}"></div>'
                                            for sv in sl_vals:
                                                pos = (sv - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{pos:.1f}%;top:-3px;width:14px;height:14px;background:var(--bear);border-radius:50%;transform:translateX(-50%);" title="SL ₹{sv:,.0f}"></div>'
                                            if buy_price:
                                                entry_pos = (buy_price - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--faint);border-radius:50%;transform:translateX(-50%);" title="Entry ₹{buy_price:,.0f}"></div>'
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#38BDF8;border:2px solid var(--surface);border-radius:50%;transform:translateX(-50%);box-shadow:0 0 8px #38BDF8;" title="LTP ₹{ltp:,.0f}"></div>'
                                            
                                            for tv in tgt_vals:
                                                pos = (tv - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{pos:.1f}%;top:-3px;width:14px;height:14px;background:var(--bull);border-radius:50%;transform:translateX(-50%);" title="Actual Tgt ₹{tv:,.0f}"></div>'
                                                
                                            if rec_t1:
                                                t1_pos = (rec_t1 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t1_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--warn);border-radius:50%;transform:translateX(-50%);" title="Rec T1 ₹{rec_t1:,.0f}"></div>'
                                            if rec_t2:
                                                t2_pos = (rec_t2 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t2_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--warn);border-radius:50%;transform:translateX(-50%);" title="Rec T2 ₹{rec_t2:,.0f}"></div>'
                                                
                                            progress_bar_html = f'<div style="width:100%;background: var(--surface-2);height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'

                                    # Trail SL recommendation
                                    reco_parts = []
                                    for o_idx, o in enumerate(orders):
                                        tgt = o["target_trigger"]
                                        if tgt and ltp and ltp >= tgt:
                                            reco_parts.append(f"⚠️ LTP crossed T{o_idx+1} (₹{tgt:,.0f}) — consider trailing SL to entry ₹{buy_price:,.0f}")
                                    if min_sl_dist is not None and min_sl_dist <= 3.0:
                                        reco_parts.append(f"🔴 SL only {min_sl_dist:.1f}% away — high risk zone")
                                    elif min_sl_dist is not None and min_sl_dist <= 5.0:
                                        reco_parts.append(f"🟡 SL {min_sl_dist:.1f}% away — watch closely")
                                    if _pyr_reason:
                                        reco_parts.append(f"⚖️ Pyramid/Trim: {_pyr_reason}")
                                    reco_str = " · ".join(reco_parts) if reco_parts else "✅ Position in range"

                                    status_color = "var(--bear)" if min_sl_dist is not None and min_sl_dist <= 3.0 else "var(--warn)" if min_sl_dist is not None and min_sl_dist <= 5.0 else "var(--bull)"
                                    reco_color = "#F87171" if min_sl_dist is not None and min_sl_dist <= 3.0 else "var(--warn)" if min_sl_dist is not None and min_sl_dist <= 5.0 else "var(--bull)"

                                    ai_key = f"ai_exit_review_{sym}"
                                    trade_style_badge = _rs_type_badge(tt_label, _tt_src)
                                    ai_html = _rs_ai_card(st.session_state.get(ai_key))

                                    expand_btn = '<label class=\"expand-btn\" title=\"Toggle Fullscreen\" style=\"cursor:pointer;float:right;margin-top:-5px;color:var(--faint);\">⛶<input type=\"checkbox\" class=\"expand-toggle\" style=\"display:none;\"></label>'

                                    r_color = "var(--bull)" if r_multiple > 0 else "var(--bear)" if r_multiple < 0 else "var(--faint)"
                                    card_html = (
                                        f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-left:4px solid {status_color};border-radius:12px;padding:16px;margin-bottom:14px;box-shadow:0 4px 20px rgba(0,0,0,0.3);text-align:left;">'
                                        f'{expand_btn}'
                                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                        f'<div><span style="font-size:1.3rem;font-weight:800;color: var(--ink-2);vertical-align:middle;font-family:Rajdhani,sans-serif;letter-spacing:0.5px;">{sym}</span>'
                                        f'{trade_style_badge}'
                                        f'<span style="font-size:0.8rem;color:var(--faint);margin-left:8px;vertical-align:middle;">{qty_str}</span></div>'
                                        f'<div style="text-align:right;padding-right:20px;"><div style="font-size:0.78rem;color:var(--faint);">'
                                        f'R-Mult: <span style="font-family:JetBrains Mono;color:{r_color};font-weight:bold;">{r_multiple_str}</span>'
                                        f' · Risk: <span style="font-family:JetBrains Mono;color:var(--bear);font-weight:bold;">₹{risk_exposure:,.2f}</span></div></div></div>'
                                        f'{progress_bar_html}'
                                        f'{rec_line}'
                                        f'<div style="font-size:0.82rem;color:var(--ink-2);margin-top:6px;line-height:1.6;">'
                                        f'<div>{combined_line}</div></div>'
                                        f'<div style="margin-top:8px;font-size:0.8rem;line-height:1.35;color:{reco_color};font-weight:700;">{reco_str}</div>'
                                        f'{ai_html}</div>'
                                    )
                                    st.markdown(card_html, unsafe_allow_html=True)

                    # Standalone Exits
                    if single_sells:
                        single_sells = sorted(single_sells, key=lambda x: x["symbol"])
                        st.markdown("---")
                        st.markdown('<div class="section-sub-lbl">🛑 Standalone Exits</div>', unsafe_allow_html=True)
                        for idx in range(0, len(single_sells), 3):
                            row = single_sells[idx:idx+3]
                            cols = st.columns(3)
                            for col, s in zip(cols, row):
                                with col:
                                    sym = s["symbol"]; trigger = s["trigger"]
                                    ltp = ltps.get(sym) or s["price"] or 0
                                    dist = (ltp - trigger) / ltp * 100 if ltp else 0.0
                                    label = "Stop Loss" if trigger < ltp else "Target"
                                    color = "var(--bear)" if trigger < ltp else "var(--bull)"
                                    
                                    flags_html = ""
                                    # Compute Days Held
                                    days_held = None
                                    if h.get("entry_date"):
                                        from datetime import date
                                        try:
                                            dt_parts = h["entry_date"].split('-')
                                            entry_d = date(int(dt_parts[0]), int(dt_parts[1]), int(dt_parts[2]))
                                            days_held = (date.today() - entry_d).days
                                        except: pass

                                    # v2.2 safety: R is anchored to the catalyst-aware initial risk
                                    # (risk_common canon): SWG 1.5x ATR swing / POS 4.5x positional.
                                    # No ATR -> no time-stop verdict (n/a), never a fake one.
                                    time_stop_hit = False
                                    r_multiple_up = None
                                    if days_held is not None and bp and ltp:
                                        _atr_pct_ts = (hist_data.get(sym) or {}).get("atr_pct") or 0
                                        if _atr_pct_ts > 0:
                                            # v2.2: SWG 1.5× · POS 4.5× (risk_common canon)
                                            _ts_mult = 1.5 if is_swing else 4.5
                                            _risk_ps = (ltp * _atr_pct_ts / 100.0) * _ts_mult
                                            if _risk_ps > 0:
                                                r_multiple_up = (ltp - bp) / _risk_ps
                                        limit_days = 10 if is_swing else 42
                                        if r_multiple_up is not None and days_held >= limit_days and r_multiple_up < 0.5:
                                            time_stop_hit = True

                                    flags_html = ""
                                    cond_trim = False
                                    cond_add = False
                                    _pyr_reason = ""   # RS-P0: init outside the guard (NameError
                                                       # at the reason_line when technicals miss)
                                    _tech_flag = hist_data.get(sym)
                                    if _tech_flag:
                                        _c5 = _tech_flag.get("close_5d_ago")
                                        if _c5 and _c5 > 0 and ltp:
                                            _dist200 = _tech_flag.get("dist_from_200", 0)
                                            _days_er = _tech_flag.get("days_to_earnings")
                                            _sma200slp = _tech_flag.get("sma200_slope", 0)
                                            _above200 = _tech_flag.get("above200", False)
                                            _ema20 = _tech_flag.get("ema20")
                                            
                                            _is_breakout = _tech_flag.get("vol_breakout", False)
                                            if (_days_er is not None and _days_er <= 3):
                                                cond_trim = True
                                            elif not _is_breakout and (ltp > _c5 * 1.15 or _dist200 > 40.0):
                                                cond_trim = True
                                                
                                            if _above200 and _sma200slp > 0 and ltp <= _c5 * 1.10 and _ema20 and ltp > _ema20:
                                                cond_add = True

                                        _flags = []
                                        # Get classification from cache
                                        _pyr_rec = pyramid_class_dict.get(sym, {})
                                        _class = _pyr_rec.get("classification", "HOLD")
                                        _pyr_reason = _pyr_rec.get("trigger", "")
                                        
                                        if _class == "EXIT":
                                            _flags.append("<span style='background:var(--bear-bg);color:var(--bear);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:800;border:1px solid var(--bear-rule);'>⬇ EXIT</span>")
                                        elif _class == "TRIM":
                                            _flags.append("<span style='background:var(--warn-bg);color:var(--warn);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:800;border:1px solid var(--warn-rule);'>✂️ TRIM</span>")
                                        elif _class == "REDUCE":
                                            _flags.append("<span style='background:var(--acc-bg);color:var(--acc);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;border:1px solid var(--acc);'>◐ REDUCE</span>")
                                        elif _class == "ADD":
                                            _flags.append("<span style='background:var(--bull-bg);color:var(--bull);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;border:1px solid var(--bull);'>▲ ADD</span>")
                                        else:  # HOLD
                                            _flags.append("<span style='background:var(--surface-2);color:var(--ink-2);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;border:1px solid #555;'>━ HOLD</span>")
                                        
                                        if time_stop_hit:
                                            _flags.append(f"<span style='background:var(--bear);color:var(--ground);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⏰ TIME STOP HIT</span>")

                                        if _tech_flag.get("vol_breakout"): _flags.append("<span style='background:var(--bull);color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;'>🚀 Breakout Vol</span>")
                                        elif _tech_flag.get("vol_climax"): _flags.append("<span style='background:var(--bear);color:var(--ground);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>🚨 Vol Climax</span>")
                                        if _tech_flag.get("days_to_earnings") is not None and _tech_flag.get("days_to_earnings") <= 5: _flags.append(f"<span style='background:var(--warn);color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⚠️ ER in {_tech_flag.get('days_to_earnings')}d</span>")
                                        if _tech_flag.get("chandelier_exit"): _flags.append(f"<span style='background:var(--surface-2);color:var(--ink-2);border:1.5px solid var(--faint);padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>TSL(22D): ₹{_tech_flag.get('chandelier_exit'):.0f}</span>")
                                        if _flags: flags_html = f"<div style='margin-bottom:6px;'>{''.join(_flags)}</div>"
                                        
                                    expand_btn = '<label class="expand-btn" title="Toggle Fullscreen" style="cursor:pointer;float:right;margin-top:-5px;">⛶<input type="checkbox" class="expand-toggle" style="display:none;"></label>'
                                    ai_key = f"ai_single_review_{sym}_{s['order_id']}"
                                    ai_html = _rs_ai_card(st.session_state.get(ai_key))
                                    reason_line = f"<div style='font-size:0.75rem;margin-top:4px;color:var(--warn);font-weight:600;'>⚖️ Pyramid/Trim: {_pyr_reason}</div>" if _pyr_reason else ""
                                    st.markdown(f'<div class="metric-card" style="padding:14px;margin-bottom:10px;border-left:3px solid {color};text-align:left;">{expand_btn}<span style="font-size:1.1rem;font-weight:700;color:var(--acc);">{sym}</span> <span style="font-size:0.8rem;color:var(--muted);">Qty: {s["qty"]}</span><br>{flags_html}<span style="font-size:0.8rem;color:var(--ink);">LTP ₹{ltp:,.2f} → {label}: ₹{trigger:,.2f} ({dist:+.1f}%)</span>{reason_line}{ai_html}</div>', unsafe_allow_html=True)

                    # Unprotected Holdings
                    if unprotected_holdings:
                        unprotected_holdings = sorted(unprotected_holdings, key=lambda x: x["symbol"])
                        st.markdown("---")
                        st.markdown('<div class="section-sub-lbl">⚠️ Unprotected Holdings (No Stop Loss)</div>', unsafe_allow_html=True)
                        for idx in range(0, len(unprotected_holdings), 3):
                            row = unprotected_holdings[idx:idx+3]
                            cols = st.columns(3)
                            for col, h in zip(cols, row):
                                with col:
                                    sym = h["symbol"]; bp = h["buy_price"]; qty = h["qty"]
                                    ltp = ltps.get(sym) or h["ltp"] or 0
                                    pnl_pct = ((ltp - bp) / bp * 100) if bp else 0.0
                                    pnl_color = "var(--bull)" if pnl_pct >= 0 else "var(--bear)"
                                    
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    is_swing = False
                                    
                                    # Trade type from the ONE rule (this block used to hold a
                                    # SECOND copy of it whose ws_score default was 100 while
                                    # the OCO copy used 0 — they disagreed on a missing score)
                                    # and no longer from the AI's own "[Swing]" echo.
                                    # SAME resolver as the OCO tiles — this site read the raw
                                    # structural verdict directly, so the two halves of the page
                                    # could disagree on one symbol.
                                    _jov_u = journal_overrides.get(sym, {}) if isinstance(journal_overrides, dict) else {}
                                    _tt_sw, tt_label, _tt_src = _rc.resolve_trade_type(
                                        timeframe=_jov_u.get("timeframe"),
                                        setup=_jov_u.get("setup"),
                                        structural=rs_trade_type.get(sym, (None, "UNKNOWN"))[0])
                                    is_swing = bool(_tt_sw)
                                    if _tech:
                                        # RS-P0: .get with defaults — direct [] here crashed the tab
                                        # on a partial tech dict (unlike the OCO branch's guards).
                                        _ap = _tech.get("atr_pct") or 0.0
                                        atr_val = (ltp * _ap) / 100
                                    else:
                                        raw_atr = get_atr(sym)
                                        if raw_atr: atr_val = raw_atr

                                    progress_bar_html = ""
                                    atr_sl = None
                                    rec_t1 = None
                                    rec_t2 = None
                                    rec_line = ""
                                    
                                    if atr_val > 0 and bp and ltp:
                                        # SECOND COPY of the same stale block (unprotected
                                        # holdings). Same three faults as the OCO tiles: 4.5 is the
                                        # TRAIL multiplier used as an initial stop (policy is 4.0),
                                        # 5x/10x is the OLD 5R/10R target policy, and the stop was
                                        # anchored at LTP while the targets were anchored at ENTRY.
                                        # Two copies is why the fix had to be made twice — worth
                                        # collapsing into one helper next time this area is touched.
                                        sl_mult = 1.5 if is_swing else 4.0
                                        _anch2 = bp if bp else ltp
                                        rec_sl = _anch2 - (atr_val * sl_mult)
                                        _runit2 = _anch2 - rec_sl
                                        try:
                                            import bull_screener as _bs_u
                                            _t1r_u, _t2r_u = _bs_u.target_r_for(
                                                (journal_overrides.get(sym, {}) or {}).get("setup"),
                                                swing=is_swing)
                                        except Exception:
                                            # canon: swing 2R/4R, positional 3R/5R (was inverted)
                                            _t1r_u, _t2r_u = (2.0, 4.0) if is_swing else (3.0, 5.0)
                                        rec_t1 = _anch2 + _t1r_u * _runit2
                                        rec_t2 = _anch2 + _t2r_u * _runit2
                                        
                                        if ltp >= rec_t1:
                                            rec_t1 = None
                                        
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        time_stop_price = None
                                        if bp and atr_val:
                                            time_stop_price = bp + (0.5 * atr_val * sl_mult)
                                        
                                        bar_min_vals = [rec_sl, bp, ltp] + ([ema20] if ema20 else [])
                                        bar_max_vals = [rec_t2, bp, ltp] + ([ema20] if ema20 else [])
                                        if time_stop_price:
                                            bar_min_vals.append(time_stop_price)
                                            bar_max_vals.append(time_stop_price)
                                            
                                        bar_min = min(bar_min_vals) * 0.98
                                        bar_max = max(bar_max_vals) * 1.02
                                        bar_range = bar_max - bar_min
                                        
                                        markers_html = ""
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier:
                                            bar_min = min(bar_min, chandelier * 0.98)
                                            bar_max = max(bar_max, chandelier * 1.02)
                                            bar_range = bar_max - bar_min
                                            
                                        if bar_range > 0:
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-6px;width:3px;height:20px;background:#C084FC;border-radius:1px;transform:translateX(-50%);" title="TSL(22D) ₹{chandelier:,.2f}"></div>'
                                            if time_stop_price:
                                                ts_pos = (time_stop_price - bar_min) / bar_range * 100
                                                if time_stop_hit:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:4px;height:20px;background:var(--bear);border-radius:1px;transform:translateX(-50%);box-shadow:0 0 8px #EF4444;" title="Time Stop HIT! Held {days_held}d (0.5R = ₹{time_stop_price:,.2f})"></div>'
                                                else:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:3px;height:20px;background:var(--warn);border-radius:1px;transform:translateX(-50%);" title="Time Stop (0.5R) ₹{time_stop_price:,.2f}"></div>'
                                                    
                                            entry_pos = (bp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--faint);border-radius:50%;transform:translateX(-50%);" title="Entry ₹{bp:,.0f}"></div>'
                                            
                                            sl_pos = (rec_sl - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{sl_pos:.1f}%;top:-3px;width:14px;height:14px;background:#C084FC;border-radius:50%;transform:translateX(-50%);" title="Rec SL ₹{rec_sl:,.0f}"></div>'
                                            
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#38BDF8;border:2px solid var(--surface);border-radius:50%;transform:translateX(-50%);box-shadow:0 0 8px #38BDF8;" title="LTP ₹{ltp:,.0f}"></div>'
                                            if rec_t1:
                                                t1_pos = (rec_t1 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t1_pos:.1f}%;top:-3px;width:14px;height:14px;background:var(--bull);border-radius:50%;transform:translateX(-50%);" title="Rec T1 ₹{rec_t1:,.0f}"></div>'
                                            
                                            t2_pos = (rec_t2 - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{t2_pos:.1f}%;top:-3px;width:14px;height:14px;background:var(--bull);border-radius:50%;transform:translateX(-50%);" title="Rec T2 ₹{rec_t2:,.0f}"></div>'
                                            
                                        pb_html = f'<div style="width:100%;background: var(--surface-2);height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                        
                                        badge_html = _rs_type_badge(tt_label, _tt_src)
                                        
                                        # R from the same anchor as the levels — see the OCO tile.
                                        _rr_risk = _runit2
                                        def _rr(t, _px=_anch2, _rk=_rr_risk):
                                            if not t or not _rk or _rk <= 0:
                                                return ''
                                            return f' <span style="color:var(--faint)">({(t - _px) / _rk:.1f}R)</span>'
                                        t1_str = f' | Rec T1: <span style="color:var(--bull);font-weight:bold;">₹{rec_t1:,.0f}</span>{_rr(rec_t1)}' if rec_t1 else ''
                                        rec_line = f'<div style="font-size:0.78rem;color:var(--ink-2);margin-top:6px;line-height:1.6;">Rec SL: <span style="color:#C084FC;font-weight:bold;">₹{rec_sl:,.0f}</span>{t1_str} | Rec T2: <span style="color:var(--bull);font-weight:bold;">₹{rec_t2:,.0f}</span>{_rr(rec_t2)}</div>'
                                    elif bp and ltp:
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        bar_min_vals = [bp, ltp] + ([ema20] if ema20 else [])
                                        bar_max_vals = [bp, ltp] + ([ema20] if ema20 else [])
                                        bar_min = min(bar_min_vals) * 0.98
                                        bar_max = max(bar_max_vals) * 1.02
                                        bar_range = bar_max - bar_min
                                        
                                        markers_html = ""
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier:
                                            bar_min = min(bar_min, chandelier * 0.98)
                                            bar_max = max(bar_max, chandelier * 1.02)
                                            bar_range = bar_max - bar_min
                                            
                                        if bar_range > 0:
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-6px;width:3px;height:20px;background:#C084FC;border-radius:1px;transform:translateX(-50%);" title="TSL(22D) ₹{chandelier:,.2f}"></div>'
                                            entry_pos = (bp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--faint);border-radius:50%;transform:translateX(-50%);" title="Entry ₹{bp:,.0f}"></div>'
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#38BDF8;border:2px solid var(--surface);border-radius:50%;transform:translateX(-50%);box-shadow:0 0 8px #38BDF8;" title="LTP ₹{ltp:,.0f}"></div>'
                                        pb_html = f'<div style="width:100%;background: var(--surface-2);height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                
                                    expand_btn = '<label class="expand-btn" title="Toggle Fullscreen" style="cursor:pointer;float:right;margin-top:-5px;color:var(--faint);">⛶<input type="checkbox" class="expand-toggle" style="display:none;"></label>'
                                    ai_key = f"ai_unprotected_review_{sym}"
                                    ai_html = _rs_ai_card(st.session_state.get(ai_key))
                                        
                                    flags_html = ""
                                    _pyr_rec = pyramid_class_dict.get(sym, {})
                                    _class = _pyr_rec.get("classification", "HOLD")
                                    _pyr_reason = _pyr_rec.get("trigger", "")
                                    
                                    _flags = []
                                    if _class == "EXIT":
                                        _flags.append("<span style='background:#451A1A;color:var(--bear);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid #7F1D1D;'>⬇ EXIT</span>")
                                    elif _class == "TRIM":
                                        _flags.append("<span style='background:#451A1A;color:var(--warn);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid #78350F;'>✂️ TRIM</span>")
                                    elif _class == "REDUCE":
                                        _flags.append("<span style='background: var(--surface-3);color:#38BDF8;padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid #0284C7;'>◐ REDUCE</span>")
                                    elif _class == "ADD":
                                        _flags.append("<span style='background:var(--bull-bg);color:var(--bull);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid var(--bull);'>▲ ADD</span>")
                                    else:  # HOLD
                                        _flags.append("<span style='background: var(--surface-2);color:var(--muted);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:bold;border:1px solid var(--muted);'>━ HOLD</span>")
                                    
                                    if _tech:
                                        if _tech.get("vol_breakout"): _flags.append("<span style='background:var(--bull-bg);color:var(--bull);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;border:1px solid var(--bull);'>🚀 Breakout Vol</span>")
                                        elif _tech.get("vol_climax"): _flags.append("<span style='background:var(--bear);color:var(--ground);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:800;'>🚨 Vol Climax</span>")
                                        if _tech.get("days_to_earnings") is not None and _tech.get("days_to_earnings") <= 5: _flags.append(f"<span style='background:#78350F;color:var(--warn);padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:700;'>⚠️ ER in {_tech.get('days_to_earnings')}d</span>")
                                        if _tech.get("chandelier_exit"): _flags.append(f"<span style='background: var(--surface-2);color:#C084FC;border:1.5px solid #7C3AED;padding:3px 8px;border-radius:6px;font-size:0.72rem;margin-right:6px;font-weight:700;'>TSL(22D): ₹{_tech.get('chandelier_exit'):.0f}</span>")
                                    if _flags: flags_html = f"<div style='margin-bottom:8px;'>{''.join(_flags)}</div>"
                                        
                                    reason_line = f"<div style='font-size:0.78rem;margin-top:6px;color:var(--warn);font-weight:600;'>⚖️ Pyramid/Trim: {_pyr_reason}</div>" if _pyr_reason else ""
                                    card_html = (
                                        f'<div style="background:linear-gradient(145deg, #2D1517 0%, #1F1315 100%);border:1.5px solid #7F1D1D;border-left:4px solid var(--bear);border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 4px 20px rgba(0,0,0,0.3);text-align:left;">'
                                        f'{expand_btn}'
                                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                        f'<div><span style="font-size:1.3rem;font-weight:800;color: var(--ink-2);font-family:Rajdhani,sans-serif;letter-spacing:0.5px;vertical-align:middle;">{sym}</span>{badge_html}'
                                        f' <span style="font-size:0.8rem;color:#F87171;font-weight:800;margin-left:8px;">⚠️ NO SL</span></div>'
                                        f'<div style="font-size:0.8rem;color:var(--faint);padding-right:20px;">Qty: {qty}</div></div>'
                                        f'{flags_html}'
                                        f'{pb_html}'
                                        f'<div style="font-size:0.82rem;color:var(--ink-2);line-height:1.6;">'
                                        f'Cost ₹{bp:,.2f} → LTP <b style="color:#38BDF8;">₹{ltp:,.2f}</b> <span style="color:{pnl_color};font-weight:bold;">({pnl_pct:+.1f}%)</span>'
                                        f'</div>'
                                        f'{rec_line}'
                                        f'{reason_line}'
                                        f'{ai_html}</div>'
                                    )
                                    st.markdown(card_html, unsafe_allow_html=True)

                # ── Tab 2: Pyramid/Trim ──
                with entry_tab2:
                    try:
                        import pyramid_logic as pl
                        pl.render_pyramid_trim(st.session_state.pyramid_classifications)
                    except Exception as _pe:
                        st.error(f"Pyramid / Trim Manager failed to load: {_pe}")

                # ── Tab 3: Pullback Entries (GTT) ──
                with entry_tab3:
                    st.markdown('<div class="section-sub-lbl">🛒 Pending Pullback Buy Entries (GTT)</div>', unsafe_allow_html=True)
                    if not buy_gtts:
                        st.info("No pending pullback GTT buy orders found.")
                    else:
                        buy_gtts = sorted(buy_gtts, key=lambda x: x["symbol"])
                        for idx in range(0, len(buy_gtts), 3):
                            row = buy_gtts[idx:idx+3]
                            cols = st.columns(3)
                            for col, b in zip(cols, row):
                                with col:
                                    sym = b["symbol"]; trigger = b["trigger"]; price = b["price"]
                                    ltp = ltps.get(sym) or 0
                                    # Distance to the buy trigger, always expressed as |gap| from LTP.
                                    gap_pct = abs(ltp - trigger) / ltp * 100 if ltp else 0.0
                                    # Two entry styles: trigger ABOVE LTP = breakout buy-stop (waits for
                                    # price to confirm by rising into it — Jay's preferred entry); trigger
                                    # BELOW LTP = dip buy-limit (fills automatically on the touch, no
                                    # confirmation). Flag the latter so it isn't a blind zone-buy.
                                    if not ltp:
                                        kind_lbl = ""; status = "LTP: N/A"; dist_color = "var(--ink-2)"; border = "var(--warn)"
                                    elif trigger > ltp:
                                        kind_lbl = "Breakout buy-stop"
                                        dist_color = "var(--bull)" if gap_pct <= 2 else "var(--acc)"
                                        status = f"🟢 {gap_pct:.1f}% below trigger — waiting for breakout confirmation"
                                        border = "var(--bull)"
                                    elif gap_pct <= 0.5:
                                        kind_lbl = "Dip buy-limit"
                                        dist_color = "var(--warn)"; border = "var(--warn)"
                                        status = f"🟡 At trigger — fills on touch (no confirmation)"
                                    else:
                                        kind_lbl = "Dip buy-limit"
                                        dist_color = "var(--warn)" if gap_pct <= 3 else "var(--muted)"; border = "var(--warn)"
                                        status = f"{'🟡' if gap_pct <= 3 else '⚪'} {gap_pct:.1f}% above trigger — waiting for pullback (resting limit, no confirmation)"
                                    pb_html = ""
                                    if ltp and trigger:
                                        _tech = hist_data.get(sym)
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        bar_min_vals = [ltp, trigger, price] + ([ema20] if ema20 else [])
                                        bar_max_vals = [ltp, trigger, price] + ([ema20] if ema20 else [])
                                        bar_min = min(bar_min_vals) * 0.99
                                        bar_max = max(bar_max_vals) * 1.01
                                        bar_range = bar_max - bar_min
                                        
                                        if bar_range > 0:
                                            markers_html = ""
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            trigger_pos = (trigger - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{trigger_pos:.1f}%;top:-3px;width:14px;height:14px;background:var(--warn);border-radius:50%;transform:translateX(-50%);" title="Trigger ₹{trigger:,.2f}"></div>'
                                            
                                            if price != trigger:
                                                limit_pos = (price - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{limit_pos:.1f}%;top:-2px;width:12px;height:12px;background:var(--muted);border-radius:50%;transform:translateX(-50%);" title="Limit ₹{price:,.2f}"></div>'
                                            
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:var(--acc);border:2px solid var(--surface);border-radius:50%;transform:translateX(-50%);" title="LTP ₹{ltp:,.2f}"></div>'
                                            
                                            pb_html = f'<div style="width:100%;background:var(--rule);height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                
                                    kind_html = f' <span style="font-size:0.75rem;color:var(--faint);">· {kind_lbl}</span>' if kind_lbl else ""
                                    
                                    setup_warning_html = ""
                                    _tech_dict = hist_data.get(sym)
                                    if _tech_dict:
                                        if _tech_dict.get("ws_score", 100) < 50 or _tech_dict.get("sma200_slope", 0) < 0:
                                            setup_warning_html = '<div style="font-size:0.75rem;color:var(--bear);font-weight:bold;margin-top:6px;">🚨 INVALID SETUP WARNING (WS Score < 50 or SMA200 slope < 0)</div>'
                                            border = "var(--bear)"
                                            
                                    entry_line = f"<b style='color:var(--warn);'>Trigger ₹{trigger:,.2f}</b> (Limit ₹{price:,.2f})"
                                    ltp_line = f"<b style='color:#38BDF8;'>LTP ₹{ltp:,.2f}</b> — <span style='color:{dist_color};font-weight:bold;'>{status}</span>" if ltp else "LTP: N/A"
                                
                                    ai_key = f"ai_entry_review_{sym}_{b['order_id']}"
                                    trade_style_badge = _rs_type_badge(rs_trade_type.get(sym, (None, "UNKNOWN"))[1])

                                    card = (
                                        f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-left:4px solid {border};border-radius:12px;padding:16px;margin-bottom:14px;box-shadow:0 4px 20px rgba(0,0,0,0.3);text-align:left;">'
                                        f'<span style="font-size:1.3rem;font-weight:800;color: var(--ink-2);font-family:Rajdhani,sans-serif;letter-spacing:0.5px;">{sym}</span>{trade_style_badge}'
                                        f' <span style="font-size:0.8rem;color:var(--faint);">Qty: {b["qty"]}</span>{kind_html}'
                                        f'{pb_html}'
                                        f'<div style="font-size:0.82rem;color:var(--ink-2);margin-top:6px;line-height:1.6;">'
                                        f'<div>{entry_line}</div><div style="margin-top:3px;">{ltp_line}</div>{setup_warning_html}</div>'
                                        f'{_rs_ai_card(st.session_state.get(ai_key))}</div>'
                                    )
                                    st.markdown(card, unsafe_allow_html=True)

                # ── Tab 4: Risk Profile ──
                with entry_tab_cq:
                    # CAPITAL QUEUE (25-Sep-2026) — the next rupee: ADD-rated holdings and new
                    # GO names on one scale, funded by EXITs. capital_queue.py is the single
                    # engine; the Trigger Board renders the same block.
                    try:
                        import capital_queue as _cq
                        _cq_exit_toggle("cq_exits_rs")
                        if st.button("🔄 Rebuild queue", key="cq_rebuild_rs"):
                            st.session_state.pop("cq_res", None)
                        if "cq_res" not in st.session_state:
                            with st.spinner("Building the capital queue (board tabs + book + sector cap)..."):
                                st.session_state["cq_res"] = _cq_build_now()
                        _cq.render(st, st.session_state["cq_res"])
                    except Exception as _cqe:
                        st.error(f"Capital queue failed: {type(_cqe).__name__}: {_cqe}")

                with entry_tab4:
                    st.markdown('<div class="section-sub-lbl">📊 Risk Exposure & Allocation Analytics</div>', unsafe_allow_html=True)
                    _equity_rp = float(total_portfolio_value or 0.0) + float(app_state.balance or 0.0)
                    portfolio_risk_pct = (total_risk / _equity_rp) * 100 if _equity_rp > 0 else 0.0
                    if portfolio_risk_pct <= 1.0:
                        risk_grade = "A+ (Excellent)"
                        risk_grade_color = "var(--bull)"
                    elif portfolio_risk_pct <= 2.0:
                        risk_grade = "A (Good)"
                        risk_grade_color = "var(--bull)"
                    elif portfolio_risk_pct <= 5.0:
                        risk_grade = "B (Moderate)"
                        risk_grade_color = "var(--warn)"
                    else:
                        risk_grade = "C (High Risk)"
                        risk_grade_color = "var(--bear)"

                    st.markdown(
                        f'<div style="background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);border: 1.5px solid var(--rule);border-top:4px solid {risk_grade_color};border-radius:12px;padding:20px;text-align:center;margin-bottom:18px;box-shadow:0 4px 20px rgba(0,0,0,0.3);">'
                        f'<div style="font-size:0.78rem;font-weight:700;color:var(--faint);letter-spacing:1px;text-transform:uppercase;font-family:JetBrains Mono;">Total Open Heat & Risk Grade</div>'
                        f'<div style="color:{risk_grade_color};font-size:2.2rem;font-weight:900;margin-top:6px;font-family:JetBrains Mono;">{portfolio_risk_pct:.1f}% ({risk_grade})</div>'
                        f'<div style="font-size:0.85rem;color:var(--ink-2);margin-top:8px;line-height:1.5;">'
                        f'Total capital at risk from current LTP to Stop Loss is <b style="color:var(--bear);">₹{format_inr_int(total_risk)}</b> '
                        f'on total portfolio equity of <b style="color:#38BDF8;">₹{format_inr_int(_equity_rp)}</b> '
                        f'(holdings ₹{format_inr_int(total_portfolio_value)} + cash ₹{format_inr_int(app_state.balance)}).'
                        f'</div></div>', unsafe_allow_html=True
                    )

                    # Per-stock risk breakdown
                    st.markdown('<div class="section-sub-lbl">Per-Stock Risk Breakdown</div>', unsafe_allow_html=True)
                    risk_rows = []
                    for sym, orders in sell_gtts_by_symbol.items():
                        ltp = ltps.get(sym) or 0
                        _tech = hist_data.get(sym)
                        for o in orders:
                            sl = o["sl_trigger"]; sl_qty = o.get("sl_qty") or o.get("qty") or 0
                            if ltp and sl:
                                current_risk = sl_qty * (ltp - sl)
                                if current_risk > 0:
                                    # RS-P0 (14-Jul-2026): divide by EQUITY (holdings+cash), not idle
                                    # cash — the headline grade was fixed to equity on 05-Jul but this
                                    # per-row column kept the cash denominator (absurd %s at low cash).
                                    portfolio_pct = (current_risk / max(_equity_rp, 1)) * 100
                                    
                                    row_data = {
                                        "Symbol": sym, 
                                        "LTP": f"₹{ltp:,.2f}", 
                                        "SL": f"₹{sl:,.2f}",
                                    }
                                    
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    atr_pct = 0.0
                                    is_swing = False
                                    ws_score = None
                                    
                                    # Third copy of the trade-type rule — also routed through
                                    # the ONE engine call, and no longer seeded from the AI's
                                    # own label.
                                    _tt_sw, _tt_lb = rs_trade_type.get(sym, (None, "UNKNOWN"))
                                    is_swing = bool(_tt_sw)
                                    if _tech:
                                        # RS-P0: .get with defaults (KeyError on partial tech dict)
                                        atr_pct = _tech.get("atr_pct") or 0.0
                                        atr_val = (ltp * atr_pct) / 100
                                        ws_score = _tech.get("ws_score")
                                    elif ltp:
                                        raw_atr = get_atr(sym)
                                        if raw_atr:
                                            atr_val = raw_atr
                                            atr_pct = (raw_atr / ltp) * 100

                                    # "UNKNOWN" must not silently render as POSITIONAL in the table.
                                    row_data["Style"] = _tt_lb
                                    
                                    # A3 FIX (2026-07-04 audit): guard the ltp division — missing
                                    # LTP rows must show "—", not crash or fake a distance.
                                    if not ltp or ltp <= 0:
                                        row_data["ATR %"] = f"{atr_pct:.2f}%" if atr_pct > 0 else "N/A"
                                        row_data["SL Dist"] = "— (no LTP)"
                                    elif atr_pct > 0:
                                        row_data["ATR %"] = f"{atr_pct:.2f}%"
                                        dist_pct = ((ltp - sl) / ltp) * 100
                                        atr_dist = dist_pct / atr_pct
                                        row_data["SL Dist"] = f"{dist_pct:.1f}% ({atr_dist:.1f} ATR)"
                                    else:
                                        row_data["ATR %"] = "N/A"
                                        row_data["SL Dist"] = f"{((ltp - sl) / ltp) * 100:.1f}%"
                                        
                                    row_data["W-Score"] = f"{ws_score}/80" if ws_score is not None else "N/A"
                                    
                                    row_data["Risk ₹"] = f"₹{current_risk:,.0f}"
                                    row_data["% Port"] = f"{portfolio_pct:.2f}%"
                                    
                                    risk_rows.append(row_data)
                    if risk_rows:
                        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)
                        
                        st.markdown('<div class="section-sub-lbl" style="margin-top:20px;">Market Persona (Stage Analysis)</div>', unsafe_allow_html=True)
                        stage_counts = {"Stage 2 🟢": 0, "Stage 1/3 🟡": 0, "Stage 4 🔴": 0}
                        
                        # Count unique symbols in portfolio
                        analyzed_symbols = set()
                        for sym in sell_gtts_by_symbol.keys():
                            if sym not in analyzed_symbols:
                                _tech = hist_data.get(sym)
                                ltp = ltps.get(sym) or 0
                                if _tech and ltp:
                                    sma200 = _tech.get("sma200", 0)
                                    sma200_slope = _tech.get("sma200_slope", 0)
                                    if sma200:
                                        if ltp > sma200 and sma200_slope > 0:
                                            stage_counts["Stage 2 🟢"] += 1
                                        elif ltp < sma200 and sma200_slope < 0:
                                            stage_counts["Stage 4 🔴"] += 1
                                        else:
                                            stage_counts["Stage 1/3 🟡"] += 1
                                    analyzed_symbols.add(sym)
                                    
                        total_analyzed = sum(stage_counts.values())
                        if total_analyzed > 0:
                            sc1, sc2, sc3 = st.columns(3)
                            sc1.metric("Stage 2 (Advancing)", f"{stage_counts['Stage 2 🟢']} ({stage_counts['Stage 2 🟢']/total_analyzed*100:.0f}%)")
                            sc2.metric("Stage 1/3 (Transition)", f"{stage_counts['Stage 1/3 🟡']} ({stage_counts['Stage 1/3 🟡']/total_analyzed*100:.0f}%)")
                            sc3.metric("Stage 4 (Declining)", f"{stage_counts['Stage 4 🔴']} ({stage_counts['Stage 4 🔴']/total_analyzed*100:.0f}%)")
                    else:
                        st.info("No measurable risk from current positions (all stops are above LTP or no positions).")

                # ── Tab 5: Settings & Overrides ──
                with entry_tab5:
                    st.markdown('<div class="section-sub-lbl">⚙️ Manual SL & Multiplier Overrides</div>', unsafe_allow_html=True)
                    st.markdown('<div style="font-size:0.85rem; color:var(--muted); margin-bottom:12px;">Configure persistent manual overrides for positions. These overrides are saved to the database and will bypass the dynamic mechanical rules.</div>', unsafe_allow_html=True)

                    # A7: manual-SL override semantics (applies to all manual overrides)
                    _rs_c1, _rs_c2 = st.columns(2)
                    with _rs_c1:
                        if "rs_sl_override_mode" not in st.session_state:
                            st.session_state["rs_sl_override_mode"] = _gm_settings().get("sl_override_mode", "Floor")
                        st.radio("Manual SL mode", ["Floor", "Exact"], horizontal=True, key="rs_sl_override_mode",
                                 on_change=lambda: _gm_settings_save(
                                     sl_override_mode=st.session_state.get("rs_sl_override_mode", "Floor")),
                                 help="Floor (default): the Chandelier can only be TIGHTENED to your manual SL, never loosened. "
                                      "Exact: your manual SL is used verbatim, even if it sits below the computed Chandelier. "
                                      "Saved to GM settings, so the 15:45 GTT trailer applies the same rule.")
                    with _rs_c2:
                        # B3: the heat budget now follows the house rule (house_policy.py) instead
                        # of a session-only input that defaulted to the retired 0.25%.
                        st.caption(f"Risk per trade (house rule, `house_policy.py`): {_HP.risk_label()}. "
                                   "The Portfolio Heat card budgets each open position at that rate.")

                    if 'df_active_global' in globals() and not app_state.df_active_global.empty:
                        # Extract current open positions
                        override_rows = []
                        for _, r in app_state.df_active_global.iterrows():
                            sym = r.get("Symbol")
                            if pd.notna(sym):
                                override_rows.append({
                                    "Symbol": sym,
                                    "Manual SL Override": float(r.get("Manual SL Override", 0)) if pd.notna(r.get("Manual SL Override")) and str(r.get("Manual SL Override")).strip() else None,
                                    "Custom CE Mult": float(r.get("Custom CE Mult", 0)) if pd.notna(r.get("Custom CE Mult")) and str(r.get("Custom CE Mult")).strip() else None,
                                    "Pyramid Status": str(r.get("Pyramid Status", "")) if pd.notna(r.get("Pyramid Status")) else ""
                                })
                        
                        if override_rows:
                            df_overrides = pd.DataFrame(override_rows)
                            edited_overrides = st.data_editor(
                                df_overrides,
                                column_config={
                                    "Symbol": st.column_config.TextColumn("Symbol", disabled=True),
                                    "Manual SL Override": st.column_config.NumberColumn("Manual SL Override (₹)", format="%.2f", step=0.05, min_value=0.0),
                                    # A4: 0/negative multipliers are invalid — enforce at input
                                    "Custom CE Mult": st.column_config.NumberColumn("Custom CE Multiplier", format="%.1f", step=0.1, min_value=0.5, max_value=8.0,
                                                                                     help="0.5–8.0. Leave blank to use the system/catalyst multiplier."),
                                    "Pyramid Status": st.column_config.SelectboxColumn("Pyramid Status", options=["", "Initial", "Scaled", "Maxed"])
                                },
                                hide_index=True,
                                use_container_width=True
                            )
                            # A10 FIX (2026-07-04 audit): the save button was a MOCK —
                            # edits were silently discarded. Now persists to the journal DB
                            # (same columns the read path at journal_overrides consumes).
                            if st.button("💾 Save Overrides to Database", type="primary"):
                                try:
                                    import sqlite3 as _sq3
                                    _conn_ov = _sq3.connect(journal_db_path())
                                    _cur_ov = _conn_ov.cursor()
                                    _nsaved = 0
                                    for _, _orow in edited_overrides.iterrows():
                                        _cur_ov.execute(
                                            "UPDATE journal SET manual_sl_override=?, custom_ce_mult=?, "
                                            "pyramid_status=? WHERE symbol=? AND status='OPEN'",
                                            (float(_orow["Manual SL Override"]) if pd.notna(_orow["Manual SL Override"]) else None,
                                             float(_orow["Custom CE Mult"]) if pd.notna(_orow["Custom CE Mult"]) else None,
                                             str(_orow["Pyramid Status"]) if pd.notna(_orow["Pyramid Status"]) else "",
                                             str(_orow["Symbol"])))
                                        _nsaved += _cur_ov.rowcount
                                    _conn_ov.commit(); _conn_ov.close()
                                    st.session_state.pop("cached_hist_data_v4", None)  # recompute Chandeliers
                                    st.session_state.pop("pyramid_classifications", None)
                                    st.success(f"✅ Overrides saved — {_nsaved} journal row(s) updated. "
                                               f"Chandeliers will recompute on next refresh.")
                                except Exception as _ove:
                                    st.error(f"❌ Override save FAILED — nothing written: {_ove}")
                        else:
                            st.info("No open positions found in the journal to override.")
                    else:
                        st.info("Journal data not loaded.")
