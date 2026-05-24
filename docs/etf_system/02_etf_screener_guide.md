# 02 — etf_screener.py Guide

> **Module role:** 4-axis scoring engine. Ranks every ETF in the universe daily/weekly across Liquidity, Trend, Relative Strength, and Rotation. Produces the canonical `ETF_Screener_Results.csv`.
> **Phase:** Foundation (Phase 1 of the ETF system).
> **Lines:** ~470.
> **Output:** `ETF_Screener_Results.csv`

---

## Why this module exists

Stock screeners filter on fundamentals (RFF, EPS growth, conviction). ETFs have **no fundamentals**. So the alpha sources are different:

1. **Liquidity** — turnover, AUM proxied via price × volume, spread
2. **Trend quality** — Stage 2 + 200DMA + EMA stack
3. **Relative strength** — Mansfield RS vs Nifty 500 + 4W momentum
4. **Rotation position** — RRG quadrant (leading vs lagging the benchmark)

Each axis scored 0-10 → Total 0-40 → Grade A+/A/B/C/D.

---

## User Guide

### Quick start

```bash
# Full universe scan -> ETF_Screener_Results.csv
python etf_screener.py
```

```python
from etf_screener import rank_universe, score_etf

# Score the full universe (~56 ETFs, ~20-40 seconds)
df = rank_universe()
print(df.head(10))   # Top 10 by Total_Score

# Subset
df = rank_universe(syms=["NIFTYBEES", "BANKBEES", "GOLDBEES", "MAFANG"])
```

### CSV output columns (v1.1 schema)

| Column | What |
|---|---|
| `Symbol` | NSE ticker |
| `Name`, `Asset_Class`, `Sub_Category`, `Underlying`, `Issuer`, `Liquidity_Tier` | From `ETF_UNIVERSE` |
| `Liquidity_Score` 0-10 | Turnover-band |
| `Trend_Score` 0-10 | Stage + position vs MAs + 52WH proximity |
| `RS_Score` 0-10 | Mansfield RS + momentum + quadrant |
| `Rotation_Score` 0-10 | RRG quadrant + magnitude |
| **`Total_Score` 0-40** | Sum of the four axes |
| **`Grade`** | *** A+ (≥32) / ** A (26-31) / * B (20-25) / C (14-19) / D (<14) |
| `Stage` 0-4 | Weinstein stage (0 = insufficient data) |
| `RRG_Quadrant` | LEADING / IMPROVING / WEAKENING / LAGGING |
| `Rotation_Vector` | Direction of travel — see table below |
| `LTP`, `SMA50`, `SMA200`, `MA200_Slope_pct`, `Above_SMA200` | Price + trend metrics |
| `Mansfield_RS`, `RS_Momentum_4W` | Relative strength |
| `Vol_60D_Lakhs`, `Turnover_60D_Cr` | Liquidity metrics |
| `Dist_52WH_pct` | Distance from 52-week high (% — negative when below) |
| **`Signal`** | BUY-LEADER / ACCUMULATE / HOLD-WATCH / EARLY-BASE / AVOID-DOWNTREND / ILLIQUID / NEUTRAL |

### Rotation Vector values (12 states)

| Vector | Transition (4w prior → now) | Meaning |
|---|---|---|
| **IGNITE** | LAGGING → IMPROVING | Early turn |
| **BREAKOUT** | IMPROVING → LEADING | Full rotation in |
| **STABLE** | LEADING → LEADING | Continuation |
| **DECAY** | LEADING → WEAKENING | Loss of momentum |
| **ROLLOVER** | WEAKENING → LAGGING | Full rotation out |
| **FALLING** | LAGGING → LAGGING | Continued downtrend |
| **CHURNING** | IMPROVING → IMPROVING | Stuck building |
| **FADING** | WEAKENING → WEAKENING | Stuck topping |
| **REJECTED** | IMPROVING → WEAKENING | Failed breakout |
| **RECOVERED** | WEAKENING → IMPROVING | Bounce |
| **COLLAPSED** | LEADING → LAGGING | Rare big drop |
| **n/a** | Insufficient data | — |

### Signal precedence (CRITICAL — matches Pine dashboard)

```
1. ILLIQUID         (turnover_60d < LIQ_MIN_CR (2.0 Cr/day))
2. AVOID-DOWNTREND  (Stage 4)
3. BUY-LEADER       (Stage 2 + LEADING + liq_score >= 6)
4. ACCUMULATE       (Stage 2 + IMPROVING)
5. HOLD-WATCH       (Stage 2 + WEAKENING)
6. EARLY-BASE       (Stage 1 + IMPROVING)
7. NEUTRAL          (everything else)
```

This **order matters**. If a Stage 2 + IMPROVING ETF is illiquid, it gets `ILLIQUID` not `ACCUMULATE`. Bug fixed 12 May 2026.

### Score axes detail

#### Liquidity (0-10)

