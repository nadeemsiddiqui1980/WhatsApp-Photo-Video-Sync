param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
    [string]$TaskName = "PhotoSyncPipeline"
)

$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $ProjectRoot "scripts\run_pipeline.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Photo Sync Pipeline auto-start" -Force
Write-Host "Scheduled task '$TaskName' registered."
