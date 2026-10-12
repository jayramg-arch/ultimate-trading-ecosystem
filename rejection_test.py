"""Pre-registered test: does a REJECTION at the level beat other GO rows?
(docs/PREREG_rejection_at_level.md, registered 12-Oct-2026 before any data.)

    python rejection_test.py          counts only (the default until the threshold is met)
    python rejection_test.py --run    run the registered test once - refuses below threshold

H1 rejection at the level; H2 (amendment 1) weak latest bar. See the pre-registration.
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


def _weak(row) -> float:
    """H2 label: 1 weak, 0 not weak, nan for a zero-range bar (excluded and counted)."""
    from gm_trigger_board import bar_grade
    r = bar_grade(row.get("o"), row.get("h"), row.get("l"), row.get("c"))
    return np.nan if r is None else float(r[0] == "weak")


def _test(name, g, col, pos, neg, rng) -> None:
    """One registered hypothesis on one plan-type cell: mean(pos) - mean(neg) >= H_MARGIN,
    median(pos) >= median(neg), symbol-bootstrap CI lower bound > 0."""
    a, b = g[g[col] == pos], g[g[col] == neg]
    diff = a["R"].mean() - b["R"].mean()
    med_ok = a["R"].median() >= b["R"].median()
    lo, hi = _boot(a, b, rng)
    passed = diff >= H_MARGIN and med_ok and lo > 0
    print("  %s: %.2fR (n %d) vs %.2fR (n %d) · diff %+.2fR · CI [%.2f, %.2f] · median %s · %s" % (
        name, a["R"].mean(), len(a), b["R"].mean(), len(b), diff, lo, hi,
        "ok" if med_ok else "worse", "PASSES" if passed else "FAILS"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    d = load()
    print("Rejection-at-level test (pre-registered 12-Oct-2026; H2 weak bar, amendment 1) - "
          "ledger rows after registration: %d" % len(d))
    if d.empty:
        print("  no rows yet - the board writes one per 5/5 row on every rebuild")
        return 0
    d["R"] = [outcome(r, 10) for _, r in d.iterrows()]
    d["weak"] = [_weak(r) for _, r in d.iterrows()]
    ok = d[d["R"].notna()]
    print("  with R10 elapsed: %d · excluded / pending: %d · zero-range bars (H2 only): %d"
          % (len(ok), len(d) - len(ok), int(ok["weak"].isna().sum())))
    ready1, ready2 = {}, {}
    for pt, g in ok.groupby("plan"):
        nr, nn = int((g["rej"] == 1).sum()), int((g["rej"] == 0).sum())
        nw, ns = int((g["weak"] == 1).sum()), int((g["weak"] == 0).sum())
        r1, r2 = nr >= MIN_N and nn >= MIN_N, nw >= MIN_N and ns >= MIN_N
        print("  %-11s H1 rejection %3d · other %3d %s   H2 weak %3d · not-weak %3d %s" % (
            pt, nr, nn, "(ready)" if r1 else "(need %d each)" % MIN_N,
            nw, ns, "(ready)" if r2 else "(need %d each)" % MIN_N))
        if r1:
            ready1[pt] = g
        if r2:
            ready2[pt] = g
    if not a.run:
        return 0
    if not ready1 and not ready2:
        print("REFUSED: no plan-type cell has %d + %d rows for either hypothesis yet." % (MIN_N, MIN_N))
        return 1
    rng = np.random.default_rng(12102026)
    for pt, g in ready1.items():
        print("\n%s" % pt)
        _test("H1 rejection vs other", g, "rej", 1, 0, rng)
    for pt, g in ready2.items():
        print("\n%s" % pt)
        _test("H2 not-weak vs weak", g, "weak", 0.0, 1.0, rng)
    return 0


if __name__ == "__main__":
    sys.exit(main())
