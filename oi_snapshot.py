# -*- coding: utf-8 -*-
"""EOD option-chain snapshot — so the walls become observable over time.

WHY THIS EXISTS. The option chain is a LIVE read: nothing is stored, so a question
like "has the call wall moved from 1200 to 1300?" is unanswerable today. That
question is the whole of Phase 5 trade management, and it is also the only route to
ever validating an options-OI rule - no history exists in any feed wired to this
system, which is why every options read currently has to stay a read and never a
gate. One row per symbol per day starts fixing that.

WHAT IT DOES NOT DO. It draws no conclusion and gates nothing. It records what the
chain said at the close, and reports what MOVED since the previous snapshot. That
is deliberate: six additions to this system have been tested and rejected, one of
them backwards, so a new signal earns its way in on measured history rather than on
a plausible story.

MISSING IS NOT ZERO. Every field is None when unreadable, never 0. Three of these
travel to the chart as drawn price levels, and a max pain of 0 renders as a
confident line below every stop.

RUN AT/AFTER THE CLOSE. Intraday the chain is still moving; the value of this file
is that each row is a SETTLED reading. Dhan rate-limits to one chain per ~3s, so a
23-name board takes ~70s and the full F&O list ~10 min.

    python oi_snapshot.py                 # F&O names on the GM board + open holdings
    python oi_snapshot.py --universe all   # every F&O underlying (slow)
    python oi_snapshot.py --report         # what moved since the previous snapshot
"""
from __future__ import annotations
import argparse, datetime as dt, os, sys, warnings
warnings.filterwarnings("ignore")

import pandas as pd

OUT = os.path.join("data", "oi_snapshots.csv")
COLS = ["date", "symbol", "spot", "expiry", "pcr", "max_pain",
        "total_ce_oi", "total_pe_oi", "put_wall", "call_wall"]


def _walls(chain: dict) -> tuple:
    """Max-OI CE strike at/above spot and PE strike at/below spot. None, never 0."""
    df, spot = chain.get("chain_df"), chain.get("spot")
    if df is None or getattr(df, "empty", True) or not spot:
        return None, None
    cols = {c.lower(): c for c in df.columns}
    sc = cols.get("strikeprice") or cols.get("strike")
    ce = cols.get("ce_oi") or cols.get("openinterest_ce") or cols.get("ce_openinterest")
    pe = cols.get("pe_oi") or cols.get("openinterest_pe") or cols.get("pe_openinterest")
    if not (sc and ce and pe):
        return None, None
    up, dn = df[df[sc] >= spot], df[df[sc] <= spot]
    cw = float(up.loc[up[ce].idxmax(), sc]) if len(up) and up[ce].notna().any() else None
    pw = float(dn.loc[dn[pe].idxmax(), sc]) if len(dn) and dn[pe].notna().any() else None
    return pw, cw


def universe(kind: str) -> list:
    import dhan_ohlcv as dh
    fno = dh.get_fno_underlyings()
    if kind == "all":
        return sorted(fno)
    names = set()
    for tf in ("75m", "125m", "Daily"):
        p = "gm_board_cache_%s.csv" % tf
        if os.path.exists(p):
            names |= set(pd.read_csv(p)["Symbol"].dropna().astype(str))
    try:                                    # open holdings matter even off the board
        import sqlite3
        c = sqlite3.connect("trade_journal_v6.db")
        names |= {r[0] for r in c.execute(
            "SELECT symbol FROM journal WHERE UPPER(status)='OPEN'")}
    except Exception as e:
        print("  (journal unreadable, board only: %s)" % e)
    return sorted(n for n in names if dh.canonical_nse_symbol(str(n)) in fno)


def snap(kind: str) -> int:
    import nse_options as no, dhan_ohlcv as dh
    syms = universe(kind)
    today = dt.date.today().strftime("%Y-%m-%d")
    prev = pd.read_csv(OUT) if os.path.exists(OUT) else pd.DataFrame(columns=COLS)
    done = set(prev[prev["date"] == today]["symbol"].astype(str)) if len(prev) else set()
    print("F&O names: %d  |  already snapped today: %d" % (len(syms), len(done)))

    rows, fails = [], 0
    for i, sym in enumerate(syms, 1):
        if sym in done:
            continue
        c = dh.canonical_nse_symbol(sym)
        try:
            ch = no.get_option_chain(c)
        except Exception:
            ch = None
        if not ch or ch.get("error"):
            fails += 1
            continue
        pw, cw = _walls(ch)
        rows.append({"date": today, "symbol": sym, "spot": ch.get("spot"),
                     "expiry": ch.get("expiry"), "pcr": ch.get("pcr"),
                     "max_pain": ch.get("max_pain"),
                     "total_ce_oi": ch.get("total_ce_oi"),
                     "total_pe_oi": ch.get("total_pe_oi"),
                     "put_wall": pw, "call_wall": cw})
        if i % 10 == 0:
            print("  ...%d/%d" % (i, len(syms)))

    if not rows:
        print("nothing new to write (%d fetch failures)" % fails)
        return 0
    out = pd.concat([prev, pd.DataFrame(rows)], ignore_index=True)[COLS]
    os.makedirs("data", exist_ok=True)
    try:                                    # atomic, like every other state write here
        from io_utils import atomic_write_text
        atomic_write_text(OUT, out.to_csv(index=False))
    except Exception:
        out.to_csv(OUT, index=False)
    print("wrote %d rows (%d failed) -> %s" % (len(rows), fails, OUT))
    return len(rows)


def report() -> int:
    """What MOVED since the previous snapshot — the Phase 5 question."""
    if not os.path.exists(OUT):
        print("no snapshots yet — run without --report first")
        return 1
    d = pd.read_csv(OUT)
    days = sorted(d["date"].unique())
    if len(days) < 2:
        print("only %d snapshot day(s); need 2 to report movement" % len(days))
        return 0
    now, before = d[d["date"] == days[-1]], d[d["date"] == days[-2]]
    m = now.merge(before, on="symbol", suffixes=("", "_p"))
    print("=== wall movement  %s vs %s ===\n" % (days[-1], days[-2]))
    print("  %-12s %10s %10s %10s %s" % ("SYMBOL", "CALL WALL", "was", "spot", "read"))
    for _, r in m.iterrows():
        cw, cwp = r["call_wall"], r["call_wall_p"]
        if pd.isna(cw) or pd.isna(cwp) or cw == cwp:
            continue
        read = ("ceiling LIFTED — let it run, trail instead of taking profit"
                if cw > cwp else "ceiling LOWERED — writers capping closer, tighten")
        print("  %-12s %10.1f %10.1f %10.1f  %s" % (r["symbol"], cw, cwp, r["spot"], read))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default="board", choices=["board", "all"])
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    raise SystemExit(report() if a.report else (0 if snap(a.universe) >= 0 else 1))
