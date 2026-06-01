#!/usr/bin/env python3
"""
test_baseline_no_hook.py — Reproduce v1 FINAL baseline WITHOUT the v2_fixes hook.

Verifies whether the apparent baseline drift between Run 20260508_105114
(alpha 4.45) and Run 20260508_170831 (alpha 2.61) is caused by the
v2_fixes.select_top_n hook subtly changing tiebreak behavior at the Top-N
truncation point even with all flags off.

Strategy: monkey-patch v2_fixes.select_top_n to raise an exception, which
forces validation.py's `except Exception:` fallback to the original code:
    picks.sort_values("Score", ascending=False).head(top_n)
"""
from __future__ import annotations
import sys
import json

# Force the fallback path by neutering the hook BEFORE validation imports it.
import v2_fixes
def _broken_hook(*a, **kw):
    raise RuntimeError("force fallback for baseline reproduction")
v2_fixes.select_top_n = _broken_hook

# Also defang adjust_record_score and adjust_catalyst_score so they're true
# no-ops. With all flags off they should already be no-ops, but let's be safe.
v2_fixes.reset()

import validation

if __name__ == "__main__":
    print("=" * 70)
    print("CLEAN BASELINE — v2_fixes hooks neutered, fallback to plain sort")
    print("=" * 70)
    result = validation.run_validation(
        months_back=12,
        top_n=10,
        universe_name="nifty500",
    )
    agg = result.get("aggregate", {})
    print()
    print("Aggregate:")
    print(json.dumps(agg, indent=2, default=str))
    print()
    print(f"Run ID: {result.get('run_id')}")
    print(f"Compare against:")
    print(f"  Prior FINAL (20260508_105114): alpha 4.45 / hit 91.7 / winrate 61.7")
    print(f"  Hook-active     (20260508_170831): alpha 2.61 / hit 91.7 / winrate 54.2")
    print(f"  This run        ({result.get('run_id')}): "
          f"alpha {agg.get('anchor_avg_alpha_pct')} / "
          f"hit {agg.get('alpha_hit_rate_pct')} / "
          f"winrate {agg.get('anchor_avg_winrate_pct')}")
