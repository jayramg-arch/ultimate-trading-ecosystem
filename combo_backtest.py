"""combo_backtest — does a PA COMBINATION beat a Σ-matched control?

THE QUESTION. Jay's hypothesis is that synergistic pairs (a structural context plus an
immediate trigger) outperform a raw Σ score. That is an edge claim, so it gets an edge
test rather than a plausibility argument.

THE CONTROL IS THE WHOLE EXPERIMENT. Comparing combo-present against everything else
would mostly rediscover that more patterns fire when a stock is moving — a combo needs
at least two patterns, so it is correlated with high Σ by construction. The comparison
that means something is:

    combo-present   vs   combo-absent AT THE SAME Σ

If the combo cohort wins only because its Σ is higher, this shows it. If a combo carries
information beyond the count, it survives the Σ match.

METHOD. For each pick in a validation details file, rebuild the price history PINNED to
that pick's own As_Of date (data_provider's replay pin — no look-ahead), recompute pattern
AGES from the same batteries the live surfaces use, and tag the combos. Outcome is
Alpha_Matched_pct, which is already matched to the trade's ACTUAL hold (the 26-Jul fix).

Small cells are expected and are reported as such. Five combos over ~464 picks will leave
some with a dozen instances; a mean over twelve trades is a story, not a result.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import pa_combos as pc


def _pin(sym, as_of, dp):
    """History as it stood at the pick's own date — never after."""
    try:
        dp.set_pinned_date(as_of)
    except Exception:
        pass
    try:
        return dp.fetch_ohlcv(sym, period="2y", interval="1d", use_cache=True, auto_adjust=True)
    except Exception:
        return None


def run(details_csv: str, limit: int = 0, out_csv: str = "") -> pd.DataFrame:
    import data_provider as dp

    d = pd.read_csv(details_csv)
    need = {"Symbol", "As_Of", "Alpha_Matched_pct"}
    missing = need - set(d.columns)
    if missing:
        raise SystemExit(f"details file lacks {missing}")
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    if limit:
        d = d.head(limit)

    rows = []
    for i, r in enumerate(d.itertuples(index=False), 1):
        sym, as_of = str(r.Symbol), str(r.As_Of)[:10]
        df = _pin(sym, as_of, dp)
        if df is None or len(df) < 100:
            continue
        # Which battery ran matters, and the column it lives in DIFFERS by screener:
        # bull emits Catalyst, recovery emits Signal_Label. Reading only Catalyst is the
        # convention bug that silently invalidated an 11.6h re-baseline - every recovery
        # pick fell through as bull. replay.catalyst_label_of() is the one resolver.
        try:
            import replay as _rp
            _lbl = _rp.catalyst_label_of(r._asdict())
        except Exception:
            _lbl = str(getattr(r, "Catalyst", "") or getattr(r, "Signal_Label", ""))
        rec = _lbl.upper().startswith(("REV", "WYC"))
        ages = pc.pattern_ages(df, recovery=rec)
        combos = pc.combos_from_ages(ages, recovery=rec)
        fired = [n for n, a in ages.items() if a == 0]
        rows.append(dict(
            symbol=sym, as_of=as_of, catalyst=_lbl,
            alpha=float(r.Alpha_Matched_pct), recovery=rec, label=_lbl,
            sigma=len(fired), patterns="|".join(sorted(fired)),
            combos="|".join(c["key"] for c in combos), n_combo=len(combos)))
        if i % 50 == 0:
            print(f"   {i}/{len(d)} …", flush=True)

    try:
        dp.set_pinned_date(None)
    except Exception:
        pass

    res = pd.DataFrame(rows)
    if out_csv and len(res):
        res.to_csv(out_csv, index=False)
        print(f"\nper-pick detail -> {out_csv}")
    return res


def report(res: pd.DataFrame) -> None:
    if not len(res):
        print("no rows scored")
        return
    print(f"\npicks scored: {len(res)}   with >=1 combo: {int((res.n_combo > 0).sum())}")
    print(f"overall mean matched alpha: {res.alpha.mean():+.2f}%   median {res.alpha.median():+.2f}%")

    print("\n── per combo, against a SIGMA-MATCHED control ──")
    print(f"{'combo':22s} {'n':>4s} {'mean α':>8s} {'median':>8s} {'win%':>6s} | "
          f"{'ctrl n':>6s} {'ctrl α':>8s} {'edge':>8s}")
    for c in pc.COMBOS:
        k = c["key"]
        hit = res[res.combos.str.contains(k, na=False)]
        if not len(hit):
            print(f"{c['name'][:22]:22s} {0:4d}   — never fired in this sample")
            continue
        # Control: same side, same Σ distribution, but this combo absent. Matching on Σ
        # is what separates "the combo matters" from "two patterns beat one".
        pool = res[(res.recovery == (c["side"] == "recovery")) &
                   (~res.combos.str.contains(k, na=False))]
        ctrl = pool[pool.sigma.isin(hit.sigma.unique())]
        e = (hit.alpha.mean() - ctrl.alpha.mean()) if len(ctrl) else np.nan
        print(f"{c['name'][:22]:22s} {len(hit):4d} {hit.alpha.mean():+8.2f} "
              f"{hit.alpha.median():+8.2f} {100*(hit.alpha > 0).mean():5.0f}% | "
              f"{len(ctrl):6d} {ctrl.alpha.mean():+8.2f} "
              f"{e:+8.2f}" if len(ctrl) else "   ctrl empty")

    print("\n── the naive view (no Σ control) — kept to show what it would have claimed ──")
    a = res[res.n_combo > 0].alpha
    b = res[res.n_combo == 0].alpha
    if len(a) and len(b):
        print(f"any combo  n={len(a):3d}  mean {a.mean():+.2f}%   |   none  n={len(b):3d}  "
              f"mean {b.mean():+.2f}%   naive edge {a.mean()-b.mean():+.2f}pp")
        print(f"   Σ: combo cohort {res[res.n_combo>0].sigma.mean():.2f} vs "
              f"{res[res.n_combo==0].sigma.mean():.2f} — if these differ, the naive edge is "
              f"mostly Σ, not synergy.")

    print("\n── plain Σ, for reference: does counting patterns predict anything at all? ──")
    g = res.groupby(res.sigma.clip(0, 5))
    print(g.alpha.agg(["count", "mean", "median"]).round(2).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default="validation_runs/validation_20260726_225547_details.csv")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="validation_runs/_combo_scored.csv")
    a = ap.parse_args()
    report(run(a.details, a.limit, a.out))
