# 25 · Scanner Filter Map — parameter-by-parameter, all four categories

Built 13 Aug 2026 from the code and from the live screener.in screen definitions.

**Update to the first version of this document:** the screener.in criteria are NOT
unauditable. Each saved screen exposes its query in the page's `query` textarea, so all
seven are reproduced verbatim in §4 and folded into the matrices below. That changes the
conclusion — see §5.

The four categories compared:

| category | producer | fundamental gate |
|---|---|---|
| **BULL** | Chartink scans 1-4 → `brute_force_match_pro` inner join | screener.in Stage-2 screens (**hard**) |
| **RECOVERY** | Chartink scans 5-7 → matcher → `recovery_screener` | screener.in Recovery screens **+ RFF ≥ 4/6** (hard ×2) |
| **CATALYST** | `bull_screener.run_bull_screener`, nifty500 | **RFF ≥ 4/6** (hard) |
| **PULLBACK** | `pullback_finder`, nifty500 | **BFF ≥ 2/5** (hard, added 13 Aug 2026) |

---

## 1 · FUNDAMENTAL parameters

`—` = not checked at all. Bull column shows the range across its four screens.

| parameter | BULL (screener.in) | RECOVERY (screen + RFF) | CATALYST (RFF) | PULLBACK (BFF) |
|---|---|---|---|---|
| **GROWTH** |
| Qtr sales growth YoY | **> 10-20%** | — | — | **≥ 15%** |
| Qtr profit growth YoY | **> 15-25%** | — | — | **≥ 20%** |
| EPS qtr > year-ago qtr | Leaders only | — | — | — |
| **PROFITABILITY / RETURNS** |
| ROCE | **> 15%** | **> 15-20%** | — | **≥ 15%** (fin 10%) |
| ROE | **> 15%** (2 of 4) | — | — | fin only (12%) |
| ROA | — | **> 5%** | **> 5%** | — |
| Net margin | Pullback: **> 10%** | — | — | — |
| Margin expansion (OPM↑) | — | — | — | **yes** |
| Net profit > 0 | implied by growth | **yes** | **yes** | **yes** |
| **BALANCE SHEET** |
| Debt / equity | **< 0.5-1.5** | **< 1-2** | **< 2** | — |
| Interest coverage | — | **> 2** (screen) / **> 3.5** (RFF) | **> 3.5** | — |
| Current ratio | — | **> 1** | **> 1** | — |
| **CASH** |
| Operating cash flow | Early Birds: **3yr > 0** | **last yr > 0** | — | — |
| Free cash flow | — | **> 0** (RFF) | **> 0** | — |
| **OWNERSHIP / GOVERNANCE** |
| Promoter holding | **> 40%** (or FII/DII > 15%) | — | — | — |
| Change in promoter holding | Early Birds: **> 0** | — | — | — |
| FII/DII holding change | Leaders: **> 0** | — | — | — |
| **Pledged %** | **< 2-5%** | — | — | — |
| **SIZE** |
| Market cap | **> ₹5,000 Cr** | **> ₹5,000 Cr** | — | — |
| Turnover | — | — | > ₹5 Cr | > ₹2 Cr |
| | | | | |
| **checks that must pass** | **all** | **all** + 4 of 6 RFF | **4 of 6 RFF** | **2 of 5 BFF** |

### What this table says

**1. The BULL standard is a GROWTH standard, and it is the strictest in the system.**
Sales growth, profit growth, ROCE, ROE, low debt, promoter skin-in-the-game, near-zero
pledge, ₹5,000 Cr floor — every condition ANDed. That is textbook SEPA.

**2. CATALYST is gated by RFF — a survival test — and checks NO growth parameter.**
Not sales, not profit growth, not margins, not ROE, no size floor, no pledge, no
ownership. A ₹600 Cr micro-cap with flat sales, 40% pledged promoter holding and ROE of
6% passes the Catalyst gate provided it is profitable with decent coverage. The same name
is rejected outright by every Bull screen.

