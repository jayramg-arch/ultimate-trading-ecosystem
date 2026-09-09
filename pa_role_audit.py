# -*- coding: utf-8 -*-
"""Does the P gate ever pass on a COIL alone?

Jay, 3 Sep 2026: "The PA patterns need not produce a tradeable setup like a
breakout, a moving average reclaim, or a volatility contraction pinch."

He is right that the gate does not distinguish them: S4's `any_pa` is an OR across
all 17 bull patterns, and three of those are CONTRACTION patterns - Inside-3, True
NR7, IB-NR7 - which say nothing has happened yet. Golden Rule 8 says in as many
words: "Don't treat a coil as a trigger. NR7 and inside bars are compression, not
ignition." So the doctrine and the gate disagree, and the gate is what fires alerts.

This measures HOW OFTEN that matters before anything is changed. Six proposed
additions have already been tested and rejected here, one of them backwards, so the
rule is measure first, gate later - and never gate on a distribution nobody checked.

READ-ONLY. Touches no live file, no order path, no gate. Safe during market hours.

Usage:  python pa_role_audit.py [--tf 75m|125m|Daily] [--limit N]
"""
from __future__ import annotations
import argparse, sys, warnings
warnings.filterwarnings("ignore")

import pandas as pd

import pa_patterns as pap

# The 17 bull patterns, split by what they ASSERT about the move. Names are the
# exact strings pa_patterns emits, so a rename breaks this loudly rather than
# silently reclassifying a pattern.
IGNITION = {
    "★★ Power Play (HTF)", "Power Play (Strong Close)", "VCP Breakout",
    "Pocket Pivot", "Stage-2 Launch", "Gap-Up Breakout", "Breakout Confirmed",
}
REVERSAL = {
    "Bullish Engulfing (gated)", "Liq Sweep Reclaim", "3-Bar Bull Reversal",
    "Wyckoff Spring", "50SMA Undercut & Reclaim", "Hammer at 50-SMA",
    "Hammer at 200-SMA",
}
CONTRACTION = {"Inside-3 (Coil)", "True NR7", "★ IB-NR7 Coil"}


