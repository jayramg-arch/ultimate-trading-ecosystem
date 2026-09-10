#!/usr/bin/env bash
# Close-basis stop A/B — TREAT arm only.
# The CONTROL is the existing run 20260909_055448: same command, and SL_BASIS defaults
# to "intraday", whose code path is asserted unchanged by tests/test_sl_basis.py. No
# point burning 30 minutes reproducing it.
# Waits for the 60-month run to finish first — these are CPU-bound and would contend.
set -u
cd "$(dirname "$0")"
PY=/c/Users/jayra/TradingData/venv/Scripts/python.exe
until grep -q "VALIDATION COMPLETE" validation_runs/_nonign_60mo.log 2>/dev/null; do sleep 60; done
echo "=== 60mo done; starting close-basis TREAT $(date) ==="
"$PY" -u validation.py --months 36 --universe nifty500 --screener bull \
      --gate s4go --qualify catalyst --catalyst_windows --bootstrap_n 10000 \
      --sl_basis close > validation_runs/_slbasis_close.log 2>&1
echo "=== close-basis TREAT done $(date) ==="
grep "run_id=" validation_runs/_slbasis_close.log | tail -1
