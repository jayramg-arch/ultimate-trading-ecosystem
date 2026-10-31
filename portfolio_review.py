"""PORTFOLIO REVIEW - every holding read by the Reviewer with the same depth as a new trade
(31-Oct-2026, Jay: "the same amount of analysis done on my portfolio stocks like any new
trade, so the new invalidation levels are identified, new opportunities and potential
drawdowns identified from the full fledged technical analysis").

WHAT IT DOES, per holding (v2 / POS-V2 names excluded - they run on Clenow's rules, no stops):
  1. reads S4 + S5 on the DAILY chart (all trade management is Daily - 13-Oct-2026) on the
     Reviewer tabs only - the same full-panel read a new trade gets, ETF index phase included;
  2. adds a HOLDING block computed by the script, never by the model: qty, cost, P&L, R,
     the resting Dhan stop, thesis, initial stop, Chandelier, the 3xATR stop, canon targets,
     open risk vs the per-trade rule, the worst overnight gap, earnings, the ladder rung, and
     a DRAWDOWN table (from LTP to the thesis close, to the Dhan stop, on the worst gap).
     These are the SL Dashboard's own numbers (sl_board.build), so the two cannot disagree;
  3. asks the Reviewer model with a holding-review prompt: the Reviewer's full doctrine,
     then HOLD / ADD / TRIM / REDUCE / EXIT, THESIS, the new INVALIDATION, STOP, DRAWDOWN,
     OPPORTUNITY;
  4. checks the answer against the house rules (post_checks) - no add when the exposure tier
     forbids adds, no averaging down, an invalidation must sit below the close and is never
     lowered, a Dhan stop is never raised inside 3xATR of the close, a lower stop needs the
     shares sold first - and appends what it found. It never writes the journal and never
     touches an order: every number here is a proposal for Jay.

RUN
  python portfolio_review.py                  all holdings - through the alert receiver's queue
                                              when it is up (so it never collides with an S4 GO
                                              review on the same tabs), else in-process
  python portfolio_review.py --direct         in-process even if the receiver is up (weekends)
  python portfolio_review.py --symbols A,B    only these holdings
  python portfolio_review.py --dump SYM       print the HOLDING block, no chart read, no model
  python portfolio_review.py --report         rebuild today's summary from the reviews already done
  PORTFOLIO_REVIEW.bat                        the same, from the desktop

OUTPUT
  every review: logs/ai_reviews/<ts>_<SYM>_D.md + a row in logs/ai_review_log.csv with source
  "portfolio", so it lands in the Reviewer Log (Doc 31); the summary of the run:
  reports/portfolio_review/Portfolio_Review_YYYYMMDD.md (+ Telegram with --telegram).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPORT_DIR = os.path.join(HERE, "reports", "portfolio_review")
SOURCE = "portfolio"
TF = "D"
RECEIVER = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------------------
# The prompt: the Reviewer's doctrine (identical text, imported - it cannot drift), then the
# job of a holder instead of the job of a buyer.
# ---------------------------------------------------------------------------------------
def _doctrine() -> str:
    import s4_review as s4
    s = s4.SYSTEM
    return s[:s.index("TONE RULES")]


def _analysis_template() -> str:
    import s4_review as s4
    s = s4.SYSTEM
    return s[s.index("ANALYSIS\n1. CONTEXT"):s.index("\nDELIBERATION\n")]


HOLD_JOB = """
THIS IS A HELD-POSITION REVIEW, NOT AN ENTRY REVIEW. Jay already owns this stock. Do the full
analysis above exactly as for a new trade - every field, the same doctrine, the same depth -
and then answer the holder's questions: is the reason he bought still true; where is it proven
wrong NOW; what can go wrong from here and what does it cost; is there an add, a trim or an
exit. The chart is the DAILY chart: every management decision is taken on the Daily close.

The HOLDING block is computed by the script from Dhan and the journal. Its numbers are exact:
quote them, never recompute or invent them. The DRAWDOWN rows are the cost of each scenario.

HOUSE RULES FOR A HELD POSITION (not negotiable - the script checks your answer against them):
- THESIS / INVALIDATION is a Daily CLOSE level: the price whose close says the reason he bought
  is no longer true. Base it on structure on the chart - the distal of the demand zone the trade
  stands on, a weekly level, the swing low that defines the trend, S4's own INVAL. It must sit
  BELOW the last close. It is RAISED when structure has moved up and the new level is at least
  1 x ATR(D) below the close; it is NEVER lowered - if structure now sits below the current
  thesis, the honest reading is that the thesis is weakening or broken, not that the line moves.
  The invalidation is NOT the Dhan stop. The house uses TWO tiers: the thesis is a close level
  on structure, and the Disaster SL resting at Dhan sits about 1 x ATR(D) BELOW it, to survive a
  wick through the thesis. Copying the Dhan stop into INVALIDATION is not an answer - name the
  structure.
