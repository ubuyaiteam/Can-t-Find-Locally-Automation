@echo off
call .venv\Scripts\activate
REM Make sure the headless browser (exact Ubuy product-card check) is installed - runs only when missing.
python -c "import playwright" 2>nul || (echo Installing Playwright browser support, one-time... & pip install "playwright>=1.44" & python -m playwright install chromium)
python -c "from playwright.sync_api import sync_playwright as s; p=s().start(); b=p.chromium.launch(); b.close(); p.stop()" 2>nul || (echo Installing Chromium for Playwright, one-time... & python -m playwright install chromium)
python -c "import pytrends" 2>nul || (echo Installing Google Trends support, one-time... & pip install "pytrends>=4.9.2")
start "" http://127.0.0.1:5000/opportunity/
python app.py
pause
