# THE GM + S4 OPERATING LOOP — workflow process

> **What this is:** the end-to-end process for running the ecosystem, in the order it
> actually happens — what runs by itself, what needs you, and what each step hands to the
> next. The [Golden Rules](./25_Golden_Rules.md) say *how to decide*; this says *when to be
> where, and with which tool*.
>
> **The shape of the day, in one line:** the machine qualifies overnight, you arm in the
> evening, the alerts watch the session, and you only open a chart when one fires.
>
> **Last updated:** 20 Aug 2026

---

## 0. THE FOUR STAGES — and what never to ask each one

Every surface answers exactly one question. Most of the confusion this system has produced
came from asking a surface a question it was never built to answer.

| Stage | Surface | Answers | Never ask it for |
|---|---|---|---|
| **QUALIFY** | Chartink · Screener.in · `pullback_finder` · Recovery RFF | *Does this name belong on the list at all?* | timing |
| **TIME** | GM Trigger Board | *Which qualified names deserve attention right now?* | the plan |
| **EXECUTE** | S4 on TradingView | *Entry, stop, target — and is it worth taking?* | qualification |
| **MANAGE** | Risk Shield · Pyramid · GTT | *What do I do now that I own it?* | entries |

**The two-stage doctrine within that:** the GM fires **early** (a name is *armed*), S4 is
the **strict execution gate** (a trade is *triggered*). They are deliberately not aligned.
GM arms → you focus → you wait for the S4 GO. Collapsing them would destroy the thing that
makes the shortlist useful.

---

## 1. THE DAILY LOOP

### 15:30 — close

Nothing to do. The session's last bar closes and the 75m/125m boundaries land together.

### 15:45 — `GTT Trail` runs (automatic)

Tighten-only Chandelier trail on the live OCO stop legs, catalyst-aware
(POS 4.5× / SWG 1.5× ATR). Telegrams a summary. **It never loosens a stop and never sells.**

> ⚠ Currently **disarmed** (`GTT_TRAIL_ENABLED=0`) while you set OCO stops and trailing
> levels by hand. Re-arm with `GTT_TRAIL_ENABLED=1` + restart, and run
> `python gtt_auto_shield.py --trail --dry-run` first to see what it would move.

### 16:00 — `Exit Signal Scan` runs (automatic)

`exit_signal_engine` checks the open book for stop hits, stage decay and time stops, and
Telegrams the ACTION rows.

### 16:30 — `Auto-Pilot Full Run` (automatic, ~the whole pipeline)

`run_pipeline.py --batch`. In order:

| Phase | Does |
|---|---|
| 0 · 0.5 | pre-flight and nuclear cleanup |
| 1 | **Chartink scanners** — the four bull scans on the Nifty 500 group |
| 2 · 3 | **Screener.in fundamentals**, then HTML → structured |
| 4 | **Golden Matcher** — the conviction match |
| 4.5 | **Recovery screener** (RFF ≥ 4 hard-gated) |
| 4.6 · 4.7 | **Bull screener**, then the broad catalyst-first scan |
| 4.75 · 4.75b | **Recovery catalyst watchlist**, then **Pullback Finder** ("At Value") |
| 4.8 | **GM board union** — the shortlist the board reads |
| 5 · 5.5 · 5.6 · 5.7 | watchlists pass 1, **X-Ray**, pass 2, stale cleanup |
| 6 · 7 | **Strike.Money sync**, **TradingView sync** (the dated watchlist) |
| 8 – 11 | backup, portfolio rotation guard, CSV export, score authenticity |

Also at 16:30: **`Post-Market Summary`** and the Windows task
**`TradingJournal_DhanSync`** (journal ↔ live Dhan book: ADD / UPDATE / CLOSE-with-verified-exit,
and it aborts rather than guess if the holdings fetch fails or returns empty).

### Evening — **THE ONE STEP THAT NEEDS YOU** (~15 minutes)