**3. PULLBACK is the weakest of the four.** BFF asks the right *kind* of question
(growth) but requires only **2 of 5** checks, and checks nothing on leverage, ownership,
pledge, size or cash flow. At the ≥ 2 floor a name can pass on "profitable + margin
expanded" alone with negative sales and profit growth.

**4. RECOVERY is the most gated book, and it is internally coherent.** The screener.in
Recovery screens are the RFF checks near-verbatim — NI > 0, OCF > 0, ICR > 2, D/E < 2,
CR > 1, ROA > 5, ROCE > 15 — and then the engine applies RFF again at ICR > 3.5. Nothing
about that is "relaxed"; it is the same test twice, the second time stricter.

**5. The quality floor collapses left to right.** Market cap ₹5,000 Cr (Bull, Recovery) →
turnover ₹5 Cr (Catalyst) → turnover ₹2 Cr and price ₹20 (Pullback). Pledge < 5% (Bull) →
unchecked everywhere else. This is the single largest divergence in the table, and it is
not a fundamental-engine question at all — it is a universe question.

---

## 2 · TECHNICAL parameters

| parameter | BULL (Chartink 1-4) | RECOVERY (Chartink 5-7) | CATALYST | PULLBACK |
|---|---|---|---|---|
| Stage / 30W MA | close > 30W MA, **30W rising** (Hunter) | — (below 200 SMA is the premise) | Stage from the 2×2; POS needs Stage 1-2 | **Stage 2 only** |
| MA stack | 50 > 150 > 200 (Hunter) | 50 ≥ 200×0.92 (EARLY) | trend template inside `weinstein_setup` | close > **rising** 200 SMA |
| vs 200 SMA | **above** | above (RS/EARLY) · **below ×0.95** (CB) | per catalyst | **above** |
| vs EMA20 | above (Hunter) · pullback to ×1.015 (PB) | — | per catalyst | **ext ≤ 1.5 ATR** |
| Mansfield RS | screen-implied | **RS line > 30W SMA** | RS in Alpha (status) | **> 0** |
| Weekly RSI | **> 50-55** | **> 50-55** (RS/EARLY) | replaced by price action | — |
| Daily RSI | > 60 (Leaders) | **< 55** (CB) | replaced by price action | — |
| ADX | > 20-25 | — | up-bar count (PA) | — |
| Distance from 52W high | within 15% (Hunter) | **10-40% off** | — | — |
| Depth off recent high | ≤ 15% (PB) | — | — | **2-18% off 20d high** |
| Volume | > 20W avg · < 10D avg (PB) · > 2× 1M avg (Leaders) | 1.25× confirm | RV per catalyst | **< 2.5× (climax reject)**, dry-up scored |
| Breakout / trigger | 20-day high (EB) | 15-20D pivot | **catalyst must fire** | **none — location only** |
| Stop / risk | — | — | — | **≤ 8% of entry** |
| Price floor | ₹20 (₹200 via screen) | ₹100 | — | ₹20 |
| Market regime | — | regime gate | SWG-PB needs `mkt_bull` | — |

### What this table says

**Pullback Finder is the only source with no trigger requirement** — by design; it
answers *where*, not *when*. It is also the only one with a **risk ceiling**.

**Catalyst is the only source that demands a firing event.** Everything else is a state
description; Catalyst requires a transition.

**Recovery's technical premise is the inverse of Bull's** (10-40% off the high, below the
200 SMA for CB) — which is why it needs a different fundamental test, and why RFF is
correct *there*.

---

## 3 · The comparison, stated plainly

| | asks | fundamentally | technically |
|---|---|---|---|
| BULL | "a great business breaking out" | growth + quality + governance + size | strong trend |
| RECOVERY | "a survivor on sale" | survival + returns | corrected, turning |
| CATALYST | "something just fired" | **survival only** | a firing event |
| PULLBACK | "sitting at value" | **growth, 2 of 5** | at value, no trigger |

