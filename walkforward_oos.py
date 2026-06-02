# walkforward_oos.py
# Phase 2 — Backtest Rigor: in-sample / out-of-sample split + overfit HARD GATE.
# ---------------------------------------------------------------------------
# WHY
#   The May validation campaign already built the realistic execution sim
#   (commission+slippage), catalyst-aware forward windows, walk-forward monthly
#   anchors, and bootstrap CI. The ONE Phase-2 deliverable still missing is the
#   roadmap's hard gate:
#
#       "After Phase 2 — if OOS Sharpe < 60% of in-sample across walk-forward
#        windows, STOP. The system is overfit; re-architect the screener."
#
#   This module consumes a validation run's per-anchor summary, splits the
#   anchors chronologically into in-sample (earlier) and out-of-sample (later),
#   and applies the gate. It does NOT re-fit anything (weights are locked; that
#   is Phase 3) — it tests TEMPORAL STABILITY: does the locked config's edge,
#   measured on the earlier anchors, persist on the later, unseen ones?
#
# METHOD
#   Each anchor's alpha_pct is treated as one period-return observation of the
#   strategy. Anchors with no qualifying picks (NaN alpha) are dropped and
#   reported (not zero-filled). Per-window:
#       mean_alpha = mean(alpha_pct)
#       sharpe     = mean(alpha_pct) / std(alpha_pct)   (temporal, per-anchor)
#
# VERDICT
#   NO-EDGE : in-sample mean alpha <= 0 -> nothing to validate; the issue is
#             the screener/windows, not overfitting. (Don't cry "overfit" when
#             there was no in-sample edge to begin with.)
#   PASS    : IS mean alpha > 0 AND OOS mean alpha > 0 AND
#             OOS sharpe >= 0.60 * IS sharpe.
#   STOP    : OOS degradation > 40% (or OOS alpha flips negative) -> overfit /
#             unstable; re-architect before Phase 3.
#
# WINDOW CAVEAT (reads the validation_window_mismatch_warning lesson)
#   The verdict is only as honest as the forward window of the run it consumes.
#   POS/WYC/REV setups need 90-180d matched horizons — run validation.py with
#   --catalyst_windows for the authoritative input. This module prints which
#   summary it used so the window convention is auditable.
#
# INVOCATION
#   python walkforward_oos.py                       # uses LAST_RUN
#   python walkforward_oos.py --summary <path.csv>  # a specific run
#   python walkforward_oos.py --is-frac 0.6         # split fraction
# ---------------------------------------------------------------------------

import os
import sys
import glob
import argparse

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(_DIR, "validation_runs")
GATE_THRESHOLD = 0.60   # OOS sharpe must be >= 60% of in-sample


def _resolve_summary(summary_path=None):
    """Find the per-anchor summary CSV to evaluate."""
    if summary_path:
        return summary_path
    ptr = os.path.join(RUNS_DIR, "LAST_RUN.txt")
    if os.path.exists(ptr):
        with open(ptr) as f:
            run_id = f.read().strip()
        cand = os.path.join(RUNS_DIR, f"validation_{run_id}_summary.csv")
        if os.path.exists(cand):
            return cand
    # fallback: newest summary
    cands = sorted(glob.glob(os.path.join(RUNS_DIR, "validation_*_summary.csv")),
                   key=os.path.getmtime, reverse=True)
    return cands[0] if cands else None


def _window_metrics(alphas):
    """mean alpha + temporal Sharpe for one window's anchor-alpha series."""
    a = np.asarray(alphas, dtype=float)
    if len(a) == 0:
        return {"n": 0, "mean_alpha": np.nan, "std_alpha": np.nan, "sharpe": np.nan,
                "hit_rate": np.nan, "cum_alpha": np.nan}
    std = a.std(ddof=1) if len(a) > 1 else np.nan
    sharpe = (a.mean() / std) if (std and std > 1e-9) else np.nan
    return {
        "n": len(a),
        "mean_alpha": round(float(a.mean()), 3),
        "std_alpha": round(float(std), 3) if not np.isnan(std) else np.nan,
        "sharpe": round(float(sharpe), 3) if not np.isnan(sharpe) else np.nan,
        "hit_rate": round(float((a > 0).mean() * 100), 1),
        "cum_alpha": round(float(a.sum()), 2),
    }


