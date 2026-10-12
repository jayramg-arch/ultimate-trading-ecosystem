@echo off
REM ===========================================================================
REM  SET_S5_ROWS - fit S5's footprint row height to the stock on your S5 chart
REM  (12-Oct-2026). S5 reads order flow from footprint ROWS; their height is one
REM  fixed input per chart, so after you change symbol, click this once. It sets
REM  'Ticks per volume row' so a typical bar spans ~10 rows (ATR / 10 / tick size).
REM  No recompile. The reviewer's own S5 tab is fitted automatically on every review.
REM    SET_S5_ROWS.bat          your S5 tab(s)
REM    SET_S5_ROWS.bat --check  show, change nothing
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" s5_rows.py %*
echo.
ping -n 6 127.0.0.1 >nul
endlocal
