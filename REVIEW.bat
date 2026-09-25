@echo off
REM ===========================================================================
REM  REVIEW - ask the AI reviewer to read one or MANY names, right now
REM  (21-Sep-2026; several names at once since 25-Sep-2026)
REM
REM  Posts to the LOCAL receiver (:8000), so each review goes through exactly the
REM  same path an S4 GO alert takes: the queue, the 30-min dedup, the reviewer's
REM  own tabs (never yours), the banner, Telegram, and a row in the Reviewer Log.
REM  Names queue and are read ONE AT A TIME, about 90 s each.
REM
REM    REVIEW.bat                                   prompts for the list
REM    REVIEW.bat TITAN 75                          one name
REM    REVIEW.bat TITAN 75 RRKABEL 125 GOLDBEES D   several names and timeframes
REM    REVIEW.bat TITAN:75,RRKABEL:125,NIFTYBEES    same, colon form; no TF = 75
REM
REM  Needs the S4 Alert Reviewer window up (Morning does that) and the reviewer
REM  tabs open in TradingView. Symbols are NSE tickers as TradingView spells them
REM  (BAJAJ-AUTO, M&M). Timeframe 75, 125 or D.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" review_many.py %*
echo.
pause
endlocal
