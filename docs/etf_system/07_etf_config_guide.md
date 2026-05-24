# 07 — etf_config.json Guide

> **Module role:** Single source of truth for ETF system thresholds. Loaded automatically by `etf_screener.py` and `etf_rotation.py` at import. Pine modules reference these values via input defaults.
> **Lines:** 52.
> **Updated:** 12 May 2026.

---

## Why this exists

Before the 12 May 2026 audit, thresholds were duplicated across Python and Pine. That led to:

- `LIQ_MIN_CR` mismatch (₹0.5Cr in Python vs ₹2.0Cr in Pine)
- RS benchmark per-ETF substitution in Python (vs locked Nifty 500 in Pine)
- Hard-coded composite weights in two files

This JSON is the **single config**. Edit here once; both Python modules pick it up. Pine modules need a manual input-default update — flag in the changelog.

---

## User Guide

### File structure

```json
{
  "version": "1.1",
  "updated": "2026-05-12",

  "benchmark_yf": "^CRSLDX",
  "liq_min_cr": 2.0,
  "liq_bands": [
    { "threshold": 10.0, "score": 10 },
    { "threshold":  5.0, "score":  8 },
    { "threshold":  2.0, "score":  6 },
    { "threshold":  1.0, "score":  4 },
    { "threshold":  0.5, "score":  2 },
    { "threshold":  0.0, "score":  0 }
  ],

  "stage2_slope_min_pct": 0.1,
  "mansfield_sma_len": 200,
  "rs_momentum_lookback_bars": 20,

  "buy_leader_min_liq_score": 6,

  "vol_profiles": {
    "low_gold_debt":     { "atr_stop_mult": 1.8, "target_atr_pct": 1.0 },
    "med_broad_equity":  { "atr_stop_mult": 2.5, "target_atr_pct": 1.5 },
    "high_sector_small": { "atr_stop_mult": 3.0, "target_atr_pct": 2.0 },
    "intl_nasdaq_fang":  { "atr_stop_mult": 2.5, "target_atr_pct": 1.8 }
  },

  "correlation_gate": {
    "enabled":   true,
    "threshold": 0.75,
    "lookback":  60
  },

  "rotation_engine": {
    "composite_long_weight":  0.60,
    "composite_short_weight": 0.40
  },

  "backtest_defaults": {
    "freq":           "monthly",
    "top_n":          8,
    "min_hold_days":  28
  },

  "min_hold_days": 28
}
```

### Which modules read which keys

| Key | Read by | Effect |
|---|---|---|
| `benchmark_yf` | `etf_screener.py`, `etf_rotation.py` | RS calculation denominator |
| `liq_min_cr` | `etf_screener.py` | ILLIQUID threshold |
| `liq_bands` | `etf_screener.py` | Liquidity_Score mapping |
| `stage2_slope_min_pct` | Documented only | Pine strategy input default |
| `mansfield_sma_len` | Documented only | Pine input default |
| `rs_momentum_lookback_bars` | Documented only | Pine input default |
| `buy_leader_min_liq_score` | Documented only | Pine strategy input default |
| `vol_profiles` | Documented only | Pine strategy Vol Profile presets |
| `correlation_gate.*` | `etf_rotation.py` | Top-picks correlation filter |
| `rotation_engine.composite_*` | `etf_rotation.py` | Sector rotation weights |
| `backtest_defaults.*` | `etf_backtest.py` | CLI defaults |
| `min_hold_days` | `etf_backtest.py` | Min-hold for Portfolio.rebalance_to |

### How Python loads it

```python
# At etf_screener.py import time
try:
    import json
    _cfg_path = os.path.join(_DIR, "etf_config.json")
    if os.path.exists(_cfg_path):
        with open(_cfg_path) as _f:
            _CFG = _json.load(_f)
        BENCHMARK_YF = _CFG.get("benchmark_yf", BENCHMARK_YF)
        LIQ_MIN_CR   = _CFG.get("liq_min_cr",   LIQ_MIN_CR)
        # ...
except Exception:
    pass   # fall back to hard-coded defaults
```

The pattern is **safe failure** — if JSON missing or malformed, hard-coded defaults are used.

### How Pine "loads" it (manual)

Pine can't read JSON files. The config values must be set as Pine input defaults manually. When you edit a value here:

1. **Update the JSON** (single source of truth)
2. **Search Pine files** for the matching default: `grep -n "liq_min_cr\|mans_len\|atr_stop_mult" *.pine`
3. **Update the Pine `input.float(...)` / `input.int(...)` defaults**
4. **Add a comment** referencing the JSON: `// matches etf_config.json["liq_min_cr"]`
5. **Run `python etf_validate.py`** to confirm Python matches

---

## Trading Guide

### Common edits

| Edit | Why | Impact |
|---|---|---|
| Raise `liq_min_cr` to 3.0 | Tighten the universe to A-tier only | Fewer signals, less slippage in live |
| Lower `buy_leader_min_liq_score` to 4 | Looser BUY-LEADER trigger | More signals, includes B-tier names |
| `correlation_gate.threshold` 0.65 | Tighter correlation filter | Fewer picks accepted; more diversified |
| `composite_long_weight` 0.7 | Weight 12W more heavily | Less responsive to short-term flips |
| `min_hold_days` 56 | Double the min-hold | Even fewer trades; longer trend rides |

### Edits that require re-running the universe

| Edit | Re-run |
|---|---|
| `liq_min_cr`, `liq_bands` | `python etf_screener.py` (recompute signals) |
| `benchmark_yf` | `python etf_screener.py && python etf_rotation.py` |
| `composite_long_weight` | `python etf_rotation.py` |
| `correlation_gate.threshold` | `python etf_rotation.py` (or backtest) |

### Edits that ALSO require Pine sync

Any threshold mirrored in Pine. Run `python etf_validate.py --compare pine_export.csv` after editing.

### Don't edit without backtest verification

For thresholds that materially affect trade frequency or selection:

```bash
# 1. Edit etf_config.json
# 2. Run backtest baseline
python etf_backtest.py --walk-forward
# 3. Compare to last known good run in backtest_runs/
# 4. If metrics regress > 1% CAGR or > 0.1 Sharpe -> revert
```

### Version field

The `version` and `updated` fields are documentation only. Convention:
- **Patch** (1.1.x): threshold tweaks
- **Minor** (1.x): new gates / new keys
- **Major** (x.0): breaking schema changes (rare)

### Backup before major edits

```bash
cp etf_config.json etf_config.json.bak.$(date +%Y%m%d)
```

The git history is your real backup — commit before edits.

### What NOT to put here

- ❌ Per-ETF overrides — that belongs in `etf_universe.py`
- ❌ Calendar events — those belong in `etf_calendar.py`
- ❌ Universe symbols — `etf_universe.py`
- ❌ Pine syntax — Pine is its own file
- ❌ Sensitive credentials — use env vars
