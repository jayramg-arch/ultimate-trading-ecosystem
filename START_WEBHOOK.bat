@echo off
REM ===========================================================================
REM  TradingView webhook receiver  (Jay, 24-Aug-2026, item #14)
REM
REM  "Webhook delivery failed" on TradingView means TV could not REACH the URL.
REM  Nothing was listening: the receiver is manual-launch, had no launcher, and
REM  logs/ held no webhook file at all -- so it had never received anything.
REM
REM  TWO PROCESSES ARE REQUIRED. This starts the first. The second is a tunnel,
REM  because TradingView's servers cannot see localhost:
REM      ngrok http 8000
REM  ...then paste the https URL + /tv-webhook into the alert's Webhook URL box.
REM
REM  THE TRAP, and the reason this has never worked for long: a FREE ngrok URL
REM  CHANGES ON EVERY RESTART, so every alert holding the old URL starts failing
REM  the moment ngrok is restarted. Alerts are already recreated daily here (the
REM  GM watchlist name is date-stamped) and are DELETED by every S4 recompile, so
REM  a rotating URL means re-pasting it into every alert, every day.
REM  Fix that first or this will keep failing:
REM     - ngrok paid: a reserved domain, then the URL never changes
REM     - Cloudflare Tunnel: free, and gives a stable hostname
REM  A static URL is a precondition, not an optimisation.
REM
REM  SAFETY: order placement is opt-in. DRY_RUN defaults to True, so this logs
REM  what it WOULD do and places nothing. Set DRY_RUN=False only when you
REM  actually want it arming live GTTs -- and note that contradicts the standing
REM  confirmation-before-entry doctrine, where the chart read has the veto.
REM ===========================================================================
setlocal
cd /d "%~dp0"

set "VENV=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%VENV%" (
  echo [X] venv python not found at %VENV%
  echo     The app runs from the TradingData venv, not a project .venv.
  pause
  exit /b 1
)

echo.
echo  ================================================================
echo   TradingView webhook receiver
echo  ================================================================
echo   DRY_RUN : %DRY_RUN%   (empty or True = logs only, places nothing)
echo   Listening on http://localhost:8000/tv-webhook
echo.
echo   In a SECOND terminal:  ngrok http 8000
echo   Then paste  https^://^<id^>.ngrok.app/tv-webhook  into the alert.
echo  ================================================================
echo.

REM Foreground, deliberately. Backgrounding a server here is how the Streamlit
REM process ended up orphaned and serving stale code for two hours; if this
REM window is open the receiver is up, and closing it stops it.
"%VENV%" dhan_tv_webhook.py

echo.
echo  Receiver stopped.
pause
