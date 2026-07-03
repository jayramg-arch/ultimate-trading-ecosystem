@echo off
TITLE Golden Matcher - Single Stock Dashboard
SETLOCAL EnableDelayedExpansion

:: 1. Define Paths
SET "ROOT_DIR=%~dp0"
SET "VENV_DIR=C:\Users\jayra\TradingData\venv"
SET "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
SET "APP_SCRIPT=%ROOT_DIR%golden_matcher_dashboard.py"

:: 2. Check Prerequisites
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

:: 3. Unicode fix - emoji / Rs symbol render correctly on Windows
SET "PYTHONIOENCODING=utf-8"
SET "PYTHONUTF8=1"

:: 4. Launch via "python -m streamlit" (bypasses the relocated streamlit.exe shim)
::    Port 8510 (8501-8504 are in use by other apps/instances)
echo Launching Golden Matcher dashboard...
start "Golden Matcher" /B "%PYTHON_EXE%" -m streamlit run "%APP_SCRIPT%" --server.port=8510 --server.headless=false

echo Server starting - browser will open shortly.
echo (Keep this window open to keep the dashboard running.)
timeout /t 3 >nul
pause
