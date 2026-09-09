@echo off
echo Closing TradingView if running...
taskkill /F /IM TradingView.exe 2>nul
timeout /t 2 /nobreak >nul
echo Launching TradingView with debug mode (port 9222)...
powershell -NoProfile -Command "$exe = (Get-AppxPackage | Where-Object { $_.PackageFamilyName -like '*n534cwy3pjxzj*' }).InstallLocation + '\TradingView.exe'; Start-Process $exe '--remote-debugging-port=9222'; Write-Host 'Launched. Wait 10 seconds before running send-trade-plan.js'"
pause
