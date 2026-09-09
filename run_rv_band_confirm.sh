#!/usr/bin/env bash
# CONFIRMATORY sample for docs/PREREG_rv_band_selection_layer.md section 2.
# 36 months so the scorer can drop every anchor already used in the 24-month run
# (validation_20260726_225547) and evaluate ONLY on anchors never looked at.
PY="/c/Users/jayra/TradingData/venv/Scripts/python.exe"
echo "=== started $(date '+%F %T') ==="
$PY -u validation.py --months 36 --universe nifty500 --screener bull \
    --catalyst_windows --bootstrap_n 10000 > validation_runs/_rv_confirm.log 2>&1
echo "=== finished $(date '+%F %T') rc=$? ==="
tail -3 validation_runs/_rv_confirm.log
