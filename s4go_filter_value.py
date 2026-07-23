"""s4go_filter_value.py — does GO-confirmation DISCRIMINATE among catalyst picks? (23 Jul 2026)

The entry A/Bs proved GO-timing can't beat buy@close on entry alpha (wait tax). This
scores GO on the RIGHT axis: as a SELECTION filter. Among the SAME catalyst picks
(buy@close baseline), do the ones that go on to confirm a GO within the entry window
have better buy@close outcomes than the ones that never confirm?

Result (2026-07): CONFIRMED +3.36% vs NEVER -1.32% -> +4.68pp mean / +9.6pp win edge,
concentrated in positional families (POS-ACCUM +10.6pp, POS/WYC +8.5pp; SWG +0.4pp).
=> GM+S4's alpha lives in SELECTION (which positional catalyst names to trust/size),
not entry timing. Reposition GO from entry-gate to conviction/quality filter.

Caveat: partial endogeneity (a name that never triggers never got momentum); the
win-rate gap (threshold metric) argues the discrimination is real, not just coupling.

Inputs (existing artifacts, no re-sim):
  BASELINE  = buy@close catalyst picks with per-trade matched alpha
  GO_RUN    = s4go catalyst run (Status != 'no GO in window' => a confirming GO fired)
"""
import pandas as pd, numpy as np

BASELINE = "validation_runs/validation_20260722_135745_details.csv"
GO_RUN   = "validation_runs/validation_20260723_063652_details.csv"


def fam(c):
    c = str(c)
    if c.startswith("POS-ACCUM"): return "POS-ACCUM"
    if c.startswith("POS") or c.startswith("WYC"): return "POS/WYC"
    if c.startswith("SWG"): return "SWG"
    if c.startswith("REV"): return "REV"
    return c


def main():
    b = pd.read_csv(BASELINE)
    b["am"] = pd.to_numeric(b["Alpha_Matched_pct"], errors="coerce")
    b = b[b["am"].notna()].copy()
    b["key"] = b["as_of"].astype(str) + "|" + b["Symbol"].astype(str)

    g = pd.read_csv(GO_RUN)
    g["key"] = g["as_of"].astype(str) + "|" + g["Symbol"].astype(str)
    g["go_fired"] = g["Status"].astype(str) != "no GO in window"
    gmap = g.groupby("key")["go_fired"].max()

    b["go_fired"] = b["key"].map(gmap)
    shared = sorted(set(b["as_of"]) & set(g["as_of"]))
    j = b[b["as_of"].isin(shared) & b["go_fired"].notna()].copy()
    j["go_fired"] = j["go_fired"].astype(bool)

    def stat(x):
        x = x["am"]
        return f"n={len(x):4d}  mean={x.mean():+.2f}%  median={x.median():+.2f}%  win={(x>0).mean()*100:5.1f}%"

    C, N = j[j["go_fired"]], j[~j["go_fired"]]
    print(f"shared anchors {len(shared)} | picks {len(j)} | confirmed {len(C)} | never {len(N)}")
    print("\n=== BUY@CLOSE outcome, split by whether a confirming GO fired ===")
    print("  GO-CONFIRMED ", stat(C))
    print("  GO-NEVER     ", stat(N))
    print(f"  --> discriminatory edge {C['am'].mean()-N['am'].mean():+.2f}pp mean | "
          f"{C['am'].gt(0).mean()*100-N['am'].gt(0).mean()*100:+.1f}pp win")

    j["fam"] = j["Catalyst_used"].fillna(j["Catalyst"]).map(fam)
    j["dir"] = np.where(j["Regime"].astype(str).str.contains("BULL", case=False), "UP", "DOWN")
    print("\n=== by family ===")
    for f, gg in j.groupby("fam"):
        c, n = gg[gg["go_fired"]]["am"], gg[~gg["go_fired"]]["am"]
        ed = f"{c.mean()-n.mean():+.2f}pp" if len(c) and len(n) else "-"
        print(f"  {f:10} CONFIRMED {c.mean():+.2f}% (n={len(c):3d})   NEVER {n.mean():+.2f}% (n={len(n):3d})   edge {ed}")
    print("\n=== by direction ===")
    for d, gg in j.groupby("dir"):
        c, n = gg[gg["go_fired"]]["am"], gg[~gg["go_fired"]]["am"]
        ed = f"{c.mean()-n.mean():+.2f}pp" if len(c) and len(n) else "-"
        print(f"  {d:4} CONFIRMED {c.mean():+.2f}% (n={len(c):3d})   NEVER {n.mean():+.2f}% (n={len(n):3d})   edge {ed}")


if __name__ == "__main__":
    main()
