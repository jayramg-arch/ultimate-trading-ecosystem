@echo off
TITLE Weinstein Commander - Mission Control
SETLOCAL EnableDelayedExpansion

:: 1. Define Paths
SET "ROOT_DIR=%~dp0"
SET "VENV_DIR=%ROOT_DIR%.venv"
SET "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
SET "STREAMLIT_EXE=%VENV_DIR%\Scripts\streamlit.exe"
SET "APP_SCRIPT=%ROOT_DIR%weinstein_commander_web.py"

:: 2. Check Prerequisites
IF NOT EXIST "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found at %VENV_DIR%
    pause
    exit /b 1
)

IF NOT EXIST "%APP_SCRIPT%" (
    echo [ERROR] App script not found at %APP_SCRIPT%
    pause
    exit /b 1
)

:: 3. Launching
echo 🦁 INITIALIZING WEINSTEIN COMMANDER...
echo 📡 Launching Mission Control UI...

:: Start Streamlit in the background
:: We remove the hardcoded port 8501 to allow auto-fallback if another instance is running
echo 🚀 Launching Mission Control...
start "Commander Server" /B "%STREAMLIT_EXE%" run "%APP_SCRIPT%" --server.headless=false

echo ✅ Server initialization triggered. 
echo 🌐 Opening browser...
timeout /t 3 >nul

echo 🕵️  Monitoring for system shutdown...
echo (Keep this window open to maintain server connection)

:: Keep window alive
pause
