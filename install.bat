@echo off
where python >nul 2>nul || (echo Python not found. Install Python 3.10+ and tick "Add to PATH" & pause & exit /b 1)
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
echo.
echo Installed. Start with run.bat
pause
