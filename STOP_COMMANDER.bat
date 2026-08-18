@echo off
REM ---------------------------------------------------------------------------
REM  STOP_COMMANDER.bat - free port 8501 and clear orphaned Web Commander procs
REM
REM  Why this exists: `python -m streamlit run` forks a CHILD that does the
REM  actual serving. Ctrl+C in the console hits the launcher; the child keeps
REM  the port, so the next launch either fails or you end up talking to the OLD
REM  code (which is how a "restart" silently changes nothing).
REM
REM  Scope is deliberate: port 8501 + command lines matching
REM  weinstein_commander only. RRG Studio (8502) and every other python are
REM  left alone.
REM ---------------------------------------------------------------------------
setlocal
echo.
echo   Stopping Weinstein Commander (port 8501)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$killed = @();" ^
  "$l = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue;" ^
  "foreach ($procId in ($l | Select-Object -Expand OwningProcess -Unique)) {" ^
  "  try { Stop-Process -Id $procId -Force -ErrorAction Stop; $killed += $procId;" ^
  "        Write-Host ('   killed ' + $procId + '  (held 8501)') -ForegroundColor Yellow }" ^
  "  catch { Write-Host ('   could not kill ' + $procId + ' : ' + $_.Exception.Message) -ForegroundColor Red } };" ^
  "$orph = Get-CimInstance Win32_Process -Filter \"Name like '%%python%%'\" |" ^
  "        Where-Object { $_.CommandLine -match 'weinstein_commander' -and $killed -notcontains $_.ProcessId };" ^
  "foreach ($o in $orph) {" ^
  "  try { Stop-Process -Id $o.ProcessId -Force -ErrorAction Stop;" ^
  "        Write-Host ('   killed ' + $o.ProcessId + '  (orphan, no port)') -ForegroundColor Yellow }" ^
  "  catch { Write-Host ('   could not kill ' + $o.ProcessId) -ForegroundColor Red } };" ^
  "Start-Sleep -Seconds 2;" ^
  "if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) {" ^
  "  Write-Host ''; Write-Host '   8501 STILL LISTENING - run this as Administrator' -ForegroundColor Red }" ^
  "else { Write-Host ''; Write-Host '   8501 free' -ForegroundColor Green };" ^
  "if (Get-NetTCPConnection -LocalPort 8502 -State Listen -ErrorAction SilentlyContinue) {" ^
  "  Write-Host '   8502 RRG Studio still up (untouched)' -ForegroundColor DarkGray }"

echo.
pause
