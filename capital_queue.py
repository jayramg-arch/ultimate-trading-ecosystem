"""capital_queue.py — one queue for the next rupee: pyramid ADDs and new GO names on one scale.

WHY (25-Sep-2026, Jay: "I cannot keep adding more stocks beyond my 22 count … how can we make
the Pyramid/Trim system more effective?"). Three measurements set the design:
  * the trim rungs are INERT (docs/PREREG_exit_policy.md) — capital is freed by EXITs and the
    trail, not by trims, so exits are what fund the queue;
  * an ADD and a NEW entry are indistinguishable in expected R (docs/PREREG_add_premise.md,
    THIN: IS −0.40 vs −0.35R, OOS +0.22 vs +0.14R) — so the choice cannot be made on return;
  * therefore it is made on RISK: an add concentrates, a new name diversifies.

THIS IS AN ORGANISING TOOL, NOT A MEASURED EDGE. The rank is the Reviewer's context ladder
(stage → leadership → location) first, then a concentration penalty, then the board's Overall.
Every input is something the board, the pyramid ladder or the order gate already computes;
nothing here re-derives a signal.

    import capital_queue as cq
    res = cq.build()          # {'queue', 'freed', 'summary'}
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_CSV = os.path.join(HERE, "FINAL_Portfolio_Picks.csv")
BOARD_TFS = ("75m", "125m", "Daily")
TIER_NOTE = {"A": "stage + leadership + zone", "B": "stage + one of leadership / level",
             "C": "stage only, or weak location"}


def _board_path(tf):
    return os.path.join(HERE, f"gm_board_cache_{tf}.csv")


def _settings():
    try:
        return json.load(open(os.path.join(HERE, "gm_settings.json"), encoding="utf-8"))
    except Exception:
        return {}


def _num(x, default=np.nan):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _is_live(row) -> bool:
    return (str(row.get("S4-GO", "")).startswith("5/5")
            or str(row.get("Category", "")).startswith("Buy Trigger Live"))


def _loc_class(loc: str) -> str:
    """zone / level / weak — the Reviewer's location ladder read off the board's Loc cell."""
    s = str(loc or "")
    if "→" in s and not s.startswith(("AT", "IN", "REACTING")):
        return "weak"                       # approaching, not at it
    if "pattern" in s and s.startswith(("AT", "IN", "REACTING")):
        return "zone"
    if "pivot+conf" in s or "S/R" in s:
        return "level"
    return "weak"                           # AVWAP / EMA only, or nothing


def load_book() -> pd.DataFrame:
    if not os.path.exists(BOOK_CSV):
        return pd.DataFrame()
    b = pd.read_csv(BOOK_CSV)
    b["Symbol"] = b["Symbol"].astype(str).str.upper()
    try:
        import data_provider as dp
        ltp = dp.get_ltp_batch(list(b["Symbol"]))
    except Exception:
        ltp = {}
    b["LTP"] = [_num(ltp.get(s)) for s in b["Symbol"]]
    b["LTP"] = b["LTP"].fillna(pd.to_numeric(b["Avg"], errors="coerce"))
    b["Value"] = pd.to_numeric(b["Qty"], errors="coerce").fillna(0) * b["LTP"]
    tot = b["Value"].sum()
    b["Weight%"] = b["Value"] / tot * 100 if tot > 0 else np.nan
    return b


def load_live_candidates(held: set) -> pd.DataFrame:
    """Every board row that is live on some tab (5/5 GO or Buy Trigger Live); one row per
    symbol, taken from the most-live tab, with the list of tabs it is live on."""
    rows = {}
    for tf in BOARD_TFS:
        p = _board_path(tf)
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p)
        for _, r in d.iterrows():
            r = r.to_dict()
            if not _is_live(r):
                continue
            sym = str(r["Symbol"]).upper()
            go5 = str(r.get("S4-GO", "")).startswith("5/5")
            prev = rows.get(sym)
            if prev is None or (go5 and not prev["_go5"]):
                r["_go5"], r["_tfs"] = go5, [tf]
                if prev:
                    r["_tfs"] = prev["_tfs"] + [tf]
                rows[sym] = r
            else:
                prev["_tfs"].append(tf)
    out = pd.DataFrame(rows.values())
    if out.empty:
        return out
    out["Symbol"] = out["Symbol"].astype(str).str.upper()
    out["Held"] = out["Symbol"].isin(held)
    return out


def _max_corr(sym: str, book_syms: list, days: int = 120):
    """Max |ρ| of daily returns against the book, and which holding. Same idea as
    pyramid_logic's Corr_Max, for a name not yet held."""
    try:
        import data_provider as dp
        def rets(s):
            f = dp.fetch_ohlcv(s, period="1y", interval="1d", use_cache=True)
            return f["Close"].pct_change().dropna().iloc[-days:] if f is not None and len(f) > 30 else None
        a = rets(sym)
        if a is None:
            return np.nan, ""
        best, who = 0.0, ""
        for h in book_syms:
            b = rets(h)
            if b is None:
                continue
            j = pd.concat([a, b], axis=1, join="inner").dropna()
            if len(j) < 40:
                continue
            c = abs(float(j.iloc[:, 0].corr(j.iloc[:, 1])))
            if c > best:
                best, who = c, h
        return best, who
    except Exception:
        return np.nan, ""


