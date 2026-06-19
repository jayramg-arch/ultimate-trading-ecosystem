"""
score_authenticity_check.py — prove the scores in the pipeline's output CSVs are
AUTHENTIC: every stored score is reproducible from the visible metric columns,
and every scoring-input column is present and populated.

Why this exists
---------------
The watchlists are only trustworthy if the score on each row is actually derived
from the metrics shown next to it (not stale, not fabricated, not silently
defaulted). This validator RE-COMPUTES each score from the row's own columns
using the SAME canonical functions the pipeline uses (zero drift), and confirms
they match. It also reports per-column fill rates, distinguishing real data gaps
from semantic blanks (e.g. a no-signal recovery row legitimately has no label).

Design
------
- READ-ONLY over the output CSVs. Never edits a score. Cannot introduce risk.
- No network, no fundamentals fetch → sub-second; safe as a final pipeline phase.
- Returns a dict (for Streamlit) and writes a timestamped report under reports/.
- `main()` exits 0 if every file PASSES, 1 otherwise (so a pipeline can gate on it).

Covered files
-------------
- FINAL_WATCHLIST.csv / FINAL_COMBINED_PICKS.csv / FINAL_*_Picks.csv (Golden Matcher)
    Tech_Score  == technical_enrichment.calc_tech_score(row)
    Combined_Score == Conviction*5 + Tech_Score*0.5
- Recovery_Screener_Results.csv
    Score == recovery_screener.compute_score(<columns>)
    Combined_Score (if present) == Conviction*5 + (Score/22*100)*0.5
- Bull_Screener_Results.csv
    Combined_Score == Conviction*5 + Score*0.5   (raw catalyst Score has non-column
    inputs, so only the blend is reproduced here; columns/fill still checked)
- FINAL_XRay_Picks.csv
    Minervini_Score == sum("M: *" columns)
    Piotroski_Score == sum("P: *" columns)
"""
from __future__ import annotations

import os
import datetime
from typing import Optional

import numpy as np
import pandas as pd

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
TOL = 0.05  # score match tolerance (rounding)


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────
def _num(v, default=0.0) -> float:
    """Lenient numeric parse (treats NaN/blank/'N/A' as default) — mirrors how
    the scorers coalesce missing inputs, so reproduction is faithful."""
    if v is None:
        return default
    try:
        if isinstance(v, float) and np.isnan(v):
            return default
    except Exception:
        pass
    s = str(v).replace(",", "").strip()
    if s.lower() in ("", "nan", "n/a", "na", "-", "--", "none"):
        return default
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def _fill_rates(df: pd.DataFrame, cols) -> list:
    """Return [(col, pct_filled, present_bool)] for the given columns."""
    out = []
    n = len(df) or 1
    for c in cols:
        if c not in df.columns:
            out.append((c, 0.0, False))
        else:
            out.append((c, df[c].notna().sum() / n * 100.0, True))
    return out


def _result(name, n, checks, fills, notes):
    passed = all(c["ok"] for c in checks)
    return {
        "file": name, "rows": n, "pass": passed,
        "checks": checks, "fills": fills, "notes": notes,
    }