This is where the day's trading is decided. Everything else is either a machine or a
reaction.

1. **Restart clean.** `STOP_COMMANDER.bat` → relaunch. A browser reload does not reload
   code; only a process restart does.
2. **Rebuild the board** — *Fetch fresh data + rebuild* (it rebuilds itself; don't also
   press Rebuild).
3. **Read the header before the rows.** Failure counts, the source-issue strip, provenance,
   AGE. An empty or header-only source list means part of the shortlist is silently
   missing — that is how Hunter names once vanished.
4. **Work the board top-down.** It opens filtered to all-gates (4/4) and sorted by Overall.
   For each name worth attention, open **Single Symbol** and read the decision path.
5. **ARM what you intend to stalk.** This is the highest-value action of the evening: an
   armed name is injected into every subsequent board union carrying the archetypes it had
   when armed, so it survives even after it stops qualifying — exactly when losing it would
   cost you the trade.
6. **Create tomorrow's alert** (§3 below).
7. **Note the sector mix strip.** If one sector is over its cap, you are about to over-
   concentrate — the same threshold the order gate will later enforce.

### 19:00 — `Weekly Market Report` (automatic, weekly)

### 08:00 / 08:30 — `Dhan Token Check`, `Pre-Market Brief` (automatic)

### 09:15 – 15:30 — the session

**You are not required to watch the board.** That is the entire point of the alerts. The
board's auto-refresh is a browser timer that Chrome throttles when the tab is hidden, and
it stops altogether if Streamlit is down or the Dhan stream drops — so it is not the layer
to depend on intraday. TradingView alerts fire on TV's servers regardless.

When an alert fires, run §4.

---

## 2. THE WEEKLY AND MONTHLY LAYER

| Cadence | Do | Why |
|---|---|---|
| **Weekend** | Read RRG / sector rotation. Refresh the manual weekly reads. | Weinstein is a weekly framework; the stage and RS that gate everything are weekly numbers. |
| **Weekend** | Review `logs/trade_reviews.csv` — the decisions, including passes. | After ~20 rows it can tell you whether your instinct beats the system. Nothing else can. |
| **Weekly** | ETF screener + rotation (`etf_screener.py`, `etf_rotation.py`). | Separate alpha source; rotation-driven, not stock-picking. |
| **Monthly** | Attribution (AUTOPSY → 📐 Attribution). | P&L decomposed by setup / stage / RS / conviction — only meaningful for SYSTEM-tagged trades. |
| **When code changes** | Re-baseline validation. | Any signal change invalidates prior Strategy Tester and walk-forward numbers. |

---

## 3. THE ALERT RITUAL (every weekday evening)

The auto-pilot writes a **new, date-stamped** TradingView watchlist each evening, so
yesterday's alert points at yesterday's list by construction.

1. **Check the board's source-issue strip first.** On a thin auto-pilot day you would
   otherwise arm a near-empty watchlist and lose a day of coverage silently.
2. **Delete yesterday's alert.** Left running it fires on names that already dropped out
   and eats the alert quota.
3. **Create today's** on the new watchlist: condition = the S4 indicator →
   **`S4 GO (PA + Location + Volume + Bar)`**, trigger **Once Per Bar Close**, app push on,
   named to match the dated watchlist (`S4 GO · GM-20AUG · 75m`).
4. **Repeat on a 125m chart** — an alert inherits the chart's resolution, so each timeframe
   needs its own. 75m closes at 10:30 · 11:45 · 13:00 · 14:15 · 15:30; 125m at 11:20 ·
   13:25 · 15:30. The 125m set skips the opening-drive bar by construction.

> ⚠ A name pinging on both is **one setup seen twice**, not corroboration — same engine,
> same gates, only the sampling rate differs. They share the 15:30 close, so duplicates
> cluster there.

