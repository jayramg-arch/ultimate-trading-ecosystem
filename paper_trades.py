#!/usr/bin/env python3
"""Paper trades: every TAKE taken the way Jay takes a trade (13-Oct-2026, Jay).

"Assume that we took the trade and start tracking its movements to see whether we are
hitting thesis SL, Hard SL, T1 or T2 - to check how our ecosystem is performing."
"When I take a trade I always use the Commander Risk Allocator: the quantity, two OCO
orders for T1 and T2 and a 3rd single order for the balance. The reviewer may recommend
reduced quantities. It should be tracked like a real trading dashboard, with the
thesis, the current trend, whether the decision was right or wrong, what went well or
wrong, and how to tweak it."

    python paper_trades.py            rebuild data/paper_trades.csv and print the summary

COHORTS  Reviewer TAKE - the AI's FINAL ruling (after every house gate).
         S4 TAKE IT   - S4's own panel VERDICT on the same read, which no gate rewrites.
         One paper position per symbol per cohort: a TAKE while that name's paper trade is
         still open is a repeat, not a second position.
LEVELS   Reviewer: its own R-CHECK plan; S4: the panel's levels. THESIS = S4's INVAL on the
         review's panel. Missing T1/T2 -> the house canon (positional 3R/5R, swing 2R/4R).
SIZE     house_policy.size_qty at the house risk (stock 0.5%, ETF 0.75% of the sizing
         capital, capped at the per-trade rupee cap) - the Risk Allocator's numbers. A
         "TAKE · reduced size" ruling is papered at HALF that risk.
ORDERS   the Risk Allocator's default 3-leg split (house canon, bull_screener.partial_qty_for):
           OCO-1   positional 25% / swing 33% at T1 + the stop
           OCO-2   positional 25% / swing 33% at T2 + the stop
           RUNNER  the balance, stop-only (no target) - exits on the stop or the thesis
         Each target leg gets at least one share while shares remain (Allocator v2.6).
CLOCK    positional on Daily bars; swing on the review's 75m/125m bars (125m for a Daily review).
FILL     the plan entry within ~3 sessions: a buy-limit when the entry is at/below the last
         closed bar's close, else a buy-stop. Gaps fill at the open.
WALK     bar by bar after the fill bar: HARD SL on a touch (gap -> the open), stop-first on a
         bar that reaches both a stop and a target; THESIS on a CLOSE below it (only when it
         sits above the stop) exits every remaining leg at that close; T1/T2 book their OCO.
         The same trades are also walked with the thesis ignored (hard SL only).
REVIEW   every trade carries a post-mortem computed from its own bars, not written by a model:
         the thesis (the review's DECIDING FACTOR / S4's verdict), the trend now (weekly
         stage + trend), right/wrong, what went well / wrong (MFE, wick sweeps, shake-outs,
         recoveries after the exit) and a tweak backed by a counterfactual on the same bars
         (a 4x ATR(D) stop at house size, hard-SL-only vs thesis, a nearer partial).
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
REDUCED_RISK_MULT = 0.5                         # "TAKE · reduced size" = half the house risk
RECOVERY_BARS = 10                              # look-ahead after an exit for a shake-out

COHORTS = {
    # the AI reviewer's FINAL ruling - after every house gate (exposure, flow, index, held)
    "Reviewer TAKE": "reviewer",
    # S4's own panel VERDICT "TAKE IT" on the same read - the mechanical system, which no
    # house gate rewrites. Since 6-Oct the exposure rule has kept the reviewer at WAIT, so
    # this is the cohort that keeps measuring the system in a Bear tape.
    "S4 TAKE IT": "s4",
}


# ── small helpers ───────────────────────────────────────────────────────────
def _ruling_word(s) -> str:
    s = re.sub(r"[*:]", " ", str(s or "")).replace("RULING", " ").strip()
    return (s.split() or [""])[0].upper().strip(",")


def _num(x):
    try:
        v = float(str(x).replace(",", ""))
        return v if v == v and v > 0 else None
    except (TypeError, ValueError):
        return None


def inr(v, dec=0) -> str:
    """₹1,23,456 (Indian grouping), signed when negative."""
    if v is None or v != v:
        return "—"
    neg = v < 0
    s = f"{abs(v):.{dec}f}"
    whole, frac = (s.split(".") + [""])[:2]
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        whole = head + "," + tail
    return ("-₹" if neg else "₹") + whole + ("." + frac if frac else "")


def _review_path(row) -> str:
    p = str(row.get("file") or "")
    return p if os.path.isabs(p) else os.path.join(HERE, p.replace("\\", os.sep))


def _read(p: str) -> str:
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def _s4_verdict(txt: str) -> str:
    m = re.search(r"^VERDICT \| ([^\n]*)", txt, re.M)
    return re.sub(r"\s*│\s*", " · ", m.group(1)).strip(" ·➤") if m else ""


def _deciding(txt: str) -> str:
    m = re.search(r"DECIDING FACTOR[\s:*]*([^\n]+)", txt.split("\n## PANEL READ\n", 1)[0])
    return m.group(1).strip(" *") if m else ""


# ── plan levels ─────────────────────────────────────────────────────────────
def _levels(row, txt: str, prefer_row: bool = False) -> dict:
    """Reviewer cohort: the review's R-CHECK plan, then the log row. S4 cohort (prefer_row):
    the PANEL's levels from the log row first - S4's plan, not the model's edit of it."""
    import s4_take
    d = {"entry": None, "stop": None, "t1": None, "t2": None, "thesis": None,
         "type": "", "setup": "", "src": "", "qty_s4": None}
    if prefer_row:
        for k in ("entry", "stop", "t1", "t2"):
            d[k] = _num(row.get(k))
        if d["entry"] and d["stop"]:
            d["src"] = "S4 panel"
    if txt:
        try:
            pl = s4_take.parse_plan(txt)
            had_panel = bool(d["src"])
            for k in ("entry", "stop", "t1", "t2"):
                if not had_panel or d[k] is None:      # S4 cohort: the file only fills gaps
                    d[k] = pl.get(k)
            d["thesis"], d["setup"], d["qty_s4"] = pl.get("thesis"), pl.get("setup"), pl.get("qty")
            d["type"] = pl.get("type") or ""
            d["src"] = d["src"] or "review"
            import entry_shadow as es
            d["type"] = es._plan_type(_review_path(row)) or d["type"]
        except Exception:
            pass
    for k in ("entry", "stop", "t1", "t2"):
        if d[k] is None:
            d[k] = _num(row.get(k))
            if d[k] is not None and not d["src"]:
                d["src"] = "log row"
    d["type"] = d["type"] or "positional"
    return d