def evaluate(summary_path=None, is_frac=0.6):
    path = _resolve_summary(summary_path)
    if not path or not os.path.exists(path):
        return {"ok": False, "message": "No validation summary found. Run validation.py first."}

    df = pd.read_csv(path)
    df = df.sort_values("as_of").reset_index(drop=True)
    total_anchors = len(df)

    # Drop no-pick anchors (NaN alpha) — reported, never zero-filled.
    valid = df[df["alpha_pct"].notna()].copy()
    dropped = total_anchors - len(valid)
    if len(valid) < 4:
        return {"ok": False, "summary_path": path,
                "message": f"Only {len(valid)} anchors with picks — too few for an IS/OOS split."}

    # Chronological split: earlier = in-sample, later = out-of-sample.
    n = len(valid)
    n_is = max(2, int(round(n * is_frac)))
    n_is = min(n_is, n - 2)   # keep >= 2 in OOS
    is_df = valid.iloc[:n_is]
    oos_df = valid.iloc[n_is:]

    m_is = _window_metrics(is_df["alpha_pct"].values)
    m_oos = _window_metrics(oos_df["alpha_pct"].values)

    # ── Hard gate ──
    verdict, reason, ratio = _gate(m_is, m_oos)

    return {
        "ok": True, "summary_path": path,
        "total_anchors": total_anchors, "no_pick_anchors": dropped,
        "is_window": (is_df["as_of"].iloc[0], is_df["as_of"].iloc[-1]),
        "oos_window": (oos_df["as_of"].iloc[0], oos_df["as_of"].iloc[-1]),
        "in_sample": m_is, "out_sample": m_oos,
        "sharpe_ratio_oos_to_is": ratio,
        "verdict": verdict, "reason": reason,
        "is_anchors": is_df[["as_of", "alpha_pct", "sharpe_ratio"]],
        "oos_anchors": oos_df[["as_of", "alpha_pct", "sharpe_ratio"]],
    }


def _gate(m_is, m_oos):
    """Return (verdict, reason, oos/is sharpe ratio)."""
    is_alpha, oos_alpha = m_is["mean_alpha"], m_oos["mean_alpha"]
    is_sh, oos_sh = m_is["sharpe"], m_oos["sharpe"]

    if not (is_alpha and is_alpha > 0):
        return ("NO-EDGE",
                "In-sample mean alpha <= 0 — there is no in-sample edge to validate. "
                "The issue is the screener/forward-window design, not overfitting. "
                "Fix the edge before invoking the overfit gate.", np.nan)

    ratio = round(oos_sh / is_sh, 2) if (is_sh and is_sh > 1e-9 and not np.isnan(oos_sh)) else np.nan

    if oos_alpha is None or np.isnan(oos_alpha) or oos_alpha <= 0:
        return ("STOP",
                f"OOS mean alpha flipped non-positive ({oos_alpha}) while in-sample was "
                f"+{is_alpha}. Edge does not persist out-of-sample — overfit/unstable.", ratio)

    if is_sh and is_sh > 0 and not np.isnan(ratio):
        if ratio >= GATE_THRESHOLD:
            return ("PASS",
                    f"OOS Sharpe is {ratio:.0%} of in-sample (>= {GATE_THRESHOLD:.0%}) "
                    f"and OOS alpha stays positive (+{oos_alpha}). Edge persists.", ratio)
        return ("STOP",
                f"OOS Sharpe is only {ratio:.0%} of in-sample (< {GATE_THRESHOLD:.0%}). "
                f"Degradation > 40% — treat as overfit; re-architect before Phase 3.", ratio)

    # IS alpha positive but IS sharpe not usable (e.g. single-anchor std) —
    # fall back to alpha-persistence only.
    return ("PASS (weak)",
            f"OOS alpha stays positive (+{oos_alpha}) vs in-sample +{is_alpha}, but "
            f"in-sample Sharpe was not estimable — verdict on alpha persistence only.", ratio)


