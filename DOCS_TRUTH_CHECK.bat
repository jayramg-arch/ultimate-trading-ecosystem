@echo off
REM ===================================================================
REM  DOCS TRUTH CHECK - does the code still match what the Library says?
REM
REM  Reports only facts that MOVED since the last accepted baseline, and
REM  names the pages that cite each one. It never edits anything: a moved
REM  fact can mean the doc is stale OR that the code change was the
REM  mistake, and both have happened here.
REM
REM  Exit 0 = nothing moved.  Exit 1 = re-check the listed pages.
REM  After fixing the pages, re-run with --accept to re-baseline.
REM
REM  Schedule daily post-close alongside the journal sync.
REM ===================================================================
title Docs truth check
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
cd /d "%PROJ%" || (echo [X] Project folder not found & goto :hold)
if not exist "%PY%" (echo [X] Python not found at %PY% & goto :hold)
"%PY%" docs_audit\truth_watch.py %*
:hold
echo.
pause
