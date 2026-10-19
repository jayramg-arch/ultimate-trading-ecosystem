# PRE-REGISTRATION — moving capital from v1 to v2

Registered **19 October 2026**, before any real v2 trade and before the first row of
`logs/system_equity.csv`. Jay approved the rule on 19 October ("I'm fine with the capital move rule for now").
The rule is coded in `system_equity.capital_rule()` and shown on ANALYSIS › ⚖️ v1 vs v2 › Capital decision.

## What is compared

| | definition |
|---|---|
| **v1** | the current system (GM + S4) — journal rows with `origin = v1`. Legacy rows (entered before 1 April 2026, cash parks, the 30-Mar-2026 tax-harvest batch, and COALINDIA) are reported separately and are **not** v1. |
| **v2** | the Clenow system — its ledger (`data/v2/real_book.json`), journal `setup = POS-V2`. |
| **capital** | v2 = one-third of the house sizing capital (`p1_paper.v2_capital()`); v1 = sizing capital less v2's. Each system's cash earns 6.75 % (the ICICI sweep-in FD). |
| **return** | time-weighted NAV from the nightly snapshot (auto-pilot Phase 12j), net of transfers (`data/system_transfers.csv`) and of rows re-classified between origins. |
| **benchmark** | Nifty 500 (`^CRSLDX`) over the same days. |

## The rule

The check runs no earlier than **6 months after v2's first real buy** and only once v2 has
**≥ 25 closed trades**. Then **move one-third of v1's capital to v2** only if all hold:

1. v2's annualised TWR beats v1's by **≥ 5 percentage points a year**;
2. v2's maximum drawdown is **no worse** than v1's;
3. v2 **beat the Nifty 500** over the same days.

Otherwise re-check every quarter. Capital never moves the other way (v2 → v1) on weaker evidence
than this; fresh money (a Dhan top-up) is a separate decision and is recorded in
`data/system_transfers.csv` as a transfer, so it never counts as return.

## What this does not decide

It does not judge either system's edge statistically — with 25 trades nothing would. It is a
guard against moving money on a few good weeks. Changing a threshold after the first live row is
written makes this a new registration, dated, with the reason.
