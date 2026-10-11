"""pca_study.py (11-Oct-2026) - Principal Component Analysis of the entry-time metrics.

Question (Jay): the board/S4 GATE names but do not RANK them, and most tracked metrics
never touch selection. Does the metric set contain independent, outcome-predicting
structure that a ranking should use?

Data: validation details (bull, 24mo Nifty 500, catalyst-aware) - every row is one
trade with its metrics AS OF ENTRY and its outcome. Outcome measured in R
(Return_pct / SL_pct) and in matched alpha. Rules, set before looking:
  * PCA is fitted on the IN-SAMPLE period only (first 60% of anchors by date) and the
    same loadings are applied out of sample - no look-ahead into the components.
  * Every number is reported IS and OOS; a signal must hold in both.
  * Confidence intervals bootstrap by SYMBOL (trades on one name share outcomes).
  * Many features are tested, so p-values get a Benjamini-Hochberg correction.
  * Families (POS / SWG) are also reported separately - pooling has misled us before.
Run:  python pca_study.py [run_id]
"""
import json, sys
import numpy as np
import pandas as pd

RUN = sys.argv[1] if len(sys.argv) > 1 else "20260819_112959"
FEATS = ["Score", "Catalyst_Score", "Alpha", "Stage", "JdK_RS_Ratio", "JdK_RS_Momentum",
         "RRG_Score", "Rel_Vol", "RSI", "VCP_Score", "Days_Since_Pivot", "SL_pct",
         "Swing_Pct_Current", "IC_Ratio", "Leg_Vel_Pct", "Vel_Accel", "EMA20_Dist_ATR",
         "Conviction", "Combined_Score", "Counter_Trend", "Broke_Pivot", "VCP_Valid"]
B = 2000
rng = np.random.default_rng(7)


def spearman(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 15:
        return np.nan
    return pd.Series(x[m]).rank().corr(pd.Series(y[m]).rank())


def perm_p(x, y, n=2000):
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 15:
        return np.nan
    r0 = abs(spearman(x, y))
    yr = pd.Series(y).rank().values
    xr = pd.Series(x).rank().values
    c = 0
    for _ in range(n):
        if abs(np.corrcoef(xr, rng.permutation(yr))[0, 1]) >= r0:
            c += 1
    return (c + 1) / (n + 1)


def bh(p):
    p = np.asarray(p, float); n = np.isfinite(p).sum()
    order = np.argsort(np.where(np.isfinite(p), p, 9)); q = np.full_like(p, np.nan)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order[:n], 1))):
        prev = min(prev, p[i] * n / rank); q[i] = prev
    return q


def sym_boot_spread(df, col, ycol):
    """Top-tercile minus bottom-tercile mean R, symbol-block bootstrap CI."""
    syms = df["Symbol"].unique()
    g = {s: df[df.Symbol == s] for s in syms}
    def spread(d):
        lo, hi = d[col].quantile([1 / 3, 2 / 3])
        return d.loc[d[col] >= hi, ycol].mean() - d.loc[d[col] <= lo, ycol].mean()
    est = spread(df)
    bs = []
    for _ in range(B):
        d = pd.concat([g[s] for s in rng.choice(syms, len(syms))])
        bs.append(spread(d))
    return est, np.nanpercentile(bs, 2.5), np.nanpercentile(bs, 97.5)


