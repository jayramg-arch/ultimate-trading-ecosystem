"""
pa_patterns.py — v1.0 (9-Jul-2026)
====================================================================
SHARED last-bar price-action pattern batteries (single source of truth).

Extracted verbatim from weinstein_commander_web_v4.0.py (Golden Matcher)
so every Python surface that needs the "did a PA trigger fire TODAY?"
read imports ONE implementation — zero Python↔Python drift.

  detect_bull_patterns(df, stage)      — 17-set bull battery
                                         (mirror of Dashboard v67.4.12 /
                                          Section4_Entry_Trigger Bull mode)
  detect_recovery_patterns(df, stage)  — 10-set recovery battery
                                         (mirror of Section4 Recovery mode)

Both return: [(name, fired: bool, tier: int, note: str), ...]
`df` = daily OHLCV with a DatetimeIndex and columns
Open/High/Low/Close/Volume; `stage` = the Weinstein stage string.

Related but DIFFERENT module: pa_field_validator.py computes VECTORIZED
per-bar detector SERIES for backtesting (whole-history, stateful lockouts).
Formulas are kept aligned by convention; this module is the canonical
last-bar read used by dashboards.

Includes the 9-Jul-2026 fixes:
  - Stage-2 Launch / 30-WMA Reclaim evaluate CONFIRMED weeks only
    (the forming W-FRI week is dropped — no mid-week repaint).
  - Higher-Low/2B requires base proximity (recent low within +10% of the
    prior base low) so it can't fire on every green day of an uptrend.
====================================================================
"""

import math

import numpy as np
import pandas as pd


