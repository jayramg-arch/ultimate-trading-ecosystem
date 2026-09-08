# -*- coding: utf-8 -*-
"""Pair the CATALYST/ARCHETYPE (the playbook) with the PA pattern (its trigger).

Jay, 3 Sep 2026: "We have these catalysts already (POS-BO, SWG-BO, SWG-PB...). We
need to see how we can pair them with the PA patterns and come up with a practical
way of identifying the setups, the way a professional trader trades."

THE IDEA. A professional does not hunt patterns, they hunt a SETUP. The catalyst
says what KIND of trade this is; the pattern that fires should be THAT kind's
trigger; and the setup then dictates what the other gates must demand. A breakout
wants volume EXPANSION and clear overhead; a pullback wants volume DRY-UP and price
AT support. Opposite tests - which is why one flat five-gate form loses information.

WHY A RESOLVER AND NOT JUST `Catalyst`. On the live board only 6 of 72 rows carry a
live catalyst (5 SWG-PB, 1 POS-BO). The other 66 are NaN, and that is BY DESIGN:
under inherited qualification a watchlist name was qualified upstream and the board
only times it, so the ARCHETYPE carries the playbook. Reading `Catalyst` alone and
calling NaN "missing" was my own misreading of the design.

READ-ONLY. Touches no gate, no order path, no live file.

Usage:  python setup_pairing.py [--tf 75m|125m|Daily] [--limit N]
"""
from __future__ import annotations
import argparse, sys, warnings
warnings.filterwarnings("ignore")

import pandas as pd
import pa_patterns as pap

# ── all 21 patterns by what they ASSERT about the move ────────────────────
# 6-Sep-2026: the RECOVERY battery's own patterns were missing from all three sets,
# so role_of() returned "unclassified" for six of the ten a recovery name can fire and
# `roles & ok` was empty -> every recovery playbook scored MISMATCH. Same defect, same
# day, in S4's f_foldSetup call site. NOTE "Bullish Engulfing" (recovery) and
# "Bullish Engulfing (gated)" (bull) are DIFFERENT STRINGS; both belong here.
IGNITION = {
    "★★ Power Play (HTF)", "Power Play (Strong Close)", "VCP Breakout",
    "Pocket Pivot", "Stage-2 Launch", "Gap-Up Breakout", "Breakout Confirmed",
    "Base Breakout (SOS/JAC)",
}
REVERSAL = {
    "Bullish Engulfing (gated)", "Liq Sweep Reclaim", "3-Bar Bull Reversal",
    "Wyckoff Spring", "50SMA Undercut & Reclaim", "Hammer at 50-SMA",
    "Hammer at 200-SMA",
    "Bullish Engulfing", "Climax Reversal (SC+AR)", "Higher-Low / 2B",
    "Hammer at support", "30-WMA Reclaim",
}
CONTRACTION = {"Inside-3 (Coil)", "True NR7", "★ IB-NR7 Coil", "Volume Dry-Up"}


def role_of(name: str) -> str:
    return ("ignition" if name in IGNITION else
            "reversal" if name in REVERSAL else
            "contraction" if name in CONTRACTION else "unclassified")


# ── the playbook: what each setup's trigger, location and volume should be ─────
# Roles are what the setup ACCEPTS as a trigger. A coil is the right trigger for a
# pullback and the wrong one for a breakout - same pattern, opposite meaning.
# 5-Sep-2026: RECONCILED WITH PINE (S4 f_foldSetup). Three of these had drifted, and
# one was inverted - ACCUM accepted ONLY ignition here while Pine accepts contraction
# or reversal and explicitly REFUSES ignition. Pine's reading is the documented one: a
# base that is already breaking is POS-BO, so calling it accumulation holds it to the
# wrong standard on both volume and bar. This module is read-only analysis, so the cost
# of the drift was silently wrong study output; any result produced before today used
# the inverted ACCUM rule.
PLAYBOOK = {
    "BREAKOUT": dict(roles={"ignition"},                            vol="expansion",  loc="above the pivot, not in supply"),
    # NOT ignition - see above.
    "ACCUM":    dict(roles={"contraction", "reversal"},             vol="pocket rule", loc="inside the base, above 200-DMA"),
    # Pine accepts all three and fails only on roleMismatch: an IGNITION fired INSIDE a
    # demand zone, which is a breakout's trigger in a pullback's location. A pocket
    # pivot off the low IS a textbook pullback entry, so a flat ban on ignition is wrong.
    "PULLBACK": dict(roles={"contraction", "reversal", "ignition"}, vol="dry-up",     loc="at demand / EMA20",
                     note="ignition only OUTSIDE a demand zone"),
    "REVERSAL": dict(roles={"reversal"},                            vol="reclaim",    loc="at the turn"),
    # Only WYC-SPRING+SOS lands here now: it genuinely is both legs.
    "RECOVERY": dict(roles={"reversal", "ignition"},                vol="reclaim",    loc="at major support"),
    "ADD":      dict(roles={"contraction", "reversal", "ignition"}, vol="dry-up ok",  loc="THE whole game - not extended"),
}

