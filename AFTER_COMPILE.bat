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
REM  4. DAILY   rebuilds the per-stock Daily "GM-POS GO <SYM>" alerts on the
REM             version just compiled. They are cloned from the 75m alert, so
REM             this runs after step 3 (the nightly Phase 12b3 does the same).
REM  5. V67     pushes Risk Shield's Chandelier (window, multiplier, floor)
REM             into v67 on every tab, so v67's line equals Risk Shield.
REM  6. ADD-ONS pushes the v2 status line (M2).
REM
REM  Keep all six TradingView tabs open (incl. Panel Layout). Needs TradingView started with the
REM  debug port (LAUNCH_TRADINGVIEW_CDP.bat / MORNING.bat).
REM  Order of work when S4Core changed: publish S4Core -> import bumped ->
REM  compile S4 -> THIS.
REM ===================================================================
title After S4 compile
set "PROJ=C:\Users\jayra\Documents\GeminiVSCode"
set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
cd /d "%PROJ%" || (echo [X] Project folder not found & goto :hold)

echo.
echo  ===== 1/6  BIND S4 SOURCES =====
"%PY%" tv_bind_s4.py
set "R1=%ERRORLEVEL%"

echo.
echo  ===== 2/6  PUSH BUNDLES =====
"%PY%" tv_push_bundles.py
set "R2=%ERRORLEVEL%"

echo.
echo  ===== 3/6  ALERTS (version + list + bundles) =====
"%PY%" tv_gm_alerts.py --upgrade-version
set "R3=%ERRORLEVEL%"

echo.
echo  ===== 4/6  DAILY GM-POS GO ALERTS (one per positional name) =====
"%PY%" tv_pos_alerts.py
set "R6=%ERRORLEVEL%"

echo.
echo  ===== 5/6  V67: settings restore + portfolio slots + Chandelier book =====
"%PY%" tv_push_v67_trail.py --restore
set "R4=%ERRORLEVEL%"

echo.
echo  ===== 6/6  ADD-ONS: v2 status line (M2) =====
"%PY%" tv_push_addons.py
set "R5=%ERRORLEVEL%"

echo.
echo  ===== SUMMARY =====
if "%R1%"=="0" (echo   [OK] bindings) else (echo   [!!] bindings - read step 1; click into any FAIL tab, then run again)
if "%R2%"=="0" (echo   [OK] bundles) else (echo   [!!] bundles - read step 2)
if "%R4%"=="0" (echo   [OK] v67 trail book) else (echo   [!!] v67 trail book - read step 5; compile v67.4.26 if the input was not found)
if "%R5%"=="0" (echo   [OK] Add-ons v2 status) else (echo   [!!] Add-ons v2 status - step 6; compile Add-ons v1.1 if the M2 input was not found)
if "%R6%"=="0" (echo   [OK] Daily GM-POS GO alerts) else (echo   [!!] Daily GM-POS GO alerts - read step 4; it needs the 75m S4 GO alert from step 3 as its template)
if "%R3%"=="0" (echo   [OK] alerts) else (echo   [!!] alerts - read step 3; if none were found, create the 75m and 125m S4 GO alerts by hand on GM_Swing, then run this again)

:hold
echo.
pause
