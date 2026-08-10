"""Shared risk primitives — single source of truth for stop/trail logic used by
the Risk Shield page (weinstein_commander_web_v4.0.py), the Pyramid/Trim manager
(pyramid_logic.py) AND the GTT auto-trail (gtt_auto_shield --trail), so the
surfaces can never drift.

Pure computation (pandas/numpy only — no Streamlit), safe to import anywhere.

Catalyst-aware Chandelier trail = validated "Risk Allocator v2.0" set:
    POS 4.5 · WYC 3.5 · REV 2.5 · SWG 1.5   (+0.5 in a bear regime)
Level = N-bar highest CLOSE − ATR(N, EWM α=1/N) × multiplier.

HOUSE-STANDARD RULING (Jay, 14-Jul-2026 Risk Shield audit, refined same day):
the trail window N is TRADE-TYPE aware — the Chandelier runs on the trade's clock:
    SWING      → N = 14  (highest-close-14 − ATR14 × mult)
    POSITIONAL → N = 22  (highest-close-22 − ATR22 × mult)   [the long-standing house trail]
Anchor window and ATR length are deliberately PAIRED (same clock). Trade type is
sensed from the journal `setup` prefix (SWG→swing; POS/WYC/REV→positional) unless
the caller passes explicit knowledge (journal Timeframe); unknown → positional 22
(preserves prior behavior). Anchor stays highest CLOSE, not the textbook HIGH —
the validation campaign's hardest lesson was that tight stops on long holds give
back found edge. Changing the anchor/close convention requires a replay.py A/B
FIRST — never an aesthetic edit. Other engines converge onto THIS module (P2
reconciliation), not the other way around.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trail_mult_for(setup, bear: bool):
    """Catalyst-aware ATR multiplier for the Chandelier trail. Returns
    (multiplier, family) or (None, None) if the setup prefix isn't recognised."""
    for pfx, m in (("POS", 4.5), ("WYC", 3.5), ("REV", 2.5), ("SWG", 1.5)):
        if str(setup or "").startswith(pfx):
            return (m + (0.5 if bear else 0.0)), pfx
    return None, None


def trail_window_for(setup, swing=None) -> int:
    """Trade-type-aware Chandelier window (Jay, 14-Jul-2026): SWING → 14,
    POSITIONAL → 22. `swing` (True/False) is the caller's explicit knowledge
    (journal Timeframe); when None, sense it from the setup prefix (SWG → swing;
    POS/WYC/REV → positional); unknown → positional 22 (prior behavior)."""
    if swing is None:
        s = str(setup or "")
        if s.startswith("SWG"):
            swing = True
        elif s.startswith(("POS", "WYC", "REV")):
            swing = False
    return 14 if swing else 22


