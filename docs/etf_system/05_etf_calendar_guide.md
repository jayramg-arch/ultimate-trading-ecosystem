# 05 — etf_calendar.py Guide

> **Module role:** Calendar-based event overlay. Maps known events (RBI MPC, Budget, FOMC, options expiry) to sub-category impact scores. No NLP, no parsing — pure date-driven tilts.
> **Phase:** Sentiment overlay (calendar variant; NLP variant gated by Phase 5).
> **Lines:** ~330.
> **Output:** Augmented screener CSV with `Calendar_Adj` + `Calendar_Notes` columns; standalone Markdown digest.

---

## Why calendar (and NOT NLP) sentiment

Phase 5 of the 6-phase roadmap is text-sentiment promotion, gated on ≥85% parser precision (still pending). ET/MC regex over prose is too noisy for trading.

This module is different: **date-based event impact** is well documented and doesn't need NLP:

- **RBI MPC** rate decisions → debt ETFs, banking, REITs/realty
- **Union Budget** → infra, defence, PSU, consumption
- **FOMC** → USD assets, gold, intl ETFs
- **F&O Expiry** (last Thursday) → intraday volatility on financials

So this isn't sentiment in the NLP sense — it's a calendar of known impacts.

---

## User Guide

### Quick start

```bash
# Print summary for next 14 days
python etf_calendar.py --summary

# Apply overlay to existing screener CSV
python etf_calendar.py --apply ETF_Screener_Results.csv

# Specific as-of date
python etf_calendar.py --as-of 2026-06-01 --window 21
```

### Programmatic use

```python
from etf_calendar import (
    EVENTS, upcoming_events, recent_events,
    aggregate_impact, apply_calendar_score, impact_summary,
)
import datetime as dt

# What's coming up?
events = upcoming_events(window_days=14)
for e in events:
    print(f"{e.date} {e.event_type:<10} {e.label}")

# Apply to a screener output
import pandas as pd
df = pd.read_csv("ETF_Screener_Results.csv")
df = apply_calendar_score(df, as_of=dt.date.today())
print(df[df["Calendar_Adj"] != 0][["Symbol", "Calendar_Adj", "Calendar_Notes"]])

# Markdown digest
print(impact_summary(window_days=14))
```

### Event types covered

| Type | Source / Schedule | Default Impact |
|---|---|---|
| **RBI_MPC** | 6 per year (every ~2 months) | Dovish: debt + banking + REITs ↑; intl ↓. Hawkish: inverse. |
| **BUDGET** | Annual (1 Feb typically) | Infra + defence + PSU + manufacturing ↑ |
| **FOMC** | 8 per year | Hawkish: gold + intl ↓. Dovish: gold + intl ↑. |
| **OPEX** | Monthly (last Thursday) | Banking + momentum ↓ (intraday vol) |

### EVENTS list

Pre-loaded with **82 events** for 2024-2026. Update from official sources:
- RBI: https://www.rbi.org.in/Scripts/MPCalendar.aspx
- Budget: PIB or finance ministry
- FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

### Impact map structure

```python
IMPACT_RBI_MPC_DOVISH = {
    "DEBT.LIQUID":    +3,
    "DEBT.GILT_5Y":   +3,
    "SECTOR.PSU_BANK": +2,
    "SECTOR.BANKING":  +2,
    "SECTOR.REALTY":   +2,
    "COMMODITY.GOLD":  +1,
    "INTL.US_NASDAQ":  -1,
    # ...
}
```

Keys are `sub_category` strings (matching `ETF_UNIVERSE[*]['sub_category']`). Values are integers in [-3, +3] per event, aggregated across nearby events and capped at [-5, +5].

### Window logic

- **Forward window** (default 5 days): pre-positions for upcoming events
- **Backward window** (default 3 days): rides the post-event move
- The aggregate `Calendar_Adj` is shown in the screener output

### Configuration overrides

Configurable via direct module edit (no JSON config yet):
- Window sizes (`apply_calendar_score(..., forward_window=5, back_window=3)`)
- Per-event impact maps (edit `IMPACT_*` dicts at top of module)

---

## Trading Guide

### How to use the overlay tactically

The `Calendar_Adj` value is **informational**, not a direct trade signal. It tells you what events are about to hit or just hit, and which sub-categories they favour.

**Workflow:**
1. Run `python etf_calendar.py --summary` Sunday evening
2. Skim the upcoming events for the week
3. If an event has high-impact items in your candidate picks: **don't trade against the event**
4. If the post-event move is already 3 days old, the calendar effect is largely priced in — don't lean on it

### Decision rules

| Situation | Action |
|---|---|
| Budget Day is 3 days out, INFRABEES shows `+3` adj | Wait for Budget; consider entry next day |
| FOMC tomorrow is hawkish-expected, MAFANG shows `-2` adj | Don't add new MAFANG position; trim if held |
| RBI MPC dovish 2 days ago, LIQUIDBEES shows `+3` adj | Position already locked; no fresh trade |
| F&O OPEX day, BANKBEES shows `-1` adj | Avoid intraday entries into banking ETFs |

### What the calendar **won't** do for you

- It won't predict the **outcome** of an event (rate hike vs cut). It uses default assumptions per event slot.
- It won't override Stage / RS / Liquidity gates. A Stage 4 ETF with positive calendar adj is still SELL.
- It won't replace a Sunday news read. Macro context > calendar shorthand.

### Updating impact maps

When an event happens with a different outcome than the default assumed:
1. Edit the `EVENTS` list — change the impact map reference for that specific event
2. Example: if Feb 2025 RBI MPC was hawkish (not dovish as assumed), change:
   ```python
   Event(dt.date(2025, 2, 7), "RBI_MPC", "RBI MPC Feb 2025", IMPACT_RBI_MPC_DOVISH, ...)
   # to:
   Event(dt.date(2025, 2, 7), "RBI_MPC", "RBI MPC Feb 2025", IMPACT_RBI_MPC_HAWKISH, "Surprise hawkish hold")
   ```
3. Re-run any backtest that depends on the calendar overlay.

### Integration with backtest

**Currently NOT integrated** with `etf_backtest.py`. The calendar overlay is a live-trading aid, not a backtest input. Future work could:
1. Apply `Calendar_Adj` as a tiebreak in `build_picks_at()` for highly-tied composite scores
2. Block entries on hawkish FOMC + intl ETF combinations during the forward window
3. Compute event-conditional alpha (does the system beat benchmark MORE on dovish RBI days?)

### Calendar discipline (operational)

| When | What |
|---|---|
| Sunday | Read `--summary` for the week ahead |
| Morning of an event | Review held positions in affected sub-categories |
| 1 day after | Verify the impact assumption vs actual move; update if needed |
| Quarterly | Refresh `EVENTS` list with confirmed dates (replace estimates) |
| Annually | Rebuild calendar for next year |

### Limits & honest caveats

1. **Default impacts are educated guesses**, not back-tested edges. Conservative trade sizing recommended.
2. **The list is incomplete** — covers RBI / Budget / FOMC / OPEX but not GST council, IIP, CPI, Q-results season, etc.
3. **F&O expiry** impact is intraday — daily-bar systems may not capture the intraday vol hit.
4. **Forward dates are estimates** — official calendars confirm only 1-2 quarters ahead.
