@echo off
REM ===========================================================================
REM  MORNING - one click brings the desk up  (21-Sep-2026)
REM
REM  Starts, in order, and ONLY what is not already running (safe to re-run):
REM    0. Tailscale connected (starts the tray app if the service is stuck)
REM    1. TradingView Desktop with the CDP port (:9222)   LAUNCH_TRADINGVIEW_CDP.bat
REM    2. Web Commander (:8501)                            LAUNCH_COMMANDER.bat
REM    3. S4 alert reviewer + ngrok tunnel (:8000/:4040)  START_ALERT_REVIEWER.bat
REM    4. Reviewer banner (the always-on-top strip)       REVIEWER_BANNER.bat
REM    5. Commander Portal for phone/tablet (:8502)       SERVE_PORTAL.bat
REM    6. File Browser for phone/tablet (:8503, Tailscale) START_FILEBROWSER.bat
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

REM 0. Tailscale (12-Oct-2026). The service can sit in "NoState" all day when the
REM    tray app did not start at boot - it then waits for the tray to tell it to
REM    connect, and the phone cannot reach this PC at all (20 Sep, 10 Oct, 11 Oct).
REM    Unattended mode (on since 12 Oct) should prevent it; this is the backstop:
REM    start the tray app if the backend is not Running, then report the state.
set "TSX=C:\Program Files\Tailscale"
if exist "%TSX%\tailscale.exe" (
    %PS% "$s=(& '%TSX%\tailscale.exe' status --json 2>$null | ConvertFrom-Json).BackendState; if ($s -eq 'Running') { exit 0 }; if (-not (Get-Process tailscale-ipn -ErrorAction SilentlyContinue)) { Start-Process '%TSX%\tailscale-ipn.exe' }; for ($i=0; $i -lt 15; $i++) { Start-Sleep 2; $s=(& '%TSX%\tailscale.exe' status --json 2>$null | ConvertFrom-Json).BackendState; if ($s -eq 'Running') { exit 2 } }; Write-Host ('          Tailscale state: ' + $s); exit 1"
    if errorlevel 2 (echo   [start] Tailscale was not connected - tray app started, now Running) else if errorlevel 1 (echo   [WARN]  Tailscale is NOT running - the phone cannot reach this PC. REMOTE_ADMIN_SETUP.bat option 1) else (echo   [ok]    Tailscale connected)
) else (
    echo   [skip]  Tailscale not installed
)

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

REM 6. File Browser (127.0.0.1:8503, published to the tailnet as http://jaynuc:8503)
call :listening 8503
if %errorlevel%==0 (echo   [ok]    File Browser :8503 already up) else (
    echo   [start] File Browser...
    start "File Browser starter" /min cmd /c "START_FILEBROWSER.bat"
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
