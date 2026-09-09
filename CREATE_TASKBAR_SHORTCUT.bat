@echo off
title Create RRG Studio Taskbar Shortcut
cd /d "%~dp0"

echo =======================================================
echo     Creating RRG Studio Desktop & Taskbar Shortcut
echo =======================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_rrg_shortcut.ps1"

echo.
echo [INFO] You can now right-click the "RRG Studio" shortcut on your Desktop or in this folder and select "Pin to taskbar".
echo.
pause