- THE DHAN STOP (Disaster SL) is the resting order. The trail owns most exits (88% in the
  book's own tests) and every stop study rejected tightening: do not tighten because price moved.
  A raise follows the house rule only: the lower of the Chandelier and close - 3 x ATR14, and
  never closer than 3 x ATR14 below the close. Stops are never lowered by a recommendation alone:
  lowering a stop widens risk, so it needs the shares sold first to keep the per-trade rule
  (sell-first rule) - if you propose a lower stop, name the shares to sell.
- ADD (pyramid) only in Stage 2, on a winner, at a pullback location (above a rising 200-DMA,
  within ~10% of the close five sessions ago, above the daily EMA20, no more than 2 x ATR
  extended), sized at 1% risk off the raised stop. Never on a loser (no averaging down). Never
  when the PRE-READ says the exposure tier forbids adds - then the answer is HOLD and you say
  what would unlock the add.
- TRIM at the canon targets (positional 3R / 5R, swing 2R / 4R), when price is 4 x ATR or more
  above the daily EMA20, or with results inside three sessions. A trim is a partial, never the
  whole position.
- EXIT on a Daily close through the thesis, Stage 4, the Chandelier breached, P&L at or below
  -8%, or the time stop (swing 60 sessions, positional 180 with R below 0.5). Stage 3 alone is a
  REDUCE or a tighter thesis, not an automatic exit. In the first 10 sessions after entry the
  structural exits are held off; the hard ones (P&L -8%, Stage 4, the stop breached) are not.
- The LADDER rung in the HOLDING block is the deterministic engine's opinion as of last
  evening's run. S4's MY TRADE / POSITION rows (when present) carry the same engine's LIVE rung
  from v67 - if the two differ, the live one is current; say which you used. Weigh it, say
  whether you agree, and why if you do not.
- The panel's Plan / Entry / T1 / T2 rows are written for a NEW entry. For a holding they mark
  where an ADD would be and what it would risk - read them that way, never as an instruction to
  buy what he already owns.

TONE RULES - these are not optional:
1. Both sides honestly. The holder's two errors are the sunk-cost hold (a broken thesis kept
   because it was right once) and the noise exit (a sound position sold on one bad bar). Name
   which one this position is closer to.
2. A position whose context and location still hold is a HOLD, however uncomfortable the last
   few bars were. "Risks remain" is never a reason to exit.
3. Every EXIT or REDUCE must name the Daily close or event that triggers it, with its number.
4. Every HOLD must name the level that would change it.
5. Where S4's rows contradict each other, say so and say which you believe.
6. Only reason from what is in the read and the HOLDING block. A field showing "-" or "n/a" is
   unknown, not neutral and not a fail. Sections marked [withheld] are not available.
7. His chart-read has veto. End with what would make you change your mind.

OUTPUT - three parts, these exact headings. Part 1 is the full analysis (same sections as an
entry review, each a short paragraph that quotes the numbers and says what they MEAN), then a
ninth section on the position itself.

"""

HOLD_OUTPUT = """
9. THE POSITION - entry, cost, P&L and R now (HOLDING block); where price sits against the
   Dhan stop, the thesis, the Chandelier and the initial stop, in ATR; whether the stop is in
   the noise band; how the trade has behaved since entry; the ladder's rung and whether the
   chart agrees with it.

DELIBERATION
CASE TO HOLD OR ADD   (weighted, best points first)
CASE TO TRIM OR EXIT   (each line ends with [FATAL] or [TOLERABLE])
WHERE THE LADDER AND S4 ARE TOO BLUNT

RECOMMENDATION
(The ruling line comes next. Begin it with "RULING:" and then ONE of: HOLD · ADD · TRIM ·
   REDUCE · EXIT, then a dash and the reason in one sentence with its number. Do not copy this note.)
RULING:
THESIS   (one of INTACT · WEAKENING · BROKEN, then the reason in one sentence with its number)
INVALIDATION   (the Daily close level that proves the thesis wrong NOW, its basis on the chart,
   and against the journal thesis in the HOLDING block: RAISE, KEEP or BROKEN. One line, a price.)
STOP   (KEEP <the Dhan stop> or RAISE TO <price> with its basis - never inside 3 x ATR14 of the
   close - or LOWER TO <price> only with "sell N shares first". One line.)
DRAWDOWN   (from the HOLDING block's DRAWDOWN rows: the cost to the thesis close, to the Dhan
   stop, and on the worst gap, and which of them is the realistic risk now. Two lines at most.)
OPPORTUNITY   (ADD at <level> with stop <price> and quantity at 1% risk - or NO ADD and why;
   then the next target and the partial plan: the canon T1 / T2 from the HOLDING block, whether
   reached, what to book there.)
WATCH   (the next level or event - results date, a Daily close - that decides this position)
FLIPS IF   (the one observation that would change the ruling, as a full sentence)

