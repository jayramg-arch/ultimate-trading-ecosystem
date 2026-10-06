"""open_risk.py - the book's open risk against a regime budget, with a trim plan (7-Oct-2026, Jay).

WHY: Jay's concern is capital protection and large drawdowns. What sets the size of a
drawdown is not any one stop, it is the rupees the WHOLE book loses if every resting stop
is hit. On 6 Oct that was ₹2.16L (7.2% of the ₹30L sizing capital) in a Bear/Cash tape,
while the old Portfolio Heat card read "WITHIN BUDGET": its budget was 0.5% x the NUMBER of
positions, so every position added raised its own ceiling. Here the budget is a fixed slice
of capital that shrinks with the regime:

    HEAT_BUDGET_PCT (house_policy)   OPEN 6%   ·   NEUTRAL 3%   ·   BEAR 3%
    (BEAR was proposed at 1.5%; Jay set it equal to NEUTRAL on 7-Oct-2026.)

The circuit breaker counts as BEAR. The tier comes from house_policy.exposure_status (the
same Option-A reading the order gate and the reviewer use).

TWO NUMBERS PER POSITION, both from the RESTING Dhan stops (the legs Risk Shield reads):
  * risk from LTP   = sum over stop legs of qty x (LTP - stop). What the book gives back if
                      every stop fills, open profit included. This is the drawdown number
                      and the one the budget is measured on.
  * capital at risk = sum over stop legs of qty x max(entry - stop, 0). Money below cost.
                      A stop at/above entry is LOCKED - zero capital at risk.
Shares with no resting stop are counted and flagged (their risk is unbounded).

THE TRIM PLAN (advisory, never an order): when risk from LTP is over budget, it proposes
SHARE trims - the stops stay where they are, which is the point: a wide stop is fine when
the quantity comes down with it. Order of trimming:
  0  swing trades NOT ELIGIBLE to convert that are under water (trade_class)
  1  positional holdings on EXIT REVIEW, or on WATCH while under water
  2  SALVAGE-only swings
  3  any other position under water
  4  winners whose stop is still below entry
  5  locked winners (stop at/above entry) - last; their risk is only open profit
Within a class the largest rupee risk goes first. Each name is trimmed only by the shares
needed to close the remaining gap.
"""
from __future__ import annotations

import math

import pandas as pd

CLASS_LABEL = {0: "swing · not convertible · losing", 1: "positional · exit review / losing watch",
               2: "swing · salvage only", 3: "losing", 4: "winner · stop below entry",
               5: "winner · stop locked"}


def budget() -> dict:
    """{'tier', 'pct', 'rupees', 'capital', 'cap_src', 'breaker'} from house_policy."""
    import house_policy as hp
    cap, src = hp.sizing_capital()
    try:
        e = hp.exposure_status()
        tier = e.get("tier") or "BEAR"
        breaker = bool(e.get("pause_until"))
    except Exception:
        tier, breaker = "BEAR", False           # unknown reads as the tightest budget
    if breaker:
        tier_b = "BEAR"
    else:
        tier_b = tier if tier in hp.HEAT_BUDGET_PCT else "BEAR"
    pct = hp.HEAT_BUDGET_PCT[tier_b]
    return {"tier": tier, "budget_tier": tier_b, "pct": pct, "rupees": cap * pct / 100.0,
            "capital": cap, "cap_src": src, "breaker": breaker}