def _canon_fill(lv: dict) -> None:
    """Missing T1/T2 -> the house canon off the plan's own stop (bull_screener.target_r_for)."""
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


def _clock(review_tf: str, plan_type: str) -> str:
    tf = str(review_tf or "").upper().replace("M", "")
    if plan_type == "positional":
        return "D"
    return tf if tf in ("75", "125") else "125"


# ── sizing: the Risk Allocator ──────────────────────────────────────────────
def _split_pct(plan_type: str):
    try:
        import bull_screener as bs
        q = bs.partial_qty_for("POS-BO" if plan_type == "positional" else "SWG-PB")
        return float(q[0]) / 100.0, float(q[1]) / 100.0      # returned in PERCENT (25, 25)
    except Exception:
        return (0.25, 0.25) if plan_type == "positional" else (0.33, 0.33)


def legs(qty: int, plan_type: str) -> tuple[int, int, int]:
    """(OCO-1, OCO-2, runner) shares - Allocator v2.6: floor of the split, each target leg at
    least one share while shares remain, the runner keeps the rest."""
    p1, p2 = _split_pct(plan_type)
    q1, q2 = int(qty * p1), int(qty * p2)
    if qty >= 1 and q1 < 1:
        q1 = 1
    if qty - q1 >= 1 and q2 < 1:
        q2 = 1
    return q1, q2, max(0, qty - q1 - q2)


def size(sym: str, entry: float, stop: float, reduced: bool) -> int:
    """Shares at the house risk and rupee cap (house_policy.size_qty); half on 'reduced'."""
    try:
        import house_policy as hp
        q, _ = hp.size_qty(sym, entry, stop)
        q = int(q or 0)
    except Exception:
        q = 0
    return int(q * REDUCED_RISK_MULT) if reduced else q


