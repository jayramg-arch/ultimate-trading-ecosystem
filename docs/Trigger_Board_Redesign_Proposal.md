# Trigger Board Redesign — "Screen Once → Time Continuously"

**Status:** PROPOSAL (for review — not yet implemented)
**Date:** 12 Jul 2026
**Author:** Jay + Claude

---

## 1. The problem (why the current design is flawed)

Today the Golden Matcher / Trigger Board takes a **union of watchlists** and runs
each name through **one uniform funnel** (`compute_workflow`) that **re-derives**
Context → Quality → Setup and then **hard-vetoes on a live catalyst** (Step-3).

Consequences:
- The catalyst is re-derived live per symbol and **overrides** why each name was
  selected. A name only becomes actionable if it is *firing a `bull_screener`
  catalyst at that instant*.
- The **catalyst scan already sweeps the universe** for firing names, so every name
  that can pass Step-3 is already in the catalyst list → the **rigorous
  (Chartink + Screener.in) watchlists contribute no new actionable names.** Their
  non-catalyst names dead-end at "BUY-WATCH · no catalyst."
- Net: **only the Nifty-500 catalyst scan drives actionable output.** The rigorous
  lists are reduced to a quality overlay, and their considerable selection work is
  thrown away.

**Root cause:** we discard the watchlist's *setup thesis* and re-qualify with a
single, stricter catalyst gate. Patching Step-3 (make the catalyst a status) is a
band-aid; the real fix is to stop re-qualifying at all.

---

## 2. The reframe

**A watchlist is not a bag of symbols — it is a QUALIFIED SETUP with a thesis.**

| Watchlist | Setup thesis | Path |
|---|---|---|
| Hunter | Stage-2 breakout candidate | Bull |
| EarlyBird | Fresh Stage-2 launch | Bull |
| Pullback | Pullback-in-uptrend | Bull |
| Leader | Leadership / RS momentum | Bull |
| Bull Catalyst | Live catalyst (POS-BO/ACCUM/SWG-*) | Bull |
| Recovery RS Survivors | RS-survivor recovery | Recovery |
| Recovery Climax Bounce | Climax reversal | Recovery |
| Recovery EarlyBirds | Early recovery turn | Recovery |
| Recovery Catalyst | Live REV-* / WYC-* signal | Recovery |
| Golden Matcher (FINAL_WATCHLIST) | Conviction-ranked union | Mixed |

Every name arrives **already carrying Context + Quality + Setup** — that is exactly
what Chartink + Screener.in (rigorous) or the catalyst scan established.

---

## 3. The better system: two clean layers

### Layer 1 — QUALIFICATION = the watchlists (already done)
Each name **inherits its setup thesis from its source.** The board does **not**
re-qualify. It runs only a lightweight **"still valid?"** guard to catch stale
membership (a name that qualified last week but has since broken down).

### Layer 2 — TIMING = the Trigger Board
The only things computed **live** are **Location** (R:R + EMA20 / zone) and
**Trigger** (PA fires) — the two layers already built. The board's job is to
**time** pre-qualified names, not re-screen them.

> **The doctrine: the watchlists QUALIFY; the board TIMES.** This is the natural
> end-state of the two-stage model (arm early, execute on the trigger).

---

## 4. Setup-aware timing (the sophistication)

Because the setup is now known, the board applies **setup-appropriate** location &
trigger logic instead of one uniform funnel:

| Archetype | Sources | Still-valid guard | Location (where) | Trigger (what fires) |
|---|---|---|---|---|
| **Breakout** | Hunter, EarlyBird, POS-BO, SWG-BO | Stage 2 · >30WMA · >200-DMA · RS+ | at/just above pivot; ≤ N ATR above it | breakout bar > pivot on volume (VCP-BO / Gap-BO / Breakout-Confirmed) |
| **Pullback** | Pullback, SWG-PB | Stage 2 · above **rising** 30WMA | into demand zone / **rising EMA20 support**; 38–62% retrace | reversal off zone (3-Bar / Hammer / Pocket / Engulf) + volume |
| **Accumulation** | EarlyBird, POS-ACCUM | Stage 1→2 · >200-DMA · RS turning · vol-accum | near base / 30WMA; not extended | Stage-2 launch (weekly 30WMA reclaim) / accum breakout |
| **Leader** | Leader | high RS · Stage 2 · >key MAs | at value (>CPR+VWAP, near EMA20); not extended | continuation (Pocket / IB-NR7 / VCP-BO) at value |
| **Recovery** | all Recovery lists, REV-*, WYC-* | beaten-down 15–35% · RFF≥4 · regime open · RS turning | **reclaiming EMA20** (resistance→support); ≤8% above | recovery PA (Climax reclaim / Spring / 2B / Base-BO / Hammer-at-support) at base |

All thresholds live in one tunable config per archetype.

---

## 5. The new per-name gate model

1. **Source → archetype** — inherited setup (union already tracks Sources).
2. **STILL VALID?** — a light break-down guard (Stage 4 / lost 200-DMA / lost 30WMA
   for the archetype). If broken → **INVALIDATED** (flag/drop). *Only* re-check;
   never a re-screen.
3. **LOCATION** — archetype-appropriate R:R + EMA20/zone. Status.
4. **TRIGGER** — archetype-appropriate PA + volume at location. The execution gate.
5. **Category = timing state** (never "no catalyst"):
   - `INVALIDATED` — broke down since watchlisted
   - `WATCH` — valid, not at location
   - `ARMED` — valid, at location, no trigger
   - `TRIGGER LIVE` — valid, at location, trigger fired (**actionable**)
   - + caveat annotations (extended / thin R:R / …)