# All THIRTEEN Unified catalysts, mirroring S4's numeric codes 1-13. The six bull names
# were the only ones here before, so every REV-*/WYC-* catalyst fell through to the
# archetype branch. SWG-REV also read RECOVERY where Pine says REVERSAL.
#
# The seven recovery catalysts split by what each one IS rather than by family:
# a climax bounce, a higher-low and a spring are TURNS; a trendline reclaim, a Sign of
# Strength and a jump across the creek are BREAKOUTS. Only SPRING+SOS is both.
CATALYST_TO_PLAY = {
    "POS-BO": "BREAKOUT", "SWG-BO": "BREAKOUT", "SWG-GAP": "BREAKOUT",
    "GAP-GO": "BREAKOUT", "POS-ACCUM": "ACCUM", "SWG-PB": "PULLBACK",
    "SWG-REV": "REVERSAL",
    "REV-CB": "REVERSAL", "REV-RS": "REVERSAL", "WYC-SPRING": "REVERSAL",
    "REV-EARLY": "BREAKOUT", "WYC-JAC": "BREAKOUT", "WYC-SOS": "BREAKOUT",
    "WYC-SPRING+SOS": "RECOVERY",
}


def playbook_of(catalyst: str, archetype: str, loc: str = "") -> tuple[str, str]:
    """Return (playbook, how it was resolved).

    A LIVE catalyst wins; otherwise the archetype carries it, because that is what
    qualified the name upstream.

    NO ETF CARVE-OUT (Jay, 3 Sep: "apply the setup criteria on ETFs as well, no
    relaxations"). An earlier version let ETFs accept any trigger, which made them
    trivially "correct" and told us nothing. An ETF's archetype is its INSTRUMENT
    CLASS and carries no setup - so it is resolved from STRUCTURE instead, the same
    way the system already infers pullback context when no list says so: at or
    reacting off a demand location = PULLBACK, otherwise BREAKOUT. Same criteria as
    every stock, just resolved from price rather than from a list.
    """
    catalyst = "" if catalyst is None else str(catalyst)
    archetype = "" if archetype is None else str(archetype)
    loc = "" if loc is None else str(loc)
    c = catalyst.strip().upper()
    if c and c.lower() != "nan" and c in CATALYST_TO_PLAY:
        return CATALYST_TO_PLAY[c], "catalyst " + c
    a = archetype.strip().lower()
    if not a or a == "nan":
        return "UNKNOWN", "nothing to resolve from"
    if "pullback" in a or "at value" in a:
        return "PULLBACK", "archetype Pullback"
    if a.startswith("rec") or "recovery" in a:
        return "RECOVERY", "archetype " + archetype.strip()
    if "pyramid" in a:
        return "ADD", "archetype Pyramid"
    if "etf" in a:
        # structure decides, because the archetype cannot
        l = loc.lower()
        at_demand = ("at pattern" in l or "at pivot" in l or "reacting off" in l
                     or "at demand" in l or "in demand" in l)
        return ("PULLBACK" if at_demand else "BREAKOUT",
                "ETF — from structure (%s)" % ("at demand" if at_demand else "not at demand"))
    if "leader" in a or "breakout" in a or "catalyst" in a or "hunter" in a or "earlybird" in a:
        return "BREAKOUT", "archetype " + archetype.strip()
    return "UNKNOWN", "archetype " + archetype.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="75m", choices=["75m", "125m", "Daily"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    board = pd.read_csv("gm_board_cache_%s.csv" % a.tf)
    syms = [str(s) for s in board["Symbol"].dropna().tolist()]
    if a.limit:
        syms = syms[: a.limit]
    col = lambda n: dict(zip(board["Symbol"].astype(str),
                             board.get(n, pd.Series(dtype=str)).astype(str)))
    s4go, cat, arch, loc = col("S4-GO"), col("Catalyst"), col("Archetype"), col("Loc")

    import data_provider as dp, dhan_ohlcv as dh, datetime as _dt
    TO = _dt.date.today().strftime("%Y-%m-%d")
    FROM = (_dt.date.today() - _dt.timedelta(days=90)).strftime("%Y-%m-%d")

    rows, skips = [], {}
    for i, sym in enumerate(syms, 1):
        try:
            d = dp.fetch_ohlcv(sym, period="1y", interval="1d").dropna()
            if len(d) < 60:
                skips["daily<60"] = skips.get("daily<60", 0) + 1
                continue
            e20 = float(d["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            e10 = float(d["Close"].ewm(span=10, adjust=False).mean().iloc[-1])
            if a.tf == "Daily":
                frame, intra = d, False
            else:
                raw = dh.fetch_intraday(dh.canonical_nse_symbol(sym), from_date=FROM,
                                        to_date=TO, interval=25)
                if raw is None or raw.empty:
                    skips["no intraday"] = skips.get("no intraday", 0) + 1
                    continue
                frame = pap.resample_intraday(raw, 75 if a.tf == "75m" else 125)
                if frame is None or len(frame) < 60:
                    skips["resampled<60"] = skips.get("resampled<60", 0) + 1
                    continue
                frame, intra = frame.iloc[:-1], True
            pats = pap.detect_bull_patterns(frame, intraday=intra, ema20_ref=e20, ema10_ref=e10)
            fired = [n for (n, f, _t, _x) in pats if f]
            if not fired:
                continue
            play, how = playbook_of(cat.get(sym, ""), arch.get(sym, ""), loc.get(sym, ""))
            roles = {role_of(n) for n in fired}
            ok = PLAYBOOK.get(play, {}).get("roles", set())
            rows.append(dict(sym=sym, fired=fired, roles=roles, play=play, how=how,
                             match=bool(roles & ok) if ok else None,
                             s4go=s4go.get(sym, "")))
        except Exception as e:
            k = "%s: %s" % (type(e).__name__, str(e)[:60])
            skips[k] = skips.get(k, 0) + 1
        if i % 15 == 0:
            print("  ...%d/%d" % (i, len(syms)), file=sys.stderr)

    if not rows:
        print("no P-passes evaluated — skips: %s" % skips)
        return 1

    print("\n=== SETUP PAIRING — %s, %d names with a fired pattern ===" % (a.tf, len(rows)))
    print("(skips: %s)\n" % (skips or "none"))
    print("  %-12s %-9s %-13s %-34s %s" % ("SYMBOL", "PLAYBOOK", "TRIGGER ROLE", "PATTERNS", "VERDICT"))
    for r in sorted(rows, key=lambda r: (r["play"], r["sym"])):
        v = ("—  no rule" if r["match"] is None else
             "✓  right trigger" if r["match"] else "⚠  MISMATCH")
        print("  %-12s %-9s %-13s %-34s %s"
              % (r["sym"], r["play"], "/".join(sorted(r["roles"])),
                 ", ".join(r["fired"])[:34], v))

    tot = [r for r in rows if r["match"] is not None]
    bad = [r for r in tot if not r["match"]]
    print("\n  classifiable        : %d of %d" % (len(tot), len(rows)))
    print("  right trigger       : %d" % (len(tot) - len(bad)))
    print("  MISMATCH            : %d" % len(bad))
    for r in bad:
        want = ", ".join(sorted(PLAYBOOK[r["play"]]["roles"]))
        print("      %-12s %s fired on a %s playbook — that wants %s"
              % (r["sym"], "/".join(sorted(r["roles"])), r["play"], want))
    print("\n  by playbook:")
    for p in sorted({r["play"] for r in rows}):
        sel = [r for r in rows if r["play"] == p]
        print("    %-9s %2d   (%s)" % (p, len(sel), sel[0]["how"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
