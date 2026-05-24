# 03 — etf_rotation.py Guide

> **Module role:** The rotation engine. Where ETFs differ most from stocks. Computes sector ranking, asset-class regime, RRG coordinates, and unified top picks per regime.
> **Phase:** Foundation (Phase 2 of the ETF system).
> **Lines:** ~680.
> **Outputs:** 4 CSVs — `ETF_Sector_Rotation.csv`, `ETF_AssetClass_Regime.csv`, `ETF_RRG_Coordinates.csv`, `ETF_Top_Picks.csv`

---

## Why this module exists

`etf_screener.py` scores each ETF on its own merits. But the **real ETF alpha is timing the rotation between exposures**: when do you tilt from IT to PSU Bank? When does Gold deserve 25% of the book vs 5%? Single-ETF screening can't answer those. The rotation engine does.

---

## User Guide

### Quick start

```bash
python etf_rotation.py
# Produces 4 CSVs in project root
```

```python
from etf_rotation import (
    sector_rotation_table, asset_class_regime,
    rrg_coordinates, top_picks_by_regime,
)

sec_df = sector_rotation_table()
regime = asset_class_regime()
rrg = rrg_coordinates(weeks=8)
picks = top_picks_by_regime(sec_df, regime, max_picks=8)
```

### Four outputs

#### 1. `ETF_Sector_Rotation.csv` — sector ranking

All 18 sector ETFs ranked by **composite RS**:

```
Composite_Score = 0.6 × rank(12W excess return) + 0.4 × rank(4W excess return)
```

The 60/40 weighting favours the established trend (12W) but lets the 4W catch the early turn — so an ETF flipping from LAGGING → IMPROVING shows up before the 12W catches up.

Quartile labels: 🟢 OVERWEIGHT / 🟡 NEUTRAL+ / 🟠 NEUTRAL− / 🔴 UNDERWEIGHT.

#### 2. `ETF_AssetClass_Regime.csv` — capital allocation regime

Compares 9 flagship ETFs across asset classes:

| Class | Flagship |
|---|---|
| EQUITY_LARGE | NIFTYBEES |
| EQUITY_MID | JUNIORBEES |
| EQUITY_SMALL | MID150BEES |
| GOLD | GOLDBEES |
| SILVER | SILVERBEES |
| INTL_NASDAQ | MON100 |
| INTL_FANG | MAFANG |
| DEBT_LIQUID | LIQUIDBEES |
| DEBT_BHARAT | BBETF |

5 regime labels:

| Regime | Trigger | Default Behaviour |
|---|---|---|
| **RISK_ON** | ≥2 equity flagships above 200DMA + outperforming gold | Heavy equity tilt |
| **GOLD_LED** | Gold flagship score > best equity flagship score | 30% gold sleeve |
| **INTL_LED** | Indian equity off, US/Intl on | Nasdaq + FANG tilt |
| **RISK_OFF** | All equities + intl off, gold not leading | Cash + bonds |
| **MIXED** | None of the above | Diversified default |

#### 3. `ETF_RRG_Coordinates.csv` — RRG plot data

Per-ETF (RS-Ratio, RS-Momentum) coordinates over the last 8 weeks. Drives the RRG quadrant plot in the Pine dashboard and Commander Web ETF page.

Each row has the quadrant label.

#### 4. `ETF_Top_Picks.csv` — actionable list

Combines #1 + #2 into a regime-aware pick list with suggested weights. **NEW (12 May 2026): correlation gate + liquidity warning columns.**

Example RISK_ON output:
```
Symbol      Weight  Reason                Source     Liquidity_Status
ITBEES       12%    Sector rotation #1    Sector     OK
PHARMABEES   12%    Sector rotation #2    Sector     OK
BANKBEES     12%    Sector rotation #3    Sector     OK
AUTOBEES     12%    Sector rotation #4    Sector     OK
METAL        12%    Sector rotation #5    Sector     OK
JUNIORBEES   15%    Mid-cap broad equity  Broad      OK
MID150BEES   15%    Mid-cap broad equity  Broad      OK
MAFANG       10%    International         Intl       OK
                                                    -----
                                          Total:    100%
```

### Allocation templates by regime

| Regime | Sector | Broad Equity | International | Commodity | Debt |
|---|--:|--:|--:|--:|--:|
| RISK_ON | 60% (5×12%) | 30% (Junior + Mid150) | 10% (MAFANG) | 0% | 0% |
| GOLD_LED | 20% (2×10%) | 0% | 10% (MAFANG) | 40% (Gold+Silver) | 30% (Liquid) |
| INTL_LED | 30% (2×15%) | 0% | 50% (FANG+Nasdaq) | 10% (Gold) | 10% (Liquid) |
| RISK_OFF | 0% | 0% | 0% | 35% (Gold+Silver) | 65% (Liquid+Bharat) |
| MIXED | 48% (4×12%) | 0% | 10% (MAFANG) | 15% (Gold) | 17% (Liquid) |