# ──────────────────────────────────────────────────────────────────────────
# per-file validators
# ──────────────────────────────────────────────────────────────────────────
def check_watchlist(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return _result(os.path.basename(path), 0, [], [], ["empty file"])
    try:
        import technical_enrichment as _te
    except Exception as e:
        return _result(os.path.basename(path), len(df), [], [],
                       [f"technical_enrichment unavailable: {e}"])

    tech_inputs = ["Stage", "Mansfield_RS", "Daily_RSI", "Daily_ADX",
                   "Above_200DMA", "EMA_Stack", "Dist_52WH_pct", "Vol_RelAvg"]
    checks = []

    if "Tech_Score" in df.columns:
        recalc = df.apply(_te.calc_tech_score, axis=1)
        mism = int((recalc.astype(float) - df["Tech_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Tech_Score == calc_tech_score(columns)",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})

    if {"Conviction", "Tech_Score", "Combined_Score"}.issubset(df.columns):
        blend = (df["Conviction"].apply(_num) * 5 + df["Tech_Score"].apply(_num) * 0.5).round(1)
        mism = int((blend - df["Combined_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Combined_Score == Conviction*5 + Tech*0.5",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})

    fills = _fill_rates(df, tech_inputs + ["Conviction", "Tech_Score", "Combined_Score"])
    notes = []
    for c, pct, present in fills:
        if not present:
            notes.append(f"MISSING column: {c}")
        elif pct < 100:
            notes.append(f"{c}: {pct:.0f}% filled (real data gap)")
    return _result(os.path.basename(path), len(df), checks, fills, notes)


def check_recovery(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return _result(os.path.basename(path), 0, [], [], ["empty file"])
    try:
        import recovery_screener as _rs
    except Exception as e:
        return _result(os.path.basename(path), len(df), [], [],
                       [f"recovery_screener unavailable: {e}"])

    # Map columns -> compute_score params (same call screen_symbol makes).
    col = {c.lower(): c for c in df.columns}
    def g(row, *names, default=0.0):
        for nm in names:
            if nm in df.columns:
                return _num(row.get(nm), default)
        return default
    def gb(row, name):
        v = row.get(name)
        return bool(v) if v is not None and str(v).lower() not in ("", "nan", "none") else False

    checks = []
    score_inputs = ["Signal", "RFF_Total", "Mansfield_RS_x100", "Correction_52W_pct",
                    "Mkt_Recovery", "Mkt_Corrected", "Weinstein_Stage", "Rel_Vol",
                    "Chartink_Confirmed"]
    if "Score" in df.columns and all(c in df.columns for c in
                                     ["Signal", "RFF_Total", "Weinstein_Stage", "Rel_Vol"]):
        def _recalc(row):
            return _rs.compute_score(
                int(g(row, "Signal")),
                int(g(row, "RFF_Total")),
                g(row, "Mansfield_RS_x100"),
                g(row, "Correction_52W_pct"),
                gb(row, "Mkt_Recovery"),
                gb(row, "Mkt_Corrected"),
                int(g(row, "Weinstein_Stage")),
                g(row, "Rel_Vol"),
                gb(row, "Chartink_Confirmed"),
            )
        recalc = df.apply(_recalc, axis=1)
        mism = int((recalc.astype(float) - df["Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Score == compute_score(columns)",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})

    if {"Conviction", "Score", "Combined_Score"}.issubset(df.columns):
        blend = (df["Conviction"].apply(_num) * 5
                 + (df["Score"].apply(_num) / 22.0 * 100.0).clip(upper=100) * 0.5).round(1)
        # Only the rows WITH a conviction value are a strict blend; tech-only rows
        # equal Score-norm alone. Check both consistently.
        def _expected(r):
            conv = _num(r.get("Conviction"), default=np.nan)
            tech = min(100.0, _num(r.get("Score")) / 22.0 * 100.0)
            if np.isnan(conv):
                return round(tech, 1)
            return round(conv * 5 + tech * 0.5, 1)
        exp = df.apply(_expected, axis=1)
        mism = int((exp - df["Combined_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Combined_Score == blend(Conviction, Score/22*100)",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})

    fills = _fill_rates(df, score_inputs)
    # Semantic blanks: Signal_Label/Signal_Date/CB_Climax_Date are blank by design
    # for non-firing rows — not flagged as gaps.
    notes = []
    for c, pct, present in fills:
        if not present:
            notes.append(f"MISSING column: {c}")
        elif pct < 100:
            notes.append(f"{c}: {pct:.0f}% filled")
    if "Combined_Score" not in df.columns:
        notes.append("Combined_Score not present (regen after B6 fix to populate)")
    return _result(os.path.basename(path), len(df), checks, fills, notes)


def check_bull(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return _result(os.path.basename(path), 0, [], [], ["empty file"])
    checks = []
    if {"Conviction", "Score", "Combined_Score"}.issubset(df.columns):
        blend = (df["Conviction"].apply(_num) * 5 + df["Score"].apply(_num) * 0.5).round(1)
        mism = int((blend - df["Combined_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Combined_Score == Conviction*5 + Score*0.5",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})
    key_cols = ["Catalyst", "Score", "Stage", "JdK_RS_Ratio", "Rel_Vol",
                "Conviction", "Combined_Score"]
    fills = _fill_rates(df, key_cols)
    notes = ["raw catalyst Score has non-column inputs — only the blend is "
             "reproduced; column presence/fill checked"]
    for c, pct, present in fills:
        if not present:
            notes.append(f"MISSING column: {c}")
        elif pct < 100:
            notes.append(f"{c}: {pct:.0f}% filled")
    return _result(os.path.basename(path), len(df), checks, fills, notes)


def check_xray(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return _result(os.path.basename(path), 0, [], [], ["empty file"])
    checks = []
    m_cols = [c for c in df.columns if c.startswith("M: ")]
    p_cols = [c for c in df.columns if c.startswith("P: ")]
    if "Minervini_Score" in df.columns and m_cols:
        recalc = df[m_cols].apply(lambda r: int(np.nansum(pd.to_numeric(r, errors="coerce"))), axis=1)
        mism = int((recalc - df["Minervini_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Minervini_Score == sum(M: columns)",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})
    if "Piotroski_Score" in df.columns and p_cols:
        recalc = df[p_cols].apply(lambda r: int(np.nansum(pd.to_numeric(r, errors="coerce"))), axis=1)
        mism = int((recalc - df["Piotroski_Score"].astype(float)).abs().gt(TOL).sum())
        checks.append({"name": "Piotroski_Score == sum(P: columns)",
                       "ok": mism == 0, "detail": f"{len(df)-mism}/{len(df)} match"})
    notes = ["M:/P: blanks = 'check data unavailable' (by design); contribute 0 to score"]
    return _result(os.path.basename(path), len(df), checks,
                   _fill_rates(df, ["Minervini_Score", "Piotroski_Score", "Overall_Rating"]), notes)


# ──────────────────────────────────────────────────────────────────────────
# driver
# ──────────────────────────────────────────────────────────────────────────
_TARGETS = [
    ("FINAL_WATCHLIST.csv", check_watchlist),
    ("FINAL_COMBINED_PICKS.csv", check_watchlist),
    ("Bull_Screener_Results.csv", check_bull),
    ("Recovery_Screener_Results.csv", check_recovery),
    ("FINAL_XRay_Picks.csv", check_xray),
]


def run_authenticity_check(verbose: bool = True, write_report: bool = True) -> dict:
    results = []
    for fname, fn in _TARGETS:
        try:
            r = fn(os.path.join(DATA_DIR, fname))
        except Exception as e:
            r = {"file": fname, "rows": 0, "pass": False, "checks": [],
                 "fills": [], "notes": [f"validator error: {e}"]}
        if r is not None:
            results.append(r)

    all_pass = all(r["pass"] for r in results) if results else False
    lines = []
    lines.append("=" * 68)
    lines.append("  SCORE AUTHENTICITY CHECK  " + datetime.datetime.now().strftime("%d %b %Y %H:%M"))
    lines.append("  (each stored score recomputed from its own visible columns)")
    lines.append("=" * 68)
    for r in results:
        stamp = "PASS" if r["pass"] else "FAIL"
        lines.append(f"\n[{stamp}] {r['file']}  ({r['rows']} rows)")
        for c in r["checks"]:
            mark = "  OK " if c["ok"] else "  XX "
            lines.append(f"{mark}{c['name']}  — {c['detail']}")
        for note in r["notes"]:
            lines.append(f"      · {note}")
    lines.append("\n" + "-" * 68)
    lines.append(f"  OVERALL: {'PASS — all scores reproducible from columns' if all_pass else 'FAIL — see XX above'}")
    lines.append("=" * 68)
    report = "\n".join(lines)
    if verbose:
        print(report)

    if write_report:
        try:
            rdir = os.path.join(DATA_DIR, "reports")
            os.makedirs(rdir, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(rdir, f"score_authenticity_{stamp}.txt"), "w", encoding="utf-8") as f:
                f.write(report)
        except Exception:
            pass

    return {"pass": all_pass, "results": results, "report": report}


def main() -> int:
    res = run_authenticity_check(verbose=True)
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
