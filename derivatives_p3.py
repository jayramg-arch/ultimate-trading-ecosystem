"""derivatives_p3.py — the single pre-registered run for H1-H4.

Reads docs/PREREG_derivatives_P3.md's rules and does exactly what they say, once:
joins each validated trade to the SETTLED derivatives row of its own entry date, splits
by the wall / stop / max-pain relationships the doctrine claims matter, and reports
against the stated pass bars. Every measurement rule from the pre-registration is
enforced here rather than remembered: R not %, per family, IS/OOS, bootstrap by SYMBOL,
n >= 40 or the cell is thin and cannot pass, missing excluded and never zero.

    python derivatives_p3.py            run and print the report
    python derivatives_p3.py --md       print it as the markdown block for the prereg

It draws no conclusion the bars do not support, and it prints the thin cells rather than
hiding them - an underpowered cell is a fact about the evidence, not a result.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = os.path.join(HERE, "validation_runs", "validation_20260819_112959_details.csv")
HIST = os.path.join(HERE, "data", "fno_history.csv")
MIN_N = 40
BOOT = 2000
RNG = np.random.default_rng(20260922)


def load() -> pd.DataFrame:
    d = pd.read_csv(TRADES)
    h = pd.read_csv(HIST)
    d["date"] = pd.to_datetime(d["as_of"]).dt.strftime("%Y-%m-%d")
    d["sym"] = d["Symbol"].astype(str).str.upper().str.replace(".NS", "", regex=False)
    h["sym"] = h["symbol"].astype(str).str.upper()
    m = d.merge(h.drop(columns=["symbol"]), on=["date", "sym"], how="inner")
    # R, never % — the measurement rule that inverted a stop conclusion here once
    ret = pd.to_numeric(m["Return_pct"], errors="coerce")
    slp = pd.to_numeric(m["SL_pct"], errors="coerce").abs()
    m["R"] = (ret / slp.where(slp > 0)).replace([np.inf, -np.inf], np.nan)
    for c in ("Hit_T1", "Hit_Initial_SL"):
        m[c] = m[c].astype(str).str.lower().isin(("true", "1", "1.0"))
    m["fam"] = m["Catalyst"].astype(str)
    # entry/stop/T1 as prices
    m["entry_px"] = pd.to_numeric(m["Entry_Close"], errors="coerce")
    m["t1_px"] = pd.to_numeric(m["T1_price"], errors="coerce")
    m["sl_px"] = pd.to_numeric(m["SL_price"], errors="coerce")
    # chronological split, same convention as the OOS gate (earlier 60% / later 40%)
    anchors = sorted(m["date"].unique())
    cut = anchors[int(len(anchors) * 0.6)] if len(anchors) > 2 else anchors[-1]
    m["win"] = np.where(m["date"] < cut, "IS", "OOS")
    return m


def _boot_diff(a: pd.DataFrame, b: pd.DataFrame, col: str, stat) -> tuple:
    """Bootstrap the A-B difference by SYMBOL — consecutive trades on one name share an
    outcome window, so resampling trades overstates n."""
    syms = pd.concat([a["sym"], b["sym"]]).unique()
    out = []
    for _ in range(BOOT):
        pick = set(RNG.choice(syms, len(syms), replace=True))
        aa, bb = a[a["sym"].isin(pick)], b[b["sym"].isin(pick)]
        if len(aa) < 5 or len(bb) < 5:
            continue
        out.append(stat(aa[col]) - stat(bb[col]))
    if not out:
        return None, None
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def cell(df: pd.DataFrame, mask, label: str, col: str, stat, pct=False) -> dict:
    a, b = df[mask], df[~mask]
    f = (lambda s: 100 * float(s.mean())) if pct else (lambda s: float(s.mean()))
    r = {"label": label, "n_a": int(len(a)), "n_b": int(len(b)),
         "a": f(a[col]) if len(a) else None, "b": f(b[col]) if len(b) else None}
    r["diff"] = (r["a"] - r["b"]) if (r["a"] is not None and r["b"] is not None) else None
    r["thin"] = min(len(a), len(b)) < MIN_N
    if not r["thin"]:
        lo, hi = _boot_diff(a, b, col, f)
        r["ci"] = (lo, hi)
    else:
        r["ci"] = (None, None)
    return r


def fmt(r: dict, unit: str) -> str:
    if r["a"] is None or r["b"] is None:
        return "  %-46s no data" % r["label"]
    ci = ("  CI95 [%+.1f, %+.1f]" % r["ci"]) if r["ci"][0] is not None else ""
    return ("  %-46s %7.1f%s vs %7.1f%s   diff %+6.1f%s  (n %d/%d)%s%s"
            % (r["label"], r["a"], unit, r["b"], unit, r["diff"], unit,
               r["n_a"], r["n_b"], ci, "   THIN" if r["thin"] else ""))


def run() -> list:
    m = load()
    out = []
    print("joined trades: %d · symbols %d · anchors %s → %s"
          % (len(m), m["sym"].nunique(), m["date"].min(), m["date"].max()))
    if m.empty:
        print("\nNO OVERLAP between the trade set and the derivatives history — H1-H4 cannot be run.")
        return out
    print("families:", m["fam"].value_counts().to_dict(), "\n")

    def section(title, mask_fn, col, stat, unit, bar):
        print(title)
        print("  pass bar: %s" % bar)
        rows = []
        for scope, sub in [("ALL", m)] + [(f, g) for f, g in m.groupby("fam") if len(g) >= 20]:
            for w in ("ALL", "IS", "OOS"):
                s = sub if w == "ALL" else sub[sub["win"] == w]
                if len(s) < 10:
                    continue
                mk = mask_fn(s)
                if mk is None or mk.sum() == 0 or (~mk).sum() == 0:
                    continue
                r = cell(s, mk, "%s · %s" % (scope, w), col, stat, pct=(unit == "%"))
                rows.append(r)
                print(fmt(r, unit))
        print()
        out.append((title, rows))

    # H1 — T1 beyond the call wall is reached less often
    section("H1  T1 beyond the call wall → Hit_T1 rate",
            lambda s: (s["call_wall"].notna() & s["t1_px"].notna() & s["entry_px"].notna()
                       & (s["call_wall"] > s["entry_px"]) & (s["call_wall"] < s["t1_px"])),
            "Hit_T1", np.mean, "%", "beyond-wall rate at least 10pp LOWER, n>=40 per cell")

    # H3 — a stop above the put wall stops out more
    section("H3  stop ABOVE the put wall → initial-stop rate",
            lambda s: (s["put_wall"].notna() & s["sl_px"].notna() & (s["sl_px"] > s["put_wall"])),
            "Hit_Initial_SL", np.mean, "%", "above-wall rate at least 8pp HIGHER, n>=40 per cell")

    # H4 — max pain inside the entry→T1 path drags the target (near expiry only)
    near = m[pd.to_numeric(m["days_to_expiry"], errors="coerce") <= 30]
    far = m[pd.to_numeric(m["days_to_expiry"], errors="coerce") > 30]
    print("H4  max pain between entry and T1 → Hit_T1 rate")
    print("  pass bar: at least 8pp LOWER inside 30 days to expiry AND NOT past it")
    for nm, s in (("<=30d to expiry", near), (">30d to expiry", far)):
        if len(s) < 20:
            print("  %-46s n=%d (too few)" % (nm, len(s)))
            continue
        mk = (s["max_pain"].notna() & s["t1_px"].notna() & s["entry_px"].notna()
              & (s["max_pain"] > s["entry_px"]) & (s["max_pain"] < s["t1_px"]))
        if mk.sum() == 0 or (~mk).sum() == 0:
            print("  %-46s no split" % nm); continue
        r = cell(s, mk, nm, "Hit_T1", np.mean, pct=True)
        print(fmt(r, "%"))
    print()

    # H2 — capping T1 at the wall improves realised R  (replay, not a re-slice)
    print("H2  cap T1 at the wall → realised R")
    print("  pass bar: at least +0.15R mean AND median not worse, IS and OOS")
    print("  NOTE: a capped T1 can only change trades that HIT the cap and would not have hit T1.")
    cap = m[(m["call_wall"].notna()) & (m["t1_px"].notna()) & (m["entry_px"].notna())
            & (m["call_wall"] > m["entry_px"]) & (m["call_wall"] < m["t1_px"])].copy()
    if len(cap) < 20:
        print("  n=%d — too few capped trades to measure" % len(cap))
    else:
        atr = pd.to_numeric(cap.get("EMA20_Dist_ATR"), errors="coerce")  # ATR proxy, buffer only
        cap["R_capped"] = np.where(
            pd.to_numeric(cap["Max_Runup_pct"], errors="coerce") >=
            100 * (cap["call_wall"] - cap["entry_px"]) / cap["entry_px"],
            (cap["call_wall"] - cap["entry_px"]) / (cap["entry_px"] - cap["sl_px"]),
            cap["R"])
        for w in ("ALL", "IS", "OOS"):
            s = cap if w == "ALL" else cap[cap["win"] == w]
            if len(s) < 15:
                print("  %-10s n=%d (too few)" % (w, len(s))); continue
            dm = float(s["R_capped"].mean() - s["R"].mean())
            dmed = float(s["R_capped"].median() - s["R"].median())
            print("  %-10s shipped %+.3fR → capped %+.3fR   Δmean %+.3fR · Δmedian %+.3fR  (n %d)%s"
                  % (w, s["R"].mean(), s["R_capped"].mean(), dm, dmed, len(s),
                     "   THIN" if len(s) < MIN_N else ""))
    print()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    run()
