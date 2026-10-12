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

> **The step-by-step version with links is Doc 35, the Daily Regime** — `DAILY_REGIME.bat`
> prints the block for right now. This section explains the machinery behind it.

### 15:30 — close

Nothing to do. The session's last bar closes and the 75m/125m boundaries land together.

### 15:45 — `GTT Trail` runs (automatic)

Tighten-only Chandelier trail on the live OCO stop legs, catalyst-aware
(POS 4.5× / SWG 1.5× ATR). Telegrams a summary. **It never loosens a stop and never sells.**

> ⚠ **Disabled since 3 Oct 2026** (`GTT_Trail_Daily`): Dhan refuses every stop modify without a
> whitelisted static IP (DH-905), while the job still exited 0. Trail by hand off v67's
> Chandelier line, which equals Risk Shield's. A static IP registered with Dhan is the only
> way back to automated stops.

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
      →  size at 0.5% risk (0.75% for an ETF) on the HONEST stop (≥1×ATR) — 1% on a pyramid add
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
| **Pyramid / Trim** | the 5-rung ladder — EXIT → TRIM → REDUCE → ADD → HOLD. For the first 10 sessions after entry it holds off rungs that were already true on the entry day, and every REDUCE (`grace sN/10` in the reason); hard exits always fire. Doc 25 Part 7d |
| **`gtt_auto_shield --trail`** | tighten-only trail at the broker — **disabled since 3 Oct** (DH-905, no whitelisted IP); trail by hand off v67's Chandelier |
| **`journal_sync`** | keeps the journal equal to the live Dhan book, daily |
| **Risk Shield → 🔥 Open risk** | the whole book's risk from LTP against the regime budget (OPEN 6% · NEUTRAL 3% · BEAR 3% of capital) and, over budget, the shares to sell with the stops left in place. Doc 25 Part 7c |
| **Risk Shield → 🔁 Swing ↔ Positional** | classify every holding, check a swing → positional conversion (four gates, new stop, max qty), record it in the journal; positional holdings that read Stage 3/4 on the weekly close show as EXIT REVIEW. Procedure: Doc 25 Part 7b |

