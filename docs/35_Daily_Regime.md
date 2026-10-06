# DAILY REGIME — what to do, when, and where (Doc 35)

*Generated from `daily_regime.py` — edit the steps there and run `python daily_regime.py --build`.*

Run `DAILY_REGIME.bat` (or `python daily_regime.py`) for the block that applies right now, with links. `--open` opens the pages, `--phase pre|session|post|weekend|all` picks a block, `--host jaynuc` gives phone links.

**The three numbers that decide every day:** the exposure tier (whether you may enter, and at what risk), open risk against its budget (6% OPEN, 3% NEUTRAL or BEAR), and the stops (one price, full cover, limit below the trigger).

---

## BEFORE THE OPEN — Trading days · 08:00 – 09:15

Arrive with the book already decided: stops covered, the day's trims known, and the exposure rule read. Nothing that happens after 09:15 should be a surprise you could have seen at 08:50.

### 08:00 · Dhan token check (automatic)
- Dhan_Token_Check refreshes the API token (TOTP). A failure arrives on Telegram — then run run_token_check.bat.

### 08:30 · Pre-market brief (automatic)
- PreMarket_Report sends GIFT Nifty, global cues, F&O participants and the calendar to Telegram.

### 08:45 · Morning digest (automatic)
- Morning_Digest: holdings at or below their Chandelier, results within 7 days, the market line.

