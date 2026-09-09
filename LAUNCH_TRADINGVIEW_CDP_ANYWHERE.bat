@echo off
TITLE TradingView Desktop (CDP debugging enabled)
SETLOCAL

:: ============================================================================
:: Runs from ANYWHERE - desktop, taskbar, Start menu.
::
:: The original LAUNCH_TRADINGVIEW_CDP.bat resolves the PowerShell script with
:: %~dp0, which means "the folder THIS .bat is in". Copy it to the desktop and it
:: looks for launch_tradingview_cdp.ps1 on the desktop and fails. `cd` does not
:: help - cd changes the working directory, not %~dp0. So the path is absolute
:: here, and only here: edit PROJECT_DIR if the project ever moves.
::
:: What the .ps1 does: TradingView Desktop is a Microsoft Store app, so launching
:: it normally opens it WITHOUT --remote-debugging-port and every TradingView MCP
:: call dies with "CDP connection failed ... fetch failed". The script resolves
:: the install path via Get-AppxPackage, kills any running instance, and relaunches
:: with the port open. Use THIS instead of the Store/taskbar icon.
:: ============================================================================

SET "PROJECT_DIR=C:\Users\jayra\Documents\GeminiVSCode"
SET "PS1=%PROJECT_DIR%\launch_tradingview_cdp.ps1"

IF NOT EXIST "%PS1%" (
    echo [ERROR] Launcher script not found:
    echo         %PS1%
    echo.
    echo         Edit PROJECT_DIR at the top of this file if the project moved.
    pause
    exit /b 1
)

:: -NoProfile so a slow or broken PowerShell profile cannot stall the launch.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*

:: The window stays open only if something went wrong; on success the script
:: reports the port and TradingView takes over.
IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Launch failed - see the message above.
    pause
)