**The two bull-family surfaces (Catalyst, Pullback) apply weaker and differently-shaped
fundamental tests than the Bull scans they descend from.** Catalyst has the wrong shape
(survival, no growth). Pullback has the right shape but a low bar and no
leverage/ownership/size leg.

Both were built to widen supply after the Chartink+screener.in funnel proved too narrow —
Catalyst on 6 Jul, Pullback on 31 Jul. Widening the *universe* was the intent. Weakening
the *fundamental standard* was a side effect, and it happened without a decision.

---

## 4 · The screener.in screens, verbatim

Fetched live 13 Aug 2026. Reproduced here so a change to a screen is visible as a diff.

**Stage2_Hunter** — `screens/3454433`
```
Market Capitalization > 5000 AND YOY Quarterly sales growth > 15 AND
YOY Quarterly profit growth > 20 AND Return on capital employed > 15 AND
Return on equity > 15 AND Debt to equity < 1 AND
(Promoter holding > 40 OR FII holding > 15 OR DII holding > 15) AND
Pledged percentage < 5 AND Down from 52w high < 25 AND Current Price > 200
```

**Stage2_Pullback** — `screens/3440648`
```
Market Capitalization > 5000 AND Return on equity > 15 AND
Return on capital employed > 15 AND NPM last year > 10 AND
Debt to equity < 0.5 AND Promoter holding > 40 AND
Down from 52w high < 20 AND Down from 52w high > 5 AND
Pledged percentage < 5 AND Volume 1week average > 100000
```

**Early_Birds** — `screens/3440667`
```
Market Capitalization > 5000 AND YOY Quarterly sales growth > 10 AND
YOY Quarterly profit growth > 15 AND Current Price > 50 AND
Debt to equity < 1.5 AND Change in Promoter holding > 0 AND
(Promoter holding > 40 OR FII holding > 15 OR DII holding > 15) AND
Operating cash flow 3years > 0
```

**Strong_Leaders** — `screens/3440684`
```
Market Capitalization > 5000 AND YOY Quarterly sales growth > 20 AND
YOY Quarterly profit growth > 25 AND
EPS latest quarter > EPS preceding year quarter AND Pledged percentage < 2 AND
volume > 2 * Volume 1month average AND
(Change in FII holding > 0 OR Change in DII holding > 0) AND
Volume 1week average > 100000 AND Return on capital employed > 15%
```

**Recovery_RS_Survivors** — `screens/3591202` · **Recovery_Early_Birds** — `screens/3591222`
(identical but for `Down from 52w high` 15 vs 20)
```
Current price > 100 AND Current price > DMA 200 AND Current price > DMA 50 AND
Down from 52w high < 15 [EB: < 20] AND RSI > 55 AND
Net profit > 0 AND Cash from operations last year > 0 AND
Interest Coverage Ratio > 2 AND Debt to equity < 2 AND Current ratio > 1 AND
Return on assets > 5 AND Return on capital employed % > 15 AND
Market Capitalization > 5000
```

**Recovery_Climax_Bounce** — `screens/3591217`
```
Current price > 100 AND Current price < DMA 200 AND Down from 52w high < 30 AND
RSI < 55 AND Net profit > 0 AND Cash from operations last year > 0 AND
Interest Coverage Ratio > 2 AND Debt to equity < 1 AND Current ratio > 1 AND
Return on assets > 5 AND Return on capital employed % > 20 AND
Market Capitalization > 5000
```

⚠️ **Note the collision:** `Recovery_RS_Survivors` demands `Down from 52w high < 15`
while its Chartink partner demands `close < 250-day high × 0.90`, i.e. **more than 10%
off**. The two sides agree only in the narrow 10-15% band. `Recovery_Early_Birds` has the
same structure at 10-20%. This is why those recovery inner joins are so lossy (RS
Survivors kept 10 of 51 on 12 Aug) — not fundamental strictness, a **band mismatch**.

---

## 5 · What changed from the first version of this document

