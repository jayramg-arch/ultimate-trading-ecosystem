# performance_attribution.py
# Phase 0 — Performance Attribution Engine  (6-phase fine-tuning roadmap)
# ---------------------------------------------------------------------------
# PURPOSE
#   Decompose REALIZED P&L into its drivers so we can see *where* alpha
#   actually comes from before we fit weights (Phase 3), gate correlation
#   (Phase 4), or trust any backtest (Phase 2).
#
#       "I am not adding features. I am compounding rigor."
#
# SCOPE
#   Unified view across BOTH the stock system (trade_journal_v6.db) AND the
#   ETF system. The ETF system has no real closed-trades log yet, so this
#   module detects its absence and SAYS SO rather than fabricating rows.
#
# DESIGN DISCIPLINE (the silent-killer rule)
#   The hedge-fund critique flagged "silent fallbacks biasing every signal
#   upward (NaN->0 patterns)". This module refuses that pattern:
#     * Rows with a missing/zero exit price or quantity are QUARANTINED and
#       reported as a data-quality line — never zero-filled into the P&L.
#     * Drivers we cannot observe on real fills (Stage / RS / Alpha Score are
#       not snapshotted at entry in the journal) are reported as an explicit
#       coverage gap, not silently imputed. Surfacing that gap is itself a
#       Phase-0 finding: the journal needs an entry-time signal snapshot.
#
# CANONICAL FORMULAS (kept byte-identical to ai_mentor_engine.py:51-52 — zero
# drift across the ecosystem):
#     realized_pnl = (exit_price - buy_price) * quantity
#     roi_pct      = (exit_price - buy_price) / buy_price * 100
#
# INVOCATION
#   Per the ecosystem invocation model, this runs via launch_script() from
#   Web Commander v4.0, never manually. The Streamlit page consumes the dict
#   returned by run_attribution(); the CLI / launch path uses main().
#
#   CLI:  python performance_attribution.py [--db PATH] [--etf-csv PATH]
#                                           [--no-save]
# ---------------------------------------------------------------------------

import os
import sys
import argparse
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd

# Windows consoles default to cp1252 and choke on the box-drawing / ₹ glyphs.
# Same idiom used across the ecosystem (e.g. chartink_replay.py).
if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

# ── Paths / constants ───────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE      = os.path.join(_DIR, "trade_journal_v6.db")
# Optional real ETF closed-trades log. Schema (when it exists) mirrors the
# journal: symbol, buy_price, exit_price, quantity, entry_date, exit_date,
# sector, trade_type, exit_reason. Absent today by design.
ETF_TRADES_CSV = os.path.join(_DIR, "ETF_Closed_Trades.csv")
REPORTS_DIR  = os.path.join(_DIR, "reports")

# Hold-period buckets (calendar days, entry -> exit). Aligned to the trade
# styles in CLAUDE.md: Swing 8-12wk, Positional 6-8mo.
HOLD_BUCKETS = [
    (0,    7,    "0–7d (scalp/failed)"),
    (7,    30,   "1–4wk (swing-fast)"),
    (30,   90,   "1–3mo (swing)"),
    (90,   180,  "3–6mo (positional)"),
    (180,  10**9,"6mo+ (investment)"),
]

# Entry-signal band buckets (continuous snapshot fields -> readable bands).
# Alpha Score 0-100; Mansfield/JdK RS-Ratio centered at 100; conviction ~5-8.5.
ALPHA_BANDS = [(0,40,"Weak (<40)"), (40,60,"Fair (40–59)"),
               (60,80,"Strong (60–79)"), (80,201,"Elite (80+)")]
RS_BANDS    = [(-1e9,100,"Laggard (<100)"), (100,105,"Leader (100–105)"),
               (105,1e9,"Strong Leader (105+)")]
CONV_BANDS  = [(-1e9,6,"Low (<6)"), (6,7.5,"Medium (6–7.5)"),
               (7.5,1e9,"High (7.5+)")]

