# Journal, Attribution & Daily Sync (Phase 0/1) — User & Trading Guide

> **Module Role:** The **performance-truth layer.** These modules turn your raw Dhan fills into an honest, attributable record: what you actually made (no flattering gaps), *which setups/stages/scores* made it, and a journal that stays in lockstep with your live broker book every day.
>
> **Files:** `performance_attribution.py` · `journal_enrichment.py` · `journal_sync.py` · `dhan_journal_v7.py` · `ai_reconcile_engine.py` · `dhan_symbols.py`. **DB:** `trade_journal_v6.db` (table `journal`).

---

## 1. `performance_attribution.py` — realized-P&L decomposition

Decomposes **closed-trade** realized P&L across 11 dimensions: System, Sector, Trade Type, Hold Period, Exit Reason, Trade Quality, **Setup/Catalyst, Entry Stage, Entry Alpha band, Entry RS band, Entry Conviction band**. Per bucket: n / win% / total ₹ / expectancy / profit-factor / signed contribution.

**Honesty layer (the anti-NaN→0 rule):** rows with a missing/zero exit price or qty are **quarantined and reported**, never zero-filled. Cash-park instruments (`LIQUID*`) are excluded (risk-off carry, not alpha). Canonical P&L is byte-identical to `ai_mentor_engine.py` (`(exit−buy)×qty`); derived metrics computed on read, never stored.

- Run: `python performance_attribution.py` (writes `reports/performance_attribution_*.csv`) or the **📐 Attribution tab** in the Web Commander AUTOPSY page.
- `contribution_pct` = signed share of **gross** \|P&L\| (robust on a net-negative book).
- Signal dimensions (setup/stage/alpha/RS) read "Unspecified" for trades closed before snapshots existed — a *shrinking* coverage gap, reported not imputed.

---

## 2. `journal_enrichment.py` — lean entry-signal snapshot

Adds **6 curated columns** to the journal so attribution can slice by signal: `setup · entry_stage · entry_alpha · entry_rs · entry_conviction · snapshot_meta`. Values come from `bull_screener.screen_symbol()` (the zero-drift PA mirror — no TradingView needed).

- `--mode migrate` (idempotent schema), `backfill` (as-of-today snapshot of OPEN trades, stamped `backfill`), `symbol` (one trade).
- **Auto-capture on new trades:** a hook in `dhan_journal_v7.upsert_trade()` captures a true `recompute` snapshot on every new OPEN insert (after commit, guarded so a fetch failure never blocks the save).
- `setup` is only meaningful at *true entry* (the catalyst is live at trigger); backfilled OPENs show `setup=NONE` if not currently triggering — by design.

---

## 3. `journal_sync.py` — daily journal ↔ Dhan holdings reconcile

Keeps the journal's OPEN positions identical to the live Dhan book:
- **ADD** live holdings missing from the journal (+ one backfill snapshot).
- **UPDATE** qty/avg that drift from Dhan.
- **CLOSE** journal OPENs no longer held — **only** with a completing SELL in the Dhan trade history (authoritative exit price/date); otherwise FLAG, never force.

**Safety:** aborts entirely if the holdings fetch fails or returns an empty book (an API hiccup must never read as "all sold"). Cash-park `LIQUID*` ignored both sides. `--dry-run` / `--no-close` flags.

**Scheduled:** Windows Task **`TradingJournal_DhanSync`** → `run_journal_sync.bat` → `.venv` python → `journal_sync.py`, **daily 4:30 PM IST** (post-close, `StartWhenAvailable`). Logs to `logs/journal_sync.log`.

---

## 4. The exit reconcile (one-time data recovery)

`ai_reconcile_engine.reconcile_journal_exit_prices()` recovers missing exit prices from the Dhan trade history. Two silent bugs fixed June 2026: the token call was outside `try` (a stale token crashed the whole reconcile), and the trade-history API returns only `securityId` + `customSymbol` (no ticker) — resolved via the new `dhan_symbols.get_nse_secid_to_symbol()` (full NSE scrip master, equities + ETFs).

**The finding that matters:** missing exit data had been *flattering* the book by ~₹4.4L. True closed-trade baseline = **−₹4,99,283 / 25.6% win / 0.24 PF**. This is the honest number all strategy work is measured against.

---

## 5. Key reminders

- **Trade off the live Dhan book, not the journal alone** — the daily sync makes them match, but the broker is authoritative (the journal had stale DMART + wrong quantities before the sync).
- **No Stage 3/4 holds** — the entry snapshot surfaces violations; RELIANCE (Stage 4) is the current open violation to exit.
- Backups are taken before every reconcile/sync write (`trade_journal_v6.backup_*.db`). The DB is *data* — not git-tracked; preserved via these dated backups.