def detect_support_zones(df: pd.DataFrame) -> dict:
    """Stateful daily Order-Block / FVG / pivot-low support trackers — the
    Python twin of the Section 4 Entry Trigger Pine (`f_zones`), so the Golden
    Matcher auto-marks the same demand zones the chart draws (automating Steps
    1-2 of the Guided Execution). Zero-drift by construction: each tracker
    mirrors the Pine bar-for-bar and reports the CURRENT active state on the
    last bar.

    Zone lifecycle (OB / FVG):
      FRESH    — formed, not yet revisited. Tradeable (the first tap is the setup).
      TESTED   — price ENTERED then LEFT (one mitigation) → greyed + EXCLUDED
                 from the trigger, but still reported (ob_tested / fvg_tested).
      VIOLATED — a bar CLOSES below the zone's distal (bottom) → the demand
                 thesis failed → the zone is DELETED (set to None), so it stops
                 drawing and stops counting. A wick below that closes back inside
                 is a spring, NOT a violation — the zone survives.
    Pivot support is a STRUCTURAL level and is never deleted: a tested pivot
    stays as support, and a VIOLATED pivot (close below) FLIPS to resistance
    (previous-support-now-resistance) and stays — cleared only when price
    reclaims it (close above).

    Returns a dict:
      ob_top/ob_bot, ob_tested   — active bullish Order Block + its tested flag.
      fvg_top/fvg_bot, fvg_tested — active 3-bar bullish FVG + its tested flag.
      pivot                       — active confirmed pivot-low SUPPORT (5,5).
      pivot_res                   — a violated pivot now acting as RESISTANCE
                                    (None until a support flips; not a support).
      at_support                  — close is inside/within 1.5% of a FRESH zone.
      zone                        — label of the tightest relationship
                                    (…/'OB tested'/'FVG tested'/'outside').
    """
    out = {"ob_top": None, "ob_bot": None, "ob_tested": False,
           "fvg_top": None, "fvg_bot": None, "fvg_tested": False,
           "pivot": None, "pivot_res": None, "at_support": False, "zone": "outside"}
    try:
        c = df["Close"].to_numpy(dtype=float); o = df["Open"].to_numpy(dtype=float)
        h = df["High"].to_numpy(dtype=float); l = df["Low"].to_numpy(dtype=float)
        v = df["Volume"].to_numpy(dtype=float)
        n = len(c)
        if n < 60:
            return out
        vol50 = pd.Series(v).rolling(50).mean().to_numpy()

        # --- Order Block (stateful) + TEST tracking ---
        # An OB is "tested" once price has ENTERED it and then LEFT (a completed
        # mitigation). The current first tap still reads fresh; only after price
        # leaves does it flip to tested → greyed + excluded from the trigger.
        ob_top = ob_bot = None; ob_tested = False; ob_in = False
        for i in range(5, n):
            if ob_top is not None:                      # test-track + invalidate the live zone
                _in = (l[i] <= ob_top and h[i] >= ob_bot)
                if ob_in and not _in:
                    ob_tested = True                    # entered then left = one completed touch
                ob_in = _in
                if c[i] < ob_bot:                       # VIOLATED (close < distal) → delete
                    ob_top = ob_bot = None; ob_tested = False; ob_in = False
            red = -1
            for k in range(1, 6):                       # nearest red candle in bars i-1..i-5
                if c[i - k] < o[i - k]:
                    red = k; break
            hi5_prev = h[i - 5:i].max()                 # ta.highest(high,5)[1] at bar i
            disp = (c[i] > hi5_prev) and (not math.isnan(vol50[i])) and (v[i] > vol50[i])
            if disp and red != -1:                      # new displacement forms/replaces the OB
                ob_top, ob_bot = h[i - red], l[i - red]
                ob_tested = False
                ob_in = False                            # impulse bar leaves the zone; not a test

        # --- FVG (stateful) + TEST tracking (a "test" = price trades back into the gap) ---
        fvg_top = fvg_bot = None; fvg_tested = False; fvg_in = False
        for i in range(2, n):
            if fvg_top is not None:
                _in = (l[i] <= fvg_top and h[i] >= fvg_bot)
                if fvg_in and not _in:
                    fvg_tested = True
                fvg_in = _in
                if c[i] < fvg_bot:                      # VIOLATED (close < distal) → delete
                    fvg_top = fvg_bot = None; fvg_tested = False; fvg_in = False
            if h[i - 2] < l[i]:
                fvg_top, fvg_bot = l[i], h[i - 2]
                fvg_tested = False
                fvg_in = False                           # price sits above the gap at formation

        # --- Pivot low (5 left / 5 right), confirmed 5 bars later, stateful ---
        # A pivot is a STRUCTURAL level, never deleted (unlike OB/FVG):
        #   * tested (price taps it and bounces) → stays as support.
        #   * VIOLATED (close below) → does NOT delete; it FLIPS to resistance
        #     (previous-support-now-resistance) and stays — often the more
        #     important level. Cleared only when price reclaims it (close above).
        # piv = active support (price above); piv_res = flipped resistance (below).
        piv = None
        piv_res = None
        for i in range(10, n):
            j = i - 5                                  # candidate pivot centre
            lo = l[j]
            is_piv = all(lo < l[j - k] for k in range(1, 6)) and all(lo < l[j + k] for k in range(1, 6))
            if is_piv:
                piv = lo
            if piv is not None and c[i] < piv:         # support violated → flip to resistance (keep)
                piv_res = piv
                piv = None
            if piv_res is not None and c[i] > piv_res:  # resistance reclaimed → clear
                piv_res = None

        cN = c[-1]
        # Only FRESH (untested) OB/FVG count as support for the trigger.
        ob_fresh  = ob_top is not None and not ob_tested
        fvg_fresh = fvg_top is not None and not fvg_tested
        inside_ob  = ob_fresh and ob_bot <= cN <= ob_top
        near_ob    = ob_fresh and cN > ob_top and (cN - ob_top) / ob_top <= 0.015
        inside_fvg = fvg_fresh and fvg_bot <= cN <= fvg_top
        near_fvg   = fvg_fresh and cN > fvg_top and (cN - fvg_top) / fvg_top <= 0.015
        near_pivot = piv is not None and cN >= piv and (cN - piv) / piv <= 0.015
        out.update(ob_top=ob_top, ob_bot=ob_bot, ob_tested=ob_tested,
                   fvg_top=fvg_top, fvg_bot=fvg_bot, fvg_tested=fvg_tested,
                   pivot=piv, pivot_res=piv_res)
        out["at_support"] = bool(inside_ob or inside_fvg or near_pivot or near_ob or near_fvg)
        out["zone"] = ("OB inside" if inside_ob else "OB near" if near_ob else
                       "FVG inside" if inside_fvg else "FVG near" if near_fvg else
                       "Pivot near" if near_pivot else
                       "OB tested" if (ob_top is not None and ob_tested) else
                       "FVG tested" if (fvg_top is not None and fvg_tested) else "outside")
    except Exception:
        pass
    return out


def _confirmed_weekly_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Resample a daily OHLCV frame to CONFIRMED W-FRI weekly bars (the forming
    week dropped), so weekly zone detection never repaints intra-week — the same
    guard as `_confirmed_weekly_close`, but for the full OHLCV set."""
    wk = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                   "Close": "last", "Volume": "sum"}).dropna()
    if len(wk) and df.index[-1].normalize() < wk.index[-1].normalize():
        wk = wk.iloc[:-1]
    return wk


def _confirmed_month_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Resample a daily OHLCV frame to CONFIRMED month-end bars (the forming month
    dropped), so monthly zone detection never repaints intra-month. Mirror of
    `_confirmed_weekly_ohlcv` — used by the GM IZE location gate so a shelf S4 tags
    Weekly (which can land on the monthly resample here) is still caught."""
    mo = df.resample("ME").agg({"Open": "first", "High": "max", "Low": "min",
                                "Close": "last", "Volume": "sum"}).dropna()
    if len(mo) and df.index[-1].normalize() < mo.index[-1].normalize():
        mo = mo.iloc[:-1]
    return mo


