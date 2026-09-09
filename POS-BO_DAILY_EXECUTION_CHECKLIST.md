# POS-BO — Daily Execution One-Pager
### 90-Day Operator Protocol · One setup · No building · Just execute

> **The rule above all rules:** The decision was made when the stock passed the screen.
> Sizing and stops are mechanical. **There is nothing left to deliberate.** Place the order.

---

## ☐ THE FREEZE (read this first, every day)
- **No new modules. No new parameters. No new Pine files. For 90 days.** The machine is finished.
- I trade **POS-BO only.** SWG-PB, recovery, ETFs — all parked until POS-BO is a habit.
- My edge is already proven: **POS-BO = +7.67% alpha, PF 3.14, 78.6% win.** I trust it because I froze it.

---

## ☐ EVENING RITUAL — same time daily (post-close, ~5:00 PM IST)

**1. Run the screen.** POS-BO catalyst only.
   `python bull_screener.py` (or 🔄 Run in Web Commander)

**2. For each new POS-BO pick — log it (60 seconds):**

| Field | Source | Rule |
|---|---|---|
| Symbol / Stage | screener | Must be **Stage 2**. No exceptions. |
| Entry (proximal) | screener | Breakout / pivot level |
| Stop-loss | ATR | 4.0× ATR (POS horizon) — *non-negotiable* |
| Risk amount | capital × **0.25%** | Small on purpose. Goal = reps, not P&L. |
| Qty | Risk ÷ (Entry − SL) | Volatility-adjusted. No rounding up. |

**3. Place the GTT the SAME evening.** Entry trigger + stop via GTT_Auto_Shield.
   - ❌ Do NOT "sleep on it." Sleeping on it = the veto. The screen already decided.
   - ❌ Do NOT re-open the chart to "double-check." One look passed it; that's enough.

**4. Done. Close the laptop.** No tinkering. The order is live; the system runs.

---

## ☐ EXIT IS NOT A DECISION EITHER
- Stop is set at entry. **Let it hit.** No moving it down, ever.
- Trail per Chandelier once in profit (already in your stack). Mechanical.
- **Time/structure target plays out over 50+ days** — POS-BO is a *positional* hold. Don't touch it for being "boring."

---

## ☐ THE NON-NEGOTIABLE FIRST ACTION
**☐ Close RELIANCE.** Stage 4, alpha 20, violates "no Stage 3/4 holds."
Hard stop ₹1,300, sell into any bounce toward 30-WMA ₹1,431. **This is the test — do it before any new trade.**

---

## ☐ BEHAVIOR JOURNAL — 2 lines, every night (NOT the P&L journal)
> 1. Did the screen fire today? **Y / N**
> 2. Did I place every order it told me to? **Y / N** — if **N**, the one-word reason: ________

After 2 weeks, read the "N — reason" column. **That list is the real problem to solve. Not the code.**

---

### Weekly (Sunday, 15 min max)
- Count: **# POS-BO trades executed this week.** That number is my confidence score — not alpha, not the backtest.
- Confirm RELIANCE (and any other Stage 3/4) is gone.
- **Do not** open the IDE. Do not "improve" anything.

---

*Confidence is a count of executed trades, not a count of features built.*
*Pinned: ____ / ____ / 2026 — Day 1 of 90.*
