@echo off
:: Auto-elevate to admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

netsh advfirewall firewall delete rule name="Nexus AI Port 8000" >nul 2>&1
netsh advfirewall firewall add rule name="Nexus AI Port 8000" dir=in action=allow protocol=TCP localport=8000

echo.
echo [OK] Port 8000 opened!
echo Phone: http://100.125.117.42:8000
echo.
pause
