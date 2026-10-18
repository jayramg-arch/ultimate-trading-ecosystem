#!/usr/bin/env python3
"""v2 house rules - V2H and P1ES (pre-registered: docs/PREREG_v2_house_rules.md, 18-Oct-2026).

Jay's answers to Doc 41's open questions, as rules layered on P1E (Clenow, ensemble rank):
F&O priority, Wednesday rebalance, house exposure tiers, a 4xATR disaster stop, tax-aware
runners + risk trims, and an ETF sleeve ranked within ETFs. ONE decision function (decide)
serves the backtest here and the live paper books in p1_paper.py, so they cannot drift.

    python v2_house.py --check      engine with every flag off vs pro_systems_backtest (P1E)
    python v2_house.py --plumbing   2018-06..2018-12, trade COUNTS only
    python v2_house.py --run        THE run - once
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v2_backtest as v2            # noqa: E402
import pro_systems_backtest as ps   # noqa: E402

OUT = os.path.join(HERE, "reports", "v2_house")

H = dict(top_pct=0.25, tax_band=0.50, risk=0.001, stop_atr=4.0, tax_from=300, tax_to=365,
         trim_mult=1.5, trim_every=4, etf_cut=0.25, etf_min=2, etf_max=5, etf_pos_cap=0.10,
         etf_sleeve=0.30, etf_liq=2e7, fno_n=210)
FLAGS = ("stop", "wed", "tiers", "fno", "taxtrim", "etf")
NONE = {k: False for k in FLAGS}
FULL = {k: True for k in FLAGS}
# 18-Oct-2026 amendment (Jay): V2H drops the exposure tiers and F&O priority - the two rules the
# registered run showed carry the cost. FULL stays the REGISTERED V2H for reproducing that run.
V2H_REGISTERED = FULL
V2H_REVISED = dict(FULL, tiers=False, fno=False)
BOOK_FLAGS = {"P1E": NONE, "P1ES": dict(NONE, stop=True), "V2H": V2H_REVISED}
INDIAN = {"BROAD_EQUITY", "SECTOR", "SMART_BETA", "THEMATIC"}
ETF_SWAP = {"GOLDIETF": "GOLDBEES"}       # curated pick whose price series is corrupt -> clean twin
ST_RATE, LT_RATE = 0.20, 0.125


# ── schedule ────────────────────────────────────────────────────────────────
def is_wed_decision(d, n) -> bool:
    """True when session d's close decides the week's orders under the Wednesday rule: the next
    session n is the week's first session on/after Wednesday."""
    return n.weekday() >= 2 and (d.weekday() < 2 or tuple(d.isocalendar()[:2]) != tuple(n.isocalendar()[:2]))


def decision_days(idx, wed: bool) -> set:
    if not wed:
        return v2._week_ends(idx)
    return {idx[i] for i in range(len(idx) - 1) if is_wed_decision(idx[i], idx[i + 1])}


# ── exposure tiers (score -> new buys allowed, risk multiplier, Indian-equity cap) ──────────
def tier(score):
    import house_policy as hp
    eff = int(score) if score is not None and score == score else 0
    t = next(t for t in hp.EXPOSURE_TIERS if eff >= t[0])
    return {"name": t[1], "new_ok": t[2], "risk_mult": t[3], "cap": (t[6] / 100.0) if t[6] else None}