Write PLAIN TEXT. No LaTeX and no math markup. Write 2.5 x ATR, +3.4%, Rs 12,345 as plain characters.
"""


def hold_system() -> str:
    return _doctrine() + HOLD_JOB + _analysis_template() + HOLD_OUTPUT


# ---------------------------------------------------------------------------------------
# The HOLDING block - the SL Dashboard's own numbers (sl_board.build), cached for a run.
# ---------------------------------------------------------------------------------------
_CACHE: dict = {"t": 0.0, "rows": {}, "meta": {}}
CACHE_S = 1800


def _book(force: bool = False) -> tuple[dict, dict]:
    if force or not _CACHE["rows"] or time.time() - _CACHE["t"] > CACHE_S:
        import sl_board
        df, meta = sl_board.build()
        _CACHE.update(t=time.time(), meta=meta,
                      rows={str(r["symbol"]).upper(): r for r in df.to_dict("records")} if not df.empty else {})
    return _CACHE["rows"], _CACHE["meta"]


def holdings() -> list[str]:
    rows, _ = _book(force=True)
    return sorted(rows)


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _inr(x) -> str:
    v = _f(x)
    if v is None:
        return "-"
    try:
        from house_policy import format_inr  # type: ignore
        return format_inr(v)
    except Exception:
        neg, v = v < 0, abs(round(v))
        s = str(int(v))
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
            s = head + "," + tail
        return ("-Rs " if neg else "Rs ") + s


def _p(x, d: int = 2) -> str:
    v = _f(x)
    return "-" if v is None else ("%.*f" % (d, v))


def _ladder(sym: str) -> str:
    try:
        import pandas as pd
        p = os.path.join(HERE, "FINAL_Portfolio_Picks.csv")
        if os.path.exists(p):
            pf = pd.read_csv(p)
            r = pf[pf["Symbol"].astype(str).str.upper() == sym]
            if not r.empty:
                r = r.iloc[0]
                asof = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%d-%b %H:%M")
                return "%s - %s (add-SL %s) [as of the %s run; S4's MY TRADE row has the live rung]" % (
                    r.get("Pyr_Class"), r.get("Pyr_Trigger"), r.get("Add_SL"), asof)
    except Exception as e:
        return "unreadable (%s)" % e
    return "not in FINAL_Portfolio_Picks.csv"


def holding_row(sym: str) -> dict | None:
    rows, _ = _book()
    return rows.get(sym.split(":")[-1].upper())


def holding_block(sym: str) -> str:
    """The script-computed numbers for one holding, as text for the prompt."""
    s = sym.split(":")[-1].upper()
    r = holding_row(s)
    if not r:
        return "HOLDING: %s is not an open holding in the Dhan book (or is a v2 name)." % s
    try:
        import sl_board
        j = sl_board._journal_rows().get(s, {})
    except Exception:
        j = {}
    qty, avg, ltp, close = _f(r.get("qty")), _f(r.get("avg")), _f(r.get("ltp")), _f(r.get("close"))
    atr = _f(r.get("atr"))
    disaster, thesis, chand = _f(r.get("disaster")), _f(r.get("thesis")), _f(r.get("chand"))
    days = ""
    try:
        import pyramid_logic as pl
        if j.get("entry_date"):
            days = " · %s sessions held (entry %s)" % (pl.sessions_since(j.get("entry_date")), str(j.get("entry_date"))[:10])
    except Exception:
        if j.get("entry_date"):
            days = " · entry %s" % str(j.get("entry_date"))[:10]

    def dd(level):
        if not (level and ltp and qty):
            return "-"
        if level >= ltp:
            return "ALREADY THROUGH - this level sits above LTP (it has broken)"
        return "%s (%+.1f%%)" % (_inr((level - ltp) * qty), (level / ltp - 1) * 100)

    lines = [
        "HOLDING (computed by the script from Dhan + the journal - exact, quote these)",
        "%s · %s plan%s · %s %s · setup %s · origin %s"
        % (s, r.get("plan"), (" (%s)" % r["plan_src"]) if r.get("plan_src") else "", int(qty or 0), "shares",
           j.get("setup") or "-", j.get("origin") or "-") + days,
        "cost %s · LTP %s · last close %s (%s) · P&L %+.1f%% = %s"
        % (_p(avg), _p(ltp), _p(close), r.get("close_src"), _f(r.get("pnl_pct")) or 0.0,
           _inr(((ltp or 0) - (avg or 0)) * (qty or 0))),
        "ATR(D) %s (%s%% of price) · daily EMA20 %s · R now %s off the R unit (initial stop %s%s)"
        % (_p(atr), _p(r.get("atr_pct"), 1), _p(r.get("ema20")), _p(r.get("r_now")), _p(r.get("initial")),
           " - policy, no recorded stop" if r.get("initial_policy") else ""),
        "DHAN STOP (resting Disaster SL) %s - %s x ATR below LTP (%s)%s"
        % (_p(disaster), _p(r.get("dist_atr"), 1), r.get("noise") or "-",
           ("  ⚠ " + r["order_warn"]) if r.get("order_warn") else ""),
        "THESIS (journal, Daily close) %s - %s%s"
        % (_p(thesis), r.get("thesis_state") or "-", (" · " + r["thesis_vs_dhan"]) if r.get("thesis_vs_dhan") else ""),
        "CHANDELIER %s (%sx)%s · house 3xATR stop %s"
        % (_p(chand), r.get("chand_mult") or "-", " ⚠ AT/ABOVE LTP - exit review" if r.get("chand_breach") is True else "",
           (_p(r.get("rec_sl")) + " (same-risk qty %s)" % int(_f(r.get("rec_qty")) or 0)) if _f(r.get("rec_sl"))
           else "- the Dhan stop is already >= 3xATR below LTP"),
        "TARGETS resting at Dhan T1 %s / T2 %s · canon off the R unit T1 %s / T2 %s"
        % (_p(r.get("t1")), _p(r.get("t2")), _p(r.get("rec_t1")), _p(r.get("rec_t2"))),
        ("IF THE DHAN STOP FILLS it LOCKS a profit of %s (stop above cost)" % _inr(-(_f(r.get("loss_if_stopped")) or 0))
         if (_f(r.get("loss_if_stopped")) or 0) < 0 else
         "RISK if the Dhan stop fills (from cost) %s vs the per-trade rule %s%s"
         % (_inr(r.get("loss_if_stopped")), _inr(r.get("budget")),
            (" ⚠ OVER - %s shares fit" % int(_f(r.get("fit_qty")))) if r.get("over_budget") is True and _f(r.get("fit_qty")) else ""))
        + " · open risk from LTP %s" % _inr(r.get("open_risk")),
        "GAP: worst overnight gap in 2 years %s%% (%s); repeated from LTP it opens at %s%s"
        % (_p(r.get("gap_worst"), 1), r.get("gap_worst_date") or "-", _p(r.get("gapw")),
           " - THROUGH the Dhan stop, fills there" if r.get("gap_through") is True else ""),
        "EARNINGS: %s" % (("in %d days (%s)" % (_f(r["earn_days"]), r.get("earn_date"))) if _f(r.get("earn_days")) is not None
                          else "unknown (no date in the earnings cache)"),
        "LADDER (pyramid engine): %s" % _ladder(s),
        "DRAWDOWN from LTP (cost of each scenario on the whole position):",
        "  to the thesis close %s    %s" % (_p(thesis), dd(thesis)),
        "  to the Dhan stop %s       %s" % (_p(disaster), dd(disaster)),
        "  to the Chandelier %s      %s" % (_p(chand), dd(chand)),
        "  on the worst gap %s       %s" % (_p(r.get("gapw")), dd(_f(r.get("gapw")))),
    ]
    if _f(r.get("plan_qty")):
        lines.append("PLANNED QTY on the SL Dashboard: %s (%s)" % (int(_f(r["plan_qty"])), r.get("plan_note") or ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------
# House-rule checks on the answer. Text only: nothing is written anywhere.
# ---------------------------------------------------------------------------------------
_NUMRX = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\d%]|\s*[Rx×])")


def _line(review: str, tag: str) -> str:
    for ln in review.splitlines():
        t = ln.replace("*", "").strip().lstrip("#• ").strip()
        if t.upper().startswith(tag):
            rest = t[len(tag):].lstrip(" :-—").strip()
            if rest and not rest.startswith("("):
                return rest
    return ""


def _num(txt: str):
    m = _NUMRX.search(txt or "")
    return float(m.group(1).replace(",", "")) if m else None


def ruling_word(review: str) -> str:
    m = re.match(r"(HOLD|ADD|TRIM|REDUCE|EXIT)", _line(review, "RULING").upper())
    return m.group(1) if m else ""


def post_checks(sym: str, review: str) -> tuple[str, list[str]]:
    """(review with any house-rule overrule applied, check lines to append)."""
    r = holding_row(sym) or {}
    out = []
    ltp, avg, close = _f(r.get("ltp")), _f(r.get("avg")), _f(r.get("close")) or _f(r.get("ltp"))
    atr, dhan, thesis = _f(r.get("atr")), _f(r.get("disaster")), _f(r.get("thesis"))
    word = ruling_word(review)

    if word == "ADD":
        why = ""
        if ltp and avg and ltp < avg:
            why = "the position is below cost - no averaging down"
        else:
            try:
                import house_policy as hp
                e = hp.exposure_status()
                if e.get("pause_until") or not e.get("adds_ok"):
                    why = ("circuit breaker until %s" % e["pause_until"]) if e.get("pause_until") \
                        else "adds are not allowed in the %s tier" % e.get("tier")
            except Exception as ex:
                why = "exposure rule unreadable (%s) - an add is not confirmed" % str(ex)[:60]
        if why:
            review = re.sub(r"(RULING:?\**:?\s*\**\s*)ADD", r"\1HOLD (house rule: %s; the model had ruled ADD)" % why,
                            review, count=1)
            out.append("ADD-CHECK: overruled to HOLD - %s" % why)
        else:
            out.append("ADD-CHECK: an add is allowed by the exposure tier - size it at 1% risk off the raised stop")

    inv = _num(_line(review, "INVALIDATION"))
    if inv is None:
        out.append("INVALIDATION-CHECK: no level could be read from the INVALIDATION line")
    else:
        msg = "INVALIDATION-CHECK: %.2f" % inv
        if dhan and atr and abs(inv - dhan) <= 0.25 * atr:
            out.append("INVALIDATION-CHECK: %.2f is the Dhan stop itself - the two-tier rule wants the thesis on "
                       "structure, about 1 x ATR (%.2f) ABOVE the Disaster SL; read the chart's zones / swing lows "
                       "for the real level" % (inv, atr))
            inv = None
        if inv is None:
            pass
        elif close and inv >= close:
            msg += " is AT/ABOVE the last close %.2f - not an invalidation level, the thesis is already broken" % close
        elif thesis and inv < thesis - 0.005 * thesis:
            msg += (" is BELOW the journal thesis %.2f - the thesis is never lowered (that widens risk); "
                    "read it as WEAKENING/BROKEN, or lower it yourself on the SL Dashboard (sell-first)" % thesis)
        elif thesis and inv > thesis * 1.001:
            room = (close - inv) / atr if (close and atr) else None
            msg += " RAISES the thesis from %.2f" % thesis
            if room is not None and room < 1.0:
                msg += " - but it is only %.1f x ATR below the close; the ratchet needs >= 1 x ATR" % room
            else:
                msg += " - the evening ratchet does the same when S4's INVAL agrees; or set it on the SL Dashboard"
        else:
            msg += " - keeps the journal thesis %s" % (_p(thesis) if thesis else "(none recorded)")
        if inv is not None:
            out.append(msg)

    st = _line(review, "STOP")
    stv = _num(st)
    up = st.upper()
    if "RAISE" in up and stv:
        msg = "STOP-CHECK: raise to %.2f" % stv
        cap = (close - 3 * atr) if (close and atr) else None
        if dhan and stv <= dhan:
            msg += " is not above the resting Dhan stop %.2f - nothing to raise" % dhan
        elif cap and stv > cap + 0.01:
            msg += (" is inside 3 x ATR of the close - the house maximum for a Dhan stop is %.2f "
                    "(close %.2f - 3 x %.2f)" % (cap, close, atr))
        else:
            msg += " fits the house rule (>= 3 x ATR below the close) - place it via SL Dashboard › Change a Disaster SL"
        out.append(msg)
    elif "LOWER" in up and stv:
        try:
            import gap_risk as gr
            allowed, sell = gr.lower_stop_qty(r.get("qty"), avg, stv, r.get("budget"))
        except Exception:
            allowed = sell = None
        if sell:
            out.append("STOP-CHECK: lower to %.2f needs %d shares SOLD FIRST (%s fit the per-trade rule)" % (stv, sell, allowed))
        elif sell == 0:
            out.append("STOP-CHECK: lower to %.2f keeps the per-trade rule at the current quantity" % stv)
        else:
            out.append("STOP-CHECK: lower to %.2f - sell-first quantity could not be computed" % stv)
    elif "KEEP" in up:
        out.append("STOP-CHECK: keep the Dhan stop %s" % _p(dhan))
    else:
        out.append("STOP-CHECK: no KEEP / RAISE / LOWER could be read from the STOP line")
    return review, out


# ---------------------------------------------------------------------------------------
# The review of one holding - called by s4_review.review_one when source == "portfolio",
# after the chart has been switched and read (so the alert receiver's queue path and the
# in-process path are the same code).
# ---------------------------------------------------------------------------------------
def review_holding(d: dict, read_txt: str, args) -> dict:
    import s4_review as s4
    sym = d["symbol"].split(":")[-1].upper()
    block = holding_block(sym)
    note, _, _ = s4.exposure_gate("HELD")
    pre = ("PRE-READ (computed by the script, not negotiable)\n%s\n\n" % note) if note else ""
    mc = s4.market_context()
    if mc:
        pre += mc + "\n\n"
    oi, _ = s4.oi_digest(read_txt)
    if oi:
        pre += oi + "\n\n"
    prompt = (pre + block + "\n\n" + read_txt +
              "\n\nDeliberate now, as the holder. S4's VERDICT and SUMMARY rows are one mechanical "
              "opinion written for a NEW entry; weigh them last.")
    system = hold_system()
    review, prov = s4.deliberate(prompt, args.provider, system=system)
    if not ruling_word(review):
        review2, prov2 = s4.deliberate(prompt + "\n\nYOUR PREVIOUS ANSWER HAD NO RULING LINE. Write "
                                       "'RULING: HOLD|ADD|TRIM|REDUCE|EXIT - reason' and the INVALIDATION, "
                                       "STOP, DRAWDOWN and OPPORTUNITY lines.", args.provider, system=system)
        if ruling_word(review2):
            review, prov = review2, prov2
    review, checks = post_checks(sym, review)
    _, oi_txt = s4.oi_digest(read_txt)
    for extra in checks + ([oi_txt] if oi_txt else []):
        review = review.rstrip() + "\n\n" + extra
    review = review.rstrip() + "\n\n---\n" + block
    path = s4.save_review(d["symbol"], d["res"], read_txt, review, prov, s4.s4_verdict_line(d), SOURCE)
    head = "%s · %s · portfolio · %s" % (d["symbol"], d["res"], prov)
    print("\n" + head + "\n" + "-" * len(head) + "\n" + review + "\n\nsaved " + os.path.relpath(path, HERE))
    if getattr(args, "telegram", False):
        s4.telegram(summary(review, sym))
    return {"rc": 0, "review": review, "path": path, "head": head, "symbol": d["symbol"], "tf": d["res"]}


def summary(review: str, sym: str) -> str:
    """The Telegram-sized cut of one holding review."""
    parts = ["💼 PORTFOLIO · %s" % sym]
    for tag in ("RULING", "THESIS", "INVALIDATION", "STOP", "DRAWDOWN", "OPPORTUNITY", "WATCH"):
        v = _line(review, tag)
        if v:
            parts.append("%s: %s" % (tag, v[:300]))
    for ln in review.splitlines():
        if ln.startswith(("ADD-CHECK", "INVALIDATION-CHECK", "STOP-CHECK")):
            parts.append(ln[:240])
    return "\n".join(parts)


# ---------------------------------------------------------------------------------------
# The run summary
# ---------------------------------------------------------------------------------------
def _today_rows(since: datetime | None = None) -> list[dict]:
    import s4_review as s4
    if not os.path.exists(s4.LOG_CSV):
        return []
    with open(s4.LOG_CSV, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("source") or "") == SOURCE]
    day = (since or datetime.now()).strftime("%Y-%m-%d")
    rows = [r for r in rows if str(r.get("ts", "")).startswith(day)]
    if since:
        rows = [r for r in rows if str(r.get("ts", "")) >= since.strftime("%Y-%m-%d %H:%M")]
    last = {}
    for r in rows:                      # the latest review per symbol
        last[str(r.get("symbol")).upper()] = r
    return list(last.values())


def build_report(since: datetime | None = None, send_telegram: bool = False) -> str:
    rows = _today_rows(since)
    os.makedirs(REPORT_DIR, exist_ok=True)
    now = datetime.now()
    path = os.path.join(REPORT_DIR, "Portfolio_Review_%s.md" % now.strftime("%Y%m%d"))
    lines = ["# Portfolio review · %s IST" % now.strftime("%d %b %Y %H:%M"), "",
             "%d holdings reviewed on the Daily chart. Every number below is a proposal - nothing was "
             "placed or written to the journal." % len(rows), "",
             "| Holding | Ruling | Thesis | Invalidation | Stop | Drawdown | Opportunity | Review |",
             "|---|---|---|---|---|---|---|---|"]
    tele = ["💼 PORTFOLIO REVIEW · %d holdings" % len(rows)]
    order = {"EXIT": 0, "REDUCE": 1, "TRIM": 2, "ADD": 3, "HOLD": 4, "": 5}
    full = []
    for r in rows:
        f = os.path.join(HERE, r.get("file", ""))
        try:
            body = open(f, encoding="utf-8").read()
        except Exception:
            body = ""
        rev = body.split("## PANEL READ")[0] if body else ""
        word = ruling_word(rev)
        cells = [_line(rev, t) for t in ("THESIS", "INVALIDATION", "STOP", "DRAWDOWN", "OPPORTUNITY")]
        full.append((order.get(word, 5), r["symbol"], word, cells, r.get("file", ""), _line(rev, "RULING")))
    full.sort()
    for _, sym, word, cells, fpath, rl in full:
        clip = [c.replace("|", "/")[:140] for c in cells]
        lines.append("| %s | %s | %s | %s | %s | %s | %s | [%s](../../%s) |"
                     % (sym, (rl or word).replace("|", "/")[:120], *clip, os.path.basename(fpath),
                        fpath.replace("\\", "/")))
        ico = {"EXIT": "🔴", "REDUCE": "🟠", "TRIM": "🟡", "ADD": "🟢", "HOLD": "⚪"}.get(word, "▫")
        inv = _num(cells[1])
        why = re.sub(r"^(HOLD|ADD|TRIM|REDUCE|EXIT)\s*[-—:]*\s*", "", rl or "", flags=re.I)
        if word in ("EXIT", "REDUCE", "TRIM", "ADD"):
            # an ACTION: the reason, the new invalidation and the stop line, so it reads without the page
            tele.append("%s %s · %s — %s\n     inval %s · stop %s"
                        % (ico, sym, word, why[:150], ("%.2f" % inv) if inv else "-", cells[2][:90] or "-"))
        else:
            tele.append("%s %s · %s · thesis %s · inval %s"
                        % (ico, sym, word or "?", (cells[0].split() or ["?"])[0], ("%.2f" % inv) if inv else "-"))
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\nreport: " + os.path.relpath(path, HERE))
    if send_telegram:
        import s4_review as s4
        n_act = sum(1 for f in full if f[2] in ("EXIT", "REDUCE", "TRIM", "ADD"))
        tele[0] += " · %d to act on" % n_act
        tele.append("\nProposals only. Full reviews: Web Commander › PORTFOLIO, and the Reviewer Log.")
        s4.telegram("\n".join(tele))
    return path


# ---------------------------------------------------------------------------------------
# The Portfolio page view (Web Commander › PORTFOLIO). Reads the Reviewer Log, so it shows
# whichever run is latest - the weekday auto-pilot phase or the Saturday task.
# ---------------------------------------------------------------------------------------
def latest_reviews() -> list[dict]:
    """The most recent portfolio review per OPEN holding: dict with symbol, ts, file, the
    recommendation lines and the script's check lines. Sold names drop out."""
    import s4_review as s4
    if not os.path.exists(s4.LOG_CSV):
        return []
    with open(s4.LOG_CSV, encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("source") or "") == SOURCE]
    last = {}
    for r in rows:
        last[str(r.get("symbol")).upper()] = r
    try:
        import sl_board
        held = set(sl_board._journal_rows())
    except Exception:
        held = set(last)
    out = []
    for sym, r in last.items():
        if held and sym not in held:
            continue
        try:
            body = open(os.path.join(HERE, r.get("file", "")), encoding="utf-8").read()
        except Exception:
            body = ""
        rev = body.split("## PANEL READ")[0]
        d = {"symbol": sym, "ts": r.get("ts", ""), "file": r.get("file", ""), "provider": r.get("provider", ""),
             "ruling_word": ruling_word(rev), "review": rev,
             "checks": [ln.strip() for ln in rev.splitlines()
                        if ln.startswith(("ADD-CHECK", "INVALIDATION-CHECK", "STOP-CHECK"))]}
        for tag in ("RULING", "THESIS", "INVALIDATION", "STOP", "DRAWDOWN", "OPPORTUNITY", "WATCH", "FLIPS IF"):
            d[tag] = _line(rev, tag)
        out.append(d)
    order = {"EXIT": 0, "REDUCE": 1, "TRIM": 2, "ADD": 3, "HOLD": 4, "": 5}
    out.sort(key=lambda x: (order.get(x["ruling_word"], 5), x["symbol"]))
    return out


