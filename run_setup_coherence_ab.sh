#!/usr/bin/env bash
# ABLATION: does gating the GO on SETUP COHERENCE (the pattern must be the right KIND
# for the playbook) beat gating on "any PA pattern fired"? Jay's question, 5-Sep-2026.
# Sequential, not parallel - they share the OHLCV cache and the Dhan feed.
PY="/c/Users/jayra/TradingData/venv/Scripts/python.exe"
COMMON="--gate s4go --months 24 --universe nifty500 --screener bull --qualify catalyst --catalyst_windows --bootstrap_n 10000"
echo "=== CONTROL  started $(date '+%F %T') ==="
$PY -u validation.py $COMMON            > validation_runs/_coh_control.log 2>&1
echo "=== CONTROL  finished $(date '+%F %T') rc=$? ==="
echo "=== TREAT    started $(date '+%F %T') ==="
$PY -u validation.py $COMMON --setup_coherent > validation_runs/_coh_treat.log 2>&1
echo "=== TREAT    finished $(date '+%F %T') rc=$? ==="
