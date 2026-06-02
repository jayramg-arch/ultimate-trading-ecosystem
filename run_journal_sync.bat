@echo off
REM Daily journal <-> Dhan holdings sync (Windows Task Scheduler entry point).
REM Logs every run (stdout + stderr) to logs\journal_sync.log.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ---------- %DATE% %TIME% ---------->> "logs\journal_sync.log"
".venv\Scripts\python.exe" journal_sync.py >> "logs\journal_sync.log" 2>&1