**A side effect worth knowing:** `gm_pb_list` and `gm_rec_list` are frozen into an alert at
creation, so pullback context and Bull/Recovery resolution would otherwise go stale.
Recreating daily keeps them never more than one session old.

**After every S4 recompile, all alerts are gone** — they bind to the compiled script id.
Recreating is mandatory, not housekeeping. Full procedure: [S4 guide §7b](./22_Section4_Entry_Trigger_Guide.md).

---

## 4. WHEN AN ALERT FIRES — the execution path

```
ping  →  open S4 on the alert's timeframe
      →  read the SUMMARY (bottom-right column) first
      →  run the 12-step checklist, stop at the first NO
      →  size at 1% risk on the HONEST stop (≥1×ATR)
      →  place entry + GTT stop
      →  log the decision, including a pass
```

**Read the SUMMARY before the rows.** It is the only field that weighs one section against
another, and its last line tells you which of the three cases you are in:

- **"This is a take-it"** — trend, leadership, location and geometry agree.
- **"The SETUP is sound but the TRADE as planned is not"** — the most common case. Fix the
  entry, the stop or the target. Do not take the plan as printed.
- **"The trigger is live but the context is against it"** — counter-trend. Legitimate only
  if you size it as one.

**The two prices you must know before entering:** `SL` (where you get out) and `INVAL`
(where the reason you bought stops being true). If they are the same price, you have no
room to be wrong.

**If the name was not armed:** see [Golden Rules §8b](./25_Golden_Rules.md). Short version —
it is not a contradiction, but check whether the board is simply stale, and do not take a
trade whose presence on the list you cannot explain.

---

## 5. AFTER THE ENTRY

| Surface | Role |
|---|---|
| **Risk Shield → Active Exits** | the live stop/target picture per position, with the Chandelier and policy-R check |
| **Pyramid / Trim** | the 5-rung ladder — EXIT → TRIM → REDUCE → ADD → HOLD |
| **`gtt_auto_shield --trail`** | tighten-only trail at the broker (when re-armed) |
| **`journal_sync`** | keeps the journal equal to the live Dhan book, daily |

The management rule that matters most: **88% of positional exits come from the trail**, and
only 8.4% ever reach 3R. Targets are upside; the trail is the mechanism. Do not tighten it —
four studies have rejected that.

---

## 6. HEALTH CHECKS — the things that fail silently

Each of these has already cost a day or more.

| Check | Symptom when it fails | Where |
|---|---|---|
| Streamlit actually restarted | "the fix didn't work" — old code still serving 8501 | `STOP_COMMANDER.bat` |
| Board source lists non-empty | part of the shortlist silently missing | board header strip |
| Data freshness | catalysts firing on dead bars | `As_Of` + provenance strip |
| Alerts bound to the CURRENT script | alert looks healthy in the list, never fires | Alerts panel — check the version and resolution |
| v67 source bindings after an S4 compile | context rows blank or wrong | run `BIND_S4_SOURCES.bat` |
| Dhan token | feed silently falls back to yfinance | 08:00 job + `logs/` |
| GTT trail actually running | stops never ratchet | `logs/gtt_shield.log` |
| Every position has a resting stop | naked exposure | Risk Shield · `--cover` |

---

## 7. THE WHOLE LOOP, COMPRESSED

```
15:45  trail tightens            (auto)
16:00  exit scan                 (auto)
16:30  auto-pilot + journal sync (auto)
─────  EVENING: restart · rebuild · read · ARM · create tomorrow's alert   ← you
09:15  session — do not watch the board
 ping  S4 → SUMMARY → checklist → size → order → log                      ← you
15:30  close
```

Everything above the line is machinery. The two moments that need judgement are **arming in
the evening** and **the checklist at the trigger** — and the second one is only as good as
the first, because an armed name is one you have already thought about.

---

*Process, not ceremony. If a step stops earning its place, remove it — but remove it
deliberately, and write down why.*
