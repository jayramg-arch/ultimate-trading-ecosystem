@echo off
REM ===========================================================================
REM REMOTE_ADMIN_SETUP.bat  (10-Oct-2026)
REM The admin-only steps for remote access from the tablet / phone over
REM Tailscale. Run it by right-click > "Run as administrator" (it re-launches
REM itself elevated if you just double-click it).
REM
REM   1  Restart Tailscale            - the first thing to try when `tailscale
REM                                     status` says NoState (wedged).
REM   2  Reset Tailscale state         - only if 1 did not help. Renames
REM                                     server-state.conf; you sign in again in
REM                                     the browser, the PC gets a NEW node and
REM                                     IP. Then delete the old node in the
REM                                     Tailscale admin console and rename the
REM                                     new one to "jaynuc" (20-Sep fix).
REM   3  Remote Desktop: Tailscale-only firewall
REM                                   - after you switch Remote Desktop ON in
REM                                     Settings > System > Remote Desktop.
REM                                     Limits port 3389 to Tailscale addresses
REM                                     (100.64.0.0/10), so nothing on the LAN or
REM                                     the internet can reach it.
REM   4  Status                        - Tailscale state + IP, Remote Desktop
REM                                     on/off, firewall scope.
REM ===========================================================================
net session >nul 2>&1
if errorlevel 1 (
  echo Asking for administrator rights...
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)
set "TS=C:\Program Files\Tailscale\tailscale.exe"

:menu
echo.
echo  ================= Remote access - admin steps =================
echo   1  Restart Tailscale
echo   2  Reset Tailscale state (re-login, new node)  - only if 1 fails
echo   3  Remote Desktop: allow Tailscale addresses only
echo   4  Status
echo   5  Publish File Browser to Tailscale (http://jaynuc:8503)
echo   Q  Quit
echo  ===============================================================
set "c="
set /p c=Choose:
if /i "%c%"=="1" goto restart
if /i "%c%"=="2" goto reset
if /i "%c%"=="3" goto rdp
if /i "%c%"=="4" goto status
if /i "%c%"=="5" goto serve
if /i "%c%"=="q" exit /b
goto menu

:restart
echo Restarting the Tailscale service...
powershell -NoProfile -Command "Restart-Service Tailscale -Force"
timeout /t 8 >nul
"%TS%" status
goto menu

:reset
echo This signs the PC out of Tailscale and creates a NEW node (new IP).
set "ok="
set /p ok=Type YES to continue:
if /i not "%ok%"=="YES" goto menu
powershell -NoProfile -Command "Stop-Service Tailscale -Force"
if exist "C:\ProgramData\Tailscale\server-state.conf" ren "C:\ProgramData\Tailscale\server-state.conf" "server-state.conf.bak_%RANDOM%"
powershell -NoProfile -Command "Start-Service Tailscale"
timeout /t 8 >nul
echo A browser window opens for the Tailscale sign-in...
"%TS%" up
"%TS%" status
echo.
echo Next: in the Tailscale admin console delete the OLD node and rename the
echo new one to "jaynuc", so http://jaynuc:8501 and :8502 keep working.
goto menu

:rdp
powershell -NoProfile -Command "if ((Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server').fDenyTSConnections -ne 0) { Write-Host 'Remote Desktop is OFF - switch it on in Settings > System > Remote Desktop first.'; exit 1 }; Set-NetFirewallRule -DisplayGroup 'Remote Desktop' -RemoteAddress 100.64.0.0/10; Get-NetFirewallRule -DisplayGroup 'Remote Desktop' | ? Enabled -eq True | Get-NetFirewallAddressFilter | select -Unique RemoteAddress | ft -auto"
goto menu

:serve
"%TS%" serve --bg --http=8503 http://127.0.0.1:8503
"%TS%" serve status
goto menu

:status
"%TS%" status
"%TS%" serve status
"%TS%" ip -4
powershell -NoProfile -Command "'Remote Desktop: ' + $(if ((Get-ItemProperty 'HKLM:\System\CurrentControlSet\Control\Terminal Server').fDenyTSConnections -eq 0) {'ON'} else {'OFF'}); Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue | ? Enabled -eq True | Get-NetFirewallAddressFilter | select -Unique RemoteAddress | ft -auto"
goto menu