def classify_trade_type_v22(df_daily, rrg: str = None):
    """SWING vs POSITIONAL — Commander Risk Allocator v2.2, ported faithfully.

    Jay, 10-Aug-2026: *"The journal's trade type is incorrect. The Commander risk allocator
    v2.2 has the mechanism to classify the trades into Swing/positional. Go by that."*

    Port of Commander_Risk_Allocator_v2.2.pine:111-155. Takes the DAILY OHLCV frame so every
    input is derived here from one source — passing 15 pre-computed scalars is how a port
    drifts from its original one field at a time.

    Returns (is_swing, label, source, family).

    THE TIE-BREAK IS THE POINT. is_positional and is_swing are BOTH commonly true, and Pine
    does NOT default to positional there — :149 uses the CATALYST detection to decide and
    only falls back to "POS" when that detection is NONE. A first version of this port
    collapsed that to "both -> positional" and made 14 of 15 live holdings positional, which
    is exactly the symptom Jay reported. The catalyst detection is therefore ported in full.

    KNOWN PARITY GAP, deliberately preserved: this file's stage uses `wma30_p = sma(30)[6]`
    (SIX weeks), while the unified 2x2 shipped this morning across S4 / v67 / the GM board
    uses a FOUR-week change. Kept at 6 here because this is a port of the allocator and the
    allocator is the authority Jay named; flagged rather than silently harmonised.
    """
    import numpy as _np
    import pandas as _pd
    if df_daily is None or len(df_daily) < 260:
        return None, "UNKNOWN", "insufficient history", None
    d = df_daily
    c, h, l, o, v = d["Close"], d["High"], d["Low"], d.get("Open", d["Close"]), d["Volume"]
    px = float(c.iloc[-1])

    def _f(x):
        try:
            x = float(x)
            return x if x == x else None
        except Exception:
            return None

    d_50, d_150, d_200 = _f(c.rolling(50).mean().iloc[-1]), _f(c.rolling(150).mean().iloc[-1]), _f(c.rolling(200).mean().iloc[-1])
    d_ema20 = _f(c.ewm(span=20, adjust=False).mean().iloc[-1])
    d_high52 = _f(h.rolling(250).max().iloc[-1])          # ta.highest(high, 250)
    d_high40c = _f(c.rolling(40).max().iloc[-1])          # ta.highest(close, 40)
    d_low40 = _f(l.rolling(40).min().iloc[-1])
    if None in (d_50, d_150, d_200, d_ema20, d_high52, d_high40c, d_low40):
        return None, "UNKNOWN", "missing MAs", None

    wk = d.resample("W-MON", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    if len(wk) < 37:
        return None, "UNKNOWN", "insufficient weekly history", None
    _w = wk["Close"].rolling(30).mean()
    wma30, wma30_p = _f(_w.iloc[-1]), _f(_w.iloc[-7])      # sma(close,30)[6] -> 6 weeks back
    if wma30 is None or wma30_p is None:
        return None, "UNKNOWN", "missing 30WMA", None

    # :113 and :119, verbatim
    stage2_uptrend = (px > d_50) and (d_50 > d_150) and (d_150 > d_200)
    stage = 2 if (px > wma30 and wma30 >= wma30_p) else 3 if px > wma30 else 4 if wma30 < wma30_p else 1

    # RS: the quadrant is Jay's manual Strike read when present. rs_momentum > 0 is the
    # same fact the quadrant encodes (LEADING / IMPROVING are the momentum-positive halves).
    q = str(rrg or "").strip().upper()
    lagging = q.startswith("LAG")
    rs_mom_pos = q.startswith(("LEAD", "IMPROV")) if q else None

    dd_from_high = (d_high52 - px) / d_high52 if d_high52 > 0 else 0.0
    base_range40 = (d_high40c - d_low40) / d_low40 if d_low40 > 0 else 1.0
    c1, c2, c3, c5 = (_f(c.iloc[-2]), _f(c.iloc[-3]), _f(c.iloc[-4]), _f(c.iloc[-6]))
    o0 = _f(o.iloc[-1])

    det_gap = bool(o0 and c1 and o0 > c1 * 1.04 and px > o0)
    det_breakout = bool(stage2_uptrend and px >= d_high40c * 0.999)
    det_pullback = bool(stage2_uptrend and abs(px - d_ema20) / d_ema20 <= 0.03 and o0 and px > o0)
    det_oversold = bool(c3 and c2 and c1 and c3 > c2 and c2 > c1 and px > c1)
    det_recovery = bool(dd_from_high >= 0.15 and c5 and px > c5 and rs_mom_pos)
    det_wyc = bool(dd_from_high >= 0.15 and base_range40 <= 0.25 and c5 and px > c5)

    # :126 auto_cat_raw
    if det_gap:
        raw = "SWG-GAP"
    elif dd_from_high >= 0.15:
        raw = "WYC" if det_wyc else ("REV" if det_recovery else "NONE")
    else:
        raw = "POS" if det_breakout else ("SWG" if det_pullback else ("SWG-REV" if det_oversold else "NONE"))

    # :134-144
    is_positional = bool(stage in (1, 2) and px > d_200 and wma30 >= wma30_p and not lagging)
    rsi14 = None
    try:
        _dd = c.diff()
        _up = _dd.clip(lower=0).rolling(14).mean()
        _dn = (-_dd.clip(upper=0)).rolling(14).mean()
        rsi14 = _f((100 - 100 / (1 + _up / _dn.replace(0, _np.nan))).iloc[-1])
    except Exception:
        pass
    _v50 = _f(v.rolling(50).mean().iloc[-1])
    volr = (_f(v.iloc[-1]) / _v50) if _v50 else None
    is_swing = bool(px > d_ema20 and d_ema20 > d_50
                    and ((rsi14 is not None and rsi14 > 55) or (volr is not None and volr > 1.5))
                    and ((px - d_ema20) / d_ema20) * 100 < 15)

    # :148-155
    if is_positional and is_swing:
        fam = raw if raw != "NONE" else "POS"
        src = f"allocator v2.2 (both -> {raw})" if raw != "NONE" else "allocator v2.2 (both, no catalyst -> POS)"
    elif is_positional:
        fam = raw if raw in ("POS", "WYC", "REV") else "POS"
        src = "allocator v2.2 (positional)"
    elif is_swing:
        fam = raw if raw.startswith("SWG") else "SWG"
        src = "allocator v2.2 (swing)"
    else:
        return None, "UNKNOWN", "allocator v2.2 (neither)", raw

    sw = fam.startswith("SWG")
    return sw, ("SWING" if sw else "POSITIONAL"), src, fam


def resolve_trade_type(timeframe=None, setup=None, structural=None, trade_type=None):
    """(is_swing, label, source) — the ONE precedence order for "is this a swing trade".

    Added 10-Aug-2026 after an audit found THREE independent answers coexisting on the
    Risk Shield page: the Chandelier clock read the journal Timeframe (falling back to the
    setup prefix, then positional), while the position tile read a purely STRUCTURAL
    classifier (ATR% / distance from the 200 / score) and could even re-derive the answer
    from the SL distance. The same symbol could therefore print SWING on its tile while its
    stop trailed on the 22-bar POSITIONAL clock — and the R-target policy check used the
    positional constants regardless.

    Precedence, strongest evidence first:
      1. journal `Timeframe`  — what YOU declared when the trade was logged
      2. `setup` prefix       — SWG -> swing; POS / WYC / REV -> positional
      3. `structural`         — the technicals' guess (caller supplies it); a HINT, so its
                                label is suffixed "?" exactly as the old tile did
      4. positional           — the long-standing default; never guess swing

    Returns the SOURCE so a caller can say which rung answered rather than presenting a
    fallback as a fact.
    """
    tf = str(timeframe or "").strip().lower()
    if "swing" in tf:
        return True, "SWING", "journal"
    if "pos" in tf:
        return False, "POSITIONAL", "journal"
    # `trade_type` IS DELIBERATELY NOT CONSULTED (10-Aug-2026). I wired it in when I found
    # it holding 'Swing' on ten of fifteen holdings while timeframe/setup were empty — Jay:
    # "the journal's trade type is incorrect... the Commander risk allocator v2.2 has the
    # mechanism... go by that." So the column is unreliable DATA, not a missing wire, and
    # the authoritative classifier is classify_trade_type_v22 above, passed in as
    # `structural`. The parameter is kept only so existing callers do not break.
    s = str(setup or "")
    if s.startswith("SWG"):
        return True, "SWING", "setup"
    if s.startswith(("POS", "WYC", "REV")):
        return False, "POSITIONAL", "setup"
    if structural is not None:
        sw = bool(structural)
        return sw, ("SWING?" if sw else "POSITIONAL?"), "structural"
    return False, "POSITIONAL", "default"


def chandelier_exit(high: pd.Series, low: pd.Series, close: pd.Series,
                    setup: str = "", bear: bool = False,
                    cap_protect: bool = False, custom_mult=None,
                    above200: bool = True, swing=None):
    """Catalyst-aware, trade-type-aware Chandelier trailing-stop level.

    Window/ATR clock (paired): swing → 14-bar, positional → 22-bar — see
    trail_window_for(). Multiplier precedence (identical to the Risk Shield page):
      1. valid custom override (>0)           → "custom"
      2. catalyst-aware set (trail_mult_for)  → "<setup/family>"
      3. heuristic fallback (4.5 bull / 5.0 bear)
      4. cap-protect (portfolio drawdown)     → 2.5, overrides all of the above

    Returns (level, multiplier, source) or (None, None, None) when there are
    fewer than N bars.
    """
    n = trail_window_for(setup, swing)
    if close is None or len(close) < n:
        return (None, None, None)

    highest_close_n = float(close.rolling(n).max().iloc[-1])
    tr = pd.concat([high - low,
                    (high - close.shift(1)).abs(),
                    (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_n = float(tr.ewm(alpha=1 / n, adjust=False).mean().iloc[-1])

    invalid_custom = custom_mult is not None and not (isinstance(custom_mult, (int, float)) and custom_mult > 0)
    if custom_mult is not None and not invalid_custom:
        mult, src = float(custom_mult), "custom"
    else:
        cat_mult, cat_fam = trail_mult_for(setup, bear)
        if cat_mult is not None:
            mult, src = cat_mult, (str(setup) or cat_fam)
        elif swing is not None:
            # TRADE TYPE, when the setup label cannot answer (10-Aug-2026).
            # The bug this fixes: `swing` used to drive ONLY the window (14 vs 22 bars)
            # while the MULTIPLIER fell through to the 4.5 heuristic. So a position the
            # page itself labelled SWING trailed on a 14-bar clock at 4.5xATR — an
            # incoherent pair, and the whole point of the 14/22 split is that the anchor
            # and the ATR multiple belong to ONE clock. Live effect: every swing holding
            # with a blank journal setup (i.e. all the backfilled ones) carried a
            # POSITIONAL trail, which is the opposite of the "tighter risk, faster exits"
            # mandate a swing trade is taken under.
            mult = (1.5 if swing else 4.5) + (0.5 if bear else 0.0)
            src = ("swing-inferred" if swing else "pos-inferred")
        else:
            mult = 4.5 if above200 else 5.0
            src = "heuristic-bull" if above200 else "heuristic-bear"
        if cap_protect:
            mult, src = 2.5, "cap-protect"

    if np.isnan(highest_close_n) or np.isnan(atr_n):
        return (None, None, None)
    return (float(highest_close_n - atr_n * mult), float(mult), src)