# ── the walk ────────────────────────────────────────────────────────────────
def _trail_params(plan_type: str):
    """House Chandelier: (window, multiplier) - positional 22 / 4.5, swing 14 / 1.5."""
    try:
        import house_policy as hp
        if plan_type == "swing":
            return hp.CHANDELIER_WINDOW_SWING, hp.CHANDELIER_MULT["SWG"]
        return hp.CHANDELIER_WINDOW_POS, hp.CHANDELIER_MULT["POS"]
    except Exception:
        return (14, 1.5) if plan_type == "swing" else (22, 4.5)


def _atr_series(df, n):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def simulate(df, fill_pos, entry, stop, t1, t2, thesis, use_thesis, q1, q2, qr,
             trail=None) -> dict:
    """Walk the bars after the fill with the three legs. Returns realised / open rupees, the
    leg outcomes, the exit, MFE/MAE in R and the exit bar.
    trail=(window, mult): the house Chandelier on the clock's bars - highest close since the
    entry (within the window) minus mult x ATR(window), known at the previous bar's close,
    TIGHTEN-ONLY above the initial stop. It is what moves the runner's stop in practice."""
    risk = entry - stop
    cur_stop = stop
    atr_s = _atr_series(df, trail[0]) if trail else None
    qty = q1 + q2 + qr
    o1 = o2 = "pending"
    live = {"oco1": q1, "oco2": q2, "run": qr}
    realised = 0.0
    mfe = mae = 0.0
    res = {"exit": "open", "exit_ts": "", "exit_px": None, "exit_pos": None,
           "t1_hit": "", "t2_hit": ""}
    for j in range(fill_pos + 1, len(df)):
        o, h, l, c = (float(df[k].iloc[j]) for k in ("Open", "High", "Low", "Close"))
        ts = str(df.index[j])[:16]
        mae = min(mae, (l - entry) / risk)
        if trail and j - 1 >= fill_pos:
            w, mult = trail
            anchor = float(df["Close"].iloc[max(fill_pos, j - w):j].max())
            lvl = anchor - mult * float(atr_s.iloc[j - 1])
            if lvl > cur_stop:
                cur_stop = lvl
        if l <= cur_stop:                               # stop-first on a two-way bar
            px = min(o, cur_stop)
            realised += sum(live.values()) * (px - entry)
            for k in live:
                live[k] = 0
            o1 = "stopped" if o1 == "pending" else o1
            o2 = "stopped" if o2 == "pending" else o2
            res.update(exit=("trail SL" if cur_stop > stop else "hard SL"), exit_ts=ts, exit_px=px,
                       exit_pos=j, stop_at_exit=cur_stop)
            break
        mfe = max(mfe, (h - entry) / risk)
        if t1 and live["oco1"] and h >= t1:
            realised += live["oco1"] * (t1 - entry); live["oco1"] = 0
            o1, res["t1_hit"] = "T1 booked", ts
        if t2 and live["oco2"] and h >= t2:
            realised += live["oco2"] * (t2 - entry); live["oco2"] = 0
            o2, res["t2_hit"] = "T2 booked", ts
        if use_thesis and thesis and thesis > stop and c < thesis and sum(live.values()):
            realised += sum(live.values()) * (c - entry)
            for k in live:
                live[k] = 0
            o1 = "thesis exit" if o1 == "pending" else o1
            o2 = "thesis exit" if o2 == "pending" else o2
            res.update(exit="thesis", exit_ts=ts, exit_px=c, exit_pos=j)
            break
        if not sum(live.values()):                      # every leg filled at a target
            res.update(exit="all targets", exit_ts=ts, exit_px=t2, exit_pos=j)
            break
    last = float(df["Close"].iloc[-1])
    open_q = sum(live.values())
    unreal = open_q * (last - entry)
    run_state = ("open" if live["run"] else
                 {"hard SL": "stopped", "trail SL": "trailed out", "thesis": "thesis exit"}.get(res["exit"], "closed"))
    res.update(realised=realised, unrealised=unreal, total=realised + unreal, open_qty=open_q,
               R=(realised + unreal) / (qty * risk) if qty and risk > 0 else None,
               mfe=mfe, mae=mae, oco1=o1, oco2=o2, runner=run_state, last=last, trail_stop=cur_stop)
    return res


