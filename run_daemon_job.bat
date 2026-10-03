@echo off
REM Task Scheduler wrapper: run_daemon_job.bat <breadth|premarket|postmarket|weekly>
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
cd /d "%PROJ%"
if not exist logs mkdir logs
echo ---------- %date% %time% %1 ---------->> logs\daemon_jobs.log
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" run_daemon_job.py %1 >> logs\daemon_jobs.log 2>&1
