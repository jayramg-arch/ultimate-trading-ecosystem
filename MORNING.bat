@echo off
REM ===========================================================================
REM  MORNING - one click brings the desk up  (21-Sep-2026)
REM
REM  Starts, in order, and ONLY what is not already running (safe to re-run):
REM    0. Tailscale connected (starts the tray app if it is missing)
REM    1. TradingView Desktop with the CDP port (:9222)   LAUNCH_TRADINGVIEW_CDP.bat
REM    2. Web Commander (:8501)                            LAUNCH_COMMANDER.bat
REM    3. S4 alert reviewer + ngrok tunnel (:8000/:4040)  START_ALERT_REVIEWER.bat
REM    4. Reviewer banner (the always-on-top strip)       REVIEWER_BANNER.bat
REM    5. Commander Portal for phone/tablet (:8502)       SERVE_PORTAL.bat
REM    6. File Browser for phone/tablet (:8503, Tailscale) START_FILEBROWSER.bat
REM
REM  16-Oct-2026: "already running" is a CONNECT test, not netstat. netstat|findstr
REM  came back empty while the services were up, so MORNING started a second receiver
REM  and - for :9222 - ran the TradingView launcher, which KILLS and relaunches TV.
REM  Every step is logged to logs\morning.log, so a run that sticks shows where.
REM
REM  NOT here, on purpose:
REM    BIND_S4_SOURCES.bat - only after an S4 compile (bindings live in the layout
REM                          and survive restarts; a recompile drops them).
REM    Alerts               - recreated nightly by the auto-pilot (Phase 12b).
REM
REM  After it runs: open the chart tabs in TV (S4 Phase-2, S5 Layout, S4 Reviewer,
REM  S5 Reviewer, S4 Phase-1, Panel Layout) - the reviewer needs its tabs open.
REM ===========================================================================
setlocal
cd /d "%~dp0"
set "PS=powershell -NoProfile -ExecutionPolicy Bypass -Command"
if not exist logs mkdir logs
set "LOG=%~dp0logs\morning.log"
call :log ===== MORNING start

echo ==============================================================
echo   WEINSTEIN COMMANDER - MORNING
echo ==============================================================

REM 0. Tailscale. The status query is time-limited (a wedged service can hang it) and
REM    the tray app is started whenever it is absent: in unattended mode the backend runs
REM    without it, but then there is no icon - which looks exactly like "not running".
call :log step 0 tailscale
if exist "C:\Program Files\Tailscale\tailscale.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0morning_tailscale.ps1"
    if errorlevel 3 (echo   [ok]    Tailscale connected - tray icon was missing, started it) else if errorlevel 2 (echo   [start] Tailscale was not connected - tray app started, now Running) else if errorlevel 1 (echo   [WARN]  Tailscale is NOT running - the phone cannot reach this PC. REMOTE_ADMIN_SETUP.bat option 1) else (echo   [ok]    Tailscale connected)
) else (
    echo   [skip]  Tailscale not installed
)

REM 1. TradingView with CDP. Only when :9222 does not answer - the launcher kills TV.
call :log step 1 tradingview
call :listening 9222
if %errorlevel%==0 (echo   [ok]    TradingView CDP :9222 already up) else (
    echo   [start] TradingView with CDP...
    call :log   starting tradingview
    call "LAUNCH_TRADINGVIEW_CDP.bat"
)

REM 2. Web Commander
call :log step 2 commander
call :listening 8501
if %errorlevel%==0 (echo   [ok]    Web Commander :8501 already up) else (
    echo   [start] Web Commander...
    call :log   starting commander
    start "Web Commander" cmd /c "LAUNCH_COMMANDER.bat"
)

REM 3. Alert reviewer (its own launcher checks ngrok on :4040 itself)
call :log step 3 reviewer
call :listening 8000
if %errorlevel%==0 (echo   [ok]    Alert reviewer :8000 already up) else (
    echo   [start] Alert reviewer + tunnel...
    call :log   starting reviewer
    start "S4 Alert Reviewer" cmd /c "START_ALERT_REVIEWER.bat"
)

REM 4. Banner (a pythonw process running reviewer_banner.py)
call :log step 4 banner
%PS% "if (Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*reviewer_banner.py*' }) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (echo   [ok]    Reviewer banner already up) else (
    echo   [start] Reviewer banner...
    call :log   starting banner
    call "REVIEWER_BANNER.bat"
)

REM 5. Portal
call :log step 5 portal
call :listening 8502
if %errorlevel%==0 (echo   [ok]    Commander Portal :8502 already up) else (
    echo   [start] Commander Portal...
    call :log   starting portal
    start "Commander Portal :8502" cmd /c "SERVE_PORTAL.bat"
)

REM 6. File Browser (127.0.0.1:8503, published to the tailnet as http://jaynuc:8503)
call :log step 6 filebrowser
call :listening 8503
if %errorlevel%==0 (echo   [ok]    File Browser :8503 already up) else (
    echo   [start] File Browser...
    call :log   starting filebrowser
    start "File Browser starter" /min cmd /c "START_FILEBROWSER.bat"
)

call :log ===== MORNING done
echo.
echo   Done. Now in TradingView: open the chart tabs (the reviewer needs its two).
echo   (After an S4 compile ONLY: AFTER_COMPILE.bat)
echo   This window closes in 8 seconds.
timeout /t 8 /nobreak >nul 2>&1
endlocal
exit /b 0

:listening
REM A port that accepts a connection on 127.0.0.1 or ::1 is up; nothing else counts.
powershell -NoProfile -Command "foreach ($h in '127.0.0.1','::1') { $c = New-Object Net.Sockets.TcpClient; try { if ($c.ConnectAsync($h, %1).Wait(800) -and $c.Connected) { $c.Close(); exit 0 } } catch {}; $c.Close() }; exit 1"
exit /b %errorlevel%

:log
>>"%LOG%" echo %date% %time% %*
exit /b 0
