@echo off
cd /d %~dp0
if not exist .venv (
  echo Creating Python virtual environment...
  py -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
for /f "delims=" %%i in ('powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '127.*' -and $_.InterfaceAlias -notmatch 'Loopback|vEthernet|VMware|VirtualBox'} | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress); Write-Output $ip"') do set LAN_IP=%%i
echo.
echo ===============================================
echo AquaMetric phone access
if defined LAN_IP (
  echo On your phone, connected to the SAME Wi-Fi, open:
  echo http://%LAN_IP%:8000
) else (
  echo Could not detect your Wi-Fi IP automatically.
  echo Run ipconfig and use your IPv4 address: http://IPv4:8000
)
echo Keep this window open while using the app.
echo Windows may ask you to allow Python through the firewall: allow Private networks.
echo ===============================================
echo.
start "" http://127.0.0.1:8000
python -m uvicorn main:app --host 0.0.0.0 --port 8000
exit /b 0
:error
echo.
echo Installation failed. Check that Python 3.11 or newer is installed.
pause
