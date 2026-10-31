@echo off
REM Saturday portfolio review - Task Scheduler entry point (Portfolio_Review_Weekly, Sat 09:30).
REM Weekdays run it inside the auto-pilot (Phase 13b); this is the weekend pass on the
REM confirmed weekly close (31-Oct-2026, Jay). Non-interactive: no pause, output to the log.
REM
REM TradingView must be up with the debug port (:9222) for the chart read. On a Saturday it
REM may not be, so it is started here first - ONLY when :9222 does not answer, because the
REM launcher restarts TradingView.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist logs mkdir logs
echo. >> logs\portfolio_review_task.log
echo === %date% %time% Saturday portfolio review >> logs\portfolio_review_task.log
powershell -NoProfile -Command "$c = New-Object Net.Sockets.TcpClient; try { if ($c.ConnectAsync('127.0.0.1', 9222).Wait(800) -and $c.Connected) { $c.Close(); exit 0 } } catch {}; $c.Close(); exit 1"
if errorlevel 1 (
    echo TradingView CDP not up - starting it >> logs\portfolio_review_task.log
    powershell -NoProfile -ExecutionPolicy Bypass -File "launch_tradingview_cdp.ps1" >> logs\portfolio_review_task.log 2>&1
    timeout /t 90 /nobreak > nul
)
"%PY%" portfolio_review.py --telegram >> logs\portfolio_review_task.log 2>&1
