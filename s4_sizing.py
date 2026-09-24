"""s4_sizing.py — S4's dynamic position risk, mirrored for the Golden Matcher sizer.

WHY (Jay, 24-Sep-2026): "the GM sizer should mirror S4's dynamic risk". The GM sizer
applied the base risk flat while S4's Qty row scales it by regime, volatility and
conviction — on ACUTAAS the same trade sized ~2.6x larger on the GM screen. S4 is the
plan of record, so the GM computes S4's number rather than a second one.

Every line below mirrors a line of `Section 4 Entry Trigger and Price Memory v10.x`
(the f_fold3889 block, ~:4219-4245) and S4Core.dailyPA (~:950-967). Where the Python side
cannot see what Pine sees, the approximation is named at the function that makes it.

    regime_risk = mkt_health ? base : max(base - 0.25, 0.25 * base)
    kelly_pts   = S2-structure + (RS slope > 0) + (chart RV > 1.1)
    kelly_mult  = max(0.5, {3: 1.25, 2: 1.0, else: 0.75}[kelly_pts] + wcl_adj)
    vol_disc    = ATR% > 3 ? min(3 / ATR%, 1) : 1
    active      = max(regime_risk * max(vol_disc * kelly_mult, 0.75), 0.25 * base)

wcl_adj = +0.25 on S4's setup S2 (Spring/LPS reversal), -0.25 when the 20-bar CHoCH
count is >= 2, else 0. NOTE: this term rests on Wyckoff, which was tested and rejected
as a trading input; it is mirrored here only because S4 applies it (the audit's step 2
decides whether it stays on both surfaces).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

_DIR = os.path.dirname(os.path.abspath(__file__))
WMA_FLAT_PCT = 0.5          # S4 input `wma_flat_pct` default (30WMA flat band, % over 10 bars)
RS_SLOPE_LEN = 60           # S4 ta.linreg(rsRatio, 60, ...)
RV_LEN = 50                 # S4 chart_rv = volume / sma(volume, 50)[1]
DYN_RV_MIN = 1.1            # S4 dyn_vol threshold


def dynamic_risk(base_pct: float, *, mkt_health: bool, s2_structure: bool, rs_up: bool,
                 rv: float | None, atr_pct: float | None, setup_s2: bool = False,
                 choch_count_20: int | None = None) -> dict:
    """The formula, with nothing fetched — so it can be tested against S4's panel."""
    base = float(base_pct)
    regime_risk = base if mkt_health else max(base - 0.25, 0.25 * base)
    dyn_vol = rv is not None and rv > DYN_RV_MIN
    kelly_pts = int(bool(s2_structure)) + int(bool(rs_up)) + int(bool(dyn_vol))
    wcl_adj = 0.25 if setup_s2 else (-0.25 if (choch_count_20 or 0) >= 2 else 0.0)
    kelly_mult = max(0.5, (1.25 if kelly_pts >= 3 else 1.0 if kelly_pts == 2 else 0.75) + wcl_adj)
    a = float(atr_pct) if atr_pct is not None and atr_pct == atr_pct else 0.0
    vol_disc = min(3.0 / a, 1.0) if a > 3.0 else 1.0
    active = max(regime_risk * max(vol_disc * kelly_mult, 0.75), 0.25 * base)
    return {"active_pct": active, "base_pct": base, "regime_risk": regime_risk,
            "mkt_health": bool(mkt_health), "kelly_pts": kelly_pts, "kelly_mult": kelly_mult,
            "wcl_adj": wcl_adj, "vol_disc": vol_disc, "atr_pct": a, "rv": rv,
            "s2_structure": bool(s2_structure), "rs_up": bool(rs_up)}