def _print(res):
    print("\n" + "═" * 72)
    print("  WALK-FORWARD IS/OOS — Phase 2 overfit hard gate")
    print("═" * 72)
    if not res.get("ok"):
        print("\n⚠️  " + res["message"])
        if res.get("summary_path"):
            print(f"    (summary: {os.path.basename(res['summary_path'])})")
        print("═" * 72 + "\n")
        return

    print(f"\n  Source run : {os.path.basename(res['summary_path'])}")
    print(f"  Anchors    : {res['total_anchors']} total · {res['no_pick_anchors']} had no picks (dropped, not zero-filled)")
    print(f"  In-sample  : {res['in_sample']['n']} anchors  [{res['is_window'][0]} → {res['is_window'][1]}]")
    print(f"  Out-sample : {res['out_sample']['n']} anchors  [{res['oos_window'][0]} → {res['oos_window'][1]}]")

    def _row(lbl, m):
        sh = "n/a" if (m["sharpe"] is None or (isinstance(m["sharpe"], float) and np.isnan(m["sharpe"]))) else f"{m['sharpe']:+.2f}"
        return (f"    {lbl:<12} mean α {m['mean_alpha']:+.2f}%   "
                f"Sharpe {sh}   hit {m['hit_rate']}%   cum α {m['cum_alpha']:+.2f}%")
    print("\n  ── Window metrics ──")
    print(_row("IN-SAMPLE", res["in_sample"]))
    print(_row("OUT-SAMPLE", res["out_sample"]))
    r = res["sharpe_ratio_oos_to_is"]
    print(f"\n  OOS/IS Sharpe ratio : {'n/a' if (r is None or np.isnan(r)) else f'{r:.2f}'}"
          f"   (gate threshold {GATE_THRESHOLD:.2f})")

    badge = {"PASS": "✅ PASS", "PASS (weak)": "🟡 PASS (weak)",
             "STOP": "🔴 STOP", "NO-EDGE": "⚪ NO-EDGE"}.get(res["verdict"], res["verdict"])
    print(f"\n  VERDICT: {badge}")
    print(f"    ↳ {res['reason']}")
    print("\n" + "═" * 72 + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 2 walk-forward IS/OOS overfit gate.")
    ap.add_argument("--summary", default=None, help="validation *_summary.csv (default: LAST_RUN)")
    ap.add_argument("--is-frac", type=float, default=0.6, help="in-sample fraction (default 0.6)")
    ap.add_argument("--save", action="store_true", help="write a gate report CSV to validation_runs/")
    args = ap.parse_args(argv)

    res = evaluate(args.summary, args.is_frac)
    _print(res)
    if args.save and res.get("ok"):
        out = os.path.join(RUNS_DIR, "walkforward_oos_gate.csv")
        pd.DataFrame([{
            "source": os.path.basename(res["summary_path"]),
            "is_anchors": res["in_sample"]["n"], "oos_anchors": res["out_sample"]["n"],
            "is_mean_alpha": res["in_sample"]["mean_alpha"], "oos_mean_alpha": res["out_sample"]["mean_alpha"],
            "is_sharpe": res["in_sample"]["sharpe"], "oos_sharpe": res["out_sample"]["sharpe"],
            "oos_to_is_sharpe": res["sharpe_ratio_oos_to_is"], "verdict": res["verdict"],
        }]).to_csv(out, index=False)
        print(f"📄 Saved gate report → {os.path.relpath(out, _DIR)}\n")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
