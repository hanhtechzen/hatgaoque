# Register a daily run (default 07:00). Usage:
#   powershell -ExecutionPolicy Bypass -File register_task.ps1 [-At 07:00]
param([string]$At = "07:00")

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$action = New-ScheduledTaskAction -Execute "$dir\run_daily.bat" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "HoaiNiemStudio" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Hoai Niem Studio - daily nostalgia video" -Force | Out-Null
Write-Host "OK: HoaiNiemStudio will run every day at $At (see Task Scheduler)."
Write-Host "Remove: Unregister-ScheduledTask -TaskName HoaiNiemStudio -Confirm:`$false"
