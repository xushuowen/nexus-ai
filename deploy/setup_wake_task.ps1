# Nexus AI - Daily wake-up at 5:58 AM
# Run this script as Administrator

$action    = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c echo Nexus wake'
$trigger   = New-ScheduledTaskTrigger -Daily -At '05:58AM'
$settings  = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest

Register-ScheduledTask `
    -TaskName   'NexusWakeUp' `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Principal  $principal `
    -Description 'Wake PC at 5:58 AM daily so Nexus can send morning report' `
    -Force

Write-Host "OK: Task created. PC will wake from sleep at 5:58 AM every day." -ForegroundColor Green
