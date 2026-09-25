# commander_pages/action_center.py - the ACTION CENTER page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('action_center', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">🎯 Action Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Consolidated view of all pending actions requiring your immediate attention.</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <style>
        .metric-card {
            background: var(--surface);
            border-radius: 10px;
            padding: 15px 18px;
            border: 1.5px solid var(--rule);
            border-left: 4px solid var(--bull);
            margin-bottom: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        }
        .metric-card.warning {
            border-left: 4px solid var(--warn);
            border-top: 1px solid var(--warn-rule);
        }
        .metric-card.danger {
            border-left: 4px solid var(--bear);
            border-top: 1px solid var(--bear-rule);
        }
        .metric-title {
            color: var(--muted);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 6px;
            font-family: 'JetBrains Mono', monospace;
        }
        .metric-value {
            color: var(--ink);
            font-size: 1.35rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.spinner("Fetching live portfolio and analyzing journal..."):
        try:
            # `DhanContext` is NOT a module-level name here — this line raised
            # NameError on every run and the bare except read it as "no holdings",
            # so this page has been showing an EMPTY live book. Route through the
            # one client factory, which already handles the 2.0.x/older SDK split.
            _dhan_ac, _ = get_dhanhq_client()
            resp = _dhan_ac.get_holdings() if _dhan_ac else None
            holdings = [item for item in resp.get('data', []) if float(item.get('totalQty', 0)) > 0] if (isinstance(resp, dict) and resp.get('status') == 'success') else []
        except Exception as _e_hold:
            _gm_logger.warning(f"live holdings fetch failed: {_e_hold}")
            holdings = []
            
        live_symbols = {}
        for h in holdings:
            sym = clean_symbol(h.get('tradingSymbol'))
            live_symbols[sym] = h

        try:
            conn = sqlite3.connect(DB_FILE)
            df_open = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
            conn.close()
        except:
            df_open = pd.DataFrame()

        db_symbols = set()
        if not df_open.empty:
            if 'symbol' in df_open.columns:
                df_open['cleaned_symbol'] = df_open['symbol'].apply(clean_symbol)
                db_symbols = set(df_open['cleaned_symbol'].tolist())

        actions = {
            'missing_journal': [],
            'pending_closure': [],
            'missing_sl_target': [],
            'pending_exits': [],
            'missing_meta': [],
        }
        
        for sym, item in live_symbols.items():
            if sym not in db_symbols:
                actions['missing_journal'].append({
                    'symbol': sym,
                    'qty': item.get('totalQty'),
                    'avg_price': item.get('avgCostPrice'),
                    'ltp': item.get('lastTradedPrice', 0)
                })

        if not df_open.empty:
            for idx, row in df_open.iterrows():
                sym = row.get('cleaned_symbol', row.get('symbol', ''))
                if sym not in live_symbols:
                    actions['pending_closure'].append(row)
                sl = pd.to_numeric(row.get('stoploss', 0), errors='coerce')
                tgt = pd.to_numeric(row.get('target', 0), errors='coerce')
                if pd.isna(sl) or sl == 0 or pd.isna(tgt) or tgt == 0:
                    actions['missing_sl_target'].append(row)
                if sym in live_symbols:
                    ltp = float(live_symbols[sym].get('lastTradedPrice', 0))
                    if ltp > 0:
                        if not pd.isna(sl) and sl > 0 and ltp <= sl:
                            actions['pending_exits'].append({'row': row, 'reason': 'SL Hit', 'ltp': ltp})
                        if not pd.isna(tgt) and tgt > 0 and ltp >= tgt:
                            actions['pending_exits'].append({'row': row, 'reason': 'Target Hit', 'ltp': ltp})
                rat = str(row.get('rationale', ''))
                scr = str(row.get('screenshot_path', ''))
                if rat.strip() in ['None', '', 'nan'] or scr.strip() in ['None', '', 'nan']:
                    actions['missing_meta'].append(row)

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"<div class='metric-card danger'><div class='metric-title'>Critical Exits/Trims</div><div class='metric-value'>{len(actions['pending_exits'])}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card warning'><div class='metric-title'>Unjournaled Buys</div><div class='metric-value'>{len(actions['missing_journal'])}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card warning'><div class='metric-title'>Pending Closures</div><div class='metric-value'>{len(actions['pending_closure'])}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='metric-title'>Missing SL/Targets</div><div class='metric-value'>{len(actions['missing_sl_target'])}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    if len(actions['pending_exits']) > 0:
        st.subheader("🚨 Pending Exits / Trims")
        for item in actions['pending_exits']:
            row = item['row']
            with st.expander(f"🔴 {row.get('symbol')} - {item['reason']} @ {item['ltp']}"):
                st.write(f"**Target:** {row.get('target')} | **StopLoss:** {row.get('stoploss')} | **LTP:** {item['ltp']}")
                st.button("Open Journal 📝", key=f"btn_ex_{row.get('id', row.get('symbol'))}", on_click=lambda: st.toast("Navigate to Journal page to update."))

    if len(actions['missing_journal']) > 0:
        st.subheader("⚠️ Missing Journal Updates (Bought Stocks)")
        st.info("These stocks are in your live portfolio but missing from the active journal.")
        st.dataframe(pd.DataFrame(actions['missing_journal']), use_container_width=True)

    if len(actions['pending_closure']) > 0:
        st.subheader("⚠️ Pending Trade Closures (Sold Stocks)")
        st.info("These stocks are marked OPEN in journal but missing from live portfolio.")
        for row in actions['pending_closure']:
            with st.expander(f"📦 {row.get('symbol')} - Qty: {row.get('quantity')}"):
                st.write(f"**Buy Price:** {row.get('buy_price')} | **Date:** {row.get('entry_date')}")

    if len(actions['missing_sl_target']) > 0:
        st.subheader("ℹ️ Missing Stop Loss / Targets")
        for row in actions['missing_sl_target']:
            with st.expander(f"🛡️ {row.get('symbol')} - Missing Risk Parameters"):
                st.write(f"**StopLoss:** {row.get('stoploss')} | **Target:** {row.get('target')}")

    if len(actions['missing_meta']) > 0:
        st.subheader("📝 Missing Metadata (Rationale/Screenshots)")
        for row in actions['missing_meta']:
            missing_items = []
            if str(row.get('rationale', '')).strip() in ['None', '', 'nan']: missing_items.append("Rationale")
            if str(row.get('screenshot_path', '')).strip() in ['None', '', 'nan']: missing_items.append("Screenshot")
            with st.expander(f"🔍 {row.get('symbol')} - Missing: {', '.join(missing_items)}"):
                st.write(f"Please update the journal entry to include these details for better AI analysis.")

    if all(len(v) == 0 for v in actions.values()):
        st.success("🎉 All caught up! No pending actions required.")
        st.balloons()
