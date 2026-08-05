"""pa_combos — synergistic PA pattern COMBINATIONS, as context → trigger sequences.

WHY THIS EXISTS (Jay, 5-Aug-2026): "Instead of treating the PA score as a numbers game,
the most profitable approach is to look for synergistic combinations — where one pattern
sets the structural stage, and the other provides the immediate micro-trigger."

That framing contains the mechanism, and it is one Σ cannot express. Σ sums booleans on a
SINGLE bar, so it cannot tell "supply dried up over three weeks and tension released
today" from "three unrelated things happened at once". A combination is a SEQUENCE:

    CONTEXT  fired within the last N bars   (structural — takes time to form)
    TRIGGER  fires on the CURRENT bar       (the release)

Two mapping corrections against the notes this came from, both verified against the live
batteries rather than assumed:

  * "SC" is ambiguous. In the BULL battery `SC` is Power Play (STRONG CLOSE). The SELLING
    climax lives in the RECOVERY battery as "Climax Reversal (SC+AR)". Reading the notes
    against the panel mis-maps these.
  * "SC + Higher Low + IN3" cannot run as written: the recovery battery has NO Inside-3
    and NO NR7. Its volatility-death pattern is Volume Dry-Up, which carries the same
    meaning (selling has evaporated), so that is the substitution used below.

STATUS: DISPLAY AND MEASUREMENT ONLY. No combo gates anything. "Combos give better
results" is an edge claim and it gets the same treatment as every other one — measured
against a Σ-matched control before it is allowed to influence a decision. See
combo_backtest.py; the control is what stops this rediscovering "more patterns = more
momentum" and calling it a finding.
"""
from __future__ import annotations

# ── pattern ROLES ────────────────────────────────────────────────────────────
# Not decoration: the role is what makes a pair synergistic rather than coincidental.
#   TENSION   — coiling / drying up. Structural, forms over bars. A CONTEXT leg.
#   IGNITION  — expansion on volume. Single-bar. A TRIGGER leg.
#   REVERSAL  — sweep-and-reclaim. Single-bar, but needs a prior break to reverse.
ROLE = {
    "VCP Breakout": "TENSION", "True NR7": "TENSION", "Inside-3 (Coil)": "TENSION",
    "★ IB-NR7 Coil": "TENSION", "Volume Dry-Up": "TENSION",
    "Pocket Pivot": "IGNITION", "Gap-Up Breakout": "IGNITION",
    "Breakout Confirmed": "IGNITION", "Power Play (Strong Close)": "IGNITION",
    "Stage-2 Launch": "IGNITION", "Base Breakout (SOS/JAC)": "IGNITION",
    "★★ Power Play (HTF)": "IGNITION",
    "Wyckoff Spring": "REVERSAL", "Bullish Engulfing": "REVERSAL",
    "Bullish Engulfing (gated)": "REVERSAL", "3-Bar Bull Reversal": "REVERSAL",
    "Liq Sweep Reclaim": "REVERSAL", "50SMA Undercut & Reclaim": "REVERSAL",
    "Hammer at 50-SMA": "REVERSAL", "Hammer at 200-SMA": "REVERSAL",
    "Hammer at support": "REVERSAL", "Climax Reversal (SC+AR)": "REVERSAL",
    "Higher-Low / 2B": "REVERSAL", "30-WMA Reclaim": "REVERSAL",
}

# ── the combos ───────────────────────────────────────────────────────────────
# ctx: list of (any-of names, max age in bars). EVERY ctx entry must be satisfied.
# trig: any-of names, must fire on the CURRENT bar (age 0).
# Windows are deliberately short. A "context" older than its window is not context any
# more, it is history — and a rule that accepts a 40-bar-old VCP would fire on almost
# everything, which is how a combo quietly becomes a synonym for "a pattern fired".
COMBOS = [
    dict(key="SPRING", name="Coiled Spring", side="bull",
         ctx=[(["VCP Breakout"], 10)],
         trig=["True NR7", "Inside-3 (Coil)", "★ IB-NR7 Coil"],
         why="supply dried up, now maximum tension at the pivot"),
    dict(key="IGNITE", name="Institutional Ignition", side="bull",
         ctx=[(["Breakout Confirmed"], 3)],
         trig=["Pocket Pivot", "Gap-Up Breakout"],
         why="the breakout has a whale behind it, not a drift"),
    dict(key="TRAP", name="Bear Trap", side="bull",
         ctx=[(["Wyckoff Spring", "Liq Sweep Reclaim"], 3)],
         trig=["Bullish Engulfing (gated)", "Bullish Engulfing"],
         why="stops swept below support, immediately reclaimed"),
    dict(key="FLOOR", name="Capitulation Floor", side="recovery",
         ctx=[(["Climax Reversal (SC+AR)"], 10), (["Wyckoff Spring"], 3)],
         trig=["Bullish Engulfing"],
         why="panic absorbed at the low, floor established"),
    dict(key="SHIFT", name="Structure Shift", side="recovery",
         ctx=[(["Climax Reversal (SC+AR)"], 40), (["Higher-Low / 2B"], 5)],
         trig=["Volume Dry-Up"],
         why="higher low held and selling has evaporated"),
]

