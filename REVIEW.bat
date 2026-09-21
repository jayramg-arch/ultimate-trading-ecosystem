@echo off
REM ===========================================================================
REM  REVIEW - ask the AI reviewer to read one name, right now  (21-Sep-2026)
REM
REM  Posts to the LOCAL receiver (:8000), so the review goes through exactly the
REM  same path an S4 GO alert takes: the queue, the 30-min dedup, the reviewer's
REM  own tabs (never yours), the banner, Telegram, and a row in the Reviewer Log.
REM  Use it when the GM board or your own S4 read makes you want the full case on
REM  a name that has not pinged - or has, and you want it re-read after the bar.
REM
REM    REVIEW.bat                 prompts for symbol and timeframe
REM    REVIEW.bat TITAN 75        no prompts
REM
REM  Needs the S4 Alert Reviewer window up (Morning does that) and the reviewer
REM  tabs open in TradingView. Symbols are NSE tickers as TradingView spells them
REM  (BAJAJ-AUTO, M&M). Timeframe 75, 125 or D.
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "SYM=%~1"
set "TF=%~2"
if "%SYM%"=="" set /p SYM=Symbol (e.g. TITAN):
if "%TF%"=="" set /p TF=Timeframe [75]:
if "%TF%"=="" set "TF=75"
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="S4_REVIEW_KEY" set "KEY=%%B"
)
if "!KEY!"=="" (echo   [X] S4_REVIEW_KEY missing from .env & pause & exit /b 1)
set "SYM=!SYM: =!"
echo.
echo   asking the reviewer for !SYM! !TF! ...
curl -s -m 10 -X POST "http://127.0.0.1:8000/s4-review?key=!KEY!" --data "!SYM! S4 GO !TF! - manual"
echo.
if errorlevel 1 (
    echo   [X] receiver not answering on :8000 - is the S4 Alert Reviewer window up?
) else (
    echo   queued. Watch the banner; the ruling lands on Telegram in about 90 s
    echo   and in the Reviewer Log. "duplicate within 30 min" = it was read recently.
)
echo.
pause
endlocal
