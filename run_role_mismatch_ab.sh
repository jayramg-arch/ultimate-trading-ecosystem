#!/usr/bin/env bash
# roleMismatch A/B — pre-registered in docs/PREREG_role_mismatch.md.
# Two arms at 36 months so FRESH anchors exist (section 5). Sequential: these runs
# are CPU-bound and a concurrent pair would just contend.
set -u
cd "$(dirname "$0")"
PY=/c/Users/jayra/TradingData/venv/Scripts/python.exe
COMMON="--months 36 --universe nifty500 --screener bull --gate s4go --catalyst_windows --bootstrap_n 10000"
echo "=== CONTROL  (role_mismatch OFF)  $(date) ==="
"$PY" -u validation.py $COMMON                    > validation_runs/_rm_control.log 2>&1
echo "=== TREAT    (role_mismatch ON)   $(date) ==="
"$PY" -u validation.py $COMMON --role_mismatch    > validation_runs/_rm_treat.log   2>&1
echo "=== DONE $(date) ==="
