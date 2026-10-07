"""tv_push_v67_trail.py — keep v67 current with no paste and no compile (4-Oct-2026).

Two pushes, both over the debug port into v67's inputs on every chart tab:
  1. SLOTS: the 25 portfolio slots Sync to TV writes into the Pine file
     (db_portfolio_sync.build_slots - same values). A Trail SL you typed on the chart is
     kept while the slot holds the same ticker. --no-slots skips this.
  2. CHANDELIER BOOK: Risk Shield's trail per holding (below).

Put Risk Shield's Chandelier on v67's chart line.

Jay trails his stops off v67's "ALGO Chandelier TSL" line, so that line must be the
Risk Shield number. v67 cannot see the journal (trade type, setup, overrides) or the
house regime score, so this script computes each holding's trail with the SAME function
Risk Shield calls (risk_common.holding_chandelier) and pushes the result into v67's
"Chandelier book" input on every chart tab:

    SYM=window,multiplier,floor;SYM=...      floor: 0 · <price> (Floor) · E<price> (Exact)

v67 then draws highest-close(window) − Wilder-ATR(window) × multiplier on its own live
bars, with the floor applied — identical inputs, identical formula. Nothing is compiled.

    python tv_push_v67_trail.py            compute + push + read back
    python tv_push_v67_trail.py --check    print the book and what each tab holds now
    python tv_push_v67_trail.py --dry-run  compute and print only
    python tv_push_v67_trail.py --snapshot save every v67 setting (every push also saves one)
    python tv_push_v67_trail.py --restore  after a v67 compile: put back settings it shifted
                                           (AFTER_COMPILE.bat passes this)

Runs nightly in the auto-pilot (Phase 12f) and from AFTER_COMPILE.bat. Needs TradingView
started with the debug port.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

INPUT_TITLE = "Chandelier book (pushed by Python - do not edit)"
V67_PREFIX = "Weinstein & Swing Pro Dashboard"

JS = r"""
(function () {
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var st = chart.getAllStudies(); var id = null;
    for (var i = 0; i < st.length; i++) if (st[i].name.indexOf(%(prefix)s) === 0) { id = st[i].id; break; }
    if (!id) return JSON.stringify({none: 1});
    var v = chart.getStudyById(id); var iid = null;
    v.getInputsInfo().forEach(function (x) { if (x.name === %(title)s) iid = x.id; });
    if (!iid) return JSON.stringify({error: "input not found - compile v67.4.26 first"});
    var want = %(want)s;
    if (want !== null) v.setInputValues([{id: iid, value: want}]);
    var got = ""; v.getInputValues().forEach(function (x) { if (x.id === iid) got = String(x.value); });
    return JSON.stringify({got: got});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


SLOTS_JS = r"""
(function () {
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var st = chart.getAllStudies(); var id = null;
    for (var i = 0; i < st.length; i++) if (st[i].name.indexOf(%(prefix)s) === 0) { id = st[i].id; break; }
    if (!id) return JSON.stringify({none: 1});
    var v = chart.getStudyById(id); var info = v.getInputsInfo();
    var cur = {}; v.getInputValues().forEach(function (x) { cur[x.id] = x.value; });
    var slots = %(slots)s; var want = []; var bad = [];
    var NAMES = ["Entry", "SL", "Trail SL", "T1", "T2", "Sector", "Date"];
    slots.forEach(function (s) {
      var k = -1;
      for (var j = 0; j < info.length; j++) if (info[j].name === "Slot " + s.i) { k = j; break; }
      if (k < 0) { bad.push("Slot " + s.i + " missing"); return; }
      for (var q = 0; q < 7; q++) if (!info[k + 1 + q] || info[k + 1 + q].name !== NAMES[q]) { bad.push("Slot " + s.i + " layout"); return; }
      var tslId = info[k + 3].id;
      // the Trail SL you typed on the chart wins while the slot holds the same ticker
      var tsl = (String(cur[info[k].id]).toUpperCase() === s.tick.toUpperCase() && Number(cur[tslId]) > 0) ? Number(cur[tslId]) : s.tsl;
      var vals = [s.tick, s.entry, s.sl, tsl, s.t1, s.t2, s.sec, s.date];
      want.push({id: info[k].id, value: vals[0]});
      for (var q2 = 0; q2 < 7; q2++) want.push({id: info[k + 1 + q2].id, value: vals[q2 + 1]});
    });
    if (bad.length) return JSON.stringify({error: bad.slice(0, 5).join("; ")});
    v.setInputValues(want);
    var got = {}; v.getInputValues().forEach(function (x) { got[x.id] = x.value; });
    var miss = want.filter(function (w) { return String(got[w.id]) !== String(w.value); }).length;
    var filled = slots.filter(function (s) { return s.tick; }).length;
    return JSON.stringify({set: want.length, miss: miss, filled: filled});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


# ── SETTINGS SNAPSHOT / RESTORE (4-Oct-2026) ─────────────────────────────────────────
# TradingView keys a study's saved input values by POSITION. An input added to v67 shifts
# every saved value below it onto the wrong input. --snapshot (run BEFORE a v67 compile)
# saves every non-slot setting by (name, occurrence); every push afterwards puts back any
# value that no longer matches the snapshot. Slots and the book are pushed separately.
SNAP_PATH = os.path.join(HERE, "data", "v67_inputs_snapshot.json")
SNAP_JS = r"""
(function () {
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var st = chart.getAllStudies(); var id = null;
    for (var i = 0; i < st.length; i++) if (st[i].name.indexOf(%(prefix)s) === 0) { id = st[i].id; break; }
    if (!id) return JSON.stringify({none: 1});
    var v = chart.getStudyById(id); var info = v.getInputsInfo();
    var cur = {}; v.getInputValues().forEach(function (x) { cur[x.id] = x.value; });
    var SKIP = {"Entry":1, "SL":1, "Trail SL":1, "T1":1, "T2":1, "Sector":1, "Date":1};
    var seen = {}; var out = [];
    info.forEach(function (x) {
      // user inputs only: TradingView's own fields (ILScript = the compiled script,
      // pineId, pineVersion...) must never be written back - that would undo a compile
      if (!/^in_\d+$/.test(String(x.id))) return;
      if (/^Slot \d+$/.test(x.name) || SKIP[x.name] || x.name === %(book)s) return;
      seen[x.name] = (seen[x.name] || 0) + 1;
      out.push({key: x.name + "#" + seen[x.name], id: x.id, value: cur[x.id]});
    });
    var restore = %(restore)s;
    if (restore === null) return JSON.stringify({inputs: out});
    var fix = [];
    out.forEach(function (o) { if (o.key in restore && String(restore[o.key]) !== String(o.value)) fix.push({id: o.id, value: restore[o.key], key: o.key}); });
    if (fix.length) v.setInputValues(fix.map(function (f) { return {id: f.id, value: f.value}; }));
    return JSON.stringify({fixed: fix.map(function (f) { return f.key; })});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()
"""


def snapshot_or_restore(restore: bool) -> int:
    import s4_review as s
    snap = {}
    if restore:
        if not os.path.exists(SNAP_PATH):
            return 0
        with open(SNAP_PATH, encoding="utf-8") as f:
            snap = json.load(f)
    out = {}
    for t in s._chart_targets():
        cid = t["url"].split("/chart/")[1].split("/")[0]
        want = json.dumps(snap.get(cid)) if restore else "null"
        if restore and cid not in snap:
            continue
        r = json.loads(s._tv(SNAP_JS % {"prefix": json.dumps(V67_PREFIX), "book": json.dumps(INPUT_TITLE),
                                        "restore": want}, t))
        if r.get("none"):
            continue
        if r.get("error"):
            print(f"chart {cid}: settings {'restore' if restore else 'snapshot'} FAIL - {r['error']}")
            continue
        if restore:
            print(f"chart {cid}: settings restored - {len(r['fixed'])} put back" +
                  (": " + ", ".join(r["fixed"][:8]) if r["fixed"] else ""))
        else:
            out[cid] = {x["key"]: x["value"] for x in r["inputs"]}
            print(f"chart {cid}: settings snapshot - {len(r['inputs'])} inputs")
    if not restore:
        os.makedirs(os.path.dirname(SNAP_PATH), exist_ok=True)
        with open(SNAP_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
    return 0


def compute_slots() -> list[dict]:
    """The 25 slot values Sync to TV writes into the Pine file (db_portfolio_sync.build_slots),
    as plain values for setInputValues."""
    import re
    from datetime import datetime, timezone
    import db_portfolio_sync as dps
    con = sqlite3.connect(dps.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        open_trades = con.execute("SELECT * FROM journal WHERE status='OPEN' ORDER BY id ASC").fetchall()
    finally:
        con.close()
    with open(os.path.join(HERE, dps.PINE_PATH), encoding="utf-8") as f:
        pine = f.read()
    out = []
    for sl in dps.build_slots(open_trades, pine):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", str(sl["date_val"]))
        date_ms = int(datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000) if m else 0
        try:
            tsl = float(sl["tsl_val"])
        except (TypeError, ValueError):
            tsl = 0.0
        out.append({"i": sl["i"], "tick": sl["tick"], "entry": float(sl["entry"]), "sl": float(sl["sl"]),
                    "tsl": tsl, "t1": float(sl["t1"]), "t2": float(sl["t2"]), "sec": sl["sec"], "date": date_ms})
    return out


def push_slots(slots: list[dict]) -> int:
    import s4_review as s
    js = SLOTS_JS % {"prefix": json.dumps(V67_PREFIX), "slots": json.dumps(slots)}
    bad = seen = 0
    for t in s._chart_targets():
        cid = t["url"].split("/chart/")[1].split("/")[0]
        r = json.loads(s._tv(js, t))
        if r.get("none"):
            continue
        seen += 1
        if r.get("error") or r.get("miss"):
            bad += 1
            print(f"chart {cid}: slots FAIL - {r.get('error') or str(r['miss']) + ' values did not stick'}")
        else:
            print(f"chart {cid}: slots OK - {r['filled']} holdings in 25 slots")
    return 1 if (bad or not seen) else 0


def _tv_keys(sym: str) -> list[str]:
    """TradingView spellings: NAM-INDIA charts as NAM_INDIA (separator aliases, 22-Sep)."""
    s = str(sym).upper().replace("NSE:", "").replace(".NS", "").strip()
    keys = [s]
    alt = s.replace("-", "_")
    if alt not in keys:
        keys.append(alt)
    return keys


def compute_book() -> list[dict]:
    """Every OPEN holding's trail, exactly as Risk Shield computes it."""
    import pandas as pd
    import data_provider as dp
    import journal_path as jp
    import risk_common as rc
    try:
        import gm_trigger_board as gtb
    except Exception:
        gtb = None

    con = sqlite3.connect(jp.JOURNAL_DB)
    try:
        df = pd.read_sql_query("SELECT * FROM journal WHERE UPPER(status)='OPEN'", con)
    finally:
        con.close()
    syms = [s for s in df["symbol"].dropna().unique() if not str(s).upper().startswith("LIQUID")]

    def _f(x):
        try:
            v = float(x)
            return v if v == v else None
        except (TypeError, ValueError):
            return None

    # market regime: the page's own source (B2), unknown = no widening
    bear = None
    try:
        from market_regime import compute_regime
        import house_policy as hp
        sc = compute_regime(persist=False).get("score")
        if sc is not None:
            bear = hp.is_bear(sc)
    except Exception as e:
        print("regime unavailable (no bear widening):", e)
    try:
        with open(os.path.join(HERE, "portfolio_history.json"), encoding="utf-8") as f:
            cap_protect = rc.capital_protection_active(json.load(f))
    except Exception:
        cap_protect = False
    try:
        with open(os.path.join(HERE, "gm_settings.json"), encoding="utf-8") as f:
            mode = (json.load(f) or {}).get("sl_override_mode", "Floor")
    except Exception:
        mode = "Floor"

    data = dp.fetch_batch_ohlcv(syms, period="2y", interval="1d", use_cache=True, auto_adjust=True)
    out = []
    for s in syms:
        r = df[df["symbol"] == s].iloc[0]
        ov = _f(r.get("manual_sl_override"))
        cm = _f(r.get("custom_ce_mult"))
        jrow = {
            "setup": str(r.get("setup") or "").strip().upper(),
            "timeframe": str(r.get("timeframe") or "").strip(),
            "buy_price": _f(r.get("buy_price")),
            "stoploss": _f(r.get("stoploss")),
            "custom_ce_mult": cm if (cm is not None and cm != 0) else None,
            "manual_sl_override": ov if (ov and ov > 0) else None,
            "entry_date": r.get("entry_date") or None,
        }
        d = data.get(s)
        rrg = None
        if gtb is not None and d is not None and not d.empty:
            try:
                rrg = gtb.rrg_live(d).get("quadrant")
            except Exception:
                rrg = None
        hc = rc.holding_chandelier(d, jrow, bear, cap_protect=cap_protect, override_mode=mode, rrg=rrg)
        out.append({"symbol": s, **{k: hc[k] for k in ("level", "raw_level", "mult", "src", "window",
                                                        "tt_label", "override", "anchored")}})
    return out


def book_string(rows: list[dict]) -> str:
    parts = []
    for r in rows:
        if r["window"] is None or r["mult"] is None:
            continue
        ov = r.get("override")
        floor = "0" if not ov else (("E%.2f" if ov[1] == "Exact" else "%.2f") % ov[0])
        # ENTRY ANCHOR (7-Oct-2026): v67 computes ta.highest(close, window), which reaches back
        # before the entry. While a position is younger than its window, send Risk Shield's
        # entry-anchored level as an EXACT floor so the chart line is that number. (An Exact
        # manual override already is the level; nothing to change.)
        if r.get("anchored") and r.get("level") is not None and not (ov and ov[1] == "Exact"):
            floor = "E%.2f" % float(r["level"])
        for k in _tv_keys(r["symbol"]):
            parts.append("%s=%d,%.4f,%s" % (k, int(r["window"]), float(r["mult"]), floor))
    return ";".join(parts)


def push(book: str | None) -> int:
    import s4_review as s
    want = json.dumps(book) if book is not None else "null"
    js = JS % {"prefix": json.dumps(V67_PREFIX), "title": json.dumps(INPUT_TITLE), "want": want}
    bad = 0
    seen = 0
    for t in s._chart_targets():
        cid = t["url"].split("/chart/")[1].split("/")[0]
        r = json.loads(s._tv(js, t))
        if r.get("none"):
            print(f"chart {cid}: no v67 - skipped")
            continue
        seen += 1
        if r.get("error"):
            bad += 1
            print(f"chart {cid}: FAIL - {r['error']}")
        elif book is not None and r.get("got") != book:
            bad += 1
            print(f"chart {cid}: FAIL - read back {len(r.get('got', ''))} chars, sent {len(book)}")
        else:
            print(f"chart {cid}: OK - {len(r.get('got', ''))} chars")
    if seen == 0:
        print("no chart tab carries v67")
        return 1
    return 1 if bad else 0


def main() -> int:
    check = "--check" in sys.argv
    dry = "--dry-run" in sys.argv
    if "--snapshot" in sys.argv:
        return snapshot_or_restore(restore=False)
    # --restore (AFTER_COMPILE only): put back settings a v67 compile shifted. Never on
    # the nightly run - it would undo a setting you changed on purpose.
    if "--restore" in sys.argv and not check and not dry:
        snapshot_or_restore(restore=True)
    rc_slots = 0
    if not check and "--no-slots" not in sys.argv:
        slots = compute_slots()
        print("slots: %d holdings -> v67 portfolio slots" % sum(1 for x in slots if x["tick"]))
        if not dry:
            rc_slots = push_slots(slots)
    rows = compute_book()
    print("%-12s %-11s %6s %5s %10s %10s  %s" % ("symbol", "type", "window", "mult", "raw", "shown", "override"))
    for r in rows:
        print("%-12s %-11s %6s %5s %10s %10s  %s" % (
            r["symbol"], r["tt_label"] or "-", r["window"] or "-",
            ("%.1f" % r["mult"]) if r["mult"] else "-",
            ("%.2f" % r["raw_level"]) if r["raw_level"] else "-",
            ("%.2f" % r["level"]) if r["level"] else "-", r["override"] or ""))
    book = book_string(rows)
    print(f"\nbook: {len(book)} chars, {len(rows)} holdings")
    if dry:
        return 0
    rc_book = push(None if check else book)
    if not check:
        snapshot_or_restore(restore=False)      # today's settings = the next restore point
    return max(rc_slots, rc_book)


if __name__ == "__main__":
    sys.exit(main())
