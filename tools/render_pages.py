"""Render every Web Commander page headlessly and record what it drew (split phase 0).

    python tools/render_pages.py --out before.json      # the app as it is
    python tools/render_pages.py --out after.json       # after a change
    python tools/render_pages.py --diff before.json after.json

Each page is run through Streamlit's AppTest with the journal pointed at a COPY
(tests/fixtures/trade_journal_v6.db, git-ignored - Jay approved 25-Sep-2026), so nothing a
page does on load can touch the live journal. Per page it records: exceptions raised, the
error/warning boxes shown, and a count of every element type drawn. A move that changes
none of that is a move; an exception that was not there before is a regression.

Run it OUTSIDE market hours: pages make the same broker/data calls they make for you.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(HERE, "weinstein_commander_web_v4.0.py")
FIX = os.path.join(HERE, "tests", "fixtures")
PAGES = ["DASHBOARD", "HUNTER", "WATCHLIST", "COMMAND", "AI LAB", "MACRO", "OPTIONS",
         "AUTOPSY", "BACKTEST", "PRE-MARKET", "POST-MARKET", "BREADTH", "ETF", "NEWS",
         "FUNDAMENTALS", "PORTFOLIO", "X-RAY", "GOLDEN MATCHER", "TV SIDECAR",
         "ACTION CENTER", "RISK SHIELD", "JOURNAL"]


def prepare_fixture() -> str:
    os.makedirs(FIX, exist_ok=True)
    dst = os.path.join(FIX, "trade_journal_v6.db")
    src = os.environ.get("COMMANDER_JOURNAL_SRC") or os.path.join(HERE, "trade_journal_v6.db")
    shutil.copy2(src, dst)
    return dst


def _walk(node):
    yield node
    for ch in getattr(node, "children", {}).values() if isinstance(getattr(node, "children", None), dict) else []:
        yield from _walk(ch)


def render(page: str, timeout: int) -> dict:
    from streamlit.testing.v1 import AppTest
    t0 = time.time()
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.session_state["page"] = page
    rec = {"page": page}
    try:
        at.run(timeout=timeout)
    except Exception as e:                      # a timeout or harness failure, not a page exception
        rec["harness_error"] = f"{type(e).__name__}: {e}"[:400]
        rec["secs"] = round(time.time() - t0, 1)
        return rec
    rec["secs"] = round(time.time() - t0, 1)
    rec["exceptions"] = [str(getattr(e, "value", e))[:300] for e in at.exception]
    rec["errors"] = [str(e.value)[:200] for e in at.error]
    rec["warnings"] = len(at.warning)
    kinds = Counter()
    for n in _walk(at._tree):
        kinds[type(n).__name__] += 1
    rec["elements"] = dict(sorted(kinds.items()))
    return rec


def diff(a_path: str, b_path: str) -> int:
    A = {r["page"]: r for r in json.load(open(a_path, encoding="utf-8"))["pages"]}
    B = {r["page"]: r for r in json.load(open(b_path, encoding="utf-8"))["pages"]}
    bad = 0
    for p in PAGES:
        a, b = A.get(p, {}), B.get(p, {})
        ea, eb = a.get("exceptions") or [], b.get("exceptions") or []
        new_exc = [x for x in eb if x not in ea]
        flag = "REGRESSION" if (new_exc or ("harness_error" in b and "harness_error" not in a)) else "ok"
        bad += flag != "ok"
        ka, kb = a.get("elements", {}), b.get("elements", {})
        dk = {k: (ka.get(k, 0), kb.get(k, 0)) for k in set(ka) | set(kb) if ka.get(k, 0) != kb.get(k, 0)}
        print(f"{p:15s} {flag:10s} exc {len(ea)}->{len(eb)}  err {len(a.get('errors', []))}->{len(b.get('errors', []))}"
              f"  elements changed: {dk if dk else 'none'}")
        for x in new_exc:
            print("      NEW EXCEPTION:", x)
        if "harness_error" in b:
            print("      HARNESS:", b["harness_error"])
    print(f"\n{bad} page(s) regressed")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--diff", nargs=2)
    ap.add_argument("--pages", help="comma list; default all 22")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    if a.diff:
        return diff(*a.diff)
    os.chdir(HERE)
    sys.path.insert(0, HERE)
    os.environ["COMMANDER_JOURNAL_DB"] = prepare_fixture()
    pages = a.pages.split(",") if a.pages else PAGES
    out = {"app": APP, "at": dt.datetime.now().isoformat(timespec="seconds"), "pages": []}
    for p in pages:
        r = render(p, a.timeout)
        out["pages"].append(r)
        print(f"{p:15s} {r.get('secs')}s  exc={len(r.get('exceptions', []))}  "
              f"err={len(r.get('errors', []))}  {r.get('harness_error', '')[:120]}")
    if a.out:
        json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
