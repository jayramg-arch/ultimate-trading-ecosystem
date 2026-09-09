@echo off
title RRG Studio — Strike.Money Cockpit
cd /d "%~dp0\.."

echo =======================================================
echo          RRG STUDIO — RELATIVE ROTATION COCKPIT
echo =======================================================
echo.

:: Check if Streamlit is already running on port 8502
netstat -ano | findstr :8502 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] RRG Studio Server is already active on port 8502.
) else (
    echo [*] Launching RRG Studio background server...
    start "" /min python -m streamlit run rrg_studio/app.py --server.port=8502 --server.headless=true
    timeout /t 3 /nobreak >nul
)

echo [*] Opening RRG Studio in Default Browser...
start http://localhost:8502
exit
