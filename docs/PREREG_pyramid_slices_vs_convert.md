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

## RESULT (19 Oct 2026, run once) — CONVERT (arm C) adopted

Check before the run (whole trades, not the comparison): the re-simulated v1 exits track the
original replay closely — 190 trades, correlation 0.94, mean −2.29 % vs −1.95 %, median −5.54 %
vs −5.77 %.

130 overlap events (99 symbols; 191 v1 positional trades, 60 never overlapped v2's cut), overlap
dates 2024-07-16 .. 2026-08-11, halves split at 2025-05-20. The v1 shares from the overlap on, as
% of their value at the overlap close:

| arm | mean | median | days held |
|---|---|---|---|
| A · two slices (v1 rules carry on) | −2.47 % | −5.62 % | 37 |
| B · convert, size kept | −0.29 % | −3.15 % | 43 |
| **C · convert + v2's resize** | **−0.14 %** | **−1.43 %** | 43 |

| vs A | mean | symbol-bootstrap CI | halves | better in |
|---|---|---|---|---|
| B | +2.18 % | [−0.51, +5.23] — includes zero | +0.61 / +3.52 | 63 % |
| **C** | **+2.33 %** | **[+0.95, +3.71]** | +4.09 / +0.82 | 74 % |

C clears all three conditions; B clears the mean and both halves but its CI includes zero.
Reading: once v2 also ranks the stock, v2's exits do better than v1's stop and trail on the same
shares, and v2's resize (a v1 position is ~3× v2's target) takes most of the money off the table.
Part of C's edge is that cash: the window is mostly a falling tape, and the released cash is
counted at 0 % here — conservative for C if v1 redeploys it. Output:
`reports/pyramid_convert_result_20261019.txt`, `reports/pyramid_convert/events.csv`.

### Descriptive addendum (19 Oct, after the run) — resize on the conversion day

Not the registered arm; run to choose the live mechanics. Resizing to v2's target at the
conversion open (instead of at the next reset day) gives C − A = **+2.58 %**, CI [+1.00, +4.20],
halves +5.06 / +0.45, better in 72 % — no worse than the registered C. The live convert therefore
resizes at once: v2 takes its target-size shares at the Wednesday open (paid from v2's cash, so the
capital split stays exact) and the excess is sold the same morning; v1's trade closes there.
`python pyramid_convert_study.py --run --immediate`.
