@echo off
REM ===========================================================================
REM  SCREENS_OFF.bat  (14-Oct-2026)
REM  Turns the monitors off and NOTHING else - the PC stays awake, so the alert
REM  receiver, ngrok, TradingView and the scheduled jobs keep running.
REM  (The sleep button / Hibernate put the PC to sleep and every alert in that
REM  window got a 404 - see Doc 26 §6c.)
REM  Any key or mouse move turns the screens back on.
REM  Waits 2 s first so the click that launched it does not wake them again.
REM ===========================================================================
timeout /t 2 /nobreak >nul
powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -Namespace W -Name U -MemberDefinition '[DllImport(\"user32.dll\")] public static extern int SendMessage(int h, int m, int w, int l);'; [W.U]::SendMessage(0xFFFF, 0x0112, 0xF170, 2) | Out-Null"