# ── the post-mortem ─────────────────────────────────────────────────────────
def _trend_now(sym: str) -> str:
    try:
        import trade_class as tc
        f = tc.daily_facts(sym)
        if not f:
            return ""
        wt = f.get("w_trend")
        try:
            wt = {1: "up", -1: "down", 0: "sideways"}.get(int(round(float(wt))), str(wt))
        except (TypeError, ValueError):
            wt = str(wt or "?").lower()
        return ("Stage %s · weekly %s · %s 200-DMA · %s" % (
            f.get("stage", "?"), wt,
            "below" if f.get("below200") else "above", f.get("asof", "")))
    except Exception:
        return ""


def postmortem(rec: dict, s: dict, sh: dict, df, alt: dict | None) -> dict:
    """Right/wrong, what went well / wrong and a tweak - every line from the trade's own bars."""
    risk = rec["fill_px"] - rec["stop"]
    well, wrong, tweak = [], [], []
    closed = s["exit"] in ("hard SL", "trail SL", "thesis", "all targets")
    R = s["R"] or 0.0
    # post-exit recovery: did price come back after the exit?
    rec_R = None
    if closed and s["exit_pos"] is not None and s["exit"] != "all targets":
        nxt = df.iloc[s["exit_pos"] + 1: s["exit_pos"] + 1 + RECOVERY_BARS]
        if len(nxt):
            rec_R = (float(nxt["High"].max()) - rec["fill_px"]) / risk
    bars_to_exit = (s["exit_pos"] - rec["_fill_pos"]) if s["exit_pos"] is not None else None

    if s["t1_hit"]:
        well.append("T1 paid on OCO-1 (%s)" % s["t1_hit"][:10])
    if s["t2_hit"]:
        well.append("T2 paid on OCO-2 (%s)" % s["t2_hit"][:10])
    if s["mfe"] >= 1.0:
        well.append("ran to +%.1fR at best" % s["mfe"])
    if s["exit"] == "thesis" and sh["total"] < s["total"]:
        well.append("thesis close saved %s vs waiting for the hard SL" % inr(s["total"] - sh["total"]))
    if not closed and R > 0:
        well.append("working: +%.2fR now, above the thesis" % R)

    if closed and bars_to_exit is not None and bars_to_exit <= 3 and s["exit"] != "all targets":
        wrong.append("out within %d bar%s of entry" % (bars_to_exit, "" if bars_to_exit == 1 else "s"))
    if s["exit"] == "trail SL" and s["total"] > 0:
        well.append("the trail locked a winner (%s)" % inr(s["total"]))
    if s["exit"] in ("hard SL", "thesis") and s["mfe"] >= 1.0:
        wrong.append("gave back a +%.1fR open gain" % s["mfe"])
    if s["exit"] == "hard SL" and s["exit_pos"] is not None and float(df["Close"].iloc[s["exit_pos"]]) > rec["stop"]:
        wrong.append("wick sweep: the stop bar closed back above the stop")
    if rec_R is not None and rec_R >= 1.0:
        wrong.append("price recovered to +%.1fR within %d bars of the exit" % (rec_R, RECOVERY_BARS))
    if s["exit"] == "thesis" and sh["total"] > s["total"]:
        wrong.append("the thesis close cost %s vs holding to the hard SL" % inr(sh["total"] - s["total"]))
    if not s["t1_hit"] and rec["t1"]:
        t1R = (rec["t1"] - rec["fill_px"]) / risk
        if s["mfe"] < t1R:
            wrong.append("T1 (%.1fR) never reached - peak +%.1fR" % (t1R, s["mfe"]))
    if rec.get("order") == "stop" and closed and R < 0:
        wrong.append("entered on a buy-stop above the trigger bar")

    # tweaks, each backed by a counterfactual on the same bars
    if alt and alt.get("total") is not None and closed and s["exit"] != "all targets":
        if alt["total"] > s["total"]:
            tweak.append("a 4x ATR(D) stop at house size (%d sh) would have made %s instead of %s"
                         % (alt["qty"], inr(alt["total"]), inr(s["total"])))
    if s["exit"] == "thesis" and sh["total"] > s["total"]:
        tweak.append("let the hard SL decide this one - the thesis close shook it out")
    if not s["t1_hit"] and s["mfe"] >= 1.5 and closed and R < 0:
        tweak.append("move the stop to entry once +1.5R is reached - it reached +%.1fR" % s["mfe"])
    if not closed:
        if R >= 1.0 and s.get("trail_stop", 0) < rec["fill_px"]:
            tweak.append("raise the stop to entry: the trade is +%.1fR (trail still at %s)"
                         % (R, round(s["trail_stop"], 2)))
        elif R < 0:
            tweak.append("hold the plan: exit only on a close below the thesis %s" % (rec["thesis"] or "—"))
    if closed and R < 0 and rec_R is not None and rec_R >= 1.0 and s["exit"] != "thesis":
        tweak.append("stop too tight: price recovered to +%.1fR after the exit - give it the 4x ATR(D) "
                     "stop at house size (smaller qty, same rupee risk)" % rec_R)
    if not tweak and closed and R < 0 and s["mfe"] < 0.5:
        tweak.append("the idea never worked (peak +%.1fR): a selection miss, not management" % s["mfe"])

    if not closed:
        verdict = "🟢 Working" if R >= 0 else "🟠 Under water"
    elif s["total"] > 0:
        verdict = "✅ Right"
    elif s["mfe"] >= 1.0 or (rec_R is not None and rec_R >= 1.0):
        verdict = "⚠️ Right idea, poor exit"
    else:
        verdict = "❌ Wrong"
    return {"verdict": verdict, "went_well": "; ".join(well) or "—",
            "went_wrong": "; ".join(wrong) or "—", "tweak": "; ".join(tweak) or "—",
            "recovery_R": None if rec_R is None else round(rec_R, 2)}


