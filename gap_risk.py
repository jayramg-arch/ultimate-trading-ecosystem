"""gap_risk.py - size on the gap, not on the stop (28-Oct-2026).

Jay: "almost all of my recent stop losses were news based" - AUBANK opened 8% lower on a news
event and went straight through its stop. A resting stop protects you from a slide, never from
a gap: on a gap the order fills at the OPEN, wherever that is. So the real worst case of a
holding is not (entry - stop) x qty but (entry - min(stop, gap open)) x qty.

This module measures each stock's own overnight gaps - open / previous close - over the last
two years of daily bars, and turns the tail into a fill price:

  gap_p95 / gap_p99   the 5% and 1% worst gap-downs (negative %), from that stock's history
  gap_worst           the single worst gap in the window, and its date
  gap_fill            min(Dhan stop, LTP x (1 + gap)): where that gap would fill you. Above the
                      stop = the stop still holds on that gap; below = it goes through
  gap_loss            qty x (avg - gap_fill): what that gap costs the position, from cost
  gap_fit_qty         shares whose gap_loss stays inside the per-trade rule

WHICH GAP (measured on the live book, 28-Oct-2026): the 1-in-100 gap was -1.6% to -3.8% on all
15 holdings and sat INSIDE every Dhan stop, while the news days that actually took stops out
(AUBANK -8%) are the tail; the 2-year worst gaps ran -4.9% to -19.7%. So the SL Dashboard sizes
on the stress case - the stock's worst gap of the last two years, repeated from today's price -
and shows p95/p99 beside it for reference.

The point it makes: widening a stop does nothing against a gap; only fewer shares does. When
gap_fill sits below the stop, the stop's distance is not the risk - the gap is.

Notes: daily bars from data_provider (Dhan, split/bonus-adjusted). A gap on a day of a corporate
action that the adjustment missed would show as an outlier; the worst gap carries its date so it
can be checked. p99 over ~500 sessions is the 5th-worst gap - stable enough to size on, not a
forecast. Display only: nothing here sizes an order.
"""
from __future__ import annotations

import math

import pandas as pd

LOOKBACK_BARS = 500        # about two years of sessions


def gap_stats(df: pd.DataFrame, lookback: int = LOOKBACK_BARS) -> dict:
    """{'n','gap_p95','gap_p99','gap_worst','gap_worst_date','gaps_3pct'} in % (negative = down).
    Empty dict when there are too few bars."""
    if df is None or getattr(df, "empty", True) or not {"Open", "Close"} <= set(df.columns):
        return {}
    d = df[["Open", "Close"]].dropna().tail(lookback + 1)
    if len(d) < 60:
        return {}
    gap = (d["Open"] / d["Close"].shift(1) - 1.0).dropna() * 100.0
    gap = gap[gap.abs() < 40]          # a > 40% open-to-close jump is a data fault, not a gap
    if len(gap) < 60:
        return {}
    w = gap.idxmin()
    return {"n": int(len(gap)),
            "gap_p95": float(gap.quantile(0.05)),
            "gap_p99": float(gap.quantile(0.01)),
            "gap_worst": float(gap.min()),
            "gap_worst_date": pd.Timestamp(w).strftime("%Y-%m-%d"),
            "gaps_3pct": int((gap <= -3.0).sum())}


def gap_fill(ltp, stop, gap_pct):
    """Fill price if a gap of gap_pct (negative %) opens from LTP: the stop when the gap opens
    above it, the open when it opens below it. None without an LTP or a gap figure."""
    try:
        ltp, g = float(ltp), float(gap_pct)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(ltp) and math.isfinite(g)) or ltp <= 0:
        return None
    open_px = ltp * (1.0 + g / 100.0)
    try:
        st = float(stop)
    except (TypeError, ValueError):
        st = 0.0
    if not (st > 0) or st >= ltp:
        # no stop below price (none, or trailed above LTP and already through): the gap open is the fill
        return open_px if not (st > 0) else min(st, open_px)
    return min(st, open_px)