> Note: the backtest module uses **expanded templates** (12+ picks per regime) with weight renormalization. The live `top_picks_by_regime` here uses the smaller default templates that sum to ~100%.

### Correlation gate (NEW 12 May 2026)

- Default threshold: 0.75 over 60 trading days
- Drops candidate picks whose correlation with an already-accepted pick exceeds 0.75
- Preserves conviction order — first-accepted wins
- Disable via `top_picks_by_regime(..., apply_correlation_gate=False)`

Prevents: 5 highly-correlated equity sectors in a commodity-led cycle.

### Liquidity warning (NEW 12 May 2026)

New column `Liquidity_Status`:

| Status | Threshold |
|---|---|
| OK | Turnover ≥ ₹2 Cr/day |
| WATCH | ₹1-2 Cr/day |
| ILLIQUID | < ₹1 Cr/day |
| ? | Unable to verify (data fetch issue) |

### Configuration overrides

From `etf_config.json`:
- `rotation_engine.composite_long_weight` (default 0.60)
- `rotation_engine.composite_short_weight` (default 0.40)
- `correlation_gate.threshold` (default 0.75)
- `correlation_gate.lookback` (default 60)

---

## Trading Guide

### When the rotation engine fires the loudest

| Symptom | Trade implication |
|---|---|
| Regime flips **RISK_ON → GOLD_LED** | Reduce equity sector exposure aggressively; rotate to GOLDBEES |
| Regime flips **MIXED → RISK_OFF** | Sell into strength; raise cash via LIQUIDBEES |
| **Top quartile shifts dramatically week-over-week** | Major sector rotation in progress — review portfolio |
| RRG shows multiple ETFs in IMPROVING quadrant | Early rotation cycle — accumulate carefully |

### Sunday weekly playbook

1. Run `python etf_rotation.py`
2. Check **regime label first** (file: `ETF_AssetClass_Regime.csv`)
3. Read the **top picks** (`ETF_Top_Picks.csv`)
4. Compare to current portfolio:
   - Names you hold but aren't in picks → consider exit
   - Names in picks you don't hold → candidates for next entry
5. Glance at **rotation table** (`ETF_Sector_Rotation.csv`) for sector-level OW/UW tilts
6. Sync TV watchlist (use the "Copy symbols" expander in Commander Web → 🪙 ETF page)

### Regime-driven mental model

> **RISK_ON** = "be aggressive": equity sectors lead, mid/smallcap kicker, small intl hedge.
> **GOLD_LED** = "the world is uncertain": gold leadership, defensive sectors only, cash sleeve fat.
> **INTL_LED** = "Indian market is sleeping but US is awake": rotate to MAFANG/MON100.
> **RISK_OFF** = "preserve capital": gold + bonds + cash. Maximum defense.
> **MIXED** = "no clear leadership": diversified default. The system isn't sure either.

### Top picks ≠ buy list

The picks are **candidates**, not direct trade signals. Always cross-check with:
1. The ETF's individual Total_Score in `ETF_Screener_Results.csv` (need ≥20 for B grade)
2. The ETF's Signal (need BUY-LEADER or ACCUMULATE)
3. Liquidity_Status = OK
4. Pine dashboard on the actual chart for last-bar confirmation

### Common pitfalls

1. **Trusting MIXED regime picks heavily** — when the system says MIXED, *it's saying it doesn't know*. Position smaller in MIXED than in RISK_ON.
2. **Ignoring correlation gate output** — if the picks engine drops 2 of 5 sector candidates as correlated, you're seeing reality (those 2 wouldn't have diversified). Don't manually re-add them.
3. **Following the 60/40 composite blindly** — sometimes the 4-week component flips first (e.g., Jan 2024 banking rotation). The composite lags by 2-3 weeks vs pure 4W rank.
4. **Holding GOLDBEES at 30% in RISK_ON** — defensives lose money during equity bulls. Trust the regime label and tilt accordingly.

### Operational cadence

| Cadence | Action |
|---|---|
| Sunday evening | Run rotation engine. Review top picks. |
| Monday open | If regime flipped, execute rebalance trades. |
| Mid-week | No action unless dashboard alerts fire on a held ETF. |
| Friday close | Review (don't trade) — prepare for Sunday refresh. |

### Cron schedule (recommended)

```bash
# Sunday 6 PM IST = Monday 00:30 UTC
30 18 * * 0  cd /path/to/GeminiVSCode && python etf_screener.py && python etf_rotation.py
```
