# Validation Framework — User Guide

> **Module Role:** End-to-end backtest harness for the Bull and Recovery screeners. Generates monthly anchors, runs the screener at each one, simulates SL/T1/T2/trail exits bar-by-bar with realistic commission, computes per-trade matched-horizon alpha vs Nifty 500, and aggregates with bootstrap confidence intervals.
>
> **Files:**
> - `validation.py` — orchestrator + CLI + aggregator
> - `replay.py` — per-trade bar-by-bar simulator + per-catalyst forward windows
> - `sector_rotation.py` — Week-4 RRG-based sector rotation overlay (opt-in)
>
> **Current versions (May 2026):** `validation.py v2.8` · `replay.py v2.9` · `sector_rotation.py v1.0`

---

## 1. Why This Exists

The old workflow used a single 30-day forward window for every trade, regardless of catalyst. This produced two large measurement errors:

1. **Positional trades looked broken** — a POS-* setup designed for 4-6 month holds was measured over 30 days and almost always "stopped out" before the thesis could play out.
2. **No statistical bounds** — point-estimate alphas like "+0.3%" were treated as facts when, on 12 anchors with high variance, they were statistically indistinguishable from zero.

`validation.py` v2.8 fixes both: per-catalyst forward windows + bootstrap CI + realistic execution.

---

## 2. Quick Start

```bash
# Recommended: catalyst-aware horizons + bootstrap CI on n500/18mo
python -u validation.py --months 18 --universe nifty500 --catalyst_windows --bootstrap_n 10000

# Faster sanity check: nifty100, 6 months
python -u validation.py --months 6 --universe nifty100 --catalyst_windows --bootstrap_n 10000
```

Output:
- Console: aggregate JSON + per-anchor summary table
- `validation_runs/validation_<run_id>_summary.csv` — per-anchor rows
- `validation_runs/validation_<run_id>_details.csv` — per-trade rows with realized exits
- `validation_runs/validation_<run_id>_meta.json` — full config + aggregate

---

## 3. CLI Reference

| Flag | Default | What it does |
|---|---|---|
| `--months N` | 12 | How many monthly anchors to evaluate, counting back from today |
| `--forward D` | 30 | Forward window in trading days (used when `--catalyst_windows` is OFF) |
| `--universe NAME` | nifty100 | Universe to scan: `nifty100`, `nifty500`, `fno`, `watchlist:<name>` |
| `--symbols A,B,C` | (none) | Custom basket; overrides `--universe` |
| `--screener bull\|recovery` | bull | Which screener to validate |
| `--catalyst_windows` | OFF | **Use per-catalyst forward windows** from `replay.FWD_DAYS_BY_CATALYST`. Strongly recommended. |
| `--bootstrap_n N` | 0 | Bootstrap iterations for the alpha CI (e.g. 10000). 0 = disabled. |
| `--top_n N` | (none) | Keep only top-N picks by Score per anchor |
| `--sector_cap K` | 0 | (Opt-in) Max picks per sector when `--top_n` is set |
| `--kill_switch_dd PCT` | 0 | (Opt-in) Halt next anchor when cumulative-alpha peak-to-trough DD ≥ X% |
| `--kill_switch_losses N` | 0 | (Opt-in) Halt next anchor after N consecutive losing anchors |
| `--sector_rotation off\|strict\|soft` | off | (Opt-in) RRG-based sector filter. `strict` = LEADING only; `soft` = LEADING+IMPROVING |

**Defaults are deliberately minimal.** Overlays (`--sector_cap`, `--kill_switch_*`, `--sector_rotation`) are instrumented for experimentation but are **NOT recommended as defaults** — May 2026 testing showed they reduce alpha when applied to the current Bull screener. They remain available for future ablation studies.

---

## 4. Catalyst-Aware Forward Windows

`replay.FWD_DAYS_BY_CATALYST` is the canonical mapping. Each pick is evaluated over its own design horizon:

| Catalyst | Forward window | Rationale |
|---|---|---|
| `POS-BO` | 120 days (~6mo) | Positional breakout |
| `POS-ACCUM` | 180 days (~9mo) | Stage 1→2 accumulation base |
| `WYC-SPRING`, `WYC-SOS`, `WYC-JAC`, `WYC-SPRING+SOS` | 120 days | Wyckoff multi-month bases |
| `REV-CB`, `REV-RS`, `REV-EARLY` | 90 days | Recovery / mean-reversion |
| `SWG-BO`, `SWG-PB`, `SWG-GAP`, `SWG-REV` | 30 days | Swing — original window |