6. **Overall / quality** — Alpha / Minervini / fundamentals / R:R as the **ranking
   overlay** (already status).

**Why this isn't "loose":** discipline shifts from a single catalyst re-derivation
to *(a)* the watchlist's own qualification + *(b)* the still-valid guard + *(c)* a
real archetype-specific **trigger** (pattern + volume at location). The trigger is
still the gate — just setup-appropriate.

---

## 6. What this fixes
- Every watchlist becomes a **first-class, equal source** — timed on its OWN setup.
- Rigorous lists **earn their keep**; the catalyst scan is **no longer privileged**
  (just "breakouts found broadly").
- **No catalyst dead-end; no redundant re-qualification.**
- The board becomes a true **timing cockpit** for the pre-qualified universe.

---

## 7. What stays vs changes (reallocation, not a teardown)
- **Keep:** `gm_load_symbol`/`gm_load_intraday` (technicals), PA batteries, the
  Location (R:R + EMA20) & Trigger layers just built, fundamentals, Overall score.
- **Change:** `compute_workflow` gate model — inherit setup, replace Steps 1–3
  re-derivation with the still-valid guard, make Location/Trigger archetype-aware.
- **New:** a `source → archetype` resolver; per-archetype location/trigger param
  sets; the timing-state Category.
- **Zero-drift:** the Single Symbol page must adopt the identical model.

---

## 8. Migration path (phased, low-risk — each phase shippable)
1. **P1 — Source→archetype + still-valid guard.** Add the mapping + break-down
   guard; as an interim, make the catalyst a *status* (the band-aid) so nothing
   regresses. Add an `Archetype` column to the board.
2. **P2 — Archetype-aware Location/Trigger** for the big three first: Breakout,
   Pullback, Recovery.
3. **P3 — Timing-state Category** replaces the catalyst-gated verdict; retire the
   "no catalyst" dead-end.
4. **P4 — Validate** the archetype timing rules on the walk-forward harness before
   locking (per the "measure, don't assert" discipline). Keep the old funnel behind
   a flag (like `USE_LEGACY_OVERALL`) for A/B comparison.

---

## 9. Decisions (RESOLVED 12 Jul 2026)
1. **Multi-source names → SHOW ALL setups the name qualifies for.** A name in both
   Hunter and Pullback shows both archetypes (e.g. an `Archetypes` list column);
   it is timed against each and the most-actionable state wins for the headline.
2. **`FINAL_WATCHLIST.csv` is NOT a plain union** — verified: it is the **top 25
   by Combined_Score** of the concatenated bull+recovery picks
   (`brute_force_match_pro.py:893`, `golden = all_combined.head(25)`). Its names
   are therefore already inside `FINAL_COMBINED_BULL/RECOVERY_PICKS.csv`.
   **Recommendation:** do NOT treat it as a distinct archetype source — resolve its
   names' archetypes from their per-strategy memberships, and use
   `FINAL_WATCHLIST` membership only as a **"★ Top-Conviction" badge/flag** on the
   board (top-25 by conviction), layered on top of the archetype.
3. **Still-valid guard → INVALIDATED on Stage 4 OR loss of the 30WMA** (both).
4. **Catalyst scan stays a SEPARATE source** (setup = "live catalyst").
5. **Universe — RESOLVED: everything is Nifty 500.**
   - **Catalyst scan = Nifty 500** (`_load_bull_universe` → `nifty500_symbols.json`,
     `run_pipeline.py:61`).
   - **All 7 Chartink scans (Bull 1–4 + Recovery 5–7) use the SAME group
     `{57960}`** (`chartink_scanner_pro.py`, lines 19/46/67/87/159/202/243). Jay
     confirmed the 4 Bull scans are Nifty 500 → therefore **`{57960}` = Nifty 500**,
     and the Recovery scans (submitted to Chartink's API on the same group) are
     **also Nifty 500**. (Recovery archetypes have no *saved* Chartink scan — the
     Python builds the clause and calls the API directly; the `rs:'nifty500'` tokens
     are RS benchmarks, not the universe.)
   - **Net: the catalyst scan and the rigorous lists share ONE universe (Nifty 500).**

   **Correction to earlier reasoning:** there is NO "out-of-universe" contribution —
   the rigorous lists do not reach symbols the catalyst scan can't. So that argument
   for the redesign is withdrawn.

   **But the redesign value stands, for a different and stronger reason —
   ARM-BEFORE-TRIGGER:**
   - The **catalyst scan is trigger-only**: it catches a Nifty-500 name only at the
     *instant* it fires a catalyst (a small subset, ~14 names).
   - The **rigorous lists are the ARMED universe**: quality names sitting in a valid
     **setup** (Hunter breakout coiling, Pullback into support, …) that have **not
     fired yet**. They are a *different, larger* subset of the same Nifty 500.
   - Today's catalyst gate collapses everything to "must be firing NOW," so those
     armed setups **dead-end at 'no catalyst'** and you only ever see names at the
     trigger instant — you can't **watch them arm and time the entry**.
   - The redesign inherits each name's **archetype** and runs the **timing** layer,
     so a Hunter name shows `WATCH → ARMED → TRIGGER LIVE` across its setup, and you
     catch the entry on *its own* trigger — not only when `bull_screener` happens to
     stamp a catalyst. **That is the value: arming + timing the quality setup
     universe, not just snapshotting the catalyst-firing instant.**

**No remaining open items** — the design is fully specified; ready for P1.

---

## 10. Risks
- Archetype timing rules must be **validated** (don't loosen into noise).
- Complexity — keep every archetype's params in one config dict.
- The still-valid guard must be **lightweight** (no heavy re-fetch on the live board).
