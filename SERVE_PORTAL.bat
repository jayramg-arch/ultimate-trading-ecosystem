@echo off
REM ===========================================================================
REM  Commander Portal server  (18-Sep-2026)
REM
REM  Serves the repo root read-only on :8502 so a phone/tablet on the Tailscale
REM  network can open:
REM    The Reviewer Log   http://jaynuc:8502/docs/portal/31_reviewer_log_v2.html
REM    The Library        http://jaynuc:8502/docs/portal/index.html
REM    any review .md     http://jaynuc:8502/logs/ai_reviews/<file>.md
REM  (the Log's "panel read" links resolve because logs/ is under the same root)
REM
REM  Web Commander itself is Streamlit on :8501 — http://jaynuc:8501
REM  Nothing here is exposed to the internet: reachable only over Tailscale or
REM  the LAN. Keep the window open; close it to stop.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo   Commander Portal on http://0.0.0.0:8502  (Tailscale: http://jaynuc:8502)
echo   Log:      /docs/portal/31_reviewer_log_v2.html
echo   Library:  /docs/portal/index.html
echo.
"%PY%" -m http.server 8502 --bind 0.0.0.0
endlocal