def gap_numbers(qty, avg, ltp, stop, gap_pct, budget):
    """(fill, loss from cost at that fill, shares that fit the rule at that fill, gap goes through
    the stop?). loss <= 0 = even that gap leaves a profit."""
    fill = gap_fill(ltp, stop, gap_pct)
    if fill is None or not qty or not avg:
        return None, None, None, False
    loss = float(qty) * (float(avg) - fill)
    fit = int(budget // (float(avg) - fill)) if (budget and float(avg) > fill) else None
    through = bool(stop and float(stop) > 0 and fill < float(stop) - 1e-9)
    return fill, loss, fit, through


# ── 29-Oct-2026: the two sizing questions the SL Dashboard, the guard and the Risk
# Allocator v2.8 all ask, in one place so the Pine mirror has a single Python twin ────────

def entry_qty(entry, stop, gap_pct, budget, cap_rupees=None):
    """Initial position size with the gap factored in (Risk Allocator v2.8 mirror).

    A resting stop caps a slide, never a gap: on a gap the order fills at the open. So the
    loss per share on a fresh entry is the LARGER of the stop distance and the stock's worst
    gap measured from the entry price:
        per_share = max(entry - stop, entry x |gap|)
    Returns {'qty', 'qty_stop', 'qty_gap', 'qty_cap', 'per_share', 'binding'} - binding is
    'stop', 'gap' or 'cap'. qty_gap is None when there is no gap figure."""
    try:
        entry, stop, budget = float(entry), float(stop), float(budget)
    except (TypeError, ValueError):
        return {"qty": 0, "qty_stop": 0, "qty_gap": None, "qty_cap": None, "per_share": None, "binding": ""}
    dist = entry - stop
    if not (entry > 0 and dist > 0 and budget > 0):
        return {"qty": 0, "qty_stop": 0, "qty_gap": None, "qty_cap": None, "per_share": None, "binding": ""}
    q_stop = int(budget // dist)
    q_gap, per = None, dist
    try:
        g = abs(float(gap_pct)) / 100.0
        if math.isfinite(g) and g > 0:
            per = max(dist, entry * g)
            q_gap = int(budget // per)
    except (TypeError, ValueError):
        pass
    q_cap = int(float(cap_rupees) // entry) if cap_rupees else None
    cands = [("stop", q_stop)] + ([("gap", q_gap)] if q_gap is not None else []) + \
            ([("cap", q_cap)] if q_cap is not None else [])
    binding, q = min(cands, key=lambda kv: (kv[1], ["gap", "stop", "cap"].index(kv[0])))
    if binding == "gap" and q_gap == q_stop:
        binding = "stop"                 # the gap only binds when it costs shares
    return {"qty": q, "qty_stop": q_stop, "qty_gap": q_gap, "qty_cap": q_cap,
            "per_share": per, "binding": binding}


def lower_stop_qty(qty, avg, new_stop, budget):
    """Shares you may hold with the Disaster SL at new_stop and stay inside the per-trade
    rule, measured from cost (the rule is a per-trade risk on the entry). A stop at or above
    cost locks a profit: no cut needed. Returns (allowed_qty, sell_first)."""
    try:
        vals = [float(qty), float(avg), float(new_stop), float(budget)]
    except (TypeError, ValueError):
        return None, None
    if not all(math.isfinite(v) for v in vals) or vals[1] <= 0:
        return None, None
    qty, avg, new_stop, budget = int(vals[0]), vals[1], vals[2], vals[3]
    if new_stop >= avg:
        return qty, 0
    allowed = min(qty, int(budget // (avg - new_stop)))
    return allowed, qty - allowed


def same_risk_qty(qty, avg, ltp, old_stop, new_stop):
    """Shares that keep the risk you carry NOW when the stop moves from old_stop to new_stop.
    From cost while the old stop is below cost; from LTP once it is above (a locked profit
    has no risk from cost to keep, so the open risk is what is kept). For information - the
    guard enforces the RULE (lower_stop_qty), not this."""
    try:
        qty, avg, ltp = float(qty), float(avg), float(ltp)
        old_stop, new_stop = float(old_stop), float(new_stop)
    except (TypeError, ValueError):
        return None
    base = avg if old_stop < avg else ltp
    if not (new_stop < old_stop < base):
        return int(qty)
    return int(qty * (base - old_stop) // (base - new_stop))


def worst_gap(symbol: str) -> dict:
    """gap_stats for one symbol off the cached 2-year daily bars (the SL Dashboard's frame).
    {} when unavailable - a sizer then falls back to the stop distance and must say so."""
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True, auto_adjust=True)
        return gap_stats(d)
    except Exception:
        return {}


def gap_section(symbols) -> str:
    """S4 bundle GAP= section: 'SYM:-6.8,SYM2:-12.0' = each name's worst 2-year overnight gap,
    one decimal. S4's Qty row sizes on max(entry - stop, entry x |gap|), the same rule as the
    GM sizer and the Risk Allocator v2.8. Names without enough history are left out (S4 then
    sizes on the stop and says 'gap ?')."""
    try:
        import data_provider as dp
        syms = sorted({str(s).upper().strip() for s in symbols if str(s).strip() and str(s).upper() != "NAN"})
        if not syms:
            return ""
        daily = dp.fetch_batch_ohlcv(syms, period="2y", interval="1d", use_cache=True, auto_adjust=True)
    except Exception:
        return ""
    out = []
    for s in syms:
        g = gap_stats(daily.get(s)) if daily else {}
        if g.get("gap_worst") is not None:
            out.append("%s:%.1f" % (s, g["gap_worst"]))
    return ",".join(out)