def resample_intraday(df_base: pd.DataFrame, minutes: int, base_minutes: int = 25) -> pd.DataFrame:
    """Session-anchored resample of intraday bars to a coarser TF (75 or 125-min).

    NSE trades 09:15–15:30 = 375 min. `pd.resample` anchors at midnight and would
    merge the overnight gap, so instead we chunk each SESSION's base bars into
    groups of (minutes // base_minutes) — anchored at the 09:15 open, exactly like
    TradingView's 75/125-min candles. The final chunk of the live session may be
    partial (the forming intraday bar) — that's intentional for entry timing.
    """
    if df_base is None or df_base.empty:
        return df_base
    step = max(1, minutes // base_minutes)
    rows = []
    for _sess, g in df_base.groupby(df_base.index.normalize()):
        g = g.sort_index()
        for i in range(0, len(g), step):
            ch = g.iloc[i:i + step]
            rows.append({"Datetime": ch.index[0],
                         "Open": float(ch["Open"].iloc[0]), "High": float(ch["High"].max()),
                         "Low": float(ch["Low"].min()), "Close": float(ch["Close"].iloc[-1]),
                         "Volume": float(ch["Volume"].sum())})
    if not rows:
        return df_base.iloc[0:0]
    out = pd.DataFrame(rows).set_index("Datetime").sort_index()
    out.index.name = "Datetime"
    return out


def detect_support_zones_dw(daily_df: pd.DataFrame) -> dict:
    """Support zones on BOTH the Daily and (confirmed) Weekly timeframes — the
    twin of the Section 4 Pine v2.1, which requests `f_zones()` on "D" and "W".
    Weekly zones are the bigger structural demand; daily are the precise entry
    level. The trading TF (125/75-min) reads both.

    Returns:
      {"daily": <detect_support_zones(daily)>,
       "weekly": <detect_support_zones(weekly)>,
       "at_support": daily.at_support OR weekly.at_support,
       "zone": "D:<zone> · W:<zone>"}
    """
    d = detect_support_zones(daily_df)
    try:
        w = detect_support_zones(_confirmed_weekly_ohlcv(daily_df))
    except Exception:
        w = {"ob_top": None, "ob_bot": None, "fvg_top": None, "fvg_bot": None,
             "pivot": None, "at_support": False, "zone": "outside"}
    return {"daily": d, "weekly": w,
            "at_support": bool(d.get("at_support") or w.get("at_support")),
            "zone": f"D:{d.get('zone','outside')} · W:{w.get('zone','outside')}"}


def _confirmed_weekly_close(c: pd.Series) -> pd.Series:
    """W-FRI weekly closes with the FORMING week dropped.

    The final resampled row is the current (incomplete) week unless the last
    daily bar IS that week's Friday label — evaluating a crossover on it
    repaints mid-week (fires Monday, un-fires by Friday), the same failure
    class as the S4 Pine request.security(D) forming-bar repaint.
    """
    wk = c.resample("W-FRI").last().dropna()
    if len(wk) and c.index[-1].normalize() < wk.index[-1].normalize():
        wk = wk.iloc[:-1]
    return wk


# ── DEAD-PATTERN FIXES (5-Aug-2026) ──────────────────────────────────────────
# Two bull patterns fired ~0% of the time and had done so for months. Measured over
# 3,000 bar-evaluations on 15 names:
#     Stage-2 Launch        0 firings  — 153 REAL weekly 30WMA crossovers in the window
#     Bullish Engulfing     0 firings  — 415 raw engulfings in the same bars
# Neither was a rare pattern. Both were mis-specified, in different ways.
# Flag kept so the before/after is one run apart rather than a memory of what changed.
PA_FIXES = True


def detect_bull_patterns(df: pd.DataFrame, stage: str = "", intraday: bool = False,
                         ema20_ref=None, ema10_ref=None) -> list:
    """Mirror of Dashboard v67's PA pattern battery, evaluated on the LAST bar.

    ``intraday=True`` (when the battery runs on 75/125-min bars) suppresses the
    weekly/positional-anchored patterns that are meaningless on an intraday TF:
    ★★ Power Play HTF ("100% in 8 weeks") and Stage-2 Launch (weekly 30-WMA
    crossover). Every other pattern is bar-based and computes correctly on any TF.
    ``ema20_ref`` / ``ema10_ref`` — when the caller runs this on an intraday TF it
    passes the DAILY EMA20/EMA10 (per the DNA "EMA20(Daily) overlaid on 75/125m"),
    so the engulfing trend-context anchors on the daily EMA20, not an intraday one.

    Formulas ported 1:1 from 'Weinstein and Swing Pro Dashboard v67.4.12.pine'
    (incl. the v67.4.x fixes: strict NR7, prior-bar VCP contraction, RSI/vol-
    gated engulfing, 50-SMA-gated pocket pivot). Jay's spec: these are strong
    PA patterns he can't reliably spot by eye — surface them loudly.

    Returns [(name, fired: bool, tier: int, note: str), ...]
    """
    pats = []
    try:
        c, o, h, l, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
        if len(c) < 60:
            return pats
        cN, oN = float(c.iloc[-1]), float(o.iloc[-1])
        hN, lN, vN = float(h.iloc[-1]), float(l.iloc[-1]), float(v.iloc[-1])
        rng = hN - lN
        vol50 = v.rolling(50).mean()
        rv = vN / float(vol50.iloc[-1]) if float(vol50.iloc[-1]) else 0.0
        sma50 = float(c.rolling(50).mean().iloc[-1])
        ema10 = float(c.ewm(span=10, adjust=False).mean().iloc[-1])
        ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
        # EMA20 (& EMA10) are DAILY anchors in the DNA — on an intraday TF the
        # caller passes the daily EMAs so the engulfing trend-context uses the
        # daily EMA20 overlaid on 75/125m (not a fresh intraday EMA20). Also keeps
        # parity with the S4 Pine, whose battery computes on daily bars.
        _e10 = float(ema10_ref) if ema10_ref is not None else ema10
        _e20 = float(ema20_ref) if ema20_ref is not None else ema20
        intrapos = (cN - lN) / rng if rng > 0 else 0.0

        # ★★ Power Play (High Tight Flag) — 100% move in 8w + tight 15-bar flag.
        # Positional/weekly by nature → suppressed on an intraday TF.
        low8w = float(l.iloc[-40:].min())
        l15 = float(l.iloc[-15:].min())
        htf = ((not intraday) and low8w > 0 and (cN - low8w) / low8w > 1.0 and l15 > 0 and
               (float(h.iloc[-15:].max()) - l15) / l15 < 0.20 and cN > sma50)
        pats.append(("★★ Power Play (HTF)", htf, 4, "100% in 8w + tight flag"))

        # Power Play (Strong Close) — bullish marubozu-ish close on volume
        sc = cN > oN and (cN - lN) > (hN - cN) * 3 and rv > 1.0
        pats.append(("Power Play (Strong Close)", sc, 2, "top-quartile close on vol"))

        # VCP Breakout — contraction on the PRIOR bar, then 10d-high break on vol
        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr10 = tr.ewm(alpha=1 / 10, adjust=False).mean()
        atr10_s50 = atr10.rolling(50).mean()
        # VWMA of VOLUME (dry-up), matching pa_field_validator + Dashboard v67 (ta.vwma(volume,5)).
        # FIX 8-Jul-2026: was (c*v) = vwma of PRICE → `< vol50` trivially True (no-op dry leg).
        vwma_vol5 = (v * v).rolling(5).sum() / v.rolling(5).sum()
        vcp_prior = (not math.isnan(float(atr10_s50.iloc[-2])) and
                     float(atr10.iloc[-2]) < float(atr10_s50.iloc[-2]) * 1.5 and
                     float(vwma_vol5.iloc[-2]) < float(vol50.iloc[-2]))
        vcp_bo = vcp_prior and cN > float(h.iloc[-11:-1].max()) and rv > 1.2 and intrapos >= 0.60
        pats.append(("VCP Breakout", vcp_bo, 3, "tight prior bar → 10d-high break"))

        # Pocket Pivot — up close, vol > any down-day vol in last 10, above 50-SMA
        mdv = 0.0
        for j in range(1, 11):
            if float(c.iloc[-1 - j]) < float(c.iloc[-2 - j]) and float(v.iloc[-1 - j]) > mdv:
                mdv = float(v.iloc[-1 - j])
        pocket = (cN > float(c.iloc[-2]) and cN > oN and mdv > 0 and vN > mdv and
                  cN > sma50 and (cN - lN) >= rng * 0.5)
        pats.append(("Pocket Pivot", pocket, 2, "vol > every down-day vol (10d)"))

        # Bullish Engulfing — v67.4.11 gate: downtrend ctx + relVol>2 + RSI[1]<40
        delta = c.diff()
        up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        c1, o1 = float(c.iloc[-2]), float(o.iloc[-2])
        raw_eng = c1 < o1 and cN > oN and oN <= c1 and cN >= o1
        if PA_FIXES:
            # BUG 2 — `cN < _e10 < _e20` is a DOWNTREND requirement, sitting in the BULL
            # battery. Together with rsi<40 and rv>2.0 it described a capitulating stock,
            # which is the RECOVERY battery's job (and its CLIMAX pattern already covers
            # it). Result: 2 firings in 11,552 bars against 415 raw engulfings — the
            # pattern was ~200x rarer than the thing it claims to detect, and it took
            # `Bear Trap` down with it (that combo needs this as its trigger).
            # The bull-side meaning of an engulf is a PULLBACK RECLAIM: price working
            # back up through the short EMA in an intact uptrend, on real volume.
            # No RSI gate — "oversold" is not part of a continuation setup.
            # ema20 here is a SCALAR (last value), so the rising test needs its own
            # series — computed locally rather than assuming one is in scope.
            _e20s = c.ewm(span=20, adjust=False).mean()
            _rising20 = len(_e20s) >= 6 and float(_e20s.iloc[-1]) > float(_e20s.iloc[-6])
            engulf = raw_eng and cN > _e20 and _rising20 and rv > 1.25
        else:
            engulf = (raw_eng and cN < _e10 < _e20 and rv > 2.0 and
                      not math.isnan(float(rsi.iloc[-2])) and float(rsi.iloc[-2]) < 40)
        pats.append(("Bullish Engulfing (gated)", engulf, 2, "engulf reclaim in uptrend on vol"))

        # Liquidity Sweep Reclaim — swept below 50-SMA in last 5 bars, reclaimed on 1.5× vol
        liq = (float(l.iloc[-5:].min()) < sma50 and cN > sma50 and
               vN > float(vol50.iloc[-1]) * 1.5)
        pats.append(("Liq Sweep Reclaim", liq, 2, "sweep < 50SMA → reclaim on vol"))

        # 3-Bar Bull Reversal — 3 lower lows, close > max of those 3 highs
        rev3 = (float(l.iloc[-2]) < float(l.iloc[-3]) and float(l.iloc[-3]) < float(l.iloc[-4])
                and cN > float(h.iloc[-4:-1].max()))
        pats.append(("3-Bar Bull Reversal", rev3, 2, "3 lower lows → reclaim"))

        # Stage-2 Launch — TRUE weekly crossover of close over 30-WMA + volume.
        # CONFIRMED weeks only (fix 9-Jul-2026) — no mid-week repaint.
        launch = False
        if not intraday:                              # weekly crossover — daily-TF only
            wk = _confirmed_weekly_close(c)
            if len(wk) >= 32:
                wma30 = wk.rolling(30).mean()
                crossed = (float(wk.iloc[-1]) > float(wma30.iloc[-1]) and
                           float(wk.iloc[-2]) <= float(wma30.iloc[-2]))
                if PA_FIXES:
                    # BUG 1 — the pattern was gated on `"2" in str(stage)`, and the ONLY
                    # production caller passes stage="". "2" in "" is False, so the price
                    # logic below never ran: 0 firings against 153 real crossovers. Every
                    # TEST passed stage="Stage 2", which is why nothing caught it.
                    # A pattern must not silently disable itself because a caller omitted
                    # an optional argument, so Stage 2 is DERIVED here: price above a
                    # RISING weekly 30-SMA. Same definition the rest of the stack settled
                    # on today (weekly sma(close,30), 4-week slope).
                    s2 = (len(wma30.dropna()) >= 5 and
                          float(wk.iloc[-1]) > float(wma30.iloc[-1]) and
                          float(wma30.iloc[-1]) > float(wma30.iloc[-5]))
                    # BUG 1b — volume was a DAILY relative-volume test gating a WEEKLY
                    # structural event. It asked that the day you happened to look also
                    # had heavy volume, which says nothing about the launch week's
                    # conviction, and it removed ~95% of the survivors. Now the crossover
                    # WEEK's volume against its own 30-week average.
                    wvol_ok = True
                    try:
                        wkv = _confirmed_weekly_ohlcv(df)["Volume"].astype(float)
                        if len(wkv) >= 30:
                            wvol_ok = float(wkv.iloc[-1]) > float(wkv.rolling(30).mean().iloc[-1]) * 1.1
                    except Exception:
                        pass
                    launch = crossed and s2 and wvol_ok
                else:
                    launch = ("2" in str(stage)) and rv > 1.25 and crossed
        pats.append(("Stage-2 Launch", launch, 3, "confirmed weekly close × over 30-WMA"))

        # Inside-3 (Coil) — three nested inside bars
        def _inside(k):
            return (float(h.iloc[-k]) < float(h.iloc[-k - 1]) and
                    float(l.iloc[-k]) > float(l.iloc[-k - 1]))
        inside = _inside(1)
        inside3 = inside and _inside(2) and _inside(3)
        pats.append(("Inside-3 (Coil)", inside3, 2, "3 nested inside bars"))

        # True NR7 — current range STRICTLY smallest of last 7
        nr7 = all((float(h.iloc[-i]) - float(l.iloc[-i])) >= rng for i in range(2, 8)) and rng > 0
        pats.append(("True NR7", nr7, 1, "tightest range of 7 bars"))
        # UNCONDITIONAL (10-Aug-2026). This was the only pattern in the battery appended
        # *inside* an `if`, so the returned list was 16 entries when the coil was quiet and
        # 17 when it fired. Consequences: the battery length was not a constant (the thing
        # the composition regression test exists to pin), a caller could not render `IBN ·`
        # as quiet the way Pine's grid does, and any positional read of the list shifted by
        # one whenever the coil fired. Σ is unaffected either way — the tier is only summed
        # when the flag is True — so this is a shape fix, not a signal change.
        pats.append(("★ IB-NR7 Coil", bool(inside and nr7), 2, "inside bar + NR7 — Crabel coil"))

        # --- v1.4 additions (17-set): strong v67-cascade triggers the curated 11 omitted.
        # Formulas mirror Section4_Entry_Trigger v1.4 / pa_field_validator (zero-drift). ---
        sma200 = float(c.rolling(200).mean().iloc[-1])
        body = abs(cN - oN); uw = hN - max(oN, cN); lw = min(oN, cN) - lN
        hammer = rng > 0 and lw > body * 2 and uw < body and max(oN, cN) >= lN + rng * 0.66
        l50p = float(l.iloc[-51:-1].min())      # prior 50-bar low  (ta.lowest(low,50)[1])
        dlockH = float(h.iloc[-21:-1].max())    # 20-bar locked resistance (ta.highest(high,20)[1])
        # Wyckoff Spring +3 — undercut prior 50-bar low, reclaim green, on LOW volume
        spring = lN < l50p and cN > l50p and cN > oN and vN < float(vol50.iloc[-1])
        pats.append(("Wyckoff Spring", spring, 3, "undercut 50-low → reclaim on low vol"))
        # Gap-Up Breakout +3 — gap over prior high, clears the 20-bar lock on vol
        gap_bo = oN > float(h.iloc[-2]) and cN > dlockH and cN > oN and rv > 1.25
        pats.append(("Gap-Up Breakout", gap_bo, 3, "gap clears 20-bar lock on vol"))
        # 50-SMA Undercut & Reclaim +2
        undercut = lN < sma50 and cN > sma50 and cN > oN and rv > 1.25
        pats.append(("50SMA Undercut & Reclaim", undercut, 2, "sweep < 50SMA → close above on vol"))
        # Hammer at 50-SMA +2
        h50 = hammer and abs(lN - sma50) / sma50 <= 0.015 and cN > sma50 and rv > 1.0
        pats.append(("Hammer at 50-SMA", h50, 2, "hammer rejects 50-SMA on vol"))
        # Hammer at 200-SMA +2
        h200 = (hammer and not math.isnan(sma200) and sma200 > 0
                and abs(lN - sma200) / sma200 <= 0.020 and cN > sma200 and rv > 1.0)
        pats.append(("Hammer at 200-SMA", h200, 2, "hammer rejects 200-SMA on vol"))
        # Breakout Confirmed +2 — anti-algo: close > 20-bar lock, top-quartile close, on vol
        bo_conf = cN > dlockH and (cN - lN) > rng * 0.75 and rv > 1.25
        pats.append(("Breakout Confirmed", bo_conf, 2, "close > 20-bar lock, top-quartile, on vol"))
    except Exception:
        pass
    return pats


def detect_recovery_patterns(df: pd.DataFrame, stage: str = "", intraday: bool = False,
                             ema20_ref=None, ema10_ref=None) -> list:
    """RECOVERY-path PA battery (10) — capitulation-reversal + Wyckoff accumulation
    + Stage 1→2 turn. These fit a beaten-down, fundamentally-strong base turning up
    (NOT the bull continuation patterns). RS-turning-up is handled in the recovery
    QUALITY gate, not here. Mirrors Section4_Entry_Trigger Recovery mode (zero-drift).
    ``intraday=True`` suppresses the weekly 30-WMA Reclaim (meaningless on 75/125-min).
    ``ema20_ref``/``ema10_ref`` — daily EMA overlay for the engulfing trend-context
    when run on an intraday TF (DNA: EMA20 is a daily anchor).
    Returns [(name, fired, tier, note), ...].
    """
    pats = []
    try:
        c, o, h, l, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
        if len(c) < 60:
            return pats
        cN, oN = float(c.iloc[-1]), float(o.iloc[-1])
        hN, lN, vN = float(h.iloc[-1]), float(l.iloc[-1]), float(v.iloc[-1])
        rng = hN - lN
        vol50 = v.rolling(50).mean(); v50 = float(vol50.iloc[-1]) if not math.isnan(float(vol50.iloc[-1])) else 0.0
        rv = vN / v50 if v50 else 0.0
        sma50 = float(c.rolling(50).mean().iloc[-1])
        sma200 = float(c.rolling(200).mean().iloc[-1])
        ema10 = float(c.ewm(span=10, adjust=False).mean().iloc[-1])
        ema20 = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
        _e10 = float(ema10_ref) if ema10_ref is not None else ema10   # daily EMA overlay on intraday
        _e20 = float(ema20_ref) if ema20_ref is not None else ema20
        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
        lo_recent = float(l.iloc[-10:].min())
        lo_prior = float(l.iloc[-40:-10].min())

        # 1. Climax Reversal (SC + Auto-Rally) +3 — a climax down-bar in the last 10
        #    (vol>2.5x, range>2*ATR, down) whose midpoint price has since reclaimed.
        climax_i = None
        for j in range(1, 11):
            if (float(c.iloc[-j]) < float(o.iloc[-j]) and float(v.iloc[-j]) > v50 * 2.5
                    and (float(h.iloc[-j]) - float(l.iloc[-j])) > atr * 2):
                climax_i = j; break
        climax_rev = False
        if climax_i:
            cmid = (float(h.iloc[-climax_i]) + float(l.iloc[-climax_i])) / 2
            climax_rev = cN > cmid and cN > oN
        pats.append(("Climax Reversal (SC+AR)", climax_rev, 3, "climax vol low → reclaim midpoint"))

        # 2. Wyckoff Spring +3
        l50p = float(l.iloc[-51:-1].min())
        spring = lN < l50p and cN > l50p and cN > oN and vN < v50
        pats.append(("Wyckoff Spring", spring, 3, "undercut 50-low → reclaim on low vol"))

        # 3. Higher-Low / Double-Bottom (2B) +3 — recent low RETESTS the prior
        # base low (holds >= 1% undercut, stays within 10% above it) and turns
        # up. The proximity ceiling (fix 9-Jul-2026) stops the pattern firing
        # on every green day of an established uptrend, where the 10-bar low
        # is trivially above the 40-bar base low.
        two_b = (lo_prior > 0 and lo_prior * 0.99 <= lo_recent <= lo_prior * 1.10
                 and cN > oN and cN > float(c.iloc[-2]))
        pats.append(("Higher-Low / 2B", two_b, 3, "higher/equal low retesting the base low, turning up"))

        # 4. Base Breakout (SOS / JAC) +3 — wide up-bar over 20-bar base resistance on vol
        base_res = float(h.iloc[-21:-1].max())
        sos = cN > base_res and rng > atr * 1.3 and rv > 1.5 and cN > oN
        pats.append(("Base Breakout (SOS/JAC)", sos, 3, "wide up-bar over base resistance on vol"))

        # 5. Bullish Engulfing (oversold) +2
        delta = c.diff()
        up = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        c1, o1 = float(c.iloc[-2]), float(o.iloc[-2])
        raw_eng = c1 < o1 and cN > oN and oN <= c1 and cN >= o1
        engulf = (raw_eng and cN < _e10 < _e20 and rv > 2.0
                  and not math.isnan(float(rsi.iloc[-2])) and float(rsi.iloc[-2]) < 40)
        pats.append(("Bullish Engulfing", engulf, 2, "engulf at oversold on 2× vol"))

        # 6. Hammer at support (200-SMA or the base low) +2
        body = abs(cN - oN); uw = hN - max(oN, cN); lw = min(oN, cN) - lN
        hammer = rng > 0 and lw > body * 2 and uw < body and max(oN, cN) >= lN + rng * 0.66
        near200 = not math.isnan(sma200) and sma200 > 0 and abs(lN - sma200) / sma200 <= 0.02
        near_base = lo_prior > 0 and abs(lN - lo_prior) / lo_prior <= 0.03
        hammer_sup = hammer and (near200 or near_base) and cN > oN and rv > 1.0
        pats.append(("Hammer at support", hammer_sup, 2, "hammer rejects 200-SMA / base low"))

        # 7. 3-Bar Bull Reversal +2
        rev3 = (float(l.iloc[-2]) < float(l.iloc[-3]) and float(l.iloc[-3]) < float(l.iloc[-4])
                and cN > float(h.iloc[-4:-1].max()))
        pats.append(("3-Bar Bull Reversal", rev3, 2, "3 lower lows → reclaim"))

        # 8. Pocket Pivot +2
        mdv = 0.0
        for j in range(1, 11):
            if float(c.iloc[-1 - j]) < float(c.iloc[-2 - j]) and float(v.iloc[-1 - j]) > mdv:
                mdv = float(v.iloc[-1 - j])
        pocket = (cN > float(c.iloc[-2]) and cN > oN and mdv > 0 and vN > mdv
                  and cN > sma50 and (cN - lN) >= rng * 0.5)
        pats.append(("Pocket Pivot", pocket, 2, "vol > every down-day vol (10d)"))

        # 9. Volume Dry-Up (VDU) +1 — supply exhausted at the base
        vdu = rv < 0.5 and rng < atr * 0.8
        pats.append(("Volume Dry-Up", vdu, 1, "supply exhausted at base (vol<50%)"))

        # 10. 30-WMA Reclaim (Stage 1→2) +3 — CONFIRMED weekly close reclaims
        # the 30-WMA (forming week dropped — fix 9-Jul-2026, no repaint).
        # Weekly by nature → suppressed on an intraday TF.
        reclaim30 = False
        if not intraday:
            wk = _confirmed_weekly_close(c)
            if len(wk) >= 31:
                wma30 = wk.rolling(30).mean()
                reclaim30 = float(wk.iloc[-1]) > float(wma30.iloc[-1]) and float(wk.iloc[-2]) <= float(wma30.iloc[-2])
        pats.append(("30-WMA Reclaim", reclaim30, 3, "confirmed weekly close reclaims 30-WMA (Stage 1→2)"))
    except Exception:
        pass
    return pats


# ── MARGINAL (knife-edge) PATTERN DETECTION ──────────────────────────────────
# WHY (Jay, 5-Aug-2026): NAM-INDIA showed PA 6 on the Golden Matcher and 2 on the S4
# panel for the SAME 75m bar. Not a logic bug — the feeds differ by a hair:
#     Dhan  O1203.5 C1210.4 -> close sits 76.4% up the bar's range -> Sigma 6
#     TV    O1201.0 C1210.0 -> close sits 73.2% up the bar's range -> Sigma 2
# A 40-paise difference in the close cost four points of Sigma, because three patterns
# were sitting exactly on their thresholds. That will keep happening: the two surfaces
# read different feeds by design, and no amount of formula parity fixes it.
#
# So instead of chasing agreement, SAY WHICH PATTERNS ARE KNIFE-EDGE. A pattern whose
# fired/not state flips under a nudge smaller than the routine disagreement between two
# feeds is not really a signal — it is a coin-flip, and it should look like one.
#
# METHOD — perturbation, deliberately NOT a table of per-pattern thresholds:
# re-run the WHOLE battery with the last bar's close and volume nudged, and report any
# pattern that changes its mind. This covers all 17 patterns with no threshold
# bookkeeping to drift out of sync, it keeps working when a formula changes, and it asks
# the question we actually care about ("would a slightly different feed disagree?")
# rather than a proxy for it.
#
# Defaults are sized from the observed feed gap, not invented: 0.15% on close (the
# Dhan/TV close differed by 0.03%, the open by 0.21%) and 3% on volume.
MARGINAL_CLOSE_EPS = 0.0015
MARGINAL_VOL_EPS   = 0.03


def marginal_patterns(df, *, intraday: bool = False, ema20_ref=None, ema10_ref=None,
                      recovery: bool = False, stage: str = "",
                      close_eps: float = MARGINAL_CLOSE_EPS,
                      vol_eps: float = MARGINAL_VOL_EPS) -> set:
    """Names of patterns sitting on their threshold at the last bar.

    Returns the set of pattern names whose fired/not state FLIPS when the last bar's
    close and volume are nudged by less than the routine difference between two data
    feeds. Empty set = every pattern is decided by a comfortable margin.

    Never raises: a failure here must not cost the caller its PA read, so it degrades to
    an empty set (reported as "no marginals" rather than a wrong claim).
    """
    fn = detect_recovery_patterns if recovery else detect_bull_patterns
    try:
        if df is None or len(df) < 60:
            return set()

        def fired(frame):
            return {n for (n, f, _t, _d) in fn(frame, stage=stage, intraday=intraday,
                                               ema20_ref=ema20_ref, ema10_ref=ema10_ref) if f}

        base = fired(df)
        marg = set()
        ci = df.columns.get_loc("Close")
        vi = df.columns.get_loc("Volume")
        hi = float(df["High"].iloc[-1])
        lo = float(df["Low"].iloc[-1])
        c0 = float(df["Close"].iloc[-1])
        v0 = float(df["Volume"].iloc[-1])
        for dc in (1 - close_eps, 1 + close_eps):
            for dv in (1 - vol_eps, 1 + vol_eps):
                p = df.copy()
                # A close outside the bar's own range is not a feed difference, it is a
                # different bar — clamp so the perturbation stays physically possible.
                p.iloc[-1, ci] = min(max(c0 * dc, lo), hi)
                p.iloc[-1, vi] = max(v0 * dv, 0.0)
                marg |= base ^ fired(p)
        return marg
    except Exception:
        return set()
