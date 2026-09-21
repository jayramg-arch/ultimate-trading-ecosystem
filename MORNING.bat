@echo off
REM ===========================================================================
REM  MORNING - one click brings the desk up  (21-Sep-2026)
REM
REM  Starts, in order, and ONLY what is not already running (safe to re-run):
REM    1. TradingView Desktop with the CDP port (:9222)   LAUNCH_TRADINGVIEW_CDP.bat
REM    2. Web Commander (:8501)                            LAUNCH_COMMANDER.bat
REM    3. S4 alert reviewer + ngrok tunnel (:8000/:4040)  START_ALERT_REVIEWER.bat
REM    4. Reviewer banner (the always-on-top strip)       REVIEWER_BANNER.bat
REM    5. Commander Portal for phone/tablet (:8502)       SERVE_PORTAL.bat
REM
REM  NOT here, on purpose:
REM    BIND_S4_SOURCES.bat - only after an S4 compile (bindings live in the layout
REM                          and survive restarts; a recompile drops them).
REM    Alerts               - recreate the 75m + 125m GO alerts on the day's list.
REM
REM  After it runs: open the five chart tabs in TV (S4 Phase-2, S5 Layout,
REM  S4 Reviewer, S5 Reviewer, S4 Phase-1) - the reviewer needs them open.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"

echo ==============================================================
echo   WEINSTEIN COMMANDER - MORNING
echo ==============================================================

REM 1. TradingView with CDP
call :listening 9222
if %errorlevel%==0 (echo   [ok]    TradingView CDP :9222 already up) else (
    echo   [start] TradingView with CDP...
    call "LAUNCH_TRADINGVIEW_CDP.bat"
)

REM 2. Web Commander
call :listening 8501
if %errorlevel%==0 (echo   [ok]    Web Commander :8501 already up) else (
    echo   [start] Web Commander...
    start "Web Commander" cmd /c "LAUNCH_COMMANDER.bat"
)

REM 3. Alert reviewer (its own launcher checks ngrok on :4040 itself)
call :listening 8000
if %errorlevel%==0 (echo   [ok]    Alert reviewer :8000 already up) else (
    echo   [start] Alert reviewer + tunnel...
    start "S4 Alert Reviewer" cmd /c "START_ALERT_REVIEWER.bat"
)

REM 4. Banner (a pythonw process running reviewer_banner.py)
%PS% "if (Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*reviewer_banner.py*' }) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (echo   [ok]    Reviewer banner already up) else (
    echo   [start] Reviewer banner...
    call "REVIEWER_BANNER.bat"
)

REM 5. Portal
call :listening 8502
if %errorlevel%==0 (echo   [ok]    Commander Portal :8502 already up) else (
    echo   [start] Commander Portal...
    start "Commander Portal :8502" cmd /c "SERVE_PORTAL.bat"
)

echo.
echo   Done. Now in TradingView: open the 5 chart tabs, then recreate the two GO alerts.
echo   (After an S4 compile ONLY: BIND_S4_SOURCES.bat)
timeout /t 8 >nul
endlocal
exit /b 0

:listening
netstat -ano | findstr /r /c:":%1 .*LISTENING" >nul 2>&1
exit /b %errorlevel%
