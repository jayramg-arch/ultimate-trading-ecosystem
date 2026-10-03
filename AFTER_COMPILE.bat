@echo off
REM ===================================================================
REM  AFTER COMPILE  -  run once after EVERY S4 compile (pin to the taskbar).
REM
REM  1. BIND    re-binds S4's 32 v67/Zigzag sources on EVERY S4 tab, waits,
REM             re-checks, re-binds any tab that slipped, prints OK/FAIL.
REM  2. BUNDLES pushes today's GM bundles (and the location setting) into S4
REM             on every tab - a compile can reset the input strings.
REM  3. ALERTS  moves both S4 GO alerts to the version just compiled (an alert
REM             keeps the version it was created on) and refreshes their list
REM             and bundles. If a compile DELETED the alerts, this says so:
REM             create the 75m and 125m alerts once by hand, on GM_Swing.
REM
REM  Keep all five TradingView tabs open. Needs TradingView started with the
REM  debug port (LAUNCH_TRADINGVIEW_CDP.bat / MORNING.bat).
REM  Order of work when S4Core changed: publish S4Core -> import bumped ->
REM  compile S4 -> THIS.
REM ===================================================================
title After S4 compile
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
cd /d "%PROJ%" || (echo [X] Project folder not found & goto :hold)

echo.
echo  ===== 1/3  BIND S4 SOURCES =====
"%PY%" tv_bind_s4.py
set "R1=%ERRORLEVEL%"

echo.
echo  ===== 2/3  PUSH BUNDLES =====
"%PY%" tv_push_bundles.py
set "R2=%ERRORLEVEL%"

echo.
echo  ===== 3/3  ALERTS (version + list + bundles) =====
"%PY%" tv_gm_alerts.py --upgrade-version
set "R3=%ERRORLEVEL%"

echo.
echo  ===== SUMMARY =====
if "%R1%"=="0" (echo   [OK] bindings) else (echo   [!!] bindings - read step 1; click into any FAIL tab, then run again)
if "%R2%"=="0" (echo   [OK] bundles) else (echo   [!!] bundles - read step 2)
if "%R3%"=="0" (echo   [OK] alerts) else (echo   [!!] alerts - read step 3; if none were found, create the 75m and 125m S4 GO alerts by hand on GM_Swing, then run this again)

:hold
echo.
pause
