#!/usr/bin/env python3
"""Paper trades: every reviewer TAKE, taken as if you took it (13-Oct-2026, Jay).

"Assume that we took the trade and start tracking its movements to see whether we are
hitting thesis SL, Hard SL, T1 or T2 - to check how our ecosystem is performing."

    python paper_trades.py            rebuild data/paper_trades.csv and print the summary

SOURCE  logs/ai_review_log.csv rows whose final ruling is TAKE (incl. TAKE · REDUCED).
        A ruling the house gates turned into WAIT (exposure, flow, index, held) is not a
        TAKE and is not paper-traded. One paper position per symbol at a time: a TAKE on a
        name whose earlier paper trade is still open is counted as a repeat, not re-entered.
LEVELS  from the review itself (s4_take.parse_plan): the reviewer's own entry / stop and
        the canon T1 / T2 printed by R-CHECK, the THESIS = S4's INVAL on the review's panel.
        Missing that, the panel levels in the log row. No entry or stop -> 'no levels'.
CLOCK   positional -> Daily bars; swing -> the review's 75m/125m bars (125m for a Daily
        review). The same split the house uses for thesis alerts.
FILL    the plan entry within FILL_WINDOW bars after the review: a buy-limit when the entry
        is at/below the last closed bar's close (the retest convention), else a buy-stop.
        Gaps fill at the open. No fill in the window -> 'no fill'.
WALK    bar by bar after the fill bar (the fill bar's own high/low order is unknown):
          HARD SL   low <= stop -> exit at min(open, stop)         (always, both policies)
          THESIS    close < thesis -> exit at that close           (two-tier policy only;
                    only when thesis > stop - a thesis at/below the stop is superseded)
          T1 / T2   high >= level -> that partial books at the level
        A bar that reaches both a stop and a target is scored stop-first (conservative).
PARTIALS house canon via bull_screener.partial_qty_for: positional 25% T1 + 25% T2, swing
        33% + 33%; the rest exits on the stop/thesis or is marked to the last close.
R       every number is in R = (price - entry) / (entry - stop). Two policies side by side:
        TWO-TIER (thesis close OR hard SL) and HARD-ONLY (the resting stop alone) - the same
        trades, so the difference is what the thesis rule is worth.
Display only. Places nothing, reads nothing from Dhan, never touches the journal.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
OUT = os.path.join(HERE, "data", "paper_trades.csv")
FILL_WINDOW = {"D": 3, "75": 8, "125": 5}      # ~3 sessions on every clock
FLOOR_SINCE = dt.date(2026, 10, 3)             # positional stop floor 4x ATR(D) from this session


def _ruling_word(s) -> str:
    s = re.sub(r"[*:]", " ", str(s or "")).replace("RULING", " ").strip()
    return (s.split() or [""])[0].upper().strip(",")


def _num(x):
    try:
        v = float(str(x).replace(",", ""))
        return v if v == v and v > 0 else None
    except (TypeError, ValueError):
        return None


def _levels(row, prefer_row: bool = False) -> dict:
    """Plan levels for one review row. Reviewer cohort: the review file's R-CHECK plan (the
    model's own levels), then the log row. S4 cohort (prefer_row): the PANEL's levels from the
    log row first - S4's plan, not the model's edit of it - then the review file."""
    import s4_take
    d = {"entry": None, "stop": None, "t1": None, "t2": None, "thesis": None,
         "type": "", "setup": "", "src": ""}
    if prefer_row:
        for k in ("entry", "stop", "t1", "t2"):
            d[k] = _num(row.get(k))
        if d["entry"] and d["stop"]:
            d["src"] = "S4 panel"
    p = str(row.get("file") or "")
    p = p if os.path.isabs(p) else os.path.join(HERE, p.replace("\\", os.sep))
    if p and os.path.exists(p):
        try:
            pl = s4_take.parse_plan(open(p, encoding="utf-8", errors="replace").read())
            had_panel = bool(d["src"])
            for k in ("entry", "stop", "t1", "t2"):
                if not had_panel or d[k] is None:      # S4 cohort: the file only fills gaps
                    d[k] = pl.get(k)
            d["thesis"], d["setup"] = pl.get("thesis"), pl.get("setup")
            d["type"] = pl.get("type") or ""
            d["src"] = d["src"] or "review"
            import entry_shadow as es
            d["type"] = es._plan_type(p) or d["type"]
        except Exception:
            pass
    for k in ("entry", "stop", "t1", "t2"):
        if d[k] is None:
            d[k] = _num(row.get(k))
            if d[k] is not None and not d["src"]:
                d["src"] = "log row"
    d["type"] = d["type"] or "positional"
    return d


def _clock(review_tf: str, plan_type: str) -> str:
    tf = str(review_tf or "").upper().replace("M", "")
    if plan_type == "positional":
        return "D"
    return tf if tf in ("75", "125") else "125"


def _partials(plan_type: str):
    try:
        import bull_screener as bs
        q = bs.partial_qty_for("POS-BO" if plan_type == "positional" else "SWG-PB")
        return float(q[0]) / 100.0, float(q[1]) / 100.0      # returned in PERCENT (25, 25)
    except Exception:
        return (0.25, 0.25) if plan_type == "positional" else (0.33, 0.33)


def _walk(df, fill_pos, entry, stop, t1, t2, thesis, use_thesis, q1, q2):
    """Walk bars after the fill. Returns the event record for one policy."""
    risk = entry - stop
    R = lambda px: (px - entry) / risk
    got1 = got2 = False
    ev = {"t1_hit": "", "t2_hit": "", "exit": "", "exit_ts": "", "exit_px": None}
    booked = 0.0
    rest = 1.0
    for j in range(fill_pos + 1, len(df)):
        o, h, l, c = (float(df[k].iloc[j]) for k in ("Open", "High", "Low", "Close"))
        ts = str(df.index[j])[:16]
        if l <= stop:                                   # stop-first on a two-way bar
            px = min(o, stop)
            ev.update(exit="hard SL", exit_ts=ts, exit_px=px)
            return ev, booked + rest * R(px), True
        if t1 and not got1 and h >= t1:
            got1 = True; ev["t1_hit"] = ts; booked += q1 * R(t1); rest -= q1
        if t2 and got1 and not got2 and h >= t2:
            got2 = True; ev["t2_hit"] = ts; booked += q2 * R(t2); rest -= q2
        if use_thesis and thesis and thesis > stop and c < thesis:
            ev.update(exit="thesis", exit_ts=ts, exit_px=c)
            return ev, booked + rest * R(c), True
    last = float(df["Close"].iloc[-1])
    ev.update(exit="open", exit_px=last)
    return ev, booked + rest * R(last), False


COHORTS = {
    # the AI reviewer's FINAL ruling - after every house gate (exposure, flow, index, held)
    "Reviewer TAKE": "reviewer",
    # S4's own panel VERDICT "TAKE IT" on the same read - the mechanical system, which no
    # house gate rewrites. Since 6-Oct the exposure rule has kept the reviewer at WAIT, so
    # this is the cohort that keeps measuring the system in a Bear tape.
    "S4 TAKE IT": "s4",
}


def _s4_verdict(row) -> str:
    p = str(row.get("file") or "")
    p = p if os.path.isabs(p) else os.path.join(HERE, p.replace("\\", os.sep))
    try:
        m = re.search(r"^VERDICT \| ([^\n│]*)", open(p, encoding="utf-8", errors="replace").read(), re.M)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


def _canon_fill(lv: dict) -> None:
    """Missing T1/T2 (older reviews printed no canon line) -> the house canon off the plan's
    own stop: positional 3R/5R, swing 2R/4R (bull_screener.target_r_for)."""
    if lv["t1"] and lv["t2"]:
        return
    try:
        import bull_screener as bs
        r1, r2 = bs.target_r_for("", swing=(lv["type"] == "swing"))
    except Exception:
        r1, r2 = (2.0, 4.0) if lv["type"] == "swing" else (3.0, 5.0)
    R = lv["entry"] - lv["stop"]
    lv["t1"] = lv["t1"] or round(lv["entry"] + r1 * R, 2)
    lv["t2"] = lv["t2"] or round(lv["entry"] + r2 * R, 2)
    lv["src"] = (lv["src"] + " + canon targets").strip(" +")


def build() -> pd.DataFrame:
    log = pd.read_csv(LOG, on_bad_lines="skip")
    log["_ts"] = pd.to_datetime(log["ts"], errors="coerce")
    log = log.dropna(subset=["_ts"]).sort_values("_ts")
    log["_w"] = log["ai_ruling"].map(_ruling_word)
    rows = []
    for cohort, kind in COHORTS.items():
        if kind == "reviewer":
            sel = log[log["_w"].eq("TAKE")]
        else:
            v = log.apply(_s4_verdict, axis=1)
            sel = log[v.str.contains("TAKE IT", case=False, na=False)]
        rows += _trade(sel, cohort, kind)
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    out.to_csv(tmp, index=False)
    os.replace(tmp, OUT)
    return out


def _trade(takes: pd.DataFrame, cohort: str, kind: str) -> list:
    import entry_shadow as es
    rows, open_until = [], {}
    for _, r in takes.iterrows():
        sym = str(r["symbol"]).upper().replace("NSE:", "")
        ts = r["_ts"].to_pydatetime()
        rec = {"cohort": cohort, "review_ts": str(ts)[:16], "symbol": sym, "review_tf": str(r.get("tf") or ""),
               "ruling": str(r.get("ai_ruling") or "").replace("RULING:", "").strip(" *"),
               "file": r.get("file")}
        if sym in open_until and (open_until[sym] is None or ts <= open_until[sym]):
            rec["status"] = "repeat (paper position open)"
            rows.append(rec); continue
        lv = _levels(r, prefer_row=(kind == "s4"))
        if lv["entry"] and lv["stop"] and lv["entry"] > lv["stop"]:
            _canon_fill(lv)
        rec.update({k: lv[k] for k in ("entry", "stop", "t1", "t2", "thesis")},
                   plan_type=lv["type"], levels_from=lv["src"])
        if not (lv["entry"] and lv["stop"] and lv["entry"] > lv["stop"]):
            rec["status"] = "no levels"; rows.append(rec); continue
        clock = _clock(r.get("tf"), lv["type"])
        rec["clock"] = clock
        df = es._bars(sym, clock, ts.date())
        if df is None or df.empty:
            rec["status"] = "no bars"; rows.append(rec); continue
        g = es._go_pos(df, clock, ts)
        if g is None:
            rec["status"] = "no bars"; rows.append(rec); continue
        go_c = float(df["Close"].iloc[g])
        kind = "limit" if lv["entry"] <= go_c else "stop"
        pos, px = es._fill(df, g + 1, g + 1 + FILL_WINDOW[clock], lv["entry"], kind)
        if pos is None:
            rec["status"] = "no fill"
            rows.append(rec); continue
        rec.update(fill_ts=str(df.index[pos])[:16], fill_px=round(px, 2), order=kind)
        stop = lv["stop"]
        if px <= stop:
            rec["status"] = "gapped through stop"; rows.append(rec); continue
        _atr = es._daily_atr(sym, ts.date())
        rec["risk_atr_d"] = round((px - stop) / _atr, 2) if _atr else None
        rec["era"] = "after 4xATR floor" if ts.date() >= FLOOR_SINCE else "before floor"
        q1, q2 = _partials(lv["type"])
        ev2, r2, done2 = _walk(df, pos, px, stop, lv["t1"], lv["t2"], lv["thesis"], True, q1, q2)
        evh, rh, doneh = _walk(df, pos, px, stop, lv["t1"], lv["t2"], lv["thesis"], False, q1, q2)
        rec.update(status=("closed" if done2 else "open"),
                   t1_hit=ev2["t1_hit"], t2_hit=ev2["t2_hit"],
                   exit=ev2["exit"], exit_ts=ev2["exit_ts"], exit_px=round(ev2["exit_px"], 2),
                   R_two_tier=round(r2, 2),
                   exit_hard_only=evh["exit"], R_hard_only=round(rh, 2),
                   last_close=round(float(df["Close"].iloc[-1]), 2),
                   bars_held=len(df) - 1 - pos)
        # one paper position per symbol: it stays "open" until its two-tier exit
        open_until[sym] = (pd.Timestamp(ev2["exit_ts"]).to_pydatetime() if done2 and ev2["exit_ts"] else None)
        rows.append(rec)
    return rows


def summary(df: pd.DataFrame) -> dict:
    """Headline numbers for the page and the CLI. R only, never rupees."""
    if df is None or df.empty or "status" not in df:
        return {}
    traded = df[df["status"].isin(["open", "closed"])]
    s = {"takes": len(df), "traded": len(traded),
         "open": int((df["status"] == "open").sum()), "closed": int((df["status"] == "closed").sum()),
         "no_fill": int((df["status"] == "no fill").sum()),
         "repeat": int(df["status"].astype(str).str.startswith("repeat").sum()),
         "no_levels": int(df["status"].isin(["no levels", "no bars", "gapped through stop"]).sum())}
    if len(traded):
        s.update(t1_rate=float((traded["t1_hit"].fillna("") != "").mean()),
                 t2_rate=float((traded["t2_hit"].fillna("") != "").mean()),
                 thesis_exits=int((traded["exit"] == "thesis").sum()),
                 hard_exits=int((traded["exit"] == "hard SL").sum()),
                 hard_only_stops=int((traded["exit_hard_only"] == "hard SL").sum()),
                 R_two_tier_mean=float(traded["R_two_tier"].mean()),
                 R_two_tier_median=float(traded["R_two_tier"].median()),
                 R_hard_only_mean=float(traded["R_hard_only"].mean()),
                 R_hard_only_median=float(traded["R_hard_only"].median()),
                 win_two_tier=float((traded["R_two_tier"] > 0).mean()))
        cl = traded[traded["status"] == "closed"]
        s["R_closed_mean"] = float(cl["R_two_tier"].mean()) if len(cl) else None
        s["median_risk_atr_d"] = float(traded["risk_atr_d"].median()) if "risk_atr_d" in traded else None
    return s


def by_group(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """The headline numbers split by one column (era, plan type, clock)."""
    t = df[df["status"].isin(["open", "closed"])] if df is not None and not df.empty else pd.DataFrame()
    if t.empty or col not in t:
        return pd.DataFrame()
    g = t.groupby(col)
    return pd.DataFrame({
        "trades": g.size(),
        "open": g["status"].apply(lambda x: int((x == "open").sum())),
        "T1 hit %": g["t1_hit"].apply(lambda x: round(100 * (x.fillna("") != "").mean(), 1)),
        "T2 hit %": g["t2_hit"].apply(lambda x: round(100 * (x.fillna("") != "").mean(), 1)),
        "thesis exits": g["exit"].apply(lambda x: int((x == "thesis").sum())),
        "hard-SL exits": g["exit"].apply(lambda x: int((x == "hard SL").sum())),
        "mean R (two-tier)": g["R_two_tier"].mean().round(2),
        "median R (two-tier)": g["R_two_tier"].median().round(2),
        "mean R (hard only)": g["R_hard_only"].mean().round(2),
        "win %": g["R_two_tier"].apply(lambda x: round(100 * (x > 0).mean(), 1)),
        "median stop (xATR D)": g["risk_atr_d"].median().round(2),
    }).reset_index()


def main() -> int:
    df = build()
    s = summary(df)
    print("Paper trades (reviewer TAKEs) - %s" % OUT)
    for k, v in s.items():
        print("  %-20s %s" % (k, round(v, 3) if isinstance(v, float) else v))
    g = by_group(df.assign(group=df["cohort"].astype(str) + " · " + df["era"].fillna("").astype(str)), "group")
    if not g.empty:
        print("\n" + g.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
