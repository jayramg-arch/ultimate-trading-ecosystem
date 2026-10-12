"""Pre-registered test: does a REJECTION at the level beat other GO rows?
(docs/PREREG_rejection_at_level.md, registered 12-Oct-2026 before any data.)

    python rejection_test.py          counts only (the default until the threshold is met)
    python rejection_test.py --run    run the registered test once - refuses below threshold
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LEDGER = os.path.join(HERE, "logs", "rejection_ledger.csv")
REGISTERED = "2026-10-12 23:00"        # rows logged before this are not part of the test
MIN_N, THIN_N, H_MARGIN, BOOT = 30, 15, 0.25, 10000


def load() -> pd.DataFrame:
    if not os.path.exists(LEDGER):
        return pd.DataFrame()
    d = pd.read_csv(LEDGER)
    d = d[d["logged"].astype(str) >= REGISTERED]
    d = d.drop_duplicates(subset=["tf", "symbol", "bar_ts"], keep="first")
    return d.reset_index(drop=True)


def outcome(row, n_sess: int):
    """R after n_sess Daily sessions from the trigger bar's date; None if not yet elapsed."""
    import data_provider as dp
    try:
        entry, stop = float(row["c"]), float(row["sl"])
    except (TypeError, ValueError):
        return None
    if not entry > stop:
        return None
    risk = entry - stop
    df = dp.fetch_ohlcv(str(row["symbol"]), period="1y", interval="1d", use_cache=True)
    if df is None or not len(df):
        return None
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    d0 = pd.Timestamp(str(row["bar_ts"])[:10])
    after = df[df.index > d0]
    if len(after) < n_sess:
        return None
    for _, b in after.iloc[:n_sess].iterrows():
        if float(b["Low"]) <= stop:
            fill = min(stop, float(b["Open"]))
            return (fill - entry) / risk
    return (float(after.iloc[n_sess - 1]["Close"]) - entry) / risk


def _boot(a: pd.DataFrame, b: pd.DataFrame, rng) -> tuple[float, float]:
    syms = pd.unique(pd.concat([a["symbol"], b["symbol"]]))
    diffs = []
    for _ in range(BOOT):
        pick = set(rng.choice(syms, size=len(syms), replace=True))
        aa, bb = a[a["symbol"].isin(pick)]["R"], b[b["symbol"].isin(pick)]["R"]
        if len(aa) and len(bb):
            diffs.append(aa.mean() - bb.mean())
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    d = load()
    print("Rejection-at-level test (pre-registered 12-Oct-2026) - ledger rows after registration: %d" % len(d))
    if d.empty:
        print("  no rows yet - the board writes one per 5/5 row on every rebuild")
        return 0
    d["R"] = [outcome(r, 10) for _, r in d.iterrows()]
    ok = d[d["R"].notna()]
    print("  with R10 elapsed: %d · excluded / pending: %d" % (len(ok), len(d) - len(ok)))
    cells = {}
    for pt, g in ok.groupby("plan"):
        nr, nn = int((g["rej"] == 1).sum()), int((g["rej"] == 0).sum())
        cells[pt] = (g, nr, nn)
        print("  %-11s rejection %3d · other %3d %s" % (pt, nr, nn,
              "(ready)" if nr >= MIN_N and nn >= MIN_N else "(need %d each)" % MIN_N))
    if not a.run:
        return 0
    ready = {pt: v for pt, v in cells.items() if v[1] >= MIN_N and v[2] >= MIN_N}
    if not ready:
        print("REFUSED: no plan-type cell has %d rejection AND %d other rows yet." % (MIN_N, MIN_N))
        return 1
    rng = np.random.default_rng(12102026)
    for pt, (g, nr, nn) in ready.items():
        rj, ot = g[g["rej"] == 1], g[g["rej"] == 0]
        diff = rj["R"].mean() - ot["R"].mean()
        med_ok = rj["R"].median() >= ot["R"].median()
        lo, hi = _boot(rj, ot, rng)
        passed = diff >= H_MARGIN and med_ok and lo > 0
        print("\n%s: rejection mean %.2fR (n %d) vs other %.2fR (n %d) · diff %+.2fR · CI [%.2f, %.2f] · "
              "median %s · H %s" % (pt, rj["R"].mean(), nr, ot["R"].mean(), nn, diff, lo, hi,
                                     "ok" if med_ok else "worse", "PASSES" if passed else "FAILS"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
