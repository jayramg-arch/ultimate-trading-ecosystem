@echo off
REM Daily Regime - the block for right now (IST, NSE holidays known), with links.
REM   DAILY_REGIME            print it
REM   DAILY_REGIME --open     print it and open its pages
REM   DAILY_REGIME --phase all
cd /d "%~dp0"
set PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe
"%PY%" daily_regime.py %*
echo.
pause
