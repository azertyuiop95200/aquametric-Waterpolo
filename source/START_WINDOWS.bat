@echo off
cd /d %~dp0
if not exist .venv (
  echo Creating Python virtual environment...
  py -m venv .venv 2>nul || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
start "" http://127.0.0.1:8000
python -m uvicorn main:app --host 127.0.0.1 --port 8000
exit /b 0
:error
echo.
echo Installation failed. Check that Python 3.11 or newer is installed.
pause
