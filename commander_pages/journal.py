# commander_pages/journal.py - the JOURNAL page of Web Commander.
#
# MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 (tools/split_pages.py,
# docs/PLAN_web_commander_split.md phase 3). The app runs this file with
# commander_pages.run('journal', globals()), so it sees exactly the globals it saw inline.
# The body stays under `if True:` so no line was re-indented. Edit the page HERE.
if True:
    st.markdown('<div class="page-title">📓 Trade Journal</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Active trades, closed history and the performance '
                'laboratory — the same views as the standalone app, reading the same DB.</div>',
                unsafe_allow_html=True)
    try:
        import journal_page
        journal_page.render(in_app=True)
    except Exception as _je:
        # Loud, and specific about which half failed. A blank page here would read
        # as "no trades" rather than "the journal did not load".
        st.error(f"❌ Journal failed to render: {type(_je).__name__}: {_je}")
        with st.expander("Traceback"):
            import traceback as _tb
            st.code(_tb.format_exc())
        st.caption("The standalone app still works: `streamlit run dhan_journal_v7.py`")
