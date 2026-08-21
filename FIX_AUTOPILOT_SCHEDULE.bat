@echo off
REM ---------------------------------------------------------------------------
REM  FIX_AUTOPILOT_SCHEDULE.bat  -  move WeinsteinAutoPilot to 16:30 weekdays
REM
REM  The task was created to run at 08:00 ("Runs Weinstein Auto-Pilot at 8 AM
REM  IST on weekdays" is its own description) and was left Disabled. Jay asked
REM  on 21-Aug-2026 for 4:30 PM on all weekdays, which also matches the
REM  documented cadence and the TradingJournal_DhanSync task.
REM
REM  Sets: 16:30, Mon-Fri, StartWhenAvailable (catches up if the PC was off),
REM        runs on battery, 3-hour execution limit.
REM
REM  Needs ADMIN - Set-ScheduledTask is privileged. This script self-elevates.
REM  Duplicate runs are already safe: run_pipeline.py holds a PID lock
REM  (auto_pilot.lock) and aborts if another auto-pilot is live.
REM ---------------------------------------------------------------------------
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo   Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

echo.
echo   Setting WeinsteinAutoPilot to 16:30, Mon-Fri, catch-up enabled...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$py='C:\Users\jayra\TradingData\venv\Scripts\python.exe';" ^
  "$proj='C:\Users\jayra\Documents\GeminiVSCode';" ^
  "if(-not (Test-Path $py)){ Write-Host '  [ERROR] venv python not found:' $py -ForegroundColor Red; exit 1 };" ^
  "$a=New-ScheduledTaskAction -Execute $py -Argument ($proj+'\run_pipeline.py --batch') -WorkingDirectory $proj;" ^
  "$t=New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 16:30;" ^
  "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3);" ^
  "Set-ScheduledTask -TaskName 'WeinsteinAutoPilot' -Action $a -Trigger $t -Settings $s | Out-Null;" ^
  "$x=Get-ScheduledTask -TaskName 'WeinsteinAutoPilot';" ^
  "$x.Description='Runs Weinstein Auto-Pilot at 4:30 PM IST on weekdays (post-close).';" ^
  "Set-ScheduledTask -InputObject $x | Out-Null;" ^
  "Enable-ScheduledTask -TaskName 'WeinsteinAutoPilot' | Out-Null;" ^
  "$x=Get-ScheduledTask -TaskName 'WeinsteinAutoPilot';" ^
  "$i=Get-ScheduledTaskInfo -TaskName 'WeinsteinAutoPilot';" ^
  "Write-Host ('  State    : ' + $x.State) -ForegroundColor Green;" ^
  "$x.Triggers | ForEach-Object { Write-Host ('  Trigger  : ' + $_.StartBoundary + '   days=' + $_.DaysOfWeek) };" ^
  "Write-Host ('  Next run : ' + $i.NextRunTime) -ForegroundColor Green;" ^
  "Write-Host ('  Catch-up : ' + $x.Settings.StartWhenAvailable);" ^
  "Write-Host ('  Action   : ' + $x.Actions[0].Execute + ' ' + $x.Actions[0].Arguments)"

echo.
pause
