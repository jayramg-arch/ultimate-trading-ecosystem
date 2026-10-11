# stop_commander.ps1 (11-Oct-2026) - stop every Web Commander server, then confirm :8501 is free.
#
# Used by STOP_COMMANDER.bat and, BEFORE launching, by LAUNCH_COMMANDER*.bat.
# Why the launchers need it: closing the Commander console does not always kill the
# server. `python -m streamlit` in the venv starts a second python (python3.13.exe) that
# does the serving, and that child can outlive the console. The next launch then found
# :8501 busy, skipped the Golden Matcher tab, and Streamlit quietly moved to another
# port - so only the dashboard tab opened.
#
# Kills only python processes whose command line names weinstein_commander, plus any
# such process listening on 8501. Something ELSE on 8501 is left alone and reported.
# Exit 0 = 8501 free.  Exit 1 = still held (by something we would not kill).
param([switch]$Quiet)

function Say($msg, $color = 'Gray') { if (-not $Quiet) { Write-Host $msg -ForegroundColor $color } }

$procs = Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
         Where-Object { $_.CommandLine -match 'weinstein_commander' }
foreach ($p in $procs) {
    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
          Say ("   stopped old Commander server " + $p.ProcessId) 'Yellow' }
    catch { Say ("   could not stop " + $p.ProcessId + " : " + $_.Exception.Message) 'Red' }
}

# Give Windows a moment to release the socket (up to ~10 s).
for ($i = 0; $i -lt 20; $i++) {
    $l = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
    if (-not $l) { Say '   8501 free' 'Green'; exit 0 }
    Start-Sleep -Milliseconds 500
}
$owner = ($l | Select-Object -Expand OwningProcess -Unique) -join ','
Say ("   8501 STILL held by pid " + $owner + " - not a Commander server, left alone") 'Red'
exit 1
