@echo off
REM Reviewer banner — always-on-top strip showing whether the AI reviewer is
REM driving your TradingView charts. Read-only: tails logs/s4_alert_review.log.
REM Right-click the strip to close. Safe to start/stop any time.
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"
start "" "%PY%" reviewer_banner.py
endlocal
