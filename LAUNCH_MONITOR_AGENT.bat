@echo off
TITLE Weinstein Commander - Market Monitor Agent
SETLOCAL EnableDelayedExpansion

:: 1. Define Paths
SET "ROOT_DIR=%~dp0"
SET "VENV_DIR=C:\Users\jayra\TradingData\venv"
SET "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
SET "AGENT_SCRIPT=%ROOT_DIR%market_monitor_agent.py"

:: 2. Check Prerequisites
IF NOT EXIST "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found at %VENV_DIR%
    pause
    exit /b 1
)

IF NOT EXIST "%AGENT_SCRIPT%" (
    echo [ERROR] Agent script not found at %AGENT_SCRIPT%
    pause
    exit /b 1
)

:: 3. Unicode fix – ensures emoji/₹ in modules render correctly on Windows
SET "PYTHONIOENCODING=utf-8"
SET "PYTHONUTF8=1"

:: 4. Launching
echo 🤖 INITIALIZING MARKET MONITOR AGENT...
echo 📡 Connecting to Scanners and Telegram Sentinel...
echo.

:: Run the agent script
"%PYTHON_EXE%" "%AGENT_SCRIPT%"

echo.
echo 🛑 Agent has terminated.
pause
