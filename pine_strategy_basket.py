# -*- coding: utf-8 -*-
"""Per-catalyst attribution from the Unified Ecosystem's Strategy Tester.

WHY THIS EXISTS. Every backtest in this project runs in Python on replay.py, while the
alerts that actually reach Jay fire from PINE. Those are two implementations of one
signal surface and the Pine one has never been measured. The Unified Ecosystem is a
strategy(), so TradingView already backtests it — and its trade list names the catalyst
on every entry and the reason on every exit:

    {"c": "SWG-PB",    "b": true,  "p": 103.1}   entry
    {"c": "50MA Fail", "b": false, "p": 103.6}   exit

so win rate and expectancy per catalyst can be computed from the pairs directly,
without scraping the summary pane.

WHAT IT IS NOT. The Strategy Tester applies UNIFIED'S OWN exits (50MA Fail, trailing
stop, time stop), not the Chandelier/GTT that Jay actually trades. So these numbers are
a SIGNAL-QUALITY measure and never a return estimate. Read the win rate and the
per-catalyst ordering; ignore the rupee P&L.

AND DO NOT READ IT PER SYMBOL. A catalyst fires 5-20 times on one name over the full
history. This codebase has already published one confident result off 4-16 name cells
and had to walk it back. Aggregate across the basket or do not use it.

USAGE — collection is manual because the trade list comes from the TradingView MCP:

    1. for each symbol: set the chart, then data_get_trades(max_trades=...)
    2. append the raw list to a per-run JSON:  {"SYMBOL": [ ...trades... ], ...}
    3. python pine_strategy_basket.py runs/<label>.json --label "post-sector-migration"

Re-run after a change and diff the two labels: that is the whole point — to know
whether a change improved the signal surface or merely moved it.
"""
from __future__ import annotations
import argparse
import json
import os
from collections import defaultdict

OUT = os.path.join("validation_runs", "pine_basket_attribution.csv")


def pair_trades(trades: list) -> list:
    """Fold the flat entry/exit stream into round trips.

    The list alternates entry (b=true) and exit (b=false) per position. An unmatched
    trailing entry is an OPEN position and is dropped rather than closed at the last
    price — a synthetic exit would invent a result that has not happened yet.
    """
    out, open_entry = [], None
    for t in trades:
        if t.get("b"):
            open_entry = t
        elif open_entry is not None:
            ep, xp = float(open_entry.get("p") or 0), float(t.get("p") or 0)
            if ep > 0:
                out.append({"catalyst": str(open_entry.get("c") or "?").strip(),
                            "exit_reason": str(t.get("c") or "?").strip(),
                            "entry": ep, "exit": xp,
                            "ret_pct": (xp - ep) / ep * 100.0})
            open_entry = None
    return out


def main(path: str, label: str) -> int:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    by_cat, by_exit, per_symbol = defaultdict(list), defaultdict(list), {}
    for sym, trades in raw.items():
        rt = pair_trades(trades)
        per_symbol[sym] = len(rt)
        for r in rt:
            by_cat[r["catalyst"]].append(r)
            by_exit[r["exit_reason"]].append(r)

    def stats(rows):
        n = len(rows)
        if not n:
            return None
        wins = [r for r in rows if r["ret_pct"] > 0]
        avg = sum(r["ret_pct"] for r in rows) / n
        med = sorted(r["ret_pct"] for r in rows)[n // 2]
        gp = sum(r["ret_pct"] for r in wins)
        gl = -sum(r["ret_pct"] for r in rows if r["ret_pct"] <= 0)
        return {"n": n, "win_pct": len(wins) / n * 100.0, "avg_pct": avg,
                "median_pct": med, "profit_factor": (gp / gl) if gl > 0 else float("inf")}

    print(f"=== {label} ===")
    print(f"  symbols: {len(raw)}   round trips: {sum(per_symbol.values())}")
    print("\n  BY CATALYST   (signal quality — NOT a return estimate)")
    print("    %-14s %5s %7s %9s %9s %7s" % ("catalyst", "n", "win%", "avg%", "median%", "PF"))
    rows_out = []
    for cat, rows in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        s = stats(rows)
        print("    %-14s %5d %6.1f%% %8.2f%% %8.2f%% %7.2f"
              % (cat, s["n"], s["win_pct"], s["avg_pct"], s["median_pct"], s["profit_factor"]))
        rows_out.append((label, "catalyst", cat, s))
    print("\n  BY EXIT REASON   (where the edge is given back)")
    for ex, rows in sorted(by_exit.items(), key=lambda kv: -len(kv[1])):
        s = stats(rows)
        print("    %-14s %5d %6.1f%% %8.2f%%" % (ex, s["n"], s["win_pct"], s["avg_pct"]))
        rows_out.append((label, "exit", ex, s))

    # Sample-size honesty: a cell this small is not evidence, and saying so in the
    # output stops it being quoted later as though it were.
    thin = [c for c, r in by_cat.items() if len(r) < 30]
    if thin:
        print("\n  ⚠ under 30 round trips, treat as indicative only: " + ", ".join(sorted(thin)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    new = not os.path.exists(OUT)
    with open(OUT, "a", encoding="utf-8", newline="") as fh:
        if new:
            fh.write("label,dimension,key,n,win_pct,avg_pct,median_pct,profit_factor\n")
        for lab, dim, key, s in rows_out:
            fh.write("%s,%s,%s,%d,%.2f,%.4f,%.4f,%.4f\n"
                     % (lab, dim, key, s["n"], s["win_pct"], s["avg_pct"],
                        s["median_pct"], min(s["profit_factor"], 999.0)))
    print(f"\n  appended -> {OUT}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--label", default="unlabelled")
    raise SystemExit(main(ap.parse_args().path, ap.parse_args().label))