def _sector_after(book: pd.DataFrame, sym: str, qty: float, px: float):
    """Sector % after this order, AT COST — the order gate's exact computation."""
    try:
        import ai_risk_manager as rm
        import sector_lookup as sl
        rows = [{"Symbol": s, "Quantity": q, "BuyPrice": a}
                for s, q, a in zip(book["Symbol"], book["Qty"], book["Avg"])]
        rows.append({"Symbol": sym, "Quantity": qty, "BuyPrice": px})
        br = (rm.analyze_sector_concentration(pd.DataFrame(rows)) or {}).get("breakdown", {})
        rec = sl.get_sector(sym)
        sec = (rec.get("display_name") or rec.get("sector_name")) if rec else None
        return sec, (float(br.get(sec, np.nan)) if sec else np.nan)
    except Exception:
        return None, np.nan


def build(cash: float | None = None, count_exits: bool | None = None,
          classes: dict | None = None) -> dict:
    """`cash` = Dhan available balance (None = unknown). `count_exits` = treat EXIT /
    REDUCE / TRIM proceeds as money available now; default from gm_settings
    `queue_count_exits`, False. Jay, 25-Sep-2026: in a deep recovery tape he is holding
    rather than exiting, so a queue that spends exit proceeds is spending money that
    does not exist. Off = fund from cash only, exits listed as "if taken"."""
    import pre_trade_gate as ptg
    import house_policy as hp
    st = _settings()
    capital = hp.sizing_capital()[0]
    capital = 0.0 if math.isnan(capital) else capital
    risk_new = hp.RISK_NEW_STOCK_PCT
    risk_add = hp.RISK_ADD_PCT
    max_alloc = hp.max_alloc()
    if count_exits is None:
        count_exits = bool(st.get("queue_count_exits", False))

    book = load_book()
    # LIVE ladder classes when the caller has them (Risk Shield computes them on load);
    # otherwise the 16:30 auto-pilot snapshot in FINAL_Portfolio_Picks.csv. Said on screen,
    # because the two can disagree intraday and the queue sits beside the live Pyramid tab.
    class_src = "16:30 snapshot"
    if classes and not book.empty:
        live = {str(k).upper(): str(v).upper() for k, v in classes.items() if v}
        hit = book["Symbol"].isin(live.keys())
        if hit.any():
            book.loc[hit, "Pyr_Class"] = book.loc[hit, "Symbol"].map(live)
            class_src = f"live ({int(hit.sum())}/{len(book)})"
    held = set(book["Symbol"]) if not book.empty else set()
    cls = dict(zip(book["Symbol"], book["Pyr_Class"])) if not book.empty else {}
    cand = load_live_candidates(held)
    # Every ADD-rated holding belongs in the queue even when no tab is live on it yet —
    # it is the one candidate the ladder already rates, so hiding it until a trigger fires
    # would make the queue look like "new names only". Pulled from the most recent board
    # row for the symbol; marked not live.
    live_syms = set(cand["Symbol"]) if not cand.empty else set()
    extra = []
    for sym in [s for s, c in cls.items() if str(c).upper() == "ADD" and s not in live_syms]:
        for tf in BOARD_TFS:
            p = _board_path(tf)
            if not os.path.exists(p):
                continue
            d = pd.read_csv(p)
            hit = d[d["Symbol"].astype(str).str.upper() == sym]
            if len(hit):
                rr = hit.iloc[0].to_dict()
                rr.update(Symbol=sym, Held=True, _go5=False, _tfs=[], _live=False)
                extra.append(rr)
                break
    if not cand.empty:
        cand["_live"] = True
    if extra:
        cand = pd.concat([cand, pd.DataFrame(extra)], ignore_index=True)

    # ── funding: what exits free, and what could be freed ────────────────────
    freed = book[book["Pyr_Class"].isin(["EXIT", "REDUCE", "TRIM"])].copy() if not book.empty else book
    if not freed.empty:
        share = freed["Pyr_Class"].map({"EXIT": 1.0, "REDUCE": 0.5, "TRIM": 1 / 3})
        freed["Frees"] = freed["Value"] * share
        freed = freed[["Symbol", "Pyr_Class", "Qty", "LTP", "Value", "Frees", "Pyr_Trigger"]]
    exit_now = float(freed.loc[freed["Pyr_Class"] == "EXIT", "Frees"].sum()) if not freed.empty else 0.0
    could = float(freed.loc[freed["Pyr_Class"] != "EXIT", "Frees"].sum()) if not freed.empty else 0.0

    # ── candidates ─────────────────────────────────────────────────────────────
    out = []
    try:
        import etf_universe as eu
    except Exception:
        eu = None
    n_open = len(held)
    for _, r in cand.iterrows() if not cand.empty else []:
        sym = r["Symbol"]
        is_add = bool(r["Held"])
        if is_add and str(cls.get(sym, "")).upper() != "ADD":
            continue                         # held, live on the board, but the ladder says not to add
        entry, sl = _num(r.get("Entry")), _num(r.get("SL"))
        if not (entry > 0 and sl > 0 and sl < entry):
            continue
        stage = _num(r.get("Stage"))
        rs = _num(r.get("RS"))
        loc = _loc_class(r.get("Loc"))
        stage_ok = stage == 2 or (str(r.get("Path", "")).lower().startswith("rec") and stage <= 2)
        lead = rs > 0
        tier = ("A" if (stage_ok and lead and loc == "zone") else
                "B" if (stage_ok and (lead or loc in ("zone", "level"))) else "C")
        etf = bool(eu and eu.is_etf(sym))
        rk = hp.risk_pct_for(sym, add=is_add)
        qty = math.floor(capital * rk / 100.0 / (entry - sl)) if capital > 0 else 0
        if max_alloc and max_alloc > 0 and entry > 0:
            qty = min(qty, math.floor(max_alloc / entry))
        amount = qty * entry
        sec, sec_after = _sector_after(book, sym, qty, entry) if qty > 0 else (r.get("Sector"), np.nan)
        if is_add:
            b = book[book["Symbol"] == sym].iloc[0]
            name_wt, corr, corr_with = _num(b["Weight%"], 0.0), _num(b.get("Corr_Max"), np.nan), str(b.get("Corr_With", "") or "")
        else:
            name_wt = 0.0
            corr, corr_with = _max_corr(sym, sorted(held))
        blocks = []
        if stage >= 3:
            blocks.append(f"Stage {int(stage)} — no trade")
        if not math.isnan(sec_after) and sec_after > ptg.SECTOR_CAP_PCT:
            blocks.append(f"sector {sec_after:.0f}% > {ptg.SECTOR_CAP_PCT:.0f}%")
        if not is_add and n_open >= ptg.MAX_OPEN_POSITIONS:
            blocks.append(f"book full ({n_open}/{ptg.MAX_OPEN_POSITIONS})")
        # CONCENTRATION PENALTY (points, lower is better): weight already in the name,
        # sector share above 20% after the order, correlation above 0.6 to any holding.
        conc = (name_wt
                + max(0.0, (sec_after if not math.isnan(sec_after) else 0.0) - 20.0)
                + 20.0 * max(0.0, (corr if not math.isnan(corr) else 0.0) - 0.6))
        out.append({
            "Type": "ADD" if is_add else ("NEW · ETF" if etf else "NEW"),
            "Live": "yes" if r.get("_live", True) else "waiting",
            "Symbol": sym, "Tier": tier, "Tabs": "/".join(r["_tfs"]) or "—",
            "S4-GO": r.get("S4-GO", ""), "Stage": stage, "RS": rs, "RRG": (r.get("RRGeng") if isinstance(r.get("RRGeng"), str) else r.get("RRG", "")),
            "Location": loc, "Sector": sec or r.get("Sector", ""),
            "Sector% after": round(sec_after, 1) if not math.isnan(sec_after) else None,
            "Name wt%": round(name_wt, 1), "Max ρ": round(corr, 2) if not math.isnan(corr) else None,
            "ρ with": corr_with, "Conc pts": round(conc, 1), "Overall": _num(r.get("Overall")),
            "Entry": entry, "SL": sl, "Risk%": rk, "Qty": qty, "Amount": round(amount, 0),
            "Blocked": " · ".join(blocks),
        })
    q = pd.DataFrame(out)
    if not q.empty:
        q["_rank"] = q["Overall"].fillna(0) - q["Conc pts"]
        q["_blk"] = q["Blocked"].ne("")
        q["_wait"] = q["Live"].ne("yes")
        q = q.sort_values(["_blk", "_wait", "Tier", "_rank"],
                          ascending=[True, True, True, False]).reset_index(drop=True)
        # funding walk. count_exits on: exits, then the REDUCE/TRIM share, then cash.
        # Off (default): cash only — exit proceeds are not money until the exit is taken.
        cash_v = _num(cash, np.nan)
        pools = ([("exits", exit_now), ("reduce/trim", could)] if count_exits else [])
        pools.append(("cash", cash_v if not math.isnan(cash_v) else np.inf))
        cum, fund = 0.0, []
        for amt, blk, live in zip(q["Amount"], q["Blocked"], q["Live"]):
            if blk or live != "yes":
                fund.append("—")
                continue
            cum += amt
            edge, lab = 0.0, "unfunded"
            for name, size in pools:
                edge += size
                if cum <= edge:
                    lab = name if not (name == "cash" and math.isnan(cash_v)) else "cash (balance unknown)"
                    break
            fund.append(lab)
        q["Funded by"] = fund
        q = q.drop(columns=["_rank", "_blk", "_wait"])
    summary = {"exit_now": exit_now, "could_free": could, "n_adds": int((q["Type"] == "ADD").sum()) if not q.empty else 0,
               "n_new": int((q["Type"] != "ADD").sum()) if not q.empty else 0, "book_n": n_open,
               "capital": capital, "risk_new": risk_new, "risk_add": risk_add,
               "cash": cash, "count_exits": count_exits, "class_src": class_src}
    return {"queue": q, "freed": freed, "summary": summary}


