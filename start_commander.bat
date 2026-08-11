@echo off
title Weinstein Commander Dashboard
cd /d "C:\Users\jayra\Documents\GeminiVSCode"
echo ============================================================
echo   WEINSTEIN COMMANDER - Dashboard
echo ------------------------------------------------------------
echo   Starting Streamlit... your browser will open shortly.
echo   KEEP THIS WINDOW OPEN while you use the dashboard.
echo   Close this window (or press Ctrl+C) to STOP it cleanly.
echo ============================================================
echo.
:: Pre-flight: undefined names on the live trading path (see preflight.py).
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" preflight.py
IF ERRORLEVEL 2 GOTO :preflight_done
IF ERRORLEVEL 1 (
    echo   Launch anyway? Ctrl+C to stop and fix, or
    pause
)
:preflight_done
echo.
"C:\Users\jayra\TradingData\venv\Scripts\python.exe" -m streamlit run weinstein_commander_web_v4.0.py
echo.
echo Dashboard stopped. You can close this window.
pause
