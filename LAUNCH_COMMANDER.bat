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

:: Start Streamlit in the background
:: We remove the hardcoded port 8501 to allow auto-fallback if another instance is running
echo 🚀 Launching Mission Control...
start "Commander Server" /B "%PYTHON_EXE%" -m streamlit run "%APP_SCRIPT%" --server.headless=false

echo ✅ Server initialization triggered. 
echo 🌐 Opening browser...
timeout /t 3 >nul

echo 🕵️  Monitoring for system shutdown...
echo (Keep this window open to maintain server connection)

:: Keep window alive
pause
