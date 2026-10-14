@echo off
REM ===========================================================================
REM  FIX_WEBHOOK.bat  (14-Oct-2026)
REM
REM  Run this when a TradingView alert reads "Webhook delivery failed - 404 not
REM  found" (or 502). It checks the alert path in three places, repairs only the
REM  piece that is down, and confirms from the PUBLIC side, the way TradingView
REM  sees it:
REM    LOCAL   receiver  http://127.0.0.1:8000/health   (dhan_tv_webhook.py)
REM    AGENT   ngrok     http://127.0.0.1:4040          (local agent API)
REM    PUBLIC  tunnel    https://<NGROK_DOMAIN>/health  (what TradingView calls)
REM
REM  Repairs:
REM    receiver down          -> stop any looping receiver window, start a fresh one
REM    tunnel offline / no ngrok -> restart ngrok on the static domain
REM  A healthy receiver is never restarted (it would kill a review in progress).
REM  If the PC woke from sleep/hibernate recently, it says so: that was the cause,
REM  and alerts sent while it slept are lost (TradingView never retries).
REM  It never places or changes an order.
REM ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Fix webhook (S4 alert path)
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
set "NGROK=%LOCALAPPDATA%\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
if not exist "%NGROK%" set "NGROK=ngrok"
set PYTHONIOENCODING=utf-8

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="NGROK_DOMAIN" set "NGROK_DOMAIN=%%B"
)
set "NGROK_DOMAIN=%NGROK_DOMAIN:https://=%"
if "%NGROK_DOMAIN%"=="" (
    echo   [X] NGROK_DOMAIN missing from .env - cannot check the public side.
    pause & exit /b 1
)

echo ==============================================================
echo   FIX WEBHOOK  -  S4 alert path
echo ==============================================================

REM --- 0. Did the PC just wake? (sleep/hibernate = the usual cause) ---------
for /f "usebackq delims=" %%W in (`powershell -NoProfile -Command "$e=Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Power-Troubleshooter';Id=1} -MaxEvents 1 -ErrorAction SilentlyContinue; if($e){$m=[int]((Get-Date)-$e.TimeCreated).TotalMinutes; '{0:dd-MMM HH:mm}|{1}' -f $e.TimeCreated,$m}"`) do set "WAKE=%%W"
set "WAKE_AT=" & set "WAKE_MIN=99999"
if defined WAKE for /f "tokens=1,2 delims=|" %%a in ("%WAKE%") do (set "WAKE_AT=%%a" & set "WAKE_MIN=%%b")
set "SLEPT=0"
if defined WAKE_AT if !WAKE_MIN! LSS 90 set "SLEPT=1"
if "%SLEPT%"=="1" (
    echo   [i]  The PC woke from sleep/hibernate at %WAKE_AT% ^(!WAKE_MIN! min ago^).
    echo        Most likely the cause: alerts sent while it slept got 404 and are lost.
    echo        Best fix: close this and click MORNING ^(brings everything up^).
    echo        Continuing anyway - repairing only the alert path.
    echo.
)

REM --- 1. Diagnose ----------------------------------------------------------
call :probe
echo   receiver :8000   : %LOCAL%
echo   ngrok agent :4040: %AGENT%
echo   public /health   : %PUB%   ^(https://%NGROK_DOMAIN%^)
echo.

if "%PUB%"=="200" if "%LOCAL%"=="200" (
    echo   [ok] The path is healthy NOW. The 404 happened while it was down.
    goto :recover
)

REM --- 2. Receiver -----------------------------------------------------------
if not "%LOCAL%"=="200" (
    echo   [fix] Receiver is down - stopping any stale receiver and starting a fresh one...
    taskkill /fi "WINDOWTITLE eq S4 webhook receiver :8000*" /t /f >nul 2>&1
    powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*dhan_tv_webhook.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
    timeout /t 2 /nobreak >nul
    start "S4 webhook receiver :8000" cmd /k "for /l %%i in () do ("%PY%" dhan_tv_webhook.py & echo. & echo [receiver exited - restarting in 10 s; close this window to stop] & timeout /t 10 /nobreak >nul)"
    call :waitlocal
)

REM --- 3. Tunnel -------------------------------------------------------------
call :probe
if not "%PUB%"=="200" (
    echo   [fix] Tunnel not answering ^(%PUB%^) - restarting ngrok on %NGROK_DOMAIN%...
    taskkill /im ngrok.exe /t /f >nul 2>&1
    taskkill /fi "WINDOWTITLE eq ngrok tunnel*" /t /f >nul 2>&1
    timeout /t 3 /nobreak >nul
    start "ngrok tunnel" cmd /k ""%NGROK%" http --url=%NGROK_DOMAIN% 8000"
)

REM --- 4. Confirm from the public side (up to ~60 s) ------------------------
set /a N=0
:confirm
call :probe
if "%PUB%"=="200" if "%LOCAL%"=="200" goto :fixed
set /a N+=1
if %N% GEQ 12 goto :failed
timeout /t 5 /nobreak >nul
goto :confirm

:fixed
echo.
echo   [ok] FIXED - receiver %LOCAL%, public tunnel %PUB%. Alerts will reach the reviewer again.
goto :recover

:failed
echo.
echo   [X] Still not healthy: receiver %LOCAL%, agent %AGENT%, public %PUB%.
echo       - public 000 / no answer : internet down, or ngrok refused the session
echo         ^(look at the "ngrok tunnel" window for the error^)
echo       - receiver not 200        : look at the "S4 webhook receiver :8000" window
echo       Last resort: click MORNING.
goto :end

:recover
echo.
echo   Next: open TradingView's Alerts Log, note the GO alerts that fired while it
echo   was down, and for each name whose setup still stands run:
echo       REVIEW SYMBOL 75      ^(or 125 / D - the alert's timeframe^)
echo   Close any extra receiver window that repeats "PORT 8000: ALREADY IN USE".
goto :end

:probe
set "LOCAL=000" & set "PUB=000" & set "AGENT=down"
for /f %%c in ('curl -s -o NUL -m 4 -w "%%{http_code}" http://127.0.0.1:8000/health 2^>nul') do set "LOCAL=%%c"
for /f %%c in ('curl -s -o NUL -m 8 -w "%%{http_code}" https://%NGROK_DOMAIN%/health 2^>nul') do set "PUB=%%c"
curl -s -m 3 http://127.0.0.1:4040/api/tunnels >nul 2>&1 && set "AGENT=up"
exit /b 0

:waitlocal
for /l %%k in (1,1,15) do (
    for /f %%c in ('curl -s -o NUL -m 3 -w "%%{http_code}" http://127.0.0.1:8000/health 2^>nul') do if "%%c"=="200" exit /b 0
    timeout /t 2 /nobreak >nul
)
exit /b 0

:end
echo.
pause
endlocal
