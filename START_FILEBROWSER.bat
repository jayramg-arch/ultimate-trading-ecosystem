@echo off
REM ===========================================================================
REM START_FILEBROWSER.bat  (10-Oct-2026)
REM Web file manager for the tablet / phone - Tailscale only.
REM   File Browser v2.63.23 in C:\Users\jayra\RemoteAccess\filebrowser
REM   listens on 127.0.0.1:8503 ONLY (never the LAN or the internet)
REM   Tailscale publishes it to your own devices:  http://jaynuc:8503
REM   Root = C:\Users\jayra\RemoteAccess\share  (junctions to GeminiVSCode,
REM   Documents, Downloads, Desktop, TradingData). Command execution is OFF.
REM   First login: C:\Users\jayra\RemoteAccess\config\INITIAL_LOGIN.txt
REM Idempotent: does nothing if it is already running. MORNING.bat calls it.
REM WARNING: the File Browser project was ARCHIVED on 2026-09-01 - no more security
REM fixes. Unfixed in v2.63.23 incl. 'upload failure-cleanup recursively deletes
REM directories'. Jay chose full access anyway (10-Oct-2026); a failed upload can
REM delete folders under the share. Keep it Tailscale-only.
REM ===========================================================================
set "RA=C:\Users\jayra\RemoteAccess"
set "TS=C:\Program Files\Tailscale\tailscale.exe"

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8503 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo Starting File Browser on 127.0.0.1:8503 ...
  REM 12-Oct-2026: the root is now C:\Users\jayra with per-user ALLOW rules (Documents,
  REM Downloads, TradingData, OneDrive\Desktop; everything else denied) - set in the
  REM database, see "filebrowser rules ls -u jay". The old RemoteAccess\share folder of
  REM JUNCTIONS never worked: Go 1.23+ reports a junction as an irregular file ("Incorrect
  REM function", 500), and as a link this version hides anything outside its root.
  REM GODEBUG=winsymlink=0 is kept so any junction inside the allowed folders still reads.
  set "GODEBUG=winsymlink=0"
  start "File Browser :8503" /min "%RA%\filebrowser\filebrowser.exe" -d "%RA%\config\filebrowser.db" -l "%RA%\logs\filebrowser.log"
) else (
  echo File Browser already running on :8503
)

REM Publish to the tailnet (WireGuard-encrypted; plain http is fine inside it).
REM The setting persists across restarts; re-running it is harmless.
"%TS%" serve --bg --http=8503 http://127.0.0.1:8503
if errorlevel 1 (
  echo.
  echo  Tailscale did not accept the publish step. Either Tailscale is not
  echo  connected yet ^(run REMOTE_ADMIN_SETUP.bat option 1 or 2^) or it needs
  echo  admin rights: REMOTE_ADMIN_SETUP.bat option 5 does it as admin.
)
