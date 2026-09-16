@echo off
REM ===========================================================================
REM  S4 alert -> AI review, end to end  (16-Sep-2026)
REM
REM  Starts the TWO processes an alert needs to reach the reviewer:
REM    1. the TradingView webhook receiver (dhan_tv_webhook.py on :8000) - its
REM       /s4-review route queues a review; /tv-webhook (orders) stays DRY_RUN
REM       and refuses everything unless WEBHOOK_SECRET is set, as before;
REM    2. the ngrok tunnel, on your STATIC domain (NGROK_DOMAIN in .env), so
REM       the URL in the alerts never changes across restarts.
REM
REM  ONE-TIME SETUP
REM    a) ngrok dashboard -> Domains -> "New Domain" (free: one static domain per
REM       account, e.g. clever-name.ngrok-free.app) -> put it in .env as
REM           NGROK_DOMAIN=clever-name.ngrok-free.app
REM    b) in EVERY S4 GO alert (75m and 125m), Notifications tab -> Webhook URL:
REM           https://<NGROK_DOMAIN>/s4-review?key=<S4_REVIEW_KEY from .env>
REM       Message: leave S4's default ("{{ticker}} S4 GO {{interval}} - ...").
REM
REM  EVERY DAY: run this before the open (or after any restart). Two console
REM  windows stay open; close them to stop. The reviewer takes the chart tabs
REM  over for ~60-90 s per alert and switches them back afterwards.
REM
REM  CHECK: logs\s4_alert_review.log — "queued ... reviewed in Ns (telegram sent)".
REM  TEST without an alert (from a third console):
REM    curl -X POST "https://<NGROK_DOMAIN>/s4-review?key=<KEY>" --data "RELIANCE S4 GO 75 - test"
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
set "NGROK=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
set PYTHONIOENCODING=utf-8

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="NGROK_DOMAIN"  set "NGROK_DOMAIN=%%B"
    if /i "%%A"=="S4_REVIEW_KEY" set "S4_REVIEW_KEY=%%B"
)

if not exist "%NGROK%" set "NGROK=ngrok"
if "%S4_REVIEW_KEY%"=="" (
    echo   [X] S4_REVIEW_KEY missing from .env - the /s4-review route refuses everything without it.
    pause & exit /b 1
)

echo ==============================================================
echo   S4 ALERT REVIEWER
echo ==============================================================
echo   receiver : http://localhost:8000/s4-review
if "%NGROK_DOMAIN%"=="" (
    echo   tunnel   : RANDOM ngrok URL - set NGROK_DOMAIN in .env for a fixed one.
    echo              Read the https URL off the ngrok window and paste it into the alerts.
) else (
    echo   tunnel   : https://%NGROK_DOMAIN%
    echo   alert URL: https://%NGROK_DOMAIN%/s4-review?key=%S4_REVIEW_KEY%
)
echo.

start "S4 webhook receiver :8000" cmd /k ""%PY%" dhan_tv_webhook.py"
timeout /t 4 /nobreak >nul
if "%NGROK_DOMAIN%"=="" (
    start "ngrok tunnel" cmd /k ""%NGROK%" http 8000"
) else (
    start "ngrok tunnel" cmd /k ""%NGROK%" http --url=%NGROK_DOMAIN% 8000"
)
echo   Both windows started. Keep them open. Log: logs\s4_alert_review.log
timeout /t 5 >nul
endlocal
