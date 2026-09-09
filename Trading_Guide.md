# The Trading Guide — Golden Matcher + S4 Entry Trigger

The end-to-end playbook for taking a name from a weekend scan to a live order, using the two tools together:

- **Golden Matcher (GM)** — *qualifies* which names to be ready for, and **arms** them.
- **S4 Entry Trigger (S4)** — *times* the exact bar and gives the **GO**.

This guide assumes the house DNA: **Weinstein stage analysis** (30-week MA anchor), **Minervini/VCP** growth selection, **Mansfield RS** vs Nifty 50/500/sector, **ATR-based stops**, **1% capital risk max (0.25% house default per trade)**, NSE, INR (₹1,23,456), trading hours 9:15 AM–3:30 PM IST.

---

## 1. The Funnel — Scanner → Scope → Sniper

```
┌── SCANNER ──────────┐   ┌── SCOPE ──────────────┐   ┌── SNIPER ────────────┐   ┌── EXECUTE ──┐
│ Chartink + Screener │ → │ Golden Matcher        │ → │ S4 Entry Trigger     │ → │ Order + GTT │
│ watchlists (Hunter, │   │ 6 gates → ARM the name│   │ GO = PA·Loc·Vol·Bar  │   │ 0.25% risk  │
│ EarlyBird, Pullback,│   │ "TRIGGER LIVE / ARMED"│   │ (the exact bar)      │   │ ATR stop    │
│ Leader, Recovery)   │   │                       │   │                      │   │             │
└─────────────────────┘   └───────────────────────┘   └──────────────────────┘   └─────────────┘
     QUALIFY (broad)            QUALIFY + ARM (focus)         TIME (the trigger)        the trade
```

**Three questions, three tools:**
1. *Which universe of names is worth watching?* → **Scanners** (the paid Chartink + Screener.in watchlists).
2. *Which of those is set up and armed right now?* → **Golden Matcher** (verdict + the Trigger Board).
3. *Is THIS the bar to buy?* → **S4 Entry Trigger** (the GO).

Never skip a stage. The scanner is the universe; the GM is the shortlist; S4 is the trigger. Each narrows the last.

---

## 2. The Two-Stage Discipline (the core idea)

The GM and S4 deliberately fire at **different moments** — this is a feature, not a bug:

| Stage | Tool | Signal | What you do |
|---|---|---|---|
| **Arm** | Golden Matcher | **TRIGGER LIVE / ARMED** (a PA pattern appeared, or all gates are good) | Put the name on the S4 chart, set the alert, **focus** |
| **Fire** | S4 Entry Trigger | **GO** (PA **at a location, with volume, on a clean bar**) | Confirm the closed bar → **buy-STOP above its high** |

> **The GM arms you early so you focus; you wait for the S4 GO to pull the trigger.** Don't act on the GM arm alone, and don't expect the GM board's "S4-GO 4/4" column to be identical to the live S4 chart — the S4 chart is **final**.

---

## 3. Weekly & Daily Cadence

| When | Do |
|---|---|
| **Weekend** | Run the scanners (Hunter / EarlyBird = fresh Stage-2 breakouts; Recovery = beaten-down turns). Run the GM Trigger Board on the union. Build the week's shortlist of **ARMED** names; export to a TradingView watchlist. |
| **Weekday pre-open** | Refresh the board; note which shortlisted names are **ARMED** / **BUY-WATCH**. Apply S4 to each; set/refresh the **"S4 GO"** alerts on 75m & 125m. |
| **Weekday (Pullback)** | Tactical entries — Pullback names retracing into a zone. Watch the S4 chart for the GO. |
| **Post-close** | Journal fills; run the daily journal↔Dhan sync; review exits (Risk Shield / Pyramid). |

---

## 4. Bull Path — the workflow, gate by gate

For a Stage-2 leader / breakout / pullback. Walk the GM's six steps:

1. **CONTEXT** (hard) — Weekly **Stage 2**, above a **rising 30-WMA**, **RS > 0** vs Nifty 500, regime BULL. *(Accumulation names: Stage 1/2 base above the 200-DMA with RS.)* Fail → **SKIP**.
2. **QUALITY** (hard) — **Alpha ≥ 50** and **Minervini ≥ 5/8** (leadership). BFF (fundamentals) is *status only*. Fail → **WATCHLIST**.
3. **SETUP** (soft) — a live catalyst / valid VCP base. No catalyst is a **caveat**, not a stop (a fired trigger still buys).
4. **LOCATION** (soft) — **above EMA20 (daily) but not extended** (≤ the ATR ceiling above it), **above CPR+VWAP value**, **R:R ≥ 2**. Weak location → wait for a pullback toward EMA20 / a fresh zone (unless the trigger fires).
5. **TRIGGER** — on the **75/125m** chart, wait for a **closed-bar PA pattern at the zone** (VCP-BO, Pocket, 3-Bar, Undercut, Spring, IB-NR7…). This is where the GM says **BUY — TRIGGER LIVE**.
6. **EXECUTE** — buy-STOP above the trigger bar's high, **structural SL** (nearest fresh zone distal, capped at 3× ATR), size at **0.25%**, place the GTT.

**Then switch to S4** for the precise GO (§6).

---

## 5. Recovery Path — the workflow, gate by gate

For a beaten-down name turning up. The gates change (a recovery name fails "Stage 2" by definition):

1. **CONTEXT** — **beaten down ≥ 10%** off the 52-week high, recovery regime open.
2. **QUALITY** (hard) — **RFF ≥ 4/6** and quality ≠ INSUFFICIENT. *Only **fundamentally strong** beaten-down names — quality on sale, not a falling knife.*
3. **SETUP** — a recovery catalyst fired (**Signal ≥ 2**: Climax-Bounce / RS / Early / Wyckoff).
4. **LOCATION** — the turn is **confirmed** and price isn't **chased** far above the recovery entry.
5. **TRIGGER** — a closed-bar **recovery PA** pattern (Climax, Spring, Higher-Low/2B, Base-BO, 30-WMA reclaim…).
6. **EXECUTE** — the recovery engine's Entry/SL/T1/T2 plan.

