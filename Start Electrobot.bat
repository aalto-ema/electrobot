@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Create the project virtual environment and install dependencies first.
    echo See README.md for setup instructions.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0run_app.py" %*
set "launch_status=%errorlevel%"
if not "%launch_status%"=="0" pause
exit /b %launch_status%
