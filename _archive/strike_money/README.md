# Strike.Money integration — archived 13 Sep 2026

The Strike.Money subscription lapsed on 13 Sep 2026 and was not renewed. Everything that
drove the portal lives here, untouched, in case it is ever revived:

- `strike_automation.py` — Playwright upload of the 17 Commander watchlists (dated names,
  49-symbol chunking) + the old RRG scrape. Was auto-pilot Phase 6 and the Watchlist
  page's "Sync to Strike.Money" button.
- `strike_proof.py`, `test_strike_*.py` — its probes and tests.
- `Strike/`, `strike_user_data*/` — the browser profile / cookie store (gitignored; do
  not commit). `strike_html.txt` — a page dump that carried bearer tokens (gitignored).
- the `*.png` — login / delete debugging screenshots.

Replaced by `commander_watchlists.py` (repo root): the base-name list moved there, and
RRG Studio (`rrg_studio/`) lists all 17 watchlists from `rrg_studio/commander_screeners.json`,
which auto-pilot Phase 6 writes from the same `Generated_Watchlists/LATEST_*.txt` files
TradingView receives. The JdK/RRG calibration against Strike's published values
(`jdk_strike_calibrate.py`, `rrg_studio/strike_holdout_20260818.csv`, `STRIKE_CAL`) is
NOT archived — it is the maths RRG Studio runs on, independent of the portal.
