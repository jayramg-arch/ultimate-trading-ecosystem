"""docs/PREREG_cash_levels.md — the analysis. Runs ONCE.

    python cash_levels_test.py --placebo    shuffle the levels; every result is noise by
                                            construction. For debugging the plumbing
                                            WITHOUT spending the one real run.
    python cash_levels_test.py              the real run.

Bars, parameters and the stopping rule are in the pre-registration. Nothing is decided
here; this only computes what that document already committed to.
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(HERE, "validation_runs", "validation_20260819_112959_details.csv")
LEVELS = os.path.join(HERE, "validation_runs", "_cash_levels_table.csv")
FNO = os.path.join(HERE, "data", "fno_history.csv")

BOOT = 2000
RNG = np.random.default_rng(20260923)
# catalyst-aware stop multiples (bull_screener) — ATR = risk / mult, since
# replay.STRUCTURAL_SL is False so every stop in this run is ATR-based
SL_MULT = {"POS": 4.0, "WYC": 3.5, "REV": 2.5, "SWG": 1.5}


def _mult(cat: str) -> float:
    return SL_MULT.get(str(cat)[:3].upper(), 1.5)


def load() -> pd.DataFrame:
    t = pd.read_csv(TRADES)
    lv = pd.read_csv(LEVELS)
    t["Symbol"] = t["Symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False)
    d = t.merge(lv, on=["Symbol", "as_of"], how="left")
    d["risk"] = d["Entry_Close"] - d["SL_price"]
    d["atr"] = d["risk"] / d["Catalyst_used"].map(_mult)
    d["R"] = d["Return_pct"] / d["SL_pct"]
    d["family"] = d["Catalyst_used"].astype(str)
    fno = set(pd.read_csv(FNO)["symbol"].astype(str).str.upper()) if os.path.exists(FNO) else set()
    d["is_cash"] = ~d["Symbol"].isin(fno)
    # ceiling / floor per Amendment 1: the nearest HVN, value-area edge only as fallback
    d["ceiling"] = d["hvn_above"].fillna(d["vah"])
    d["floor"] = d["hvn_below"].fillna(d["val"])
    return d


def split_is_oos(d: pd.DataFrame):
    anchors = sorted(d["as_of"].unique())
    cut = anchors[int(len(anchors) * 0.6)]
    return d[d["as_of"] < cut], d[d["as_of"] >= cut], cut


def boot_diff(d: pd.DataFrame, mask_a, mask_b, value, n=BOOT):
    """Bootstrap the (a - b) difference, resampling SYMBOLS not trades.

    Consecutive trades on one name share an outcome window, so a trade-level resample
    overstates n — rule 4 of the pre-registration.
    """
    syms = d["Symbol"].unique()
    out = []
    by = {s: g for s, g in d.groupby("Symbol")}
    for _ in range(n):
        pick = RNG.choice(syms, size=len(syms), replace=True)
        g = pd.concat([by[s] for s in pick], ignore_index=True)
        a, b = g[mask_a(g)][value], g[mask_b(g)][value]
        if len(a) < 5 or len(b) < 5:
            continue
        out.append(a.mean() - b.mean())
    return np.array(out)


def p_one_sided(samples: np.ndarray, direction: str) -> float:
    """Directional p: the share of resamples that contradict the hypothesis."""
    if samples.size == 0:
        return 1.0
    return float((samples >= 0).mean() if direction == "neg" else (samples <= 0).mean())


def holm(pvals: dict, alpha=0.10) -> dict:
    """Holm-Bonferroni. The pre-registration's answer to ~100 uncorrected variants."""
    order = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, blocked = len(order), {}, False
    for i, (k, p) in enumerate(order):
        thr = alpha / (m - i)
        ok = (p <= thr) and not blocked
        if not ok:
            blocked = True
        out[k] = {"p": p, "thr": thr, "survives": ok}
    return out