def regime_inputs(p: dict, stock_mask: pd.DataFrame, bench_ohlcv: pd.DataFrame) -> dict:
    """Pieces of market_regime's composite score, on the point-in-time stock members."""
    C = p["Close"][stock_mask.columns]
    m = stock_mask.reindex(index=C.index, fill_value=False).astype(bool)
    s200, s50 = C.rolling(200).mean(), C.rolling(50).mean()
    n200 = (s200.notna() & m).sum(axis=1).replace(0, np.nan)
    n50 = (s50.notna() & m).sum(axis=1).replace(0, np.nan)
    ch = C.diff()
    vm = m & C.notna() & C.shift().notna()
    b = bench_ohlcv.copy()
    b.index = pd.to_datetime(b.index)
    if getattr(b.index, "tz", None) is not None:
        b.index = b.index.tz_localize(None)
    b.index = b.index.normalize()
    b = b[~b.index.duplicated(keep="last")][["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
    return {"b200": ((C > s200) & m).sum(axis=1) / n200 * 100, "b50": ((C > s50) & m).sum(axis=1) / n50 * 100,
            "ad": pd.DataFrame({"advance_count": ((ch > 0) & vm).sum(axis=1),
                                "decline_count": ((ch < 0) & vm).sum(axis=1)}), "bench": b}


def regime_score(d, ri: dict) -> tuple:
    """market_regime.compute_regime's score, rebuilt as of the close of d."""
    import market_regime as mr
    b = ri["bench"].loc[:d]
    if len(b) < 210:
        return None, {}
    c = b["Close"]
    s50, s200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
    comps = {"above_sma200_rising": bool(ri["b200"].get(d, 0) >= 50),
             "breadth_above_50": bool(ri["b50"].get(d, 0) >= 50)}
    dd = mr.compute_distribution_days(b)
    comps["dd_low"] = bool((not dd.get("stress", False)) and dd.get("count", 0) <= 3)
    comps["no_death_cross"] = bool(not (s50 < s200))
    comps["follow_through"] = bool(mr.detect_follow_through(b).get("active"))
    comps["breadth_thrust"] = bool(mr.detect_breadth_thrust(ri["ad"].loc[:d].tail(120)).get("active"))
    w = {"above_sma200_rising": 3, "breadth_above_50": 2, "dd_low": 2, "no_death_cross": 1,
         "follow_through": 1, "breadth_thrust": 1}
    return min(10, sum(w[k] for k, v in comps.items() if v)), comps


# ── the ETF pool ──────────────────────────────────────────────────────────────
def etf_pool() -> dict:
    """{symbol: meta} - curated tradeable ETFs, no DEBT, with corrupt series swapped for a clean twin."""
    import etf_universe as eu
    out = {}
    for s, m in eu.ETF_UNIVERSE.items():
        if m.get("asset_class") in eu.NON_TRADEABLE_CLASSES:
            continue
        out[ETF_SWAP.get(s, s)] = m
    return out


def is_etf_symbol(s: str) -> bool:
    try:
        import etf_universe as eu
        if eu.is_etf(s):
            return True
    except Exception:
        pass
    u = str(s).upper()
    return any(t in u for t in ("BEES", "IETF", "ETF", "CASE")) or u in ("LIQUID1", "NV20")


# ── the decision ──────────────────────────────────────────────────────────────
def _ens(g, d, el):
    sc = pd.DataFrame({lb: g["clenow%d" % lb].loc[d][el] for lb in (60, 90, 120)}).dropna()
    return sc.rank(pct=True).mean(axis=1).sort_values(ascending=False)


def decide(d, ctx: dict, flags: dict, equity: float, cash: float, pos: dict, n_dec: int) -> dict:
    """The weekly orders. pos = {sym: {sh, entry, entry_date, last, kind}}. Returns sells, trims
    [(sym, shares)], buys [(sym, amount, kind)], and what was read (ranks, tier, score)."""
    C, g, f = ctx["C"], ctx["g"], ctx["f"]
    cl = C.loc[d]
    stocks, etfs = ctx["stocks"], ctx["etfs"]
    el = (cl > g["sma100"].loc[d]) & ~g["gap90"].loc[d] & g["liq"].loc[d] & f["has"].loc[d]
    el = el.reindex(stocks).fillna(False).astype(bool)
    if flags.get("stage") and ctx.get("stage"):        # B3: v1's first test - weekly Stage 1 or 2 only
        el = el & ctx["stage"](d).reindex(el.index).isin([1, 2])
    sc = _ens(g, d, list(el[el].index)) if el.any() else pd.Series(dtype=float)
    n = len(sc)
    cut = max(1, math.ceil(H["top_pct"] * n)) if n else 0
    top, band = set(sc.index[:cut]), set(sc.index[:max(1, math.ceil(H["tax_band"] * n))] if n else [])

    def _tax_hold(s, q):
        held = (pd.Timestamp(d) - pd.Timestamp(q["entry_date"])).days
        return flags["taxtrim"] and q["last"] > q["entry"] and H["tax_from"] <= held < H["tax_to"]

    sells, stale = [], []
    for s, q in pos.items():
        if q.get("kind", "stock") != "stock":
            continue
        if s in top or (s in band and _tax_hold(s, q)):
            continue
        if ctx.get("stale_keep") and not (cl.get(s, float("nan")) == cl.get(s, float("nan"))):
            stale.append(s)                  # A: no bar today - kept and flagged, never sold on a gap
            continue
        sells.append(s)
    # ETFs - ranked within the ETF pool only
    esc, ecut, etop, prem_out = pd.Series(dtype=float), 0, set(), {}
    if flags["etf"] and etfs:
        ee = (cl[etfs] > g["sma100"].loc[d][etfs]) & ~g["gap90"].loc[d][etfs] & ctx["etf_has"].loc[d][etfs] \
            & (ctx["etf_turn"].loc[d][etfs] >= H["etf_liq"])
        cand = list(ee[ee].index)
        # NAV premium (18-Oct, Jay): an ETF trading more than etf_inav's cap (3 %) away from its NAV
        # is out of the pool - its price no longer tracks what it holds, so its trend score measures
        # the premium (MAFANG +53.8 %, MONQ50 +104.5 % on 15-Oct NAV: creations suspended at the
        # overseas-investment ceiling). Out of the pool means no buy, and a holding is sold.
        # Live only: there is no NAV history for the backtest (ctx has no prem_ok there).
        prem_out = {}
        if ctx.get("prem_ok"):
            for s in list(cand):
                ok, prem, why = ctx["prem_ok"](s)
                if not ok:
                    prem_out[s] = why
                    cand.remove(s)
        best = {}
        for s in cand:                                   # one per underlying: the most traded
            u = ctx["etf_meta"][s].get("underlying") or s
            if u not in best or ctx["etf_turn"].at[d, s] > ctx["etf_turn"].at[d, best[u]]:
                best[u] = s
        cand = list(best.values())
        if cand:
            esc = _ens(g, d, cand)
            ecut = min(len(esc), H["etf_max"], max(H["etf_min"], math.ceil(H["etf_cut"] * len(esc))))
            etop = set(esc.index[:ecut])
        eband = set(esc.index[:max(1, math.ceil(H["tax_band"] * len(esc)))]) if len(esc) else set()
        for s, q in pos.items():
            if q.get("kind") == "etf" and not (s in etop or (s in eband and _tax_hold(s, q))):
                sells.append(s)
    elif not flags["etf"]:
        sells += [s for s, q in pos.items() if q.get("kind") == "etf"]
    # trims - Clenow's one-way risk rebalance, every 4th decision
    trims = []
    if flags["taxtrim"] and n_dec % H["trim_every"] == 0:
        tgt_risk = equity * H["risk"]
        for s, q in pos.items():
            if s in sells:
                continue
            a = g["atr20"].at[d, s] if s in g["atr20"].columns else float("nan")
            if a == a and a > 0 and q["sh"] * a > H["trim_mult"] * tgt_risk:
                trims.append((s, q["sh"] - tgt_risk / a))
    # regime and tier
    up200 = bool(g["b_up200"].get(d, False))
    score, comps = ctx["score"](d) if flags["tiers"] else (None, {})
    tr = tier(score) if flags["tiers"] else {"name": "-", "new_ok": True, "risk_mult": 1.0, "cap": None}
    ind_ok = up200 and tr["new_ok"]
    risk = H["risk"] * tr["risk_mult"]
    free = cash + sum(pos[s]["sh"] * pos[s]["last"] for s in sells) * (1 - v2.COST) \
        + sum(sh * pos[s]["last"] for s, sh in trims) * (1 - v2.COST)
    left = {s: q["sh"] * q["last"] for s, q in pos.items() if s not in sells}
    for s, sh in trims:
        left[s] -= sh * pos[s]["last"]

    def _ind(s):
        return pos[s].get("kind", "stock") == "stock" or ctx["etf_meta"].get(s, {}).get("asset_class") in INDIAN
    room = (tr["cap"] * equity - sum(v for s, v in left.items() if _ind(s))) if tr["cap"] else float("inf")
    buys, skipped = [], {}
    # v1 rules borrowed into v2 (PREREG_v2_borrowed_rules): constants imported from house_policy /
    # sniper_trigger so they cannot drift from v1.
    import house_policy as hp
    st_ = {"n": len([s for s in pos if s not in sells]),
           "heat": sum(q["sh"] * max(0.0, q["last"] - q["stop"]) for s, q in pos.items()
                       if s not in sells and q.get("stop")),
           "sect": {}, "hold": [s for s in left if pos[s].get("kind", "stock") == "stock"]}
    if flags.get("sector"):
        for s, v in left.items():
            sec = ctx.get("sector", {}).get(s)
            if sec:
                st_["sect"][sec] = st_["sect"].get(sec, 0.0) + v
    R = ctx["ret"].loc[:d].tail(250) if (flags.get("corr") and "ret" in ctx) else None

    def _borrow(s, a, kind):
        """The amount after the borrowed rules, None to skip this name, 'break' to stop buying."""
        if flags.get("maxpos") and st_["n"] >= hp.MAX_OPEN_POSITIONS:
            return "break"
        if flags.get("poscap"):
            a = min(a, hp.MAX_ALLOC_DEFAULT / hp.CAPITAL_DEFAULT * equity)
        if kind == "stock" and flags.get("sector"):
            sec = ctx.get("sector", {}).get(s)
            if sec and st_["sect"].get(sec, 0.0) + a > hp.SECTOR_CAP_PCT / 100.0 * equity:
                skipped[s] = "sector cap (%s)" % sec
                return None
        if kind == "stock" and R is not None and st_["hold"] and s in R.columns:
            try:
                from sniper_trigger import CORRELATION_BLOCK as _cb
            except Exception:
                _cb = 0.90
            c = R[[h for h in st_["hold"] if h in R.columns]].corrwith(R[s]).max()
            if c == c and c > _cb:
                skipped[s] = "correlation %.2f" % c
                return None
        if flags.get("heat"):
            a14 = ctx["f"]["atr"].at[d, s]
            if a14 == a14 and st_["heat"] + a * H["stop_atr"] * a14 / cl[s] > hp.HEAT_BUDGET_PCT["OPEN"] / 100.0 * equity:
                return "break"
        if ctx.get("earn_days"):                      # A: results inside the fill week -> defer
            dd = ctx["earn_days"](s)
            if dd is not None and 0 <= dd <= 7:
                skipped[s] = "results in %d days" % dd
                return None
        return a

    def _took(s, a, kind):
        st_["n"] += 1
        if flags.get("heat"):
            a14 = ctx["f"]["atr"].at[d, s]
            st_["heat"] += a * H["stop_atr"] * (a14 if a14 == a14 else 0.0) / cl[s]
        sec = ctx.get("sector", {}).get(s)
        if sec:
            st_["sect"][sec] = st_["sect"].get(sec, 0.0) + a
        if kind == "stock":
            st_["hold"].append(s)
    if ind_ok and n:
        order = list(sc.index)
        if flags["fno"]:
            fset = ctx["fno"](d)
            inc = list(sc.index[:cut])
            order = [s for s in inc if s in fset] + [s for s in inc if s not in fset] + list(sc.index[cut:])
        for s in order:
            if s in pos:
                continue
            a = ps._sizes(equity, cl[s], g["atr20"].at[d, s], risk)
            if a <= 0 or a > free or a > room:
                break
            b = _borrow(s, a, "stock")
            if b == "break":
                break
            if b is None:
                continue
            a = b
            buys.append((s, a, "stock"))
            _took(s, a, "stock")
            free -= a * (1 + v2.COST)
            room -= a
    if flags["etf"] and len(esc):
        sleeve = H["etf_sleeve"] * equity - sum(v for s, v in left.items() if pos[s].get("kind") == "etf")
        for s in esc.index[:ecut]:
            if s in pos:
                continue
            cls = ctx["etf_meta"][s].get("asset_class")
            if cls in INDIAN:
                if not ind_ok:
                    continue
            elif not (cl[s] > g["sma200"].at[d, s]):
                continue
            # gold / silver / international follow their own trend, so the Indian-equity tier's risk
            # multiplier does not apply to them (18-Oct fix: it zeroed them in the BEAR tier)
            a = min(ps._sizes(equity, cl[s], g["atr20"].at[d, s], risk if cls in INDIAN else H["risk"]),
                    H["etf_pos_cap"] * equity)
            if cls in INDIAN:
                a = min(a, room)
            a = min(a, sleeve)
            if a <= 0 or a > free:
                continue
            b = _borrow(s, a, "etf")
            if b == "break":
                break
            if b is None:
                continue
            a = b
            buys.append((s, a, "etf"))
            _took(s, a, "etf")
            free -= a * (1 + v2.COST)
            sleeve -= a
            if cls in INDIAN:
                room -= a
    return {"sells": sells, "trims": trims, "buys": buys, "ranked": sc, "cut": cut, "etf_ranked": esc,
            "etf_cut": ecut, "etf_premium_out": prem_out, "skipped": skipped, "stale": stale, "tier": tr, "score": score, "comps": comps, "up200": up200}


# ── borrowed-rule data (PREREG_v2_borrowed_rules) ─────────────────────────────
def weekly_stage_table(p: dict, cols: list) -> pd.DataFrame:
    """Weekly Stage (bull_screener's 2x2 - the definition S4 / v67 / GM share) per name, indexed
    by the W-FRI week label. Reading the last label <= d uses only CONFIRMED weeks: a forming
    week's label is the coming Friday, which is after d."""
    import bull_screener as bs
    out = {}
    for s in cols:
        df = pd.DataFrame({k: p[k][s] for k in ("Open", "High", "Low", "Close", "Volume")}).dropna()
        if len(df) < 200:
            continue
        wk = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                       "Volume": "sum"}).dropna()
        try:
            out[s] = bs.compute_weekly_stage_and_wks(wk)[0]
        except Exception:
            continue
    return pd.DataFrame(out)