def main():
    d = pd.read_csv(f"validation_runs/validation_{RUN}_details.csv")
    d = d[d["Status"].astype(str).str.upper().isin(["OK", "CLOSED", "FILLED", "DONE"]) | d["Return_pct"].notna()]
    d = d[d["Return_pct"].notna() & (pd.to_numeric(d["SL_pct"], errors="coerce") > 0)].copy()
    for c in ("Counter_Trend", "Broke_Pivot", "VCP_Valid"):
        d[c] = d[c].astype(str).str.lower().isin(["true", "1", "yes"]).astype(float)
    for c in FEATS:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["R"] = d["Return_pct"] / d["SL_pct"]
    d["A"] = pd.to_numeric(d["Alpha_Matched_pct"], errors="coerce")
    d["fam"] = d["Catalyst"].astype(str).str.split("-").str[0]
    anchors = sorted(d["as_of"].unique())
    cut = anchors[int(len(anchors) * 0.6)]
    d["win"] = np.where(d["as_of"] < cut, "IS", "OOS")
    feats = [f for f in FEATS if d[f].notna().mean() > 0.8 and d[f].std() > 0]
    out = {"run": RUN, "n": len(d), "split_at": cut, "features": feats}
    print(f"run {RUN}: {len(d)} trades, {d.Symbol.nunique()} symbols, split {cut} "
          f"(IS {sum(d.win=='IS')} / OOS {sum(d.win=='OOS')})")
    print("features used:", ", ".join(feats))

    # ---- 1. how much independent information is in the metric set? --------------
    IS = d[d.win == "IS"]
    mu, sd = IS[feats].mean(), IS[feats].std()
    Z = ((d[feats] - mu) / sd).fillna(0.0)
    C = np.corrcoef(Z[d.win == "IS"].values.T)
    ev, evec = np.linalg.eigh(C)
    idx = ev.argsort()[::-1]; ev, evec = ev[idx], evec[:, idx]
    share = ev / ev.sum()
    pr = ev.sum() ** 2 / (ev ** 2).sum()          # participation ratio = effective dims
    print(f"\n1) {len(feats)} metrics -> effective dimensions (participation ratio) {pr:.1f}")
    print("   variance share by component:", " ".join(f"PC{i+1} {s:.0%}" for i, s in enumerate(share[:8])))
    k = int((np.cumsum(share) < 0.80).sum() + 1)
    print(f"   components needed for 80% of the variance: {k}")
    out.update(eff_dims=pr, var_share=share.tolist(), k80=k)
    # strongly redundant pairs
    pairs = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            if abs(C[i, j]) >= 0.6:
                pairs.append((feats[i], feats[j], round(C[i, j], 2)))
    print("   redundant pairs |r|>=0.6:", pairs if pairs else "none")
    out["redundant_pairs"] = pairs
    scores = Z.values @ evec
    npc = min(8, len(feats))
    for i in range(npc):
        sgn = 1.0
        d[f"PC{i+1}"] = scores[:, i] * sgn
    print("\n   loadings (top 4 per component):")
    load = {}
    for i in range(npc):
        top = sorted(zip(feats, evec[:, i]), key=lambda t: -abs(t[1]))[:4]
        load[f"PC{i+1}"] = [(f, round(v, 2)) for f, v in top]
        print(f"   PC{i+1} ({share[i]:.0%}):", ", ".join(f"{f} {v:+.2f}" for f, v in top))
    out["loadings"] = load

    # ---- 2. does any metric or component predict the outcome? -------------------
    rows = []
    for col in feats + [f"PC{i+1}" for i in range(npc)]:
        r_is = spearman(d.loc[d.win == "IS", col].values, d.loc[d.win == "IS", "R"].values)
        r_oos = spearman(d.loc[d.win == "OOS", col].values, d.loc[d.win == "OOS", "R"].values)
        p_oos = perm_p(d.loc[d.win == "OOS", col].values, d.loc[d.win == "OOS", "R"].values, 1000)
        a_oos = spearman(d.loc[d.win == "OOS", col].values, d.loc[d.win == "OOS", "A"].values)
        rows.append(dict(metric=col, rho_IS=r_is, rho_OOS=r_oos, p_OOS=p_oos, rhoAlpha_OOS=a_oos))
    t = pd.DataFrame(rows)
    t["q_OOS"] = bh(t["p_OOS"].values)
    t["same_sign"] = np.sign(t.rho_IS) == np.sign(t.rho_OOS)
    t = t.sort_values("rho_OOS", key=lambda s: -s.abs())
    print("\n2) rank correlation with R (Spearman), IS vs OOS; q = BH-corrected OOS p")
    print(t.to_string(index=False, float_format=lambda v: f"{v:+.3f}"))
    out["predictive"] = t.round(4).to_dict("records")

    # ---- 3. the ranking test: top vs bottom tercile, OOS, per family ------------
    print("\n3) tercile spread (top - bottom mean R), OOS, symbol-block bootstrap 95% CI")
    cands = ["Combined_Score", "Score", "Conviction", "Alpha", "RRG_Score", "PC1", "PC2", "PC3"]
    best = t[t.metric.str.startswith("PC") == False].head(3).metric.tolist()
    res = []
    for col in dict.fromkeys(cands + best):
        if col not in d:
            continue
        for fam in ("ALL", "POS", "SWG"):
            sub = d[(d.win == "OOS") & ((d.fam == fam) | (fam == "ALL"))].dropna(subset=[col, "R"])
            if len(sub) < 45:
                continue
            est, lo, hi = sym_boot_spread(sub, col, "R")
            res.append(dict(metric=col, family=fam, n=len(sub), spread_R=est, ci_lo=lo, ci_hi=hi))
            print(f"   {col:16s} {fam:3s} n={len(sub):3d}  spread {est:+.2f}R  CI [{lo:+.2f}, {hi:+.2f}]"
                  + ("   <- excludes 0" if lo > 0 or hi < 0 else ""))
    out["tercile"] = res

    # ---- 4. outcome profile, for context ----------------------------------------
    print("\n4) outcome profile: mean R {:+.2f}, median R {:+.2f}, P(R>=2) {:.0%}, P(R<=-0.9) {:.0%}".format(
        d.R.mean(), d.R.median(), (d.R >= 2).mean(), (d.R <= -0.9).mean()))
    json.dump(out, open(f"reports/pca_study_{RUN}.json", "w"), indent=1, default=float)
    print(f"\nwritten reports/pca_study_{RUN}.json")


if __name__ == "__main__":
    main()
