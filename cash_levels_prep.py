"""Step 1 of docs/PREREG_cash_levels.md — build the level table.

Data preparation only: for each of the 515 trades, the pre-registered 120-day profile,
the AVWAP-BO anchor and the delivery signal AS OF THE ENTRY DATE. No outcome is read
here, so running it cannot influence the hypotheses.

Cached to a CSV so the analysis can be re-run without re-fetching 515 pinned histories —
the analysis itself runs ONCE, but debugging its plumbing on a placebo must not cost
another hour of fetching.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(HERE, "validation_runs", "validation_20260819_112959_details.csv")
OUT = os.path.join(HERE, "validation_runs", "_cash_levels_table.csv")


def main() -> int:
    import volume_profile as vp
    import cash_bhavcopy as cb

    t = pd.read_csv(TRADES)
    deliv_all = cb.load()
    rows, miss_px, miss_dl = [], 0, 0

    for i, r in t.iterrows():
        sym = str(r["Symbol"]).upper().replace(".NS", "")
        as_of = str(r["as_of"])
        try:
            lv = vp.structural_levels(sym, pinned_date=as_of) or {}
        except Exception:
            lv = {}
        if not lv:
            miss_px += 1

        # delivery, as of the entry date, from the shared accessor (contiguity guard and
        # all) so the test and the live line cannot diverge
        try:
            ds = cb.delivery_signal(sym, as_of) if not deliv_all.empty else {}
        except Exception:
            ds = {}
        if not ds:
            miss_dl += 1

        hv = lv.get("hvns") or []
        entry = float(r["Entry_Close"]) if pd.notna(r.get("Entry_Close")) else None
        rows.append({
            "Symbol": sym, "as_of": as_of,
            "poc": lv.get("poc"), "vah": lv.get("vah"), "val": lv.get("val"),
            "avwap_bo": lv.get("avwap_bo"),
            "hvn_above": min([h for h in hv if entry and h > entry], default=None),
            "hvn_below": max([h for h in hv if entry and h < entry], default=None),
            "n_hvn": len(hv),
            "deliv_pct": ds.get("deliv_pct"), "deliv_mean20": ds.get("mean20"),
            "deliv_ratio": ds.get("ratio"),
        })
        if (i + 1) % 50 == 0:
            print("  %d/%d" % (i + 1, len(t)), flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print("\nwrote %s" % os.path.relpath(OUT, HERE))
    print("trades           : %d" % len(out))
    print("no price profile : %d" % miss_px)
    print("no delivery      : %d" % miss_dl)
    print("have hvn_above   : %d" % out["hvn_above"].notna().sum())
    print("have hvn_below   : %d" % out["hvn_below"].notna().sum())
    print("have avwap_bo    : %d" % out["avwap_bo"].notna().sum())
    return 0


if __name__ == "__main__":
    sys.exit(main())
