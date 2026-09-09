$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$WorkspacePath = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $WorkspacePath) { $WorkspacePath = (Get-Location).Path }

$ExePath = Join-Path $WorkspacePath "RRG_Studio.exe"
$IconPath = Join-Path $WorkspacePath "rrg_icon.ico"

# 1. Desktop Shortcut pointing directly to native RRG_Studio.exe
$DesktopShortcutPath = Join-Path $DesktopPath "RRG Studio.lnk"
$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $WorkspacePath
$Shortcut.Description = "RRG Studio - Sector Rotation Cockpit"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
}
$Shortcut.Save()
Write-Host "[SUCCESS] Created Desktop Shortcut at: $DesktopShortcutPath" -ForegroundColor Green

# 2. Workspace Shortcut
$WorkspaceShortcutPath = Join-Path $WorkspacePath "RRG Studio.lnk"
$LocalShortcut = $WshShell.CreateShortcut($WorkspaceShortcutPath)
$LocalShortcut.TargetPath = $ExePath
$LocalShortcut.WorkingDirectory = $WorkspacePath
$LocalShortcut.Description = "RRG Studio - Sector Rotation Cockpit"
if (Test-Path $IconPath) {
    $LocalShortcut.IconLocation = "$IconPath,0"
}
$LocalShortcut.Save()
Write-Host "[SUCCESS] Created Workspace Shortcut at: $WorkspaceShortcutPath" -ForegroundColor Green
