# morning_tailscale.ps1 - MORNING.bat step 0 (16-Oct-2026).
# Exit 0 = connected, 3 = connected but the tray icon was missing (started it),
# 2 = was not connected, tray started, now Running, 1 = not running after ~20 s.
# The status query runs in a job with a 10 s limit: a wedged service can hang it,
# and that is one way MORNING.bat appeared stuck.
$ts  = 'C:\Program Files\Tailscale\tailscale.exe'
$ipn = 'C:\Program Files\Tailscale\tailscale-ipn.exe'

function Get-TsState {
    $j = Start-Job -ScriptBlock { param($p) & $p status --json 2>$null } -ArgumentList $ts
    if (Wait-Job $j -Timeout 10) {
        $o = Receive-Job $j; Remove-Job $j -Force
        try { return (($o | Out-String) | ConvertFrom-Json).BackendState } catch { return 'unreadable' }
    }
    Remove-Job $j -Force
    return 'timeout'
}

$tray = [bool](Get-Process tailscale-ipn -ErrorAction SilentlyContinue)
# 18-Oct-2026: started through WMI so the tray app does not attach to MORNING's console
# (Start-Process left it attached and the MORNING window could not close).
if (-not $tray -and (Test-Path $ipn)) {
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = '"' + $ipn + '"' } -ErrorAction SilentlyContinue
    if (-not $r -or $r.ReturnValue -ne 0) { Start-Process $ipn }
}
$s = Get-TsState
if ($s -eq 'Running') { if ($tray) { exit 0 } else { exit 3 } }
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep 2
    $s = Get-TsState
    if ($s -eq 'Running') { exit 2 }
}
Write-Host ('          Tailscale state: ' + $s)
exit 1
