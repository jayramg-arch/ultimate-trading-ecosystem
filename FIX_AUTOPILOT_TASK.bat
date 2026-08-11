@echo off
TITLE Repoint WeinsteinAutoPilot at the TradingData venv
chcp 65001 >nul

:: ============================================================================
:: The WeinsteinAutoPilot scheduled task runs:
::     Execute   : python                       <- PATH lookup = global 3.14
::     Arguments : ...\run_pipeline.py --batch
:: The app runs on C:\Users\jayra\TradingData\venv (3.13). Different
:: interpreter, different pandas, different installed packages - so a
:: scheduled auto-pilot would NOT be running the code you tested by hand.
::
:: The task was created with RunLevel=Highest, so editing it needs an elevated
:: shell. That is the ONLY reason this is a separate file. Run once; idempotent.
::
:: Uses PowerShell Set-ScheduledTask, NOT `schtasks /Change` - schtasks stops to
:: ask for the run-as password and then warns that an empty one may stop the
:: task running at all. Set-ScheduledTask leaves the credentials alone.
::
:: This does NOT enable the task. It is Disabled and staying that way - whether
:: the auto-pilot runs unattended at 08:00 is your decision, not a side effect
:: of fixing the interpreter.
:: Backup of the original task XML:
::   _archive\scheduled_tasks\WeinsteinAutoPilot_before_20260811.xml
:: ============================================================================

net session >nul 2>&1
IF NOT "%ERRORLEVEL%"=="0" (
    echo   Requesting administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$py='C:\Users\jayra\TradingData\venv\Scripts\python.exe';" ^
  "$proj='C:\Users\jayra\Documents\GeminiVSCode';" ^
  "if(-not (Test-Path $py)){ Write-Host '  [ERROR] venv python not found:' $py -ForegroundColor Red; Write-Host '  Nothing changed.'; exit 1 };" ^
  "$t=Get-ScheduledTask -TaskName 'WeinsteinAutoPilot' -ErrorAction Stop;" ^
  "Write-Host ''; Write-Host '  BEFORE : ' $t.Actions[0].Execute $t.Actions[0].Arguments;" ^
  "$a=New-ScheduledTaskAction -Execute $py -Argument ($proj+'\run_pipeline.py --batch') -WorkingDirectory $proj;" ^
  "Set-ScheduledTask -TaskName 'WeinsteinAutoPilot' -Action $a -ErrorAction Stop | Out-Null;" ^
  "$n=Get-ScheduledTask -TaskName 'WeinsteinAutoPilot';" ^
  "Write-Host '  AFTER  : ' $n.Actions[0].Execute $n.Actions[0].Arguments -ForegroundColor Green;" ^
  "Write-Host ('  STATE  :  ' + $n.State + '   (Disabled is deliberate)');" ^
  "Write-Host ''"

IF ERRORLEVEL 1 (
    echo.
    echo   [ERROR] The change did not apply - see the message above.
)
echo.
pause
