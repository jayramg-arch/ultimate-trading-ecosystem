"""wcl_context.py — Weinstein Context Layers (WCL v1.2) Wyckoff + SMC ported to Python.

Companion to ``zone_engine.py``. That module ported S4's leg-base-leg demand/supply
zones, S/R levels, AVWAPs and Volume Profile; this one ports the two remaining WCL
subsystems that had no Python implementation at all:

  * **Wyckoff event series** — SC / PS / ST / Spring / LPS / SOS on the accumulation
    side, PSY / BC / UT / SOW / LPSY on the distribution side, with a 15-bar decay.
  * **SMC structure** — BOS / CHoCH swing structure, liquidity sweeps, and the
    20-bar CHoCH count that drives Structure Health.

WHY THIS EXISTS
---------------
Before this module, the Golden Matcher and Trigger Board rendered "WCL Context",
"Structure Health" and a Wyckoff bias from *proxies*: Wyckoff was ``acc_ok and
stage in (1,2)``, SMC was the string ``Active_Dir`` (or, on the board, literally the
path name), and ``choch_count_20`` was read with ``default=0`` and produced nowhere —
so Structure Health was permanently ``CLEAN (0)``. The panels agreed in wording and
could not agree in number. This module computes the same quantities Pine computes,
so a GM-vs-S4 disagreement now means something (feed or timeframe), rather than
meaning the two surfaces were never running the same calculation.

SOURCE OF TRUTH
---------------
Ported 1:1 from ``Section4_Entry_Trigger_v5.9.pine`` (renamed from _v5.0 on 29-Jul;
the port was made against in-file title v5.1), sections
"Wyckoff Series" and "SMC Module". Three Pine behaviours are load-bearing and are
reproduced deliberately — do not "clean them up":

1. ``ta.pivothigh(high, 10, 10)`` resolves on the CONFIRMATION bar, 10 bars after the
   pivot itself. Pine therefore records ``wyk_last_bar := bar_index`` (the confirmation
   bar) while testing the PIVOT bar's characteristics via ``[wyk_pb]``. Freshness and
   decay are measured from the confirmation bar. We do the same.
2. The bearish Wyckoff block runs UNCONDITIONALLY after the bullish one (it is a second
   ``if``, not an ``else``), so a bar satisfying both resolves to DISTRIBUTION.
3. ``smc_choch_up = smc_bull_bos and not smc_trend_up`` is evaluated BEFORE the trend
   flag is updated on that bar, i.e. against the prior bar's trend state.

Because all three depend on persistent ``var`` state, this is a bar-by-bar loop rather
than a vectorised pass. At ~500 bars x ~50 board symbols that is ~25k iterations —
negligible next to the OHLCV fetch.

PIVOT TIE-BREAKING (documented assumption): ``ta.pivothigh`` treats an exact tie as
breaking the pivot; we implement strictly-greater on both sides to match. Exact ties
are rare and, where they occur, the two surfaces are already on different feeds
(Dhan vs TradingView), so this is not the leading source of any disagreement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

try:                                    # reuse the ATR already ported — zero drift
    from zone_engine import _wilder_atr as _atr_pair
except Exception:                       # pragma: no cover - stand-alone fallback
    def _atr_pair(h, l, c, length=14):
        tr = np.empty(len(c))
        tr[0] = h[0] - l[0]
        for i in range(1, len(c)):
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        atr = np.full(len(c), np.nan)
        if len(c) >= length:
            atr[length - 1] = tr[:length].mean()
            for i in range(length, len(c)):
                atr[i] = (atr[i - 1] * (length - 1) + tr[i]) / length
        return tr, atr


# Pine constants — keep these names identical to the .pine so a diff is mechanical.
WYK_PIVOT_LEN = 10
WYK_VOL_LOOKBK = 20
WYK_DECAY_BARS = 15
SMC_BOS_LEN = 10
SMC_LIQ_LEN = 10
CHOCH_WINDOW = 20


def _confirmed_pivots(vals: np.ndarray, left: int, right: int, high: bool) -> np.ndarray:
    """Mirror of ta.pivothigh / ta.pivotlow.

    Returns an array the same length as ``vals``, NaN everywhere except at each
    CONFIRMATION index ``i`` (= pivot index + ``right``), where it holds the pivot's
    value. Strictly-greater/-less on both sides, so ties break the pivot.
    """
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(left, n - right):
        v = vals[i]
        if np.isnan(v):
            continue
        window_l = vals[i - left:i]
        window_r = vals[i + 1:i + right + 1]
        if high:
            ok = (window_l < v).all() and (window_r < v).all()
        else:
            ok = (window_l > v).all() and (window_r > v).all()
        if ok:
            out[i + right] = v          # value surfaces on the CONFIRMATION bar
    return out


def wyckoff_state(df: pd.DataFrame, pivot_len: int = WYK_PIVOT_LEN,
                  vol_lookback: int = WYK_VOL_LOOKBK,
                  decay_bars: int = WYK_DECAY_BARS, atr_len: int = 14) -> dict:
    """Port of the Pine "Wyckoff Series" block.

    Returns the LATEST state (what the panel shows), not a series:
        event      — 'SOS' | 'Spring' | 'LPS' | 'SC' | 'PS' | 'ST' |
                     'SOW' | 'LPSY' | 'UT' | 'BC' | 'PSY' | '—'
        bias       — 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL'
        score_base — undecayed tier, +4..-4 (matches wyk_score_base)
        age_bars   — bars since the event's CONFIRMATION bar (9999 if none)
        score_comp — decayed score actually fed to the context total
    """
    out = {"event": "—", "bias": "NEUTRAL", "score_base": 0,
           "age_bars": 9999, "score_comp": 0, "ok": False}
    if df is None or len(df) < max(pivot_len * 2 + 2, vol_lookback + 2, atr_len + 2):
        return out

    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    o = df["Open"].to_numpy(float)
    v = df["Volume"].to_numpy(float)
    n = len(c)

    _, atr = _atr_pair(h, l, c, atr_len)
    avg_vol = pd.Series(v).rolling(vol_lookback).mean().to_numpy()

    rng = h - l
    denom = np.maximum(rng, 0.001)
    hi_vol = v > avg_vol * 1.5
    lo_vol = v < avg_vol * 0.7
    wide = rng > atr * 1.4
    narrow = rng < atr * 0.6
    up_bar = c > o
    dn_bar = c < o
    cls_hi = (c - l) / denom > 0.65
    cls_lo = (h - c) / denom > 0.65

    ph = _confirmed_pivots(h, pivot_len, pivot_len, high=True)
    pl = _confirmed_pivots(l, pivot_len, pivot_len, high=False)
    pb = pivot_len

    prev_pl = np.nan
    curr_pl = np.nan
    last_event, bias, score_base = "—", "NEUTRAL", 0
    last_idx = None

    for i in range(n):
        has_ph = not np.isnan(ph[i])
        has_pl = not np.isnan(pl[i])
        if has_pl:
            prev_pl, curr_pl = curr_pl, pl[i]
        lower_low = has_pl and not np.isnan(prev_pl) and pl[i] < prev_pl

        j = i - pb                       # the PIVOT bar, whose character we test
        if j < 0:
            continue
        if np.isnan(atr[j]) or np.isnan(avg_vol[j]):
            continue
        w_hiv, w_lov = hi_vol[j], lo_vol[j]
        w_wid, w_nar = wide[j], narrow[j]
        w_chi, w_clo = cls_hi[j], cls_lo[j]
        w_upb, w_dnb = up_bar[j], dn_bar[j]

        sc_c = has_pl and w_hiv and w_wid and w_clo
        ps_c = has_pl and w_hiv and (not w_clo) and (not sc_c)
        st_c = has_pl and w_lov and w_nar
        spr_c = has_pl and w_lov and w_chi and w_upb
        sos_c = has_ph and w_hiv and w_wid and w_chi and w_upb
        lps_c = has_pl and w_lov and w_upb and (not spr_c)
        psy_c = has_ph and w_hiv and (not w_chi)
        bc_c = has_ph and w_hiv and w_wid and w_chi and (not w_upb)
        ut_c = has_ph and w_hiv and w_wid and w_clo
        sow_c = lower_low and w_hiv and w_wid and w_clo and w_dnb
        lpsy_c = has_ph and w_lov and w_nar and w_dnb

        # bullish ladder
        if sos_c:
            last_event, bias, score_base, last_idx = "SOS", "ACCUMULATION", 4, i
        elif spr_c or lps_c:
            last_event = "Spring" if spr_c else "LPS"
            bias, score_base, last_idx = "ACCUMULATION", 3, i
        elif sc_c:
            last_event, bias, score_base, last_idx = "SC", "ACCUMULATION", 2, i
        elif ps_c or st_c:
            last_event = "PS" if ps_c else "ST"
            bias, score_base, last_idx = "ACCUMULATION", 1, i

        # bearish ladder — a SECOND if, not an else: distribution wins a tie (Pine parity)
        if sow_c:
            last_event, bias, score_base, last_idx = "SOW", "DISTRIBUTION", -4, i
        elif lpsy_c or ut_c or bc_c or psy_c:
            last_event = ("LPSY" if lpsy_c else "UT" if ut_c else "BC" if bc_c else "PSY")
            bias, last_idx = "DISTRIBUTION", i
            score_base = -3 if (lpsy_c or ut_c) else -2

    age = (n - 1 - last_idx) if last_idx is not None else 9999
    decay_mult = max(0.0, 1.0 - int(age / decay_bars) * 0.25)
    out.update({"event": last_event, "bias": bias, "score_base": int(score_base),
                "age_bars": int(age), "ok": True,
                "score_comp": int(round(score_base * decay_mult))})
    return out


def smc_state(df: pd.DataFrame, bos_len: int = SMC_BOS_LEN,
              liq_len: int = SMC_LIQ_LEN, choch_window: int = CHOCH_WINDOW) -> dict:
    """Port of the Pine "SMC Module" block (BOS / CHoCH / sweeps / structure health).

    Returns the LATEST state:
        trend_up       — swing-structure direction
        last_event     — 'BOS ▲' | 'CHoCH ▲' | 'BOS ▼' | 'CHoCH ▼' | '—'
        last_was_bull / last_choch / age_bars
        choch_count_20 — CHoCH events inside the trailing window (Structure Health)
        sweep / sweep_bull / sweep_age_bars
        score          — the Pine _smc_score: ±2 trend, ±1 fresh-CHoCH bonus
    """
    out = {"trend_up": True, "last_event": "—", "last_was_bull": True,
           "last_choch": False, "age_bars": 9999, "choch_count_20": 0,
           "sweep": "—", "sweep_bull": False, "sweep_age_bars": 9999,
           "score": 0, "ok": False}
    if df is None or len(df) < max(bos_len, liq_len) * 2 + 2:
        return out

    h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    n = len(c)

    ph_bos = _confirmed_pivots(h, bos_len, bos_len, high=True)
    pl_bos = _confirmed_pivots(l, bos_len, bos_len, high=False)
    ph_liq = _confirmed_pivots(h, liq_len, liq_len, high=True)
    pl_liq = _confirmed_pivots(l, liq_len, liq_len, high=False)

    last_sh = np.nan
    last_sl = np.nan
    prev_sh = np.nan                     # prior BAR's value — ta.crossover needs [1]
    prev_sl = np.nan
    trend_up = True
    last_event, last_was_bull, last_choch = "—", True, False
    last_idx = None
    choch_bars: list[int] = []
    liq_ph = np.nan
    liq_pl = np.nan
    sweep, sweep_bull, sweep_idx = "—", False, None

    for i in range(n):
        if not np.isnan(ph_bos[i]):
            last_sh = ph_bos[i]
        if not np.isnan(pl_bos[i]):
            last_sl = pl_bos[i]

        # ta.crossover(close, last_sh) — compares against the PRIOR bar's level too
        cross_up = (i > 0 and not np.isnan(last_sh) and not np.isnan(prev_sh)
                    and c[i] > last_sh and c[i - 1] <= prev_sh)
        cross_dn = (i > 0 and not np.isnan(last_sl) and not np.isnan(prev_sl)
                    and c[i] < last_sl and c[i - 1] >= prev_sl)

        bull_bos = (not np.isnan(last_sh)) and cross_up
        bear_bos = (not np.isnan(last_sl)) and cross_dn
        # evaluated against the PRIOR trend state, before the update below
        choch_up = bull_bos and not trend_up
        choch_dn = bear_bos and trend_up

        if bull_bos:
            trend_up = True
        if bear_bos:
            trend_up = False

        if choch_up or choch_dn:
            choch_bars.append(i)
        while choch_bars and (i - choch_bars[0]) > choch_window:
            choch_bars.pop(0)

        if bull_bos:
            last_event = "CHoCH ▲" if choch_up else "BOS ▲"
            last_was_bull, last_choch, last_idx = True, choch_up, i
        if bear_bos:
            last_event = "CHoCH ▼" if choch_dn else "BOS ▼"
            last_was_bull, last_choch, last_idx = False, choch_dn, i

        if not np.isnan(ph_liq[i]):
            liq_ph = ph_liq[i]
        if not np.isnan(pl_liq[i]):
            liq_pl = pl_liq[i]

        if (not np.isnan(liq_pl)) and l[i] < liq_pl and c[i] > liq_pl:
            sweep, sweep_bull, sweep_idx = "Sweep ▲", True, i
        if (not np.isnan(liq_ph)) and h[i] > liq_ph and c[i] < liq_ph:
            sweep, sweep_bull, sweep_idx = "Sweep ▼", False, i

        prev_sh, prev_sl = last_sh, last_sl

    age = (n - 1 - last_idx) if last_idx is not None else 9999
    sweep_age = (n - 1 - sweep_idx) if sweep_idx is not None else 9999
    score = (2 if trend_up else -2) + \
            ((1 if last_was_bull else -1) if (last_choch and age <= 10) else 0)

    out.update({"trend_up": bool(trend_up), "last_event": last_event,
                "last_was_bull": bool(last_was_bull), "last_choch": bool(last_choch),
                "age_bars": int(age), "choch_count_20": len(choch_bars),
                "sweep": sweep, "sweep_bull": bool(sweep_bull),
                "sweep_age_bars": int(sweep_age), "score": int(score), "ok": True})
    return out


def structure_health(choch_count: int) -> tuple[str, str]:
    """Pine _struct_str / status. 0-1 CLEAN, 2-3 CHOPPY, 4+ BROKEN.

    MEASURED 28-Jul-2026 over 38 board names, daily + 75m, at bos_len 5 / 7 / 10:
    the count NEVER reached 3. Distribution tops out at 2 (0/38 at >= 3 in every
    cell); >= 2 occurs on 3% of daily names and 11-13% of 75m names. Consequences,
    both deliberate and left as-is for Pine parity:

      * The "BROKEN" tier is UNREACHABLE — it will never render. Do not read its
        absence as "no name is broken".
      * "CHOPPY" means exactly 2 CHoCH in the trailing 20 bars.
      * A gate keyed on `choch_count >= 3` (the v5.0 header proposed one) would
        never fire. That is why the Structure-Health GO downgrade was DROPPED
        rather than shipped — see the S4 v5.1 header.

    Treat this as a DISPLAY row. Before promoting it to anything that gates or
    sizes, it needs outcome evidence that CHoCH count predicts worse trades —
    which nobody has measured. Re-tiering to make the labels "look right" would
    silently break Pine parity; change both surfaces together or neither.
    """
    if choch_count <= 1:
        return f"CLEAN ({choch_count})", "pass"
    if choch_count <= 3:
        return f"CHOPPY ({choch_count})", "watch"
    return f"BROKEN ({choch_count})", "fail"


def stage_score(below_30w=None, below_200=None) -> int:
    """Pine ``stage_score``, including the v5.1 fail-safe.

    Pine reads ``bel30w = close < sma150`` (the daily 150-SMA standing in for the
    30-week MA) and ``bel200 = close < sma200``. A MISSING value must fail to the
    BEARISH side — reading it as "not below" handed back the maximum bullish score
    on no data, which is the silent-fallback pattern this desk explicitly bans.
    """
    b30 = True if below_30w is None else bool(below_30w)
    b200 = True if below_200 is None else bool(below_200)
    if (not b30) and (not b200):
        return 3
    if not b200:
        return 1
    return -2


def context_band(total: int) -> str:
    if total >= 9:
        return "STRONG BULL"
    if total >= 4:
        return "BULL"
    if total >= -3:
        return "NEUTRAL"
    if total >= -6:
        return "CAUTION"
    return "BEAR"


def wcl_context(df: pd.DataFrame, vp_score: int = 0, below_30w=None,
                below_200=None, vp_above_vah: bool | None = None,
                choch_window: int = CHOCH_WINDOW) -> dict:
    """Full WCL context for one symbol — the Python twin of the S4 panel block.

    ``vp_score`` is the Volume-Profile tier (+3 above VAH, +1 VA upper, -1 VA lower,
    -3 below VAL) — pass ``zone_engine.vp_support``'s position mapped to that scale,
    or 0 when VP is unavailable.

    Returns wyckoff / smc sub-dicts plus the composite: ``total_base``, ``setup``,
    ``setup_pri``, ``setup_bonus``, ``total_final``, ``band``, ``struct``.
    """
    wyk = wyckoff_state(df)
    smc = smc_state(df, choch_window=choch_window)

    vp_s = int(vp_score or 0)
    stg = stage_score(below_30w, below_200)
    total_base = wyk["score_comp"] + vp_s + smc["score"] + stg

    choch = smc["choch_count_20"]
    setup, pri, bear = "● NONE", 0, False

    wyk_fresh_15 = wyk["age_bars"] <= 15
    wyk_fresh_10 = wyk["age_bars"] <= 10
    smc_fresh_10 = smc["age_bars"] <= 10

    if wyk["score_base"] == 3 and wyk_fresh_15 and smc["trend_up"] \
            and vp_s >= 1 and total_base >= 4:
        setup, pri = "✓ S2 — Spring/LPS Reversal", 5
    elif smc["sweep_bull"] and smc["sweep_age_bars"] <= 10 and smc["last_choch"] \
            and smc["last_was_bull"] and smc_fresh_10 and vp_s > -3:
        setup, pri = "✓ S3 — Sweep+CHoCH Reversal", 4
    elif vp_s >= 1 and wyk["bias"] == "ACCUMULATION" and total_base >= 2:
        setup, pri = "✓ S1 — OB Retest + VP Support", 3
    elif smc["last_was_bull"] and (not smc["last_choch"]) and smc["age_bars"] <= 20 \
            and bool(vp_above_vah) and choch <= 1:
        setup, pri = "✓ S5 — Stage 2 Continuation > VAH", 2
    elif wyk["score_base"] == 4 and wyk_fresh_10 and vp_s >= 1 and smc["trend_up"]:
        setup, pri = "✓ S6 — SOS Momentum Push", 2
    elif wyk["score_base"] <= -3 and wyk_fresh_15 and (not smc["trend_up"]) \
            and total_base <= -3:
        setup, pri, bear = "✗ S7 — Distribution Breakdown", 3, True
    elif choch >= 3:
        setup, pri = "● S8 — Choppy Range", 1

    bonus = 2 if pri >= 4 else ((-2 if bear else 1) if pri == 3 else (-1 if pri == 1 else 0))
    total_final = total_base + bonus
    struct_str, struct_status = structure_health(choch)

    return {
        "wyckoff": wyk, "smc": smc,
        "vp_score": vp_s, "stage_score": stg,
        "total_base": total_base, "setup": setup, "setup_pri": pri,
        "setup_bear": bear, "setup_bonus": bonus, "total_final": total_final,
        "band": context_band(total_final),
        "struct": struct_str, "struct_status": struct_status,
        "choch_count_20": choch,
    }


def stage_path(below_30w=None, wma30_falling=None) -> tuple[int, str]:
    """THE SHARED Bull/Recovery/NO-TRADE classifier — one definition for BOTH surfaces.

    Mirrors Section4_Entry_Trigger_v5.9.pine exactly (the Weinstein 2x2):

        below 30WMA   30WMA falling   stage   path
           no             no            2     bull
           yes            no            1     recovery
           no             yes           3     none   (topping)
           yes            yes           4     none   (declining)

    S4 derives the two flags from its daily security (d_bel30 = close < SMA150,
    d_s150dn = SMA150 <= SMA150[10]); Python passes the equivalents. A MISSING flag
    fails to the BEARISH side, matching the v5.1 nz(..., 1.0) fail-safe — an unknown
    stage must never be treated as a healthy one.

    NOTE the surfaces still differ on ONE thing, deliberately: GM also carries the
    inherited archetype (which watchlist surfaced the name), which encodes RFF >= 4 and
    the recovery screener's other pillars. Pine cannot see any of that
    (request.financial is capped at 5 calls). So stage decides TRADEABLE on both; the
    archetype remains a GM-only tiebreak when stage is not decisive.
    """
    b30 = True if below_30w is None else bool(below_30w)
    dn = True if wma30_falling is None else bool(wma30_falling)
    if dn:
        return (4, "none") if b30 else (3, "none")
    return (1, "recovery") if b30 else (2, "bull")
