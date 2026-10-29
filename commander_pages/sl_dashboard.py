# commander_pages/sl_dashboard.py - 🎚️ SL DASHBOARD (28-Oct-2026).
#
# Jay: "To have all the SL activity in one place." One lane per holding with every stop and
# target on it, all lanes on ONE axis (distance from LTP in daily ATR, or in %), so the book
# reads at a glance on a wide monitor; a triage list; the table underneath.
# Engine: sl_board.py (Streamlit-free). Nothing here places, moves or cancels an order.
# Runs in the app's namespace via commander_pages.run('sl_dashboard', globals()).
if True:
    import math as _m
    import os as _os
    import pandas as _pd
    import plotly.graph_objects as _go
    import sl_board as _sb
    from commander_core import format_inr_int as _ri

    st.markdown('<div class="page-title">🎚️ SL Dashboard · every stop of the book</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Thesis SL = a Daily CLOSE below it ends the idea (never an order) // '
                'Disaster SL = the resting Dhan stop, for gaps and news // the size is set off the Disaster SL, '
                'so a wider stop needs fewer shares</div>', unsafe_allow_html=True)

    @st.cache_data(ttl=300, show_spinner="Reading Dhan holdings, resting orders and the journal…")
    def _sl_build():
        return _sb.build()

    _c1, _c2, _c3, _c5, _c4 = st.columns([1.3, 1.6, 1.0, 1.0, 0.8])
    _unit_lbl = _c1.radio("Axis", ["ATR(D) from LTP", "% from LTP"], horizontal=True, key="sl_unit",
                          help="ATR puts every holding on the same volatility scale: −3 means three daily "
                               "ATRs below today's price, whatever the stock. % is the plain price distance.")
    _sort = _c2.radio("Order", ["Triage", "Risk vs rule", "Thesis cushion", "Symbol"], horizontal=True,
                      key="sl_sort")
    _show_tg = _c3.toggle("Show targets", value=True, key="sl_tg",
                          help="Hide T1/T2 to zoom the axis onto the stops.")
    _fit = _c5.toggle("Fit all levels", value=False, key="sl_fit",
                      help="Off: the axis is held to −7…+14×ATR (−25…+50%) so the stops are readable, and a level "
                           "beyond it is pinned to the edge as an arrow. On: every level at its true distance.")
    if _c4.button("🔄 Refresh", key="sl_refresh", help="Re-read Dhan and the journal (cached 5 min)."):
        _sl_build.clear()
    _unit = "atr" if _unit_lbl.startswith("ATR") else "pct"

    try:
        _df, _meta = _sl_build()
    except Exception as _e:
        st.error(f"SL Dashboard could not be built: {_e}")
        st.stop()
    if _df.empty:
        st.info("No open holdings.")
        st.stop()

    _df = _df.copy()
    _tri = _df.apply(lambda r: _sb.triage(r), axis=1)
    _df["tri_rank"] = [t[0] for t in _tri]
    _df["tri_why"] = [t[1] for t in _tri]
    _df["cushion_atr"] = [((r.close or r.ltp) - r.thesis) / r.atr if (r.thesis and r.atr) else _m.inf
                          for r in _df.itertuples()]
    _df["excess"] = (_df["loss_if_stopped"].fillna(0) - _df["budget"]).clip(lower=0)
    if _sort == "Triage":
        _df = _df.sort_values(["tri_rank", "excess"], ascending=[True, False])
    elif _sort == "Risk vs rule":
        _df = _df.sort_values("loss_if_stopped", ascending=False, na_position="last")
    elif _sort == "Thesis cushion":
        _df = _df.sort_values("cushion_atr")
    else:
        _df = _df.sort_values("symbol")
    _df = _df.reset_index(drop=True)

    _ICON = {0: "⛔", 1: "🔻", 2: "⚠️", 3: "💰", 4: "📳", 5: "👀", 6: "📅", 7: "🌩️"}
    try:
        import stop_history as _sh0
        _hist_w = dict(zip(*[_sh0.summary(open_syms=list(_df["symbol"]))[c] for c in ("symbol", "widened")]))
    except Exception:
        _hist_w = {}

    # ── KPI strip ────────────────────────────────────────────────────────────
    _heat = _meta.get("heat") or {}
    _open_r = float(_df["open_risk"].fillna(0).sum())
    _loss = float(_df["loss_if_stopped"].clip(lower=0).fillna(0).sum())
    _over = _df[_df["over_budget"]]
    _broken = int((_df["thesis_state"] == "BROKEN").sum())
    _noise = int((_df["noise"] == "red").sum())
    _cb = int(_df["chand_breach"].sum())
    _gap_tot = float(_df["gap_loss"].clip(lower=0).fillna(0).sum())
    _gap_thr = int(_df["gap_through"].sum())

    def _card(label, value, sub, colour):
        return (f'<div style="flex:1;min-width:170px;background:rgba(255,255,255,0.03);border:1px solid '
                f'rgba(255,255,255,0.08);border-left:4px solid {colour};border-radius:8px;padding:10px 14px;">'
                f'<div style="font-size:0.72rem;color:#94A3B8;text-transform:uppercase;letter-spacing:.06em;">{label}</div>'
                f'<div style="font-size:1.45rem;font-weight:700;font-family:JetBrains Mono,monospace;color:{colour};">{value}</div>'
                f'<div style="font-size:0.75rem;color:#94A3B8;">{sub}</div></div>')

    _hb = float(_heat.get("rupees") or 0)
    _cards = [
        _card("Open risk at Dhan stops", f"₹{_ri(_open_r)}",
              (f"budget ₹{_ri(_hb)} ({_heat.get('pct', 0):g}% · {_heat.get('budget_tier', '')}) · "
               f"{_open_r / _hb * 100:.0f}% used") if _hb else "from LTP to each resting stop",
              "#EF4444" if (_hb and _open_r > _hb) else "#22C55E"),
        _card("Loss if every stop fills", f"₹{_ri(_loss)}", "from cost, losing positions only", "#F97316"),
        _card("Over the per-trade rule", f"{len(_over)} / {len(_df)}",
              (f"₹{_ri(_over['excess'].sum())} beyond {_meta['risk_pct_stock']:g}% "
               f"(ETF {_meta['risk_pct_etf']:g}%) of ₹{_ri(_meta['capital'])}"),
              "#EF4444" if len(_over) else "#22C55E"),
        _card("Thesis broken on the close", str(_broken), "close below the Thesis SL = the idea is wrong",
              "#EF4444" if _broken else "#22C55E"),
        _card("Stops inside the noise", str(_noise), "Dhan stop < 1.5×ATR(D) from LTP",
              "#F59E0B" if _noise else "#22C55E"),
        _card("Chandelier breached", str(_cb), "trail at/above LTP = exit review", "#22D3EE" if _cb else "#22C55E"),
        _card("Gap stress", f"₹{_ri(_gap_tot)}",
              f"worst 2y gap repeated: +₹{_ri(max(_gap_tot - _loss, 0))} beyond the stops · "
              f"{_gap_thr} open below their stop", "#FB7185" if _gap_thr else "#22C55E"),
    ]
    st.markdown('<div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 14px 0;">' + "".join(_cards) + "</div>",
                unsafe_allow_html=True)
    _src = (f"Levels: {'Dhan resting orders' if _meta['orders_ok'] else 'JOURNAL (Dhan order book unreadable)'} · "
            f"book: {_meta['source']} · sizing capital ₹{_ri(_meta['capital'])} ({_meta['cap_src']})")
    if _meta.get("v2_skipped"):
        _src += f" · {_meta['v2_skipped']} v2 holding(s) not shown (no stops by design)"
    if _meta.get("failed"):
        _src += " · no data: " + ", ".join(_meta["failed"])
    if _meta.get("chand_err"):
        _src += " · Chandelier unavailable: " + _meta["chand_err"]
    st.caption(_src)

    # ── the ladder ───────────────────────────────────────────────────────────
    # NaN -> None once, so every "is this level there?" test below is a plain truth test
    _rows = [{k: (None if isinstance(v, float) and v != v else v) for k, v in rec.items()}
             for rec in _df.to_dict("records")]
    _n = len(_rows)
    _fig = _go.Figure()
    # Lane i sits at y = n-1-i (first row on top). Inside a lane: stops just BELOW the line,
    # LTP / Avg / EMA20 ON it, targets just ABOVE - so a cluster of stops never hides the price.
    _STOPS = ("initial", "thesis", "disaster", "rec_sl", "chand", "gapw")
    _TGTS = ("t1", "t2", "rec_t1", "rec_t2")
    _DY = 0.17
    for i, r in enumerate(_rows):
        r["_y"] = _n - 1 - i
    # Scale: by default the axis runs -7..+14 xATR (-25..+50 %): every stop below, and a
    # positional T1 (3R off a 4xATR stop = 12xATR) above. A level beyond it is pinned to the
    # edge as an arrow; its hover still gives the true value.
    _LIM = (-7.0, 14.0) if _unit == "atr" else (-25.0, 50.0)

    def _x(r, p):
        return _sb.to_axis(r, p, _unit)

    def _clamp(v):
        if _fit or v is None:
            return v, ""
        if v > _LIM[1]:
            return _LIM[1], "R"
        if v < _LIM[0]:
            return _LIM[0], "L"
        return v, ""

    def _fmt(v):
        return f"{v:,.2f}" if v < 100 else f"{v:,.1f}"

    def _seg(x0, x1, yy, colour, width):
        a, _ = _clamp(x0)
        b, _ = _clamp(x1)
        _fig.add_trace(_go.Scatter(x=[a, b], y=[yy, yy], mode="lines", hoverinfo="skip", showlegend=False,
                                   line=dict(color=colour, width=width)))

    _shapes = []
    for i, r in enumerate(_rows):
        y = r["_y"]
        pts = [_x(r, r.get(k)) for k, *_ in _sb.LEVELS if (_show_tg or k not in _TGTS) and r.get(k)]
        pts = [p for p in pts if p is not None]
        if not pts:
            continue
        # the lane, the noise haze, the decision band and the runway
        _seg(min(pts), max(pts), y, "rgba(148,163,184,0.35)", 2)
        if r.get("atr"):
            xn = _x(r, r["ltp"] - 1.5 * r["atr"])
            if xn is not None:
                _seg(xn, 0, y, "rgba(245,158,11,0.22)", 14)
        xd, xt = _x(r, r.get("disaster")), _x(r, r.get("thesis"))
        if xd is not None and xt is not None and xt > xd:
            _seg(xd, xt, y - _DY, "rgba(239,68,68,0.40)", 9)
        xt1 = _x(r, r.get("t1") or r.get("rec_t1"))
        if _show_tg and xt1 is not None and xt1 > 0:
            _seg(0, xt1, y + _DY, "rgba(34,197,94,0.18)", 9)
        if i % 2 == 0:
            _shapes.append(dict(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=y - 0.5, y1=y + 0.5,
                                fillcolor="rgba(255,255,255,0.03)", line_width=0, layer="below"))

    # one trace per level type, so the legend toggles a level across the whole book
    for key, label, colour, sym, size in _sb.LEVELS:
        if not _show_tg and key in _TGTS:
            continue
        off = -_DY if key in _STOPS else (_DY if key in _TGTS else 0.0)
        xs, ys, tips, syms = [], [], [], []
        for r in _rows:
            p = r.get(key)
            if not p:
                continue
            xv = _x(r, p)
            if xv is None:
                continue
            xc, side = _clamp(xv)
            xs.append(xc)
            ys.append(r["_y"] + off)
            syms.append("arrow-right" if side == "R" else "arrow-left" if side == "L" else sym)
            atrd = (p - r["ltp"]) / r["atr"] if r.get("atr") else float("nan")
            pct = (p / r["ltp"] - 1) * 100
            extra = ""
            if key == "initial" and r.get("initial_policy"):
                extra = "<br>policy stop (no initial SL recorded)"
            elif key == "thesis":
                extra = f"<br>{r.get('thesis_state') or ''} · {r.get('thesis_vs_dhan') or ''}<br>judged on: {r.get('close_src')}"
            elif key == "disaster":
                extra = (f"<br>{r['dist_atr']:.1f}×ATR below LTP" if r.get("dist_atr") else "") + \
                        (f"<br>⚠ {r['order_warn']}" if r.get("order_warn") else "")
            elif key == "rec_sl" and r.get("rec_qty") is not None:
                extra = f"<br>same rupee risk at this stop: {int(r['rec_qty'])} sh (now {int(r['qty'])})"
            elif key == "chand":
                extra = f"<br>trail ×{r.get('chand_mult')}" + (" · BREACHED" if r.get("chand_breach") else "")
            elif key == "gapw":
                extra = (f"<br>worst open {r.get('gap_worst', 0):+.1f}% on {r.get('gap_worst_date')} repeated today"
                         + ("<br>⚠ opens BELOW the Dhan stop - the stop does not cap this loss" if r.get("gap_through")
                            else "<br>still above the Dhan stop") +
                         (f"<br>stress loss ₹{_ri(r['gap_loss'])}" if r.get("gap_loss") and r["gap_loss"] > 0 else ""))
            elif key == "avg":
                extra = f"<br>P&L {r['pnl_pct']:+.1f}%" + (f" · {r['r_now']:+.2f}R" if r.get("r_now") is not None else "")
            if side:
                extra += "<br><i>off the scale - pinned to the edge</i>"
            tips.append(f"<b>{r['symbol']} · {label}</b><br>₹{_fmt(p)}<br>{pct:+.1f}% · {atrd:+.1f}×ATR(D){extra}")
        if xs:
            hollow = sym.endswith("open") or sym in ("line-ns", "x-thin")
            _fig.add_trace(_go.Scatter(
                x=xs, y=ys, mode="markers", name=label, text=tips, hovertemplate="%{text}<extra></extra>",
                marker=dict(symbol=syms, size=size, color=colour,
                            line=dict(width=2 if hollow else 1, color=colour if hollow else "#0B1220"))))

    # left: the verdict chip; right: the risk chip
    _ann = []
    for r in _rows:
        icon = _ICON.get(r["tri_rank"], "✅")
        _ann.append(dict(xref="paper", yref="y", x=-0.005, y=r["_y"], xanchor="right", showarrow=False,
                         text=f"{icon} <b>{r['symbol']}</b> <span style='color:#94A3B8'>{r['plan'][:3]} · "
                              f"{r['pnl_pct']:+.1f}%</span>"
                              + (f" <span style='color:#F97316'>↘{_hist_w[r['symbol']]}</span>"
                                 if _hist_w.get(r["symbol"]) else "")
                              + (f" <span style='color:#FACC15'>📅{int(r['earn_days'])}d</span>"
                                 if r.get("earn_soon") else ""),
                         font=dict(size=12, color="#E2E8F0")))
        loss = r.get("loss_if_stopped")
        if loss is not None:
            if loss <= 0:
                txt, col = f"🔒 locks ₹{_ri(-loss)}", "#22C55E"
            else:
                mult = loss / r["budget"] if r["budget"] else 0
                col = "#EF4444" if r["over_budget"] else ("#F59E0B" if mult > 0.8 else "#22C55E")
                txt = f"₹{_ri(loss)} = {mult:.1f}× rule"
                if r["over_budget"] and r.get("fit_qty") is not None and r["fit_qty"] < r["qty"]:
                    txt += f" → {int(r['fit_qty'])} sh"
        else:
            txt, col = "no stop", "#EF4444"
        _ann.append(dict(xref="paper", yref="y", x=1.005, y=r["_y"], xanchor="left", showarrow=False,
                         text=txt, font=dict(size=12, color=col, family="JetBrains Mono, monospace")))

    _unit_axis = "distance from LTP, × daily ATR(14)" if _unit == "atr" else "distance from LTP, %"
    _fig.add_vline(x=0, line=dict(color="rgba(248,250,252,0.55)", width=1, dash="dot"))
    if _unit == "atr":
        for _g in (-4, -3, -1.5):
            _fig.add_vline(x=_g, line=dict(color="rgba(148,163,184,0.14)", width=1))
    _xa = dict(title=_unit_axis, zeroline=False, gridcolor="rgba(148,163,184,0.10)",
               ticksuffix="×" if _unit == "atr" else "%", dtick=1 if _unit == "atr" else 5)
    if not _fit:
        _xa["range"] = [_LIM[0] - 0.3, _LIM[1] + 0.3] if _unit == "atr" else [_LIM[0] - 1, _LIM[1] + 1]
    _fig.update_layout(
        height=max(380, 58 * _n + 150), shapes=_shapes, annotations=_ann,
        margin=dict(l=210, r=210, t=70, b=50), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1"), hoverlabel=dict(bgcolor="#0F172A", font_size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0, font=dict(size=12),
                    itemclick="toggle", itemdoubleclick="toggleothers"),
        xaxis=_xa,
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.6, _n - 0.4]))
    st.plotly_chart(_fig, width="stretch", config={"displaylogo": False})
    st.caption("Lane = one holding: stops just below the line, LTP / Avg / EMA20 on it, targets just above. Red bar = Disaster SL → Thesis SL (the gap a news gap jumps straight across). "
               "Amber haze = within 1.5×ATR below LTP: a resting stop there is inside the noise. Green bar = runway "
               "to T1. Pink ▽ = this stock's worst 2-year gap repeated from today; ↘n = times the Dhan stop was widened. Right: what the Dhan stop costs if it fills, against the per-trade rule, and the share count "
               "that fits the rule at that stop. Click a legend item to hide a level; double-click to isolate it.")

    # ── triage ───────────────────────────────────────────────────────────────
    _t = _df[_df["tri_rank"] < 9]
    if len(_t):
        st.markdown("**Look at first**")
        _lines = []
        for r in _t.itertuples():
            act = {
                0: ("the close is through the thesis, so the plan says exit. If you hold, re-set the thesis on "
                    "purpose (journal + its alert) rather than leave a level that has already been crossed"),
                1: "the trail has been crossed - exit review",
                2: "fix the resting orders on Dhan (one price, every share covered, limit below trigger)",
                3: (f"trim to {int(r.fit_qty)} sh to keep this stop, or tighten the stop"
                    if (r.fit_qty is not None and r.fit_qty == r.fit_qty and r.fit_qty < r.qty) else "tighten the stop"),
                4: (f"wider to ₹{_fmt(r.rec_sl)} at {int(r.rec_qty)} sh keeps the same risk"
                    if (r.rec_sl == r.rec_sl and r.rec_sl and r.rec_qty == r.rec_qty and r.rec_qty is not None)
                    else "a wider stop with fewer shares"),
                5: "one more weak close decides it",
                6: (f"cut to {int(r.gap_fit_qty)} sh before the results on {r.earn_date} (gap-sized), "
                    "or accept that a repeat of its worst gap costs more than the rule"
                    if (r.gap_fit_qty == r.gap_fit_qty and r.gap_fit_qty is not None) else "size for the gap before results"),
                7: (f"size for the gap, not the stop: {int(r.gap_fit_qty)} sh keeps that gap inside the rule"
                    if (r.gap_fit_qty == r.gap_fit_qty and r.gap_fit_qty is not None and r.gap_fit_qty < r.qty)
                    else "size for the gap, not the stop"),
            }.get(r.tri_rank, "")
            _lines.append(f"- **{r.symbol}** — {r.tri_why}: {act}")
        st.markdown("\n".join(_lines))

    # ── four tabs under the chart ────────────────────────────────────────────
    def _rs(v):
        return "" if (v is None or v != v) else ("−₹" if v < 0 else "₹") + _ri(abs(v))

    _tab_lv, _tab_ed, _tab_hist, _tab_gap = st.tabs(
        ["📋 Every level", "✏️ Edit thesis & plan", "📜 Stop moves", "📉 Gap risk"])

    with _tab_lv:
        _tb = _pd.DataFrame({
            "Flag": [_ICON.get(x, "✅") for x in _df["tri_rank"]],
            "Symbol": _df["symbol"], "Plan": _df["plan"], "Qty": _df["qty"].astype(int),
            "Avg": _df["avg"], "LTP": _df["ltp"], "P&L %": _df["pnl_pct"], "R now": _df["r_now"],
            "ATR(D)": _df["atr"], "EMA20(D)": _df["ema20"],
            "Initial SL": _df["initial"], "Thesis SL": _df["thesis"], "Thesis": _df["thesis_state"],
            "Disaster SL": _df["disaster"], "Stop ×ATR": _df["dist_atr"],
            "Rec SL 3×ATR": _df["rec_sl"], "Rec qty": _df["rec_qty"],
            "Chandelier": _df["chand"],
            "T1": _df["t1"], "T2": _df["t2"], "Rec T1": _df["rec_t1"], "Rec T2": _df["rec_t2"],
            "Loss if stopped": [_rs(v) for v in _df["loss_if_stopped"]],
            "Rule ₹": [_rs(v) for v in _df["budget"]],
            "Fits rule (sh)": [int(f) if (f == f and f is not None and f < q) else None
                               for f, q in zip(_df["fit_qty"], _df["qty"])],
            "Planned qty": _df["plan_qty"],
            "Open risk": [_rs(v) for v in _df["open_risk"]],
            "Stop vs initial": _df["widened_pct"],
            "Widened (times)": [_hist_w.get(s, 0) for s in _df["symbol"]],
            "Gap stress loss": [_rs(v) for v in _df["gap_loss"]],
            "Orders": _df["order_warn"], "Why": _df["tri_why"],
        })
        _num = {c: st.column_config.NumberColumn(format="%.2f") for c in
                ("Avg", "LTP", "ATR(D)", "EMA20(D)", "Initial SL", "Thesis SL", "Disaster SL", "Rec SL 3×ATR",
                 "Chandelier", "T1", "T2", "Rec T1", "Rec T2")}
        _num.update({
            "P&L %": st.column_config.NumberColumn(format="%+.1f%%"),
            "R now": st.column_config.NumberColumn(format="%+.2f"),
            "Stop ×ATR": st.column_config.NumberColumn(format="%.1f", help="Dhan stop distance below LTP in ATR(D). <1.5 = noise"),
            "Stop vs initial": st.column_config.NumberColumn(format="%+.0f%%", help="Risk per share at the Dhan stop vs the initial SL. +150% = the stop is 2.5× as far from cost as planned"),
            "Rec qty": st.column_config.NumberColumn(format="%d", help="Shares that keep today's rupee risk at the Rec SL"),
            "Fits rule (sh)": st.column_config.NumberColumn(format="%d", help="Shares whose loss at the CURRENT Dhan stop stays inside the per-trade rule (shown only when below the holding)"),
            "Planned qty": st.column_config.NumberColumn(format="%d", help="Your planned holding after a trim (Edit tab). A plan, not an order"),
            "Widened (times)": st.column_config.NumberColumn(format="%d", help="How many times the Dhan stop has been moved DOWN on this holding (Stop moves tab)"),
        })
        st.dataframe(_tb, width="stretch", hide_index=True, column_config=_num,
                     height=min(42 + 35 * len(_tb), 760))
        st.download_button("⬇️ CSV", _df.to_csv(index=False).encode("utf-8"), file_name="sl_dashboard.csv",
                           mime="text/csv", key="sl_csv")

    # ── edit: thesis level and planned quantity ─────────────────────────────
    with _tab_ed:
        st.markdown("Set the **Thesis SL** (a Daily close below it ends the idea) and, where the loss at the Dhan stop "
                    "is over the rule, a **Planned qty** - the holding you mean to cut to. Saving writes the thesis to the "
                    "journal (backed up first) and the plan to `data/sl_plan.json`, and logs both in the stop history. "
                    "**Nothing here places, moves or cancels an order** - the trim and any Dhan stop change are yours, on Dhan.")
        _ed_src = _pd.DataFrame({
            "Symbol": _df["symbol"], "Qty": _df["qty"].astype(int), "LTP": _df["ltp"].round(2),
            "ATR(D)": _df["atr"].round(2), "Dhan stop": _df["disaster"].round(2),
            "Thesis SL": _df["thesis"].round(2),
            "Planned qty": _df["plan_qty"],
            "Fits rule (sh)": [int(f) if (f == f and f is not None) else None for f in _df["fit_qty"]],
            "Note": _df["plan_note"],
        })
        _ed = st.data_editor(
            _ed_src, key="sl_editor", hide_index=True, width="stretch",
            disabled=["Symbol", "Qty", "LTP", "ATR(D)", "Dhan stop", "Fits rule (sh)"],
            column_config={
                "Thesis SL": st.column_config.NumberColumn(format="%.2f", min_value=0.0,
                                                           help="A Daily CLOSE below this ends the idea. Blank = no thesis"),
                "Planned qty": st.column_config.NumberColumn(format="%d", min_value=0, step=1,
                                                             help="The holding you plan to cut to. Blank = no plan"),
                "Note": st.column_config.TextColumn(help="Why - e.g. 'trim into strength above 1,520'"),
                "Fits rule (sh)": st.column_config.NumberColumn(format="%d", help="Shares that fit the rule at the CURRENT Dhan stop"),
            })

        # what changed, and what it implies - checked before anything is written
        _edits, _warn = [], []
        for _o, _n in zip(_ed_src.to_dict("records"), _ed.to_dict("records")):
            _e = {"symbol": _n["Symbol"], "qty": _o["Qty"], "disaster": _o["Dhan stop"]}
            _avg = float(_df.loc[_df["symbol"] == _n["Symbol"], "avg"].iloc[0])
            _e["avg"] = _avg

            def _v(x):
                return None if (x is None or x != x) else float(x)
            if _v(_n["Thesis SL"]) != _v(_o["Thesis SL"]):
                _e["thesis"] = _v(_n["Thesis SL"])
                _t = _e["thesis"]
                if _t is not None:
                    if _t >= _o["LTP"]:
                        _warn.append(f"**{_n['Symbol']}**: thesis ₹{_fmt(_t)} is at/above LTP ₹{_fmt(_o['LTP'])} - "
                                     "it is already broken on the next close.")
                    _d = _sb.rec_disaster_for(_t, _o["ATR(D)"])
                    if _d is not None:
                        _fit = int(_df.loc[_df["symbol"] == _n["Symbol"], "budget"].iloc[0] // (_avg - _d)) \
                            if _avg > _d else None
                        _warn.append(f"**{_n['Symbol']}**: with thesis ₹{_fmt(_t)} the two-tier Disaster SL is "
                                     f"₹{_fmt(_d)} (thesis − 1×ATR)" +
                                     (f"; at that stop the rule fits **{_fit} sh** (you hold {int(_o['Qty'])})."
                                      if _fit is not None else "; it locks a profit."))
                    if _o["Dhan stop"] and _t < _o["Dhan stop"]:
                        _warn.append(f"**{_n['Symbol']}**: thesis below the Dhan stop - the Dhan order fires first, so "
                                     "the thesis is superseded (no alert, drawn dimmed).")
            if _v(_n["Planned qty"]) != _v(_o["Planned qty"]):
                _e["plan_qty"] = _v(_n["Planned qty"])
                if _e["plan_qty"] is not None and _e["plan_qty"] >= _o["Qty"]:
                    _warn.append(f"**{_n['Symbol']}**: planned qty {int(_e['plan_qty'])} is not below the holding "
                                 f"({int(_o['Qty'])}) - it will be ignored.")
            if str(_n["Note"] or "") != str(_o["Note"] or ""):
                _e["note"] = _n["Note"]
            if len(_e) > 4:
                _edits.append(_e)

        for _w in _warn:
            st.markdown("- " + _w)
        _c_a, _c_b, _c_c = st.columns([1, 1.4, 2.6])
        if _c_a.button(f"💾 Save {len(_edits)} change(s)", type="primary", disabled=not _edits, key="sl_save"):
            _res = _sb.save_edits(_edits)
            if _res["errors"]:
                st.error(" · ".join(_res["errors"]))
            st.success(f"Saved: {_res['thesis']} thesis level(s), {_res['plan']} plan(s)."
                       + (f" Journal backup: `{_os.path.basename(_res['backup'])}`." if _res["backup"] else ""))
            st.session_state["sl_need_push"] = bool(_res["thesis"])
            _sl_build.clear()
        _alerts = _c_b.checkbox("also rebuild the thesis alerts", value=True, key="sl_push_alerts",
                                help="tv_thesis_alerts.py: one GM-THESIS alert per holding with a thesis above its Dhan stop "
                                     "(Daily close, webhook to Telegram). Takes a minute or two.")
        _lbl = "📡 Push to TradingView" + (" (thesis changed - push now)" if st.session_state.get("sl_need_push") else "")
        if _c_c.button(_lbl, key="sl_push",
                       help="Runs the same two scripts the 16:30 auto-pilot runs: the v67 stop book + slots, then the "
                            "thesis alerts. Needs TradingView open with CDP."):
            with st.spinner("Pushing the v67 stop book" + (" and rebuilding thesis alerts…" if _alerts else "…")):
                _out = _sb.push_to_tradingview(alerts=_alerts)
            for _scr, _rc, _tail in _out:
                (st.success if _rc == 0 else st.error)(f"{_scr}: {'OK' if _rc == 0 else f'exit {_rc}'}")
                if _tail:
                    st.code(_tail, language="text")
            if all(rc == 0 for _, rc, _ in _out):
                st.session_state["sl_need_push"] = False

        # ── lowering a Disaster SL: the shares go first (29-Oct-2026) ───────────────────
        import gap_risk as _grk
        import stop_guard as _sgd
        st.markdown("---")
        st.markdown("#### ⬇️ Change a Disaster SL — sell first, then Web Commander places the modify")
        _rev = _sgd.revert_enabled()
        st.markdown(
            "A lower stop with the same shares is a bigger bet. **The stop guard accepts a lowered Dhan stop only "
            "once the holding fits the per-trade rule at the new level** (from cost; a stop still above cost is "
            "free). Otherwise it Telegrams you and "
            + ("**puts the stop back** to the last approved level." if _rev else
               "will put the stop back once revert is switched on (`STOP_GUARD_REVERT=1` in .env - it is in "
               "**alarm mode** now).")
            + " Order of work: **1. sell the excess on Dhan · 2. shrink the stop legs to the holding on Dhan · "
              "3. lower the stop HERE** - Check at Dhan runs every condition and Place the modify sends it only when "
              "all pass (a stop lowered by hand on Dhan is caught by the guard).")
        _lc1, _lc2 = st.columns([1, 1])
        _lsym = _lc1.selectbox("Holding", list(_df["symbol"]), key="sl_low_sym")
        _lr = _df[_df["symbol"] == _lsym].iloc[0].to_dict()
        _cur = _lr.get("disaster") or 0.0
        _lnew = _lc2.number_input("New Disaster SL (trigger)", min_value=0.0,
                                  value=float(round(_cur * 0.97, 1)) if _cur else 0.0, step=0.5, key="sl_low_new")
        if _lnew and _cur and _lnew >= _cur:
            st.info(f"₹{_fmt(_lnew)} is not below the current Dhan stop ₹{_fmt(_cur)} - raising a stop needs no cut.")
        elif _lnew:
            _allow, _sell = _grk.lower_stop_qty(_lr["qty"], _lr["avg"], _lnew, _lr["budget"] * _sgd.RULE_SLACK)
            _same = _grk.same_risk_qty(_lr["qty"], _lr["avg"], _lr["ltp"], _cur, _lnew)
            _gf, _gl, _gfit, _gth = _grk.gap_numbers(_allow or 0, _lr["avg"], _lr["ltp"], _lnew,
                                                    _lr.get("gap_worst"), _lr["budget"])
            _m1, _m2, _m3, _m4 = st.columns(4)
            _m1.metric("Hold now", f"{int(_lr['qty'])} sh",
                       f"loss at ₹{_fmt(_cur)}: ₹{_ri(max(_lr['qty'] * (_lr['avg'] - _cur), 0))}", delta_color="off")
            _m2.metric("Allowed at the new stop", f"{_allow} sh",
                       f"rule ₹{_ri(_lr['budget'])}", delta_color="off")
            _m3.metric("Sell first", f"{_sell} sh", "before the stop comes down" if _sell else "no cut needed",
                       delta_color="inverse" if _sell else "off")
            _m4.metric("Keeps today's risk", f"{_same} sh", "same rupees as now", delta_color="off")
            _lines = []
            if _lnew >= _lr["avg"]:
                _lines.append("The new stop is still above cost - it gives back profit, not capital. Accepted as is.")
            if _gth and _gl is not None and _gl > _lr["budget"] * _sgd.RULE_SLACK:
                _lines.append(f"Gap check at {_allow} sh: a repeat of its worst gap ({_lr['gap_worst']:.1f}%) opens "
                              f"at ₹{_fmt(_gf)}, below the new stop - loss ₹{_ri(_gl)}, over the rule. "
                              f"{_gfit} sh fits even that.")
            if _lr.get("earn_soon"):
                _lines.append(f"Results on {_lr['earn_date']} ({int(_lr['earn_days'])}d): size for the gap, not the stop.")
            for _x in _lines:
                st.markdown("- " + _x)

        # ── ROUTED THROUGH WEB COMMANDER (29-Oct-2026): check every condition at Dhan, then modify ──
        if _lnew and _cur and abs(_lnew - _cur) >= 0.01:
            import stop_change as _scg
            _key = (_lsym, round(float(_lnew), 2))
            _pc1, _pc2 = st.columns([1, 1])
            if _pc1.button("🔍 Check at Dhan", key="sl_chg_plan",
                           help="Reads the live Dhan holding, every resting stop leg and the LTP, and runs every "
                                "condition. Nothing is sent."):
                with st.spinner("Reading Dhan…"):
                    st.session_state["sl_chg"] = (_key, _scg.plan(_lsym, _lnew))
            _pl = st.session_state.get("sl_chg")
            if _pl and _pl[0] == _key:
                _p = _pl[1]
                for _c in _p["checks"]:
                    _ic = "✅" if _c["ok"] else ("⛔" if _c["block"] else "⚠️")
                    st.markdown(f"{_ic} **{_c['name']}** — {_c['detail']}")
                if _p.get("trigger"):
                    st.caption(f"Would send: every stop leg → trigger ₹{_fmt(_p['trigger'])}, limit ₹{_fmt(_p['limit'])} "
                               f"({len(_p.get('legs') or [])} leg(s)). The journal stop and the trail floor follow; "
                               "the stop guard records it as approved.")
                _go = _pc2.button("✅ Place the modify on Dhan", type="primary", disabled=not _p["ok"],
                                  key="sl_chg_apply",
                                  help="Re-reads Dhan and re-runs every check first; sends only if all still pass.")
                if not _p["ok"]:
                    st.error("Not sendable: " + "; ".join(c["name"] for c in _p["checks"] if c["block"] and not c["ok"])
                             + ". Fix it on Dhan (sell first, then shrink the legs), then check again.")
                if _go:
                    with st.spinner("Re-checking and modifying at Dhan…"):
                        _r = _scg.apply(_lsym, _lnew)
                    if _r["ok"]:
                        st.success(f"{_lsym}: {len(_r['done'])} leg(s) now at ₹{_fmt(_r['plan']['trigger'])}. "
                                   + " · ".join(_r["notes"]))
                    elif _r["done"]:
                        st.warning(f"{len(_r['done'])} leg(s) changed, {len(_r['failed'])} FAILED: "
                                   + "; ".join(f"{f['order_id']} {f['resp']}" for f in _r["failed"])
                                   + " — the legs now disagree; fix on Dhan.")
                    else:
                        st.error(" · ".join(_r["notes"]) or "nothing sent")
                    if _r.get("readback"):
                        st.caption("Dhan now: " + ", ".join(f"{o} @ ₹{_fmt(t)}" for o, t in _r["readback"]))
                    st.session_state.pop("sl_chg", None)
                    _sl_build.clear()
        _gev = _sgd.load_events()
        if len(_gev):
            st.caption("Stop guard - last events (`logs/stop_guard_events.csv`)")
            st.dataframe(_gev.tail(12).iloc[::-1], width="stretch", hide_index=True)

    # ── stop moves: is widening a habit? ────────────────────────────────────
    with _tab_hist:
        import stop_history as _shm
        _ev = _shm.events()
        _sm = _shm.summary(_ev, open_syms=list(_df["symbol"]))
        _hc1, _hc2 = st.columns([1, 1])
        if _hc1.button("📸 Record today's stops now", key="sl_hist_rec",
                       help="Adds today's row per holding (the nightly Phase 12k does this at 16:30)."):
            if _meta.get("orders_ok"):
                st.success(f"Recorded {_shm.record_board(_df)} holdings.")
                st.rerun()
            else:
                st.error("Dhan order book unreadable - not recorded (it would log journal stops as Dhan's).")
        if _hc2.button("⏮ Back-fill from journal backups", key="sl_hist_bf",
                       help="One row per holding from each dated journal backup since June. Safe to run again."):
            st.success(f"Back-filled {_shm.backfill_from_backups()} rows.")
            st.rerun()
        if _ev.empty:
            st.info("No stop moves on record yet - press Back-fill once, then the nightly snapshot keeps it current.")
        else:
            _w_tot = _sm["widened"].sum() if len(_sm) else 0
            _r_tot = _sm["risk_added"].sum() if len(_sm) else 0.0
            st.markdown(f"**Open holdings: {int(_w_tot)} widening(s) on record, adding ₹{_ri(_r_tot)} of risk at "
                        f"the shares held** - against {int(_sm['tightened'].sum())} tightening(s). "
                        "A widening is the stop moving DOWN with the same shares: the loss at the stop grows by the "
                        "rupees shown. The fix is not to never widen, but to cut shares when you do.")
            _smd = _sm[_sm["widened"] + _sm["tightened"] + _sm["thesis_down"] > 0].sort_values(
                ["widened", "risk_added"], ascending=False)
            st.dataframe(_smd.rename(columns={
                "symbol": "Symbol", "widened": "Widened", "widened_below_entry": "…while below entry",
                "tightened": "Tightened", "thesis_down": "Thesis lowered", "risk_added": "Risk added ₹",
                "last_move": "Last move"}).assign(**{"Risk added ₹": lambda x: x["Risk added ₹"].map(_rs)}),
                width="stretch", hide_index=True)
            _um = _shm.unmatched_widenings(_ev)
            _um = _um[_um["symbol"].isin(_df["symbol"])] if len(_um) else _um
            if len(_um):
                st.markdown(f"**{len(_um)} widening(s) without the quantity cut** - the shares held after the move "
                            "did not fit the rule at the new stop (the test the stop guard now enforces).")
                st.dataframe(_um.sort_values("date", ascending=False)[
                    ["date", "symbol", "from", "to", "qty_to", "allowed", "sell_first", "rupees"]].rename(columns={
                    "date": "Date", "symbol": "Symbol", "from": "From", "to": "To", "qty_to": "Held",
                    "allowed": "Rule allowed", "sell_first": "Should have sold", "rupees": "Risk ₹ added"}).assign(
                    **{"Risk ₹ added": lambda x: x["Risk ₹ added"].map(_rs)}),
                    width="stretch", hide_index=True,
                    column_config={"From": st.column_config.NumberColumn(format="%.2f"),
                                   "To": st.column_config.NumberColumn(format="%.2f")})
            _pick = st.selectbox("Moves for", ["(all open holdings)"] + list(_smd["symbol"]), key="sl_hist_sym")
            _evs = _ev[_ev["symbol"].isin(_df["symbol"])] if _pick.startswith("(") else _ev[_ev["symbol"] == _pick]
            _evs = _evs.sort_values("date", ascending=False).assign(
                rupees=lambda x: x["rupees"].map(_rs))
            st.dataframe(_evs.rename(columns={"date": "Date", "symbol": "Symbol", "kind": "Move", "from": "From",
                                              "to": "To", "pct": "Change %", "rupees": "Risk ₹ (+ = added)",
                                              "below_entry": "Below entry"}),
                         width="stretch", hide_index=True,
                         column_config={"From": st.column_config.NumberColumn(format="%.2f"),
                                        "To": st.column_config.NumberColumn(format="%.2f"),
                                        "Change %": st.column_config.NumberColumn(format="%+.1f%%")})
            st.caption("Sources: journal backups (daily, from June - the journal stop, synced from Dhan at 16:30 "
                       "since 4 Oct), the nightly Dhan snapshot, and thesis edits saved here. Moves under 0.2% are "
                       "treated as rounding.")

    # ── gap risk: the gap goes through the stop ──────────────────────────────
    with _tab_gap:
        st.markdown("A resting stop protects against a **slide**, never against a **gap**: on a news open the order fills "
                    "at the open, wherever that is. The stress test below repeats each stock's **worst overnight gap of "
                    "the last two years** from today's price. Where that open is below the Dhan stop, the stop's distance "
                    "is not the risk - the gap is, and only fewer shares cuts it.")
        _g = _df.sort_values("gap_loss", ascending=False, na_position="last")
        _gt = _pd.DataFrame({
            "Symbol": _g["symbol"], "Qty": _g["qty"].astype(int), "LTP": _g["ltp"], "Dhan stop": _g["disaster"],
            "Gap p95 %": _g["gap_p95"], "Gap p99 %": _g["gap_p99"], "Worst gap %": _g["gap_worst"],
            "Worst on": _g["gap_worst_date"], "Gaps ≤ −3% (2y)": _g["gaps_3pct"],
            "Worst-gap open": _g["gapw"],
            "Through the stop?": ["⚠ yes" if x else "no" for x in _g["gap_through"]],
            "Loss at the stop": [_rs(v) for v in _g["loss_if_stopped"]],
            "Stress loss": [_rs(v) for v in _g["gap_loss"]],
            "Rule ₹": [_rs(v) for v in _g["budget"]],
            "Fits rule on the gap (sh)": [int(f) if (f == f and f is not None and f < q) else None
                                          for f, q in zip(_g["gap_fit_qty"], _g["qty"])],
        })
        st.dataframe(_gt, width="stretch", hide_index=True, column_config={
            "LTP": st.column_config.NumberColumn(format="%.2f"),
            "Dhan stop": st.column_config.NumberColumn(format="%.2f"),
            "Worst-gap open": st.column_config.NumberColumn(format="%.2f"),
            "Gap p95 %": st.column_config.NumberColumn(format="%.1f%%", help="1 session in 20 opened at least this far down"),
            "Gap p99 %": st.column_config.NumberColumn(format="%.1f%%", help="1 session in 100"),
            "Worst gap %": st.column_config.NumberColumn(format="%.1f%%", help="the single worst open vs previous close in ~500 sessions"),
            "Fits rule on the gap (sh)": st.column_config.NumberColumn(format="%d",
                help="Shares whose loss, if the worst gap repeated today, stays inside the per-trade rule")})
        _thr = _df[_df["gap_through"]]
        st.caption(f"{len(_thr)} of {len(_df)} holdings: the worst gap would open below the Dhan stop"
                   + (" (" + ", ".join(_thr["symbol"]) + ")" if len(_thr) else "")
                   + ". The 1-in-100 gap sits inside every stop on today's book; the news days are the tail. Many worst "
                   "gaps share one date (7 Apr 2025, the index-wide open) - a market gap, not a company one.")

    with st.expander("How to read the levels — and Chandelier vs Rec SL"):
        st.markdown(
            "- **Initial SL** — the stop the trade was planned on (journal `initial_sl`; the policy stop when none was "
            "recorded). It is the R unit: Rec T1/T2 are measured from it.\n"
            "- **Thesis SL** — a Daily CLOSE below it proves the idea wrong. Never an order, so an intraday news wick "
            "cannot take you out; the close decides.\n"
            "- **Disaster SL** — the resting Dhan stop, the one that actually fires. Its job is gaps and real "
            "collapses, so it sits further away than the thesis (thesis − 1×ATR, no closer to cost than the floor: "
            "positional 4×, swing 1.5×ATR). **The position is sized off this one.**\n"
            "- **Chandelier** — the TRAIL: highest close since entry (14 bars swing / 22 positional) minus a multiple "
            "of ATR. It only rises. A close below it says the trend has given back too much.\n"
            "- **Rec SL 3×ATR** — a FLOOR on distance, not a trail: a resting stop closer than 3×ATR to LTP sits "
            "inside the noise and gets swept. Shown only when the Dhan stop is closer; it comes with the share count "
            "that keeps today's rupee risk, so widening never adds risk. **They answer different questions and are not "
            "the same level.**\n"
            "- **EMA20 (D)** — the daily trend's mean; pullbacks to it are where adds and re-entries live.\n"
            "- **T1/T2 (Dhan)** — the resting target legs. **Rec T1/T2** — the canon off the R unit: swing 2R/4R, "
            "positional 3R/5R.\n\n"
            "**The risk rule.** A news gap goes through a stop, so the loss is decided by the share count as much as "
            "by the stop price. If you widen a stop, cut the shares to the number in *Fits rule (sh)* — otherwise the "
            "loss at the Disaster SL grows past the rule even though nothing else changed.")