def cell(d, name):
    return "%s n=%d" % (name, len(d))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--placebo", action="store_true",
                    help="shuffle the level columns — results are noise by construction")
    a = ap.parse_args()

    d = load()
    if a.placebo:
        cols = ["poc", "vah", "val", "avwap_bo", "hvn_above", "hvn_below",
                "ceiling", "floor", "deliv_ratio"]
        idx = RNG.permutation(len(d))
        for c in cols:
            d[c] = d[c].to_numpy()[idx]
        print("*** PLACEBO — levels shuffled across trades. Any 'pass' here is a BUG. ***\n")

    print("trades %d · cash-only %d · F&O %d" % (len(d), d["is_cash"].sum(), (~d["is_cash"]).sum()))
    print("families:", d["family"].value_counts().to_dict())
    is_, oos, cut = split_is_oos(d)
    print("IS/OOS split at %s — IS %d, OOS %d\n" % (cut, len(is_), len(oos)))

    results, pvals = {}, {}
    cash = d[d["is_cash"]].copy()

    # ---------------------------------------------------------------- H0 validity
    print("=" * 78)
    print("H0  construct validity — do the cash levels locate the options levels?")
    print("=" * 78)
    fno = d[~d["is_cash"]].copy()
    h0 = None
    try:
        f = pd.read_csv(FNO)
        f["symbol"] = f["symbol"].astype(str).str.upper()
        f = f.rename(columns={"date": "as_of"})
        m = fno.merge(f[["as_of", "symbol", "call_wall", "max_pain"]],
                      left_on=["Symbol", "as_of"], right_on=["symbol", "as_of"], how="inner")
        m = m[m["atr"] > 0]
        mm = m.dropna(subset=["ceiling", "call_wall"])
        pp = m.dropna(subset=["poc", "max_pain"])
        if len(mm) >= 20 and len(pp) >= 20:
            d_ceil = (mm["ceiling"] - mm["call_wall"]).abs() / mm["atr"]
            d_poc = (pp["poc"] - pp["max_pain"]).abs() / pp["atr"]
            sh_ceil = (mm["ceiling"].to_numpy() -
                       RNG.permutation(mm["call_wall"].to_numpy()))
            sh_ceil = np.abs(sh_ceil) / mm["atr"].to_numpy()
            sh_poc = np.abs(pp["poc"].to_numpy() -
                            RNG.permutation(pp["max_pain"].to_numpy())) / pp["atr"].to_numpy()
            print("  ceiling vs call wall : median %.2f ATR (n=%d) · shuffled %.2f"
                  % (d_ceil.median(), len(mm), np.median(sh_ceil)))
            print("  POC     vs max pain  : median %.2f ATR (n=%d) · shuffled %.2f"
                  % (d_poc.median(), len(pp), np.median(sh_poc)))
            h0 = bool(d_ceil.median() <= 1.0 and d_poc.median() <= 1.0
                      and d_ceil.median() < np.median(sh_ceil)
                      and d_poc.median() < np.median(sh_poc))
            print("  VERDICT: %s" % ("PASS — the substitutes locate the same prices" if h0
                                     else "FAIL — they do not locate the same prices"))
        else:
            print("  THIN — %d ceiling / %d poc pairs, need 20" % (len(mm), len(pp)))
    except Exception as e:
        print("  NOT RUN — %s" % e)
    results["H0"] = h0

    # ---------------------------------------------------------------- H1
    print("\n" + "=" * 78)
    print("H1  a T1 beyond the ceiling is reached LESS often   (bar: >=10pp, n>=40)")
    print("=" * 78)
    h1 = cash.dropna(subset=["ceiling", "Hit_T1", "T1_price"]).copy()
    h1["beyond"] = h1["T1_price"] > h1["ceiling"]
    for fam in ["ALL"] + sorted(h1["family"].unique()):
        g = h1 if fam == "ALL" else h1[h1["family"] == fam]
        a_, b_ = g[g["beyond"]], g[~g["beyond"]]
        if len(a_) < 40 or len(b_) < 40:
            print("  %-10s THIN (%s / %s)" % (fam, cell(a_, "beyond"), cell(b_, "below")))
            continue
        diff = (a_["Hit_T1"].mean() - b_["Hit_T1"].mean()) * 100
        print("  %-10s beyond %.1f%% (n=%d) vs below %.1f%% (n=%d)  ->  %+.1fpp"
              % (fam, a_["Hit_T1"].mean() * 100, len(a_), b_["Hit_T1"].mean() * 100,
                 len(b_), diff))
        if fam == "ALL":
            s = boot_diff(g, lambda x: x["beyond"], lambda x: ~x["beyond"], "Hit_T1")
            pvals["H1"] = p_one_sided(s * 100, "neg")
            results["H1"] = bool(diff <= -10.0)
            print("       bootstrap p(one-sided) = %.3f" % pvals["H1"])

    # ---------------------------------------------------------------- H2
    print("\n" + "=" * 78)
    print("H2  NOT RUN (Amendment 3) — needs a bar-level replay of the partial ladder")
    print("=" * 78)
    b = cash.dropna(subset=["ceiling", "T1_price"])
    bind = b[b["T1_price"] > b["ceiling"]]
    print("  observation only, no pass/fail: a cap would have bound on %d of %d cash trades"
          % (len(bind), len(b)))
    if len(bind):
        reach = bind["Max_Runup_pct"] >= ((bind["ceiling"] / bind["Entry_Close"]) - 1) * 100
        print("  of those, price reached the capped level in %d (%.0f%%), and the shipped"
              % (reach.sum(), 100 * reach.mean()))
        print("  plan's own T1 in %d (%.0f%%)" % (bind["Hit_T1"].sum(), 100 * bind["Hit_T1"].mean()))
    results["H2"] = None

    # ---------------------------------------------------------------- H3
    print("\n" + "=" * 78)
    print("H3  a stop ABOVE the floor stops out MORE (Amendment 2)   (bar: >=8pp, n>=40)")
    print("=" * 78)
    h3 = cash.dropna(subset=["floor", "Hit_Initial_SL", "SL_price"]).copy()
    h3["stop_above"] = h3["SL_price"] > h3["floor"]
    a_, b_ = h3[h3["stop_above"]], h3[~h3["stop_above"]]
    if len(a_) < 40 or len(b_) < 40:
        print("  THIN (%s / %s)" % (cell(a_, "above"), cell(b_, "below")))
    else:
        diff = (a_["Hit_Initial_SL"].mean() - b_["Hit_Initial_SL"].mean()) * 100
        print("  stop above floor %.1f%% (n=%d) vs below %.1f%% (n=%d)  ->  %+.1fpp"
              % (a_["Hit_Initial_SL"].mean() * 100, len(a_),
                 b_["Hit_Initial_SL"].mean() * 100, len(b_), diff))
        s = boot_diff(h3, lambda x: x["stop_above"], lambda x: ~x["stop_above"], "Hit_Initial_SL")
        pvals["H3"] = p_one_sided(s * 100, "pos")
        results["H3"] = bool(diff >= 8.0)
        print("       bootstrap p(one-sided) = %.3f" % pvals["H3"])

    # ---------------------------------------------------------------- H4
    print("\n" + "=" * 78)
    print("H4  POC between entry and T1 drags the target, and the pull WEAKENS with distance")
    print("=" * 78)
    h4 = cash.dropna(subset=["poc", "T1_price", "Hit_T1"]).copy()
    h4 = h4[h4["atr"] > 0]
    h4["between"] = (h4["poc"] > h4["Entry_Close"]) & (h4["poc"] < h4["T1_price"])
    h4["dist"] = (h4["poc"] - h4["Entry_Close"]).abs() / h4["atr"]
    near, far = h4[h4["dist"] <= 1.0], h4[h4["dist"] > 2.0]
    for nm, g in (("near (<=1 ATR)", near), ("far (>2 ATR)", far)):
        a_, b_ = g[g["between"]], g[~g["between"]]
        if len(a_) < 40 or len(b_) < 40:
            print("  %-16s THIN (%s / %s)" % (nm, cell(a_, "between"), cell(b_, "not")))
            continue
        print("  %-16s between %.1f%% (n=%d) vs not %.1f%% (n=%d)  ->  %+.1fpp"
              % (nm, a_["Hit_T1"].mean() * 100, len(a_), b_["Hit_T1"].mean() * 100, len(b_),
                 (a_["Hit_T1"].mean() - b_["Hit_T1"].mean()) * 100))
    a_, b_ = h4[h4["between"]], h4[~h4["between"]]
    if len(a_) >= 40 and len(b_) >= 40:
        diff = (a_["Hit_T1"].mean() - b_["Hit_T1"].mean()) * 100
        print("  %-16s between %.1f%% vs not %.1f%%  ->  %+.1fpp"
              % ("pooled", a_["Hit_T1"].mean() * 100, b_["Hit_T1"].mean() * 100, diff))
        s = boot_diff(h4, lambda x: x["between"], lambda x: ~x["between"], "Hit_T1")
        pvals["H4"] = p_one_sided(s * 100, "neg")
        results["H4"] = bool(diff <= -8.0)
        print("       bootstrap p(one-sided) = %.3f" % pvals["H4"])

    # ---------------------------------------------------------------- H5
    print("\n" + "=" * 78)
    print("H5  entries on RISING delivery outperform   (bar: >=+0.15R, IS and OOS)")
    print("=" * 78)
    h5 = cash.dropna(subset=["deliv_ratio", "R"]).copy()
    h5["rising"] = h5["deliv_ratio"] >= 1.0
    for nm, g in (("IS", h5[h5["as_of"] < cut]), ("OOS", h5[h5["as_of"] >= cut]),
                  ("ALL", h5)):
        a_, b_ = g[g["rising"]], g[~g["rising"]]
        if len(a_) < 40 or len(b_) < 40:
            print("  %-4s THIN (%s / %s)" % (nm, cell(a_, "rising"), cell(b_, "falling")))
            continue
        diff = a_["R"].mean() - b_["R"].mean()
        print("  %-4s rising %+.3fR (n=%d) vs falling %+.3fR (n=%d)  ->  %+.3fR"
              % (nm, a_["R"].mean(), len(a_), b_["R"].mean(), len(b_), diff))
        if nm == "ALL":
            s = boot_diff(h5, lambda x: x["rising"], lambda x: ~x["rising"], "R")
            pvals["H5"] = p_one_sided(s, "pos")
            results["H5"] = bool(diff >= 0.15)
            print("       bootstrap p(one-sided) = %.3f" % pvals["H5"])

    # ---------------------------------------------------------------- verdicts
    print("\n" + "=" * 78)
    print("VERDICTS — effect-size bar AND Holm-Bonferroni at family-wise alpha 0.10")
    print("=" * 78)
    hb = holm(pvals) if pvals else {}
    for k in ["H1", "H2", "H3", "H4", "H5"]:
        if k == "H2":
            print("  H2  NOT RUN (Amendment 3)")
            continue
        size = results.get(k)
        h = hb.get(k)
        if size is None or h is None:
            print("  %s  NOT RUN / THIN" % k)
            continue
        verdict = "PASS" if (size and h["survives"]) else (
            "suggestive, NOT passing" if size else "FAIL")
        print("  %s  size bar %-5s · p %.3f vs Holm threshold %.3f · %s"
              % (k, "met" if size else "missed", h["p"], h["thr"], verdict))
    print("\nH0 (validity gate): %s" % {True: "PASS", False: "FAIL", None: "not run"}[results["H0"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
