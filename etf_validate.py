"""
etf_validate.py -- Cross-validation harness for the ETF Trading System.

Built 12 May 2026 as Enhancement #1 from the validation audit.

Purpose
-------
The ETF system has three independent signal-generation surfaces:
    1. Python (etf_screener.py)        -- CLI / Commander Web
    2. Pine Dashboard (Commander_ETF_Dashboard_v1.1)
    3. Pine Strategy  (Commander_ETF_Strategy_v1.1)

Per CLAUDE.md "signal consistency is sacred". This harness:
    a) Recomputes all signal components in Python from the universe
    b) Exports a reference CSV (ETF_Validate_Reference.csv) that matches
       the values shown in the Pine dashboard's data window pins
    c) Runs internal consistency checks (precedence ordering, thresholds)
    d) Reports any per-ETF drift to logs/etf_validation_<date>.md

To verify Pine matches Python:
    1. python etf_validate.py                -> writes reference CSV
    2. In TradingView, load Commander ETF Dashboard on each test ETF
    3. Right-click chart -> "Copy Data Window" for each
    4. Run: python etf_validate.py --compare <pasted_csv>

Usage
-----
    python etf_validate.py                 # generate reference + run checks
    python etf_validate.py --etfs NIFTYBEES,BANKBEES,GOLDBEES,MAFANG
    python etf_validate.py --strict        # fail (exit 1) on any drift
"""
from __future__ import annotations

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from etf_universe import ETF_UNIVERSE, get_meta
from etf_screener import (
    rank_universe, score_liquidity, score_trend, score_rs, score_rotation,
    _compute_stage, _rotation_vector, BENCHMARK_YF, LIQ_MIN_CR,
)

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_CSV = "ETF_Validate_Reference.csv"
REPORT_DIR    = "logs"


# ----------------------------------------------------------------------------
# Internal consistency checks (do not need TradingView)
# ----------------------------------------------------------------------------
def check_signal_precedence(df: pd.DataFrame) -> List[Dict]:
    """Verify the Python signal ladder matches Pine ordering:
       ILLIQUID > AVOID-DOWNTREND > BUY-LEADER > ACCUMULATE >
       HOLD-WATCH > EARLY-BASE > NEUTRAL
    """
    issues = []
    for _, r in df.iterrows():
        sym = r["Symbol"]
        sig = str(r.get("Signal", ""))
        stage = r.get("Stage", 0)
        quad = r.get("RRG_Quadrant", "")
        liq = r.get("Liquidity_Score", 0)
        turnover = r.get("Turnover_60D_Cr", 0)

        # Rule 1: if turnover < LIQ_MIN_CR, signal MUST be ILLIQUID
        if turnover is not None and turnover < LIQ_MIN_CR and "ILLIQUID" not in sig:
            issues.append({
                "symbol": sym, "rule": "ILLIQUID_precedence",
                "expected": "ILLIQUID", "actual": sig,
                "context": f"turnover={turnover:.2f} < {LIQ_MIN_CR}"
            })

        # Rule 2: if stage == 4 AND turnover >= LIQ_MIN_CR, signal MUST be AVOID
        elif stage == 4 and (turnover is None or turnover >= LIQ_MIN_CR):
            if "AVOID" not in sig:
                issues.append({
                    "symbol": sym, "rule": "AVOID_precedence",
                    "expected": "AVOID-DOWNTREND", "actual": sig,
                    "context": f"stage=4, turnover={turnover}"
                })

        # Rule 3: if BUY-LEADER, must have stage=2 + LEADING + liq_score>=6
        if "BUY-LEADER" in sig:
            if not (stage == 2 and quad == "LEADING" and liq >= 6):
                issues.append({
                    "symbol": sym, "rule": "BUY_LEADER_gates",
                    "expected": "stage=2 AND LEADING AND liq>=6",
                    "actual": f"stage={stage}, quad={quad}, liq={liq}",
                    "context": "BUY-LEADER signalled without all gates"
                })

    return issues


