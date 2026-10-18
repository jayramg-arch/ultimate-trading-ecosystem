# 42 · The v2 System — end-to-end operating framework (18 Oct 2026)

The design and the evidence are in Doc 41; the rules and their tests in PREREG_v2_house_rules and
PREREG_v2_borrowed_rules. This document is how v2 RUNS, end to end — every step, who does it, when,
and which file carries it to the next step. It is defined first; the components are built to it.

## 1. Scope and decisions it rests on

- v2 runs in full form now, for real money, beside the current system (Jay, 18 Oct). It does not
  wait for 16 Jan 2027 — but it only BUYS when the Nifty 500 is above its 200-day SMA, so in
  practice real buying starts when the market recovers. The paper books keep running as the record.
- **Capital:** one-third of the trading capital (house sizing capital ÷ 3 = ₹10,00,000 today;
  `V2_CAPITAL` in .env overrides). The current system keeps the rest.
- **The live rule set is V2H** (`v2_house.V2H_LIVE`): P1E's ensemble rank, top 25 %, 0.10 % of
  equity per ATR20, Wednesday rebalance, a 4 × ATR14 disaster stop with the house Chandelier trail,
  tax-aware runners + monthly risk trims, the ETF sleeve (own pool, NAV premium ≤ 3 %), sector cap
  25 %, correlation block 0.90, per-trade cap 3.33 % of equity; earnings and stale-data guards.
- **No targets, no intraday triggers.** The trigger is the weekly rank at Tuesday's close.

## 2. The weekly cycle

| When (IST) | Step | Who / what | Output |
|---|---|---|---|
| **Tue 16:30** | ① v2 engine runs first in the auto-pilot (before the watchlists are built) | `p1_paper.py` + `v2_house.py` | fills, marks, stops for the paper books; the Tuesday-close **decision** |
| Tue ~16:35 | ② your orders sized for your real v2 book (from your journal rows) | `p1_paper.v2_workflow` | order sheet `reports/p1_paper/orders_<date>.md` → section **YOUR v2 ORDERS** |
| Tue ~16:35 | ③ the TradingView list + the chart status line | same | `FINAL_V2_WATCHLIST.csv` → **`V2_System-DDMONYY`**; `data/v2/addon_status.txt` → Add-ons M2 |
| Tue ~16:35 | ④ the week's buys go to the reviewer (Daily chart, S4 + S5 read, execution check only) | receiver, tag `v2` | a ruling per name in the Reviewer Log + Telegram |
| Tue ~16:40 | ⑤ Telegram summary of all books + the order count | `p1_paper.send_summary` | one message |
| Tue ~17:00 | ⑥ watchlists generated and pushed to TradingView | auto-pilot Phase 4.8 / 7 | `V2_System-DDMONYY` in TradingView |
| **Tue evening** | ⑦ **you review** (10–15 min): the 🧭 v2 page (orders, rulings), then the `V2_System` list on a **Daily** chart with S4, S5 and Add-ons | Jay | buy / skip per name |
| **Wed 09:15** | ⑧ **you place** the sells and buys at the open; one Dhan stop order per buy at its disaster stop (full shares, limit below trigger) | Jay at Dhan | orders + resting stops |
| Wed after the fill | ⑨ record each buy: `python v2_take.py SYM --price P --qty Q` | Jay (one line per buy) | journal OPEN row, setup `POS-V2`, stop = initial SL |
| **Daily 16:30** | ⑩ the nightly run: paper books marked and stopped; the regime-turn alert; journal sync closes any v2 row Dhan sold | auto-pilot | Telegram if the regime turned |
| Daily, as needed | ⑪ trail: Risk Shield shows the Chandelier for `POS-V2` rows; raise the Dhan stop when it moves up (the automatic GTT trail is off since 3 Oct — static IP pending) | Jay | tightened stop |

Fridays need nothing for v2; P1E and the research books still decide at Friday's close for the record.

## 3. The TradingView list and what S4 / S5 do with it

