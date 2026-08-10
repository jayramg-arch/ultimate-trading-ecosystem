@echo off
REM ===================================================================
REM  BIND S4 SOURCES  -  pin this to the taskbar.
REM
REM  Run it immediately after EVERY S4 compile. TradingView drops all 18
REM  input.source bindings on every recompile (measured: a compile that
REM  changed no inputs at all left 0 of 18 alive), and an unbound panel
REM  silently reads `close` - the RS/RRG, Signal-Quality-RSI and Sector
REM  rows go blank or print "not bound" and you lose the Daily trend arrow.
REM
REM  Also run it after the "Calculation timed out - remove the indicator
REM  and reapply it" error: reapplying creates a NEW study instance with
REM  empty inputs, so that error costs you the bindings too.
REM
REM  Needs TradingView Desktop started via LAUNCH_TRADINGVIEW_CDP.bat
REM  (it must expose --remote-debugging-port=9222).
REM ===================================================================
title Bind S4 sources
cd /d "%~dp0"

set "PY=C:\Users\jayra\TradingData\venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [X] Python not found at %PY%
    goto :hold
)

echo.
echo  ---- BEFORE ----
"%PY%" tv_bind_s4.py --check
echo.
echo  ---- BINDING ----
"%PY%" tv_bind_s4.py
set "RC=%ERRORLEVEL%"
echo.

if "%RC%"=="0" (
    echo  [OK] All 18 sources bound.
) else if "%RC%"=="2" (
    echo  [X] Could not reach TradingView.
    echo      Start it with LAUNCH_TRADINGVIEW_CDP.bat, open a chart, then re-run.
) else (
    echo  [!] Finished with problems - read the report above.
    echo      "MISSING PLOT" means the v67 Dashboard or the Swing Zigzag is not on
    echo      this chart, or a plot was renamed. Both must be loaded: S4 reads THEIR
    echo      plots, so it cannot bind to something that is not there.
)

:hold
echo.
REM Foreground pause, never `start /B` - an orphaned window is how "I restarted
REM and it is still wrong" became ambiguous once already.
pause