MAX_LOOKBACK = 40 + 1


def pattern_ages(df, *, recovery: bool = False, lookback: int = MAX_LOOKBACK,
                 intraday: bool = False, ema20_ref=None, ema10_ref=None) -> dict:
    """{pattern name: bars since it last fired} — 0 = the current bar, None = not within
    `lookback`.

    The battery evaluates the LAST bar only, so ages come from re-running it over a
    trailing window. That is the honest way to get them: no second implementation of any
    pattern, so an age can never disagree with the flag it is an age OF.
    """
    import pa_patterns as pap
    fn = pap.detect_recovery_patterns if recovery else pap.detect_bull_patterns
    ages: dict[str, int] = {}
    if df is None or len(df) < 60:
        return ages
    n = min(lookback, max(0, len(df) - 60))
    for age in range(n + 1):
        sub = df if age == 0 else df.iloc[:-age]
        if len(sub) < 60:
            break
        try:
            for nm, fired, _t, _d in fn(sub, intraday=intraday,
                                        ema20_ref=ema20_ref, ema10_ref=ema10_ref):
                if fired and nm not in ages:
                    ages[nm] = age
        except Exception:
            break
    return ages


def combos_from_ages(ages: dict, *, recovery: bool = False) -> list[dict]:
    """Which combos are live, given pattern ages. Pure — no data access, so it is
    trivially testable and shared by the panel, the board and the backtest."""
    side = "recovery" if recovery else "bull"
    out = []
    for c in COMBOS:
        if c["side"] != side:
            continue
        legs, ok = [], True
        for names, win in c["ctx"]:
            hit = [(n, ages[n]) for n in names if ages.get(n) is not None and ages[n] <= win]
            if not hit:
                ok = False
                break
            hit.sort(key=lambda x: x[1])
            legs.append(hit[0])
        if not ok:
            continue
        fired_now = [n for n in c["trig"] if ages.get(n) == 0]
        if not fired_now:
            continue
        out.append({**c, "ctx_legs": legs, "trigger": fired_now[0]})
    return out


def detect_combos(df, *, recovery: bool = False, **kw) -> list[dict]:
    return combos_from_ages(pattern_ages(df, recovery=recovery, **kw), recovery=recovery)


def combo_label(c: dict, short: bool = True) -> str:
    """'Coiled Spring · VCP 6b → NR7 now' — the context AGE is the part Σ cannot show,
    and the part that says whether the story is still fresh."""
    def _s(n):
        return (n.replace("★★ ", "").replace("★ ", "").replace(" Breakout", "")
                 .replace("Power Play (Strong Close)", "Strong Close")
                 .replace("Bullish Engulfing (gated)", "Engulf")
                 .replace("Bullish Engulfing", "Engulf")
                 .replace("Climax Reversal (SC+AR)", "Climax")
                 .replace("Inside-3 (Coil)", "IN3").replace("True NR7", "NR7")
                 .replace("Wyckoff Spring", "Spring").replace("Volume Dry-Up", "VDU")
                 .replace("Higher-Low / 2B", "2B").replace("Pocket Pivot", "PP")
                 .replace("Gap-Up", "GAP").replace("Breakout Confirmed", "BC"))
    ctx = " + ".join(f"{_s(n)} {a}b" for n, a in c["ctx_legs"])
    return f"{c['name']} · {ctx} → {_s(c['trigger'])} now" if short else \
           f"{c['name']} · {ctx} → {_s(c['trigger'])} now — {c['why']}"