**Swing or positional (7 Oct).** Classify at entry from the list the GO came from
(GM_Positional = positional, GM_Swing = swing; S4's Plan row breaks a tie) and write it into
the journal Timeframe. A swing becomes positional only through the Risk Shield conversion
check, judged on a Daily close: working (at T1, or the new stop above entry), the rule reads
positional, Stage 2 weekly, sector not Stage 4. The new stop is never closer than
4 × ATR(D) and the quantity is trimmed to the house risk. A losing swing converts only at
half risk (salvage); otherwise its swing stop applies. Every weekly close, positional
holdings that read Stage 3/4 go to the exit/reduce review — the evening digest lists them
under `TRADE CLASS`.

The management rule that matters most: **88% of positional exits come from the trail**, and
only 8.4% ever reach 3R. Targets are upside; the trail is the mechanism. Do not tighten it —
four studies have rejected that.

---

## 6. HEALTH CHECKS — the things that fail silently

Each of these has already cost a day or more.

| Check | Symptom when it fails | Where |
|---|---|---|
| Streamlit actually restarted | "the fix didn't work" — old code still serving 8501; or only the dashboard tab opens and not the GM tab | Since 11 Oct the launchers stop an old Commander server themselves (`stop_commander.ps1`), pin port 8501 and open the GM tab only once the app answers. `STOP_COMMANDER.bat` still works by hand |
| Board source lists non-empty | part of the shortlist silently missing | board header strip |
| Data freshness | catalysts firing on dead bars | `As_Of` + provenance strip |
| Alerts bound to the CURRENT script | alert looks healthy in the list, never fires | Alerts panel — check the version and resolution |
| v67 source bindings after an S4 compile | context rows blank or wrong | run `BIND_S4_SOURCES.bat` |
| Dhan token | feed silently falls back to yfinance | 08:00 job + `logs/` |
| GTT trail actually running | stops never ratchet | `logs/gtt_shield.log` |
| Every position has a resting stop | naked exposure | Risk Shield · `--cover` |
| Daily bars current after midnight | every daily read one session behind until Dhan's next-day publish (fixed 7 Oct: the intraday session-fill asked Dhan for `to_date` = the session, which Dhan treats as exclusive) | a Swing ↔ Positional `close` that matches the last session |
| S4 alert path (ngrok + receiver) | TradingView alert reads "Webhook delivery failed — 404" (tunnel offline) or "502" (receiver down); the review never happens and TradingView does not retry | Telegram **S4 ALERT PATH DOWN** from the 15-min check (9:15 onward); then `START_ALERT_REVIEWER.bat` and `REVIEW SYMBOL TF` for anything missed |
| Open risk inside budget | a book that loses far more than planned if the tape breaks | Risk Shield 🔥 Open risk card |
| Thesis alerts set (two-tier stop) | a close below a holding's thesis passes unnoticed; only the farther Dhan disaster stop is left | auto-pilot Phase 12b4 line in the evening digest; `python tv_thesis_alerts.py --dry-run`; the receiver must be up (`/thesis-alert`) |
| S5 footprint rows fit the stock | S5's order-flow rows read "ROWS TOO COARSE" and say nothing | the reviewer fits its own tab; on yours click `Set S5 Rows` (SET_S5_ROWS.bat) after changing symbol |

## 6b. AWAY FROM THE DESK (10–11 Oct 2026)

Everything runs on the PC; phone and tablet reach it over **Tailscale only** (nothing on a
public tunnel except the ngrok webhook).

| What | Address | Notes |
|---|---|---|
| Web Commander | `http://jaynuc:8501` | `?view=gm_window&mobile=1` for the GM |
| Library / Reviewer Log | `http://jaynuc:8502/docs/portal/index.html` | `SERVE_PORTAL.bat` |
| Files | `http://jaynuc:8503` | File Browser, `START_FILEBROWSER.bat` (MORNING step 6, Desktop shortcut); 127.0.0.1 + `tailscale serve`; root = profile folder, rules allow only Documents · Downloads · TradingData · OneDrive\Desktop (AppData etc. refused); command exec off; user `jay` |
| The desktop | Remote Desktop to `jaynuc` | RDP firewall scoped to 100.64.0.0/10. **Disconnect, never sign out.** Microsoft account email + password (not PIN). Prefer the Desktop shortcut *Hand Back to PC* (`HANDBACK_TO_CONSOLE.bat`): returns the session to the PC screen so the desk keeps a display (leaves the PC unlocked). Jobs are run this way |

`REMOTE_ADMIN_SETUP.bat` (admin): 1 restart Tailscale · 2 reset state + re-login (node back to
`jaynuc`) · 3 RDP firewall to the tailnet · 4 status · 5 publish File Browser. If the daemon is in
`NoState`, nothing is reachable. Real cause (11–12 Oct): the tray app had not started and the
service waits for it — fixed by **unattended mode** (on) and MORNING step 0 (starts the tray app).
File Browser does not follow links (junction = "Something went wrong", link = "It feels lonely
here"), so access is set by rules, not a folder of links: `filebrowser rules ls -u jay`. Log:
`RemoteAccess\logs\filebrowser.log`.
File Browser was archived upstream on 1 Sep 2026 (no security fixes; an upload failure can
delete a directory recursively) — keep uploads small, change the initial password and delete
`RemoteAccess\config\INITIAL_LOGIN.txt`.

**Market Regime page (11 Oct)** — Web Commander → STATE OF MARKET → 🎲 REGIME HMM: a 2-state
Gaussian HMM on daily index returns says CALM or VOLATILE (filtered probability = knowable at
that close). It describes how wide daily swings are — for stop distance and patience. It does
not replace the exposure rule and it is not a direction signal.

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
