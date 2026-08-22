# 27 — The Backtest Process, and a Glossary

*Written 21-Aug-2026. Describes the harness as it actually is in the code, not as
the notes remember it. Every number quoted here came out of a real run.*

This document exists because the backtest is the **only clean evidence about the
system that exists**. The trade journal cannot serve that purpose: it mixes
system-entered trades with discretionary and tax-loss-harvested ones and the two
cannot be separated retroactively. So when a decision has to be made about whether
something works, this harness is the court — and it is worth knowing exactly how it
reaches a verdict, and where it has misled us before.

---

## 1. What a backtest here can and cannot tell you

**It can** answer: *does this selection rule pick names that beat the index over the
horizon the setup was designed for?*

**It cannot** answer:
- Whether *you* will execute it. Every trade here fills mechanically.
- Anything intraday. The replay runs on **daily bars** (`interval="1d"`). `GO_Date`
  carries no time of day, so no study of "is a 10:30 trigger worse than 11:45" is
  possible from this data, however much we would like one.
- Whether a discretionary chart read adds value. It measures the mechanical rule.

**And it carries known biases, disclosed in the code:**
- **Survivorship.** The universe is today's Nifty 500. Names that were delisted or
  fell out never appear. `validation.py:92-96` labels its alpha an *upper bound* for
  this reason.
- **Corporate actions.** `auto_adjust=True` with row-only pin slicing means a split
  or bonus is retro-applied to history.

---

## 2. The four modules, and what each is for

| Module | Job | Run it when |
|---|---|---|
| `validation.py` | The **harness**. Walks anchors month by month, screens at each, hands picks to replay, aggregates. | Re-baselining after any signal change |
| `replay.py` | The **execution simulator**. Bar-by-bar SL / T1 / T2 / trail with costs. | Never directly — validation calls it |
| `walkforward_oos.py` | The **overfit gate**. Splits anchors chronologically, compares in-sample to out-of-sample. | After every re-baseline, before believing it |
| `catalyst_regime_partition.py` | The **lens**. Breaks results down by family, direction, exit reason. | Always. The pooled number lies (see §6) |

### The flow

```
anchor date  →  screener runs AS OF that date (point-in-time pinned)
             →  picks
             →  replay simulates each pick forward, bar by bar
             →  per-trade matched alpha
             →  aggregate per anchor  →  summary.csv
             →  walkforward_oos.py     →  PASS / STOP / NO-EDGE
             →  catalyst_regime_partition.py  →  where the edge actually lives
```

---

## 3. Running one

The canonical bull re-baseline:

```bash
python -u validation.py --months 24 --universe nifty500 --catalyst_windows --bootstrap_n 10000
```

Recovery is the same with `--screener recovery`. **It takes hours** (per-anchor
fundamental fetches), so run it detached and read the log later.

Key flags:

| Flag | Default | What it does |
|---|---|---|
| `--months` | 12 | How far back to walk. 24 is the standard baseline. |
| `--universe` | nifty100 | `nifty500` for a real run. |
| `--screener` | bull | `bull` or `recovery`. |
| `--catalyst_windows` | off | **Turn this on.** Each catalyst gets its design horizon instead of a flat 30 days. |
| `--bootstrap_n` | 0 | 10000 gives you a confidence interval. Without it you have a point estimate and no idea if it is noise. |
| `--gate` | catalyst | `s4go` instead simulates entering only on an S4 GO. |
| `--forward` | 30 | Only used when `--catalyst_windows` is off. |

### The one check to run before reading any result

```bash
python -c "import pandas as pd; d=pd.read_csv('validation_runs/<run>_details.csv'); print(d['forward_days_used'].value_counts())"
```

If you asked for `--catalyst_windows` you must see **60 / 90 / 120 / 180** in there.
Seeing only `30` means the windows silently did not apply and the run is invalid. This
is not hypothetical: an 11.6-hour recovery run was thrown away because recovery emits
its label in a column called `Signal_Label` while replay was reading `Catalyst`, so
every pick fell through to the 30-day default *with the flag on*.

---

## 4. How the simulator actually trades

`replay.py`, bar by bar on daily data:

- **Entry** — default `entry_mode="retest"`: a buy-limit at the trigger bar's close,
  filled on the first pullback within the retest window. This is the default because
  it was measured against the alternative: buy-stop **−0.02%** mean matched alpha vs
  retest **+0.38%**, better in *every* family, and filling 320 names against 268.