To modify, edit the dict at the top of `replay.py`.

**Side-effect:** when `--catalyst_windows` is ON, anchors near today are pushed back further so the longest window (180d for POS-ACCUM) still has forward data. Use `--months 18` or higher to retain a usable sample.

---

## 5. Realistic Execution Model

The simulator (`replay._simulate_one_trade`) walks bar-by-bar from the entry close:

1. Each bar: check intrabar SL hit → T1 → T2 (priority order; SL first, conservative).
2. On T1 hit: take 25% (POS/WYC/REV) or 33-50% (SWG) of position; move trail SL to breakeven.
3. On T2 hit: take another partial.
4. Trail SL ratchets up bar-by-bar (Chandelier-style, 4.5×ATR by default).
5. If still open at end of window: mark-to-market at final close (`Exit_Reason = "Time expiry"`).
6. Commission/slippage: 0.10% per leg (entry + each exit). For a 3-leg trade (T1 + T2 + final), that's 0.4% drag.

**Exit_Reason values:**
- `SL hit` — stopped at the INITIAL SL (true loss). Flag: `Hit_Initial_SL = True`
- `Trail SL` — stopped at a trailing SL above the initial SL (often a profit-protection exit, not a loss). Flag: `Hit_Trail_SL = True`
- `Time expiry` — held through the full window
- The legacy `Hit_SL` flag fires on BOTH initial-SL and trail-SL exits; use the split flags (`Hit_Initial_SL` / `Hit_Trail_SL`) for accurate diagnostics.

---

## 6. Matched-Horizon Alpha

When `--catalyst_windows` is ON, each trade's alpha is computed against the **benchmark return over the same horizon** as that trade:

```
trade_alpha = trade_return - bench_return(over forward_days_used for that trade)
```

This appears in the details CSV as `Alpha_Matched_pct`. The per-anchor aggregate then uses the mean of per-trade matched alphas, not a single anchor-level bench. This is the correct treatment when mixed horizons share an anchor.

---

## 7. Bootstrap Confidence Interval

When `--bootstrap_n N` is set (recommend 10000):

- Resample the anchor-level alpha series with replacement N times
- Report `alpha_ci95_low`, `alpha_ci95_high`, `alpha_bootstrap_mean`, `alpha_prob_positive_pct`

`alpha_prob_positive_pct` is the fraction of bootstrap iterations where the resampled mean alpha was > 0. This is the most useful number for judging whether an observed point estimate is meaningful:

- **> 95%**: strong evidence of positive alpha
- **70-95%**: directional evidence; not statistically confirmed
- **40-70%**: indistinguishable from zero
- **< 40%**: directional evidence of negative alpha

The current Bull screener baseline (n500/18mo, catalyst windows): `prob = ~74%` — directional but not confirmed.

---

## 8. Reading the Output

### Aggregate JSON (key fields)

```json
{
  "n_picks_total": 132,
  "anchor_avg_alpha_pct": 1.10,
  "anchor_median_alpha_pct": 0.54,
  "alpha_hit_rate_pct": 62.5,
  "anchor_avg_sharpe_ratio": -2.71,
  "final_cumulative_alpha_pct": 8.84,
  "alpha_ci95_low": -1.20,
  "alpha_ci95_high": 3.66,
  "alpha_prob_positive_pct": 80.8
}
```

### Per-anchor summary CSV columns

`as_of, picks_universe, picks_filtered, picks_with_data, win_rate_pct, avg_return_pct, alpha_pct, sharpe_ratio, sortino_ratio, calmar_ratio, halted, duration_s`

### Per-trade details CSV columns (the gold)

`Symbol, Catalyst, Catalyst_used, forward_days_used, Entry, SL_pct, T1_pct, T2_pct, Return_pct, Benchmark_Matched_pct, Alpha_Matched_pct, Exit_Reason, Days_Held, Hit_Initial_SL, Hit_Trail_SL, Hit_T1, Hit_T2, Max_Drawdown_pct, Max_Runup_pct, Cost_Drag_pct`

Filter on `Catalyst_used` for per-catalyst analysis.

---

## 9. Common Pitfalls

