"""zone_engine.py — Python port of the S4 Pine IZE demand/supply zone engine.

Faithful mirror of `Section4_Entry_Trigger_v3.0.pine` (v4.0) `f_detectZone` +
`f_structZone` + the zone lifecycle, so the Golden Matcher's LOCATION gate can use
the SAME leg-base-leg zones the S4 chart draws — instead of the older OB/FVG/pivot
proxy in `pa_patterns.detect_support_zones`.

Ports, with the v3.5-v4.0 refinements:
  * gap-bridged ("invisible") candles — always on (methodology, not a toggle)
  * leg-in -> base -> leg-out formations: RBR / DBR (demand) · RBD / DBD (supply)
  * PER-TF leg-in strictness (legin_ltf 0.6 intraday/daily · legin_htf 1.2 W/M)   [#35]
  * wick distals (house rule) + narrow-zone wick-to-wick rescue                    [#34]
  * per-TF width band (x ATR14)
  * FVG-Polygraph tag (leg-out left an imbalance)
  * base-count / body / volume score + confluence-lite (FVG / gap)
  * lifecycle: reaction -> TESTED (travel in the zone's OWN-TF ATR; + daily EMA20
    cross for DAILY zones only, per the #25/#40/#42 HTF over-removal fix) -> VIOLATED
    (close beyond distal) -> aged out (calendar, per TF)
  * STRUCTURAL (pivot-based) zones — port of f_structZone: a pivot high -> supply shelf
    (PvH), a pivot low -> demand shelf (PvL). Same gap-bridged candles, scored 40..75 so
    a pattern zone always wins dedup; width FLOOR scaled by STRUCT_MIN_W_MULT. Run through
    the SAME lifecycle. This is what makes the D/W/M DZ/SZ counts match S4's panel.

Also ports (the rest of S4's location gate):
  * the S/R HORIZONTAL-LEVEL engine (f_srLevels) — pivot clustering + #30 wick-pierce
    touches + MTTWR grade (tests WEAKEN a level) + R<->S flip → near_sr
  * ANCHORED VWAPs (f_anchors + f_avwap) — Low / BO / Gap anchors → near_avwap

Ported 31 Jul 2026 (Jay's call — closes the last scoring-parity gap with S4):
  * #27 RECENCY DECAY — `Zone.recency_score` (f_recencyScore). Derived, never stored:
    `Zone.score` remains the INTRINSIC merit, so nothing that already reads `score`
    changes meaning and the decay cannot compound across re-reads.
  * #3/#26 CONTROLLING PROMOTION — all three criteria (leads-to-a-new-ATH/ATL with the
    house pullback rule · 50-SMA trend shift · breaks an opposing controlling zone),
    the D/W/M-only TF gate (#2b — never intraday-native), EXCLUSIVITY (one per
    direction, nearest the extreme, a newcomer supersedes only if genuinely nearer),
    and the 2-touch leash a controlling zone earns.
  NOTE both are SCORING/RANKING features. The GM location gate consumes a BOOLEAN
  (`at_support`), so neither can change which names pass it — expect no board movement
  unless/until `ize_score` starts driving ranking.

Deliberately NOT ported: near_ema (price is near the daily EMA20 most of the time — it
would loosen the gate and make the board over-predict; S4 includes it only because the S4
chart is final). And the purely visual layers: geometry/rectangles and manual trendlines.

Public API:
  detect_zones(df, tf)      -> list[Zone] active at the last bar (fresh + tested)
  zone_support(df, tf, px)  -> dict: at_support / in_fresh_dz / nearest zone
  detect_sr_levels(df, tf)  -> list[dict] graded horizontal S/R levels (FRESH/TESTED/MTTWR)
  sr_support(df, tf, px)    -> dict: near_sr (price near a non-MTTWR support level)
  avwap_support(df, px)     -> dict: near_avwap (price near a Low/BO/Gap AVWAP)

`df` is an OHLCV DataFrame (columns Open/High/Low/Close/Volume), oldest-first, for the
timeframe named by `tf` ("75m" / "125m" / "D" / "W" / "M").
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

# ── Per-TF config (mirrors the S4 inputs) ────────────────────────────────────
# `piv` = the structural-zone pivot length for that TF (left = right, the Swing Zigzag
# convention). Canonical per the Zigzag / S/R Lab and S4 v7.5: Monthly 1 · Weekly 5 ·
# Daily 2 · Intraday 2. One global 5/3 used to serve every TF, which was wrong in both
# directions — too coarse to find the daily shelves price actually turns at, and far too
# long for monthly bars, which are scarce and individually significant.
# Mirrored here because the GM location gate calls detect_zones(): if these drift from
# the S4 inputs, the board and the chart disagree about where support IS, which is the
# whole class of bug the archetype handoff was built to end.
TF_CFG = {
    "75m":  dict(minW=0.20, maxW=2.0, legin=0.6, age_days=21,   piv=2, pad=3, thr=1.5),
    "125m": dict(minW=0.25, maxW=2.5, legin=0.6, age_days=28,   piv=2, pad=3, thr=1.5),
    "D":    dict(minW=0.30, maxW=3.0, legin=0.6, age_days=182,  piv=2, pad=3, thr=1.5),   # legin_ltf
    "W":    dict(minW=0.40, maxW=3.5, legin=1.0, age_days=730,  piv=5, pad=2, thr=0.8),   # legin_htf (1.0 = S4 canonical, 19-Jul restore; was 1.2)
    "M":    dict(minW=0.50, maxW=4.0, legin=1.0, age_days=1460, piv=1, pad=1, thr=0.5),   # legin_htf (1.0 = S4 canonical, 19-Jul restore; was 1.2)
}

# Global geometry params — S4 defaults (grpZG / grpZS).
ERC_MULT        = 1.2     # leg-out TR >= this x ATR14
LEG_BODY_STRONG = 0.75    # strong leg body/range
LEG_BODY_AVG    = 0.55    # average leg body/range (rescued by follow-through) + leg-in body
LEGIN_MAX_WICK  = 1.0     # leg-in max wick/body
BASE_RNG_ATR    = 0.6     # a base candle's TR < this x ATR
STRONG_FT       = 0.75    # follow-through net displacement x ATR
BODY_RATIO      = 0.65    # base body/range max
MAX_BASE_TR     = 2.5     # hard base TR veto x ATR
MIN_BASE        = 1
MAX_BASE        = 6
NB_TOL          = 0       # non-base tolerance inside a base run
FT_LAG          = 1       # confirmation lag (bars after leg-out before the zone exists)
FT_MAX_RESCUE   = 2       # average-leg follow-through rescue bars
TESTED_TRAVEL_ATR = 2.0   # travel (in the zone's OWN-TF ATR) to retire a reacted zone
NARROW_WICK     = True    # #34 narrow-zone wick-to-wick rescue
TOUCH_TOL       = 0.015   # "near a zone" tolerance for the location gate (1.5%, S4 parity)

# Structural (pivot-based) zones — port of Pine f_structZone (grpZP inputs).
# A pivot high → supply shelf (PvH); a pivot low → demand shelf (PvL). Weaker than a
# leg-base-leg formation (scored 40..75 so a pattern zone always wins dedup), same
# gap-bridged candles + per-TF ageing; the width FLOOR is scaled by STRUCT_MIN_W_MULT
# because a pivot shelf (body-to-extreme of one candle) is legitimately narrower.
# RETIRED as the pivot length — kept only as the fallback for an unknown TF key, so a
# caller passing something not in TF_CFG degrades to the old behaviour instead of
# raising. The live value comes from TF_CFG[tf]["piv"] (S4 v7.5 parity).
STRUCT_PV_FALLBACK = 2    # was pivotLeft=5 / pivotRight=3 applied to every TF alike
STRUCT_CLOSED_CONFIRM = True   # S4 v7.6: the bar confirming a pivot must itself be closed
RESOLVE_OPPOSING = True        # S4 v7.7: a band may not be supply and demand at once
# PIVOT-SHELF DEFINITION. "A" = body-to-extreme (Pine parity today): the shelf spans the
# whole bridged body plus the wick. "B" = rejection region only: body TOP -> high for a
# supply shelf, low -> body BOTTOM for demand. Under A the body is typically ~75% of the
# zone, and for a pivot HIGH the lower body is where price traded UP THROUGH, not where
# supply sat. A/B'd before choosing — see the session notes.
# CHOSEN: "B", measured 5-Aug-2026 across the 55-name board universe —
#   monthly median width 8.7% -> 4.9%, weekly 5.5% -> 3.9%, daily 3.6% -> 3.3%
#   zone COUNT rose (95->109 monthly): narrower shelves survive the max-width ceiling
#   that was discarding real structure for being too fat
#   at_support flips: ZERO names on any timeframe -> the location gate does not move,
#   which is the bar a geometry change has to clear before it may ship.
SHELF_MODE = "B" 
STRUCT_PAD       = 3      # structPadBars (each side of the pivot)
STRUCT_TOP_THR   = 1.5    # structTopThrATR  (body-top tolerance × ATR)
STRUCT_DEEP_THR  = 1.5    # structDeepThrATR (body-bottom tolerance × ATR)
STRUCT_MIN_MOVE  = 1.0    # pivotMinMoveATR (min move away from the pivot × ATR)
STRUCT_MIN_W_MULT = 0.5   # structMinWMult (width-band FLOOR scaler for structural only)

# ── #27 RECENCY DECAY (port of Pine f_recencyScore, v3.7) ────────────────────
# AGE and RECENCY are two different measurements: age decides when a zone is
# retired, recency says a fresher zone of equal intrinsic merit is the stronger
# one. `Zone.score` stays the INTRINSIC score (Pine's z.strength); the decayed
# read is derived, never stored — so this can lower a grade but can never
# blackout a zone. Linear to the TF's ageing cap, floored at 0.
RECENCY_DECAY    = True
RECENCY_MAX_DROP = 20     # full penalty once a zone reaches its TF ageing cap

# ── #3/#26 CONTROLLING-ZONE PROMOTION (port of Pine, v4.3 + v4.4 #2b) ────────
# A Controlling zone is the one that TURNED the market, and gets a longer leash
# (2 touches vs 1). Three criteria, OR'd — mirroring Pine lines ~1924-1944:
#   1. LEADS TO a new ATH/ATL — house rule: it must lead to one, never CONTINUE
#      one. Requires the pullback (>= CTRL_MIN_LOWER_HIGHS bars off the high
#      before the zone formed), the base sitting below the prior extreme, and the
#      leg-out closing through it.
#   2. TREND SHIFT — price was below the 50-SMA for the whole lookback and the
#      leg-out closes above it (mirrored for supply).
#   3. BREAKS AN OPPOSING controlling zone.
# TF gate (#2b): D/W/M only — an intraday-native zone is never Controlling.
# EXCLUSIVE (#2): one controlling zone per direction — the one nearest the
# ATH (demand) / ATL (supply). A newcomer supersedes the incumbent ONLY if it is
# genuinely nearer; otherwise the incumbent keeps the title.
MARK_CONTROLLING        = True
CTRL_MIN_LOWER_HIGHS    = 2      # Pine ctrlMinLowerHighs
CTRL_TRENDSHIFT_BARS    = 20     # Pine's ft+1..ft+20 below-MA lookback
CTRL_TF                 = ("D", "W", "M")
CTRL_MAX_TOUCHES        = 2      # vs 1 for an ordinary zone

# ── SPENT DEMAND STAYS VISIBLE (port of Pine v8.8 `keep_tested_demand`) ──────
# The old rule deleted a demand zone the moment it was TESTED. But the REACTION
# is the entry and the TRAVEL is the trade working, so the zone was retired
# immediately AFTER proving itself — the most evidenced level on the chart was
# the one erased, and a second approach to a proven level had nothing to trade.
# Now a spent demand zone is KEPT (z.tested = True) instead of dropped, on a
# touch budget: normal 1 test, Controlling or score >= DEMAND_STRONG_SCORE 2.
#
# The asymmetry is the whole point and is deliberate (Jay, 6-Aug-2026):
#   "A one-time tested SUPPLY zone can still act as a resistance, while a
#    tested DEMAND zone cannot serve as a location/trigger."
# So a spent demand zone stays VISIBLE (callers can still see the level and its
# geometry) but is excluded from the LOCATION gate in zone_support() — it does
# not arm a trade. Supply keeps its existing path untouched.
#
# A VIOLATED zone is still deleted at once, both directions. That is not a test,
# it is a failure — price closed through the distal.
KEEP_TESTED_DEMAND   = True
DEMAND_STRONG_SCORE  = 75     # Pine demand_strong_score — earns the 2nd test


@dataclass
class Zone:
    proximal: float
    distal: float
    is_demand: bool
    pattern: str            # RBR / DBR / RBD / DBD
    tf: str
    score: int
    n_base: int
    has_fvg: bool
    origin_idx: int         # bar index the zone was CREATED at (leg-out + FT_LAG)
    origin_ms: int          # origin timestamp (ns->ms) for calendar ageing
    tested: bool = False
    violated: bool = False
    reacted: bool = False
    react_ref: float = field(default=float("nan"))
    was_in: bool = False
    ema_pre: bool = False    # at reaction, price on the pre-cross side of EMA20 (daily rule)
    controlling: bool = False    # #3/#26 — the zone that TURNED the market
    age_ms: int = 0              # age at the last bar, set by the lifecycle pass
    cap_ms: int = 0              # this TF's ageing cap, set by the lifecycle pass

    @property
    def width(self) -> float:
        return abs(self.proximal - self.distal)

    @property
    def recency_score(self) -> int:
        """#27 — the AGE-ADJUSTED read (Pine f_recencyScore). `score` stays the
        intrinsic merit; this is what a grade/label should show. Floored at 0."""
        if not RECENCY_DECAY or self.cap_ms <= 0:
            return int(self.score)
        frac = min(max(self.age_ms, 0) / self.cap_ms, 1.0)
        return int(max(round(self.score - RECENCY_MAX_DROP * frac), 0))

    @property
    def max_touches(self) -> int:
        """Completed tests this zone survives before it is spent.

        DEMAND (Pine v8.8): Controlling **or** intrinsic score >= DEMAND_STRONG_SCORE
        earns a 2nd test; everything else is spent on the 1st. The score clause is
        demand-only — Pine gates it inside the `z.isDemand` branch, so supply keeps
        the older controlling-only rule and is not silently loosened by this port.
        Uses the INTRINSIC score, not recency_score: a zone's leash is what it was
        built with, and must not shrink just because it aged.
        """
        if self.is_demand and KEEP_TESTED_DEMAND:
            return 2 if (self.controlling or self.score >= DEMAND_STRONG_SCORE) else 1
        return CTRL_MAX_TOUCHES if self.controlling else 1


# ── helpers ──────────────────────────────────────────────────────────────────
def _wilder_atr(h, l, c, length=14):
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


def _eff(o, h, l, c):
    """Gap-bridged (invisible) candles: open re-anchored at prior close, h/l expanded."""
    inv_open = np.empty(len(c))
    inv_open[0] = o[0]
    inv_open[1:] = c[:-1]
    eo = inv_open
    ec = c
    eh = np.maximum(h, inv_open)
    el = np.minimum(l, inv_open)
    eb = np.abs(ec - eo)
    er = eh - el
    return eo, eh, el, ec, eb, er


# ── detection ────────────────────────────────────────────────────────────────
def detect_zones(df: pd.DataFrame, tf: str = "D") -> list[Zone]:
    cfg = TF_CFG.get(tf, TF_CFG["D"])
    minW, maxW, legin_atr, age_days = cfg["minW"], cfg["maxW"], cfg["legin"], cfg["age_days"]
    if df is None or len(df) < 60:
        return []
    o = df["Open"].to_numpy(float); h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float);  c = df["Close"].to_numpy(float)
    v = df["Volume"].to_numpy(float)
    n = len(c)
    eo, eh, el, ec, eb, er = _eff(o, h, l, c)
    tr, atr = _wilder_atr(eh, el, ec, 14)
    vol20 = pd.Series(v).rolling(20).mean().to_numpy()
    ema20 = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    ts_ms = (df.index.view("int64") // 1_000_000) if hasattr(df.index, "view") else np.arange(n)

    # ── #3/#26 controlling-criteria inputs (mirror Pine's ath/atl/bsATH/bsATL/ma50) ──
    # ath[i]/atl[i] = the running extreme AS OF bar i; bs_ath[i] = bars since that
    # extreme was last set (Pine's ta.barssince(ath > ath[1])) — the "has price come
    # off the high?" test that makes a zone LEAD TO a new ATH rather than continue one.
    ma50 = pd.Series(ec).rolling(50).mean().to_numpy()
    ath = np.maximum.accumulate(eh)
    atl = np.minimum.accumulate(el)
    bs_ath = np.zeros(n, dtype=int)
    bs_atl = np.zeros(n, dtype=int)
    for i in range(1, n):
        bs_ath[i] = 0 if ath[i] > ath[i - 1] else bs_ath[i - 1] + 1
        bs_atl[i] = 0 if atl[i] < atl[i - 1] else bs_atl[i - 1] + 1
    ctrl_allowed = MARK_CONTROLLING and tf in CTRL_TF   # #2b: never intraday-native

    def _is_controlling(lo_i: int, li_i: int, demand: bool) -> bool:
        """Criteria 1 (leads to a new extreme) OR 2 (50-SMA trend shift). Criterion 3
        (breaks an opposing controlling zone) needs the zone list and runs afterward."""
        if not ctrl_allowed or lo_i < 1:
            return False
        prior = ath[li_i] if demand else atl[li_i]
        if math.isnan(prior):
            return False
        if demand:
            base_no_new = ath[lo_i - 1] <= prior      # ATH did not advance during the base
            leads_to    = ec[lo_i] > prior            # leg-out closes through it
            pulled_back = bs_ath[li_i] >= CTRL_MIN_LOWER_HIGHS
        else:
            base_no_new = atl[lo_i - 1] >= prior
            leads_to    = ec[lo_i] < prior
            pulled_back = bs_atl[li_i] >= CTRL_MIN_LOWER_HIGHS
        if leads_to and base_no_new and pulled_back:
            return True
        # Criterion 2 — the whole lookback on the far side of the 50-SMA, then through it.
        s = max(lo_i - CTRL_TRENDSHIFT_BARS, 0)
        if s >= lo_i or math.isnan(ma50[lo_i]):
            return False
        seg_c, seg_m = ec[s:lo_i], ma50[s:lo_i]
        ok = ~np.isnan(seg_m)
        if not ok.any():
            return False
        if demand:
            was_far = bool((seg_c[ok] <= seg_m[ok]).all())
            return was_far and ec[lo_i] > ma50[lo_i]
        was_far = bool((seg_c[ok] >= seg_m[ok]).all())
        return was_far and ec[lo_i] < ma50[lo_i]

    zones: list[Zone] = []
    is_daily_or_lower = tf in ("D", "75m", "125m")  # EMA/level tested rule scope (#25 fix)

    # A candidate leg-out at index `lo` forms a zone that first EXISTS at lo+FT_LAG.
    for lo in range(MAX_BASE + 2, n):
        a = atr[lo]
        if math.isnan(a) or a <= 0:
            continue
        leg_big = tr[lo] > a * ERC_MULT
        if not leg_big or er[lo] <= 0:
            continue
        body_r = eb[lo] / er[lo]
        strong = body_r >= LEG_BODY_STRONG
        average = (body_r >= LEG_BODY_AVG) and not strong
        dir_bull = ec[lo] > eo[lo]
        dir_bear = ec[lo] < eo[lo]
        closes_up = ec[lo] > eh[lo] - er[lo] * 0.25
        closes_dn = ec[lo] < el[lo] + er[lo] * 0.25

        # follow-through rescue for an AVERAGE leg (needs bars AFTER lo)
        def _ft_ok(bull: bool) -> bool:
            if strong:
                return True
            if not average:
                return False
            end = min(lo + FT_MAX_RESCUE, n - 1)
            if end <= lo:
                return False
            ercH, ercL, ercC = eh[lo], el[lo], ec[lo]
            for j in range(lo + 1, end + 1):
                disp = (ec[j] - ercC) if bull else (ercC - ec[j])
                no_rev = (ec[j] >= ercL) if bull else (ec[j] <= ercH)
                prog = (ec[j] > ercC) if bull else (ec[j] < ercC)
                if disp > a * STRONG_FT and no_rev and prog:
                    return True
            return False

        for is_demand in (True, False):
            if is_demand and not (dir_bull and closes_up and (strong or (average and _ft_ok(True)))):
                continue
            if (not is_demand) and not (dir_bear and closes_dn and (strong or (average and _ft_ok(False)))):
                continue

            # base scan — going OLDER from lo-1
            zt = None            # proximal accumulator (body extreme)
            zt_wick = None       # wick extreme (for #34)
            n_base = 0
            b_start = lo - 1     # oldest base bar index
            nb_streak = 0
            i2 = lo - 1
            while i2 >= 1 and n_base < MAX_BASE + 1:
                cr, cb = er[i2], eb[i2]
                small_body = cr > 0 and (cb / cr) <= BODY_RATIO
                small_rng = tr[i2] < atr[i2] * BASE_RNG_ATR
                is_base = (small_body or small_rng) and tr[i2] < atr[i2] * MAX_BASE_TR
                if is_base:
                    nb_streak = 0
                    n_base += 1
                    b_start = i2
                    if is_demand:
                        pv = max(ec[i2], eo[i2])
                        zt = pv if zt is None else max(zt, pv)
                        zt_wick = eh[i2] if zt_wick is None else max(zt_wick, eh[i2])
                    else:
                        pv = min(ec[i2], eo[i2])
                        zt = pv if zt is None else min(zt, pv)
                        zt_wick = el[i2] if zt_wick is None else min(zt_wick, el[i2])
                else:
                    nb_streak += 1
                    if nb_streak > NB_TOL:
                        break
                i2 -= 1
            if not (MIN_BASE <= n_base <= MAX_BASE) or zt is None:
                continue

            li = b_start - 1     # leg-in = one older than the oldest base bar
            if li < 0:
                continue
            li_rng, li_body = er[li], eb[li]
            li_uw = eh[li] - max(ec[li], eo[li])
            li_lw = min(ec[li], eo[li]) - el[li]
            li_maxw = max(li_uw, li_lw)
            legin_wick_ok = li_body > 0 and li_maxw <= li_body * LEGIN_MAX_WICK
            legin_valid = (li_rng > 0 and (li_body / li_rng) >= LEG_BODY_AVG
                           and tr[li] > atr[li] * legin_atr and legin_wick_ok)
            if not legin_valid:
                continue
            li_bull = ec[li] > eo[li]

            if is_demand:
                pattern = "RBR" if li_bull else "DBR"
                # distal = min wick low over the pattern-aware range
                dist_to = li if pattern == "DBR" else b_start
                zb = min(el[k] for k in range(dist_to, lo + 1))
                if NARROW_WICK and zt_wick is not None and (zt - zb) < a * minW:
                    zt = max(zt, zt_wick)          # #34 widen proximal to the base wick
                proximal, distal = zt, zb
            else:
                pattern = "RBD" if li_bull else "DBD"
                dist_from = lo
                dist_to = li if pattern == "RBD" else b_start
                zt2 = max(eh[k] for k in range(dist_to, lo + 1))
                zb2 = zt                            # proximal (body min) for supply
                if NARROW_WICK and zt_wick is not None and (zt2 - zb2) < a * minW:
                    zb2 = min(zb2, zt_wick)
                proximal, distal = zb2, zt2

            w = abs(proximal - distal)
            if not (a * minW <= w <= a * maxW):
                continue

            # FVG (raw prices — the gap-bridge erases the very imbalance)
            has_fvg = (lo >= 1 and lo + 1 < n and
                       (l[lo - 1] > h[lo + 1] if is_demand else h[lo - 1] < l[lo + 1]))
            # score: leg-out body (0-40) + volume surge floored (0-30) + base (0-25) + gap/fvg
            ep = int(min(body_r * 40.0, 40.0))
            vr = v[lo] / vol20[lo] if (not math.isnan(vol20[lo]) and vol20[lo] > 0) else 1.0
            vp = int(min(max((vr - 1.0) * 12.0, 0.0), 30.0))
            bp = {1: 12, 2: 25, 3: 25, 4: 20, 5: 10}.get(n_base, 5)
            raw = min(ep + vp + bp, 95)
            gap_pts = 10 if (is_demand and o[lo] - c[lo - 1] > a * 0.3) else 0
            fvg_pts = 15 if has_fvg else 0
            score = min(raw + gap_pts + fvg_pts, 100)

            origin = min(lo + FT_LAG, n - 1)
            zones.append(Zone(proximal=proximal, distal=distal, is_demand=is_demand,
                              pattern=pattern, tf=tf, score=score, n_base=n_base,
                              has_fvg=has_fvg, origin_idx=origin, origin_ms=int(ts_ms[origin]),
                              controlling=_is_controlling(lo, li, is_demand)))

    # ── structural (pivot-based) zones — port of Pine f_structZone ──
    # Emit a shelf at each confirmed pivot; append into the SAME `zones` list so the
    # lifecycle/ageing below treats them identically to pattern zones.
    # Left = right, per TF (S4 v7.5 pivNative / piv_d / piv_w / piv_m).
    _pv = int((TF_CFG.get(tf) or {}).get("piv", STRUCT_PV_FALLBACK))
    # PER-TF PAD + BODY TOLERANCE (5-Aug-2026). These decide how far a pivot shelf
    # reaches into its NEIGHBOURS' bodies, and a single global pair was the root cause of
    # the POLYCAB monthly zones: at 1.5 x a ~1400-point monthly ATR the tolerance is
    # ~2100 points, so the June supply shelf swallowed July's close and became 11% wide.
    # ATR scales with the timeframe, so a fixed multiple of it does not.
    _cfg = TF_CFG.get(tf) or {}
    pvL, pvR, pad = _pv, _pv, int(_cfg.get("pad", STRUCT_PAD))
    _thr = float(_cfg.get("thr", STRUCT_TOP_THR))
    # CLOSED-CONFIRMATION (S4 v7.6 struct_closed_confirm parity) — BUT ONLY WHERE THE
    # LAST ROW CAN STILL BE TRADING. Pine needs this on every TF because
    # request.security includes the forming HTF bar. Python does not: both W and M
    # frames reach this function through pa_patterns._confirmed_weekly_ohlcv /
    # _confirmed_month_ohlcv, which have ALREADY dropped the in-progress period. Applying
    # the withhold there too would delay every weekly zone by a week and every monthly
    # zone by a MONTH for no protection — measured on POLYCAB, it withheld the 9106.5
    # shelf whose confirming bar (July) was long closed.
    # So: withhold on the raw frames (intraday and D, which fetch_ohlcv returns with
    # today's incomplete bar attached), skip on the pre-confirmed W/M frames.
    _raw_last_bar = tf not in ("W", "M")
    _last_ok = n - pvR - (1 if (STRUCT_CLOSED_CONFIRM and _raw_last_bar) else 0)
    for i in range(pvL, max(pvL, _last_ok)):
        a = atr[i]
        if math.isnan(a) or a <= 0:
            continue
        hi_i, lo_i = eh[i], el[i]
        is_ph = all(hi_i > eh[i - k] for k in range(1, pvL + 1)) and all(hi_i >= eh[i + k] for k in range(1, pvR + 1))
        is_pl = all(lo_i < el[i - k] for k in range(1, pvL + 1)) and all(lo_i <= el[i + k] for k in range(1, pvR + 1))
        origin = min(i + pvR, n - 1)
        klo, khi = max(i - pad, 0), min(i + pad, n - 1)
        if is_ph:                                        # pivot high → structural SUPPLY (PvH)
            sTop = eh[i]
            sBot = max(ec[i], eo[i]) if SHELF_MODE == "B" else min(ec[i], eo[i])
            for k in range(klo, khi + 1):
                bhi, blo = max(ec[k], eo[k]), min(ec[k], eo[k])
                if bhi >= sTop - a * _thr and blo >= sTop - a * _thr and blo < sBot:
                    sBot = blo
            wH = sTop - sBot
            low_since = float(el[i:origin + 1].min())
            if (sTop - low_since) > a * STRUCT_MIN_MOVE and a * minW * STRUCT_MIN_W_MULT <= wH <= a * maxW:
                sc = min(40 + int((sTop - low_since) / a * 5.0), 75)
                zones.append(Zone(proximal=sBot, distal=sTop, is_demand=False, pattern="PvH",
                                  tf=tf, score=sc, n_base=0, has_fvg=False,
                                  origin_idx=origin, origin_ms=int(ts_ms[origin])))
        if is_pl:                                        # pivot low → structural DEMAND (PvL)
            dBot = el[i]
            dTop = min(ec[i], eo[i]) if SHELF_MODE == "B" else max(ec[i], eo[i])
            for k in range(klo, khi + 1):
                bhi, blo = max(ec[k], eo[k]), min(ec[k], eo[k])
                if blo <= dBot + a * _thr and bhi <= dBot + a * _thr and bhi > dTop:
                    dTop = bhi
            wL = dTop - dBot
            high_since = float(eh[i:origin + 1].max())
            if (high_since - dBot) > a * STRUCT_MIN_MOVE and a * minW * STRUCT_MIN_W_MULT <= wL <= a * maxW:
                sc = min(40 + int((high_since - dBot) / a * 5.0), 75)
                zones.append(Zone(proximal=dTop, distal=dBot, is_demand=True, pattern="PvL",
                                  tf=tf, score=sc, n_base=0, has_fvg=False,
                                  origin_idx=origin, origin_ms=int(ts_ms[origin])))

    # ── #3/#26 controlling pass: criterion 3 + EXCLUSIVITY, in FORMATION order ──
    # Pine resolves these at insertion time against the live activeZones array, so the
    # order is chronological — reproduced here by walking zones by origin_idx. Criterion
    # 3 (breaks an opposing controlling zone) can only be judged against the incumbents
    # that already existed, which is why it cannot live in the detection loop above.
    if ctrl_allowed and zones:
        live_ctrl: list[Zone] = []            # incumbents, in formation order
        for z in sorted(zones, key=lambda q: (q.origin_idx, q.proximal)):
            breaks_opposing = any(
                (z.proximal > zo.distal) if z.is_demand else (z.proximal < zo.distal)
                for zo in live_ctrl if zo.is_demand != z.is_demand
            )
            final_ctrl = z.controlling or breaks_opposing
            if not final_ctrl:
                continue
            # EXCLUSIVE: supersede a same-direction incumbent ONLY if genuinely nearer
            # the extreme (demand → higher proximal; supply → lower). Otherwise the
            # incumbent keeps the title and the newcomer stays ordinary.
            same = [zo for zo in live_ctrl if zo.is_demand == z.is_demand]
            nearer = all((z.proximal > zo.proximal) if z.is_demand else (z.proximal < zo.proximal)
                         for zo in same)
            if not nearer:
                z.controlling = False
                continue
            for zo in same:
                zo.controlling = False
                live_ctrl.remove(zo)
            z.controlling = True
            live_ctrl.append(z)

    # ── lifecycle: run each zone forward from its origin to the last bar ──
    last_ms = int(ts_ms[-1])
    cap_ms = age_days * 86_400_000
    atrD = atr  # own-TF ATR (this df IS the zone's TF)
    alive: list[Zone] = []
    for z in zones:
        if last_ms - z.origin_ms > cap_ms:
            continue                                    # aged out
        # #27: stamp the inputs recency_score derives from (never the decayed value —
        # `score` must stay the intrinsic merit so the decay can't compound on re-read).
        z.age_ms, z.cap_ms = last_ms - z.origin_ms, cap_ms
        was_in = False
        reacted = False
        react_ref = float("nan")
        ema_pre = False
        killed = False
        spent = False
        touch_n = 0
        for i in range(z.origin_idx + 1, n):
            if z.is_demand:
                touched = l[i] <= z.proximal and c[i] >= z.distal
                moved_out = l[i] > z.proximal
            else:
                touched = h[i] >= z.proximal and c[i] <= z.distal
                moved_out = h[i] < z.proximal
            if was_in and moved_out and i > z.origin_idx + 1:
                reacted = True
                react_ref = z.proximal
                ema_pre = (c[i] < ema20[i]) if z.is_demand else (c[i] > ema20[i])
            was_in = touched
            if reacted:
                need = TESTED_TRAVEL_ATR * (atrD[i] if not math.isnan(atrD[i]) else 0.0)
                c_travel = (h[i] >= react_ref + need) if z.is_demand else (l[i] <= react_ref - need)
                c_ema = False
                if is_daily_or_lower and tf == "D":     # EMA cross retires DAILY zones only (#25 fix)
                    c_ema = ema_pre and ((c[i] > ema20[i]) if z.is_demand else (c[i] < ema20[i]))
                if c_travel or c_ema:
                    # Below the budget the zone survives and is re-armed for another
                    # reaction cycle. AT the budget it is SPENT — and what that means
                    # now differs by direction (Pine v8.8): a demand zone is kept and
                    # flagged tested (visible, but no longer a location — see
                    # zone_support), while supply retires as before.
                    touch_n += 1
                    if touch_n >= z.max_touches:
                        if KEEP_TESTED_DEMAND and z.is_demand:
                            spent = True                 # keep it, stop scanning it
                        else:
                            killed = True                # TESTED -> removed
                        break
                    reacted, react_ref, ema_pre = False, float("nan"), False
            # violation: close beyond the distal
            if (c[i] < z.distal) if z.is_demand else (c[i] > z.distal):
                killed = True
                break
        if killed:
            continue
        z.was_in = was_in
        z.reacted = reacted
        # A spent demand zone stays in the list — deliberately. Callers still want to
        # SEE the level; only the location gate stops honouring it.
        if spent:
            z.tested = True
        alive.append(z)

    # de-dup: pattern zones win over structural on overlap (Pine skips a pivot shelf that
    # duplicates a pattern zone), then higher score. Same-direction overlap only.
    # Ordering deliberately does NOT prefer a controlling zone. Pine dedups at insertion,
    # BEFORE the promotion is finalised, so promoting here would be a Python-only rule —
    # and measured on the 43-name board universe it flipped the location gate on NYKAA
    # (a controlling PvL winning an overlap the old ordering dropped). A scoring feature
    # must not move a boolean gate; parity with Pine and gate-neutrality agree here.
    alive.sort(key=lambda z: (z.pattern in ("PvH", "PvL"), -z.score))
    kept: list[Zone] = []
    for z in alive:
        dup = False
        for k in kept:
            if k.is_demand == z.is_demand:
                if max(z.proximal, z.distal) >= min(k.proximal, k.distal) and \
                   min(z.proximal, z.distal) <= max(k.proximal, k.distal):
                    dup = True
                    break
        if not dup:
            kept.append(z)

    # ── opposing-overlap resolution (S4 v7.7 resolveOpposing parity) ──
    # A band cannot be supply AND demand. Measured on POLYCAB monthly: SZ 9106.5-10126
    # and DZ 8791-9961 overlapped by 855 pts with spot inside BOTH, so the board could
    # report "at support" on prices the chart called supply — the drift class this whole
    # session has been closing. Newer zone wins the contested band; the older opposing
    # one is trimmed back to its edge. Everything here is ONE timeframe already (the
    # caller passes a single-TF frame), so the Pine same-TF restriction is implicit.
    # Fully engulfed → marked tested (kept, excluded downstream), never dropped.
    # proximal is the APPROACH edge: upper for demand, lower for supply — same as Pine.
    if RESOLVE_OPPOSING and len(kept) > 1:
        for _new in sorted(kept, key=lambda z: z.origin_idx):
            n_hi = max(_new.proximal, _new.distal)
            n_lo = min(_new.proximal, _new.distal)
            for _old in kept:
                if _old is _new or _old.is_demand == _new.is_demand or _old.tested:
                    continue
                if _old.origin_idx >= _new.origin_idx:
                    continue                            # only trim what came BEFORE
                o_hi = max(_old.proximal, _old.distal)
                o_lo = min(_old.proximal, _old.distal)
                if not (n_hi > o_lo and n_lo < o_hi):
                    continue                            # no overlap
                if _new.is_demand:                      # new demand below → raise supply floor
                    if o_hi - max(o_lo, n_hi) > 0:
                        _old.proximal = max(o_lo, n_hi)
                    else:
                        _old.tested = True
                else:                                   # new supply above → lower demand ceiling
                    if min(o_hi, n_lo) - o_lo > 0:
                        _old.proximal = min(o_hi, n_lo)
                    else:
                        _old.tested = True
    return kept


TF_RANK = {"75m": 0, "125m": 0, "25m": 0,
           "D": 1, "Daily": 1, "W": 2, "Weekly": 2, "M": 3, "Monthly": 3}


def htf_nesting(supports: dict, chart_tf: str = "D") -> dict:
    """How far ABOVE the chart is the highest timeframe that also holds price in a
    demand zone? A 75m zone sheltered by a monthly zone is a different proposition
    from one sheltered by a daily zone, and a flat "2+ timeframes overlap" count
    throws that away.

    `supports` maps a TF key ("D"/"W"/"M"/native) to a zone_support() result. Only
    at_support entries count, and only for a TF strictly ABOVE the chart's own — a
    zone on the chart's timeframe is NATIVE, not nesting.

    Mirrors S4 v9.0's `_htfNest`. Returns rank 0-3 (M 3 · W 2 · D 1) + a label.

    SCOPE, deliberately: this is a GRADING signal. It is not written back into
    Zone.score, so it cannot reach max_touches and cannot buy a nested zone the
    second test the v8.8 budget grants at score >= 75 (Jay, 7-Aug). Grading and
    lifecycle stay separate.
    """
    base = TF_RANK.get(str(chart_tf), 0)
    best, best_tf = 0, None
    for tf, sup in (supports or {}).items():
        # Accepts a full zone_support() result OR a plain bool — the board carries
        # the flags forward from gm_load_symbol, which cannot resolve the rank.
        at = bool(sup.get("at_support")) if isinstance(sup, dict) else bool(sup)
        if not at:
            continue
        r = TF_RANK.get(str(tf), 0)
        if r > base and r > best:
            best, best_tf = r, str(tf)
    return {"htf_rank": best, "htf_tf": best_tf,
            "htf_label": ("" if not best else f"nested {best_tf}")}


def zone_support(df: pd.DataFrame, tf: str = "D", price: float | None = None) -> dict:
    """The GM LOCATION half, mirroring S4's z_inDZ: is `price` inside/near a FRESH
    demand zone drawn by the IZE engine on this TF? Returns the gate + the zone."""
    out = {"at_support": False, "in_fresh_dz": False, "zone": None,
           "proximal": None, "distal": None, "score": None, "has_fvg": False, "n_dz": 0, "n_sz": 0,
           # #27 / #3: the age-adjusted read and the Controlling flag. `score` stays the
           # INTRINSIC merit so nothing downstream that already reads it changes meaning.
           "recency_score": None, "controlling": False, "n_ctrl": 0,
           "n_dz_spent": 0}
    zones = detect_zones(df, tf)
    if not zones:
        return out
    px = float(price) if price is not None else float(df["Close"].iloc[-1])
    dz = [z for z in zones if z.is_demand]
    sz = [z for z in zones if not z.is_demand]
    out["n_dz"], out["n_sz"] = len(dz), len(sz)
    out["n_ctrl"] = sum(1 for z in zones if z.controlling)
    best = None
    # SPENT demand is excluded from the gate but NOT from the list or the counts —
    # the level is still on the chart, it just no longer arms a trade. This also
    # closes a pre-existing gap: zones marked tested by the overlap-resolution pass
    # were already being counted as fresh support, against this function's own
    # docstring.
    out["n_dz_spent"] = sum(1 for z in dz if z.tested)
    for z in dz:
        if z.tested:
            continue
        inside = z.distal <= px <= z.proximal
        near = px > z.proximal and (px - z.proximal) / z.proximal <= TOUCH_TOL
        if inside or near:
            # Prefer a CONTROLLING zone, then score — the promotion is the whole point
            # of porting it, so it has to win the "which zone am I at" choice too.
            if best is None or (z.controlling, z.score) > (best.controlling, best.score):
                best = z
                out["at_support"] = True
                out["in_fresh_dz"] = bool(inside)
    if best is not None:
        out.update(zone=best.pattern, proximal=best.proximal, distal=best.distal,
                   score=best.score, has_fvg=best.has_fvg,
                   recency_score=best.recency_score, controlling=bool(best.controlling))
    return out


# ── S/R HORIZONTAL LEVELS (port of S4 Pine f_srLevels) ───────────────────────
# The other half of S4's location gate (near_sr). A LEVEL is price memory (unlike
# a zone, which is fuel): it survives a test but WEAKENS. Ports:
#   * cluster confirmed pivots into persistent level objects (running-mean price,
#     CUMULATIVE touch count that never decays)
#   * #30 WICK-PIERCE touches — a pivot counts when the level line threads its wick
#     (upper wick of a high / lower wick of a low), not only its extreme; a pierce
#     is counted but does NOT drag the level's price
#   * MTTWR grade — the house inversion: 1..min_touch = FRESH, up to n-1 = TESTED,
#     >= mttwr = MTTWR (primed to break, EXCLUDED from support)
#   * role derived from price (R<->S flip), min-space (distinct tests), pool cap
# NOTE levels use RAW prices/ATR (not the gap-bridged candles the zones use).
# mttwr_n raised 4 -> 6 (18-Jul) to mirror the S4 Pine: measured on live data a 40-pivot
# pool graded 40-45% of ALL levels MTTWR, so the nearest support was almost always
# excluded and near_sr never fired — the location gate silently lost a source.
SR_DEFAULTS = dict(pvL=5, pvR=5, pool=40, tol_atr=0.6, min_space=5,
                   min_touch=2, mttwr_n=6, wick_touch=True, wick_fit=True)


def detect_sr_levels(df: pd.DataFrame, tf: str = "D", **kw) -> list[dict]:
    """Return graded horizontal S/R levels: {price, touches, from_high, grade, role}.
    grade ∈ FRESH/TESTED/MTTWR · role ∈ SUPPORT/RESISTANCE (from the last close)."""
    p = {**SR_DEFAULTS, **kw}
    pvL, pvR, pool = p["pvL"], p["pvR"], p["pool"]
    tol_atr, min_space = p["tol_atr"], p["min_space"]
    min_touch, mttwr_n, wick = p["min_touch"], p["mttwr_n"], p["wick_touch"]
    wick_fit = p.get("wick_fit", True)
    if df is None or len(df) < (pvL + pvR + 5):
        return []
    o = df["Open"].to_numpy(float); h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float);  c = df["Close"].to_numpy(float)
    n = len(c)
    _, atr = _wilder_atr(h, l, c, 14)
    mttwr_eff = max(mttwr_n, min_touch + 1)
    # price · touches · first-bar · from-high · last-bar · wick-band intersection lo/hi (#8)
    Lp, Lc, Lt, Lh, Lb, Lil, Lih = [], [], [], [], [], [], []

    def _merge(val, wk_bound, is_high, bar):
        a = atr[bar] if bar < n and not math.isnan(atr[bar]) else 0.0
        tol = tol_atr * a
        if tol <= 0:
            return
        band_lo, band_hi = min(val, wk_bound), max(val, wk_bound)   # this pivot's wick band
        j, bd, pierce_only = -1, 1e18, False
        for i2 in range(len(Lp)):
            lp = Lp[i2]; d = abs(lp - val)
            near = d <= tol
            prc = wick and ((lp <= val and lp >= wk_bound) if is_high else (lp >= val and lp <= wk_bound))
            if (near or prc) and d < bd:
                bd, j, pierce_only = d, i2, (prc and not near)
        if j >= 0:
            if bar - Lb[j] >= min_space:
                cnt = Lc[j] + 1
                # #8 wick-fit (Pine sr_wick_fit): place the line at the midpoint of the
                # INTERSECTION of member wick bands — the price that threads every member
                # wick. When the new band still intersects, shrink+re-centre; when it does
                # NOT, the touch still counts but the line STAYS PUT (never mean-drifts).
                # Mean-drag only when wick_fit is OFF (and not a pierce-only touch).
                _nl, _nh = max(Lil[j], band_lo), min(Lih[j], band_hi)
                if wick_fit and _nl <= _nh:
                    Lil[j], Lih[j] = _nl, _nh
                    Lp[j] = (_nl + _nh) / 2.0
                elif (not wick_fit) and not pierce_only:   # a wick-pierce does NOT drag the price
                    Lp[j] = (Lp[j] * (cnt - 1) + val) / cnt
                Lc[j] = cnt; Lb[j] = bar
        else:
            Lp.append(val); Lc.append(1); Lt.append(bar); Lh.append(is_high); Lb.append(bar)
            Lil.append(band_lo); Lih.append(band_hi)
            while len(Lp) > pool:                          # evict the oldest first-touch
                old = min(range(len(Lp)), key=lambda k: Lt[k])
                for arr in (Lp, Lc, Lt, Lh, Lb, Lil, Lih):
                    arr.pop(old)

    for b in range(pvL, n - pvR):                          # confirmed pivots
        hi, lo = h[b], l[b]
        is_ph = all(hi > h[b - k] for k in range(1, pvL + 1)) and all(hi >= h[b + k] for k in range(1, pvR + 1))
        is_pl = all(lo < l[b - k] for k in range(1, pvL + 1)) and all(lo <= l[b + k] for k in range(1, pvR + 1))
        if is_ph:
            _merge(hi, (max(o[b], c[b]) if wick else hi), True, b)
        if is_pl:
            _merge(lo, (min(o[b], c[b]) if wick else lo), False, b)

    px = c[-1]
    out = []
    for i in range(len(Lp)):
        t = Lc[i]
        if t < min_touch:            # Pine f_srLevels line 1456: `if c >= minTouch` — a single
            continue                 # pivot is a SWING POINT, not a level; emit only proven levels
        grade = "FRESH" if t <= min_touch else ("MTTWR" if t >= mttwr_eff else "TESTED")
        out.append(dict(price=Lp[i], touches=t, from_high=Lh[i], grade=grade,
                        role=("RESISTANCE" if Lp[i] > px else "SUPPORT")))
    return out


def sr_support(df: pd.DataFrame, tf: str = "D", price: float | None = None) -> dict:
    """S4 `near_sr` mirror: is `price` within 1.5% ABOVE a non-MTTWR SUPPORT level?
    (Leaning a stop on an MTTWR level — primed to break — is the mistake the grade
    exists to prevent, so MTTWR is excluded, exactly like S4.)"""
    out = {"near_sr": False, "level": None, "grade": None, "n_levels": 0}
    levels = detect_sr_levels(df, tf)
    if not levels:
        return out
    out["n_levels"] = len(levels)
    px = float(price) if price is not None else float(df["Close"].iloc[-1])
    best = None
    for L in levels:
        if L["role"] == "SUPPORT" and L["grade"] != "MTTWR" and L["price"] <= px:
            if (px - L["price"]) / px <= TOUCH_TOL:
                if best is None or L["price"] > best["price"]:   # nearest below
                    best = L
    if best is not None:
        out.update(near_sr=True, level=best["price"], grade=best["grade"])
    return out


# ── ANCHORED VWAPs (port of S4 Pine f_anchors + f_avwap + near_avwap) ─────────
# Three price-memory anchors: Low (most recent N-day low / Stage-1 bottom), BO
# (close crossing the prior N-bar high), Gap (last gap-up >= gap_pct on volume).
# AVWAP = cumsum(hlc3 * volume) / cumsum(volume) from the anchor bar. near_avwap =
# price within 1.5% ABOVE the nearest AVWAP below it (an AVWAP acting as support).
AVWAP_DEFAULTS = dict(low_look=252, bo_look=40, gap_pct=3.0, gap_volx=1.5, tol=0.015)


def avwap_support(df: pd.DataFrame, price: float | None = None, **kw) -> dict:
    """S4 `near_avwap` mirror. Returns {near_avwap, nearest, avwaps:{low/bo/gap}}."""
    p = {**AVWAP_DEFAULTS, **kw}
    low_look, bo_look = p["low_look"], p["bo_look"]
    gap_pct, gap_volx, tol = p["gap_pct"], p["gap_volx"], p["tol"]
    out = {"near_avwap": False, "nearest": None, "avwaps": {}}
    if df is None or len(df) < 60:
        return out
    o = df["Open"].to_numpy(float); h = df["High"].to_numpy(float)
    l = df["Low"].to_numpy(float);  c = df["Close"].to_numpy(float)
    v = df["Volume"].to_numpy(float)
    n = len(c)
    px = float(price) if price is not None else float(c[-1])
    hlc3 = (h + l + c) / 3.0
    prev_c = np.concatenate(([np.nan], c[:-1]))
    anchors = {}
    # Low anchor — most recent bar whose low is the trailing-low_look minimum.
    rmin = pd.Series(l).rolling(low_look, min_periods=1).min().to_numpy()
    idx = np.where(l <= rmin + 1e-9)[0]
    if len(idx):
        anchors["low"] = int(idx[-1])
    # BO anchor — close crosses over the prior bo_look-bar high.
    lvl = pd.Series(h).rolling(bo_look).max().shift(1).to_numpy()
    prev_lvl = np.concatenate(([np.nan], lvl[:-1]))
    cross = (c > lvl) & (prev_c <= prev_lvl) & ~np.isnan(lvl) & ~np.isnan(prev_lvl)
    idx = np.where(cross)[0]
    if len(idx):
        anchors["bo"] = int(idx[-1])
    # Gap anchor — open gaps up >= gap_pct over prior close, on >= gap_volx x 50-avg vol.
    vol50 = pd.Series(v).rolling(50).mean().to_numpy()
    gap = (o > prev_c * (1.0 + gap_pct / 100.0)) & (v > vol50 * gap_volx) & ~np.isnan(vol50) & ~np.isnan(prev_c)
    idx = np.where(gap)[0]
    if len(idx):
        anchors["gap"] = int(idx[-1])

    below = []
    for name, a in anchors.items():
        cv = v[a:].sum()
        av = float((hlc3[a:] * v[a:]).sum() / cv) if cv > 0 else float("nan")
        out["avwaps"][name] = av
        if not math.isnan(av) and av <= px:
            below.append(av)
    if below:
        nearest = max(below)                       # nearest AVWAP below price
        out["nearest"] = nearest
        out["near_avwap"] = bool((px - nearest) / px <= tol)
    return out


# ── VOLUME PROFILE SUPPORT (port of S4 v5.0 Pine VP support gate) ────────────
def vp_support(df: pd.DataFrame, price: float | None = None) -> dict:
    """Volume Profile (POC / VAH / VAL) support gate check mirroring S4 v5.0 Pine.
    Price near VAL (within 1.5%) or near POC (within 1.5%) turns support_pass = True.
    """
    out = {"near_vp_val": False, "near_vp_poc": False, "at_vp_support": False,
           "vp_val": None, "vp_poc": None, "vp_vah": None, "vp_pos": "—"}
    if df is None or len(df) < 40:
        return out
    px = float(price) if price is not None else float(df["Close"].iloc[-1])
    win = df.iloc[-120:] if len(df) >= 120 else df
    tp = (win["High"] + win["Low"] + win["Close"]) / 3.0
    vol = win["Volume"]
    lo_p, hi_p = float(win["Low"].min()), float(win["High"].max())
    nb = 40
    if hi_p > lo_p:
        edges = np.linspace(lo_p, hi_p, nb + 1)
        bidx = np.clip(np.digitize(tp, edges) - 1, 0, nb - 1)
        prof = np.zeros(nb)
        for bi, vv in zip(bidx, vol):
            prof[bi] += vv
        pb = int(prof.argmax())
        poc = float((edges[pb] + edges[pb + 1]) / 2.0)
        tgt = float(prof.sum() * 0.70)
        lo_b, hi_b = pb, pb
        acc_v = float(prof[pb])
        while acc_v < tgt and (lo_b > 0 or hi_b < nb - 1):
            lft = float(prof[lo_b - 1]) if lo_b > 0 else -1.0
            rgt = float(prof[hi_b + 1]) if hi_b < nb - 1 else -1.0
            if rgt >= lft:
                hi_b += 1
                acc_v += float(prof[hi_b])
            else:
                lo_b -= 1
                acc_v += float(prof[lo_b])
        val_lo = float((edges[lo_b] + edges[lo_b + 1]) / 2.0)
        vah_hi = float((edges[hi_b] + edges[hi_b + 1]) / 2.0)
        
        near_val = px >= val_lo and (px - val_lo) / px <= 0.015
        near_poc = px >= poc and abs(px - poc) / px <= 0.015
        
        pos = "ABOVE VAH" if px > vah_hi else ("IN VA (upper)" if px > poc else ("IN VA (lower)" if px >= val_lo else "BELOW VAL"))
        
        out.update({
            "near_vp_val": near_val,
            "near_vp_poc": near_poc,
            "at_vp_support": near_val or near_poc,
            "vp_val": val_lo,
            "vp_poc": poc,
            "vp_vah": vah_hi,
            "vp_pos": pos
        })
    return out