def position_risk(sell_gtts_by_symbol: dict, single_sells: list, ltps: dict,
                  journal: pd.DataFrame) -> pd.DataFrame:
    """One row per held symbol. `journal` = OPEN rows with symbol, quantity, buy_price,
    timeframe. Legs: OCO dicts with sl_trigger / sl_qty|qty; singles with trigger / qty."""
    legs: dict[str, list[tuple[float, float]]] = {}
    for sym, orders in (sell_gtts_by_symbol or {}).items():
        for o in orders or []:
            sl = o.get("sl_trigger")
            q = o.get("sl_qty") or o.get("qty") or 0
            if sl and q:
                legs.setdefault(str(sym).upper(), []).append((float(q), float(sl)))
    for s in single_sells or []:
        if s.get("trigger") and s.get("qty"):
            legs.setdefault(str(s["symbol"]).upper(), []).append((float(s["qty"]), float(s["trigger"])))

    j = journal.copy()
    j["symbol"] = j["symbol"].astype(str).str.upper().str.strip()
    j = j.groupby("symbol", as_index=False).agg(
        qty=("quantity", "sum"), entry=("buy_price", "mean"), timeframe=("timeframe", "first"))
    rows = []
    for r in j.itertuples():
        ltp = float((ltps or {}).get(r.symbol) or (ltps or {}).get(r.symbol.replace("&", "_")) or 0.0)
        lg = legs.get(r.symbol, [])
        cov = sum(q for q, _ in lg)
        risk_ltp = sum(q * max(ltp - sl, 0.0) for q, sl in lg) if ltp else float("nan")
        risk_cap = sum(q * max(float(r.entry or 0) - sl, 0.0) for q, sl in lg)
        stop = (sum(q * sl for q, sl in lg) / cov) if cov else float("nan")
        rows.append({
            "symbol": r.symbol, "timeframe": r.timeframe or "", "qty": float(r.qty or 0),
            "covered": cov, "uncovered": max(float(r.qty or 0) - cov, 0.0),
            "entry": float(r.entry or 0), "ltp": ltp, "stop": stop,
            "stop_pct": (stop / ltp - 1) * 100 if (ltp and cov) else float("nan"),
            "risk_ltp": risk_ltp, "risk_cap": risk_cap,
            "locked": bool(cov and stop >= float(r.entry or 0)),
            "pnl_pct": (ltp / float(r.entry) - 1) * 100 if (ltp and r.entry) else float("nan"),
        })
    return pd.DataFrame(rows)


def trim_class(row, tc_action: str | None) -> int:
    a = str(tc_action or "")
    losing = row["ltp"] and row["ltp"] < row["entry"]
    if a == "NOT ELIGIBLE" and losing:
        return 0
    if a == "EXIT REVIEW" or (a == "WATCH" and losing):
        return 1                       # a WINNER on watch (e.g. ATR just over 4%) is not trimmed first
    if a.startswith("SALVAGE"):
        return 2
    if losing:
        return 3
    return 5 if row["locked"] else 4


def trim_plan(df: pd.DataFrame, budget_rs: float, tc_actions: dict | None = None) -> pd.DataFrame:
    """Rows to trim (share counts) so risk from LTP <= budget_rs. Stops unchanged."""
    if df.empty:
        return df.assign(cls=[], trim=[], risk_after=[])
    d = df.copy()
    d["cls"] = [trim_class(r, (tc_actions or {}).get(r["symbol"])) for _, r in d.iterrows()]
    d["per_share"] = (d["risk_ltp"] / d["covered"]).where(d["covered"] > 0, 0.0).fillna(0.0)
    d["trim"] = 0
    excess = float(d["risk_ltp"].fillna(0).sum()) - float(budget_rs)
    for i in d.sort_values(["cls", "risk_ltp"], ascending=[True, False]).index:
        if excess <= 0:
            break
        ps = d.at[i, "per_share"]
        if not ps or ps <= 0:
            continue
        n = min(int(d.at[i, "covered"]), int(math.ceil(excess / ps)))
        d.at[i, "trim"] = n
        excess -= n * ps
    d["risk_after"] = d["risk_ltp"].fillna(0) - d["trim"] * d["per_share"]
    d["class"] = d["cls"].map(CLASS_LABEL)
    return d


def summary(df: pd.DataFrame, b: dict) -> dict:
    tot = float(df["risk_ltp"].fillna(0).sum()) if not df.empty else 0.0
    cap = b["capital"] or 0.0
    return {"risk_ltp": tot, "risk_ltp_pct": tot / cap * 100 if cap else float("nan"),
            "risk_cap": float(df["risk_cap"].sum()) if not df.empty else 0.0,
            "over": tot - b["rupees"], "uncovered": df.loc[df["uncovered"] > 0, "symbol"].tolist() if not df.empty else [],
            "no_ltp": df.loc[df["ltp"] <= 0, "symbol"].tolist() if not df.empty else []}