1. **Running without `--catalyst_windows`** — defaults to 30-day window for every trade; positional setups will appear broken. **Always use `--catalyst_windows`** unless you're explicitly studying swing-only behavior.
2. **Using `Hit_SL` as the failure metric** — this flag fires on both initial and trail exits. Use `Hit_Initial_SL` for actual losses; `Hit_Trail_SL` is often a profit-protection exit.
3. **Concluding from small samples** — 12-14 anchors is small. Always run `--bootstrap_n 10000` and read the CI before drawing strategy conclusions.
4. **Enabling overlays as defaults** — `--sector_cap`, `--kill_switch_*`, and `--sector_rotation` are opt-in experiments. They did not improve the Bull screener in May 2026 testing.
5. **Comparing runs with different `--months` or `--catalyst_windows` setting** — they're not directly comparable.

---

## 10. Diagnostic Workflow When a Number Looks Wrong

1. Read the per-trade CSV. Find the symbol that drives the surprise.
2. Check `Exit_Reason` and `Hit_Initial_SL` / `Hit_Trail_SL` for that trade.
3. Check `forward_days_used` — was the right window applied?
4. Check `Benchmark_Matched_pct` — was the right horizon used for the bench?
5. Open the chart in TradingView, mark entry/SL/T1/T2 prices, and verify visually.

If the simulator's exit doesn't match a manual chart read, suspect a bug (and report). The simulator is bar-resolution and intentionally conservative — it assumes worst-case ordering when a bar touches multiple levels.

---

## 11. Important Caveats

- **30-day vs 120-day vs 180-day anchors mix in the same run.** Cumulative-alpha numbers are sums of trades closing at different end dates. Don't interpret as an equity-curve replay.
- **The simulator is a forward-test of the picks already made**, not a strategy backtest. It tells you "given these picks, what would realistic execution have delivered." It does NOT model live order routing latency, partial fills, or slippage during gaps beyond the 0.10%/leg cost assumption.
- **Bench is Nifty 500 (`^CRSLDX`)** by default. To change, edit `BENCHMARK_YF` at the top of `replay.py`.
- **No survivorship bias correction.** The universe is the current Nifty 500 / Nifty 100 constituents — delisted names are not in the universe. For 12-18 month horizons this is a minor effect for liquid Indian large/mid-caps, but it's a real bias.

---

## 12. Memory & Lessons

The May 2026 campaign produced two permanent lessons saved to memory:

1. **Forward-window mismatch warning** — never recommend catalyst removal from a 30-day backtest. Positional/Wyckoff/recovery setups need 90-180 day windows.
2. **Bull v1.9 baseline** — the original 30-day measurement showed +0.30% alpha with Sharpe -2.23. Properly-windowed measurement shows +0.90-1.10% alpha. The screener was being mis-measured, not failing.

See `~/.claude/projects/.../memory/MEMORY.md`.

---

## 13. May 2026 Changelog

| Version | Date | Change |
|---|---|---|
| `replay.py v2.6` | 2026-05-21 | Bar-by-bar `_simulate_one_trade` + `forward_returns_with_exits` + commission/slippage (0.10%/leg) + Sharpe/Sortino/Calmar in summary |
| `replay.py v2.8` | 2026-05-21 | `FWD_DAYS_BY_CATALYST` + per-pick matched-horizon alpha (`Alpha_Matched_pct`) + per-pick `forward_days_used` |
| `replay.py v2.9` | 2026-05-21 | Split `Hit_SL` into `Hit_Initial_SL` (true loss) and `Hit_Trail_SL` (often profit-protect) |
| `validation.py v2.6` | 2026-05-21 | Wired in `forward_returns_with_exits` + Sharpe/Sortino/Calmar surfacing |
| `validation.py v2.7` | 2026-05-21 | Sector cap + equity-curve kill switch + bootstrap CI (opt-in) |
| `validation.py v2.8` | 2026-05-21 | `--catalyst_windows` flag + matched-horizon aggregation + anchor end-offset adjustment |
| `sector_rotation.py v1.0` | 2026-05-21 | RRG-based sector overlay (`strict` / `soft` / `off`) using canonical JdK 1-pass formula |
| `sectors.db` | 2026-05-21 | Backfilled 128 missing sector mappings (HYUNDAI, IREDA, NTPCGREEN, etc.); added `NSE:CNXCONSUM` and `NSE:CNXCOMMODITIES` sector_meta rows |
