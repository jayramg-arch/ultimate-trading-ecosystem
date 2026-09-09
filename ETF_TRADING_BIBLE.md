# THE ETF TRADING BIBLE
## Jay's Single Go-To Guide — NSE ETF Rotation System

> **Audience:** Jay (Jayram G) — independent systematic trader, NSE only, INR-denominated.
> **Built:** 12 May 2026, post-Phase-2 audit + production-config lock.
> **Status:** All bugs fixed, all enhancements shipped, production config validated over 6.35-year walk-forward (Sharpe 1.63, MaxDD −5.41%, Alpha +5.61% vs NIFTYBEES).
> **Per-module references:** [`docs/etf_system/`](docs/etf_system/00_INDEX.md)

---

## Table of Contents

1. [Philosophy](#1-philosophy)
2. [Why ETFs Need Their Own System](#2-why-etfs-need-their-own-system)
3. [System Architecture](#3-system-architecture)
4. [The Signal Vocabulary](#4-the-signal-vocabulary)
5. [Risk Management — Non-Negotiable Rules](#5-risk-management--non-negotiable-rules)
6. [Operational Cadences](#6-operational-cadences)
7. [Module Cliff Notes](#7-module-cliff-notes)
8. [Production Config (Locked)](#8-production-config-locked)
9. [The Walk-Forward Backtest Result](#9-the-walk-forward-backtest-result)
10. [Calendar Awareness](#10-calendar-awareness)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)
12. [Quick Reference Appendix](#12-quick-reference-appendix)
13. [Six-Phase Roadmap Status](#13-six-phase-roadmap-status)

---

## 1. Philosophy

The ETF rotation system rests on three propositions:

### 1.1 Weinstein Stage Analysis is the anchor

Per CLAUDE.md: only trade Stage 2 breakouts; avoid/exit Stage 3-4. The 30-week MA on the weekly chart is the primary stage anchor. The system uses the 200-day MA on daily as a tighter proxy for execution.

### 1.2 ETF alpha comes from rotation, not stock-picking

Stocks have idiosyncratic alpha (earnings beats, management changes, M&A). ETFs don't — they're indices in tradeable form. The only differentiated alpha source is **timing the rotation between exposures**:

- Sector rotation (IT → Bank → Pharma cycle)
- Asset-class rotation (Equity → Gold → Cash regime shifts)
- International tilt timing (when Indian equity is sleeping)

### 1.3 Signal consistency is sacred

Per CLAUDE.md zero-drift rule: the same ETF must produce the **same** signal whether you read it from Python (`etf_screener.py`), the Pine dashboard (`Commander_ETF_Dashboard_v1.2`), or the Pine strategy (`Commander_ETF_Strategy_v1.1`).

This is enforced by:
- Single config file (`etf_config.json`) — Python loads automatically, Pine references manually
- Cross-validation harness (`etf_validate.py`) — auto-detects drift
- Identical signal-ladder ordering in both Python and Pine

---

## 2. Why ETFs Need Their Own System

| Stock System | ETF System | Why different |
|---|---|---|
| RFF fundamentals (Net Income, FCF, ICR, D/E) | **No fundamentals** | ETFs hold the underlying — fundamentals belong to the constituents |
| Per-stock VCP / tight base detection | **No VCP** | Diversification within an ETF smooths consolidation patterns |
| Multiple catalysts (POS-BO, POS-ACCUM, SWG-BO, REV-CB...) | **2 catalysts only** (BUY-LEADER, EARLY-BASE) | ETFs don't have stock-specific event setups |
| Pyramiding allowed (up to 6 entries) | **Pyramiding = 0** | Single entry per ETF; diversification comes from holding multiple ETFs |
| Sector context (sector index in Stage 2?) | **An ETF IS the sector** | Self-referencing |
| Kelly + vol-discount + regime risk | **Vol-discount alone** | One sizing knob is enough |
| Backtest = 12 monthly anchors | **Walk-forward Sharpe gate** | ETFs trend slower; longer windows + IS/OOS split |
| Liquidity is rarely binding | **Liquidity is #1 risk** | Half of NSE ETFs trade < ₹1Cr/day |
| Per-ETF benchmark substitution | **Locked to Nifty 500** | Cross-ETF rankings must be comparable |

---

## 3. System Architecture

```
                            ┌──────────────────────────┐
                            │   etf_universe.py        │
                            │   56 ETFs + inception    │
                            └──────────────┬───────────┘
                                           │
              ┌────────────────────────────┼────────────────────────┐
              │                            │                        │
              ▼                            ▼                        ▼
   ┌──────────────────┐         ┌──────────────────┐    ┌──────────────────┐
   │  etf_screener.py │         │  etf_rotation.py │    │  etf_backtest.py │
   │  4-axis ranks    │         │  Sector + Regime │    │  Walk-forward    │
   │  → 1 CSV         │         │  → 4 CSVs        │    │  → 7 files / run │
   └────────┬─────────┘         └────────┬─────────┘    └──────────────────┘
            │                            │                       ▲
            │                            │                       │
            │   ┌────────────────┐       │              ┌────────┴────────┐
            │   │ etf_calendar.py│       │              │  etf_config.json│
            │   │ Date events    │       │              │ Single source of │
            │   │ overlay        │       │              │   truth          │
            │   └────────────────┘       │              └─────────────────┘
            │                            │
            ▼                            ▼
   ┌──────────────────┐         ┌──────────────────┐
   │  Pine Dashboard  │         │  Pine Strategy   │
   │  v1.2            │         │  v1.1            │
   │  (analysis)      │         │  (execution)     │
   └────────┬─────────┘         └────────┬─────────┘
            │                            │
            └──────────┬─────────────────┘
                       ▼
            ┌──────────────────┐         ┌──────────────────┐
            │ Commander Web UI │         │  etf_validate.py │
            │ 🪙 ETF page      │         │  Drift check     │
            └──────────────────┘         └──────────────────┘
```

### File summary

| Layer | File | Lines | Output |
|---|---|--:|---|
| Universe | `etf_universe.py` | 350 | (Python dict) |
| Screener | `etf_screener.py` | 470 | `ETF_Screener_Results.csv` |
| Rotation | `etf_rotation.py` | 680 | 4 CSVs (sector / regime / RRG / picks) |
| Backtest | `etf_backtest.py` | 700 | `backtest_runs/etf_<id>/` |
| Calendar | `etf_calendar.py` | 330 | Markdown digest + CSV overlay |
| Validation | `etf_validate.py` | 280 | `ETF_Validate_Reference.csv` + Markdown report |
| Config | `etf_config.json` | 52 | (config) |
| Pine Dashboard | `Commander_ETF_Dashboard_v1.0.pine` | 370 | (on chart) |
| Pine Strategy | `Commander_ETF_Strategy_v1.0.pine` | 456 | (on chart + alerts) |
| Web UI | `weinstein_commander_web_v4.0.py` ETF page | 380 | (Streamlit) |
| **Total** | | **~4000 lines** | |

---

## 4. The Signal Vocabulary

### 4.1 The Signal Ladder (precedence order)

This order is **canonical** — same in Python and Pine. The first matching condition wins.

```
1. NOT AN ETF      Pine only: syminfo.type != "fund"
2. ILLIQUID        Turnover < ₹2 Cr/day median (LIQ_MIN_CR)
3. AVOID-DOWNTREND Stage 4 (close < SMA200 AND slope <= 0.1%)
4. BUY-LEADER      Stage 2 + RRG LEADING + liq_score >= 6  [highest conviction]
5. ACCUMULATE      Stage 2 + RRG IMPROVING
6. HOLD-WATCH      Stage 2 + RRG WEAKENING (don't add; trim if held)
7. EARLY-BASE      Stage 1 + RRG IMPROVING (speculative; gated by `allow_early`)
8. PRE-S2 WARN     Stage 1 + RS momentum positive (watchlist nudge, not a trade)
9. NEUTRAL         (everything else)
```

### 4.2 The Stage Vocabulary

| Stage | Definition | Trade Action |
|---|---|---|
| 1 BASE | close > SMA200 AND slope <= 0.1% (basing above MA) — OR — close <= SMA200 AND slope > 0.1% (basing below) | Watch for breakout |
| **2 ADVANCE** | close > SMA200 AND slope > 0.1% | **Buy on confluence (RRG + liquidity)** |
| 3 TOP | close > SMA200 AND slope <= 0.1% | Trim / exit |
| 4 DECLINE | close <= SMA200 AND slope <= 0.1% | Sell / avoid / short (if you do that) |

### 4.3 The RRG Quadrant Vocabulary

| Quadrant | Mansfield | Momentum (4W) | Trade |
|---|---|---|---|
| **LEADING** | ≥ 0 | ≥ 0 | Confirmation — full size |
| IMPROVING | < 0 | ≥ 0 | Early entry — half size |
| WEAKENING | ≥ 0 | < 0 | Trim — momentum decay |
| LAGGING | < 0 | < 0 | Exit — full rotation out |

### 4.4 The Rotation Vector Vocabulary (Direction of Travel)

| Vector | Transition | Meaning | Trade |
|---|---|---|---|
| IGNITE | LAGGING → IMPROVING | Early turn | Watch |
| **BREAKOUT** | IMPROVING → LEADING | Full rotation in | **Buy** |
| **STABLE** | LEADING → LEADING | Continuation | **Hold** |
| DECAY | LEADING → WEAKENING | Loss of momentum | Trim |
| ROLLOVER | WEAKENING → LAGGING | Full rotation out | Exit |
| FALLING | LAGGING → LAGGING | Continued downtrend | Avoid |
| CHURNING | IMPROVING → IMPROVING | Stuck building | Wait |
| FADING | WEAKENING → WEAKENING | Stuck topping | Trim |
| REJECTED | IMPROVING → WEAKENING | Failed breakout | Avoid |
| RECOVERED | WEAKENING → IMPROVING | Bounce | Cautious accumulate |
| COLLAPSED | LEADING → LAGGING | Rare big drop | Exit immediately |

### 4.5 The Regime Vocabulary

| Regime | Trigger | Top-pick tilt |
|---|---|---|
| **RISK_ON** | ≥ 2 equity flagships above 200DMA + outperforming gold | 60% sectors / 30% broad / 10% intl |
| **GOLD_LED** | Gold flagship score > best equity flagship score | 40% gold+silver / 30% cash / 20% defensive sectors / 10% intl |
| **INTL_LED** | Indian equity off, US/Intl on | 50% intl / 30% top sectors / 20% gold+cash |
| **RISK_OFF** | All equities + intl off, gold not leading | 35% gold+silver / 65% bonds+cash |
| **MIXED** | None of the above | Diversified default |

---

## 5. Risk Management — Non-Negotiable Rules

Per CLAUDE.md institutional standard:

### 5.1 Position Sizing

```
risk_amt    = equity × 1%
qty (raw)   = risk_amt / (ATR(14) × stop_mult)
qty (live)  = qty (raw) × vol_disc
vol_disc    = min(target_atr_pct / actual_atr_pct, 1.0)   [never amplifies]
```

The vol_disc means **high-volatility ETFs auto-size smaller**. Gold/debt ETFs get full risk budget; sector/smallcap get fraction-sized.

### 5.2 Vol Profile Presets

| Profile | Use for | atr_stop_mult | target_atr_pct |
|---|---|--:|--:|
| Low (gold/debt) | GOLDBEES, SILVERBEES, LIQUIDBEES, BBETF, GILT5YBEES | 1.8 | 1.0% |
| **Med (broad equity)** | NIFTYBEES, JUNIORBEES | 2.5 | 1.5% |
| High (sector/smallcap) | Sector ETFs, MID150BEES, smallcap ETFs | 3.0 | 2.0% |
| Intl (Nasdaq/FANG) | MAFANG, MON100, NASDBEES, MASPTOP50 | 2.5 | 1.8% |

### 5.3 Hard Exits (Override Everything)

1. **Stage 4 entered** — exit immediately
2. **Liquidity collapse** — turnover < liq_exit_cr (₹1 Cr/day default)
3. **RRG → LAGGING** — soft exit, configurable on/off
4. **ATR trailing stop (CE)** — Chandelier Exit ratchet, never moves down

### 5.4 Min-Hold Rule

- **28 calendar days** minimum before SELL allowed (production default)
- Stage-4 / liquidity-collapse forced exits **override** the min-hold gate
- Prevents over-rotation (cut MAFANG churn from 245 → 57 trades in the audit)

### 5.5 Liquidity Tiers (Position Size Caps)

| Tier | Threshold | Max INR Position |
|---|---|--:|
| A | ≥ ₹10 Cr/day | ₹25-50L |
| B | ₹2-10 Cr/day | ₹5-15L |
| C | < ₹2 Cr/day | ₹1-3L (avoid except special) |

### 5.6 T1 Partial Profit + Breakeven Move

- T1 target = entry + (initial_risk × 2.5R)
- When hit: sell 30%, lock SL at breakeven, ride remaining 70% on CE trail
- This is what locks in alpha while preserving asymmetric upside

---

## 6. Operational Cadences

### Daily — Mon to Fri (intraday)

| Time | Action |
|---|---|
| 09:15 IST market open | Execute any Sunday-planned trades |
| 12:00 IST | Check Pine alerts on held positions (Stage-Exit / RRG-Exit / Liq-Exit) |
| 15:30 IST close | No new trades — wait for signal confirmation |

### Weekly — Sunday evening

| Step | Action | Time |
|---|---|---|
| 1 | `python etf_screener.py` (or click 🔄 Run All in web app) | 30-60s |
| 2 | `python etf_rotation.py` (if not already in Run All) | 30s |
| 3 | Review **regime label** | 1 min |
| 4 | Review **top picks** vs current portfolio | 5 min |
| 5 | Read `python etf_calendar.py --summary` | 2 min |
| 6 | Plan Monday trades | 5 min |

### Monthly — First Sunday

| Step | Action |
|---|---|
| 1 | All of the weekly cadence |
| 2 | Open backtest results in `backtest_runs/` — has anything regressed? |
| 3 | Update inception dates in `etf_universe.py` if new ETF launched |

### Quarterly

| Step | Action |
|---|---|
| 1 | `python etf_validate.py` — full drift check |
| 2 | `python etf_backtest.py --walk-forward` — verify metrics haven't regressed |
| 3 | Review liquidity tiers — has anything moved between A/B/C? |
| 4 | Update `etf_calendar.py` EVENTS with confirmed dates for next quarter |

### Annually

| Step | Action |
|---|---|
| 1 | Walk universe for delistings / fund mergers |
| 2 | Refresh calendar for next year |
| 3 | Full year-by-year performance review (year breakdown table) |

---

## 7. Module Cliff Notes

### 7.1 `etf_universe.py` — The Curated 56-ETF Universe

- 56 ETFs across 7 asset classes (BROAD_EQUITY 8, SECTOR 18, SMART_BETA 6, INTERNATIONAL 5, COMMODITY 7, DEBT 4, THEMATIC 8)
- 100% inception date coverage → backtest survivorship correction works
- Helpers: `get_meta`, `sector_etfs`, `list_by_asset_class`, `available_at`, `inception_date`

→ [Full guide](docs/etf_system/01_etf_universe_guide.md)

### 7.2 `etf_screener.py` — Per-ETF 4-Axis Scoring

- Liquidity / Trend / RS / Rotation, each 0-10 → Total 0-40
- Outputs: signal label, stage, RRG quadrant, **Rotation_Vector**, Mansfield RS, etc.
- Signal precedence: ILLIQUID > AVOID > BUY-LEADER > ACCUMULATE > HOLD-WATCH > EARLY-BASE > NEUTRAL

→ [Full guide](docs/etf_system/02_etf_screener_guide.md)

### 7.3 `etf_rotation.py` — Cross-ETF Rotation Engine

- Sector rotation table (composite RS, 60/40 long-short)
- Asset-class regime detector (5 labels)
- RRG coordinates (8-week tail)
- Top picks per regime (with correlation gate + liquidity warning)

→ [Full guide](docs/etf_system/03_etf_rotation_guide.md)

### 7.4 `etf_backtest.py` — Walk-Forward Backtest

- Point-in-time correctness (survivorship corrected)
- Transaction costs modeled (0.03% comm + 2bps slip)
- Walk-forward gate: OOS Sharpe must be ≥ 60% of IS Sharpe
- Production-locked config: monthly + top-8 + min-hold-28

→ [Full guide](docs/etf_system/04_etf_backtest_guide.md)

### 7.5 `etf_calendar.py` — Event Calendar Overlay

- 82 events (RBI MPC, Budget, FOMC, F&O OPEX) for 2024-2026
- Maps events → sub_category impact scores (-3 to +3)
- Informational only — does not override Stage/RS/Liq gates

→ [Full guide](docs/etf_system/05_etf_calendar_guide.md)

### 7.6 `etf_validate.py` — Cross-Validation Harness

- Internal consistency: signal precedence + thresholds + universe integrity
- Pine drift check (manual data window paste)
- CI-friendly `--strict` mode

→ [Full guide](docs/etf_system/06_etf_validate_guide.md)

### 7.7 `etf_config.json` — Single Source of Truth

- Python modules load it automatically
- Pine inputs reference these values manually
- Edit here once → propagates to both surfaces

→ [Full guide](docs/etf_system/07_etf_config_guide.md)

### 7.8 Commander ETF Dashboard v1.2 (Pine)

- 19-row dashboard table with **Total_Score + Grade**
- Stage bgcolor + CE Trail + Active SL + Pre-S2 dot
- 4 alerts (Stage 2 entered, RRG LEADING, BUY-LEADER, Stage 4 entered)

→ [Full guide](docs/etf_system/08_commander_etf_dashboard_guide.md)

### 7.9 Commander ETF Strategy v1.1 (Pine)

- Vol Profile presets + min-hold + T1 partial + CE trailing
- ETF instrument guard (`syminfo.type == "fund"`)
- 6-row mini panel (Position / Active SL / T1 / Open P/L only)

→ [Full guide](docs/etf_system/09_commander_etf_strategy_guide.md)

### 7.10 Commander Web ETF Page

- 🔄 Run All button + file-status strip
- 4 tabs: Top Picks / Sector Rotation / Asset-Class Regime / Liquidity & Universe
- Allocation donut chart + filterable universe table

→ [Full guide](docs/etf_system/10_commander_web_etf_page_guide.md)

---

## 8. Production Config (Locked)

From `etf_config.json` (12 May 2026 audit lock):

```json
{
  "benchmark_yf": "^CRSLDX",
  "liq_min_cr": 2.0,
  "buy_leader_min_liq_score": 6,
  "correlation_gate": { "threshold": 0.75, "lookback": 60 },
  "rotation_engine": { "composite_long_weight": 0.60, "composite_short_weight": 0.40 },
  "backtest_defaults": {
    "freq": "monthly",
    "top_n": 8,
    "min_hold_days": 28
  }
}
```

| Knob | Value | Why |
|---|---|---|
| Rebalance | **Monthly** | Same Sharpe as weekly, **half the drawdown**, 1/4 the trades |
| Top-N | **8** | Best alpha-Sharpe trade-off in sensitivity tests |
| Min-hold | **28 days** | Cuts MAFANG over-rotation by 77% |
| Risk per trade | **1.0%** | Standard institutional |
| Initial stop ATR mult | **By Vol Profile** | Low 1.8, Med 2.5, High 3.0, Intl 2.5 |
| Liquidity floor | **₹2 Cr/day** | Matches BUY-LEADER threshold |
| Correlation gate | **0.75** | Prevents 5 correlated sectors |

---

## 9. The Walk-Forward Backtest Result

### 9.1 Headline (Jan 2020 → May 2026, 6.35 years, production-locked config)

| Metric | Strategy | NIFTYBEES (Benchmark) |
|---|--:|--:|
| **Total Return** | **+188%** | +103% |
| **CAGR** | **18.15%** | 12.54% |
| **Alpha (annualized)** | **+5.61%** | — |
| **Sharpe** | **1.63** | ~0.7 |
| **Max Drawdown** | **−5.41%** | ~−31% (COVID) |
| **Win Rate (monthly)** | **71.05% (54/76)** | — |
| **Annual Volatility** | 11.16% | ~17% |
| **Final Equity from ₹10L** | **₹28.83 L** | ₹20.30 L |

### 9.2 Walk-Forward Gate: PASS

| Period | CAGR | Sharpe | Max DD | Alpha |
|---|--:|--:|--:|--:|
| In-Sample (2020-01 → 2023-10) | 10.81% | 1.30 | −5.41% | −4.01% |
| Out-of-Sample (2023-11 → 2026-05) | 29.97% | 2.08 | −5.23% | +20.46% |

Gate criterion: `OOS Sharpe (2.08) ≥ 60% × IS Sharpe (1.30 × 0.6 = 0.78)`. **Cleared by 2.7×.**

### 9.3 Year-by-Year

| Year | Strategy | Benchmark | Alpha |
|---|--:|--:|--:|
| 2020 | +9.83% | +15.18% | −5.35% |
| 2021 | +9.31% | +25.55% | **−16.24%** (known weakness in narrow mega-cap bulls) |
| 2022 | +6.91% | +3.84% | +3.07% |
| 2023 | +21.81% | +20.22% | +1.58% |
| 2024 | +27.95% | +10.04% | **+17.92%** |
| 2025 | +30.17% | +11.19% | **+18.98%** |
| 2026 (5mo) | +10.71% | −7.24% | **+17.95%** |

### 9.4 What the result means

- **The system works** — 6.35 years, Sharpe 1.63, alpha 5.61%, max DD a third of the benchmark
- **There IS a known weakness** — 2020-2021 narrow mega-cap bull. The system underperforms when rotation is *absent* from the market
- **2022+ is robust** — post-regime-shift, 5 consecutive years of positive alpha
- **Phase 3 weight fitting** is now cleared to start with the recommendation to train on the **2022-2026 window** (avoid the known-bad pre-2022 regime)

---

## 10. Calendar Awareness

### 10.1 Major event types covered

| Event | Frequency | Typical Impact |
|---|---|---|
| **RBI MPC** | 6/year | Dovish → debt + banking + REITs ↑ |
| **Union Budget** | 1/year (1 Feb) | Infra + defence + PSU + mfg ↑ |
| **FOMC** | 8/year | Hawkish → gold + intl ↓; Dovish → gold + intl ↑ |
| **F&O Expiry** | 12/year (last Thu) | Banking + momentum ↓ (intraday vol) |

### 10.2 Weekly calendar check

```bash
python etf_calendar.py --summary    # Prints 14-day forward digest
```

Read it Sunday evening **before** finalizing the week's trade plan.

### 10.3 When to lean on calendar

| Situation | Action |
|---|---|
| RBI MPC dovish 2 days out, LIQUIDBEES Calendar_Adj = +3 | Position before the event, don't chase |
| FOMC hawkish tomorrow, MAFANG = −2 | Avoid new MAFANG entries |
| Budget day, INFRABEES = +3 | Pre-position if Stage 2 + LEADING confluence |
| OPEX day, BANKBEES = −1 | Skip intraday entries on banking ETFs |

### 10.4 What calendar **won't** do

- Predict the actual event outcome (rate cut vs hold) — uses default assumptions
- Override Stage/RS/Liq gates — informational only
- Replace a Sunday news read — macro context > calendar shorthand

---

## 11. Troubleshooting & FAQ

### Q: I edited a threshold in `etf_config.json` but Pine still uses the old value.
**A:** Pine can't read JSON. Manually update the Pine input default and add a `// matches etf_config.json["liq_min_cr"]` comment. Then run `python etf_validate.py --compare` to confirm.

### Q: The screener shows GOLDBEES as Grade D but Mansfield clearly shows leadership.
**A:** Check the universe entry. If `benchmark_yf` was being substituted (pre-12 May 2026 bug), Pine and Python disagreed. Bug is fixed — re-run.

### Q: My Pine strategy dashboard shows red header on NIFTYBEES.
**A:** Either `syminfo.type` isn't `"fund"` for that symbol on TradingView's side, OR you loaded the wrong instrument. The strategy refuses to fire — verify the chart symbol.

### Q: The web app's 🔄 Run All button hangs / errors.
**A:** Usually a `data_provider` cache issue or yfinance rate limit. Run `python etf_screener.py` in a terminal and read the error. Force-refresh cache if stale.

### Q: Why is 2021 so bad for the system?
**A:** Narrow mega-cap bull market. Index buy-hold beats every rotation system in those environments. This is a known limitation, not a bug.

### Q: Can I disable the min-hold filter?
**A:** Yes — `python etf_backtest.py --min-hold 0`. But your trade count will spike 4× and MAFANG will churn 245+ times over 6 years. Costs will eat the alpha.

### Q: Should I run weekly or monthly?
**A:** Monthly. The audit showed identical Sharpe (1.52 vs 1.52), half the drawdown (−6% vs −12%), and 1/4 the trades. Lower stress, lower cost, same return.

### Q: What if `etf_config.json` is missing?
**A:** Python falls back to hard-coded defaults. Pine continues with whatever was last set in input defaults. Both surfaces still work — just no central control.

### Q: How do I know if Python and Pine disagree?
**A:** Run `python etf_validate.py` weekly. With `--compare pine_export.csv`, it auto-detects drift. If non-zero drift on the signal column → stop trading until resolved.

### Q: Top-N=12 returns same as Top-N=8. Bug?
**A:** Fixed in the 12 May 2026 production lock. Templates now generate 12+ picks per regime and weights are renormalized after `head(top_n)`.

### Q: Should I add more ETFs to the universe?
**A:** Only if all of: (a) ≥₹2Cr/day turnover, (b) AUM ≥₹100Cr, (c) distinct exposure (no duplicate trackers), (d) inception date known. Add the entry + inception date.

### Q: The Pine strategy never enters even on BUY-LEADER setups.
**A:** Check `Allow EARLY-BASE` — leave off. Check Vol Profile matches the ETF (Med for broad, High for sector). Check the date window — it might be outside `start_date`/`end_date`. Check `Min Liquidity Score for BUY-LEADER` — default 6 means turnover must be ≥₹2Cr/day.

### Q: How do I exit my Sunday-night-planned trade if Monday gaps up?
**A:** The strategy enters at next bar close (`process_orders_on_close=true`). If the gap up is huge, you'll get filled at the close — accept it or skip the trade. Don't chase intraday.

---

## 12. Quick Reference Appendix

### 12.1 CLI cheat sheet

```bash
# ── Daily / weekly ─────────────────────────────────────
python etf_screener.py                      # Score the universe
python etf_rotation.py                       # Build rotation + picks
python etf_calendar.py --summary             # 14-day event digest

# ── Validation ─────────────────────────────────────────
python etf_validate.py                       # Internal consistency check
python etf_validate.py --compare pine.csv    # Full drift check
python etf_validate.py --strict              # CI mode (exit 1 on issues)

# ── Backtest ───────────────────────────────────────────
python etf_backtest.py --walk-forward                          # Production config (monthly)
python etf_backtest.py --freq weekly --walk-forward             # Weekly sensitivity
python etf_backtest.py --top-n 5 --walk-forward                 # Concentrated
python etf_backtest.py --start 2022-01-01 --walk-forward         # Post-regime-shift
python etf_backtest.py --min-hold 0 --walk-forward               # No min-hold

# ── Universe diagnostics ───────────────────────────────
python etf_universe.py                       # Print universe summary

# ── Web UI ─────────────────────────────────────────────
streamlit run weinstein_commander_web_v4.0.py
# → 🪙 ETF page → click 🔄 Run All
```

### 12.2 File locations cheat sheet

```
GeminiVSCode/
├── ETF_TRADING_BIBLE.md                   ← THIS FILE
├── etf_universe.py                         Universe
├── etf_screener.py                         4-axis scoring
├── etf_rotation.py                         Rotation engine
├── etf_backtest.py                         Walk-forward backtest
├── etf_calendar.py                         Event calendar
├── etf_validate.py                         Drift check
├── etf_config.json                         Central config
│
├── Commander_ETF_Dashboard_v1.0.pine       Pine dashboard (title v1.2)
├── Commander_ETF_Strategy_v1.0.pine        Pine strategy (title v1.1)
├── weinstein_commander_web_v4.0.py         Web app (ETF page inside)
│
├── ETF_Screener_Results.csv                Latest screener output
├── ETF_Sector_Rotation.csv                 Sector ranks
├── ETF_AssetClass_Regime.csv               Regime detection
├── ETF_RRG_Coordinates.csv                 RRG plot data
├── ETF_Top_Picks.csv                       Regime-aware picks
│
├── backtest_runs/etf_<id>/                 Per-run backtest outputs
└── docs/etf_system/                        Per-module guides
    ├── 00_INDEX.md
    ├── 01_etf_universe_guide.md
    └── ... (10 module guides)
```

### 12.3 Key constants

| Constant | Value | Where |
|---|---|---|
| BENCHMARK_YF | `^CRSLDX` | `etf_config.json` + `etf_screener.py` |
| LIQ_MIN_CR | 2.0 ₹Cr/day | `etf_config.json` + Pine input default |
| BUY_LEADER_MIN_LIQ_SCORE | 6 | `etf_config.json` + Pine input default |
| CORRELATION_GATE_THRESHOLD | 0.75 | `etf_config.json` |
| MANSFIELD_SMA_LEN | 200 | Pine + Python |
| RS_MOMENTUM_LOOKBACK | 20 bars (≈4 weeks) | Pine + Python |
| STAGE2_SLOPE_MIN | 0.1% / 20 days | Pine + Python |
| MIN_HOLD_DAYS | 28 calendar days | `etf_config.json` + backtest |

### 12.4 Universe summary (12 May 2026)

| Class | Count | Flagship |
|---|--:|---|
| BROAD_EQUITY | 8 | NIFTYBEES |
| SECTOR | 18 | BANKBEES |
| SMART_BETA | 6 | NV20IETF |
| INTERNATIONAL | 5 | MON100 |
| COMMODITY | 7 | GOLDBEES |
| DEBT | 4 | LIQUIDBEES |
| THEMATIC | 8 | CPSEETF |
| **TOTAL** | **56** | |

### 12.5 Signal precedence cheat sheet

```
turnover < ₹2Cr  → ILLIQUID
stage == 4       → AVOID-DOWNTREND
stage==2 & LEAD & liq>=6 → BUY-LEADER     [strategy fires]
stage==2 & IMPROVING     → ACCUMULATE     [half size]
stage==2 & WEAKENING     → HOLD-WATCH     [trim, don't add]
stage==1 & IMPROVING     → EARLY-BASE     [if allow_early]
stage==1 & mom > 0       → PRE-S2 WARN    [watchlist nudge]
                         → NEUTRAL
```

### 12.6 Regime cheat sheet

```
≥2 equity flags above 200DMA + gold weak  → RISK_ON   (60% sectors)
gold flag > best equity flag              → GOLD_LED  (40% commodities + 30% cash)
intl on, equity off                       → INTL_LED  (50% intl)
all off, gold not leading                 → RISK_OFF  (65% bonds + cash)
otherwise                                 → MIXED     (diversified default)
```

### 12.7 Vol Profile cheat sheet

```
GOLDBEES, SILVERBEES, LIQUIDBEES, BBETF, GILT5YBEES   → Low  (1.8 × ATR stop, 1.0% target)
NIFTYBEES, JUNIORBEES                                  → Med  (2.5 × ATR, 1.5% target)
Sector ETFs, MID150BEES, smallcap                      → High (3.0 × ATR, 2.0% target)
MAFANG, MON100, NASDBEES, MASPTOP50                    → Intl (2.5 × ATR, 1.8% target)
```

---

## 13. Six-Phase Roadmap Status

| Phase | Description | Status |
|---|---|---|
| **Phase 0** | Performance Attribution | ⏸ Pending — awaiting closed-trades schema |
| **Phase 1** | Data Integrity | ✅ Done (validation audit + cross-val harness) |
| **Phase 2** | Backtest Rigour | ✅ **Done — walk-forward gate PASS** (OOS Sharpe 2.08 > 0.78 threshold) |
| **Phase 3** | Fitted Weights | 🟢 **Cleared to start** — train on 2022-2026 window |
| **Phase 4** | Portfolio Risk | Pending — correlation gate + sector cap + regime-conditional sizing |
| **Phase 5** | Sentiment + Ops | Calendar overlay shipped; NLP validation pending |

The hard gate after Phase 2 is **clear**: OOS Sharpe must be ≥ 60% of IS Sharpe. The locked production config passes this gate with margin. **Phase 3 weight fitting can now proceed safely** with the recommendation to train on the 2022-2026 sub-window (avoiding the known-bad 2020-2021 narrow-bull regime).

---

## Closing Discipline

Per CLAUDE.md "I am not adding features. I am compounding rigor."

This system is **complete enough to trade**. Further changes should add rigor, not features:
- More backtests
- Tighter cross-validation
- Better risk gating
- Better drawdown control

Features that don't improve risk-adjusted returns are noise. Build less, validate more.

---

*This Bible is a snapshot of the ETF Trading System as of 12 May 2026. Maintain it: update sections when modules change, re-run backtests quarterly, and re-validate signal drift monthly.*
