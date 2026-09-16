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

REM  16-Sep-2026: the receiver had died silently by 17:00 while the tunnel stayed up,
REM  so TradingView got 502s and alerts were lost. The receiver window now RESTARTS
REM  it if it ever exits (10 s pause), and ngrok is only started when its local API
REM  (:4040) is not already answering - the free plan allows one agent session.
start "S4 webhook receiver :8000" cmd /k "for /l %%i in () do ("%PY%" dhan_tv_webhook.py & echo. & echo [receiver exited - restarting in 10 s; close this window to stop] & timeout /t 10 /nobreak >nul)"
timeout /t 4 /nobreak >nul
curl -s -m 3 http://127.0.0.1:4040/api/tunnels >nul 2>&1
if %errorlevel%==0 (
    echo   ngrok is already running - not starting a second agent.
) else if "%NGROK_DOMAIN%"=="" (
    start "ngrok tunnel" cmd /k ""%NGROK%" http 8000"
) else (
    start "ngrok tunnel" cmd /k ""%NGROK%" http --url=%NGROK_DOMAIN% 8000"
)
echo   Windows started. Keep them open. Log: logs\s4_alert_review.log
timeout /t 5 >nul
endlocal
