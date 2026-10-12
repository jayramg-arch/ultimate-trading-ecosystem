@echo off
REM ===========================================================================
REM  RESET_FILEBROWSER_PASSWORD - set the File Browser password for user "jay"
REM  (12-Oct-2026)
REM
REM  For when the web form refuses the current password. This does not need the
REM  old one: it writes the new password straight into File Browser's database.
REM  You type it twice; the typing is hidden and it is never written to a file.
REM
REM  File Browser has to be stopped while its database is changed, so this stops
REM  it, sets the password, and starts it again via START_FILEBROWSER.bat.
REM  Signed-in sessions (e.g. on the phone) will need to sign in again.
REM ===========================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$fb='C:\Users\jayra\RemoteAccess\filebrowser\filebrowser.exe'; $db='C:\Users\jayra\RemoteAccess\config\filebrowser.db';" ^
  "$a=Read-Host 'New File Browser password for jay (12+ characters)' -AsSecureString; $b=Read-Host 'Type it again' -AsSecureString;" ^
  "$p1=[Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($a));" ^
  "$p2=[Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($b));" ^
  "if ($p1 -ne $p2) { Write-Host '  The two entries differ - nothing changed.' -ForegroundColor Red; exit 1 };" ^
  "if ($p1.Length -lt 12) { Write-Host '  Too short (12+ characters) - nothing changed.' -ForegroundColor Red; exit 1 };" ^
  "Stop-Process -Name filebrowser -Force -ErrorAction SilentlyContinue; Start-Sleep 1;" ^
  "& $fb -d $db users update jay -p $p1 2>&1 | Out-Null;" ^
  "if ($LASTEXITCODE -ne 0) { Write-Host '  File Browser refused the change - the old password still works.' -ForegroundColor Red; exit 2 };" ^
  "Write-Host '  Password changed.' -ForegroundColor Green; exit 0"
REM 1 = nothing touched (File Browser still running) · 2 = stopped but not changed (restart it)
if errorlevel 2 (call "%~dp0START_FILEBROWSER.bat" & goto :done)
if errorlevel 1 goto :done
call "%~dp0START_FILEBROWSER.bat"
echo.
echo   Sign in on the phone with the NEW password, then delete
echo   C:\Users\jayra\RemoteAccess\config\INITIAL_LOGIN.txt
:done
echo.
pause
endlocal
