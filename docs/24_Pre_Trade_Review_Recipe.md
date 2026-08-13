# 24 · Pre-Trade Review — standing recipe

**Purpose:** one fixed procedure, run between "GM says armed" and "order placed",
that makes the gap between the system's read and your instinct **visible and
written down** before money moves.

Jay, 12-Aug-2026: *"Sometimes my natural instinct is overriding what the S4
panel / GM AI tells me. To arrest this and improve my focus, I would like to take
this approach."*

An override is not banned. It is **logged**. That is the whole mechanism: after
20-30 trades the log answers a question no amount of arguing can — do your
overrides make money or cost it?

---

## When to run it

| | |
|---|---|
| **Trigger** | GM Single Symbol reads ARMED or BUY — TRIGGER LIVE, and you are about to place the order |
| **Not for** | browsing, screening, or "what do you think of X". This is a gate, not a chat |
| **Cost** | ~2,000 tokens · one tool call · a few seconds |

---

## What Claude reads — ONE call

```
mcp__tradingview__data_get_pine_tables(study_filter="Section 4")
```

That single call returns the whole decision surface: all six panel sections, the
gate chips (`P·L·V·B`), Room, Confluence, TRIGGER, VERDICT, the plan levels, and
the VI · PORTFOLIO rows.

**Why CDP and not the Chrome extension:** TradingView draws the panel on a
`<canvas>`. There is no DOM text to read — measured 12-Aug, a DOM query for the
panel returned empty. The extension would have to screenshot and interpret
pixels: 3-5x the tokens, and a misread decimal on a stop is a live risk. CDP
returns the numbers as written.

Add only if needed: `quote_get` (live price, ~50 tokens), `chart_get_state`
(confirm symbol/TF, ~100). **Do not** screenshot unless the numbers look wrong
and the chart's SHAPE is the question. **Never** call `data_get_ohlcv` without
`summary=true`.

**Prerequisite:** TradingView Desktop must be launched with the debug port —
`LAUNCH_TRADINGVIEW_CDP.bat`. Started normally, port 9222 is shut and every tool
fails with "fetch failed".

**Already on screen, not re-fetched:** the GM AI brief (evidence, gaps, the
disconfirming case). Run it on the GM page first; the review does not duplicate
it.

---

## What Claude gives back — fixed shape, no essay

```
SYSTEM SAYS      stage · location · trigger state · room · R:R · what is blocking
YOUR CALL        what you said you want to do, in your words
DIVERGENCE       the specific gap, or "none - you and the panel agree"
THE ONE QUESTION the single thing that decides it
IF OVERRIDING    the sentence you write before placing
```

Five short blocks. If there is no divergence it says so in one line and stops —
agreement does not need paragraphs.

---

## Rules Claude follows

1. **Quote the panel verbatim.** Never paraphrase a gate into something softer.
   "V✗ RV 0.72" is not "volume is a little light".
2. **Never talk you INTO a trade.** Your own doctrine: the chart-read has veto
   power, not entry power. Same applies to the review — it can raise a reason to
   stop, never manufacture a reason to go.
3. **No new analysis mid-review.** If a fresh idea appears, it is a note for
   after the trade, not an input to this one. Scope creep at the point of entry
   is how a considered setup becomes an improvised one.
4. **Blocked gates are stated first**, before anything encouraging.
5. **Silence on what is already known.** No restating the whole panel back.

---

## The override sentence

If you place against the panel, you write **one line** first:

> *Overriding <what> because <what you see that the system cannot>.*

Then it goes in the log. Two reasons this works:

- **It is hard to write a bad one.** "Overriding no-volume because it feels
  ready" reads as what it is, in your own handwriting.
- **It becomes evidence.** Joined against outcomes later, the log tells you
  whether your reads beat the system's. If they do, the system needs changing.
  If they do not, you have the answer you were looking for when you asked for
  this.

Log it with:

```bash
python log_trade_review.py SYMBOL --verdict "S4 says" --call "what I did" --override "reason"
```

Writes `logs/trade_reviews.csv`. Omit `--override` when you followed the system —
those rows are the control group, and without them the log proves nothing.

---

## Why this exists at all

Everything measured in this repo says the same thing: **the signal generation is
not the weak part.** Four stop studies rejected tightening. The GO gate turned
out to be a classifier, not an entry optimiser. The edge, where it exists, is
thin and lumpy — POS-BO carried by big winners, a median trade that loses to the
index.

A system that thin cannot survive discretionary overrides that nobody counts.
Not because instinct is worthless — yours has the context the panel does not —
but because an uncounted override is indistinguishable from a mistake, forever.
This makes them countable.

Related: `docs/23_Golden_Matcher_Guide.md` · `docs/22_Section4_Entry_Trigger_Guide.md`