### 08:45 · Start the desk — MORNING.bat (one click) (YOU)
- Double-click Morning on the desktop. It starts, in order and only what is not running: TradingView with the CDP port, Web Commander, the alert receiver + ngrok, the reviewer banner, the Library server.
- Check the window "S4 webhook receiver :8000" is open — closing it is the only way alerts stop being reviewed.
- Check TradingView has its six tabs open: S4 Phase-2 and S5 Layout (yours), S4 Reviewer and S5 Reviewer, Phase-1 and Panel Layout. If the reviewer tabs are missing, reviews FAIL loudly; they never borrow yours.
- Banner green = reviewer idle.
- Open: [Web Commander · Dashboard](http://localhost:8501/?p=DASHBOARD)

### 08:50 · Read the morning digest, then decide the exits (YOU)
- Every name listed as at/below its Chandelier: decide now — exit at the open, or hold because the resting stop already handles it. Write the decision down; do not decide it in the first minute of trade.
- Results within 3 days on a held name: decide the size (trim or hold), never the direction, from the result risk.

### 08:55 · Risk Shield — stops, open risk, class (YOU)
- Banners first: 'Stops disagree' or 'Partly covered' → fix on Dhan before 09:15: ONE stop price per holding, covering the full quantity, limit price below the trigger.
- 🔥 Open risk card: if OVER budget, the expander lists the shares to sell with the stops left in place. Those trims are today's first orders (Doc 25 Part 7c).
- 🔁 Swing ↔ Positional tab: any EXIT REVIEW name is decided like an exit above.
- Open: [Risk Shield (🔥 Open risk card · 🔁 Swing ↔ Positional tab · warnings)](http://localhost:8501/?p=RISK%20SHIELD) · [Doc 25 Part 7c · open-risk budget](http://localhost:8502/docs/portal/25_golden_rules.html#p7c) · [Dhan web (orders · positions · forever orders)](https://web.dhan.co)

### 09:00 · Read the tape and the exposure rule (YOU)
- Pre-Market page and the MACRO regime. The S4 Section I header (and the SUMMARY's EXPOSURE section) says the tier: BEAR or circuit breaker = no new entries today — a management-only day. NEUTRAL = half risk, at most 3 new entries a week. A follow-through day or breadth thrust unlocks 2 half-risk pilots.
- This one line decides whether any alert today can become a trade.
- Open: [Pre-Market](http://localhost:8501/?p=PRE-MARKET) · [Macro (regime, sectors)](http://localhost:8501/?p=MACRO)

---

## DURING MARKET HOURS — Trading days · 09:15 – 15:30

The alerts watch the session, the reviewer reads the chart, and you act only when a review arrives. No code changes, no compiles, no restarts — if something breaks, roll back, do not fix forward.

### 09:15 · Execute the planned trims and exits first (YOU)
- The trims and exits you decided before the open, at or shortly after the open. Then resize each remaining holding's stop legs to the new quantity (one price, full cover).
- Open: [Dhan web (orders · positions · forever orders)](https://web.dhan.co) · [Risk Shield (🔥 Open risk card · 🔁 Swing ↔ Positional tab · warnings)](http://localhost:8501/?p=RISK%20SHIELD)

### bar closes · S4 GO alerts → the reviewer → Telegram (automatic)
- 75m closes 10:30 · 11:45 · 13:00 · 14:15 · 15:30; 125m closes 11:20 · 13:25 · 15:30. The two watchlist alerts cover GM_Swing names. About 90 seconds later the review arrives on Telegram and in the Log.
- Daily GO alerts (GM-POS GO, positional names) are reviewed after the close, at 15:31.

### on a review · When a review arrives — the execution path (YOU)
- Open S4 on YOUR S4 Phase-2 tab, on the alert's timeframe. Read the SUMMARY first — EXPOSURE is binding.
- Take only TAKE-IT rulings. A swing name can be timed on 75m/125m; a POSITIONAL name is decided on the Daily close only — an intraday GO on a positional name is information, not an entry.
- Size with the Risk Allocator on the S4 stop: 0.5% (stock) / 0.75% (ETF), half in a NEUTRAL tape or on a pilot, never above the ₹1L per-trade cap.
- Place the entry and the stop together on Dhan: one stop price, full cover, limit below the trigger.
- Write the class (Swing/Positional) at entry — s4_take does it after the close (below).
- Open: [Reviewer Log (Doc 31)](http://localhost:8502/docs/portal/31_reviewer_log_v2.html) · [Section Four (Doc 22)](http://localhost:8502/docs/portal/22_section_four.html) · [Dhan web (orders · positions · forever orders)](https://web.dhan.co)

### any time · Manual review of a name (YOU)
- REVIEW.bat SYMBOL TF (e.g. REVIEW TITAN 75) — same path as an alert, on the reviewer's own tabs.

### all day · Holdings: let the stops work (YOU)
- Do not widen a stop unless you cut the quantity so the rupees at risk do not grow (Doc 25 Part 7b).
- Do not convert a swing to positional intraday — conversions are judged on a Daily close.
- A new position's first 10 sessions: the ladder shows 'grace sN/10: held off …' for rungs that were true on the entry day. Those describe your entry — act only on the hard exits (stop hit, P&L -8%, Stage 4).
- Optional glance 5 minutes after each bar close; the board is the arm stage and does not decay in 30 minutes.
- Open: [Doc 25 Part 7b · swing or positional](http://localhost:8502/docs/portal/25_golden_rules.html#p7b)

---

## AFTER MARKET HOURS — Trading days · 15:30 – 21:00

The machine rebuilds everything between 16:00 and about 17:30. Your 20 minutes start when the evening digest lands: read what the day did, then set up tomorrow.

### 15:31 · Daily GO alerts reviewed (automatic)
- Positional GM-POS GO alerts that fired on the close are reviewed now — this is the positional entry decision.

### 15:35 · Log the day's decisions (YOU)
- For each trade taken: python s4_take.py SYMBOL --tf 75 --price FILL --qty SHARES. For each TAKE you passed on: python s4_take.py SYMBOL --skip "why". This is the scoring — it is the only way the live record can tell you whether the system's trades work.
- Check on Dhan that today's entries have their stop resting, full quantity.
- Open: [Reviewer Log (Doc 31)](http://localhost:8502/docs/portal/31_reviewer_log_v2.html) · [Dhan web (orders · positions · forever orders)](https://web.dhan.co)

### 16:00 · Exit scan (automatic)
- Exit_Scan_Daily: stop hits, stage decay, time stops → Telegram ACTION rows.

### 16:30 · Auto-pilot, journal sync, post-market report (automatic)
- WeinsteinAutoPilot runs the whole pipeline (scans → Golden Matcher → screens → watchlists → TV sync). TradingJournal_DhanSync makes the journal equal the Dhan book and reads the resting stops back. PostMarket_Report goes to Telegram. 16:45 Breadth_Daily.

### ~17:00 · Evening run — boards, bundles, alerts, records (automatic)
- Phase 12: Daily/125m/75m boards, bundles pushed to S4, the two watchlist alerts moved to today's GM_Swing list, positional Daily alerts and zone-approach alerts rebuilt, v67 slots + trail pushed, live record and trade log rebuilt, board reviews. Phase 14 sends the evening digest. 17:15 docs truth check, 18:45 F&O bhavcopy.

### ~17:30 · Read the evening digest (YOU)
- Phases not OK · boards (5/5 counts against the 20-day median) · reviewer failures · bindings per tab (32/32) · alert versions · exit review · TRADE CLASS (positional EXIT REVIEW, swings that may convert).
- Anything red here is fixed tonight — this is the only window for code.

### 17:35 · Risk Shield — the book after today (YOU)
- 🔥 Open risk: over budget → plan tomorrow's trims (they go first at 09:15).
- 🔁 Swing ↔ Positional: a swing that passes all four gates may be converted now (it is a Daily close) — record it, then on Dhan set the new stop (and sell any trim), then Sync to TV. A losing swing converts only at half risk. EXIT REVIEW names are decided for tomorrow's open.
- Open: [Risk Shield (🔥 Open risk card · 🔁 Swing ↔ Positional tab · warnings)](http://localhost:8501/?p=RISK%20SHIELD) · [Doc 25 Part 7b · swing or positional](http://localhost:8502/docs/portal/25_golden_rules.html#p7b)

### 17:45 · Tomorrow's candidates — the boards (YOU)
- Daily board: the 5/5 positional names are tomorrow's Daily-close candidates. 125m/75m boards: swing names the alerts will time. Open each worth attention in the Golden Matcher and read the decision path.
- ARM what you intend to stalk — an armed name stays in tomorrow's union even if it stops qualifying.
- Open: [GM board · Daily (positional)](http://localhost:8501/?view=gm_board_maximized&tf=Daily) · [GM board · 125m (swing)](http://localhost:8501/?view=gm_board_maximized&tf=125m) · [GM board · 75m (swing)](http://localhost:8501/?view=gm_board_maximized&tf=75m) · [Golden Matcher (own window)](http://localhost:8501/?view=gm_window)

### 18:00 · Read the record (YOU)
- Reviewer Log: today's rulings. Trade Log: TAKE vs what you bought. Live Record: the system's numbers.
- Open: [Reviewer Log (Doc 31)](http://localhost:8502/docs/portal/31_reviewer_log_v2.html) · [Trade Log (Doc 34)](http://localhost:8502/docs/portal/34_trade_log.html) · [Live Record (Doc 33)](http://localhost:8502/docs/portal/33_live_record.html)

### if compiled · After any S4 / v67 compile (YOU)
- AFTER_COMPILE.bat — binds and verifies all tabs, pushes the bundles, moves the alerts to the new version, restores v67 settings and pushes the slots. All TradingView tabs must be open first.

---

## WEEKENDS AND HOLIDAYS — Saturday · Sunday · NSE holidays

The weekly stage only changes after a Friday close. The weekend is for the weekly read, the book's re-qualification, planning and system work — never for orders.

### Sat · Re-qualify the book on the weekly close (YOU)
- 🔁 Swing ↔ Positional: positional holdings that read Stage 3/4 on the confirmed weekly close are EXIT REVIEW — plan the exit for Monday. WATCH names (below the 200-DMA, weekly trend down): decide trim or hold.
- 🔥 Open risk: the budget for Monday's tier; plan the trims.
- Open: [Risk Shield (🔥 Open risk card · 🔁 Swing ↔ Positional tab · warnings)](http://localhost:8501/?p=RISK%20SHIELD) · [Doc 25 Part 7b · swing or positional](http://localhost:8502/docs/portal/25_golden_rules.html#p7b) · [Doc 25 Part 7c · open-risk budget](http://localhost:8502/docs/portal/25_golden_rules.html#p7c)

### Sat · The market's stage before the stock's (YOU)
- MACRO and BREADTH: regime score, % of stocks above the 50/200-DMA, new highs vs lows, Stage-2 share, McClellan. Write one line: what tier Monday is likely to start in, and what would unlock pilots.
- Sector rotation: the RRG (START_RRG_STUDIO.bat — it uses :8502, so stop the Library server first).
- Open: [Macro (regime, sectors)](http://localhost:8501/?p=MACRO) · [Breadth (McClellan, % above MAs)](http://localhost:8501/?p=BREADTH)

### Sat · Strategic planning — fresh Stage-2 names (YOU)
- HUNTER and the Golden Matcher Daily board: Hunter / EarlyBird picks, fresh Stage-2 breakouts. Weekly charts on TradingView for the GM_Positional list; mark Daily+ demand zones by hand where the engine has none.
- X-Ray for the fundamentals of anything you would stalk. ETF page for the rotation read.
- Open: [Hunter (fresh Stage-2 breakouts)](http://localhost:8501/?p=HUNTER) · [GM board · Daily (positional)](http://localhost:8501/?view=gm_board_maximized&tf=Daily) · [X-Ray (fundamentals)](http://localhost:8501/?p=X-RAY) · [ETF (screener + rotation)](http://localhost:8501/?p=ETF)

### Sun · Review the week (YOU)
- Trade Log and Live Record: what was taken, skipped, and how the system's trades did. Journal: lessons on every exit. logs/board_counts_history.csv: were quiet days the market or a gate?
- Monthly: AUTOPSY → Attribution.
- Open: [Trade Log (Doc 34)](http://localhost:8502/docs/portal/34_trade_log.html) · [Live Record (Doc 33)](http://localhost:8502/docs/portal/33_live_record.html) · [Journal](http://localhost:8501/?p=JOURNAL) · [Autopsy (attribution)](http://localhost:8501/?p=AUTOPSY)

### Sun 19:00 · Weekly report (automatic)
- Weekly_Report goes to Telegram.

### any time · System work (YOU)
- Code changes, compiles and restarts belong here or after 15:30. After an S4 / v67 compile: AFTER_COMPILE.bat. Before Monday: Web Commander restarted on the latest code, and MORNING.bat on Monday morning.
- Open: [The Library](http://localhost:8502/docs/portal/index.html)