def inr(x) -> str:
    """₹1,23,456 — Indian grouping (house rule for every rupee figure)."""
    v = _num(x)
    if math.isnan(v):
        return "—"
    neg, n = v < 0, int(round(abs(v)))
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = head + "," + tail
    return ("-₹" if neg else "₹") + s


def _hp_label() -> str:
    try:
        import house_policy as hp
        return hp.risk_label()
    except Exception:
        return "house risk"


def render(st, res=None):
    """Streamlit block — the same on the Risk Shield and the board."""
    res = res or build()
    s, q, f = res["summary"], res["queue"], res["freed"]
    st.caption("One queue for the next rupee: today's pyramid ADDs and new GO names on ONE scale. "
               "Ranked by the Reviewer's context ladder (tier A/B/C), then a concentration penalty "
               "(weight already in the name · sector above 20% · correlation above 0.6), then the "
               "board's Overall. Organising tool, not a measured edge: adds and new entries measured "
               "indistinguishable in R (docs/PREREG_add_premise.md), so the choice is made on risk.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash available", inr(s.get("cash")) if s.get("cash") is not None else "unknown")
    c2.metric("Exits + reduce/trim " + ("(counted)" if s.get("count_exits") else "(if taken)"),
              inr(s['exit_now'] + s['could_free']))
    c3.metric("Candidates", f"{s['n_adds']} add · {s['n_new']} new")
    c4.metric("Book", f"{s['book_n']} open", help="Ladder classes: " + str(s.get("class_src", "16:30 snapshot")))
    if q is None or q.empty:
        st.info("Nothing live to fund right now — no ADD-rated holding and no GO / Buy-Trigger-Live name on the boards.")
    else:
        qv = q.copy()
        for c in ("Amount", "Entry", "SL"):
            qv[c] = qv[c].map(inr) if c == "Amount" else qv[c].map(lambda v: f"₹{v:,.2f}" if v < 1000 else inr(v))
        st.dataframe(qv, hide_index=True, use_container_width=True)
        st.caption("Tier A = " + TIER_NOTE["A"] + " · B = " + TIER_NOTE["B"] + " · C = " + TIER_NOTE["C"]
                   + ". Qty sizes at the house risk (" + _hp_label() + ") and the Max ₹/trade cap. "
                   + ("Funding counts EXIT/REDUCE/TRIM proceeds as available." if s.get("count_exits")
                      else "Funding is CASH ONLY — exit proceeds are not counted until you take the exit "
                           "(GM settings → queue_count_exits to change)."))
    if f is not None and not f.empty:
        with st.expander("Where the money comes from — EXIT / REDUCE / TRIM holdings"):
            fv = f.copy()
            for c in ("Value", "Frees"):
                fv[c] = fv[c].map(inr)
            st.dataframe(fv, hide_index=True, use_container_width=True)