# ── build ───────────────────────────────────────────────────────────────────
def build() -> pd.DataFrame:
    log = pd.read_csv(LOG, on_bad_lines="skip")
    log["_ts"] = pd.to_datetime(log["ts"], errors="coerce")
    log = log.dropna(subset=["_ts"]).sort_values("_ts")
    log["_w"] = log["ai_ruling"].map(_ruling_word)
    log["_txt"] = log.apply(lambda r: _read(_review_path(r)), axis=1)
    rows = []
    for cohort, kind in COHORTS.items():
        if kind == "reviewer":
            sel = log[log["_w"].eq("TAKE")]
        else:
            sel = log[log["_txt"].map(lambda t: "TAKE IT" in _s4_verdict(t).upper())]
        rows += _trade(sel, cohort, kind)
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    out.to_csv(tmp, index=False)
    os.replace(tmp, OUT)
    return out


def _trade(takes: pd.DataFrame, cohort: str, kind: str) -> list:
    import entry_shadow as es
    rows, open_until, trend_cache = [], {}, {}
    for _, r in takes.iterrows():
        sym = str(r["symbol"]).upper().replace("NSE:", "")
        ts = r["_ts"].to_pydatetime()
        txt = r["_txt"]
        ruling = str(r.get("ai_ruling") or "").replace("RULING:", "").strip(" *")
        reduced = kind == "reviewer" and "REDUC" in ruling.upper()
        rec = {"cohort": cohort, "review_ts": str(ts)[:16], "symbol": sym, "review_tf": str(r.get("tf") or ""),
               "ruling": ruling if kind == "reviewer" else "S4: " + _s4_verdict(txt)[:80],
               "reduced": reduced, "file": r.get("file"),
               "thesis_logic": (_deciding(txt) if kind == "reviewer" else _s4_verdict(txt))[:300]}
        if sym in open_until and (open_until[sym] is None or ts <= open_until[sym]):
            rec["status"] = "repeat (paper position open)"
            rows.append(rec); continue
        lv = _levels(r, txt, prefer_row=(kind == "s4"))
        if lv["entry"] and lv["stop"] and lv["entry"] > lv["stop"]:
            _canon_fill(lv)
        rec.update({k: lv[k] for k in ("entry", "stop", "t1", "t2", "thesis", "setup")},
                   plan_type=lv["type"], levels_from=lv["src"])
        if not (lv["entry"] and lv["stop"] and lv["entry"] > lv["stop"]):
            rec["status"] = "no levels"; rows.append(rec); continue
        clock = _clock(r.get("tf"), lv["type"])
        rec["clock"] = clock
        df = es._bars(sym, clock, ts.date())
        g = es._go_pos(df, clock, ts) if (df is not None and not df.empty) else None
        if g is None:
            rec["status"] = "no bars"; rows.append(rec); continue
        go_c = float(df["Close"].iloc[g])
        kind_o = "limit" if lv["entry"] <= go_c else "stop"
        pos, px = es._fill(df, g + 1, g + 1 + FILL_WINDOW[clock], lv["entry"], kind_o)
        if pos is None:
            rec["status"] = "no fill"; rows.append(rec); continue
        stop = lv["stop"]
        rec.update(fill_ts=str(df.index[pos])[:16], fill_px=round(px, 2), order=kind_o, _fill_pos=pos)
        if px <= stop:
            rec["status"] = "gapped through stop"; rows.append(rec); continue
        qty = size(sym, px, stop, reduced)
        if qty < 1:
            rec["status"] = "size 0 (risk cap)"; rows.append(rec); continue
        q1, q2, qr = legs(qty, lv["type"])
        _atr = es._daily_atr(sym, ts.date())
        rec.update(qty=qty, q_oco1=q1, q_oco2=q2, q_runner=qr, invested=round(qty * px),
                   risk_rs=round(qty * (px - stop)),
                   risk_atr_d=round((px - stop) / _atr, 2) if _atr else None,
                   era="after 4xATR floor" if ts.date() >= FLOOR_SINCE else "before floor")
        tr = _trail_params(lv["type"])
        s = simulate(df, pos, px, stop, lv["t1"], lv["t2"], lv["thesis"], True, q1, q2, qr, trail=tr)
        sh = simulate(df, pos, px, stop, lv["t1"], lv["t2"], lv["thesis"], False, q1, q2, qr, trail=tr)
        alt = None
        if _atr and px - 4.0 * _atr < stop:              # counterfactual: the 4x ATR(D) floor
            s4a = px - 4.0 * _atr
            qa = size(sym, px, s4a, reduced)
            if qa >= 1:
                a1, a2, ar = legs(qa, lv["type"])
                R4 = px - s4a
                t1a = px + (lv["t1"] - px) / (px - stop) * R4 if lv["t1"] else None
                t2a = px + (lv["t2"] - px) / (px - stop) * R4 if lv["t2"] else None
                alt = simulate(df, pos, px, s4a, t1a, t2a, lv["thesis"], True, a1, a2, ar, trail=tr)
                alt["qty"] = qa
        closed = s["exit"] != "open"
        rec["trail_stop"] = round(s["trail_stop"], 2)
        rec.update(status=("closed" if closed else "open"),
                   oco1=s["oco1"], oco2=s["oco2"], runner=s["runner"],
                   t1_hit=s["t1_hit"], t2_hit=s["t2_hit"],
                   exit=s["exit"], exit_ts=s["exit_ts"],
                   exit_px=None if s["exit_px"] is None else round(s["exit_px"], 2),
                   last_close=round(s["last"], 2), open_qty=s["open_qty"],
                   pnl_realised=round(s["realised"]), pnl_open=round(s["unrealised"]),
                   pnl_total=round(s["total"]), pnl_pct=round(s["total"] / (qty * px) * 100, 2),
                   R_two_tier=None if s["R"] is None else round(s["R"], 2),
                   pnl_hard_only=round(sh["total"]), exit_hard_only=sh["exit"],
                   R_hard_only=None if sh["R"] is None else round(sh["R"], 2),
                   pnl_4atr=None if not alt else round(alt["total"]),
                   mfe_R=round(s["mfe"], 2), mae_R=round(s["mae"], 2),
                   bars_held=((s["exit_pos"] if closed else len(df) - 1) - pos))
        if sym not in trend_cache:
            trend_cache[sym] = _trend_now(sym)
        rec["trend_now"] = trend_cache[sym]
        rec.update(postmortem(rec, s, sh, df, alt))
        open_until[sym] = (pd.Timestamp(s["exit_ts"]).to_pydatetime() if closed and s["exit_ts"] else None)
        rec.pop("_fill_pos", None)
        rows.append(rec)
    for rr in rows:
        rr.pop("_fill_pos", None)
    return rows


