@echo off
TITLE Weinstein Commander - Mission Control
SETLOCAL EnableDelayedExpansion

:: ============================================================================
:: Runs from ANY location - desktop, taskbar, Start menu, anywhere.
::
:: WHY THE ORIGINAL FAILS OFF THE DESKTOP: LAUNCH_COMMANDER.bat builds its paths
:: from %~dp0, which is "the folder THIS .bat is sitting in". Copy that file to
:: the desktop and %~dp0 becomes the desktop, so it looks for the app there and
:: gives up. Adding "cd" does not fix it - cd changes the working directory, it
:: does not change %~dp0. This file hardcodes the project path instead.
::
:: The working directory still matters: the app opens FINAL_*.csv, gm_board_cache_*.csv
:: and logs\ by RELATIVE path, so we cd into the project before launching or it
:: comes up with an empty board and no watchlists.
:: ============================================================================

SET "PROJECT_DIR=C:\Users\jayra\Documents\GeminiVSCode"
SET "VENV_DIR=C:\Users\jayra\TradingData\venv"
SET "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
SET "APP_SCRIPT=%PROJECT_DIR%\weinstein_commander_web_v4.0.py"

:: UTF-8 console so the banner prints emoji instead of mojibake.
chcp 65001 >nul

:: ---- prerequisites, each named individually so a failure says WHICH one -----
IF NOT EXIST "%PROJECT_DIR%" (
    echo [ERROR] Project folder not found: %PROJECT_DIR%
    echo         Edit PROJECT_DIR at the top of this file if the project moved.
    pause & exit /b 1
)
IF NOT EXIST "%PYTHON_EXE%" (
    echo [ERROR] Python not found: %PYTHON_EXE%
    echo         The venv lives in TradingData, NOT in the project folder.
    pause & exit /b 1
)
IF NOT EXIST "%APP_SCRIPT%" (
    echo [ERROR] App script not found: %APP_SCRIPT%
    pause & exit /b 1
)

:: Relative paths inside the app resolve from here.
cd /d "%PROJECT_DIR%"

SET "PYTHONIOENCODING=utf-8"
SET "PYTHONUTF8=1"

echo.
echo   WEINSTEIN COMMANDER
echo   project : %PROJECT_DIR%
echo   python  : %PYTHON_EXE%
echo.
echo   Launching Mission Control...

:: NOTE: python -m streamlit, never streamlit.exe. The .exe is a launcher stub with
:: the interpreter path baked in at venv-creation time - this venv was built under
:: "E:\Gemini\VS Code\.venv", which no longer exists, so the shim dies with
:: "Unable to create process". -m resolves the interpreter at run time.
:: RUN IN THE FOREGROUND. This was:
::     start "Commander Server" /B "%PYTHON_EXE%" -m streamlit run ...
::     pause
:: `start /B` spawns Streamlit as a SEPARATE process and the batch then sits at
:: `pause`. Ctrl+C is delivered to the batch waiting on `pause`, so it kills the
:: BATCH and orphans the server — which keeps holding the port. That is why
:: Ctrl+C did not stop anything, and why a "restart" could silently leave the old
:: server serving the page you were looking at.
::
:: Foreground means the console owns the process: Ctrl+C reaches Streamlit, it
:: shuts down, the batch ends and the window closes. Streamlit on Windows
:: sometimes wants a second Ctrl+C — that is normal.
"%PYTHON_EXE%" -m streamlit run "%APP_SCRIPT%" --server.headless=false

:: Only hold the window open if it FAILED, so the error is readable. A clean
:: Ctrl+C exits quietly instead of demanding a keypress.
IF ERRORLEVEL 1 (
    echo.
    echo   [ERROR] Streamlit exited with an error - see the trace above.
    pause
)