# Dimensions we attribute across. Each maps a (derived) column -> display label.
# The lower block are the entry-signal drivers — the whole point of Phase 0:
# "which setups / stages / scores actually pay me." They read "Unspecified"
# for trades closed before the snapshot columns existed (honest, not imputed).
DIMENSIONS = [
    ("system",       "System (Stock / ETF)"),
    ("sector",       "Sector"),
    ("trade_type",   "Trade Type"),
    ("hold_bucket",  "Hold Period"),
    ("exit_reason",  "Exit Reason"),
    ("trade_quality","Trade Quality"),
    # ── entry-signal snapshot drivers ──
    ("setup",        "Setup / Catalyst"),
    ("stage_label",  "Entry Stage (Weinstein)"),
    ("alpha_band",   "Entry Alpha Score"),
    ("rs_band",      "Entry RS (Mansfield)"),
    ("conv_band",    "Entry Conviction"),
]


# ── INR formatting (local copy — matches the established per-file pattern;
#    importing the Streamlit app here would pull in a heavy/circular dep) ─────
def format_inr(number):
    """Indian comma format: 1,23,456.78"""
    try:
        if number is None or (isinstance(number, float) and np.isnan(number)):
            return "0.00"
        val = float(number); sign = "-" if val < 0 else ""; val = abs(val)
        s, *d = str("{:.2f}".format(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + "".join([r] + d)
    except (ValueError, TypeError, AttributeError):
        return str(number)


def format_inr_int(number):
    """Indian comma format, no decimals: 1,23,456"""
    try:
        if number is None or (isinstance(number, float) and np.isnan(number)):
            return "0"
        val = float(number); sign = "-" if val < 0 else ""; val = abs(val)
        s = str(int(round(val)))
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + r
    except (ValueError, TypeError, AttributeError):
        return str(number)


# ── Loaders ─────────────────────────────────────────────────────────────────
def _load_stock_trades(db_file=DB_FILE):
    """Load CLOSED stock trades from the journal DB. Tags system='STOCK'."""
    if not os.path.exists(db_file):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_file)
        df = pd.read_sql_query("SELECT * FROM journal WHERE status = 'CLOSED'", conn)
        conn.close()
    except Exception as e:
        print(f"⚠️  Could not read journal DB: {e}")
        return pd.DataFrame()
    if not df.empty:
        df["system"] = "STOCK"
    return df


def _load_etf_trades(etf_csv=ETF_TRADES_CSV):
    """Load real ETF closed trades IF a log exists. Tags system='ETF'.

    Returns an empty frame when absent — the caller reports the gap. We do NOT
    synthesise ETF trades from etf_backtest.py (that is a simulator, not fills).
    """
    if not os.path.exists(etf_csv):
        return pd.DataFrame()
    try:
        df = pd.read_csv(etf_csv)
    except Exception as e:
        print(f"⚠️  Could not read ETF trades CSV: {e}")
        return pd.DataFrame()
    if not df.empty:
        df["system"] = "ETF"
        if "status" in df.columns:
            df = df[df["status"].astype(str).str.upper() == "CLOSED"].copy()
    return df


# ── Cleaning / enrichment ───────────────────────────────────────────────────
def _prepare(df):
    """Coerce types, compute realized P&L, quarantine incomplete rows.

    Returns (clean_df, quality) where quality is a dict describing exactly how
    many rows were dropped and why — so missing data is SURFACED, not hidden.
    """
    quality = {"total_closed": int(len(df)), "dropped": {}, "attributable": 0}
    if df.empty:
        return df, quality

    df = df.copy()
    for col in ("buy_price", "exit_price", "quantity"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")

    # Quarantine rule: a P&L is only real if buy, exit and qty are all present
    # and non-zero. Anything else is an incomplete journal row — report it,
    # never zero-fill it (that would manufacture fake flat trades).
    bad_buy  = ~(df["buy_price"]  > 0)
    bad_exit = ~(df["exit_price"] > 0)
    bad_qty  = ~(df["quantity"].abs() > 0)
    quality["dropped"]["missing_buy_price"]  = int(bad_buy.sum())
    quality["dropped"]["missing_exit_price"] = int((bad_exit & ~bad_buy).sum())
    quality["dropped"]["missing_quantity"]   = int((bad_qty & ~bad_buy & ~bad_exit).sum())

    df = df[~(bad_buy | bad_exit | bad_qty)].copy()
    quality["attributable"] = int(len(df))
    if df.empty:
        return df, quality

    # Canonical P&L (identical to ai_mentor_engine.py — zero drift).
    df["realized_pnl"] = (df["exit_price"] - df["buy_price"]) * df["quantity"]
    df["roi_pct"]      = (df["exit_price"] - df["buy_price"]) / df["buy_price"] * 100.0

    # Hold period (calendar days). Unparseable dates -> "Unknown" bucket.
    ed = pd.to_datetime(df.get("entry_date"), errors="coerce")
    xd = pd.to_datetime(df.get("exit_date"),  errors="coerce")
    df["hold_days"] = (xd - ed).dt.days
    df["hold_bucket"] = df["hold_days"].apply(_bucket_hold)

    # Entry-signal snapshot drivers (present only on trades captured after the
    # journal_enrichment columns were added). Derive labels/bands; missing ->
    # "Unspecified" so they never silently bias a band.
    df["stage_label"] = pd.to_numeric(df.get("entry_stage"), errors="coerce") \
        .apply(lambda s: f"Stage {int(s)}" if pd.notna(s) else None)
    df["alpha_band"]  = pd.to_numeric(df.get("entry_alpha"), errors="coerce").apply(
        lambda v: _band(v, ALPHA_BANDS))
    df["rs_band"]     = pd.to_numeric(df.get("entry_rs"), errors="coerce").apply(
        lambda v: _band(v, RS_BANDS))
    df["conv_band"]   = pd.to_numeric(df.get("entry_conviction"), errors="coerce").apply(
        lambda v: _band(v, CONV_BANDS))

    # Normalise label columns so groupby keys are clean.
    for col in ("sector", "trade_type", "exit_reason", "trade_quality",
                "setup", "stage_label", "alpha_band", "rs_band", "conv_band"):
        if col not in df.columns:
            df[col] = np.nan
        df[col] = (df[col].astype("string").str.strip()
                   .replace({"": pd.NA, "None": pd.NA, "nan": pd.NA, "NONE": pd.NA})
                   .fillna("Unspecified"))
    return df, quality


def _band(v, bands):
    """Map a numeric value into a labeled band; NaN -> None (-> Unspecified)."""
    if v is None or pd.isna(v):
        return None
    for lo, hi, label in bands:
        if lo <= v < hi:
            return label
    return None


def _bucket_hold(days):
    if days is None or (isinstance(days, float) and np.isnan(days)) or pd.isna(days):
        return "Unknown (no dates)"
    if days < 0:
        return "Unknown (no dates)"
    for lo, hi, label in HOLD_BUCKETS:
        if lo <= days < hi:
            return label
    return HOLD_BUCKETS[-1][2]


# ── Core attribution ────────────────────────────────────────────────────────
def _attribute(df, dim_col):
    """Group realized P&L by one dimension. Returns a tidy DataFrame.

    contribution_pct is a SIGNED share of gross absolute P&L
    (pnl / Σ|pnl|), not a share of net. Net-based shares invert their sign
    whenever the book is net-negative (a winning bucket would read negative),
    which is misleading; the gross denominator keeps winners positive and
    losers negative regardless of the net result.
    """
    gross_abs = df["realized_pnl"].abs().sum()
    rows = []
    for key, g in df.groupby(dim_col, dropna=False):
        pnl   = g["realized_pnl"].sum()
        wins  = g[g["realized_pnl"] > 0]
        losses= g[g["realized_pnl"] < 0]
        gross_profit = wins["realized_pnl"].sum()
        gross_loss   = abs(losses["realized_pnl"].sum())
        n = len(g)
        rows.append({
            "dimension":     dim_col,
            "bucket":        str(key),
            "n_trades":      n,
            "win_rate_pct":  round(100.0 * len(wins) / n, 1) if n else 0.0,
            "total_pnl":     round(pnl, 2),
            "avg_roi_pct":   round(g["roi_pct"].mean(), 2),
            "expectancy":    round(pnl / n, 2) if n else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0
                             else (np.inf if gross_profit > 0 else 0.0),
            "contribution_pct": round(100.0 * pnl / gross_abs, 1)
                             if gross_abs > 1e-9 else 0.0,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("total_pnl", ascending=False).reset_index(drop=True)
    return out


def run_attribution(db_file=DB_FILE, etf_csv=ETF_TRADES_CSV):
    """Build the full attribution. Returns a dict (Streamlit-consumable):

        {
          "headline":  {...overall metrics...},
          "quality":   {...data-quality / coverage report...},
          "tables":    {dim_col: DataFrame, ...},
          "trades":    cleaned per-trade DataFrame,
          "ok":        bool,
          "message":   str,
        }
    """
    stock = _load_stock_trades(db_file)
    etf   = _load_etf_trades(etf_csv)

    raw = pd.concat([d for d in (stock, etf) if not d.empty], ignore_index=True) \
          if (not stock.empty or not etf.empty) else pd.DataFrame()

    df, quality = _prepare(raw)
    quality["etf_log_present"] = bool(not etf.empty)
    quality["stock_trades_closed"] = int(len(stock))
    quality["etf_trades_closed"]   = int(len(etf))
    # Entry-signal snapshot coverage. As of journal_enrichment.py these ARE
    # captured for new trades (and as-of-today backfills of open ones), so the
    # signal dimensions populate going forward. Trades closed before the
    # snapshot columns existed read "Unspecified" — reported, never imputed.
    if not df.empty and "snapshot_meta" in df.columns:
        # snapshot_meta is set whenever a snapshot was captured (even backfills,
        # where setup itself is NONE) — the reliable coverage marker.
        n_snap = int(df["snapshot_meta"].notna().sum())
        quality["signal_snapshot_coverage"] = f"{n_snap}/{len(df)} closed trades carry an entry snapshot"
    quality["unobservable_drivers"] = []  # closed via journal_enrichment.py
    quality["unobservable_note"] = (
        "Entry-signal snapshot now captured at trade creation "
        "(journal_enrichment.py). Pre-snapshot closed trades show 'Unspecified' "
        "on the signal dimensions — a shrinking coverage gap, not imputed."
    )

    if df.empty:
        return {"ok": False, "headline": {}, "quality": quality,
                "tables": {}, "trades": df,
                "message": ("No attributable closed trades. "
                            f"{quality['total_closed']} CLOSED rows found, "
                            "all quarantined for missing exit/qty data.")}

    # Headline metrics.
    total_pnl = df["realized_pnl"].sum()
    wins = df[df["realized_pnl"] > 0]
    gross_profit = wins["realized_pnl"].sum()
    gross_loss   = abs(df[df["realized_pnl"] < 0]["realized_pnl"].sum())
    headline = {
        "n_trades":      int(len(df)),
        "total_realized":round(total_pnl, 2),
        "win_rate_pct":  round(100.0 * len(wins) / len(df), 1),
        "expectancy":    round(total_pnl / len(df), 2),
        "avg_roi_pct":   round(df["roi_pct"].mean(), 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0
                         else (np.inf if gross_profit > 0 else 0.0),
        "best_trade":    round(df["realized_pnl"].max(), 2),
        "worst_trade":   round(df["realized_pnl"].min(), 2),
    }

    tables = {}
    for col, _label in DIMENSIONS:
        if col in df.columns:
            t = _attribute(df, col)
            if not t.empty:
                tables[col] = t

    return {"ok": True, "headline": headline, "quality": quality,
            "tables": tables, "trades": df, "message": "OK"}


# ── Reporting (console + CSV) ───────────────────────────────────────────────
def _print_report(result):
    q = result["quality"]
    print("\n" + "═" * 72)
    print("  PERFORMANCE ATTRIBUTION  —  Phase 0  (realized P&L decomposition)")
    print("═" * 72)

    # Data-quality block first — the honesty layer.
    print("\n▸ DATA QUALITY & COVERAGE")
    print(f"    Stock closed trades : {q['stock_trades_closed']}")
    print(f"    ETF closed trades   : {q['etf_trades_closed']}"
          f"{'' if q['etf_log_present'] else '   (no ETF log — ETF_Closed_Trades.csv absent)'}")
    print(f"    Total CLOSED rows   : {q['total_closed']}")
    print(f"    Attributable        : {q['attributable']}")
    dropped = {k: v for k, v in q.get("dropped", {}).items() if v}
    if dropped:
        print(f"    Quarantined         : "
              + ", ".join(f"{v} {k.replace('_',' ')}" for k, v in dropped.items()))
    if q.get("signal_snapshot_coverage"):
        print(f"    Signal snapshot     : {q['signal_snapshot_coverage']}")
    print(f"        ↳ {q['unobservable_note']}")

    if not result["ok"]:
        print("\n⚠️  " + result["message"])
        print("═" * 72 + "\n")
        return

    h = result["headline"]
    pf = "∞" if h["profit_factor"] == np.inf else f"{h['profit_factor']:.2f}"
    print("\n▸ HEADLINE")
    print(f"    Trades              : {h['n_trades']}")
    print(f"    Total Realized P&L  : ₹{format_inr(h['total_realized'])}")
    print(f"    Win Rate            : {h['win_rate_pct']}%")
    print(f"    Expectancy / trade  : ₹{format_inr(h['expectancy'])}")
    print(f"    Avg ROI / trade     : {h['avg_roi_pct']}%")
    print(f"    Profit Factor       : {pf}")
    print(f"    Best / Worst trade  : ₹{format_inr(h['best_trade'])} / ₹{format_inr(h['worst_trade'])}")

    for col, label in DIMENSIONS:
        t = result["tables"].get(col)
        if t is None or t.empty:
            continue
        print(f"\n▸ BY {label.upper()}")
        print(f"    {'bucket':<26}{'n':>4}{'win%':>7}{'tot ₹':>14}"
              f"{'exp ₹':>11}{'PF':>7}{'contrib%':>10}")
        print("    " + "-" * 79)
        for _, r in t.iterrows():
            pf_r = "∞" if r["profit_factor"] == np.inf else f"{r['profit_factor']:.2f}"
            print(f"    {r['bucket'][:25]:<26}{int(r['n_trades']):>4}"
                  f"{r['win_rate_pct']:>7.1f}{format_inr_int(r['total_pnl']):>14}"
                  f"{format_inr_int(r['expectancy']):>11}{pf_r:>7}"
                  f"{r['contribution_pct']:>9.1f}%")
    print("\n" + "═" * 72 + "\n")


def _save_csv(result):
    """Persist the long-form attribution table to reports/."""
    if not result["ok"]:
        return None
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    long_df = pd.concat(list(result["tables"].values()), ignore_index=True)
    path = os.path.join(REPORTS_DIR, f"performance_attribution_{stamp}.csv")
    long_df.to_csv(path, index=False)
    # Also drop the cleaned per-trade frame for drill-down.
    trades_path = os.path.join(REPORTS_DIR, f"performance_attribution_trades_{stamp}.csv")
    result["trades"].to_csv(trades_path, index=False)
    print(f"📄 Saved attribution → {os.path.relpath(path, _DIR)}")
    print(f"📄 Saved per-trade    → {os.path.relpath(trades_path, _DIR)}")
    return path


# ── Entry point ─────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 0 performance attribution.")
    ap.add_argument("--db", default=DB_FILE, help="trade journal SQLite path")
    ap.add_argument("--etf-csv", default=ETF_TRADES_CSV, help="ETF closed-trades CSV path")
    ap.add_argument("--no-save", action="store_true", help="print only, do not write CSVs")
    args = ap.parse_args(argv)

    result = run_attribution(db_file=args.db, etf_csv=args.etf_csv)
    _print_report(result)
    if not args.no_save:
        _save_csv(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