| first version said | corrected |
|---|---|
| "the bull fundamental standard is unstateable from the code" | **Wrong** — every screen is readable at its URL, now reproduced above. |
| "three fundamental engines, not applied by path" | **Stands, and is sharper**: the Bull screens are a *growth* standard, ≈ BFF's own thresholds (sales 15 / profit 20 / ROCE 15). So BFF is the engine that matches the Bull path, and RFF-on-Catalyst is the outlier — now provable rather than argued. |
| — | **New**: the biggest gap is not the engine at all, it is the **₹5,000 Cr market-cap floor** the Bull and Recovery books enforce and Catalyst and Pullback do not. |

---

## 6 · Still not measured

- Whether RFF-gated catalysts outperform BFF-gated ones.
- Whether the ₹5,000 Cr floor helps or hurts on this book.
- Whether the 131 names (73%) the inner join discards underperform.

No forward-return test partitions on any fundamental field. Every option below is a
judgement until one does.

## 6a · MEASURED — the BFF gate, 14 Aug 2026

The partition §6 said nobody had run. `fundamental_gate_partition.py --col BFF_Base`
on `validation_20260809_191508` (519 POS trades, 60/120/180d windows), with BFF
reconstructed **point-in-time** from screener.in's `#quarters`/`#ratios` history
(`screener_history.py` → `fundamental_replay.bff_as_of`). **431 of 519 resolved (83%).**

| BFF | n | mean α | median | win |
|---:|---:|---:|---:|---:|
| 1 | 62 | −0.12 | −1.84 | 29% |
| 2 | 100 | −0.33 | −2.06 | 26% |
| 3 | 127 | −0.08 | −2.39 | 27% |
| **4** | 109 | **+1.14** | −2.32 | 32% |
| **5** | 28 | **+1.01** | −1.21 | 43% |

Split at ≥ 4: hi **+1.12%** / 34% win · lo **−0.19%** / 27% · edge **+1.31pp** ·
symbol-block CI95 **[−0.67, +3.06]** · IS +1.50pp → OOS +1.20pp (80% retained) ·
per-anchor hi **+2.47** vs lo **−0.46**, hi wins **11/17**.

**DECISION (Jay): keep BFF ≥ 4.** Defensible, not proven.

FOR: the edge **persists OOS** at 80% retention, clearing the ≥50% bar in the
sweep protocol that killed most previous additions. It is a **threshold effect,
not a gradient** — 1/2/3 are indistinguishable, then 4/5 jump — which is the
shape a GATE should have, and why the near-zero Spearman (−0.012) is not the
indictment it looks like. The **portfolio-level** gap (+2.47 vs −0.46) is wider
than the trade-level one.

AGAINST: **the CI straddles zero**, and it is materially weaker than RFF:

| | edge | CI95 | IS → OOS |
|---|---:|---|---|
| RFF ≥ 5 | +2.40pp | [+0.92, +3.88] ✅ | +1.01 → +4.52 |
| BFF ≥ 4 | +1.31pp | [−0.67, +3.06] ❌ | +1.50 → +1.20 |

**Do NOT raise to 5** — n=28. **Every bucket's median is negative** (−1.2 to −2.4):
BFF shifts the mean, it does not change the big-winner-carried shape of the book.

⚠️ **Coverage is uneven and the OOS half is the THINNER one** — 100% across
2024-10 → 2025-06, but 30–85% from 2025-07 on. So the OOS persistence rests on a
partially-sampled cohort and is weaker than the headline implies. (A coverage
re-check also hit screener.in DNS failures, so recent-anchor loss is part network,
part history depth — not cleanly separable.)

---

## 7 · Options

**A · Give the bull family one fundamental standard.** BFF on Catalyst and Pullback,
RFF on Recovery. Raises Pullback's floor from 2/5 and replaces Catalyst's survival test
with a growth test. Changes what the Catalyst list admits → measure before/after.

**B · Add the missing legs to BFF** — market cap, pledge, promoter/institutional holding,
D/E. These are the Bull screens' own conditions and they are cheap (already in the
screener.in row BFF fetches). This closes most of the gap without touching the engine
choice.

