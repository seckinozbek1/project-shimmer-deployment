# Registers the loop's checker and watch tasks (tools/loop/checker_tasks.py) as per-user Windows scheduled
# tasks (no admin), each started hidden through pyw.exe. Lead 14:14, 18 Nov; supervisor batch 12:30 item E.
# Kept apart from register_mechanism_tasks.ps1, which the launch-chain lane also edits. Re-running replaces
# the same tasks; it deletes no file.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\loop\register_checker_tasks.ps1
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pyw = 'C:\WINDOWS\pyw.exe'
$user = "$env:USERDOMAIN\$env:USERNAME"

function Register-CheckerTask([string]$name, [string]$kind, $trigger, [int]$limitMinutes, [string]$text) {
    $action = New-ScheduledTaskAction -Execute $pyw -WorkingDirectory $root `
        -Argument "-3.12 -X utf8 `"$root\tools\loop\checker_tasks.py`" $kind"
    $settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes $limitMinutes)
    $p = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $p -Settings $settings `
        -Description $text -Force | Out-Null
    "registered $name"
}

function Every([int]$minutes, [int]$offsetMinutes) {
    New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes($offsetMinutes)) `
        -RepetitionInterval (New-TimeSpan -Minutes $minutes)
}

Register-CheckerTask 'ShimmerComplianceCheck' 'compliance' (Every 120 17) 60 `
    'Shimmer loop (order 106): fresh headless compliance checker (claude -p, sonnet, medium) every 2 hours.'
Register-CheckerTask 'ShimmerFollowthroughCheck' 'followthrough' (New-ScheduledTaskTrigger -Daily -At '07:00') 60 `
    'Shimmer loop (order 103): fresh headless decision follow-through checker, daily.'
Register-CheckerTask 'ShimmerCheckerCheck' 'checkercheck' (New-ScheduledTaskTrigger -Daily -At '08:00') 60 `
    'Shimmer loop (orders 103, 106): checker of the checkers samples the newest reports, daily.'
Register-CheckerTask 'ShimmerDiskSweepDaily' 'disksweep' (New-ScheduledTaskTrigger -Daily -At '06:00') 150 `
    'Shimmer loop: disk_sweep.py --dry-run daily (never --apply; deletions need Seckin''s yes).'
Register-CheckerTask 'ShimmerLoopRecovery' 'recovery' (Every 10 3) 5 `
    'Shimmer loop: ALERT.md and FOR_SECKIN when the lead is silent 30 minutes and LOOP_STATE is not DONE; starts nothing.'
