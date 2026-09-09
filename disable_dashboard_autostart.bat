@echo off
REM One-time fix: stop the dashboard from auto-launching (hidden/headless) at every
REM login. That background instance was the prime suspect for the memory-exhaustion
REM freezes. After this, launch the dashboard yourself with start_commander.bat.
REM RUN THIS AS ADMINISTRATOR: right-click this file -> "Run as administrator".
echo Disabling the 'Weinstein Commander Web' login auto-start task...
echo.
schtasks /Change /TN "Weinstein Commander Web" /DISABLE
echo.
if %errorlevel%==0 (
  echo SUCCESS - the dashboard will NO LONGER auto-start at login.
  echo Start it manually with start_commander.bat whenever you want it.
) else (
  echo FAILED ^(error %errorlevel%^).
  echo You must run this AS ADMINISTRATOR:
  echo    right-click disable_dashboard_autostart.bat  -^>  Run as administrator
)
echo.
pause