**C · Fix the recovery band collision** in §4 — Chartink and screener.in disagree on the
drawdown window, which is throttling the recovery joins for no stated reason.

**D · Leave it.** Every path is gated. Nothing measured says the differences cost
anything.

---

## 8 · PROPOSED parameter table

### 8.0 · First, a correction to §1

§1 called the missing **₹5,000 Cr market-cap floor** on Catalyst and Pullback "the
single largest divergence". Measured on today's 20-name Catalyst list, **every name is
already above ₹12,835 Cr** — smallest ACE ₹12,835 Cr, median ~₹30,000 Cr. The floor is
**not binding**. It is a real gap in the *code* and a non-event in the *output*, because
the technical gates (turnover ≥ ₹5 Cr, Stage 2, RS, alpha) already select large caps.

So a market-cap floor on Catalyst is **insurance, not a filter** — worth having so a
regime that surfaces micro-caps cannot slip through, worth nothing today. Unmeasured for
Pullback, which reaches lower (₹2 Cr turnover, ₹20 price) and is where a floor could
actually bind.

### 8.1 · The design

**Jay's ruling (13 Aug 2026), which sets the trade-off:** *"I'm ok to have fewer results
from GM+S4, rather than having a huge list of unreliable results."*

That resolves the tension every version of this document kept hedging on. The earlier
draft proposed *loosened* common thresholds (pledge < 10, mcap ≥ ₹2,000 Cr) to protect
supply. **Supply is not the objective.** So the proposal below aligns the bull family to
the Bull screens' OWN standard — the one Jay wrote, the strictest in the system — rather
than to a diluted version of it.

Two tiers. Governance, solvency and size are not style-dependent; growth-vs-survival is.

| # | parameter | BULL | RECOVERY | CATALYST | PULLBACK |
|---|---|---|---|---|---|
| **TIER 1 — common core, at BULL-screen strength everywhere** |
| 1 | Net profit > 0 | keep | keep | keep | keep |
| 2 | Pledged % | < 5 keep | **< 5** ADD | **< 5** ADD | **< 5** ADD |
| 3 | Market cap | ≥ ₹5,000 Cr keep | ≥ ₹5,000 Cr keep | **≥ ₹5,000 Cr** ADD | **≥ ₹5,000 Cr** ADD |
| 4 | Promoter > 40% *or* FII/DII > 15% | keep | **ADD** | **ADD** | **ADD** |
| 5 | Turnover | via screen | via screen | ≥ ₹5 Cr keep | **≥ ₹5 Cr** (was 2) |
| 6 | Price floor | ₹200 / ₹50 keep | ₹100 keep | **₹100** ADD | **₹100** (was 20) |
| **TIER 2 — path engine** (the question each book is entitled to ask) |
| 7 | engine | screener.in growth screens | **RFF ≥ 4/6** keep | **BFF ≥ 4/5** *(was RFF)* | **BFF ≥ 4/5** *(was 2)* |
| 8 | sales growth | > 10-20% | — | ≥ 15% via BFF | ≥ 15% via BFF |
| 9 | profit growth | > 15-25% | — | ≥ 20% via BFF | ≥ 20% via BFF |
| 10 | ROCE | > 15% | > 15-20% | ≥ 15% via BFF | ≥ 15% via BFF |
| 11 | ROE | > 15% | — | **≥ 15%** ADD | **≥ 15%** ADD |
| 12 | Debt / equity | < 0.5-1.5 | < 1-2 | **< 1.5** ADD | **< 1.5** ADD |
| 13 | margin expansion | — | — | via BFF | via BFF |
| 14 | solvency (ICR/CR/ROA/FCF) | — | **RFF, full** | — | — |
| **TIER 3 — path-specific, unchanged** |
| 15 | drawdown premise | within 15-25% of high | **10-40% off** | — | 2-18% off 20d high |
| 16 | trigger required | breakout clause | signal ≥ 2 | **catalyst fires** | **none (location)** |
| 17 | risk ceiling | — | — | — | ≤ 8% |