- **Name:** `V2_System-DDMONYY` (the date of the run). Names in this order (the Add-ons line on the chart says which group a name is in): **BUY** (this week's
  buys — yours and the V2H paper book's), **SELL**, **HOLD** (your v2 holdings, then paper),
  **WATCH** (the top 30 of the rank, for context).
- **S4 and S5 are execution aids for v2, not judges.** The reviewer reads them on the Daily chart
  for each buy and is told the selection is already made: it looks only for reasons not to buy at
  Wednesday's open — over-extension, results within the week, a wall within 1 ATR, a gap, thin
  liquidity. A WAIT or PASS means skip that buy this week; the name comes back next Tuesday if it
  still ranks.
- **Ignore S4's own VERDICT / GO / TAKE-IT rows on v2 names** — those are the current system's entry
  rules (PA, location, volume, bar), which v2 deliberately does not use.
- **Add-ons M2 (v2 status)** prints the v2 facts on the chart of any v2 name: rank of N, the section
  (BUY / SELL / HOLD / WATCH), the disaster or trailed stop (drawn as a line), real or paper holding,
  and the date of the decision. Pushed nightly with the status file; display only.

## 4. Triggers and alerts

| Event | Signal | Channel |
|---|---|---|
| The week's orders | Tuesday close, ranked by the rules | order sheet, v2 page, Telegram summary |
| Reviewer ruling per buy | Tuesday evening | Telegram (per review) + Reviewer Log |
| The regime turns | the Nifty 500 closes across its 200-day SMA | Telegram, once, the evening it happens |
| A stop is hit | Dhan executes the resting stop | Dhan; journal sync closes the row at 16:30 |
| The trail moves up | Chandelier above the resting stop | Risk Shield (you raise the Dhan stop) |
| NOT used for v2 | S4 GO alerts, GM-POS GO / zone / thesis alerts | those belong to the current system |

## 5. Components and their status

| # | Component | File | Status |
|---|---|---|---|
| C1 | rules engine (one `decide()` for backtest and live) | `v2_house.py` | built, tested |
| C2 | nightly engine + paper books + order sheet + Telegram | `p1_paper.py` | built |
| C3 | rank board + v2 page | `p1_paper.write_board`, `commander_pages/v2_system.py` | built |
| C4 | reviewer routing (tag v2, execution-only context) | `v2_core.py`, receiver | built |
| C5 | real-book orders from the journal | `p1_paper.v2_workflow` | built, dry-run tested |
| C6 | record a real fill | `v2_take.py` | built |
| C7 | TradingView list `V2_System-DDMONYY` | `FINAL_V2_WATCHLIST.csv` + `watchlist_manager` + Phase 7 | built (first push Tue 20 Oct) |
| C8 | pipeline order: v2 engine before the watchlists | `run_pipeline.py` (Phase 12i → 4.79) | built |
| C9 | chart status (Add-ons M2) + its pusher | `Commander_Addons_v1.0.pine` (v1.1), `tv_push_addons.py`, AFTER_COMPILE step 5 | built — **Jay compiles Add-ons v1.1** |
| C10 | regime-turn alert | `p1_paper.v2_workflow` | built |
| C11 | Risk Shield / journal sync for `POS-V2` rows | existing (setup prefix POS → positional trail) | works as is |

## 6. Data contracts

- **Journal:** a v2 holding is an OPEN row with `setup = POS-V2`, `Timeframe = Positional`,
  `initial_sl = stoploss = disaster stop`, no targets. This is how v2 tells its holdings from the
  current system's.
- **`FINAL_V2_WATCHLIST.csv`:** `Symbol, Section, Rank, Stop, Held`.
- **`data/v2/addon_status.txt`:** one line, `_ASOF:<date>;<fill date>,SYM:<rank>/<n>;<section>;<stop>;<held>,…`
  (each `-`/`&` symbol also under TradingView's `_` spelling).
- **Order sheet:** the paper books, then `## YOUR v2 ORDERS` with side, shares, value and stop.

## 7. Risk controls and the open decisions (Jay)

In force: the regime gate, the resting disaster stop + Chandelier trail, per-trade cap 3.33 %,
sector cap 25 %, correlation block, ETF NAV premium and liquidity floors, earnings and stale-data
guards, the reviewer's one-week deferral.

Open:
1. **The house open-risk budget and the 25-position limit.** Both starved v2 in the test. Proposal:
   they apply to the current system's book; v2 is limited by its own capital slice and rules.
2. **A name held by both systems.** Proposal: v2 does not buy a name the current system already
   holds (no double exposure); it still holds what it owns.
3. **Order type at Wednesday's open.** Proposal: a limit at Tuesday's close + 1 %, cancelled if unfilled
   by 10:00 (the backtest filled at the open price).
4. **Automatic trailing at Dhan** needs a static IP registered with Dhan (deferred) — until then the
   trail is raised by hand from Risk Shield.

## 8. Decisions of 18 Oct (evening) and the designs they need

**D1 — house limits.** The open-risk budget, exposure tiers, circuit breaker, 25-position limit
and the order gate count only the current system's positions (built).

**D2 — v2 may pyramid onto a current-system holding** (Jay: with positional trades auto-trailed,
both systems exit the same way). Design, keeping the house invariant of ONE journal row and ONE
stop price per holding:
- **The v2 ledger** `data/v2/real_book.json` is v2's record of ITS shares: per symbol, shares, entry,
  entry date, the add's disaster stop. The journal keeps one row per symbol (owned by whichever
  system bought first); `journal_sync` keeps that row's quantity equal to Dhan's total.
- **v2 buys a name the current system holds** → the order sheet marks it **PYRAMID (onto a
  current-system holding)**; after the fill there is still ONE resting stop for ALL shares, at the
  higher of the holding's current stop and the add's disaster stop (fill − 4 × ATR14).
  `v2_take.py` records the slice in the ledger and leaves the journal row alone.
- **v2 sells its slice** when the rank says so: the order sheet gives the slice's shares only;
  `v2_take.py SYM --sell --price P` closes the slice; the current system's shares stay.
- **A stop fill sells everything** (one stop): the nightly run sees the journal row CLOSED and closes
  the slice too, at the journal's exit price.
- v2's limits (per-trade cap, sector cap) count v2's slices; the current system's count its rows.

**D3 — Wednesday order type:** a limit at Tuesday's close + 1 %, cancelled if unfilled by 10:00.

**D4 — auto-trailing**, for v2 holdings AND the current system's POSITIONAL holdings; swing trades
are NOT trailed (Jay). Design (`gtt_auto_shield --trail`, one pass per Dhan stop order):
- level = the house positional Chandelier (highest close since entry, 22 sessions, − 4.5 × ATR22);
- never closer than **3 × ATR14 to the last close** (`house_policy.DHAN_STOP_MIN_ATR`): the new stop
  is the LOWER of the two, so a trail can never sit inside normal daily noise;
- raise-only; once a day after the close (15:45), on closing prices; never sells — if the level is
  at/above the close it is reported as an exit review, not placed;
- a hand-set stop (Risk Shield override) is the floor (Floor mode) or the stop itself (Exact mode);
- **dry run first:** each evening a Telegram lists the moves it would make; nothing changes at Dhan
  until Jay switches it live — which also needs the static IP registered with Dhan (DH-905).

**D5 — a full v2 page in Web Commander** (EXECUTION › 🧭 v2 SYSTEM), separate from the paper page:
status strip (regime, next decision and fill dates, v2 capital, equity, cash); this week's orders
for your book with the reviewer's rulings and the pyramid list; your v2 book (slices, stops,
Chandelier, rank now); the rank board with filters and the ETF pool (premium, liquidity); risk
(sector weights vs the 25 % cap, per-name size vs the cap); the trail proposals; the weekly
checklist; rules and evidence. The paper books stay on 🧭 PAPER · v2 SYSTEM.

### Built (18 Oct evening)

| # | Component | File | Status |
|---|---|---|---|
| C12 | v2 ledger (v2's own shares, shared holdings) + `v2_take --sell` | `v2_ledger.py`, `v2_take.py` | built, tested |
| C13 | pyramid buys on the order sheet (one stop for all shares, the current system's rung) | `p1_paper.v2_workflow` | built |
| C14 | auto-trail: positional only, capped at close − 3 × ATR14, Telegram report | `gtt_auto_shield.py --trail`, task `GTT_Trail_Daily` 15:45 | built — **dry run** (first report Mon 19 Oct) |
| C15 | the v2 page | `commander_pages/v2_live.py` (EXECUTION › 🧭 v2 SYSTEM) | built |
| C16 | house limits exclude v2 | `house_policy.is_v2` / `v2_symbols`, `open_risk`, `pre_trade_gate` | built |

To switch the trail live: register the PC's (or a relay's) static IP with Dhan, then remove
`--dry-run` from `run_gtt_trail.bat`.