def stage_lookup(W: pd.DataFrame):
    def at(d):
        rows = W.loc[:d]
        return rows.iloc[-1] if len(rows) else pd.Series(dtype=float)
    return at


def atr_ewm(p: dict, n: int) -> pd.DataFrame:
    C, Hh, L = p["Close"], p["High"], p["Low"]
    prev = C.shift()
    tr = np.maximum(Hh - L, np.maximum((Hh - prev).abs(), (L - prev).abs()))
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def sector_map(cols: list) -> dict:
    try:
        import sector_lookup as sl
    except Exception:
        return {}
    out = {}
    for s in cols:
        try:
            v = sl.get_sector_name(s)
        except Exception:
            v = None
        if v:
            out[s] = str(v)
    return out


def trail_level(closes: pd.Series, atr22: float) -> float:
    """House Chandelier (risk_common, POS): highest close of the last 22 bars ON/AFTER entry
    minus 4.5 x ATR22. `closes` = the position's closes from entry to today."""
    import house_policy as hp
    if not len(closes) or not atr22 == atr22:
        return float("nan")
    return float(closes.tail(hp.CHANDELIER_WINDOW_POS).max()) - hp.CHANDELIER_MULT["POS"] * float(atr22)


# ── tax (descriptive) ─────────────────────────────────────────────────────────
def fy_tax(real: list) -> pd.Series:
    """real = [(date, gain, long_term)]. Tax per FY (Apr-Mar): ST losses offset ST then LT, LT
    losses offset LT only, net losses carried forward. Returns {FY end date: tax}."""
    if not real:
        return pd.Series(dtype=float)
    R = pd.DataFrame(real, columns=["date", "gain", "lt"])
    R["fy"] = [d.year + (1 if d.month >= 4 else 0) for d in pd.to_datetime(R["date"])]
    cst = clt = 0.0                      # carried-forward ST / LT losses (positive amounts)
    out = {}
    for fy, gr in R.groupby("fy"):
        st, lt = float(gr.loc[~gr["lt"], "gain"].sum()), float(gr.loc[gr["lt"], "gain"].sum())
        if st < 0 < lt:                  # this year's ST loss sets off this year's LT gain
            u = min(-st, lt)
            st, lt = st + u, lt - u
        for amt_name in ("st", "lt"):    # ST carry offsets ST then LT
            v = st if amt_name == "st" else lt
            if v > 0 and cst > 0:
                u = min(cst, v)
                cst -= u
                v -= u
            if amt_name == "st":
                st = v
            else:
                lt = v
        if lt > 0 and clt > 0:           # LT carry offsets LT only
            u = min(clt, lt)
            clt, lt = clt - u, lt - u
        if st < 0:
            cst, st = cst - st, 0.0
        if lt < 0:
            clt, lt = clt - lt, 0.0
        out[pd.Timestamp(fy, 3, 31)] = ST_RATE * st + LT_RATE * lt
    return pd.Series(out)