def check_threshold_consistency() -> List[Dict]:
    """Verify Python-side thresholds match etf_config.json (if present)."""
    issues = []
    cfg_path = os.path.join(_DIR, "etf_config.json")
    if not os.path.exists(cfg_path):
        return issues
    import json
    try:
        with open(cfg_path) as f:
            cfg = json.load(f)
    except Exception as e:
        issues.append({"rule": "json_load", "context": str(e)})
        return issues

    # Python LIQ_MIN_CR must match config
    cfg_liq = cfg.get("liq_min_cr")
    if cfg_liq is not None and abs(cfg_liq - LIQ_MIN_CR) > 1e-9:
        issues.append({
            "rule": "LIQ_MIN_CR_mismatch",
            "expected": cfg_liq, "actual": LIQ_MIN_CR,
            "context": "etf_screener.py imported old value -- restart Python"
        })

    # Benchmark
    cfg_bench = cfg.get("benchmark_yf")
    if cfg_bench and cfg_bench != BENCHMARK_YF:
        issues.append({
            "rule": "BENCHMARK_mismatch",
            "expected": cfg_bench, "actual": BENCHMARK_YF,
        })

    return issues


def check_universe_integrity() -> List[Dict]:
    """Verify ETF_UNIVERSE entries are well-formed."""
    issues = []
    required = ["name", "asset_class", "sub_category", "underlying",
                "issuer", "liquidity_tier"]
    valid_classes = {"BROAD_EQUITY", "SECTOR", "SMART_BETA", "INTERNATIONAL",
                     "COMMODITY", "DEBT", "THEMATIC"}
    valid_tiers = {"A", "B", "C"}

    for sym, meta in ETF_UNIVERSE.items():
        for key in required:
            if key not in meta:
                issues.append({"symbol": sym, "rule": "missing_field",
                                "context": f"missing '{key}'"})
        if meta.get("asset_class") not in valid_classes:
            issues.append({"symbol": sym, "rule": "invalid_asset_class",
                            "context": f"got '{meta.get('asset_class')}'"})
        if meta.get("liquidity_tier") not in valid_tiers:
            issues.append({"symbol": sym, "rule": "invalid_liquidity_tier",
                            "context": f"got '{meta.get('liquidity_tier')}'"})
    return issues


# ----------------------------------------------------------------------------
# Pine drift comparison (manual: paste Pine data window CSV)
# ----------------------------------------------------------------------------
PINE_COLS = ["Stage", "Mansfield_RS", "RS_Momentum_4W", "Liquidity_Score",
             "Turnover_60D_Cr", "Dist_200DMA_pct", "Dist_52WH_pct",
             "MA200_Slope_pct"]


def compare_pine_drift(reference: pd.DataFrame, pine_csv: str,
                        tolerance_pct: float = 1.0) -> List[Dict]:
    """Compare the reference CSV against a Pine-exported data window snapshot.
    Pine CSV should have columns matching PINE_COLS (case-insensitive)
    plus a 'Symbol' column.
    """
    issues = []
    if not os.path.exists(pine_csv):
        return [{"rule": "pine_csv_missing", "context": pine_csv}]

    pine = pd.read_csv(pine_csv)
    pine.columns = [c.strip() for c in pine.columns]
    if "Symbol" not in pine.columns:
        return [{"rule": "pine_csv_no_symbol_col", "context": str(pine.columns.tolist())}]

    for _, prow in pine.iterrows():
        sym = prow["Symbol"]
        ref_row = reference[reference["Symbol"] == sym]
        if ref_row.empty:
            issues.append({"symbol": sym, "rule": "symbol_missing_from_python"})
            continue
        ref_row = ref_row.iloc[0]
        for col in PINE_COLS:
            if col not in pine.columns or col not in reference.columns:
                continue
            pv = prow[col]
            rv = ref_row[col]
            try:
                pv = float(pv); rv = float(rv)
            except Exception:
                continue
            if rv != 0:
                drift_pct = abs(pv - rv) / abs(rv) * 100
                if drift_pct > tolerance_pct:
                    issues.append({
                        "symbol": sym, "rule": f"drift_{col}",
                        "pine": pv, "python": rv,
                        "drift_pct": round(drift_pct, 2),
                    })
    return issues


