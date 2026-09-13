# -*- coding: utf-8 -*-
"""
build_tv_index_map.py — ETF → TradingView ticker of its UNDERLYING INDEX.

For the reviewer's Phase-1 read (13-Sep-2026): an ETF is a bet on its index, so the
S4 panel on the INDEX chart is the thesis and the ETF chart is the tradability. The
Studio's index tickers are Dhan/NSE spellings ("NIFTY AUTO"); TradingView's differ
("NSE:CNXAUTO"), so resolve each `etf_universe` underlying ONCE through TradingView's
own symbol search — run from the chart page over CDP, the way the app calls it — and
cache to data/tv_index_map.json. Edit the file by hand for any wrong hit; re-running
keeps hand edits (only missing/blank entries are looked up unless --force).

    python build_tv_index_map.py            # fill in what is missing
    python build_tv_index_map.py --force    # re-resolve everything
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "tv_index_map.json")

KICK = r"""
window.__idxres = null;
(async () => {
  const names = %s; const out = {};
  for (const n of names) {
    try {
      const r = await fetch('https://symbol-search.tradingview.com/symbol_search/v3/?text=' + encodeURIComponent(n) + '&exchange=NSE&lang=en&search_type=index&domain=production');
      const j = await r.json();
      out[n] = (j.symbols||[]).filter(s => (s.exchange||'')==='NSE').slice(0,6).map(s => [ (s.prefix||s.exchange)+':'+String(s.symbol).replace(/<[^>]+>/g,''), String(s.description||'').replace(/<[^>]+>/g,''), s.type ]);
    } catch(e) { out[n] = 'ERR ' + e; }
  }
  window.__idxres = out;
})(); 'kicked'
"""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("index", "").replace("nifty", "nifty"))


def pick(name: str, hits) -> str | None:
    """The hit whose description is the index name (TV appends ' Index'), else the
    first hit whose description contains every word of the name, else None."""
    if not isinstance(hits, list):
        return None
    want = _norm(name)
    for tk, desc, typ in hits:
        if _norm(desc) == want:
            return tk
    words = [w for w in re.split(r"\W+", name.lower()) if w and w != "index"]
    for tk, desc, typ in hits:
        d = desc.lower()
        if all(w in d for w in words):
            return tk
    return None


def load() -> dict:
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    import etf_universe
    uni = getattr(etf_universe, "ETF_UNIVERSE", None) or getattr(etf_universe, "UNIVERSE")
    cur = load()
    todo = {}
    for sym, e in uni.items():
        und = (e.get("underlying") or "").strip()
        if not und:
            continue
        if args.force or not (cur.get(sym) or {}).get("tv"):
            todo[sym] = und
    if not todo:
        print("nothing to resolve (%d mapped)" % len(cur)); return 0
    import s4_review as sr
    tgt = sr._chart_targets()[0]
    names = sorted(set(todo.values()))
    sr._tv(KICK % json.dumps(names), tgt)
    res = None
    for _ in range(120):
        time.sleep(1)
        v = sr._tv("JSON.stringify(window.__idxres)", tgt)
        if v and v != "null":
            res = json.loads(v); break
    if res is None:
        print("TradingView symbol search did not answer", file=sys.stderr); return 2
    n_ok = 0
    for sym, und in todo.items():
        hits = res.get(und)
        tk = pick(und, hits)
        cur[sym] = {"underlying": und, "tv": tk,
                    "candidates": [h[0] + " · " + h[1] for h in hits[:4]] if isinstance(hits, list) else []}
        n_ok += bool(tk)
        print("%-12s %-32s -> %s" % (sym, und, tk or "?? " + "; ".join(cur[sym]["candidates"][:3])))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1, ensure_ascii=False)
    print("%d/%d resolved -> %s" % (n_ok, len(todo), os.path.relpath(OUT, HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
