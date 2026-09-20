@echo off
REM Pre-open Dhan token check + auto-refresh (08:00 IST Mon-Fri) — Task Scheduler
REM entry point, same pattern as run_journal_sync.bat / run_gtt_trail.bat.
REM AUD-PY-06 (20-Sep-2026): the in-app 08:00 job only REPORTED an expired token
REM and only ran while Web Commander was up. This refreshes it (dhan_auth TOTP) so
REM the feed is on Dhan before the open whatever the app is doing.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ---------- %DATE% %TIME% ---------->> "logs\token_check.log"
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" dhan_token_check.py >> "logs\token_check.log" 2>&1
