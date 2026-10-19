# PREREG · pyramiding a v1 holding through v2: two slices or convert (19 Oct 2026)

Jay (19 Oct): when v2 buys a stock the current system (v1) already holds, keep two slices (v1's
shares on v1's stop, v2's shares on v2's exits) or convert the whole holding to v2's rules?
Written BEFORE any number below exists.

## Data and unit

- **v1 trades:** the positional (POS-*) trades of the bull validation run `20260819_112959`
  (24 months, Nifty 500): signal date, entry close, initial stop. Re-simulated on the survivorship
  panel with v1's positional exit rules, the house constants: initial stop as recorded, T1 = 3R
  (25 % of shares), T2 = 5R (25 %), the rest trailed by the Chandelier (highest close since entry
  over 22 sessions − 4.5 × ATR22, tighten only), stop touched intraday → out at the lower of the
  open and the stop. The bear-tape +0.5 multiplier is left out. No time stop; still open at the
  panel's end → marked to the last close.
- **Overlap:** the first Wednesday-rule decision day after the entry, while v1 still holds shares,
  on which the stock is inside v2's buy cut (eligible: close > SMA100, no 15 % gap in 90 days,
  liquidity, index member; ensemble rank in the top 25 %). One event per v1 trade.
- **Unit:** the v1 shares still held at the overlap close, valued at that close (= 100 %).

## The arms (what happens to those v1 shares from the overlap on)

- **A · two slices:** v1's rules carry on, unchanged.
- **B · convert, size kept:** the v1 shares switch to v2's exits — no stop, no targets; sold at the
  open after the first decision day on which the stock is outside v2's cut (or ineligible).
- **C · convert with v2's resize:** as B, but at the next reset day the holding is cut to v2's
  target size (₹10L v2 equity × 0.10 % ÷ ATR20, at most ₹33,333); the v1 position is sized as v1
  sizes it (0.5 % of ₹30L to the initial stop, at most ₹1,00,000). The cash released earns nothing.

v2's own slice is the same in A and in B/C (v2 buys its target in A; in B/C the v2 money it does
not need here buys another name) and is left out of the comparison.

## Decision rule (one run)

Convert (B or C) is adopted only if its mean result minus A's is **≥ +1.0 %** of the position's
value, the symbol-bootstrap 95 % CI of that difference is above zero, and the difference has the
same sign in both halves (events before / after the median overlap date). Otherwise: **two slices**.
Reported alongside: median, share of events where convert was better, worst event, holding days.

Known limits: the v1 rules are a re-simulation (no catalyst-specific multipliers, no bear tape);
one panel; a v1 entry that never overlaps v2 tells us nothing and is left out.
