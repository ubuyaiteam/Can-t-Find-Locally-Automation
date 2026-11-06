@echo off
REM Run once after updating the engine: installs the headless browser used for the exact Ubuy product-card check.
call .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
echo.
echo Updated. Start with run.bat
pause
