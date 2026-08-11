@echo off
TITLE Weinstein Commander - Mission Control
SETLOCAL EnableDelayedExpansion
:: Console to UTF-8 so the emoji below print as emoji, not as "≡ƒªü" mojibake. Cosmetic
:: only — but a launcher that looks broken invites you to go hunting for a fault.
chcp 65001 >nul

:: 1. Define Paths
SET "ROOT_DIR=%~dp0"
SET "VENV_DIR=C:\Users\jayra\TradingData\venv"
SET "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
:: NOTE: streamlit.exe is NOT used and must not be reintroduced. A console-script .exe
:: is a launcher stub with the interpreter path baked in AT CREATION TIME — this venv
:: was built under "E:\Gemini\VS Code\.venv", which no longer exists, so the shim dies
:: with "Unable to create process". The venv and streamlit itself are fine; only the
:: wrapper is stale. "python -m streamlit" resolves the interpreter at run time and is
:: immune to the venv being moved. (Same fix the Golden dashboard launcher used.)
SET "APP_SCRIPT=%ROOT_DIR%weinstein_commander_web_v4.0.py"

:: 2. Check Prerequisites
IF NOT EXIST "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found at %VENV_DIR%
    pause
    exit /b 1
)

IF NOT EXIST "%PYTHON_EXE%" (
    echo [ERROR] Python not found at %PYTHON_EXE%
    pause
    exit /b 1
)

IF NOT EXIST "%APP_SCRIPT%" (
    echo [ERROR] App script not found at %APP_SCRIPT%
    pause
    exit /b 1
)

:: 3. Unicode fix – ensures emoji/₹ in modules render correctly on Windows
SET "PYTHONIOENCODING=utf-8"
SET "PYTHONUTF8=1"

:: 3. Launching
echo 🦁 INITIALIZING WEINSTEIN COMMANDER...
echo 📡 Launching Mission Control UI...

:: ---- PRE-FLIGHT: undefined names on the live trading path -------------------
:: ~1s parse, no imports, no execution. Catches the class of bug that cost a
:: whole session on 11-Aug-2026: a name referenced inside a loop but defined
:: further down the file, swallowed by a batch except that reported it as
:: "Technicals fetch failed this run". py_compile cannot see these.
:: Exit 1 = real findings (offer to stop). Exit 2 = linter missing (carry on).
"%PYTHON_EXE%" "%ROOT_DIR%preflight.py"
IF ERRORLEVEL 2 GOTO :preflight_done
IF ERRORLEVEL 1 (
    echo   Launch anyway? Ctrl+C to stop and fix, or
    pause
)
:preflight_done

:: Start Streamlit in the background
:: We remove the hardcoded port 8501 to allow auto-fallback if another instance is running
echo 🚀 Launching Mission Control...
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
