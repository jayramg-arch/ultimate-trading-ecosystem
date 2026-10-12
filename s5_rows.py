"""Fit S5's footprint row height to the stock on the chart (12-Oct-2026, Jay).

WHY: S5 reads order flow from footprint ROWS, and the row height ('Ticks per volume row',
default 200 ticks) is one fixed number per chart - Pine needs a compile-time constant, so S5
cannot size it per stock itself. At 200 ticks a TVSMOTOR 125m bar spans ~3 rows (S5 said
"ROWS TOO COARSE"), and with 3 rows stacked imbalances, trapped zones and big rows cannot
exist. This sets the input from outside, while S5 runs (no recompile):

    ticks = round( ATR14(chart TF) / ROWS_PER_ATR / tick size )

so a typical bar spans ~ROWS_PER_ATR rows. ATR is computed in the page from the chart's own
bars (Wilder, same as S5's ta.atr); the tick size comes from Dhan's scrip master, because
NSE ticks vary with price (0.01 below Rs 250 up to Rs 5 above Rs 20,000) and the widget API
does not expose it.

Used by: s4_review (the reviewer's own S5 tab, before every read) and SET_S5_ROWS.bat
(your S5 tabs - the reviewer tabs are left alone unless --all).

    python s5_rows.py            fit every S5 tab that is NOT a reviewer tab
    python s5_rows.py --all      every S5 tab, reviewer tabs included
    python s5_rows.py --check    show what each tab has and would get, change nothing
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROWS_PER_ATR = 10          # a typical bar ~ this many footprint rows
TICKS_MIN, TICKS_MAX = 1, 5000      # S5's input bounds
REFIT_TOL = 0.15           # leave the input alone within +/-15% of the target
INPUT_TITLE = "Ticks per volume row"
SCRIP = os.path.join(HERE, "data", "dhan_scrip_master.csv")


@lru_cache(maxsize=1)
def _ticks_table() -> dict:
    out = {}
    try:
        with open(SCRIP, encoding="utf-8", errors="ignore") as fh:
            for r in csv.DictReader(fh):
                if r.get("SEM_EXM_EXCH_ID") == "NSE" and r.get("SEM_SEGMENT") == "E":
                    try:
                        out[r["SEM_TRADING_SYMBOL"].strip().upper()] = float(r["SEM_TICK_SIZE"]) / 100.0
                    except (TypeError, ValueError, KeyError):
                        pass
    except FileNotFoundError:
        pass
    return out


def tick_size(tv_symbol: str) -> float | None:
    """Rupee tick for an NSE chart symbol ('NSE:BAJAJ_AUTO' -> BAJAJ-AUTO). None if unknown."""
    s = str(tv_symbol).split(":")[-1].strip().upper()
    t = _ticks_table()
    return t.get(s) or t.get(s.replace("_", "-")) or t.get(s.replace("_", "&"))


def target_ticks(atr: float, tick: float) -> int | None:
    if not atr or not tick or atr <= 0 or tick <= 0:
        return None
    return int(max(TICKS_MIN, min(TICKS_MAX, round(atr / ROWS_PER_ATR / tick))))


READ_JS = r"""
(function () {
  try {
    var c = (window.TradingViewApi || window.tvWidget).activeChart();
    var st = c.getAllStudies(), id = null;
    st.forEach(function (s) { if (s.name.indexOf("S5 Analysis Panel") === 0) id = s.id; });
    if (!id) return JSON.stringify({s5: false});
    var s5 = c.getStudyById(id), tid = null, cur = null;
    s5.getInputsInfo().forEach(function (i) { if (i.name === %(title)s) tid = i.id; });
    s5.getInputValues().forEach(function (x) { if (x.id === tid) cur = x.value; });
    // ATR14, Wilder, from the chart's own bars (the last 150 are plenty)
    var b = c.getSeries().data().bars(), li = b.lastIndex(), fi = Math.max(b.firstIndex(), li - 150);
    var atr = null, prevC = null, n = 0, sum = 0;
    for (var i = fi; i <= li; i++) {
      var v = b.valueAt(i); if (!v) continue;
      var h = v[2], l = v[3], cl = v[4];
      var tr = prevC == null ? h - l : Math.max(h - l, Math.abs(h - prevC), Math.abs(l - prevC));
      if (n < 14) { sum += tr; n++; if (n === 14) atr = sum / 14; }
      else atr = (atr * 13 + tr) / 14;
      prevC = cl;
    }
    return JSON.stringify({s5: true, sym: c.symbol(), res: c.resolution(), atr: atr, ticks: cur, tid: tid});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""

SET_JS = r"""
(function () {
  try {
    var c = (window.TradingViewApi || window.tvWidget).activeChart();
    var id = null; c.getAllStudies().forEach(function (s) { if (s.name.indexOf("S5 Analysis Panel") === 0) id = s.id; });
    if (!id) return JSON.stringify({error: "no S5"});
    var s5 = c.getStudyById(id);
    s5.setInputValues([{id: %(tid)s, value: %(val)d}]);
    var got = null; s5.getInputValues().forEach(function (x) { if (x.id === %(tid)s) got = x.value; });
    return JSON.stringify({got: got});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


def fit(targets: list, apply: bool = True) -> list[dict]:
    """Fit every S5 found on `targets` (CDP chart targets). Returns one dict per tab with an
    S5: sym, res, atr, tick, cur, want, changed, note. Never raises for a single tab."""
    from tv_gm_alerts import _eval
    out = []
    for t in targets:
        try:
            r = json.loads(_eval(t["webSocketDebuggerUrl"], READ_JS % {"title": json.dumps(INPUT_TITLE)}) or "{}")
        except Exception as e:
            out.append({"tab": t.get("url", "")[-10:], "note": "read failed: %s" % e}); continue
        if not r.get("s5"):
            continue
        tick = tick_size(r.get("sym", ""))
        want = target_ticks(r.get("atr"), tick)
        row = {"tab": t.get("url", "").rstrip("/").split("/")[-1], "sym": r.get("sym"), "res": r.get("res"),
               "atr": r.get("atr"), "tick": tick, "cur": r.get("ticks"), "want": want, "changed": False, "note": ""}
        if want is None:
            row["note"] = "no tick size for this symbol (index or unknown) - left alone"
        elif r.get("ticks") and abs(want - r["ticks"]) <= REFIT_TOL * r["ticks"]:
            row["note"] = "already fits"
        elif apply:
            try:
                g = json.loads(_eval(t["webSocketDebuggerUrl"], SET_JS % {"tid": json.dumps(r["tid"]), "val": want}) or "{}")
                row["changed"] = g.get("got") == want
                row["note"] = "set" if row["changed"] else "read back %s" % g
            except Exception as e:
                row["note"] = "set failed: %s" % e
        else:
            row["note"] = "would set"
        out.append(row)
    return out


def _review_layouts() -> set:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass
    return {x.strip() for x in (os.getenv("S4_REVIEW_CHARTS") or "").split(",") if x.strip()}


def main() -> int:
    ap = argparse.ArgumentParser(description="Fit S5's footprint row height to each chart's stock")
    ap.add_argument("--all", action="store_true", help="include the reviewer's own tabs")
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    a = ap.parse_args()
    from tv_bind_s4 import _chart_targets_all
    tabs = _chart_targets_all()
    if not tabs:
        print("ERROR: no TradingView chart tab over CDP - is TradingView running with the debug port?")
        return 2
    rev = _review_layouts()
    if not a.all:
        tabs = [t for t in tabs if not any(r in t.get("url", "") for r in rev)]
    rows = fit(tabs, apply=not a.check)
    if not rows:
        print("no S5 on the selected tab(s)")
        return 1
    for r in rows:
        if "sym" not in r:
            print("  %s: %s" % (r["tab"], r["note"])); continue
        print("  %-10s %-18s %-4s ATR %s · tick %s · rows %s -> %s  [%s]" % (
            r["tab"], r["sym"], r["res"], "%.2f" % r["atr"] if r["atr"] else "?",
            r["tick"], r["cur"], r["want"], r["note"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
