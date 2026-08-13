# 25 · Scanner Filter Map — every auto-pilot source, technical and fundamental

Built 13 Aug 2026 from the code, in response to: *"We initially started with Bull
scanners… strong technical and fundamental filters. Later we added Recovery… relaxed
the fundamental filters. Then Catalyst… I'm not sure whether they have any fundamental
filters. Now Pullback Finder, entirely bypassing fundamental filters. I'm not
comfortable with this approach."*

The concern is right that the standard drifted. It is wrong in one specific: **the
Catalyst list is hard-gated on fundamentals** (RFF ≥ 4/6, added 6 Jul 2026,
`run_pipeline.py:406-425`). The actual problem is not a missing gate — it is that
**three different fundamental engines are in use and they are not applied by path**.

---

## 1 · The map

| # | Source | Universe | Technical filter | Fundamental filter | Strength |
|---|---|---|---|---|---|
| 1 | **Stage 2 Hunter** | Chartink `{57960}` = N500 | 30W MA rising · close > 30W MA · 50>150>200 SMA stack · close > EMA20 · close > 200 SMA · within 15% of 52W high · weekly RSI > 55 · daily ADX > 20 · vol > 20W avg · ≥ ₹20 | membership in screener.in **Stage2 Hunter** screen | **HARD** (inner join) |
| 2 | **Stage 2 Pullback** | same | close > 30W MA · weekly RSI > 55 · low < EMA20×1.015 · close > EMA20 · vol < 10D avg · close > 200 SMA · range < prior range · ≥ ₹20 | screener.in **Pullback** screen | **HARD** (inner join) |
| 3 | **Early Birds** | same | weekly RSI > 50 · close > 50 SMA and < ×1.15 · weekly MACD cross up · prior signal < 0 · close > 20-day high · vol > 100k · ≥ ₹20 | screener.in **Early Birds** screen | **HARD** (inner join) |
| 4 | **Strong Leaders** | same | daily RSI > 60 · close > 20 SMA · ADX > 25 · vol > 20D avg · close > 200 SMA · ≥ ₹20 | screener.in **Leaders** screen | **HARD** (inner join) |
| 5 | **REV-RS** | same | Mansfield RS > 30W SMA · 10–40% off 52W high · close > 200 SMA · close > 50 SMA · weekly RSI > 55 · ≥ ₹100 | screener.in **RS Survivors** + **RFF ≥ 4/6** | **HARD ×2** |
| 6 | **REV-CB** | same | RS > 30W SMA · 10–40% off high · close < 200 SMA×0.95 · daily RSI < 55 · ≥ ₹100 | screener.in **Climax Bounce** + **RFF ≥ 4/6** | **HARD ×2** |
| 7 | **REV-EARLY** | same | 50 SMA ≥ 200 SMA×0.92 · 10–40% off high · close > 50 and 150 SMA · RS > 30W SMA · weekly RSI > 50 · ≥ ₹100 | screener.in **Recovery Early Birds** + **RFF ≥ 4/6** | **HARD ×2** |
| 8 | **Bull Catalyst** | nifty500, full | `bull_screener` catalyst gates (POS-BO · POS-ACCUM · SWG-BO · SWG-PB · SWG-GAP · SWG-REV) + Stage-4 swing-BO dropped | **RFF ≥ 4/6**, INSUFFICIENT blocked | **HARD** |
| 9 | **Recovery Catalyst** | nifty500 | `recovery_screener` pillars, Signal ≥ 2 · 15–35% drawdown band · regime gate | **RFF ≥ 4/6** (inside the engine) | **HARD** |
| 10 | **Pullback Finder** | nifty500, full | Stage 2 · close > rising 200 SMA · Mansfield > 0 · ext ≤ 1.5 ATR · depth 2–18% · ≥ 50 SMA×0.97 · vol < 2.5× · risk ≤ 8% · ≥ ₹2 Cr turnover | **BFF ≥ 2/5** (13 Aug 2026) | **HARD** |
| 11 | **Portfolio / Pyramid** | live holdings | `pyramid_logic` ADD rung only | none — already owned | n/a |

Sources 1–7 feed the matcher (`brute_force_match_pro`); 8–11 are direct CSV producers.
All eleven feed the Trigger Board, which inherits their qualification and only times it.

---

## 2 · The three fundamental engines

| engine | asks | checks | where it is HARD | where it is soft |
|---|---|---|---|---|
| **screener.in screens** | "is it in my saved screen?" | *unknown to the codebase* — see §3 | sources 1–7 | — |
| **RFF** (`recovery_screener.get_rff`) | "will it survive?" | NI > 0 · FCF > 0 · ICR > 3.5 · D/E < 2 · CR > 1 · ROA > 5% | sources 5–9 | — |
| **BFF** (`bull_fundamental_filter`) | "is it growing?" | profit growth ≥ 20% · sales growth ≥ 15% · margin expansion · ROCE ≥ 15% · profitable | source 10 | **Bull path GM QUALITY — display only** |

### The mismatch worth deciding on

