@echo off
REM Point the two S4 GO alerts (75m + 125m) at today's GM board list, with today's bundles.
REM Runs automatically as auto-pilot Phase 12b. Use this after pushing bundles by hand.
REM   REFRESH_ALERTS            refresh both alerts
REM   REFRESH_ALERTS --dry-run  show what would change, touch nothing
cd /d "%~dp0"
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" tv_gm_alerts.py %*
pause