def render_streamlit() -> None:
    import pandas as pd
    import streamlit as st
    st.markdown("#### 🧭 AI holdings review — every holding read like a new trade (Daily chart)")
    revs = latest_reviews()
    if not revs:
        st.info("No portfolio review yet. It runs after the close on weekdays (auto-pilot Phase 13b) and on "
                "Saturday 09:30, or now: PORTFOLIO_REVIEW.bat.")
        return
    newest = max(r["ts"] for r in revs)
    oldest = min(r["ts"] for r in revs)
    cnt = {}
    for r in revs:
        cnt[r["ruling_word"] or "?"] = cnt.get(r["ruling_word"] or "?", 0) + 1
    icon = {"EXIT": "🔴", "REDUCE": "🟠", "TRIM": "🟡", "ADD": "🟢", "HOLD": "⚪", "?": "▫"}
    st.caption("%d holdings · reviewed %s%s · %s · proposals only - nothing is placed or written to the journal"
               % (len(revs), newest, ("" if oldest[:10] == newest[:10] else " (oldest %s)" % oldest),
                  "  ".join("%s %s %d" % (icon.get(k, "▫"), k, v) for k, v in cnt.items())))
    tbl = pd.DataFrame([{
        "Holding": r["symbol"], "Ruling": "%s %s" % (icon.get(r["ruling_word"] or "?", "▫"), r["RULING"][:110]),
        "Thesis": r["THESIS"][:80], "Invalidation": r["INVALIDATION"][:110], "Stop": r["STOP"][:90],
        "Drawdown": r["DRAWDOWN"][:110], "Opportunity": r["OPPORTUNITY"][:110],
        "Checks": ("⚠ %d" % sum(1 for c in r["checks"] if any(w in c for w in
                   ("BELOW", "AT/ABOVE", "inside 3", "Dhan stop itself", "overruled", "SOLD FIRST", "only")))) or "",
        "Reviewed": r["ts"]} for r in revs])
    st.dataframe(tbl, width="stretch", hide_index=True)
    for r in revs:
        with st.expander("%s %s · %s · %s" % (icon.get(r["ruling_word"] or "?", "▫"), r["symbol"],
                                             r["ruling_word"] or "?", r["ts"])):
            for c in r["checks"]:
                st.markdown("`%s`" % c)
            st.markdown(r["review"].replace("\n", "  \n"))
            st.caption("file: %s · %s" % (r["file"], r["provider"]))