# ── the backtest loop ─────────────────────────────────────────────────────────
def run_book(flags: dict, p: dict, ctx: dict, start, end) -> tuple:
    O, L, C = p["Open"], p["Low"], p["Close"]
    days = C.index[(C.index >= start) & (C.index <= end)]
    dec = decision_days(days, flags["wed"])
    bk = v2.Book(1.0)
    pend, eq, real, n_dec, hold_days = None, [], [], 0, []

    def _sell(s, px, d, sh=None):
        q = bk.pos[s]
        sh = q["sh"] if sh is None else min(sh, q["sh"])
        gain = sh * (px * (1 - v2.COST) - q["entry"] * (1 + v2.COST))
        held = (d - q["entry_date"]).days
        real.append((d, gain, held > 365))
        if sh >= q["sh"] - 1e-12:
            hold_days.append(held)
            bk.sell(s, px)
        else:
            bk.cash += sh * px * (1 - v2.COST)
            bk.traded += sh * px
            bk.trades += 1
            q["sh"] -= sh

    for d in days:
        if pend:
            for s in pend["sells"]:
                if s in bk.pos:
                    px = O.at[d, s]
                    _sell(s, px if px == px else bk.pos[s]["last"], d)
            for s, sh in pend["trims"]:
                if s in bk.pos:
                    px = O.at[d, s]
                    _sell(s, px if px == px else bk.pos[s]["last"], d, sh)
            for s, amt, kind in pend["buys"]:
                px = O.at[d, s]
                if px == px and s not in bk.pos and amt > 0:
                    stop = None
                    if flags["stop"]:
                        a14 = ctx["f"]["atr"].at[pend["d"], s]
                        stop = px - H["stop_atr"] * a14 if a14 == a14 else None
                    bk.buy(s, px, amt, stop)
                    if s in bk.pos:
                        bk.pos[s]["entry_date"], bk.pos[s]["kind"] = d, kind
            pend = None
        for s in list(bk.pos):
            q, lo, op = bk.pos[s], L.at[d, s], O.at[d, s]
            if q["stop"] and lo == lo and lo <= q["stop"]:
                _sell(s, min(op, q["stop"]) if op == op else q["stop"], d)
        for s, q in bk.pos.items():
            c = C.at[d, s]
            if c == c:
                q["last"] = c
            if flags.get("trail") and q.get("stop"):            # B7: the house Chandelier, tighten only
                lv = trail_level(C[s].loc[q["entry_date"]:d].dropna(), ctx["atr22"].at[d, s])
                if lv == lv and lv > q["stop"]:
                    q["stop"] = lv
        eq.append(bk.value(C, d))
        if d in dec:
            n_dec += 1
            r = decide(d, ctx, flags, eq[-1], bk.cash, bk.pos, n_dec)
            pend = {"d": d, "sells": r["sells"], "trims": r["trims"], "buys": r["buys"]}
    e = pd.Series(eq, index=days)
    tax = fy_tax(real)
    paid = pd.Series(0.0, index=days)
    for fy_end, t in tax.items():
        paid.loc[paid.index > fy_end] += t
    stats = {"trades": bk.trades, "years": (days[-1] - days[0]).days / 365.25,
             "median_hold": float(np.median(hold_days)) if hold_days else float("nan"),
             "lt_share": (sum(g_ for _, g_, lt in real if lt and g_ > 0) /
                          max(1e-12, sum(g_ for _, g_, _lt in real if g_ > 0)))}
    return e, e - paid, stats


