# Register the Discord wake/sleep watcher as a logon Scheduled Task (Windows).
# Idempotent: re-registering replaces the old task. Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File setup/install_watcher.ps1
# Prereqs:
#   - Hermes venv python at the default location (override with -PythonExe)
#   - DISCORD_BOT_TOKEN in $env:HERMES_HOME\.env
param(
  [string]$PythonExe = "C:\Program Files\Hermes\hermes-agent\venv\Scripts\pythonw.exe",
  [string]$WatcherPy = "$PSScriptRoot\..\watcher\discord_watcher.py",
  [string]$TaskName  = "HermesDiscordWatcher"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
  # common Hermes layouts
  $candidates = @(
    "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\pythonw.exe",
    "$env:USERPROFILE\.hermes\venv\Scripts\pythonw.exe"
  )
  $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $found) { throw "pythonw.exe not found; pass -PythonExe explicitly" }
  $PythonExe = $found
}
$WatcherPy = (Resolve-Path $WatcherPy).Path

$action   = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$WatcherPy`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 `
             -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8

$state = (Get-ScheduledTask -TaskName $TaskName).State
Write-Host "Task '$TaskName' registered and started (state: $state)."
Write-Host "Watcher log: $env:HERMES_HOME\logs\discord_watcher.log"
Write-Host "In Discord: @<yourbot> wake | sleep | status"