def role_of(name: str) -> str:
    if name in IGNITION:
        return "ignition"
    if name in REVERSAL:
        return "reversal"
    if name in CONTRACTION:
        return "contraction"
    return "unclassified"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="75m", choices=["75m", "125m", "Daily"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    try:
        board = pd.read_csv("gm_board_cache_%s.csv" % a.tf)
    except Exception as e:
        print("no board cache for %s: %s" % (a.tf, e))
        return 1
    syms = [str(s) for s in board["Symbol"].dropna().tolist()]
    if a.limit:
        syms = syms[: a.limit]
    s4go = dict(zip(board["Symbol"].astype(str), board.get("S4-GO", pd.Series(dtype=str)).astype(str)))
    cat  = dict(zip(board["Symbol"].astype(str), board.get("Catalyst", pd.Series(dtype=str)).astype(str)))
    arch = dict(zip(board["Symbol"].astype(str), board.get("Archetype", pd.Series(dtype=str)).astype(str)))

    import data_provider as dp
    import dhan_ohlcv as dh
    import datetime as _dt
    _TO = _dt.date.today().strftime('%Y-%m-%d')
    _FROM = (_dt.date.today() - _dt.timedelta(days=90)).strftime('%Y-%m-%d')

    rows, errs, skips = [], [], {}
    for i, sym in enumerate(syms, 1):
        try:
            d = dp.fetch_ohlcv(sym, period="1y", interval="1d").dropna()
            if len(d) < 60:
                skips['daily<60'] = skips.get('daily<60',0)+1
                continue
            e20 = float(d["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            e10 = float(d["Close"].ewm(span=10, adjust=False).mean().iloc[-1])
            if a.tf == "Daily":
                frame, intra = d, False
            else:
                mins = 75 if a.tf == "75m" else 125
                # WITHOUT a date range Dhan returns ~55 bars (2 days), which resamples
                # to 19 x 75m and silently fails the 60-bar guard - that is why the
                # first run evaluated nothing and reported no error. 90 days ~ 900 base bars.
                raw = dh.fetch_intraday(dh.canonical_nse_symbol(sym), from_date=_FROM,
                                        to_date=_TO, interval=25)
                if raw is None or raw.empty:
                    skips['no intraday'] = skips.get('no intraday',0)+1
                    continue
                frame = pap.resample_intraday(raw, mins)
                if frame is None or len(frame) < 60:
                    skips['resampled<60'] = skips.get('resampled<60',0)+1
                    continue
                frame = frame.iloc[:-1] if len(frame) > 60 else frame   # drop the forming bar
                intra = True
            pats = pap.detect_bull_patterns(frame, intraday=intra, ema20_ref=e20, ema10_ref=e10)
            fired = [n for (n, f, _t, _x) in pats if f]
            roles = {role_of(n) for n in fired}
            rows.append(dict(sym=sym, n=len(fired), fired=fired, roles=roles,
                             s4go=s4go.get(sym, ""), cat=cat.get(sym, ""),
                             arch=arch.get(sym, "")))
        except Exception as e:
            errs.append((sym, type(e).__name__, str(e)[:70]))
            continue
        if i % 10 == 0:
            print("  ...%d/%d" % (i, len(syms)), file=sys.stderr)

    if not rows:
        print("no rows evaluated — skips: %s" % skips)
        print("first 5 errors:")
        for e in errs[:5]: print("   %s  %s: %s" % e)
        return 1

    p_pass = [r for r in rows if r["n"] > 0]
    coil_only = [r for r in p_pass if r["roles"] == {"contraction"}]
    ign = [r for r in p_pass if "ignition" in r["roles"]]
    rev = [r for r in p_pass if "reversal" in r["roles"]]

    print("\n=== P-GATE ROLE AUDIT — %s, %d names evaluated ===" % (a.tf, len(rows)))
    print("  P passes (>=1 pattern fired) : %d" % len(p_pass))
    print("  ...containing an IGNITION    : %d" % len(ign))
    print("  ...containing a REVERSAL     : %d" % len(rev))
    print("  ...CONTRACTION ONLY (a coil) : %d   <-- the gate the doctrine forbids"
          % len(coil_only))

    gos = [r for r in p_pass if r["s4go"].strip().startswith(("4/4", "5/5"))]
    go_coil = [r for r in gos if r["roles"] == {"contraction"}]
    print("\n  board rows at full gates     : %d" % len(gos))
    print("  ...of those, coil-only        : %d" % len(go_coil))
    if go_coil:
        for r in go_coil:
            print("        %-12s %s" % (r["sym"], ", ".join(r["fired"])))

    # THE QUESTION THAT DECIDES IT: a coil is the CORRECT trigger for a PULLBACK and
    # the wrong one for a breakout. Same pattern, opposite meaning - and the flat gate
    # cannot tell them apart, because it never asks what qualified the name.
    print("\n  --- coil-only P-passes, by what QUALIFIED the name ---")
    _pull = ("pullback", "pb", "at value")
    _n = 0
    for r in coil_only:
        tag = (str(r.get("cat", "")) + " / " + str(r.get("arch", ""))).strip(" /") or "(none)"
        hit = any(k in tag.lower() for k in _pull)
        _n += hit
        print("    %-12s %-36s %s" % (r["sym"], tag[:36],
                                      "coil = RIGHT trigger" if hit else "coil on a NON-pullback"))
    if coil_only:
        print("    -> %d of %d coil-only names are pullback-qualified (%.0f%%)"
              % (_n, len(coil_only), 100.0 * _n / len(coil_only)))

    print("\n  --- pattern frequency ---")
    freq = {}
    for r in p_pass:
        for n in r["fired"]:
            freq[n] = freq.get(n, 0) + 1
    for n, c in sorted(freq.items(), key=lambda kv: -kv[1]):
        print("    %-28s %3d   [%s]" % (n, c, role_of(n)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
