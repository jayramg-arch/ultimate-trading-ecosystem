"""v2_core.py - shared pieces of the v2 system (17-Oct-2026, Doc 41).

The v2 system runs beside the current (trigger) system, through the same plumbing:
  rank board  - data/v2/board.csv, the weekly ranked list (written by p1_paper.py nightly)
  reviewer    - each Friday's buy list is queued on the alert receiver tagged "- v2"; the review
                gets V2 CONTEXT (this module) so it judges EXECUTION, not the selection
  paper       - p1_paper.py books: P1E (rules only, the v2 primary), P1ER (P1E, but skips names the
                reviewer rules WAIT/PASS), and the research controls P1, P1F.
Nothing here places an order with Dhan.
"""
from __future__ import annotations

import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.join(HERE, "data", "v2")
BOARD = os.path.join(V2_DIR, "board.csv")
PRIMARY = "P1E"                  # the v2 system's book; P1/P1F are research controls
REVIEWED = "P1ER"                # P1E filtered by the reviewer
REVIEW_TAG = "v2"
REVIEW_LOG = os.path.join(HERE, "logs", "ai_review_log.csv")


def board() -> pd.DataFrame:
    return pd.read_csv(BOARD) if os.path.exists(BOARD) else pd.DataFrame()


def context(symbol: str) -> str:
    """The V2 CONTEXT block appended to the reviewer's POSITION CONTEXT for a "- v2" review."""
    sym = str(symbol).upper().replace("NSE:", "")
    b = board()
    row = b[b["symbol"] == sym].iloc[0] if (len(b) and (b["symbol"] == sym).any()) else None
    if row is None:
        facts = "not on the current v2 board"
    else:
        facts = ("rank %d of %d eligible · trend-quality score %.2f · weekly action %s · regime %s" % (
            int(row["rank"]), int(row["eligible"]), float(row["score"]), str(row["action"]),
            "UP (Nifty 500 above its 200-day SMA)" if bool(row["regime_up"]) else "DOWN (no new buys)"))
    return (
        "\n\nV2 CONTEXT (this review is for the v2 system, NOT an S4 GO)\n"
        "- %s: %s.\n"
        "- The v2 system (Clenow 'Stocks on the Move', ensemble rank) has ALREADY selected this name on "
        "rules that passed a pre-registered, survivorship-corrected tournament. Do NOT re-litigate the "
        "selection, and do not require an S4 GO, a PA pattern or a demand zone - those are the other "
        "system's rules.\n"
        "- Judge EXECUTION for the coming week only: is buying at the next open sensible (Monday for P1E, Wednesday for the V2H house book)? Name concrete "
        "reasons from the panel: price extended far above the 20-EMA / a vertical last week (wait for a "
        "calmer entry), an earnings date inside the next 5 sessions, a large overhead supply/wall within "
        "1 ATR, a gap or a corporate action that distorts the read, illiquidity.\n"
        "- Ruling meaning for v2: TAKE = buy at the next open as the system plans; WAIT = skip this week, "
        "the system may offer it again at the next rebalance; PASS = skip until it re-qualifies. Default to TAKE "
        "when nothing concrete argues against the entry - the rules, not the panel, chose the name."
    ) % (sym, facts)


def latest_reviews(since: str) -> dict:
    """{SYMBOL: ruling word} from the Reviewer Log for reviews at/after `since` (a date string).
    v2-tagged reviews win over any other review of the same name; otherwise the latest one."""
    if not os.path.exists(REVIEW_LOG):
        return {}
    try:
        L = pd.read_csv(REVIEW_LOG, on_bad_lines="skip")
    except Exception:
        return {}
    L["_ts"] = pd.to_datetime(L.get("ts"), errors="coerce")
    L = L[L["_ts"] >= pd.Timestamp(since)]
    if L.empty:
        return {}
    L["_w"] = L["ai_ruling"].astype(str).str.upper().str.extract(r"(TAKE|WAIT|PASS)")[0]
    L["_v2"] = L.get("source", pd.Series("", index=L.index)).astype(str).str.lower().eq(REVIEW_TAG)
    out = {}
    for sym, g in L.dropna(subset=["_w"]).sort_values(["_v2", "_ts"]).groupby(L["symbol"].astype(str).str.upper()):
        out[sym.replace("NSE:", "")] = g.iloc[-1]["_w"]
    return out


def queue_reviews(symbols: list) -> str:
    """Queue the week's v2 buys on the alert receiver (Daily read), tagged '- v2'."""
    if not symbols:
        return "v2 reviews: no buys this week"
    try:
        import review_many as rm
        if not rm.receiver_up():
            return "v2 reviews: receiver not running - %d buys left unreviewed" % len(symbols)
        bad = rm.post([(s, "D") for s in symbols], tag=REVIEW_TAG)
        return "v2 reviews: %d queued%s" % (len(symbols) - bad, ("; %d failed" % bad) if bad else "")
    except Exception as e:
        return "v2 reviews: not queued (%s)" % e