# ── summaries ───────────────────────────────────────────────────────────────
def summary(df: pd.DataFrame) -> dict:
    """Headline numbers for the page and the CLI."""
    if df is None or df.empty or "status" not in df:
        return {}
    t = df[df["status"].isin(["open", "closed"])]
    s = {"takes": len(df), "traded": len(t),
         "open": int((df["status"] == "open").sum()), "closed": int((df["status"] == "closed").sum()),
         "no_fill": int((df["status"] == "no fill").sum()),
         "repeat": int(df["status"].astype(str).str.startswith("repeat").sum()),
         "no_levels": int(df["status"].isin(["no levels", "no bars", "gapped through stop", "size 0 (risk cap)"]).sum())}
    if len(t):
        cl = t[t["status"] == "closed"]
        wins, losses = cl[cl["pnl_total"] > 0]["pnl_total"], cl[cl["pnl_total"] < 0]["pnl_total"]
        s.update(pnl_total=float(t["pnl_total"].sum()), pnl_realised=float(t["pnl_realised"].sum()),
                 pnl_open=float(t["pnl_open"].sum()), pnl_hard_only=float(t["pnl_hard_only"].sum()),
                 invested_open=float(t[t["status"] == "open"]["invested"].sum()),
                 win_rate=float((cl["pnl_total"] > 0).mean()) if len(cl) else None,
                 profit_factor=(float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() else None),
                 avg_win=float(wins.mean()) if len(wins) else None,
                 avg_loss=float(losses.mean()) if len(losses) else None,
                 R_mean=float(t["R_two_tier"].mean()), R_median=float(t["R_two_tier"].median()),
                 R_hard_only_mean=float(t["R_hard_only"].mean()),
                 t1_rate=float((t["t1_hit"].fillna("") != "").mean()),
                 t2_rate=float((t["t2_hit"].fillna("") != "").mean()),
                 thesis_exits=int((t["exit"] == "thesis").sum()),
                 hard_exits=int((t["exit"] == "hard SL").sum()),
                 trail_exits=int((t["exit"] == "trail SL").sum()),
                 median_risk_atr_d=(float(t["risk_atr_d"].median()) if t["risk_atr_d"].notna().any() else None),
                 verdicts=t["verdict"].value_counts().to_dict())
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
        "net P&L ₹": g["pnl_total"].sum().round(0),
        "T1 hit %": g["t1_hit"].apply(lambda x: round(100 * (x.fillna("") != "").mean(), 1)),
        "T2 hit %": g["t2_hit"].apply(lambda x: round(100 * (x.fillna("") != "").mean(), 1)),
        "thesis exits": g["exit"].apply(lambda x: int((x == "thesis").sum())),
        "hard-SL exits": g["exit"].apply(lambda x: int((x == "hard SL").sum())),
        "trail exits": g["exit"].apply(lambda x: int((x == "trail SL").sum())),
        "mean R": g["R_two_tier"].mean().round(2),
        "median R": g["R_two_tier"].median().round(2),
        "mean R (hard only)": g["R_hard_only"].mean().round(2),
        "win %": g["pnl_total"].apply(lambda x: round(100 * (x > 0).mean(), 1)),
        "median stop (xATR D)": g["risk_atr_d"].median().round(2),
    }).reset_index()


def main() -> int:
    df = build()
    s = summary(df)
    print("Paper trades - %s" % OUT)
    for k, v in s.items():
        print("  %-20s %s" % (k, round(v, 3) if isinstance(v, float) else v))
    g = by_group(df.assign(group=df["cohort"].astype(str) + " · " + df.get("era", pd.Series(dtype=str)).fillna("").astype(str)), "group")
    if not g.empty:
        print(chr(10) + g.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
