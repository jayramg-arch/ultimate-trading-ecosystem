"""morning_digest.py - the pre-market Telegram (3-Oct-2026, Jay). Task Scheduler
`Morning_Digest`, 08:45 IST, trading days only.

What to ACT on today, nothing else:
  * EXIT REVIEW - holdings whose catalyst-aware Chandelier is at or above the last price,
    with the resting stop beside it. Stops are managed by hand (the automated trail cannot
    modify orders - Dhan DH-905, no whitelisted IP), so this list is the trail.
  * earnings inside the next 7 days for open positions (a binary event changes SIZE);
  * the market line (regime, breadth, McClellan).

    python morning_digest.py            build + send
    python morning_digest.py --print    build, print, send nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from digest_common import HERE, exit_review, exit_review_lines, market_line, now_ist, send


def earnings_soon(days: int = 7) -> list[str]:
    p = os.path.join(HERE, "data", "earnings_dates.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return []
    dates = d.get("dates", d) if isinstance(d, dict) else {}
    today = now_ist().date()
    out = []
    for sym, v in sorted(dates.items()):
        try:
            when = dt.date.fromisoformat(str(v.get("date") if isinstance(v, dict) else v)[:10])
        except Exception:
            continue
        n = (when - today).days
        if 0 <= n <= days:
            out.append("  %s in %dd (%s)" % (sym, n, when.strftime("%d %b")))
    return out


def earnings_sizing(lines: list[str]) -> list[str]:
    """29-Oct-2026: each earnings line gains the GAP-SIZED holding - the shares whose loss stays
    inside the per-trade rule if the stock repeats its worst 2-year overnight gap from today
    (gap_risk via sl_board, the SL Dashboard's own numbers). A result is a gap you can see coming;
    the stop does not cap it. Best-effort: on any failure the plain lines are returned."""
    syms = [ln.split()[0] for ln in lines if ln.strip()]
    try:
        import sl_board
        df, _ = sl_board.build(symbols=syms)
        rows = {r["symbol"]: r for r in df.to_dict("records")} if len(df) else {}
    except Exception as e:
        return lines + ["  (gap sizing unavailable: %s)" % str(e)[:60]]
    out = []
    for ln in lines:
        r = rows.get(ln.split()[0]) if ln.strip() else None
        if not r:
            continue                 # not held: the cache also carries board names (29-Oct-2026)
        if r.get("gap_worst") is None:
            out.append(ln)
            continue
        q, fit, loss, rule = int(r["qty"]), r.get("gap_fit_qty"), r.get("gap_loss"), r.get("budget") or 0
        if loss is None or loss <= rule * 1.05 or fit is None or fit >= q:
            out.append(ln + " - worst gap (%.1f%%) stays inside the rule at %d sh" % (r["gap_worst"], q))
        else:
            out.append(ln + " - hold %d -> gap-sized %d (sell %d before); worst gap %.1f%% costs Rs %s vs rule Rs %s"
                       % (q, fit, q - fit, r["gap_worst"], f"{loss:,.0f}", f"{rule:,.0f}"))
    return out


def build() -> str:
    t = now_ist()
    L = ["MORNING · %s" % t.strftime("%a %d %b %Y %H:%M IST")]
    mk = market_line()
    if mk:
        L += ["", "MARKET: " + mk]
    rows, err = exit_review()
    L.append("")
    if err:
        L.append("EXIT REVIEW: not available - %s" % err)
    elif rows:
        L.append("EXIT REVIEW · %d holding(s) at/below their Chandelier (your stops are set by hand):" % len(rows))
        L += exit_review_lines(rows)
        L.append("  CE = catalyst-aware Chandelier; % = LTP vs CE. Review each: exit, or tighten the stop.")
    else:
        L.append("EXIT REVIEW: no holding is below its Chandelier.")
    try:
        from digest_common import thesis_lines
        L += [""] + thesis_lines()
    except Exception as e:
        L += ["", "THESIS: failed (%s)" % str(e)[:80]]
    es = earnings_sizing(earnings_soon()) if earnings_soon() else []
    if es:
        L += ["", "EARNINGS within 7 days, holdings (size, not direction):"] + es
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args()
    try:
        import nse_calendar
        if not a.print and not nse_calendar.is_trading_day(now_ist().date()):
            print("not a trading day - no morning digest")
            return 0
    except Exception:
        pass
    txt = build()
    print(txt)
    if not a.print:
        print("sent" if send(txt) else "NOT SENT (Telegram) - copy in reports/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
