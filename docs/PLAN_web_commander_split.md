# Plan — splitting Web Commander into page modules

*Written 25 Sep 2026 after the integration audit. Approved in principle by Jay ("5) Yes");
this document is the plan to approve before any code moves.*

## Why

`weinstein_commander_web_v4.0.py` is 19,700+ lines: **5,770 lines** of shared setup and helpers,
then 22 pages in one `if/elif page ==` chain. Three costs, all seen in the last month:

1. **Nothing can be tested without running the whole app.** Every page's logic sits inside
   Streamlit calls, so a page is checked only by clicking it. The audit's five sizers on four
   risk rates survived because no test could import any of them.
2. **Drift hides in distance.** The same rule was re-implemented 2,000–10,000 lines apart
   (E-02's stop vs Risk Shield's, the two earnings lookups).
3. **One failure takes out every page.** A `NameError` in one helper surfaces as four unrelated
   Risk Shield symptoms (10–11 Aug), and every edit risks the whole file.

## Sizes (lines, 25 Sep)

| page | lines | page | lines |
|---|---:|---|---:|
| RISK SHIELD | 3,009 | OPTIONS | 416 |
| GOLDEN MATCHER | 2,362 | DASHBOARD | 377 |
| HUNTER | 1,109 | PRE-MARKET | 356 |
| WATCHLIST | 1,102 | TV SIDECAR | 306 |
| AI LAB | 585 | AUTOPSY | 302 |
| X-RAY | 531 | POST-MARKET | 285 |
| BREADTH | 520 | BACKTEST | 283 |
| ETF | 518 | FUNDAMENTALS | 197 |
| COMMAND | 456 | NEWS | 189 |
| PORTFOLIO | 455 | ACTION CENTER | 160 |
| MACRO | 453 | JOURNAL | ~15 |

Shared state: 291 `st.session_state` references, 10 cached functions, and a handful of
module-level globals every page reads (`balance`, `sys_status`, `total_cap`,
`df_active_global`, `df_live_holdings`, the regime pills).

## The rules the split must keep

- **Behaviour-identical, move-only.** No logic change rides along with a move. A fix found
  during a move is a separate commit.
- **One page per evening, after 15:30.** Each move is merged, rendered and checked before the
  next; the market-hours rule applies to every step.
- **Session-state keys do not change.** Widget keys and `st.session_state` names stay exactly
  as they are, so no saved state, pop-out or bookmark breaks.
- **The entry file keeps its name and its routes** — `?view=gm_window`, `?view=gm_board_maximized`,
  `?p=`, `?tf=` — because `MORNING.bat`, the desktop shortcuts, the ALL-3-BOARDS button and
  `gm_evening_headless.py` (auto-pilot Phase 12) all address it.
- **Cached functions move with a stable name.** `st.cache_data` keys on module + name, so a
  move empties that cache once; that is acceptable, a renamed function is not.

## Phases

**Phase 0 — a safety net first (1 evening).** An AppTest smoke suite that renders every page
from a fixture (a copy of the journal, the board caches, `gm_settings.json`, Dhan mocked
offline) and records exceptions and the widget tree per page. It runs before and after every
move; a move is done when the tree is unchanged. Nothing moves until this is green.

**Phase 1 — shared context (1–2 evenings).** A `commander_context.py` that builds the
module-level globals once per rerun into one object (`balance`, `sys_status`, capital,
holdings, regime, the journal frame) and exposes the helpers pages share (`inr`,
`format_inr_int`, `section`, `card`, the Dhan client). The main file calls it and pages
receive it. This is where the "which capital?" class of bug becomes impossible to reintroduce.

**Phase 2 — pure cores out (3–4 evenings).** Move the Streamlit-free logic into importable
modules, re-exported from the main file so nothing else changes:
`gm_core.py` (`compute_workflow`, `compute_recovery_workflow`, the stop ladder,
`_house_initial_stop`, the section builders), `risk_shield_core.py` (the per-position tile
maths, heat, proposals), `hunter_core.py`, `watchlist_core.py`. Each gets characterization
tests pinned on today's output.

**Phase 3 — pages out (one per evening, ~12 evenings).** Each `elif page ==` block becomes
`commander_pages/<page>.py` with `render(ctx)`. Order: smallest and least traded-on first
(JOURNAL, NEWS, FUNDAMENTALS, ACTION CENTER, BACKTEST, POST-MARKET, AUTOPSY, TV SIDECAR,
PRE-MARKET, DASHBOARD, OPTIONS, MACRO, PORTFOLIO, COMMAND, ETF, BREADTH, X-RAY, AI LAB,
WATCHLIST, HUNTER), then **GOLDEN MATCHER** and **RISK SHIELD** last, each over two evenings
(helpers, then page), because they are the ones you trade from.

**Phase 4 — guards (1 evening).** Tests that fail if a page re-implements a house rule
(extends `tests/test_house_policy.py`), and a line-count budget per page file so the split
does not silently regrow.

**End state:** the main file is a router of roughly 1,500 lines (setup, nav, pop-out routes),
22 page files of 150–1,500 lines, and cores that import without Streamlit.

## Effort and risk

About **20 working evenings** in total, spread over 4–6 weeks at one page an evening.
Riskiest steps: Phase 1 (every page reads those globals) and the two big pages. Mitigation:
the Phase-0 widget-tree diff, move-only commits, one page per evening, and a revert that is
one `git revert` per page.

## What needs Jay's go-ahead

1. This plan, as written or amended.
2. The Phase-0 fixture uses a **copy** of `trade_journal_v6.db` under `tests/fixtures/`,
   git-ignored — confirm it is fine to copy the journal there.
3. Scheduling: one page per evening after 15:30 means ~4–6 weeks; say if you want it faster
   (two pages an evening doubles the review load) or paused around results season.

## Outcome — executed 25 Sep 2026, in one pass (Jay: "finish everything in one go")

| phase | done | how it was proven |
|---|---|---|
| 0 safety net | `tools/render_pages.py` + journal copy in `tests/fixtures/` | renders every page, diffs exceptions / error boxes / element counts |
| 1 shared context | **not built as a separate object** — see below | — |
| 2 pure cores | `commander_core.py`: 46 functions + 20 constants (GM decision core, stop ladder, helpers) | AST selection + trap check; pyflakes 0 undefined names before and after; imports standalone; characterization tests |
| 3 pages | 22 files in `commander_pages/`, router 19,715 → 4,309 lines | byte-for-byte reassembly proof in `tools/split_pages.py` |
| 4 guards | `tests/test_split_guards.py`; house-policy guard now scans router + core + pages | 282 tests pass |

**Why phase 1 was not built as planned.** Pages run in the router's namespace
(`commander_pages.run(slug, globals())`), which is what makes the move provably
behaviour-identical — a context object would have meant rewriting every global read on 22
pages, i.e. a logic change riding along with the move. The rules the context object was
meant to protect already have one owner (`house_policy.py`). The remaining shared globals
(`balance`, `sys_status`, the journal frames) are the next refactor, now that each page is
its own file and can be converted and tested one at a time.

**Found on the way:** the shared `_g` getter was rebound inside two pages (fixed); a dead
duplicate `_range_bar` (removed); 25 modules each carry their own journal path (noted,
AUD-INT-14).

**Still to do after the merge:** render every page before and after with
`tools/render_pages.py` (outside market hours), and edit pages in `commander_pages/` from now
on — Streamlit's watcher does not see those files, so restart after an edit.
