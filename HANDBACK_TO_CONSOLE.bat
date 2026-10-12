@echo off
REM ===========================================================================
REM  HANDBACK_TO_CONSOLE - end a Remote Desktop visit WITHOUT leaving the desk
REM  headless  (12-Oct-2026)
REM
REM  Run this from the phone/tablet INSTEAD of pressing Disconnect. It hands
REM  your session back to the PC's own screen: the Remote Desktop window on the
REM  phone closes, and the desk keeps a real display attached, exactly as if you
REM  had been sitting at it. TradingView, Commander, the alert receiver and the
REM  banner carry on drawing and running.
REM
REM  Why: a plain Disconnect leaves the session with NO display attached. Some
REM  apps stop drawing then, and the reviewer drives TradingView, so a headless
REM  desk is the one state worth avoiding during market hours.
REM
REM  Trade-off: the PC is left UNLOCKED on its own screen (that is what keeps a
REM  display attached). Anyone at the PC can use it until you lock it.
REM
REM  Needs administrator rights (Windows rule for tscon), so it asks once (UAC).
REM  Run at the PC itself it does nothing.
REM ===========================================================================
REM Ask Windows which session this is ("query session" marks the current one with >).
REM Not %SESSIONNAME%: that is frozen when a program starts, so Explorer launched at
REM the PC still says Console after you reconnect from the phone.
powershell -NoProfile -Command "if ((query session | Select-String '^>') -match '^>console') { exit 0 } else { exit 1 }"
if not errorlevel 1 (
    echo   You are already on the PC's own screen - nothing to hand back.
    ping -n 4 127.0.0.1 >nul
    exit /b 0
)

REM Elevate (tscon to the console needs admin). The elevated copy re-runs this file.
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

REM This process's own session id = the session to hand back.
for /f %%i in ('powershell -NoProfile -Command "(Get-Process -Id $PID).SessionId"') do set "SID=%%i"
if "%SID%"=="" (
    echo   Could not read the session id - nothing changed.
    pause
    exit /b 1
)
echo   Handing session %SID% back to the PC screen...
"%windir%\System32\tscon.exe" %SID% /dest:console
if errorlevel 1 (
    echo   tscon refused - the session is still on Remote Desktop.
    pause
    exit /b 1
)
exit /b 0