# ----------------------------------------------------------------------------
# Reference CSV generator
# ----------------------------------------------------------------------------
def build_reference(symbols: Optional[List[str]] = None) -> pd.DataFrame:
    """Build the per-ETF reference table that Pine should match exactly."""
    df = rank_universe(syms=symbols)
    if df.empty:
        return df
    # Subset to the columns that Pine surfaces have access to
    keep = [c for c in [
        "Symbol", "Asset_Class", "Sub_Category",
        "Stage", "RRG_Quadrant", "Rotation_Vector",
        "Liquidity_Score", "Trend_Score", "RS_Score", "Rotation_Score",
        "Total_Score", "Grade",
        "Mansfield_RS", "RS_Momentum_4W",
        "Turnover_60D_Cr", "MA200_Slope_pct", "Dist_52WH_pct",
        "LTP", "Signal",
    ] if c in df.columns]
    return df[keep]


# ----------------------------------------------------------------------------
# Report writer
# ----------------------------------------------------------------------------
def write_report(issues: Dict[str, List], etfs_checked: int) -> str:
    os.makedirs(os.path.join(_DIR, REPORT_DIR), exist_ok=True)
    fname = f"etf_validation_{datetime.now():%Y%m%d_%H%M%S}.md"
    path = os.path.join(_DIR, REPORT_DIR, fname)

    total = sum(len(v) for v in issues.values())
    with open(path, "w") as f:
        f.write(f"# ETF Validation Report\n")
        f.write(f"\nGenerated: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"\nETFs checked: {etfs_checked}\n")
        f.write(f"\nTotal issues: **{total}**\n\n")

        for section, items in issues.items():
            f.write(f"## {section} ({len(items)} issues)\n\n")
            if not items:
                f.write("_None._\n\n")
                continue
            for it in items:
                f.write(f"- **{it.get('rule', '?')}** -- ")
                if "symbol" in it:
                    f.write(f"`{it['symbol']}` -- ")
                if "expected" in it:
                    f.write(f"expected `{it['expected']}`, got `{it.get('actual', '?')}`. ")
                if "drift_pct" in it:
                    f.write(f"drift `{it['drift_pct']}%` (pine={it.get('pine')}, py={it.get('python')}). ")
                if "context" in it:
                    f.write(f"{it['context']}")
                f.write("\n")
            f.write("\n")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--etfs", help="Comma-separated symbols (default: full universe)")
    parser.add_argument("--compare", help="Path to Pine-exported CSV for drift check")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any issue found")
    parser.add_argument("--tolerance", type=float, default=1.0,
                         help="Drift tolerance in percent (default 1.0)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    print("ETF Validation Harness")
    print("=" * 60)

    syms = args.etfs.split(",") if args.etfs else None

    # 1. Build reference
    print(f"\n[1/4] Building reference CSV...")
    ref = build_reference(syms)
    if ref.empty:
        print("  ERROR: reference empty (data fetch failed?)")
        sys.exit(2)
    ref.to_csv(os.path.join(_DIR, REFERENCE_CSV), index=False)
    print(f"  -> {REFERENCE_CSV} ({len(ref)} ETFs)")

    # 2. Internal consistency
    print(f"\n[2/4] Checking signal precedence...")
    precedence_issues = check_signal_precedence(ref)
    print(f"  {len(precedence_issues)} issues")

    print(f"\n[3/4] Checking threshold + universe consistency...")
    threshold_issues = check_threshold_consistency()
    universe_issues  = check_universe_integrity()
    print(f"  threshold: {len(threshold_issues)} issues")
    print(f"  universe:  {len(universe_issues)} issues")

    # 3. Optional Pine drift check
    drift_issues = []
    if args.compare:
        print(f"\n[4/4] Comparing against Pine export ({args.compare})...")
        drift_issues = compare_pine_drift(ref, args.compare, args.tolerance)
        print(f"  {len(drift_issues)} drift issues (tol {args.tolerance}%)")
    else:
        print(f"\n[4/4] Pine drift check skipped (no --compare arg).")

    # 4. Report
    issues = {
        "Signal Precedence":  precedence_issues,
        "Thresholds":         threshold_issues,
        "Universe Integrity": universe_issues,
        "Pine Drift":         drift_issues,
    }
    report_path = write_report(issues, etfs_checked=len(ref))
    total = sum(len(v) for v in issues.values())
    print(f"\nReport: {report_path}")
    print(f"Total issues: {total}")
    if total == 0:
        print("STATUS: CLEAN")
        sys.exit(0)
    if args.strict:
        print("STATUS: FAIL (strict mode)")
        sys.exit(1)
    print("STATUS: ISSUES (advisory)")


if __name__ == "__main__":
    main()