**RFF is a survival test; BFF is a growth test.** They answer different questions and
they were built for different books — RFF for beaten-down names whose tape you cannot
trust, BFF for Minervini leaders where the market has already voted.

Today:

- The **Bull Catalyst** list — POS-BO breakouts, the core positional edge — is gated by
  **RFF**, the recovery/balance-sheet filter. A high-growth leader carrying debt from a
  capex cycle can fail ICR > 3.5 or D/E < 2 and be dropped, while a low-growth, cash-rich,
  ex-growth company passes cleanly. That is the opposite of SEPA.
- **BFF**, the growth filter actually built for the bull path, is **display-only** there.
- **Pullback Finder** — also a bull setup — now uses **BFF**, not RFF.

So two bull surfaces are gated by two different engines, and the one designed for bull
is the one that does not gate. This is drift, not design.

---

## 3 · The unauditable part

The fundamental criteria for sources 1–7 are **not in this repository.** They are saved
screens in Jay's screener.in account, fetched by URL:

| screen | URL |
|---|---|
| Stage2 Hunter | `screener.in/screens/3454433/stage2-hunter-final/` |
| Pullback | `screener.in/screens/3440648/pullback-fundamentals-jay/` |
| Early Birds | `screener.in/screens/3440667/early-birds-fundamentals-jay/` |
| Leaders | `screener.in/screens/3440684/leader-fundamentals-jay/` |
| RS Survivors | `screener.in/screens/3591202/rs-survivors/` |
| Climax Bounce | `screener.in/screens/3591217/climax-bottom-bounce/` |
| Recovery Early Birds | `screener.in/screens/3591222/recovery-early-birds/` |

Consequences, in order of how much they matter:

1. **Nobody can state the bull fundamental standard from the code.** The strongest claim
   available is "it passed a screen Jay wrote at some point."
2. **The join is invisible as a gate.** Measured 13 Aug: it discards **131 of 180 (73%)**
   technical picks, including BOSCHLTD, TITAN, SIEMENS, INDIGO, ICICIBANK, HAL,
   ABBOTINDIA. A dropped name is *never scored* — absent and rejected look identical.
   Now logged per target (`logs/matcher_join_drops.csv`).
3. **Editing a screen silently re-gates the pipeline** with no diff, no version, no note.
4. **An expired cookie degrades to a smaller master**, which reads as a market with fewer
   qualifying names rather than as a fetch failure.

---

## 4 · Answering the original worry directly

| Jay's statement | Verdict |
|---|---|
| "Bull scanners had strong technical AND fundamental filters" | **True** — but the fundamental half is a screener.in screen nobody can read from here. |
| "Recovery relaxed the fundamental filters" | **False, inverted.** Recovery is the *most* gated book: a screener.in screen **and** RFF ≥ 4/6 with INSUFFICIENT blocked. RFF was raised 1 → 4 on 4 Jun 2026 on Jay's own instruction. |
| "Not sure whether Catalyst has any fundamental filters" | **It does** — RFF ≥ 4/6 hard, `run_pipeline.py:406`, added 6 Jul 2026. |
| "Pullback Finder entirely bypasses fundamental filters" | **Was true until 13 Aug 2026.** Now BFF ≥ 2/5 hard. |

**So the book is more gated than it felt — and less consistent than it should be.**
Every path has a hard fundamental gate. No two bull paths use the same one.

---

## 5 · Options, in the order I would take them

Nothing here is shipped. Each is a decision, and none should be taken on the strength of
this document alone — the standing rule on this system is that six of the last six
additions were rejected by measurement.

**A · Decide the bull fundamental standard, then apply it to every bull surface.**
The cheapest coherent version: **BFF for bull (catalyst + pullback + Chartink bull),
RFF for recovery.** Each engine then gates the book it was designed for. This would
change what the Catalyst list admits, so it needs a measured before/after, not a flip.

**B · Make the screener.in criteria explicit.** Either transcribe each screen's
conditions into a comment block beside its URL (cheap, manual, drifts), or replace the
join with an in-code fundamental gate (BFF/RFF) so the standard is versioned with the
code. The second removes the 73% invisible drop as a side effect.

**C · Report the fundamental funnel every run, per source.** The join-drop log does this
for sources 1–7; RFF gating already logs a kept/dropped line; BFF now reports weak vs
unreadable separately. Missing: one consolidated line so the whole funnel is legible in
one place.

**D · Leave it.** Defensible: every path *is* gated, and the inconsistency has not been
shown to cost anything. The honest position is that no measurement currently
distinguishes "RFF on bull" from "BFF on bull" in forward returns.

---

## 6 · What is NOT measured

- Whether RFF-gated bull catalysts outperform BFF-gated ones. **Nobody knows.**
- Whether the 131 names the join discards underperform. **Nobody knows** — the
  count is measured, the consequence is not.
- Whether any fundamental gate improves matched-horizon alpha on this book at all.
  The bull validation runs were never partitioned by fundamental score.

Related: `11_Bull_Screener_v3_3_Guide.md` · `09_Recovery_Screener_v2_1_Guide.md` ·
`23_Golden_Matcher_Guide.md`
