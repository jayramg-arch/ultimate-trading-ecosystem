"""tv_push_v67_trail.py — put Risk Shield's Chandelier on v67's chart line (4-Oct-2026).

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
                                                        "tt_label", "override")}})
    return out


def book_string(rows: list[dict]) -> str:
    parts = []
    for r in rows:
        if r["window"] is None or r["mult"] is None:
            continue
        ov = r.get("override")
        floor = "0" if not ov else (("E%.2f" if ov[1] == "Exact" else "%.2f") % ov[0])
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
    return push(None if check else book)


if __name__ == "__main__":
    sys.exit(main())
