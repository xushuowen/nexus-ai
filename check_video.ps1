$f = Get-Item "C:\Users\Xushu\OneDrive\Desktop\Nexus AI - Neural Interface - Google Chrome 2026-02-24 14-25-57.mp4"
$mb = [math]::Round($f.Length / 1MB, 2)
Write-Host "Size: $mb MB"
Write-Host "Created: $($f.CreationTime)"
