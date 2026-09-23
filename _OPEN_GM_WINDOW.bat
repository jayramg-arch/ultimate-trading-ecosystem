@echo off
REM ===========================================================================
REM  _OPEN_GM_WINDOW.bat  -  (22-Sep-2026)
REM
REM  Opens the Golden Matcher as a TAB in the Chrome window already open, on
REM  the Trigger Board - beside the Commander tab Streamlit opens itself.
REM  Spawned in the background by the Commander launchers BEFORE Streamlit takes
REM  the console, so it has to wait for the server to answer first.
REM
REM  Called as:  _OPEN_GM_WINDOW.bat [port]      (default 8501)
REM
REM  Why a separate file: LAUNCH_COMMANDER.bat runs Streamlit in the FOREGROUND
REM  (deliberately - see the note there about Ctrl+C orphaning the server), so
REM  the launcher has no line of execution left after the server is up. This
REM  polls from a detached window instead.
REM
REM  ?view=gm_window = the existing GM pop-out route: sidebar hidden, the
REM  Single Symbol <-> Trigger Board switch still live. The board is only the
REM  DEFAULT (seeded on a fresh session in weinstein_commander_web_v4.0.py),
REM  so switching to Single Symbol inside the window sticks.
REM ===========================================================================
setlocal
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8501"
set "URL=http://localhost:%PORT%/?view=gm_window"

REM `ping -n N 127.0.0.1` is the sleep, not `timeout` - timeout aborts with
REM "Input redirection is not supported" whenever stdin is not a console, which
REM is exactly how a spawned/scripted launch runs it.
REM Wait up to ~60s for Streamlit to bind the port. It usually takes 3-8s cold.
set /a TRIES=0
:wait
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 goto up
set /a TRIES+=1
if %TRIES% GEQ 60 (
    echo   [gm-window] :%PORT% never came up - open %URL% yourself.
    ping -n 6 127.0.0.1 >nul
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait

:up
REM The port is bound a moment before the app can actually serve a page; without
REM this the new tab lands on a connection error and has to be reloaded.
ping -n 4 127.0.0.1 >nul

REM A TAB in the Chrome window that is already open, beside the Commander tab
REM Streamlit opened - NOT a separate window (22-Sep, Jay). Chrome with a bare
REM URL and no --new-window hands the URL to the running instance, which opens
REM it as a tab in the current window. Calling chrome.exe by path rather than
REM `start "" <url>` keeps it in Chrome even if some other browser is registered
REM as the default handler.
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
    start "" "%CHROME%" "%URL%"
) else (
    REM No Chrome - hand it to the default browser, which also reuses its
    REM existing window as a tab.
    start "" "%URL%"
)
endlocal
exit /b 0
