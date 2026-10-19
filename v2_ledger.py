"""v2_ledger.py - the v2 system's record of ITS shares (18-Oct-2026, Doc 42 §8 D2).

The house keeps ONE journal row and ONE resting stop per holding; journal_sync holds that row's
quantity equal to Dhan's total. v2 may pyramid onto a holding the current system already owns
(Jay, 18-Oct), so v2 cannot use journal rows to know which shares are its own. This ledger is
that record: per symbol, v2's shares, average entry, entry date and the slice's disaster stop,
plus whether the holding is shared with the current system.

    data/v2/real_book.json  {"open": {SYM: {...}}, "closed": [{...}, ...]}

Written by v2_take.py (buys and v2 sells). Reconciled nightly against the journal: a holding
that is no longer OPEN in the journal was sold in full (its one stop fired, or it was exited) -
the slice is closed at the journal's exit price. Nothing here talks to Dhan.
"""
from __future__ import annotations

import datetime as dt
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.environ.get("V2_LEDGER") or os.path.join(HERE, "data", "v2", "real_book.json")   # env: tests


def load() -> dict:
    try:
        with open(LEDGER, encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("open", {})
        d.setdefault("closed", [])
        return d
    except Exception:
        return {"open": {}, "closed": []}


def save(d: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    txt = json.dumps(d, indent=1, default=str)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(LEDGER, txt)
    except Exception:
        with open(LEDGER, "w", encoding="utf-8") as f:
            f.write(txt)


def buy(sym: str, price: float, qty: float, stop: float | None = None, date: str | None = None,
        shared: bool = False) -> dict:
    """Add v2 shares (a new slice, or more of an existing one - averaged entry, first date kept).
    stop None = no stop (v2's rule from 19-Oct-2026: Clenow's exits only)."""
    d = load()
    s = sym.upper()
    q = d["open"].get(s)
    if q:
        tot = q["sh"] + qty
        q["entry"] = (q["entry"] * q["sh"] + price * qty) / tot
        q["sh"] = tot
        if stop:
            q["stop"] = max(float(q.get("stop") or 0), float(stop))
        q["shared"] = bool(q.get("shared")) or shared
    else:
        d["open"][s] = {"sh": float(qty), "entry": float(price), "entry_date": date or dt.date.today().isoformat(),
                        "stop": float(stop) if stop else None, "shared": bool(shared)}
    save(d)
    return d["open"][s]


def sell(sym: str, price: float, qty: float | None = None, date: str | None = None, why: str = "v2 rank") -> dict | None:
    """Close (or reduce) v2's slice. Returns the closed record, None if v2 holds no such slice."""
    d = load()
    s = sym.upper()
    q = d["open"].get(s)
    if not q:
        return None
    n = q["sh"] if qty is None else min(float(qty), q["sh"])
    rec = {"symbol": s, "sh": n, "entry": q["entry"], "entry_date": q["entry_date"], "exit": float(price),
           "exit_date": date or dt.date.today().isoformat(), "why": why, "shared": bool(q.get("shared"))}
    d["closed"].append(rec)
    if n >= q["sh"] - 1e-9:
        d["open"].pop(s)
    else:
        q["sh"] -= n
    save(d)
    return rec


def reconcile(journal) -> list[str]:
    """Close slices whose holding is no longer OPEN in the journal (sold in full - the one stop
    fired, or it was exited), at the journal's exit price. `journal` = the full journal frame
    (symbol, status, quantity, exit_price, exit_date). Returns notes; flags a slice larger than
    the journal's quantity (shares sold that the ledger was not told about)."""
    import pandas as pd
    d = load()
    notes = []
    if not d["open"]:
        return notes
    J = journal.copy()
    J["symbol"] = J["symbol"].astype(str).str.upper()
    op = J[J["status"].astype(str).str.upper() == "OPEN"]
    opq = op.groupby("symbol")["quantity"].sum()
    changed = False
    for s in list(d["open"]):
        q = d["open"][s]
        if s not in opq.index:
            cl = J[(J["symbol"] == s) & (J["status"].astype(str).str.upper() == "CLOSED")]
            cl = cl.sort_values("exit_date") if "exit_date" in cl.columns else cl
            px = float(cl["exit_price"].iloc[-1]) if len(cl) and pd.notna(cl["exit_price"].iloc[-1]) else q["entry"]
            dte = str(cl["exit_date"].iloc[-1]) if len(cl) else dt.date.today().isoformat()
            d["closed"].append({"symbol": s, "sh": q["sh"], "entry": q["entry"], "entry_date": q["entry_date"],
                                "exit": px, "exit_date": dte, "why": "holding closed in the journal", "shared": q.get("shared")})
            d["open"].pop(s)
            notes.append("%s: holding closed in the journal - v2 slice closed at %.2f" % (s, px))
            changed = True
        elif float(opq[s] or 0) + 1e-9 < q["sh"]:
            notes.append("%s: v2 slice %g sh but the journal holds %g - record the sale with v2_take --sell"
                         % (s, q["sh"], float(opq[s])))
    if changed:
        save(d)
    return notes


def realised() -> float:
    return sum((c["exit"] - c["entry"]) * c["sh"] for c in load()["closed"])
