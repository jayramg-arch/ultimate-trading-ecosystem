@echo off
REM Morning Telegram digest (Task Scheduler: Morning_Digest, 08:45 IST Mon-Fri).
REM Exit review (holdings at/below their Chandelier), earnings in 7 days, market line.
REM Read-only. Skips NSE holidays by itself.
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
cd /d "%PROJ%"
if not exist logs mkdir logs
echo ---------- %date% %time% ---------->> logs\morning_digest.log
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" morning_digest.py >> logs\morning_digest.log 2>&1