def render(st, sell_gtts_by_symbol, single_sells, ltps, inr) -> None:
    """Risk Shield headline card + expander. `inr` = the page's ₹ formatter."""
    import trade_class as tc
    b = budget()
    try:
        jr = tc.open_positions()
    except Exception as e:
        st.warning(f"🔥 Open risk: journal unreadable ({e})")
        return
    df = position_risk(sell_gtts_by_symbol, single_sells, ltps, jr)
    s = summary(df, b)
    over = s["over"] > 0
    col = "var(--bear)" if over else "var(--bull)"
    tier_txt = f"{b['tier']}" + (" · circuit breaker → BEAR budget" if b["breaker"] else "")
    st.markdown(
        f"<div style='background:linear-gradient(145deg, var(--surface-2) 0%, var(--surface-3) 100%);"
        f"border:1.5px solid {col};border-radius:10px;padding:12px 16px;margin:4px 0 8px;font-size:0.9rem;"
        f"color: var(--ink-2);box-shadow:0 4px 16px rgba(0,0,0,0.2);'>"
        f"🔥 <b>Open risk:</b> ₹{inr(s['risk_ltp'])} ({s['risk_ltp_pct']:.1f}% of ₹{inr(b['capital'])}) if every "
        f"resting stop fills, vs the <b>{b['pct']:g}%</b> budget for a {tier_txt} tape = ₹{inr(b['rupees'])} — "
        f"<b style='color:{col}'>{'OVER by ₹' + inr(s['over']) + ' 🚨' if over else 'WITHIN BUDGET ✅'}</b>"
        f"<br><span style='font-size:0.8rem;color:var(--muted);'>Capital below cost at risk: ₹{inr(s['risk_cap'])} "
        f"(the rest is open profit the stops would give back). Budget OPEN 6% · NEUTRAL 3% · BEAR 3% of the "
        f"sizing capital (house_policy.HEAT_BUDGET_PCT).</span></div>",
        unsafe_allow_html=True)
    if s["uncovered"]:
        st.error("Shares with NO resting stop (risk unbounded, not in the total): " + ", ".join(s["uncovered"]))
    if s["no_ltp"]:
        st.caption("No live LTP, excluded from the total: " + ", ".join(s["no_ltp"]))

    with st.expander("Open-risk plan — per position, and the trims that fit the budget", expanded=over):
        acts = {}
        try:
            book = st.session_state.get("_or_tc_book")
            if book is None:
                book = tc.review_book()
                st.session_state["_or_tc_book"] = book
            acts = dict(zip(book["symbol"], book["action"]))
        except Exception as e:
            st.caption(f"trade_class verdicts unavailable ({e}); trims ranked on P&L and stop only")
        p = trim_plan(df, b["rupees"], acts)
        if p.empty:
            st.info("No open positions.")
            return
        view = p.sort_values(["cls", "risk_ltp"], ascending=[True, False])
        view = view.assign(**{
            "risk ₹": view["risk_ltp"].round(0), "below-cost ₹": view["risk_cap"].round(0),
            "stop %": view["stop_pct"].round(1), "P&L %": view["pnl_pct"].round(1),
            "after ₹": view["risk_after"].round(0)})
        st.dataframe(view[["symbol", "timeframe", "class", "qty", "ltp", "stop", "stop %", "P&L %",
                           "risk ₹", "below-cost ₹", "trim", "after ₹"]],
                     width="stretch", hide_index=True)
        t = view[view["trim"] > 0]
        if over and not t.empty:
            st.markdown("**To fit the budget, sell these shares on Dhan and leave the stops where they are:** "
                        + " · ".join(f"{r.symbol} {int(r.trim)}" for r in t.itertuples())
                        + f" — frees ₹{inr(float((t['risk_ltp'] - t['risk_after']).sum()))} of risk.")
            st.caption("Advisory. Order: swing trades that cannot convert and are losing → positional on exit "
                       "review/watch → salvage-only swings → other losers → winners with the stop below entry → "
                       "locked winners. After each sale, resize that holding's stop legs to the remaining "
                       "quantity (one price, full cover). Doc 25 Part 7c.")
        elif not over:
            st.caption("Within budget - no trim needed. The order above is the one a trim would follow.")
