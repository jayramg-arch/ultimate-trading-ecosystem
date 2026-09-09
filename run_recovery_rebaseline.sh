#!/bin/bash
# Recovery re-baseline — the FIRST valid one. Held until after 15:30 IST so the ~12h run
# does not compete with the live board for the Dhan feed during the session.
cd "C:/Users/jayra/Documents/GeminiVSCode"
LOG="validation_runs/_recovery_rebaseline_20260810.log"
PY="C:/Users/jayra/TradingData/venv/Scripts/python.exe"

# wait for the close
while [ "$(date +%H%M)" -lt "1531" ]; do sleep 30; done

echo "=== launching $(date '+%F %T') ===" >> "$LOG"
# PRE-FLIGHT: the 6-Aug attempt died at anchor 14/19 with 'Offline: serving EXPIRED cache'.
# Refuse to start blind rather than grind 12h on stale bars.
"$PY" -c "
import sys,warnings; warnings.filterwarnings('ignore')
import data_provider as dp
p=dp.get_ltp('RELIANCE'); s=str(dp.get_last_source('RELIANCE') or '')
print('preflight LTP',p,'source',s)
sys.exit(0 if (p and s.startswith('dhan')) else 1)
" >> "$LOG" 2>&1
if [ $? -ne 0 ]; then echo "PREFLIGHT FAILED — feed not live. Not starting." >> "$LOG"; exit 1; fi

"$PY" -u validation.py --months 24 --universe nifty500 --screener recovery \
      --catalyst_windows --bootstrap_n 10000 >> "$LOG" 2>&1
echo "=== finished $(date '+%F %T') rc=$? ===" >> "$LOG"
