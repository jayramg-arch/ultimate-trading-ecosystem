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

Related: `11_Bull_Screener_v3_3_Guide.md` · `09_Recovery_Screener_v2_1_Guide.md` ·
`23_Golden_Matcher_Guide.md`