> Recovery is **fundamentals-first**; Bull is **technical-leadership-first**. Trade recovery off the **Python** engine (Pine's RFF is a platform-limited "Lite" version).

---

## 6. Timing the entry on S4 — the GO

Once the GM has **armed** a name, switch to the S4 Entry Trigger on the chart (apply on **75m**, the default trigger TF):

1. **Set the mode** — Auto usually resolves correctly; if the GM pathed it Recovery but S4 Auto shows Bull (or vice-versa), **set S4 Mode manually to match the GM path** (Pine can't see the GM's live decision).
2. **Confirm the location** — the S4 **Support Zone / Zones (MTF)** row should show price *at* a fresh demand zone (the S4 IZE zones are richer than the GM's proxy).
3. **Wait for GO** — the **TRIGGER** row must read **GO**: a PA pattern (**P**) at a location (**L**) with volume (**V** — RV ≥ 1.0) on a clean bar (**B**). A coil (NR7) is *compression*, not a trigger; a dead-volume reclaim (RV < 1) is a skip.
4. **Read the VERDICT** — S4's swing-vs-positional ruling: **swing needs ≥ 2.0R**, **positional needs ≥ 20% ROI to T1**. If NEITHER GATE, the entry may be clean but the trade isn't worth the risk.
5. **Check Arrival · Δ** (v4.0) — a **FAST** arrival into demand with **absorbing Δ+** is the highest-quality tap; a **GRIND** arrival with **bleeding Δ−** is a caution (momentum absorbing the level).
6. **Act on the alert ping, not the touch** — the "S4 GO" alert fires once per bar close.

---

## 7. Confirmation before entry — the #1 discipline

**The single most common mistake is entering at the zone on the touch, skipping confirmation.** The fix is mechanical:

> **Alert → wait for the CLOSED trigger bar → place a buy-STOP above its high.** Never a buy-limit *at* the zone.

A zone touch is *location*. A closed pattern bar with volume is the *trigger*. Confirmation is the missing catalyst between "price is here" and "buy." The chart retains **veto power** — it can talk you *out* of a trade, never *into* one.

---

## 8. Risk, sizing & stops

- **Position size** — Risk per trade = **0.25%** of capital (house default; 1% hard ceiling). `Qty = Capital × Risk% / (Entry − SL)`. The GM sizer and the S4 Qty row both compute this from the plan's own Entry/SL.
- **Stop-loss** — **structural first**: the nearest fresh demand-zone **distal** below entry (the invalidation), with a **0.25% buffer** below it to survive wick-hunts, **capped at 3× ATR** so a stop is never absurdly far. Else EMA20 dynamic support. **ATR-based, non-discretionary.**
- **Targets** — T1 = nearest overhead (supply zone / flipped pivot / 52W high); require **R:R ≥ 2** for a swing.
- **No Stage 3/4 holds** — exit names that roll into Stage 3/4 (the Sell-to-Buy rotation matrix frees the capital into the top-conviction armed names).

---

## 9. A worked example (the flow)

1. **Weekend:** the Hunter scan surfaces *WOCKPHARMA*. It lands on the GM board with archetype **Breakout**, `★` (top-conviction).
2. **GM:** verdict **ARMED · AWAIT TRIGGER** — Stage 2, Alpha 8.5-class, RS positive, above EMA20, R:R 2.4. Board S4-GO reads `3/4 · no PA` (armed, waiting for the pattern). You add it to the S4 watchlist and set the "S4 GO" alert (75m).
3. **Weekday:** price pulls back to a fresh daily demand zone. On the **75m** S4 chart, a **Pocket Pivot** fires at the zone on RV 1.4, closing strong. The S4 **TRIGGER** row flips to **GO  P✓ L✓ V✓ B✓  Bull-only  8/13**, Arrival reads **FAST · absorbing Δ+**. VERDICT: *SWING — clears 2R*.
4. **Execute:** buy-STOP above the trigger bar's high; SL at the zone distal (−1.9%, structural); Qty from 0.25% risk; GTT placed. Journal logs the OPEN with the entry snapshot.

---

## 10. What each tool decides — and does NOT

| Decision | Scanner | Golden Matcher | S4 Entry Trigger |
|---|---|---|---|
| Is it in my universe? | ✅ | — | — |
| Stage / RS / leadership (Context+Quality) | partial | ✅ | — (reads structure) |
| Catalyst / setup archetype | ✅ (qualifies) | ✅ (times) | — |
| Location (at a zone?) | — | ✅ (proxy/IZE) | ✅ (full IZE zones — final) |
| The exact entry bar (GO) | — | previews (S4-GO col) | ✅ **final** |
| Stop / target / size | — | ✅ | ✅ |

**Golden rule:** the GM *arms*; **S4 is the final say on the trigger and the location**. If the two disagree, the S4 chart wins (set S4's mode to match the GM path first).

---

## 11. Pre-trade checklist

- [ ] Name came from a scanner (not a hunch)
- [ ] GM verdict = **ARMED** or **BUY — TRIGGER LIVE** (hard gates passed; Recovery: RFF ≥ 4)
- [ ] S4 mode matches the GM path (Bull/Recovery)
- [ ] Price **at a fresh demand zone** on S4 (not open space)
- [ ] S4 **GO**: P✓ L✓ V✓ B✓ (pattern · location · RV ≥ 1 · clean bar)
- [ ] VERDICT clears the house rule (swing ≥ 2R / positional ≥ 20% to T1)
- [ ] Arrival is FAST/absorbing (not GRIND/bleeding)
- [ ] **Closed** trigger bar confirmed → buy-STOP above its high (never buy the touch)
- [ ] Structural ATR-capped SL; size at 0.25%; GTT set
- [ ] Not a Stage 3/4 hold; portfolio correlation acceptable

---

## 12. Common mistakes → the fix

| Mistake | Fix |
|---|---|
| Entering on the zone touch | Wait for the **closed** trigger bar; buy-STOP above its high |
| Acting on the GM arm alone | The GM arms; wait for the **S4 GO** |
| Expecting board S4-GO = live S4 | It's a *predictor*; the S4 chart is final (mode/feed/staleness differ) |
| Trading a recovery on the pattern alone | Recovery needs **RFF ≥ 4** (fundamentally strong), not just a bounce |
| Chasing an extended breakout | Step-4 LOCATION: not > the ATR ceiling above EMA20; wait for a pullback |
| Discretionary stop | ATR-based structural stop only — no overrides |
| Holding into Stage 3/4 | Exit; rotate capital to armed top-conviction names |

---

*Pair this with the **Golden Matcher Guide** (the qualify/arm engine) and the **S4 Entry Trigger Guide** (the timing layer). The DNA above (Weinstein · Minervini/VCP · Mansfield RS · ATR stops · 0.25% risk · NSE/INR) governs every trade; the tools enforce it.*
