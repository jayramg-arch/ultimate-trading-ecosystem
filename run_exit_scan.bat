@echo off
REM 16:00 IST exit-signal scan (stop hits, stage decay, time stops -> Telegram ACTION
REM rows) — Task Scheduler entry point. AUD-PY-06 (20-Sep-2026): the in-app job had
REM no catch-up and needed Web Commander up at 16:00; this survives restarts and
REM runs on wake if the machine slept through it. The in-app copy is idempotent, so
REM both firing on one day only repeats a message.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ---------- %DATE% %TIME% ---------->> "logs\exit_scan.log"
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" exit_signal_engine.py --silent >> "logs\exit_scan.log" 2>&1
