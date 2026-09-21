@echo off
REM Push both Golden Matcher bundles (gm_bundles\latest.txt) into S4 on EVERY chart
REM tab that carries it, over TradingView's CDP port - replaces six manual pastes.
REM Needs TradingView launched with LAUNCH_TRADINGVIEW_CDP.bat and the S4 tabs open.
REM Runs automatically at the end of the Evening run too; this is the by-hand button.
REM   PUSH_BUNDLES.bat --check   shows what each tab holds, changes nothing.
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" tv_push_bundles.py %*
echo.
pause
endlocal
