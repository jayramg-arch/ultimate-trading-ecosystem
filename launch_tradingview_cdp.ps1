# ============================================================================
# launch_tradingview_cdp.ps1 - start TradingView Desktop with the Chrome
# DevTools Protocol (remote-debugging) port ENABLED, so the TradingView MCP /
# Claude can connect to it. Use THIS instead of the taskbar/Start-menu icon.
#
# Why: TradingView Desktop is a Microsoft Store (UWP/Electron) app. Launched the
# normal way it opens WITHOUT --remote-debugging-port, so CDP tools fail with
# "CDP connection failed ... fetch failed". This script resolves the install
# path via Get-AppxPackage (works without enumerating the ACL-locked
# WindowsApps folder, and survives version updates), kills any running
# instance, and relaunches it with the port open.
#
# NOTE: kept ASCII-only and try/catch-free so it parses under BOTH Windows
# PowerShell 5.1 (what the .bat uses) and PowerShell 7.
#
# Usage:   powershell -ExecutionPolicy Bypass -File launch_tradingview_cdp.ps1
#          (or just double-click LAUNCH_TRADINGVIEW_CDP.bat)
#          Optional: -Port 9222   (default; must match the MCP's CDP port)
# ============================================================================
param([int]$Port = 9222)

# Resolve TradingView Desktop via the AppX package model - NO folder enumeration
# (WindowsApps is ACL-locked for a normal-user PowerShell 5.1 process), and the
# version-stamped InstallLocation is returned for us so it survives updates.
$pkg = Get-AppxPackage -Name "*TradingView*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $pkg) {
    Write-Host "ERROR: TradingView Desktop AppX package not found. Is it installed from the Microsoft Store?"
    exit 1
}
$exe = Join-Path $pkg.InstallLocation "TradingView.exe"
if (-not (Test-Path $exe)) {
    Write-Host "ERROR: TradingView.exe not found at $exe"
    exit 1
}
Write-Host "TradingView exe: $exe"

# A normally-launched TradingView has NO CDP port - must restart it clean.
$running = Get-Process TradingView -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ("Stopping {0} running TradingView instance(s)..." -f $running.Count)
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 1000
}

# 18-Oct-2026: launch through WMI, NOT Start-Process. TradingView (Electron) attaches to
# its parent's console, so started from MORNING.bat it shared that window: the window
# could not close while TV ran ("MORNING hung"), and closing it would have killed TV.
# WMI cannot start the Store exe directly (access denied, rc 2), so WMI starts a WINDOWLESS
# PowerShell (conhost --headless) and that one starts TV: TV then attaches to an invisible
# console nobody can close by accident.
$inner = "Start-Process -FilePath '" + $exe + "' -ArgumentList '--remote-debugging-port=" + $Port + "'"
$cmd = 'conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "' + $inner + '"'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd } -ErrorAction SilentlyContinue
$up = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if (Get-Process TradingView -ErrorAction SilentlyContinue) { $up = $true; break }
}
if (-not $up) {
    Write-Host "Detached launch did not start TradingView - falling back to Start-Process (this window may then stay open while TV runs)."
    Start-Process -FilePath $exe -ArgumentList "--remote-debugging-port=$Port"
}
Start-Sleep -Milliseconds 2000

# Verify the port is actually listening (no try/catch - 5.1-safe)
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/json/version" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($resp -and $resp.StatusCode -eq 200) {
    Write-Host "OK - CDP is live on port $Port."
} else {
    Write-Host "Launched, but port $Port not answering yet - give TradingView a few seconds to finish loading, then retry the MCP health check."
}
Write-Host ""
Write-Host "You can close this window."
