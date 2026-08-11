@echo off
REM Daily journal <-> Dhan holdings sync (Windows Task Scheduler entry point).
REM Logs every run (stdout + stderr) to logs\journal_sync.log.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ---------- %DATE% %TIME% ---------->> "logs\journal_sync.log"
REM Pre-flight (see preflight.py): --unattended never blocks and always exits 0.
REM Findings go to logs\preflight.log and Telegram - a sync that silently wrote
REM nothing is worse than one that failed loudly.
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" preflight.py --unattended >> "logs\journal_sync.log" 2>&1
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" journal_sync.py >> "logs\journal_sync.log" 2>&1
