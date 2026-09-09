@echo off
REM 60-month confirmatory control run for the abandon variant (H7).
REM Pre-registered in docs/PREREG_role_mismatch.md BEFORE the run: threshold frozen at
REM NonIgn_Score >= 1, confirmatory set = anchors absent from 20260909_055448.
REM
REM Deferred to after the close on purpose. Started at 10:01 IST on 9 Sep 2026, killed
REM two minutes in: it is a read-only measurement, which the market-hours protocol
REM allows, but a 60-month x nifty500 sweep with Dhan=ON can trip DH-904 throttling,
REM and that lands on the LIVE board's feed, not just on this run.
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo Started %DATE% %TIME% > "validation_runs\_nonign_60mo.log"
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" -u validation.py ^
  --months 60 --universe nifty500 --screener bull ^
  --gate s4go --qualify catalyst --catalyst_windows --bootstrap_n 10000 ^
  >> "validation_runs\_nonign_60mo.log" 2>&1
echo Finished %DATE% %TIME% >> "validation_runs\_nonign_60mo.log"