**Changes from today:**

| change | rationale | measured cost |
|---|---|---|
| Catalyst: RFF → **BFF ≥ 4** | it is a bull book and today checks NO growth parameter | **8 of 20 dropped** — 12 pass ≥ 4, 14 pass ≥ 3, 20 pass ≥ 2 |
| Pullback: BFF **2 → 4** | at 2/5 a name passes on "profitable + margin expanded" with negative growth | unmeasured — needs a full run |
| **pledge < 5%**, **mcap ≥ ₹5,000 Cr**, **promoter/institutional**, **ROE ≥ 15%**, **D/E < 1.5** on Cat + PB | these are the Bull screens' own conditions; the bull family should meet the bull standard | mcap: **zero today** (§8.0). Others unmeasured — fields not yet fetched. |
| Pullback price ₹20 → **₹100**, turnover ₹2 Cr → **₹5 Cr** | the ₹20/₹2 Cr floor is the loosest in the system and admits names no other book would look at | unmeasured |
| Recovery: add pledge/promoter | the only Tier-1 legs it lacks | unmeasured |

**Still deliberately NOT proposed:**

- **Solvency legs (ICR/CR/ROA/FCF) on the bull family.** That is RFF's job and the exact
  mismatch this table removes — a high-growth leader mid-capex can fail ICR > 3.5.
  Re-adding them under another name recreates the problem.
- **Bull screens tightened.** They are already the standard everything else is being
  raised to.

### 8.2 · Implementation cost, stated honestly

| item | status | order |
|---|---|---|
| BFF ≥ 4 on Pullback | one CONFIG value | **1** |
| Pullback price ₹100 / turnover ₹5 Cr | two CONFIG values | **1** |
| BFF instead of RFF on Catalyst | ~15 lines in `run_pipeline.py:406-425`, same shape as the existing RFF block | **2** |
| **pledge %**, **market cap**, **promoter / FII / DII holding**, **D/E** | **NOT currently fetched.** `_fetch_screener_bff_row` returns 7 keys only: Net profit, OPM_Now, OPM_Prev, ROCE, ROE, profit_growth, sales_growth. ROE is already there; the rest need a parser extension against the screener.in company page (all four are on it — top ratios + shareholding). | **3** |

Phase 1 and 2 are config-and-a-block. Phase 3 is one parser extension in
`_fetch_screener_bff_row` that unlocks five parameters at once — worth doing as a single
piece of work rather than five.

**Sequencing note:** BFF's ≥ 4 threshold currently means "4 of 5 growth checks". Once
pledge/mcap/holding/D-E join the check set, `min_bff_score` must be re-based or the
meaning of "4" silently changes. Better: keep BFF as the 5-check growth score and add
the Tier-1 legs as **separate hard gates** beside it, so each one's contribution stays
readable in the log.

### 8.3 · The honest caveat, and what it does not excuse

**No forward-return test partitions on any fundamental field.** So this table is
*coherent* — each book asks the question its premise entitles it to ask, and the bull
family is held to the bull standard — but coherence is not proven edge.

Given Jay's ruling that fewer/reliable beats many/unreliable, the asymmetry matters more
than the uncertainty: a stricter gate that turns out not to add alpha costs some missed
trades; a loose gate that admits weak businesses into a positional book costs capital in
names he would never have picked by hand. Those are not symmetric, and the ruling says
which side to err on.

The measurable version remains worth running, and would settle the *engine* question
specifically: take the existing `validation.py` bull runs, score each pick's BFF and RFF
at its anchor date, and partition matched-horizon alpha by both. If BFF separates and RFF
does not, §8.1's core swap is confirmed rather than argued.

**Recommended order: ship Phase 1 (config only, reversible), run the partition, then
decide Phase 2-3 on the result.**

Related: `11_Bull_Screener_v3_3_Guide.md` · `09_Recovery_Screener_v2_1_Guide.md` ·
`23_Golden_Matcher_Guide.md`
