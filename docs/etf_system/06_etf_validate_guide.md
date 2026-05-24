# 06 — etf_validate.py Guide

> **Module role:** Cross-validation harness. Verifies Python signals match Pine signals. Catches drift bugs automatically. Per CLAUDE.md "signal consistency is sacred".
> **Phase:** Quality assurance.
> **Lines:** ~280.
> **Outputs:** `ETF_Validate_Reference.csv`, `logs/etf_validation_<date>.md`

---

## Why this module exists

The ETF system has three independent signal-generation surfaces:
1. **Python** (`etf_screener.py`) — CLI / Commander Web
2. **Pine Dashboard** (`Commander_ETF_Dashboard_v1.2`)
3. **Pine Strategy** (`Commander_ETF_Strategy_v1.1`)

Per CLAUDE.md "signal consistency is sacred". This module:

a. Recomputes all signal components in Python from the universe
b. Exports a reference CSV that matches Pine's data window pin values
c. Runs **internal consistency checks** (precedence, thresholds, universe integrity)
d. **Cross-compares** Python vs Pine via a pasted Pine export

---

## User Guide

### Quick start

```bash
# Internal consistency check (no TradingView needed)
python etf_validate.py
```

Outputs:
- `ETF_Validate_Reference.csv` — the per-ETF "what Pine should match"
- `logs/etf_validation_<timestamp>.md` — issue list

### Three check types

#### 1. Signal Precedence

Verifies Python's signal ladder matches Pine's:

```
ILLIQUID > AVOID-DOWNTREND > BUY-LEADER > ACCUMULATE >
HOLD-WATCH > EARLY-BASE > NEUTRAL
```

Flags any ETF where the signal violates precedence (e.g., illiquid Stage 2 ETF labeled `ACCUMULATE` instead of `ILLIQUID`).

#### 2. Threshold Consistency

Verifies Python constants match `etf_config.json`:
- `LIQ_MIN_CR` matches config
- `BENCHMARK_YF` matches config

#### 3. Universe Integrity

Verifies every `ETF_UNIVERSE` entry is well-formed:
- All required fields present
- `asset_class` ∈ valid set
- `liquidity_tier` ∈ {A, B, C}

#### 4. Pine Drift (optional — requires --compare)

Compares per-ETF Pine values vs Python reference within a tolerance (default 1%).

### CLI arguments

| Flag | Default | Purpose |
|---|---|---|
| `--etfs SYMS` | full universe | Comma-separated subset to validate |
| `--compare PATH` | — | Path to Pine-exported CSV for drift check |
| `--strict` | off | Exit 1 if any issue found (CI-friendly) |
| `--tolerance` | 1.0 | Drift tolerance in percent |

### Full Pine vs Python comparison workflow

```bash
# Step 1. Generate Python reference
python etf_validate.py
# -> ETF_Validate_Reference.csv

# Step 2. In TradingView:
#   - Load Commander ETF Dashboard v1.2 on each test ETF
#   - Right-click chart -> Copy Data Window
#   - Paste each into a CSV with a Symbol column

# Step 3. Compare
python etf_validate.py --compare pine_export.csv --tolerance 1.0
```

### Programmatic use

```python
from etf_validate import (
    build_reference, check_signal_precedence,
    check_threshold_consistency, check_universe_integrity,
)

ref = build_reference()
precedence_issues = check_signal_precedence(ref)
threshold_issues  = check_threshold_consistency()
universe_issues   = check_universe_integrity()
```

### Output report structure

`logs/etf_validation_YYYYMMDD_HHMMSS.md`:

```
# ETF Validation Report

Generated: 2026-05-12T22:33:00
ETFs checked: 56
Total issues: 0

## Signal Precedence (0 issues)
_None._

## Thresholds (0 issues)
_None._

## Universe Integrity (0 issues)
_None._

## Pine Drift (0 issues)
_None._
```

If issues exist, each has fields: `rule`, `symbol` (if applicable), `expected`, `actual`, `context`.

### CI integration

```bash
# In a Sunday cron job
python etf_validate.py --strict
echo $?
# 0 = clean, 1 = issues, 2 = data fetch failure
```

If non-zero, alert / hold downstream pipeline (don't trade off signals that just changed).

---

## Trading Guide

### Why this matters for trading

The audit on 12 May 2026 found 7 bugs, 3 of which were signal-drift between Python and Pine:

1. **ILLIQUID precedence inverted in Python** — Stage 2 + IMPROVING + illiquid was labeled `ACCUMULATE` in Python but `ILLIQUID` in Pine. **Same ETF, opposite trade decision.**
2. **ILLIQUID threshold mismatch** — Python used ₹0.5Cr/day, Pine used ₹2Cr/day. **Different illiquid universe.**
3. **Mansfield RS benchmark substitution** — Python used per-ETF underlying benchmark; Pine used Nifty 500 universally. **Different RS values for the same ETF.**

Without this harness, you'd discover those bugs only by trading off contradictory signals. **The harness catches them automatically.**

### Operational use

| When | Why |
|---|---|
| **After any threshold change** in `etf_config.json` | Verify Pine still matches |
| **After any signal-ladder edit** in `etf_screener.py` | Verify precedence holds |
| **Before deploying a new Pine version** | Compare data window vs Python |
| **Sunday** as part of cron | Catch silent drift |

### What the harness catches vs misses

**Catches:**
- Signal precedence violations
- Threshold inconsistencies  
- Universe entries with malformed metadata
- Per-ETF numeric drift > tolerance (with `--compare`)

**Misses:**
- Pine bugs that affect plot rendering but not data window values
- Bugs that only manifest intrabar (the harness checks bar-close values)
- Calendar overlay drift (calendar is Python-only; no Pine equivalent yet)

### Reading drift issues

If `Pine Drift` section has entries like:
```
- drift_Mansfield_RS -- `BANKBEES` -- expected `12.34`, got `8.91`. drift `27.66%`
```

Then BANKBEES Mansfield value differs by 27.66% between Pine and Python. Likely causes:
1. Pine using different benchmark (check Pine `bench_sym` input)
2. Pine using different SMA length (check `mans_len` input)
3. Pine's `request.security` returning lookahead-biased data

### When to ignore (rare)

- If `drift_pct ~ 0.5%`, this is likely Pine's bar-close vs Python's last-data-row off-by-one (TradingView's bar-close for the day isn't always identical to yfinance's "today" row when running mid-day). Tolerable for most workflows.
- If only **one** ETF drifts and the rest are clean, investigate that one ETF's data — could be a corporate action.

### When to STOP and fix immediately

- Multiple ETFs drift the same column by similar magnitudes → systemic calculation difference. Fix Pine OR Python.
- Signal column drifts (Python says BUY-LEADER, Pine says ACCUMULATE) → precedence or threshold bug. **Do not trade until resolved.**
- New universe entry fails integrity → fix `etf_universe.py` before next screener run.

### Files saved per run

```
ETF_Validate_Reference.csv     (overwritten each run)
logs/etf_validation_<ts>.md    (preserved per run — audit trail)
```

The Markdown reports are your audit trail. Don't delete — review the historical sequence to spot recurring issues.
