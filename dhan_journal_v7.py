"""dhan_journal_v7 — the standalone Trade Journal, and the name everything imports.

WHAT CHANGED (23-Sep-2026) AND WHY
----------------------------------
This file used to be 1,704 lines: a data layer, and then a Streamlit app painted at
MODULE level from `st.set_page_config` onward. That meant importing it for a data
helper RENDERED THE WHOLE JOURNAL into whatever page triggered the import — which
happened twice (Risk Shield, 10-Sep, and the Golden Matcher's "Log OPEN trade"
button, which also kicked off a live Dhan portfolio sync as a side effect). There
was a comment warning about it, then a helper that read DB_FILE out of this file's
SOURCE to avoid importing it, then a test. Three workarounds for one shape.

It is now split at the seam it always had:

    journal_core.py   the data layer, VERBATIM — schema, migration, upsert_trade,
                      the Dhan fetches. No UI, safe to import from anywhere.
    journal_page.py   the dashboard, wrapped in render(). Draws only when called.

This file re-exports the data layer under its original name, so every existing
importer keeps working unchanged (s4_take, journal_enrichment, journal_sync,
pages/1_home, the web app's guided execution), and boots the standalone app when
run directly. `streamlit run dhan_journal_v7.py` behaves exactly as before.

The UI bootstrap sits behind `if __name__ == "__main__"`, so importing this module
no longer paints anything — which is also what lets tests/test_no_ui_module_imports
stop flagging it (that guard deliberately skips a main-guard).

Jay's call, 23-Sep: the journal is an active part of Web Commander, not a second
app in a second console. The in-app page is JOURNAL; this remains for running it
on its own.
"""

# The data layer, under its original names. Consumers import upsert_trade, load_db,
# init_db, migrate_db, get_sector, fetch_active_orders, DB_FILE, dhan … from here.
from journal_core import *        # noqa: F401,F403
import journal_core as _core      # noqa: F401  — for `dhan_journal_v7._core.X` if ever needed

# Re-exported explicitly as well, so a reader can see what this module promises and
# `from dhan_journal_v7 import X` keeps working even if journal_core grows an __all__.
from journal_core import (        # noqa: F401
    DB_FILE, SCREENSHOT_DIR, DEFAULT_SECTOR, CLIENT_ID, API_KEY, dhan,
    init_db, migrate_db, load_db, upsert_trade, parse_rr,
    calculate_ageing, get_fy, clean_symbol, get_sector, format_inr,
    to_excel, save_screenshot, fetch_live_data, fetch_active_orders,
    sync_history_data,
)

if __name__ == "__main__":
    # Standalone only. Never on import — that is the whole point of the split.
    import streamlit as st

    st.set_page_config(page_title="Trade Journal v7", layout="wide",
                       page_icon="📘", initial_sidebar_state="expanded")
    import journal_page

    journal_page.render(in_app=False)
