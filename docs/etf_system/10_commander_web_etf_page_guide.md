# 10 — Commander Web ETF Page Guide

> **Module role:** Streamlit UI surfacing all ETF system outputs in one tab. Consumes the 5 CSVs produced by `etf_screener.py` and `etf_rotation.py`. Adds Run-All button + file-status strip + 4 functional tabs.
> **Phase:** Phase 4 of the ETF system.
> **Location:** Inside `weinstein_commander_web_v4.0.py`, page identifier `'ETF'`.
> **Lines:** ~380 (within the larger 7000+ line web app).

---

## What it shows

A single 🪙 ETF page under the DISCOVERY nav group with:

- **File-status strip** — 5 colour-coded chips showing freshness of each CSV
- **🔄 Run All** button — runs the Python screener + rotation in one click (~30-60s)
- **4 tabs**: Top Picks / Sector Rotation / Asset-Class Regime / Liquidity & Universe

No real-time price feeds — it reads CSVs that the screener/rotation engine produced. Treat it as a **review and review-confirm UI**, not a live tape.

---

## User Guide

### Launching

```bash
streamlit run weinstein_commander_web_v4.0.py
```

Browser opens → click 🪙 **ETF** in the sidebar (under DISCOVERY group).

### File status strip — colour meaning

| Icon | Age | Meaning |
|---|---|---|
| 🟢 | < 24h | Fresh |
| 🟡 | 24-72h | Stale but usable |
| 🔴 | > 72h or missing | Re-run before trusting |

Shows for each of the 5 CSVs: row count + last-modified timestamp.

### 🔄 Run All button

Single click runs:
1. `etf_screener.rank_universe()` → writes `ETF_Screener_Results.csv`
2. `etf_rotation.sector_rotation_table()` → `ETF_Sector_Rotation.csv`
3. `etf_rotation.asset_class_regime()` → `ETF_AssetClass_Regime.csv`
4. `etf_rotation.rrg_coordinates()` → `ETF_RRG_Coordinates.csv`
5. `etf_rotation.top_picks_by_regime()` → `ETF_Top_Picks.csv`

Spinner shows during the run; takes 30-60s typically.

### Tab 1 — 🎯 Top Picks

- **Active Regime card** at top (RISK_ON green / GOLD_LED blue / RISK_OFF red / MIXED amber / INTL_LED amber)
- **Picks table** merged with screener data: Symbol, Suggested_Weight_pct, Reason, Source, LTP, Stage, RRG_Quadrant, Total_Score, Signal, Liquidity_Status
- **📋 Copy symbols** expander with `NSE:NIFTYBEES,NSE:BANKBEES,…` ready to paste into TradingView watchlist

### Tab 2 — 🔄 Sector Rotation

- 4 metrics row: count of OVERWEIGHT / NEUTRAL+ / NEUTRAL− / UNDERWEIGHT sectors
- Full ranked table with 4W + 12W excess returns + composite score (signed % formatting)
- **Methodology expander**: 60/40 composite explanation

### Tab 3 — 📊 Asset-Class Regime

- Large **Regime card** with detection timestamp
- **Risk-On Asset Classes** count metric
- **Donut chart** of suggested allocation across asset classes (Plotly, dark theme)
- Detail table sorted by score
- **Regime rules expander** with trigger table

### Tab 4 — 💧 Liquidity & Universe

3 filter row:
- Asset Class (dropdown)
- Liquidity Tier (A only / A+B / A+B+C)
- Grade (multi-select)

4 metrics row:
- Universe size
- Stage 2 count
- LEADING count
- Liquid (≥₹2Cr/d) count

Full sortable table with all 4-axis scores + Stage + RRG + LTP + Mansfield + Turnover + 52WH distance + Signal. Height 560px.

---

## Trading Guide

### Weekly workflow on the ETF page

#### Sunday evening (review + plan)

1. Open Commander Web → 🪙 ETF
2. Click 🔄 **Run All** (wait 30-60s)
3. **Tab 3 — Regime**: confirm regime label. This is your weekly "thesis."
4. **Tab 1 — Top Picks**: review the regime-aware list.
   - Names you already hold + in picks → keep
   - Names you hold NOT in picks → exit candidate
   - Names in picks NOT held → entry candidates
