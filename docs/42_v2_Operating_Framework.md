# 42 · The v2 System — end-to-end operating framework (18 Oct 2026, revised 19 Oct)

The design and the evidence are in Doc 41; the rules and their tests in PREREG_v2_house_rules and
PREREG_v2_borrowed_rules. This document is how v2 RUNS, end to end — every step, who does it, when,
and which file carries it to the next step. It is defined first; the components are built to it.

## 1. Scope and decisions it rests on

- v2 runs in full form now, for real money, beside the current system (Jay, 18 Oct). It does not
  wait for 16 Jan 2027 — but it only BUYS when the Nifty 500 is above its 200-day SMA, so in
  practice real buying starts when the market recovers. The paper books keep running as the record.
- **Capital:** one-third of the trading capital (house sizing capital ÷ 3 = ₹10,00,000 today;
  `V2_CAPITAL` in .env overrides). The current system keeps the rest.
- **The live rule set is V2H** (`v2_house.V2H_CLENOW`, from 19 Oct — §10): P1E's ensemble rank,
  top 25 %, 0.10 % of equity per ATR20, Wednesday rebalance, **no stop and no trail** (Clenow's exits),
  a **twice-monthly two-way resize** to equal risk (±10 % band), tax-aware runners, the ETF sleeve
  (own pool, NAV premium ≤ 3 %), sector cap 25 %, correlation block 0.90, per-trade cap 3.33 % of
  equity; earnings, stale-data and **NSE surveillance** guards.
- **No targets, no intraday triggers.** The trigger is the weekly rank at the decision close
  (Tuesday; Monday when Tuesday is an NSE holiday, as on 19 Oct 2026).

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
| **Wed 09:15** | ⑧ **you place** the order sheet at the open: SELL, RESIZE ↓/↑, BUY (no stop order), and CONVERT (sell the excess of a current-system holding, **cancel its v1 stop**) | Jay at Dhan | orders; no stops for v2 |
| Wed after the fill | ⑨ record each fill: `v2_take.py SYM --price P --qty Q` (buy / resize ↑), `--sell` (sell / resize ↓), `--convert --keep K` (convert) | Jay (one line per fill) | journal + v2 ledger |
| **Daily 16:30** | ⑩ the nightly run: paper books marked; the **v2 EXIT WATCH** (Telegram for any holding failing an exit at that close); the regime-turn alert; journal sync closes any v2 row Dhan sold | auto-pilot | Telegram when there is something to see |
| Any day | ⑪ look: Risk Shield › 🧭 v2 Holdings, and Add-ons M2 on the chart (100-DMA line, ±15 % band, rank vs cut) | Jay | — |

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
- **Add-ons M2 (v2 status, v1.2)** prints the v2 facts on the chart of any v2 name: the section
  (BUY / SELL / HOLD / WATCH), rank of N against the buy cut, real or paper holding, the decision
  date, and v2's exit levels — the 100-day average of daily closes (orange line) and the previous
  close ±15 % (dotted), plus flags for "not in the Nifty 500" and "NSE surveillance". Pushed nightly
  with the status file; display only.

## 4. Triggers and alerts

| Event | Signal | Channel |
|---|---|---|
| The week's orders | Tuesday close, ranked by the rules | order sheet, v2 page, Telegram summary |
| Reviewer ruling per buy | Tuesday evening | Telegram (per review) + Reviewer Log |
| The regime turns | the Nifty 500 closes across its 200-day SMA | Telegram, once, the evening it happens |
| An exit fails at a close | below the 100-DMA, a > 15 % one-day move, outside the cut, out of the index, surveillance | **v2 EXIT WATCH** Telegram that evening; sold at the next rebalance open if still failing at the decision close |
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
| C9 | chart status (Add-ons M2) + its pusher | `Commander_Addons_v1.0.pine` (v1.2), `tv_push_addons.py`, AFTER_COMPILE step 5 | built — **Jay compiles Add-ons v1.2** |
| C10 | regime-turn alert | `p1_paper.v2_workflow` | built |
| C11 | Risk Shield / journal sync for `POS-V2` rows | the v1 trail, exit scan, ladder, v67 slots and stop warnings SKIP `POS-V2` (19 Oct) | built |

## 6. Data contracts

- **Journal:** a v2 holding is an OPEN row with `setup = POS-V2`, `Timeframe = Positional`, no stop,
  no targets. A converted holding's v1 row is CLOSED at the conversion price ("Converted to v2") and
  a new v2 row opens at the same price. Each holding is ONE system's — never both.
- **`FINAL_V2_WATCHLIST.csv`:** `Symbol, Section, Rank, Stop, Held` (Stop empty for v2).
- **`data/v2/addon_status.txt`:** one line, `_ASOF:<date>;<fill date>,SYM:<rank>/<n>;<section>;<stop>;<held>;<cut>;<flags>,…`
  (flags: X = not in the Nifty 500, S = NSE surveillance; each `-`/`&` symbol also under `_`).
- **Order sheet:** the paper books, then `## YOUR v2 ORDERS` (order, shares, value, note, cash
  needed), then `## v2 EXIT WATCH` when a holding fails an exit.

## 7. Risk controls and the open decisions (Jay)

In force (19 Oct): the regime gate, Clenow's exits (no resting stop — §10), the twice-monthly resize,
per-trade cap 3.33 %, sector cap 25 %, correlation block, ETF NAV premium and liquidity floors, NSE
surveillance, earnings and stale-data guards, the reviewer's one-week deferral. The open items below
were decided on 18 Oct (§8) and revised on 19 Oct (§10); kept for the record.

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

**D2 — v2 may pyramid onto a current-system holding** — *superseded 19 Oct by CONVERT (§10); kept for the record* (Jay: with positional trades auto-trailed,
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

## 9. The static-IP relay for Dhan order calls (JioFiber has no static IP)

Dhan accepts order placement and changes only from the IP registered on the account (DH-905
otherwise); data, holdings and the journal sync are unaffected. Jio gives no static IP at home, so
a small **AWS Lightsail server in Mumbai** with a static IP relays ONLY the order calls. It is
reachable only over Tailscale — the proxy is never open to the internet — and the Dhan token is
never stored on it.

**Jay's part (account and payment are yours):**
1. Create an AWS account; open **Lightsail** → *Create instance* → Region **Mumbai (ap-south-1)**,
   Linux, **Ubuntu 24.04**, the cheapest plan **with a public IPv4** (the $3.50 plans are IPv6-only).
2. *Networking* → **Create static IP** → attach it to the instance. In the instance's firewall,
   keep only SSH (22).
3. Open the instance's browser SSH and paste:
   ```
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up --hostname=dhanrelay
   sudo apt-get update && sudo apt-get install -y tinyproxy
   sudo sed -i 's/^#\?Port .*/Port 8888/; s/^Allow .*/Allow 100.64.0.0\/10/' /etc/tinyproxy/tinyproxy.conf
   sudo systemctl restart tinyproxy
   echo 'precedence ::ffff:0:0/96  100' | sudo tee -a /etc/gai.conf && sudo systemctl restart tinyproxy
   ```
   The last line makes the relay prefer IPv4: Dhan's API is on CloudFront, which also answers over
   IPv6, and a Lightsail server is dual-stack - without it Dhan sees the server's IPv6 address and
   replies DH-905 although the IPv4 is registered (found 18-Oct).
   (sign the `tailscale up` link in with the same account as the PC).
4. On the PC, add to `.env`: `DHAN_ORDER_PROXY=http://dhanrelay:8888`, then run
   `python dhan_relay.py --check` — it prints the relay's public IP. It must equal the Lightsail
   static IP.
5. Register that IP at web.dhan.co → Profile → Trading & Data APIs → static IP. **It locks for 7
   days**, so do step 4 first.
6. **Refresh the Dhan access token after registering the IP** (`python dhan_auth.py --force`): Dhan
   applies a newly registered IP only to tokens issued after it — the 18-Oct test was refused (DH-905)
   with the earlier token and accepted right after a refresh. The 08:00 job refreshes daily anyway.
7. `python dhan_relay.py --test-modify` re-submits one OCO and one SINGLE stop at their SAME values
   through the relay (it asks first). "RELAY WORKS" → remove `--dry-run` from `run_gtt_trail.bat`.
   **Passed 18 Oct 2026** (both kinds accepted via 16.4.135.197; read back unchanged).

**The code side (built):** `dhan_relay.py` wraps the dhanhq order methods once per process
(installed by `dhan_auth`, and by `n8n_order_handler`); with `DHAN_ORDER_PROXY` unset nothing
changes. Every surface that places or changes an order — the trail, Risk Shield's tighten
buttons, the webhook, the MCP server — goes through the relay the moment the variable is set.

## 10. Decisions of 19 Oct (Jay) — Clenow's rules, convert, and what watches v2

| # | Decision | Evidence |
|---|---|---|
| 1 | **No stop, no trail on v2.** Exits are Clenow's: out of the top-25 % cut, a decision close below the 100-day average, a one-day move beyond 15 % in 90 days, leaving the Nifty 500. | Descriptive run (`v2_house.py --clenow`): CAGR 17.3 % → 20.4 %, MAR 0.86 → 1.00, max DD −20.1 % → −20.3 %. |
| 2 | **Twice-monthly two-way resize** (every second decision) to equal risk, ±10 % band — replaces the monthly trims and the B8 top-up. | Same run: ±10 % band 20.5 % / MAR 1.00 at 553 trades a year; no band 0.97 at 854; ±25 % 0.97. |
| 3 | **NSE surveillance exclusion** (`nse_surveillance.py`): ASM Stage II+, any GSM stage, a 5 % / 2 % band or trade-for-trade = out of the pool (no buy; a holding is sold). Live only. | 4 Nifty 500 names out on 19 Oct: HFCL, STLTECH, MTARTECH, VISL. |
| 4 | **The Nifty 500 list refreshes nightly** (auto-pilot Phase 0.6, `check_universe_listing.py --refresh`); REITs and placeholders left out. | The list was 12-Aug: 25 joiners and 28 leavers of the September reconstitution were missing. |
| 5 | **Dhan's daily bars are split/bonus adjusted** — the 15 % rule does not misfire on a corporate action. | 20 of 20 splits/bonuses in Nifty 500 names (Oct-25 .. Aug-26): ex-date move −2 % to +14 % on Dhan, the provider cache and the backtest panel alike. |
| 6 | **CONVERT, not two slices**, when v2 buys a stock the current system holds: the whole holding becomes v2's and is resized to v2's target at the open; the excess is sold; the v1 stop is cancelled. | PREREG_pyramid_slices_vs_convert: 130 overlaps, convert + resize − v1 rules = +2.33 % of the position, CI [+0.95, +3.71], both halves positive; resizing at once (descriptive) +2.58 %, CI [+1.00, +4.20]. |
| 7 | **v2 cash earns the bank sweep-in FD rate** (≥ 6.75 %, Jay); no liquid ETF. Money moves to Dhan before a Wednesday with buys — the order sheet states the amount. When the market recovers Jay tops up the Dhan account. | — |
| 8 | **Later, on real results:** compare v1 and v2 live returns; then move part of v1's capital into v2, or add fresh capital to v2 (Jay). | No rule yet — decided on the live record, not on the backtest. |

**How v2 is watched without stops:** Risk Shield › **🧭 v2 Holdings** (`v2_risk.py` — exits per
holding, rank vs cut, distance to the 100-DMA, 90-day max move, index/surveillance, resize target vs
held, tax-hold band, sector weights, the next decision and whether it is a resize day); the nightly
**v2 EXIT WATCH** Telegram; Add-ons **M2 v1.2** on the chart. The current system's trail job, 16:00
exit scan, pyramid ladder, v67 slots/stop book, swing/positional review and stop warnings leave v2
holdings alone.

**What a v2 order is:** one buy at the open (limit at the decision close + 1 %, cancelled by 10:00),
no stop order, no target legs — the current system's Risk Allocator and OCO legs do not apply.