# ---------------------------------------------------------------------------------------
def _receiver_up() -> bool:
    try:
        import requests
        return requests.get(RECEIVER + "/health", timeout=3).status_code < 500
    except Exception:
        return False


def _queue(syms: list[str]) -> list[str]:
    import requests
    key = os.getenv("S4_REVIEW_KEY") or os.getenv("WEBHOOK_SECRET") or ""
    queued = []
    for s in syms:
        try:
            r = requests.post(RECEIVER + "/s4-review", params={"key": key},
                              data=("%s S4 GO D - portfolio" % s).encode(), timeout=10)
            js = r.json() if r.status_code == 200 else {}
            print("  %-12s %s" % (s, js.get("status") or r.status_code), js.get("reason", ""))
            if js.get("queued"):
                queued.append(s)
        except Exception as e:
            print("  %-12s queue failed: %s" % (s, e))
    return queued


def _wait_for(syms: list[str], since: datetime, timeout_s: int) -> None:
    want = {s.upper() for s in syms}
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        done = {str(r.get("symbol")).upper() for r in _today_rows(since)}
        left = want - done
        print("  %d/%d reviewed%s" % (len(want) - len(left), len(want),
                                       ("  (waiting: %s)" % ", ".join(sorted(left))) if left else ""), flush=True)
        if not left:
            return
        time.sleep(30)
    print("  timed out - run `python portfolio_review.py --report` once the queue has finished")


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", help="comma list of holdings (default: every holding)")
    ap.add_argument("--direct", action="store_true", help="review in-process even if the receiver is up")
    ap.add_argument("--provider", choices=["auto", "claude", "gemini"], default="auto")
    ap.add_argument("--telegram", action="store_true", help="send the run summary to Telegram")
    ap.add_argument("--dump", metavar="SYM", help="print one holding's HOLDING block and exit")
    ap.add_argument("--report", action="store_true", help="rebuild today's summary and exit")
    ap.add_argument("--no-wait", action="store_true",
                    help="queue on the receiver and return (auto-pilot); a detached watcher sends the summary")
    ap.add_argument("--await", dest="await_syms", metavar="SYMS",
                    help="(internal) wait until these holdings are reviewed, then build + send the summary")
    ap.add_argument("--since", help="(internal, with --await) the run's start, YYYY-MM-DDTHH:MM")
    args = ap.parse_args()

    if args.await_syms:
        since = datetime.fromisoformat(args.since) if args.since else datetime.now().replace(second=0, microsecond=0)
        syms = [s for s in args.await_syms.split(",") if s]
        _wait_for(syms, since, timeout_s=240 * len(syms) + 1800)
        build_report(since, send_telegram=args.telegram)
        return 0
    if args.dump:
        print(holding_block(args.dump))
        return 0
    if args.report:
        build_report(send_telegram=args.telegram)
        return 0

    syms = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else holdings()
    _, meta = _book()
    print("portfolio review: %d holdings%s: %s" % (len(syms),
          (" (v2 names skipped: %d)" % meta.get("v2_skipped")) if meta.get("v2_skipped") else "", ", ".join(syms)))
    if not syms:
        return 0
    since = datetime.now().replace(second=0, microsecond=0)

    if not args.direct and _receiver_up():
        print("queueing through the alert receiver (one at a time, ~90 s each, never over an S4 GO review):")
        queued = _queue(syms)
        if args.no_wait:
            # The auto-pilot must not sit on the queue for ~25 minutes, but the summary has to wait
            # for the last review: a detached watcher does the waiting and sends it (Jay, 31-Oct).
            if queued:
                import subprocess
                os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
                _log = open(os.path.join(HERE, "logs", "portfolio_review.log"), "a", encoding="utf-8")
                _log.write("\n=== %s watcher for %s\n" % (since.isoformat(timespec="minutes"), ",".join(queued)))
                _log.flush()
                cmd = [sys.executable, os.path.abspath(__file__), "--await", ",".join(queued),
                       "--since", since.isoformat(timespec="minutes")] + (["--telegram"] if args.telegram else [])
                flags = (getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                         | getattr(subprocess, "CREATE_NO_WINDOW", 0))
                subprocess.Popen(cmd, cwd=HERE, stdout=_log, stderr=subprocess.STDOUT, creationflags=flags, close_fds=True)
            print("portfolio review: %d of %d queued on the receiver (one at a time, ~90 s each); summary%s when done"
                  % (len(queued), len(syms), " to Telegram" if args.telegram else ""))
            return 0 if len(queued) == len(syms) else 1
        if queued:
            _wait_for(queued, since, timeout_s=240 * len(queued) + 300)
        build_report(since, send_telegram=args.telegram)
        return 0

    import types
    import s4_review as s4
    a = types.SimpleNamespace(bars=s4.BARS_N, dump=False, provider=args.provider, telegram=False, source=SOURCE)
    failed = []
    for s in syms:
        try:
            s4.review_one(s, TF, a)
        except Exception as e:
            print("%s: %s" % (s, e), file=sys.stderr)
            failed.append(s)
    if failed:
        print("\nnot reviewed: %s  (re-run with --symbols %s)" % (", ".join(failed), ",".join(failed)))
    try:
        import build_review_portal
        build_review_portal.build()
    except Exception as e:
        print("portal rebuild failed: %s" % e, file=sys.stderr)
    build_report(since, send_telegram=args.telegram)
    print("portfolio review: %d of %d reviewed in-process" % (len(syms) - len(failed), len(syms)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
