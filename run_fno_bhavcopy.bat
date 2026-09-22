@echo off
REM ===========================================================================
REM  Daily F&O derivatives history  (Task Scheduler: Fno_Bhavcopy_Daily, 18:45)
REM
REM  One NSE file per trading day -> data/fno_history.csv: near-month futures OI
REM  and change, settlement, and the reconstructed option chain (PCR, max pain,
REM  call/put wall, ATM dOI) for every F&O name. This is the history every
REM  derivatives rule has to be validated against; without it the walls are an
REM  opinion. Backfilled to 27-Mar-2026 on 21-Sep.
REM
REM  18:45 because NSE publishes the bhavcopy after ~18:00 IST - the 16:30
REM  auto-pilot is too early. --backfill 5 catches a day the PC slept through,
REM  and days already stored are skipped, so re-running costs nothing.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" fno_bhavcopy.py --backfill 5 >> "logs\fno_bhavcopy.log" 2>&1
endlocal
