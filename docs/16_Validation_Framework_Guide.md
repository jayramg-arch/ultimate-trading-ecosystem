# Validation & Backtest Framework — User & Trading Guide

> **Module Role:** The **honesty layer.** Every claim about a strategy's edge — "POS-BO works," "recovery is regime-appropriate," "SWG-PB is the wrong tool now" — is produced here. This framework replays the screeners at historical dates, grades the picks against their *matched-horizon* forward returns, and tells you whether an edge is real, in which regime, and whether it survives out-of-sample.
>
> **Files:** `validation.py` (walk-forward harness) · `replay.py` (per-anchor screen + realistic execution sim) · `walkforward_oos.py` (overfit hard gate) · `catalyst_regime_partition.py` (per-family / per-regime edge) · `data_provider.py` (date-pinnable OHLCV with hard download timeout) · `sector_rotation.py` (opt-in RRG overlay).

---

## 0. What Changed (June 2026)

- **`walkforward_oos.py` (NEW)** — the roadmap's Phase-2 **overfit hard gate**: splits anchors chronologically into in-sample / out-of-sample and checks **OOS Sharpe ≥ 60% of IS** (verdicts: PASS / STOP / NO-EDGE).
- **`catalyst_regime_partition.py` (NEW)** — splits backtest trades by **catalyst family**, **market direction** (up/down tape), and **exit reason**. This proved the pooled "NO-EDGE" verdicts were composition artifacts — per-family, most catalysts are positive.
- **`data_provider.py` hard download timeout** — `yf.download` is wrapped in a daemon thread with a `join(timeout)` (30s single / 60s batch). A stalled Yahoo Finance connection (which once froze a run for ~15 hours) now aborts and falls through to nselib/cache instead of hanging forever. Protects every run **and** the scheduled daily journal sync.

---

## 1. Core Concepts (read these first)

### Matched Alpha — the metric that matters
**Alpha = your return − the benchmark's (^CRSLDX) return over the same window.** It answers *"did this beat the market, or just ride it?"* A +8% trade in a +8% market is **0 alpha** — single-stock risk for nothing.

**"Matched"** measures each trade over **its own design horizon** (`--catalyst_windows`), not a fixed 30 days:

| Catalyst | Matched window |
|---|---|
| POS-ACCUM | 180 d |
| POS-BO / WYC-* | 120 d |
| REV-* (recovery) | 90 d |
| SWG-PB | 60 d |
| SWG-BO / GAP / REV | 30 d |

> **The cardinal rule (saved to memory):** *never judge a positional/recovery setup on a 30-day window.* Measuring a 120–180-day setup over 30 days is invalid — it produced false "remove this catalyst" calls in May 2026 that were later rolled back. Always use `--catalyst_windows`.

### Up Tape / Down Tape — the regime cut
The direction the **benchmark** moved over the trade's forward window. Splitting alpha by tape is the regime test: recovery and breakout setups are **defensive** (positive in down tapes, lag in up tapes); swing-pullback needs an up-trend. Always partition before ranking on pooled alpha.

### Win % / Profit Factor
Win % = share of profitable trades; PF = gross profit ÷ gross loss. Read alongside alpha — a low win rate with big winners (trend-following) still makes money; a high win rate with a few large losses does not.

---

## 2. `validation.py` — the walk-forward harness

Runs the screener at each of N monthly anchors and aggregates per-anchor + overall stats.

```
python validation.py --months 24 --universe nifty500 --screener bull \
                     --catalyst_windows --bootstrap_n 10000 [--top_n 10]
```

| Flag | Meaning |
|---|---|
| `--months` | number of monthly anchors |
| `--universe` | `nifty100` / `nifty500` (current constituents → mild survivorship bias) |
| `--screener` | `bull` or `recovery` |
| `--catalyst_windows` | per-catalyst matched forward windows (**use this**) |
| `--bootstrap_n` | bootstrap CI on mean anchor alpha (e.g. 10000) |
| `--top_n` | keep only the top-N by Score per anchor (mirrors the live Top-N — the *tradeable* edge) |
| `--sector_rotation` | opt-in RRG overlay (`strict`/`soft`); off by default — strict cut alpha in testing |

Outputs `validation_runs/validation_<id>_{summary,details}.csv` and updates `LAST_RUN.txt`.

> **Note on speed:** the recovery screener fetches fundamentals (RFF) at *every* anchor, so a 24-month recovery run takes ~2–3 hours. Bull runs are much faster. The download timeout (§6) prevents hangs but does not change the base cost.

---

## 3. `replay.py` — per-anchor screen + realistic execution sim

For one anchor: pins data to that date, runs the screener, then **simulates each trade bar-by-bar** with SL / T1 / T2 / Chandelier-trail and **0.10% per-leg commission+slippage**. Reports `Sharpe`, `Sortino`, `Calmar` and split exit flags:
- `Hit_Initial_SL` — a true loss (use as the failure metric).
- `Hit_Trail_SL` — often a profit-protect exit (don't read as failure).
- `Exit_Reason` ∈ {SL hit, Trail SL, Time expiry, T1/T2, no entry bar}.

`FWD_DAYS_BY_CATALYST` is the canonical matched-window map (§1).

---

## 4. `walkforward_oos.py` — the overfit hard gate

```
python walkforward_oos.py            # uses LAST_RUN
```
Splits the anchors chronologically (earlier 60% in-sample, later 40% out-of-sample), treats each anchor's alpha as a period return, and applies:

- **PASS** — OOS Sharpe ≥ 60% of IS and OOS alpha > 0.
- **STOP** — OOS degradation > 40% (overfit) → do **not** proceed to weight-fitting.
- **NO-EDGE** — IS alpha already ≤ 0 (nothing to overfit; fix the screener/window first).

> **Always read this *per catalyst family*, not pooled.** A pooled STOP/NO-EDGE is usually one weak catalyst dragging several positive ones (§5).

---

## 5. `catalyst_regime_partition.py` — where the edge actually lives

```
python catalyst_regime_partition.py  # uses LAST_RUN details
```
Partitions trades by **catalyst family**, **direction (up/down tape)**, and **exit reason**, on matched alpha. The decisive lens — it revealed:
- The bull "NO-EDGE" was a composition artifact (4 of 5 catalysts positive; one drag).
- Recovery is positive in down tapes, negative in up tapes (regime-fit).
- The recurring exit signature: most catalysts' losers are **early stop-outs**, survivors are big winners → **the stops, not the signals, are the drag.**

---

## 6. `data_provider.py` — pinnable data + hard timeout

- `set_pinned_date(as_of)` makes all fetches return data **as of** that date (no lookahead) — the backbone of honest backtests.
- On-disk cache + rate limiting + nselib (NSE-direct) fallback.
- **Hard download timeout** (`YF_DOWNLOAD_TIMEOUT_S = 30`): no fetch can hang the process; a stalled download continues via fallback/cache.

---

## 7. Recommended Workflow

1. `validation.py --months 24 --universe nifty500 --screener bull --catalyst_windows --top_n 10` (the tradeable run).
2. `catalyst_regime_partition.py` — read per-family × direction. Identify edge-carriers vs drags.
3. `walkforward_oos.py` — per-family stability check before any Phase-3 weight-fitting.
4. Never act on a pooled verdict, a non-matched window, or an in-sample-only number.