# ── live paper books (p1_paper.py) ────────────────────────────────────────────
def live_context(p: dict, f: dict, g: dict, stocks: list, etfs: list) -> dict:
    """The decide() context on the live Nifty 500 panel (+ the ETF pool)."""
    import data_provider as dp
    Cc, Vv = p["Close"], p["Volume"]
    pool = etf_pool()
    fno_live = set()
    try:
        fh = pd.read_csv(os.path.join(HERE, "data", "fno_history.csv"), usecols=["date", "symbol"])
        fno_live = set(fh.loc[fh["date"] == fh["date"].max(), "symbol"].astype(str).str.upper())
    except Exception:
        pass
    bench = dp.fetch_ohlcv("^CRSLDX", period="2y", interval="1d", use_cache=True)
    ri = regime_inputs(p, f["has"][stocks], bench)
    cache = {}

    def _prem_ok(s):                     # etf_inav: T-1 NAV vs price, cap ETF_MAX_PREMIUM_PCT (3 %)
        try:
            import etf_inav
            return etf_inav.is_tradeable(s)
        except Exception as e:
            return True, None, "premium unavailable (%s)" % e

    def score(d):
        if d not in cache:
            cache[d] = regime_score(d, ri)
        return cache[d]
    def _earn(s):                        # A: earnings_calendar (yfinance, cached); unknown -> None
        try:
            import earnings_calendar as ec
            ec.refresh([s])
            return ec.days_to_earnings(s)
        except Exception:
            return None
    ctx = {"C": Cc, "g": g, "f": f, "stocks": stocks, "etfs": [s for s in etfs if s in pool],
           "etf_meta": pool, "etf_has": Cc.notna().cumsum() >= v2.MIN_BARS,
           "etf_turn": (Cc * Vv).rolling(50).median(), "fno": lambda d: fno_live, "score": score,
           "prem_ok": _prem_ok, "earn_days": _earn, "stale_keep": True}
    _add_borrowed(ctx, p, stocks)
    return ctx


def _next_session(d: dt.date) -> dt.date:
    import nse_calendar as nc
    n = d + dt.timedelta(days=1)
    while not nc.is_trading_day(n):
        n += dt.timedelta(days=1)
    return n


