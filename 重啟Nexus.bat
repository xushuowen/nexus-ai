@echo off
echo Killing process on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo Killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo Killing all Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1

ping 127.0.0.1 -n 4 >nul

echo Starting Nexus AI (HTTPS)...
cd /d C:\Users\Xushu\nexus
start "Nexus AI" python run.py

echo Done! Open: https://100.125.117.42:8000