def daily_structure(daily: pd.DataFrame) -> dict:
    """S4Core.dailyPA's three flags on the last CLOSED daily bar (S4 reads the closed
    bar with confirm-daily on): below the 30WMA proxy (SMA150), the proxy's 10-bar
    slope state (rising / flat / falling against a 0.5% band), below the 200-DMA."""
    c = daily["Close"].astype(float)
    if len(c) < 210:
        return {}
    s150, s200 = c.rolling(150).mean(), c.rolling(200).mean()
    chg = (s150.iloc[-1] - s150.iloc[-11]) / s150.iloc[-1] * 100.0 if s150.iloc[-1] > 0 else 0.0
    s150dn = 0.0 if chg > WMA_FLAT_PCT else (1.0 if chg < -WMA_FLAT_PCT else 0.5)
    bel30 = bool(c.iloc[-1] < s150.iloc[-1])
    bel200 = bool(c.iloc[-1] < s200.iloc[-1])
    h, l = daily["High"].astype(float), daily["Low"].astype(float)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])   # ta.atr = RMA
    return {"bel30": bel30, "s150dn": s150dn, "bel200": bel200,
            "s2_structure": (not bel200) and (not bel30) and s150dn < 0.5,
            "atr_pct": atr / float(c.iloc[-1]) * 100.0 if c.iloc[-1] > 0 else None}


def s4_rv(frame: pd.DataFrame) -> float | None:
    """S4's chart_rv: this bar's volume over the mean of the PRIOR 50 bars."""
    v = frame["Volume"].astype(float)
    if len(v) < RV_LEN + 1:
        return None
    base = float(v.iloc[-RV_LEN - 1:-1].mean())
    return float(v.iloc[-1]) / base if base > 0 else None


def rs_slope_up(frame: pd.DataFrame, bench_daily_close: pd.Series) -> bool | None:
    """S4's rsSlope > 0: slope of a 60-bar linear regression of close / Nifty-500 daily
    close, on the chart timeframe. APPROXIMATION: S4 uses TradingView's CNX500 series;
    this uses the ^CRSLDX daily close as of each bar's date — same index, different feed."""
    if frame is None or len(frame) < RS_SLOPE_LEN or bench_daily_close is None:
        return None
    b = bench_daily_close.copy()
    b.index = pd.to_datetime(b.index).normalize()
    idx = pd.to_datetime(frame.index)
    bd = b.reindex(idx.normalize(), method="ffill").values
    r = frame["Close"].astype(float).values / bd
    r = r[-RS_SLOPE_LEN:]
    if np.isnan(r).any():
        return None
    return bool(np.polyfit(np.arange(RS_SLOPE_LEN), r, 1)[0] > 0)


def market_health() -> bool | None:
    """S4 f_mkt_health: CNX500 close > SMA200 and SMA50 > SMA200 — read from the
    regime file the auto-pilot writes, so no extra fetch."""
    try:
        d = json.load(open(os.path.join(_DIR, "regime_state.json"), encoding="utf-8"))["last"]
        return bool(d["close"] > d["sma200"] and d["sma50"] > d["sma200"])
    except Exception:
        return None


def gm_dynamic_risk(symbol: str, base_pct: float, trigger_frame: pd.DataFrame | None = None,
                    wcl: dict | None = None) -> dict:
    """Everything the GM sizer needs, fetched through data_provider (cached)."""
    import data_provider as dp
    daily = dp.fetch_ohlcv(symbol, period="2y", interval="1d")
    bench = dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d")
    ds = daily_structure(daily) if daily is not None else {}
    frame = trigger_frame if trigger_frame is not None and len(trigger_frame) else daily
    mh = market_health()
    wcl = wcl or {}
    out = dynamic_risk(
        base_pct,
        mkt_health=bool(mh),
        s2_structure=bool(ds.get("s2_structure")),
        rs_up=bool(rs_slope_up(frame, bench["Close"] if bench is not None else None)),
        rv=s4_rv(frame) if frame is not None else None,
        atr_pct=ds.get("atr_pct"),
        setup_s2=str(wcl.get("setup", "")).find("S2") >= 0,
        choch_count_20=wcl.get("choch_count_20"))
    out["mkt_health_known"] = mh is not None
    out["structure_known"] = bool(ds)
    return out


def describe(r: dict) -> str:
    """One line for the sizer caption, in the order S4 applies the terms."""
    bits = [f"base {r['base_pct']:.2f}%"]
    if not r["mkt_health"]:
        bits.append(f"regime not bull → {r['regime_risk']:.2f}%")
    bits.append(f"Kelly {r['kelly_pts']}/3 ×{r['kelly_mult']:.2f}"
                + (f" (WCL {r['wcl_adj']:+.2f})" if r["wcl_adj"] else ""))
    if r["vol_disc"] < 1.0:
        bits.append(f"ATR {r['atr_pct']:.1f}% ×{r['vol_disc']:.2f}")
    return " · ".join(bits) + f" = **{r['active_pct']:.2f}%**"
