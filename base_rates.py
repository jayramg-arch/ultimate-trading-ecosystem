"""base_rates.py — measured base rates per setup family, for the S4 panel.

21-Sep-2026. Replaces the "ML win probability" row, which was a six-feature logistic
fitted in May on 45k SIMULATED Unified-strategy trades, before the price-action
conversion, never validated out-of-sample, and printing ~50% for every name. A
per-trade probability from ~500 trades would be that number with more digits.

What this ships instead is the honest ceiling at this sample size: the OUTCOME
DISTRIBUTION of the trades this system actually produced in the latest matched-horizon
validation runs, per setup family (and per family x regime where the cell is thick
enough), with n always shown. Win probability is deliberately NOT the headline: the
book is a low-hit-rate / big-winner profile, so P(win) ranks setups wrongly. The
numbers that decide size are expectancy in R and the shape around it.

Per cell:
    ER      mean R-multiple            (Return_pct / SL_pct — sized-to-risk return)
    P2R     % of trades that reached >= 2R
    PSTOP   % that hit the INITIAL stop (and the median days to it)
    WIN     % with Return_pct > 0
    ALPHA   mean / median matched-horizon alpha vs Nifty 500
    n       trades in the cell

Sources: the bull run named in validation_runs/LAST_RUN_BULL.txt (falls back to the
19-Aug re-baseline) and the recovery run in LAST_RUN.txt, with CB-Watch pre-signals
removed. Recovery cells are family-only (no regime split) — n is too thin.

Outputs
    data/base_rates.json                     every cell, for the board and the docs
    br_section(board_df) -> "BR=SYM:code,…"  one bundle section; code =
        FAM_ER_P2R_PSTOP_n  e.g.  POSBO_+0.21_14_12_147   (no , : | ; — the bundle
        grammar's separators; S4Core.fundStr returns the code, S4 splits on "_")

CLI:  python base_rates.py            build + print the table
      python base_rates.py --json     print the JSON
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "validation_runs")
OUT = os.path.join(HERE, "data", "base_rates.json")

BULL_FALLBACK_RUN = "20260819_112959"     # 24mo nifty500, catalyst-aware, RRG+forming-week fixes
MIN_N_CELL = 30                            # below this a cell is reported but flagged thin
MIN_N_REGIME = 30                          # regime split shown only when its cell has this many

# board archetype / catalyst -> family key used in the cells
FAMILY_OF_CATALYST = {
    "POS-BO": "POSBO", "POS-ACCUM": "POSAC", "SWG-PB": "SWGPB", "SWG-BO": "SWGBO",
    "SWG-GAP": "SWGGAP", "SWG-REV": "SWGREV",
    "REV-EARLY": "REVE", "REV-RS": "REVRS", "REV-CB": "REVCB", "WYC-SOS": "WYC",
    "WYC-SPRING": "WYC", "WYC-JAC": "WYC",
}
FAMILY_OF_ARCHETYPE = {           # when the board row carries no live catalyst
    "Pullback": "SWGPB", "Breakout": "POSBO", "Leader": "POSBO", "Catalyst-Scan": "POSBO",
    "Recovery-Early": "REVE", "Recovery-Climax": "REVCB", "Rec-Catalyst-Scan": "REVE",
    "Recovery-RS": "REVRS",
}
FAMILY_LABEL = {"POSBO": "POS-BO", "POSAC": "POS-ACCUM", "SWGPB": "SWG-PB", "SWGBO": "SWG-BO",
                "SWGGAP": "SWG-GAP", "SWGREV": "SWG-REV", "REVE": "REV-EARLY", "REVRS": "REV-RS",
                "REVCB": "REV-CB", "WYC": "WYC-*"}


def _run_id(pointer: str, fallback: str) -> str:
    try:
        with open(os.path.join(RUNS, pointer), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return fallback


def _details(run_id: str) -> pd.DataFrame:
    p = os.path.join(RUNS, f"validation_{run_id}_details.csv")
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def _cell(df: pd.DataFrame) -> dict:
    ret = pd.to_numeric(df["Return_pct"], errors="coerce")
    slp = pd.to_numeric(df["SL_pct"], errors="coerce").abs()
    r = (ret / slp.where(slp > 0)).replace([np.inf, -np.inf], np.nan)
    alpha = pd.to_numeric(df.get("Alpha_Matched_pct"), errors="coerce")
    hit_sl = df.get("Hit_Initial_SL", pd.Series(dtype=float))
    hit_sl = hit_sl.astype(str).str.lower().isin(("true", "1", "1.0"))
    days = pd.to_numeric(df.get("Days_Held"), errors="coerce")
    n = int(r.notna().sum())
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "ER": round(float(r.mean()), 2),
        "R_median": round(float(r.median()), 2),
        "P2R": round(100 * float((r >= 2.0).mean()), 1),
        "P3R": round(100 * float((r >= 3.0).mean()), 1),
        "PSTOP": round(100 * float(hit_sl.mean()), 1) if len(hit_sl) else None,
        "stop_days_med": (float(days[hit_sl].median()) if hit_sl.any() else None),
        "WIN": round(100 * float((ret > 0).mean()), 1),
        "alpha_mean": round(float(alpha.mean()), 2) if alpha.notna().any() else None,
        "alpha_median": round(float(alpha.median()), 2) if alpha.notna().any() else None,
        "thin": n < MIN_N_CELL,
    }


def build() -> dict:
    bull_id = _run_id("LAST_RUN_BULL.txt", BULL_FALLBACK_RUN)
    rec_id = _run_id("LAST_RUN.txt", "")
    bull = _details(bull_id)
    rec = _details(rec_id)
    if not rec.empty and "Signal" in rec.columns:          # CB-Watch = pre-signal, never a trade
        rec = rec[pd.to_numeric(rec["Signal"], errors="coerce").fillna(0) >= 2]
    cells: dict = {}
    if not bull.empty:
        for cat, g in bull.groupby("Catalyst"):
            fam = FAMILY_OF_CATALYST.get(str(cat))
            if not fam:
                continue
            cells[fam] = _cell(g)
            if "Regime" in g.columns:
                for reg, gg in g.groupby("Regime"):
                    c = _cell(gg)
                    if c["n"] >= MIN_N_REGIME:
                        cells[f"{fam}@{reg}"] = c
    if not rec.empty and "Signal_Label" in rec.columns:
        for lab, g in rec.groupby("Signal_Label"):
            fam = FAMILY_OF_CATALYST.get(str(lab))
            if not fam:
                continue
            if fam in cells:                                   # WYC-* pooled
                both = pd.concat([g])
                cells[fam] = _cell(both) if cells[fam]["n"] == 0 else cells[fam]
            else:
                cells[fam] = _cell(g)
    out = {"built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
           "bull_run": bull_id, "recovery_run": rec_id,
           "bull_n": int(len(bull)), "recovery_n": int(len(rec)), "cells": cells}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, OUT)
    return out


def load() -> dict:
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return build()


def current_regime() -> str:
    """BULL/BEAR by the same rule bull_screener stamps on picks (close > SMA200 and
    SMA50 > SMA200 on the benchmark), read from regime_state.json."""
    try:
        with open(os.path.join(HERE, "regime_state.json"), encoding="utf-8") as f:
            last = json.load(f)["last"]
        return "BULL" if (last["close"] > last["sma200"] and last["sma50"] > last["sma200"]) else "BEAR"
    except Exception:
        return ""


def family_for_row(row) -> str:
    cat = str(row.get("Catalyst", "") or "").strip()
    if cat in FAMILY_OF_CATALYST:
        return FAMILY_OF_CATALYST[cat]
    for a in str(row.get("Archetype", "") or "").split(","):
        a = a.strip()
        if a in FAMILY_OF_ARCHETYPE:
            return FAMILY_OF_ARCHETYPE[a]
    return ""


def code_for(fam: str, br: dict, regime: str = "") -> str:
    """FAM_ER_P2R_PSTOP_n — regime cell when thick enough, else the family cell."""
    cells = br.get("cells", {})
    c = cells.get(f"{fam}@{regime}") if regime else None
    tag = fam + ("@" + regime[0] if c else "")
    c = c or cells.get(fam)
    if not c or not c.get("n"):
        return ""
    return "%s_%+.2f_%.0f_%.0f_%d" % (tag, c["ER"], c["P2R"], c["PSTOP"] or 0, c["n"])


def br_section(board_df: pd.DataFrame) -> str:
    """The BR= bundle section for every board row that maps to a family."""
    br = load()
    reg = current_regime()
    items = []
    for _, row in board_df.iterrows():
        sym = str(row.get("Symbol", "")).strip().upper()
        fam = family_for_row(row)
        if not sym or not fam:
            continue
        code = code_for(fam, br, reg)
        if code:
            items.append(f"{sym}:{code}")
    return "BR=" + ",".join(sorted(set(items)))


def table(br: dict) -> str:
    rows = ["%-14s %5s %6s %6s %6s %6s %7s %7s" % ("cell", "n", "E[R]", "medR", "P>=2R", "Pstop", "win%", "alpha")]
    for k, c in sorted(br["cells"].items()):
        if not c.get("n"):
            continue
        rows.append("%-14s %5d %+6.2f %+6.2f %5.0f%% %5.0f%% %6.1f%% %+6.2f%s" % (
            k, c["n"], c["ER"], c["R_median"], c["P2R"], c["PSTOP"] or 0, c["WIN"],
            c["alpha_mean"] or 0, "  (thin)" if c.get("thin") else ""))
    return "\n".join(rows)


if __name__ == "__main__":
    b = build()
    if "--json" in sys.argv:
        print(json.dumps(b, indent=1))
    else:
        print("bull run %s (n=%d) · recovery run %s (n=%d, ex CB-Watch) · regime now %s\n"
              % (b["bull_run"], b["bull_n"], b["recovery_run"], b["recovery_n"], current_regime()))
        print(table(b))
