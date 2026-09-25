"""journal_path — the ONE place the trade journal's location is decided (AUD-INT-14, 25-Sep-2026).

Before this, 25 modules each carried their own path; twelve were relative
("trade_journal_v6.db"), so they silently opened a DIFFERENT (or brand-new, empty)
database whenever the working directory was not the project folder — e.g. a Task
Scheduler job started elsewhere. Every live module now imports JOURNAL_DB from here.

COMMANDER_JOURNAL_DB overrides it (the render harness points it at a copy).
Deliberately import-safe: no sqlite, no side effects — journal_core creates the DB, this
module only names it.
"""
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
JOURNAL_DB = os.environ.get("COMMANDER_JOURNAL_DB") or os.path.join(APP_DIR, "trade_journal_v6.db")
