"""wyckoff_score_study.py — does the Wyckoff term earn its place in the WCL score?

Implements `docs/PREREG_wyckoff_score_value.md` EXACTLY. Written while the held-out
validation run was still in flight, so the test could not be shaped by its result.

Question: `wyk_score_comp` feeds total_base -> total_final -> Pine confluence and the
board's overall_score. Signed as it is, the engine asserts higher Wyckoff -> better
trade. Is that true out of sample?

HELD-OUT = anchors strictly before 2024-06-17 (never used by wyckoff_veto_study.py).
BURNED   = anchors on/after that date (reference only; cannot drive the decision).

Decision rule (fixed in the prereg, not renegotiable here):
  KEEP        monotone terciles AND rho > 0 AND p < 0.05 AND n >= 150
  DEMOTE      rho <= 0 AND terciles flat/inverted
  INCONCLUSIVE everything else, including n < 150 — change nothing

Usage: python wyckoff_score_study.py --details <heldout_details.csv>
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import wcl_context as W

SPLIT = pd.Timestamp("2024-06-17")     # first anchor of the burned (veto-study) sample
MIN_N = 150                            # prereg: below this the result is INCONCLUSIVE
PERM_N = 10000


def _spearman(x, y):
    return pd.Series(x).rank().corr(pd.Series(y).rank())


def _perm_p(x, y, n=PERM_N, seed=12345):
    """Permutation p-value for rho != 0. Deterministic seed so the number is
    reproducible — an unseeded p-value invites quietly re-rolling until it passes."""
    rng = np.random.default_rng(seed)
    obs = _spearman(x, y)
    if not np.isfinite(obs):
        return obs, float("nan")
    y = np.asarray(y)
    hits = 0
    for _ in range(n):
        if abs(_spearman(x, rng.permutation(y))) >= abs(obs):
            hits += 1
    return obs, (hits + 1) / (n + 1)


def _terciles(d, col):
    neg = d[d[col] < 0]["Alpha_Matched_pct"]
    zer = d[d[col] == 0]["Alpha_Matched_pct"]
    pos = d[d[col] > 0]["Alpha_Matched_pct"]
    return [("neg", neg), ("zero", zer), ("pos", pos)]


def _describe(d, col, label):
    print(f"\n  {label} — by {col}")
    means = []
    for nm, s in _terciles(d, col):
        if len(s):
            print(f"    {nm:5} n={len(s):4d}  alpha {s.mean():+6.2f}%  win {(s>0).mean()*100:4.1f}%")
            means.append(s.mean())
        else:
            print(f"    {nm:5} n=   0")
            means.append(np.nan)
    rho, p = _perm_p(d[col].values, d["Alpha_Matched_pct"].values)
    mono = all(np.diff([m for m in means if np.isfinite(m)]) > 0) if sum(np.isfinite(means)) >= 2 else False
    print(f"    spearman rho {rho:+.4f}  perm p {p:.4f}  monotone-increasing {mono}")
    return rho, p, mono


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", required=True)
    args = ap.parse_args()

    d = pd.read_csv(args.details)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["as_of_ts"] = pd.to_datetime(d["as_of"])
    print(f"run trades={len(d)}  symbols={d['Symbol'].nunique()}  "
          f"anchors {d['as_of'].min()} -> {d['as_of'].max()}")

    import data_provider as dp
    frames = {}
    for i, s in enumerate(sorted(d["Symbol"].unique()), 1):
        try:
            f = dp.fetch_ohlcv(s, period="10y", interval="1d")
            if f is not None and len(f) >= 260:
                frames[s] = f
        except Exception:
            pass
        if i % 50 == 0:
            print(f"  fetched {i} …", file=sys.stderr)

    wy, sm, tf = [], [], []
    for _, r in d.iterrows():
        f = frames.get(r["Symbol"])
        w = s_ = t_ = np.nan
        if f is not None:
            try:
                cut = f.loc[:r["as_of_ts"]]
                if len(cut) >= 120:
                    w = W.wyckoff_state(cut)["score_comp"]
                    s_ = W.smc_state(cut)["score"]
                    t_ = w + s_
            except Exception:
                pass
        wy.append(w); sm.append(s_); tf.append(t_)
    d["wyk"], d["smc"], d["wyk_smc"] = wy, sm, tf
    d = d[d["wyk"].notna()].copy()

    held = d[d["as_of_ts"] < SPLIT]
    burned = d[d["as_of_ts"] >= SPLIT]
    print(f"\nHELD-OUT n={len(held)}  (anchors < {SPLIT.date()})")
    print(f"BURNED   n={len(burned)}  (reference only)")

    print("\n================ PRIMARY (held-out, decision-bearing) ================")
    if len(held) == 0:
        print("  no held-out trades — INCONCLUSIVE by rule")
        return
    print(f"  baseline alpha {held['Alpha_Matched_pct'].mean():+.2f}%  "
          f"win {(held['Alpha_Matched_pct']>0).mean()*100:.1f}%")
    rho, p, mono = _describe(held, "wyk", "HELD-OUT Wyckoff")

    print("\n================ SECONDARY (pre-declared, decision-irrelevant) ========")
    _describe(held, "smc", "HELD-OUT SMC")
    _describe(held, "wyk_smc", "HELD-OUT Wyckoff+SMC")
    if len(burned):
        _describe(burned, "wyk", "BURNED Wyckoff (already-used sample)")
        _describe(burned, "smc", "BURNED SMC")

    print("\n================ DECISION (prereg rule) ================")
    n_ok = len(held) >= MIN_N
    keep = mono and (rho > 0) and (p < 0.05) and n_ok
    demote = (rho <= 0) and (not mono)
    print(f"  n >= {MIN_N} ............. {len(held):4d}   {'PASS' if n_ok else 'FAIL'}")
    print(f"  rho > 0 ................ {rho:+.4f}  {'PASS' if rho > 0 else 'FAIL'}")
    print(f"  perm p < 0.05 .......... {p:.4f}  {'PASS' if p < 0.05 else 'FAIL'}")
    print(f"  terciles monotone ...... {mono}")
    verdict = "KEEP as scored" if keep else ("DEMOTE to display-only" if (demote and n_ok) else "INCONCLUSIVE — change nothing")
    print(f"\n  VERDICT: {verdict}")


if __name__ == "__main__":
    main()