5. **Tab 2 — Sector Rotation**: glance at OVERWEIGHT vs UNDERWEIGHT sectors
6. **Tab 4 — Liquidity & Universe**: filter to Grade A+/A, Tier A+B → confirm the highest-conviction names

#### Monday morning (execute)

1. Pull up each entry candidate in TradingView
2. **Verify on the Dashboard panel** (Pine):
   - SIGNAL = BUY-LEADER or ACCUMULATE
   - Total Score ≥ 26
   - Liquidity = OK
3. **Enter via the Strategy alert** (or manually)

#### Mid-week (monitor)

- Don't re-run. The Strategy on TradingView has live signals.
- Use the web page only if a held position triggers a STAGE-EXIT or RRG-EXIT alert.

### Reading the colour legend

| Colour on regime cards / signals | Meaning |
|---|---|
| 🟢 Green | RISK_ON / BUY-LEADER / OVERWEIGHT |
| 🟡 Amber | MIXED / INTL_LED / ACCUMULATE / EARLY-BASE / NEUTRAL+ |
| 🔵 Blue | GOLD_LED |
| 🟠 Orange | NEUTRAL- / HOLD-WATCH |
| 🔴 Red | RISK_OFF / AVOID-DOWNTREND / UNDERWEIGHT / ILLIQUID |

### How to interpret the donut chart

The allocation donut sums to 100%. Slices show the regime engine's **suggested portfolio tilt**:

```
RISK_ON donut typically:
 - Sector tilts: 60% (5×12% across top-quartile sectors)
 - Broad equity: 30% (Junior + Mid150)
 - Intl: 10% (MAFANG)

GOLD_LED donut:
 - Gold: 30%
 - Liquid: 30%
 - Silver: 10%
 - Intl hedge: 10%
 - Defensive sectors: 20%
```

These are **suggested weights, not orders**. You decide how much of your account to allocate to the rotation system vs other strategies.

### Common UI gotchas

- **🔴 Sectors chip says "not generated"** but you ran the screener: check log — `etf_rotation.py` may have failed but `etf_screener.py` succeeded.
- **Allocation donut empty**: regime detected but no flagships scored above 200DMA. This is RISK_OFF — system is signalling defense.
- **Stale 🟡 chip** but you don't want to wait 60s for Run-All: use CLI `python etf_screener.py` in a terminal in parallel.
- **Filtered table empty**: Loosen filters. Default filter excludes Tier C ETFs.

### Decision rules from the picks table

| Pick characteristic | Action |
|---|---|
| Total_Score ≥ 32, Signal = BUY-LEADER, Liquidity_Status = OK | Top conviction — full size |
| Total_Score 26-31, Signal = ACCUMULATE | Half size — watch for BUY-LEADER promotion |
| Total_Score 20-25, in picks but no BUY/ACC signal | Just diversification weight — skip |
| Suggested_Weight_pct ≥ 25% (heavy allocation) | Verify the regime label warrants this (e.g., GOLDBEES at 30% only makes sense in GOLD_LED) |
| Liquidity_Status = WATCH or ILLIQUID | Skip even if weight is high |

### Sync workflow with TradingView

After clicking Run All:
1. Open **Tab 1 → Copy symbols** expander
2. Copy the `NSE:NIFTYBEES,NSE:BANKBEES,...` string
3. In TradingView → Watchlist → Add Symbols → paste
4. Load Commander ETF Dashboard on each watchlist symbol
5. Visually verify the SIGNAL matches the web app's Signal column

### When to manually trigger Run All

| Trigger | Action |
|---|---|
| Sunday evening planning | Always |
| After market open Monday if no Sunday run | Yes |
| Mid-week regime question | No — Pine dashboard is more current |
| After universe edit (new ETF added) | Yes |
| After threshold change in `etf_config.json` | Yes |

### Limits

- File-status chip ages refresh on page reload only. Click 🔄 Refresh in the chip strip area or full-page reload (Ctrl+R).
- The page can't run the backtest module (`etf_backtest.py`) — that's CLI only.
- Calendar overlay (`etf_calendar.py`) not yet wired into this page. Use CLI: `python etf_calendar.py --summary`.
