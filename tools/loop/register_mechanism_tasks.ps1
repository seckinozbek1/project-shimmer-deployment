# Registers the loop's standing mechanisms as per-user Windows scheduled tasks (no admin), each started
# hidden through pyw.exe (no console window), like ShimmerRecordsBackup. Supervisor batch 2026-11-18 12:30,
# items D and E. Re-running replaces the same tasks; it deletes no file.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\loop\register_mechanism_tasks.ps1
#
# ShimmerRecordsBackup keeps its trigger and settings; only its action is pointed at backup_guarded.py.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pyw = 'C:\WINDOWS\pyw.exe'
$user = "$env:USERDOMAIN\$env:USERNAME"

function New-LoopAction([string]$script, [string]$extra = '') {
    $a = "-3.12 -X utf8 `"$root\tools\loop\$script`""
    if ($extra) { $a = "$a $extra" }
    New-ScheduledTaskAction -Execute $pyw -Argument $a -WorkingDirectory $root
}

function New-LoopSettings([int]$limitMinutes) {
    New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes $limitMinutes)
}

function Register-LoopTask([string]$name, $action, $trigger, [int]$limitMinutes, [string]$text) {
    $p = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $p `
        -Settings (New-LoopSettings $limitMinutes) -Description $text -Force | Out-Null
    "registered $name"
}

function Every([int]$minutes, [int]$offsetMinutes) {
    $start = (Get-Date).Date.AddMinutes($offsetMinutes)
    New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes $minutes)
}

Register-LoopTask 'ShimmerResourceReading' (New-LoopAction 'resource_reading.py') (Every 30 13) 5 `
    'Shimmer loop: free RAM, disk, page file and helper processes every 30 minutes; ALERT.md below a floor.'
Register-LoopTask 'ShimmerMechanismWatchdog' (New-LoopAction 'mechanism_watchdog.py') (Every 15 7) 5 `
    'Shimmer loop: every 15 minutes, ALERT.md when a standing mechanism is overdue.'
Register-LoopTask 'ShimmerLaunchChain' (New-LoopAction 'launch_chain.py') (Every 3 1) 180 `
    'Shimmer loop: every 3 minutes, launches each planned step (chain.json beside launch.py) whose prerequisites are done; preflight first, one launch at a time, never a cap raised. A pass begins no launch after 50 min (but the seal after its request); worst case about 152 min, under the 180-minute limit.'
Register-LoopTask 'ShimmerBranchBackup' (New-LoopAction 'backup_guarded.py' 'branches') (Every 60 50) 180 `
    'Shimmer loop: backup_private.py (all branches and tags to backup-private) every hour; ALERT.md on failure.'
Register-LoopTask 'ShimmerDriveBackup' (New-LoopAction 'drive_paced.py') (New-ScheduledTaskTrigger -Daily -At '03:30') 480 `
    'Shimmer loop: paced Google Drive archive of uncovered parts, daily; checks each archive against Drive.'
Register-LoopTask 'ShimmerBackupCoverage' (New-LoopAction 'backup_guarded.py' 'coverage') (New-ScheduledTaskTrigger -Daily -At '05:00') 120 `
    'Shimmer loop: backup_coverage.py daily; ALERT.md on an irreplaceable part not covered.'
Register-LoopTask 'ShimmerRestoreDrill' (New-LoopAction 'backup_guarded.py' 'drill') (New-ScheduledTaskTrigger -Daily -At '05:30') 120 `
    'Shimmer loop: restore_drill.py daily (writes only into a new drill folder); ALERT.md when it does not pass.'

$t = Get-ScheduledTask -TaskName 'ShimmerRecordsBackup' -ErrorAction SilentlyContinue
if ($t) {
    Set-ScheduledTask -TaskName 'ShimmerRecordsBackup' -Action (New-LoopAction 'backup_guarded.py' 'records') | Out-Null
    'ShimmerRecordsBackup action now runs backup_guarded.py records (trigger and settings kept)'
} else {
    'ShimmerRecordsBackup not found; not created here'
}