| Turnover_60D_Cr | Score |
|---|--:|
| ≥ ₹10Cr/day | 10 |
| ≥ ₹5Cr/day | 8 |
| ≥ ₹2Cr/day | 6 |
| ≥ ₹1Cr/day | 4 |
| ≥ ₹0.5Cr/day | 2 |
| else | 0 |

#### Trend (0-10, additive)

- `+5` Stage 2 — `+2` Stage 1 (partial credit for basing)
- `+2` above SMA200
- `+1` above SMA50
- `+1` SMA200 slope > 0.5%/month
- `+1` within 5% of 52W high
- Clamped at 10

#### RS (0-10, additive)

- `+3` Mansfield > 0 — `+2` > 5 — `+1` > 15 (progressive)
- `+2` Momentum_4W > 0 — `+1` > 3
- `+1` quadrant == LEADING
- Clamped at 10

#### Rotation (0-10)

- Base: `+7` LEADING — `+5` IMPROVING — `+3` WEAKENING — `+1` LAGGING
- Bonus: `+2` momentum > 5 / `+1` momentum > 0
- Bonus: `+1` Mansfield > 10
- Clamped at 10

### Configuration overrides

Read from `etf_config.json` at import:
- `benchmark_yf` (default `^CRSLDX`)
- `liq_min_cr` (default 2.0)
- `liq_bands`

If `etf_config.json` is missing, hard-coded defaults are used.

---

## Trading Guide

### Daily / weekly use

| Cadence | What |
|---|---|
| **Weekend** (Sat/Sun) | Run `python etf_screener.py`. Review top 10 by Total_Score. Identify BUY-LEADER + ACCUMULATE signals. |
| **Weekday** (intraday) | Pine dashboard mirrors the same signals in real-time. CSV gets stale during the week; Pine doesn't. |
| **Sunday before TV layout** | If a name's score crossed a threshold (e.g. moved from 24 → 32, B → A+), add to watchlist. |

### How to read the output

```
Symbol  Total  Grade  Stage  RRG       Mansfield  Signal
ITBEES   34   *** A+   2     LEADING    +18.5    🟢 BUY-LEADER
INFRABEES 28   ** A    2     IMPROVING  +6.2     🟡 ACCUMULATE
GOLDBEES  31   ** A    2     LEADING    +14.1    🟢 BUY-LEADER
NIFTYBEES 23   * B     2     WEAKENING  -1.8     🟠 HOLD-WATCH
SILVERBEES 17  C       1     IMPROVING  -8.2     🟡 EARLY-BASE
```

### Decision rules

- **A+ (≥32)** + BUY-LEADER → **High conviction buy**. Strategy fires here.
- **A (26-31)** + ACCUMULATE → Add to watchlist; wait for BUY-LEADER promotion.
- **A** + HOLD-WATCH → Stage 2 but rotation weakening. **Don't buy**; trim if held.
- **B** + EARLY-BASE → Half-size speculative entry IF strategy's `allow_early=true`.
- **C/D** or AVOID/ILLIQUID → Skip.

### Common pitfalls

1. **Chasing Mansfield > 30** — these are extended trends with mean-reversion risk. Trim, don't add.
2. **Ignoring ILLIQUID even with stage=2** — won't be able to exit cleanly. Liquidity is paramount.
3. **Buying CHURNING / FADING** rotation vectors — these say the ETF is stuck, not breaking out.
4. **Buying without checking Sub_Category for correlation** — two top-quartile ETFs in `SECTOR.PSU_BANK` and `SECTOR.BANKING` are ~85% correlated. The rotation engine's correlation gate handles this for picks; manual screener users should be aware.

### Interpreting the Grade letter

| Grade | Score | Meaning |
|---|---|---|
| *** A+ | 32-40 | All four axes strong. Top quartile of the universe. |
| ** A | 26-31 | Three strong axes, one merely OK. Solid trade. |
| * B | 20-25 | Two strong, two soft. Watchlist material; not yet a buy. |
| C | 14-19 | Mediocre across the board. Skip. |
| D | < 14 | Avoid. Probably Stage 3/4 + weak RS. |

### Cross-platform consistency (zero drift)

Per CLAUDE.md "signal consistency is sacred":
- The Pine dashboard `Commander_ETF_Dashboard_v1.2` replicates the **exact same** signal ladder and score formula
- Run `python etf_validate.py --compare <pine_export.csv>` to verify drift = 0%

### When the screener is wrong (data integrity)

If a known A-grade ETF shows up as D, suspect:
1. **Stale yfinance cache** — `data_provider` cache may be > 7 days old. Force-refresh.
2. **Inception too recent** — ETF needs ≥220 bars (~1 year). Newer ETFs return Stage=0.
3. **Benchmark missing** — if `^CRSLDX` fetch failed, all RS scores are 0.

Check the run log for warnings starting with `Benchmark missing` or `No data for`.
