Start-Process -FilePath 'pythonw.exe' -ArgumentList 'C:\Users\Xushu\nexus\run.py' -WorkingDirectory 'C:\Users\Xushu\nexus' -WindowStyle Hidden
Start-Sleep -Seconds 6
$p = Get-Process pythonw -ErrorAction SilentlyContinue
if ($p) { Write-Host "OK PID:" $p.Id } else { Write-Host "failed" }