- **Costs** — `COST_PER_LEG_DEFAULT = 0.10` (%). STT + brokerage + slippage.
- **Stop** — catalyst-aware. Positional 4×ATR, swing tighter. `STRUCTURAL_SL = False`:
  the structural variant had the best mean and passed the OOS gate and was **still
  rejected**, because the median went −0.48R → −1.01R and stop-outs 11.8% → 52.7%.
- **Targets** — R-canon: positional 3R/5R, swing 2R/4R, nothing under 2R. Partials
  25/25 for positional, so half the position rides the trail uncapped.
- **Exit** — initial SL, trail SL, target, or time expiry at the horizon.

### The design horizons (`FWD_DAYS_BY_CATALYST`)

| Family | Days | Why |
|---|---:|---|
| POS-ACCUM | 180 | Stage 1→2 accumulation takes months |
| POS-BO, WYC-* | 120 | 4–6 month positional evaluation |
| REV-* | 90 | Recovery needs a quarter to play out |
| SWG-PB | 60 | The pullback must complete *before* the swing runs |
| SWG-BO | 30 | Matches the design |

---

## 5. The gates a result must clear

A number does not change anything until it survives all of these. They exist because
each one has caught a wrong conclusion of ours at least once.

1. **Plateau.** The neighbouring parameter cells must also beat control. A lone
   winning cell is noise.
2. **Interior.** If the best cell is at the edge of the grid, the grid is
   mis-specified — the search just ran to the boundary. An edge winner **fails**.
3. **OOS retention.** Out-of-sample must keep **≥50%** of the in-sample margin. One
   study retained +0.19pp of a +5.84pp margin — a 97% collapse — and still passed a
   naive "is it positive" test.
4. **Bootstrap stability.** The winner or a neighbour must win in ≥25% of 500
   resamples, and the 5th percentile of (best − control) must exceed zero.
5. **Median.** Not worse by more than 0.25R. A better mean with a much worse median
   means you converted quick small losses into slow large ones.
6. **The overfit gate** (`walkforward_oos.py`): `PASS` requires IS alpha > 0, OOS
   alpha > 0, and OOS Sharpe ≥ **60%** of IS. `NO-EDGE` means IS alpha was already
   ≤ 0 — there is nothing to overfit and the problem is the signal, not the fit.

**Measure stops and sizing in R, never in per-trade %.** Position size is
`risk / (k × ATR)`, so a percentage metric structurally rewards a wider stop for
exposure it never paid for. Re-running one stop study in R **inverted** a conclusion
that had already been reported.

---

## 6. Read it per family. Always.

Pooling has produced a false conclusion **three separate times**:

- June 2026: a pooled "NO-EDGE" verdict. Per family, POS-BO was +7.67% with PF 3.14 —
  17 positional winners were being drowned by 115 bleeding swing trades.
- "The swing book has no OOS edge." Wrong: SWG-PB was **+0.42% IS / +0.52% OOS**, the
  most stable catalyst in the book. It had been pooled with SWG-REV, the actual drag.
- A pooled stop-out rate that hid the fact that SWG-PB stops out *more often* than
  SWG-REV and is profitable anyway.

So: **split by catalyst family before concluding anything.** And when a family has
n < 30, say so and do not act on it.

### A live warning about the direction split

"UP tape / DOWN tape" is currently derived from the sign of the benchmark over the
matched window — and after the horizon fix that window's *length* is `days_held`, an
**outcome**. Fast stop-outs self-select into DOWN, long runners into UP. The old
"breakouts behave defensively in down tapes" claim was an artifact of this and is
retired. Do not replace it with a smaller version of the same claim. Fix the label
first: derive direction from an **ex-ante** window before quoting any per-direction
result.

---

## 7. The four mistakes that have cost us the most

1. **Window mismatch.** Judging a 180-day accumulation setup on a 30-day forward
   window. This produced recommendations to *delete* catalysts that were fine; all
   were rolled back. Never assess a positional or recovery setup on a short window.
2. **Full-window benchmark against an early-exiting trade.** The stock leg exited at
   ~30 days while the benchmark leg ran the full 120–180. 92% of trades were affected.
   Headline alpha fell +2.56% → +0.80% and the median went negative when fixed. **If
   a trade can exit early, the benchmark must exit with it.**
3. **Endogenous labelling.** Detecting a "confirmation" inside a window that overlaps
   the outcome window measures "it rallied, so it both confirmed and returned". An
   apparent +6.54pp out-of-sample edge evaporated under a clean disjoint-window
   harness.
4. **Pooling** — §6.

---

## 8. What the harness currently says

On the corrected conventions, bull, 24 months, Nifty 500, catalyst-aware:

- Mean matched alpha around **+0.5% to +1.0% per trade**.
- The **median trade loses to the index**. This is a low-hit-rate, big-winner-carried
  trend profile — roughly a third of trades win, and 8.4% ever reach 3R.
- Bootstrap probability that true alpha is positive: hovering near **50%**, with a
  confidence interval that straddles zero.
- **40% of trades die at the initial stop within about 7 days**, at a 5.9% win rate.
- The trail owns **88%** of positional exits.

Read honestly: the correctness fixes made the measurement trustworthy; they did not
create an edge. **Plan around +1%, not +5%.** And note the standing recommendation:
30 positional trades logged through guided execution would tell us more than another
backtest, because it is the one thing the harness structurally cannot measure.

---

## 9. Glossary

**Alpha (matched)** — the trade's return minus the benchmark's return **over the same
holding period**. "Matched" is the important word; see the horizon mistake in §7.

**Anchor** — a historical date the screener is run as of. Anchors are spaced roughly
a month apart.

**ATR** — Average True Range, the volatility unit. Stops and extension are quoted in
multiples of it so they mean the same thing across names.

**Bootstrap** — resampling the results thousands of times to see how much the answer
moves. Produces the confidence interval and P(α>0). **Resample by symbol, not by
row**: with a 20-day window on daily bars, consecutive rows share ~95% of their
outcome window, so row-level resampling wildly overstates the sample size.

**Catalyst / family** — the setup label a pick fired on (POS-BO, POS-ACCUM, SWG-PB,
SWG-BO, SWG-REV, REV-*, WYC-*). "Family" is the prefix: POS, SWG, REV, WYC.

**Chandelier** — a trailing stop hung from the highest close over a lookback window,
minus a multiple of ATR. Catalyst-aware: positional 4.5×, swing 1.5×. Tighten-only.

**Confidence interval (CI95)** — the range the true value plausibly sits in. **If it
straddles zero, you do not have a demonstrated edge**, whatever the point estimate.

**Embargo** — a gap inserted between the in-sample and out-of-sample windows so
overlapping trade horizons cannot leak across the split.

**Expectancy** — average outcome per trade. Mean R is the honest version.

**Forward window** — how long a pick is tracked. Should equal the setup's *design*
horizon, hence `--catalyst_windows`.

**IS / OOS** — in-sample (the earlier chronological share, default 60%) and
out-of-sample (the later 40%). Splitting by *time*, never randomly.

**Matched horizon** — see Alpha. The benchmark leg must run exactly as long as the
trade did.

**NO-EDGE** — the gate's verdict when in-sample alpha is already ≤ 0. Not an overfit
diagnosis: there was nothing to overfit. Fix the signal.

**PASS / STOP** — gate verdicts. PASS needs positive alpha in both windows and OOS
Sharpe ≥ 60% of IS. STOP means the edge degraded more than 40% or flipped negative.

**PF (profit factor)** — gross wins ÷ gross losses. Above 1 makes money; below 1
does not.

**Point-in-time** — the discipline of computing every input using only data that
existed at the anchor date. Enforced by pinning in `data_provider`, with runtime
assertions. Violating it is look-ahead bias and invalidates everything.

**R / R-multiple** — profit or loss expressed in units of the risk originally taken.
A trade risking ₹1,000 that makes ₹2,000 is +2R. **The correct unit for any stop or
sizing study**, because percentage returns silently reward wide stops.

**Retest entry** — buying the pullback to the trigger bar's close rather than chasing
a buy-stop above its high. The measured default.

**Sharpe / Sortino / Calmar** — risk-adjusted return measures. Sortino penalises only
downside volatility; Calmar divides return by max drawdown.

**Slippage / cost per leg** — 0.10% charged on each entry and exit.

**Stop-out** — an exit at the *initial* stop, distinct from a trail-SL exit. The
distinction matters: a trail exit is often a profit-protect, and conflating them once
produced a false panic about the stop being too tight.

**Survivorship bias** — the universe contains only names that still exist today, so
past failures are invisible and results are an upper bound.

**Time expiry** — the trade ran to the end of its forward window without hitting a
stop or target. Historically the most profitable exit bucket, which is a comment on
the stops, not a strategy.

**Trail SL** — the moving stop. Owns 88% of positional exits and is the least-tested
lever in the system.

**Walk-forward** — re-running the screen at successive historical anchors rather than
fitting once over the whole period.

---

## 10. Related documents

- `docs/25_Golden_Rules.md` — the DO/DON'T doctrine for shortlisting
- `docs/26_GM_S4_Workflow.md` — the daily operating loop
- `docs/16_Validation_Framework_Guide.md` — the fuller technical reference for the
  harness modules