def step_live(st: dict, p: dict, ctx: dict, flags: dict, start: dt.date, reviewed: bool = False) -> list:
    """Advance one house book (P1ES / V2H) through every completed session after st['last_date'],
    with the same fills, stops and decisions as run_book. Returns the decided order lines."""
    O, L, C = p["Open"], p["Low"], p["Close"]
    days = [d for d in C.index if d.date() >= start and
            (st["last_date"] is None or d.date() > dt.date.fromisoformat(st["last_date"]))]
    orders = []

    def _px(frame, d, s, fb):
        v = frame.at[d, s] if s in frame.columns else float("nan")
        return float(v) if v == v else fb

    def _sell(s, px, d, why, sh=None):
        q = st["pos"][s]
        sh = q["sh"] if sh is None else min(sh, q["sh"])
        amt = sh * px
        st["cash"] += amt * (1 - v2.COST)
        st["trades"].append({"date": str(d.date()), "side": why, "symbol": s, "price": round(px, 2),
                             "shares": round(sh, 2), "value": round(amt), "pnl": round(amt - sh * q["entry"])})
        if sh >= q["sh"] - 1e-9:
            st["pos"].pop(s)
        else:
            q["sh"] -= sh

    for d in days:
        pend = st.get("pending")
        if pend:
            for s in pend.get("sells", []):
                if s in st["pos"]:
                    _sell(s, _px(O, d, s, st["pos"][s]["last"]), d, "SELL")
            for s, sh in pend.get("trims", []):
                if s in st["pos"]:
                    _sell(s, _px(O, d, s, st["pos"][s]["last"]), d, "TRIM", sh)
            rulings = {}
            if reviewed:
                try:
                    import v2_core
                    rulings = v2_core.latest_reviews(pend.get("decided"))
                except Exception:
                    rulings = {}
            for s, amt, kind, a14 in pend.get("buys", []):
                if reviewed and rulings.get(s) in ("WAIT", "PASS"):
                    st["trades"].append({"date": str(d.date()), "side": "SKIP", "symbol": s,
                                         "reason": "reviewer %s - reconsidered next rebalance" % rulings[s]})
                    continue
                px = _px(O, d, s, float("nan"))
                if not px == px or s in st["pos"]:
                    continue
                amt = min(amt, st["cash"] / (1 + v2.COST))
                if amt <= 0:
                    continue
                sh = amt / px
                st["cash"] -= amt * (1 + v2.COST)
                stop = round(px - H["stop_atr"] * a14, 2) if (flags["stop"] and a14 and a14 == a14) else None
                st["pos"][s] = {"sh": sh, "entry": px, "entry_date": str(d.date()), "last": px,
                                "kind": kind, "stop": stop}
                st["trades"].append({"date": str(d.date()), "side": "BUY", "symbol": s, "price": round(px, 2),
                                     "shares": round(sh, 2), "value": round(amt), "kind": kind, "stop": stop})
            st["pending"] = None
        for s in list(st["pos"]):                     # the resting disaster stop
            q = st["pos"][s]
            lo = _px(L, d, s, float("nan"))
            if q.get("stop") and lo == lo and lo <= q["stop"]:
                op = _px(O, d, s, q["stop"])
                _sell(s, min(op, q["stop"]), d, "STOP")
        for s, q in st["pos"].items():
            c = _px(C, d, s, float("nan"))
            if c == c:
                q["last"] = c
            if flags.get("trail") and q.get("stop"):            # B7: the house Chandelier, tighten only
                lv = trail_level(C[s].loc[pd.Timestamp(q["entry_date"]):d].dropna(), ctx["atr22"].at[d, s])
                if lv == lv and lv > q["stop"]:
                    q["stop"] = round(lv, 2)
        equity = st["cash"] + sum(q["sh"] * q["last"] for q in st["pos"].values())
        st["history"].append({"date": str(d.date()), "equity": round(equity), "cash": round(st["cash"]),
                              "positions": len(st["pos"]), "nifty500": round(float(p["bench"].get(d, float("nan"))), 1)})
        st["last_date"] = str(d.date())
        n = _next_session(d.date())
        is_dec = is_wed_decision(pd.Timestamp(d.date()), pd.Timestamp(n)) if flags["wed"] else \
            (n.isocalendar()[:2] != d.date().isocalendar()[:2])
        if not is_dec:
            continue
        st["n_dec"] = int(st.get("n_dec", 0)) + 1
        posv = {s: dict(q, entry_date=pd.Timestamp(q["entry_date"])) for s, q in st["pos"].items()}
        r = decide(d, ctx, flags, equity, st["cash"], posv, st["n_dec"])
        a14 = ctx["f"]["atr"].loc[d]
        st["pending"] = {"decided": str(d.date()), "fill": str(n), "sells": r["sells"],
                         "trims": [[s, round(sh, 4)] for s, sh in r["trims"]],
                         "buys": [[s, round(a), k, round(float(a14.get(s, float("nan"))), 4)] for s, a, k in r["buys"]],
                         "regime_up": r["up200"], "score": r["score"], "tier": r["tier"]["name"],
                         "eligible": int(len(r["ranked"])),
                         "watch": [[s, round(float(v), 3), round(float(C.at[d, s]), 2)] for s, v in r["ranked"].head(20).items()],
                         "etf_watch": [[s, round(float(v), 3)] for s, v in r["etf_ranked"].head(8).items()],
                         "etf_premium_out": r.get("etf_premium_out", {})}
        rank_pos = {s: i + 1 for i, s in enumerate(r["ranked"].index)}
        for s in r["sells"]:
            orders.append({"book": st["name"], "side": "SELL", "symbol": s, "rank": rank_pos.get(s, "-"),
                           "close": round(float(C.at[d, s]), 2), "shares": round(st["pos"][s]["sh"], 2),
                           "approx_value": round(st["pos"][s]["sh"] * st["pos"][s]["last"])})
        for s, sh in r["trims"]:
            orders.append({"book": st["name"], "side": "TRIM", "symbol": s, "rank": rank_pos.get(s, "-"),
                           "close": round(float(C.at[d, s]), 2), "shares": round(sh, 2),
                           "approx_value": round(sh * st["pos"][s]["last"])})
        for s, a, k in r["buys"]:
            px = float(C.at[d, s])
            orders.append({"book": st["name"], "side": "BUY" if k == "stock" else "BUY ETF", "symbol": s,
                           "rank": rank_pos.get(s, "-"), "close": round(px, 2), "shares": int(a // px),
                           "approx_value": round(a), "atr20": round(float(ctx["g"]["atr20"].at[d, s]), 2),
                           "stop≈": round(px - H["stop_atr"] * float(a14.get(s, float("nan"))), 2) if flags["stop"] else None})
    return orders


# ── panel + context ───────────────────────────────────────────────────────────
def load_backtest() -> tuple:
    import pickle
    import survivorship_backtest as sb
    import data_provider as dp
    p = pickle.load(open(sb.PANEL, "rb"))
    C = p["Close"].astype(float)
    bad = set((C.pct_change().abs() > 0.5).sum().loc[lambda x: x >= 3].index)
    mem = sb.membership(p)
    pool = etf_pool()
    etfs = [s for s in pool if s in C.columns and s not in bad]
    stocks = [s for s in mem.columns[mem.any()] if s not in bad and not is_etf_symbol(s)]
    cols = sorted(set(stocks) | set(etfs))
    for k in ("Open", "High", "Low", "Close", "Volume"):
        p[k] = p[k][cols].astype(float)
    mem = mem.reindex(columns=cols, fill_value=False)
    mem[etfs] = False
    f = v2.features(p)
    f["has"] = f["has"] & mem
    f["elig"] = f["elig"] & mem
    g = ps.pro_features(p, f)
    Cc, Vv = p["Close"], p["Volume"]
    turn = (Cc * Vv).rolling(126, min_periods=100).median()
    idx = Cc.index
    me = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max()
    rebal = [x for k, x in me.items() if k.month in (6, 12)]
    has_raw = Cc.notna().cumsum() >= v2.MIN_BARS
    fno_sets = []                       # F&O proxy: the fno_n most-traded names at each Jun/Dec rebalance
    for x in rebal:
        t = turn.loc[x, stocks].where(has_raw.loc[x, stocks]).dropna()
        fno_sets.append((x, set(t.sort_values(ascending=False).index[:H["fno_n"]])))

    def fno(d):
        s = set()
        for x, st in fno_sets:
            if x < d:
                s = st
        return s
    bench = dp.fetch_ohlcv("^CRSLDX", period="10y", interval="1d", use_cache=True)
    ri = regime_inputs(p, mem[stocks], bench)
    cache = {}

    def score(d):
        if d not in cache:
            cache[d] = regime_score(d, ri)
        return cache[d]
    ctx = {"C": p["Close"], "g": g, "f": f, "stocks": stocks, "etfs": etfs, "etf_meta": pool,
           "etf_has": Cc.notna().cumsum() >= v2.MIN_BARS, "etf_turn": (Cc * Vv).rolling(50).median(),
           "fno": fno, "score": score}
    _add_borrowed(ctx, p, stocks)
    return p, f, g, ctx


def _add_borrowed(ctx: dict, p: dict, stocks: list) -> None:
    """Data the borrowed v1 rules read: daily returns (correlation), ATR22 (Chandelier), sector
    names, and the weekly Stage table (built on first use - it is the slow part)."""
    ctx["ret"] = p["Close"].pct_change()
    ctx["atr22"] = atr_ewm(p, 22)
    ctx["sector"] = sector_map(stocks)
    box = {}

    def stage(d):
        if "W" not in box:
            box["at"] = stage_lookup(weekly_stage_table(p, stocks))
            box["W"] = True
        return box["at"](d)
    ctx["stage"] = stage


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--plumbing", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--revised", action="store_true", help="the amended V2H, DESCRIPTIVE (post-hoc)")
    ap.add_argument("--borrowed", action="store_true", help="PREREG_v2_borrowed_rules - once")
    a = ap.parse_args()
    if not (a.check or a.plumbing or a.run or a.revised or a.borrowed):
        ap.print_help()
        return 0
    p, f, g, ctx = load_backtest()
    S, SP, E = v2.START, v2.SPLIT, v2.END
    if a.check:
        e1, _ = ps.run_sys("P1", p, f, g, S, pd.Timestamp("2020-12-31"), params={"ensemble": True, "top_pct": 0.25})
        e2, _, st = run_book(NONE, p, ctx, S, pd.Timestamp("2020-12-31"))
        diff = float((e1 / e1.iloc[0] - e2 / e2.iloc[0]).abs().max())
        print("max |equity difference| P1E run_sys vs v2_house all-off: %.10f  (trades %d)" % (diff, st["trades"]))
        return 0 if diff < 1e-9 else 1
    if a.plumbing:
        for name, fl in BOOK_FLAGS.items():
            _, _, st = run_book(fl, p, ctx, S, pd.Timestamp("2018-12-31"))
            print(name, "trades", st["trades"])
        return 0
    if a.revised:                       # suggested BY the run below - descriptive, never pass/fail
        rows = []
        for name, fl in (("P1E", NONE), ("P1ES", BOOK_FLAGS["P1ES"]), ("V2H registered", V2H_REGISTERED),
                         ("V2H revised", V2H_REVISED)):
            e, ea, st = run_book(fl, p, ctx, S, E)
            for half, (s0, s1) in {"full": (S, E), "H1": (S, SP - pd.Timedelta(days=1)), "H2": (SP, E)}.items():
                m = v2.metrics(e.loc[s0:s1])
                m.update(book=name, half=half)
                if half == "full":
                    m["CAGR after tax%"] = v2.metrics(ea).get("CAGR%")
                    m["trades/yr"] = round(st["trades"] / st["years"], 1)
                rows.append(m)
        T = pd.DataFrame(rows)[["book", "half", "CAGR%", "maxDD%", "MAR", "Sharpe", "CAGR after tax%", "trades/yr"]]
        print(T.to_string(index=False))
        print("\nDESCRIPTIVE ONLY: the revised rule set was chosen after seeing the ablations; it is judged forward.")
        return 0
    if a.borrowed:                      # PREREG_v2_borrowed_rules - THE run, once
        def _m(e):
            r_ = {}
            for half, (s0, s1) in {"full": (S, E), "H1": (S, SP - pd.Timedelta(days=1)), "H2": (SP, E)}.items():
                r_[half] = v2.metrics(e.loc[s0:s1])
            return r_
        base_e, base_a, base_st = run_book(V2H_REVISED, p, ctx, S, E)
        res = {"V2H (baseline)": (_m(base_e), base_st, v2.metrics(base_a))}
        names = {"sector": "B1 sector cap 25 %", "corr": "B2 correlation > 0.90", "stage": "B3 Stage 1/2 only",
                 "poscap": "B4 per-trade cap 3.33 %", "heat": "B5 open-risk budget 6 %",
                 "maxpos": "B6 max 25 positions", "trail": "B7 house Chandelier trail"}
        adopted = []
        for k, nm in names.items():
            e, ea, st = run_book(dict(V2H_REVISED, **{k: True}), p, ctx, S, E)
            m = _m(e)
            ok = all(m[h]["MAR"] >= res["V2H (baseline)"][0][h]["MAR"] - 0.05 for h in ("H1", "H2"))
            res[nm + (" ADOPT" if ok else " REJECT")] = (m, st, v2.metrics(ea))
            if ok:
                adopted.append(k)
            print("done", nm, "ADOPT" if ok else "REJECT", flush=True)
        if adopted:
            e, ea, st = run_book(dict(V2H_REVISED, **{k: True for k in adopted}), p, ctx, S, E)
            res["combined: " + "+".join(adopted)] = (_m(e), st, v2.metrics(ea))
        rows = []
        for nm, (m, st, ma) in res.items():
            rows.append({"book": nm, "CAGR%": m["full"]["CAGR%"], "maxDD%": m["full"]["maxDD%"],
                         "MAR": m["full"]["MAR"], "MAR H1": m["H1"]["MAR"], "MAR H2": m["H2"]["MAR"],
                         "Sharpe": m["full"]["Sharpe"], "after tax%": ma.get("CAGR%"),
                         "trades/yr": round(st["trades"] / st["years"], 1)})
        T = pd.DataFrame(rows)
        os.makedirs(OUT, exist_ok=True)
        T.to_csv(os.path.join(OUT, "borrowed_metrics.csv"), index=False)
        print(T.to_string(index=False))
        if adopted:
            b = res["V2H (baseline)"][0]
            cm = res["combined: " + "+".join(adopted)][0]
            fine = all(cm[h]["MAR"] >= b[h]["MAR"] - 0.10 for h in ("H1", "H2"))
            print("\nADOPTED: %s · combination %s" % (", ".join(adopted),
                  "holds (all adopted rules join V2H)" if fine else "falls >0.10 below baseline -> keep only the single best"))
        else:
            print("\nADOPTED: none")
        return 0
    books = dict(BOOK_FLAGS, V2H=V2H_REGISTERED)
    for k in ("wed", "tiers", "fno", "taxtrim", "etf"):
        books["P1E+" + k] = dict(NONE, **{k: True})
    res, aft, extra = {}, {}, {}
    for name, fl in books.items():
        e, ea, st = run_book(fl, p, ctx, S, E)
        res[name], aft[name], extra[name] = e, ea, st
        print("done", name, st, flush=True)
    e3, _ = v2.run_variant("B3", p, f, S, E)
    res["B3 Momentum-30 replica"] = e3
    b1 = p["bench"].loc[S:E].dropna()
    res["B1 Nifty 500"] = b1 / b1.iloc[0]
    rows = []
    for name, e in res.items():
        for half, (s0, s1) in {"full": (S, E), "H1": (S, SP - pd.Timedelta(days=1)), "H2": (SP, E)}.items():
            m = v2.metrics(e.loc[s0:s1])
            m.update(book=name, half=half)
            if half == "full" and name in aft:
                ma = v2.metrics(aft[name])
                m["CAGR after tax%"] = ma.get("CAGR%")
                m["trades/yr"] = round(extra[name]["trades"] / extra[name]["years"], 1)
                m["median hold d"] = extra[name]["median_hold"]
                m["LT share of gains%"] = round(extra[name]["lt_share"] * 100, 1)
            rows.append(m)
    T = pd.DataFrame(rows)
    cols = ["book", "half", "CAGR%", "maxDD%", "MAR", "Sharpe", "CAGR after tax%", "trades/yr", "median hold d",
            "LT share of gains%"]
    T = T[[c for c in cols if c in T.columns]]
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "metrics.csv"), index=False)
    pd.DataFrame({k: v / v.iloc[0] for k, v in res.items()}).to_csv(os.path.join(OUT, "equity.csv"))
    print(T.to_string(index=False))
    G = {h: T[T.half == h].set_index("book") for h in ("H1", "H2")}
    h1 = all(G[h].at["P1ES", "MAR"] >= G[h].at["P1E", "MAR"] - 0.10 for h in G)
    h2 = all(G[h].at["V2H", "MAR"] > G[h].at["B1 Nifty 500", "MAR"] and
             G[h].at["V2H", "MAR"] > G[h].at["B3 Momentum-30 replica", "MAR"] and
             G[h].at["V2H", "MAR"] >= G[h].at["P1E", "MAR"] - 0.15 for h in G)
    print("\nH1 (stop affordable) %s · H2 (V2H the candidate) %s" % ("PASS" if h1 else "FAIL", "PASS" if h2 else "FAIL"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
